"""F2.01: limites preservam frases e palavras, sem exigir legenda na fonte."""
import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
TMP=Path(tempfile.mkdtemp(prefix='ec-gancho-integro-'))
os.environ.update(DADOS=str(TMP),BANCO_ARQ=str(TMP/'studio.sqlite'),ESTEIRA_COMPLETA='0')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import agente as ag


class GanchoIntegro(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'A1_GANCHO_INTEGRO':'1'});self.env.start();self.addCleanup(self.env.stop)
        self.co={'dur_min':4,'dur_max':9,'proibidos':[],'nota_min':0}
        self.frs=[{'ini':0.,'fim':2.,'texto':'Uma introdução.'},
                  {'ini':2.1,'fim':5.,'texto':'A frase está só'},
                  {'ini':5.1,'fim':8.,'texto':'na metade do argumento'},
                  {'ini':8.1,'fim':10.,'texto':'que acaba aqui.'},
                  {'ini':10.1,'fim':13.,'texto':'Próxima ideia completa.'}]

    def test_junta_chunks_e_persistem_limites_justificativa(self):
        r=ag.validar([{'inicio':5.1,'fim':8.,'nota':90,'gancho':'Argumento inteiro'}],self.frs,self.co)[0]
        self.assertLessEqual(r['ini'],2.1)
        self.assertGreaterEqual(r['fim'],10.)
        self.assertLessEqual(r['fim'],10.1)
        self.assertIn('acaba aqui.',r['texto'])
        self.assertTrue(r['gancho_integridade']['verificado'])
        self.assertEqual(r['gancho_integridade']['inicio_solicitado'],5.1)
        self.assertLessEqual(r['fim']-r['ini'],9)

    def test_sem_fronteira_na_duracao_nao_finge_frase_completa(self):
        self.co['dur_max']=5
        self.assertEqual(ag.validar([{'inicio':2.1,'fim':8.,'nota':90}],self.frs,self.co),[])
        self.assertEqual(ag.validar([{'inicio':1,'fim':5}],[],self.co),[])

    def test_pausa_tambem_fecha_frase(self):
        self.frs[3]['texto']='sem pontuação'
        self.frs[4]['ini']=11.
        r=ag.validar([{'inicio':5.1,'fim':8.,'nota':90}],self.frs,self.co)
        self.assertTrue(r)
        self.assertGreaterEqual(r[0]['fim'],10.)

    def test_flag_off_preserva_limites_anteriores(self):
        with patch.dict(os.environ,{'A1_GANCHO_INTEGRO':'0'}):
            r=ag.validar([{'inicio':5.1,'fim':8.,'nota':90}],self.frs,self.co)[0]
        self.assertNotIn('gancho_integridade',r)

    def test_sem_legenda_continua_pelos_eventos_sem_falsa_verificacao(self):
        import gameplay_indexer as gi
        d={'ini':0,'fim':6,'nota':85,'score':5,'porque':'Pico de som'}
        with patch.object(gi,'picos_de_audio',return_value=[]),patch.object(gi,'_picos',return_value=[]), \
             patch.object(gi,'destaques',return_value=[d]),patch.object(ag,'_cenas_leves',return_value=[]), \
             patch.object(ag,'_textos_do_momento',return_value={'titulo':'Momento','gancho':'Olha isso'}):
            r=ag.escolher_sem_fala(TMP/'video.mp4',20,[],1,self.co,'Vídeo',TMP)
        self.assertTrue(r[0]['sem_legenda'])
        self.assertFalse(r[0]['gancho_integridade']['verificado'])

if __name__=='__main__':unittest.main()
