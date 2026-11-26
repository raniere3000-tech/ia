"""F4.03: respostas oficiais simuladas, ausência != zero, snapshots já existentes."""
import json,os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
TMP=Path(tempfile.mkdtemp(prefix='ec-metricas-'))
os.environ.update(DADOS=str(TMP),BANCO_ARQ=str(TMP/'studio.sqlite'),ESTEIRA_COMPLETA='0')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import agente as ag
import aprendizado as ap
import banco as db
import postagem as pg

db.migrar()
class Metricas(unittest.TestCase):
    def setUp(self):
        db.executar('DELETE FROM aprendizado_snapshots');pg.salvar_posts([])
        ag._mudar(lambda e:e.update(cortes=[]))
    def post(self,id='p1',origem='agente3',metricas=None):
        return {'id':id,'video':id,'origem':origem,'quando':1000,'modelo':'T1','medido':True,'metricas_em':2000,
                'redes':{'youtube':{'status':'postado','feito':1100}},'metricas':metricas or {'youtube':{'views':0,'curtidas':3}}}
    def test_youtube_short_watch_e_link_curto_sem_inventar_campo_omitido(self):
        resposta=(200,{}, {'items':[{'statistics':{'viewCount':'0','likeCount':'7'}}]})
        with patch.object(pg,'_token_google',return_value='teste'),patch.object(pg,'http',return_value=resposta) as http:
            for link in ['https://youtube.com/shorts/Abc123456_-','https://www.youtube.com/watch?feature=share&v=Abc123456_-',
                         'https://youtu.be/Abc123456_-?t=3']:
                m=ag.medir_post({'redes':{'youtube':{'status':'postado','link':link}}})['youtube']
                self.assertEqual(m,{'views':0,'curtidas':7,'comentarios':None})
                self.assertIn('id=Abc123456_-',http.call_args.args[1])
            n=http.call_count
            ag.medir_post({'redes':{'youtube':{'status':'postado','link':'https://outro.example/shorts/Abc123456_-'}}})
            self.assertEqual(http.call_count,n)
    def test_erro_permissao_ou_tiktok_sem_adaptador_nao_vira_zero(self):
        with patch.object(pg,'_token_google',return_value='teste'),patch.object(pg,'http',return_value=(403,{},{})) as http:
            p={'redes':{'youtube':{'status':'postado','link':'https://youtu.be/Abc123456_-'},
                        'tiktok':{'status':'postado','ref':'publish-id'},'instagram':{'status':'agendado'}}}
            m=ag.medir_post(p)
            self.assertEqual(set(m),{'youtube','tiktok'})
            self.assertTrue(all(x is None for rede in m.values() for x in rede.values()))
            self.assertEqual(http.call_count,1)
    def test_instagram_engajamento_nao_inventa_views_ou_retencao(self):
        with patch.object(pg,'_pagina_meta',return_value={'token':'teste'}),patch.object(pg,'http',return_value=(200,{}, {'like_count':0,'comments_count':2})):
            m=ag.medir_post({'redes':{'instagram':{'status':'postado','ref':'ig1'}}})['instagram']
        self.assertEqual(m,{'views':None,'curtidas':0,'comentarios':2});self.assertNotIn('retencao',m)
        for v in [-1,True,float('inf'),float('nan'),1.5,'invalido']:self.assertIsNone(ag._numero(v))
    def test_publicacoes_ia_manuais_com_data_origem_e_rede_sem_duplicar_corte(self):
        p=self.post();p2=self.post('p2','manual',{'youtube':{'curtidas':0,'comentarios':2},'tiktok':{'views':None}})
        pg.salvar_posts([p,p2])
        with patch.dict(os.environ,{'METRICAS_PUBLICACOES':'0'}):self.assertEqual(ap.capturar(publicacoes=pg.posts())['novos'],0)
        with patch.dict(os.environ,{'METRICAS_PUBLICACOES':'1'}):
            self.assertEqual(ap.capturar(publicacoes=pg.posts())['novos'],2);self.assertEqual(ap.capturar(publicacoes=pg.posts())['novos'],0)
        rows=db.todos('SELECT * FROM aprendizado_snapshots')
        self.assertEqual({r['item'] for r in rows},{'post:p1','post:p2'})
        self.assertTrue(all(r['fonte']=='rede' and r['rede']=='youtube' and r['periodo_ini']==1100 and r['periodo_fim']==2000 for r in rows))
        m=json.loads(next(r for r in rows if r['item']=='post:p2')['metricas'])
        self.assertNotIn('views',m);self.assertEqual(m['curtidas'],0)
    def test_post_do_corte_ja_representado_nao_duplica_amostra(self):
        p=self.post();pg.salvar_posts([p])
        ag._mudar(lambda e:e['cortes'].append({'id':'c1','post':'p1','medido':True,'metricas':p['metricas'],'postado':1100,'metricas_em':2000}))
        with patch.dict(os.environ,{'METRICAS_PUBLICACOES':'1'}):
            self.assertEqual(ap.capturar(publicacoes=pg.posts())['novos'],1);self.assertEqual(ap.capturar(publicacoes=pg.posts())['novos'],0)
        self.assertEqual(db.um('SELECT item FROM aprendizado_snapshots')['item'],'c1')
    def test_legado_sem_instante_da_coleta_preserva_ausencia(self):
        p=self.post();p.pop('metricas_em');p['metricas']['youtube']={'views':None,'curtidas':-3}
        pg.salvar_posts([p])
        with patch.dict(os.environ,{'METRICAS_PUBLICACOES':'1'}):self.assertEqual(ap.capturar(publicacoes=pg.posts())['novos'],0)
        p['metricas']['youtube']={'comentarios':2};pg.salvar_posts([p])
        with patch.dict(os.environ,{'METRICAS_PUBLICACOES':'1'}):self.assertEqual(ap.capturar(publicacoes=pg.posts())['novos'],1)
        self.assertIsNone(db.um('SELECT periodo_fim FROM aprendizado_snapshots')['periodo_fim'])
    def test_coleta_registra_hora_real_e_inventario_nao_consulta_contas(self):
        p=self.post();p.update(medido=False,quando=time.time()-3*86400);pg.salvar_posts([p])
        t=time.time()
        with patch.dict(os.environ,{'METRICAS_PUBLICACOES':'1'}),patch.object(ag,'medir_post',return_value={'youtube':{'views':0}}):ag.aprender(ajustar=False)
        atual=pg.posts()[0];self.assertGreaterEqual(atual['metricas_em'],t)
        self.assertEqual(db.um('SELECT COUNT(*) n FROM aprendizado_snapshots')['n'],1)
        with patch.object(pg,'http',side_effect=AssertionError('sem conta real')):
            inv=ag.inventario_metricas()
        self.assertFalse(inv['redes']['tiktok']['coletor'])
        self.assertTrue(all(not x['autorizacao_verificada'] and x['retencao']=='nao_coletada' for x in inv['redes'].values()))

if __name__=='__main__':unittest.main()
