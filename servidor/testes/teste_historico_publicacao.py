"""F4.04: versão congelada no envio; contas simuladas e banco temporário."""
import json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
TMP=Path(tempfile.mkdtemp(prefix='ec-historico-'))
os.environ.update(DADOS=str(TMP),BANCO_ARQ=str(TMP/'studio.sqlite'),ESTEIRA_COMPLETA='0',PUBLICACAO_CONTEXTO='1',METRICAS_PUBLICACOES='1')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import banco as db
import postagem as pg
import aprendizado as ap
import agente as ag
import pipeline as pl
db.migrar()
class Historico(unittest.TestCase):
    def setUp(self):
        pg.salvar_posts([]);ag._mudar(lambda e:e.update(cortes=[]))
        db.executar('DELETE FROM aprendizado_snapshots')
        self.arq=pg.VIDEOS/'v.mp4';self.arq.write_bytes(b'versao-1'*1000)
        self.p=pg.criar_post({'video':'v','redes':['youtube','instagram'],'titulo':'Título inicial','legenda':'Texto inicial','quando':pg.agora()-1})
        ag._mudar(lambda e:e['cortes'].append({'id':'c1','post':self.p['id'],'video':'v','gancho':'Frase completa','canal':'canal1','perfil':'perfil1'}))
    def enviar(self,rede):
        def publicado(p,arq):
            pg.REF[rede]='id-'+rede
            return 'https://example.test/'+rede
        with patch.dict(pg.PUBLICAR,{rede:publicado}),patch.object(pg,'conferencia',return_value=[{'item':'teste','ok':True,'bloqueia':False}]),patch.object(pg,'_capa',return_value={'sha':'capa1','variante':'v1'}):
            pg._publicar_um(self.p['id'],rede)
        return pg.posts()[0]['redes'][rede]
    def test_envio_congela_id_render_gancho_capa_e_instante(self):
        a=self.enviar('youtube');c=a['publicacao']
        self.assertEqual(c['ref'],'id-youtube');self.assertEqual(c['render_sha'],pl.sha_arquivo(self.arq))
        self.assertEqual(c['gancho'],'Frase completa');self.assertEqual(c['capa_selecionada']['sha'],'capa1')
        self.assertEqual(c['publicado_em'],a['feito']);self.assertEqual(c['vertente'],'cortes')
        self.assertEqual(c['canal'],'perfil1');self.assertEqual(c['canal_origem'],'canal1');self.assertIsNone(c['efeitos'])
    def test_editar_depois_nao_reescreve_publicacao_ou_snapshot(self):
        a=self.enviar('youtube');original=json.dumps(a['publicacao'],sort_keys=True)
        pg._mudar(self.p['id'],lambda q:q.update(medido=True,metricas={'youtube':{'views':0}},metricas_em=pg.agora()))
        ap.capturar(publicacoes=pg.posts())
        snapshot=db.um('SELECT * FROM aprendizado_snapshots')
        self.assertEqual(json.dumps(json.loads(snapshot['variaveis'])['_publicacao'],sort_keys=True),original)
        self.arq.write_bytes(b'versao-2'*1000)
        ag._mudar(lambda e:e['cortes'][0].update(gancho='Outro gancho'))
        pg._mudar(self.p['id'],lambda q:q.update(titulo='Título novo'))
        b=self.enviar('instagram')['publicacao']
        self.assertNotEqual(b['render_sha'],a['publicacao']['render_sha']);self.assertEqual(b['gancho'],'Outro gancho')
        self.assertEqual(json.dumps(pg.posts()[0]['redes']['youtube']['publicacao'],sort_keys=True),original)
        self.assertEqual(db.um('SELECT * FROM aprendizado_snapshots')['variaveis'],snapshot['variaveis'])
        self.assertEqual(ap.capturar(publicacoes=pg.posts())['novos'],0)
    def test_recibo_so_se_vinculado_ao_hash_real_e_legado_sem_contexto(self):
        r=self.arq.with_suffix('.efeitos.json');r.write_text(json.dumps({'arquivo_sha':'errado','efeitos':['zoom']}))
        self.assertIsNone(pg.contexto_publicacao(self.p,self.arq)['efeitos'])
        r.write_text(json.dumps({'arquivo_sha':pl.sha_arquivo(self.arq),'status':'concluido','efeitos':[{'tipo':'zoom','status':'aplicado'}]}))
        self.assertEqual(pg.contexto_publicacao(self.p,self.arq)['efeitos']['efeitos'][0]['status'],'aplicado')
        with patch.dict(os.environ,{'PUBLICACAO_CONTEXTO':'0'}):a=self.enviar('youtube')
        self.assertNotIn('publicacao',a)
    def test_falha_nao_registra_contexto_como_publicado(self):
        with patch.dict(pg.PUBLICAR,{'youtube':lambda *a:(_ for _ in ()).throw(pg.ErroRede('simulado'))}),patch.object(pg,'conferencia',return_value=[{'item':'teste','ok':True,'bloqueia':False}]),patch.object(pg,'_avisar_falha'):
            pg._publicar_um(self.p['id'],'youtube')
        a=pg.posts()[0]['redes']['youtube'];self.assertEqual(a['status'],'erro');self.assertNotIn('publicacao',a)
if __name__=='__main__':unittest.main()
