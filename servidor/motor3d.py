"""Motor 3D por software (numpy, sem placa de vídeo) para os estilos 3D.

Medido no celular do dono (teste_3d.py): ~257 ms por quadro a 540x960, ou seja ~8 s de render por segundo de vídeo.
Por isso o 3D é um FUNDO EM LOOP de 4 s (movimento periódico), desenhado uma vez por estilo/formato/paleta e guardado
em cache; o FFmpeg repete o loop pela duração da cena e põe o texto por cima. Os estilos 3D ficam como beta.
"""
from __future__ import annotations

import hashlib
import math
import os
import subprocess
from pathlib import Path

try:
    import numpy as np
except ImportError:           # sem numpy os estilos 3D continuam indisponíveis
    np = None

FPS = 30
PERIODO = 4.0                                   # segundos do loop
CACHE = Path(os.getenv('DADOS', str(Path.home() / '.estudioclip'))) / 'cache3d'
ESTILOS_3D = ('cinema3d', 'brinquedo_blocos', 'plastico3d', 'retro3d_2000')
VERSAO = 1


def disponivel() -> bool:
    return np is not None


def _hex(h: str) -> tuple:
    h = h.lstrip('#')
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _esfera(n=14):
    v, f = [], []
    for i in range(n + 1):
        a = math.pi * i / n
        for j in range(n * 2):
            b = 2 * math.pi * j / (n * 2)
            v.append((math.sin(a) * math.cos(b), math.cos(a), math.sin(a) * math.sin(b)))
    for i in range(n):
        for j in range(n * 2):
            p = i * n * 2 + j
            q = i * n * 2 + (j + 1) % (n * 2)
            f += [(p, q, p + n * 2), (q, q + n * 2, p + n * 2)]
    return np.array(v, float), np.array(f)


def _cubo():
    v = np.array([(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], float)
    f = np.array([(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)])
    return v, f


def _girar(v, ax, ay):
    cx, sx, cy, sy = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay)
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    return v @ rx.T @ ry.T


def _desenhar(W, H, fundo, objetos, luz):
    img = np.zeros((H, W, 3), np.float32)
    g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    img[:] = (np.array(fundo[0], np.float32) * (1 - g) + np.array(fundo[1], np.float32) * g)[:, None, :]
    z = np.full((H, W), 1e9, np.float32)
    for v0, f, escala, pos, cor, ax, ay, brilho in objetos:
        v = _girar(v0 * escala, ax, ay) + np.array(pos)
        cam = 6.0
        s = (cam * 0.9) / (cam + v[:, 2])
        base = min(W, H) * 0.5
        cx, cy = (0.74 * W, 0.5 * H) if W > H * 1.2 else (0.5 * W, 0.46 * H)      # no horizontal o painel fica à direita
        px = cx + v[:, 0] * s * base
        py = cy - v[:, 1] * s * base
        for a, b, c in f:
            p0, p1, p2 = v[a], v[b], v[c]
            n = np.cross(p1 - p0, p2 - p0)
            ln = np.linalg.norm(n)
            if ln == 0:
                continue
            n /= ln
            if n[2] > 0:
                continue
            xs, ys = (px[a], px[b], px[c]), (py[a], py[b], py[c])
            x0, x1 = max(int(min(xs)), 0), min(int(max(xs)) + 1, W)
            y0, y1 = max(int(min(ys)), 0), min(int(max(ys)) + 1, H)
            if x0 >= x1 or y0 >= y1:
                continue
            den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
            if abs(den) < 1e-9:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1, dtype=np.float32) + .5, np.arange(y0, y1, dtype=np.float32) + .5)
            l1 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / den
            l2 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / den
            l3 = 1 - l1 - l2
            prof = l1 * p0[2] + l2 * p1[2] + l3 * p2[2]
            ok = (l1 >= 0) & (l2 >= 0) & (l3 >= 0) & (prof < z[y0:y1, x0:x1])
            if not ok.any():
                continue
            difusa = max(0.0, float(-n @ luz))
            cor_f = np.array(cor, np.float32) * (0.28 + 0.72 * difusa)
            if brilho:                                     # brilho de plástico: reflexo branco onde a luz bate de frente
                meio = -luz + np.array([0, 0, -1.0]); meio /= np.linalg.norm(meio)
                cor_f = cor_f + 255 * brilho * max(0.0, float(n @ meio)) ** 24
            z[y0:y1, x0:x1][ok] = prof[ok]
            img[y0:y1, x0:x1][ok] = cor_f
    return np.clip(img, 0, 255).astype(np.uint8)


def _cena(eid, pal, ph):
    """Objetos no instante de fase ph (0..2π). Tudo periódico: o loop emenda sem salto. Cabem na faixa entre o título e o destaque."""
    p0, p1, p2 = [_hex(c) for c in pal]
    if eid == 'cinema3d':
        return ((p0, tuple(int(c * 0.35 + 40) for c in p0)),
                [(_ESF, _ESF_F, 0.6, (0, 0.15, 0), p1, 0.3, ph, 0.0),
                 (_CUB, _CUB_F, 0.25, (0.95 * math.cos(ph), -0.75, 0.95 * math.sin(ph)), p2, ph * 2, ph * 3, 0.0)])
    if eid == 'brinquedo_blocos':
        return (((250, 240, 225), (205, 220, 235)),
                [(_CUB, _CUB_F, 0.34, (0, -0.34, 0), p0, 0.35, ph, 0.15), (_CUB, _CUB_F, 0.27, (0, 0.27, 0), p1, 0.35, -ph, 0.15),
                 (_CUB, _CUB_F, 0.2, (0, 0.74, 0), p2, 0.35, ph * 2, 0.15)])
    if eid == 'plastico3d':
        return ((p0, tuple(int(c * 0.6) for c in p0)),
                [(_ESF, _ESF_F, 0.5, (0, -0.4, 0), p1, 0, ph, 0.9), (_ESF, _ESF_F, 0.34, (0, 0.42, 0), p2, 0, ph, 0.9),
                 (_ESF, _ESF_F, 0.06, (-0.12, 0.5, -0.3), (30, 30, 30), 0, 0, 0.5), (_ESF, _ESF_F, 0.06, (0.12, 0.5, -0.3), (30, 30, 30), 0, 0, 0.5)])
    # retro3d_2000: poucos triângulos, sem brilho, resolução baixa
    return ((p0, tuple(min(255, c + 40) for c in p0)),
            [(_ESF_B, _ESF_B_F, 0.6, (0, 0.15, 0), p2, 0.4, ph, 0.0), (_CUB, _CUB_F, 0.28, (0.95 * math.cos(ph), -0.75, 0.95 * math.sin(ph)), p1, ph, ph * 2, 0.0)])


if np is not None:
    _ESF, _ESF_F = _esfera(14)
    _ESF_B, _ESF_B_F = _esfera(6)
    _CUB, _CUB_F = _cubo()


def caminho(eid: str, W: int, H: int, pal: list) -> Path:
    h = hashlib.sha256(f'{VERSAO}|{eid}|{W}x{H}|{pal[:3]}'.encode()).hexdigest()[:16]
    return CACHE / f'{eid}-{W}x{H}-{h}.mp4'


def gerar_loop(eid: str, W: int, H: int, pal: list, cancelado=None, progresso=None) -> Path:
    """Desenha o loop de 4 s (se ainda não existe) e devolve o arquivo. Levanta InterruptedError se cancelado."""
    if np is None:
        raise RuntimeError('Os estilos 3D precisam do numpy (pkg install python-numpy).')
    arq = caminho(eid, W, H, pal)
    if arq.exists() and arq.stat().st_size > 1000:
        return arq
    CACHE.mkdir(parents=True, exist_ok=True)
    retro = eid == 'retro3d_2000'
    fator = (0.25 if retro else 0.5)
    w, h = max(2, int(W * fator) // 2 * 2), max(2, int(H * fator) // 2 * 2)
    luz = np.array([-0.45, -0.7, 0.55]); luz /= np.linalg.norm(luz)      # direção em que a luz viaja: de cima/esquerda, para dentro da cena
    tmp = arq.with_suffix('.tmp.mp4')
    filtro = f'scale={W}:{H}:flags={"neighbor" if retro else "lanczos"}'
    ff = subprocess.Popen(['ffmpeg', '-nostdin', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-r', str(FPS), '-i', '-',
                           '-vf', filtro, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'veryfast', '-crf', '20', '-g', str(FPS), str(tmp)],
                          stdin=subprocess.PIPE)
    n = int(PERIODO * FPS)
    try:
        for q in range(n):
            if cancelado and cancelado():
                raise InterruptedError()
            fundo, objetos = _cena(eid, pal, 2 * math.pi * q / n)
            ff.stdin.write(_desenhar(w, h, fundo, objetos, luz).tobytes())
            if progresso:
                progresso((q + 1) / n)
        ff.stdin.close()
        if ff.wait() != 0:
            raise RuntimeError('O FFmpeg não conseguiu gravar o fundo 3D.')
    except BaseException:
        try:
            ff.kill()
        except OSError:
            pass
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(arq)
    return arq
