"""Servidor do EstúdioClip: baixa um vídeo do YouTube pelo link para o site cortar sozinho.

Use apenas com vídeos seus ou com autorização do dono.
Rodar:  python servidor.py   (abre em http://localhost:8787)
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

VERSAO = '1.0.0'
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

app = FastAPI(title='EstúdioClip servidor', version=VERSAO)
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()


@app.middleware('http')
async def cors(request, call_next):
    """CORS + Private Network Access (o site no github.io pode chamar o localhost)."""
    origem = request.headers.get('origin', '')
    ok = origem in ORIGENS or '*' in ORIGENS
    if request.method == 'OPTIONS':
        resp = JSONResponse({}, status_code=204 if ok else 403)
    else:
        resp = await call_next(request)
    if ok:
        resp.headers['Access-Control-Allow-Origin'] = origem
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Token'
        resp.headers['Access-Control-Allow-Private-Network'] = 'true'
        resp.headers['Access-Control-Expose-Headers'] = 'Content-Length, X-Titulo'
        resp.headers['Vary'] = 'Origin'
    return resp


def checar_token(tok: str | None):
    if TOKEN and (tok or '') != TOKEN:
        raise HTTPException(401, 'Senha do servidor errada. Confira em Chaves e ajustes.')


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


class Pedido(BaseModel):
    url: str


@app.get('/saude')
def saude():
    import yt_dlp
    return {'ok': True, 'versao': VERSAO, 'yt_dlp': yt_dlp.version.__version__, 'senha': bool(TOKEN), 'max_minutos': MAX_MIN}


@app.post('/baixar')
def iniciar(p: Pedido, x_token: str | None = Header(default=None)):
    checar_token(x_token)
    url = p.url.strip()
    if not (YT.match(url) or (QUALQUER_URL and url.startswith('http'))):
        raise HTTPException(400, 'Envie um link do YouTube.')
    limpar_antigos()
    jid = uuid.uuid4().hex[:12]
    JOBS[jid] = {'status': 'baixando', 'pct': 0, 'criado': time.time(), 'url': url}
    threading.Thread(target=baixar, args=(jid, url), daemon=True).start()
    return {'id': jid}


@app.get('/baixar/{jid}')
def status(jid: str, x_token: str | None = Header(default=None)):
    checar_token(x_token)
    j = JOBS.get(jid)
    if not j:
        raise HTTPException(404, 'Download não encontrado (o servidor reiniciou?). Tente de novo.')
    return {k: j.get(k) for k in ('status', 'pct', 'erro', 'titulo', 'duracao', 'tamanho')}


@app.get('/baixar/{jid}/arquivo')
def arquivo(jid: str, x_token: str | None = Header(default=None), token: str | None = None):
    checar_token(x_token or token)
    j = JOBS.get(jid)
    if not j or j.get('status') != 'pronto':
        raise HTTPException(404, 'Arquivo ainda não está pronto.')
    caminho = Path(j['arquivo'])

    def apagar():
        shutil.rmtree(PASTA / jid, ignore_errors=True)
        JOBS.pop(jid, None)

    nome = re.sub(r'[^\w\- ]+', '', j.get('titulo') or 'video')[:80].strip() or 'video'
    resp = FileResponse(caminho, media_type='video/mp4' if caminho.suffix == '.mp4' else 'video/webm',
                        filename=nome + caminho.suffix, background=BackgroundTask(apagar))
    resp.headers['X-Titulo'] = re.sub(r'[^\x20-\x7e]', '', j.get('titulo') or '')[:200]
    return resp


if __name__ == '__main__':
    print(f'\n  EstúdioClip servidor {VERSAO} rodando em http://localhost:{PORTA}')
    print('  Cole esse endereço no site, em Chaves e ajustes > Servidor de cortes pelo link.')
    print('  Deixe esta janela aberta enquanto usa o site. Para parar: Ctrl+C\n')
    uvicorn.run(app, host=HOST, port=PORTA, log_level='warning')
