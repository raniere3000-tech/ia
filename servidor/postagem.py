"""Agendador do EstúdioClip: guarda os vídeos e posts no celular/PC e publica nas SUAS contas na hora marcada.

Redes: YouTube (Shorts), Facebook (Reels da Página), Instagram (Reels), TikTok. Kwai não tem API pública:
o post fica como "manual" com o botão de baixar o vídeo.
Só usa a biblioteca padrão do Python (roda no Termux).
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

DADOS = Path(os.getenv('DADOS', str(Path.home() / '.estudioclip')))
VIDEOS = DADOS / 'videos'
VIDEOS.mkdir(parents=True, exist_ok=True)
ARQ_CONTAS = DADOS / 'contas.json'
ARQ_POSTS = DADOS / 'posts.json'
GRAPH_V = os.getenv('GRAPH_VERSAO', 'v24.0')
REDES = ('youtube', 'facebook', 'instagram', 'tiktok', 'kwai')

# Endereços das APIs (trocáveis só para testes).
URL = {
    'google_auth': os.getenv('BASE_GOOGLE_AUTH', 'https://accounts.google.com'),
    'google_token': os.getenv('BASE_GOOGLE_TOKEN', 'https://oauth2.googleapis.com'),
    'google_api': os.getenv('BASE_GOOGLE_API', 'https://www.googleapis.com'),
    'fb_dialog': os.getenv('BASE_FB_DIALOG', 'https://www.facebook.com'),
    'graph': os.getenv('BASE_GRAPH', 'https://graph.facebook.com'),
    'graph_video': os.getenv('BASE_GRAPH_VIDEO', 'https://graph-video.facebook.com'),
    'rupload': os.getenv('BASE_RUPLOAD', 'https://rupload.facebook.com'),
    'tiktok_auth': os.getenv('BASE_TIKTOK_AUTH', 'https://www.tiktok.com'),
    'tiktok_api': os.getenv('BASE_TIKTOK_API', 'https://open.tiktokapis.com'),
}

LOCK = threading.RLock()
ESTADOS: dict[str, dict] = {}   # state do OAuth -> {provedor, volta, criado}


class ErroRede(Exception):
    pass


# ---------------------------------------------------------------- armazenamento
def _ler(arq: Path, padrao):
    try:
        return json.loads(arq.read_text(encoding='utf-8'))
    except Exception:
        return padrao


def _gravar(arq: Path, dados):
    tmp = arq.with_suffix('.tmp')
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(arq)
    try:
        os.chmod(arq, 0o600)
    except OSError:
        pass


def contas() -> dict:
    with LOCK:
        return _ler(ARQ_CONTAS, {})


def salvar_contas(c: dict):
    with LOCK:
        _gravar(ARQ_CONTAS, c)


def posts() -> list:
    with LOCK:
        return _ler(ARQ_POSTS, [])


def salvar_posts(p: list):
    with LOCK:
        _gravar(ARQ_POSTS, p)


def agora() -> float:
    return time.time()


# ---------------------------------------------------------------- HTTP
def http(metodo: str, url: str, *, dados: bytes | None = None, form: dict | None = None, js=None,
         cab: dict | None = None, tempo=120):
    cab = dict(cab or {})
    if form is not None:
        dados = urllib.parse.urlencode(form).encode()
        cab.setdefault('Content-Type', 'application/x-www-form-urlencoded')
    elif js is not None:
        dados = json.dumps(js).encode()
        cab.setdefault('Content-Type', 'application/json; charset=UTF-8')
    req = urllib.request.Request(url, data=dados, method=metodo, headers=cab)
    try:
        with urllib.request.urlopen(req, timeout=tempo) as r:
            corpo = r.read()
            return r.status, dict(r.headers), _json(corpo)
    except urllib.error.HTTPError as e:
        corpo = e.read()
        return e.code, dict(e.headers or {}), _json(corpo)
    except urllib.error.URLError as e:
        raise ErroRede(f'Sem conexão com {urllib.parse.urlparse(url).netloc}: {e.reason}')


def _json(b: bytes):
    try:
        return json.loads(b.decode() or '{}')
    except Exception:
        return {'_texto': b[:500].decode(errors='replace')}


def _msg(j) -> str:
    if isinstance(j, dict):
        e = j.get('error')
        if isinstance(e, dict):
            return e.get('message') or e.get('error_user_msg') or e.get('code') or json.dumps(e)[:300]
        if isinstance(e, str):
            return j.get('error_description') or e
        return j.get('_texto') or json.dumps(j)[:300]
    return str(j)[:300]


def _ok(st, j, oque):
    if st >= 300:
        raise ErroRede(f'{oque}: {_msg(j)}')
    return j


# ---------------------------------------------------------------- contas / OAuth
# provedor: google (YouTube), meta (Facebook + Instagram), tiktok
ESCOPOS = {
    'google': 'https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly',
    'meta': 'pages_show_list,pages_read_engagement,pages_manage_posts,instagram_basic,instagram_content_publish,business_management',
    'tiktok': 'user.info.basic,video.upload,video.publish',
}


def status_contas() -> dict:
    c = contas()
    out = {}
    for prov in ('google', 'meta', 'tiktok'):
        d = c.get(prov, {})
        out[prov] = {'app': bool(d.get('client_id') and d.get('client_secret')), 'conectado': bool(d.get('token')),
                     'nome': d.get('nome', ''), 'client_id': d.get('client_id', ''), 'paginas': [
                         {'id': p['id'], 'nome': p['nome'], 'instagram': p.get('ig_usuario', '')} for p in d.get('paginas', [])],
                     'pagina': d.get('pagina', ''), 'erro': d.get('erro', '')}
    return out


def salvar_app(prov: str, client_id: str, client_secret: str):
    if prov not in ESCOPOS:
        raise ErroRede('Rede desconhecida.')
    c = contas()
    d = c.get(prov, {})
    if client_id.strip():
        d['client_id'] = client_id.strip()
    if client_secret.strip():
        d['client_secret'] = client_secret.strip()
    c[prov] = d
    salvar_contas(c)


def url_login(prov: str, volta: str) -> str:
    d = contas().get(prov, {})
    if not d.get('client_id') or not d.get('client_secret'):
        raise ErroRede('Primeiro salve o ID e o segredo do app desta rede.')
    for s, v in list(ESTADOS.items()):
        if agora() - v['criado'] > 1800:
            ESTADOS.pop(s, None)
    estado = f'{prov}_{secrets.token_urlsafe(16)}'
    ESTADOS[estado] = {'prov': prov, 'volta': volta, 'criado': agora()}
    if prov == 'google':
        q = {'client_id': d['client_id'], 'redirect_uri': volta, 'response_type': 'code', 'scope': ESCOPOS['google'],
             'access_type': 'offline', 'prompt': 'consent', 'include_granted_scopes': 'true', 'state': estado}
        return URL['google_auth'] + '/o/oauth2/v2/auth?' + urllib.parse.urlencode(q)
    if prov == 'meta':
        q = {'client_id': d['client_id'], 'redirect_uri': volta, 'response_type': 'code', 'scope': ESCOPOS['meta'], 'state': estado}
        return f"{URL['fb_dialog']}/{GRAPH_V}/dialog/oauth?" + urllib.parse.urlencode(q)
    q = {'client_key': d['client_id'], 'redirect_uri': volta, 'response_type': 'code', 'scope': ESCOPOS['tiktok'], 'state': estado}
    return URL['tiktok_auth'] + '/v2/auth/authorize/?' + urllib.parse.urlencode(q)


def receber_codigo(code: str, estado: str) -> str:
    e = ESTADOS.pop(estado, None)
    if not e:
        raise ErroRede('Login expirou ou veio de outro servidor. Clique em "Entrar" de novo.')
    prov, volta = e['prov'], e['volta']
    c = contas()
    d = c.get(prov, {})
    if prov == 'google':
        st, _, j = http('POST', URL['google_token'] + '/token', form={
            'code': code, 'client_id': d['client_id'], 'client_secret': d['client_secret'], 'redirect_uri': volta, 'grant_type': 'authorization_code'})
        _ok(st, j, 'Google recusou o login')
        d['token'] = {'access': j['access_token'], 'refresh': j.get('refresh_token') or d.get('token', {}).get('refresh'), 'expira': agora() + j.get('expires_in', 3600) - 60}
        c[prov] = d
        salvar_contas(c)
        try:
            st, _, j = http('GET', URL['google_api'] + '/youtube/v3/channels?part=snippet&mine=true', cab={'Authorization': 'Bearer ' + d['token']['access']})
            itens = j.get('items') or []
            d['nome'] = itens[0]['snippet']['title'] if itens else '(conta sem canal do YouTube)'
        except Exception:
            d['nome'] = 'YouTube conectado'
    elif prov == 'meta':
        base = f"{URL['graph']}/{GRAPH_V}"
        st, _, j = http('GET', base + '/oauth/access_token?' + urllib.parse.urlencode({
            'client_id': d['client_id'], 'client_secret': d['client_secret'], 'redirect_uri': volta, 'code': code}))
        _ok(st, j, 'Facebook recusou o login')
        curto = j['access_token']
        st, _, j = http('GET', base + '/oauth/access_token?' + urllib.parse.urlencode({
            'grant_type': 'fb_exchange_token', 'client_id': d['client_id'], 'client_secret': d['client_secret'], 'fb_exchange_token': curto}))
        longo = j.get('access_token', curto) if st < 300 else curto
        st, _, j = http('GET', base + '/me?fields=name&access_token=' + urllib.parse.quote(longo))
        d['nome'] = j.get('name', 'Facebook conectado') if st < 300 else 'Facebook conectado'
        st, _, j = http('GET', base + '/me/accounts?' + urllib.parse.urlencode({
            'fields': 'id,name,access_token,instagram_business_account{id,username}', 'limit': 100, 'access_token': longo}))
        _ok(st, j, 'Não consegui ler suas Páginas do Facebook')
        paginas = []
        for p in j.get('data', []):
            ig = p.get('instagram_business_account') or {}
            paginas.append({'id': p['id'], 'nome': p.get('name', ''), 'token': p.get('access_token', ''),
                            'ig_id': ig.get('id', ''), 'ig_usuario': ig.get('username', '')})
        if not paginas:
            raise ErroRede('Nenhuma Página do Facebook encontrada. Na hora do login, marque a Página (e o Instagram) que o app pode usar.')
        d['token'] = {'usuario': longo}
        d['paginas'] = paginas
        if d.get('pagina') not in [p['id'] for p in paginas]:
            com_ig = [p for p in paginas if p['ig_id']]
            d['pagina'] = (com_ig or paginas)[0]['id']
    else:
        st, _, j = http('POST', URL['tiktok_api'] + '/v2/oauth/token/', form={
            'client_key': d['client_id'], 'client_secret': d['client_secret'], 'code': code,
            'grant_type': 'authorization_code', 'redirect_uri': volta})
        if st >= 300 or 'access_token' not in j:
            raise ErroRede('TikTok recusou o login: ' + (j.get('error_description') or _msg(j)))
        d['token'] = {'access': j['access_token'], 'refresh': j.get('refresh_token'), 'expira': agora() + j.get('expires_in', 86400) - 120,
                      'open_id': j.get('open_id')}
        c[prov] = d
        salvar_contas(c)
        try:
            st, _, j = http('GET', URL['tiktok_api'] + '/v2/user/info/?fields=display_name', cab={'Authorization': 'Bearer ' + d['token']['access']})
            d['nome'] = (j.get('data') or {}).get('user', {}).get('display_name') or 'TikTok conectado'
        except Exception:
            d['nome'] = 'TikTok conectado'
    d.pop('erro', None)
    c[prov] = d
    salvar_contas(c)
    return prov


def escolher_pagina(pagina: str):
    c = contas()
    d = c.get('meta', {})
    if pagina not in [p['id'] for p in d.get('paginas', [])]:
        raise ErroRede('Página não encontrada.')
    d['pagina'] = pagina
    salvar_contas(c)


def sair(prov: str):
    c = contas()
    d = c.get(prov, {})
    for k in ('token', 'nome', 'paginas', 'pagina', 'erro'):
        d.pop(k, None)
    c[prov] = d
    salvar_contas(c)


def _token_google() -> str:
    c = contas()
    d = c.get('google', {})
    t = d.get('token')
    if not t:
        raise ErroRede('YouTube não conectado. Em "Agendar posts", entre com sua conta.')
    if agora() < t.get('expira', 0):
        return t['access']
    if not t.get('refresh'):
        raise ErroRede('Login do YouTube expirou. Entre de novo.')
    st, _, j = http('POST', URL['google_token'] + '/token', form={
        'client_id': d['client_id'], 'client_secret': d['client_secret'], 'refresh_token': t['refresh'], 'grant_type': 'refresh_token'})
    if st >= 300:
        d['erro'] = 'Login expirou. Entre de novo (se acontecer toda semana, publique o app do Google: veja o "?").'
        salvar_contas(c)
        raise ErroRede('Login do YouTube expirou: ' + _msg(j) + '. Entre de novo em "Agendar posts".')
    t['access'] = j['access_token']
    t['expira'] = agora() + j.get('expires_in', 3600) - 60
    salvar_contas(c)
    return t['access']


def _token_tiktok() -> dict:
    c = contas()
    d = c.get('tiktok', {})
    t = d.get('token')
    if not t:
        raise ErroRede('TikTok não conectado. Em "Agendar posts", entre com sua conta.')
    if agora() < t.get('expira', 0):
        return t
    st, _, j = http('POST', URL['tiktok_api'] + '/v2/oauth/token/', form={
        'client_key': d['client_id'], 'client_secret': d['client_secret'], 'grant_type': 'refresh_token', 'refresh_token': t.get('refresh', '')})
    if st >= 300 or 'access_token' not in j:
        d['erro'] = 'Login expirou. Entre de novo.'
        salvar_contas(c)
        raise ErroRede('Login do TikTok expirou. Entre de novo em "Agendar posts".')
    t.update(access=j['access_token'], refresh=j.get('refresh_token', t.get('refresh')), expira=agora() + j.get('expires_in', 86400) - 120)
    salvar_contas(c)
    return t


def _pagina_meta() -> dict:
    d = contas().get('meta', {})
    if not d.get('token'):
        raise ErroRede('Facebook/Instagram não conectado. Em "Agendar posts", entre com sua conta.')
    for p in d.get('paginas', []):
        if p['id'] == d.get('pagina'):
            return p
    raise ErroRede('Escolha a Página do Facebook em "Agendar posts".')


# ---------------------------------------------------------------- vídeos
def receber_pedaco(vid: str | None, offset: int, dados: bytes, nome: str) -> dict:
    if vid is None:
        vid = uuid.uuid4().hex[:12]
        ext = '.webm' if nome.lower().endswith('.webm') else '.mov' if nome.lower().endswith('.mov') else '.mp4'
        (VIDEOS / (vid + '.parte' + ext)).write_bytes(b'')
    if not vid.isalnum():
        raise ErroRede('Vídeo inválido.')
    partes = list(VIDEOS.glob(vid + '.parte.*'))
    if not partes:
        raise ErroRede('Envio não encontrado. Tente de novo.')
    arq = partes[0]
    if arq.stat().st_size != offset:
        raise ErroRede(f'Pedaço fora de ordem (esperava {arq.stat().st_size}).')
    with open(arq, 'ab') as f:
        f.write(dados)
    return {'video': vid, 'recebido': arq.stat().st_size}


PREPARANDO: set[str] = set()


def finalizar_video(vid: str) -> dict:
    """Converte em segundo plano (no celular pode levar alguns minutos) e já devolve."""
    partes = list(VIDEOS.glob(vid + '.parte.*'))
    if not partes:
        raise ErroRede('Envio não encontrado.')
    PREPARANDO.add(vid)
    threading.Thread(target=_converter, args=(vid, partes[0]), daemon=True).start()
    return {'video': vid, 'preparando': True}


def _converter(vid: str, arq: Path):
    try:
        _converter_agora(vid, arq)
    except Exception as e:  # noqa: BLE001
        print('conversão:', e)
        if arq.exists():
            arq.replace(VIDEOS / (vid + arq.suffix.replace('.parte', '')))
    finally:
        PREPARANDO.discard(vid)
        acordar()


def _converter_agora(vid: str, arq: Path):
    final = VIDEOS / (vid + '.mp4')
    tmp = VIDEOS / (vid + '.conv.mp4')
    ff = shutil.which('ffmpeg')
    if not ff:
        arq.replace(final if arq.suffix != '.webm' else VIDEOS / (vid + '.webm'))
        return
    # MP4 "normal" (as redes recusam alguns MP4 gravados pelo navegador) e WEBM -> MP4.
    recodificar = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-c:a', 'aac', '-b:a', '160k']
    tentativas = [['-c', 'copy'], recodificar] if arq.suffix != '.webm' else [recodificar]
    for opc in tentativas:
        p = subprocess.run([ff, '-nostdin', '-y', '-v', 'error', '-i', str(arq), *opc, '-movflags', '+faststart', str(tmp)],
                           stdin=subprocess.DEVNULL, capture_output=True, text=True)
        if p.returncode == 0:
            tmp.replace(final)
            arq.unlink(missing_ok=True)
            return
    tmp.unlink(missing_ok=True)
    arq.replace(final if arq.suffix != '.webm' else VIDEOS / (vid + '.webm'))


def video_pronto(vid: str) -> bool:
    return vid not in PREPARANDO and not list(VIDEOS.glob(vid + '.parte.*'))


def video_path(vid: str) -> Path:
    for ext in ('.mp4', '.webm', '.mov'):
        p = VIDEOS / (vid + ext)
        if p.exists():
            return p
    raise ErroRede('Arquivo do vídeo não está mais no servidor.')


# ---------------------------------------------------------------- posts
def criar_post(d: dict) -> dict:
    vid = str(d.get('video', ''))
    if not vid.isalnum() or not (list(VIDEOS.glob(vid + '.*'))):
        raise ErroRede('Vídeo não encontrado no servidor. Envie de novo.')
    redes = [r for r in d.get('redes', []) if r in REDES]
    if not redes:
        raise ErroRede('Escolha pelo menos uma rede.')
    quando = float(d.get('quando') or agora())
    p = {
        'id': uuid.uuid4().hex[:10], 'video': vid, 'criado': agora(), 'quando': quando,
        'titulo': str(d.get('titulo', ''))[:100], 'legenda': str(d.get('legenda', ''))[:2200],
        'opcoes': {'youtube_privacidade': d.get('youtube_privacidade', 'public'), 'tiktok_modo': d.get('tiktok_modo', 'rascunho')},
        'redes': {r: {'status': 'manual' if r == 'kwai' else 'agendado', 'link': '', 'erro': ''} for r in redes},
    }
    with LOCK:
        ps = posts()
        ps.append(p)
        salvar_posts(ps)
    return p


def lista_posts() -> list:
    ps = sorted(posts(), key=lambda p: p['quando'])
    for p in ps:
        p['preparando'] = not video_pronto(p['video'])
    return ps


def _mudar(pid: str, f):
    with LOCK:
        ps = posts()
        for p in ps:
            if p['id'] == pid:
                f(p)
                salvar_posts(ps)
                return p
    raise ErroRede('Post não encontrado.')


def cancelar_post(pid: str):
    with LOCK:
        ps = posts()
        alvo = [p for p in ps if p['id'] == pid]
        if not alvo:
            raise ErroRede('Post não encontrado.')
        if any(r['status'] == 'postando' for r in alvo[0]['redes'].values()):
            raise ErroRede('Este post está sendo enviado agora. Espere terminar.')
        ps = [p for p in ps if p['id'] != pid]
        salvar_posts(ps)
    if not any(p['video'] == alvo[0]['video'] for p in ps) and alvo[0]['video'] not in PREPARANDO:
        for arq in VIDEOS.glob(alvo[0]['video'] + '.*'):
            arq.unlink(missing_ok=True)


def postar_agora(pid: str):
    def f(p):
        p['quando'] = agora()
        for r in p['redes'].values():
            if r['status'] == 'erro':
                r.update(status='agendado', erro='')
    _mudar(pid, f)
    acordar()


def marcar_feito(pid: str, rede: str):
    _mudar(pid, lambda p: p['redes'].get(rede, {}).update(status='postado', erro=''))


# ---------------------------------------------------------------- publicação em cada rede
def _texto(p: dict, limite: int) -> str:
    t = (p['legenda'] or p['titulo']).strip()
    return t[:limite]


def postar_youtube(p: dict, arq: Path) -> str:
    tok = _token_google()
    titulo = (p['titulo'] or p['legenda'] or 'Corte').strip()[:100]
    if '#shorts' not in (titulo + p['legenda']).lower():
        desc = (p['legenda'] + '\n\n#shorts').strip()
    else:
        desc = p['legenda']
    meta = {'snippet': {'title': titulo, 'description': desc[:5000], 'categoryId': '22'},
            'status': {'privacyStatus': p['opcoes'].get('youtube_privacidade', 'public'), 'selfDeclaredMadeForKids': False}}
    tam = arq.stat().st_size
    st, cab, j = http('POST', URL['google_api'] + '/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status', js=meta,
                      cab={'Authorization': 'Bearer ' + tok, 'X-Upload-Content-Type': 'video/mp4', 'X-Upload-Content-Length': str(tam)})
    _ok(st, j, 'YouTube recusou o envio')
    destino = cab.get('Location') or cab.get('location')
    if not destino:
        raise ErroRede('YouTube não devolveu o endereço de envio.')
    with open(arq, 'rb') as f:
        st, _, j = http('PUT', destino, dados=f.read(), cab={'Content-Type': 'video/mp4', 'Content-Length': str(tam)}, tempo=1800)
    _ok(st, j, 'YouTube recusou o vídeo')
    vid = j.get('id')
    priv = (j.get('status') or {}).get('privacyStatus')
    link = f'https://youtube.com/shorts/{vid}'
    if p['opcoes'].get('youtube_privacidade', 'public') != 'private' and priv == 'private':
        link += '  (o YouTube deixou privado: projeto do Google ainda não verificado; veja o "?")'
    return link


def _rupload(url: str, token: str, arq: Path):
    tam = arq.stat().st_size
    with open(arq, 'rb') as f:
        st, _, j = http('POST', url, dados=f.read(), cab={'Authorization': 'OAuth ' + token, 'offset': '0', 'file_size': str(tam),
                                                          'Content-Type': 'application/octet-stream'}, tempo=1800)
    _ok(st, j, 'Meta recusou o arquivo')
    return j


def postar_facebook(p: dict, arq: Path) -> str:
    pg = _pagina_meta()
    base = f"{URL['graph']}/{GRAPH_V}"
    st, _, j = http('POST', f"{base}/{pg['id']}/video_reels", form={'upload_phase': 'start', 'access_token': pg['token']})
    _ok(st, j, 'Facebook recusou o Reels')
    vid = j['video_id']
    _rupload(j.get('upload_url') or f"{URL['rupload']}/video-upload/{GRAPH_V}/{vid}", pg['token'], arq)
    st, _, j = http('POST', f"{base}/{pg['id']}/video_reels", form={
        'upload_phase': 'finish', 'video_id': vid, 'video_state': 'PUBLISHED', 'description': _texto(p, 2200), 'access_token': pg['token']})
    _ok(st, j, 'Facebook não publicou o Reels')
    return f'https://www.facebook.com/reel/{vid}'


def postar_instagram(p: dict, arq: Path) -> str:
    pg = _pagina_meta()
    if not pg.get('ig_id'):
        raise ErroRede('A Página escolhida não tem Instagram profissional ligado. Ligue o Instagram à Página no app do Instagram ou no Facebook.')
    base = f"{URL['graph']}/{GRAPH_V}"
    st, _, j = http('POST', f"{base}/{pg['ig_id']}/media", form={
        'media_type': 'REELS', 'upload_type': 'resumable', 'caption': _texto(p, 2200), 'share_to_feed': 'true', 'access_token': pg['token']})
    _ok(st, j, 'Instagram recusou o Reels')
    cont = j['id']
    _rupload(j.get('uri') or f"{URL['rupload']}/ig-api-upload/{GRAPH_V}/{cont}", pg['token'], arq)
    for _ in range(120):   # até ~10 min processando
        st, _, j = http('GET', f"{base}/{cont}?fields=status_code,status&access_token=" + urllib.parse.quote(pg['token']))
        sc = j.get('status_code')
        if sc == 'FINISHED':
            break
        if sc in ('ERROR', 'EXPIRED'):
            raise ErroRede('Instagram não aceitou o vídeo: ' + str(j.get('status', sc)))
        time.sleep(float(os.getenv('ESPERA_IG', '5')))
    else:
        raise ErroRede('Instagram demorou demais para processar o vídeo.')
    st, _, j = http('POST', f"{base}/{pg['ig_id']}/media_publish", form={'creation_id': cont, 'access_token': pg['token']})
    _ok(st, j, 'Instagram não publicou')
    mid = j['id']
    st, _, j = http('GET', f"{base}/{mid}?fields=permalink&access_token=" + urllib.parse.quote(pg['token']))
    return j.get('permalink') or f"https://www.instagram.com/{pg.get('ig_usuario', '')}"


def postar_tiktok(p: dict, arq: Path) -> str:
    t = _token_tiktok()
    cab = {'Authorization': 'Bearer ' + t['access']}
    tam = arq.stat().st_size
    if tam <= 64 * 1024 * 1024:
        pedaco, n = tam, 1
    else:
        pedaco = 10 * 1024 * 1024
        n = tam // pedaco
    fonte = {'source': 'FILE_UPLOAD', 'video_size': tam, 'chunk_size': pedaco, 'total_chunk_count': n}
    direto = p['opcoes'].get('tiktok_modo') == 'direto'
    if direto:
        st, _, j = http('POST', URL['tiktok_api'] + '/v2/post/publish/creator_info/query/', js={}, cab=cab)
        opcoes = ((j.get('data') or {}).get('privacy_level_options') or ['SELF_ONLY']) if st < 300 else ['SELF_ONLY']
        priv = 'PUBLIC_TO_EVERYONE' if 'PUBLIC_TO_EVERYONE' in opcoes else opcoes[0]
        corpo = {'post_info': {'title': _texto(p, 2200), 'privacy_level': priv}, 'source_info': fonte}
        rota = '/v2/post/publish/video/init/'
    else:
        corpo = {'source_info': fonte}
        rota = '/v2/post/publish/inbox/video/init/'
    st, _, j = http('POST', URL['tiktok_api'] + rota, js=corpo, cab=cab)
    erro = (j.get('error') or {})
    if st >= 300 or (erro.get('code') not in (None, 'ok')):
        raise ErroRede('TikTok recusou: ' + (erro.get('message') or _msg(j)))
    dados = j['data']
    with open(arq, 'rb') as f:
        for i in range(n):
            ini = i * pedaco
            fim = tam - 1 if i == n - 1 else ini + pedaco - 1
            f.seek(ini)
            bloco = f.read(fim - ini + 1)
            st, _, jj = http('PUT', dados['upload_url'], dados=bloco, cab={'Content-Type': 'video/mp4', 'Content-Length': str(len(bloco)),
                                                                          'Content-Range': f'bytes {ini}-{fim}/{tam}'}, tempo=1800)
            if st >= 300:
                raise ErroRede('TikTok recusou o envio do vídeo: ' + _msg(jj))
    if direto:
        return 'Enviado ao TikTok' + ('' if priv == 'PUBLIC_TO_EVERYONE' else ' como "Só eu" (app ainda não aprovado pelo TikTok)')
    return 'Está nos rascunhos/notificações do TikTok: abra o app e toque em Postar'


PUBLICAR = {'youtube': postar_youtube, 'facebook': postar_facebook, 'instagram': postar_instagram, 'tiktok': postar_tiktok}


# ---------------------------------------------------------------- relógio
_acordar = threading.Event()


def acordar():
    _acordar.set()


def _publicar_um(pid: str, rede: str):
    def iniciar(p):
        p['redes'][rede].update(status='postando', erro='', inicio=agora())
    p = _mudar(pid, iniciar)
    try:
        link = PUBLICAR[rede](p, video_path(p['video']))
        _mudar(pid, lambda q: q['redes'][rede].update(status='postado', link=link, erro='', feito=agora()))
    except Exception as e:  # noqa: BLE001
        msg = str(e) if isinstance(e, ErroRede) else f'Erro inesperado: {e}'
        _mudar(pid, lambda q: q['redes'][rede].update(status='erro', erro=msg[:500]))


def ciclo():
    """Publica tudo que já passou do horário (uma rede por vez)."""
    for p in lista_posts():
        if p['quando'] > agora() or not video_pronto(p['video']):
            continue
        for rede, r in p['redes'].items():
            if r['status'] == 'agendado':
                _publicar_um(p['id'], rede)
            elif r['status'] == 'postando' and agora() - r.get('inicio', 0) > 3600:
                _mudar(p['id'], lambda q, rede=rede: q['redes'][rede].update(status='erro', erro='O envio foi interrompido (servidor desligou?). Clique em Tentar de novo.'))


def iniciar_relogio():
    # Posts que estavam "postando" quando o servidor caiu voltam como erro para você decidir.
    with LOCK:
        ps = posts()
        for p in ps:
            for r in p['redes'].values():
                if r['status'] == 'postando':
                    r.update(status='erro', erro='O servidor desligou durante o envio. Clique em Tentar de novo.')
        salvar_posts(ps)

    def laco():
        while True:
            try:
                ciclo()
            except Exception as e:  # noqa: BLE001
                print('agendador:', e)
            _acordar.wait(float(os.getenv('INTERVALO_AGENDA', '30')))
            _acordar.clear()
    threading.Thread(target=laco, daemon=True).start()


def resumo_data(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()
