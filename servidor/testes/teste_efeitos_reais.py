"""F2.02: compara frames renderizados, plano e recibos, com mídia própria registrada."""
import json,os,sys,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
TMP=Path(tempfile.mkdtemp(prefix='ec-efeitos-reais-'))
os.environ.update(DADOS=str(TMP),BANCO_ARQ=str(TMP/'studio.sqlite'),ESTEIRA_COMPLETA='0')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import banco as db
import contratos as ct
import editor_ia as ed
import projetos as pj
import renderizador as rd
import agente as ag

db.migrar()
BASE=TMP/'base.mp4'
subprocess.run(['ffmpeg','-nostdin','-y','-v','error','-f','lavfi','-i','testsrc2=s=160x90:r=30:d=3',
                '-f','lavfi','-i','sine=f=440:d=3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(BASE)],check=True)

def frame(p,t):
    return subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(p),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])

def dif(a,b):
    return sum(abs(x-y) for x,y in zip(a,b))/max(1,min(len(a),len(b)))


class EfeitosReais(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'A5_EFEITOS_REAIS':'1'});self.env.start();self.addCleanup(self.env.stop)
    def plano(self,efeitos):
        return ct.validar_plano({'clips':[{'source':'principal','in_ms':0,'out_ms':3000}], 'effects':efeitos,'target_aspect_ratio':'16:9'})
    def render(self,nome,efeitos,ass=None):
        p=TMP/(nome+'.mp4');ed._finalizar_efeitos(self.plano(efeitos),BASE,p,ass=ass);return p

    def test_zoom_so_no_intervalo_comprovado_por_frames(self):
        controle=self.render('controle',[])
        saida=self.render('zoom',[{'tipo':'zoom','nivel':1.4,'ini_ms':1000,'fim_ms':2000}])
        antes=dif(frame(controle,.3),frame(saida,.3));durante=dif(frame(controle,1.5),frame(saida,1.5));depois=dif(frame(controle,2.6),frame(saida,2.6))
        print(f'Zoom: diferença média RGB antes={antes:.2f}, durante={durante:.2f}, depois={depois:.2f}')
        self.assertGreater(durante,10)
        # H.264 usa predição entre quadros; fora do efeito a diferença deve ser
        # pequena em relação à mudança visual medida no intervalo aplicado.
        self.assertLess(max(antes,depois),durante*.2)
        r=json.loads(saida.with_suffix('.efeitos.json').read_text())
        self.assertEqual((r['planejados'],r['aplicados'],r['falhas']),(1,1,0))
        self.assertEqual(r['arquivo_sha'],rd.sha256(saida))

    def test_broll_registrado_e_licenca_obrigatoria(self):
        foto=TMP/'blue.png'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=blue:s=160x90','-frames:v','1',str(foto)],check=True)
        aid=pj.registrar_asset(foto,'blue.png','image/png')['asset']['id']
        e={'tipo':'broll','asset':aid,'direitos':'meu','ini_ms':1000,'fim_ms':2000}
        saida=self.render('broll',[e]);q=frame(saida,1.5)
        self.assertGreater(sum(q[2::3])/len(q[2::3]),200)
        self.assertLess(sum(q[0::3])/len(q[0::3]),35)
        with self.assertRaises(ct.ErroContrato):self.plano([dict(e,direitos='desconhecido')])
        with patch.dict(os.environ,{'A5_EFEITOS_REAIS':'0'}),self.assertRaises(ct.ErroContrato):self.plano([e])

    def test_legenda_real_e_noop_nao_conta_como_efeito(self):
        ass=TMP/'caption.ass';t=dict(ag.PADRAO['cortes']['template'],gancho=False,legenda='destaque')
        ass.write_text(ag.montar_ass([(0.5,1.8,'PALAVRA')],0,3,t,'',160,90))
        cap={'tipo':'caption','ligado':1,'tamanho':.07,'altura':.5}
        saida=self.render('legenda',[cap],ass)
        self.assertGreater(dif(frame(BASE,1),frame(saida,1)),1)
        noop=self.render('noop',[{'tipo':'zoom','nivel':1,'ini_ms':0,'fim_ms':3000}])
        self.assertEqual(json.loads(noop.with_suffix('.efeitos.json').read_text())['aplicados'],0)

    def test_falha_nao_substitui_video_anterior(self):
        saida=TMP/'anterior.mp4';saida.write_bytes(b'VERSAO ANTERIOR')
        p=self.plano([{'tipo':'broll','asset':'a'*16,'direitos':'meu','ini_ms':0,'fim_ms':1000}])
        with self.assertRaises(pj.ErroProjeto):ed._finalizar_efeitos(p,BASE,saida)
        self.assertEqual(saida.read_bytes(),b'VERSAO ANTERIOR')
        self.assertEqual(json.loads(saida.with_suffix('.efeitos.json').read_text())['status'],'falhou')

    def test_editor_nao_declara_efeitos_sem_recibo_do_render(self):
        import pipeline as pl
        r=pl.criar('manual','sem-recibo','Teste')
        with self.assertRaises(FileNotFoundError):
            ed.rodar(r['id'],'sem-recibo',self.plano([]),lambda p:BASE,lambda p:{})

    def test_executor_do_corte_aplica_fade_e_emite_recibo(self):
        t=dict(ag.PADRAO['cortes']['template'],resolucao=360,gancho=False,legenda='nenhuma')
        plano=self.plano([{'tipo':'fade','entrada_ms':300,'saida_ms':300},{'tipo':'zoom','nivel':1.2,'ini_ms':1000,'fim_ms':2000}])
        saida=TMP/'corte.mp4'
        ed.executar_corte(plano,BASE,{'ini':0,'fim':3,'gancho':''},[],t,saida,TMP)
        self.assertAlmostEqual(rd.duracao(saida),3,delta=.25)
        recibo=json.loads(saida.with_suffix('.efeitos.json').read_text())
        self.assertEqual(recibo['aplicados'],2)
        q0=frame(saida,.03);q1=frame(saida,.6)
        self.assertLess(sum(q0)/len(q0),sum(q1)/len(q1)*.6)

    def test_montagem_com_velocidade_por_trecho_e_audio_sincronizado(self):
        saida = TMP / 'velocidade.mp4'
        plano = dict(self.plano([]), schema_version=ct.SCHEMA_TIMELINE, clips=[
            {'in_ms': 0, 'out_ms': 1000},
            {'in_ms': 1500, 'out_ms': 2100, 'speed': 0.5},
            {'in_ms': 2400, 'out_ms': 3000, 'speed': 2},
        ], protected_hook={'in_ms': 0, 'out_ms': 900})
        plano = ct.validar_plano(plano)
        with patch.dict(ct.ASPECTOS, {'16:9': (160, 90)}):
            ed.executar_importado(plano, BASE, saida)
        streams = {s['codec_type']: float(s['duration']) for s in rd.sonda(saida)['streams']}
        self.assertAlmostEqual(streams['video'], 2.5, delta=0.12)
        self.assertAlmostEqual(streams['audio'], streams['video'], delta=0.10)
        self.assertGreater(dif(frame(BASE, 1.25), frame(saida, 1.25)), 10)
        palavra = ed.palavras_saida(plano, [(1.6, 1.7, 'palavra')])[0]
        self.assertAlmostEqual(palavra[0], 1.2)
        self.assertAlmostEqual(palavra[1], 1.4)
        recibo = json.loads(saida.with_suffix('.efeitos.json').read_text())
        self.assertEqual(recibo['arquivo_sha'], rd.sha256(saida))
        self.assertEqual(recibo['montagem']['trechos'], plano['clips'])
        subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(saida), '-f', 'null', '-'], check=True)

    def test_montagem_sem_audio_preserva_gancho_de_abertura(self):
        fonte = TMP / 'silencioso.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(BASE), '-an', '-c:v', 'copy', str(fonte)], check=True)
        tpl = dict(ag.PADRAO['cortes']['template'], resolucao=360, gancho=True, legenda='nenhuma', formato='16:9')
        corte = {'ini': 0, 'fim': 3, 'gancho': 'GANCHO INTEIRO'}
        with patch.dict(os.environ, {'A5_EDITOR_PRO': '1'}):
            plano = ed.plano_do_corte(corte, tpl, 3)
        self.assertEqual(plano['protected_hook'], {'in_ms': 0, 'out_ms': 3000})
        _, mudancas = ed.corrigir(plano, [{'acao': 'ajustar_inicio', 'delta_ms': 400}])
        self.assertEqual(mudancas, [])
        plano['effects'].append({'tipo': 'fade', 'saida_ms': 200})
        saida = TMP / 'silencioso-editado.mp4'
        ed.executar_corte(plano, fonte, corte, [], tpl, saida, TMP)
        self.assertFalse(ed.tem_audio(saida))
        self.assertAlmostEqual(rd.duracao(saida), 3, delta=0.12)
        self.assertEqual(json.loads(saida.with_suffix('.efeitos.json').read_text())['montagem']['gancho_protegido'],
                         plano['protected_hook'])

if __name__=='__main__':unittest.main()
