"""Servidor do EstúdioClip: baixa um vídeo do YouTube pelo link para o site cortar sozinho.

Use apenas com vídeos seus ou com autorização do dono.
Também agenda e publica os cortes nas SUAS contas (postagem.py).
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

import postagem as pg

VERSAO = '1.3.0'
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
TT = re.compile(r'^https?://([a-z]+\.)?tiktok\.com/', re.I)  # TikTok (vídeo público)

COOKIES = pg.DADOS / 'youtube-cookies.txt'  # cookies do YouTube enviados pelo site (opcional)
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
        if COOKIES.exists():
            return ('O YouTube ainda pede login (confirmar que não é robô), mesmo com os cookies. Os cookies podem ter vencido: '
                    'exporte de novo em Chaves e ajustes > "YouTube pede login". Ou baixe o vídeo e use Enviar arquivo.')
        return ('O YouTube pediu login para confirmar que não é robô (acontece muito com internet de celular). '
                'Resolva enviando os cookies do YouTube em Chaves e ajustes > "YouTube pede login", ou baixe o vídeo e use Enviar arquivo.')
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


def salvar_cookies(corpo: bytes | None) -> dict:
    """Guarda (ou apaga) o cookies.txt do YouTube. Mantém só as linhas do YouTube/Google."""
    if corpo is None:
        COOKIES.unlink(missing_ok=True)
        return {'ok': True, 'cookies': False}
    texto = corpo.decode('utf-8', 'replace').replace('\r\n', '\n')
    linhas = []
    for ln in texto.split('\n'):
        partes = ln.split('\t')
        dominio = partes[0].replace('#HttpOnly_', '') if partes else ''
        if len(partes) >= 7 and (dominio.endswith('youtube.com') or dominio.endswith('google.com')):
            linhas.append(ln)
    if not any('youtube.com' in ln for ln in linhas):
        raise Erro(400, 'Esse arquivo não tem cookies do YouTube. Exporte com a extensão "Get cookies.txt LOCALLY" estando na página do youtube.com e logado.')
    COOKIES.parent.mkdir(parents=True, exist_ok=True)
    COOKIES.write_text('# Netscape HTTP Cookie File\n' + '\n'.join(linhas) + '\n', encoding='utf-8')
    try:
        os.chmod(COOKIES, 0o600)
    except OSError:
        pass
    return {'ok': True, 'cookies': True, 'linhas': len(linhas)}


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
    if COOKIES.exists():
        opts['cookiefile'] = str(COOKIES)
    try:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as e:  # noqa: BLE001
            m = str(e).lower()
            if 'sign in to confirm' not in m and 'not a bot' not in m:
                raise
            # Tenta de novo fingindo ser outros aplicativos do YouTube (TV, Safari, celular).
            j['pct'] = 0
            j['parte'] = 0
            opts2 = dict(opts, extractor_args={'youtube': {'player_client': ['tv', 'web_safari', 'mweb']}})
            with yt_dlp.YoutubeDL(opts2) as ydl:
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
        rota = urlparse(self.path).path.rstrip('/')
        limite = 40 * 1024 * 1024 if rota == '/video' else 5 * 1024 * 1024 if rota == '/cookies' else 100000
        self.corpo = self.rfile.read(n) if 0 < n <= limite else b''
        if n > limite:
            self.close_connection = True
        self.rodar(self.post)

    def rodar(self, f):
        try:
            f(urlparse(self.path).path.rstrip('/') or '/')
        except Erro as e:
            self.json(e.status, {'detail': e.msg})
        except pg.ErroRede as e:
            self.json(400, {'detail': str(e)})
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
            return self.json(200, {'ok': True, 'download': versao_yt is not None, 'agendador': True, 'versao': VERSAO, 'yt_dlp': versao_yt, 'senha': bool(TOKEN), 'max_minutos': MAX_MIN, 'cookies': COOKIES.exists(),
                                   'aviso': None if versao_yt else 'yt-dlp não instalado: rode  pip install -U yt-dlp'})
        if caminho == '/contas':
            self.token_ok()
            return self.json(200, pg.status_contas())
        if caminho == '/posts':
            self.token_ok()
            return self.json(200, {'posts': pg.lista_posts(), 'agora': time.time()})
        mv = re.fullmatch(r'/posts/(\w+)/video', caminho)
        if mv:
            self.token_ok()
            alvo = [x for x in pg.posts() if x['id'] == mv.group(1)]
            if not alvo:
                raise Erro(404, 'Post não encontrado.')
            return self.enviar_arquivo(pg.video_path(alvo[0]['video']), (alvo[0]['titulo'] or 'corte'))
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

    def enviar_arquivo(self, caminho_arq: Path, nome: str):
        tamanho = caminho_arq.stat().st_size
        nome = re.sub(r'[^\w\- ]+', '', nome)[:60].strip() or 'corte'
        self.send_response(200)
        self.cors()
        self.send_header('Content-Type', 'video/mp4' if caminho_arq.suffix == '.mp4' else 'video/webm')
        self.send_header('Content-Length', str(tamanho))
        self.send_header('Content-Disposition', f'attachment; filename="{nome}{caminho_arq.suffix}"')
        self.end_headers()
        with open(caminho_arq, 'rb') as f:
            shutil.copyfileobj(f, self.wfile, 1024 * 1024)

    def corpo_json(self) -> dict:
        try:
            d = json.loads(self.corpo or b'{}')
            return d if isinstance(d, dict) else {}
        except ValueError:
            raise Erro(400, 'Pedido inválido.')

    def post(self, caminho: str):
        if caminho in ('/cookies', '/cookies/apagar'):
            self.token_ok()
            return self.json(200, salvar_cookies(self.corpo if caminho == '/cookies' else None))
        if caminho != '/baixar':
            self.token_ok()
            try:
                return self.json(200, self.post_agenda(caminho) or {'ok': True})
            except pg.ErroRede as e:
                raise Erro(400, str(e))
        self.token_ok()
        try:
            url = str(json.loads(self.corpo or b'{}').get('url', '')).strip()
        except ValueError:
            raise Erro(400, 'Pedido inválido.')
        if not (YT.match(url) or TT.match(url) or (QUALQUER_URL and url.startswith('http'))):
            raise Erro(400, 'Envie um link do YouTube ou do TikTok.')
        limpar_antigos()
        jid = uuid.uuid4().hex[:12]
        JOBS[jid] = {'status': 'baixando', 'pct': 0, 'criado': time.time(), 'url': url}
        threading.Thread(target=baixar, args=(jid, url), daemon=True).start()
        self.json(200, {'id': jid})


def _rotas_agenda(self, caminho: str):
    d = self.corpo_json() if caminho != '/video' else {}
    q = parse_qs(urlparse(self.path).query)
    if caminho == '/contas/codigo':
        return {'rede': pg.receber_codigo(str(d.get('code', '')), str(d.get('state', '')))}
    if caminho == '/contas/meta/pagina':
        return pg.escolher_pagina(str(d.get('pagina', '')))
    m = re.fullmatch(r'/contas/(google|meta|tiktok)/(app|login|sair)', caminho)
    if m:
        prov, acao = m.groups()
        if acao == 'app':
            return pg.salvar_app(prov, str(d.get('client_id', '')), str(d.get('client_secret', '')))
        if acao == 'login':
            return {'url': pg.url_login(prov, str(d.get('volta', '')))}
        return pg.sair(prov)
    if caminho == '/video':
        vid = q.get('video', [None])[0]
        return pg.receber_pedaco(vid, int(q.get('offset', ['0'])[0]), self.corpo, q.get('nome', ['video.mp4'])[0])
    m = re.fullmatch(r'/video/(\w+)/fim', caminho)
    if m:
        return pg.finalizar_video(m.group(1))
    if caminho == '/posts':
        return pg.criar_post(d)
    m = re.fullmatch(r'/posts/(\w+)/(agora|cancelar|feito)', caminho)
    if m:
        pid, acao = m.groups()
        if acao == 'agora':
            return pg.postar_agora(pid)
        if acao == 'cancelar':
            return pg.cancelar_post(pid)
        return pg.marcar_feito(pid, str(d.get('rede', '')))
    raise Erro(404, 'Rota não encontrada.')


Handler.post_agenda = _rotas_agenda


def main():
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        print('Falta o yt-dlp. Rode:  pip install -U yt-dlp')
        raise SystemExit(1)
    if not shutil.which('ffmpeg') and not ffmpeg_path():
        print('Aviso: FFmpeg não encontrado. Vídeos acima de 360p podem falhar. (Termux: pkg install ffmpeg)')
    pg.iniciar_relogio()
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
