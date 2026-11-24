"""Biblioteca visual compartilhada: 12 estilos que tratam a imagem de um corte (cor, brilho, textura, moldura, HUD).

Camada 1 do documento de melhorias: o ESTILO VISUAL é independente do template (layout, legenda, tarjas) e dos efeitos
de movimento. Um corte guarda `estilo_visual` (id), `estilo_forca` (0 a 1) e `estilo_off` (componentes desligados).
O FFmpeg monta aqui; o site desenha o mesmo estilo no canvas (frontend/src/lib/estilosVisuais.ts) para a prévia e a
exportação do navegador. Estes estilos são TRATAMENTO e MONTAGEM sobre o vídeo real: não viram 3D nem refazem a filmagem.

Cada estilo declara os filtros do FFmpeg de que precisa. Se o FFmpeg do aparelho não tiver algum, o estilo aparece como
"indisponível" com o motivo, em vez de falhar na hora de renderizar. Só biblioteca padrão do Python.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from functools import lru_cache
from pathlib import Path

import postagem as pg

VERSAO = 1
ARQ_MEDIDAS = pg.DADOS / 'estilos_medidas.json'
FONTES = Path(__file__).parent / 'fontes'
PIPELINES = ('clip_browser', 'clip_server', 'agent1')      # onde o estilo é aplicado de verdade hoje
COMPONENTES = {'grade': 'Cor e contraste', 'brilho': 'Brilho (glow)', 'vinheta': 'Vinheta', 'textura': 'Grão e ruído', 'moldura': 'Moldura',
               'hud': 'Faixas e HUD', 'distorcao': 'Distorção de cor', 'foco': 'Desfoque de foco', 'pixel': 'Borda pixelada', 'flash': 'Clarão de entrada'}


class ErroEstilo(Exception):
    pass


def _l(n: float, t: float, f: float) -> float:
    """Vai do valor neutro n até o valor do estilo t conforme a força f (0 a 1)."""
    return n + (t - n) * max(0.0, min(1.0, f))


def _hex(c: str) -> str:
    return '0x' + c.lstrip('#')


# Cada estilo: peças em ordem. ('componente', 'tipo', valor). tipo 'f' = filtros em cadeia; os outros são especiais.
def _gamer_neon(L, A, f, txt):
    return [('grade', 'f', f'eq=contrast={_l(1, 1.12, f):.3f}:saturation={_l(1, 1.45, f):.3f}:brightness={_l(0, 0.02, f):.3f}'),
            ('brilho', 'glow', (18, _l(0, 0.42, f))),
            ('vinheta', 'f', f'vignette=angle={_l(0.0, 0.628, f):.3f}'),
            ('moldura', 'f', f'drawbox=x=0:y=0:w=iw:h=ih:color=0x00F0FF@{_l(0, 0.9, f):.2f}:t=10,drawbox=x=14:y=14:w=iw-28:h=ih-28:color=0xFF2BD6@{_l(0, 0.8, f):.2f}:t=5')]


def _cinema_noturno(L, A, f, txt):
    return [('grade', 'f', f'colorbalance=rs={_l(0, -0.08, f):.3f}:bs={_l(0, 0.12, f):.3f}:rm={_l(0, -0.06, f):.3f}:bm={_l(0, 0.10, f):.3f}:bh={_l(0, 0.08, f):.3f},'
                           f'eq=contrast={_l(1, 1.15, f):.3f}:brightness={_l(0, -0.04, f):.3f}:saturation={_l(1, 0.85, f):.3f}'),
            ('vinheta', 'f', f'vignette=angle={_l(0.0, 0.785, f):.3f}'),
            ('hud', 'f', f'drawbox=x=0:y=0:w=iw:h=ih*0.07:color=black@{_l(0, 1, f):.2f}:t=fill,drawbox=x=0:y=ih*0.93:w=iw:h=ih*0.07:color=black@{_l(0, 1, f):.2f}:t=fill')]


def _golden_cinematic(L, A, f, txt):
    return [('grade', 'f', f'colorbalance=rs={_l(0, 0.10, f):.3f}:gs={_l(0, 0.03, f):.3f}:bs={_l(0, -0.10, f):.3f}:rm={_l(0, 0.08, f):.3f}:bm={_l(0, -0.08, f):.3f}:rh={_l(0, 0.06, f):.3f}:bh={_l(0, -0.05, f):.3f},'
                           f'eq=contrast={_l(1, 1.08, f):.3f}:saturation={_l(1, 1.15, f):.3f}'),
            ('textura', 'f', f'noise=alls={int(_l(0, 8, f))}:allf=t'),
            ('vinheta', 'f', f'vignette=angle={_l(0.0, 0.524, f):.3f}'),
            ('hud', 'f', f'drawbox=x=0:y=0:w=iw:h=ih*0.05:color=black@{_l(0, 1, f):.2f}:t=fill,drawbox=x=0:y=ih*0.95:w=iw:h=ih*0.05:color=black@{_l(0, 1, f):.2f}:t=fill')]


def _miniatura(L, A, f, txt):
    return [('grade', 'f', f'eq=contrast={_l(1, 1.1, f):.3f}:saturation={_l(1, 1.4, f):.3f}'),
            ('foco', 'tilt', (10, f)),
            ('moldura', 'f', f'drawbox=x=0:y=0:w=iw:h=ih:color=0xC89B5E@{_l(0, 1, f):.2f}:t=26,drawbox=x=26:y=26:w=iw-52:h=ih-52:color=0x5B3A1A@{_l(0, 0.9, f):.2f}:t=4')]


def _maquete_papel(L, A, f, txt):
    return [('grade', 'f', f'eq=saturation={_l(1, 1.25, f):.3f}:contrast={_l(1, 1.05, f):.3f},unsharp=5:5:{_l(0, 0.8, f):.2f}'),
            ('textura', 'f', f'noise=alls={int(_l(0, 7, f))}:allf=t'),
            ('moldura', 'f', f'drawbox=x=0:y=0:w=iw:h=ih:color=0xF3EBDD@{_l(0, 1, f):.2f}:t=34,drawbox=x=34:y=34:w=iw-68:h=ih-68:color=black@{_l(0, 0.28, f):.2f}:t=8,'
                             f'drawbox=x=42:y=42:w=iw-84:h=ih-84:color=0xD8CCB8@{_l(0, 0.8, f):.2f}:t=3')]


def _acrilico(L, A, f, txt):
    return [('grade', 'f', f'eq=contrast={_l(1, 1.05, f):.3f}:brightness={_l(0, 0.02, f):.3f}:saturation={_l(1, 1.1, f):.3f}'),
            ('hud', 'f', f'drawbox=x=0:y=0:w=iw:h=ih*0.09:color=white@{_l(0, 0.14, f):.2f}:t=fill,drawbox=x=0:y=ih*0.91:w=iw:h=ih*0.09:color=white@{_l(0, 0.14, f):.2f}:t=fill,'
                         f'drawbox=x=0:y=ih*0.09:w=iw:h=2:color=white@{_l(0, 0.55, f):.2f}:t=fill,drawbox=x=0:y=ih*0.91:w=iw:h=2:color=white@{_l(0, 0.55, f):.2f}:t=fill'),
            ('moldura', 'f', f'drawbox=x=10:y=10:w=iw-20:h=ih-20:color=white@{_l(0, 0.45, f):.2f}:t=3'),
            ('brilho', 'glow', (22, _l(0, 0.18, f)))]


def _porcelana(L, A, f, txt):
    return [('grade', 'f', f'eq=brightness={_l(0, 0.05, f):.3f}:contrast={_l(1, 0.95, f):.3f}:saturation={_l(1, 0.8, f):.3f},'
                           f'colorbalance=rm={_l(0, 0.03, f):.3f}:bm={_l(0, 0.02, f):.3f}'),
            ('brilho', 'glow', (16, _l(0, 0.28, f))),
            ('moldura', 'f', f'drawbox=x=0:y=0:w=iw:h=ih:color=0xFAF7F2@{_l(0, 1, f):.2f}:t=22,drawbox=x=22:y=22:w=iw-44:h=ih-44:color=0xE8DFD2@{_l(0, 0.9, f):.2f}:t=3')]


def _industrial(L, A, f, txt):
    return [('grade', 'f', f'eq=contrast={_l(1, 1.3, f):.3f}:saturation={_l(1, 0.55, f):.3f},colorbalance=bs={_l(0, 0.05, f):.3f}:bm={_l(0, 0.04, f):.3f}'),
            ('textura', 'f', f'noise=alls={int(_l(0, 14, f))}:allf=t+u'),
            ('vinheta', 'f', f'vignette=angle={_l(0.0, 0.70, f):.3f}'),
            ('hud', 'f', f'drawbox=x=0:y=0:w=iw:h=ih*0.035:color=0xF2C200@{_l(0, 1, f):.2f}:t=fill,drawbox=x=0:y=ih*0.965:w=iw:h=ih*0.035:color=0xF2C200@{_l(0, 1, f):.2f}:t=fill')]


def _comic(L, A, f, txt):
    return [('grade', 'f', f'eq=contrast={_l(1, 1.25, f):.3f}:saturation={_l(1, 1.6, f):.3f},lutyuv=y=\'trunc(val/{int(_l(1, 36, f))})*{int(_l(1, 36, f))}+{int(_l(0, 18, f))}\''),
            ('textura', 'f', f'drawgrid=w={max(8, int(L / 60))}:h={max(8, int(L / 60))}:t=3:c=black@{_l(0, 0.2, f):.2f}'),
            ('moldura', 'f', f'drawbox=x=0:y=0:w=iw:h=ih:color=black@{_l(0, 1, f):.2f}:t=16')]


def _vhs(L, A, f, txt):
    return [('grade', 'f', f'eq=saturation={_l(1, 1.3, f):.3f}:contrast={_l(1, 1.05, f):.3f},gblur=sigma={_l(0, 0.8, f):.2f}'),
            ('distorcao', 'f', f'rgbashift=rh={int(_l(0, -4, f))}:bh={int(_l(0, 4, f))}'),
            ('textura', 'f', f'noise=alls={int(_l(0, 20, f))}:allf=t,drawgrid=y=0:h=4:t=1:c=black@{_l(0, 0.35, f):.2f}'),
            ('vinheta', 'f', f'vignette=angle={_l(0.0, 0.785, f):.3f}')]


def _pixel(L, A, f, txt):
    return [('grade', 'f', f'eq=saturation={_l(1, 1.3, f):.3f}:contrast={_l(1, 1.08, f):.3f}'),
            ('pixel', 'pixel', (14, int(min(L, A) * 0.05))),
            ('hud', 'f', f'drawbox=x=0:y=0:w=iw:h=ih*0.03:color=0x39FF6A@{_l(0, 1, f):.2f}:t=fill,drawbox=x=0:y=ih*0.97:w=iw:h=ih*0.03:color=0x39FF6A@{_l(0, 1, f):.2f}:t=fill')]


def _replay(L, A, f, txt):
    tag = re.sub(r"[^\w .,\-]", '', txt or 'REPLAY')[:24] or 'REPLAY'
    fonte = str(FONTES / 'Inter-Bold.otf').replace('\\', '/').replace(':', '\\:')
    return [('grade', 'f', f'eq=contrast={_l(1, 1.12, f):.3f}:saturation={_l(1, 1.2, f):.3f}'),
            ('hud', 'f', f'drawbox=x={int(L * 0.04)}:y={int(A * 0.045)}:w={int(L * 0.4)}:h={int(A * 0.045)}:color=0xE10600@{_l(0, 0.95, f):.2f}:t=fill,'
                         f"drawtext=fontfile='{fonte}':text='{tag}':fontsize={int(A * 0.03)}:fontcolor=white@{_l(0, 1, f):.2f}:x={int(L * 0.055)}:y={int(A * 0.052)}"),
            ('flash', 'f', f'fade=t=in:st=0:d={_l(0.01, 0.25, f):.2f}:c=white')]


PRESETS = {
    'gamer_neon': dict(nome='Gamer Neon', desc='Brilho, moldura neon, vinheta e cores fortes.', custo='medio', filtros=['eq', 'gblur', 'blend', 'vignette', 'drawbox'], pecas=_gamer_neon),
    'cinema_noturno': dict(nome='Cinema Noturno', desc='Tons frios, contraste, vinheta e barras de cinema.', custo='leve', filtros=['colorbalance', 'eq', 'vignette', 'drawbox'], pecas=_cinema_noturno),
    'golden_cinematic': dict(nome='Cinemático Dourado', desc='Luz quente simulada, grão leve e barras finas.', custo='leve', filtros=['colorbalance', 'eq', 'noise', 'vignette', 'drawbox'], pecas=_golden_cinematic),
    'miniatura_isometrica': dict(nome='Miniatura Isométrica', desc='Efeito maquete: foco só no meio, cores vivas e moldura de madeira.', custo='pesado', filtros=['eq', 'gblur', 'gradients', 'maskedmerge', 'drawbox'],
                                 pecas=_miniatura, beta='É um falso tilt-shift (desfoque em faixas); não muda a perspectiva da imagem.'),
    'maquete_papel': dict(nome='Maquete de Papel', desc='Moldura de papel com sombra, cores vivas e grão.', custo='leve', filtros=['eq', 'unsharp', 'noise', 'drawbox'], pecas=_maquete_papel),
    'acrilico_glass': dict(nome='Acrílico / Glass', desc='Painéis translúcidos, reflexo e brilho suave.', custo='medio', filtros=['eq', 'gblur', 'blend', 'drawbox'], pecas=_acrilico,
                           beta='Os painéis são simulados (faixas translúcidas); o vídeo atrás não é desfocado.'),
    'porcelana_suave': dict(nome='Porcelana Suave', desc='Cores claras e suaves, brilho delicado e moldura limpa.', custo='medio', filtros=['eq', 'colorbalance', 'gblur', 'blend', 'drawbox'], pecas=_porcelana),
    'industrial_impacto': dict(nome='Industrial', desc='Contraste duro, cores frias, ruído e faixas amarelas de aviso.', custo='leve', filtros=['eq', 'colorbalance', 'noise', 'vignette', 'drawbox'], pecas=_industrial),
    'comic_gameplay': dict(nome='Quadrinhos Gamer', desc='Cores chapadas, retícula de quadrinhos e borda grossa.', custo='leve', filtros=['eq', 'lutyuv', 'drawgrid', 'drawbox'], pecas=_comic),
    'retro_vhs': dict(nome='Retro VHS', desc='Linhas de varredura, ruído e deslocamento de cor.', custo='leve', filtros=['eq', 'gblur', 'rgbashift', 'noise', 'drawgrid', 'vignette'], pecas=_vhs),
    'pixel_stream': dict(nome='Pixel Stream', desc='Borda pixelada e faixas verdes estilo 8-bit.', custo='medio', filtros=['eq', 'scale', 'split', 'crop', 'overlay', 'drawbox'], pecas=_pixel),
    'sports_replay': dict(nome='Replay Esportivo', desc='Etiqueta REPLAY (ou o texto que você escolher), clarão de entrada e cores de transmissão.', custo='leve', filtros=['eq', 'drawbox', 'drawtext', 'fade'],
                          pecas=_replay, beta='Não faz câmera lenta nem congela quadro: só a etiqueta, o clarão e a cor.'),
}


@lru_cache(maxsize=1)
def filtros_disponiveis() -> frozenset:
    try:
        r = subprocess.run(['ffmpeg', '-hide_banner', '-filters'], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    return frozenset(m.group(1) for m in re.finditer(r'^\s*[TSC.]{3}\s+(\w+)\s', r.stdout, re.M))


def _faltam(pid: str) -> list:
    disp = filtros_disponiveis()
    if not disp:
        return ['ffmpeg']
    return sorted(set(PRESETS[pid]['filtros']) - disp)


def validar(pid: str, forca=1.0, desligar=None) -> tuple[str, float, tuple]:
    """Confere os campos de estilo vindos do site. Id desconhecido é recusado com mensagem (nunca ignorado em silêncio)."""
    if not pid:
        return '', 1.0, ()
    if pid not in PRESETS:
        raise ErroEstilo(f'Estilo visual desconhecido: "{pid}".')
    try:
        f = max(0.0, min(1.0, float(forca)))
    except (TypeError, ValueError):
        f = 1.0
    off = tuple(sorted({str(x) for x in (desligar or []) if str(x) in COMPONENTES}))
    return pid, f, off


def grafo(pid: str, L: int, A: int, entrada: str, saida: str, forca: float = 1.0, desligar=(), texto: str = '') -> str:
    """Trecho de filter_complex que trata a imagem: `entrada` -> `saida`. Peças desligadas somem; força 0 deixa a imagem igual."""
    if pid not in PRESETS:
        raise ErroEstilo(f'Estilo visual desconhecido: "{pid}".')
    if float(forca) <= 0:
        return f'{entrada}null{saida}'
    falta = _faltam(pid)
    if falta:
        raise ErroEstilo(f'O FFmpeg deste aparelho não tem o filtro {", ".join(falta)}, necessário para o estilo {PRESETS[pid]["nome"]}.')
    pecas = [p for p in PRESETS[pid]['pecas'](L, A, forca, texto) if p[0] not in desligar]
    seg, cadeia, atual, n = [], [], entrada, [0]

    def novo():
        n[0] += 1
        return f'[vp{n[0]}]'

    def fechar():
        nonlocal atual, cadeia
        if cadeia:
            nxt = novo()
            seg.append(f'{atual}{",".join(cadeia)}{nxt}')
            atual, cadeia = nxt, []
    for nome, tipo, val in pecas:
        if tipo == 'f':
            cadeia.append(val)
        elif tipo == 'glow' and val[1] > 0.001:
            fechar()
            a, b, c, nxt = novo(), novo(), novo(), novo()
            seg.append(f'{atual}split{a}{b}')
            seg.append(f'{b}gblur=sigma={val[0]}{c}')
            seg.append(f'{a}{c}blend=all_mode=screen:all_opacity={val[1]:.2f}{nxt}')
            atual = nxt
        elif tipo == 'tilt' and val[1] > 0.001:
            fechar()
            a, b, b2, c, m, nxt = novo(), novo(), novo(), novo(), novo(), novo()
            seg.append(f'{atual}split=3{a}{b}{b2}')
            seg.append(f'{b}gblur=sigma={val[0] * max(0.3, val[1]):.1f}{c}')
            # máscara tirada do próprio vídeo (acaba junto com ele): preto no meio (nítido), branco nas bordas (desfocado)
            seg.append(f"{b2}format=gray,geq=lum='clip(255*(abs(2*Y/H-1)-0.25)/0.6\\,0\\,255)'{m}")
            seg.append(f'{a}{c}{m}maskedmerge{nxt}')
            atual = nxt
        elif tipo == 'pixel':
            fechar()
            bloco, marg = val
            a, b, c, d, nxt = novo(), novo(), novo(), novo(), novo()
            seg.append(f'{atual}split{a}{b}')
            seg.append(f'{b}scale={L // bloco}:{A // bloco}:flags=neighbor,scale={L}:{A}:flags=neighbor{c}')
            seg.append(f'{a}crop={L - 2 * marg}:{A - 2 * marg}:{marg}:{marg}{d}')
            seg.append(f'{c}{d}overlay={marg}:{marg}{nxt}')
            atual = nxt
    fechar()
    if atual == entrada:               # tudo desligado ou força 0: passa direto
        return f'{entrada}null{saida}'
    seg[-1] = seg[-1][:-len(atual)] + saida
    return ';'.join(seg)


# ---------------------------------------------------------------- catálogo, medição e demonstração
def _medidas() -> dict:
    return pg._ler(ARQ_MEDIDAS, {})


def listar() -> list:
    med = _medidas()
    out = []
    for pid, p in PRESETS.items():
        falta = _faltam(pid)
        status = 'unavailable' if falta else ('beta' if p.get('beta') else 'ready')
        out.append({'id': pid, 'nome': p['nome'], 'descricao': p['desc'], 'versao': VERSAO, 'status': status,
                    'motivo': ('Falta no FFmpeg: ' + ', '.join(falta)) if falta else p.get('beta', ''), 'custo': p['custo'],
                    'pipelines': [] if falta else list(PIPELINES), 'componentes': sorted({x[0] for x in p['pecas'](1080, 1920, 1.0, '')}),
                    'medido': med.get(pid)})
    return out


def _gerar_base(destino: Path, seg: float = 3.0, L: int = 360, A: int = 640):
    """Vídeo de teste sintético (padrão em movimento + tom), para medir e demonstrar sem usar mídia de terceiros."""
    r = subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', f'testsrc2=size={L}x{A}:rate=30:duration={seg}',
                        '-f', 'lavfi', '-i', f'sine=frequency=440:duration={seg}', '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                        '-shortest', str(destino)], capture_output=True, text=True)
    if r.returncode != 0:
        raise ErroEstilo('Não consegui gerar o vídeo de teste: ' + r.stderr[-200:])


def aplicar_arquivo(entrada: Path, destino: Path, pid: str, forca: float = 1.0, desligar=(), texto: str = '', L: int = 0, A: int = 0, crf: int = 23):
    """Trata um MP4 pronto com o estilo (usado nas demonstrações e no pós-tratamento de vídeos já montados)."""
    if not (L and A):
        r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', str(entrada)], capture_output=True, text=True)
        L, A = (int(x) for x in r.stdout.strip().split(',')[:2])
    fc = grafo(pid, L, A, '[0:v]', '[v]', forca, desligar, texto)
    r = subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(entrada), '-filter_complex', fc, '-map', '[v]', '-map', '0:a?', '-c:v', 'libx264',
                        '-preset', 'veryfast', '-crf', str(crf), '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', str(destino)], capture_output=True, text=True)
    if r.returncode != 0 or not destino.exists() or destino.stat().st_size < 1000:
        destino.unlink(missing_ok=True)
        raise ErroEstilo('O FFmpeg não conseguiu aplicar o estilo: ' + (r.stderr.strip()[-300:] or 'erro desconhecido'))


def medir(pid: str) -> dict:
    """Renderiza 3 s de teste em 360x640 e guarda quanto tempo levou NESTE aparelho. Sem medir, a tela diz 'não medido'."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        base, saida = Path(d) / 'base.mp4', Path(d) / 'estilo.mp4'
        _gerar_base(base)
        t0 = time.time()
        aplicar_arquivo(base, saida, pid)
        seg = time.time() - t0
    m = {'segundos': round(seg, 2), 'por_segundo_de_video': round(seg / 3.0, 2), 'resolucao': '360x640', 'quando': time.time()}
    with pg.LOCK:
        d = _medidas()
        d[pid] = m
        pg._gravar(ARQ_MEDIDAS, d)
    return m


def demo(pid: str, destino: Path) -> Path:
    """Demonstração lado a lado: sem estilo (esquerda) e com estilo (direita), em vídeo de verdade."""
    import tempfile
    if pid not in PRESETS:
        raise ErroEstilo('Estilo desconhecido.')
    with tempfile.TemporaryDirectory() as d:
        base, tratado = Path(d) / 'base.mp4', Path(d) / 'estilo.mp4'
        _gerar_base(base, 3.0)
        aplicar_arquivo(base, tratado, pid)
        r = subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(base), '-i', str(tratado), '-filter_complex', 'hstack=inputs=2[v]', '-map', '[v]', '-map', '1:a?',
                            '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', str(destino)], capture_output=True, text=True)
        if r.returncode != 0:
            raise ErroEstilo('Não consegui montar a demonstração: ' + r.stderr[-200:])
    return destino


def demo_pronta(pid: str) -> Path:
    """Demonstração guardada em disco (gerada na primeira vez; refeita quando a versão da biblioteca muda)."""
    if pid not in PRESETS:
        raise ErroEstilo('Estilo desconhecido.')
    pasta = pg.DADOS / 'estilos_demo'
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / f'{pid}-v{VERSAO}.mp4'
    if not arq.exists() or arq.stat().st_size < 1000:
        demo(pid, arq)
    return arq
