"""F1.08: recusar proposta mantém seleção aprovada, versão e trilha de decisão."""
import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

TMP=Path(tempfile.mkdtemp(prefix='ec-rejeitar-thumb-'))
os.environ.update(DADOS=str(TMP),BANCO_ARQ=str(TMP/'studio.sqlite'),ESTEIRA_COMPLETA='0',AGENTE6_SEM_VIGIA='1')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import banco as db
import thumbnails as th
import fila
import api_v1

db.migrar();th.iniciar()


class RejeitarThumb(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'THUMB_REJEICAO':'1'});self.env.start();self.addCleanup(self.env.stop)
        self.video=TMP/'video.mp4';self.video.write_bytes(os.urandom(32))
        self.resolver=patch.object(th,'resolver',return_value={'arquivo':self.video,'titulo':'Vídeo teste'});self.resolver.start();self.addCleanup(self.resolver.stop)
        self.j=th.criar({'origem':'corte','referencia':'c1','variantes':2,'metodo':'frame'})
        db.executar("UPDATE thumbnail_jobs SET estado='aguardando_escolha' WHERE id=?",self.j['id'])
        self.v1=self.variante(1,1,'green');self.v2=self.variante(2,1,'blue')
        th.selecionar(self.j['id'],{'variante_id':self.v1,'versao':1})

    def variante(self,n,versao,cor):
        vid=os.urandom(6).hex();p=TMP/(vid+'.jpg');Image.new('RGB',(320,180),cor).save(p)
        sha=hashlib.sha256(p.read_bytes()).hexdigest()
        rel={'nota':90,'aprovado':True,'criterios':{},'bloqueios':[],'notas':[],'texto':'Gancho'}
        db.executar('INSERT INTO thumbnail_variantes (id,job,numero,versao,arquivo,sha256,formato,estado,criado,nota,relatorio) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    vid,self.j['id'],n,versao,str(p),sha,'16:9','aprovada',time.time(),90,json.dumps(rel))
        return vid

    def rejeitar(self,vid=None,versao=1):
        return th.rejeitar(self.j['id'],{'variante_id':vid or self.v2,'versao':versao,'motivo':'Não gostei'},'teste')

    def test_api_recusa_preserva_selecao_e_nao_gera(self):
        antes=db.um('SELECT COUNT(*) n FROM jobs')['n']
        caminho='/api/v1/thumbnails/jobs/'+self.j['id']+'/rejeitar'
        class H:
            headers={}
            path=caminho
            corpo=json.dumps({'variante_id':self.v2,'versao':1}).encode()
        r=api_v1.tratar(H(),'POST',caminho,{'nome':'teste','id':'teste'})
        self.assertEqual(r['selecao']['variante'],self.v1)
        self.assertEqual(th.capa_para_video(self.video)['variante'],self.v1)
        self.assertEqual(db.um('SELECT COUNT(*) n FROM jobs')['n'],antes)
        self.assertEqual(db.um('SELECT estado FROM thumbnail_variantes WHERE id=?',self.v2)['estado'],'rejeitada')
        self.assertTrue(self.rejeitar()['repetido'])
        self.assertEqual(db.um("SELECT COUNT(*) n FROM eventos WHERE recurso=? AND acao='thumbnail_proposta_rejeitada'",'thumb:'+self.j['id'])['n'],1)
        with self.assertRaises(th.ErroThumb):
            th.selecionar(self.j['id'],{'variante_id':self.v2,'versao':1,'confirmacao':True})

    def test_escolhida_preservada_ate_substituta_validada(self):
        with self.assertRaises(th.ErroThumb):
            self.rejeitar(self.v1)
        self.assertTrue(th.selecionar(self.j['id'],{'variante_id':self.v1,'versao':1})['repetido'])
        self.rejeitar()
        self.assertEqual(th.capa_para_video(self.video)['variante'],self.v1)
        nova=self.variante(2,2,'red')
        th.selecionar(self.j['id'],{'variante_id':nova,'versao':2})
        self.assertEqual(th.capa_para_video(self.video)['variante'],nova)
        self.assertEqual(db.um('SELECT COUNT(*) n FROM thumbnail_selecoes WHERE video_sha=? AND revogado IS NULL',self.j['video_sha'])['n'],1)
        self.assertEqual(db.um('SELECT estado FROM thumbnail_variantes WHERE id=?',self.v2)['estado'],'rejeitada')

    def test_flag_off_e_versoes_erradas(self):
        with patch.dict(os.environ,{'THUMB_REJEICAO':'0'}),self.assertRaises(th.ErroThumb):
            self.rejeitar()
        with self.assertRaises(th.ErroThumb):
            self.rejeitar(versao=2)
        self.video.write_bytes(b'render novo')
        with self.assertRaises(th.ErroThumb):
            self.rejeitar()
        self.assertIsNone(th.capa_para_video(self.video))
        self.assertFalse(th.pacote(self.j['id'])['valido'])

if __name__=='__main__':
    unittest.main()
