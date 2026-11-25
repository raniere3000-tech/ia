"""Fecho: flags off, canal próprio, datas ausentes e metadados do render arquivado."""
import json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
TMP=Path(tempfile.mkdtemp(prefix='ec-compat-'))
os.environ.update(DADOS=str(TMP),BANCO_ARQ=str(TMP/'studio.sqlite'),ESTEIRA_COMPLETA='0')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import banco as db
import postagem as pg
import aprendizado as ap
import coordenador as co
import agente as ag
import pipeline as pl
import projetos as pj
db.migrar()
class Compatibilidade(unittest.TestCase):
    def setUp(self):
        for t in ('aprendizado_snapshots','versoes','renders'):db.executar('DELETE FROM '+t)
        ag._mudar(lambda e:e.update(cortes=[]));pg.salvar_posts([])
        self.arq=pg.VIDEOS/'copia.mp4';self.arq.write_bytes(b'render-aprovado')
        self.p={'id':'p1','video':'copia','origem':'agente3','projeto':'proj1'}
    def test_inteligencia_off_sem_propostas_ou_teste(self):
        with patch.dict(os.environ,{'INTELIGENCIA_METRICAS':'0'}):
            self.assertFalse(ap.painel()['inteligencia_habilitada'])
            self.assertEqual(co.sugestoes()['feedback_metricas'],[])
            with self.assertRaises(co.ErroCoord) as e:co.testar_hipotese('inexistente',versao=1)
            self.assertEqual(e.exception.status,409)
        with patch.dict(os.environ,{'INTELIGENCIA_METRICAS':'1'}):
            self.assertTrue(ap.painel()['inteligencia_habilitada']);self.assertEqual(len(co.sugestoes()['feedback_metricas']),6)
    def test_canal_fonte_nao_e_perfil_de_publicacao(self):
        ag._mudar(lambda e:e['cortes'].append({'id':'c1','video':'copia','canal':'fonte-youtube'}))
        with patch.object(pg,'_capa',return_value=None):c=pg.contexto_publicacao(self.p,self.arq)
        self.assertIsNone(c['canal']);self.assertEqual(c['canal_origem'],'fonte-youtube')
        ag._mudar(lambda e:e['cortes'][0].update(perfil='meu-perfil',perfil_versao=2))
        with patch.object(pg,'_capa',return_value=None):c=pg.contexto_publicacao(self.p,self.arq)
        self.assertEqual(c['canal'],'meu-perfil');self.assertEqual(c['perfil_versao'],2)
    def test_legado_nao_inventa_instante_de_medicao(self):
        ag._mudar(lambda e:e['cortes'].append({'id':'c1','postado':1700000000,'medido':True,'metricas':{'youtube':{'views':0}}}))
        self.assertEqual(ap.capturar()['novos'],1)
        self.assertIsNone(db.um('SELECT periodo_fim FROM aprendizado_snapshots')['periodo_fim'])
        self.assertEqual(ap.indicadores({'de':'2023-01-01'})['publicacoes'],0)
    def test_copia_ia_recupera_recibo_e_roteiro_da_versao_renderizada(self):
        sha=pl.sha_arquivo(self.arq);original=TMP/'render-original.mp4';original.write_bytes(self.arq.read_bytes())
        recibo=original.with_suffix('.efeitos.json');recibo.write_text(json.dumps({'arquivo_sha':sha,'status':'concluido','efeitos':[{'tipo':'zoom','status':'aplicado'}]}))
        db.executar('INSERT INTO renders(id,projeto,versao,arquivo,sha256,criado) VALUES (?,?,?,?,?,?)','r1','proj1',3,str(original),sha,1000)
        dados={'render':{'sha':sha},'roteiro':{'titulo':'Antigo'},'cenas':[]}
        h=pj.hash_roteiro(dados);dados['aprovacao_roteiro']={'aprovado':True,'hash':h}
        db.executar('INSERT INTO versoes(projeto,revisao,dados,criado) VALUES (?,?,?,?)','proj1',1,json.dumps(dados),1000)
        dados['roteiro']['titulo']='Editado depois'
        db.executar('INSERT INTO versoes(projeto,revisao,dados,criado) VALUES (?,?,?,?)','proj1',2,json.dumps(dados),2000)
        pl.emitir_certificado('proj1',sha,{'score':80,'blocking_findings':[]})
        with patch.object(pg,'_capa',return_value=None):c=pg.contexto_publicacao(self.p,self.arq)
        self.assertEqual(c['roteiro_sha'],h);self.assertEqual(c['render_versao'],3)
        self.assertEqual(c['efeitos']['efeitos'][0]['tipo'],'zoom');self.assertEqual(c['certificado']['sha256'],sha)
        self.assertIsNotNone(c['criterio_qa'])
        recibo.write_text(json.dumps({'arquivo_sha':sha,'status':'falhou','efeitos':[]}))
        with patch.object(pg,'_capa',return_value=None):self.assertIsNone(pg.contexto_publicacao(self.p,self.arq)['efeitos'])
    def test_reposts_do_mesmo_render_nao_inflam_amostra_de_feedback(self):
        for i in range(ap.MIN_AMOSTRAS*2):
            g='A' if i<ap.MIN_AMOSTRAS else 'B'
            ap._gravar_retrato('rede','youtube',str(i),{}, {'views':100 if g=='A' else 10},1000,2000,
                publicacao={'post':str(i),'vertente':'cortes','canal':'meu-perfil','gancho':g,'render_sha':'mesmo-render-'+g})
        a=next(x for x in co.feedback_metricas() if x['agente']=='agente1')
        self.assertEqual(a['estado'],'dados_insuficientes');self.assertEqual(a['amostras'],2)
    def test_envio_ia_identifica_canal_retornado_sem_nova_consulta(self):
        p=pg.criar_post({'video':'copia','redes':['youtube'],'titulo':'IA','origem':'agente3','quando':pg.agora()-1})
        def publicado(p,arq):
            p['_canal_publicado']='UC-meu-canal';pg.REF['youtube']='video1'
            return 'https://youtu.be/video1'
        with patch.dict(os.environ,{'PUBLICACAO_CONTEXTO':'1'}),patch.object(pg,'_capa',return_value=None),patch.dict(pg.PUBLICAR,{'youtube':publicado}),patch.object(pg,'conferencia',return_value=[{'item':'teste','ok':True,'bloqueia':False}]):
            pg._publicar_um(p['id'],'youtube')
        atual=pg.posts()[0];c=atual['redes']['youtube']['publicacao']
        self.assertEqual(c['canal'],'youtube:UC-meu-canal');self.assertEqual(c['canal_rede'],'UC-meu-canal')
        self.assertEqual(c['vertente'],'criacao_ia');self.assertNotIn('_canal_publicado',atual)
    def test_youtube_preserva_id_e_canal_da_resposta_do_upload(self):
        p=dict(self.p,titulo='IA',legenda='Texto',opcoes={'youtube_privacidade':'public'})
        respostas=[(200,{'Location':'https://upload.example.test'},{}),(200,{}, {'id':'video1','snippet':{'channelId':'UC-proprio'},'status':{'privacyStatus':'public'}})]
        with patch.object(pg,'_token_google',return_value='token-simulado'),patch.object(pg,'http',side_effect=respostas) as http,patch.object(pg,'_capa_youtube'):
            pg.postar_youtube(p,self.arq)
        self.assertEqual(http.call_count,2);self.assertEqual(p['_canal_publicado'],'UC-proprio');self.assertEqual(pg.REF.pop('youtube'),'video1')
if __name__=='__main__':unittest.main()
