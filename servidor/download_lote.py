"""Download de vídeos em lote (Publicações): MP4 individuais, ZIP só com vídeos e pacote completo (MP4 + capa + TXT de publicação).

Regras:
- Só lê. Não renderiza, não chama agentes nem redes sociais, não muda status, horário, aprovação ou estoque de nenhum post.
- O cliente só manda IDs de post; o caminho do arquivo sempre vem do registro do servidor (nunca de texto do cliente).
- O ZIP é montado por streaming (ZIP_STORED: MP4 já é comprimido), um preparo por vez, com progresso, cancelamento e limpeza.
- Capa: só a aprovada para a versão FINAL do vídeo (hash). Sem ela, o MP4 e o TXT seguem e o relatório avisa.
"""
from __future__ import annotations

import errno
import json
import re
import secrets
import shutil
import threading
import time
import unicodedata
import zipfile
from pathlib import Path

import banco as db
import postagem as pg

DIR = pg.DADOS / 'downloads'
MAX_ITENS = 300
RESERVA_BYTES = 200 * 1024 * 1024        # folga que sempre sobra no disco do celular
VALIDADE_S = 24 * 3600                   # arquivos prontos ficam 24 h e depois são apagados
LINK_S = 6 * 3600
FORMATOS = ('pacote', 'zip', 'mp4')
REDES_ORDEM = ('youtube', 'tiktok', 'instagram', 'facebook', 'kwai')
NOME_REDE = {'youtube': 'YOUTUBE', 'tiktok': 'TIKTOK', 'instagram': 'INSTAGRAM', 'facebook': 'FACEBOOK', 'kwai': 'KWAI'}
NAO_CONFIG = '[não configurado]'
_PREPARO = threading.Semaphore(1)        # um ZIP por vez: o celular também roda os agentes
_VIVOS: dict = {}                        # id -> {'cancelar': Event}  (jobs sendo preparados NESTE processo)
_TRAVA = threading.Lock()


class ErroDownload(Exception):
    def __init__(self, status: int, msg: str):
        super().__init__(msg)
        self.status, self.msg = status, msg


# ---------------------------------------------------------------- nomes
def limpar_nome(t, n: int = 80) -> str:
    """Nome de arquivo seguro para Android e Windows: sem emoji, sem caracteres proibidos, sem '..', sem barras, tamanho limitado."""
    t = unicodedata.normalize('NFC', str(t or ''))
    saida = []
    for c in t:
        cat = unicodedata.category(c)
        if c in '️︎' or cat in ('So', 'Sk', 'Cs', 'Co', 'Cn'):
            continue                                       # emoji e símbolos: ficam só dentro do TXT
        saida.append(' ' if cat in ('Cc', 'Cf', 'Zs', 'Zl', 'Zp') else c)
    t = ''.join(saida)
    t = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', '', t)
    t = re.sub(r'\.{2,}', '.', t)
    t = re.sub(r'\s+', ' ', t).strip(' .')
    return t[:n].rstrip(' .')


def titulo_do_post(p: dict) -> str:
    t = str(p.get('titulo') or '').strip()
    if not t:
        leg = str(p.get('legenda') or '').strip()
        t = leg.splitlines()[0].strip() if leg else ''
    return t


def nome_base(seq: int, titulo: str, pid: str, usados: set) -> str:
    """'001 - Título - a1b2c3'. O identificador vem do ID real do post; se dois colidirem, usa o ID inteiro."""
    t = limpar_nome(titulo) or f'Video - {pid}'
    for tam in (6, len(pid)):
        base = f'{seq:03d} - {t} - {pid[:tam]}'
        if base not in usados:
            usados.add(base)
            return base
    base = f'{seq:03d} - {t} - {pid}-{secrets.token_hex(2)}'
    usados.add(base)
    return base


# ---------------------------------------------------------------- capa (somente leitura: nunca revoga nada)
def _extensao_real(arq: Path) -> tuple[str, str] | None:
    try:
        with open(arq, 'rb') as f:
            c = f.read(16)
    except OSError:
        return None
    if c[:3] == b'\xff\xd8\xff':
        return '.jpg', 'image/jpeg'
    if c[:8] == b'\x89PNG\r\n\x1a\n':
        return '.png', 'image/png'
    if c[:4] == b'RIFF' and c[8:12] == b'WEBP':
        return '.webp', 'image/webp'
    return None


def capa_do_video(arq: Path, p: dict | None = None) -> dict:
    """{'estado': ok|ausente|desatualizada, 'arquivo', 'ext', 'nota'}. ok = capa aprovada e escolhida para o hash EXATO deste arquivo."""
    try:
        import pipeline as pl
        sha = pl.sha_arquivo(arq)
        sels = db.todos('SELECT * FROM thumbnail_selecoes WHERE video_sha=? AND revogado IS NULL AND aprovado=1 ORDER BY criado DESC', sha) if sha else []
        for s in sels:
            v = db.um('SELECT arquivo FROM thumbnail_variantes WHERE id=?', s['variante'])
            f = Path(v['arquivo']) if v else None
            if not f or not f.is_file():
                continue
            import hashlib
            if hashlib.sha256(f.read_bytes()).hexdigest() != s['thumb_sha']:
                return {'estado': 'desatualizada', 'nota': 'O arquivo da capa mudou depois de aprovado.'}
            tipo = _extensao_real(f)
            if not tipo:
                return {'estado': 'ausente', 'nota': 'O arquivo da capa não é uma imagem reconhecida.'}
            return {'estado': 'ok', 'arquivo': f, 'ext': tipo[0], 'mime': tipo[1], 'nota': ''}
        # há capa para uma versão ANTERIOR deste vídeo? (então está desatualizada, não ausente)
        refs = []
        if p:
            if p.get('projeto'):
                refs.append(('render', p['projeto']))
            try:
                import agente as ag
                refs += [('corte', c['id']) for c in (ag.estado().get('cortes') or []) if c.get('post') == p.get('id')]
            except Exception:  # noqa: BLE001
                pass
        for origem, ref in refs:
            j = db.um("SELECT 1 FROM thumbnail_selecoes s JOIN thumbnail_jobs j ON j.id=s.job WHERE j.origem=? AND j.referencia=? AND s.aprovado=1", origem, ref)
            if j:
                return {'estado': 'desatualizada', 'nota': 'A capa aprovada é de uma versão anterior do vídeo.'}
    except Exception as e:  # noqa: BLE001 - capa nunca impede o download do MP4
        return {'estado': 'ausente', 'nota': f'Não consegui conferir a capa: {str(e)[:100]}'}
    return {'estado': 'ausente', 'nota': 'Sem capa aprovada para a versão final.'}


# ---------------------------------------------------------------- texto de publicação
_RE_TAG = re.compile(r'#\w+', re.UNICODE)
_RE_URL = re.compile(r'https?://[^\s\]\)>"]+')
_RE_LINK_ORIGINAL = re.compile(r'^\s*Link original do vídeo\s*\[[^\]]*\]\s*$', re.IGNORECASE)


def _tags(texto: str) -> list:
    out, vistos = [], set()
    for t in _RE_TAG.findall(texto or ''):
        if t.casefold() not in vistos:
            vistos.add(t.casefold())
            out.append(t)
    return out


def _descricao_sem_repeticao(legenda: str, titulo: str) -> str:
    """Descrição para o campo próprio: tira o que já aparece nos outros campos (título, linha só de hashtags, link original)."""
    linhas = str(legenda or '').replace('\r\n', '\n').split('\n')
    while linhas and not linhas[0].strip():
        linhas.pop(0)
    if linhas and titulo and linhas[0].strip().casefold() == titulo.strip().casefold():
        linhas.pop(0)
    out = []
    for l in linhas:
        if l.strip() and not _RE_TAG.sub('', l).strip(' .·|-'):
            continue                                       # linha só de hashtags
        if _RE_LINK_ORIGINAL.match(l):
            continue
        out.append(l.rstrip())
    return '\n'.join(out).strip()


def _links_rede(p: dict, rede: str, meta_links: list | None = None) -> list:
    achados = []
    for l in meta_links or []:
        if isinstance(l, dict) and l.get('url'):
            achados.append(f"{l['rotulo']}: {l['url']}" if l.get('rotulo') else l['url'])
    leg = str(p.get('legenda') or '')
    m = re.search(r'Link original do vídeo\s*\[([^\]\n]*)\]', leg)
    if m and _RE_URL.search(m.group(1)) and not any(m.group(1).strip() in a for a in achados):
        achados.append('Vídeo original: ' + m.group(1).strip())
    own = str(((p.get('redes') or {}).get(rede) or {}).get('link') or '')
    u = _RE_URL.search(own)
    if u and not any(u.group(0) in a for a in achados):
        achados.append('Publicado: ' + u.group(0))
    return achados


def _bloco_rede(p: dict, rede: str, titulo_post: str) -> str:
    """Um bloco por rede, só com o que existe salvo no EstúdioClip. Nada é inventado nem gerado de novo."""
    L = [f'========== {NOME_REDE[rede]} ==========']
    if rede == 'tiktok':
        meta = p.get('tiktok_meta') or {}
        titulo = str(meta.get('titulo') or '').strip() or titulo_post
        desc = str(meta.get('descricao') or '').strip()
        tags = [str(h) for h in (meta.get('hashtags') or [])]
        links = _links_rede(p, rede, meta.get('links') or [])
        try:
            import tiktok_assistido as ta
            pronto = ta.texto_para_copiar(p).strip()
        except Exception:  # noqa: BLE001
            pronto = ''
    else:
        legenda = str(p.get('legenda') or '').strip()
        titulo = str(p.get('titulo') or '').strip()
        desc = _descricao_sem_repeticao(legenda, titulo)
        tags = _tags(legenda)
        links = _links_rede(p, rede)
        pronto = legenda
    L.append(f'TÍTULO: {titulo or NAO_CONFIG}')
    L.append('DESCRIÇÃO: ' + (desc if desc else NAO_CONFIG))
    L.append('HASHTAGS: ' + (' '.join(tags) if tags else NAO_CONFIG))
    L.append('LINKS: ' + (links[0] if links else NAO_CONFIG))
    L += [f'       {x}' for x in links[1:]]
    if pronto:
        L += ['', 'TEXTO PRONTO PARA COPIAR:', pronto]
    return '\n'.join(L)


def texto_publicacao(p: dict) -> str:
    titulo = titulo_do_post(p)
    cab = [f'VÍDEO: {titulo or "Video - " + p["id"]}', f'ID: {p["id"]}']
    redes = [r for r in REDES_ORDEM if r in (p.get('redes') or {})]
    blocos = [_bloco_rede(p, r, str(p.get('titulo') or '').strip()) for r in redes]
    return '\n'.join(cab) + '\n\n' + '\n\n'.join(blocos) + '\n'


# ---------------------------------------------------------------- itens e jobs
def _arquivo_do_post(p: dict) -> tuple[Path | None, str]:
    """(caminho, motivo). O caminho vem sempre do registro do post."""
    try:
        if not pg.video_pronto(p['video']):
            return None, 'O vídeo ainda está sendo preparado.'
        arq = pg.video_path(p['video'])
        if not arq.is_file() or arq.stat().st_size < 1000:
            return None, 'O arquivo do vídeo está vazio ou incompleto.'
        return arq, ''
    except pg.ErroRede:
        return None, 'O arquivo final não está mais no servidor.'
    except OSError:
        return None, 'Não consegui ler o arquivo do vídeo.'


def montar_itens(ids: list) -> list:
    if not isinstance(ids, list) or not ids or any(not isinstance(x, str) for x in ids):
        raise ErroDownload(400, 'Escolha pelo menos um vídeo.')
    if len(ids) > MAX_ITENS:
        raise ErroDownload(400, f'Escolha no máximo {MAX_ITENS} vídeos por vez.')
    por_id = {p['id']: p for p in pg.posts()}
    vistos, usados, itens = set(), set(), []
    for pid in ids:
        if pid in vistos:
            continue
        vistos.add(pid)
        n = len(itens) + 1
        p = por_id.get(pid) if re.fullmatch(r'\w{1,40}', pid) else None
        if not p:
            itens.append({'n': n, 'post': pid[:40], 'nome': nome_base(n, '', re.sub(r'\W', '', pid)[:10] or 'x', usados), 'titulo': '', 'disponivel': False,
                          'motivo': 'Post não encontrado.', 'capa': '', 'tamanho': 0})
            continue
        arq, motivo = _arquivo_do_post(p)
        itens.append({'n': n, 'post': pid, 'nome': nome_base(n, titulo_do_post(p), pid, usados), 'titulo': titulo_do_post(p), 'disponivel': arq is not None,
                      'motivo': motivo, 'capa': '', 'tamanho': arq.stat().st_size if arq else 0, 'ext_video': arq.suffix.lower() if arq else ''})
    return itens


def _gravar(j: dict):
    db.kv_gravar('download.job.' + j['id'], j)


def _ler(jid: str) -> dict | None:
    return db.kv('download.job.' + jid)


def _indice() -> list:
    return db.kv('download.indice', []) or []


def _agora() -> float:
    return time.time()


def limpar(forcar_todos: bool = False):
    """Apaga arquivos prontos velhos e sobras (.part) de jobs que não estão mais sendo preparados. Nunca toca em vídeo original."""
    DIR.mkdir(parents=True, exist_ok=True)
    ind, novos = _indice(), []
    for jid in ind:
        j = _ler(jid)
        velho = not j or _agora() - float(j.get('criado') or 0) > VALIDADE_S
        if (velho or forcar_todos) and jid not in _VIVOS:
            for f in DIR.glob(jid + '*'):
                try:
                    f.unlink()
                except OSError:
                    pass
            db.executar('DELETE FROM kv WHERE chave=?', 'download.job.' + jid)
        else:
            novos.append(jid)
    db.kv_gravar('download.indice', novos[-30:])
    for f in DIR.glob('*.part'):                           # sobra de um servidor que caiu no meio
        base = f.name.split('.')[0]
        if base not in _VIVOS and _agora() - f.stat().st_mtime > 600:
            try:
                f.unlink()
            except OSError:
                pass


def _link(jid: str, caminho: str) -> str:
    import autenticacao as au
    return au.assinar_url(f'/api/v1/downloads/{jid}/{caminho}', LINK_S)


def _publico(j: dict) -> dict:
    j = dict(j)
    j['itens'] = [dict(i) for i in j['itens']]
    if j['formato'] == 'mp4' and j['estado'] in ('pronto', 'parcial'):
        for i in j['itens']:
            if i['disponivel']:
                i['url'] = _link(j['id'], f'item/{i["n"]}')
    arq = j.get('arquivo')
    if arq and j['estado'] in ('pronto', 'parcial') and (DIR / arq['arquivo']).is_file():
        j['arquivo'] = {'nome': arq['nome'], 'tamanho': arq['tamanho'], 'url': _link(j['id'], 'arquivo')}
    else:
        j['arquivo'] = None
    j.pop('posts', None)
    return j


def obter(jid: str) -> dict:
    if not re.fullmatch(r'[0-9a-f]{12}', jid or ''):
        raise ErroDownload(404, 'Download não encontrado.')
    j = _ler(jid)
    if not j:
        raise ErroDownload(404, 'Download não encontrado (já expirou ou foi cancelado).')
    if j['estado'] == 'preparando' and jid not in _VIVOS:    # o servidor reiniciou no meio do preparo
        j.update(estado='falhou', erro='O servidor reiniciou durante o preparo. Toque em "Tentar novamente".', fim=_agora())
        _gravar(j)
    return _publico(j)


def criar(ids: list, formato: str, quem: str = 'site') -> dict:
    if formato not in FORMATOS:
        raise ErroDownload(400, 'Formato inválido (pacote, zip ou mp4).')
    limpar()
    itens = montar_itens(ids)
    disp = [i for i in itens if i['disponivel']]
    jid = secrets.token_hex(6)
    j = {'id': jid, 'formato': formato, 'estado': 'preparando', 'total': len(itens), 'disponiveis': len(disp), 'preparados': 0, 'bytes_feitos': 0,
         'bytes_total': sum(i['tamanho'] for i in disp), 'itens': itens, 'arquivo': None, 'erro': '', 'falhas': [], 'sem_capa': 0, 'criado': _agora(), 'fim': None,
         'posts': [i['post'] for i in itens], 'por': str(quem)[:60]}
    if not disp:
        j.update(estado='falhou', erro='Nenhum dos vídeos selecionados está disponível no servidor.', fim=_agora())
        _gravar(j)
    elif formato == 'mp4':           # MP4 individual: nada a preparar, cada vídeo é entregue direto do arquivo final
        j.update(estado='pronto' if len(disp) == len(itens) else 'parcial', preparados=len(disp), bytes_feitos=j['bytes_total'], fim=_agora(),
                 falhas=[{'n': i['n'], 'nome': i['nome'], 'motivo': i['motivo']} for i in itens if not i['disponivel']])
        _gravar(j)
    else:
        _gravar(j)
        _VIVOS[jid] = {'cancelar': threading.Event()}
        threading.Thread(target=_preparar, args=(jid,), daemon=True, name='download-' + jid).start()
    db.kv_gravar('download.indice', (_indice() + [jid])[-30:])
    db.evento(str(quem)[:60], 'download_lote_criado', 'download:' + jid, {'formato': formato, 'total': len(itens), 'disponiveis': len(disp)})
    return _publico(j)


def cancelar(jid: str, quem: str = 'site') -> dict:
    j = _ler(jid)
    if not j:
        raise ErroDownload(404, 'Download não encontrado.')
    if j['estado'] != 'preparando':
        raise ErroDownload(409, 'Este download já terminou.')
    v = _VIVOS.get(jid)
    if v:
        v['cancelar'].set()
    else:                                                     # sem fio vivo (servidor reiniciou): só limpa
        j.update(estado='cancelado', fim=_agora())
        _gravar(j)
        for f in DIR.glob(jid + '*'):
            f.unlink(missing_ok=True)
    db.evento(str(quem)[:60], 'download_lote_cancelado', 'download:' + jid)
    return obter(jid)


def tentar_de_novo(jid: str, quem: str = 'site') -> dict:
    j = _ler(jid)
    if not j:
        raise ErroDownload(404, 'Download não encontrado.')
    if j['estado'] == 'preparando':
        raise ErroDownload(409, 'Este download ainda está sendo preparado.')
    novo = criar(j.get('posts') or [], j['formato'], quem)
    if jid not in _VIVOS:
        for f in DIR.glob(jid + '*'):
            f.unlink(missing_ok=True)
        db.executar('DELETE FROM kv WHERE chave=?', 'download.job.' + jid)
        db.kv_gravar('download.indice', [x for x in _indice() if x != jid])
    return novo


# ---------------------------------------------------------------- preparo do ZIP
class _Cancelado(Exception):
    pass


def _espaco_livre(pasta: Path) -> int:
    pasta.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(pasta).free


def _copiar(zf: zipfile.ZipFile, origem: Path, arcname: str, j: dict, ev: threading.Event, tamanho_esperado: int | None = None):
    zi = zipfile.ZipInfo(arcname, time.localtime(origem.stat().st_mtime)[:6])
    zi.compress_type = zipfile.ZIP_STORED
    zi.external_attr = 0o644 << 16
    esperado = tamanho_esperado if tamanho_esperado is not None else origem.stat().st_size
    feito = 0
    ultimo = time.time()
    with open(origem, 'rb') as f, zf.open(zi, 'w', force_zip64=True) as w:
        while True:
            if ev.is_set():
                raise _Cancelado()
            bloco = f.read(1 << 20)
            if not bloco:
                break
            w.write(bloco)
            feito += len(bloco)
            j['bytes_feitos'] += len(bloco)
            if time.time() - ultimo > 1:
                _gravar(j)
                ultimo = time.time()
    if feito != esperado:       # o arquivo mudou durante a leitura: não entrega um MP4 pela metade como se estivesse bom
        raise OSError(f'O arquivo mudou durante a cópia ({feito} de {esperado} bytes).')


def _relatorio(j: dict) -> str:
    L = ['RELATÓRIO DO DOWNLOAD', f'Gerado em {time.strftime("%Y-%m-%d %H:%M")}', '']
    ausentes = [i for i in j['itens'] if not i['disponivel']]
    if ausentes:
        L.append('VÍDEOS QUE NÃO ENTRARAM (indisponíveis):')
        L += [f'  {i["n"]:03d} - {i["titulo"] or i["post"]}: {i["motivo"]}' for i in ausentes]
        L.append('')
    if j['falhas']:
        L.append('FALHAS NA CÓPIA:')
        L += [f'  {f["nome"]}: {f["motivo"]}' for f in j['falhas']]
        L.append('')
    sem = [i for i in j['itens'] if i['disponivel'] and i.get('capa') in ('ausente', 'desatualizada')]
    if sem:
        L.append('VÍDEOS SEM CAPA (o MP4 e o TXT foram incluídos):')
        L += [f'  {i["nome"]}: {"capa desatualizada" if i["capa"] == "desatualizada" else "sem capa aprovada para a versão final"}' for i in sem]
        L.append('')
    return '\n'.join(L).strip() + '\n'


def _preparar(jid: str):
    ev = _VIVOS[jid]['cancelar']
    DIR.mkdir(parents=True, exist_ok=True)
    parte, final = DIR / f'{jid}.zip.part', DIR / f'{jid}.zip'
    j = _ler(jid)
    try:
        with _PREPARO:
            if ev.is_set():
                raise _Cancelado()
            j = _ler(jid)
            falta = j['bytes_total'] + RESERVA_BYTES - _espaco_livre(DIR)
            if falta > 0:
                raise ErroDownload(507, f'Falta espaço no celular: preciso de cerca de {j["bytes_total"] // 1048576} MB livres além da folga e faltam {falta // 1048576} MB. '
                                        'Apague arquivos ou baixe menos vídeos por vez.')
            por_id = {p['id']: p for p in pg.posts()}
            pacote = j['formato'] == 'pacote'
            with zipfile.ZipFile(parte, 'w', zipfile.ZIP_STORED, allowZip64=True) as zf:
                for i in j['itens']:
                    if ev.is_set():
                        raise _Cancelado()
                    if not i['disponivel']:
                        continue
                    p = por_id.get(i['post'])
                    arq, motivo = _arquivo_do_post(p) if p else (None, 'O post foi removido.')
                    if not arq:             # sumiu entre o pedido e o preparo
                        i.update(disponivel=False, motivo=motivo)
                        j['falhas'].append({'n': i['n'], 'nome': i['nome'], 'motivo': motivo})
                        continue
                    pasta = f'{i["nome"]}/' if pacote else ''
                    _copiar(zf, arq, f'{pasta}{i["nome"]}{arq.suffix.lower()}', j, ev)
                    if pacote:
                        cp = capa_do_video(arq, p)
                        i['capa'] = cp['estado']
                        if cp['estado'] == 'ok':
                            _copiar(zf, cp['arquivo'], f'{pasta}{i["nome"]}_CAPA{cp["ext"]}', j, ev)
                        else:
                            j['sem_capa'] += 1
                        zf.writestr(zipfile.ZipInfo(f'{pasta}{i["nome"]}_PUBLICACAO.txt', time.localtime()[:6]), texto_publicacao(p).encode('utf-8'),
                                    compress_type=zipfile.ZIP_DEFLATED)
                    i['preparado'] = True
                    j['preparados'] += 1
                    _gravar(j)
                if any(not i['disponivel'] for i in j['itens']) or j['falhas'] or j['sem_capa']:
                    zf.writestr('RELATORIO.txt', _relatorio(j).encode('utf-8'), compress_type=zipfile.ZIP_DEFLATED)
            if ev.is_set():
                raise _Cancelado()
            if not j['preparados']:
                raise ErroDownload(409, 'Nenhum vídeo pôde ser copiado.')
            parte.replace(final)
            nome = f'EstudioClip_{time.strftime("%Y-%m-%d_%H%M")}{"" if pacote else "_videos"}.zip'
            perdidos = any(not i['disponivel'] for i in j['itens'])
            j.update(estado='parcial' if perdidos else 'pronto', fim=_agora(), arquivo={'nome': nome, 'tamanho': final.stat().st_size, 'arquivo': final.name},
                     disponiveis=sum(1 for i in j['itens'] if i['disponivel']))
            j['falhas'] = j['falhas'] + [{'n': i['n'], 'nome': i['nome'], 'motivo': i['motivo']} for i in j['itens'] if not i['disponivel']
                                          and not any(f['n'] == i['n'] for f in j['falhas'])]
            _gravar(j)
    except _Cancelado:
        parte.unlink(missing_ok=True)
        j = _ler(jid) or j
        j.update(estado='cancelado', fim=_agora())
        _gravar(j)
    except ErroDownload as e:
        parte.unlink(missing_ok=True)
        j = _ler(jid) or j
        j.update(estado='falhou', erro=e.msg, fim=_agora())
        _gravar(j)
    except OSError as e:
        parte.unlink(missing_ok=True)
        j = _ler(jid) or j
        msg = 'Acabou o espaço no celular durante o preparo.' if e.errno == errno.ENOSPC else f'Erro ao preparar o arquivo: {e}'
        j.update(estado='falhou', erro=msg[:300], fim=_agora())
        _gravar(j)
    except Exception as e:  # noqa: BLE001 - o preparo nunca derruba o servidor
        parte.unlink(missing_ok=True)
        j = _ler(jid) or j
        j.update(estado='falhou', erro=f'Erro inesperado ao preparar: {str(e)[:200]}', fim=_agora())
        _gravar(j)
    finally:
        _VIVOS.pop(jid, None)


# ---------------------------------------------------------------- entrega (rotas assinadas)
def arquivo_zip(jid: str) -> tuple[Path, str]:
    j = _ler(jid) if re.fullmatch(r'[0-9a-f]{12}', jid or '') else None
    if not j or j['estado'] not in ('pronto', 'parcial') or not j.get('arquivo'):
        raise ErroDownload(404, 'Este download não está pronto (ou já expirou).')
    f = DIR / j['arquivo']['arquivo']
    if not f.is_file() or f.parent != DIR:
        raise ErroDownload(404, 'O arquivo expirou. Prepare de novo.')
    return f, j['arquivo']['nome']


def arquivo_item(jid: str, n: int) -> tuple[Path, str]:
    j = _ler(jid) if re.fullmatch(r'[0-9a-f]{12}', jid or '') else None
    if not j or j['formato'] != 'mp4' or j['estado'] not in ('pronto', 'parcial'):
        raise ErroDownload(404, 'Download não encontrado.')
    i = next((x for x in j['itens'] if x['n'] == n and x['disponivel']), None)
    if not i:
        raise ErroDownload(404, 'Vídeo não encontrado neste download.')
    p = next((x for x in pg.posts() if x['id'] == i['post']), None)
    arq, motivo = _arquivo_do_post(p) if p else (None, 'O post foi removido.')
    if not arq:
        raise ErroDownload(404, motivo)
    return arq, i['nome'] + arq.suffix.lower()
