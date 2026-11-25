"""Filtros de composição a partir de um EditPlan validado."""
from pathlib import Path

import contratos as ct
import projetos as pj
import renderizador as rd

_MEDIA = {'image/png': 'png_pipe', 'image/jpeg': 'jpeg_pipe', 'image/webp': 'webp_pipe',
          'video/mp4': 'mov', 'video/quicktime': 'mov'}


def _entrada(cmd: list, asset: str) -> dict:
    midia = pj.asset(asset)
    formato = _MEDIA.get(midia['mime'])
    if not formato:
        raise ct.ErroContrato('A composição aceita PNG, JPEG, WebP ou vídeo MP4/MOV.')
    if rd.sha256(Path(midia['caminho'])) != midia['sha256']:
        raise ct.ErroContrato('O conteúdo do asset visual mudou depois do registro.')
    cmd.extend(['-protocol_whitelist', 'file', '-f', formato, '-i', midia['caminho']])
    return midia


def requisitos(e: dict) -> set[str]:
    if e['tipo'] == 'mascara':
        return {'drawbox'}
    if e['tipo'] == 'desfoque_movimento':
        return {'tmix'}
    nomes = {'scale', 'format', 'setsar', 'setpts', 'overlay'}
    if e.get('chroma'):
        nomes.add('chromakey')
    if e.get('mascara_asset'):
        nomes.add('alphamerge')
    return nomes


def _trajeto(keyframes: list, eixo: str, pixels: int, inicio: float) -> str:
    ultimo = keyframes[-1][eixo] * pixels
    expr = f'{ultimo:.4f}'
    for pronto, proximo in reversed(list(zip(keyframes, keyframes[1:]))):
        a, b = (inicio + q['ms'] / 1000 for q in (pronto, proximo))
        p = f'clip((t-{a:.3f})/{b-a:.3f},0,1)'
        if proximo['easing'] == 'suave':
            p = f'(({p})^2*(3-2*({p})))'
        pos = pronto[eixo] * pixels
        delta = (proximo[eixo] - pronto[eixo]) * pixels
        expr = f'if(lt(t,{b:.3f}),{pos:.4f}+({delta:.4f})*({p}),{expr})'
    return f"'{expr}'"


def aplicar(e: dict, cmd: list, filtros: list, atual: str, indice: int, entrada: int,
            largura: int, altura: int, total: float) -> tuple[int, dict]:
    a, b = e['ini_ms'] / 1000, e['fim_ms'] / 1000
    if not 0 <= a < b <= total + 0.001:
        raise ct.ErroContrato('Intervalo da composição passa da duração renderizada.')
    ativo = f"enable='gte(t,{a:.3f})*lt(t,{b:.3f})'"
    saida = f'[e{indice}]'
    tipo = e['tipo']
    if tipo == 'desfoque_movimento':
        filtros.append(f"{atual}tmix=frames={e.get('quadros', 3)}:{ativo}{saida}")
        return entrada, {}

    x, y = int(e['x'] * largura), int(e['y'] * altura)
    w, h = max(2, int(e['w'] * largura) // 2 * 2), max(2, int(e['h'] * altura) // 2 * 2)
    if tipo == 'mascara':
        filtros.append(f"{atual}drawbox=x={x}:y={y}:w={w}:h={h}:color=black@{e.get('opacidade', 1):.3f}:t=fill:{ativo}{saida}")
        return entrada, {}

    midia = _entrada(cmd, e['asset'])
    evidencias = {'asset_sha': midia['sha256']}
    camada = f'[camada{indice}]'
    cadeia = f'[{entrada}:v:0]scale={w}:{h},setsar=1,format=yuva420p,setpts=PTS-STARTPTS'
    entrada += 1
    if e.get('chroma'):
        cor = {'verde': '0x00ff00', 'azul': '0x0000ff'}[e['chroma']]
        cadeia += f",chromakey=color={cor}:similarity={e.get('similaridade', 0.14):.3f}:blend=0.03"
    filtros.append(cadeia + camada)
    if e.get('mascara_asset'):
        midia_mascara = _entrada(cmd, e['mascara_asset'])
        evidencias['mascara_sha'] = midia_mascara['sha256']
        filtros.extend([f'[{entrada}:v:0]scale={w}:{h},setsar=1,format=gray,setpts=PTS-STARTPTS[m{indice}]',
                        f'{camada}[m{indice}]alphamerge[alpha{indice}]'])
        entrada += 1
        camada = f'[alpha{indice}]'
    keyframes = e.get('keyframes')
    pos_x, pos_y = (_trajeto(keyframes, 'x', largura, a), _trajeto(keyframes, 'y', altura, a)) if keyframes else (x, y)
    filtros.extend([f'{camada}setpts=PTS+{a:.3f}/TB[tempo{indice}]',
                    f'{atual}[tempo{indice}]overlay=x={pos_x}:y={pos_y}:eval=frame:repeatlast=1:{ativo}{saida}'])
    if midia['mime'].startswith('image/') and not (e.get('chroma') or e.get('mascara_asset')) and (w, h) == (largura, altura):
        evidencias['imagem_estatica'] = [a, b]
    return entrada, evidencias
