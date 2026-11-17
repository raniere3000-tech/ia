"""Vídeo longo pelo link: com trechos marcados, o servidor baixa só o pedaço (o limite vale para o pedaço).

Rodar:  python servidor/testes/teste_trecho_link.py
Sem internet: o yt-dlp é simulado (aqui só se confere o pedido feito a ele).
"""
import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='trecho-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yt_dlp  # noqa: E402
import servidor as sv  # noqa: E402

falhas = 0


def confere(c, nome):
    global falhas
    print(('ok    ' if c else 'FALHA ') + nome)
    falhas += 0 if c else 1


pedidos = []


class FalsoYDL:
    def __init__(self, opts):
        self.opts = opts
        pedidos.append(opts)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=True):
        Path(self.opts['outtmpl'].replace('%(ext)s', 'mp4')).write_bytes(b'x' * 2000)
        return {'title': 'Zelda', 'duration': 5 * 3600 + 27 * 60}


yt_dlp.YoutubeDL = FalsoYDL
sv.PASTA = TMP
sv.ffmpeg_path = lambda: '/usr/bin/ffmpeg'

f = sv.faixa_pedida({'de': 7972, 'ate': 8879})
confere(f == (7972.0, 8879.0), 'faixa lida do pedido')
confere(sv.faixa_pedida({}) is None, 'sem faixa: baixa o vídeo inteiro como antes')
try:
    sv.faixa_pedida({'de': 0, 'ate': 4 * 3600})
    confere(False, 'pedaço maior que o limite é recusado')
except sv.Erro as e:
    confere('servidor baixa até 180 minutos' in str(e), 'pedaço maior que o limite é recusado com explicação')

sv.JOBS['a'] = {'status': 'baixando', 'pct': 0}
sv.baixar('a', 'https://www.youtube.com/watch?v=abc', f)
o = pedidos[-1]
j = sv.JOBS['a']
confere(j['status'] == 'pronto' and j['inicio'] == 7972.0, 'vídeo de 5 h com trecho marcado: baixa e diz onde o pedaço começa')
confere('download_ranges' in o and o.get('force_keyframes_at_cuts'), 'pede ao yt-dlp só o pedaço marcado')
confere(o['match_filter']({'duration': 19648, 'is_live': False}) is None, 'o limite de 180 min não barra o vídeo longo quando é só um pedaço')

sv.JOBS['b'] = {'status': 'baixando', 'pct': 0}
sv.baixar('b', 'https://www.youtube.com/watch?v=abc')
o = pedidos[-1]
confere('download_ranges' not in o and 'inicio' not in sv.JOBS['b'], 'sem trechos: baixa inteiro')
confere(o['match_filter']({'duration': 19648, 'is_live': False}) is not None, 'sem trechos: vídeo de 5 h continua barrado pelo limite')

sv.ffmpeg_path = lambda: None          # FFmpeg do Termux: está no PATH (yt-dlp acha sozinho)
sv.shutil.which = lambda n: '/data/data/com.termux/files/usr/bin/ffmpeg' if n == 'ffmpeg' else None
sv.JOBS['t'] = {'status': 'baixando', 'pct': 0}
sv.baixar('t', 'https://www.youtube.com/watch?v=abc', f)
confere(sv.JOBS['t']['status'] == 'pronto' and 'download_ranges' in pedidos[-1], 'FFmpeg instalado pelo pkg (no PATH) é reconhecido')
sv.shutil.which = lambda n: None
sv.JOBS['c'] = {'status': 'baixando', 'pct': 0}
sv.baixar('c', 'https://www.youtube.com/watch?v=abc', f)
confere(sv.JOBS['c']['status'] == 'erro' and 'FFmpeg' in sv.JOBS['c']['erro'], 'sem FFmpeg: explica o que instalar')

print('\n' + ('TUDO OK' if not falhas else f'{falhas} FALHA(S)'))
sys.exit(1 if falhas else 0)
