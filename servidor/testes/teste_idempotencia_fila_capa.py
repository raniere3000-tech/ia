"""F1.07: dois pedidos concorrentes mantêm um job/efeito e versões novas permitidas."""
import os
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

TMP=Path(tempfile.mkdtemp(prefix='ec-idempotencia-'))
os.environ.update(DADOS=str(TMP),BANCO_ARQ=str(TMP/'studio.sqlite'),ESTEIRA_COMPLETA='0',AGENTE6_SEM_VIGIA='1')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import banco as db
import fila
import thumbnails as th

db.migrar();th.iniciar()


class Idempotencia(unittest.TestCase):
    def setUp(self):
        db.executar('DELETE FROM jobs');db.executar('DELETE FROM thumbnail_jobs')
        db.executar('DELETE FROM thumbnail_variantes')
        fila.registrar('teste.idempotente',lambda ctx:{})
        self.arq=TMP/'video.mp4';self.arq.write_bytes(b'video original')
        self.info={'arquivo':self.arq,'titulo':'Teste','canal':'','origem':'corte','referencia':'c1'}

    def juntos(self,f,n=2):
        b=threading.Barrier(n)
        def chamar(_):
            b.wait(timeout=10)
            return f()
        with ThreadPoolExecutor(max_workers=n) as ex:
            return list(ex.map(chamar,range(n)))

    def test_enfileirar_concorrente(self):
        rs=self.juntos(lambda:fila.enfileirar('teste.idempotente',agente='agente3',chave='acao:projeto:versao:1',dados={'texto':'x'*10000}),8)
        self.assertEqual(len({r['id'] for r in rs}),1)
        self.assertEqual(db.um("SELECT COUNT(*) n FROM eventos WHERE recurso=? AND acao='job_criado'",'job:'+rs[0]['id'])['n'],1)
        novo=fila.enfileirar('teste.idempotente',agente='agente3',chave='acao:projeto:versao:2')
        self.assertNotEqual(novo['id'],rs[0]['id'])

    def criar(self):
        return th.criar({'origem':'corte','referencia':'c1','metodo':'frame','variantes':1,'chave_idempotencia':'cliente-1'})

    def test_criar_capa_concorrente_e_novo_render(self):
        with patch.object(th,'resolver',return_value=self.info):
            rs=self.juntos(self.criar)
            self.assertEqual(len({r['id'] for r in rs}),1)
            self.assertEqual(db.um('SELECT COUNT(*) n FROM thumbnail_jobs')['n'],1)
            self.assertEqual(db.um('SELECT COUNT(*) n FROM jobs')['n'],1)
            self.arq.write_bytes(b'render versao nova')
            self.assertNotEqual(self.criar()['id'],rs[0]['id'])

    def test_refazer_capa_concorrente_tem_um_efeito(self):
        with patch.object(th,'resolver',return_value=self.info):
            j=th._job(self.criar()['id'])
            db.executar("UPDATE jobs SET status='concluido' WHERE id=?",j['fila_job'])
            db.executar("UPDATE thumbnail_jobs SET estado='aguardando_escolha' WHERE id=?",j['id'])
            def refazer():
                try:
                    return th.refazer(j['id'],{'numero':1,'texto':'Novo texto'})
                except th.ErroThumb as e:
                    self.assertEqual(e.status,409)
                    return {'ocupado':True}
            rs=self.juntos(refazer)
            self.assertEqual(db.um('SELECT COUNT(*) n FROM jobs')['n'],2)
            r=th._job(j['id'])
            self.assertNotEqual(r['fila_job'],j['fila_job'])
            # Se o primeiro render falhou sem produzir versão, uma nova ação é permitida.
            db.executar("UPDATE jobs SET status='falhou' WHERE id=?",r['fila_job'])
            db.executar("UPDATE thumbnail_jobs SET estado='falhou' WHERE id=?",j['id'])
            r2=th._job(th.refazer(j['id'],{'numero':1,'texto':'Novo texto'})['id'])
            self.assertNotEqual(r2['fila_job'],r['fila_job'])

    def test_cancelar_e_liberar_repetidos_nao_duplicam(self):
        j=fila.enfileirar('teste.idempotente',agente='agente3')
        rs=self.juntos(lambda:fila.cancelar(j['id']))
        self.assertTrue(all(r['status']=='cancelado' for r in rs))
        self.assertEqual(db.um("SELECT COUNT(*) n FROM eventos WHERE recurso=? AND acao='job_cancelado'",'job:'+j['id'])['n'],1)
        self.juntos(lambda:fila.liberar(j['id']))
        self.assertEqual(fila.obter(j['id'])['status'],'cancelado')

if __name__=='__main__':
    unittest.main()
