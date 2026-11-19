"""Agente 2, programação diária: modos fixo/automático/misto, dias e exceções, prévia de 7 dias, fuso, e a regra de ouro:
nenhum horário recebe vídeo sem o certificado do diretor para o arquivo atual. Também cobre o corte manual passando pela esteira.

Rodar: cd servidor && PYTHONPATH=. python3 testes/teste_agenda_agente2.py
"""
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-ag2-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
os.environ.pop('PIPELINE_V2', None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import banco as db  # noqa: E402
import agente as ag  # noqa: E402
import postagem as pg  # noqa: E402
import pipeline as pl  # noqa: E402
import agenda_postagem as a2  # noqa: E402
import rotas_esteira as rt  # noqa: E402

db.migrar()
pg.acordar = lambda: None
ag.enviar_email = lambda *a, **k: 'mid'
ok = falhas = 0


def check(c, m):
    global ok, falhas
    if c:
        ok += 1
        print('  ok  ', m)
    else:
        falhas += 1
        print('  FALHOU:', m)


def erro(f, *a, **k):
    try:
        f(*a, **k)
    except (a2.ErroAgenda, rt.ErroRota) as e:
        return e
    return None


def rota(metodo, caminho, corpo=None, q=None):
    return rt.tratar(metodo, caminho, q or {}, lambda: corpo or {}, 'teste')


print('1. Modo fixo e horários por dia')
yt = {'platform': 'youtube', 'mode': 'fixed', 'weekdays': [0, 1, 2, 3, 4], 'fixed_times': ['09:00', '12:00', '18:00']}
cfg = a2.validar(yt)
check(a2.meta_do_dia(cfg, 0) == 3 and a2.meta_do_dia(cfg, 6) == 0, 'três horários = meta de 3 por dia; domingo sem horário = 0')
check(a2.meta_do_dia(a2.validar(dict(yt, fixed_times=['09:00', '18:00'])), 0) == 2, 'tirar um horário muda a meta sozinho')
check(erro(a2.validar, dict(yt, fixed_times=['09:00', '09:00'])) is not None, 'horário repetido é recusado')
check(erro(a2.validar, dict(yt, fixed_times=['25:00'])) is not None, 'horário inválido é recusado')
check(erro(a2.validar, dict(yt, fixed_times=['09:00', '09:30'])) is not None, 'horários a menos do intervalo mínimo são recusados')
cfg_dia = a2.validar({'platform': 'youtube', 'mode': 'fixed', 'weekly_rules': {'0': ['09:00', '12:00', '18:00'], '6': []}})
check(a2.meta_do_dia(cfg_dia, 0) == 3 and a2.meta_do_dia(cfg_dia, 6) == 0, 'segunda com 3, domingo com 0')
seg = date(2026, 11, 23)
cfg_exc = a2.validar(dict(yt, exceptions={seg.isoformat(): 'pausado'}))
check(a2.horarios_do_dia(cfg_exc, 0, seg.isoformat()) == [] and len(a2.horarios_do_dia(cfg_exc, 0, (seg + timedelta(days=7)).isoformat())) == 3,
      'feriado suspende só a data marcada')
check(erro(a2.validar, dict(yt, foo='bar', platform='orkut')) is not None, 'rede desconhecida é recusada')

print('2. Automático e misto')
auto = a2.validar({'platform': 'instagram', 'mode': 'automatic', 'flex_slots_per_day': 4, 'automatic_window': {'start': '09:00', 'end': '21:00'},
                   'minimum_gap_minutes': 120})
h = [x[0] for x in a2.horarios_do_dia(auto, 2, None)]
check(len(h) == 4 and all(a2._hm(b) - a2._hm(a) >= 120 for a, b in zip(h, h[1:])), f'4 posts espalhados na janela com 2 h de intervalo: {h}')
check(erro(a2.validar, {'platform': 'instagram', 'mode': 'automatic', 'flex_slots_per_day': 8, 'automatic_window': {'start': '09:00', 'end': '12:00'},
                        'minimum_gap_minutes': 60}) is not None, 'quantidade que não cabe na janela é recusada no formulário')
mix = a2.validar({'platform': 'tiktok', 'mode': 'mixed', 'weekdays': [0, 1, 2, 3, 4, 5, 6], 'fixed_times': ['12:00'], 'flex_slots_per_day': 2,
                  'automatic_window': {'start': '10:00', 'end': '20:00'}, 'minimum_gap_minutes': 90})
hm = a2.horarios_do_dia(mix, 3, None)
check(len(hm) == 3 and len({x[0] for x in hm}) == 3 and ('12:00', 'fixo') in hm, f'misto: 1 fixo + 2 flexíveis sem repetir: {hm}')

print('3. Fuso e horário de verão')
utc, off = a2.local_para_utc(date(2026, 11, 20), '09:00', a2.fuso('America/Sao_Paulo'))
check(datetime.fromtimestamp(utc, timezone.utc).hour == 12 and off == '-03:00', '09:00 em São Paulo = 12:00 UTC')
utc, off = a2.local_para_utc(date(2026, 11, 20), '23:30', a2.fuso('America/Sao_Paulo'))
check(datetime.fromtimestamp(utc, timezone.utc).date() == date(2026, 11, 21), 'virada do dia: 23:30 local cai no dia seguinte em UTC')
ny = a2.fuso('America/New_York')
utc, off = a2.local_para_utc(date(2026, 3, 8), '02:30', ny)
check(datetime.fromtimestamp(utc, ny).hour == 3, 'horário que não existe (início do horário de verão) anda para frente')
utc, off = a2.local_para_utc(date(2026, 11, 1), '01:30', ny)
check(off == '-04:00', 'horário repetido (fim do horário de verão) usa a primeira vez')
check(erro(a2.validar, dict(yt, timezone='Marte/Base')) is not None, 'fuso desconhecido é recusado')

print('4. Critério de aceite: YouTube 09/12/18 e Instagram 10/14, prévia de 7 dias')
r_yt = rota('POST', '/api/v1/agent2/schedules', dict(yt, weekdays=list(range(7))))
r_ig = rota('POST', '/api/v1/agent2/schedules', {'platform': 'instagram', 'mode': 'fixed', 'weekdays': [1, 3, 5], 'fixed_times': ['10:00', '14:00']})
check(erro(rota, 'POST', '/api/v1/agent2/schedules', dict(yt)) is not None, 'segunda programação para a mesma conta e rede é recusada')
inicio = (datetime.now(a2.fuso('America/Sao_Paulo')) + timedelta(days=1)).date()
pv = a2.previa(dict(yt, weekdays=list(range(7))), 7, inicio)
check(pv['total'] == 21 and len(pv['dias']) == 7, 'YouTube: 21 horários em 7 dias')
pi = a2.previa({'platform': 'instagram', 'mode': 'fixed', 'weekdays': [1, 3, 5], 'fixed_times': ['10:00', '14:00']}, 7, inicio)
check(pi['total'] == 6, 'Instagram: 2 horários em 3 dias = 6')
check(any('esteira' in x for x in pv['avisos']) and any('aprovado' in x for x in pv['avisos']), 'prévia avisa esteira desligada e falta de vídeo aprovado')
check(db.um('SELECT COUNT(*) n FROM posting_slots')['n'] > 0, 'slots dos próximos dias criados')
antes = db.um('SELECT COUNT(*) n FROM posting_slots')['n']
a2.reconciliar(r_yt['id'])
check(db.um('SELECT COUNT(*) n FROM posting_slots')['n'] == antes, 'reconciliar de novo (ou reiniciar) não duplica horários')
check(erro(rota, 'PATCH', f'/api/v1/agent2/schedules/{r_yt["id"]}', {'fixed_times': ['09:00'], 'version': 99}) is not None,
      'edição com versão velha (outro aparelho) é recusada')
r2 = rota('PATCH', f'/api/v1/agent2/schedules/{r_yt["id"]}', {'fixed_times': ['09:00', '18:00'], 'weekdays': list(range(7)), 'version': r_yt['version']})
check(r2['version'] == 2 and a2.meta_do_dia(r2, 0) == 2, 'edição com a versão certa sobe a versão')
check(db.um("SELECT COUNT(*) n FROM posting_slots WHERE agenda=? AND hora_local='12:00' AND estado='cancelado'", r_yt['id'])['n'] > 0,
      'horário vazio que saiu da programação é cancelado')

print('5. Sem certificado, nada é agendado')


def gerar(nome, cor):
    arq = pg.VIDEOS / nome
    subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', f'color=c={cor}:s=720x1280:d=4:r=30', '-f', 'lavfi', '-i', 'sine=f=300:d=4',
                    '-vf', 'noise=alls=20:allf=t', '-c:v', 'libx264',
                    '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(arq)], check=True)
    return arq


arq1 = gerar('va1.mp4', 'blue')
arq2 = gerar('va2.mp4', 'green')
base = dict(gancho='', hashtags=['#a'], motivo='m', nota=80, ini=0, fim=4, post='', origem='', origem_titulo='', canal='', canal_nome='', variacoes=[], fala='site',
            tamanho=1, email=False, tipo='manual', direitos={'origem': 'meu', 'nota': ''}, qa={})
ag._mudar(lambda e: e['cortes'].extend([dict(base, id='k1', titulo='Um', video='va1', chave='x1', criado=1, hash=ag._hash(arq1), status='pronto'),
                                         dict(base, id='k2', titulo='Dois', video='va2', chave='x2', criado=2, hash=ag._hash(arq2), status='pronto')]))
check(a2.ciclo()['agendados'] == 0, 'esteira desligada: nenhum horário recebe vídeo')
pl.ligar(True, 'teste')
check(a2.ciclo()['agendados'] == 0 and not pg.posts(), 'esteira ligada mas sem certificado: nenhum post criado')
rel_ruim = {'score': 69, 'blocking_findings': [], 'findings': [], 'partes': {}, 'passed': False}
try:
    pl.emitir_certificado('k1', pl.sha_arquivo(arq1), rel_ruim)
    check(False, 'nota 69 não pode ganhar certificado')
except pl.ErroPipeline:
    check(True, 'nota 69 não ganha certificado (logo nunca é agendada)')
try:
    pl.emitir_certificado('k1', pl.sha_arquivo(arq1), {'score': 70, 'blocking_findings': [{'category': 'audio', 'evidence': 'sem som'}]})
    check(False, 'nota 70 com bloqueio não pode ganhar certificado')
except pl.ErroPipeline:
    check(True, 'nota 70 com bloqueio técnico não ganha certificado')
pl.emitir_certificado('k1', pl.sha_arquivo(arq1), {'score': 70, 'blocking_findings': []})
res = a2.ciclo()
s1 = db.todos("SELECT * FROM posting_slots WHERE estado='agendado'")
check(res['agendados'] == 2 and {x['rede'] for x in s1} == {'youtube', 'instagram'} and all(x['ref'] == 'k1' for x in s1),
      'nota 70 sem bloqueio: 1 horário por rede recebe o vídeo (cada rede é uma publicação)')
check(len(pg.posts()) == 2 and all(len(p['redes']) == 1 and p['origem'] == 'agenda' for p in pg.posts()), 'um post por rede, marcado como da agenda')
check(a2.ciclo()['agendados'] == 0, 'rodar de novo não duplica nem repete o vídeo para tapar buraco')
check(db.um("SELECT COUNT(*) n FROM posting_slots WHERE estado='vazio'")['n'] > 0, 'os outros horários ficam vazios')

print('6. Arquivo mudou depois do certificado')
with open(arq2, 'ab') as f:
    f.write(b'\0' * 16)
pl.emitir_certificado('k2', 'f' * 64, {'score': 90, 'blocking_findings': []})       # certificado de OUTRO arquivo
check(a2.ciclo()['agendados'] == 0, 'certificado que não bate com o SHA do arquivo atual: não agenda')
p0 = pg.posts()[0]
with open(arq1, 'ab') as f:
    f.write(b'\0' * 16)
conf = pg.conferencia(p0, list(p0['redes'])[0])
check(any(x['item'] == 'certificado' and x['bloqueia'] for x in conf), 'arquivo alterado depois de agendado: a conferência na hora de postar barra')

print('7. Horário perdido (servidor desligado)')
s = s1[0]
db.executar('UPDATE posting_slots SET quando_utc=? WHERE id=?', time.time() - 3600, s['id'])
pg._mudar(s['post'], lambda q: q.update(quando=time.time() - 3600, agenda=dict(q['agenda'], ate=time.time() - 3600 + 900)))
conf = pg.conferencia(next(p for p in pg.posts() if p['id'] == s['post']), s['rede'])
check(any(x['item'] == 'horario' and x['bloqueia'] for x in conf), 'next_slot: a conferência não deixa postar atrasado')
a2.ciclo()
check(db.um('SELECT estado FROM posting_slots WHERE id=?', s['id'])['estado'] == 'perdido' and not any(p['id'] == s['post'] for p in pg.posts()),
      'horário vira "perdido" e o post atrasado é cancelado')
check(next(c for c in ag.estado()['cortes'] if c['id'] == 'k1')['status'] in ('pronto', 'agendado'), 'o vídeo volta para a fila (ou segue no outro horário)')

print('8. Cancelar um horário pela tela')
s = db.um("SELECT * FROM posting_slots WHERE estado='agendado' LIMIT 1")
if s:
    r = rota('PATCH', f'/api/v1/agent2/slots/{s["id"]}', {'acao': 'cancelar'})
    check(r['estado'] == 'cancelado' and not any(p['id'] == s['post'] for p in pg.posts()), 'cancelar libera o horário e apaga o post')
    a2.reconciliar(s['agenda'])
    check(db.um('SELECT estado FROM posting_slots WHERE id=?', s['id'])['estado'] == 'cancelado', 'cancelado por você não volta sozinho')
else:
    check(False, 'havia um horário agendado para cancelar')
m = rota('GET', '/api/v1/agent2/metrics')
check('youtube' in m['por_rede'] and 'meta' in m['por_rede']['youtube'], 'métricas por rede')

print('9. Corte manual do site passa pelo editor e pelo diretor')
import fila  # noqa: E402
fila.registrar('esteira.recebido', ag.job_esteira_recebido, 'pesado')
arq3 = gerar('va3.mp4', 'red')
ag.salvar_config({'postagem': {'redes': ['youtube']}})
r = ag.receber_manual({'video': 'va3', 'titulo': 'Manual', 'direitos': {'origem': 'meu'}, 'destino': 'pronto'})
c = next(x for x in ag.estado()['cortes'] if x['id'] == r['id'])
check(c['qa']['diretor']['veredito'] == 'conferindo', 'corte manual fica "conferindo" enquanto o diretor olha')
j = db.um("SELECT * FROM jobs WHERE tipo='esteira.recebido'")
check(j is not None, 'trabalho pesado do diretor entrou na fila')


class Ctx:
    def __init__(self, d):
        self.dados = d

    def progresso(self, *a):
        pass


import json  # noqa: E402
out = ag.job_esteira_recebido(Ctx(json.loads(j['dados'])))
c = next(x for x in ag.estado()['cortes'] if x['id'] == r['id'])
check(c['qa']['diretor']['veredito'] == 'aprovado' and c['status'] == 'pronto', f'aprovado pelo diretor (nota {c["qa"]["nota"]})')
check(pl.portao_postagem(pg.video_path('va3'))['ok'], 'certificado preso ao arquivo do corte manual')

shutil.rmtree(TMP, ignore_errors=True)
print(f'\n{ok} ok, {falhas} falhas')
sys.exit(1 if falhas else 0)
