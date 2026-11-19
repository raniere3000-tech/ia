"""Painel do Início e da Central de Agentes (GET /api/v1/dashboard/resumo), com servidor HTTP de verdade e SQLite.

Confere: precisa de login; nada inventado (vazio = 0 contado ou None quando a fonte não existe); vídeos ≠ tarefas;
agendado ≠ publicado; tempo ativo = soma medida (decorrido); filtro Hoje/7d/30d; o painel não grava nada.

Rodar: cd servidor && python3 testes/teste_painel.py
"""
import json
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import socket
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-painel-'))
os.environ.update(DADOS=str(TMP / 'dados'), BANCO_ARQ=str(TMP / 'dados' / 'studio.sqlite'), CHAVE_MESTRA_ARQ=str(TMP / 'chave'),
                  TOKEN='senha-de-teste-123', FILA_INTERVALO='0.3', ESPERA_INICIAL_AGENTE='99999', BACKUP_DIARIO='0',
                  INTERVALO_AGENDA='600', INTERVALO_AGENDA2='600', CENTRAL_SEM_ACORDAR='1', AGENTE6_SEM_VIGIA='1', COORDENADOR_SEM_VIGIA='1')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ok_n = falhas = 0


def confere(cond, nome):
    global ok_n, falhas
    if cond:
        ok_n += 1
        print('  ok ', nome)
    else:
        falhas += 1
        print('  FALHOU', nome)


def livre():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


import servidor as S  # noqa: E402
import banco as db  # noqa: E402
import postagem as pg  # noqa: E402
import agente as ag  # noqa: E402
import painel  # noqa: E402

fila_parar = None
S.ligar_servicos()
porta = livre()
threading.Thread(target=ThreadingHTTPServer(('127.0.0.1', porta), S.Handler).serve_forever, daemon=True).start()
BASE = f'http://127.0.0.1:{porta}'


def api(caminho, cab=None):
    req = urllib.request.Request(BASE + caminho, headers=cab or {})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        return e.code, None


TOK = {'X-Token': 'senha-de-teste-123'}
agora = time.time()

print('1. login')
st, _ = api('/api/v1/dashboard/resumo')
confere(st == 401, 'sem senha o painel não abre (401)')
st, r = api('/api/v1/dashboard/resumo?periodo=7d', TOK)
confere(st == 200 and r['periodo'] == '7d' and r['backend_disponivel'] is True, 'com senha abre')
confere(len(r['agentes']) == 7 and [a['id'] for a in r['agentes']] == [f'agente{i}' for i in range(1, 8)], 'sete agentes, na ordem 1..7')
confere(r['totais']['agendados'] == 0 and r['totais']['publicados'] == 0 and r['proxima_publicacao'] is None, 'servidor vazio: zero contado e sem próxima publicação')
confere(r['totais']['aprovados_disponiveis'] is None, 'esteira desligada: "aprovados" fica indisponível (None), não 0')
a7 = r['agentes'][6]
confere(a7['estado'] == 'parado', 'A7 parado quando não há ordem (abrir a tela não o deixa "rodando")')

print('2. dados de verdade no banco')
JOBS = [  # id, agente, status, terminado, decorrido
    ('j1', 'agente3', 'concluido', agora - 3600, 120.0),
    ('j2', 'agente3', 'concluido', agora - 3 * 86400, 60.0),
    ('j3', 'agente3', 'falhou', agora - 600, 30.0),
    ('j4', 'agente6', 'concluido', agora - 20 * 86400, 45.0),
    ('j5', 'agente1', 'rodando', None, 0.0),
    ('j6', 'agente1', 'na_fila', None, 0.0),
]
for jid, a, stt, term, dec in JOBS:
    db.executar('INSERT INTO jobs (id, agente, tipo, projeto, titulo, status, run_at, recurso, criado, iniciado, terminado, decorrido, etapa) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', jid, a, 'teste.' + a, '', 'Trabalho ' + jid, stt, agora - 7200, 'leve',
                agora - 7200, (term - dec) if term else (agora - 50 if stt == 'rodando' else None), term, dec, 'Etapa')
# a fila de verdade está ligada: estes trabalhos de mentira não podem ser pegos por ela
db.executar("UPDATE jobs SET lease=?, heartbeat=?, pausado=CASE WHEN status='na_fila' THEN 1 ELSE 0 END WHERE id IN ('j5','j6')", agora + 99999, agora + 99999)
# o mesmo arquivo renderizado duas vezes conta como UM vídeo
for rid, sha, t in (('r1', 'a' * 64, agora - 3600), ('r2', 'a' * 64, agora - 1800), ('r3', 'b' * 64, agora - 2 * 86400)):
    db.executar('INSERT INTO renders (id, projeto, versao, arquivo, sha256, criado) VALUES (?,?,?,?,?,?)', rid, 'p', 1, 'x.mp4', sha, t)
ag._mudar(lambda e: e['cortes'].extend([{'id': 'c1', 'criado': agora - 100, 'status': 'pronto'},
                                        {'id': 'c2', 'criado': agora - 100, 'status': 'descartado'},
                                        {'id': 'c3', 'criado': agora - 40 * 86400, 'status': 'postado'}]))
pg.salvar_posts([
    {'id': 'p1', 'video': 'v1', 'quando': agora + 7200, 'titulo': 'Mais tarde', 'redes': {'youtube': {'status': 'agendado'}, 'tiktok': {'status': 'agendado'}}},
    {'id': 'p2', 'video': 'v2', 'quando': agora + 3600, 'titulo': 'Logo', 'redes': {'instagram': {'status': 'agendado'}, 'facebook': {'status': 'postado', 'feito': agora - 60}}},
    {'id': 'p3', 'video': 'v3', 'quando': agora - 86400 * 10, 'titulo': 'Antigo', 'redes': {'youtube': {'status': 'postado', 'feito': agora - 86400 * 10}, 'kwai': {'status': 'erro'}}},
])
antes_posts = json.dumps(pg.posts(), sort_keys=True)
antes_jobs = db.todos('SELECT * FROM jobs ORDER BY id')

st, r = api('/api/v1/dashboard/resumo?periodo=7d', TOK)
t = r['totais']
confere(t['videos_por_origem'] == {'agente1': 1, 'agente3': 2}, 'vídeos: 1 corte (descartado e antigo ficam fora) + 2 arquivos distintos do Agente 3')
confere(t['videos_criados'] == 3, 'total de vídeos = 3 (render repetido do mesmo SHA conta uma vez)')
confere(t['em_producao'] == 2, 'em produção = 2 tarefas (rodando + na fila), separado de vídeos')
confere(t['agendados'] == 3, 'agendados = 3 envios por rede (YouTube, TikTok, Instagram)')
confere(t['publicados'] == 1, 'publicados em 7 dias = 1 (o de 10 dias atrás fica fora; agendado não conta)')
confere(t['falhas'] == 1 and t['posts_com_erro'] == 1, 'falhas de tarefa e posts com erro separados')
confere(r['proxima_publicacao'] and r['proxima_publicacao']['post'] == 'p2' and r['proxima_publicacao']['redes'] == ['instagram'],
        'próxima publicação = a mais cedo, só com as redes ainda agendadas')
a3 = next(a for a in r['agentes'] if a['id'] == 'agente3')
confere(a3['concluidas_periodo'] == 2 and a3['falhas_periodo'] == 1, 'Agente 3: 2 concluídas e 1 falha em 7 dias')
confere(a3['tempo_ativo_s'] == 210, 'Agente 3: tempo ativo = soma medida (120+60+30 s)')
a6 = next(a for a in r['agentes'] if a['id'] == 'agente6')
confere(a6['concluidas_periodo'] == 0 and a6['tempo_ativo_s'] is None, 'Agente 6: sem trabalho no período → tempo "não disponível" (None), não 0')
a1 = next(a for a in r['agentes'] if a['id'] == 'agente1')
confere(a1['estado'] == 'trabalhando' and a1['na_fila'] == 1, 'Agente 1: estado atual vem da fila (trabalhando, 1 na fila)')
a2 = next(a for a in r['agentes'] if a['id'] == 'agente2')
confere(a2['concluidas_periodo'] == 1 and a2['unidade'] == 'posts por rede', 'Agente 2 conta posts feitos, não tarefas')
confere(any(x['tipo'] == 'post_erro' for x in r['alertas']) and any(x['tipo'] == 'falha' for x in r['alertas']), 'alertas só do que existe (post com erro, falha nas últimas 24 h)')

print('3. períodos')
st, r30 = api('/api/v1/dashboard/resumo?periodo=30d', TOK)
a6 = next(a for a in r30['agentes'] if a['id'] == 'agente6')
confere(a6['concluidas_periodo'] == 1 and a6['tempo_ativo_s'] == 45, '30 dias inclui o trabalho de 20 dias atrás')
confere(r30['totais']['publicados'] == 2, '30 dias inclui o post de 10 dias atrás')
st, rh = api('/api/v1/dashboard/resumo?periodo=hoje', TOK)
lt = time.localtime(rh['inicio'])
confere(rh['periodo'] == 'hoje' and (lt.tm_hour, lt.tm_min, lt.tm_sec) == (0, 0, 0), 'Hoje começa à meia-noite no fuso do servidor')
st, rx = api('/api/v1/dashboard/resumo?periodo=qualquer', TOK)
confere(rx['periodo'] == '7d', 'período desconhecido vira 7 dias')
confere(painel.inicio_periodo('7d', 1000000.0) == 1000000.0 - 7 * 86400, 'janela de 7 dias exata')

print('4. só leitura')
confere(json.dumps(pg.posts(), sort_keys=True) == antes_posts, 'posts iguais depois de ler o painel (nada postado nem mudado)')
confere([(j['id'], j['status']) for j in db.todos('SELECT id, status FROM jobs ORDER BY id')] == [(j['id'], j['status']) for j in antes_jobs], 'fila não mexida pelo painel')
txt = json.dumps(r)
confere('senha-de-teste-123' not in txt and 'token' not in txt.lower(), 'resposta sem senha nem token')

print(f'\n{ok_n} ok, {falhas} falharam')
sys.exit(1 if falhas else 0)
