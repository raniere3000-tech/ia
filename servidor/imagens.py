"""Busca de fotos para as cenas (Pexels ou Pixabay com chave grátis; sem chave, Wikimedia Commons só com domínio público, CC0 ou CC BY com crédito).

A foto é só matéria-prima: o estilo da cena a remodela (estilos_codigo.estilizar). Só baixa de endereços que a própria
API devolveu e só de domínios conhecidos. O crédito de cada foto fica guardado para aparecer no e-mail do vídeo.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

URL_PEXELS = os.getenv('BASE_PEXELS', 'https://api.pexels.com')
URL_PIXABAY = os.getenv('BASE_PIXABAY', 'https://pixabay.com')
URL_WIKI = os.getenv('BASE_WIKI', 'https://commons.wikimedia.org')
HOSTS_OK = ('images.pexels.com', 'upload.wikimedia.org', 'pixabay.com', 'cdn.pixabay.com')
MAX_BYTES = 12 * 1024 * 1024
LICENCAS_LIVRES = ('public domain', 'cc0', 'pd', 'dominio publico')


class SemFoto(Exception):
    pass


def _get_json(url: str, cab: dict | None = None, tempo: int = 30) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent': 'EstudioClip/2.0', **(cab or {})})
    with urllib.request.urlopen(req, timeout=tempo) as r:
        return json.loads(r.read(4 * 1024 * 1024))


def _host_ok(url: str) -> bool:
    if os.getenv('PERMITIR_QUALQUER_URL') == '1':
        return True
    u = urlparse(url)
    return u.scheme == 'https' and (u.hostname or '') in HOSTS_OK


def baixar(url: str, arq: Path):
    if not _host_ok(url):
        raise SemFoto('Endereço de imagem fora dos domínios permitidos.')
    req = urllib.request.Request(url, headers={'User-Agent': 'EstudioClip/2.0'})
    total = 0
    tmp = Path(str(arq) + '.tmp')
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, 'wb') as f:
        if 'image' not in (r.headers.get('Content-Type') or ''):
            raise SemFoto('O endereço não devolveu uma imagem.')
        while True:
            b = r.read(1 << 16)
            if not b:
                break
            total += len(b)
            if total > MAX_BYTES:
                tmp.unlink(missing_ok=True)
                raise SemFoto('Imagem grande demais.')
            f.write(b)
    tmp.replace(arq)


def _pexels(consulta: str, vertical: bool, chave: str, pular: set) -> list:
    ori = 'portrait' if vertical else 'landscape'
    j = _get_json(f'{URL_PEXELS}/v1/search?query={urllib.parse.quote(consulta)}&orientation={ori}&per_page=12&size=medium', {'Authorization': chave})
    out = []
    for f in j.get('photos') or []:
        src = f.get('src') or {}
        url = src.get('large2x') or src.get('large') or src.get('original')
        if url and str(f.get('id')) not in pular:
            out.append({'id': str(f.get('id')), 'url': url, 'fonte': 'pexels', 'credito': f'Foto de {f.get("photographer") or "autor desconhecido"} no Pexels', 'link': f.get('url') or ''})
    return out


def _pixabay(consulta: str, vertical: bool, chave: str, pular: set) -> list:
    q = urllib.parse.urlencode({'key': chave, 'q': consulta[:100], 'image_type': 'photo', 'orientation': 'vertical' if vertical else 'horizontal',
                                'per_page': 20, 'safesearch': 'true', 'min_width': 800})
    j = _get_json(f'{URL_PIXABAY}/api/?{q}')
    out = []
    for f in j.get('hits') or []:
        url = f.get('largeImageURL') or f.get('webformatURL')
        if url and str(f.get('id')) not in pular:
            out.append({'id': 'px' + str(f.get('id')), 'url': url, 'fonte': 'pixabay', 'credito': f'Imagem de {f.get("user") or "autor desconhecido"} no Pixabay',
                        'link': f.get('pageURL') or ''})
    return out


def _wikimedia(consulta: str, pular: set) -> list:
    q = urllib.parse.urlencode({'action': 'query', 'format': 'json', 'generator': 'search', 'gsrsearch': f'filetype:bitmap {consulta}', 'gsrnamespace': 6,
                                'gsrlimit': 20, 'prop': 'imageinfo', 'iiprop': 'url|extmetadata|size|mime', 'iiurlwidth': 1280})
    j = _get_json(f'{URL_WIKI}/w/api.php?{q}')
    out = []
    for pg in (j.get('query') or {}).get('pages', {}).values():
        ii = (pg.get('imageinfo') or [{}])[0]
        meta = ii.get('extmetadata') or {}
        lic = re.sub(r'\s+', ' ', str((meta.get('LicenseShortName') or {}).get('value') or '')).lower()
        livre = any(lic == k or lic.startswith(k) for k in LICENCAS_LIVRES)
        so_credito = re.fullmatch(r'cc[ -]by( \d\.\d)?', lic) is not None      # CC BY: pode usar dando o crédito (que vai no e-mail e na legenda)
        if not (livre or so_credito):
            continue
        if ii.get('mime') not in ('image/jpeg', 'image/png') or (ii.get('width') or 0) < 800:
            continue
        url = ii.get('thumburl') or ii.get('url')
        if url and str(pg.get('pageid')) not in pular:
            autor = re.sub(r'<[^>]+>', '', str((meta.get('Artist') or {}).get('value') or 'autor desconhecido'))[:80]
            out.append({'id': str(pg.get('pageid')), 'url': url, 'fonte': 'wikimedia', 'credito': f'{autor}, Wikimedia Commons ({lic})', 'link': ii.get('descriptionurl') or ''})
    return out


def buscar(consulta: str, formato: str, pasta: Path, chave_pexels: str = '', pular: set | None = None, chave_pixabay: str = '') -> dict:
    """Devolve {arquivo, fonte, credito, link, id}. Levanta SemFoto se nada servir."""
    consulta = re.sub(r'\s+', ' ', consulta or '').strip()[:80]
    if not consulta:
        raise SemFoto('Sem palavras para procurar a foto.')
    pular = pular or set()
    vertical = formato != '16:9'
    candidatos, falhas = [], []
    # ordem: Pexels, Pixabay (as duas com chave grátis), e por fim Wikimedia (sem chave, acha menos)
    fontes = ([lambda: _pexels(consulta, vertical, chave_pexels, pular)] if chave_pexels else []) + \
             ([lambda: _pixabay(consulta, vertical, chave_pixabay, pular)] if chave_pixabay else []) + [lambda: _wikimedia(consulta, pular)]
    for f in fontes:
        try:
            candidatos = f()
        except Exception as e:       # rede fora, chave recusada... tenta a próxima fonte
            falhas.append(str(e)[:120])
            continue
        if candidatos:
            break
    if not candidatos and falhas:
        raise SemFoto('A busca de fotos falhou: ' + '; '.join(falhas))
    pasta.mkdir(parents=True, exist_ok=True)
    for c in candidatos[:4]:
        arq = pasta / f'{c["fonte"]}-{hashlib.sha1(c["id"].encode()).hexdigest()[:12]}.jpg'
        try:
            if not arq.exists():
                baixar(c['url'], arq)
            return {'arquivo': str(arq), **{k: c[k] for k in ('id', 'fonte', 'credito', 'link')}}
        except Exception:
            continue
    raise SemFoto(f'Nenhuma foto servível para "{consulta}".')
