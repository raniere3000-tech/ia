"""Agente 2: cada rede é independente. TikTok com erro ou travado não impede o YouTube; a falha avisa na hora
e dá para tentar de novo só na rede que falhou.

Rodar:  python servidor/testes/teste_redes_independentes.py   (sem internet: as redes são simuladas)
"""
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import sys
import tempfile
import threading
import time
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='redes-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
os.environ['CHAVE_MESTRA_ARQ'] = str(TMP / 'chave')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import banco as db  # noqa: E402
import agente as ag  # noqa: E402
import postagem as pg  # noqa: E402

falhas = ok = 0


def confere(c, nome):
    global falhas, ok
    print(('ok    ' if c else 'FALHA ') + nome)
    falhas += 0 if c else 1
    ok += 1 if c else 0


db.migrar()
pg.status_contas = lambda: {k: {'conectado': True, 'erro': '', 'paginas': [], 'pagina': ''} for k in set(pg.PROV.values())}
pg.conferencia = lambda p, rede: [{'item': 'arquivo', 'ok': True, 'bloqueia': False, 'detalhe': ''}]
AVISOS = []
ag.avisar = lambda tipo, assunto, corpo, *a, **k: AVISOS.append((tipo, assunto, corpo)) or True
enviados = []
TIKTOK = {'modo': 'erro'}
LIBERA = threading.Event()


def tiktok(p, arq):
    if TIKTOK['modo'] == 'erro':
        raise pg.ErroRede('TikTok recusou (unaudited_client_can_only_post_to_private_accounts): o app ainda não foi aprovado.')
    if TIKTOK['modo'] == 'trava':
        LIBERA.wait(20)
    if TIKTOK['modo'] == 'quebra':
        raise KeyError('data')
    enviados.append(('tiktok', p['id']))
    return 'Enviado ao TikTok'


pg.PUBLICAR['tiktok'] = tiktok
pg.PUBLICAR['youtube'] = lambda p, arq: (enviados.append(('youtube', p['id'])), 'https://youtu.be/x')[1]
pg.PUBLICAR['instagram'] = lambda p, arq: (enviados.append(('instagram', p['id'])), 'https://instagram.com/p/x')[1]
pg.VIDEOS.mkdir(parents=True, exist_ok=True)


def post(n, redes):
    (pg.VIDEOS / f'v{n}.mp4').write_bytes(os.urandom(5000))
    p = pg.criar_post({'video': f'v{n}', 'redes': redes, 'quando': pg.agora() - 5, 'titulo': f'Vídeo {n}', 'legenda': 'x'})
    return p['id']


def st(pid):
    return {r: x['status'] for r, x in next(x for x in pg.posts() if x['id'] == pid)['redes'].items()}


# 1. TikTok primeiro na lista e com erro: YouTube e Instagram postam do mesmo jeito
p1 = post(1, ['tiktok', 'youtube', 'instagram'])
pg.ciclo()
s = st(p1)
confere(s == {'tiktok': 'erro', 'youtube': 'postado', 'instagram': 'postado'}, f'TikTok com erro não impede YouTube e Instagram: {s}')
confere(any('Tiktok' in a[1] and ('Youtube' in a[1] or 'Ainda vai para: Youtube' in a[2]) for a in AVISOS),
        'aviso na hora: falhou no TikTok e diz que o YouTube foi ou vai sem depender dele')
confere(any('Tentar de novo no Tiktok' in a[2] for a in AVISOS), 'o aviso diz como tentar de novo só no TikTok')

# 2. tentar de novo só no TikTok: não reenvia o YouTube
TIKTOK['modo'] = 'ok'
n_yt = sum(1 for e in enviados if e[0] == 'youtube')
pg.postar_agora(p1, 'tiktok')
pg.ciclo()
s = st(p1)
confere(s['tiktok'] == 'postado' and sum(1 for e in enviados if e[0] == 'youtube') == n_yt, f'tentar de novo só no TikTok: posta lá e não repete o YouTube ({s})')
try:
    pg.postar_agora(p1, 'facebook')
    confere(False, 'rede que não está no post: recusada')
except pg.ErroRede:
    confere(True, 'rede que não está no post: recusada')

# 3. TikTok travado (envio demorando): o YouTube de outro post sai mesmo assim
TIKTOK['modo'] = 'trava'
p2 = post(2, ['tiktok', 'youtube'])
t0 = time.time()
pg.ciclo(esperar=False)
fim = time.time() + 10
while time.time() < fim and st(p2)['youtube'] != 'postado':
    time.sleep(0.1)
confere(st(p2)['youtube'] == 'postado' and st(p2)['tiktok'] == 'postando', f'TikTok travado: YouTube postado em {time.time() - t0:.1f}s sem esperar ({st(p2)})')
p3 = post(3, ['youtube'])
pg.ciclo(esperar=False)
fim = time.time() + 10
while time.time() < fim and st(p3)['youtube'] != 'postado':
    time.sleep(0.1)
confere(st(p3)['youtube'] == 'postado', 'post novo do YouTube sai enquanto o TikTok ainda está travado')
pg.ciclo(esperar=False)
confere(sum(1 for e in enviados if e == ('tiktok', p2)) == 0 and st(p2)['tiktok'] == 'postando', 'o mesmo envio do TikTok não é disparado duas vezes')
LIBERA.set()
fim = time.time() + 10
while time.time() < fim and st(p2)['tiktok'] != 'postado':
    time.sleep(0.1)
confere(st(p2)['tiktok'] == 'postado' and enviados.count(('tiktok', p2)) == 1, 'TikTok termina depois, uma vez só')

# 4. erro inesperado (bug) numa rede não derruba as outras
TIKTOK['modo'] = 'quebra'
p4 = post(4, ['tiktok', 'youtube'])
pg.ciclo()
s = st(p4)
confere(s == {'tiktok': 'erro', 'youtube': 'postado'}, f'erro inesperado só no TikTok: YouTube postado ({s})')

# Um post que já saiu pode receber destinos sem perder o link ou repetir o primeiro envio.
p5 = post(5, ['youtube'])
pg.ciclo()
original = next(p for p in pg.posts() if p['id'] == p5)
pg.publicar_em_outras_redes(p5, ['youtube', 'instagram', 'kwai'])
pg.publicar_em_outras_redes(p5, ['instagram', 'kwai'])
pg.ciclo()
atual = next(p for p in pg.posts() if p['id'] == p5)
confere(st(p5) == {'youtube': 'postado', 'instagram': 'postado', 'kwai': 'manual'},
        'Instagram é enviado e Kwai fica manual no mesmo post')
confere(atual['redes']['youtube'] == original['redes']['youtube'] and atual['quando'] == original['quando'],
        'o histórico e o horário original são preservados')
confere(enviados.count(('youtube', p5)) == enviados.count(('instagram', p5)) == 1,
        'repetir a solicitação não duplica envios')

print(f'\n{ok} ok, {falhas} falha(s)')
sys.exit(1 if falhas else 0)
