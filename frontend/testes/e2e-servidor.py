"""Servidor de teste para testes/e2e-areas.cjs: porta 8799, senha senha-e2e-123, dados de mentira numa pasta temporária."""
import os, sys, tempfile, time, threading
from pathlib import Path
TMP = Path(tempfile.mkdtemp(prefix='ec-e2e-'))
os.environ.update(DADOS=str(TMP/'dados'), BANCO_ARQ=str(TMP/'dados'/'studio.sqlite'), CHAVE_MESTRA_ARQ=str(TMP/'chave'), TOKEN='senha-e2e-123',
                  FILA_INTERVALO='0.3', ESPERA_INICIAL_AGENTE='99999', BACKUP_DIARIO='0', INTERVALO_AGENDA='600', INTERVALO_AGENDA2='600',
                  CENTRAL_SEM_ACORDAR='1', AGENTE6_SEM_VIGIA='1', COORDENADOR_SEM_VIGIA='1')
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'servidor'))
from http.server import ThreadingHTTPServer
import servidor as S, banco as db, postagem as pg, agente as ag
S.ligar_servicos()
agora = time.time()
for jid, a, st, term, dec, tit in [('j1','agente3','concluido',agora-3600,120.0,'Por que o céu é azul'),('j2','agente3','falhou',agora-600,30.0,'Vídeo com erro'),
                                   ('j5','agente3','rodando',None,0.0,'História do café'),('j6','agente1','na_fila',None,0.0,'Corte do canal X')]:
    db.executar('INSERT INTO jobs (id, agente, tipo, projeto, titulo, status, run_at, recurso, criado, iniciado, terminado, decorrido, etapa, progresso, lease, heartbeat, pausado) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', jid, a, 'teste.'+a, '', tit, st, agora-7200, 'leve', agora-7200,
                (term-dec) if term else (agora-95 if st=='rodando' else None), term, dec, 'Montando o vídeo' if st=='rodando' else 'Etapa', 40 if st=='rodando' else 0,
                agora+99999, agora+99999, 1 if st=='na_fila' else 0)
db.executar('INSERT INTO renders (id, projeto, versao, arquivo, sha256, criado) VALUES (?,?,?,?,?,?)', 'r1', 'p', 1, 'x.mp4', 'a'*64, agora-3000)
ag._mudar(lambda e: e['cortes'].append({'id':'c1','criado':agora-100,'status':'pronto'}))
pg.salvar_posts([{'id':'p1','video':'v1','quando':agora+7200,'titulo':'Por que o céu é azul','legenda':'','criado':agora-100,'origem':'manual','hash':'','redes':{'youtube':{'status':'agendado','link':'','erro':''},'tiktok':{'status':'agendado','link':'','erro':''}}},
                 {'id':'p2','video':'v2','quando':agora-3600,'titulo':'Ontem','legenda':'','criado':agora-9000,'origem':'manual','hash':'','redes':{'instagram':{'status':'postado','feito':agora-3600,'link':'https://youtu.be/x','erro':''},'kwai':{'status':'erro','erro':'Falhou de teste','link':''}}}])
print('PRONTO', flush=True)
ThreadingHTTPServer(('127.0.0.1', 8799), S.Handler).serve_forever()
