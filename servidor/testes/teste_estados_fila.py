"""F1.04: leitura normalizada não altera status, não inventa execução, sobrevive reinício."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-estados-'))
os.environ.update(DADOS=str(TMP), BANCO_ARQ=str(TMP/'studio.sqlite'), ESTEIRA_COMPLETA='0', CENTRAL_SEM_ACORDAR='1')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import banco as db
import fila
import api_v1
import coordenador as co

db.migrar()


class EstadosFila(unittest.TestCase):
    def test_mapa_e_precedencia(self):
        for status, esperado in [('novo','CREATED'),('agendado','QUEUED'),('na_fila','QUEUED'),
                ('aguardando_aprovacao','WAITING_USER'),('aguardando_tentativa','RETRYABLE_ERROR'),
                ('cancelado','CANCELLED'),('falhou','FAILED'),('concluido','COMPLETED')]:
            with self.subTest(status=status):
                j={'status':status,'pausado':0,'cancelar':0}
                r=fila.estado_publico(j,1000)
                self.assertEqual(r['estado_comum'],esperado)
                self.assertEqual(j,{'status':status,'pausado':0,'cancelar':0})
        self.assertEqual(fila.estado_publico({'status':'rodando','cancelar':1,'pausado':1})['estado_comum'],'CANCEL_REQUESTED')
        self.assertEqual(fila.estado_publico({'status':'na_fila','pausado':1})['estado_comum'],'PAUSED')
        self.assertEqual(fila.estado_publico({'status':'concluido','pausado':1,'cancelar':1})['estado_comum'],'COMPLETED')

    def test_heartbeat_e_lease(self):
        self.assertEqual(fila.estado_publico({'status':'rodando','heartbeat':999,'lease':1100},1000)['estado_comum'],'RUNNING')
        for heart,lease in [(0,1100),(100,1100),(999,900)]:
            r=fila.estado_publico({'status':'rodando','heartbeat':heart,'lease':lease},1000)
            self.assertEqual(r['estado_comum'],'RETRYABLE_ERROR')
            self.assertTrue(r['heartbeat_atrasado'])
            self.assertTrue(r['estado_motivo'])

    def test_api_lista_painel_e_reinicio_sem_escrita_de_leitura(self):
        fila.registrar('teste.estado', lambda ctx: {})
        j=fila.enfileirar('teste.estado',agente='agente3')
        db.executar("UPDATE jobs SET status='rodando', heartbeat=?, lease=? WHERE id=?",time.time()-500,time.time()-100,j['id'])
        antes=db.um('SELECT * FROM jobs WHERE id=?',j['id'])
        x=next(x for x in fila.lista()['jobs'] if x['id']==j['id'])
        self.assertEqual(x['estado_comum'],'RETRYABLE_ERROR')
        self.assertIsNone(x['fim_previsto'])
        self.assertIsNone(x['restante'])
        self.assertEqual(fila.lista('erros')['jobs'][0]['id'],j['id'])
        class H:
            headers={}
            path="/api/v1/fila/"+j["id"]
        r=api_v1.tratar(H(),'GET','/api/v1/fila/'+j['id'],{'nome':'teste','id':'teste'})
        self.assertEqual(r['estado_comum'],'RETRYABLE_ERROR')
        ag=next(a for a in co.agentes()['agentes'] if a['id']=='agente3')
        self.assertNotEqual(ag['estado'],'trabalhando')
        self.assertEqual(ag['jobs_recuperaveis'][0]['job'],j['id'])
        self.assertEqual(antes,db.um('SELECT * FROM jobs WHERE id=?',j['id']))
        code="import fila; assert fila.recuperar()>=1; j=fila.obter('"+j['id']+"'); assert j['status']=='na_fila'; assert fila.estado_publico(j)['estado_comum']=='QUEUED'"
        p=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stderr)

if __name__=='__main__':
    unittest.main()
