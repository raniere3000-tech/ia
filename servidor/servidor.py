"""Servidor do EstúdioClip: baixa um vídeo do YouTube pelo link para o site cortar sozinho.

Use apenas com vídeos seus ou com autorização do dono.
Só precisa de Python 3.9+, yt-dlp e FFmpeg (roda no Windows, Mac, Linux e Android/Termux).
Rodar:  python servidor.py   (abre em http://localhost:8787)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

VERSAO = '1.1.0'
PORTA = int(os.getenv('PORT', os.getenv('PORTA', '8787')))
HOST = os.getenv('HOST', '127.0.0.1')
TOKEN = os.getenv('TOKEN', '').strip()
MAX_MIN = float(os.getenv('MAX_MINUTOS', '180'))
ALTURA = int(os.getenv('ALTURA_MAX', '720'))
ORIGENS = [o.strip() for o in os.getenv('ORIGENS', 'https://raniere3000-tech.github.io,http://localhost:5173,http://localhost:4173').split(',') if o.strip()]
QUALQUER_URL = os.getenv('PERMITIR_QUALQUER_URL') == '1'  # só para testes
PASTA = Path(os.getenv('PASTA_TEMP', tempfile.gettempdir())) / 'estudioclip'
PASTA.mkdir(parents=True, exist_ok=True)
YT = re.compile(r'^https?://(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/', re.I)

JOBS: dict[str, dict] = {}
LOCK = threading.Lock()


class Erro(Exception):
    def __init__(self, status: int, msg: str):
        super().__init__(msg)
        self.status = status
        self.msg = msg


def limpar_antigos():
    agora = time.time()
    with LOCK:
        for jid, j in list(JOBS.items()):
            if agora - j['criado'] > 3600:
                shutil.rmtree(PASTA / jid, ignore_errors=True)
                JOBS.pop(jid, None)


def ffmpeg_path() -> str | None:
    if shutil.which('ffmpeg'):
        return None  # yt-dlp acha sozinho
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def js_runtimes() -> dict:
    try:
        import deno
        return {'deno': {'path': deno.find_deno_bin()}}
    except Exception:
        return {'deno': {}, 'node': {}}


def erro_amigavel(msg: str) -> str:
    m = msg.lower()
    if 'sign in to confirm' in m or 'not a bot' in m:
        return 'O YouTube bloqueou este servidor (pede login para confirmar que não é robô). Rode o servidor no seu próprio computador.'
    if 'private video' in m:
        return 'Este vídeo é privado.'
    if 'members-only' in m or 'join this channel' in m:
        return 'Este vídeo é só para membros do canal.'
    if 'does not pass filter' in m or 'duration' in m and 'filter' in m:
        return f'O vídeo passa de {int(MAX_MIN)} minutos, o limite do servidor.'
    if 'live event will begin' in m or 'is live' in m:
        return 'Live ainda em andamento. Espere terminar para cortar.'
    if 'video unavailable' in m:
        return 'Vídeo indisponível (removido, bloqueado no país ou link errado).'
    if 'proxy' in m or 'timed out' in m or 'connection' in m:
        return 'O servidor não conseguiu acessar o YouTube (sem internet, proxy ou firewall).'
    limpo = re.sub(r'^ERROR:\s*', '', msg.strip().splitlines()[-1]).split('; please report')[0]
    return 'Não deu para baixar: ' + limpo[-300:]


def baixar(jid: str, url: str):
    import yt_dlp
    j = JOBS[jid]
    pasta = PASTA / jid
    pasta.mkdir(parents=True, exist_ok=True)

    def progresso(d):
        if d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            feito = d.get('downloaded_bytes') or 0
            parte = j.get('parte', 0)
            pct = (feito / total * 100) if total else 0
            # vídeo e áudio vêm separados: 0–85% vídeo, 85–98% áudio
            j['pct'] = round(pct * 0.85 if parte == 0 else 85 + pct * 0.13, 1)
        elif d.get('status') == 'finished':
            j['parte'] = j.get('parte', 0) + 1

    opts = {
        'format': f'bv*[height<={ALTURA}][vcodec^=avc1]+ba[ext=m4a]/b[height<={ALTURA}][ext=mp4]/bv*[height<={ALTURA}]+ba/b[height<={ALTURA}]/b',
        'merge_output_format': 'mp4',
        'outtmpl': str(pasta / 'video.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [progresso],
        'match_filter': yt_dlp.utils.match_filter_func(f'!is_live & duration <=? {int(MAX_MIN * 60)}'),
        'js_runtimes': js_runtimes(),
    }
    ff = ffmpeg_path()
    if ff:
        opts['ffmpeg_location'] = ff
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        if info is None:
            raise RuntimeError('does not pass filter')
        arquivos = sorted(pasta.glob('video.*'), key=lambda p: p.stat().st_size, reverse=True)
        arquivos = [a for a in arquivos if a.suffix in ('.mp4', '.webm', '.mkv', '.mov')]
        if not arquivos:
            longo = (info.get('duration') or 0) > MAX_MIN * 60
            raise RuntimeError('does not pass filter' if longo else 'arquivo não encontrado depois do download')
        j.update(status='pronto', pct=100, arquivo=str(arquivos[0]), titulo=info.get('title') or 'video',
                 duracao=info.get('duration'), tamanho=arquivos[0].stat().st_size)
    except Exception as e:  # noqa: BLE001
        j.update(status='erro', erro=erro_amigavel(str(e)))
        shutil.rmtree(pasta, ignore_errors=True)



class Handler(BaseHTTPRequestHandler):
    server_version = 'EstudioClip/' + VERSAO
    protocol_version = 'HTTP/1.1'

    def log_message(self, *a):  # silencioso
        pass

    # ---- respostas ----
    def cors(self):
        origem = self.headers.get('Origin', '')
        if origem and (origem in ORIGENS or '*' in ORIGENS):
            self.send_header('Access-Control-Allow-Origin', origem)
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Token')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.send_header('Access-Control-Expose-Headers', 'Content-Length, X-Titulo')
            self.send_header('Vary', 'Origin')

    def json(self, status: int, dados: dict):
        corpo = json.dumps(dados, ensure_ascii=False).encode()
        self.send_response(status)
        self.cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def token_ok(self):
        tok = self.headers.get('X-Token') or parse_qs(urlparse(self.path).query).get('token', [''])[0]
        if TOKEN and tok != TOKEN:
            raise Erro(401, 'Senha do servidor errada. Confira em Chaves e ajustes.')

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        self.rodar(self.get)

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        self.corpo = self.rfile.read(n) if 0 < n <= 10000 else b''
        if n > 10000:
            self.close_connection = True
        self.rodar(self.post)

    def rodar(self, f):
        try:
            f(urlparse(self.path).path.rstrip('/') or '/')
        except Erro as e:
            self.json(e.status, {'detail': e.msg})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa: BLE001
            self.json(500, {'detail': f'Erro interno: {e}'})

    # ---- rotas ----
    def get(self, caminho: str):
        if caminho in ('/', '/saude'):
            try:
                import yt_dlp
                versao_yt = yt_dlp.version.__version__
            except Exception:
                versao_yt = None
            return self.json(200, {'ok': versao_yt is not None, 'versao': VERSAO, 'yt_dlp': versao_yt, 'senha': bool(TOKEN), 'max_minutos': MAX_MIN,
                                   'aviso': None if versao_yt else 'yt-dlp não instalado: rode  pip install -U yt-dlp'})
        m = re.fullmatch(r'/baixar/(\w+)(/arquivo)?', caminho)
        if not m:
            raise Erro(404, 'Rota não encontrada.')
        self.token_ok()
        jid, arquivo = m.group(1), m.group(2)
        j = JOBS.get(jid)
        if not arquivo:
            if not j:
                raise Erro(404, 'Download não encontrado (o servidor reiniciou?). Tente de novo.')
            return self.json(200, {k: j.get(k) for k in ('status', 'pct', 'erro', 'titulo', 'duracao', 'tamanho')})
        if not j or j.get('status') != 'pronto':
            raise Erro(404, 'Arquivo ainda não está pronto.')
        caminho_arq = Path(j['arquivo'])
        tamanho = caminho_arq.stat().st_size
        self.send_response(200)
        self.cors()
        self.send_header('Content-Type', 'video/mp4' if caminho_arq.suffix == '.mp4' else 'video/webm')
        self.send_header('Content-Length', str(tamanho))
        self.send_header('X-Titulo', re.sub(r'[^\x20-\x7e]', '', j.get('titulo') or '')[:200])
        self.end_headers()
        try:
            with open(caminho_arq, 'rb') as f:
                shutil.copyfileobj(f, self.wfile, 1024 * 1024)
        finally:
            shutil.rmtree(PASTA / jid, ignore_errors=True)
            JOBS.pop(jid, None)

    def post(self, caminho: str):
        if caminho != '/baixar':
            raise Erro(404, 'Rota não encontrada.')
        self.token_ok()
        try:
            url = str(json.loads(self.corpo or b'{}').get('url', '')).strip()
        except ValueError:
            raise Erro(400, 'Pedido inválido.')
        if not (YT.match(url) or (QUALQUER_URL and url.startswith('http'))):
            raise Erro(400, 'Envie um link do YouTube.')
        limpar_antigos()
        jid = uuid.uuid4().hex[:12]
        JOBS[jid] = {'status': 'baixando', 'pct': 0, 'criado': time.time(), 'url': url}
        threading.Thread(target=baixar, args=(jid, url), daemon=True).start()
        self.json(200, {'id': jid})


def main():
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        print('Falta o yt-dlp. Rode:  pip install -U yt-dlp')
        raise SystemExit(1)
    if not shutil.which('ffmpeg') and not ffmpeg_path():
        print('Aviso: FFmpeg não encontrado. Vídeos acima de 360p podem falhar. (Termux: pkg install ffmpeg)')
    srv = ThreadingHTTPServer((HOST, PORTA), Handler)
    print(f'\n  EstúdioClip servidor {VERSAO} rodando em http://localhost:{PORTA}')
    print('  Cole esse endereço no site, em Chaves e ajustes > Cortes direto pelo link.')
    if TOKEN:
        print('  Senha ligada: cole a mesma senha no site.')
    print('  Deixe esta janela aberta enquanto usa o site. Para parar: Ctrl+C\n')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
