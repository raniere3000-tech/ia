"""F5.01: filtros não criam dados e leituras cumulativas não são somadas."""
import os,sys,tempfile,unittest
from pathlib import Path
TMP=Path(tempfile.mkdtemp(prefix='ec-indicadores-'))
os.environ.update(DADOS=str(TMP),BANCO_ARQ=str(TMP/'studio.sqlite'))
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import banco as db
import aprendizado as ap
db.migrar()
class Indicadores(unittest.TestCase):
    def setUp(self):db.executar('DELETE FROM aprendizado_snapshots')
    def gravar(self,item,vt='cortes',canal='c1',rede='youtube',views=0,t=1700000000,ref=None):
        return ap._gravar_retrato('rede',rede,item,{}, {'views':views} if views is not None else {'comentarios':2},t-100,t,
            publicacao={'post':item,'ref':ref or item,'render_sha':'sha1','vertente':vt,'canal':canal})
    def test_ultima_medicao_sem_somar_acumulados_e_sem_mutacao(self):
        self.gravar('p1',views=10);self.gravar('p1',views=20,t=1700000100)
        self.gravar('outro-id-local',views=20,t=1700000100,ref='p1')
        a=ap.indicadores();self.assertEqual(a['publicacoes'],1);self.assertEqual(a['medidas']['views']['valor'],20)
        antes=db.todos('SELECT * FROM aprendizado_snapshots');ap.indicadores();self.assertEqual(db.todos('SELECT * FROM aprendizado_snapshots'),antes)
    def test_vertente_rede_canal_periodo_combinados(self):
        self.gravar('p1');self.gravar('p2',vt='criacao_ia',canal='c2',rede='instagram',views=99)
        a=ap.indicadores({'vertente':'criacao_ia','rede':'instagram','canal':'c2','de':'2023-11-14','ate':'2023-11-14'})
        self.assertEqual(a['publicacoes'],1);self.assertEqual(a['medidas']['views']['valor'],99)
        self.assertEqual(ap.indicadores({'canal':'c1','vertente':'criacao_ia'})['publicacoes'],0)
        self.assertEqual(ap.indicadores({'de':'2023-11-15'})['publicacoes'],0)
    def test_zero_real_ausencia_e_legado(self):
        self.gravar('p1');self.gravar('p2',views=None)
        ap._gravar_retrato('rede','youtube','legado',{}, {'curtidas':2},None,None)
        a=ap.indicadores();self.assertEqual(a['medidas']['views'],{'valor':0,'amostras':1})
        self.assertIsNone(a['medidas']['retencao']['valor']);self.assertEqual(a['medidas']['comentarios']['valor'],2)
        self.assertEqual(ap.indicadores({'vertente':'indisponivel'})['publicacoes'],1)
        self.assertEqual(ap.indicadores({'de':'2023-11-14'})['publicacoes'],2)
    def test_filtros_invalidos_e_consulta_sem_http(self):
        from unittest.mock import patch
        import postagem as pg
        for f in [{'rede':'inventada'},{'vertente':'agente8'},{'de':'2025-01-01','ate':'2024-01-01'}]:
            with self.assertRaises(ap.ErroAprendizado):ap.indicadores(f)
        with patch.object(pg,'http',side_effect=AssertionError('sem rede')):self.assertEqual(ap.indicadores()['publicacoes'],0)
if __name__=='__main__':unittest.main()
