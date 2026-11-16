"""Personagens 3D com câmera de verdade, desenhados por software (numpy, sem placa de vídeo).

Mesmo elenco, cenários e catálogo de ações do desenho 2D (rig2d): cada personagem vira um boneco de peças (caixas e
esferas) com juntas; as ações viram ângulos das juntas a cada quadro; a câmera se move de verdade no espaço (aberto, médio,
close) sempre do mesmo lado da cena (eixo de 180°). A boca abre pelo volume da voz.

É LENTO no celular (o dono mediu o 3D por software: centenas de ms por quadro). Por isso desenha em meia resolução e
15 quadros por segundo, e o FFmpeg completa para 30. Fica guardado em cache: refazer a mesma cena não desenha de novo.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from pathlib import Path

import rig2d

try:
    import numpy as np
except ImportError:
    np = None

VERSAO = 2
FPS_3D = int(os.getenv('FPS_3D', '15'))
ESCALA = float(os.getenv('ESCALA_3D', '0.5'))
CACHE = Path(os.getenv('DADOS', str(Path.home() / '.estudioclip'))) / 'cache3d' / 'cenas'
ZOOM = {'WS': None, 'MS': 1.7, 'CU': 0.95, 'ECU': 0.55}     # altura (em metros) que o plano mostra


def disponivel() -> bool:
    return np is not None


def _rgb(h: str) -> tuple:
    h = h.lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# ---------------------------------------------------------------- malhas
def _caixa():
    v = np.array([(x, y, z) for x in (-.5, .5) for y in (-.5, .5) for z in (-.5, .5)], float)
    f = np.array([(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)])
    return v, f


def _esfera(n=7):
    """Esfera de raio 0,5 com polos (anéis de n faixas)."""
    m = n * 2
    v = [(0.0, 0.5, 0.0)]
    for i in range(1, n):
        a = math.pi * i / n
        for j in range(m):
            b = 2 * math.pi * j / m
            v.append((math.sin(a) * math.cos(b) * .5, math.cos(a) * .5, math.sin(a) * math.sin(b) * .5))
    v.append((0.0, -0.5, 0.0))
    f = [(0, 1 + (j + 1) % m, 1 + j) for j in range(m)]
    for i in range(n - 2):
        for j in range(m):
            p, q = 1 + i * m + j, 1 + i * m + (j + 1) % m
            f += [(p, q, q + m), (p, q + m, p + m)]
    ult = len(v) - 1
    for j in range(m):
        p, q = 1 + (n - 2) * m + j, 1 + (n - 2) * m + (j + 1) % m
        f.append((p, q, ult))
    return np.array(v, float), np.array(f)


def _plano():
    """Quadrado no chão (só a face de cima): o chão é feito de vários destes para nenhum ficar atrás da câmera."""
    return np.array([(-.5, 0, -.5), (-.5, 0, .5), (.5, 0, -.5), (.5, 0, .5)], float), np.array([(0, 1, 3), (0, 3, 2)])


if np is not None:
    PLANO = _plano()
    CAIXA = _caixa()
    ESFERA = _esfera(8)
    ESFERA_P = _esfera(4)


# ---------------------------------------------------------------- matrizes
def _T(x, y, z):
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


def _S(x, y, z):
    return np.diag((x, y, z, 1.0))


def _R(eixo, a):
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    if eixo == 'x':
        m[1:3, 1:3] = ((c, -s), (s, c))
    elif eixo == 'y':
        m[0, 0], m[0, 2], m[2, 0], m[2, 2] = c, s, -s, c
    else:
        m[0:2, 0:2] = ((c, -s), (s, c))
    return m


# ---------------------------------------------------------------- ações -> pose
def _suave(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _env(t, t0, t1, rampa=0.25):
    if t < t0 or t > t1 + rampa:
        return 0.0
    return _suave((t - t0) / rampa) * (1 - _suave((t - t1) / rampa))


def _x_palco(pos: str) -> float:
    return (rig2d.POSICOES.get(pos, 0.5) - 0.5) * 4.6


def pose(el: dict, t: float, fala: float, dur: float) -> dict:
    """Ângulos (radianos) e posição do personagem no instante t. Mesmo catálogo de ações do 2D."""
    p = {'x': _x_palco(el['posicao']), 'y': 0.0, 'giro': 0.0, 'tronco_x': 0.0, 'tronco_z': 0.0, 'cab_y': 0.0, 'cab_x': 0.0, 'cab_z': 0.0,
         'ombro_e_z': 0.08, 'ombro_d_z': -0.08, 'ombro_e_x': 0.0, 'ombro_d_x': 0.0, 'cot_e': 0.1, 'cot_d': 0.1,
         'coxa_e': 0.0, 'coxa_d': 0.0, 'joelho_e': 0.0, 'joelho_d': 0.0, 'boca': fala, 'olhos': 1.0, 'sentado': 0.0}
    p['tronco_x'] += 0.015 * math.sin(t * 2.1)                     # respiração
    p['ombro_e_z'] += 0.02 * math.sin(t * 2.1)
    p['ombro_d_z'] -= 0.02 * math.sin(t * 2.1)
    if (t % 3.3) < 0.13:
        p['olhos'] = 0.12
    sentado = 0.0
    for a in el.get('acoes') or []:
        tp, t0 = a['tipo'], a['t']
        d = a.get('dur') or rig2d.ACOES[tp][1] or max(0.1, dur - t0)
        t1 = t0 + d
        k = _env(t, t0, t1) * a.get('intensidade', 1.0)
        lado = 1 if (a.get('alvo') or 'direita') == 'direita' else -1
        if tp == 'piscar' and t0 <= t <= t1:
            p['olhos'] = 0.12
        elif tp == 'olhar':
            if a.get('alvo') in ('cima', 'baixo'):
                p['cab_x'] += (-0.35 if a['alvo'] == 'cima' else 0.3) * k
            else:
                p['cab_y'] += 0.55 * lado * k
                p['tronco_z'] -= 0.04 * lado * k
        elif tp in ('andar', 'correr'):
            alvo = _x_palco(a.get('alvo') or 'direita')
            pr = _suave((t - t0) / max(0.2, d)) if t >= t0 else 0.0
            ini = p['x']
            p['x'] = ini + (alvo - ini) * pr
            if t0 <= t <= t1 and abs(alvo - ini) > 0.05:
                f = 2.6 if tp == 'correr' else 1.8
                amp = 0.7 if tp == 'correr' else 0.45
                w = math.sin(2 * math.pi * f * (t - t0))
                kk = _env(t, t0, t1, 0.2)
                p['coxa_e'] += amp * w * kk
                p['coxa_d'] -= amp * w * kk
                p['joelho_e'] += amp * max(0, -w) * 1.2 * kk
                p['joelho_d'] += amp * max(0, w) * 1.2 * kk
                p['ombro_e_x'] -= amp * 0.8 * w * kk
                p['ombro_d_x'] += amp * 0.8 * w * kk
                p['giro'] += (1.2 if alvo > ini else -1.2) * kk
                p['y'] += 0.03 * abs(math.sin(2 * math.pi * f * (t - t0))) * kk
                if tp == 'correr':
                    p['tronco_x'] -= 0.18 * kk
        elif tp == 'sentar' and t >= t0:
            sentado = max(sentado, _suave((t - t0) / 0.6))
        elif tp == 'levantar' and t >= t0:
            sentado = min(sentado, 1 - _suave((t - t0) / max(0.3, d)))
        elif tp == 'apontar':
            o = 'ombro_d_z' if lado > 0 else 'ombro_e_z'
            p[o] += -1.45 * k if lado > 0 else 1.45 * k
            p['cot_d' if lado > 0 else 'cot_e'] -= 0.08 * k
            p['cab_y'] += 0.3 * lado * k
        elif tp == 'acenar':
            p['ombro_d_z'] -= 2.5 * k
            p['cot_d'] += (0.35 + 0.35 * math.sin((t - t0) * 12)) * k
        elif tp in ('pegar', 'segurar'):
            p['ombro_e_x'] -= 1.1 * k
            p['ombro_d_x'] -= 1.1 * k
            p['cot_e'] += 0.5 * k
            p['cot_d'] += 0.5 * k
            if tp == 'pegar':
                p['tronco_x'] -= 0.3 * k * max(0, math.sin(math.pi * min(1, (t - t0) / max(0.1, d))))
        elif tp == 'entregar':
            o = 'd' if lado > 0 else 'e'
            p[f'ombro_{o}_x'] -= 1.2 * k
            p[f'ombro_{o}_z'] += (-0.5 if lado > 0 else 0.5) * k
            p['giro'] += 0.35 * lado * k
        elif tp in ('reagir', 'assustar'):
            p['tronco_x'] += 0.22 * k
            p['ombro_e_z'] += 0.9 * k
            p['ombro_d_z'] -= 0.9 * k
            p['cot_e'] += 1.0 * k
            p['cot_d'] += 1.0 * k
            if tp == 'assustar':
                p['y'] += 0.18 * math.sin(math.pi * min(1.0, max(0.0, (t - t0) / 0.45)))
            p['boca'] = max(p['boca'], 0.8 * k)
        elif tp == 'rir':
            p['tronco_z'] += 0.06 * math.sin((t - t0) * 18) * k
            p['cab_x'] -= 0.2 * k
            p['boca'] = max(p['boca'], (0.5 + 0.4 * abs(math.sin((t - t0) * 14))) * k)
        elif tp == 'falar' and t >= t0:
            g = min(1.0, fala * 2)
            p['cot_d'] += 0.35 * g * (0.5 + 0.5 * math.sin(t * 5))
            p['ombro_d_x'] -= 0.25 * g
            p['cab_x'] += 0.04 * math.sin(t * 7) * g
    if sentado:
        p['y'] -= 0.42 * sentado
        p['coxa_e'] -= 1.45 * sentado
        p['coxa_d'] -= 1.45 * sentado
        p['joelho_e'] += 1.45 * sentado
        p['joelho_d'] += 1.45 * sentado
    p['sentado'] = sentado
    return p


# ---------------------------------------------------------------- boneco
def boneco(perfil: dict, ps: dict, expressao: str) -> list:
    """Lista de (malha, matriz, cor, brilho) de um personagem na pose ps."""
    pe = rig2d.validar_personagem(perfil)
    s = pe['altura']
    larg = {'magro': 0.36, 'medio': 0.42, 'forte': 0.52}[pe['corpo']]
    pele, cab, roupa, calca, sapato, olho = (_rgb(pe[k]) for k in ('pele', 'cabelo', 'roupa', 'calca', 'sapato', 'olhos'))
    out = []
    raiz = _T(ps['x'], ps['y'], 0) @ _R('y', ps['giro']) @ _S(s, s, s)
    quadril = raiz @ _T(0, 0.92, 0)
    tronco = quadril @ _R('x', ps['tronco_x']) @ _R('z', ps['tronco_z'])
    out.append((CAIXA, tronco @ _T(0, 0.28, 0) @ _S(larg, 0.58, 0.26), roupa, 0))
    out.append((CAIXA, quadril @ _T(0, -0.02, 0) @ _S(larg * 0.95, 0.14, 0.25), calca, 0))
    # cabeça
    pesc = tronco @ _T(0, 0.6, 0)
    out.append((CAIXA, pesc @ _S(0.1, 0.1, 0.1), pele, 0))
    cabeca = pesc @ _R('y', ps['cab_y']) @ _R('x', ps['cab_x']) @ _R('z', ps['cab_z']) @ _T(0, 0.2, 0)
    out.append((ESFERA, cabeca @ _S(0.34, 0.38, 0.34), pele, 0.05))
    if pe['cabelo_tipo'] != 'careca':
        out.append((ESFERA, cabeca @ _T(0, 0.05, 0.03) @ _S(0.37, 0.36, 0.36), cab, 0))   # topo e nuca (a frente fica para o rosto)
        if pe['cabelo_tipo'] == 'longo':
            out.append((CAIXA, cabeca @ _T(0, -0.12, 0.1) @ _S(0.38, 0.36, 0.18), cab, 0))
        elif pe['cabelo_tipo'] == 'coque':
            out.append((ESFERA_P, cabeca @ _T(0, 0.22, 0.06) @ _S(0.14, 0.14, 0.14), cab, 0))
        elif pe['cabelo_tipo'] == 'cacheado':
            out.append((ESFERA, cabeca @ _T(0, 0.09, 0.03) @ _S(0.42, 0.34, 0.4), cab, 0))
    ab = max(0.12, ps['olhos'])
    for lx in (-0.075, 0.075):
        out.append((ESFERA_P, cabeca @ _T(lx, 0.02, -0.14) @ _S(0.075, 0.08 * ab, 0.06), (250, 250, 250), 0.2))
        out.append((ESFERA_P, cabeca @ _T(lx + 0.004 * (1 if ps['cab_y'] > 0 else -1), 0.015, -0.168) @ _S(0.038, 0.045 * ab, 0.02), olho, 0.4))
        out.append((CAIXA, cabeca @ _T(lx, 0.085 + (0.012 if expressao == 'surpreso' else 0), -0.17)
                    @ _R('z', {'bravo': 0.3, 'triste': -0.3, 'preocupado': -0.2}.get(expressao, 0) * (1 if lx > 0 else -1))
                    @ _S(0.07, 0.014, 0.012), cab, 0))
    b = ps['boca']
    lb = 0.11 if expressao == 'feliz' else 0.08
    out.append((CAIXA, cabeca @ _T(0, -0.085, -0.165) @ _S(lb * (1 - 0.25 * b), 0.012 + 0.04 * b, 0.015), (120, 30, 40), 0))
    if pe['acessorio'] == 'oculos':
        out.append((CAIXA, cabeca @ _T(0, 0.02, -0.19) @ _S(0.26, 0.09, 0.01), (40, 40, 40), 0.3))
    elif pe['acessorio'] == 'bone':
        out.append((CAIXA, cabeca @ _T(0, 0.17, -0.02) @ _S(0.36, 0.1, 0.36), roupa, 0))
        out.append((CAIXA, cabeca @ _T(0, 0.13, -0.2) @ _S(0.3, 0.03, 0.18), roupa, 0))
    elif pe['acessorio'] == 'laco':
        out.append((ESFERA_P, cabeca @ _T(0.14, 0.15, 0) @ _S(0.1, 0.08, 0.06), (230, 60, 120), 0))
    # braços
    for lado, sx in (('e', -1), ('d', 1)):
        ombro = tronco @ _T(sx * (larg / 2 + 0.06), 0.52, 0) @ _R('x', ps[f'ombro_{lado}_x']) @ _R('z', ps[f'ombro_{lado}_z'])
        out.append((CAIXA, ombro @ _T(0, -0.15, 0) @ _S(0.11, 0.32, 0.11), roupa, 0))
        cot = ombro @ _T(0, -0.3, 0) @ _R('x', -ps[f'cot_{lado}'])
        out.append((CAIXA, cot @ _T(0, -0.13, 0) @ _S(0.09, 0.28, 0.09), pele, 0))
        out.append((ESFERA_P, cot @ _T(0, -0.3, 0) @ _S(0.1, 0.1, 0.1), pele, 0))
    # pernas
    for lado, sx in (('e', -1), ('d', 1)):
        coxa = quadril @ _T(sx * larg * 0.24, 0, 0) @ _R('x', ps[f'coxa_{lado}'])
        out.append((CAIXA, coxa @ _T(0, -0.22, 0) @ _S(0.15, 0.46, 0.15), calca, 0))
        jo = coxa @ _T(0, -0.45, 0) @ _R('x', ps[f'joelho_{lado}'])
        out.append((CAIXA, jo @ _T(0, -0.2, 0) @ _S(0.13, 0.42, 0.13), calca, 0))
        out.append((CAIXA, jo @ _T(0, -0.43, -0.05) @ _S(0.15, 0.08, 0.27), sapato, 0.1))
    if ps['sentado'] > 0.05:   # banquinho aparece ao sentar
        out.append((CAIXA, _T(ps['x'], 0.24, 0.12) @ _S(0.55, 0.48 * min(1, ps['sentado'] * 1.5), 0.45), (120, 85, 55), 0))
    return out


# ---------------------------------------------------------------- cenário
def cenario(cn: dict) -> tuple:
    """(céu em cima, céu embaixo) e a lista de peças fixas do cenário."""
    chao = _rgb(cn['chao'])
    # chão em ladrilhos: um triângulo com ponta atrás da câmera some inteiro, então o chão não pode ser uma peça só
    # perto da câmera os ladrilhos são rasos (1,25 m), longe são fundos: pouco triângulo e sem buraco embaixo do quadro
    linhas = [(-12 + 1.25 * k, 1.25) for k in range(12)] + [(3 + 3 * k, 3) for k in range(5)]
    out = [(PLANO, _T(x, 0, z + d / 2) @ _S(8.02, 1, d + 0.02), tuple(int(c * (0.975 if (k + j) % 2 else 1.0)) for c in chao), 0)
           for j, x in enumerate(range(-16, 17, 8)) for k, (z, d) in enumerate(linhas)]
    out.append((PLANO, _T(0, 0, 43) @ _S(120, 1, 50), chao, 0))
    tipo = cn['tipo']
    if tipo == 'parque':
        for x, z, s in ((-4.2, 5, 1.2), (3.8, 6.5, 1.5), (-1.5, 9, 1.8), (6.5, 9, 1.4), (-7, 8, 1.6)):
            out.append((CAIXA, _T(x, s * 0.6, z) @ _S(0.25 * s, 1.2 * s, 0.25 * s), (110, 75, 45), 0))
            out.append((ESFERA, _T(x, s * 1.5, z) @ _S(1.3 * s, 1.2 * s, 1.3 * s), (70, 150, 70), 0))
    elif tipo in ('casa', 'escola', 'escritorio'):
        parede = _rgb(cn['ceu'])
        out.append((CAIXA, _T(0, 3, 3.2) @ _S(30, 6.5, 0.2), parede, 0))
        out.append((CAIXA, _T(0, 0.08, 3.05) @ _S(30, 0.16, 0.1), tuple(int(c * 0.7) for c in parede), 0))
        if tipo == 'casa':
            out.append((CAIXA, _T(-2.6, 0.3, 2.5) @ _S(2.2, 0.6, 0.8), (150, 70, 70), 0))
            out.append((CAIXA, _T(-2.6, 0.75, 2.85) @ _S(2.2, 0.7, 0.2), (150, 70, 70), 0))
            out.append((CAIXA, _T(2.4, 2.0, 3.08) @ _S(1.4, 1.1, 0.04), (220, 235, 250), 0.2))
            out.append((CAIXA, _T(-0.4, 2.2, 3.08) @ _S(0.8, 0.6, 0.04), (60, 140, 120), 0))
        elif tipo == 'escola':
            out.append((CAIXA, _T(0, 1.9, 3.08) @ _S(3.6, 1.4, 0.05), (40, 90, 60), 0))
            out.append((CAIXA, _T(0, 1.15, 3.0) @ _S(3.6, 0.08, 0.15), (150, 110, 70), 0))
        else:
            out.append((CAIXA, _T(2.6, 0.75, 2.2) @ _S(1.8, 0.08, 0.9), (150, 110, 70), 0))
            for x in (1.9, 3.3):
                out.append((CAIXA, _T(x, 0.36, 2.2) @ _S(0.08, 0.72, 0.8), (90, 70, 50), 0))
            out.append((CAIXA, _T(2.6, 1.05, 2.4) @ _S(0.7, 0.45, 0.05), (30, 30, 35), 0.3))
    elif tipo == 'rua':
        out.append((CAIXA, _T(0, 0.08, 3.5) @ _S(40, 0.16, 2), (170, 170, 170), 0))
        for k, (x, h) in enumerate(((-7, 6), (-3.5, 4), (0, 7), (3.6, 5), (7.2, 6.5))):
            cor = ((190, 120, 90), (120, 150, 190), (200, 190, 150), (150, 110, 140), (110, 160, 140))[k]
            out.append((CAIXA, _T(x, h / 2, 6) @ _S(3.3, h, 2.5), cor, 0))
            for jy in range(1, int(h) - 1, 2):
                out.append((CAIXA, _T(x, jy + 0.5, 4.73) @ _S(2.2, 0.6, 0.03), (230, 240, 250), 0.2))
    return (_rgb(cn['ceu']), _rgb(cn['ceu2'])), out


# ---------------------------------------------------------------- câmera
def _olhar(olho, alvo, giro: float = 0.0):
    f = np.array(alvo, float) - np.array(olho, float)
    f /= np.linalg.norm(f)
    r = np.cross(np.array([math.sin(giro), math.cos(giro), 0]), f)
    r /= np.linalg.norm(r)
    u = np.cross(f, r)
    m = np.eye(4)
    m[0, :3], m[1, :3], m[2, :3] = r, u, f
    m[:3, 3] = -m[:3, :3] @ np.array(olho, float)
    return m


def camera(plano: str, alvo_x: float, cabeca_y: float, grupo: tuple, W: int, H: int, prog: float, k: int, angulo: str = 'normal') -> tuple:
    """Posição e alvo da câmera de um plano. Sempre na frente (z negativo): o eixo de 180° nunca é cruzado."""
    vfov = math.radians(38)
    asp = W / H
    hfov = 2 * math.atan(math.tan(vfov / 2) * asp)
    if plano == 'WS' or plano not in ZOOM:
        x0, x1 = grupo
        largura = (x1 - x0) + 1.3
        dist = max(largura / 2 / math.tan(hfov / 2), 2.4 / 2 / math.tan(vfov / 2))
        alvo = ((x0 + x1) / 2, 1.05, 0)
        olho = (alvo[0], 1.75, -dist)
    else:
        alt = ZOOM[plano]
        dist = alt / 2 / math.tan(vfov / 2)
        ay = cabeca_y - (0.32 if plano == 'MS' else 0.02)
        alvo = (alvo_x, ay, 0)
        olho = (alvo_x + (0.25 if k % 2 else -0.25) * dist * 0.3, ay + 0.05, -dist)
    # movimento motivado: aproxima 6% ao longo do plano e gira de leve
    f = 1 - 0.06 * _suave(prog)
    olho = (alvo[0] + (olho[0] - alvo[0]) * f + 0.08 * math.sin(prog * 1.5), alvo[1] + (olho[1] - alvo[1]) * f, alvo[2] + (olho[2] - alvo[2]) * f)
    # ângulo de verdade: a câmera desce (olha para cima) ou sobe (olha para baixo); 'inclinado' gira a câmera no próprio eixo
    d = abs(olho[2] - alvo[2])
    if angulo == 'baixo':
        olho = (olho[0], max(0.25, alvo[1] - 0.45 * d), olho[2])
    elif angulo == 'alto':
        olho = (olho[0], alvo[1] + 0.6 * d, olho[2])
    return olho, alvo, vfov, (0.16 if angulo == 'inclinado' else 0.0)


# ---------------------------------------------------------------- desenho
def desenhar(W, H, ceu, pecas, olho, alvo, vfov, luz, giro: float = 0.0) -> 'np.ndarray':
    img = np.empty((H, W, 3), np.float32)
    g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    img[:] = (np.array(ceu[0], np.float32) * (1 - g) + np.array(ceu[1], np.float32) * g)[:, None, :]
    zb = np.full((H, W), np.inf, np.float32)
    V = _olhar(olho, alvo, giro)
    foc = (H / 2) / math.tan(vfov / 2)
    luz_v = (V[:3, :3] @ luz)
    for malha, M, cor, brilho in pecas:
        v0, f = malha
        vv = (V @ M @ np.c_[v0, np.ones(len(v0))].T).T[:, :3]
        z = vv[:, 2]
        if (z < 0.05).all():
            continue
        zs = np.maximum(z, 0.05)
        px = W / 2 + vv[:, 0] * foc / zs
        py = H / 2 - vv[:, 1] * foc / zs
        a, b, c = f[:, 0], f[:, 1], f[:, 2]
        n = np.cross(vv[b] - vv[a], vv[c] - vv[a])
        frente = (n * vv[a]).sum(1) < 0
        vis = frente & (z[a] > 0.05) & (z[b] > 0.05) & (z[c] > 0.05)
        ln = np.linalg.norm(n, axis=1) + 1e-12
        dif = np.clip(-(n @ luz_v) / ln, 0, 1)
        corv = np.array(cor, np.float32)
        for i in np.nonzero(vis)[0]:
            ia, ib, ic = a[i], b[i], c[i]
            xs, ys = (px[ia], px[ib], px[ic]), (py[ia], py[ib], py[ic])
            x0, x1 = max(int(min(xs)), 0), min(int(max(xs)) + 1, W)
            y0, y1 = max(int(min(ys)), 0), min(int(max(ys)) + 1, H)
            if x0 >= x1 or y0 >= y1:
                continue
            den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
            if abs(den) < 1e-9:
                continue
            gx = np.arange(x0, x1, dtype=np.float32)[None, :] + .5
            gy = np.arange(y0, y1, dtype=np.float32)[:, None] + .5
            l1 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / den
            l2 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / den
            l3 = 1 - l1 - l2
            prof = l1 * z[ia] + l2 * z[ib] + l3 * z[ic]
            zz = zb[y0:y1, x0:x1]
            ok = (l1 >= -1e-4) & (l2 >= -1e-4) & (l3 >= -1e-4) & (prof < zz)
            if not ok.any():
                continue
            cf = corv * (0.42 + 0.62 * dif[i])
            if brilho:
                cf = cf + 255 * brilho * dif[i] ** 12
            zz[ok] = prof[ok]
            img[y0:y1, x0:x1][ok] = cf
    return img


def _sombras(img, W, H, olho, alvo, vfov, xs, giro: float = 0.0):
    """Sombra de contato: mancha escura e suave no chão sob cada personagem (projeção do disco no chão)."""
    V = _olhar(olho, alvo, giro)
    foc = (H / 2) / math.tan(vfov / 2)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    for x in xs:
        pts = []
        for ang in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
            p = V @ np.array([x + 0.42 * math.cos(ang), 0.001, 0.3 * math.sin(ang), 1.0])
            if p[2] <= 0.05:
                break
            pts.append((W / 2 + p[0] * foc / p[2], H / 2 - p[1] * foc / p[2]))
        if len(pts) < 4:
            continue
        cx, cy = (pts[0][0] + pts[2][0]) / 2, (pts[1][1] + pts[3][1]) / 2
        rx, ry = max(2.0, abs(pts[0][0] - pts[2][0]) / 2), max(1.5, abs(pts[1][1] - pts[3][1]) / 2)
        d = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
        img *= (1 - 0.38 * np.clip(1 - d, 0, 1))[:, :, None]


def _quadro(W, H, ceu, fixos, elenco, perfis, t, dur, niveis, falante, planos, tempos, luz):
    poses = []
    for el in elenco:
        fala = 0.0
        if el['personagem_id'] == falante and niveis:
            fala = niveis[min(len(niveis) - 1, int(t * 12))] / 3
        poses.append((el, pose(el, t, fala, dur)))
    pecas = list(fixos)
    for el, ps in poses:
        pecas += boneco(perfis[el['personagem_id']], ps, el.get('expressao', 'neutro'))
    k = 0
    for k, (t0, t1) in enumerate(tempos):
        if t < t1 or k == len(tempos) - 1:
            break
    pl = planos[k]
    alvo_el = next((x for x in poses if x[0]['personagem_id'] == pl.get('personagem')), None) \
        or next((x for x in poses if x[0]['personagem_id'] == falante), None) or poses[0]
    s = rig2d.validar_personagem(perfis[alvo_el[0]['personagem_id']])['altura']
    xs = [ps['x'] for _, ps in poses]
    prog = (t - tempos[k][0]) / max(0.1, tempos[k][1] - tempos[k][0])
    olho, alvo, vfov, giro = camera(pl.get('plano', 'WS'), alvo_el[1]['x'], (1.72 + alvo_el[1]['y']) * s, (min(xs), max(xs)), W, H, prog, k,
                                    pl.get('angulo') or 'normal')
    img = desenhar(W, H, ceu, pecas, olho, alvo, vfov, luz, giro)
    _sombras(img, W, H, olho, alvo, vfov, xs, giro)
    return np.clip(img, 0, 255).astype(np.uint8)


def chave(cena: dict, W: int, H: int, dur: float) -> str:
    d = {k: cena.get(k) for k in ('elenco', 'planos', 'personagem', 'texto')}
    d.update(p=cena.get('_personagens'), c=cena.get('_cenario'), a=_sha_arquivo(cena.get('_audio')))
    return hashlib.sha256(json.dumps([VERSAO, FPS_3D, ESCALA, d, W, H, round(dur, 2)], sort_keys=True, default=str).encode()).hexdigest()[:20]


def _sha_arquivo(p):
    if not p or not Path(p).exists():
        return ''
    st = Path(p).stat()
    return f'{st.st_size}-{int(st.st_mtime)}'


def caminho(cena: dict, W: int, H: int, dur: float) -> Path:
    return CACHE / f'cena-{chave(cena, W, H, dur)}.mp4'


def preparar_cena(cena: dict, W: int, H: int, dur: float, cancelado=None, progresso=None) -> Path:
    """Desenha a cena 3D inteira (sem texto nem som) e guarda. O estilo põe legenda e áudio por cima."""
    if np is None:
        raise RuntimeError('O 3D precisa do numpy (pkg install python-numpy).')
    arq = caminho(cena, W, H, dur)
    if arq.exists() and arq.stat().st_size > 1000:
        return arq
    CACHE.mkdir(parents=True, exist_ok=True)
    perfis = cena.get('_personagens') or {}
    elenco = [e for e in (cena.get('elenco') or []) if e['personagem_id'] in perfis]
    if not elenco:
        elenco, perfis = rig2d.elenco_padrao(cena, ['#7ec8f2', '#ffffff', '#ff8c42'])
    cn = rig2d.validar_cenario(cena.get('_cenario') or {'tipo': 'parque'})
    ceu, fixos = cenario(cn)
    planos = cena.get('planos') or [{'id': 'p1', 'plano': 'WS', 'peso': 1.0, 'personagem': ''}]
    tot = sum(p.get('peso', 1.0) for p in planos) or 1
    tempos, t = [], 0.0
    for p in planos:
        d = dur * p.get('peso', 1.0) / tot
        tempos.append((t, t + d))
        t += d
    falante = (cena.get('personagem') or '').strip().lower()
    nomes = {k: rig2d.validar_personagem(p)['nome'].lower() for k, p in perfis.items()}
    falante = next((k for k in perfis if falante in (k, nomes.get(k))), elenco[0]['personagem_id'] if len(elenco) == 1 else '')
    niveis = rig2d.niveis_fala(Path(cena['_audio']) if cena.get('_audio') else None, dur) if falante else []
    if falante and not any(n for n in niveis) and cena.get('texto'):     # sem narração ainda: boca mexe num ritmo de fala
        niveis = [(0, 2, 1, 3, 1, 2, 0, 1)[i % 8] for i in range(int(dur * 12) + 1)]
    w, h = max(2, int(W * ESCALA) // 2 * 2), max(2, int(H * ESCALA) // 2 * 2)
    luz = np.array([0.45, -0.75, 0.5]); luz /= np.linalg.norm(luz)
    tmp = arq.with_suffix('.tmp.mp4')
    ff = subprocess.Popen(['ffmpeg', '-nostdin', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-r', str(FPS_3D),
                           '-i', '-', '-vf', f'scale={W}:{H}:flags=bicubic', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'veryfast', '-crf', '20',
                           str(tmp)], stdin=subprocess.PIPE)
    n = max(1, int(round(dur * FPS_3D)))
    try:
        for q in range(n):
            if cancelado and cancelado():
                raise InterruptedError()
            ff.stdin.write(_quadro(w, h, ceu, fixos, elenco, perfis, q / FPS_3D, dur, niveis, falante, planos, tempos, luz).tobytes())
            if progresso:
                progresso((q + 1) / n)
        ff.stdin.close()
        if ff.wait() != 0:
            raise RuntimeError('O FFmpeg não conseguiu gravar a cena 3D.')
    except BaseException:
        try:
            ff.kill()
        except OSError:
            pass
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(arq)
    return arq
