"""Agente 2: publicação assistida do TikTok.

Cada post guarda as informações para publicar no TikTok (título, descrição, hashtags e links) em `p['tiktok_meta']`
e, quando você mexe à mão, a etapa em `p['tiktok_estado']` ('confirmacao' ou 'publicado').
O status mostrado no site (`estado`) é calculado a partir da rede TikTok do post + essa etapa, então vale para
vídeos novos e antigos sem mexer em nenhum registro existente.

Atualização retroativa (`migrar`): percorre todos os posts, preenche SÓ o que falta (nunca troca o que já existe
ou o que você editou), não renderiza, não gera capa, não envia nada ao TikTok e não apaga registros.
Antes de gravar, guarda uma cópia do arquivo de posts (uma vez).

Direct Post: `modo_envio(p)` decide entre 'direto' e 'assistido'. Enquanto o TikTok não aprovar o app, tudo é assistido
(vídeo nos rascunhos + informações para copiar). Depois da aprovação, basta ligar `direct_post_aprovado` (ver `ligar_direct_post`)
e quem pediu 'direto' passa a postar direto, sem mudar mais nada.
"""
from __future__ import annotations

import re
import shutil
import time

import descricao as ds

VERSAO_META = 1
ESTADOS = ('pendente_envio', 'agendado', 'enviado_tiktok', 'aguardando_publicacao_manual',
           'aguardando_confirmacao', 'publicado', 'falha', 'cancelado')
ROTULOS = {
    'pendente_envio': 'Pendente de envio', 'agendado': 'Agendado', 'enviado_tiktok': 'Enviado ao TikTok',
    'aguardando_publicacao_manual': 'Aguardando publicação manual', 'aguardando_confirmacao': 'Aguardando confirmação',
    'publicado': 'Publicado', 'falha': 'Falha', 'cancelado': 'Cancelado',
}
LIMITE_DESC = 2200
CAMPOS = ('titulo', 'descricao', 'hashtags', 'links')
_RE_TAG = re.compile(r'#[^\W_][\w]*', re.UNICODE)
_RE_URL = re.compile(r'https?://[^\s\[\]<>"]{3,500}')


def _pg():
    import postagem as pg
    return pg


# ---------------------------------------------------------------- status
def estado(p: dict, agora: float | None = None) -> str:
    """Um dos 8 status do TikTok para este vídeo (qualquer post, novo ou antigo)."""
    agora = agora if agora is not None else time.time()
    manual = p.get('tiktok_estado') or ''
    if manual == 'publicado':
        return 'publicado'
    r = (p.get('redes') or {}).get('tiktok')
    if not r:
        return 'aguardando_confirmacao' if manual == 'confirmacao' else 'pendente_envio'
    st = r.get('status')
    if st == 'cancelado':
        return 'cancelado'
    if st == 'erro':
        return 'falha'
    if st == 'agendado':
        q = r.get('quando') or p.get('quando') or 0
        return 'agendado' if q > agora + 60 else 'pendente_envio'
    if st in ('postando', 'liberacao'):
        return 'pendente_envio'
    if st == 'manual':
        return 'aguardando_publicacao_manual'
    if st == 'postado':
        link = str(r.get('link') or '')
        if link.startswith('http'):
            return 'publicado'
        if manual == 'confirmacao':
            return 'aguardando_confirmacao'
        baixo = link.lower()
        if 'rascunho' in baixo or 'notifica' in baixo or 'só eu' in baixo:
            return 'aguardando_publicacao_manual'
        return 'enviado_tiktok'
    return 'pendente_envio'


# ---------------------------------------------------------------- metadados
def _tags_do_texto(texto: str) -> list:
    return ds.hashtags(_RE_TAG.findall(texto or ''))


def _palavras_do_titulo(titulo: str) -> list:
    """Hashtags geradas só quando não existe nenhuma fonte: palavras de verdade do título (nada inventado)."""
    ruins = {'sobre', 'quando', 'porque', 'depois', 'ainda', 'essa', 'esse', 'para', 'como', 'mais'}
    out = []
    for w in re.findall(r'[^\W_]{5,}', ds.titulo_limpo(titulo), flags=re.UNICODE):
        if w.casefold() not in ruins:
            out.append(w)
    return ds.hashtags(out[:4])


def _links_conhecidos(p: dict) -> list:
    """Links que já existem: o do vídeo original (rodapé da descrição ou do corte do agente) e os das redes onde já saiu."""
    achados = []
    leg = str(p.get('legenda') or '')
    m = re.search(r'Link original do vídeo \[([^\]\n]*)\]', leg)
    if m and ds.link_valido(m.group(1)):
        achados.append({'rotulo': 'Vídeo original', 'url': ds.link_valido(m.group(1))})
    try:
        import agente as ag
        for c in (ag.estado().get('cortes') or []):
            if c.get('post') == p.get('id') and ds.link_valido(c.get('origem_url')):
                achados.append({'rotulo': 'Vídeo original', 'url': ds.link_valido(c['origem_url'])})
    except Exception:  # noqa: BLE001  (sem agente carregado: segue só com o que há no post)
        pass
    for rede, r in (p.get('redes') or {}).items():
        u = _RE_URL.search(str((r or {}).get('link') or ''))
        if u and rede != 'tiktok':
            achados.append({'rotulo': {'youtube': 'YouTube Shorts', 'instagram': 'Instagram Reels', 'facebook': 'Facebook Reels'}.get(rede, rede.capitalize()),
                            'url': u.group(0)})
    vistos, out = set(), []
    for a in achados:
        if a['url'] not in vistos:
            vistos.add(a['url'])
            out.append(a)
    return out[:12]


def _meta_vazia() -> dict:
    return {'v': VERSAO_META, 'titulo': '', 'descricao': '', 'hashtags': [], 'links': [], 'origem': {},
            'preparado': time.time(), 'editado': 0, 'copiado': 0, 'aberto': 0, 'avisado': 0}


def completar(p: dict) -> bool:
    """Preenche só o que falta em p['tiktok_meta']. Devolve True se mudou algo. Nunca sobrescreve texto existente."""
    meta = p.get('tiktok_meta')
    novo = not isinstance(meta, dict)
    if novo:
        meta = _meta_vazia()
    mudou = novo
    origem = meta.setdefault('origem', {})

    def pôr(campo, valor, de):
        nonlocal mudou
        meta[campo] = valor
        origem[campo] = de
        mudou = True

    legenda = str(p.get('legenda') or '').strip()
    if not str(meta.get('titulo') or '').strip():
        t = ds.titulo_limpo(p.get('titulo') or '') or ds.titulo_limpo(legenda.split('\n')[0] if legenda else '')
        if t:
            pôr('titulo', t, 'existente' if p.get('titulo') else 'da descrição')
    if not str(meta.get('descricao') or '').strip():
        if legenda:
            pôr('descricao', legenda[:5000], 'existente')
        elif meta.get('titulo'):
            pôr('descricao', ds.compor(meta['titulo'], meta.get('hashtags') or [], ''), 'gerado')
    if not meta.get('hashtags'):
        tags = _tags_do_texto(legenda)
        de = 'existente'
        if not tags:
            tags = _projeto_tags(p)
            de = 'do roteiro'
        if not tags:
            tags = _palavras_do_titulo(meta.get('titulo') or '')
            de = 'gerado'
        if tags:
            pôr('hashtags', tags, de)
    if not meta.get('links'):
        ls = _links_conhecidos(p)
        if ls:
            pôr('links', ls, 'existente')
    if mudou:
        p['tiktok_meta'] = meta
    return mudou


def _projeto_tags(p: dict) -> list:
    if not p.get('projeto'):
        return []
    try:
        import projetos
        d = projetos.obter(p['projeto'])
        return ds.hashtags((((d or {}).get('dados') or d or {}).get('roteiro') or {}).get('hashtags') or [])
    except Exception:  # noqa: BLE001
        return []


def migrar(simular: bool = False) -> dict:
    """Atualização retroativa. Seguro para repetir: só preenche o que falta."""
    pg = _pg()
    resumo = {'posts': 0, 'atualizados': 0, 'ja_prontos': 0, 'campos_gerados': 0, 'simulado': simular}
    with pg.LOCK:
        ps = pg.posts()
        resumo['posts'] = len(ps)
        if simular:
            import copy
            ps = copy.deepcopy(ps)
        antes_gerados = sum(1 for p in ps for v in ((p.get('tiktok_meta') or {}).get('origem') or {}).values() if v == 'gerado')
        mudou_algum = False
        for p in ps:
            if completar(p):
                resumo['atualizados'] += 1
                mudou_algum = True
            else:
                resumo['ja_prontos'] += 1
        resumo['campos_gerados'] = sum(1 for p in ps for v in ((p.get('tiktok_meta') or {}).get('origem') or {}).values() if v == 'gerado') - antes_gerados
        if mudou_algum and not simular:
            bak = pg.ARQ_POSTS.with_name('posts.antes-tiktok.json')
            if pg.ARQ_POSTS.exists() and not bak.exists():
                shutil.copy2(pg.ARQ_POSTS, bak)
            pg.salvar_posts(ps)
    return resumo


# ---------------------------------------------------------------- visão e edição
def visao(p: dict) -> dict:
    """O que o site mostra: status, texto pronto para copiar e o que já foi enviado ao TikTok."""
    meta = p.get('tiktok_meta') or {}
    e = estado(p)
    r = (p.get('redes') or {}).get('tiktok') or {}
    return {'estado': e, 'rotulo': ROTULOS[e], 'meta': {k: meta.get(k, [] if k in ('hashtags', 'links') else '') for k in CAMPOS},
            'origem': meta.get('origem') or {}, 'texto': texto_para_copiar(p), 'ja_enviado': r.get('status') == 'postado', 'pode_reenviar': r.get('status') not in ('postando', 'agendado', 'liberacao'),
            'modo': modo_envio(p), 'editado': meta.get('editado') or 0, 'copiado': meta.get('copiado') or 0}


def texto_para_copiar(p: dict) -> str:
    meta = p.get('tiktok_meta') or {}
    partes = []
    if meta.get('titulo'):
        partes.append(str(meta['titulo']))
    desc = str(meta.get('descricao') or '')
    if desc:
        partes.append(desc)
    faltam = [h for h in meta.get('hashtags') or [] if h.casefold() not in desc.casefold()]
    if faltam:
        partes.append(' '.join(faltam))
    ls = [f"{l['rotulo']}: {l['url']}" if l.get('rotulo') else l['url'] for l in meta.get('links') or []
          if l.get('url') and l['url'] not in desc]
    if ls:
        partes.append('\n'.join(ls))
    return '\n\n'.join(partes)


def texto_do_envio(p: dict, limite: int = LIMITE_DESC) -> str:
    """Texto que vai junto no Direct Post: o que você editou no TikTok (se existir) ou a legenda do post."""
    t = texto_para_copiar(p).strip() if (p.get('tiktok_meta') or {}).get('editado') else ''
    return (t or (p.get('legenda') or p.get('titulo') or '')).strip()[:limite]


def _limpar_links(v) -> list:
    out = []
    for l in v if isinstance(v, list) else []:
        if isinstance(l, str):
            l = {'rotulo': '', 'url': l}
        if isinstance(l, dict) and ds.link_valido(l.get('url')):
            out.append({'rotulo': str(l.get('rotulo') or '')[:40], 'url': ds.link_valido(l['url'])})
    return out[:12]


def editar(pid: str, d: dict) -> dict:
    """Edita título, descrição, hashtags e links do TikTok deste post (qualquer status). Não mexe em vídeo, capa nem nas outras redes."""
    pg = _pg()
    if not any(k in d for k in CAMPOS):
        raise pg.ErroRede('Nada para salvar.')
    desc = d.get('descricao')
    if isinstance(desc, str) and len(desc) > 5000:
        raise pg.ErroRede('A descrição passa de 5000 caracteres.')

    def f(p):
        completar(p)
        meta = p['tiktok_meta']
        if isinstance(d.get('titulo'), str):
            meta['titulo'] = ds.titulo_limpo(d['titulo'])
        if isinstance(desc, str):
            meta['descricao'] = desc.strip()
        if 'hashtags' in d:
            meta['hashtags'] = ds.hashtags(d['hashtags'])
        if 'links' in d:
            meta['links'] = _limpar_links(d['links'])
        for k in CAMPOS:
            if k in d:
                meta.setdefault('origem', {})[k] = 'editado'
        meta['editado'] = time.time()
    p = pg._mudar(pid, f)
    return visao(p)


def registrar(pid: str, acao: str, d: dict | None = None) -> dict:
    """copiado | abrir | confirmar | reabrir. Só anota a etapa; nunca envia nada ao TikTok."""
    pg = _pg()
    d = d or {}
    if acao == 'reenviar':
        return reenviar(pid)
    if acao not in ('copiado', 'abrir', 'confirmar', 'reabrir'):
        raise pg.ErroRede('Ação desconhecida.')

    def f(p):
        completar(p)
        meta = p['tiktok_meta']
        r = (p.get('redes') or {}).get('tiktok')
        if acao == 'copiado':
            meta['copiado'] = time.time()
        elif acao == 'abrir':
            meta['copiado'] = meta['aberto'] = time.time()
            if estado(p) not in ('publicado', 'cancelado', 'falha') and not (r and r.get('status') in ('postando',)):
                p['tiktok_estado'] = 'confirmacao'
                pg._anotar(p, 'tiktok', 'aguardando_confirmacao', 'Informações copiadas e TikTok aberto. Falta você confirmar que publicou.')
        elif acao == 'confirmar':
            if r and r.get('status') == 'postando':
                raise pg.ErroRede('O envio ao TikTok está acontecendo agora. Espere terminar.')
            p['tiktok_estado'] = 'publicado'
            link = ds.link_valido(d.get('link'))
            if r is None:
                p['redes']['tiktok'] = {'status': 'postado', 'link': link or 'Publicado por você no app do TikTok', 'erro': '', 'feito': time.time(), 'manual': True}
            elif r.get('status') != 'postado':
                r.update(status='postado', erro='', link=link or 'Publicado por você no app do TikTok', feito=time.time(), manual=True)
            elif link:
                r['link'] = link
            pg._anotar(p, 'tiktok', 'postado', link or 'Confirmado por você: publicado no app do TikTok')
        elif acao == 'reabrir':
            p.pop('tiktok_estado', None)
    p = pg._mudar(pid, f)
    return visao(p)


def reenviar(pid: str) -> dict:
    """Publicar novamente: manda o MESMO arquivo ao TikTok outra vez (novo rascunho), sem precisar achar o envio antigo.
    O envio anterior fica guardado em `envios_anteriores`; a conferência de sempre vale de novo (arquivo, versão aprovada, conta)."""
    pg = _pg()

    def f(p):
        r = (p.get('redes') or {}).get('tiktok')
        if r and r.get('status') in ('postando', 'agendado', 'liberacao'):
            raise pg.ErroRede('Este vídeo já está na fila do TikTok. Espere o envio terminar ou use "Postar agora".')
        if not pg.video_pronto(p['video']) or not pg.video_path(p['video']).is_file():
            raise pg.ErroRede('O vídeo não está mais no servidor, então não dá para enviar de novo.')
        completar(p)
        if r:
            if r.get('status') in ('postado', 'erro', 'cancelado'):
                r.setdefault('envios_anteriores', []).append({'estado': estado(p), 'link': str(r.get('link') or '')[:300], 'erro': str(r.get('erro') or '')[:300],
                                                              'feito': r.get('feito') or 0, 'em': time.time()})
                r['envios_anteriores'] = r['envios_anteriores'][-10:]
            for k in ('lote', 'lote_pausado', 'intervalo_api_s', 'quando', 'feito', 'manual', 'ref', 'inicio'):
                r.pop(k, None)
            r.update(status='agendado', link='', erro='', tentativas=0, proxima=0, outra_rede=True)
        else:
            p['redes']['tiktok'] = {'status': 'agendado', 'link': '', 'erro': '', 'outra_rede': True}
        p.pop('tiktok_estado', None)
        (p.get('tiktok_meta') or {})['avisado'] = 0
        pg._anotar(p, 'tiktok', 'outra_rede', 'Você pediu para publicar novamente no TikTok (mesmo arquivo).')
    p = pg._mudar(pid, f)
    pg.acordar()
    return visao(p)


# ---------------------------------------------------------------- aviso (vídeo novo)
def notificar_pronto(pid: str):
    """Depois que o vídeo novo chega ao TikTok, avisa que as informações estão prontas para publicar (uma vez só)."""
    pg = _pg()
    aviso = {}

    def f(p):
        completar(p)
        meta = p['tiktok_meta']
        if meta.get('avisado') or estado(p) not in ('aguardando_publicacao_manual', 'enviado_tiktok'):
            return
        meta['avisado'] = time.time()
        aviso['titulo'] = meta.get('titulo') or (p.get('titulo') or 'Vídeo')[:60]
    pg._mudar(pid, f)
    if not aviso:
        return
    try:
        import agente as ag
        ag.avisar('tiktok_pronto', 'TikTok: informações prontas para publicar',
                  f'O vídeo "{aviso["titulo"]}" já está no TikTok.\n\nTítulo, descrição, hashtags e links estão prontos. '
                  'Abra Posts, toque em "TikTok", depois em "Copiar e abrir TikTok" e publique no app.', zap_tipo='a2_tiktok')
    except Exception as e:  # noqa: BLE001  (aviso é extra)
        print('tiktok_assistido: aviso', e)


# ---------------------------------------------------------------- Direct Post (preparado, desligado)
def direct_post_aprovado() -> bool:
    """True só depois que o TikTok aprovar o app e você ligar. Variável TIKTOK_DIRECT_POST_APROVADO=1 ou arquivo de ajuste."""
    import os
    if os.getenv('TIKTOK_DIRECT_POST_APROVADO') == '1':
        return True
    pg = _pg()
    return bool(pg._ler(pg.DADOS / 'tiktok_ajustes.json', {}).get('direct_post_aprovado'))


def ligar_direct_post(ligado: bool = True):
    pg = _pg()
    arq = pg.DADOS / 'tiktok_ajustes.json'
    a = pg._ler(arq, {})
    a['direct_post_aprovado'] = bool(ligado)
    pg._gravar(arq, a)


def modo_envio(p: dict) -> str:
    """'direto' só se você pediu direto E o app já foi aprovado; senão 'assistido' (rascunho + informações para copiar)."""
    pediu = (p.get('opcoes') or {}).get('tiktok_modo') == 'direto'
    return 'direto' if pediu and direct_post_aprovado() else 'assistido'
