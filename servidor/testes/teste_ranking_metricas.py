"""F5.02: comparação por plataforma e métrica, contexto imutável."""
import json,os,sys,tempfile,unittest
from pathlib import Path
TMP=Path(tempfile.mkdtemp(prefix='ec-ranking-'))
os.environ.update(DADOS=str(TMP),BANCO_ARQ=str(TMP/'studio.sqlite'))
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import banco as db
import aprendizado as ap
db.migrar()
class Ranking(unittest.TestCase):
    def setUp(self):db.executar('DELETE FROM aprendizado_snapshots')
    def guardar(self,item,m,rede='youtube',ctx=None):
        ap._gravar_retrato('rede',rede,item,{},m,1000,2000,publicacao=ctx)
    def test_metrica_ausente_nao_compete_com_zero_e_redes_separadas(self):
        self.guardar('a',{'views':0});self.guardar('b',{'views':10})
        self.guardar('c',{'curtidas':90});self.guardar('ig',{'curtidas':100},'instagram')
        d={g['rede']:g for g in ap.indicadores()['destaques']}
        self.assertEqual([x['item'] for x in d['youtube']['videos']],['b','a'])
        self.assertEqual(d['youtube']['sem_metrica'],1);self.assertEqual(d['instagram']['videos'],[])
        c={g['rede']:g for g in ap.indicadores({'metrica':'curtidas'})['destaques']}
        self.assertEqual(c['youtube']['videos'][0]['item'],'c')
    def test_rastreio_conserva_fonte_render_capa_gancho_efeitos_e_horario(self):
        ctx={'render_sha':'sha-v1','gancho':'Gancho completo','modelo':'T1','capa_selecionada':{'sha':'thumb1'},'publicado_em':1000,
             'efeitos':{'efeitos':[{'tipo':'zoom','status':'aplicado'},{'tipo':'reframe','status':'noop'}]}}
        self.guardar('a',{'views':0},ctx=ctx)
        ctx.update(render_sha='sha-v2',gancho='Mudou')
        v=ap.indicadores()['destaques'][0]['videos'][0]
        self.assertEqual(v['publicacao']['render_sha'],'sha-v1');self.assertEqual(v['publicacao']['gancho'],'Gancho completo')
        self.assertEqual(v['publicacao']['capa_selecionada']['sha'],'thumb1');self.assertEqual(v['medido_em'],2000)
        self.assertEqual(v['fonte'],'rede');self.assertEqual(v['publicacao']['publicado_em'],1000)
    def test_limite_e_legado_nao_inventam_contexto(self):
        for i in range(15):self.guardar(str(i),{'views':i})
        g=ap.indicadores()['destaques'][0];self.assertEqual(len(g['videos']),10)
        self.assertTrue(all(x['publicacao'] is None for x in g['videos']))
        with self.assertRaises(ap.ErroAprendizado):ap.indicadores({'metrica':'retencao'})
if __name__=='__main__':unittest.main()
