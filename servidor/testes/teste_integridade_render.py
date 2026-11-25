"""F2.03: mídia real, detecção opt-in e publicação só depois da conferência."""
import hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
TMP=Path(tempfile.mkdtemp(prefix='ec-integridade-'))
os.environ.update(DADOS=str(TMP),BANCO_ARQ=str(TMP/'studio.sqlite'),ESTEIRA_COMPLETA='0')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import banco as db
import exportacao as ex
import fila
import projetos as pj
import renderizador as rd

db.migrar();ex.iniciar()

def gerar(nome, filtro='', audio=7):
    p=TMP/(nome+'.mp4')
    cmd=['ffmpeg','-nostdin','-y','-v','error','-f','lavfi','-i','testsrc2=s=160x90:r=30:d=7',
         '-f','lavfi','-i',f'sine=f=440:d={audio}']
    if filtro:cmd+=['-vf',filtro]
    subprocess.run(cmd+['-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(p)],check=True)
    return p

class Integridade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.normal=gerar('normal')
        cls.preto=gerar('preto',"drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(t,2,4)'")
        cls.parado=gerar('parado','trim=duration=1,tpad=stop_mode=clone:stop_duration=6')
        cls.dessincronizado=gerar('dessincronizado',audio=3)

    def conf(self,p,**kw):
        pasta=TMP/(p.stem+'-qa');pasta.mkdir(exist_ok=True)
        with patch.dict(os.environ,{'RENDER_INTEGRIDADE':'1'}):
            return rd.conferir(p,pasta,dict(largura=160,altura=90,duracao=7,**kw))

    def test_normal_tem_volume_codec_e_sincronia_medidos(self):
        c=self.conf(self.normal)
        self.assertTrue(c['ok'],c['erros'])
        self.assertEqual((c['codec'],c['audio']),('h264','aac'))
        self.assertLess(c['integridade']['diferenca_audio_video_s'],.1)
        self.assertIsInstance(c['integridade']['volume_medio_db'],float)
        self.assertLess(c['integridade']['pico_db'],0)

    def test_preto_inesperado_bloqueia_e_intencional_so_no_intervalo(self):
        c=self.conf(self.preto)
        self.assertFalse(c['ok']);self.assertTrue(c['integridade']['pretos'])
        self.assertTrue(self.conf(self.preto,pretos_previstos=[[2,4]])['ok'])
        self.assertFalse(self.conf(self.preto,pretos_previstos=[[0,1]])['ok'])
        with patch.dict(os.environ,{'RENDER_INTEGRIDADE':'0'}):
            self.assertTrue(rd.conferir(self.preto,TMP,{'largura':160,'altura':90,'duracao':7})['ok'])

    def test_congelamento_ate_o_fim_nao_escapa_do_detector(self):
        c=self.conf(self.parado)
        self.assertFalse(c['ok']);self.assertTrue(c['integridade']['congelamentos'])
        self.assertTrue(self.conf(self.parado,parados_previstos=[[.9,7]])['ok'])
        self.assertFalse(self.conf(self.parado,parados_previstos=[[0,1]])['ok'])

    def test_audio_curto_bloqueia(self):
        c=self.conf(self.dessincronizado)
        self.assertFalse(c['ok'])
        self.assertGreater(c['integridade']['diferenca_audio_video_s'],3)

    def test_editor_reprovado_preserva_video_anterior(self):
        import editor_ia as ed
        destino=TMP/'edicao.mp4';destino.write_bytes(b'anterior')
        plano={'clips':[{'source':'principal','in_ms':0,'out_ms':7000}],
               'effects':[],'target_aspect_ratio':'16:9'}
        with patch.dict(os.environ,{'A5_EFEITOS_REAIS':'1','RENDER_INTEGRIDADE':'1'}):
            with self.assertRaisesRegex(rd.ErroRender,'congelada'):
                ed._finalizar_efeitos(plano,self.parado,destino)
        self.assertEqual(destino.read_bytes(),b'anterior')
        recibo=json.loads(destino.with_suffix('.efeitos.json').read_text())
        self.assertEqual(recibo['status'],'falhou')
        self.assertTrue(recibo['integridade']['congelamentos'])

    def test_editor_aprovado_registra_conferencia(self):
        import editor_ia as ed
        destino=TMP/'edicao-aprovada.mp4'
        plano={'clips':[{'source':'principal','in_ms':0,'out_ms':7000}],
               'effects':[],'target_aspect_ratio':'16:9'}
        with patch.dict(os.environ,{'A5_EFEITOS_REAIS':'1','RENDER_INTEGRIDADE':'1'}):
            ed._finalizar_efeitos(plano,self.normal,destino)
        recibo=json.loads(destino.with_suffix('.efeitos.json').read_text())
        self.assertEqual(recibo['status'],'concluido')
        self.assertTrue(recibo['integridade']['analise_ok'])
        self.assertEqual(recibo['arquivo_sha'],rd.sha256(destino))

    def test_exportacao_reprovada_preserva_anterior_e_retry_limitado(self):
        manifesto={'quadros':[{'dur':1}], 'formato':'16:9','nome':'integridade'}
        with patch.dict(ex.ec.FORMATOS,{'16:9':(160,90)}):
            pedido=ex.pedir(manifesto,'teste');j=fila.obter(pedido['job'])
            self.assertEqual(j['max_tentativas'],2)
            v=json.loads(j['dados'])['manifesto']
            chave=hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()[:20]
            pasta=ex.PASTA/chave;pasta.mkdir(parents=True,exist_ok=True)
            anterior=pasta/'final.mp4';anterior.write_bytes(b'versao anterior intocada')
            with patch.object(rd,'conferir',return_value={'ok':False,'erros':['preto inesperado'],'avisos':[]}):
                with self.assertRaisesRegex(RuntimeError,'preto inesperado'):
                    ex.job_exportar(fila.Contexto(j))
            self.assertEqual(anterior.read_bytes(),b'versao anterior intocada')
            self.assertTrue((pasta/'final.tmp.mp4').exists())
            self.assertEqual(json.loads(fila.obter(j['id'])['dados'])['diagnostico']['etapa'],'conferencia')

if __name__=='__main__':unittest.main()
