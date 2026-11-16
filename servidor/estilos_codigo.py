"""Estilos visuais do EstúdioClip e o motor que transforma uma CENA (dados declarativos) em vídeo com FFmpeg.

Segurança: a IA nunca escreve código. Ela devolve só campos de texto e escolhas de uma lista
(validados em `validar_cena`). Este arquivo transforma esses campos em filtros do FFmpeg que nós
escrevemos. Nada vindo da IA vira comando, caminho de arquivo ou expressão.

Os 16 estilos aparecem no site com o status REAL de cada um:
  operacional  -> o servidor (Termux) já faz o vídeo neste estilo, só com FFmpeg
  beta         -> faz, mas ainda simples / precisa de mais testes no aparelho
  indisponivel -> ainda não existe motor que rode no celular; não é oferecido na produção
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import textwrap
from pathlib import Path

import icones
import motor3d
import raster
import rig2d

VERSAO_MOTOR = 9
FONTE = Path(__file__).parent / 'fontes' / 'Inter-Bold.otf'
FPS = 30

ESTILOS = [
    # id, nome, técnica, status, prioridade, descrição, paleta
    ('documentario', 'Documentário (fotos reais)', 'Foto em tela cheia com movimento de câmera, título forte e legenda grande', 'operacional', 'prioritária',
     'O visual dos canais de curiosidades: uma foto real ocupando a tela em cada cena, câmera que se move devagar, '
     'título no alto e legenda grande palavra por palavra. Melhor com a chave grátis do Pexels.', ['#0b0b0f', '#ffd23f', '#ffffff']),
    ('cinema3d', '3D de cinema', 'Objetos e câmera 3D com luz e material', 'indisponivel', 'avançada',
     'Precisa de um motor 3D. Ainda não há um que rode de forma estável no Termux; fica para depois de um teste no aparelho.', ['#0b0f1a', '#f2b544', '#e8eef9']),
    ('brinquedo_blocos', 'Blocos de brinquedo', 'Blocos modulares 3D articulados', 'indisponivel', 'avançada',
     'Depende do motor 3D (não validado no Android).', ['#d62828', '#f7c600', '#1d70b8']),
    ('plastico3d', 'Bonequinho de plástico', '3D estilizado com brilho de plástico', 'indisponivel', 'avançada',
     'Depende do motor 3D (não validado no Android).', ['#ffcf56', '#ff6f59', '#4ecdc4']),
    ('retro3d_2000', '3D anos 2000', 'Low-poly com texturas simples', 'indisponivel', 'intermediária',
     'Depende do motor 3D (não validado no Android).', ['#2b2d42', '#8d99ae', '#ef233c']),
    ('lousa_giz', 'Lousa de giz', 'Fundo de lousa, giz que escreve palavra por palavra', 'operacional', 'prioritária',
     'Texto escrito aos poucos em giz, sublinhado e poeira de giz. Bom para explicações.', ['#23382b', '#f2f2e9', '#f7d66b']),
    ('traco_neon', 'Traço neon', 'Traços e textos brilhantes sobre fundo escuro', 'operacional', 'prioritária',
     'Moldura e texto com brilho neon que pulsa. Bom para games e tecnologia.', ['#05010f', '#22e4ff', '#ff3df2']),
    ('quadrinhos', 'Quadrinhos', 'Quadro, retícula, balão de fala e onomatopeia', 'operacional', 'prioritária',
     'Quadro de HQ com retícula, balão com o texto e a palavra de destaque em onomatopeia.', ['#ffd23f', '#111111', '#ee4266']),
    ('vetor_chapado', 'Vetor chapado', 'Formas planas animadas e tipografia', 'operacional', 'prioritária',
     'Formas de cor sólida que entram deslizando, cartão com o título. Ideal para explicações e mascotes.', ['#3a86ff', '#ffbe0b', '#fb5607']),
    ('palitinho', 'Palitinho', 'Bonequinho de palitos com poses simples', 'beta', 'prioritária',
     'Bonequinho de palitos que gesticula ao lado do texto. Poses ainda simples.', ['#ffffff', '#111111', '#e63946']),
    ('pixel_art', 'Pixel art', 'Cena em baixa resolução ampliada sem suavizar', 'operacional', 'prioritária',
     'Tudo desenhado em blocos de pixel, paleta curta e personagem que pula.', ['#1b1b3a', '#ffd166', '#06d6a0']),
    ('papel_recortado', 'Papel recortado', 'Camadas de papel com sombra que balançam', 'operacional', 'prioritária',
     'Recortes de papel colorido com sombra sobre fundo de papel pardo.', ['#d9c3a0', '#e76f51', '#2a9d8f']),
    ('cartoon2d', 'Desenho animado 2D', 'Ilustração por IA com movimento de câmera', 'beta', 'intermediária',
     'Precisa de um gerador de imagem ligado (Gemini). Sem ele, este estilo não é usado.', ['#ffffff', '#ff8c42', '#3d5a80']),
    ('motion_graphics', 'Motion graphics', 'Números, barras e tipografia animada', 'operacional', 'prioritária',
     'Contador animado, barras que crescem e grade. Ideal para dados e curiosidades com números.', ['#0d1b2a', '#00f5d4', '#fee440']),
    ('parallax_25d', '2.5D / Parallax', 'Camadas em profundidade que andam em velocidades diferentes', 'beta', 'intermediária',
     'Montanhas em camadas com profundidade. Com imagem de IA, a imagem vira as camadas.', ['#14213d', '#fca311', '#e5e5e5']),
    ('quadro_branco', 'Quadro branco', 'Caneta que escreve no quadro e marca-texto', 'operacional', 'prioritária',
     'Texto escrito aos poucos em caneta azul com marca-texto na palavra de destaque.', ['#fbfbf8', '#1d3557', '#ffe066']),
    ('animado2d', 'Desenho animado com personagens', 'Personagens 2D articulados, boca pela voz e cenário em camadas', 'beta', 'prioritária',
     'Personagens próprios que andam, apontam, acenam e falam com a boca pela voz, em cenários simples. '
     'Use em Séries animadas para ter elenco fixo; sem série, aparece um apresentador. Só vista de frente.', ['#7ec8f2', '#ffffff', '#ff8c42']),
    ('mapas_animados', 'Mapas animados', 'Mapas vetoriais com rotas e marcadores', 'indisponivel', 'intermediária',
     'Precisa de uma base de mapas com licença de uso. Ainda não incluída.', ['#cfe8ef', '#2a6f97', '#e63946']),
]
CAMPOS = ('id', 'nome', 'tecnica', 'status', 'prioridade', 'descricao', 'paleta')
CAMERAS = ('parado', 'aproximar', 'afastar', 'panoramica')
PLANOS = ('WS', 'MS', 'CU', 'ECU')                       # aberto, médio, close, close extremo
ZOOM_PLANO = {'WS': 1.0, 'MS': 1.4, 'CU': 1.9, 'ECU': 2.6}
CLIMAS = ('nenhum', 'chuva', 'neve', 'poeira', 'neblina')       # partículas por cima da cena (só quando a cena pede)
LUZES = ('neutra', 'quente', 'fria', 'noite', 'dramatica')      # camada de cor
ANGULOS = ('normal', 'baixo', 'alto', 'inclinado')              # altura/inclinação da câmera em cada plano
LUZ_FILTROS = {'quente': ['colorbalance=rs=.07:gs=.02:bs=-.07:rm=.05:bm=-.05'], 'fria': ['colorbalance=rs=-.06:bs=.09:rm=-.04:bm=.06'],
               'noite': ['eq=brightness=-0.10:saturation=0.75', 'colorbalance=rs=-.05:bs=.12:bm=.08'],
               'dramatica': ['eq=contrast=1.22:saturation=1.1:brightness=-0.03', 'vignette=PI/4']}
GIRO = 0.09            # inclinação do plano 'inclinado' (radianos)
ZOOM_GIRO = 1.16       # zoom extra para o giro não mostrar bordas pretas
NOME_PLANO = {'WS': 'aberto', 'MS': 'médio', 'CU': 'close', 'ECU': 'close extremo'}
FORMATOS = {'9:16': (1080, 1920), '16:9': (1920, 1080), '1:1': (1080, 1080)}


def catalogo() -> list:
    out = []
    for e in ESTILOS:
        d = dict(zip(CAMPOS, e))
        if d['id'] in motor3d.ESTILOS_3D:
            if motor3d.disponivel():
                d['status'] = 'beta'
                d['descricao'] = ('Fundo 3D em loop de 4 s (desenhado por software, sem placa de vídeo), com o texto por cima. '
                                  'Lento: o primeiro uso de cada formato leva cerca de 30 s; depois fica guardado. Cenas de até 30 s.')
            else:
                d['descricao'] = 'Precisa do numpy no Termux: pkg install python-numpy'
        d['servidor'] = d['status'] != 'indisponivel'
        d['formatos'] = list(FORMATOS) if d['servidor'] else []
        d['custo'] = 'Só o processamento do celular' if d['id'] != 'cartoon2d' else 'Uma imagem de IA por cena (custo do Gemini)'
        d['precisa_imagem'] = d['id'] == 'cartoon2d'
        out.append(d)
    return out


def estilo(eid: str) -> dict:
    for d in catalogo():
        if d['id'] == eid:
            return d
    return next(d for d in catalogo() if d['id'] == 'vetor_chapado')


def utilizavel(eid: str, tem_imagem: bool = False) -> bool:
    e = estilo(eid)
    return e['id'] == eid and e['servidor'] and (tem_imagem or not e['precisa_imagem'])


# ---------------------------------------------------------------- validação da cena (o que a IA pode mandar)
def _txt(v, n: int) -> str:
    s = re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', ' ', str(v or '')).strip()
    return s[:n]


def _num(v, pad: float, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return pad


def validar_planos(lista) -> list:
    """Planos da cena (schema 2). Só campos de uma lista fechada e números dentro de faixas; o resto é descartado.
    inicio/fim são frações da cena (0 a 1), para continuarem certos quando a narração muda de duração."""
    out = []
    for k, p in enumerate(lista[:6] if isinstance(lista, list) else []):
        if not isinstance(p, dict):
            continue
        out.append({'id': re.sub(r'[^a-z0-9]', '', str(p.get('id') or ''))[:8] or f'p{k + 1}',
                    'plano': p.get('plano') if p.get('plano') in PLANOS else 'WS',
                    'camera': p.get('camera') if p.get('camera') in CAMERAS else 'aproximar',
                    'foco_x': _num(p.get('foco_x'), 0.5, 0.0, 1.0), 'foco_y': _num(p.get('foco_y'), 0.45, 0.0, 1.0),
                    'peso': _num(p.get('peso'), 1.0, 0.3, 3.0),
                    'busca': _txt(p.get('busca'), 60), 'intencao': _txt(p.get('intencao'), 120),
                    'personagem': re.sub(r'[^a-z0-9_-]', '', str(p.get('personagem') or '').lower())[:40]})
        # campos novos só entram quando usados: planos antigos continuam com a mesma chave de cache
        if p.get('angulo') in ANGULOS and p['angulo'] != 'normal':
            out[-1]['angulo'] = p['angulo']
        if p.get('luz') in LUZES:
            out[-1]['luz'] = p['luz']
        ch = validar_chaves(p.get('chaves'))
        if ch:
            out[-1]['chaves'] = ch
    return out


def validar_chaves(lista) -> list:
    """Quadros-chave do movimento de câmera dentro do plano: 2 a 4 pontos {t (0 a 1 do plano), zoom, x, y (0 a 1 da imagem)}."""
    out = []
    for k in (lista[:4] if isinstance(lista, list) else []):
        if isinstance(k, dict):
            out.append({'t': round(_num(k.get('t'), 0, 0, 1), 3), 'zoom': round(_num(k.get('zoom'), 1, 1, 3), 3),
                        'x': round(_num(k.get('x'), 0.5, 0, 1), 3), 'y': round(_num(k.get('y'), 0.45, 0, 1), 3)})
    out.sort(key=lambda k: k['t'])
    return out if len(out) >= 2 and out[-1]['t'] > out[0]['t'] else []


def expr_chaves(ch: list, campo: str, prog: str, mult: float = 1.0) -> str:
    """Expressão do FFmpeg que liga os quadros-chave em linha reta (prog vai de 0 a 1 ao longo do plano)."""
    pts = [(k['t'], k[campo] * mult) for k in ch]
    out = f'{pts[-1][1]:.4f}'
    for (t0, v0), (t1, v1) in reversed(list(zip(pts, pts[1:]))):
        out = f'if(lt({prog},{t1:.3f}),{v0:.4f}+({v1 - v0:.4f})*({prog}-{t0:.3f})/{max(t1 - t0, 0.001):.3f},{out})'
    return f'if(lt({prog},{pts[0][0]:.3f}),{pts[0][1]:.4f},{out})'


def filtro_angulo(angulo: str, W: int, H: int, en: str = '') -> str:
    """Câmera de baixo (linhas fecham para cima), de cima (fecham para baixo) ou inclinada. Os cantos vão para fora
    do quadro, então não aparece borda preta; o 'inclinado' depende do zoom extra ZOOM_GIRO aplicado antes."""
    e = f":enable='{en}'" if en else ''
    d = W * 0.09
    if angulo == 'baixo':
        return f'perspective=x0=0:y0=0:x1={W}:y1=0:x2={-d:.0f}:y2={H}:x3={W + d:.0f}:y3={H}:sense=destination{e}'
    if angulo == 'alto':
        return f'perspective=x0={-d:.0f}:y0=0:x1={W + d:.0f}:y1=0:x2=0:y2={H}:x3={W}:y3={H}:sense=destination{e}'
    if angulo == 'inclinado':
        return f'rotate={GIRO}:fillcolor=black{e}'
    return ''


def planos_auto(cena: dict, dur: float) -> list:
    """Sem planos escritos: corta a cena a cada ~2,6 s alternando aberto, médio e close (ritmo de vídeo curto)."""
    n = max(1, min(4, round(dur / 2.6)))
    seq = ('WS', 'MS', 'CU', 'MS') if (cena.get('camera') != 'afastar') else ('CU', 'MS', 'WS', 'MS')
    cams = ('aproximar', 'panoramica', 'aproximar', 'afastar')
    focos = ((0.5, 0.45), (0.42, 0.42), (0.58, 0.4), (0.5, 0.5))
    return [{'id': f'p{k + 1}', 'plano': seq[k], 'camera': cams[k], 'foco_x': focos[k][0], 'foco_y': focos[k][1], 'peso': 1.0, 'busca': '', 'intencao': ''}
            for k in range(n)]


def tempos_planos(planos: list, dur: float) -> list[tuple[float, float]]:
    tot = sum(p['peso'] for p in planos) or 1
    t, out = 0.0, []
    for p in planos:
        d = dur * p['peso'] / tot
        out.append((round(t, 3), round(min(dur, t + d), 3)))
        t += d
    return out


def validar_cena(c: dict, i: int = 0) -> dict:
    els = []
    for e in (c.get('elementos') or [])[:5] if isinstance(c.get('elementos'), list) else []:
        if isinstance(e, dict):
            try:
                valor = max(0.0, min(100.0, float(e.get('valor', 50))))
            except (TypeError, ValueError):
                valor = 50.0
            els.append({'rotulo': _txt(e.get('rotulo'), 18), 'valor': valor})
    num = c.get('numero')
    try:
        num = None if num in (None, '') else max(-1e9, min(1e9, float(num)))
    except (TypeError, ValueError):
        num = None
    try:
        dur = float(c.get('duracao_alvo') or c.get('duracao') or 0)
    except (TypeError, ValueError):
        dur = 0
    return {
        'id': re.sub(r'[^a-z0-9]', '', str(c.get('id') or ''))[:12] or f'c{i + 1}',
        'texto': _txt(c.get('texto') or c.get('fala'), 600),
        'titulo': _txt(c.get('titulo'), 70),
        'destaque': _txt(c.get('destaque'), 24),
        'numero': num, 'unidade': _txt(c.get('unidade'), 12),
        'elementos': els,
        'camera': c.get('camera') if c.get('camera') in CAMERAS else 'parado',
        'personagem': _txt(c.get('personagem'), 40), 'emocao': _txt(c.get('emocao'), 30),
        'busca': _txt(c.get('busca'), 60),
        'cenario': _txt(c.get('cenario'), 160), 'visual': _txt(c.get('visual') or c.get('prompt_visual'), 400),
        'movimento': _txt(c.get('movimento'), 160), 'enquadramento': _txt(c.get('enquadramento'), 60),
        'duracao_alvo': max(0.0, min(60.0, dur)),
        'estilo': c.get('estilo') if c.get('estilo') in [e[0] for e in ESTILOS] else '',
        'planos': validar_planos(c.get('planos')),
        'elenco': rig2d.validar_elenco(c.get('elenco'), None, max(1.0, min(60.0, dur or 60.0))),
        'cenario_id': re.sub(r'[^a-z0-9_-]', '', str(c.get('cenario_id') or '').lower())[:40],
        'voz': _txt(c.get('voz'), 20),
        'clima': c.get('clima') if c.get('clima') in CLIMAS else 'nenhum',
        'luz': c.get('luz') if c.get('luz') in LUZES else 'neutra',
    }


# ---------------------------------------------------------------- montagem do filtro
def _esc(p: Path | str) -> str:
    return str(p).replace('\\', '/').replace(':', '\\:').replace("'", "\\'").replace(',', '\\,')


def quebrar(texto: str, largura_px: float, tam: float) -> list[str]:
    por_linha = max(6, int(largura_px / (tam * 0.56)))
    return textwrap.wrap(texto, por_linha) or ['']


def _escalada_para(arq: Path, w: int, h: int) -> Path:
    out = arq.with_name(f'{arq.stem}-{w}x{h}.png')
    if not out.exists():
        import subprocess
        tmp = out.with_suffix('.tmp.png')
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(arq), '-vf', f'scale={w}:{h}:flags=bicubic', '-frames:v', '1', str(tmp)],
                       check=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
        tmp.replace(out)
    return out


def _escalada(arq: Path, esc: float) -> Path:
    """Cópia da peça já no tamanho da tela (feita uma vez e guardada), para o FFmpeg não reescalar a cada quadro."""
    esc = round(esc, 3)
    if abs(esc - 1) < 0.002:
        return arq
    out = arq.with_name(f'{arq.stem}@{esc}.png')
    if not out.exists():
        tmp = out.with_suffix('.tmp.png')
        import subprocess
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(arq), '-vf', f'scale=trunc(iw*{esc}/2)*2:trunc(ih*{esc}/2)*2:flags=bicubic',
                        '-frames:v', '1', str(tmp)], check=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
        tmp.replace(out)
    return out


class Comp:
    def __init__(self, W: int, H: int, dur: float, pasta: Path):
        self.W, self.H, self.dur, self.pasta = W, H, dur, pasta
        self.args: list[str] = []
        self.f: list[str] = []
        self.n = 0
        self.k = 0
        self.v = ''
        self.nt = 0
        self.efeitos = True
        self.sons: list[float] = []      # instantes de 'whoosh' (corte de plano)

    def _rot(self) -> str:
        self.k += 1
        return f'v{self.k}'

    def entrada(self, args: list) -> int:
        self.args += args
        self.n += 1
        return self.n - 1

    def fundo(self, cor: str, grad: tuple | None = None):
        c = cor.lstrip('#')
        if grad:
            i = self.entrada(['-f', 'lavfi', '-i', f'gradients=s={self.W}x{self.H}:c0=0x{grad[0].lstrip("#")}:c1=0x{grad[1].lstrip("#")}:speed=0.008:r={FPS}:d={self.dur:.3f}'])
        else:
            i = self.entrada(['-f', 'lavfi', '-i', f'color=c=0x{c}:s={self.W}x{self.H}:r={FPS}:d={self.dur:.3f}'])
        self.v = f'[{i}:v]'
        self.filtro('format=yuv420p')

    def fundo_video(self, arq: Path):
        """Fundo vindo de um vídeo em loop (usado pelos estilos 3D)."""
        i = self.entrada(['-stream_loop', '-1', '-i', str(arq)])
        self.v = f'[{i}:v]'
        self.filtro(f'scale={self.W}:{self.H},setsar=1,fps={FPS},format=yuv420p')

    def filtro(self, expr: str):
        r = self._rot()
        self.f.append(f'{self.v}{expr}[{r}]')
        self.v = f'[{r}]'

    def png(self, arq: Path, x: str, y: str, ini: float = 0, fade: float = 0.35, escala: tuple | None = None, vizinho: bool = False, fim: float | None = None):
        i = self.entrada(['-loop', '1', '-framerate', str(FPS), '-t', f'{self.dur:.3f}', '-i', str(arq)])
        cadeia = 'format=rgba'
        if escala:
            cadeia += f',scale={int(escala[0])}:{int(escala[1])}' + (':flags=neighbor' if vizinho else '')
        if fade:
            cadeia += f',fade=t=in:st={ini:.2f}:d={fade:.2f}:alpha=1'
        r = self._rot()
        self.f.append(f'[{i}:v]{cadeia}[{r}]')
        en = f"between(t,{ini:.2f},{fim:.2f})" if fim is not None else f'gte(t,{ini:.2f})'
        o = self._rot()
        self.f.append(f"{self.v}[{r}]overlay=x='{x}':y='{y}':eval=frame:enable='{en}'[{o}]")
        self.v = f'[{o}]'

    def peca_girando(self, arq: Path, esc: float, angulo: str, x: str, y: str, enable: str = ''):
        """Peça de personagem articulado: imagem com o pivô no centro, girada pelo ângulo (expressão de t) e posta em (x, y)."""
        arq = _escalada(arq, esc)
        i = self.entrada(['-loop', '1', '-framerate', str(FPS), '-t', f'{self.dur:.3f}', '-i', str(arq)])
        r = self._rot()
        gira = f",rotate=a='{angulo}':c=none:ow=iw:oh=ih" if angulo not in ('0', '0.0') else ''
        self.f.append(f'[{i}:v]format=rgba{gira}[{r}]')
        o = self._rot()
        en = f":enable='{enable}'" if enable else ''
        self.f.append(f"{self.v}[{r}]overlay=x='{x}':y='{y}':eval=frame{en}[{o}]")
        self.v = f'[{o}]'

    def imagem(self, arq: Path, x: int, y: int, w: int, h: int, camera: str, ini: float = 0, borda: str = ''):
        frames = max(1, int(self.dur * FPS))
        z = {'aproximar': f"1+0.12*on/{frames}", 'afastar': f"1.12-0.12*on/{frames}", 'panoramica': '1.12', 'parado': '1.0'}[camera]
        px = f"(iw-iw/zoom)*on/{frames}" if camera == 'panoramica' else 'iw/2-(iw/zoom/2)'
        i = self.entrada(['-i', str(arq)])
        r = self._rot()
        self.f.append(f"[{i}:v]scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
                      f"zoompan=z='{z}':x='{px}':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={FPS},format=rgba,"
                      f"fade=t=in:st={ini:.2f}:d=0.4:alpha=1[{r}]")
        if borda:
            self.f[-1] = self.f[-1][:-len(f'[{r}]')] + f",drawbox=x=0:y=0:w=iw:h=ih:color={borda}:t=8[{r}]"
        o = self._rot()
        self.f.append(f"{self.v}[{r}]overlay=x={x}:y={y}:eval=init:shortest=0[{o}]")
        self.v = f'[{o}]'

    def imagem_plano(self, arq: Path, ini: float, fim: float, plano: dict, primeiro: bool = False):
        """Um plano da cena em tela cheia: enquadramento (aberto/médio/close) em volta do foco, movimento da câmera
        e um pequeno 'soco' de zoom no corte, que dá a sensação de câmera viva."""
        W, H = self.W, self.H
        frames = max(2, int(round((fim - ini) * FPS)) + 1)
        z0 = min(ZOOM_PLANO.get(plano.get('plano'), 1.0), plano.get('_zmax') or 2.6)
        cam = plano.get('camera') or 'aproximar'
        mov = {'aproximar': f'{z0:.3f}+{z0 * 0.09:.3f}*on/{frames}', 'afastar': f'{z0 * 1.09:.3f}-{z0 * 0.09:.3f}*on/{frames}',
               'panoramica': f'{z0 * 1.06:.3f}', 'parado': f'{z0:.3f}'}[cam if cam in CAMERAS else 'aproximar']
        soco = '' if primeiro else f'+0.06*max(0,1-on/7)'
        fx, fy = plano.get('foco_x', 0.5), plano.get('foco_y', 0.45)
        cx = f'({fx - 0.07:.3f}+0.14*on/{frames})*iw' if cam == 'panoramica' else f'{fx:.3f}*iw'
        cy = f'{fy:.3f}*ih'
        ang = plano.get('angulo') or 'normal'
        zg = ZOOM_GIRO if ang == 'inclinado' else 1.0
        if plano.get('chaves'):       # movimento livre: os quadros-chave mandam no zoom e no centro
            prog = f'on/{max(1, frames - 1)}'
            mov = f"min({plano.get('_zmax') or 3.0:.3f},{expr_chaves(plano['chaves'], 'zoom', prog)})"
            cx, cy = f"({expr_chaves(plano['chaves'], 'x', prog)})*iw", f"({expr_chaves(plano['chaves'], 'y', prog)})*ih"
        z = f'({mov}{soco})*{zg}' if zg != 1 else f'{mov}{soco}'
        # inclinado: gira a foto antes do zoom e prende a janela no miolo, onde o giro não deixou canto preto
        giro = f'rotate={GIRO}:fillcolor=black,' if zg != 1 else ''
        mx, my = (f'iw*{(1 - 1 / zg) / 2:.4f}', f'ih*{(1 - 1 / zg) / 2:.4f}') if zg != 1 else ('0', '0')
        extra = filtro_angulo(ang, W, H) if ang in ('baixo', 'alto') else ''
        i = self.entrada(['-i', str(arq)])
        r = self._rot()
        self.f.append(f"[{i}:v]scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},{giro}"
                      f"zoompan=z='{z}':x='max({mx},min(iw-iw/zoom-{mx},{cx}-iw/zoom/2))':y='max({my},min(ih-ih/zoom-{my},{cy}-ih/zoom/2))':"
                      f"d={frames}:s={W}x{H}:fps={FPS},{extra + ',' if extra else ''}setpts=PTS-STARTPTS+{ini:.3f}/TB,format=yuv420p[{r}]")
        o = self._rot()
        self.f.append(f"{self.v}[{r}]overlay=0:0:eof_action=pass:enable='between(t,{ini:.3f},{fim + 0.04:.3f})'[{o}]")
        self.v = f'[{o}]'

    def _arq_texto(self, texto: str) -> Path:
        self.nt += 1
        arq = self.pasta / f'txt{self.nt}.txt'
        arq.write_text(texto, encoding='utf-8')
        return arq

    def texto(self, texto: str, x: str, y: str, tam: float, cor: str, ini: float = 0, fade: float = 0.4, borda: int = 0,
              cor_borda: str = '#000000', caixa: str = '', fim: float | None = None, sombra: int = 0, tam_expr: str = ''):
        if not texto.strip():
            return
        arq = self._arq_texto(texto)
        alpha = f"if(lt(t,{ini:.2f}),0,min(1,(t-{ini:.2f})/{max(fade, 0.01):.2f}))" if fade else '1'
        opts = [f"fontfile='{_esc(FONTE)}'", f"textfile='{_esc(arq)}'", 'expansion=none', f"fontsize={tam_expr or int(tam)}",
                f"fontcolor=0x{cor.lstrip('#')}", f"x={x}", f"y={y}", f"alpha='{alpha}'", f"line_spacing={int(tam * 0.18)}"]
        if borda:
            opts += [f'borderw={borda}', f"bordercolor=0x{cor_borda.lstrip('#')}"]
        if sombra:
            opts += [f'shadowx={sombra}', f'shadowy={sombra}', 'shadowcolor=black@0.45']
        if caixa:
            opts += ['box=1', f'boxcolor={caixa}', f'boxborderw={int(tam * 0.35)}']
        en = f"between(t,{ini:.2f},{fim:.2f})" if fim is not None else f'gte(t,{ini:.2f})'
        opts.append(f"enable='{en}'")
        self.filtro('drawtext=' + ':'.join(opts))

    def palavras(self, texto: str, x0: int, y0: int, largura: int, tam: float, cor: str, ini: float, fim_rev: float, **kw):
        """Escreve palavra por palavra (giz, caneta): cada prefixo aparece num intervalo."""
        pal = texto.split()
        if not pal:
            return
        passos = min(len(pal), 14)
        grupos = [pal[: max(1, round(len(pal) * (k + 1) / passos))] for k in range(passos)]
        dt = max(0.12, (fim_rev - ini) / passos)
        for k, g in enumerate(grupos):
            linhas = quebrar(' '.join(pal), largura, tam)
            # mantém a quebra de linha do texto inteiro (as palavras não pulam de linha enquanto escreve)
            restante = ' '.join(g)
            parcial = []
            for ln in linhas:
                if not restante:
                    break
                if restante.startswith(ln):
                    parcial.append(ln)
                    restante = restante[len(ln):].strip()
                else:
                    parcial.append(restante)
                    restante = ''
            t0 = ini + k * dt
            t1 = ini + (k + 1) * dt if k < passos - 1 else None
            self.texto('\n'.join(parcial), str(x0), str(y0), tam, cor, ini=t0, fade=0, fim=t1, **kw)

    def legenda(self, ass: Path):
        self.filtro(f"subtitles=filename='{_esc(ass)}':fontsdir='{_esc(FONTE.parent)}'")

    def comando(self, audio: Path | None, saida: Path) -> list[str]:
        cmd = ['ffmpeg', '-nostdin', '-y', '-v', 'error', *self.args]
        if audio:
            ia = self.n
            cmd += ['-i', str(audio)]
            afiltro = f'[{ia}:a]aresample=48000,aformat=channel_layouts=stereo,apad=whole_dur={self.dur:.3f}[a]'
        else:
            ia = self.n
            cmd += ['-f', 'lavfi', '-i', f'anullsrc=r=48000:cl=stereo:d={self.dur:.3f}']
            afiltro = f'[{ia}:a]anull[a]'
        if self.efeitos and self.sons:
            # som curto de transição nos cortes, baixinho por baixo da voz
            k = self.n + 1
            cmd += ['-f', 'lavfi', '-i', 'anoisesrc=d=0.4:c=pink:a=0.5:r=48000']
            ramos = []
            parts = [afiltro.replace('[a]', '[voz]')]
            parts.append(f'[{k}:a]highpass=f=500,lowpass=f=5000,afade=t=in:d=0.16,afade=t=out:st=0.16:d=0.24,volume=0.22,aformat=channel_layouts=stereo,asplit={len(self.sons)}' +
                         ''.join(f'[w{j}]' for j in range(len(self.sons))))
            for j, t in enumerate(self.sons):
                ms = max(0, int((t - 0.18) * 1000))
                parts.append(f'[w{j}]adelay={ms}|{ms}[d{j}]')
                ramos.append(f'[d{j}]')
            parts.append(f'[voz]{"".join(ramos)}amix=inputs={len(ramos) + 1}:duration=first:normalize=0[a]')
            afiltro = ';'.join(parts)
        final = self.v
        grafo = ';'.join(self.f + [f'{final}format=yuv420p,setsar=1[vout]', afiltro])
        return cmd + ['-filter_complex', grafo, '-map', '[vout]', '-map', '[a]', '-r', str(FPS), '-c:v', 'libx264', '-preset', 'veryfast',
                      '-crf', '22', '-pix_fmt', 'yuv420p', '-g', str(FPS * 2), '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-ac', '2',
                      '-t', f'{self.dur:.3f}', '-movflags', '+faststart', str(saida)]


# ---------------------------------------------------------------- legendas (ASS)
def _ass_t(t: float) -> str:
    t = max(0.0, t)
    return f'{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}'


def _ass_cor(h: str, a: int = 0) -> str:
    h = h.lstrip('#')
    return f'&H{a:02X}{h[4:6]}{h[2:4]}{h[0:2]}'.upper()


def _acento(cor: str) -> str:
    """Cor da palavra que está sendo falada: amarelo sobre texto claro, vermelho sobre texto escuro."""
    r, g, b = raster.cor(cor)[:3]
    return '#ffd23f' if (0.299 * r + 0.587 * g + 0.114 * b) > 120 else '#d62839'


def legenda_ass(texto: str, dur: float, W: int, H: int, cor: str, borda: str, caixa: bool, arq: Path, tamanho: float = 0.056, y_rel: float = 0.86):
    """Legenda grande com a palavra falada acesa (karaokê) e uma entrada com leve 'pop'. O tempo de cada palavra
    é proporcional ao tamanho dela dentro da fala da cena."""
    pal = texto.split()
    tam = int(min(W, H) * tamanho * (1.45 if H > W else 1.0))
    blocos, atual = [], []
    for p in pal:
        atual.append(p)
        if len(' '.join(atual)) > (20 if H > W else 36) or p.endswith(('.', '!', '?')):
            blocos.append(atual)
            atual = []
    if atual:
        blocos.append(atual)
    def peso_p(w):
        return len(w) + 1 + (4 if w.endswith(('.', '!', '?', ':')) else 2 if w.endswith((',', ';')) else 0)
    total = sum(sum(peso_p(w) for w in b) for b in blocos) or 1
    t = 0.04
    eventos = []
    for b in blocos:
        peso = sum(peso_p(w) for w in b)
        d = max(0.5, (dur - 0.32) * peso / total)
        partes = []
        for w in b:
            cs = max(6, int(round(d * 100 * peso_p(w) / peso)))
            partes.append('{\\k%d}%s' % (cs, w.replace('{', '(').replace('}', ')')))
        txt = '{\\fscx88\\fscy88\\t(0,140,\\fscx100\\fscy100)}' + ' '.join(partes)
        eventos.append(f'Dialogue: 0,{_ass_t(t)},{_ass_t(min(dur, t + d))},L,,0,0,0,,{txt}')
        t += d
    margem = int(H * (1 - y_rel))
    estilo_ln = (f'Style: L,Inter,{tam},{_ass_cor(_acento(cor))},{_ass_cor(cor)},{_ass_cor(borda)},{_ass_cor("#000000", 0x60)},-1,0,0,0,100,100,0,0,'
                 f'{3 if caixa else 1},{max(3, tam // 11)},0,2,{int(W * 0.06)},{int(W * 0.06)},{margem},1')
    arq.write_text('[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 0\n\n[V4+ Styles]\n'
                   'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, '
                   'ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n%s\n\n[Events]\n'
                   'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n%s\n' % (W, H, estilo_ln, '\n'.join(eventos)),
                   encoding='utf-8')
    return arq


# ---------------------------------------------------------------- peças desenhadas (PNG)
def _peca(pasta: Path, nome: str, desenhar) -> Path:
    arq = pasta / f'{nome}.png'
    if not arq.exists():
        desenhar().salvar(arq)
    return arq


def _circulo(pasta, cor, r=120):
    def d():
        t = raster.Tela(r * 2 + 4, r * 2 + 4)
        t.elipse(r + 2, r + 2, r, r, raster.cor(cor))
        return t
    return _peca(pasta, f'circ_{cor.strip("#")}_{r}', d)


def _cartao(pasta, w, h, cor, raio, sombra=True, nome='cartao'):
    esc = 4   # desenha em 1/4 e o FFmpeg amplia (rápido no celular)
    def d():
        t = raster.Tela(w // esc + 6, h // esc + 6)
        if sombra:
            t.retangulo(4, 5, w // esc + 4, h // esc + 5, (0, 0, 0, 70), raio / esc)
        t.retangulo(1, 1, w // esc, h // esc, raster.cor(cor), raio / esc)
        return t
    return _peca(pasta, f'{nome}_{cor.strip("#")}_{w}x{h}', d), (w + 6 * esc, h + 6 * esc)


def _linha_giz(pasta, w, cor):
    def d():
        t = raster.Tela(w // 2, 14)
        rnd = random.Random(7)
        x = 2
        while x < w // 2 - 6:
            nx = min(w // 2 - 4, x + rnd.randint(18, 40))
            t.linha(x, 7 + rnd.uniform(-1.5, 1.5), nx, 7 + rnd.uniform(-1.5, 1.5), raster.cor(cor, 230), 4, aspero=0.55, semente=x)
            x = nx
        return t
    return _peca(pasta, f'giz_{cor.strip("#")}_{w}', d), (w, 28)


def _degrade(pasta, alfa_max: int, para_baixo: bool):
    """Faixa preta que vai do transparente ao escuro (o FFmpeg estica para a largura da tela)."""
    def d():
        t = raster.Tela(4, 128)
        for y in range(128):
            k = y / 127 if para_baixo else 1 - y / 127
            t.retangulo(0, y, 4, y + 1, (0, 0, 0, int(alfa_max * k ** 1.6)))
        return t
    return _peca(pasta, f'degrade_{alfa_max}_{int(para_baixo)}', d)


def _reticula(pasta, cor):
    def d():
        t = raster.Tela(120, 120)
        for y in range(0, 120, 12):
            for x in range(0 if (y // 12) % 2 == 0 else 6, 120, 12):
                t.elipse(x + 3, y + 3, 2.6, 2.6, raster.cor(cor, 70))
        return t
    return _peca(pasta, f'ret_{cor.strip("#")}', d)


def _balao(pasta, w, h):
    esc = 3
    def d():
        tw, th = w // esc, h // esc
        t = raster.Tela(tw + 8, th + 30)
        t.elipse(tw / 2 + 4, th / 2 + 4, tw / 2, th / 2, (17, 17, 17, 255))
        t.poligono([(tw * 0.25, th * 0.8), (tw * 0.18, th + 26), (tw * 0.42, th * 0.9)], (17, 17, 17, 255))
        t.elipse(tw / 2 + 4, th / 2 + 4, tw / 2 - 3, th / 2 - 3, (255, 255, 255, 255))
        t.poligono([(tw * 0.27, th * 0.78), (tw * 0.21, th + 20), (tw * 0.39, th * 0.86)], (255, 255, 255, 255))
        return t
    return _peca(pasta, f'balao_{w}x{h}', d), (w + 8 * esc, h + 30 * esc)


def _palito(pasta, pose: int, cor: str):
    def d():
        t = raster.Tela(160, 260)
        c = raster.cor(cor)
        t.elipse(80, 40, 28, 28, c, borda=6)
        t.linha(80, 70, 80, 165, c, 7)
        if pose == 0:
            t.linha(80, 95, 35, 135, c, 7)
            t.linha(80, 95, 125, 135, c, 7)
        else:
            t.linha(80, 95, 30, 55, c, 7)
            t.linha(80, 95, 132, 120, c, 7)
        t.linha(80, 165, 45, 245, c, 7)
        t.linha(80, 165, 115, 245, c, 7)
        return t
    return _peca(pasta, f'palito{pose}_{cor.strip("#")}', d)


def _pixel_heroi(pasta, cor):
    mapa = ['..XXXX..', '.XXXXXX.', '.X.XX.X.', '.XXXXXX.', '..XXXX..', '.XXXXXX.', 'X.XXXX.X', '..X..X..']
    def d():
        t = raster.Tela(8, 8)
        c = raster.cor(cor)
        for y, ln in enumerate(mapa):
            for x, ch in enumerate(ln):
                if ch == 'X':
                    t.retangulo(x, y, x + 1, y + 1, c)
        return t
    return _peca(pasta, f'heroi_{cor.strip("#")}', d)


def _montanhas(pasta, w, h, cor, semente):
    esc = 4
    def d():
        tw, th = w // esc, h // esc
        t = raster.Tela(tw, th)
        rnd = random.Random(semente)
        fases = [rnd.uniform(0, 6) for _ in range(3)]
        pts = [(0, th)]
        for x in range(0, tw + 1, 4):
            y = th * 0.45 + sum(math.sin(x / tw * math.pi * 2 * (k + 1) + fases[k]) * th * 0.12 / (k + 1) for k in range(3))
            pts.append((x, y))
        pts.append((tw, th))
        t.poligono(pts, raster.cor(cor))
        return t
    return _peca(pasta, f'mont_{cor.strip("#")}_{semente}_{w}x{h}', d), (w, h)


# ---------------------------------------------------------------- estilos
def _layout(W, H):
    v = H > W
    return {
        'v': v, 'margem': int(W * 0.08),
        'titulo_y': int(H * (0.085 if v else 0.08)), 'titulo_tam': int(W * (0.082 if v else 0.042)),
        'painel': (int(W * 0.06), int(H * 0.235), int(W * 0.88), int(H * 0.43)) if v else (int(W * 0.52), int(H * 0.22), int(W * 0.42), int(H * 0.56)),
        'texto_larg': int(W * 0.84) if v else int(W * 0.42),
    }


# ---------------------------------------------------------------- foto -> estilo (remodela a imagem para ficar no estilo da cena)
def _duotone(bg: str, fg: str) -> str:
    """Mapa de duas cores: preto vira bg e branco vira fg (a luminosidade da imagem vira o desenho)."""
    b, f = raster.cor(bg)[:3], raster.cor(fg)[:3]
    return 'lutrgb=' + ':'.join(f"{k}='clip({b[i]}+val*({f[i] - b[i]})/255,0,255)'" for i, k in enumerate(('r', 'g', 'b')))


def _posterizar(n: int) -> str:
    q = 256 // n
    return 'lutrgb=' + ':'.join(f"{k}='trunc(val/{q})*{q}+{q // 2}'" for k in ('r', 'g', 'b'))


_TRACO = 'dilation=threshold0=255:coordinates=255,dilation=threshold0=255:coordinates=255,lutyuv=y=min(255\\,val*3)'


def _filtro_estilo(eid: str, w: int, h: int, pal: tuple) -> str | None:
    p0, p1, p2 = pal
    pre = f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1'
    if eid == 'vetor_chapado':
        return f'[0:v]{pre},gblur=sigma=3,eq=saturation=1.5:contrast=1.1,{_posterizar(5)}[o]'
    if eid == 'quadrinhos':
        return (f'[0:v]{pre},split[a][b];[a]format=gbrp,gblur=sigma=1.5,eq=saturation=1.7:contrast=1.25,{_posterizar(4)}[c];'
                f'[b]gblur=sigma=1.2,edgedetect=low=0.08:high=0.22,{_TRACO},negate,format=gbrp[e];[c]format=gbrp[c2];[c2][e]blend=all_mode=multiply,format=rgb24[o]')
    if eid == 'cartoon2d':
        return (f'[0:v]{pre},split[a][b];[a]format=gbrp,gblur=sigma=2,eq=saturation=1.4:contrast=1.1,{_posterizar(7)}[c];'
                f'[b]gblur=sigma=1.5,edgedetect=low=0.1:high=0.25,{_TRACO},negate,format=gbrp[e];[c]format=gbrp[c2];[c2][e]blend=all_mode=multiply,format=rgb24[o]')
    if eid == 'traco_neon':
        return (f'[0:v]{pre},gblur=sigma=1.6,edgedetect=low=0.05:high=0.16,{_TRACO},split[a][b];[b]gblur=sigma=7[g];'
                f'[a][g]blend=all_mode=lighten,eq=brightness=0.05,{_duotone("#05010f", p1)}[o]')
    if eid == 'lousa_giz':
        return f'[0:v]{pre},gblur=sigma=2,edgedetect=low=0.04:high=0.14,{_TRACO},noise=alls=18:allf=t,{_duotone(p0, p1)}[o]'
    if eid == 'quadro_branco':
        return f'[0:v]{pre},gblur=sigma=2,edgedetect=low=0.04:high=0.14,{_TRACO},{_duotone(p0, p1)}[o]'
    if eid == 'papel_recortado':
        return f'[0:v]{pre},gblur=sigma=2.5,eq=saturation=1.25:contrast=1.05,{_posterizar(5)},noise=alls=10:allf=u[o]'
    if eid == 'motion_graphics':
        return f'[0:v]{pre},format=gray,eq=contrast=1.35,format=rgb24,{_duotone(p0, p1)}[o]'
    if eid == 'pixel_art':
        return (f'[0:v]scale={w // 8}:{h // 8}:force_original_aspect_ratio=increase:flags=area,crop={w // 8}:{h // 8},setsar=1,split[a][b];'
                f'[a]palettegen=max_colors=14:stats_mode=single[p];[b][p]paletteuse=dither=bayer:bayer_scale=3,scale={w}:{h}:flags=neighbor[o]')
    if eid == 'documentario':
        return f'[0:v]{pre},eq=saturation=1.12:contrast=1.07:brightness=-0.02,unsharp=5:5:0.6,vignette=PI/4.5[o]'
    if eid == 'parallax_25d':
        return f'[0:v]{pre},eq=saturation=1.25:contrast=1.08,vignette=PI/5[o]'
    return None


def estilizar(eid: str, imagem: Path | None, pasta: Path, w: int, h: int, pal: tuple) -> Path | None:
    """Passa a foto pelo visual do estilo (posterizar, contornos, duas cores, pixel...). Sem filtro para o estilo, devolve a foto como veio."""
    if not imagem:
        return None
    graf = _filtro_estilo(eid, w, h, pal)
    if not graf:
        return imagem
    saida = pasta / f'estilizada-{eid}-{hashlib.sha1(str(imagem).encode()).hexdigest()[:8]}.png'
    import renderizador
    try:
        renderizador.rodar(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(imagem), '-filter_complex', graf, '-map', '[o]', '-frames:v', '1', str(saida)], tempo_max=180)
    except renderizador.ErroRender:
        return imagem          # se o filtro falhar a cena sai com a foto original, nunca sem imagem
    return saida


def _zoom_max(arq, W: int, H: int) -> float:
    """Quanto dá para aproximar a foto sem ficar borrada: depende do tamanho real dela."""
    try:
        import renderizador
        v = next(x for x in renderizador.sonda(Path(arq)).get('streams', []) if x.get('width'))
        lado = min(v['width'] / W, v['height'] / H)       # quanto a foto cobre a tela, no lado mais curto
        return max(1.3, min(2.6, lado * 1.6))
    except Exception:
        return 1.6


def montar(eid: str, cena: dict, W: int, H: int, dur: float, pasta: Path, imagem: Path | None, audio: Path | None, saida: Path, paleta: list | None = None,
           imagens_planos: list | None = None, efeitos: bool = True) -> list:
    """Devolve o comando do FFmpeg que faz o clipe desta cena. `imagens_planos`: foto própria de cada plano (ou None),
    usada pelo estilo documentário; sem ela, cada plano reenquadra a foto da cena."""
    e = estilo(eid)
    if not utilizavel(e['id'], bool(imagem)):
        e = estilo('vetor_chapado')
    p0, p1, p2 = (paleta or e['paleta'])[:3] if len(paleta or e['paleta']) >= 3 else e['paleta']
    L = _layout(W, H)
    imagem_original = imagem
    if imagem and e['id'] != 'cartoon2d':
        pw, ph = (W * 3 // 2, H * 3 // 2) if e['id'] == 'documentario' else (L['painel'][2], L['painel'][3])
        imagem = estilizar(e['id'], imagem, pasta, pw, ph, (p0, p1, p2))
    if e['id'] == 'documentario' and imagem:
        planos = cena.get('planos') or planos_auto(cena, dur)
        imgs = list(imagens_planos or [])[:len(planos)]
        imgs += [None] * (len(planos) - len(imgs))
        orig = [x or imagem_original for x in imgs]
        planos = [dict(p, _zmax=_zoom_max(o, W, H)) for p, o in zip(planos, orig)]
        cena = dict(cena, planos=planos, _imgs=[estilizar(e['id'], x, pasta, W * 3 // 2, H * 3 // 2, (p0, p1, p2)) if x else imagem for x in imgs])
    c = Comp(W, H, dur, pasta)
    c.efeitos = efeitos
    titulo = cena.get('titulo') or ''
    destaque = cena.get('destaque') or ''
    m = L['margem']
    tam = L['titulo_tam']
    fn = globals()['_e_' + e['id']]
    leg_cor, leg_borda, leg_caixa = fn(c, cena, L, W, H, dur, pasta, imagem, (p0, p1, p2), titulo, destaque, m, tam)
    if efeitos:
        _ambiente(c, cena, W, H, dur)
    if cena.get('texto'):
        extra = {'tamanho': 0.064, 'y_rel': 0.80 if H > W else 0.88} if e['id'] == 'documentario' else \
            {'tamanho': 0.06, 'y_rel': 0.885 if H > W else 0.95} if e['id'] == 'animado2d' else {}
        c.legenda(legenda_ass(cena['texto'], dur, W, H, leg_cor, leg_borda, leg_caixa, pasta / 'legenda.ass', **extra))
    return c.comando(audio, saida)


def _camada_clima(tipo: str, w: int, h: int) -> Path:
    """Partículas desenhadas uma vez (semente fixa: o mesmo vídeo sai igual sempre) num ladrilho que se repete ao rolar."""
    pasta = Path(os.getenv('DADOS', str(Path.home() / '.estudioclip'))) / 'efeitos'
    pasta.mkdir(parents=True, exist_ok=True)
    horizontal = tipo == 'neblina'
    tw, th = (w * 2, h) if horizontal else (w, h * 2)
    arq = pasta / f'clima-{tipo}-{tw}x{th}-v1.png'
    if arq.exists():
        return arq
    rnd = random.Random(7)
    t = raster.Tela(tw, th)
    n = {'chuva': 170, 'neve': 110, 'poeira': 80, 'neblina': 16}[tipo]
    for _ in range(n):
        x, y = rnd.uniform(0, w if horizontal else tw), rnd.uniform(0, h if not horizontal else th)
        for dx, dy in ((0, 0), (w, 0)) if horizontal else ((0, 0), (0, h)):
            if tipo == 'chuva':
                comp = rnd.uniform(8, 16) if dy == 0 else comp
                t.linha(x + dx, y + dy, x + dx - comp * 0.18, y + dy + comp, raster.cor('#dbe9ff', 120), esp=1.1)
            elif tipo == 'neve':
                r = rnd.uniform(0.8, 2.2) if dy == 0 else r
                t.elipse(x + dx, y + dy, r, r, raster.cor('#ffffff', 215))
            elif tipo == 'poeira':
                r = rnd.uniform(0.5, 1.2) if dy == 0 else r
                t.elipse(x + dx, y + dy, r, r, raster.cor('#ffe7ad', 130))
            else:
                rx, ry = (rnd.uniform(w * 0.18, w * 0.4), rnd.uniform(h * 0.03, h * 0.07)) if dx == 0 else (rx, ry)
                t.elipse(x + dx, y + dy, rx, ry, raster.cor('#ffffff', 20))
    t.salvar(arq)
    return arq


def _ambiente(c, cena, W, H, dur):
    """Luz (camada de cor) e clima (chuva, neve, poeira, neblina). Só entra o que a cena pediu."""
    luz = cena.get('luz') or 'neutra'
    planos = cena.get('planos') or []
    if any(p.get('luz') for p in planos):
        # luz por plano: cada trecho usa a luz do seu plano (ou a da cena, se o plano não escolheu)
        for p, (t0, t1) in zip(planos, tempos_planos([dict(p, peso=p.get('peso', 1.0)) for p in planos], dur)):
            fs = LUZ_FILTROS.get(p.get('luz') or luz) or []
            if fs:
                fim = dur + 1 if p is planos[-1] else t1
                c.filtro(','.join(f"{f}:enable='between(t,{t0:.3f},{fim:.3f})'" for f in fs))
    elif luz in LUZ_FILTROS:
        c.filtro(','.join(LUZ_FILTROS[luz]))
    clima = cena.get('clima') or 'nenhum'
    if clima not in CLIMAS or clima == 'nenhum':
        return
    w, h = max(64, W // 4), max(64, H // 4)
    arq = _camada_clima(clima, w, h)
    if clima == 'neblina':
        c.png(arq, f'-mod(t*{W * 0.04:.1f},{W})', '0', 0, 0.6, (W * 2, H))
        return
    vel = {'chuva': H * 1.6, 'neve': H * 0.12, 'poeira': -H * 0.04}[clima]
    y = f'-{H}+mod(t*{vel:.1f},{H})' if vel > 0 else f'-mod(t*{-vel:.1f},{H})'
    x = f'{W * 0.02:.1f}*sin(t*0.7)' if clima != 'chuva' else '0'
    c.png(arq, x, y, 0, 0.3, (W, H * 2))


def _y_dest(L, H):
    x, y, w, h = L['painel']
    return y + h + int(L['titulo_tam'] * 0.75) if L['v'] else int(H * 0.82)


def _imagem_painel(c, imagem, L, cena, borda=''):
    if imagem:
        x, y, w, h = L['painel']
        c.imagem(imagem, x, y, w, h, cena.get('camera') or 'aproximar', 0.3, borda)
        return True
    return False


def _e_vetor_chapado(c, cena, L, W, H, dur, pasta, imagem, pal, titulo, destaque, m, tam):
    p0, p1, p2 = pal
    c.fundo(p0)
    r = int(W * 0.22)
    c.png(_circulo(pasta, p1, 100), f"W-w*0.75+12*sin(t*1.6)", f"H*0.62-h/2+10*cos(t*1.3)", 0.0, 0.5, (r * 2, r * 2))
    c.png(_circulo(pasta, p2, 100), f"-w*0.35", f"H*0.05+14*sin(t*1.1)", 0.15, 0.5, (int(r * 1.4), int(r * 1.4)))
    cw, ch = int(W - 2 * m), int(tam * 3.4)
    arq, (sw, sh) = _cartao(pasta, cw, ch, '#ffffff', 28)
    c.png(arq, f"{m - 12}", f"if(lt(t,0.5),H,{L['titulo_y'] - 20}+(H-{L['titulo_y'] - 20})*max(0,1-t/0.5)^3)", 0, 0, (sw, sh))
    if not _imagem_painel(c, imagem, L, cena, 'white'):
        _barras(c, cena, L, W, H, pal, 0.6)
    ln = quebrar(titulo, cw - 60, tam)[:2]
    c.texto('\n'.join(ln), f'{m + 30}', f"{L['titulo_y'] + int(tam * 0.4)}", tam, '#1b1b1b', ini=0.45)
    if destaque:
        c.texto(destaque.upper(), '(w-text_w)/2', f'{_y_dest(L, H)}', tam * 0.8, '#ffffff', ini=0.9, borda=6, cor_borda=p2)
    return '#ffffff', '#111111', True


def _heroi(c, cena, L, pal, ini):
    """Cena sem imagem nem barras: um pictograma ligado ao assunto, que entra, flutua e ganha anéis, em vez de um painel vazio."""
    x, y, w, h = L['painel']
    lado = int(min(w, h) * 0.9)
    nome = icones.escolher(f"{cena.get('titulo', '')} {cena.get('destaque', '')} {cena.get('texto', '')}")
    cor1, cor2 = pal[1], pal[2]
    arq = c.pasta / f'ico_{nome}_{cor1.strip("#")}_{cor2.strip("#")}.png'
    if not arq.exists():
        icones.desenhar(nome, cor1, cor2).salvar(arq)
    cx, cy = x + w // 2, y + h // 2
    disco = _circulo(c.pasta, cor2, 120)
    dl = int(lado * 1.05)
    c.png(disco, f'{cx - dl // 2}', f'{cy - dl // 2}', ini, 0.4, (dl, dl))      # disco de fundo
    ponto = _circulo(c.pasta, cor1, 14)
    for k in range(3):                                                         # três pontos que giram em volta
        raio = dl * 0.62
        fase = k * 2.094
        c.png(ponto, f'{cx - 14}+{raio:.0f}*cos(t*1.6+{fase:.3f})', f'{cy - 14}+{raio * 0.55:.0f}*sin(t*1.6+{fase:.3f})', ini + 0.2, 0.3, (28, 28))
    c.png(arq, f'{cx - lado // 2}', f'{cy - lado // 2}+{lado * 0.035:.0f}*sin(t*2.4)', ini, 0.35, (lado, lado))


def _barras(c, cena, L, W, H, pal, ini):
    els = cena.get('elementos') or []
    if not els:
        _heroi(c, cena, L, pal, ini)
        return
    x, y, w, h = L['painel']
    n = len(els)
    bw = int(w / (n * 1.6))
    for k, e in enumerate(els):
        bh = max(12, int(h * 0.8 * e['valor'] / 100))
        arq, (sw, sh) = _cartao(c.pasta, bw, bh, pal[(k % 2) + 1], 10, False, f'barra{k}')
        bx = x + int(k * bw * 1.6 + bw * 0.3)
        t0 = ini + k * 0.15
        c.png(arq, str(bx), f"{y + h}-{sh}*min(1,max(0,(t-{t0:.2f})/0.6))", t0, 0.1, (sw, sh))
        if e['rotulo']:
            c.texto(e['rotulo'], f'{bx}', f'{y + h + 14}', max(22, int(L["titulo_tam"] * 0.42)), '#ffffff', ini=t0 + 0.3, borda=3)
    # base cobre a parte da barra que ainda está "abaixo do chão"
    c.filtro(f"drawbox=x={x}:y={y + h}:w={w}:h=6:color=white@0.9:t=fill")


def _e_lousa_giz(c, cena, L, W, H, dur, pasta, imagem, pal, titulo, destaque, m, tam):
    p0, p1, p2 = pal
    c.fundo(p0)
    c.filtro('noise=alls=9:allf=t+u')
    c.filtro(f"drawbox=x=0:y=0:w=iw:h=ih:color=0x6b4423:t={int(min(W, H) * 0.035)}")
    c.filtro(f"drawbox=x={int(min(W, H) * 0.035)}:y={int(min(W, H) * 0.035)}:w=iw-{int(min(W, H) * 0.07)}:h=ih-{int(min(W, H) * 0.07)}:color=0x3e2a14@0.6:t=4")
    fim_rev = min(dur * 0.55, 0.4 + 0.22 * len(titulo.split()))
    c.palavras(titulo, m + 10, L['titulo_y'], W - 2 * m, tam, p1, 0.3, fim_rev)
    n_lin = len(quebrar(titulo, W - 2 * m, tam))
    arq, (sw, sh) = _linha_giz(pasta, int(W * 0.6), p2)
    c.png(arq, f'{m}', f"{L['titulo_y'] + int(n_lin * tam * 1.2) + 10}", fim_rev, 0.5, (sw, sh))
    if not _imagem_painel(c, imagem, L, cena, '0xf2f2e9'):
        _barras(c, cena, L, W, H, (p0, p1, p2), fim_rev)
    if destaque:
        c.texto(destaque, '(w-text_w)/2', f'{_y_dest(L, H)}', tam * 1.15, p2, ini=fim_rev + 0.2, fade=0.6)
    return p1, '#1a2a20', False


def _e_quadro_branco(c, cena, L, W, H, dur, pasta, imagem, pal, titulo, destaque, m, tam):
    p0, p1, p2 = pal
    c.fundo(p0)
    c.filtro('drawgrid=w=60:h=60:t=1:c=0x1d3557@0.05')
    fim_rev = min(dur * 0.55, 0.4 + 0.25 * len(titulo.split()))
    if destaque:
        dw = int(len(destaque) * tam * 0.62) + 40
        arq, (sw, sh) = _cartao(pasta, dw, int(tam * 1.25), p2, 6, False, 'marca')
        c.png(arq, f'(W-{sw})/2', f'{_y_dest(L, H) - 10}', fim_rev, 0.25, (sw, sh))
        c.texto(destaque, '(w-text_w)/2', f'{_y_dest(L, H) + int(tam * 0.1)}', tam, p1, ini=fim_rev + 0.15, fade=0.2)
    c.palavras(titulo, m, L['titulo_y'], W - 2 * m, tam, p1, 0.3, fim_rev)
    if not _imagem_painel(c, imagem, L, cena, '0x1d3557'):
        _barras(c, cena, L, W, H, (p0, p1, '#457b9d'), fim_rev)
    return p1, '#ffffff', False


def _e_traco_neon(c, cena, L, W, H, dur, pasta, imagem, pal, titulo, destaque, m, tam):
    p0, p1, p2 = pal
    c.fundo(p0)
    x, y, w, h = L['painel']
    c.filtro(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=0x{p1.lstrip('#')}@'0.6+0.4*abs(sin(t*2))':t=10:enable='gte(t,0.2)'".replace("@'0.6+0.4*abs(sin(t*2))'", '@0.9'))
    c.filtro(f"drawbox=x={m // 2}:y={m // 2}:w=iw-{m}:h=ih-{m}:color=0x{p2.lstrip('#')}@0.8:t=6")
    _imagem_painel(c, imagem, L, cena) or _barras(c, cena, L, W, H, (p0, p1, p2), 0.5)
    ln = quebrar(titulo, W - 2 * m, tam)
    c.texto('\n'.join(ln), '(w-text_w)/2', f"{L['titulo_y']}", tam, p2, ini=0.25)
    if destaque:
        c.texto(destaque.upper(), '(w-text_w)/2', f'{_y_dest(L, H)}', tam * 0.9, p1, ini=0.8)
    # brilho: borra uma cópia e soma por cima (efeito neon)
    r1, r2, r3 = c._rot(), c._rot(), c._rot()
    c.f.append(f'{c.v}split[{r1}][{r2}]')
    c.f.append(f'[{r2}]gblur=sigma={max(6, W // 90)}[{r3}]')
    o = c._rot()
    c.f.append(f'[{r1}][{r3}]blend=all_mode=screen:all_opacity=0.6[{o}]')
    c.v = f'[{o}]'
    c.filtro("eq=brightness='0.02*sin(t*6)':eval=frame")
    return p1, '#000000', False


def _e_quadrinhos(c, cena, L, W, H, dur, pasta, imagem, pal, titulo, destaque, m, tam):
    p0, p1, p2 = pal
    c.fundo(p0)
    ret = _reticula(pasta, p1)
    for yy in range(0, H, 480):
        for xx in range(0, W, 480):
            c.png(ret, str(xx), str(yy), 0, 0, (480, 480))
    c.filtro(f"drawbox=x={m // 2}:y={m // 2}:w=iw-{m}:h=ih-{m}:color=0x{p1.lstrip('#')}:t={max(8, W // 90)}")
    _imagem_painel(c, imagem, L, cena, '0x111111') or _barras(c, cena, L, W, H, (p0, p1, p2), 0.6)
    bw, bh = int(W * 0.84), int(tam * 4.2)
    arq, (sw, sh) = _balao(pasta, bw, bh)
    c.png(arq, f'(W-{sw})/2', f"{L['titulo_y'] - 30}", 0.15, 0.2, (sw, sh))
    ln = quebrar(titulo, bw * 0.72, tam * 0.85)[:3]
    c.texto('\n'.join(ln).upper(), '(w-text_w)/2', f"{L['titulo_y'] + int(bh / 2 - len(ln) * tam * 0.5)}", tam * 0.85, '#111111', ini=0.35)
    if destaque:
        yy = _y_dest(L, H)
        c.texto(destaque.upper() + '!', '(w-text_w)/2', str(yy), tam * 1.4, p0, ini=0.7, fade=0.01, borda=max(6, W // 140), cor_borda=p1,
                tam_expr=f"'{int(tam * 1.4)}*(1+0.25*max(0,1-(t-0.7)/0.25)*gte(t,0.7))'")
    return '#ffffff', '#111111', True


def _e_pixel_art(c, cena, L, W, H, dur, pasta, imagem, pal, titulo, destaque, m, tam):
    p0, p1, p2 = pal
    c.fundo(p0)
    k = 8      # 1 pixel de arte = 8 pixels de vídeo
    for i in range(0, W, k * 6):
        c.filtro(f"drawbox=x={i}:y={int(H * 0.82)}:w={k * 5}:h={k * 2}:color=0x{p2.lstrip('#')}:t=fill")
    c.filtro(f"drawbox=x=0:y={int(H * 0.84)}:w=iw:h=ih:color=0x2b2d42:t=fill")
    c.filtro(f"drawbox=x={W - k * 20}:y={k * 10}:w={k * 8}:h={k * 8}:color=0x{p1.lstrip('#')}:t=fill")
    heroi = _pixel_heroi(pasta, p1)
    c.png(heroi, f"mod(t*{W // 6},W+w)-w", f"{int(H * 0.82) - k * 12}-abs(sin(t*5))*{k * 6}", 0.2, 0.1, (k * 12, k * 12), vizinho=True)
    if imagem:
        x, y, w, h = L['painel']
        i = c.entrada(['-i', str(imagem)])
        r = c._rot()
        c.f.append(f"[{i}:v]scale={w // k}:{h // k}:force_original_aspect_ratio=increase,crop={w // k}:{h // k},scale={w}:{h}:flags=neighbor[{r}]")
        o = c._rot()
        c.f.append(f"{c.v}[{r}]overlay=x={x}:y={y}[{o}]")
        c.v = f'[{o}]'
    else:
        _barras(c, cena, L, W, H, (p0, p1, p2), 0.5)
    ln = quebrar(titulo.upper(), W - 2 * m, tam)
    c.texto('\n'.join(ln), '(w-text_w)/2', f"{L['titulo_y']}", tam, p1, ini=0.2, fade=0.01, borda=k // 2, cor_borda='#000000')
    if destaque:
        c.texto(destaque.upper(), '(w-text_w)/2', f'{_y_dest(L, H)}', tam * 0.9, p2, ini=0.8, fade=0.01, borda=k // 2)
    # tudo vira pixel grande: reduz e amplia sem suavizar
    c.filtro(f'scale={W // 4}:{H // 4}:flags=neighbor,scale={W}:{H}:flags=neighbor')
    return '#ffffff', '#000000', True


def _e_papel_recortado(c, cena, L, W, H, dur, pasta, imagem, pal, titulo, destaque, m, tam):
    p0, p1, p2 = pal
    c.fundo(p0)
    c.filtro('noise=alls=7:allf=u')
    r = int(W * 0.2)
    c.png(_circulo(pasta, p2, 100), f"W-w*0.8", f"H*0.78+8*sin(t*1.7)", 0, 0.4, (r * 2, r * 2))
    a1, s1 = _montanhas(pasta, W, int(H * 0.3), p1, 3)
    c.png(a1, '0', f"H-h+6*sin(t*1.2)", 0, 0.4, s1)
    cw, ch = int(W - 2 * m), int(tam * 3.2)
    arq, (sw, sh) = _cartao(pasta, cw, ch, '#fffaf0', 6, True, 'papel')
    c.png(arq, f"{m}+4*sin(t*1.5)", f"{L['titulo_y'] - 20}", 0.1, 0.3, (sw, sh))
    _imagem_painel(c, imagem, L, cena, 'white') or _barras(c, cena, L, W, H, (p0, p1, p2), 0.6)
    ln = quebrar(titulo, cw - 60, tam)[:2]
    c.texto('\n'.join(ln), f'{m + 30}+4*sin(t*1.5)', f"{L['titulo_y'] + int(tam * 0.35)}", tam, '#3b2a1a', ini=0.35)
    if destaque:
        c.texto(destaque, '(w-text_w)/2', f'{_y_dest(L, H)}', tam, '#fffaf0', ini=0.8, sombra=6)
    return '#fffaf0', '#3b2a1a', True


def _e_motion_graphics(c, cena, L, W, H, dur, pasta, imagem, pal, titulo, destaque, m, tam):
    p0, p1, p2 = pal
    c.fundo(p0)
    c.filtro(f"drawgrid=w={W // 12}:h={W // 12}:t=1:c=0x{p1.lstrip('#')}@0.08")
    c.filtro(f"drawbox=x={m}:y={L['titulo_y'] - 24}:w='min({W - 2 * m},{W - 2 * m}*t/0.5)':h=8:color=0x{p1.lstrip('#')}:t=fill".replace(f"w='min({W - 2 * m},{W - 2 * m}*t/0.5)'", f'w={W - 2 * m}'))
    ln = quebrar(titulo, W - 2 * m, tam)
    c.texto('\n'.join(ln), f'{m}', f"{L['titulo_y']}", tam, '#ffffff', ini=0.15)
    if cena.get('numero') is not None:
        n = cena['numero']
        yn = int(H * (0.36 if L['v'] else 0.38))
        # contador que sobe de 0 até o número (expressão nossa; o número já foi validado como float)
        c.filtro(f"drawtext=fontfile='{_esc(FONTE)}':text='%{{eif\\:{n:.4f}*min(1,t/1.5)\\:d}}':fontsize={int(tam * 2.4)}:fontcolor=0x{p2.lstrip('#')}:"
                 f"x=(w-text_w)/2:y={yn}")
        unidade = cena.get('unidade') or ''
        if unidade:
            c.texto(unidade, '(w-text_w)/2', str(yn + int(tam * 2.7)), tam * 0.9, p1, ini=0.3)
    if not _imagem_painel(c, imagem, L, cena):
        if cena.get('numero') is None:
            _barras(c, cena, L, W, H, (p0, p1, p2), 0.4)
    if destaque:
        c.texto(destaque.upper(), '(w-text_w)/2', f'{_y_dest(L, H)}', tam * 0.8, p1, ini=1.0, caixa='black@0.4')
    return '#ffffff', '#000000', True


def _e_palitinho(c, cena, L, W, H, dur, pasta, imagem, pal, titulo, destaque, m, tam):
    p0, p1, p2 = pal
    c.fundo(p0)
    c.filtro(f"drawbox=x=0:y={int(H * 0.80)}:w=iw:h=6:color=0x{p1.lstrip('#')}:t=fill")
    alto = int(H * 0.32)
    larg = int(alto * 160 / 260)
    px = int(W * 0.12)
    py = int(H * 0.80) - alto
    for k in range(int(dur / 0.5) + 1):
        pose = k % 2
        c.png(_palito(pasta, pose, p1), str(px), str(py), k * 0.5, 0, (larg, alto), fim=(k + 1) * 0.5)
    ln = quebrar(titulo, W - 2 * m, tam)
    c.texto('\n'.join(ln), '(w-text_w)/2', f"{L['titulo_y']}", tam, p1, ini=0.2)
    if destaque:
        c.texto(destaque, f'{px + larg + 40}', f'{py + alto // 3}', tam, p2, ini=0.6)
    return p1, '#ffffff', False


def _e_parallax_25d(c, cena, L, W, H, dur, pasta, imagem, pal, titulo, destaque, m, tam):
    p0, p1, p2 = pal
    if imagem:
        i = c.entrada(['-loop', '1', '-framerate', str(FPS), '-t', f'{dur:.3f}', '-i', str(imagem)])
        b, f1 = c._rot(), c._rot()
        c.f.append(f"[{i}:v]scale={int(W * 1.3)}:{int(H * 1.3)}:force_original_aspect_ratio=increase,crop={int(W * 1.3)}:{int(H * 1.3)},split[{b}][{f1}]")
        bg, fg = c._rot(), c._rot()
        c.f.append(f"[{b}]gblur=sigma=18,crop={W}:{H}:x='(iw-ow)/2+40*sin(t*0.5)':y='(ih-oh)/2'[{bg}]")
        c.f.append(f"[{f1}]scale={int(W * 0.8)}:-2,crop={int(W * 0.7)}:{int(H * 0.5)}:x='(iw-ow)/2-30*sin(t*0.5)':y='(ih-oh)/2',format=rgba[{fg}]")
        o = c._rot()
        c.f.append(f"[{bg}][{fg}]overlay=x=(W-w)/2:y=H*0.28[{o}]")
        c.v = f'[{o}]'
    else:
        c.fundo(p0, (p0, '#3a506b'))
        c.png(_circulo(pasta, p1, 100), f"W*0.65", f"H*0.18+20*sin(t*0.4)", 0, 0.5, (int(W * 0.3), int(W * 0.3)))
        for k, (cor, vel, alt) in enumerate([('#2c3e66', 12, 0.45), ('#1f2b4a', 28, 0.38), ('#10182c', 55, 0.30)]):
            arq, (sw, sh) = _montanhas(pasta, W * 2, int(H * alt), cor, k + 1)
            c.png(arq, f"-mod(t*{vel},{W})", f"H-h", 0, 0, (sw, sh))
    ln = quebrar(titulo, W - 2 * m, tam)
    c.texto('\n'.join(ln), '(w-text_w)/2', f"{L['titulo_y']}", tam, p2, ini=0.3, sombra=5)
    if destaque:
        c.texto(destaque, '(w-text_w)/2', f'{_y_dest(L, H)}', tam, p1, ini=0.8, sombra=5)
    return '#ffffff', '#000000', True


def _linhas_centro(c, linhas, y0, tam, cor, **kw):
    """Cada linha centralizada sozinha (o drawtext alinha o bloco pela esquerda)."""
    for k, ln in enumerate(linhas):
        c.texto(ln, '(w-text_w)/2', f'{y0 + int(k * tam * 1.18)}', tam, cor, **kw)


def _e_documentario(c, cena, L, W, H, dur, pasta, imagem, pal, titulo, destaque, m, tam):
    """Foto em tela cheia com movimento lento, escurecida no alto e embaixo para o texto aparecer, título forte e
    a palavra de destaque numa tarja amarela. Sem foto: fundo escuro em movimento com o título grande no meio (nunca ícone)."""
    p0, p1, p2 = pal
    v = H > W
    if imagem:
        c.fundo(p0)
        planos = cena.get('planos') or [{'plano': 'WS', 'camera': cena.get('camera') or 'aproximar'}]
        for k, (pl, (t0, t1)) in enumerate(zip(planos, tempos_planos([dict(p, peso=p.get('peso', 1.0)) for p in planos], dur))):
            c.imagem_plano((cena.get('_imgs') or [imagem] * len(planos))[k], t0, t1 if k < len(planos) - 1 else dur, pl, k == 0)
            if k:
                c.sons.append(t0)
    else:
        c.fundo(p0, ('#1a1a2e', '#3a2a5e'))
    c.png(_degrade(pasta, 200, False), '0', '0', 0, 0, (W, int(H * (0.34 if v else 0.30))))
    c.png(_degrade(pasta, 235, True), '0', f'{H - int(H * (0.46 if v else 0.40))}', 0, 0, (W, int(H * (0.46 if v else 0.40))))
    tt = int(W * (0.088 if v else 0.05))
    ln = quebrar(titulo.upper() if len(titulo) <= 42 else titulo, W - 2 * m, tt)[:3]
    if imagem:
        _linhas_centro(c, ln, int(H * (0.075 if v else 0.07)), tt, '#ffffff', ini=0.15, fade=0.3, borda=max(4, W // 200), cor_borda='#000000', sombra=4)
        if destaque:
            td = int(tt * 0.62)
            c.texto(destaque.upper(), '(w-text_w)/2', f"{int(H * (0.075 if v else 0.07)) + int(tt * 1.18 * len(ln)) + int(td * 0.6)}", td, '#111111',
                    ini=0.7, fade=0.2, caixa=f'0x{p1.lstrip("#")}@0.97')
    else:
        # sem foto, o título vira o centro da cena, grande, com a tarja de destaque embaixo
        tg = int(W * (0.11 if v else 0.06))
        lg = quebrar(titulo.upper(), W - 2 * m, tg)[:4]
        y0 = int(H * 0.36) - len(lg) * int(tg * 0.6)
        _linhas_centro(c, lg, y0, tg, '#ffffff', ini=0.15, fade=0.35, borda=max(4, W // 200), cor_borda='#000000', sombra=5)
        if destaque:
            td = int(tg * 0.55)
            c.texto(destaque.upper(), '(w-text_w)/2', f'{y0 + int(tg * 1.18 * len(lg)) + td}', td, '#111111', ini=0.7, fade=0.2,
                    caixa=f'0x{p1.lstrip("#")}@0.97')
    if c.efeitos:
        c.filtro('fade=t=in:st=0:d=0.14:color=white')      # clarão curto na entrada da cena
    return '#ffffff', '#000000', False


def _fundo_cenario(cn: dict, w: int, h: int, chao_rel: float, arq: Path) -> Path:
    """Cenário pequeno (1/4 da tela) desenhado em Python e ampliado pelo FFmpeg: fica levemente desfocado, como fundo de desenho."""
    t = raster.Tela(w, h)
    c0, c1 = raster.cor(cn['ceu']), raster.cor(cn['ceu2'])
    chao = int(h * chao_rel)
    for y in range(chao):
        f = y / max(1, chao)
        t.retangulo(0, y, w, y + 1, tuple(int(c0[k] + (c1[k] - c0[k]) * f) for k in range(3)) + (255,))
    t.retangulo(0, chao, w, h, raster.cor(cn['chao']))
    t.retangulo(0, chao, w, chao + max(1, h // 160), raster.cor(_escuro(cn['chao'], 0.75)))
    rnd = random.Random(sum(map(ord, cn['nome'] + cn['tipo'])))
    noite = cn['horario'] == 'noite'
    if cn['tipo'] in ('parque', 'rua', 'vazio') and noite:
        for _ in range(40):
            t.elipse(rnd.random() * w, rnd.random() * chao * 0.7, 0.8, 0.8, (255, 255, 230, 200))
        t.elipse(w * 0.8, h * 0.12, w * 0.06, w * 0.06, (245, 240, 210, 255))
    elif cn['tipo'] in ('parque', 'rua'):
        t.elipse(w * 0.82, h * 0.1, w * 0.07, w * 0.07, raster.cor('#fff3b0'))
    if cn['tipo'] == 'parque':
        for k in range(3):
            t.elipse(w * (0.15 + 0.4 * k), chao + h * 0.02, w * 0.45, h * 0.12, raster.cor(_escuro(cn['chao'], 0.85 - 0.05 * k)))
        for x in (0.1, 0.9):
            tx = w * x
            t.retangulo(tx - w * 0.015, chao - h * 0.14, tx + w * 0.015, chao + 2, raster.cor('#6b4226'))
            for dx, dy, r in ((0, -0.19, 0.09), (-0.05, -0.15, 0.07), (0.05, -0.15, 0.07)):
                t.elipse(tx + w * dx, chao + h * dy, w * r, w * r, raster.cor('#3f8f3a' if not noite else '#24502a'))
    elif cn['tipo'] == 'rua':
        x = 0
        while x < w:
            bw, bh = w * (0.18 + rnd.random() * 0.12), h * (0.22 + rnd.random() * 0.25)
            cor = rnd.choice(['#c9ada7', '#9a8c98', '#b5838d', '#a3b18a', '#d4a373'])
            t.retangulo(x, chao - bh, x + bw - 2, chao, raster.cor(_escuro(cor, 0.6) if noite else cor))
            for wy in range(int(chao - bh + h * 0.03), int(chao - h * 0.04), max(4, int(h * 0.045))):
                for wx in range(int(x + bw * 0.15), int(x + bw * 0.85), max(4, int(bw * 0.3))):
                    t.retangulo(wx, wy, wx + bw * 0.16, wy + h * 0.022, raster.cor('#ffe8a3' if noite and rnd.random() > 0.4 else '#dfe7ef'))
            x += bw
        t.retangulo(0, chao + h * 0.03, w, chao + h * 0.035, raster.cor('#f1f1f1'))
    elif cn['tipo'] in ('casa', 'escola', 'escritorio'):
        t.retangulo(0, chao - h * 0.06, w, chao, raster.cor(_escuro(cn['ceu'], 0.88)))
        jx, jy, jw, jh = w * 0.62, chao - h * 0.36, w * 0.26, h * 0.2
        t.retangulo(jx - 3, jy - 3, jx + jw + 3, jy + jh + 3, raster.cor('#ffffff'))
        t.retangulo(jx, jy, jx + jw, jy + jh, raster.cor('#203a70' if noite else '#9fd3f5'))
        t.retangulo(jx + jw / 2 - 1, jy, jx + jw / 2 + 1, jy + jh, raster.cor('#ffffff'))
        if cn['tipo'] == 'escola':
            t.retangulo(w * 0.08, chao - h * 0.38, w * 0.5, chao - h * 0.17, raster.cor('#2f5d3a'))
            t.retangulo(w * 0.08, chao - h * 0.17, w * 0.5, chao - h * 0.16, raster.cor('#8b5a2b'))
        elif cn['tipo'] == 'escritorio':
            t.retangulo(w * 0.05, chao - h * 0.1, w * 0.4, chao - h * 0.085, raster.cor('#6b4f3a'))
            t.retangulo(w * 0.07, chao - h * 0.085, w * 0.09, chao, raster.cor('#6b4f3a'))
            t.retangulo(w * 0.36, chao - h * 0.085, w * 0.38, chao, raster.cor('#6b4f3a'))
            t.retangulo(w * 0.15, chao - h * 0.17, w * 0.28, chao - h * 0.1, raster.cor('#2b2d42'))
        else:
            t.retangulo(w * 0.08, chao - h * 0.33, w * 0.3, chao - h * 0.2, raster.cor('#e9c46a'))
            t.retangulo(w * 0.1, chao - h * 0.315, w * 0.28, chao - h * 0.215, raster.cor('#2a9d8f'))
    return t.salvar(arq)


def _escuro(hexa: str, f: float) -> str:
    r, g, b, _ = raster.cor(hexa)
    return '#%02x%02x%02x' % (int(r * f), int(g * f), int(b * f))


ZOOM_2D = {'WS': 1.0, 'MS': 1.45, 'CU': 2.0, 'ECU': 2.3}


def _e_animado2d(c, cena, L, W, H, dur, pasta, imagem, pal, titulo, destaque, m, tam):
    """Cena com personagens articulados (rig2d). Composição em resolução maior quando há close, e a câmera
    (cortes de plano com leve aproximação) é aplicada no fim, sem mexer na ação dos personagens."""
    perfis = cena.get('_personagens') or {}
    elenco = [e for e in (cena.get('elenco') or []) if e['personagem_id'] in perfis]
    if not elenco:
        elenco, perfis = rig2d.elenco_padrao(cena, pal)
    cn = rig2d.validar_cenario(cena.get('_cenario') or {'tipo': 'parque' if not perfis.get('apresentador') else 'vazio', 'ceu': pal[0]})
    planos = cena.get('planos') or [{'id': 'p1', 'plano': 'WS', 'peso': 1.0, 'personagem': ''}]
    ss = float(os.getenv('RIG_SS', '1.0')) if any(ZOOM_2D.get(p.get('plano'), 1) > 1 for p in planos) else 1.0
    Wc, Hc = int(W * ss) // 2 * 2, int(H * ss) // 2 * 2
    c.W, c.H = Wc, Hc
    v = H > W
    chao_rel = 0.80 if v else 0.86
    chao_y = Hc * chao_rel
    altura = Hc * (0.40 if v else 0.62) / (1.25 if len(elenco) > 2 else 1)
    fundo = _fundo_cenario(cn, max(64, Wc // 4), max(64, Hc // 4), chao_rel, pasta / 'cenario.png')
    c.fundo(cn['ceu'])
    c.png(_escalada_para(fundo, int(Wc * 1.025), Hc), f'-{Wc * 0.025:.0f}*t/{dur:.2f}', '0', 0, 0)
    falante = (cena.get('personagem') or '').strip().lower()
    nomes = {k: rig2d.validar_personagem(p)['nome'].lower() for k, p in perfis.items()}
    pos = {}
    pasta_pecas = Path(os.getenv('DADOS', str(Path.home() / '.estudioclip'))) / 'rig2d'
    for el in elenco:
        p = rig2d.validar_personagem(perfis[el['personagem_id']])
        fala = falante in (el['personagem_id'], nomes.get(el['personagem_id'])) or (len(elenco) == 1 and bool(cena.get('texto')))
        if fala and not any(a['tipo'] == 'falar' for a in el['acoes']):
            el = dict(el, acoes=[{'t': 0.0, 'tipo': 'falar', 'alvo': '', 'intensidade': 1.0, 'dur': 0}] + el['acoes'])
        pos[el['personagem_id']] = rig2d.colocar(c, el, p, rig2d.pecas(p, pasta_pecas), chao_y, altura, Wc, dur, fala, cena.get('_audio'))
        if fala:
            pos['_falante'] = pos[el['personagem_id']]
    # câmera: cortes entre planos, foco no personagem do plano (ou em quem fala)
    tempos = tempos_planos([dict(p, peso=p.get('peso', 1.0)) for p in planos], dur)
    zs, xs, ys, angs, giros, ms = [], [], [], [], [], []
    for p, (t0, t1) in zip(planos, tempos):
        z = ZOOM_2D.get(p.get('plano'), 1.0) / ss
        alvo = pos.get(p.get('personagem') or '') or pos.get('_falante') or next(iter(pos.values()))
        fy = alvo['cabeca_y'] + (0.06 * Hc if p.get('plano') in ('CU', 'ECU') else 0.12 * Hc) if p.get('plano') != 'WS' else Hc / 2
        fx = alvo['x_px'] if p.get('plano') != 'WS' else Wc / 2
        f0, f1 = int(t0 * FPS), max(int(t0 * FPS) + 1, int(t1 * FPS))
        zz = f'{z * ss:.4f}*(1+0.035*(on-{f0})/{f1 - f0})' if z * ss > 1 else f'(1+0.02*on/{max(1, int(dur * FPS))})'
        ex, ey = f'{fx:.1f}', f'{fy:.1f}'
        if p.get('chaves'):
            prog = f'(on-{f0})/{f1 - f0}'
            zz = expr_chaves(p['chaves'], 'zoom', prog)
            ex, ey = expr_chaves(p['chaves'], 'x', prog, Wc), expr_chaves(p['chaves'], 'y', prog, Hc)
        fim = dur + 1 if p is planos[-1] else t1
        if p.get('angulo') == 'inclinado':
            zz = f'({zz})*{ZOOM_GIRO}'
            giros.append((t0, fim))
            ms.append((f1, f'{(1 - 1 / ZOOM_GIRO) / 2:.4f}'))
        else:
            ms.append((f1, '0'))
            if p.get('angulo') in ('baixo', 'alto'):
                angs.append((p['angulo'], t0, fim))
        zs.append((f1, zz))
        xs.append((f1, ex))
        ys.append((f1, ey))
        if t0 > 0.05:
            c.sons.append(t0)

    def por_plano(lst):
        out = lst[-1][1]
        for f1, e in reversed(lst[:-1]):
            out = f'if(lt(on,{f1}),{e},{out})'
        return out
    if giros:     # plano inclinado: gira o quadro antes do zoom; a janela fica no miolo (margem m), sem canto preto
        c.filtro(f"rotate={GIRO}:fillcolor=black:enable='" + '+'.join(f'between(t,{a:.3f},{b:.3f})' for a, b in giros) + "'")
    mm = por_plano(ms)
    c.filtro(f"zoompan=z='{por_plano(zs)}':x='clip({por_plano(xs)}-iw/zoom/2,iw*{mm},iw-iw/zoom-iw*{mm})':y='clip({por_plano(ys)}-ih/zoom/2,ih*{mm},ih-ih/zoom-ih*{mm})'"
             f":d=1:s={W}x{H}:fps={FPS}")
    for a, t0, t1 in angs:
        c.filtro(filtro_angulo(a, W, H, f'between(t,{t0:.3f},{t1:.3f})'))
    c.W, c.H = W, H
    c.sons = c.sons[:0]   # diálogo: sem 'whoosh' nos cortes
    if titulo and not cena.get('elenco'):
        ln = quebrar(titulo, W - 2 * m, tam * 0.8)
        c.texto('\n'.join(ln), '(w-text_w)/2', f"{L['titulo_y']}", tam * 0.8, '#ffffff', ini=0.2, borda=max(4, W // 200), cor_borda='#111111')
    return '#ffffff', '#000000', True


def _e_cartoon2d(c, cena, L, W, H, dur, pasta, imagem, pal, titulo, destaque, m, tam):
    p0, p1, p2 = pal
    c.fundo(p0)
    if imagem:
        c.imagem(imagem, 0, 0, W, H, cena.get('camera') or 'aproximar', 0)
    ln = quebrar(titulo, W - 2 * m, tam)
    c.texto('\n'.join(ln), '(w-text_w)/2', f"{L['titulo_y']}", tam, '#ffffff', ini=0.3, borda=max(5, W // 180), cor_borda=p2)
    return '#ffffff', '#000000', True


def _e_3d(eid, c, cena, L, W, H, dur, pasta, imagem, pal, titulo, destaque, m, tam):
    p0, p1, p2 = pal
    c.fundo_video(motor3d.caminho(eid, W, H, list(pal)))
    ln = quebrar(titulo, W - 2 * m, tam)
    c.texto('\n'.join(ln), '(w-text_w)/2', f"{L['titulo_y']}", tam, '#ffffff', ini=0.2, borda=max(5, W // 180), cor_borda='#000000', sombra=3)
    if destaque:
        c.texto(destaque.upper(), '(w-text_w)/2', f'{_y_dest(L, H)}', tam * 0.9, p1 if eid != 'brinquedo_blocos' else p0, ini=0.8, borda=max(4, W // 220), cor_borda='#000000')
    return '#ffffff', '#000000', True


def _e_cinema3d(*a):
    return _e_3d('cinema3d', *a)


def _e_brinquedo_blocos(*a):
    return _e_3d('brinquedo_blocos', *a)


def _e_plastico3d(*a):
    return _e_3d('plastico3d', *a)


def _e_retro3d_2000(*a):
    return _e_3d('retro3d_2000', *a)


def preparar(eid: str, W: int, H: int, dur: float, paleta: list | None, cancelado=None, progresso=None):
    """Passo prévio dos estilos que precisam de um arquivo pronto (3D). Os outros não fazem nada."""
    if eid in motor3d.ESTILOS_3D and utilizavel(eid):
        if dur > 30.5:
            raise ValueError('Os estilos 3D aceitam cenas de até 30 s. Divida a cena em duas.')
        pal = (paleta or estilo(eid)['paleta'])
        motor3d.gerar_loop(eid, W, H, list(pal)[:3] if len(pal) >= 3 else estilo(eid)['paleta'], cancelado, progresso)


def chave_cena(eid: str, cena: dict, W: int, H: int, dur: float, audio_sha: str, imagem_sha: str, paleta) -> str:
    base = json.dumps([VERSAO_MOTOR, eid, cena, W, H, round(dur, 2), audio_sha, imagem_sha, paleta], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(base.encode()).hexdigest()[:24]


def demo_cena(eid: str) -> dict:
    """Cena de demonstração igual para todos os estilos (comparar lado a lado)."""
    return validar_cena({'titulo': 'Por que o céu é azul?', 'destaque': 'Luz do sol', 'texto': 'A luz do sol se espalha no ar e o azul se espalha mais.',
                         'numero': 71 if eid == 'motion_graphics' else None, 'unidade': '%',
                         'elementos': [{'rotulo': 'Azul', 'valor': 90}, {'rotulo': 'Verde', 'valor': 55}, {'rotulo': 'Vermelho', 'valor': 25}] if eid == 'motion_graphics' else []})
