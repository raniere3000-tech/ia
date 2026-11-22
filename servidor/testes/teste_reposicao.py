"""Agente 2 + Coordenador: você postou antes da hora -> o horário volta a ficar livre, recebe o próximo vídeo aprovado
e, se não houver nenhum, o Agente 2 pede mais ao Coordenador, que manda o Agente 1 cortar.

Rodar: cd servidor && python3 testes/teste_reposicao.py   (sem internet: o Agente 1 é simulado)
"""
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-repo-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
os.environ['CHAVE_MESTRA_ARQ'] = str(TMP / 'chave')
os.environ['COORDENADOR_SEM_VIGIA'] = '1'
os.environ.pop('PIPELINE_V2', None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import banco as db  # noqa: E402
import agente as ag  # noqa: E402
import postagem as pg  # noqa: E402
import pipeline as pl  # noqa: E402
import agenda_postagem as a2  # noqa: E402
import coordenador as co  # noqa: E402
import orquestrador as oq  # noqa: E402

db.migrar()
pg.acordar = lambda: None
ag.enviar_email = lambda *a, **k: 'mid'
ag.avisar = lambda *a, **k: True
PEDIDOS = []
import fila  # noqa: E402

fila.registrar('agente1.pesado', lambda ctx: {'ok': True}, 'pesado')


def falso_a1(oque, link=''):
    PEDIDOS.append(oque)
    return {'job': fila.enfileirar('agente1.pesado', agente='agente1', dados={'oque': oque})['id'], 'fila': True}


ag.ENFILEIRAR = falso_a1
ok = falhas = 0


def check(c, m):
    global ok, falhas
    ok += 1 if c else 0
    falhas += 0 if c else 1
    print('  ok  ' if c else '  FALHOU:', m)


def gerar(nome, cor):
    arq = pg.VIDEOS / nome
    pg.VIDEOS.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', f'color=c={cor}:s=720x1280:d=3:r=30', '-f', 'lavfi', '-i', 'sine=f=300:d=3',
                    '-vf', 'noise=alls=20:allf=t', '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(arq)], check=True)
    return arq


BASE = dict(gancho='', hashtags=['#a'], motivo='m', nota=80, ini=0, fim=3, post='', origem='', origem_titulo='', canal='', canal_nome='', variacoes=[],
            fala='site', tamanho=1, email=False, tipo='manual', direitos={'origem': 'meu', 'nota': ''}, qa={})


def corte_certificado(cid, cor, n):
    arq = gerar(f'{cid}.mp4', cor)
    ag._mudar(lambda e: e['cortes'].append(dict(BASE, id=cid, titulo=f'Corte {cid}', video=cid, chave=cid, criado=n, hash=ag._hash(arq), status='pronto')))
    pl.emitir_certificado(cid, pl.sha_arquivo(arq), {'score': 85, 'blocking_findings': []})


def ordens_repo():
    return [r for r in db.todos('SELECT * FROM coordenador_ordens ORDER BY criado') if (co._l(r['plano_json'], {}) or {}).get('reposicao')]


# dois horários por dia, os dois nas próximas 24 h (fuso de São Paulo)
tz = a2.fuso('America/Sao_Paulo')
agora_l = datetime.now(tz)
h1 = (agora_l + timedelta(hours=3)).strftime('%H:00')
h2 = (agora_l + timedelta(hours=9)).strftime('%H:00')
pl.ligar(True, 'teste')
cfg = a2.criar({'platform': 'youtube', 'mode': 'fixed', 'weekdays': list(range(7)), 'fixed_times': sorted([h1, h2]), 'timezone': 'America/Sao_Paulo'}, 'teste')

print('1. Horários cheios: nada de pedir mais vídeo')
corte_certificado('k1', 'blue', 1)
corte_certificado('k2', 'green', 2)
res = a2.ciclo()
prox = db.todos("SELECT * FROM posting_slots WHERE quando_utc<? AND estado<>'cancelado' ORDER BY quando_utc", time.time() + 24 * 3600)
check(res['agendados'] >= 2 and len(prox) == 2 and all(s['estado'] == 'agendado' for s in prox), f'os 2 horários das próximas 24 h receberam vídeo: {res}')
check('reposicao' not in res and not ordens_repo() and not PEDIDOS, 'com vídeo em todos os horários, o Agente 2 não pede nada')

print('2. Você posta antes da hora: o horário fica livre')
s1 = prox[0]
p1 = s1['post']
pg.postar_agora(p1)
s1b = db.um('SELECT * FROM posting_slots WHERE id=?', s1['id'])
post1 = next(p for p in pg.posts() if p['id'] == p1)
check(s1b['estado'] == 'vazio' and not s1b['post'] and 'antes da hora' in (s1b['motivo'] or ''), f'horário de {s1["hora_local"]} voltou a ficar livre')
check(post1['quando'] <= time.time() and not post1.get('agenda'), 'o post vai agora e não fica mais preso ao horário')
c1 = next(c for c in ag.estado()['cortes'] if c['id'] == 'k1')
check(c1['status'] == 'agendado' and not c1.get('via_agenda') and c1['quando'] <= time.time(), 'o corte já postado não volta para a fila')
check(db.um("SELECT t FROM eventos WHERE acao='slot_liberado'") is not None, 'fica registrado no histórico que o horário foi liberado')

print('3. Sem vídeo para o horário: o Agente 2 pede ao Coordenador, que manda o Agente 1 cortar')
res = a2.ciclo()
s1c = db.um('SELECT * FROM posting_slots WHERE id=?', s1['id'])
check(s1c['estado'] == 'vazio', 'o mesmo corte não é usado de novo para tapar o buraco')
check(res.get('reposicao', {}).get('ok'), f'o Agente 2 pediu mais vídeos: {res.get("reposicao")}')
rs = ordens_repo()
check(len(rs) == 1 and rs[0]['autor'] == 'agente2' and rs[0]['status'] == 'em_execucao', 'o Coordenador abriu uma ordem de reposição')
ts = db.todos('SELECT * FROM coordenador_tarefas WHERE ordem_id=?', rs[0]['id']) if rs else []
check(PEDIDOS == ['cortar'] and any(t['acao'] == 'a1.rodar' and t['job_id'] for t in ts), f'o Agente 1 recebeu "cortar": {PEDIDOS}')

print('4. Sem pedidos repetidos')
res = a2.ciclo()
check(not res.get('reposicao', {}).get('ok') and len(ordens_repo()) == 1 and PEDIDOS == ['cortar'], 'rodar de novo não abre outra ordem enquanto a primeira trabalha')
db.executar("UPDATE coordenador_ordens SET status='concluida' WHERE id=?", rs[0]['id'])
r = co.pedir_reposicao('teste', {})
check(not r['ok'] and 'há pouco' in r['motivo'], 'depois que termina, espera o intervalo antes de pedir de novo')
db.kv_gravar('agente7.ultima_reposicao', time.time() - 2 * 3600)
oq.pausar('teste')
r = co.pedir_reposicao('teste', {})
check(not r['ok'] and 'pausada' in r['motivo'].lower(), 'Central pausada: não pede nada')
oq.retomar('teste')
co.salvar_config({'reposicao_automatica': False}, 'teste')
r = co.pedir_reposicao('teste', {})
check(not r['ok'] and 'desligada' in r['motivo'], 'opção desligada no Coordenador: não pede nada')
co.salvar_config({'reposicao_automatica': True}, 'teste')
check(co.config()['reposicao_intervalo_min'] == 60, 'intervalo padrão de 60 minutos')
try:
    co.salvar_config({'reposicao_intervalo_min': 5}, 'teste')
    check(co.config()['reposicao_intervalo_min'] >= 10, 'intervalo menor que 10 minutos não é aceito')
except co.ErroCoord:
    check(True, 'intervalo menor que 10 minutos não é aceito')

print('4b. Reposição que só falha: não avisa a cada hora e espera cada vez mais')
AVISOS_R = []
_av_orig = ag.avisar
ag.avisar = lambda tipo, assunto, corpo, *a, **k: AVISOS_R.append((assunto, corpo)) or True
db.kv_gravar('agente7.reposicao_falhas', {'n': 0, 'motivo': ''})


def falha_repo(motivo):
    oid = 'rf' + str(len(AVISOS_R)) + str(time.time())[-5:]
    db.executar('INSERT INTO coordenador_ordens (id, autor, texto, plano_json, versao_plano, status, criado, atualizado, chave) VALUES (?,?,?,?,?,?,?,?,?)',
                oid, 'agente2', 'repo', '{"intencao": "fazer_cortes", "reposicao": true, "resposta": "Reposição automática: x"}', 1, 'em_execucao',
                time.time(), time.time(), None)
    tid = co._nova_tarefa(oid, 'cortar', 'agente1', 'a1.rodar', {'oque': 'cortar'}, [])
    co._set_tarefa(tid, estado='falhou', erro=motivo, fim=time.time())
    db.executar("UPDATE coordenador_ordens SET status='falhou' WHERE id=?", oid)
    co._avisar(oid, 'falhou')


falha_repo('O Agente 1 terminou sem nenhum corte aprovado.')
check(len(AVISOS_R) == 1 and 'sem nenhum corte' in AVISOS_R[0][1], 'primeira falha: avisa com o motivo de verdade')
falha_repo('O Agente 1 terminou sem nenhum corte aprovado.')
falha_repo('O Agente 1 terminou sem nenhum corte aprovado.')
check(len(AVISOS_R) == 1, 'mesma falha de novo: não avisa outra vez')
check(co._intervalo_reposicao(co.config()) == 60 * 8, 'depois de 3 falhas seguidas, espera 8 h para pedir de novo')
falha_repo('O Agente 1 não entrou na fila.')
check(len(AVISOS_R) == 2, 'motivo novo: avisa')
for _ in range(10):
    falha_repo('O Agente 1 não entrou na fila.')
check(co._intervalo_reposicao(co.config()) == 24 * 60, 'no máximo 1 pedido por dia enquanto só falha')
co._reposicao_terminou({'id': 'nada'}, 'concluida')
check(co._intervalo_reposicao(co.config()) == 60, 'deu certo: volta ao intervalo normal')
# o motivo que o Agente 1 deu (ex.: nenhum vídeo novo) aparece na tarefa, em vez de só "sem nenhum corte"
jx = fila.enfileirar('agente1.pesado', agente='agente1', dados={'oque': 'cortar', 'teste': 'msg'})['id']
db.executar("UPDATE jobs SET status='concluido', resultado=? WHERE id=?", '{"ok": true, "mensagem": "Nenhum vídeo novo nos canais aprovados."}', jx)
db.executar('INSERT INTO coordenador_ordens (id, autor, texto, plano_json, versao_plano, status, criado, atualizado, chave) VALUES (?,?,?,?,?,?,?,?,?)',
            'rfmsg', 'agente2', 'repo', '{"intencao": "fazer_cortes", "reposicao": true}', 1, 'em_execucao', time.time(), time.time(), None)
tx = co._nova_tarefa('rfmsg', 'cortar', 'agente1', 'a1.rodar', {'oque': 'cortar'}, [])
co._set_tarefa(tx, estado='executando', job_id=jx, resultado={})
co._acompanhar(co._ordem('rfmsg'), next(t for t in co._tarefas('rfmsg') if t['id'] == tx))
tf = next(t for t in co._tarefas('rfmsg') if t['id'] == tx)
check(tf['estado'] == 'falhou' and 'Nenhum vídeo novo nos canais aprovados' in (tf['erro'] or ''), f'a tarefa mostra o motivo do Agente 1: {tf["erro"]}')
ag.avisar = _av_orig
db.executar("DELETE FROM coordenador_tarefas WHERE ordem_id LIKE 'rf%'")
db.executar("DELETE FROM coordenador_ordens WHERE id LIKE 'rf%'")

print('5. O Agente 1 entregou um corte novo: ele vai para o mesmo horário')
corte_certificado('k3', 'red', 3)
res = a2.ciclo()
s1d = db.um('SELECT * FROM posting_slots WHERE id=?', s1['id'])
check(s1d['estado'] == 'agendado' and s1d['ref'] == 'k3', f'o horário de {s1["hora_local"]} recebeu o corte novo')
pk3 = next(p for p in pg.posts() if p['id'] == s1d['post'])
check(abs(pk3['quando'] - s1['quando_utc']) < 1, 'o post novo sai no horário original')

print('6. Caminho antigo (sem programação diária)')
db.executar('UPDATE posting_schedules SET ligado=0')
check(not a2.tem_programacao(), 'programação desligada')
ag.salvar_config({'postagem': {'redes': ['youtube'], 'faixas': [{'dia': d, 'hora': h1} for d in range(7)]}})
ag._mudar(lambda e: [c.update(status='postado') for c in e['cortes']])
db.executar("UPDATE coordenador_ordens SET status='concluida'")
db.kv_gravar('agente7.ultima_reposicao', 0)
antes = len(PEDIDOS)
ag.trabalhar_postagem()
check(len(PEDIDOS) == antes + 1 and len(ordens_repo()) == 2, 'sem corte pronto e com horário livre: pede mais cortes ao Coordenador')
ag.trabalhar_postagem()
check(len(PEDIDOS) == antes + 1, 'não pede de novo enquanto o Agente 1 trabalha')

print('7. Ordem do Coordenador (vídeos próprios, um por dia): postar antes da hora adianta o próximo')
oid = 'ordem7'
agora7 = time.time()
db.executar('INSERT INTO coordenador_ordens (id, autor, texto, plano_json, versao_plano, status, criado, atualizado, chave) VALUES (?,?,?,?,?,?,?,?,?)',
            oid, 'site', '3 vídeos de curiosidades, um por dia', '{"intencao": "produzir_videos", "parametros": {}}', 1, 'em_execucao', agora7, agora7, None)
dia = [agora7 + 86400 * (n + 1) for n in range(3)]
posts7, tids = [], []
for n in range(3):
    tid = co._nova_tarefa(oid, f'agendar_{n + 1}', 'agente2', 'a2.agendar', {'i': n, 'redes': ['youtube'], 'quando': dia[n]}, [])
    tids.append(tid)
    if n < 2:      # vídeos 1 e 2 prontos e agendados; o 3 ainda em produção
        a7 = gerar(f'cur{n}.mp4', ['yellow', 'purple'][n])
        pl.emitir_certificado(f'cur{n}', pl.sha_arquivo(a7), {'score': 85, 'blocking_findings': []})
        pp = pg.criar_post({'video': f'cur{n}', 'redes': ['youtube'], 'quando': dia[n], 'titulo': f'Curiosidade {n + 1}', 'legenda': 'x', 'origem': 'agente3'})
        posts7.append(pp['id'])
        co._set_tarefa(tid, estado='concluida', resultado={'posts': [pp['id']], 'quando': dia[n]})
pg.postar_agora(posts7[0])
ps = {p['id']: p for p in pg.posts()}
t7 = {t['id']: t for t in co._tarefas(oid)}
check(ps[posts7[0]]['quando'] <= time.time(), 'o vídeo 1 sai agora')
check(abs(ps[posts7[1]]['quando'] - dia[0]) < 1, 'o vídeo 2 subiu para o horário que ficou livre (o do vídeo 1)')
check(abs(t7[tids[2]]['parametros']['quando'] - dia[1]) < 1, 'o vídeo 3, ainda em produção, já vai para o horário do vídeo 2')
check(co.eventos(oid, 'antecipado'), 'fica no histórico da ordem')
pg.postar_agora(posts7[0])
check(abs(next(p for p in pg.posts() if p['id'] == posts7[1])['quando'] - dia[0]) < 1, 'tentar de novo o mesmo post não adianta nada de novo')

shutil.rmtree(TMP, ignore_errors=True)
print(f'\n{ok} ok, {falhas} falhas')
sys.exit(1 if falhas else 0)
