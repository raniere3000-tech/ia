"""F5.04: hipótese versionada, autorização, amostra nova, contexto e rollback."""
import os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
TMP=Path(tempfile.mkdtemp(prefix='ec-memoria-metricas-'))
os.environ.update(DADOS=str(TMP),BANCO_ARQ=str(TMP/'studio.sqlite'))
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import banco as db
import aprendizado as ap
import coordenador as co
db.migrar()
class Memoria(unittest.TestCase):
    def setUp(self):
        for t in ('aprendizado_snapshots','aprendizado_experimentos','coordenador_memorias','coordenador_memoria_versoes','coordenador_memoria_evidencias'):db.executar('DELETE FROM '+t)
        db.kv_gravar('agente7.sugestoes_dispensadas',[])
        for i in range(ap.MIN_AMOSTRAS*2):self.observar(str(i),'A' if i<ap.MIN_AMOSTRAS else 'B',publicado=1000)
    def observar(self,id,gancho,canal='c1',vt='cortes',publicado=None):
        ap._gravar_retrato('rede','youtube',id,{}, {'views':100 if gancho=='A' else 20},publicado or time.time(),time.time(),
            publicacao={'vertente':vt,'canal':canal,'gancho':gancho,'post':id,'render_sha':'sha'+id,'publicado_em':publicado or time.time()})
    def propor(self):
        s=next(x for x in co.sugestoes()['sugestoes'] if x['id'].startswith('metricas.agente1'))
        return co.propor_sugestao(s['id'])
    def confirmar(self):
        m=self.propor();return co.confirmar_memoria(m['id'],'usuario',m['versao'])
    def test_proposta_evidencia_responsavel_e_confirmacao_explicita(self):
        m=self.propor();a=m['dados']['_aprendizado']
        self.assertEqual(m['status'],'proposta');self.assertEqual(a['responsavel'],'agente1')
        self.assertEqual(a['amostra'],ap.MIN_AMOSTRAS*2);self.assertEqual(len(a['snapshots']),a['amostra'])
        self.assertTrue(m['evidencias']);self.assertEqual(m['escopo'],'canal:c1')
        with self.assertRaises(co.ErroCoord):co.testar_hipotese(m['id'],versao=m['versao'])
        self.assertEqual(db.um('SELECT COUNT(*) n FROM aprendizado_experimentos')['n'],0)
    def test_teste_aprovado_exclui_historico_outro_canal_e_vertente(self):
        m=self.confirmar();ex=co.testar_hipotese(m['id'],versao=m['versao'])
        self.assertEqual(ex['lados']['a']['n'],0);self.assertEqual(ex['lados']['b']['n'],0)
        self.observar('novoA','A');self.observar('novoB','B')
        self.observar('fora-canal','A',canal='c2');self.observar('fora-vertente','B',vt='criacao_ia')
        e=ap.ler_experimento(ex['id']);self.assertEqual(e['lados']['a']['n'],1);self.assertEqual(e['lados']['b']['n'],1)
        self.assertEqual(e['resultado'],'dados insuficientes')
        atual=co.memoria(m['id']);self.assertEqual(co.testar_hipotese(m['id'],versao=atual['versao'])['id'],ex['id'])
        self.assertEqual(db.um('SELECT COUNT(*) n FROM aprendizado_experimentos')['n'],1)
    def test_cas_e_falha_transacional_sem_teste_orfao(self):
        m=self.confirmar()
        with self.assertRaises(co.ErroCoord):co.testar_hipotese(m['id'],versao=1)
        with patch.object(co,'_versao',side_effect=RuntimeError('simular falha')):
            with self.assertRaises(RuntimeError):co.testar_hipotese(m['id'],versao=m['versao'])
        self.assertEqual(db.um('SELECT COUNT(*) n FROM aprendizado_experimentos')['n'],0)
        self.assertEqual(co.memoria(m['id'])['versao'],m['versao'])
    def test_isolamento_memoria_dna_e_rollback_versionado(self):
        m=self.confirmar();ctx={'canal':'c1','vertente':'cortes','redes':['youtube']}
        self.assertIn(m['id'],[x['id'] for x in co.memorias_aplicaveis(ctx)])
        for outro in [dict(ctx,vertente='criacao_ia'),dict(ctx,canal='c2'),dict(ctx,redes=['instagram']),{'canal':'c1','redes':['youtube']}]:
            self.assertNotIn(m['id'],[x['id'] for x in co.memorias_aplicaveis(outro)])
        ex=co.testar_hipotese(m['id'],versao=m['versao']);atual=co.memoria(m['id'])
        self.assertEqual(set(atual['dados']),{'_aprendizado'}) # sem voz/estilo/ritmo ou permissões de postagem
        des=co.desativar_memoria(m['id'],versao=atual['versao'])
        self.assertEqual(ap.ler_experimento(ex['id'])['status'],'encerrado')
        self.observar('futuro','A');self.assertEqual(ap.ler_experimento(ex['id'])['lados']['a']['n'],0)
        rev=co.reverter_memoria(m['id'],1);self.assertEqual(rev['status'],'proposta')
        self.assertGreater(rev['versao'],des['versao']);self.assertEqual(rev['dados']['_aprendizado']['teste_id'],'')
    def test_amostra_insuficiente_nao_vira_hipotese_e_alvos_nao_aplicam_pesos(self):
        db.executar('DELETE FROM aprendizado_snapshots')
        self.assertFalse(any(x['id'].startswith('metricas.') for x in co.sugestoes()['sugestoes']))
        for alvo in ('roteiro','efeitos','capa','horario','criterios'):
            with self.assertRaises(ap.ErroAprendizado):ap.aplicar(alvo)
if __name__=='__main__':unittest.main()
