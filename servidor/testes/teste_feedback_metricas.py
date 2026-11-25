"""F5.03: seis agentes, amostra e isolamento; não aplica configurações."""
import os,sys,tempfile,unittest
from pathlib import Path
TMP=Path(tempfile.mkdtemp(prefix='ec-feedback-'))
os.environ.update(DADOS=str(TMP),BANCO_ARQ=str(TMP/'studio.sqlite'))
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import banco as db
import aprendizado as ap
import coordenador as co
db.migrar()
class Feedback(unittest.TestCase):
    def setUp(self):db.executar('DELETE FROM aprendizado_snapshots')
    def gravar(self,i,g,canal='c1',vt='cortes'):
        ap._gravar_retrato('rede','youtube',str(i),{}, {'views':100 if g=='A' else 20},1000,2000,
            publicacao={'vertente':vt,'canal':canal,'gancho':g,'post':str(i),'render_sha':'sha'+str(i)})
    def test_vazio_seis_agentes_dados_insuficientes_sem_mutar(self):
        from unittest.mock import patch
        with patch.object(co,'criar_memoria',side_effect=AssertionError('não aplica')),patch.object(db,'kv_gravar',side_effect=AssertionError('não muda config')):
            r=co.feedback_metricas()
        self.assertEqual({x['agente'] for x in r},{'agente1','agente2','agente3','agente4','agente5','agente6'})
        self.assertTrue(all(x['estado']=='dados_insuficientes' for x in r))
    def test_amostra_por_valor_contexto_e_evidencia(self):
        for i in range(ap.MIN_AMOSTRAS*2):self.gravar(i,'A' if i<ap.MIN_AMOSTRAS else 'B')
        a=next(x for x in co.feedback_metricas() if x['agente']=='agente1')
        self.assertEqual(a['estado'],'hipotese_observacional');self.assertEqual(len(a['snapshots']),ap.MIN_AMOSTRAS*2)
        self.assertIn('não prova causa',a['recomendacao']);self.assertEqual(a['comparacoes'][0]['valor'],'A')
        self.assertTrue(all(x['estado']=='dados_insuficientes' for x in co.feedback_metricas() if x['agente'] in ('agente3','agente4')))
    def test_nao_mistura_canal_ou_vertente_para_completar_amostra(self):
        for i in range(ap.MIN_AMOSTRAS*2):self.gravar(i,'A' if i<ap.MIN_AMOSTRAS else 'B',canal='c1' if i<ap.MIN_AMOSTRAS else 'c2')
        self.assertTrue(all(x['estado']=='dados_insuficientes' for x in co.feedback_metricas()))
        db.executar('DELETE FROM aprendizado_snapshots')
        for i in range(ap.MIN_AMOSTRAS*2):self.gravar(i,'A' if i<ap.MIN_AMOSTRAS else 'B',vt='cortes' if i<ap.MIN_AMOSTRAS else 'criacao_ia')
        self.assertTrue(all(x['estado']=='dados_insuficientes' for x in co.feedback_metricas()))
if __name__=='__main__':unittest.main()
