"""Tempo máximo do FFmpeg (renderizador.rodar): lento mas andando NÃO é morto; travado é; o erro diz onde.

Motivo (22/11): o Agente 3 falhava 3 vezes com "O FFmpeg passou do tempo máximo." no celular, que é lento.
Usa um "ffmpeg" de mentira (script) que imprime o avanço como o -progress do FFmpeg de verdade.

Rodar: cd servidor && python3 testes/teste_ffmpeg_tempo.py
"""
import os
import stat
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import renderizador as rd  # noqa: E402

ok_n = falhas = 0


def confere(cond, nome):
    global ok_n, falhas
    ok_n, falhas = (ok_n + 1, falhas) if cond else (ok_n, falhas + 1)
    print('  ok ' if cond else '  FALHOU', nome)


TMP = Path(tempfile.mkdtemp(prefix='ec-fftempo-'))
FALSO = TMP / 'ffmpeg'
# argumentos: <passos> <espera entre passos> <código de saída>; com -progress imprime out_time_ms a cada passo
FALSO.write_text('''#!/usr/bin/env python3
import sys, time
o = dict(a.split('=', 1) for a in sys.argv[1:] if '=' in a and not a.startswith('-'))
for i in range(1, int(o.get('passos', 5)) + 1):
    print(f'frame={i * 10}\\nout_time_ms={i * 1000000}\\nprogress=continue', flush=True)
    time.sleep(float(o.get('espera', 0.5)))
print('erro de teste', file=sys.stderr)
sys.exit(int(o.get('cod', 0)))
''')
FALSO.chmod(FALSO.stat().st_mode | stat.S_IEXEC)
F = str(FALSO)


def roda(*args, **kw):
    t0 = time.time()
    try:
        rd.rodar([F, *args], **kw)
        return 'ok', time.time() - t0
    except rd.ErroRender as e:
        return str(e), time.time() - t0


print('1. lento mas andando passa do tempo_max sem ser morto')
rd.FFMPEG_FATOR_TEMPO, rd.FFMPEG_PARADO_S = 4, 600
r, s = roda('passos=6', 'espera=0.5', tempo_max=1.5)       # leva ~3 s; limite 1.5 × 4 = 6 s
confere(r == 'ok', f'terminou ({s:.1f} s, tempo_max 1.5 s)')

print('2. lento demais continua tendo limite (e diz onde)')
rd.FFMPEG_FATOR_TEMPO = 2
r, s = roda('passos=40', 'espera=0.25', tempo_max=1, etapa='plano 2 de 3')
confere('tempo máximo' in r and 'plano 2 de 3' in r and s < 5, f'parou em ~2 s: {r[:90]}')
rd.FFMPEG_FATOR_TEMPO = 4

print('3. travado (sem avançar) é parado pelo tempo sem avanço')
rd.FFMPEG_PARADO_S = 1.5
r, s = roda('passos=1', 'espera=30', tempo_max=100, etapa='cena 4')
confere('travou' in r and 'cena 4' in r and s < 5, f'parou em ~1.5 s sem avanço: {r[:90]}')
r, s = roda('passos=8', 'espera=0.6', tempo_max=100)
confere(r == 'ok', 'avançando a cada 0.6 s não é "travado" (limite sem avanço 1.5 s)')
rd.FFMPEG_PARADO_S = 600

print('4. progresso e erro do FFmpeg')
vistos = []
r, _ = roda('passos=4', 'espera=0.35', progresso=vistos.append, dur=4)
confere(r == 'ok' and vistos and vistos[-1] == 1.0 and vistos == sorted(vistos), f'progresso sobe até 100% ({vistos})')
r, _ = roda('passos=1', 'espera=0', 'cod=1', etapa='juntando as cenas')
confere(r.startswith('FFmpeg falhou (juntando as cenas)') and 'erro de teste' in r, f'falha mostra a etapa e a linha do erro: {r[:80]}')

print('5. cancelar e outros programas')
flag = threading.Event()
threading.Timer(0.8, flag.set).start()
t0 = time.time()
try:
    rd.rodar([F, 'passos=50', 'espera=0.3'], flag.is_set)
    confere(False, 'cancelar interrompe')
except InterruptedError:
    confere(time.time() - t0 < 4, 'cancelar interrompe')
t0 = time.time()
try:
    rd.rodar(['sleep', '5'], tempo_max=1)
    confere(False, 'outro programa: tempo_max vale como antes')
except rd.ErroRender as e:
    confere('tempo máximo' in str(e) and time.time() - t0 < 3, 'outro programa (sem avanço): tempo_max vale como antes')

print(f'\n{ok_n} ok, {falhas} falharam')
sys.exit(1 if falhas else 0)
