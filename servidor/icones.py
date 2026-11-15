"""Pictogramas desenhados por código (só biblioteca padrão) para preencher o painel das cenas sem imagem.

A cena ganha um ícone ligado ao assunto (lâmpada, relógio, gráfico...), escolhido por palavras do título e do texto.
"""
from __future__ import annotations

import math
import unicodedata

import raster

S = 240

# palavras (sem acento) -> ícone. A primeira que bater vence; sem nenhuma, o ícone sai do próprio texto.
PALAVRAS = [
    ('relogio', ('tempo', 'hora', 'minuto', 'segundo', 'ano', 'anos', 'dia', 'dias', 'seculo', 'historia', 'idade', 'antigo', 'passado', 'futuro')),
    ('grafico', ('cresc', 'aument', 'dinheiro', 'lucro', 'preco', 'milh', 'bilh', 'por cento', '%', 'mercado', 'venda', 'rico', 'salario', 'economia', 'numero')),
    ('raio', ('energia', 'eletric', 'raio', 'rapido', 'veloc', 'forca', 'poder', 'trov', 'luz', 'bateria')),
    ('globo', ('mundo', 'terra', 'planeta', 'pais', 'global', 'oceano', 'continente', 'espaco', 'universo', 'ceu', 'natureza')),
    ('gota', ('agua', 'chuva', 'mar', 'rio', 'gota', 'suor', 'oceano', 'molhad', 'liquid', 'beber')),
    ('coracao', ('amor', 'coracao', 'saude', 'vida', 'paix', 'sentiment', 'emoc', 'feliz', 'familia')),
    ('estrela', ('melhor', 'top', 'famos', 'estrela', 'sucesso', 'premio', 'campea', 'record', 'incrivel', 'maior')),
    ('lampada', ('ideia', 'descobr', 'inven', 'criar', 'cria', 'segredo', 'pensa', 'cerebro', 'mente', 'aprend', 'ciencia', 'por que', 'porque', 'como', 'curios')),
]
GERAIS = ('lampada', 'estrela', 'globo', 'raio')


def _sem_acento(t: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower()) if unicodedata.category(c) != 'Mn')


def escolher(texto: str) -> str:
    t = ' ' + _sem_acento(texto) + ' '
    for nome, chaves in PALAVRAS:
        if any(k in t for k in chaves):
            return nome
    return GERAIS[sum(map(ord, t)) % len(GERAIS)]


def desenhar(nome: str, c1: str, c2: str) -> raster.Tela:
    t = raster.Tela(S, S)
    a, b = raster.cor(c1), raster.cor(c2)
    m = S / 2
    if nome == 'lampada':
        for k in range(-2, 3):                                  # raios de luz
            ang = math.radians(-90 + k * 38)
            t.linha(m + math.cos(ang) * 84, 116 + math.sin(ang) * 84, m + math.cos(ang) * 104, 116 + math.sin(ang) * 104, b, 9)
        t.elipse(m, 116, 60, 60, a)
        t.retangulo(m - 30, 160, m + 30, 200, a, 4)
        t.elipse(m - 22, 98, 12, 18, (255, 255, 255, 110))
        for k, y in enumerate((172, 187, 202)):
            t.retangulo(m - 32 + k * 3, y, m + 32 - k * 3, y + 8, b, 4)
        t.retangulo(m - 13, 214, m + 13, 223, b, 4)
    elif nome == 'relogio':
        t.elipse(m, m, 108, 108, a)
        t.elipse(m, m, 90, 90, b)
        for k in range(12):
            ang = math.radians(k * 30)
            t.linha(m + math.cos(ang) * 76, m + math.sin(ang) * 76, m + math.cos(ang) * 84, m + math.sin(ang) * 84, a, 6 if k % 3 == 0 else 3)
        t.linha(m, m, m, m - 62, a, 9)
        t.linha(m, m, m + 44, m + 12, a, 9)
        t.elipse(m, m, 9, 9, a)
    elif nome == 'grafico':
        for k, h in enumerate((70, 112, 156)):
            t.retangulo(30 + k * 62, S - 30 - h, 76 + k * 62, S - 30, a if k < 2 else b, 8)
        t.linha(30, 130, 100, 84, b, 10)
        t.linha(100, 84, 140, 108, b, 10)
        t.linha(140, 108, 206, 36, b, 10)
        t.poligono([(214, 28), (176, 36), (206, 66)], b)
    elif nome == 'estrela':
        pts = []
        for k in range(10):
            r = 112 if k % 2 == 0 else 46
            ang = math.radians(-90 + k * 36)
            pts.append((m + math.cos(ang) * r, m + 6 + math.sin(ang) * r))
        t.poligono(pts, a)
        pts2 = [(m + (x - m) * 0.55, m + 6 + (y - m - 6) * 0.55) for x, y in pts]
        t.poligono(pts2, b)
    elif nome == 'raio':
        t.poligono([(138, 8), (52, 130), (112, 130), (88, 232), (190, 96), (128, 96)], a)
        t.poligono([(130, 40), (84, 112), (122, 112), (110, 170), (156, 104), (116, 104)], b)
    elif nome == 'globo':
        t.elipse(m, m, 108, 108, a)
        for cx, cy, rx, ry in ((80, 90, 34, 26), (150, 80, 30, 22), (110, 150, 40, 30), (170, 150, 22, 28), (60, 150, 18, 20)):
            t.elipse(cx, cy, rx, ry, b)
        t.elipse(m, m, 108, 108, (255, 255, 255, 150), 5)
        t.elipse(m, m, 44, 108, (255, 255, 255, 90), 3)
    elif nome == 'gota':
        t.poligono([(m, 14), (m - 78, 128), (m + 78, 128)], a)
        t.elipse(m, 142, 78, 78, a)
        t.elipse(m - 28, 142, 14, 30, b)
    elif nome == 'coracao':
        t.elipse(m - 46, 92, 56, 56, a)
        t.elipse(m + 46, 92, 56, 56, a)
        t.poligono([(m - 98, 118), (m + 98, 118), (m, 218)], a)
        t.elipse(m - 58, 78, 14, 20, b)
    return t
