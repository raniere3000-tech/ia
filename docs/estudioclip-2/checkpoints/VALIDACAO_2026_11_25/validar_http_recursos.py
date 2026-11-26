"""Contrato HTTP dos recursos ativos; banco e token de teste, sem APIs externas."""
import json,os,sys,tempfile,threading,time,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
TMP=Path(tempfile.mkdtemp(prefix='ec-http-ativos-'))
FLAGS='A1_MESMA_FONTE A1_GANCHO_INTEGRO THUMB_REJEICAO A5_EFEITOS_REAIS RENDER_INTEGRIDADE DNA_CORTE A3_EDICAO_COMPARTILHADA FORMATOS_IA METRICAS_PUBLICACOES PUBLICACAO_CONTEXTO INTELIGENCIA_METRICAS'.split()
os.environ.update(dict.fromkeys(FLAGS,'1'));os.environ.update(DADOS=str(TMP),BANCO_ARQ=str(TMP/'db.sqlite'),CHAVE_MESTRA_ARQ=str(TMP/'chave'),TOKEN='senha-validacao-123')
sys.path.insert(0,'/workspace/scratch/ecb4bcf1d97f/estudioclip/servidor')
import banco as db,servidor as S,aprendizado as ap,postagem as pg
from http.server import ThreadingHTTPServer
db.migrar()
http=ThreadingHTTPServer(('127.0.0.1',0),S.Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
URL='http://127.0.0.1:'+str(http.server_port)
def get(path,auth=True):
    req=urllib.request.Request(URL+path,headers={'X-Token':'senha-validacao-123'} if auth else {})
    try:
        with urllib.request.urlopen(req,timeout=15) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
class HTTPAtivos(unittest.TestCase):
    def setUp(self):
        db.executar('DELETE FROM aprendizado_snapshots');t=time.time()
        for id,vt,rede,m in [('zero','cortes','youtube',{'views':0,'curtidas':2}),('ia','criacao_ia','youtube',{'views':123}),('ig','cortes','instagram',{'curtidas':8})]:
            ap._gravar_retrato('rede',rede,id,{},m,t-100,t,publicacao={'post':id,'ref':id,'render_sha':'sha-'+id,'vertente':vt,'canal':'perfil-teste','titulo':'Teste '+id,'publicado_em':t-100})
    def test_autenticacao_e_resposta_de_flags(self):
        self.assertIn(get('/agente/aprendizado',False)[0],(401,403))
        status,d=get('/agente/aprendizado');self.assertEqual(status,200,d);self.assertTrue(d['inteligencia_habilitada']);self.assertTrue(d['coleta']['publicacoes_habilitadas'])
    def test_filtro_ia_canal_rede_com_dados_persistidos(self):
        status,d=get('/agente/aprendizado/indicadores?vertente=criacao_ia&rede=youtube&canal=perfil-teste')
        self.assertEqual(status,200,d);self.assertEqual(d['publicacoes'],1);self.assertEqual(d['medidas']['views']['valor'],123)
        self.assertEqual(d['destaques'][0]['videos'][0]['publicacao']['render_sha'],'sha-ia')
    def test_zero_real_nao_vira_ausencia(self):
        _,d=get('/agente/aprendizado/indicadores?vertente=cortes&rede=youtube')
        self.assertEqual(d['medidas']['views']['valor'],0);self.assertEqual(len(d['destaques'][0]['videos']),1)
    def test_metrica_ausente_e_periodo_vazio(self):
        _,d=get('/agente/aprendizado/indicadores?rede=instagram');self.assertIsNone(d['medidas']['views']['valor']);self.assertEqual(d['destaques'][0]['sem_metrica'],1)
        _,d=get('/agente/aprendizado/indicadores?de=2100-01-01');self.assertEqual(d['publicacoes'],0)
    def test_flag_desligada_e_filtro_invalido_nao_burlam_api(self):
        with patch.dict(os.environ,{'INTELIGENCIA_METRICAS':'0'}):self.assertEqual(get('/agente/aprendizado/indicadores')[0],404)
        self.assertEqual(get('/agente/aprendizado/indicadores?rede=inventada')[0],400)
    def test_consultas_nao_alteram_snapshots_nem_publicam(self):
        antes=db.todos('SELECT * FROM aprendizado_snapshots')
        with patch.object(pg,'http',side_effect=AssertionError('nenhuma API real')):
            self.assertEqual(get('/agente/aprendizado/indicadores')[0],200)
        self.assertEqual(db.todos('SELECT * FROM aprendizado_snapshots'),antes);self.assertEqual(pg.posts(),[])
try:r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HTTPAtivos))
finally:http.shutdown();http.server_close()
sys.exit(not r.wasSuccessful())
