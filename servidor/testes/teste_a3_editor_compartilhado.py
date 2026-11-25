"""F3.03: A3 usa A5/A4 existentes, com render real e certificado por SHA."""
import copy,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
TMP=Path(tempfile.mkdtemp(prefix='ec-a3-a5-'))
os.environ.update(DADOS=str(TMP),BANCO_ARQ=str(TMP/'studio.sqlite'),ESTEIRA_COMPLETA='0',PIPELINE_V2='0')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import banco as db
import contratos as ct
import editor_ia as ed
import fila
import pipeline as pl
import postagem as pg
import produtor as pr
import projetos as pj
import qualidade as qd
import renderizador as rd

db.migrar();pr.iniciar()
BASE=TMP/'cena.mp4'
subprocess.run(['ffmpeg','-nostdin','-y','-v','error','-f','lavfi','-i','testsrc2=s=160x284:r=30:d=1.5',
                '-f','lavfi','-i','sine=f=440:d=1.5','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(BASE)],check=True)
def frame(p,t):
    return subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(p),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
def diferenca(a,b):return sum(abs(x-y) for x,y in zip(a,b))/len(a)

class Compartilhado(unittest.TestCase):
    def setUp(self):
        for p in [patch.dict(os.environ,{'A3_EDICAO_COMPARTILHADA':'1','A5_EFEITOS_REAIS':'0'}),
                  patch.dict(pr.ec.FORMATOS,{'9:16':(160,284)}),patch.dict(ct.ASPECTOS,{'9:16':(160,284)})]:
            p.start();self.addCleanup(p.stop)
    def projeto(self,tipo='história narrada'):
        p=pr.novo({'briefing':{'tema':'Por que o céu muda de cor?','tipo':tipo,'estilo':'quadro_branco','formato':'9:16'},
                    'roteiro':{'titulo':'Teste','gancho':'Você sabia?','cenas':[{'texto':'O céu muda de cor.','titulo':'Pergunta'},
                                  {'texto':'A luz atravessa o ar.','titulo':'Explicação'}]}})
        def preparar(d,_p):
            for c in d['cenas']:c['clipe']={'arquivo':str(BASE),'dur':1.5}
            d['qualidade']=qd.resumo([],None)
        pj.mudar_dados(p['id'],preparar)
        job=fila.enfileirar('agente3.produzir',agente='agente3',projeto=p['id'],dados={'projeto':p['id'],'etapa':'final'})
        return pj.obter(p['id']),fila.Contexto(job)
    def montar(self,p,ctx):
        resultado=pr.etapa_final(ctx,p['id'],p,p['dados']['briefing'])
        return pj.obter(p['id']),resultado
    def test_historia_renderiza_fade_e_a4_certifica_sha_real(self):
        p,ctx=self.projeto();pronto,r=self.montar(p,ctx)
        self.assertEqual(pronto['status'],'ready_for_review',r)
        render=pronto['dados']['render'];arq=Path(db.um('SELECT arquivo FROM renders WHERE id=?',render['id'])['arquivo'])
        recibo=json.loads(arq.with_suffix('.efeitos.json').read_text())
        self.assertEqual(recibo['arquivo_sha'],rd.sha256(arq));self.assertEqual(recibo['aplicados'],1)
        self.assertEqual(recibo['sem_alteracao'],1)  # reframe manter não conta como efeito
        self.assertEqual(pronto['dados']['edicao_compartilhada'],recibo)
        self.assertTrue(pronto['dados']['diretor']['certificado'])
        self.assertEqual(pronto['dados']['diretor']['sha'],recibo['arquivo_sha'])
        run=pl.obter(pronto['dados']['diretor']['esteira'])
        self.assertEqual(run['dados']['execucao_efeitos']['arquivo_sha'],recibo['arquivo_sha'])
        self.assertEqual(ct.hash_plano(pl.ultimo_plano(run['id'])),recibo['plano_hash'])
        self.assertLess(sum(frame(arq,.02))/len(frame(arq,.02)),sum(frame(BASE,.02))/len(frame(BASE,.02))*.75)
        self.assertEqual(pg.posts(),[])
    def test_curiosidade_aplica_zoom_pontual_no_mesmo_motor(self):
        p,ctx=self.projeto('curiosidades');plano=ed.plano_importado(3,'9:16')
        plano['effects'].append({'tipo':'zoom','nivel':1.4,'ini_ms':500,'fim_ms':2200})
        pj.mudar_dados(p['id'],lambda d,_p:d.update(plano_edicao=plano))
        p=pj.obter(p['id']);pronto,r=self.montar(p,ctx)
        self.assertEqual(pronto['status'],'ready_for_review',r)
        arq=Path(db.um('SELECT arquivo FROM renders WHERE id=?',pronto['dados']['render']['id'])['arquivo'])
        controle=TMP/(p['id']+'-controle.mp4');rd.concatenar([BASE,BASE],controle,TMP)
        self.assertGreater(diferenca(frame(arq,.9),frame(controle,.9)),8)
        self.assertLess(diferenca(frame(arq,.2),frame(controle,.2)),8)
        self.assertEqual(pronto['dados']['edicao_compartilhada']['aplicados'],1)
    def test_opiniao_pendente_nao_burla_diretor_nem_emite_certificado(self):
        p,ctx=self.projeto();achado=qd._problema('visual_ia','baixa','Rosto cortado','Abrir plano',natureza='julgamento')
        with patch.object(pr,'visao_ia',return_value=[achado]):pronto,r=self.montar(p,ctx)
        self.assertNotEqual(pronto['status'],'ready_for_review')
        self.assertFalse(pronto['dados'].get('render'))
        self.assertEqual(pronto['dados']['diretor']['veredito'],'refazendo')
        self.assertFalse(pronto['dados']['diretor'].get('certificado'))
        self.assertEqual(pg.posts(),[])
    def test_falha_real_do_efeito_preserva_saida_e_render_anterior(self):
        p,ctx=self.projeto();destino=TMP/(p['id']+'-anterior.mp4');destino.write_bytes(b'anterior')
        plano=ed.plano_importado(1.5);plano['effects'].append({'tipo':'caption','ligado':1,'tamanho':.06,'altura':.8})
        pj.mudar_dados(p['id'],lambda d,_p:d.update(plano_edicao=plano,render={'sha':'anterior'}))
        with self.assertRaises(ct.ErroContrato):pr._editar_montagem(ctx,p['id'],p['dados']['briefing'],BASE,destino)
        self.assertEqual(destino.read_bytes(),b'anterior')
        dados=pj.obter(p['id'])['dados'];self.assertEqual(dados['render']['sha'],'anterior')
        self.assertEqual(dados['edicao_compartilhada']['status'],'falhou')
    def test_timeline_nao_muda_sem_refazer_storyboard(self):
        p,ctx=self.projeto();plano=ed.plano_importado(1)
        pj.mudar_dados(p['id'],lambda d,_p:d.update(plano_edicao=plano))
        with self.assertRaisesRegex(ct.ErroContrato,'storyboard'):
            pr._editar_montagem(ctx,p['id'],p['dados']['briefing'],BASE,TMP/'proibido.mp4')
    def test_flag_desligada_preserva_fluxo_anterior(self):
        p,ctx=self.projeto()
        with patch.dict(os.environ,{'A3_EDICAO_COMPARTILHADA':'0'}),patch.object(ed,'executar_importado') as executor:
            pronto,r=self.montar(p,ctx)
        executor.assert_not_called();self.assertEqual(pronto['status'],'ready_for_review')
        self.assertNotIn('edicao_compartilhada',pronto['dados'])
    def test_analise_visual_real_filtra_confianca_e_mantem_bloqueio(self):
        p,ctx=self.projeto();cid=p['dados']['cenas'][0]['id']
        resposta={'pontos':[{'cena':cid,'plano':'p1','problema':'Rosto cortado','sugestao':'Abrir plano','confianca':.8},
                            {'cena':cid,'problema':'Talvez a cor','confianca':.3}]}
        with patch.object(pr.ag,'segredos',return_value={'gemini':'teste'}),patch.object(pr.ag,'gemini',return_value=resposta):
            a=pr.visao_ia(p['id'],BASE,rd.sha256(BASE),p['dados']['cenas'],dict(p['dados']['briefing'],qa_visao=True))
        self.assertEqual(len(a),1);self.assertEqual(a[0]['natureza'],'julgamento')
        self.assertIn('confiança 0.80',a[0]['evidencia'])
        self.assertFalse(qd.veredito(qd.resumo(a,{'ok':True}))['aprovado'])
    def test_cancelamento_preserva_arquivo_anterior(self):
        p,ctx=self.projeto();destino=TMP/(p['id']+'-cancelado.mp4');destino.write_bytes(b'anterior')
        with patch.object(ctx,'cancelado',return_value=True),self.assertRaises(InterruptedError):
            pr._editar_montagem(ctx,p['id'],p['dados']['briefing'],BASE,destino)
        self.assertEqual(destino.read_bytes(),b'anterior')
    def test_recibo_com_sha_falso_nao_libera_montagem(self):
        import shutil
        p,ctx=self.projeto();destino=TMP/(p['id']+'-recibo-falso.mp4')
        def falso(plano,fonte,saida,**kwargs):
            shutil.copyfile(fonte,saida)
            saida.with_suffix('.efeitos.json').write_text(json.dumps({'status':'concluido','arquivo_sha':'falso','plano_hash':ct.hash_plano(plano)}))
        with patch.object(ed,'executar_importado',side_effect=falso),self.assertRaisesRegex(rd.ErroRender,'comprovar'):
            pr._editar_montagem(ctx,p['id'],p['dados']['briefing'],BASE,destino)
        self.assertFalse(pj.obter(p['id'])['dados'].get('render'))
        self.assertEqual(pj.obter(p['id'])['dados']['edicao_compartilhada']['status'],'falhou')

if __name__=='__main__':unittest.main()
