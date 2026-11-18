"""Servidor do EstúdioClip: baixa um vídeo do YouTube pelo link para o site cortar sozinho.

Use apenas com vídeos seus ou com autorização do dono.
Também agenda e publica os cortes nas SUAS contas (postagem.py).
Só precisa de Python 3.9+, yt-dlp e FFmpeg (roda no Windows, Mac, Linux e Android/Termux).
Rodar:  python servidor.py   (abre em http://localhost:8787)
"""
from __future__ import annotations

import hmac
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

import cofre
import postagem as pg
import agente as ag
import modelos as mo
import visual_presets as vp
import gameplay_indexer as gpi
import modo_render as mr
import perfis as pf
import aprendizado as apz
import publish_package as pub
import banco as db
import autenticacao as au
import projetos as pj
import fila
import aprovacoes as apv
import renderizador as rd
import produtor
import api_v1

VERSAO = '2.0.0'
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

COOKIES = pg.DADOS / 'youtube-cookies.cofre'  # cookies do YouTube enviados pelo site (opcional), guardados criptografados
_COOKIES_ANTIGO = pg.DADOS / 'youtube-cookies.txt'
try:
    os.chmod(pg.DADOS, 0o700)
except OSError:
    pass
if _COOKIES_ANTIGO.exists():      # versão antiga guardava em texto puro: cifra e apaga o original
    try:
        COOKIES.write_bytes(cofre.cifrar(_COOKIES_ANTIGO.read_bytes()))
        os.chmod(COOKIES, 0o600)
        _COOKIES_ANTIGO.unlink()
    except (OSError, cofre.ErroCofre) as _e:
        print('cookies:', _e)


def cookies_para(pasta: Path) -> str | None:
    """O yt-dlp só lê cookies de arquivo: abre o cofre num arquivo temporário dentro da pasta do download."""
    if not COOKIES.exists():
        return None
    try:
        claro = cofre.decifrar(COOKIES.read_bytes().strip())
    except (OSError, cofre.ErroCofre) as e:
        print('cookies:', e)
        return None
    arq = pasta / 'cookies.tmp'
    fd = os.open(arq, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(claro)
    return str(arq)
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()
FALHAS: dict[str, list] = {}     # quem errou a senha -> horários dos erros (trava tentativa em massa)
MAX_FALHAS, JANELA_FALHAS = int(os.getenv('MAX_FALHAS', '8')), 600


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
    msg = re.sub(r'\x1b\[[0-9;]*m', '', msg)        # tira as cores do terminal
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
    if 'requested format' in m or 'format is not available' in m:
        return ('O YouTube não liberou nenhum formato de vídeo para o servidor (pode ser a versão do yt-dlp). '
                'No Termux rode: pip install -U yt-dlp e tente de novo.')
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
    COOKIES.write_bytes(cofre.cifrar(('# Netscape HTTP Cookie File\n' + '\n'.join(linhas) + '\n').encode('utf-8')))
    try:
        os.chmod(COOKIES, 0o600)
    except OSError:
        pass
    return {'ok': True, 'cookies': True, 'linhas': len(linhas)}


def faixa_pedida(d: dict) -> tuple[float, float] | None:
    """Trecho do vídeo a baixar (em segundos), quando o site já marcou os cortes: assim um vídeo longo não precisa vir inteiro."""
    try:
        de, ate = float(d.get('de')), float(d.get('ate'))
    except (TypeError, ValueError):
        return None
    de = max(0.0, de)
    if ate - de < 1:
        raise Erro(400, 'Trecho inválido para baixar.')
    if ate - de > MAX_MIN * 60:
        raise Erro(400, f'Os trechos marcados ocupam {int((ate - de) // 60)} minutos do vídeo; o servidor baixa até {int(MAX_MIN)} minutos de uma vez. '
                        'Marque trechos mais próximos uns dos outros ou baixe em duas vezes.')
    return de, ate


def baixar(jid: str, url: str, faixa: tuple[float, float] | None = None):
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
    if faixa:
        # só o pedaço com os trechos marcados: o limite de duração vale para o pedaço, não para o vídeo inteiro
        opts['download_ranges'] = yt_dlp.utils.download_range_func(None, [faixa])
        opts['force_keyframes_at_cuts'] = True
        opts['match_filter'] = yt_dlp.utils.match_filter_func('!is_live')
        j['inicio'] = faixa[0]
    tem_ffmpeg = bool(ff or shutil.which('ffmpeg'))   # ffmpeg_path() devolve None quando o FFmpeg já está no PATH (o do Termux)
    if ff:
        opts['ffmpeg_location'] = ff
    if not tem_ffmpeg and faixa:
        j.update(status='erro', erro='Para baixar só um trecho de vídeo longo o servidor precisa do FFmpeg. No Termux rode: pkg install -y ffmpeg')
        return
    if not tem_ffmpeg:
        # Sem FFmpeg não dá para juntar vídeo e áudio separados: o vídeo viria MUDO.
        # Então pede só arquivos que já trazem vídeo e som juntos.
        opts['format'] = f'b[height<={ALTURA}][ext=mp4][acodec!=none]/b[acodec!=none][vcodec!=none]/b'
    ck = cookies_para(pasta)
    if ck:
        opts['cookiefile'] = ck
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
        arquivos = [a for a in arquivos if a.suffix in ('.mp4', '.webm', '.mkv', '.mov') and not re.search(r'\.f\d+$', a.stem)] or \
                   [a for a in arquivos if a.suffix in ('.mp4', '.webm', '.mkv', '.mov')]
        if not arquivos:
            longo = not faixa and (info.get('duration') or 0) > MAX_MIN * 60
            raise RuntimeError('does not pass filter' if longo else 'arquivo não encontrado depois do download')
        (pasta / 'cookies.tmp').unlink(missing_ok=True)
        j.update(status='pronto', pct=100, arquivo=str(arquivos[0]), titulo=info.get('title') or 'video',
                 duracao=info.get('duration'), tamanho=arquivos[0].stat().st_size)
    except Exception as e:  # noqa: BLE001
        j.update(status='erro', erro=erro_amigavel(str(e)))
        shutil.rmtree(pasta, ignore_errors=True)



def baixar_para_agente(url: str, pasta: Path, idioma: str, progresso):
    """Download usado pelo agente: devolve (arquivo, informações, legenda automática json3 ou None)."""
    import yt_dlp
    if not (YT.match(url) or (QUALQUER_URL and url.startswith('http'))):
        raise ag.ErroAgente('O agente só baixa links do YouTube.')
    estado = {'parte': 0}

    def gancho(d):
        if d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            pct = (d.get('downloaded_bytes') or 0) / total * 100 if total else 0
            progresso(pct * 0.85 if estado['parte'] == 0 else 85 + pct * 0.13)
        elif d.get('status') == 'finished':
            estado['parte'] += 1

    opts = {
        'format': f'bv*[height<={ALTURA}][vcodec^=avc1]+ba[ext=m4a]/b[height<={ALTURA}][ext=mp4]/bv*[height<={ALTURA}]+ba/b[height<={ALTURA}]/b',
        'merge_output_format': 'mp4', 'outtmpl': str(pasta / 'video.%(ext)s'), 'noplaylist': True, 'quiet': True, 'no_warnings': True,
        'progress_hooks': [gancho], 'js_runtimes': js_runtimes(),
        'match_filter': yt_dlp.utils.match_filter_func(f'!is_live & duration <=? {int(MAX_MIN * 60)}'),
        'writeautomaticsub': True, 'writesubtitles': True, 'subtitlesformat': 'json3',
        'subtitleslangs': [idioma, idioma + '-orig', idioma + '-BR'], 'ignoreerrors': False,
    }
    ff = ffmpeg_path()
    if ff:
        opts['ffmpeg_location'] = ff
    ck = cookies_para(pasta)
    if ck:
        opts['cookiefile'] = ck
    try:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as e:  # noqa: BLE001
            m = str(e).lower()
            if 'subtitle' in m or 'caption' in m or '429' in m:
                # a legenda falhou: baixa só o vídeo e deixa a IA ouvir a fala
                opts.update(writeautomaticsub=False, writesubtitles=False)
            elif 'sign in to confirm' in m or 'not a bot' in m:
                opts['extractor_args'] = {'youtube': {'player_client': ['tv', 'web_safari', 'mweb']}}
            else:
                raise
            estado['parte'] = 0
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
    except Exception as e:  # noqa: BLE001
        raise ag.ErroAgente(erro_amigavel(str(e)))
    finally:
        (pasta / 'cookies.tmp').unlink(missing_ok=True)
    if info is None:
        raise ag.ErroAgente(f'O vídeo passa de {int(MAX_MIN)} minutos ou é uma live.')
    achar = lambda: sorted((a for a in pasta.glob('video.*') if a.suffix in ('.mp4', '.webm', '.mkv', '.mov')  # noqa: E731
                            and not re.search(r'\.f\d+$', a.stem)), key=lambda p: p.stat().st_size, reverse=True)
    videos = achar()
    if not videos and info.get('is_live'):
        raise ag.ErroAgente('Este vídeo é uma live que ainda está no ar. O agente tenta de novo depois que ela terminar.')
    if not videos and (info.get('duration') or 0) > MAX_MIN * 60:
        # O yt-dlp pula (sem erro) o vídeo que passa do limite: baixa só os primeiros MAX_MIN minutos e corta deles.
        if not (ffmpeg_path() or shutil.which('ffmpeg')):
            raise ag.ErroAgente(f'O vídeo tem {int(info["duration"] // 60)} minutos (limite {int(MAX_MIN)}). Para baixar só um pedaço, instale o FFmpeg: pkg install -y ffmpeg')
        progresso(0)
        estado['parte'] = 0
        opts.update(download_ranges=yt_dlp.utils.download_range_func(None, [(0, MAX_MIN * 60)]), force_keyframes_at_cuts=False,
                    match_filter=yt_dlp.utils.match_filter_func('!is_live'))
        try:
            ck = cookies_para(pasta)
            if ck:
                opts['cookiefile'] = ck
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True) or info
        except Exception as e:  # noqa: BLE001
            raise ag.ErroAgente(erro_amigavel(str(e)))
        finally:
            (pasta / 'cookies.tmp').unlink(missing_ok=True)
        info = dict(info, duration=MAX_MIN * 60, trecho_inicial=True)
        videos = achar()
    if not videos:
        sobras = ', '.join(a.name for a in pasta.glob('video.*'))[:200]
        raise ag.ErroAgente('O arquivo não apareceu depois do download.' + (f' Ficou só: {sobras}.' if sobras else ''))
    legendas = sorted(pasta.glob('video.*.json3'), key=lambda p: ('orig' not in p.name, len(p.name)))
    return videos[0], info, (legendas[0] if legendas else None)


ag.BAIXAR = baixar_para_agente


def url_da_live(link: str) -> dict:
    """Parte Live: abre a live (sem baixar) e devolve os endereços do vídeo ao vivo para o FFmpeg gravar.
    O YouTube muda os formatos de live com frequência: tenta vídeo+áudio juntos, depois separados, e depois outros
    "aplicativos" do YouTube (TV, Safari, celular), com e sem os seus cookies."""
    import yt_dlp
    if not (YT.match(link) or (QUALQUER_URL and link.startswith('http'))):
        raise ag.ErroAgente('A parte Live grava só links do YouTube.')
    alt = int(os.getenv('ALTURA_LIVE', '1080'))       # corte vertical recorta a imagem: precisa da melhor resolução da live
    fmt = (f'b[height<={alt}][acodec!=none][vcodec!=none]/bv*[height<={alt}]+ba/'
           'b[acodec!=none][vcodec!=none]/bv*+ba/b/bv*')
    base = {'format': fmt, 'format_sort': ['res', 'fps', 'br'], 'noplaylist': True, 'quiet': True, 'no_warnings': True, 'no_color': True,
            'js_runtimes': js_runtimes()}

    def altura(i):
        return max([i.get('height') or 0] + [f.get('height') or 0 for f in i.get('requested_formats') or []])
    tentativas = [{}, {'extractor_args': {'youtube': {'player_client': ['tv', 'web_safari', 'mweb']}}},
                  {'extractor_args': {'youtube': {'player_client': ['ios', 'android', 'tv_simply']}}}, {'sem_cookies': True}]
    ultimo = ''
    info = melhor = None
    for extra in tentativas:
        pasta = PASTA / ('live-' + uuid.uuid4().hex[:6])
        pasta.mkdir(parents=True, exist_ok=True)
        opts = dict(base, **{k: v for k, v in extra.items() if k != 'sem_cookies'})
        ck = None if extra.get('sem_cookies') else cookies_para(pasta)
        if ck:
            opts['cookiefile'] = ck
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
            if info and (info.get('url') or info.get('requested_formats')):
                if not melhor or altura(info) > altura(melhor):
                    melhor = info
                if altura(melhor) >= min(alt, 720):
                    break          # boa qualidade: não precisa tentar outro modo
                ultimo = f'O YouTube só mandou a live em {altura(info)}p neste modo.'
            else:
                ultimo = 'O YouTube não mandou nenhum formato de vídeo desta live.'
            info = None
        except Exception as e:  # noqa: BLE001
            ultimo = str(e)
            m = ultimo.lower()
            if not any(x in m for x in ('requested format', 'format is not available', 'sign in to confirm', 'not a bot', 'no video formats', 'http error 403')):
                break          # erro que outro modo não resolve (vídeo privado, sem internet...)
        finally:
            shutil.rmtree(pasta, ignore_errors=True)
    info = melhor
    if not info:
        raise ag.ErroAgente(erro_amigavel(ultimo))
    if info.get('requested_formats'):            # vídeo e áudio separados: o FFmpeg junta os dois na gravação
        urls = [f['url'] for f in info['requested_formats'] if f.get('url')]
    else:
        urls = [info['url']] if info.get('url') else []
    return {'url': urls[0] if urls else '', 'urls': urls, 'titulo': info.get('title') or 'Live', 'id': info.get('id') or '',
            'canal': info.get('channel_id') or '', 'canal_nome': info.get('channel') or info.get('uploader') or '',
            'ao_vivo': bool(info.get('is_live')) and bool(urls), 'altura': altura(info)}


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
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Token, X-Sessao, If-Match, Idempotency-Key, Range')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.send_header('Access-Control-Expose-Headers', 'Content-Length, Content-Range, Accept-Ranges, X-Titulo, ETag')
            self.send_header('Access-Control-Max-Age', '600')
            self.send_header('Vary', 'Origin')

    def json(self, status: int, dados: dict, etag=None):
        corpo = json.dumps(dados, ensure_ascii=False).encode()
        self.send_response(status)
        self.cors()
        if etag is not None:
            self.send_header('ETag', f'"{etag}"')
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Length', str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def quem(self) -> str:
        # Pelo túnel todo pedido chega de 127.0.0.1; o Cloudflare informa o endereço real de quem pediu.
        return self.headers.get('CF-Connecting-IP') or self.client_address[0]

    def token_ok(self):
        """Aceita a sessão do aparelho (X-Sessao) ou a senha do servidor (X-Token). Devolve a sessão, se houver."""
        ses = self.headers.get('X-Sessao') or ''
        if ses:
            s = au.validar(ses)
            if s:
                return s
            if not self.headers.get('X-Token'):
                raise Erro(401, 'Este aparelho foi desconectado ou a sessão venceu. Entre de novo em Ajustes > Aparelhos.')
        if not TOKEN:
            return None
        quem = self.quem()
        agora = time.time()
        with LOCK:
            erros = [t for t in FALHAS.get(quem, []) if agora - t < JANELA_FALHAS]
            FALHAS[quem] = erros
            if len(FALHAS) > 5000:
                FALHAS.clear()
        if len(erros) >= MAX_FALHAS:
            raise Erro(429, 'Muitas tentativas com a senha errada. Espere 10 minutos.')
        tok = self.headers.get('X-Token') or ''
        if not hmac.compare_digest(tok.encode(), TOKEN.encode()):
            with LOCK:
                FALHAS.setdefault(quem, []).append(agora)
            time.sleep(0.4)
            raise Erro(401, 'Senha do servidor errada. Confira em Chaves e ajustes.')
        return None

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        self.corpo = b''
        self.rodar(self.get)

    def _ler_corpo(self, metodo: str):
        n = int(self.headers.get('Content-Length') or 0)
        rota = urlparse(self.path).path.rstrip('/')
        if rota.startswith('/api/v1/'):
            limite = api_v1.limite_corpo(metodo, rota)
        else:
            limite = 40 * 1024 * 1024 if rota == '/video' else 5 * 1024 * 1024 if rota == '/cookies' else 12 * 1024 * 1024 if rota == '/modelos' else 1_300_000 if rota == '/agente/aprendizado/importar' else 100000
        self.corpo = self.rfile.read(n) if 0 < n <= limite else b''
        if n > limite:
            self.close_connection = True
            raise Erro(413, 'Pedido grande demais.')

    def do_POST(self):
        self.rodar(lambda c: (self._ler_corpo('POST'), self.post(c)))

    def do_PUT(self):
        self.rodar(lambda c: (self._ler_corpo('PUT'), self.api('PUT', c)))

    def do_PATCH(self):
        self.rodar(lambda c: (self._ler_corpo('PATCH'), self.api('PATCH', c)))

    def do_DELETE(self):
        self.rodar(lambda c: (self._ler_corpo('DELETE'), self.api('DELETE', c)))

    def api(self, metodo: str, caminho: str):
        if not caminho.startswith('/api/v1/'):
            raise Erro(404, 'Rota não encontrada.')
        sessao = None
        q = parse_qs(urlparse(self.path).query)
        if metodo == 'GET' and caminho.startswith('/api/v1/assets/') and q.get('sig'):
            if not api_v1._arquivo_assinado(caminho, q):
                raise Erro(403, 'Link vencido. Abra de novo pelo site.')
        elif (metodo, caminho) not in api_v1.ABERTAS:
            sessao = self.token_ok()
        try:
            r = api_v1.tratar(self, metodo, caminho, sessao)
        except api_v1.Resposta as arq:
            return self.enviar_parcial(arq.arquivo, arq.mime, arq.nome, arq.baixar)
        etag = r.get('revisao') if isinstance(r, dict) and 'revisao' in r and 'id' in r else None
        return self.json(200, r, etag)

    def enviar_parcial(self, arq: Path, mime: str, nome: str = '', baixar: bool = False):
        """Arquivo com suporte a Range (o <video> do navegador pede pedaços para poder pular no tempo)."""
        tamanho = arq.stat().st_size
        ini, fim = 0, tamanho - 1
        m = re.fullmatch(r'bytes=(\d*)-(\d*)', (self.headers.get('Range') or '').strip())
        parcial = bool(m and (m.group(1) or m.group(2)))
        if parcial:
            if m.group(1):
                ini = int(m.group(1))
                fim = min(int(m.group(2)), tamanho - 1) if m.group(2) else tamanho - 1
            else:
                ini = max(0, tamanho - int(m.group(2)))
            if ini > fim or ini >= tamanho:
                self.send_response(416)
                self.cors()
                self.send_header('Content-Range', f'bytes */{tamanho}')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
        self.send_response(206 if parcial else 200)
        self.cors()
        self.send_header('Content-Type', mime)
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(fim - ini + 1))
        if parcial:
            self.send_header('Content-Range', f'bytes {ini}-{fim}/{tamanho}')
        if baixar:
            limpo = re.sub(r'[^\w\-. ]+', '', nome)[:80].strip() or 'arquivo'
            self.send_header('Content-Disposition', f'attachment; filename="{limpo}"')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'private, max-age=3600')
        self.end_headers()
        with open(arq, 'rb') as f:
            f.seek(ini)
            falta = fim - ini + 1
            while falta > 0:
                bloco = f.read(min(1024 * 1024, falta))
                if not bloco:
                    break
                self.wfile.write(bloco)
                falta -= len(bloco)

    def rodar(self, f):
        try:
            f(urlparse(self.path).path.rstrip('/') or '/')
        except Erro as e:
            self.json(e.status, {'detail': e.msg})
        except au.ErroAuth as e:
            self.json(e.status, {'detail': e.msg})
        except pj.ErroProjeto as e:
            self.json(e.status, {'detail': str(e), **(getattr(e, 'extra', None) or {})})
        except apv.ErroAprovacao as e:
            self.json(e.status, {'detail': str(e)})
        except apz.ErroAprendizado as e:
            self.json(e.codigo, {'detail': str(e)})
        except (pg.ErroRede, ag.ErroAgente, mo.ErroModelo, vp.ErroEstilo, gpi.ErroGameplay, pf.ErroPerfil, pub.ErroPacote, produtor.ErroProdutor, rd.ErroRender, ValueError, FileNotFoundError) as e:
            self.json(400, {'detail': str(e)})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa: BLE001
            print('erro interno:', repr(e))   # o detalhe fica só no terminal do servidor
            self.json(500, {'detail': 'Erro interno no servidor. Veja o terminal do servidor para o detalhe.'})

    # ---- rotas ----
    def get(self, caminho: str):
        if caminho.startswith('/api/v1/'):
            return self.api('GET', caminho)
        if caminho in ('/', '/saude'):
            try:
                import yt_dlp
                versao_yt = yt_dlp.version.__version__
            except Exception:
                versao_yt = None
            return self.json(200, {'ok': True, 'download': versao_yt is not None, 'agendador': True, 'agente': True, 'versao': VERSAO, 'yt_dlp': versao_yt, 'senha': bool(TOKEN), 'max_minutos': MAX_MIN, 'cookies': COOKIES.exists(),
                                   'api': 1, 'projetos': True, 'fila': True, 'agente3': rd.tem_ffmpeg(),
                                   'aviso': None if versao_yt else 'yt-dlp não instalado: rode  pip install -U yt-dlp'})
        if caminho == '/contas':
            self.token_ok()
            return self.json(200, pg.status_contas())
        if caminho == '/posts':
            self.token_ok()
            return self.json(200, {'posts': pg.lista_posts(), 'agora': time.time()})
        if caminho == '/agente':
            self.token_ok()
            return self.json(200, ag.ver())
        mk = re.fullmatch(r'/agente/cortes/(\w+)/pacote(?:/capa/(\d))?', caminho)
        if mk:
            self.token_ok()
            if mk.group(2) is not None:
                return self.enviar_arquivo(pub.capa_arquivo(mk.group(1), int(mk.group(2))), 'capa')
            return self.json(200, pub.obter(mk.group(1)))
        if caminho == '/perfis':
            self.token_ok()
            return self.json(200, {'perfis': pf.listar()})
        mp = re.fullmatch(r'/perfis/(\w+)(?:/(resolvido|validar))?', caminho)
        if mp:
            self.token_ok()
            if mp.group(2) == 'validar':
                return self.json(200, {'problemas': pf.validar(mp.group(1), [m['id'] for m in mo.biblioteca()['modelos']], produtor.VOZES)})
            if mp.group(2) == 'resolvido':
                cfg = ag.config()
                return self.json(200, pf.resolver(mp.group(1), pf.padrao_do_site(cfg['cortes'], cfg['postagem'])))
            p = pf.obter(mp.group(1))
            return self.json(200, p)
        if caminho == '/agente/modos':
            self.token_ok()
            return self.json(200, {'modos': mr.resumo()})
        if caminho == '/agente/aprendizado':
            self.token_ok()
            return self.json(200, apz.painel())
        if caminho == '/agente/gameplay':
            self.token_ok()
            return self.json(200, {'analises': gpi.listar(), 'historias': gpi.HISTORIAS})
        mg = re.fullmatch(r'/agente/gameplay/(\w+)', caminho)
        if mg:
            self.token_ok()
            return self.json(200, gpi.relatorio(mg.group(1)))
        if caminho == '/estilos-visuais':
            self.token_ok()
            return self.json(200, {'versao': vp.VERSAO, 'estilos': vp.listar(), 'componentes': vp.COMPONENTES})
        me = re.fullmatch(r'/estilos-visuais/(\w+)/demo', caminho)
        if me:
            self.token_ok()
            return self.enviar_arquivo(vp.demo_pronta(me.group(1)), 'demo-' + me.group(1))
        if caminho == '/modelos':
            self.token_ok()
            return self.json(200, mo.biblioteca(ag.config()['cortes']['template']))
        ma = re.fullmatch(r'/agente/cortes/(\w+)/video', caminho)
        if ma:
            chave = parse_qs(urlparse(self.path).query).get('chave', [''])[0]
            if not chave:
                self.token_ok()
            return self.enviar_arquivo(*ag.video_do_corte(ma.group(1), chave))
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
            return self.json(200, {k: j.get(k) for k in ('status', 'pct', 'erro', 'titulo', 'duracao', 'tamanho', 'inicio')})
        if not j or j.get('status') != 'pronto':
            raise Erro(404, 'Arquivo ainda não está pronto.')
        caminho_arq = Path(j['arquivo'])
        tamanho = caminho_arq.stat().st_size
        self.send_response(200)
        self.cors()
        self.send_header('Content-Type', 'image/jpeg' if caminho_arq.suffix == '.jpg' else 'video/mp4' if caminho_arq.suffix == '.mp4' else 'video/webm')
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
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
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
        if caminho.startswith('/api/v1/'):
            return self.api('POST', caminho)
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
            pedido = json.loads(self.corpo or b'{}')
            url = str(pedido.get('url', '')).strip()
        except (ValueError, AttributeError):
            raise Erro(400, 'Pedido inválido.')
        faixa = faixa_pedida(pedido)
        if not (YT.match(url) or TT.match(url) or (QUALQUER_URL and url.startswith('http'))):
            raise Erro(400, 'Envie um link do YouTube ou do TikTok.')
        limpar_antigos()
        jid = uuid.uuid4().hex[:12]
        JOBS[jid] = {'status': 'baixando', 'pct': 0, 'criado': time.time(), 'url': url}
        threading.Thread(target=baixar, args=(jid, url, faixa), daemon=True).start()
        self.json(200, {'id': jid})


def _rotas_agenda(self, caminho: str):
    d = self.corpo_json() if caminho != '/video' else {}
    q = parse_qs(urlparse(self.path).query)
    if caminho == '/agente/config':
        ag.salvar_config(d)
        pg.acordar()
        return ag.ver()
    if caminho == '/agente/chaves':
        ag.salvar_segredos(d)
        return ag.ver()
    if caminho == '/agente/canais':
        return ag.acao_canal(d)
    if caminho == '/modelos':
        return mo.salvar(d)
    mk = re.fullmatch(r'/agente/cortes/(\w+)/pacote/(montar|editar|aprovar)', caminho)
    if mk:
        c = next((x for x in ag.estado()['cortes'] if x['id'] == mk.group(1)), None)
        if not c:
            raise ag.ErroAgente('Corte não encontrado.')
        if mk.group(2) == 'montar':
            return pub.montar(c, ag.config()['postagem']['redes'], d.get('redes'))
        if mk.group(2) == 'editar':
            return pub.editar(mk.group(1), d)
        return pub.aprovar(mk.group(1), 'site')
    if caminho == '/perfis':
        return pf.salvar(d, str(d.get('id', '')))
    mp = re.fullmatch(r'/perfis/(\w+)/(duplicar|restaurar|apagar)', caminho)
    if mp:
        if mp.group(2) == 'duplicar':
            return pf.duplicar(mp.group(1))
        if mp.group(2) == 'restaurar':
            return pf.restaurar(mp.group(1), d.get('versao', 0))
        pf.apagar(mp.group(1))
        return {'ok': True}
    if caminho == '/agente/aprendizado/importar':
        return apz.importar(str(d.get('nome', '')), str(d.get('formato', '')), d.get('conteudo'))
    if caminho == '/agente/aprendizado/capturar':
        ag.aprender(ajustar=False)
        return {**apz.capturar(), 'painel': apz.painel()}
    if caminho == '/agente/aprendizado/apagar':
        return apz.apagar(d)
    if caminho == '/agente/aprendizado/aplicar':
        return apz.aplicar(str(d.get('variavel', '')))
    if caminho == '/agente/aprendizado/desfazer':
        return apz.desfazer(str(d.get('variavel', '')))
    if caminho == '/agente/aprendizado/experimento':
        return apz.criar_experimento(d)
    if caminho == '/agente/aprendizado/experimento/encerrar':
        return apz.encerrar_experimento(str(d.get('id', '')))
    if caminho == '/agente/gameplay/analisar':
        return gpi.pedir_analise(d)
    if caminho == '/agente/gameplay/comparar':
        return gpi.pedir_comparacao(d)
    if caminho == '/agente/gameplay/cortar':
        return gpi.pedir_corte(d)
    mg = re.fullmatch(r'/agente/gameplay/(\w+)/historia', caminho)
    if mg:
        return gpi.propor_de_novo(mg.group(1), str(d.get('historia', '')), bool(d.get('usar_ia', True)))
    if caminho == '/estilos-visuais/medir':
        return {'medido': vp.medir(str(d.get('id', ''))), 'estilos': vp.listar()}
    if caminho == '/agente/pesos':
        return ag.salvar_pesos(d)
    if caminho == '/agente/aprender':
        ag.aprender(ajustar=False)      # lê os números que já podem ser lidos e só então ajusta
        return {'redes': ag.ajustar_pesos(), **ag.ver()}
    if caminho == '/agente/cortes/manual':
        return ag.receber_manual(d)
    if caminho == '/agente/rodar':
        return ag.rodar_agora(str(d.get('oque', '')), str(d.get('link', '')).strip())
    if caminho == '/agente/parar':
        return ag.parar_tudo()
    if caminho == '/agente/whatsapp/comando':     # mensagem sua no WhatsApp (pela ponte) -> resposta
        import comandos
        return {'resposta': comandos.responder(str(d.get('texto', ''))[:2000], 'whatsapp')}
    if caminho == '/agente/whatsapp/teste':
        ag.avisar_whatsapp('teste', '*EstúdioClip*: teste de aviso. Se chegou, os avisos e os pedidos de aprovação vão aparecer aqui.', erro=True)
        return {'ok': True}
    if caminho == '/agente/email/teste':
        ag.enviar_email('Teste de aviso', 'Se você recebeu este e-mail, os avisos do agente estão funcionando.')
        return {'ok': True}
    m = re.fullmatch(r'/agente/cortes/(\w+)/(descartar|agendar|liberar|email|editor|permitir)', caminho)
    if m:
        return ag.acao_corte(*m.groups())
    if caminho == '/contas/codigo':
        return {'rede': pg.receber_codigo(str(d.get('code', '')), str(d.get('state', '')))}
    if caminho == '/contas/verificar':
        return pg.verificar_contas()
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
    m = re.fullmatch(r'/posts/(\w+)/(agora|cancelar|feito|editar|liberar)', caminho)
    if m:
        pid, acao = m.groups()
        if acao == 'editar':
            return pg.editar_post(pid, d)
        if acao == 'liberar':
            return pg.liberar(pid)
        if acao == 'agora':
            return pg.postar_agora(pid)
        if acao == 'cancelar':
            return pg.cancelar_post(pid)
        return pg.marcar_feito(pid, str(d.get('rede', '')))
    raise Erro(404, 'Rota não encontrada.')


Handler.post_agenda = _rotas_agenda
Handler.TOKEN = TOKEN


# ---------------------------------------------------------------- agente de cortes pela fila
def _job_agente1(ctx):
    """Pedido manual do agente de cortes, agora pela fila (antes era recusado quando estava ocupado)."""
    oque, link = ctx.dados.get('oque', ''), ctx.dados.get('link', '')
    ctx.progresso(5, {'buscar': 'Buscando canais', 'cortar': 'Fazendo cortes', 'link': 'Cortando o link', 'tema': 'Procurando vídeo pelo tema', 'postar': 'Agendando cortes'}.get(oque, oque))
    nome = {'buscar': 'Busca de canais', 'cortar': 'Agente de cortes', 'link': 'Corte do link', 'tema': 'Corte por tema', 'postar': 'Agente de postagem'}.get(oque, oque)
    try:
        if oque == 'buscar':
            ag.buscar_canais()
        elif oque == 'cortar':
            ag.trabalhar_cortes(True)
        elif oque == 'link':
            ag.trabalhar_cortes(True, link)
        elif oque == 'tema':
            ag.trabalhar_cortes(True, '', link)
        elif oque == 'postar':
            ag.trabalhar_postagem()
    except (ag.ErroAgente, pg.ErroRede) as e:
        ag.anotar(f'{nome}: {e}', 'erro')       # aparece no histórico do agente, como antes
        e.definitivo = True
        raise
    finally:
        ag.etapa('')
        ag.depois_do_trabalho()      # Central ligada: continua repondo o estoque logo depois do seu pedido
    return {'resultado': {'ok': True}, 'etapa': 'Concluído'}


def _enfileirar_agente1(oque: str, link: str = '') -> dict:
    ja = db.um("SELECT id FROM jobs WHERE agente='agente1' AND status IN ('agendado','na_fila','rodando') AND dados=?",
               json.dumps({'oque': oque, 'link': link}, ensure_ascii=False))
    if ja:
        return {'ok': True, 'job': ja['id'], 'fila': True, 'ja_na_fila': True}
    pesado = oque in ('cortar', 'link', 'tema')
    j = fila.enfileirar('agente1.' + ('pesado' if pesado else 'leve'), agente='agente1', dados={'oque': oque, 'link': link},
                        recurso='pesado' if pesado else 'leve', titulo={'buscar': 'Buscar canais', 'cortar': 'Fazer cortes', 'link': 'Cortar link', 'tema': 'Cortar por tema',
                                                                        'postar': 'Agendar cortes prontos'}.get(oque, oque),
                        max_tentativas=1)
    return {'ok': True, 'job': j['id'], 'fila': True, 'ocupado': ag.OCUPADO.locked()}


def ligar_servicos():
    import agendador
    import backups
    import emails
    db.migrar()
    fila.CADEADO_PESADO = ag.OCUPADO       # um trabalho pesado por vez, dividido com o agente de cortes
    fila.registrar('agente1.pesado', _job_agente1, 'pesado')
    fila.registrar('agente1.leve', _job_agente1, 'leve')
    ag.ENFILEIRAR = _enfileirar_agente1
    import live
    live.PEGAR = url_da_live
    live.iniciar()
    ag.PENDENTES = lambda: (db.um("SELECT COUNT(*) AS n FROM jobs WHERE agente='agente1' AND status IN ('agendado','na_fila','rodando')") or {'n': 0})['n']
    produtor.iniciar()
    gpi.iniciar()
    api_v1.iniciar()
    fila.iniciar()
    agendador.iniciar()
    emails.iniciar()
    if os.getenv('BACKUP_DIARIO', '1') == '1':
        backups.iniciar()


def main():
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        print('Falta o yt-dlp. Rode:  pip install -U yt-dlp')
        raise SystemExit(1)
    if not shutil.which('ffmpeg') and not ffmpeg_path():
        print('Aviso: FFmpeg não encontrado. Vídeos acima de 360p podem falhar. (Termux: pkg install ffmpeg)')
    if HOST not in ('127.0.0.1', 'localhost', '::1') and not TOKEN:
        print('Por segurança o servidor não abre para a rede sem senha. Defina TOKEN=suasenha (ou use iniciar-termux.sh link).')
        raise SystemExit(1)
    if TOKEN and len(TOKEN) < 10:
        print('Aviso: a senha do servidor é curta. Use pelo menos 10 letras e números (bash iniciar-termux.sh senha).')
    pg.iniciar_relogio()
    ag.iniciar()
    ligar_servicos()
    if not rd.tem_ffmpeg():
        print('Aviso: sem FFmpeg o Agente 3 não produz vídeos (Termux: pkg install ffmpeg).')
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
