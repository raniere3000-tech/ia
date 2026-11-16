"""Motor de personagens 2D articulados (vista de frente), feito para rodar no Termux só com Python e FFmpeg.

Como funciona:
- Cada personagem é desenhado UMA vez em peças (tronco, cabeça, braços, antebraços, coxas, canelas), cada peça com o
  pivô (a junta) no centro da imagem. As peças ficam guardadas por versão do personagem.
- A cena vira expressões de tempo do FFmpeg: cada junta tem um ângulo que muda com o tempo (ações do catálogo com
  entrada e saída suaves), e a posição de cada peça vem da cadeia pai > filho (cinemática direta).
- A boca segue o volume da fala do personagem que está falando (aproximação por volume, sem fonemas).
- A IA só escolhe ações de uma lista fechada, com números dentro de faixas. Nada é executado a partir do texto.

Limites conhecidos (ditos na tela): só vista de frente (sem ¾ e perfil), sem IK, caminhada estilizada.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import wave
from pathlib import Path

import raster

VERSAO_RIG = 2
RIG_ID = 'svg-humano-v1'
K = 6                     # pixels por unidade no desenho interno (personagem ~ 100 unidades de altura)
TIPOS_CABELO = ('curto', 'longo', 'careca', 'coque', 'cacheado')
CORPOS = ('magro', 'medio', 'forte')
ACESSORIOS = ('nenhum', 'oculos', 'bone', 'laco')
EXPRESSOES = ('neutro', 'feliz', 'triste', 'bravo', 'surpreso', 'preocupado')
POSICOES = {'esquerda': 0.27, 'centro': 0.5, 'direita': 0.73}
BOCAS = ('fechada', 'pequena', 'aberta', 'o', 'sorriso', 'triste', 'larga')
ACOES = {
    # tipo: (descrição, duração padrão em s, expressão que força ou '')
    'idle': ('parado, respirando', 0, ''),
    'piscar': ('piscar os olhos', 0.15, ''),
    'olhar': ('virar a cabeça para um lado (alvo: esquerda, direita, cima, baixo)', 1.5, ''),
    'andar': ('andar até um lado (alvo: esquerda, direita, centro)', 2.0, ''),
    'correr': ('correr até um lado (alvo: esquerda, direita, centro)', 1.2, ''),
    'sentar': ('sentar (fica sentado até levantar)', 0, ''),
    'levantar': ('levantar depois de sentar', 0.6, ''),
    'apontar': ('apontar para um lado (alvo: esquerda, direita)', 1.6, ''),
    'acenar': ('acenar com a mão', 1.6, 'feliz'),
    'pegar': ('pegar algo na frente', 1.2, ''),
    'segurar': ('segurar algo na frente do corpo', 2.0, ''),
    'entregar': ('estender o braço entregando algo (alvo: esquerda, direita)', 1.4, ''),
    'reagir': ('reagir surpreso, recuando', 0.9, 'surpreso'),
    'rir': ('rir', 1.5, 'feliz'),
    'assustar': ('levar um susto', 1.0, 'surpreso'),
    'falar': ('gesticular enquanto fala', 0, ''),
}
JUNTAS = ('tronco', 'cabeca', 'braco_e', 'antebraco_e', 'braco_d', 'antebraco_d', 'coxa_e', 'canela_e', 'coxa_d', 'canela_d')
BASE = {'braco_e': 0.12, 'braco_d': -0.12, 'antebraco_e': 0.05, 'antebraco_d': -0.05, 'coxa_e': 0.04, 'coxa_d': -0.04,
        'canela_e': -0.04, 'canela_d': 0.04}
LIMITES = {'tronco': 0.5, 'cabeca': 0.6, 'braco_e': 3.0, 'braco_d': 3.0, 'antebraco_e': 2.4, 'antebraco_d': 2.4,
           'coxa_e': 1.6, 'coxa_d': 1.6, 'canela_e': 1.8, 'canela_d': 1.8}


# ---------------------------------------------------------------- validação (o que a IA ou a pessoa pode mandar)
def _cor(v, pad: str) -> str:
    v = str(v or '').strip()
    return v.lower() if re.fullmatch(r'#[0-9a-fA-F]{6}', v) else pad


def _txt(v, n: int) -> str:
    return re.sub(r'[\x00-\x1f\x7f]', ' ', str(v or '')).strip()[:n]


def _num(v, pad: float, lo: float, hi: float) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return pad
    return pad if math.isnan(x) else max(lo, min(hi, x))


def validar_personagem(d: dict) -> dict:
    d = d if isinstance(d, dict) else {}
    return {
        'nome': _txt(d.get('nome'), 40) or 'Personagem',
        'descricao': _txt(d.get('descricao'), 300),
        'pele': _cor(d.get('pele'), '#e8b98f'), 'cabelo': _cor(d.get('cabelo'), '#3b2a1a'), 'olhos': _cor(d.get('olhos'), '#2b1d0e'),
        'roupa': _cor(d.get('roupa'), '#3a86ff'), 'calca': _cor(d.get('calca'), '#1d3557'), 'sapato': _cor(d.get('sapato'), '#222222'),
        'cabelo_tipo': d.get('cabelo_tipo') if d.get('cabelo_tipo') in TIPOS_CABELO else 'curto',
        'corpo': d.get('corpo') if d.get('corpo') in CORPOS else 'medio',
        'acessorio': d.get('acessorio') if d.get('acessorio') in ACESSORIOS else 'nenhum',
        'altura': _num(d.get('altura'), 1.0, 0.75, 1.15),
        'voz': _txt(d.get('voz'), 20) or 'Puck',
    }


def validar_elenco(lista, ids_validos: set | None = None, dur_max: float = 60.0) -> list:
    """Quem aparece na cena e o que faz. Só ações do catálogo, tempos dentro da cena, no máximo 3 personagens."""
    out = []
    for e in (lista if isinstance(lista, list) else [])[:3]:
        if not isinstance(e, dict):
            continue
        pid = re.sub(r'[^a-z0-9_-]', '', str(e.get('personagem_id') or '').lower())[:40]
        if not pid or (ids_validos is not None and pid not in ids_validos) or any(x['personagem_id'] == pid for x in out):
            continue
        acoes = []
        for a in (e.get('acoes') if isinstance(e.get('acoes'), list) else [])[:12]:
            if not isinstance(a, dict) or a.get('tipo') not in ACOES:
                continue
            acoes.append({'t': round(_num(a.get('t'), 0.0, 0.0, dur_max), 2), 'tipo': a['tipo'],
                          'alvo': a.get('alvo') if a.get('alvo') in ('esquerda', 'direita', 'centro', 'cima', 'baixo') else '',
                          'intensidade': round(_num(a.get('intensidade'), 1.0, 0.2, 1.5), 2),
                          'dur': round(_num(a.get('dur'), ACOES[a['tipo']][1], 0.0, dur_max), 2)})
        acoes.sort(key=lambda a: a['t'])
        out.append({'personagem_id': pid, 'posicao': e.get('posicao') if e.get('posicao') in POSICOES else ('esquerda', 'direita', 'centro')[len(out)],
                    'expressao': e.get('expressao') if e.get('expressao') in EXPRESSOES else 'neutro', 'acoes': acoes})
    return out


def validar_cenario(d: dict) -> dict:
    d = d if isinstance(d, dict) else {}
    tipo = d.get('tipo') if d.get('tipo') in ('rua', 'casa', 'escola', 'parque', 'escritorio', 'vazio') else 'parque'
    hor = d.get('horario') if d.get('horario') in ('dia', 'tarde', 'noite') else 'dia'
    ceu = {'dia': ('#7ec8f2', '#d7f0ff'), 'tarde': ('#f6a06b', '#ffd9a0'), 'noite': ('#0e1a3a', '#2b3d6b')}[hor]
    if tipo in ('casa', 'escola', 'escritorio'):
        ceu = {'dia': ('#f3e3c7', '#fbf2df'), 'tarde': ('#e9cfa8', '#f6e3c4'), 'noite': ('#4a4060', '#6b5f86')}[hor]
    return {'nome': _txt(d.get('nome'), 40) or 'Cenário', 'descricao': _txt(d.get('descricao'), 300), 'tipo': tipo, 'horario': hor,
            'ceu': _cor(d.get('ceu'), ceu[0]), 'ceu2': _cor(d.get('ceu2'), ceu[1]),
            'chao': _cor(d.get('chao'), {'rua': '#8d8d8d', 'parque': '#6fbf5a', 'vazio': '#cfcfcf'}.get(tipo, '#b98b5e'))}


def assinatura(p: dict) -> str:
    return hashlib.sha256(json.dumps([VERSAO_RIG, {k: v for k, v in p.items() if k not in ('nome', 'descricao', 'voz')}], sort_keys=True).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- desenho das peças (uma vez por versão)
def _escurecer(hexa: str, f: float = 0.8) -> str:
    r, g, b, _ = raster.cor(hexa)
    return '#%02x%02x%02x' % (int(r * f), int(g * f), int(b * f))


class _Peca:
    """Tela com o pivô no centro; desenha em unidades (u) do personagem."""

    def __init__(self, raio_u: float):
        self.lado = int(2 * math.ceil(raio_u * K) + 4)
        self.t = raster.Tela(self.lado, self.lado)
        self.c = self.lado / 2

    def X(self, u):
        return self.c + u * K

    def ret(self, x0, y0, x1, y1, cor, raio=0.0):
        self.t.retangulo(self.X(x0), self.X(y0), self.X(x1), self.X(y1), raster.cor(cor), raio * K)

    def eli(self, cx, cy, rx, ry, cor, borda=0.0, alfa=255):
        self.t.elipse(self.X(cx), self.X(cy), rx * K, ry * K, raster.cor(cor, alfa), borda * K)

    def lin(self, x0, y0, x1, y1, cor, esp=1.0):
        self.t.linha(self.X(x0), self.X(y0), self.X(x1), self.X(y1), raster.cor(cor), esp * K)

    def pol(self, pts, cor):
        self.t.poligono([(self.X(x), self.X(y)) for x, y in pts], raster.cor(cor))


RAIOS = {'tronco': 36, 'cabeca': 29, 'braco': 17, 'antebraco': 18, 'coxa': 27, 'canela': 26}
OFFSETS = {  # pivô da peça no quadro do pai (unidades), pai
    'coxa_e': ((-4.5, 1), 'raiz'), 'coxa_d': ((4.5, 1), 'raiz'), 'canela_e': ((0, 24), 'coxa_e'), 'canela_d': ((0, 24), 'coxa_d'),
    'tronco': ((0, 0), 'raiz'), 'braco_e': ((-11, -26), 'tronco'), 'braco_d': ((11, -26), 'tronco'),
    'antebraco_e': ((0, 14.5), 'braco_e'), 'antebraco_d': ((0, 14.5), 'braco_d'), 'cabeca': ((0, -31), 'tronco'),
}
ALTURA_QUADRIL = 48.5   # do chão até a raiz (quadril)


def _largura(p):
    return {'magro': 0.86, 'medio': 1.0, 'forte': 1.2}[p['corpo']]


def _tronco(p) -> _Peca:
    k = _largura(p)
    t = _Peca(RAIOS['tronco'])
    t.ret(-2.6, -34, 2.6, -28, p['pele'])
    t.pol([(-9 * k, 3), (9 * k, 3), (11 * k, -25), (8 * k, -30.5), (-8 * k, -30.5), (-11 * k, -25)], p['roupa'])
    t.eli(-10.2 * k, -25.5, 3.4, 3.2, p['roupa'])
    t.eli(10.2 * k, -25.5, 3.4, 3.2, p['roupa'])
    t.ret(-9.6 * k, 0, 9.6 * k, 3.6, p['calca'])
    t.eli(-4.5, 1.5, 4.0, 3.0, p['calca'])
    t.eli(4.5, 1.5, 4.0, 3.0, p['calca'])
    t.lin(-3, -30.3, 0, -26.5, _escurecer(p['roupa']), 0.8)
    t.lin(3, -30.3, 0, -26.5, _escurecer(p['roupa']), 0.8)
    return t


def _membro(cor, comp, larg, raio, junta_cor=None, mao=None, pe=None, lado=1) -> _Peca:
    t = _Peca(raio)
    t.ret(-larg / 2, -0.5, larg / 2, comp, cor, larg / 2.4)
    t.eli(0, 0, larg / 2, larg / 2, junta_cor or cor)
    if mao:
        t.eli(0, comp + 1.6, 3.1, 3.3, mao)
    if pe:
        t.eli(1.8 * lado, comp + 1.2, 5.0, 2.7, pe)
    return t


def _cabeca(p, expr: str) -> _Peca:
    t = _Peca(RAIOS['cabeca'])
    pele, cab = p['pele'], p['cabelo']
    tipo = p['cabelo_tipo']
    if tipo == 'longo':
        t.ret(-11.6, -19, 11.6, 1.5, cab, 4)
    if tipo == 'coque':
        t.eli(0, -25.5, 4.6, 4.2, cab)
    t.eli(-10.4, -11.5, 2.2, 2.8, pele)
    t.eli(10.4, -11.5, 2.2, 2.8, pele)
    if tipo != 'careca':
        t.eli(0, -15.2, 11.6, 10.6, cab)
    if tipo == 'cacheado':
        for ang in range(0, 360, 30):
            a = math.radians(ang)
            if math.sin(a) < 0.35:
                t.eli(10.5 * math.cos(a), -14 + 9.8 * math.sin(a), 3.4, 3.4, cab)
    t.eli(0, -10.6, 10.0, 10.8, pele)
    if tipo in ('curto', 'coque', 'cacheado', 'longo'):
        t.pol([(-10, -15), (-6, -21), (2, -22.5), (8.5, -20), (10.2, -14), (6, -17.5), (-3, -18.2)], cab)
    # olhos
    ry = 3.6 if expr == 'surpreso' else 2.9
    for s in (-1, 1):
        t.eli(4 * s, -12, 2.6, ry, '#ffffff')
        t.eli(4 * s, -11.6, 1.55 if expr != 'surpreso' else 1.25, 1.65 if expr != 'surpreso' else 1.35, p['olhos'])
        t.eli(4 * s + 0.6, -12.4, 0.5, 0.5, '#ffffff')
    if expr == 'feliz':
        for s in (-1, 1):
            t.eli(4 * s, -8.6, 2.9, 1.0, pele)       # bochecha sobe e aperta o olho
            t.eli(6.8 * s, -6.8, 1.6, 0.9, '#f08080', alfa=90)
    # sobrancelhas: (y interna, y externa)
    sb = {'neutro': (-16.3, -16.3), 'feliz': (-16.8, -16.5), 'triste': (-17.6, -15.6), 'bravo': (-15.0, -17.2),
          'surpreso': (-18.4, -18.0), 'preocupado': (-17.4, -16.0)}[expr]
    for s in (-1, 1):
        t.lin(1.6 * s, sb[0], 6.4 * s, sb[1], _escurecer(cab, 0.9) if tipo != 'careca' else _escurecer(pele, 0.6), 1.1)
    t.eli(0, -7.6, 1.1, 0.8, _escurecer(pele, 0.82))
    ac = p['acessorio']
    if ac == 'oculos':
        for s in (-1, 1):
            t.eli(4 * s, -12, 3.6, 3.4, '#1d1d1d', borda=0.6)
        t.lin(-0.6, -12.3, 0.6, -12.3, '#1d1d1d', 0.6)
    elif ac == 'bone':
        t.eli(0, -19.8, 10.8, 5.6, p['roupa'])
        t.ret(-1, -17.6, 14.5, -15.2, _escurecer(p['roupa']), 1.2)
    elif ac == 'laco':
        t.pol([(6, -22), (12, -25), (12, -19)], '#e63946')
        t.pol([(6, -22), (1, -25.5), (1.5, -19)], '#e63946')
        t.eli(6, -22, 1.4, 1.4, '#b5202c')
    return t


BOCA_Y, OLHOS_Y = -4.4, -12.0     # centro da boca e dos olhos no quadro da cabeça (peças pequenas, giram junto)


def _boca(p, tipo: str) -> _Peca:
    t = _Peca(4.5)
    esc = '#5a1a1a'
    y = 0
    if tipo == 'fechada':
        t.lin(-2.4, y, 2.4, y, esc, 0.9)
    elif tipo == 'sorriso':
        for i in range(9):
            a0, a1 = math.pi * (0.15 + 0.7 * i / 9), math.pi * (0.15 + 0.7 * (i + 1) / 9)
            t.lin(3.2 * math.cos(a0), y - 1.2 + 2.2 * math.sin(a0), 3.2 * math.cos(a1), y - 1.2 + 2.2 * math.sin(a1), esc, 0.9)
    elif tipo == 'triste':
        for i in range(9):
            a0, a1 = math.pi * (1.15 + 0.7 * i / 9), math.pi * (1.15 + 0.7 * (i + 1) / 9)
            t.lin(2.8 * math.cos(a0), y + 1.6 + 1.8 * math.sin(a0), 2.8 * math.cos(a1), y + 1.6 + 1.8 * math.sin(a1), esc, 0.9)
    elif tipo == 'pequena':
        t.eli(0, y, 2.2, 1.1, esc)
    elif tipo == 'aberta':
        t.eli(0, y + 0.4, 3.0, 2.5, esc)
        t.eli(0, y + 1.6, 1.8, 1.0, '#e06666')
    elif tipo == 'o':
        t.eli(0, y + 0.2, 1.7, 2.2, esc)
    elif tipo == 'larga':        # 'e', 'i': boca esticada com dentes
        t.eli(0, y + 0.3, 3.4, 1.5, esc)
        t.ret(-2.6, y - 0.5, 2.6, y + 0.3, '#f4f1ea', 0.4)
    return t


def _palpebras(p) -> _Peca:
    t = _Peca(7.5)
    for s in (-1, 1):
        t.eli(4 * s, 0, 3.0, 3.9, p['pele'])
        t.lin(1.6 * s, 0.4, 6.4 * s, 0.4, _escurecer(p['pele'], 0.55), 0.7)
    return t


def pecas(p: dict, pasta_base: Path) -> dict:
    """Desenha (ou reaproveita) as peças deste personagem. Devolve {nome: arquivo PNG}."""
    p = validar_personagem(p)
    pasta = pasta_base / assinatura(p)
    feito = pasta / 'ok.json'
    nomes = (['tronco', 'braco_e', 'braco_d', 'antebraco_e', 'antebraco_d', 'coxa_e', 'coxa_d', 'canela_e', 'canela_d', 'palpebras', 'sombra']
             + [f'cabeca_{e}' for e in EXPRESSOES] + [f'boca_{b}' for b in BOCAS])
    arqs = {n: pasta / f'{n}.png' for n in nomes}
    if feito.exists() and all(a.exists() for a in arqs.values()):
        return arqs
    pasta.mkdir(parents=True, exist_ok=True)
    k = _largura(p)
    desenhos = {
        'tronco': lambda: _tronco(p),
        'braco_e': lambda: _membro(p['roupa'], 14.5, 6.2 * k, RAIOS['braco']),
        'braco_d': lambda: _membro(p['roupa'], 14.5, 6.2 * k, RAIOS['braco']),
        'antebraco_e': lambda: _membro(p['pele'], 12.5, 4.8 * k, RAIOS['antebraco'], mao=p['pele']),
        'antebraco_d': lambda: _membro(p['pele'], 12.5, 4.8 * k, RAIOS['antebraco'], mao=p['pele']),
        'coxa_e': lambda: _membro(p['calca'], 24, 7.4 * k, RAIOS['coxa']),
        'coxa_d': lambda: _membro(p['calca'], 24, 7.4 * k, RAIOS['coxa']),
        'canela_e': lambda: _membro(p['calca'], 21.5, 6.4 * k, RAIOS['canela'], pe=p['sapato'], lado=-1),
        'canela_d': lambda: _membro(p['calca'], 21.5, 6.4 * k, RAIOS['canela'], pe=p['sapato'], lado=1),
        'palpebras': lambda: _palpebras(p),
    }
    for e in EXPRESSOES:
        desenhos[f'cabeca_{e}'] = lambda e=e: _cabeca(p, e)
    for b in BOCAS:
        desenhos[f'boca_{b}'] = lambda b=b: _boca(p, b)
    for n, f in desenhos.items():
        f().t.salvar(arqs[n])
    s = raster.Tela(64, 16)
    s.elipse(32, 8, 30, 6, (0, 0, 0, 70))
    s.salvar(arqs['sombra'])
    feito.write_text(json.dumps({'rig': RIG_ID, 'versao': VERSAO_RIG}))
    return arqs


# ---------------------------------------------------------------- expressões de tempo (ângulos e posições)
class E:
    """Expressão do FFmpeg com constante dobrada: soma de termos em texto + número."""

    def __init__(self, c: float = 0.0, termos: list | None = None):
        self.c, self.termos = c, list(termos or [])

    def __add__(self, o):
        o = o if isinstance(o, E) else E(float(o))
        return E(self.c + o.c, self.termos + o.termos)

    def __mul__(self, k: float):
        return E(self.c * k, [f'{k:.5g}*({x})' for x in self.termos]) if k != 1 else self

    def const(self) -> bool:
        return not self.termos

    def __str__(self):
        partes = [f'({x})' for x in self.termos]
        if abs(self.c) > 1e-6 or not partes:
            partes.append(f'{self.c:.5g}')
        return '+'.join(partes).replace('+-', '-')


def _cos(a: E) -> E:
    return E(math.cos(a.c)) if a.const() else E(0, [f'cos({a})'])


def _sin(a: E) -> E:
    return E(math.sin(a.c)) if a.const() else E(0, [f'sin({a})'])


def _rot(a: E, ox: float, oy: float) -> tuple[E, E]:
    """Vetor (ox, oy) girado pelo ângulo a (sentido horário na tela)."""
    if a.const():
        c, s = math.cos(a.c), math.sin(a.c)
        return E(ox * c - oy * s), E(ox * s + oy * c)
    c, s = _cos(a), _sin(a)
    return c * ox + s * (-oy), s * ox + c * oy


def _env(t0: float, t1: float, sub: float = 0.3, desce: float | None = None) -> str:
    """0 antes de t0, sobe suave até 1, fica, e desce suave até 0 em t1."""
    d = sub if desce is None else desce
    a = f'clip((t-{t0:.3f})/{max(0.05, sub):.3f},0,1)'
    s1 = f'{a}*{a}*(3-2*{a})'
    if t1 >= 1e5:
        return s1
    b = f'clip(({t1:.3f}-t)/{max(0.05, d):.3f},0,1)'
    return f'{s1}*{b}*{b}*(3-2*{b})'


def _janelas(acoes: list, dur: float) -> list:
    """Converte a lista de ações em janelas (tipo, t0, t1, ação). Sentar dura até levantar."""
    out = []
    sentado = None
    for a in acoes:
        tp = a['tipo']
        if tp == 'sentar':
            sentado = a['t']
            continue
        if tp == 'levantar':
            if sentado is not None:
                out.append(('sentar', sentado, a['t'] + 0.3, a))
                sentado = None
            continue
        d = a['dur'] or ACOES[tp][1] or (dur - a['t'])
        out.append((tp, a['t'], min(dur + 1, a['t'] + d), a))
    if sentado is not None:
        out.append(('sentar', sentado, 1e6, {'intensidade': 1.0}))
    return out


def canais(el: dict, dur: float, x0: float, u: float, W: int) -> tuple[dict, E, E, list]:
    """Ângulos de cada junta e deslocamento da raiz (x em pixels, y em pixels) ao longo do tempo.
    Devolve (ângulos, dx, dy, janelas de expressão)."""
    ang = {j: E(BASE.get(j, 0.0)) for j in JUNTAS}
    dx, dy = E(), E()
    expr_jan = []
    fase = (hash(el['personagem_id']) % 100) / 100 * 6.28
    # respirar sempre, bem de leve
    ang['tronco'] += E(0, [f'0.012*sin(2*PI*t/3.4+{fase:.2f})'])
    ang['cabeca'] += E(0, [f'0.018*sin(2*PI*t/3.4+{fase + 0.6:.2f})'])
    for tp, t0, t1, a in _janelas(el['acoes'], dur):
        k = a.get('intensidade', 1.0)
        env = _env(t0, t1, 0.12 if tp in ('assustar', 'reagir') else 0.3)
        lado = -1 if a.get('alvo') == 'esquerda' else 1
        if ACOES.get(tp, ('', 0, ''))[2]:
            expr_jan.append((ACOES[tp][2], t0, t1))

        def soma(j, v, termo=''):
            ang[j] = ang[j] + E(0, [f'{v * k:.4g}*{env}' + (f'*{termo}' if termo else '')])
        if tp == 'olhar':
            v = {'esquerda': -0.2, 'direita': 0.2, 'cima': 0.0, 'baixo': 0.0}.get(a.get('alvo') or 'direita', 0.2)
            soma('cabeca', v if v else 0.0)
            if a.get('alvo') in ('cima', 'baixo'):
                dy = dy + E(0, [f'{-1.2 if a["alvo"] == "cima" else 0.8:.2f}*{u:.3f}*{env}'])
            soma('tronco', v * 0.25)
        elif tp in ('andar', 'correr'):
            alvo = POSICOES.get(a.get('alvo') or 'direita', 0.73) * W
            dist = alvo - x0
            rapido = tp == 'correr'
            f = 2.6 if rapido else 1.7
            amp = 0.55 if rapido else 0.38
            prog = f'clip((t-{t0:.3f})/{max(0.2, t1 - t0):.3f},0,1)'
            dx = dx + E(0, [f'{dist:.1f}*{prog}*{prog}*(3-2*{prog})'])
            w = f'sin(2*PI*{f}*(t-{t0:.3f}))'
            for j, s in (('coxa_e', 1), ('coxa_d', -1)):
                ang[j] = ang[j] + E(0, [f'{amp * s:.3f}*{env}*{w}'])
            for j, s in (('canela_e', -1), ('canela_d', 1)):
                ang[j] = ang[j] + E(0, [f'{amp * 0.6 * s:.3f}*{env}*{w}'])
            for j, s in (('braco_e', -1), ('braco_d', 1)):
                ang[j] = ang[j] + E(0, [f'{amp * 0.7 * s:.3f}*{env}*{w}'])
            dy = dy + E(0, [f'-{(2.2 if rapido else 1.2) * u:.2f}*{env}*abs({w})'])
            soma('tronco', 0.08 * (1 if dist > 0 else -1) * (1.6 if rapido else 1))
        elif tp == 'sentar':
            dy = dy + E(0, [f'{13 * u:.2f}*{env}'])
            soma('coxa_e', 1.15)
            soma('coxa_d', -1.15)
            soma('canela_e', -1.15)
            soma('canela_d', 1.15)
            soma('braco_e', 0.25)
            soma('braco_d', -0.25)
            soma('antebraco_e', -0.9)
            soma('antebraco_d', 0.9)
        elif tp == 'apontar':
            if lado < 0:
                soma('braco_e', 1.45)
                soma('antebraco_e', 0.05)
            else:
                soma('braco_d', -1.45)
                soma('antebraco_d', -0.05)
            soma('cabeca', 0.12 * lado)
        elif tp == 'acenar':
            soma('braco_d', -2.5)
            soma('antebraco_d', -0.2)
            ang['antebraco_d'] = ang['antebraco_d'] + E(0, [f'{0.38 * k:.3f}*{env}*sin(2*PI*3.2*(t-{t0:.3f}))'])
        elif tp in ('pegar', 'segurar'):
            soma('braco_e', -0.35)
            soma('antebraco_e', -1.25)
            soma('braco_d', 0.35)
            soma('antebraco_d', 1.25)
            if tp == 'pegar':
                soma('tronco', 0.0)
                dy = dy + E(0, [f'{2.0 * u:.2f}*{env}'])
        elif tp == 'entregar':
            if lado < 0:
                soma('braco_e', 1.2)
                soma('antebraco_e', 0.15)
            else:
                soma('braco_d', -1.2)
                soma('antebraco_d', -0.15)
            soma('tronco', 0.06 * lado)
        elif tp in ('reagir', 'assustar'):
            forte = tp == 'assustar'
            soma('braco_e', 1.6 if forte else 0.6)
            soma('antebraco_e', -0.7 if forte else 0.6)
            soma('braco_d', -1.6 if forte else -0.6)
            soma('antebraco_d', 0.7 if forte else -0.6)
            soma('cabeca', -0.1)
            dy = dy + E(0, [f'-{(4.5 if forte else 1.5) * u:.2f}*{_env(t0, t0 + 0.45, 0.12, 0.25)}'])
        elif tp == 'rir':
            ang['cabeca'] = ang['cabeca'] + E(0, [f'{0.1 * k:.3f}*{env}*sin(2*PI*4.5*(t-{t0:.3f}))'])
            ang['tronco'] = ang['tronco'] + E(0, [f'{0.04 * k:.3f}*{env}*sin(2*PI*4.5*(t-{t0:.3f}))'])
            soma('braco_e', -0.3)
            soma('antebraco_e', -1.0)
        elif tp == 'falar':
            for j, v, f in (('braco_e', 0.22, 0.7), ('antebraco_e', -0.35, 0.7), ('braco_d', -0.18, 0.55), ('antebraco_d', 0.3, 0.55)):
                ang[j] = ang[j] + E(0, [f'{v * k:.3f}*{env}*(0.5+0.5*sin(2*PI*{f}*(t-{t0:.3f})+{fase:.2f}))'])
            ang['cabeca'] = ang['cabeca'] + E(0, [f'{0.05 * k:.3f}*{env}*sin(2*PI*1.6*(t-{t0:.3f}))'])
    return ang, dx, dy, expr_jan


# ---------------------------------------------------------------- boca pelo volume da fala
def niveis_fala(wav: Path | None, dur: float, passo: float = 1 / 12) -> list[int]:
    """0 = fechada, 1 = pouco aberta, 2 = aberta ('a'), 3 = redonda ('o', 'u'), 4 = larga ('e', 'i').
    Abertura pelo volume; forma pela taxa de cruzamentos por zero (vogal fechada/escura x aberta/clara). Aproximação, sem fonemas."""
    n = max(1, int(dur / passo))
    if not wav or not Path(wav).exists():
        return [0] * n
    try:
        with wave.open(str(wav), 'rb') as w:
            sr, ch, larg = w.getframerate(), w.getnchannels(), w.getsampwidth()
            dados = w.readframes(w.getnframes())
    except (wave.Error, OSError, EOFError):
        return [0] * n
    if larg != 2:
        return [0] * n
    import array
    a = array.array('h')
    a.frombytes(dados[:len(dados) // 2 * 2])
    if ch > 1:
        a = a[::ch]
    jan = max(1, int(sr * passo))
    rms, zcr = [], []
    for i in range(n):
        bloco = a[i * jan:(i + 1) * jan]
        rms.append(math.sqrt(sum(x * x for x in bloco[::4]) / max(1, len(bloco[::4]))) if bloco else 0.0)
        zcr.append(sum((bloco[k] >= 0) != (bloco[k + 1] >= 0) for k in range(0, len(bloco) - 1, 2)) / max(1, len(bloco) // 2) if bloco else 0.0)
    ref = sorted(rms)[int(len(rms) * 0.92)] if rms else 0
    if ref <= 50:
        return [0] * n
    vozes = sorted(z for r, z in zip(rms, zcr) if r / ref >= 0.5)
    med = (vozes[len(vozes) // 4] + vozes[len(vozes) * 3 // 4]) / 2 if vozes else 0     # meio entre as vogais escuras e as claras
    out, abertos = [], 0
    for r, z in zip(rms, zcr):
        v = r / ref
        nv = 0 if v < 0.18 else 1 if v < 0.5 else 2
        if nv == 2:
            if med > 0 and z > med * 1.25:
                nv = 4
            elif med > 0 and z < med * 0.75:
                nv = 3
            elif med <= 0:
                abertos += 1
                nv = 3 if abertos % 5 == 0 else 2
        out.append(nv)
    return out


def _segmentos(niveis: list, valor: int, passo: float) -> list[tuple[float, float]]:
    seg, ini = [], None
    for i, v in enumerate(niveis + [-1]):
        if v == valor and ini is None:
            ini = i
        elif v != valor and ini is not None:
            seg.append((ini * passo, i * passo))
            ini = None
    return seg


def _soma_janelas(seg: list) -> str:
    return '+'.join(f'between(t,{a:.3f},{b - 0.001:.3f})' for a, b in seg) or '0'


# ---------------------------------------------------------------- montagem no filtro do FFmpeg
def colocar(c, el: dict, p: dict, arqs: dict, chao_y: float, altura_px: float, W: int, dur: float, falando: bool, wav: Path | None):
    """Coloca um personagem na composição `c` (estilos_codigo.Comp). Tudo em expressões de tempo; nenhuma imagem por quadro em Python."""
    u = altura_px / 100 * p['altura']
    esc = u / K
    x0 = POSICOES[el['posicao']] * W
    ang, dx, dy, jan = canais(el, dur, x0, u, W)
    raiz_x = E(x0) + dx
    raiz_y = E(chao_y - ALTURA_QUADRIL * u) + dy
    mundo = {'raiz': (raiz_x, raiz_y, E(0.0))}
    for nome in ('tronco', 'coxa_e', 'coxa_d', 'canela_e', 'canela_d', 'braco_e', 'braco_d', 'antebraco_e', 'antebraco_d', 'cabeca'):
        (ox, oy), pai = OFFSETS[nome]
        px, py, pa = mundo[pai]
        rx, ry = _rot(pa, ox * u, oy * u)
        mundo[nome] = (px + rx, py + ry, pa + ang[nome] if pai != 'raiz' else ang[nome])
    # sombra no chão (acompanha a caminhada)
    import estilos_codigo as _ec
    c.png(_ec._escalada_para(arqs['sombra'], int(30 * u), int(7 * u)), f'{raiz_x}-w/2', f'{chao_y - 3.2 * u:.1f}', 0, 0)

    def peca(nome, arq, enable='', desloc=None):
        px, py, a = mundo[nome]
        if desloc:
            rx, ry = _rot(a, desloc[0] * u, desloc[1] * u)
            px, py = px + rx, py + ry
        c.peca_girando(arq, esc, str(a), f'{px}-w/2', f'{py}-h/2', enable)

    for nome in ('coxa_e', 'canela_e', 'coxa_d', 'canela_d', 'tronco'):
        peca(nome, arqs[nome])
    # cabeça: expressão base, trocada nas janelas de ações que pedem outra
    base = el['expressao']
    usadas = {}
    for ex, t0, t1 in jan:
        if ex != base:
            usadas.setdefault(ex, []).append((t0, min(t1, dur + 1)))
    fora = '+'.join(f'between(t,{a:.3f},{b:.3f})' for seg in usadas.values() for a, b in seg)
    peca('cabeca', arqs[f'cabeca_{base}'], f'not({fora})' if fora else '')
    for ex, seg in usadas.items():
        peca('cabeca', arqs[f'cabeca_{ex}'], _soma_janelas(seg))
    # boca: quem fala segue o volume; quem não fala fica com a boca da expressão
    passo = 1 / 12
    if falando:
        nv = niveis_fala(wav, dur, passo)
        fechada = 'sorriso' if base == 'feliz' else 'triste' if base in ('triste', 'preocupado') else 'fechada'
        for valor, nome in ((0, fechada), (1, 'pequena'), (2, 'aberta'), (3, 'o'), (4, 'larga')):
            seg = _segmentos(nv, valor, passo)
            if valor == 0:
                seg = seg + [(len(nv) * passo, dur + 1)]
            if seg:
                peca('cabeca', arqs[f'boca_{nome}'], _soma_janelas(seg), (0, BOCA_Y))
    else:
        nome = 'sorriso' if base == 'feliz' else 'triste' if base in ('triste', 'preocupado') else 'fechada'
        peca('cabeca', arqs[f'boca_{nome}'], '', (0, BOCA_Y))
    # piscar a cada ~3,5 s (cada personagem num ritmo)
    sem = sum(map(ord, el['personagem_id']))
    piscadas, t = [], 0.6 + (sem % 17) / 10
    while t < dur:
        piscadas.append((t, t + 0.13))
        t += 2.6 + (sem * (len(piscadas) + 3) % 23) / 10
    piscadas += [(a, a + 0.13) for tp, a, _b, _x in _janelas(el['acoes'], dur) if tp == 'piscar']
    if piscadas:
        peca('cabeca', arqs['palpebras'], _soma_janelas(piscadas), (0, OLHOS_Y))
    for nome in ('braco_e', 'antebraco_e', 'braco_d', 'antebraco_d'):
        peca(nome, arqs[nome])
    return {'x_px': x0, 'cabeca_y': chao_y - (ALTURA_QUADRIL + 31 + 11) * u, 'tronco_y': chao_y - (ALTURA_QUADRIL + 14) * u}


def elenco_padrao(cena: dict, pal: tuple) -> tuple[list, dict]:
    """Sem série: um apresentador com as cores da paleta, falando a narração."""
    p = validar_personagem({'nome': 'Apresentador', 'roupa': pal[2] if pal[2] not in ('#ffffff', '#fff') else pal[1], 'calca': '#2b2d42'})
    acoes = [{'t': 0.0, 'tipo': 'falar', 'alvo': '', 'intensidade': 1.0, 'dur': 0}]
    if cena.get('destaque'):
        acoes.append({'t': 0.4, 'tipo': 'apontar', 'alvo': 'direita', 'intensidade': 1.0, 'dur': 1.6})
    return [{'personagem_id': 'apresentador', 'posicao': 'centro', 'expressao': 'feliz', 'acoes': acoes}], {'apresentador': p}


def folha_modelo(p: dict, pasta_base: Path, arq: Path) -> Path:
    """Folha de modelo: corpo inteiro (pose base) + as 6 expressões + as bocas. Montada em Python, sem FFmpeg."""
    p = validar_personagem(p)
    arqs = pecas(p, pasta_base)
    lido = {n: _ler_png(a) for n, a in arqs.items()}
    W, H = int(K * 180), int(K * 116)
    tela = raster.Tela(W, H, (250, 248, 243, 255))
    cx, chao = K * 32, H - K * 6
    mundo = {'raiz': (cx, chao - ALTURA_QUADRIL * K)}
    for nome in ('tronco', 'coxa_e', 'coxa_d', 'canela_e', 'canela_d', 'braco_e', 'braco_d', 'antebraco_e', 'antebraco_d', 'cabeca'):
        (ox, oy), pai = OFFSETS[nome]
        px, py = mundo[pai]
        mundo[nome] = (px + ox * K, py + oy * K)
    for nome in ('coxa_e', 'canela_e', 'coxa_d', 'canela_d', 'tronco', 'cabeca_neutro', 'boca_fechada', 'braco_e', 'antebraco_e', 'braco_d', 'antebraco_d'):
        chave = nome.split('_')[0] if nome.startswith(('cabeca', 'boca')) else nome
        x, y = mundo['cabeca' if chave in ('cabeca', 'boca') else nome]
        _colar(tela, lido[nome], x, y + (BOCA_Y * K if chave == 'boca' else 0))
    for i, ex in enumerate(EXPRESSOES):
        x, y = K * (82 + (i % 3) * 34), K * (44 + (i // 3) * 50)
        _colar(tela, lido[f'cabeca_{ex}'], x, y)
        _colar(tela, lido['boca_sorriso' if ex == 'feliz' else 'boca_triste' if ex in ('triste', 'preocupado') else 'boca_o' if ex == 'surpreso' else 'boca_fechada'], x, y + BOCA_Y * K)
    return tela.salvar(arq)


def _ler_png(arq: Path) -> tuple[int, int, bytes]:
    import zlib
    b = arq.read_bytes()
    w, h = int.from_bytes(b[16:20], 'big'), int.from_bytes(b[20:24], 'big')
    i, idat = 8, b''
    while i < len(b):
        n = int.from_bytes(b[i:i + 4], 'big')
        tp = b[i + 4:i + 8]
        if tp == b'IDAT':
            idat += b[i + 8:i + 8 + n]
        i += 12 + n
    cru = zlib.decompress(idat)
    linhas = [cru[y * (w * 4 + 1) + 1:(y + 1) * (w * 4 + 1)] for y in range(h)]   # o raster grava sem filtro
    return w, h, b''.join(linhas)


def _colar(tela, img, cx, cy):
    w, h, px = img
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    for y in range(h):
        for x in range(w):
            i = (y * w + x) * 4
            a = px[i + 3]
            if a:
                tela._misturar(x0 + x, y0 + y, (px[i], px[i + 1], px[i + 2], a))
