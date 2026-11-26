"""Lotes por rede: prévia, idempotência, calendário, cancelamento e ritmo de envio."""
import copy
import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

TMP = Path(tempfile.mkdtemp(prefix='ec-lotes-'))
os.environ.update(DADOS=str(TMP), BANCO_ARQ=str(TMP/'studio.sqlite'), ESTEIRA_COMPLETA='0', TOKEN='senha-teste-lotes-123', CENTRAL_SEM_ACORDAR='1')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import banco as db
import postagem as pg
import publicacao_lotes as lotes
import agenda_postagem as agenda

db.migrar()


class PublicacaoLotes(unittest.TestCase):
    def setUp(self):
        pg.salvar_posts([])
        pg._gravar(pg.DADOS/'ritmo_posts.json', {})
        db.executar('DELETE FROM kv')
        db.executar('DELETE FROM posting_slots')
        db.executar('DELETE FROM posting_schedules')
        self.inicio = time.time()+3600

    def post(self, id, redes=None, video=None):
        video = video or 'video'+id
        (pg.VIDEOS/(video+'.mp4')).write_bytes(b'x'*2000)
        p = {'id': id, 'video': video, 'titulo': 'Vídeo '+id, 'quando': self.inicio-7200, 'criado': self.inicio-7200,
             'redes': copy.deepcopy(redes or {'youtube': {'status':'postado', 'link':'https://youtube.com/x', 'erro':''}}),
             'legenda': '', 'opcoes': {}, 'hash': video}
        pg.salvar_posts(pg.posts()+[p])
        return p

    def pedido(self, ids, **extra):
        return dict(posts=ids, redes=['tiktok'], inicio=self.inicio, intervalo_min=30, intervalo_api_s=30,
                    modo='intervalo', reagendar=False, **extra)

    def criar(self, d, chave='lote-teste-123456'):
        previa=lotes.previa(d)
        req=dict(d, chave=chave, versao=previa['versao'])
        return lotes.criar(req), req

    def test_horarios_independentes_e_preview_so_leitura(self):
        p1,p2=self.post('p1'),self.post('p2',{'youtube':{'status':'agendado','link':'','erro':'','quando':self.inicio+9000}})
        antes=copy.deepcopy(pg.posts())
        d=self.pedido(['p2','p1'])
        pv=lotes.previa(d)
        self.assertEqual(pg.posts(),antes)
        self.assertEqual([x['quando'] for x in pv['agendados']],[self.inicio,self.inicio+1800])
        self.criar(d)
        for p in pg.posts():
            original=next(x for x in (p1,p2) if x['id']==p['id'])
            self.assertEqual(p['redes']['youtube'],original['redes']['youtube'])
            self.assertEqual(p['quando'],original['quando'])
        self.assertEqual(pg.posts()[1]['redes']['tiktok']['quando'],self.inicio)

    def test_pulados_duplicados_arquivos_e_liberacao(self):
        self.post('p1',{'tiktok':{'status':'postado','link':'ok','erro':''}})
        self.post('p2',{'tiktok':{'status':'agendado','link':'','erro':''}})
        self.post('p3')
        self.post('p4',video='videop3')
        self.post('p5',{'tiktok':{'status':'liberacao','link':'','erro':'confira'}})
        self.post('p6'); (pg.VIDEOS/'videop6.mp4').unlink()
        pv=lotes.previa(self.pedido(['p1','p2','p3','p4','p5','p6']))
        self.assertEqual([x['post'] for x in pv['agendados']],['p3'])
        self.assertEqual(len(pv['ignorados']),3)
        self.assertEqual(len(pv['ajustes']),2)

    def test_reagendar_apenas_com_opcao_explicita(self):
        self.post('p1',{'tiktok':{'status':'agendado','link':'','erro':'','quando':self.inicio+900}})
        d=self.pedido(['p1'])
        self.assertEqual(len(lotes.previa(d)['ignorados']),1)
        d['reagendar']=True
        self.criar(d)
        self.assertEqual(pg.posts()[0]['redes']['tiktok']['quando'],self.inicio)

    def test_idempotencia_e_guardas_de_preview(self):
        self.post('p1')
        d=self.pedido(['p1'])
        r,req=self.criar(d)
        antes=copy.deepcopy(pg.posts())
        self.assertTrue(lotes.criar(req)['repetido'])
        self.assertEqual(pg.posts(),antes)
        with self.assertRaises(pg.ErroRede):
            lotes.criar(dict(req, intervalo_min=60))
        self.post('p2')
        d2=self.pedido(['p2'])
        pv=lotes.previa(d2)
        self.post('p3',{'tiktok':{'status':'agendado','link':'','erro':'','quando':pv['agendados'][0]['quando']}})
        with self.assertRaises(pg.ErroRede):
            lotes.criar(dict(d2,chave='lote-velho-123456',versao=pv['versao']))
        self.assertNotIn('tiktok',next(p for p in pg.posts() if p['id']=='p2')['redes'])

    def test_pausa_retomada_cancelamento_preserva_publicados(self):
        self.post('p1');self.post('p2')
        res,_=self.criar(self.pedido(['p1','p2']))
        lid=res['lote']
        lotes.acao(lid,'pausar')
        self.assertTrue(lotes.listar()['lotes'][0]['pausado'])
        pg._mudar('p1',lambda p:p['redes']['tiktok'].update(status='postado',link='https://tiktok.com/v1'))
        lotes.acao(lid,'retomar')
        self.assertFalse(lotes.listar()['lotes'][0]['pausado'])
        lotes.acao(lid,'cancelar')
        self.assertEqual(pg.posts()[0]['redes']['tiktok']['status'],'postado')
        self.assertEqual(pg.posts()[1]['redes']['tiktok']['status'],'cancelado')
        self.assertEqual(pg.posts()[0]['redes']['youtube']['status'],'postado')
        db.con().close(); del db._local.c
        self.assertEqual(lotes.listar()['lotes'][0]['cancelados'],1)

    def test_intervalo_api_quando_servidor_volta_atrasado(self):
        self.post('p1');self.post('p2')
        self.criar(self.pedido(['p1','p2']))
        enviados=[]
        clock=[self.inicio+7200]
        with patch.object(pg,'agora',side_effect=lambda:clock[0]), patch.object(pg,'conferencia',return_value=[]), \
             patch.dict(pg.PUBLICAR,{'tiktok':lambda p,a:enviados.append(p['id']) or 'ok'}):
            pg.ciclo()
            self.assertEqual(enviados,['p1'])
            pg.ciclo(); self.assertEqual(enviados,['p1'])
            clock[0]+=31
            pg.ciclo(); self.assertEqual(enviados,['p1','p2'])

    def test_pausa_e_cancelamento_reconferidos_na_fila(self):
        self.post('p1');self.post('p2')
        res,_=self.criar(self.pedido(['p1','p2']))
        enviados=[]
        def enviar(p,a):
            enviados.append(p['id'])
            lotes.acao(res['lote'],'cancelar')
            return 'ok'
        with patch.object(pg,'agora',return_value=self.inicio+7200), patch.object(pg,'conferencia',return_value=[]), \
             patch.dict(pg.PUBLICAR,{'tiktok':enviar}):
            lotes.acao(res['lote'],'pausar');pg.ciclo();self.assertEqual(enviados,[])
            lotes.acao(res['lote'],'retomar');pg.ciclo()
        self.assertEqual(enviados,['p1'])
        self.assertEqual(pg.posts()[1]['redes']['tiktok']['status'],'cancelado')

    def test_publicacao_mantem_portoes(self):
        self.post('p1');self.criar(self.pedido(['p1']))
        with patch.object(pg,'agora',return_value=self.inicio+10), \
             patch.object(pg,'conferencia',return_value=[{'item':'diretor','ok':False,'bloqueia':True,'detalhe':'Sem aprovação'}]), \
             patch.dict(pg.PUBLICAR,{'tiktok':lambda p,a:self.fail('publicou sem aprovação')}),patch.object(pg,'_avisar_falha'):
            pg.ciclo()
        self.assertEqual(pg.posts()[0]['redes']['tiktok']['status'],'erro')

    def test_retry_after_bloqueia_so_rede_afetada(self):
        self.post('p1',{'tiktok':{'status':'agendado','link':'','erro':''}})
        self.post('p2',{'tiktok':{'status':'agendado','link':'','erro':''},'youtube':{'status':'agendado','link':'','erro':''}})
        enviados=[]
        def limitado(p,a):
            enviados.append(('tiktok',p['id']))
            raise pg.ErroTemporario('limite',600)
        with patch.object(pg,'agora',return_value=self.inicio), patch.object(pg,'conferencia',return_value=[]), \
             patch.dict(pg.PUBLICAR,{'tiktok':limitado,'youtube':lambda p,a:enviados.append(('youtube',p['id'])) or 'ok'}):
            pg.ciclo()
        self.assertEqual([x for x in enviados if x[0]=='tiktok'],[('tiktok','p1')])
        self.assertIn(('youtube','p2'),enviados)
        self.assertGreaterEqual(pg.posts()[0]['redes']['tiktok']['proxima'],self.inicio+600)
        e=urllib.error.HTTPError('https://exemplo',429,'limite',{'Retry-After':'120'},io.BytesIO(b'{"error":"limite"}'))
        with patch.object(urllib.request,'urlopen',side_effect=e):
            st,_,j=pg.http('GET','https://exemplo')
        with self.assertRaises(pg.ErroTemporario) as ctx:
            pg._ok(st,j,'enviar')
        self.assertEqual(ctx.exception.retry_after,120)

    def test_postar_agora_so_rede_escolhida(self):
        self.post('p1',{'tiktok':{'status':'agendado','quando':self.inicio+600,'link':'','erro':''},
                        'youtube':{'status':'agendado','quando':self.inicio+7200,'link':'','erro':''}})
        youtube=copy.deepcopy(pg.posts()[0]['redes']['youtube'])
        pg.postar_agora('p1','tiktok')
        self.assertEqual(pg.posts()[0]['redes']['youtube'],youtube)
        self.assertLess(pg.posts()[0]['redes']['tiktok']['quando'],self.inicio)

    def slot(self,id,quando):
        db.executar("INSERT OR IGNORE INTO posting_schedules (id, conta, rede, fuso, modo, regras, ligado, apagado) VALUES ('agenda','conta','tiktok','America/Sao_Paulo','fixed','{}',1,0)")
        db.executar("INSERT INTO posting_slots (id,agenda,conta,rede,data_local,hora_local,quando_utc,tipo,estado) VALUES (?,'agenda','conta','tiktok','2026-11-24',?,?,'fixed','vazio')",id,time.strftime('%H:%M',time.gmtime(quando)),quando)

    def test_programacao_reserva_e_recupera_slot(self):
        self.post('p1');self.post('p2')
        self.slot('slot1',self.inicio+900);self.slot('slot2',self.inicio+2700)
        d=self.pedido(['p1','p2']);d['modo']='programacao'
        res,_=self.criar(d)
        self.assertEqual([x['quando'] for x in res['agendados']],[self.inicio+900,self.inicio+2700])
        self.assertEqual(db.um("SELECT post FROM posting_slots WHERE id='slot1'")['post'],'p1')
        db.executar("UPDATE posting_slots SET estado='vazio',post=NULL WHERE id='slot1'")
        s=db.um("SELECT * FROM posting_slots WHERE id='slot1'")
        self.assertEqual(agenda._reservar(s,{}),'agendado')
        self.assertEqual(db.um("SELECT post FROM posting_slots WHERE id='slot1'")['post'],'p1')
        self.assertEqual(len(pg.posts()),2)
        lotes.acao(res['lote'],'pausar')
        agenda._acompanhar(db.um("SELECT * FROM posting_slots WHERE id='slot1'"),{})
        self.assertEqual(db.um("SELECT estado FROM posting_slots WHERE id='slot1'")['estado'],'agendado')

    def test_rotas_http_exigem_login_e_agendam(self):
        import servidor as S
        self.post('p1')
        servidor=ThreadingHTTPServer(('127.0.0.1',0),S.Handler)
        threading.Thread(target=servidor.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{servidor.server_port}'
        def request(path,data=None,token=True):
            headers={'Content-Type':'application/json'}
            if token:headers['X-Token']=os.environ['TOKEN']
            req=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
            with urllib.request.urlopen(req,timeout=10) as r:return json.loads(r.read())
        try:
            with self.assertRaises(urllib.error.HTTPError) as ctx:request('/posts/lotes',token=False)
            self.assertEqual(ctx.exception.code,401)
            d=self.pedido(['p1'])
            pv=request('/posts/lotes/previa',d)
            res=request('/posts/lotes',dict(d,chave='lote-http-123456',versao=pv['versao']))
            self.assertEqual(len(res['agendados']),1)
            self.assertEqual(len(request('/posts/lotes')['lotes']),1)
            self.assertTrue(request('/posts/lotes/'+res['lote']+'/pausar',{})['lotes'][0]['pausado'])
        finally:
            servidor.shutdown();servidor.server_close()


if __name__=='__main__':unittest.main()
