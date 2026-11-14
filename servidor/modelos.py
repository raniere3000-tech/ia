"""Biblioteca de templates (modelos de vídeo) compartilhada entre o site e os agentes.

O site grava aqui os mesmos modelos que usa na edição manual. O Agente de Cortes lê deste
arquivo, sorteia um dos modelos ativos (com pesos) e monta o vídeo com o FFmpeg seguindo os
mesmos campos. Só biblioteca padrão do Python.
"""
from __future__ import annotations

import base64
import random
import re
import time
from pathlib import Path

import postagem as pg

ARQ = pg.DADOS / 'modelos.json'
FORMATOS = {'9:16': (1080, 1920), '1:1': (1080, 1080), '16:9': (1920, 1080)}
LAYOUTS = ('desfoque', 'cheio', 'gameplay-streamer')
EFEITOS = ('nenhum', 'zoom-acao', 'transicao-fade', 'virada-cena')   # os que o servidor também sabe fazer
ESTILOS = ('destaque', 'simples', 'caixa', 'nenhuma')
POS_LOGO = ('top-left', 'top-right', 'bottom-left', 'bottom-right')
QUALIDADES = {'alta': 20, 'media': 23, 'leve': 27}                   # CRF do x264
MAX_MODELOS = 30
MAX_ATIVOS = 3
LOGO_MAX = 2_000_000
PISO = 0.15          # nenhum modelo ativo cai abaixo de 15% de chance: mantém a variedade
PASSO = 0.3          # quanto o aprendizado anda por rodada em direção ao resultado medido
MIN_AMOSTRAS = 2     # vídeos medidos por modelo, em uma rede, antes de mexer no peso
_COR = re.compile(r'#[0-9a-fA-F]{6}')


class ErroModelo(Exception):
    pass


def _regiao(r, padrao):
    try:
        x, y, w, h = (max(0.0, min(1.0, float(r[k]))) for k in ('x', 'y', 'w', 'h'))
        w, h = max(0.05, min(1 - x, w)), max(0.05, min(1 - y, h))
        return {'x': round(x, 4), 'y': round(y, 4), 'w': round(w, 4), 'h': round(h, 4)}
    except (KeyError, TypeError, ValueError):
        return dict(padrao)


def _num(v, padrao, a, b):
    try:
        return max(a, min(b, float(v)))
    except (TypeError, ValueError):
        return padrao


def _cor(v, padrao):
    return v if isinstance(v, str) and _COR.fullmatch(v) else padrao


BASE = {
    'id': '', 'nome': 'Modelo', 'layout': 'desfoque', 'formato': '9:16', 'zoom': 1.0, 'posX': 0.5, 'posY': 0.5,
    'jogo': {'x': 0, 'y': 0, 'w': 1, 'h': 1}, 'camera': {'x': 0.72, 'y': 0.62, 'w': 0.28, 'h': 0.38}, 'divisao': 62,
    'legenda': 'karaoke-amarelo', 'legendaPos': 'baixo', 'efeito': 'nenhum', 'gancho': True, 'ganchoPos': 'topo',
    'tarja': None, 'cor': '#7758ef', 'logo': '', 'logoPos': 'top-right', 'moldura': False, 'credito': '',
    'resolucao': 1080, 'qualidade': 'media',
    'leg': {'estilo': 'destaque', 'cor': '#FFFFFF', 'corDestaque': '#FFE14D', 'maiusculas': True},
}
PADROES = [
    dict(BASE, id='padrao', nome='Fundo desfocado'),
    dict(BASE, id='tela-cheia', nome='Tela cheia', layout='cheio', legenda='impacto-vermelho', efeito='transicao-fade',
         leg={'estilo': 'destaque', 'cor': '#FFFFFF', 'corDestaque': '#FF4D4D', 'maiusculas': True}),
    dict(BASE, id='gameplay-streamer', nome='Gameplay + Streamer', layout='gameplay-streamer', legenda='neon-gamer', legendaPos='meio',
         leg={'estilo': 'destaque', 'cor': '#FFFFFF', 'corDestaque': '#5CE1E6', 'maiusculas': True}),
]


def limpar(m: dict) -> dict:
    """Confere um modelo vindo do site e devolve só o que o sistema entende."""
    if not isinstance(m, dict):
        raise ErroModelo('Modelo inválido.')
    mid = re.sub(r'[^a-zA-Z0-9_-]', '', str(m.get('id', '')))[:40]
    if not mid:
        raise ErroModelo('Modelo sem identificação.')
    tj = m.get('tarja')
    tarja = None
    if isinstance(tj, dict) and (tj.get('topo') or tj.get('base')):
        tarja = {'topo': bool(tj.get('topo')), 'base': bool(tj.get('base')), 'textoTopo': str(tj.get('textoTopo', ''))[:60],
                 'textoBase': str(tj.get('textoBase', ''))[:60], 'cor': _cor(tj.get('cor'), '#111111'),
                 'corTexto': _cor(tj.get('corTexto'), '#FFFFFF'), 'altura': _num(tj.get('altura'), 12, 4, 25)}
    logo = m.get('logo') if isinstance(m.get('logo'), str) else ''
    if logo and (not logo.startswith('data:image/') or len(logo) > LOGO_MAX):
        logo = ''
    lg = m.get('leg') if isinstance(m.get('leg'), dict) else {}
    return {
        'id': mid, 'nome': (str(m.get('nome', '')).strip() or 'Modelo')[:40],
        'layout': m.get('layout') if m.get('layout') in LAYOUTS else 'desfoque',
        'formato': m.get('formato') if m.get('formato') in FORMATOS else '9:16',
        'zoom': round(_num(m.get('zoom'), 1.0, 1.0, 1.6), 2),
        'posX': round(_num(m.get('posX'), 0.5, 0, 1), 3), 'posY': round(_num(m.get('posY'), 0.5, 0, 1), 3),
        'jogo': _regiao(m.get('jogo'), BASE['jogo']), 'camera': _regiao(m.get('camera'), BASE['camera']),
        'divisao': round(_num(m.get('divisao'), 62, 35, 80)),
        'legenda': re.sub(r'[^a-z0-9-]', '', str(m.get('legenda', '')))[:40],
        'legendaPos': 'meio' if m.get('legendaPos') == 'meio' else 'baixo',
        'efeito': str(m.get('efeito', 'nenhum'))[:30] or 'nenhum',
        'gancho': bool(m.get('gancho', True)), 'ganchoPos': 'alto' if m.get('ganchoPos') == 'alto' else 'topo',
        'tarja': tarja, 'cor': _cor(m.get('cor'), '#7758ef'), 'logo': logo,
        'logoPos': m.get('logoPos') if m.get('logoPos') in POS_LOGO else 'top-right',
        'moldura': bool(m.get('moldura')), 'credito': str(m.get('credito', ''))[:40],
        'resolucao': 720 if _num(m.get('resolucao'), 1080, 360, 2160) < 1000 else 1080,
        'qualidade': m.get('qualidade') if m.get('qualidade') in QUALIDADES else 'media',
        'leg': {'estilo': lg.get('estilo') if lg.get('estilo') in ESTILOS else ('nenhuma' if not m.get('legenda') else 'destaque'),
                'cor': _cor(lg.get('cor'), '#FFFFFF'), 'corDestaque': _cor(lg.get('corDestaque'), '#FFE14D'),
                'maiusculas': bool(lg.get('maiusculas', True))},
    }


def _do_template_antigo(t: dict) -> dict:
    """Quem já usava o agente tinha um único template; ele vira o primeiro modelo da biblioteca."""
    tarja = None
    if t.get('tarja_topo', '').strip() or t.get('tarja_base', '').strip():
        tarja = {'topo': bool(t['tarja_topo'].strip()), 'base': bool(t['tarja_base'].strip()), 'textoTopo': t['tarja_topo'], 'textoBase': t['tarja_base'],
                 'cor': t.get('cor_tarja', '#111111'), 'corTexto': t.get('cor_tarja_texto', '#FFFFFF'), 'altura': 8}
    est = t.get('legenda', 'destaque')
    return limpar(dict(BASE, id='padrao', nome='Fundo desfocado', layout='cheio' if t.get('enquadramento') == 'cortar' else 'desfoque',
                       zoom=t.get('zoom', 1.0), legenda={'destaque': 'karaoke-amarelo', 'simples': 'classico-contorno', 'caixa': 'legenda-caixa'}.get(est, ''),
                       legendaPos=t.get('legenda_pos', 'baixo'), gancho=t.get('gancho', True), ganchoPos=t.get('gancho_pos', 'topo'), tarja=tarja,
                       resolucao=t.get('qualidade', 1080),
                       leg={'estilo': est, 'cor': t.get('cor', '#FFFFFF'), 'corDestaque': t.get('cor_destaque', '#FFE14D'), 'maiusculas': t.get('maiusculas', True)}))


def biblioteca(antigo: dict | None = None) -> dict:
    """Lê a biblioteca. Na primeira vez cria os três modelos de partida."""
    with pg.LOCK:
        d = pg._ler(ARQ, None)
        if isinstance(d, dict) and isinstance(d.get('modelos'), list) and d['modelos']:
            return d
        ms = [limpar(m) for m in PADROES]
        if antigo:
            ms[0] = _do_template_antigo(antigo)
        d = {'atualizado': 0, 'modelos': ms}
        pg._gravar(ARQ, d)
        return d


def salvar(d: dict) -> dict:
    if not isinstance(d, dict) or not isinstance(d.get('modelos'), list):
        raise ErroModelo('Envie a lista de modelos.')
    ms, vistos = [], set()
    for m in d['modelos'][:MAX_MODELOS]:
        m = limpar(m)
        if m['id'] not in vistos:
            vistos.add(m['id'])
            ms.append(m)
    if not ms:
        raise ErroModelo('A biblioteca precisa de pelo menos um modelo.')
    novo = {'atualizado': float(d.get('atualizado') or time.time()), 'modelos': ms}
    with pg.LOCK:
        pg._gravar(ARQ, novo)
    return novo


def por_id(mid: str) -> dict | None:
    return next((m for m in biblioteca()['modelos'] if m['id'] == mid), None)


def resumo() -> list:
    """Para as telas que só precisam saber quais modelos existem."""
    return [{'id': m['id'], 'nome': m['nome'], 'layout': m['layout'], 'formato': m['formato']} for m in biblioteca()['modelos']]


def ativos(ids: list) -> list:
    """Os modelos escolhidos para os agentes (até 3). Sem escolha válida, usa os primeiros da biblioteca."""
    ms = {m['id']: m for m in biblioteca()['modelos']}
    bons = [ms[i] for i in dict.fromkeys(ids) if i in ms][:MAX_ATIVOS]
    return bons or list(ms.values())[:MAX_ATIVOS]


def tpl(m: dict) -> dict:
    """Traduz o modelo para os campos que a montagem com FFmpeg usa."""
    tj = m['tarja'] or {}
    lg = m['leg']
    return {
        'modelo': m['id'], 'formato': m['formato'], 'legenda': lg['estilo'] if m['legenda'] else 'nenhuma', 'cor': lg['cor'],
        'cor_destaque': lg['corDestaque'], 'maiusculas': lg['maiusculas'], 'tamanho': 'medio', 'legenda_pos': m['legendaPos'],
        'enquadramento': {'cheio': 'cortar'}.get(m['layout'], m['layout']), 'zoom': m['zoom'], 'pos_x': m['posX'], 'pos_y': m['posY'],
        'jogo': m['jogo'], 'camera': m['camera'], 'divisao': m['divisao'], 'efeito': m['efeito'] if m['efeito'] in EFEITOS else 'nenhum',
        'gancho': m['gancho'], 'gancho_pos': m['ganchoPos'],
        'tarja_topo_on': bool(tj.get('topo')), 'tarja_base_on': bool(tj.get('base')), 'tarja_topo': tj.get('textoTopo', ''), 'tarja_base': tj.get('textoBase', ''),
        'cor_tarja': tj.get('cor', '#111111'), 'cor_tarja_texto': tj.get('corTexto', '#FFFFFF'), 'tarja_alt': tj.get('altura', 12),
        'cor_marca': m['cor'], 'logo': m['logo'], 'logo_pos': m['logoPos'], 'moldura': m['moldura'], 'credito': m['credito'],
        'qualidade': m['resolucao'], 'crf': QUALIDADES[m['qualidade']],
    }


def gravar_logo(logo: str, destino: Path) -> Path | None:
    """Salva o logo (data URL) em arquivo para o FFmpeg. SVG não é aceito pelo FFmpeg e fica de fora."""
    m = re.match(r'data:image/(png|jpeg|webp);base64,(.+)', logo or '', re.S)
    if not m:
        return None
    try:
        arq = destino.with_suffix('.' + ('jpg' if m.group(1) == 'jpeg' else m.group(1)))
        arq.write_bytes(base64.b64decode(m.group(2)))
        return arq
    except (ValueError, OSError):
        return None


# ---------------------------------------------------------------- pesos e aprendizado
def chances(pesos: dict, ids: list, redes: list) -> dict:
    """Chance de cada modelo ativo no sorteio: média dos pesos nas redes, com piso para manter variedade."""
    if not ids:
        return {}
    igual = 1 / len(ids)
    bruto = {}
    for i in ids:
        vals = [float((pesos.get(r) or {}).get(i, igual)) for r in redes] or [igual]
        bruto[i] = max(0.0, sum(vals) / len(vals))
    return _com_piso(bruto)


def normalizar(bruto: dict) -> dict:
    """Pesos somando 1 (sem o piso: ele só entra na hora do sorteio)."""
    total = sum(max(0.0, v) for v in bruto.values())
    if total <= 0:
        return {i: 1 / len(bruto) for i in bruto}
    return {i: max(0.0, v) / total for i, v in bruto.items()}


def _com_piso(bruto: dict) -> dict:
    n = len(bruto)
    piso = min(PISO, 1 / n)
    total = sum(bruto.values()) or 1
    p = {i: v / total for i, v in bruto.items()}
    livres = 1 - piso * n
    return {i: round(piso + livres * v, 4) for i, v in p.items()}


def sortear(pesos: dict, ids: list, redes: list, rnd: random.Random) -> str:
    ch = chances(pesos, ids, redes)
    return rnd.choices(list(ch), weights=list(ch.values()))[0]


def aprender(pesos: dict, ids: list, medidas: dict) -> tuple[dict, list]:
    """Aproxima os pesos, aos poucos, do resultado medido em cada rede.

    medidas = {rede: {modelo: [visualizações de cada vídeo]}}. Só mexe em uma rede quando todos os
    modelos ativos têm pelo menos MIN_AMOSTRAS vídeos medidos nela, para comparar em condições iguais.
    """
    novo, notas = {r: dict(v) for r, v in pesos.items()}, []
    for rede, por_modelo in medidas.items():
        if len(ids) < 2 or any(len(por_modelo.get(i, [])) < MIN_AMOSTRAS for i in ids):
            continue
        medias = {i: sum(por_modelo[i]) / len(por_modelo[i]) for i in ids}
        if sum(medias.values()) <= 0:
            continue
        alvo = normalizar(medias)
        atual = normalizar({i: float(novo.get(rede, {}).get(i, 1 / len(ids))) for i in ids})
        novo[rede] = {i: round(atual[i] + PASSO * (alvo[i] - atual[i]), 4) for i in ids}
        notas.append(rede)
    return novo, notas
