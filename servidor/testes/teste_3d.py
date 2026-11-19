"""Teste do motor 3D no celular (Termux). Não altera nada do servidor.

Rodar:  python servidor/testes/teste_3d.py
Precisa de: python-numpy (pkg install python-numpy) e ffmpeg.
Desenha uma esfera e um cubo girando com luz e sombra (rasterizador em software, sem placa de vídeo),
mede o tempo por quadro, grava ~/teste3d.mp4 e diz se vale a pena ligar os estilos 3D neste aparelho.
"""
import math
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import shutil
import subprocess
import sys
import time

try:
    import numpy as np
except ImportError:
    print('Falta o numpy. Rode:  pkg install -y python-numpy   e tente de novo.')
    sys.exit(2)

if not shutil.which('ffmpeg'):
    print('Falta o ffmpeg. Rode:  pkg install -y ffmpeg   e tente de novo.')
    sys.exit(2)

W, H, FPS, QUADROS = 540, 960, 30, 60          # meia resolução: o FFmpeg amplia para 1080x1920 no vídeo final
SAIDA = os.path.join(os.path.expanduser('~'), 'teste3d.mp4')   # no Termux não existe /tmp


def esfera(n=14):
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


def cubo():
    v = np.array([(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], float)
    f = np.array([(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)])
    return v, f


def girar(v, ax, ay):
    cx, sx, cy, sy = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay)
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    return v @ rx.T @ ry.T


def desenhar(quadro, objetos, t):
    img = np.zeros((H, W, 3), np.float32)
    grad = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    img[:] = (np.array([11, 15, 26], np.float32) * (1 - grad) + np.array([40, 30, 70], np.float32) * grad)[:, None, :]
    z = np.full((H, W), 1e9, np.float32)
    luz = np.array([0.4, 0.7, -0.6]); luz /= np.linalg.norm(luz)
    for v0, f, escala, pos, cor, vel in objetos:
        v = girar(v0 * escala, t * 0.7 * vel, t * 1.1 * vel) + np.array(pos)
        cam = 6.0
        s = (cam * 0.9) / (cam + v[:, 2])
        px = W / 2 + v[:, 0] * s * W * 0.5
        py = H / 2 - v[:, 1] * s * W * 0.5
        for a, b, c in f:
            p0, p1, p2 = v[a], v[b], v[c]
            n = np.cross(p1 - p0, p2 - p0)
            ln = np.linalg.norm(n)
            if ln == 0:
                continue
            n /= ln
            if n[2] > 0:                       # de costas para a câmera
                continue
            xs, ys = (px[a], px[b], px[c]), (py[a], py[b], py[c])
            x0, x1 = max(int(min(xs)), 0), min(int(max(xs)) + 1, W)
            y0, y1 = max(int(min(ys)), 0), min(int(max(ys)) + 1, H)
            if x0 >= x1 or y0 >= y1:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1, dtype=np.float32) + .5, np.arange(y0, y1, dtype=np.float32) + .5)
            den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
            if abs(den) < 1e-9:
                continue
            l1 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / den
            l2 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / den
            l3 = 1 - l1 - l2
            dentro = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
            prof = l1 * p0[2] + l2 * p1[2] + l3 * p2[2]
            ok = dentro & (prof < z[y0:y1, x0:x1])
            if not ok.any():
                continue
            brilho = 0.25 + 0.75 * max(0.0, float(-n @ luz))
            z[y0:y1, x0:x1][ok] = prof[ok]
            img[y0:y1, x0:x1][ok] = np.array(cor, np.float32) * brilho
    return np.clip(img, 0, 255).astype(np.uint8)


def main():
    es_v, es_f = esfera()
    cu_v, cu_f = cubo()
    print(f'Desenhando {QUADROS} quadros {W}x{H} (esfera com {len(es_f)} triângulos + cubo)...')
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
                           '-i', '-', '-vf', 'scale=1080:1920:flags=lanczos', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'veryfast', SAIDA],
                          stdin=subprocess.PIPE)
    tempos = []
    for q in range(QUADROS):
        t = q / FPS
        objetos = [(es_v, es_f, 1.0, (0, 0.8, 0), (240, 180, 60), 1.0), (cu_v, cu_f, 0.55, (0.4, -1.6, -0.6), (90, 170, 240), 1.6)]
        t0 = time.time()
        quadro = desenhar(q, objetos, t)
        tempos.append(time.time() - t0)
        ff.stdin.write(quadro.tobytes())
    ff.stdin.close()
    ff.wait()
    media = sum(tempos) / len(tempos)
    por_seg = media * FPS
    print(f'\nTempo médio por quadro: {media * 1000:.0f} ms   (o pior: {max(tempos) * 1000:.0f} ms)')
    print(f'Cada segundo de vídeo leva cerca de {por_seg:.1f} s para desenhar.')
    print(f'Um vídeo de 45 s levaria cerca de {por_seg * 45 / 60:.1f} minutos só de 3D (sem voz e legenda).')
    print(f'Vídeo de teste: {SAIDA}   (abra no celular e veja se está bom)')
    if por_seg <= 6:
        print('RESULTADO: BOM. Dá para ligar os estilos 3D simples neste aparelho.')
    elif por_seg <= 15:
        print('RESULTADO: LENTO, mas possível. Serviria para vídeos curtos, produzidos em segundo plano.')
    else:
        print('RESULTADO: MUITO LENTO. Melhor manter o 3D desligado neste aparelho.')
    print('\nMande para o Claude o texto acima (de "Tempo médio" até "RESULTADO").')


main()
