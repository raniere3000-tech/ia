"""Agendador do EstúdioClip: guarda os vídeos e posts no celular/PC e publica nas SUAS contas na hora marcada.

Redes: YouTube (Shorts), Facebook (Reels da Página), Instagram (Reels), TikTok. Kwai não tem API pública:
o post fica como "manual" com o botão de baixar o vídeo.
Só usa a biblioteca padrão do Python (roda no Termux).
"""
from __future__ import annotations

import descricao as ds
import hashlib
import json
import os
import re
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

import cofre

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


class ErroTemporario(ErroRede):
    """Falha que costuma passar sozinha (internet caiu, rede fora do ar, limite por minuto): o agendador tenta de novo."""


# Esperas, em minutos, antes de cada nova tentativa automática de um post que falhou por motivo passageiro.
ESPERAS = [float(x) for x in os.getenv('ESPERAS_TENTATIVA', '2,10,30,120').split(',') if x.strip()]


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
        return cofre.ler_json(ARQ_CONTAS, {})


def salvar_contas(c: dict):
    with LOCK:
        cofre.gravar_json(ARQ_CONTAS, c)


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
        raise ErroTemporario(f'Sem conexão com {urllib.parse.urlparse(url).netloc}: {e.reason}')
    except OSError as e:   # queda no meio do envio, tempo esgotado
        raise ErroTemporario(f'A conexão com {urllib.parse.urlparse(url).netloc} caiu no meio: {e}')


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
    if st >= 500 or st == 429:
        raise ErroTemporario(f'{oque} (erro {st}, a rede está instável ou pediu para esperar): {_msg(j)}')
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
                     'pagina': d.get('pagina', ''), 'erro': d.get('erro', ''), 'verificado': d.get('verificado', 0)}
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


def verificar_contas() -> dict:
    """Confere se o login de cada rede ainda vale (renova o que dá) para avisar antes da hora do post."""
    for prov in ('google', 'meta', 'tiktok'):
        if not contas().get(prov, {}).get('token'):
            continue
        erro = ''
        try:
            if prov == 'google':
                _token_google()
            elif prov == 'tiktok':
                _token_tiktok()
            else:
                d = contas()['meta']
                st, _, j = http('GET', f"{URL['graph']}/{GRAPH_V}/me?fields=id&access_token=" + urllib.parse.quote(d['token']['usuario']), tempo=30)
                if 400 <= st < 500:
                    erro = 'O Facebook não aceita mais este login (' + _msg(j)[:120] + '). Entre de novo.'
        except ErroTemporario:
            continue   # sem internet agora: não dá para saber, confere na próxima
        except ErroRede as e:
            erro = str(e)
        c = contas()
        d = c.get(prov, {})
        if erro:
            d['erro'] = erro
        else:
            d.pop('erro', None)
        d['verificado'] = agora()
        c[prov] = d
        salvar_contas(c)
    return status_contas()


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
def assinatura(vid: str) -> str:
    """Impressão digital do arquivo, para não postar o mesmo vídeo duas vezes na mesma rede."""
    if not video_pronto(vid):
        return ''
    try:
        h = hashlib.sha1()
        with open(video_path(vid), 'rb') as f:
            for bloco in iter(lambda: f.read(1 << 20), b''):
                h.update(bloco)
        return h.hexdigest()
    except (ErroRede, OSError):
        return ''


def criar_post(d: dict) -> dict:
    vid = str(d.get('video', ''))
    if not vid.isalnum() or not (list(VIDEOS.glob(vid + '.*'))):
        raise ErroRede('Vídeo não encontrado no servidor. Envie de novo.')
    redes = [r for r in d.get('redes', []) if r in REDES]
    if not redes:
        raise ErroRede('Escolha pelo menos uma rede.')
    import pipeline as pl
    if pl.ligado():          # esteira ligada: nem chega a criar o post sem o certificado do diretor para este arquivo
        pp = pl.portao_postagem(video_path(vid))
        if not pp['ok']:
            raise ErroRede(pp['detalhe'])
    quando = float(d.get('quando') or agora())
    marca = assinatura(vid)
    if marca and not d.get('repetir'):
        # o mesmo arquivo não vai duas vezes para a mesma rede
        for outro in posts():
            repetidas = [r for r in redes if r in outro['redes'] and outro['redes'][r]['status'] != 'erro'] if outro.get('hash') == marca else []
            if repetidas:
                raise ErroRede('Este mesmo vídeo já está agendado ou postado em ' + ', '.join(x.capitalize() for x in repetidas) + '. Para postar de novo mesmo assim, cancele o post anterior.')
    p = {
        'id': uuid.uuid4().hex[:10], 'video': vid, 'criado': agora(), 'quando': quando,
        'titulo': str(d.get('titulo', ''))[:100], 'legenda': str(d.get('legenda', ''))[:5000],
        'opcoes': {'youtube_privacidade': d.get('youtube_privacidade', 'public'), 'tiktok_modo': d.get('tiktok_modo', 'rascunho')},
        'redes': {r: {'status': 'manual' if r == 'kwai' else 'agendado', 'link': '', 'erro': ''} for r in redes},
        'modelo': re.sub(r'[^a-zA-Z0-9_-]', '', str(d.get('modelo', '')))[:40], 'origem': str(d.get('origem', 'manual'))[:20], 'hash': marca,
        'direitos': {'origem': str((d.get('direitos') or {}).get('origem', ''))[:20], 'nota': str((d.get('direitos') or {}).get('nota', ''))[:300]} if isinstance(d.get('direitos'), dict) else None,
        # Agente 3: de qual projeto/versão aprovada veio e quais créditos de imagem a legenda precisa levar
        'projeto': re.sub(r'[^a-zA-Z0-9]', '', str(d.get('projeto', '')))[:40], 'render_sha': re.sub(r'[^a-f0-9]', '', str(d.get('render_sha', '')))[:64],
        'creditos': [str(x)[:160] for x in (d.get('creditos') or [])[:12]] if isinstance(d.get('creditos'), list) else [],
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


def cancelar_post(pid: str, manter_video: bool = False):
    with LOCK:
        ps = posts()
        alvo = [p for p in ps if p['id'] == pid]
        if not alvo:
            raise ErroRede('Post não encontrado.')
        if any(r['status'] == 'postando' for r in alvo[0]['redes'].values()):
            raise ErroRede('Este post está sendo enviado agora. Espere terminar.')
        ps = [p for p in ps if p['id'] != pid]
        salvar_posts(ps)
    if not manter_video and not any(p['video'] == alvo[0]['video'] for p in ps) and alvo[0]['video'] not in PREPARANDO:
        for arq in VIDEOS.glob(alvo[0]['video'] + '.*'):
            arq.unlink(missing_ok=True)


def postar_agora(pid: str, rede: str = ''):
    """Posta agora. Com `rede`, tenta de novo SÓ nessa rede (as que já foram ficam como estão)."""
    antes: dict = {}

    def f(p):
        if rede and rede not in p['redes']:
            raise ErroRede('Este post não tem essa rede.')
        if not rede:
            antes['quando'] = p['quando'] if p['quando'] > agora() + 60 else 0
            if p['quando'] > agora() + 60 and (p.get('agenda') or {}).get('slot'):
                p['agenda_liberada'] = p['agenda']['slot']     # postado antes da hora: o horário da programação volta a ficar livre
                p.pop('agenda', None)
            p['quando'] = min(p['quando'], agora())
        for nome, r in p['redes'].items():
            if (not rede or nome == rede) and r['status'] in ('erro', 'agendado'):
                r.update(status='agendado', erro='', tentativas=0, proxima=0)
                if rede:
                    _anotar(p, nome, 'tentar_de_novo', 'Você pediu para tentar de novo só nesta rede.')
    p = _mudar(pid, f)
    acordar()
    if not rede:
        try:       # o corte acompanha: a vaga do horário antigo fica livre para o próximo corte
            import agente
            agente._mudar(lambda e: [x.update(quando=agora(), via_agenda=False) for x in e['cortes'] if x.get('post') == pid])
        except Exception as e:  # noqa: BLE001
            print('postagem: corte do post', e)
        if antes.get('quando') and not p.get('agenda_liberada') and p.get('origem') != 'agenda':
            try:       # vídeo de uma ordem do Coordenador: o próximo da série sobe para o horário que ficou livre
                import coordenador as co
                co.post_antecipado(pid, antes['quando'])
            except Exception as e:  # noqa: BLE001
                print('postagem: post antecipado', e)
        if p.get('agenda_liberada'):
            try:
                import agenda_postagem as a2
                a2.liberar_horario(p['agenda_liberada'], pid)
            except Exception as e:  # noqa: BLE001
                print('postagem: liberar horário', e)


def liberar(pid: str, quem: str = 'site') -> dict:
    """Liberação especial: você decide postar mesmo sem a origem do vídeo registrada.
    Vale só para os bloqueios liberáveis e só para este arquivo; fica registrada no relatório do post."""
    def f(p):
        redes = [r for r, x in p['redes'].items() if x['status'] in ('liberacao', 'erro')]
        itens = sorted({x['item'] for r in redes for x in conferencia(dict(p, liberacao=None), r) if x.get('liberavel')})
        if not itens:
            raise ErroRede('Este post não tem nada que precise de liberação especial.')
        p['liberacao'] = {'itens': itens, 't': agora(), 'quem': str(quem)[:60], 'hash': p.get('hash') or ''}
        for r in redes:
            p['redes'][r].update(status='agendado', erro='', tentativas=0, proxima=0)
            _anotar(p, r, 'liberado', 'Liberação especial dada por você para: ' + ', '.join(itens))
    p = _mudar(pid, f)
    acordar()
    return p


def editar_post(pid: str, d: dict) -> dict:
    """Muda a hora, as redes, o título ou a legenda de um post que ainda não saiu.
    Redes que já postaram ficam como estão; tirar uma rede só vale para as que ainda não foram."""
    def f(p):
        if any(r['status'] == 'postando' for r in p['redes'].values()):
            raise ErroRede('Este post está sendo enviado agora. Espere terminar.')
        if d.get('quando') is not None:
            try:
                q = float(d['quando'])
            except (TypeError, ValueError):
                raise ErroRede('Horário inválido.')
            if q < agora() - 60:
                raise ErroRede('Escolha um horário no futuro (ou use Postar agora).')
            p['quando'] = q
            for r in p['redes'].values():
                if r['status'] in ('agendado', 'erro'):
                    r.update(status='agendado', erro='', tentativas=0, proxima=0)
        if isinstance(d.get('redes'), list):
            novas = [r for r in d['redes'] if r in REDES]
            feitas = [r for r, s in p['redes'].items() if s['status'] == 'postado']
            if not novas and not feitas:
                raise ErroRede('Deixe pelo menos uma rede (ou cancele o post).')
            p['redes'] = {r: s for r, s in p['redes'].items() if r in novas or r in feitas}
            for r in novas:
                p['redes'].setdefault(r, {'status': 'manual' if r == 'kwai' else 'agendado', 'link': '', 'erro': ''})
        if d.get('titulo') is not None:
            p['titulo'] = str(d['titulo'])[:100]
        if d.get('legenda') is not None:
            p['legenda'] = str(d['legenda'])[:5000]
    p = _mudar(pid, f)
    acordar()
    try:                                  # o corte do agente acompanha o novo horário
        import agente
        agente._mudar(lambda e: [x.update(quando=p['quando']) for x in e['cortes'] if x.get('post') == pid])
    except Exception:
        pass
    return p


def marcar_feito(pid: str, rede: str):
    _mudar(pid, lambda p: p['redes'].get(rede, {}).update(status='postado', erro=''))


# ---------------------------------------------------------------- publicação em cada rede
def _texto(p: dict, limite: int) -> str:
    t = (p['legenda'] or p['titulo']).strip()
    return t[:limite]


def postar_youtube(p: dict, arq: Path) -> str:
    tok = _token_google()
    titulo = (p['titulo'] or p['legenda'] or 'Corte').strip()[:100]
    # descrição no formato do Agente 3 termina no "Link original do vídeo [...]": não se acrescenta nada depois
    # (o YouTube reconhece o Short pelo vídeo vertical e curto)
    if '#shorts' not in (titulo + p['legenda']).lower() and not ds.aplicado(p['legenda']):
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
    _capa_youtube(p, arq, vid, tok)
    priv = (j.get('status') or {}).get('privacyStatus')
    link = f'https://youtube.com/shorts/{vid}'
    if p['opcoes'].get('youtube_privacidade', 'public') != 'private' and priv == 'private':
        link += '  (o YouTube deixou privado: projeto do Google ainda não verificado; veja o "?")'
    return link


def _capa(arq: Path) -> dict | None:
    try:
        import thumbnails as th
        return th.capa_para_video(arq)
    except Exception:  # noqa: BLE001 - capa nunca derruba o post
        return None


def _nota_capa(p: dict, rede: str, msg: str):
    try:
        _mudar(p['id'], lambda q: _anotar(q, rede, 'capa', msg))
    except ErroRede:
        pass


def _capa_youtube(p: dict, arq: Path, vid: str, tok: str):
    """Agente 6: manda a capa aprovada PARA ESTE ARQUIVO (thumbnails.set). Se o YouTube recusar, o vídeo continua postado e fica a nota."""
    cap = _capa(arq)
    if not cap or not vid:
        return
    try:
        dados = cap['arquivo'].read_bytes()
        st, _, j = http('POST', URL['google_api'] + '/upload/youtube/v3/thumbnails/set?videoId=' + urllib.parse.quote(vid), dados=dados,
                        cab={'Authorization': 'Bearer ' + tok, 'Content-Type': 'image/jpeg', 'Content-Length': str(len(dados))}, tempo=120)
        if st < 300:
            import thumbnails as th
            th.marcar_rede_ok('youtube')
            _nota_capa(p, 'youtube', 'Capa do Agente 6 enviada.')
        else:
            _nota_capa(p, 'youtube', 'O YouTube não aceitou a capa (o vídeo foi postado): ' + _msg(j)[:200] +
                       (' A conta precisa estar verificada para capa personalizada.' if st == 403 else ''))
    except (OSError, ErroTemporario) as e:
        _nota_capa(p, 'youtube', f'Capa não enviada (o vídeo foi postado): {e}'[:300])


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
    REF['facebook'] = str(vid)
    return f'https://www.facebook.com/reel/{vid}'


def postar_instagram(p: dict, arq: Path) -> str:
    pg = _pagina_meta()
    if not pg.get('ig_id'):
        raise ErroRede('A Página escolhida não tem Instagram profissional ligado. Ligue o Instagram à Página no app do Instagram ou no Facebook.')
    base = f"{URL['graph']}/{GRAPH_V}"
    st, _, j = http('POST', f"{base}/{pg['ig_id']}/media", form={
        'media_type': 'REELS', 'upload_type': 'resumable', 'caption': _texto(p, 2200), 'share_to_feed': 'true', 'access_token': pg['token'],
        **({'thumb_offset': str(cap['tempo_ms'])} if (cap := _capa(arq)) and cap['tempo_ms'] else {})})
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
    REF['instagram'] = str(mid)
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
    caiu_rascunho = False
    if direto:
        st, _, j = http('POST', URL['tiktok_api'] + '/v2/post/publish/creator_info/query/', js={}, cab=cab)
        opcoes = ((j.get('data') or {}).get('privacy_level_options') or ['SELF_ONLY']) if st < 300 else ['SELF_ONLY']
        priv = 'PUBLIC_TO_EVERYONE' if 'PUBLIC_TO_EVERYONE' in opcoes else opcoes[0]
        corpo = {'post_info': {'title': _texto(p, 2200), 'privacy_level': priv}, 'source_info': fonte}
        cap = _capa(arq)
        if cap and cap['tempo_ms']:            # o TikTok só aceita o MOMENTO do vídeo como capa (não a arte)
            corpo['post_info']['video_cover_timestamp_ms'] = cap['tempo_ms']
        rota = '/v2/post/publish/video/init/'
    else:
        corpo = {'source_info': fonte}
        rota = '/v2/post/publish/inbox/video/init/'
    st, _, j = http('POST', URL['tiktok_api'] + rota, js=corpo, cab=cab)
    erro = _erro_dict(j)
    if direto and priv != 'SELF_ONLY' and _falhou(st, erro) and _tiktok_nao_auditado(erro, j):
        # App ainda não aprovado pelo TikTok: só aceita "Só eu" (SELF_ONLY) em conta privada. Tenta assim primeiro.
        priv = 'SELF_ONLY'
        corpo['post_info']['privacy_level'] = priv
        st, _, j = http('POST', URL['tiktok_api'] + rota, js=corpo, cab=cab)
        erro = _erro_dict(j)
    if direto and _falhou(st, erro) and 400 <= st < 500 and _erro_codigo(erro) not in ('access_token_invalid', 'scope_not_authorized', 'spam_risk_user_banned_from_posting'):
        # Postagem direta recusada (app não aprovado, conta pública...): manda como rascunho.
        direto, rota = False, '/v2/post/publish/inbox/video/init/'
        st, _, j = http('POST', URL['tiktok_api'] + rota, js={'source_info': fonte}, cab=cab)
        erro = _erro_dict(j)
        caiu_rascunho = True
    if _falhou(st, erro):
        raise ErroRede(_erro_tiktok(erro, j, st, rota))
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
    _conferir_tiktok(dados.get('publish_id'), cab)
    if direto:
        return 'Enviado ao TikTok' + ('' if priv == 'PUBLIC_TO_EVERYONE' else ' como "Só eu" (app ainda não aprovado pelo TikTok)')
    if caiu_rascunho:
        return ('O app ainda não foi aprovado pelo TikTok e a postagem direta só vale para conta privada: '
                'o vídeo foi para os rascunhos/notificações do TikTok. Abra o app e toque em Postar')
    return 'Está nos rascunhos/notificações do TikTok: abra o app e toque em Postar'


def _erro_dict(j) -> dict:
    """O TikTok às vezes manda o erro como texto ou fora do formato: deixa sempre {'code','message'}."""
    if not isinstance(j, dict):
        return {'code': '', 'message': str(j)[:300]}
    e = j.get('error')
    if isinstance(e, dict):
        return e
    if isinstance(e, str):
        return {'code': e, 'message': j.get('error_description') or j.get('message') or ''}
    if j.get('_texto'):
        return {'code': '', 'message': j['_texto']}
    return {}


def _erro_codigo(erro: dict) -> str:
    return str(erro.get('code') or '')


def _falhou(st: int, erro: dict) -> bool:
    return st >= 300 or _erro_codigo(erro) not in ('', 'ok')


def _tiktok_nao_auditado(erro: dict, j=None) -> bool:
    texto = (str(erro.get('message') or '') + ' ' + json.dumps(j or {}, ensure_ascii=False)[:2000]).lower()
    return _erro_codigo(erro).startswith('unaudited_client') or 'integration guidelines' in texto or 'content-sharing-guidelines' in texto


def _erro_tiktok(erro: dict, j, st: int = 0, rota: str = '') -> str:
    """Traduz os erros mais comuns do TikTok para algo que dá para resolver."""
    cod = _erro_codigo(erro)
    msg = erro.get('message') or _msg(j)
    onde = 'rascunho' if 'inbox' in rota else 'postagem direta'
    rastro = f' [HTTP {st}, {onde}, servidor v2]'
    dicas = {
        'unaudited_client_can_only_post_to_private_accounts': 'o app ainda não foi aprovado pelo TikTok. Até a aprovação, a conta precisa estar privada na hora de postar',
        'spam_risk_too_many_posts': 'limite diário de postagens pelo app atingido. Tente amanhã',
        'spam_risk_too_many_pending_share': 'já há 5 vídeos esperando nos rascunhos do TikTok nas últimas 24 h. Publique ou apague os rascunhos no app e tente de novo',
        'spam_risk_user_banned_from_posting': 'esta conta está impedida de postar pelo TikTok no momento',
        'reached_active_user_cap': 'o app atingiu o limite diário de contas que podem postar',
        'scope_not_authorized': 'a permissão de envio de vídeo não foi concedida. Desconecte e entre de novo, aceitando todas as permissões',
        'access_token_invalid': 'o login do TikTok expirou. Desconecte e entre de novo',
        'privacy_level_option_mismatch': 'a privacidade escolhida não está disponível para esta conta',
        'url_ownership_unverified': 'o endereço do vídeo não foi verificado no TikTok',
    }
    if cod in dicas:
        return f'TikTok recusou ({cod}): {dicas[cod]}.' + rastro
    if _tiktok_nao_auditado(erro, j):
        return ('TikTok recusou: o app ainda não foi aprovado pelo TikTok e ele barrou o envio. Confira: conta do TikTok privada, '
                'a mesma conta que está em "Usuários de teste" do Sandbox, e as chaves do Sandbox no EstúdioClip. Detalhe: ' + msg + rastro)
    return 'TikTok recusou' + (f' ({cod})' if cod else '') + ': ' + msg + rastro


def _conferir_tiktok(publish_id, cab):
    """Depois do envio, pergunta ao TikTok se ele aceitou o vídeo (ele recusa formato ou duração depois de receber)."""
    if not publish_id:
        return
    for _ in range(int(os.getenv('CONFERE_TIKTOK', '24'))):
        try:
            st, _, j = http('POST', URL['tiktok_api'] + '/v2/post/publish/status/fetch/', js={'publish_id': publish_id}, cab=cab, tempo=30)
        except ErroRede:
            return
        if st >= 300:
            return
        d = j.get('data') or {}
        estado = d.get('status')
        if estado == 'FAILED':
            raise ErroRede('O TikTok recebeu mas recusou o vídeo: ' + str(d.get('fail_reason') or 'motivo não informado'))
        if estado in ('PUBLISH_COMPLETE', 'SEND_TO_USER_INBOX') or not estado:
            return
        time.sleep(float(os.getenv('ESPERA_TIKTOK', '5')))


REF: dict = {}      # identificação do post em cada rede, usada depois para ler os números
PUBLICAR = {'youtube': postar_youtube, 'facebook': postar_facebook, 'instagram': postar_instagram, 'tiktok': postar_tiktok}


# ---------------------------------------------------------------- relógio
_acordar = threading.Event()


def acordar():
    _acordar.set()


PROV = {'youtube': 'google', 'facebook': 'meta', 'instagram': 'meta', 'tiktok': 'tiktok'}
# duração máxima que cada rede aceita para o formato curto (segundos), conferida antes de enviar
MAX_SEG = {'youtube': 180, 'facebook': 90, 'instagram': 900, 'tiktok': 600}


def _anotar(p: dict, rede: str, evento: str, detalhe: str = ''):
    """Relatório da publicação: o que aconteceu em cada rede, em ordem (fica no próprio post)."""
    p.setdefault('relatorio', []).append({'t': agora(), 'rede': rede, 'evento': evento, 'detalhe': detalhe[:300]})
    p['relatorio'] = p['relatorio'][-40:]


DONOS = ('meu', 'autorizado', 'regra')       # de quem é o vídeo (mesma lista do Agente 1)
LIBERAVEIS = ('direitos',)                  # bloqueios que VOCÊ pode liberar (liberação especial); os técnicos continuam barrando


def liberacao_valida(p: dict) -> dict | None:
    """Liberação especial dada por você, presa ao arquivo: se o vídeo mudar, precisa liberar de novo."""
    lib = p.get('liberacao') or {}
    if not lib.get('itens'):
        return None
    if lib.get('hash', '') != (p.get('hash') or ''):
        return None
    return lib


def conferencia(p: dict, rede: str) -> list[dict]:
    """Portões do Agente 2 antes de postar, item por item: {item, ok, bloqueia, detalhe}.
    Bloqueio impede o envio desta rede; aviso só fica no relatório. Não gasta tentativa."""
    out = []

    def item(nome, ok, detalhe, bloqueia=True):
        out.append({'item': nome, 'ok': bool(ok), 'bloqueia': bool(bloqueia and not ok), 'detalhe': detalhe})
    try:
        arq = video_path(p['video'])
    except ErroRede as e:
        item('arquivo', False, str(e))
        return out
    item('arquivo', arq.stat().st_size >= 1000, 'Arquivo do vídeo no servidor.' if arq.stat().st_size >= 1000 else 'O arquivo do vídeo está vazio.')
    try:     # esteira dos 5 agentes: com ela ligada, só sai arquivo com o certificado do diretor PARA ESTE ARQUIVO
        import pipeline as pl
        pp = pl.portao_postagem(arq)
        if pp['ativo']:
            item('certificado', pp['ok'], pp['detalhe'])
    except Exception as e:  # noqa: BLE001  (sem conseguir conferir, não sai)
        item('certificado', False, f'Não consegui conferir a aprovação do diretor: {str(e)[:120]}')
    if rede == 'youtube':    # Agente 6: só exige capa se você ligou "exigir capa no YouTube"
        try:
            import thumbnails as th
            if th.config()['exigir_capa_youtube']:
                item('capa', th.capa_para_video(arq) is not None, 'Capa aprovada para este arquivo.' if th.capa_para_video(arq) else
                     'Falta a capa aprovada para este arquivo (Agente 6). Escolha uma capa em Thumbnails ou desligue "exigir capa".')
        except Exception as e:  # noqa: BLE001
            item('capa', False, f'Não consegui conferir a capa: {str(e)[:120]}')
    try:     # Agente 7: com "exigir liberação do coordenador" ligado, só sai o pacote que você liberou (vídeo + capa pelo hash)
        import coordenador as co
        if co.config()['exigir_liberacao']:
            lib = co.liberado(arq)
            item('liberacao', lib['ok'], 'Pacote liberado no Coordenador (Agente 7).' if lib['ok'] else
                 'Falta liberar o pacote final no Coordenador (Agente 7), ou o vídeo/capa mudou depois da liberação.')
    except Exception as e:  # noqa: BLE001
        item('liberacao', False, f'Não consegui conferir a liberação do coordenador: {str(e)[:120]}')
    ag2 = p.get('agenda') or {}
    if ag2.get('ate') and ag2.get('politica') != 'publish_when_online' and agora() > ag2['ate'] and not p['redes'].get(rede, {}).get('tentativas'):
        item('horario', False, 'O horário da programação diária já passou (servidor estava desligado): não posto atrasado.')
    if p.get('hash'):
        igual = assinatura(p['video']) in ('', p['hash'])
        item('versao', igual, 'É o mesmo arquivo que foi agendado.' if igual else 'O arquivo mudou depois de agendado (não é a versão que você aprovou). Agende de novo.')
    prov = PROV.get(rede)
    if prov:
        c = status_contas()[prov]
        if not c['conectado']:
            item('conta', False, f'A conta do {rede.capitalize()} não está conectada. Entre em Publicações > Contas.')
        elif c['erro']:
            item('conta', False, f'A conta do {rede.capitalize()} precisa de login de novo: {c["erro"][:160]}')
        elif rede == 'instagram' and not any(x.get('instagram') for x in c['paginas'] if x['id'] == c['pagina']):
            item('conta', False, 'A Página escolhida não tem um Instagram profissional ligado.')
        else:
            item('conta', True, f'Conta do {rede.capitalize()} conectada.')
    try:
        import renderizador as rd
        dur = rd.duracao(arq)
    except Exception:  # noqa: BLE001
        dur = 0
    # formato do arquivo (codec): as redes aceitam H.264/H.265 com áudio AAC num MP4/MOV
    try:
        import renderizador as rd
        sd = rd.sonda(arq)
        vs = [x for x in sd.get('streams', []) if x.get('codec_type') == 'video']
        aus = [x for x in sd.get('streams', []) if x.get('codec_type') == 'audio']
        cv, ca = (vs[0].get('codec_name', '') if vs else ''), (aus[0].get('codec_name', '') if aus else '')
        ok_fmt = cv in ('h264', 'hevc') and ca in ('aac', '')
        item('formato', ok_fmt, f'Vídeo {cv or "sem imagem"}{", áudio " + ca if ca else ", sem áudio"}' + ('.' if ok_fmt else
             ': as redes pedem H.264 com áudio AAC. Exporte de novo.'), bool(vs) and not ok_fmt)
    except Exception as e:  # noqa: BLE001  (sem ffprobe não bloqueia: só avisa)
        item('formato', True, f'Não deu para ler o formato do arquivo ({str(e)[:80]}).', False)
    if dur and rede in MAX_SEG:
        item('duracao', dur <= MAX_SEG[rede] + 0.5, f'{dur:.0f} s (o {rede.capitalize()} aceita até {MAX_SEG[rede]} s).')
    # direitos: de quem é o vídeo
    dono = (p.get('direitos') or {}).get('origem', '')
    if p.get('origem', 'manual') in ('agente', 'agente-manual', 'agente3'):
        item('direitos', dono in DONOS, f'Origem registrada: {dono}.' if dono in DONOS else 'Falta registrar de quem é o vídeo (seu, autorizado ou regra pública de cortes).')
    else:
        item('direitos', True, f'Origem registrada: {dono}.' if dono else 'Enviado por você, sem origem registrada (confira se pode postar).', False)
    lib = liberacao_valida(p)
    for x in out:
        if x['item'] in LIBERAVEIS and x['bloqueia']:
            if lib and x['item'] in lib['itens']:
                quando = datetime.fromtimestamp(lib.get('t') or agora()).strftime('%d/%m %H:%M')
                x.update(bloqueia=False, liberado=True, detalhe=x['detalhe'] + f' Liberação especial dada por você em {quando}: vai postar mesmo assim.')
            else:
                x['liberavel'] = True
    if p.get('origem') in ('agente', 'agente-manual'):
        _portao_agente1(p, item)
    if p.get('origem') == 'agente3' and p.get('projeto'):
        _portao_agente3(p, item)
    # créditos das imagens que pedem atribuição (ex.: Wikimedia CC BY) precisam estar no texto do post
    faltam = [cr for cr in p.get('creditos') or [] if cr not in (p.get('legenda') or '') and cr not in (p.get('titulo') or '')]
    if p.get('creditos'):
        item('creditos', not faltam, 'Créditos das imagens na legenda.' if not faltam else 'Falta na legenda o crédito: ' + '; '.join(faltam[:3]))
    # K4: as regras das skills do Agente 2 viram uma lista para VOCÊ conferir (não decidem nada sozinhas e nunca liberam o post)
    try:
        from skills import roteador
        from skills import catalogo as skcat
        sel = roteador.selecionar('agente2.publicar')
        regras = []
        for sid in sel['usar']:
            _d, rg = skcat.regras(sid) or ('', [])
            regras += [f'[{sid}] {x}' for x in rg[:2]]
        if regras:
            item('boas_praticas', True, 'Confira também: ' + ' | '.join(regras[:5]), False)
            bloq = [x['item'] for x in out if x['bloqueia']]
            roteador.concluir(sel['usar'], 'agente2.publicar', artefato=f'post:{p.get("id", "")}:{rede}:{(p.get("hash") or "")[:12]}', origem='agente2',
                              saida=f'conferência de {len(out)} itens: ' + ('liberado' if not bloq else 'bloqueado em ' + ', '.join(bloq[:4])))
        elif not sel['usar']:
            item('boas_praticas', True, 'Sem lista extra de conferência (skills desligadas): ' + (sel.get('fallback') or ''), False)
            roteador._fallback('agente2.publicar', 'agente2', '', '', sel)
    except Exception:  # noqa: BLE001
        pass
    return out


def _portao_agente1(p: dict, item):
    """Corte do Agente 1: confere de novo o canal de origem e a inspeção do corte (algo pode ter mudado desde o agendamento)."""
    try:
        import agente as ag
        c = next((x for x in ag.estado()['cortes'] if x.get('post') == p['id']), None)
        if not c:
            return
        r = ag.conferir(c)
        item('origem_do_corte', not r['bloqueios'], 'Canal de origem e inspeção do corte ok.' if not r['bloqueios'] else ' '.join(r['bloqueios']))
    except Exception as e:  # noqa: BLE001
        item('origem_do_corte', True, f'Não deu para conferir o corte agora: {str(e)[:120]}', False)


def _portao_agente3(p: dict, item):
    """Vídeo do Agente 3: só a versão aprovada, sem falha técnica na conferência de qualidade."""
    try:
        import banco as db
        import projetos as pj
        ap = db.um("SELECT * FROM aprovacoes WHERE projeto=? AND render_sha=? AND decisao='aprovado' ORDER BY criado DESC LIMIT 1", p['projeto'], p.get('render_sha') or '')
        depois = db.um("SELECT id FROM aprovacoes WHERE projeto=? AND render_sha=? AND decisao='rejeitado' AND criado>?", p['projeto'], p.get('render_sha') or '',
                       (ap or {}).get('criado') or 0)
        item('aprovacao', bool(ap) and not depois, 'Versão aprovada por você.' if ap and not depois else 'Esta versão do vídeo não está aprovada (ou foi rejeitada depois).')
        import aprovacoes as apv
        dr = apv.diretor_ok(pj.obter(p['projeto']), p.get('render_sha') or '')
        item('diretor', dr['aprovado'], 'Aprovado pelo diretor de qualidade.' if dr['aprovado'] else
             'O diretor de qualidade não aprovou este vídeo: ' + ' '.join(dr['motivos'])[:300])
        q = (pj.obter(p['projeto'])['dados'].get('qualidade') or {}).get('status', '')
        ok_q = q not in ('', 'falha_tecnica')      # sem conferência técnica registrada também não sai
        item('qualidade', ok_q, 'Conferência de qualidade sem falha técnica.' if ok_q else
             ('A conferência de qualidade achou falha técnica neste vídeo.' if q else 'Este vídeo ainda não passou pela conferência técnica.'))
    except Exception as e:  # noqa: BLE001  (projeto apagado etc.)
        item('aprovacao', False, f'Não achei a aprovação deste vídeo: {str(e)[:120]}')


def preflight(p: dict, rede: str) -> list:
    """Conferência antes de postar. Devolve os bloqueios (vazio = pode postar)."""
    return [x['detalhe'] for x in conferencia(p, rede) if x['bloqueia']]


def _publicar_um(pid: str, rede: str):
    atual = next((x for x in posts() if x['id'] == pid), None)
    if atual is None:
        return
    conf = conferencia(atual, rede)
    bloqueios = [x['detalhe'] for x in conf if x['bloqueia']]
    if bloqueios and all(x.get('liberavel') for x in conf if x['bloqueia']):
        msg = 'Precisa da sua liberação especial para postar: ' + ' '.join(bloqueios) + ' Toque em "Liberar e postar" se quiser postar mesmo assim.'
        def pedir(q):
            q['redes'][rede].update(status='liberacao', erro=msg[:500])
            _anotar(q, rede, 'pede_liberacao', msg)
        _mudar(pid, pedir)
        return
    if bloqueios:
        msg = 'Conferência antes de postar: ' + ' '.join(bloqueios)
        def barrar(q):
            q['redes'][rede].update(status='erro', erro=msg[:500])
            _anotar(q, rede, 'bloqueado', msg)
        _mudar(pid, barrar)
        _avisar_falha(pid, rede, msg)
        return

    def iniciar(p):
        p['redes'][rede].update(status='postando', erro='', inicio=agora())
        _anotar(p, rede, 'enviando', 'Conferência ok: ' + ', '.join(x['item'] for x in conf if x['ok']) +
                ''.join(f' Aviso: {x["detalhe"]}' for x in conf if not x['ok'] and not x['bloqueia']))
    p = _mudar(pid, iniciar)
    try:
        REF.pop(rede, None)
        link = PUBLICAR[rede](p, video_path(p['video']))
        ref = REF.pop(rede, '')
        def ok(q):
            q['redes'][rede].update(status='postado', link=link, erro='', feito=agora(), ref=ref)
            _anotar(q, rede, 'postado', link)
        _mudar(pid, ok)
    except ErroTemporario as e:
        n = int(p['redes'][rede].get('tentativas', 0))
        if n < len(ESPERAS):
            prox = agora() + ESPERAS[n] * 60
            hora = datetime.fromtimestamp(prox).strftime('%H:%M')
            def de_novo(q):
                q['redes'][rede].update(status='agendado', tentativas=n + 1, proxima=prox,
                                        erro=f'{str(e)[:380]} O servidor tenta de novo sozinho às {hora} (tentativa {n + 2} de {len(ESPERAS) + 1}).')
                _anotar(q, rede, 'tentar_de_novo', str(e))
            _mudar(pid, de_novo)
        else:
            _mudar(pid, lambda q: q['redes'][rede].update(status='erro', erro=(str(e)[:400] + f' Tentei {n + 1} vezes. Toque em Tentar de novo nesta rede.')))
            _avisar_falha(pid, rede, str(e)[:400])
    except Exception as e:  # noqa: BLE001
        msg = str(e) if isinstance(e, ErroRede) else f'Erro inesperado: {e}'
        def falhou(q):
            q['redes'][rede].update(status='erro', erro=msg[:500])
            _anotar(q, rede, 'erro', msg)
        _mudar(pid, falhou)
        _avisar_falha(pid, rede, msg)


_EM_ENVIO: set = set()                  # (post, rede) sendo enviado agora
_TRAVA_REDE: dict = {}                  # uma trava por rede: TikTok travado não segura o YouTube
_TRAVA_ENVIO = threading.Lock()


def _enviar_rede(pid: str, rede: str):
    """Envia um post para UMA rede. Erro aqui fica só nesta rede (as outras seguem normalmente)."""
    with _TRAVA_ENVIO:
        trava = _TRAVA_REDE.setdefault(rede, threading.Lock())
    try:
        with trava:
            _publicar_um(pid, rede)
    except Exception as e:  # noqa: BLE001  (nunca derruba o envio das outras redes)
        msg = f'Erro inesperado ao postar: {str(e)[:300]}'
        try:
            def falhou(q):
                if q['redes'].get(rede, {}).get('status') in ('agendado', 'postando'):
                    q['redes'][rede].update(status='erro', erro=msg)
                    _anotar(q, rede, 'erro', msg)
            _mudar(pid, falhou)
            _avisar_falha(pid, rede, msg)
        except Exception:  # noqa: BLE001
            pass
    finally:
        with _TRAVA_ENVIO:
            _EM_ENVIO.discard((pid, rede))


def ciclo(esperar: bool = True):
    """Publica tudo que já passou do horário. Cada rede vai por conta própria: se uma falhar ou demorar
    (ex.: TikTok), as outras (ex.: YouTube) são postadas do mesmo jeito. esperar=False: não espera os envios acabarem."""
    fios = []
    for p in lista_posts():
        if p['quando'] > agora() or not video_pronto(p['video']):
            continue
        for rede, r in p['redes'].items():
            if r['status'] == 'agendado':
                if agora() < r.get('proxima', 0):
                    continue
                with _TRAVA_ENVIO:
                    if (p['id'], rede) in _EM_ENVIO:
                        continue
                    _EM_ENVIO.add((p['id'], rede))
                t = threading.Thread(target=_enviar_rede, args=(p['id'], rede), daemon=True, name=f'post-{rede}')
                t.start()
                fios.append(t)
            elif r['status'] == 'postando' and agora() - r.get('inicio', 0) > 3600 and (p['id'], rede) not in _EM_ENVIO:
                _mudar(p['id'], lambda q, rede=rede: q['redes'][rede].update(status='erro', erro='O envio foi interrompido (servidor desligou?). Toque em Tentar de novo nesta rede.'))
    if esperar:
        for t in fios:
            t.join()


def _avisar_falha(pid: str, rede: str, msg: str):
    """Avisa na hora que UMA rede falhou, dizendo o que já foi postado nas outras e como tentar de novo só nela."""
    try:
        p = next((x for x in posts() if x['id'] == pid), None)
        if not p:
            return
        nome = rede.capitalize()
        ok = [r.capitalize() for r, x in p['redes'].items() if x['status'] == 'postado']
        outras = [r.capitalize() for r, x in p['redes'].items() if r != rede and x['status'] in ('agendado', 'postando')]
        corpo = (f'Post: {p.get("titulo") or (p.get("legenda") or "")[:60]}\n\nNão foi para o {nome}: {msg}\n\n'
                 + (f'Já foi postado em: {", ".join(ok)}.\n' if ok else '')
                 + (f'Ainda vai para: {", ".join(outras)} (não depende do {nome}).\n' if outras else '')
                 + f'\nPara tentar de novo só no {nome}: abra Publicações (Posts agendados) e toque em "Tentar de novo no {nome}".\n')
        import agente as ag
        ag.avisar('falha', f'Falhou no {nome}' + (f' (já foi no {", ".join(ok)})' if ok else ''), corpo, zap_tipo='a2_falha')
    except Exception as e:  # noqa: BLE001  (aviso é extra)
        print('postagem: aviso de falha', e)


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
        conferido = 0.0
        while True:
            try:
                # De 6 em 6 horas confere os logins, para o aviso aparecer antes da hora do post.
                if agora() - conferido > float(os.getenv('CONFERE_CONTAS_H', '6')) * 3600:
                    conferido = agora()
                    verificar_contas()
                ciclo(esperar=False)
            except Exception as e:  # noqa: BLE001
                print('agendador:', e)
            _acordar.wait(float(os.getenv('INTERVALO_AGENDA', '30')))
            _acordar.clear()
    threading.Thread(target=laco, daemon=True).start()


def resumo_data(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()
