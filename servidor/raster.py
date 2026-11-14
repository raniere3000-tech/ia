"""Desenho simples em memória e gravação de PNG (só biblioteca padrão).

Usado para as peças dos estilos por código (formas, bonequinho de palitos, balão de fala, retícula...).
As peças são desenhadas UMA vez em tamanho pequeno e o FFmpeg anima e compõe.
"""
from __future__ import annotations

import math
import random
import struct
import zlib
from pathlib import Path


def cor(hexa: str, alfa: int = 255) -> tuple:
    h = (hexa or '#000000').lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alfa
    except ValueError:
        return 0, 0, 0, alfa


class Tela:
    def __init__(self, w: int, h: int, fundo=(0, 0, 0, 0)):
        self.w, self.h = int(w), int(h)
        self.px = bytearray(bytes(fundo) * (self.w * self.h))

    def _misturar(self, x: int, y: int, c: tuple, cobertura: float = 1.0):
        if not (0 <= x < self.w and 0 <= y < self.h):
            return
        a = c[3] / 255 * cobertura
        if a <= 0:
            return
        i = (y * self.w + x) * 4
        p = self.px
        ad = p[i + 3] / 255
        ao = a + ad * (1 - a)
        if ao <= 0:
            return
        for k in range(3):
            p[i + k] = int((c[k] * a + p[i + k] * ad * (1 - a)) / ao)
        p[i + 3] = int(ao * 255)

    def retangulo(self, x0, y0, x1, y1, c, raio: float = 0):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        for y in range(max(0, y0), min(self.h, y1)):
            for x in range(max(0, x0), min(self.w, x1)):
                if raio:
                    cx = min(max(x, x0 + raio), x1 - raio - 1)
                    cy = min(max(y, y0 + raio), y1 - raio - 1)
                    d = math.hypot(x - cx, y - cy)
                    if d > raio + 0.5:
                        continue
                    self._misturar(x, y, c, min(1, raio + 0.5 - d) if d > raio - 0.5 else 1)
                else:
                    self._misturar(x, y, c)

    def elipse(self, cx, cy, rx, ry, c, borda: float = 0):
        for y in range(max(0, int(cy - ry - 1)), min(self.h, int(cy + ry + 2))):
            for x in range(max(0, int(cx - rx - 1)), min(self.w, int(cx + rx + 2))):
                d = math.hypot((x - cx) / max(rx, 0.5), (y - cy) / max(ry, 0.5))
                r = min(rx, ry)
                dist = (d - 1) * r          # distância aproximada até a borda, em pixels
                if borda:
                    if -borda - 0.5 <= dist <= 0.5:
                        self._misturar(x, y, c, min(1, 0.5 - dist) if dist > -0.5 else min(1, dist + borda + 0.5))
                elif dist <= 0.5:
                    self._misturar(x, y, c, min(1, 0.5 - dist))

    def linha(self, x0, y0, x1, y1, c, esp: float = 2, aspero: float = 0, semente: int = 1):
        rnd = random.Random(semente)
        mx0, mx1 = int(min(x0, x1) - esp - 1), int(max(x0, x1) + esp + 2)
        my0, my1 = int(min(y0, y1) - esp - 1), int(max(y0, y1) + esp + 2)
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy or 1
        for y in range(max(0, my0), min(self.h, my1)):
            for x in range(max(0, mx0), min(self.w, mx1)):
                t = max(0, min(1, ((x - x0) * dx + (y - y0) * dy) / L2))
                d = math.hypot(x - (x0 + t * dx), y - (y0 + t * dy))
                if d <= esp / 2 + 0.5:
                    cob = min(1, esp / 2 + 0.5 - d)
                    if aspero:
                        cob *= 1 - aspero * rnd.random()
                    self._misturar(x, y, c, cob)

    def poligono(self, pts: list, c):
        ys = [p[1] for p in pts]
        for y in range(max(0, int(min(ys))), min(self.h, int(max(ys)) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                (xa, ya), (xb, yb) = pts[i], pts[(i + 1) % n]
                if (ya <= y + 0.5 < yb) or (yb <= y + 0.5 < ya):
                    xs.append(xa + (y + 0.5 - ya) * (xb - xa) / (yb - ya))
            xs.sort()
            for a, b in zip(xs[::2], xs[1::2]):
                for x in range(max(0, int(a)), min(self.w, int(b) + 1)):
                    self._misturar(x, y, c)

    def salvar(self, arq: Path):
        linhas = b''.join(b'\x00' + bytes(self.px[y * self.w * 4:(y + 1) * self.w * 4]) for y in range(self.h))

        def bloco(tipo: bytes, dados: bytes) -> bytes:
            return struct.pack('>I', len(dados)) + tipo + dados + struct.pack('>I', zlib.crc32(tipo + dados) & 0xffffffff)
        png = b'\x89PNG\r\n\x1a\n' + bloco(b'IHDR', struct.pack('>IIBBBBB', self.w, self.h, 8, 6, 0, 0, 0)) + \
            bloco(b'IDAT', zlib.compress(linhas, 6)) + bloco(b'IEND', b'')
        tmp = Path(str(arq) + '.tmp')
        tmp.write_bytes(png)
        tmp.replace(arq)
        return arq
