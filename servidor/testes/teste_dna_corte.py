"""F2.04: perfis antigos, isolamento de canal e render real pelo A1/manual."""
import copy,json,os,random,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
TMP=Path(tempfile.mkdtemp(prefix='ec-dna-'))
os.environ.update(DADOS=str(TMP),BANCO_ARQ=str(TMP/'studio.sqlite'),ESTEIRA_COMPLETA='0')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import agente as ag
import banco as db
import modelos as mo
import perfis as pf
import renderizador as rd

db.migrar()
class DnaCorte(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'DNA_CORTE':'1'});self.env.start();self.addCleanup(self.env.stop)
        self.p=pf.salvar({'nome':'Canal DNA','templates':['padrao'],'cores':{'primaria':'#123456'},
                         'dna_corte':{'fonte':'Inter','legenda':'simples','zoom':1.3,'ritmo':'dinamico'}})
    def test_legado_salva_duplica_restaura_sem_migracao(self):
        antigo=pf.salvar({'nome':'Antigo'})
        dados=pf._dados();dados['perfis'][antigo['id']].pop('dna_corte');pf.pg._gravar(pf.ARQ,dados)
        self.assertEqual(pf.obter(antigo['id'])['dna_corte'],{})
        self.assertEqual(pf.duplicar(antigo['id'])['dna_corte'],{})
        p=pf.salvar(dict(pf.obter(antigo['id']),dna_corte={'zoom':1.1}),antigo['id'])
        self.assertEqual(p['versao'],2)
        self.assertEqual(pf.restaurar(p['id'],1)['dna_corte'],{})
    def test_flag_off_limites_e_isolamento(self):
        t=mo.tpl(mo.limpar(mo.BASE|{'id':'x'}));original=copy.deepcopy(t)
        with patch.dict(os.environ,{'DNA_CORTE':'0'}):pf.aplicar_ao_tpl(t,self.p,random.Random(1))
        self.assertEqual(t['zoom'],original['zoom']);self.assertNotIn('ritmo',t)
        pf.aplicar_ao_tpl(t,self.p,random.Random(1));self.assertEqual(t['zoom'],1.3)
        outro=pf.salvar({'nome':'Outro'});t2=mo.tpl(mo.limpar(mo.BASE|{'id':'x'}))
        pf.aplicar_ao_tpl(t2,outro,random.Random(1));self.assertNotIn('ritmo',t2)
        self.assertEqual(pf.limpar_dna({'zoom':float('nan'),'fonte':'x,ASS','ritmo':'x'}),{})
        self.assertEqual(pf.limpar_dna({'zoom':10})['zoom'],1.6)
        self.assertEqual(pf.limpar_dna({'zoom':.1})['zoom'],1)
    def test_ritmo_ass_muda_blocos_sem_mudar_timestamps_fonte(self):
        palavras=[(i*.3,i*.3+.25,w) for i,w in enumerate('um dois tres seis sete oito'.split())]
        t=mo.tpl(mo.limpar(mo.BASE|{'id':'x'}));t.update(legenda='simples',gancho=False)
        a=ag.montar_ass(palavras,0,3,dict(t,ritmo='calmo'),' ',320,180)
        b=ag.montar_ass(palavras,0,3,dict(t,ritmo='dinamico'),' ',320,180)
        self.assertLess(a.count('Dialogue:'),b.count('Dialogue:'))
        self.assertIn('Style: Leg,Inter,',b)
        self.assertEqual(palavras[0],(0,.25,'um'))
    def test_a1_aplica_dna_no_render_e_na_tentativa_sem_legenda(self):
        base=TMP/'fonte.mp4'
        subprocess.run(['ffmpeg','-nostdin','-y','-v','error','-f','lavfi','-i','testsrc2=s=320x180:r=30:d=4',
                        '-f','lavfi','-i','sine=f=440:d=4','-c:v','libx264','-c:a','aac',str(base)],check=True)
        capturados=[];editar=ag.editar
        def render(video,c,palavras,tpl,saida,pasta):
            capturados.append(copy.deepcopy(tpl));return editar(video,c,palavras,tpl,saida,pasta)
        pre={'palavras':[], 'itens':[{'ini':0,'fim':3,'gancho':'Teste','titulo':'Teste','sem_legenda':True}]}
        with patch.dict(mo.FORMATOS,{'9:16':(320,180)}),patch.object(ag,'editar',side_effect=render),\
             patch.object(ag,'ajustar_camera',return_value=None),patch.object(ag,'etapa'),\
             patch.object(ag,'ajustar_corte',return_value=None),\
             patch.object(ag,'inspecionar_corte',side_effect=[{'erros':['forcar retry']},{'erros':[]}]),\
             patch.object(ag,'veredito_corte',side_effect=lambda qa:{'aprovado':not qa['erros'],'motivos':qa['erros']}):
            cortes=ag.processar_video({'id':'teste-dna','titulo':'Teste'},1,(base,{'duration':4},None),
                                      ajustes={'perfil':self.p['id'],'variar':['zoom']},pre=pre)
        self.assertEqual(len(capturados),2)
        for t in capturados:
            self.assertEqual((t['zoom'],t['ritmo'],t['legenda']),(1.3,'dinamico','nenhuma'))
        self.assertEqual(cortes[0]['perfil'],self.p['id'])
        self.assertTrue(any('DNA' in x for x in cortes[0]['variacoes']))
        self.assertAlmostEqual(rd.duracao(ag.pg.VIDEOS/(cortes[0]['video']+'.mp4')),3,delta=.2)

    def test_escolha_manual_do_template_com_dna_do_canal(self):
        import gameplay_indexer as gi
        base=TMP/'manual.mp4'
        subprocess.run(['ffmpeg','-nostdin','-y','-v','error','-f','lavfi','-i','testsrc2=s=320x180:r=30:d=4',
                        '-f','lavfi','-i','sine=f=440:d=4','-c:v','libx264','-c:a','aac',str(base)],check=True)
        rel={'id':'dna-manual','arquivo':str(base),'duracao':4,'titulo':'Manual','palavras':[],
             'eventos':[],'fonte':'arquivo','historia':'tutorial','direitos':{'origem':'meu'},
             'destaques':[{'id':'d1','ini':0,'fim':3,'ganchos':[],'porque':'teste','eventos':[]}]}
        class Ctx:
            dados={'gid':rel['id'],'destaque':'d1','perfil':self.p['id'],'modelo':'tela-cheia'}
            def progresso(self,*args):pass
        capturados=[];editar=ag.editar
        def render(video,c,palavras,tpl,saida,pasta):
            capturados.append(copy.deepcopy(tpl));return editar(video,c,palavras,tpl,saida,pasta)
        with patch.object(gi,'ler',return_value=rel),patch.dict(mo.FORMATOS,{'9:16':(320,180)}),\
             patch.object(ag,'editar',side_effect=render),patch.object(ag,'inspecionar_corte',return_value={}),\
             patch.object(ag,'veredito_corte',return_value={'aprovado':True,'motivos':[]}):
            r=gi.job_cortar(Ctx())['resultado']
        corte=next(c for c in ag.estado()['cortes'] if c['id']==r['corte'])
        self.assertEqual(corte['modelo'],'tela-cheia')
        self.assertEqual(capturados[0]['zoom'],1.3)
        self.assertEqual(capturados[0]['cor_marca'],'#123456')
        self.assertIn('DNA do corte',str(corte['variacoes']))
        self.assertAlmostEqual(rd.duracao(ag.pg.VIDEOS/(corte['video']+'.mp4')),3,delta=.2)

if __name__=='__main__':unittest.main()
