"""Estilo de corte "Comparação em tela dividida" (ex.: jogo antigo x jogo novo, antes x depois).

Formato pensado para Shorts de comparação: duas imagens ao mesmo tempo, uma em cima da outra no vertical (9:16 e 1:1)
ou lado a lado no 16:9, uma faixa fina separando as duas, um rótulo colorido para cada lado e um selo "VS" que aparece
com um pulinho bem na divisa. As duas partes saem do MESMO quadro do vídeo (um vídeo que já vem "lado a lado" ou
"um em cima do outro"), então ficam sempre sincronizadas. O mesmo desenho é feito no site (frontend/src/lib/render.ts).

Usado pelo Agente de Cortes (agente.filtro_video / montar_ass) quando o template tem layout 'comparacao'.
Só biblioteca padrão do Python + FFmpeg.
"""
from __future__ import annotations

PADRAO = {'a': {'x': 0, 'y': 0, 'w': 0.5, 'h': 1}, 'b': {'x': 0.5, 'y': 0, 'w': 0.5, 'h': 1},
          'rotuloA': 'ANTES', 'rotuloB': 'DEPOIS', 'corA': '#FF5A36', 'corB': '#2BB8FF', 'vs': True, 'textoVs': 'VS'}
COR_VS = '#FFD23F'          # selo amarelo com letra escura: aparece bem em cima de qualquer cor de jogo
COR_DIVISA = '#FFFFFF'


def _par(n: float) -> int:
    return int(n) // 2 * 2


def _comp(tpl: dict) -> dict:
    c = dict(PADRAO)
    c.update({k: v for k, v in (tpl.get('comp') or {}).items() if v is not None})
    return c


def geometria(tpl: dict, L: int, A: int) -> dict:
    """Onde fica cada lado no vídeo final. Vertical e quadrado: A em cima, B embaixo. 16:9: A à esquerda, B à direita."""
    div = max(35, min(65, float(tpl.get('divisao') or 50))) / 100
    esp = max(6, _par(min(L, A) * 0.012))                     # espessura da faixa que separa os dois lados
    if L > A:
        w1 = _par(L * div)
        return {'empilhado': False, 'pa': (w1, A), 'pb': (L - w1, A), 'corte': w1, 'esp': esp, 'centro': (w1, A // 2)}
    h1 = _par(A * div)
    return {'empilhado': True, 'pa': (L, h1), 'pb': (L, A - h1), 'corte': h1, 'esp': esp, 'centro': (L // 2, h1)}


def _recorte(r: dict) -> str:
    return f"crop=iw*{r['w']:.4f}:ih*{r['h']:.4f}:iw*{r['x']:.4f}:ih*{r['y']:.4f}"


def filtro_quadro(tpl: dict, L: int, A: int, entrada: str = '[0:v]', saida: str = '[v0]') -> str:
    """Parte do filtro do FFmpeg: recorta os dois lados do mesmo quadro, junta e desenha a faixa do meio."""
    c, g = _comp(tpl), geometria(tpl, L, A)
    (wa, ha), (wb, hb) = g['pa'], g['pb']
    lado = lambda r, w, h, nome: f"[{nome}]{_recorte(r)},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1[{nome}p]"
    juntar = 'vstack' if g['empilhado'] else 'hstack'
    e, k = g['esp'], g['corte']
    faixa = (f"drawbox=x=0:y={k - e // 2}:w={L}:h={e}:color=0x{COR_DIVISA[1:]}:t=fill" if g['empilhado']
             else f"drawbox=x={k - e // 2}:y=0:w={e}:h={A}:color=0x{COR_DIVISA[1:]}:t=fill")
    return (f"{entrada}split=2[ca][cb];{lado(c['a'], wa, ha, 'ca')};{lado(c['b'], wb, hb, 'cb')};"
            f"[cap][cbp]{juntar}=inputs=2,{faixa}{saida}")


def _ass_cor(hexa: str) -> str:
    h = hexa.lstrip('#')
    return f'&H00{h[4:6]}{h[2:4]}{h[0:2]}&'.upper()


def _ass_txt(s: str) -> str:
    return s.replace('\\', '').replace('{', '(').replace('}', ')').replace('\n', ' ')


def _circulo(r: float) -> str:
    """Desenho de um círculo em comandos do ASS (curvas de Bézier), de 0 a 2r."""
    k = 0.5523 * r
    d = 2 * r
    p = lambda *v: ' '.join(f'{x:.0f}' for x in v)
    return (f'm {p(r, 0)} b {p(r + k, 0, d, r - k, d, r)} b {p(d, r + k, r + k, d, r, d)} '
            f'b {p(r - k, d, 0, r + k, 0, r)} b {p(0, r - k, r - k, 0, r, 0)}')


def ass_estilos(tpl: dict, L: int, A: int) -> list:
    """Estilos do ASS para os rótulos e o selo (caixa cheia na cor de cada lado, letra branca)."""
    c = _comp(tpl)
    t = min(L, A) * 0.05
    caixa = lambda nome, cor: (f'Style: {nome},Inter,{t:.0f},&H00FFFFFF&,&H00FFFFFF&,{_ass_cor(cor)},{_ass_cor(cor)},-1,0,0,0,100,100,1,0,3,'
                               f'{t * 0.32:.1f},0,5,0,0,0,1')
    return [caixa('CompA', c['corA']), caixa('CompB', c['corB']),
            f'Style: CompVs,Inter,{t * 1.05:.0f},&H00111111&,&H00111111&,&H00111111&,&H00000000&,-1,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1']


def ass_eventos(tpl: dict, L: int, A: int, dur: float) -> list:
    """(início, fim, estilo, texto, camada) dos rótulos e do selo VS, com entrada animada nos primeiros instantes."""
    c, g = _comp(tpl), geometria(tpl, L, A)
    t = min(L, A) * 0.05
    m = min(L, A) * 0.05                       # distância da borda
    folga = g['esp'] / 2 + t * 0.32 + t * 0.35  # rótulo encostado na faixa, sem tocar nela
    k = g['corte']
    ev = []
    if g['empilhado']:
        pos_a = ('\\an1', m, k - folga, -L * 0.6)        # A: canto de baixo à esquerda do lado de cima
        pos_b = ('\\an9', L - m, k + folga, L * 1.6)     # B: canto de cima à direita do lado de baixo
    else:
        pos_a = ('\\an1', m, A - m * 1.4, -L * 0.4)
        pos_b = ('\\an3', L - m, A - m * 1.4, L * 1.4)
    for estilo, txt, (an, x, y, x0), atraso in (('CompA', c['rotuloA'], pos_a, 0), ('CompB', c['rotuloB'], pos_b, 120)):
        txt = _ass_txt(str(txt).strip().upper())
        if txt:
            ev.append((0, dur, estilo, f'{{{an}\\move({x0:.0f},{y:.0f},{x:.0f},{y:.0f},{atraso},{atraso + 380})}}{txt}', 2))
    if c.get('vs', True):
        r = t * 1.15
        cx, cy = g['centro']
        pulo = '\\fscx0\\fscy0\\t(150,330,\\fscx118\\fscy118)\\t(330,430,\\fscx100\\fscy100)'
        ev.append((0, dur, 'CompVs', f'{{\\an5\\pos({cx},{cy})\\bord{g["esp"] * 0.6:.0f}\\3c{_ass_cor(COR_DIVISA)}\\1c{_ass_cor(COR_VS)}{pulo}\\p1}}{_circulo(r)}{{\\p0}}', 3))
        ev.append((0, dur, 'CompVs', f'{{\\an5\\pos({cx},{cy + t * 0.04:.0f}){pulo}}}{_ass_txt(c.get("textoVs") or "VS")[:4].upper()}', 4))
    return ev
