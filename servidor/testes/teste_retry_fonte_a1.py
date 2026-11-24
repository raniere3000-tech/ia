"""F1.05: retry limitado/persistente na mesma fonte, flag desligada por padrão."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TMP=Path(tempfile.mkdtemp(prefix='ec-retry-a1-'))
os.environ.update(DADOS=str(TMP), BANCO_ARQ=str(TMP/'studio.sqlite'), ESTEIRA_COMPLETA='0')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import agente as ag
import banco as db
import fila

db.migrar()


class RetryFonte(unittest.TestCase):
    def setUp(self):
        db.executar("DELETE FROM kv WHERE chave LIKE 'a1.%'")
        ag._mudar(lambda e:e['vistos'].clear())
        self.env=patch.dict(os.environ,{'A1_MESMA_FONTE':'1','A1_FONTE_MAX_TENTATIVAS':'3'})
        self.env.start();self.addCleanup(self.env.stop)
        cfg=ag.config();cfg['cortes']['por_analise']=0
        self.cfg=patch.object(ag,'config',return_value=cfg);self.cfg.start();self.addCleanup(self.cfg.stop)
        self.v={'id':'abcdefghijk','titulo':'Fonte sem legenda','canal':'canal-teste','legenda':False}
        self.escolher=patch.object(ag,'proximo_video',return_value=self.v.copy()).start()
        self.addCleanup(patch.stopall)
        patch.object(ag,'_depois_de_cortar',return_value='feito').start()
        patch.object(ag,'avisar').start()

    def chave(self):
        return db.um("SELECT chave FROM kv WHERE chave LIKE 'a1.pendente:%'")['chave']

    def vencer(self):
        k=self.chave();r=db.kv(k);r['proxima']=0;db.kv_gravar(k,r)

    def test_mesma_fonte_apos_timeout_e_sem_legenda(self):
        with patch.object(ag,'processar_video',side_effect=[TimeoutError('timeout'),[]]) as processar:
            ag.trabalhar_cortes(True)
            self.assertNotIn(self.v['id'],ag.estado()['vistos'])
            self.assertEqual(db.kv(self.chave())['tentativas'],1)
            ag.trabalhar_cortes(True)  # cedo demais: não baixa nem chama IA novamente
            self.assertEqual(processar.call_count,1)
            self.vencer()
            self.assertEqual(ag.trabalhar_cortes(True),'feito')
            self.assertEqual([c.args[0]['id'] for c in processar.call_args_list],[self.v['id']]*2)
            self.assertEqual(self.escolher.call_count,1)
            self.assertIsNone(db.um("SELECT chave FROM kv WHERE chave LIKE 'a1.pendente:%'"))

    def test_tentativas_limitadas_e_atraso_crescente(self):
        with patch.object(ag,'processar_video',side_effect=ag.ErroAgente('HTTP 429 temporário')) as processar:
            ag.trabalhar_cortes(True)
            r1=db.kv(self.chave());self.vencer()
            ag.trabalhar_cortes(True)
            r2=db.kv(self.chave())
            self.assertGreater(r2['proxima']-r1['proxima'],100)
            self.vencer();ag.trabalhar_cortes(True)
            self.assertEqual(processar.call_count,3)
            self.assertEqual(self.escolher.call_count,1)
            self.assertEqual(db.kv('a1.fonte:'+self.v['id'])['estado'],'BLOCKED')
            self.assertIn(self.v['id'],ag.estado()['vistos'])

    def test_definitivo_e_orcamento_nao_repetem(self):
        for msg in ('Vídeo privado','URL inválida','Sem autorização para cortar','O teto de R$ 10 foi atingido'):
            with self.subTest(msg=msg),patch.object(ag,'processar_video',side_effect=ag.ErroAgente(msg)) as proc:
                ag.trabalhar_cortes(True)
                self.assertEqual(proc.call_count,1)
                self.assertIsNone(db.um("SELECT chave FROM kv WHERE chave LIKE 'a1.pendente:%'"))
                self.assertEqual(db.kv('a1.fonte:'+self.v['id'])['estado'],'BLOCKED')

    def test_ffmpeg_temporario_e_permissao_revogada(self):
        ag._mudar(lambda e:e['canais'].append({'id':'canal-teste','status':'aprovado'}))
        with patch.object(ag,'processar_video',side_effect=ag.ErroAgente('FFmpeg: recurso temporariamente indisponível')):
            ag.trabalhar_cortes(True)
        self.assertEqual(db.kv(self.chave())['estado'],'RETRYABLE_ERROR')
        self.vencer()
        ag._mudar(lambda e:e['canais'].clear())
        with patch.object(ag,'processar_video') as proc:
            ag.trabalhar_cortes(True)
            proc.assert_not_called()
        self.assertEqual(db.kv('a1.fonte:'+self.v['id'])['estado'],'BLOCKED')

    def test_flag_desligada_preserva_comportamento(self):
        with patch.dict(os.environ,{'A1_MESMA_FONTE':'0'}),patch.object(ag,'processar_video',side_effect=ag.ErroAgente('timeout')):
            ag.trabalhar_cortes(True)
        self.assertIn(self.v['id'],ag.estado()['vistos'])
        self.assertIsNone(db.um("SELECT chave FROM kv WHERE chave LIKE 'a1.%'"))

    def test_cancelamento_nao_faz_tentativa(self):
        ag.CONTROLE_TRABALHO.cancelado=lambda:True
        try:
            with patch.object(ag,'processar_video') as proc,self.assertRaises(fila.Cancelado):
                ag.trabalhar_cortes(True)
            proc.assert_not_called()
        finally:
            del ag.CONTROLE_TRABALHO.cancelado

    def test_fila_reagenda_sem_trocar_fonte(self):
        def handler(ctx):
            ag.CONTROLE_TRABALHO.job=ctx.id
            try:
                return {'resultado':ag.trabalhar_cortes(True)}
            finally:
                del ag.CONTROLE_TRABALHO.job
        fila.registrar('teste.retry',handler)
        j=fila.enfileirar('teste.retry',agente='agente1',max_tentativas=1)
        db.executar("UPDATE jobs SET status='rodando' WHERE id=?",j['id'])
        with patch.object(ag,'processar_video',side_effect=TimeoutError('timeout')):
            fila._executar(fila.obter(j['id']))
        atual=fila.obter(j['id'])
        self.assertEqual(atual['status'],'na_fila')
        self.assertEqual(atual['tentativas'],0)  # contador da fonte controla o limite
        self.assertGreater(atual['proxima'],0)
        fila.cancelar(j['id'])
        with patch.object(ag,'processar_video') as proc:
            ag.trabalhar_cortes(True)
            proc.assert_not_called()
        self.assertEqual(db.kv('a1.fonte:'+self.v['id'])['estado'],'CANCELLED')

    def test_reinicio_nao_escolhe_outro_video(self):
        with patch.object(ag,'processar_video',side_effect=TimeoutError('timeout')):
            ag.trabalhar_cortes(True)
        self.vencer()
        code='''
import agente as ag,banco as db
ag.proximo_video=lambda *a: (_ for _ in ()).throw(AssertionError('Não pode buscar outra fonte'))
ag.processar_video=lambda v,n: (__import__('pathlib').Path(__import__('sys').argv[1]).write_text(v['id']),[])[1]
ag._depois_de_cortar=lambda *a:'ok'
assert ag.trabalhar_cortes(True)=='ok'
'''
        out=TMP/'fonte-reinicio.txt'
        r=subprocess.run([sys.executable,'-c',code,str(out)],capture_output=True,text=True,timeout=15)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(out.read_text(),self.v['id'])

if __name__=='__main__':
    unittest.main()
