"""F3.02: snapshots existentes, duas cenas e duas versões; FFmpeg real, sem IA/rede."""
import copy,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
TMP=Path(tempfile.mkdtemp(prefix='ec-consistencia-'))
os.environ.update(DADOS=str(TMP),BANCO_ARQ=str(TMP/'studio.sqlite'),ESTEIRA_COMPLETA='0')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import banco as db
import estilos_codigo as ec
import produtor as pr
import projetos as pj
import qualidade as qd
import renderizador as rd
import series as sr

db.migrar()
class Consistencia(unittest.TestCase):
    def setUp(self):
        self.seg=patch.object(pr.ag,'segredos',return_value={});self.seg.start();self.addCleanup(self.seg.stop)
        s=sr.criar({'titulo':'Identidade','cenas_qtd':2,'duracao_alvo':10,'estilo':'animado2d'})
        self.sid=s['id']
        self.a=sr.criar_personagem({'serie_id':self.sid,'nome':'Ana','voz':'Kore','roupa':'#e63946'})
        self.b=sr.criar_personagem({'serie_id':self.sid,'nome':'Beto','voz':'Puck','roupa':'#2233aa'})
        self.cn=sr.criar_cenario({'serie_id':self.sid,'nome':'Sala','tipo':'casa','ceu':'#123456'})
        self.p1=self.episodio('Primeiro')
    def episodio(self,titulo):
        e=sr.criar_episodio(self.sid,{'titulo':titulo,'resumo':'Duas falas','produzir':False})
        p=pj.obter(e['projeto_id']);foto=p['dados']['serie']
        cenas=[ec.validar_cena({'id':f'c{i}','texto':'Olá, amigo.','personagem':pid,'voz':foto['personagens'][pid]['voz'],
                 'cenario_id':self.cn['id'],'elenco':[{'personagem_id':pid,'posicao':'centro'}]}) for i,pid in enumerate([self.a['id'],self.b['id']])]
        pj.mudar_dados(p['id'],lambda d,_p:d.update(cenas=cenas))
        return pj.obter(p['id'])
    def mudar_biblioteca(self):
        sr.salvar_rig(self.a['id'],{'dados':{'roupa':'#00ff00','voz':'Charon'}})
        sr.atualizar_cenario(self.cn['id'],{'nome':'Sala','tipo':'parque','ceu':'#abcdef'})
    def conferir(self,p):
        return pr.continuidade_serie(p['id'],p['dados']['cenas'],p['dados']['briefing'])
    def test_biblioteca_nova_nao_bloqueia_snapshot_comprovado(self):
        self.mudar_biblioteca();p2=self.episodio('Segundo')
        velho=pj.obter(self.p1['id'])
        self.assertEqual(velho['dados']['serie'],self.p1['dados']['serie'])
        self.assertEqual(velho['dados']['serie']['personagens'][self.a['id']]['voz'],'Kore')
        self.assertEqual(p2['dados']['serie']['personagens'][self.a['id']]['voz'],'Charon')
        self.assertNotEqual(velho['dados']['serie']['cenarios'],p2['dados']['serie']['cenarios'])
        achados=self.conferir(velho)
        aviso=next(x for x in achados if 'mudou de aparência' in x['descricao'])
        self.assertEqual(aviso['resolucao'],'snapshot_preservado');self.assertIn('hash',aviso['evidencia'])
        self.assertTrue(qd.veredito(qd.resumo(achados,{'ok':True}))['aprovado'])
    def test_snapshot_alterado_sem_troca_explicita_de_versao_bloqueia(self):
        pid=self.p1['id']
        def adulterar(d,_p):d['serie']['personagens'][self.a['id']]['roupa']='#ffffff'
        pj.mudar_dados(pid,adulterar)
        achados=self.conferir(pj.obter(pid))
        self.assertTrue(any('diverge' in x['descricao'] for x in achados))
        self.assertFalse(qd.veredito(qd.resumo(achados,{'ok':True}))['aprovado'])
    def test_voz_cenario_e_personagem_invalidos_continuam_bloqueados(self):
        p=copy.deepcopy(self.p1);c=p['dados']['cenas'][0];c['voz']='Puck';c['cenario_id']='nao-existe'
        p['dados']['cenas'][1]['personagem']='intruso'
        a=self.conferir(p);text=' '.join(x['descricao'] for x in a)
        self.assertIn('voz Puck',text);self.assertIn('cenário',text);self.assertIn('intruso',text)
        self.assertFalse(qd.veredito(qd.resumo(a,{'ok':True}))['aprovado'])
    def test_versao_historica_ausente_nao_recebe_excecao(self):
        self.mudar_biblioteca()
        db.executar('DELETE FROM personagens_versoes WHERE personagem_id=? AND versao=1',self.a['id'])
        a=self.conferir(self.p1)
        self.assertTrue(any('Não foi possível' in x['descricao'] and x['status']=='aberto' for x in a))
        self.assertFalse(qd.veredito(qd.resumo(a,{'ok':True}))['aprovado'])
    def test_contradicao_com_fato_aprovado_continua_bloqueada(self):
        def preparar(d,_p):
            d['serie']['biblia']=['Ana perdeu o medo do escuro.']
            d['cenas'][0]['texto']='Eu ainda tenho medo do escuro.'
        pj.mudar_dados(self.p1['id'],preparar)
        p=pj.obter(self.p1['id'])
        resposta={'contradicoes':[{'cena':p['dados']['cenas'][0]['id'],'fato':'Ana perdeu o medo do escuro.',
                                  'problema':'Ana afirma que ainda tem medo do escuro.'}]}
        with patch.object(pr.ag,'segredos',return_value={'gemini':'teste'}),patch.object(pr.ag,'gemini',return_value=resposta):
            a=self.conferir(p)
        self.assertTrue(any(x['descricao'].startswith('Bíblia:') and x['status']=='aberto' for x in a))
        self.assertFalse(qd.veredito(qd.resumo(a,{'ok':True}))['aprovado'])
    def render(self,p,prefixo):
        d=p['dados'];out=[]
        for i,c in enumerate(d['cenas']):
            pasta=TMP/(prefixo+str(i));pasta.mkdir()
            voz=d['serie']['personagens'][c['personagem']]['voz'];som=pasta/'fala.wav'
            subprocess.run(['ffmpeg','-nostdin','-y','-v','error','-f','lavfi','-i',f'sine=f={440 if voz=="Charon" else 220}:d=1',str(som)],check=True)
            c=dict(c,audio={'arquivo':str(som)})
            eid,c,img,audio,imgs,_=pr.preparar_cena(p['id'],i,c,d['cenas'],d['briefing'],dados=d)
            self.assertEqual(c['_cenario'],d['serie']['cenarios'][self.cn['id']])
            self.assertEqual(c['_personagens'][c['personagem']]['voz'],voz)
            arq=pasta/'cena.mp4';rd.rodar(ec.montar(eid,c,180,320,1,pasta,img,audio,arq,imagens_planos=imgs),tempo_max=30)
            self.assertAlmostEqual(rd.duracao(arq),1,delta=.2);out.append(rd.sha256(arq))
        return out
    def test_render_duas_cenas_preserva_identidade_apos_mudar_biblioteca(self):
        antes=self.render(self.p1,'antes')
        self.mudar_biblioteca();p2=self.episodio('Versão nova')
        depois=self.render(pj.obter(self.p1['id']),'depois')
        novo=self.render(p2,'novo')
        self.assertEqual(antes,depois)
        self.assertNotEqual(antes[0],novo[0])
        self.assertEqual(self.p1['dados']['briefing']['estilo'],p2['dados']['briefing']['estilo'])

if __name__=='__main__':unittest.main()
