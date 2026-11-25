"""Agendador do EstúdioClip: guarda os vídeos e posts no celular/PC e publica nas SUAS contas na hora marcada.

Redes: YouTube (Shorts), Facebook (Reels da Página), Instagram (Reels), TikTok. Kwai não tem API pública:
o post fica como "manual" com o botão de baixar o vídeo.
Só usa a biblioteca padrão do Python (roda no Termux).
"""
from __future__ import annotations

import descricao as ds
import tiktok_assistido as ta
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
from email.utils import parsedate_to_datetime

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
    def __init__(self, mensagem, retry_after=0):
        super().__init__(mensagem)
        self.retry_after = retry_after


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
        j = _json(corpo)
        if e.code == 429 and isinstance(j, dict):
            valor = (e.headers or {}).get('Retry-After', '')
            try:
                espera = float(valor)
            except ValueError:
                try:
                    espera = parsedate_to_datetime(valor).timestamp() - agora()
                except (TypeError, ValueError, OverflowError):
                    espera = 0
            j['_retry_after_s'] = max(0, espera)
        return e.code, dict(e.headers or {}), j
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
        raise ErroTemporario(f'{oque} (erro {st}, a rede está instável ou pediu para esperar): {_msg(j)}',
                            float(j.get('_retry_after_s') or 0) if isinstance(j, dict) else 0)
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
    try:
        import esteira as es
        completa = es.completa()
    except Exception:  # noqa: BLE001
        completa = False
    if completa:             # esteira dos 7 agentes: o Publicador só agenda o pacote liberado pelo Coordenador (vídeo + capa pelo hash)
        falta = es.falta_para_postar(pl.sha_arquivo(video_path(vid)), vid, str(d.get('projeto') or ''))
        if falta:
            raise ErroRede(falta)
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
    ta.completar(p)          # TikTok assistido: título, descrição, hashtags e links já ficam prontos antes do envio
    with LOCK:
        ps = posts()
        ps.append(p)
        salvar_posts(ps)
    return p


_MIGROU_TIKTOK = False


def lista_posts() -> list:
    global _MIGROU_TIKTOK
    if not _MIGROU_TIKTOK:               # atualização retroativa: preenche só o que falta nos posts antigos (1x por execução)
        _MIGROU_TIKTOK = True
        try:
            ta.migrar()
        except Exception as e:  # noqa: BLE001
            print('postagem: migração do TikTok assistido', e)
    ps = sorted(posts(), key=lambda p: p['quando'])
    for p in ps:
        p['tiktok'] = ta.visao(p)
        p['preparando'] = not video_pronto(p['video'])
        try:
            p['arquivo_disponivel'] = video_path(p['video']).is_file()
        except ErroRede:
            p['arquivo_disponivel'] = False
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
                r['quando'] = agora()
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


def liberar(pid: str, quem: str = 'site', rede: str = '') -> dict:
    """Liberação especial: você decide postar mesmo sem a origem do vídeo registrada.
    Vale só para os bloqueios liberáveis e só para este arquivo; fica registrada no relatório do post."""
    def f(p):
        if rede and rede not in p['redes']:
            raise ErroRede('Este post não tem essa rede.')
        redes = [r for r, x in p['redes'].items() if (not rede or r == rede) and x['status'] in ('liberacao', 'erro')]
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


def publicar_em_outras_redes(pid: str, redes: list) -> dict:
    """Acrescenta destinos ao mesmo post e conserva o histórico de cada rede."""
    if not isinstance(redes, list) or not redes or any(not isinstance(r, str) or r not in REDES for r in redes):
        raise ErroRede('Escolha pelo menos uma rede válida.')
    redes = list(dict.fromkeys(redes))

    def adicionar(p):
        if not any(r['status'] == 'postado' for r in p['redes'].values()):
            raise ErroRede('O post ainda não foi publicado em nenhuma rede.')
        novas = [r for r in redes if r not in p['redes']]
        if not novas:
            return
        if not video_pronto(p['video']) or not video_path(p['video']).is_file():
            raise ErroRede('O vídeo ainda precisa estar disponível no servidor.')
        marca = assinatura(p['video'])
        duplicadas = {r for outro in posts() if outro['id'] != pid
                      and (outro.get('video') == p['video'] or (marca and outro.get('hash') == marca))
                      for r in novas if r in outro['redes']}
        if duplicadas:
            raise ErroRede('Uma das redes escolhidas já tem este vídeo em outro post. Confira a aba Posts.')
        for r in novas:
            p['redes'][r] = {'status': 'manual' if r == 'kwai' else 'agendado', 'link': '', 'erro': '', 'outra_rede': True}
            _anotar(p, r, 'outra_rede', 'Destino acrescentado depois da primeira publicação.')

    p = _mudar(pid, adicionar)
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
                    r.update(status='agendado', erro='', tentativas=0, quando=q, proxima=0)
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
    REF['youtube'] = vid or ''
    p['_canal_publicado'] = (j.get('snippet') or {}).get('channelId')
    _capa_youtube(p, arq, vid, tok)
    priv = (j.get('status') or {}).get('privacyStatus')
    link = f'https://youtube.com/shorts/{vid}'
    if p['opcoes'].get('youtube_privacidade', 'public') != 'private' and priv == 'private':
        link += '  (o YouTube deixou privado: projeto do Google ainda não verificado; veja o "?")'
    return link


def contexto_publicacao(p: dict, arq: Path) -> dict:
    """Retrato local antes do envio. Não afirma que a rede aceitou a capa."""
    import pipeline as pl
    import agente as ag
    sha = pl.sha_arquivo(arq)
    corte = next((c for c in ag.estado()['cortes'] if c.get('post') == p['id'] or
                  c.get('video') == p['video']), {})
    capa = _capa(arq) or {}
    import banco as db
    import projetos as pj
    registro = db.um('SELECT * FROM renders WHERE projeto=? AND sha256=? ORDER BY versao DESC LIMIT 1', p.get('projeto') or '', sha) or {}
    roteiro_sha = None
    for v in db.todos('SELECT dados FROM versoes WHERE projeto=? ORDER BY revisao', p.get('projeto') or ''):
        try:
            dados = json.loads(v['dados'])
        except (TypeError, ValueError):
            continue
        if isinstance(dados, dict) and isinstance(dados.get('render'), dict) and dados['render'].get('sha') == sha and pj.roteiro_aprovado(dados):
            roteiro_sha = dados['aprovacao_roteiro']['hash']
            break
    cert = pl.certificado(sha) or {}
    efeitos = None
    try:
        # O arquivo da fila é uma cópia; o recibo IA pode permanecer junto ao render original.
        candidatos = [arq.with_suffix('.efeitos.json')]
        if registro.get('arquivo'):
            candidatos.append(Path(registro['arquivo']).with_suffix('.efeitos.json'))
        for caminho in candidatos:
            try:
                recibo = json.loads(caminho.read_text())
            except (OSError, ValueError):
                continue
            if isinstance(recibo, dict) and recibo.get('arquivo_sha') == sha and recibo.get('status') == 'concluido':
                efeitos = recibo
                break
    except (OSError, ValueError):
        pass
    return {'schema': 1, 'post': p['id'], 'video': p['video'], 'render_sha': sha,
            'projeto': p.get('projeto') or None, 'origem': p.get('origem') or 'manual',
            'vertente': 'criacao_ia' if p.get('origem') == 'agente3' else ('cortes' if corte else 'manual'),
            'corte': corte.get('id'), 'canal': corte.get('perfil') or None,
            'canal_origem': corte.get('canal') or None, 'perfil_versao': corte.get('perfil_versao'),
            'render_versao': registro.get('versao'), 'roteiro_sha': roteiro_sha,
            'criterio_qa': cert.get('versao_politica'),
            'certificado': {k: cert.get(k) for k in ('id', 'sha256', 'nota', 'versao_politica', 'modalidade', 'manual')} if cert else None,
            'titulo': p.get('titulo'), 'legenda': p.get('legenda'),
            'gancho': corte.get('gancho'), 'modelo': p.get('modelo') or corte.get('modelo'),
            'efeitos': efeitos,
            'capa_selecionada': {k: capa.get(k) for k in ('sha', 'formato', 'tempo_ms', 'job', 'variante')} if capa else None,
            'capa_envio': 'consultar_historico_da_rede', 'capturado_em': agora()}


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


CAPA: dict = {}     # estado da capa no envio em andamento, por rede (vai para p['redes'][rede]['capa'] junto com o "postado")
ESPERAS_CAPA = [5, 15, 60, 180, 720]     # minutos entre novas tentativas SÓ da capa (o vídeo não é reenviado)


def _estado_capa(estado: str, cap: dict | None, estrategia: str, detalhe: str = '', **extra) -> dict:
    """Estados: aplicada (a rede confirmou), indicada (a rede aceitou o tempo do quadro da capa), falhou (tenta de novo sozinho),
    bloqueada (a rede recusou de vez: ex. conta sem verificação), manual (você aplica no app), sem_capa (sem capa escolhida)."""
    return {'estado': estado, 'estrategia': estrategia, 'sha': (cap or {}).get('sha', ''), 'variante': (cap or {}).get('variante', ''),
            'job': (cap or {}).get('job', ''), 'tempo_ms': (cap or {}).get('tempo_ms', 0), 'detalhe': detalhe[:300], 't': agora(), **extra}


def _enviar_capa_youtube(vid: str, cap: dict, tok: str) -> tuple[int, dict]:
    dados = cap['arquivo'].read_bytes()
    return http('POST', URL['google_api'] + '/upload/youtube/v3/thumbnails/set?videoId=' + urllib.parse.quote(vid), dados=dados,
                cab={'Authorization': 'Bearer ' + tok, 'Content-Type': 'image/jpeg', 'Content-Length': str(len(dados))}, tempo=120)[::2]


def _capa_youtube(p: dict, arq: Path, vid: str, tok: str):
    """Agente 6: manda a capa aprovada PARA ESTE ARQUIVO (thumbnails.set). Se o YouTube recusar, o vídeo continua postado,
    a capa fica como "falhou" (com o ID do vídeo) e o servidor tenta de novo SÓ a capa depois — sem postar de novo."""
    cap = _capa(arq)
    if not cap or not vid:
        CAPA['youtube'] = _estado_capa('sem_capa', None, 'imagem', 'Sem capa escolhida para este arquivo.', ref_rede=vid or '', tentativas=0)
        return
    try:
        st, j = _enviar_capa_youtube(vid, cap, tok)
        if st < 300:
            import thumbnails as th
            th.marcar_rede_ok('youtube')
            _nota_capa(p, 'youtube', 'Capa do Agente 6 enviada.')
            CAPA['youtube'] = _estado_capa('aplicada', cap, 'imagem', 'O YouTube confirmou a capa.', ref_rede=vid, tentativas=1)
        else:
            msg = ('O YouTube não aceitou a capa (o vídeo foi postado): ' + _msg(j)[:200] +
                   (' A conta precisa estar verificada para capa personalizada.' if st == 403 else ''))
            _nota_capa(p, 'youtube', msg)
            CAPA['youtube'] = _estado_capa('bloqueada' if st in (401, 403) else 'falhou', cap, 'imagem', msg, ref_rede=vid, tentativas=1,
                                           proxima=agora() + ESPERAS_CAPA[0] * 60)
    except (OSError, ErroTemporario, ErroRede) as e:
        _nota_capa(p, 'youtube', f'Capa não enviada (o vídeo foi postado): {e}'[:300])
        CAPA['youtube'] = _estado_capa('falhou', cap, 'imagem', f'Capa não enviada: {e}', ref_rede=vid, tentativas=1,
                                       proxima=agora() + ESPERAS_CAPA[0] * 60)


def _id_youtube(r: dict) -> str:
    cap = r.get('capa') or {}
    if cap.get('ref_rede'):
        return cap['ref_rede']
    m = re.search(r'(?:shorts/|watch\?v=|youtu\.be/)([\w-]{6,20})', r.get('link') or '')
    return m.group(1) if m else ''


def reenviar_capa(pid: str, rede: str = 'youtube', quem: str = 'agente2', forcar: bool = False) -> dict:
    """Manda de novo SÓ a capa de um vídeo JÁ postado (YouTube: thumbnails.set com o ID que já existe). Nunca reenvia o vídeo.
    forcar=True é o botão "reenviar capa" (você pediu): ignora a espera e o limite automático."""
    import thumbnails as th
    if rede != 'youtube':
        raise ErroRede('Só o YouTube aceita trocar a capa depois de postado pela integração. Nas outras redes, troque no app.')
    p = next((x for x in posts() if x['id'] == pid), None)
    if not p or rede not in p['redes']:
        raise ErroRede('Post não encontrado.')
    r = p['redes'][rede]
    if r.get('status') != 'postado':
        raise ErroRede('O vídeo ainda não foi postado nesta rede: a capa vai junto no envio.')
    vid = _id_youtube(r)
    if not vid:
        raise ErroRede('Não achei o ID do vídeo no YouTube para trocar a capa.')
    ant = r.get('capa') or {}
    if ant.get('estado') == 'aplicada' and not forcar:
        return ant
    n = int(ant.get('tentativas') or 0)
    if not forcar and n >= th.config()['max_envios_capa']:
        return ant
    try:
        arq = video_path(p['video'])
    except ErroRede as e:
        raise ErroRede(f'O arquivo do vídeo não está mais no servidor: {e}')
    cap = _capa(arq)
    if not cap:
        novo = _estado_capa('sem_capa', None, 'imagem', 'Sem capa escolhida e válida para este arquivo.', ref_rede=vid, tentativas=n)
    else:
        try:
            st, j = _enviar_capa_youtube(vid, cap, _token_google())
            if st < 300:
                th.marcar_rede_ok('youtube')
                novo = _estado_capa('aplicada', cap, 'imagem', 'O YouTube confirmou a capa (só a capa foi reenviada).', ref_rede=vid, tentativas=n + 1)
            else:
                fim = st in (401, 403) or n + 1 >= th.config()['max_envios_capa']
                novo = _estado_capa('bloqueada' if st in (401, 403) else 'falhou', cap, 'imagem', 'O YouTube não aceitou a capa: ' + _msg(j)[:200],
                                    ref_rede=vid, tentativas=n + 1, **({} if fim else {'proxima': agora() + ESPERAS_CAPA[min(n + 1, len(ESPERAS_CAPA) - 1)] * 60}))
        except (OSError, ErroTemporario, ErroRede) as e:
            novo = _estado_capa('falhou', cap, 'imagem', f'Capa não enviada: {e}', ref_rede=vid, tentativas=n + 1,
                                proxima=agora() + ESPERAS_CAPA[min(n + 1, len(ESPERAS_CAPA) - 1)] * 60)
    def gravar(q):
        q['redes'][rede]['capa'] = novo
        _anotar(q, rede, 'capa', f'{novo["estado"]}: {novo["detalhe"]}')
    _mudar(pid, gravar)
    th.registrar_aplicacao(pid, rede, novo, quem)
    return novo


def reenviar_capas_pendentes(limite: int = 5) -> list:
    """Passada automática: capas do YouTube que falharam depois do vídeo postado (sem repetir o post)."""
    import thumbnails as th
    if not th.config()['reenviar_capa']:
        return []
    feitos = []
    for p in posts():
        r = p['redes'].get('youtube') or {}
        c = r.get('capa') or {}
        if r.get('status') == 'postado' and c.get('estado') == 'falhou' and c.get('proxima') and c['proxima'] <= agora():
            try:
                feitos.append((p['id'], reenviar_capa(p['id'], 'youtube', 'agente2-reenvio')['estado']))
            except (ErroRede, ErroTemporario) as e:
                print('postagem: reenvio da capa', p['id'], e)
            if len(feitos) >= limite:
                break
    return feitos


def _versao_com_capa(arq: Path, rede: str) -> tuple[Path, dict | None, dict | None]:
    """TikTok/Instagram: a rede só aceita um MOMENTO do vídeo como capa. Com a estratégia "quadro", vai a versão de publicação
    com a arte escolhida no quadro final (presa à mesma escolha). Sem isso, usa o quadro original de onde a capa saiu."""
    try:
        import thumbnails as th
        estr = th.config()['estrategia_rede'].get(rede, 'quadro')
        cap = th.capa_para_video(arq)
        if not cap:
            return arq, None, _estado_capa('sem_capa', None, estr, 'Sem capa escolhida para este arquivo.')
        if estr == 'quadro':
            e = th.video_com_capa(arq)
            if e:
                return e['arquivo'], dict(cap, tempo_ms=e['tempo_ms']), None
            return arq, cap, None
        return arq, cap if estr != 'nenhuma' else None, None
    except Exception as e:  # noqa: BLE001 - capa nunca derruba o post
        print('postagem: versão com capa', e)
        return arq, None, None


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
    p['_canal_publicado'] = pg['id']
    return f'https://www.facebook.com/reel/{vid}'


def postar_instagram(p: dict, arq: Path) -> str:
    pg = _pagina_meta()
    if not pg.get('ig_id'):
        raise ErroRede('A Página escolhida não tem Instagram profissional ligado. Ligue o Instagram à Página no app do Instagram ou no Facebook.')
    base = f"{URL['graph']}/{GRAPH_V}"
    arq, cap, sem = _versao_com_capa(arq, 'instagram')
    st, _, j = http('POST', f"{base}/{pg['ig_id']}/media", form={
        'media_type': 'REELS', 'upload_type': 'resumable', 'caption': _texto(p, 2200), 'share_to_feed': 'true', 'access_token': pg['token'],
        **({'thumb_offset': str(cap['tempo_ms'])} if cap and cap['tempo_ms'] else {})})
    _ok(st, j, 'Instagram recusou o Reels')
    # o Instagram aceitou o pedido COM o tempo da capa: fica "indicada" (a rede não devolve a capa para conferir)
    CAPA['instagram'] = sem or (_estado_capa('indicada', cap, 'quadro', f'O Instagram aceitou o quadro da capa em {cap["tempo_ms"]} ms.')
                                if cap and cap['tempo_ms'] else _estado_capa('manual', cap, 'quadro', 'Escolha a capa no app do Instagram.'))
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
    p['_canal_publicado'] = pg['ig_id']
    st, _, j = http('GET', f"{base}/{mid}?fields=permalink&access_token=" + urllib.parse.quote(pg['token']))
    return j.get('permalink') or f"https://www.instagram.com/{pg.get('ig_usuario', '')}"


def postar_tiktok(p: dict, arq: Path) -> str:
    t = _token_tiktok()
    cab = {'Authorization': 'Bearer ' + t['access']}
    arq, cap_pub, sem_capa = _versao_com_capa(arq, 'tiktok')
    tam = arq.stat().st_size
    if tam <= 64 * 1024 * 1024:
        pedaco, n = tam, 1
    else:
        pedaco = 10 * 1024 * 1024
        n = tam // pedaco
    fonte = {'source': 'FILE_UPLOAD', 'video_size': tam, 'chunk_size': pedaco, 'total_chunk_count': n}
    direto = ta.modo_envio(p) == 'direto'     # antes da aprovação do TikTok, tudo é assistido (rascunho)
    caiu_rascunho = False
    if direto:
        st, _, j = http('POST', URL['tiktok_api'] + '/v2/post/publish/creator_info/query/', js={}, cab=cab)
        opcoes = ((j.get('data') or {}).get('privacy_level_options') or ['SELF_ONLY']) if st < 300 else ['SELF_ONLY']
        priv = 'PUBLIC_TO_EVERYONE' if 'PUBLIC_TO_EVERYONE' in opcoes else opcoes[0]
        corpo = {'post_info': {'title': ta.texto_do_envio(p, 2200), 'privacy_level': priv}, 'source_info': fonte}
        cap = cap_pub
        if cap and cap['tempo_ms']:            # o TikTok só aceita o MOMENTO do vídeo como capa: o quadro final com a arte
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
    if sem_capa:
        CAPA['tiktok'] = sem_capa
    elif direto and cap_pub and cap_pub['tempo_ms']:
        CAPA['tiktok'] = _estado_capa('indicada', cap_pub, 'quadro', f'O TikTok aceitou o quadro da capa em {cap_pub["tempo_ms"]} ms.')
    else:       # rascunho (envio assistido): quem escolhe a capa é você, no app
        seg = (cap_pub or {}).get('tempo_ms', 0) / 1000
        CAPA['tiktok'] = _estado_capa('manual', cap_pub, 'quadro', 'No app do TikTok, toque em "Capa" e escolha o ÚLTIMO quadro do vídeo'
                                      + (f' ({seg:.1f} s): é a arte do Agente 6.' if seg else '.'))
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


def versao_aprovada(arq: Path) -> str:
    """O arquivo que está no servidor agora tem aprovação própria? (certificado do diretor ou liberação do Coordenador
    para ESTE arquivo). Devolve o texto da aprovação ou '' se não tem. Arquivo trocado sem aprovação continua barrado."""
    try:
        import pipeline as pl
        sha = pl.sha_arquivo(arq)
        c = pl.certificado(sha)
        if c:
            return f'aprovada pelo diretor (nota {c["nota"]}{", revisão manual" if c.get("manual") else ""})'
        import coordenador as co
        if co.liberado_sha(sha)['ok']:
            return 'liberada por você no Coordenador'
    except Exception as e:  # noqa: BLE001  (sem conseguir conferir, não aceita a troca)
        print('postagem: versão aprovada', e)
    return ''


def arquivo_trocado(vid: str, motivo: str = '') -> int:
    """Um agente trocou o arquivo do vídeo por uma versão nova aprovada: os posts ainda não enviados passam a
    apontar para esta versão (senão a conferência acha que o arquivo "mudou depois de agendado")."""
    nova = assinatura(vid)
    if not nova:
        return 0
    n = 0
    with LOCK:
        ps = posts()
        for p in ps:
            if p.get('video') != vid or not p.get('hash') or p['hash'] == nova:
                continue
            if any(r['status'] in ('postado', 'postando') for r in p['redes'].values()):
                continue
            p['hash'] = nova
            _anotar(p, '', 'versao_nova', 'Arquivo trocado por uma versão nova' + (f' ({motivo})' if motivo else '') + ': o post usa a versão nova.')
            n += 1
        if n:
            salvar_posts(ps)
    return n


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
    try:     # Agente 6: capa escolhida e válida PARA ESTE ARQUIVO (capa de versão antiga do vídeo não vale), em toda rede que exige capa
        import thumbnails as th
        if th.exige_capa(rede):
            cap = th.capa_para_video(arq)
            item('capa', cap is not None, 'Capa aprovada para este arquivo.' if cap else
                 'Falta a capa aprovada para este arquivo (Agente 6). O Agente 6 está fazendo ou escolhendo a capa; '
                 'se demorar, veja Agentes > Agente 6 ou desligue "exigir capa" para esta rede.')
    except Exception as e:  # noqa: BLE001
        item('capa', False, f'Não consegui conferir a capa: {str(e)[:120]}')
    try:     # Agente 7: com "exigir liberação do coordenador" ligado, só sai o pacote que você liberou (vídeo + capa pelo hash)
        import coordenador as co
        if co.exigir_liberacao_efetiva():
            lib = co.liberado(arq)
            item('liberacao', lib['ok'], 'Pacote liberado no Coordenador (Agente 7).' if lib['ok'] else
                 'Falta liberar o pacote final no Coordenador (Agente 7), ou o vídeo/capa mudou depois da liberação.')
    except Exception as e:  # noqa: BLE001
        item('liberacao', False, f'Não consegui conferir a liberação do coordenador: {str(e)[:120]}')
    ag2 = p.get('agenda') or {}
    redes = p.get('redes') if isinstance(p.get('redes'), dict) else {}
    destino = redes.get(rede) if isinstance(redes.get(rede), dict) else {}
    item('destino', bool(destino.get('status')), 'Destino de publicação configurado.' if destino.get('status') else
         'Falta configurar esta rede no post antes de publicar.')
    if not destino.get('outra_rede') and ag2.get('ate') and ag2.get('politica') != 'publish_when_online' and agora() > ag2['ate'] and not destino.get('tentativas'):
        item('horario', False, 'O horário da programação diária já passou (servidor estava desligado): não posto atrasado.')
    if p.get('hash'):
        atual = assinatura(p['video'])
        if atual in ('', p['hash']):
            item('versao', True, 'É o mesmo arquivo que foi agendado.')
        else:
            aprov = versao_aprovada(arq)
            if aprov:      # o editor/diretor refez o vídeo depois de agendado e o arquivo novo foi aprovado: vale o novo
                item('versao', True, f'O vídeo foi refeito depois de agendado e a versão nova foi {aprov}. Vai postar esta versão.')
                out[-1]['nova_versao'] = atual
            else:
                item('versao', False, 'O arquivo mudou depois de agendado e esta versão nova ainda não foi aprovada pelo diretor '
                     'nem liberada no Coordenador. Mande para o editor e o diretor (ou agende de novo).')
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
        if ap and ap.get('origem') == 'site_manual' and not depois:
            import pipeline as pl
            cert = pl.certificado(p['render_sha'])
            if cert and cert['manual'] and cert['ref'] == p['projeto']:
                item('diretor', True, 'Versão liberada manualmente pelo usuário.')
            else:
                item('diretor', False, 'A liberação manual deste arquivo precisa ser renovada.')
        else:
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


def _garantir_link(pid: str) -> str | None:
    """Última conferência antes de enviar: post de um corte leva o link do vídeo original na descrição (crédito ao criador).
    Vale também para posts agendados antes de existir o link e para descrições editadas à mão. Sem link conhecido, não inventa:
    fica anotado no relatório do post."""
    try:
        import agente as ag
        import descricao as ds
        p = next((x for x in posts() if x['id'] == pid), None)
        if not p or str(p.get('origem') or '') in ('agente3', 'coordenador'):     # vídeo próprio: não tem vídeo original
            return None
        c = next((x for x in ag.estado()['cortes'] if x.get('post') == pid), None) or \
            next((x for x in ag.estado()['cortes'] if x.get('video') == p['video']), None)
        if not c:
            return None
        link = ag.link_original(c)
        if link and link in (p.get('legenda') or ''):
            return 'ok'

        def f(q):
            if link:
                q['legenda'] = ds.com_link(q.get('legenda') or ds.compor(q.get('titulo') or c.get('titulo') or 'Corte', c.get('hashtags') or []), link)[:5000]
                _anotar(q, '', 'link_original', 'Link do vídeo original colocado na descrição antes de enviar.')
            elif not any(x.get('evento') == 'sem_link' for x in q.get('relatorio') or []):
                _anotar(q, '', 'sem_link', 'Não sei de qual vídeo este corte saiu: a descrição vai sem o link original.')
        _mudar(pid, f)
        return 'colocado' if link else 'sem_link'
    except Exception as e:  # noqa: BLE001  (nunca atrapalha o envio)
        print('postagem: link original', e)
        return None


def horario_rede(p: dict, r: dict) -> float:
    return float(r.get('quando', p['quando']))


def _proxima_rede(rede: str) -> float:
    with LOCK:
        return float(_ler(DADOS / 'ritmo_posts.json', {}).get(rede) or 0)


def _adiar_rede(rede: str, segundos: float):
    if segundos <= 0:
        return
    with LOCK:
        ritmo = _ler(DADOS / 'ritmo_posts.json', {})
        ritmo[rede] = max(float(ritmo.get(rede) or 0), agora() + segundos)
        _gravar(DADOS / 'ritmo_posts.json', ritmo)


def _destino_pronto(p: dict, rede: str) -> bool:
    redes = p.get('redes') if isinstance(p.get('redes'), dict) else {}
    r = redes.get(rede) if isinstance(redes.get(rede), dict) else {}
    return (r.get('status') == 'agendado' and not r.get('lote_pausado')
            and (r.get('outra_rede') and 'quando' not in r or horario_rede(p, r) <= agora())
            and float(r.get('proxima') or 0) <= agora() and _proxima_rede(rede) <= agora())


def _publicar_um(pid: str, rede: str):
    _garantir_link(pid)
    atual = next((x for x in posts() if x['id'] == pid), None)
    if not atual or not _destino_pronto(atual, rede):
        return
    conf = conferencia(atual, rede)
    bloqueios = [x['detalhe'] for x in conf if x['bloqueia']]
    if bloqueios and all(x.get('liberavel') for x in conf if x['bloqueia']):
        msg = 'Precisa da sua liberação especial para postar: ' + ' '.join(bloqueios) + ' Toque em "Liberar e postar" se quiser postar mesmo assim.'
        def pedir(q):
            if not _destino_pronto(q, rede):
                return
            q['redes'][rede].update(status='liberacao', erro=msg[:500])
            _anotar(q, rede, 'pede_liberacao', msg)
        _mudar(pid, pedir)
        return
    so_esteira = bloqueios and all(x['item'] in ('certificado', 'capa', 'liberacao') for x in conf if x['bloqueia'])
    if so_esteira and agora() - float(atual['redes'][rede].get('esperando_esteira') or agora()) < 24 * 3600:
        # falta só etapa da esteira (diretor, capa ou liberação): o post espera e tenta de novo; só vira erro depois de 24 h
        msg = 'Esperando a esteira dos 7 agentes: ' + ' '.join(bloqueios)
        def esperar(q):
            if not _destino_pronto(q, rede):
                return
            r = q['redes'][rede]
            if not r.get('esperando_esteira'):
                _anotar(q, rede, 'esperando_esteira', msg)
            r.update(status='agendado', erro=msg[:500], proxima=agora() + 600, esperando_esteira=r.get('esperando_esteira') or agora())
        _mudar(pid, esperar)
        return
    if bloqueios:
        msg = 'Conferência antes de postar: ' + ' '.join(bloqueios)
        def barrar(q):
            if not _destino_pronto(q, rede):
                return
            q['redes'][rede].update(status='erro', erro=msg[:500])
            _anotar(q, rede, 'bloqueado', msg)
        _mudar(pid, barrar)
        _avisar_falha(pid, rede, msg)
        return

    nova = next((x.get('nova_versao') for x in conf if x.get('nova_versao')), '')

    iniciou = False
    def iniciar(p):
        nonlocal iniciou
        if not _destino_pronto(p, rede):
            return
        iniciou = True
        p['redes'][rede].update(status='postando', erro='', inicio=agora())
        if nova and p.get('hash') != nova:       # passa a valer a versão nova aprovada (evita postar a mesma de novo depois)
            _anotar(p, rede, 'versao_nova', 'O vídeo foi refeito depois de agendado; a versão nova tem aprovação própria e é a que vai.')
            if p.get('liberacao', {}).get('hash') == p['hash']:
                p['liberacao']['hash'] = nova
            p['hash'] = nova
        _anotar(p, rede, 'enviando', 'Conferência ok: ' + ', '.join(x['item'] for x in conf if x['ok']) +
                ''.join(f' Aviso: {x["detalhe"]}' for x in conf if not x['ok'] and not x['bloqueia']))
    p = _mudar(pid, iniciar)
    if not iniciou:
        return
    try:
        REF.pop(rede, None)
        CAPA.pop(rede, None)
        arq = video_path(p['video'])
        contexto = contexto_publicacao(p, arq) if os.getenv('PUBLICACAO_CONTEXTO', '0') == '1' else None
        p.pop('_canal_publicado', None)
        link = PUBLICAR[rede](p, arq)
        canal_rede = p.pop('_canal_publicado', None)
        if contexto is not None:
            contexto['canal_rede'] = str(canal_rede) if canal_rede else None
            contexto['canal'] = contexto.get('canal') or (rede + ':' + str(canal_rede) if canal_rede else None)
        ref = REF.pop(rede, '')
        capa = CAPA.pop(rede, None) or (_estado_capa('manual', None, 'manual', 'Esta rede não recebe capa pela integração: aplique no app.')
                                        if rede == 'facebook' else None)
        def ok(q):
            feito = agora()
            q['redes'][rede].update(status='postado', link=link, erro='', feito=feito, ref=ref, **({'capa': capa} if capa else {}))
            if contexto is not None:
                q['redes'][rede]['publicacao'] = dict(contexto, rede=rede, ref=ref or None, link=link, publicado_em=feito)
            _anotar(q, rede, 'postado', link)
        _mudar(pid, ok)
        if capa:
            try:
                import thumbnails as th
                th.registrar_aplicacao(pid, rede, capa, 'agente2')
            except Exception as e:  # noqa: BLE001
                print('postagem: registro da capa', e)
        if rede == 'tiktok':
            ta.notificar_pronto(pid)
    except ErroTemporario as e:
        n = int(p['redes'][rede].get('tentativas', 0))
        _adiar_rede(rede, max(0, getattr(e, 'retry_after', 0)))
        if n < len(ESPERAS):
            espera = max(ESPERAS[n] * 60, getattr(e, 'retry_after', 0))
            prox = agora() + espera
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
    finally:
        _adiar_rede(rede, float(p['redes'][rede].get('intervalo_api_s') or 0))


_EM_ENVIO: set = set()                  # (post, rede) sendo enviado agora
_TRAVA_REDE: dict = {}                  # uma trava por rede: TikTok travado não segura o YouTube
_TRAVA_ENVIO = threading.Lock()
_REDES_ATIVAS: set = set()


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


def _enviar_lista(rede: str, ids: list):
    try:
        for pid in ids:
            _enviar_rede(pid, rede)
    finally:
        with _TRAVA_ENVIO:
            _REDES_ATIVAS.discard(rede)
            for pid in ids:
                _EM_ENVIO.discard((pid, rede))


def ciclo(esperar: bool = True):
    """Publica tudo que já passou do horário. Cada rede vai por conta própria: se uma falhar ou demorar
    (ex.: TikTok), as outras (ex.: YouTube) são postadas do mesmo jeito. esperar=False: não espera os envios acabarem."""
    fios, por_rede = [], {}
    try:
        reenviar_capas_pendentes()
    except Exception as e:  # noqa: BLE001  (reenvio de capa nunca segura as postagens)
        print('postagem: reenvio de capas', e)
    for p in lista_posts():
        if not video_pronto(p['video']):
            continue
        for rede, r in p['redes'].items():
            if _destino_pronto(p, rede):
                por_rede.setdefault(rede, []).append((horario_rede(p, r), p['id']))
            elif r['status'] == 'postando' and agora() - r.get('inicio', 0) > 3600 and (p['id'], rede) not in _EM_ENVIO:
                _mudar(p['id'], lambda q, rede=rede: q['redes'][rede].update(status='erro', erro='O envio foi interrompido (servidor desligou?). Toque em Tentar de novo nesta rede.'))
    for rede, itens in por_rede.items():
        with _TRAVA_ENVIO:
            if rede in _REDES_ATIVAS:
                continue
            ids = [pid for _, pid in sorted(itens)]
            _REDES_ATIVAS.add(rede)
            _EM_ENVIO.update((pid, rede) for pid in ids)
        t = threading.Thread(target=_enviar_lista, args=(rede, ids), daemon=True, name=f'post-{rede}')
        t.start()
        fios.append(t)
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
