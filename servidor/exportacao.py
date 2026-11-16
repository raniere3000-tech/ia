"""Exportação da Montagem manual feita no servidor (alternativa à gravação no navegador).

O site manda um MANIFESTO (dados, nunca código): quadros com a mídia (arquivo já enviado), início, duração, animação e
legendas, mais o áudio já mixado no navegador. O servidor faz cada quadro como um pedaço separado (guardado por hash:
se um falhar, só ele é refeito na próxima tentativa), junta com transição e legenda e confere o resultado.
Quando algo dá errado, o diagnóstico diz qual quadro, em que segundo, qual mídia e o comando do FFmpeg usado.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path

import banco as db
import estilos_codigo as ec
import fila
import postagem as pg
import projetos as pj
import renderizador as rd

ANIMS = ('zoom-in', 'zoom-out', 'pan-esq', 'pan-dir', 'tremer', 'parado')
EFEITOS = ('nenhum', 'blur-background', 'virada-cena', 'transicao-fade', 'camera-shake', 'pb', 'vinheta')
FPS = 30
TRANS = 0.4
GRUPO = int(os.getenv('EXPORT_GRUPO', '20'))
MAX_QUADROS = 300
MAX_TOTAL = 20 * 60
PASTA = pg.DADOS / 'exportacoes'


class ErroExport(pj.ErroProjeto):
    pass


def _num(v, lo, hi):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ErroExport(400, 'Número inválido no manifesto.')
    if x != x or not lo <= x <= hi:
        raise ErroExport(400, f'Valor fora da faixa no manifesto ({x}).')
    return x


def validar(m: dict) -> dict:
    """Confere o manifesto inteiro antes de pôr na fila: só campos conhecidos, números em faixas e arquivos que existem."""
    if not isinstance(m, dict):
        raise ErroExport(400, 'Manifesto inválido.')
    formato = m.get('formato') if m.get('formato') in ec.FORMATOS else '9:16'
    qs = m.get('quadros')
    if not isinstance(qs, list) or not qs:
        raise ErroExport(400, 'Nenhum quadro para exportar.')
    if len(qs) > MAX_QUADROS:
        raise ErroExport(400, f'No máximo {MAX_QUADROS} quadros por exportação.')
    out, t = [], 0.0
    for i, q in enumerate(qs):
        if not isinstance(q, dict):
            raise ErroExport(400, f'Quadro {i + 1} inválido.')
        aid = str(q.get('asset') or '')
        midia = None
        if aid:
            if not re.fullmatch(r'\w{4,40}', aid):
                raise ErroExport(400, f'Quadro {i + 1}: arquivo inválido.')
            a = pj.asset(aid)
            tipo = 'video' if a['mime'].startswith('video/') else 'imagem' if a['mime'].startswith('image/') else ''
            if not tipo:
                raise ErroExport(400, f'Quadro {i + 1}: o arquivo "{a["nome"]}" não é imagem nem vídeo.')
            midia = {'asset': aid, 'tipo': tipo, 'sha256': a['sha256'], 'nome': a['nome']}
        dur = _num(q.get('dur'), 0.2, MAX_TOTAL)
        leg = []
        for lg in (q.get('legendas') or [])[:40]:
            if isinstance(lg, dict) and str(lg.get('texto') or '').strip():
                a0, a1 = _num(lg.get('ini'), 0, dur + 1), _num(lg.get('fim'), 0, dur + 1)
                if a1 > a0:
                    leg.append({'ini': a0, 'fim': a1, 'texto': re.sub(r'[\x00-\x1f{}\\]', ' ', str(lg['texto']))[:200]})
        entrada = q.get('entrada') if q.get('entrada') in ('fade', 'corte') else ('fade' if m.get('transicao') == 'fade' else 'corte')
        out.append({'n': int(_num(q.get('n', i + 1), 0, 10000)), 'ini': round(t, 3), 'dur': round(dur, 3), 'anim': q.get('anim') if q.get('anim') in ANIMS else 'parado',
                    'midia': midia, 'visual': str(q.get('visual') or '')[:120], 'legendas': leg, 'entrada': 'corte' if i == 0 else entrada,
                    'de': round(_num(q.get('de', 0), 0, 36000), 3) if midia and midia['tipo'] == 'video' else 0,
                    'brilho': int(_num(q.get('brilho', 100), 0, 300)), 'contraste': int(_num(q.get('contraste', 100), 0, 300)),
                    'saturacao': int(_num(q.get('saturacao', 100), 0, 300)), 'efeito': q.get('efeito') if q.get('efeito') in EFEITOS else 'nenhum'})
        t += dur
    if t > MAX_TOTAL:
        raise ErroExport(400, 'O vídeo passa de 20 minutos. Divida em partes.')
    audio = None
    if m.get('audio'):
        a = pj.asset(str(m['audio']))
        if not a['mime'].startswith('audio/'):
            raise ErroExport(400, 'O áudio do manifesto não é um arquivo de som.')
        audio = {'asset': a['id'], 'sha256': a['sha256']}
    textos = []
    for x in (m.get('textos') or [])[:400]:
        if isinstance(x, dict) and str(x.get('texto') or '').strip():
            a0, a1 = _num(x.get('ini'), 0, MAX_TOTAL), _num(x.get('fim'), 0, MAX_TOTAL)
            if a1 > a0:
                cor = str(x.get('cor') or '#ffffff')
                textos.append({'ini': round(a0, 3), 'fim': round(min(a1, t), 3), 'texto': re.sub(r'[\x00-\x09\x0b-\x1f{}\\]', ' ', str(x['texto']))[:300],
                               'pos': x.get('pos') if x.get('pos') in ('topo', 'meio', 'baixo') else 'baixo', 'tam': int(_num(x.get('tam', 100), 30, 400)),
                               'cor': cor.lower() if re.fullmatch(r'#[0-9a-fA-F]{6}', cor) else '#ffffff', 'fundo': bool(x.get('fundo'))})
    return {'formato': formato, 'legendas': bool(m.get('legendas', True)), 'textos': textos,
            'quadros': out, 'audio': audio, 'total': round(t, 3), 'nome': re.sub(r'[^\w .-]', '', str(m.get('nome') or 'montagem'))[:60] or 'montagem'}


def pedir(m: dict, quem: str) -> dict:
    """Mesmo manifesto = mesmo trabalho: pronto devolve o vídeo já feito; falhou é tentado de novo (reaproveitando os quadros prontos)."""
    v = validar(m)
    chave = 'export-' + hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()[:20]
    ja = db.um('SELECT * FROM jobs WHERE chave=?', chave)
    if ja and ja['status'] in ('falhou', 'cancelado', 'aguardando_tentativa'):
        j = fila.tentar_de_novo(ja['id'])
    elif ja and ja['status'] == 'concluido' and not _video_existe(ja):
        db.executar('UPDATE jobs SET chave=NULL WHERE id=?', ja['id'])
        j = None
    else:
        j = ja
    if not j:
        j = fila.enfileirar('manual.exportar', agente='editor', dados={'manifesto': v}, recurso='pesado', titulo=f'Exportar "{v["nome"]}" no servidor',
                            chave=chave, max_tentativas=2)
    db.evento(quem, 'export_pedido', 'job:' + j['id'], {'quadros': len(v['quadros']), 'total': v['total']})
    return {'job': j['id'], 'total': v['total'], 'quadros': len(v['quadros'])}


def _video_existe(j: dict) -> bool:
    try:
        pj.asset(json.loads(j['resultado'] or '{}')['asset'])
        return True
    except (KeyError, ValueError, TypeError, pj.ErroProjeto):
        return False


def _filtro_midia(q: dict, W: int, H: int, dur: float) -> str:
    """Cobre a tela e aplica a animação do quadro (mesma ideia da prévia do navegador)."""
    fr = max(1, int(dur * FPS))
    cobre = f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1'
    a = q['anim']
    if a == 'parado':
        return cobre + f',fps={FPS}'
    if q['midia']['tipo'] == 'video':   # vídeo: só um leve movimento por crop, sem zoompan (que trava o tempo do vídeo)
        if a == 'tremer':
            return cobre.replace(f'crop={W}:{H}', f"scale=iw*1.06:ih*1.06,crop={W}:{H}:x='(iw-ow)/2+sin(t*90/{dur:.3f})*{W * 0.012:.1f}*max(0,1-t*3/{dur:.3f})':y='(ih-oh)/2'") + f',fps={FPS}'
        return cobre + f',fps={FPS}'
    S = 2  # imagem: zoompan em resolução dobrada para não tremer
    z = {'zoom-in': f'1+0.12*on/{fr}', 'zoom-out': f'1.12-0.12*on/{fr}', 'pan-esq': '1.14', 'pan-dir': '1.14', 'tremer': '1.06'}[a]
    x = {'pan-esq': f'(iw-iw/zoom)*(1-on/{fr})', 'pan-dir': f'(iw-iw/zoom)*on/{fr}',
         'tremer': f'iw/2-iw/zoom/2+sin(on/{fr}*90)*{W * S * 0.012:.1f}*max(0,1-on/{fr}*3)'}.get(a, 'iw/2-iw/zoom/2')
    return (f'scale={W * S}:{H * S}:force_original_aspect_ratio=increase,crop={W * S}:{H * S},setsar=1,'
            f"zoompan=z='{z}':x='{x}':y='ih/2-ih/zoom/2':d={fr}:s={W}x{H}:fps={FPS}")


def _pos_filtros(q: dict, W: int, H: int, dur: float) -> str:
    """Ajustes e efeitos do bloco (os mesmos do editor do site), depois da imagem já cobrir a tela."""
    f = []
    if q['brilho'] != 100:
        k = q['brilho'] / 100
        f.append(f'colorchannelmixer=rr={k:.3f}:gg={k:.3f}:bb={k:.3f}')
    if q['contraste'] != 100 or q['saturacao'] != 100:
        f.append(f"eq=contrast={q['contraste'] / 100:.3f}:saturation={q['saturacao'] / 100:.3f}")
    ef = q['efeito']
    if ef == 'pb':
        f.append('hue=s=0')
    if ef == 'camera-shake':   # pequenos tremores a cada 4 segundos
        W2, H2 = W + W // 32 * 2, H + H // 32 * 2
        f.append(f"scale={W2}:{H2},crop={W}:{H}:x='(iw-ow)/2+if(lt(mod(t,4),0.22),sin(t*91)*{W * 0.012:.1f},0)'"
                 f":y='(ih-oh)/2+if(lt(mod(t,4),0.22),cos(t*77)*{H * 0.01:.1f},0)'")
    if ef == 'vinheta':
        f.append('vignette=angle=PI/4.5')
    if ef == 'transicao-fade':
        d = min(0.4, dur / 2)
        f.append(f'fade=t=in:st=0:d={d:.3f},fade=t=out:st={dur - d:.3f}:d={d:.3f}')
    if ef == 'virada-cena':
        f.append(f'fade=t=in:st=0:d={min(0.35, dur):.3f}:color=white')
    return ','.join(f)


def comando_pedaco(q: dict, W: int, H: int, cauda: float, saida: Path) -> list:
    dur = q['dur']
    fim = ['-r', str(FPS), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-g', str(FPS * 2), str(saida)]
    if not q['midia']:
        return ['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', f'color=c=0x16161d:s={W}x{H}:r={FPS}:d={dur + cauda:.3f}', *fim]
    a = pj.asset(q['midia']['asset'])
    if q['midia']['tipo'] == 'imagem':
        entrada = ['-loop', '1', '-framerate', str(FPS), '-t', f'{dur:.3f}', '-i', a['caminho']]
    else:
        entrada = ['-stream_loop', '-1', *(['-ss', f"{q['de']:.3f}"] if q['de'] else []), '-t', f'{dur:.3f}', '-i', a['caminho']]
    if q['efeito'] == 'blur-background':   # imagem inteira no centro, fundo desfocado feito com ela mesma
        base = (f'[0:v]split=2[f0][b0];[b0]scale={W // 24}:{H // 24}:force_original_aspect_ratio=increase,crop={W // 24}:{H // 24},boxblur=2:1,'
                f'scale={W}:{H},setsar=1,colorchannelmixer=rr=.65:gg=.65:bb=.65[fundo];'
                f'[f0]scale={W}:{H}:force_original_aspect_ratio=decrease,setsar=1[frente];[fundo][frente]overlay=(W-w)/2:(H-h)/2,fps={FPS}')
    else:
        base = '[0:v]' + _filtro_midia(q, W, H, dur)
    pos = _pos_filtros(q, W, H, dur)
    vf = base + (',' + pos if pos else '') + f',trim=duration={dur:.3f},setpts=PTS-STARTPTS,format=yuv420p'
    if cauda:
        vf += f',tpad=stop_mode=clone:stop_duration={cauda:.3f}'
    return ['ffmpeg', '-nostdin', '-y', '-v', 'error', *entrada, '-an', '-filter_complex', vf + '[v]', '-map', '[v]', *fim]


def _cor_ass(hexa: str) -> str:
    return ('&H00%s%s%s' % (hexa[5:7], hexa[3:5], hexa[1:3])).upper()


def _ass(v: dict, W: int, H: int, arq: Path) -> Path | None:
    """Legendas das falas (por quadro) e os textos do editor (posição, tamanho, cor e fundo de cada um)."""
    fs = int(min(W, H) * 0.052)
    linhas = []
    if v['legendas']:
        for q in v['quadros']:
            for lg in q['legendas']:
                linhas.append((q['ini'] + lg['ini'], q['ini'] + min(lg['fim'], q['dur']), 'L', lg['texto'], ''))
    for x in v.get('textos') or []:
        est = {'topo': 'T', 'meio': 'M', 'baixo': 'L'}[x['pos']] + ('F' if x['fundo'] else '')
        tags = f"\\fs{int(fs * x['tam'] / 100)}" + (f"\\c{_cor_ass(x['cor'])}" if x['cor'] != '#ffffff' else '')
        linhas.append((x['ini'], x['fim'], est, x['texto'].replace('\n', '\\N'), '{' + tags + '}'))
    if not linhas:
        return None
    mv = int(H * (1 - (0.8 if H > W else 0.86)))
    estilos = ''
    for nome, alin, margem in (('L', 2, mv), ('T', 8, int(H * 0.08)), ('M', 5, 0)):
        for fundo in ('', 'F'):
            borda, contorno, fundo_cor = (3, max(2, fs // 5), '&H66000000') if fundo else (1, max(3, fs // 6), '&H00000000')
            estilos += (f'Style: {nome}{fundo},Inter,{fs},&H00FFFFFF,&H00FFFFFF,{fundo_cor if fundo else "&H00000000"},{fundo_cor},-1,0,0,0,100,100,0,0,'
                        f'{borda},{contorno},0,{alin},{int(W * 0.08)},{int(W * 0.08)},{margem},1\n')
    cab = ('[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 0\n\n[V4+ Styles]\n'
           'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, '
           'Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n%s\n'
           '[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n') % (W, H, estilos)
    corpo = ''.join(f'Dialogue: 0,{ec._ass_t(a)},{ec._ass_t(b)},{e},,0,0,0,,{tg}{t}\n' for a, b, e, t, tg in sorted(linhas))
    arq.write_text(cab + corpo, encoding='utf-8')
    return arq


def _diag(etapa: str, q: dict | None, cmd: list, erro: str) -> dict:
    d = {'etapa': etapa, 'erro': erro[-600:], 'comando': ' '.join(x if re.fullmatch(r'[\w./:=,+-]+', x) else repr(x) for x in cmd)[:3000]}
    if q:
        d.update(quadro=q['n'], inicio=q['ini'], fim=round(q['ini'] + q['dur'], 3), midia=(q['midia'] or {}).get('nome', 'sem mídia'),
                 timecode=f'{int(q["ini"] // 60):02d}:{q["ini"] % 60:05.2f}')
    return d


def _grafo_juntar(pedacos: list, base: int) -> tuple:
    """Encadeia os pedaços: mistura (xfade) onde o quadro entra suave, emenda (concat) onde é corte seco.
    Cada pedaço começa em `ini`; o anterior já traz a cauda da mistura, então o offset do xfade é o próprio início."""
    if len(pedacos) == 1:
        return f'[{base}:v]null[j0]', '[j0]'
    partes, ant, t0 = [], f'[{base}:v]', pedacos[0]['ini']
    for i in range(1, len(pedacos)):
        o = f'[j{i}]'
        p = pedacos[i]
        if p['tr'] > 0:
            partes.append(f"{ant}[{base + i}:v]xfade=transition=fade:duration={p['tr']:.3f}:offset={p['ini'] - t0:.3f}{o}")
        else:
            partes.append(f'{ant}[{base + i}:v]concat=n=2:v=1:a=0{o}')
        ant = o
    return ';'.join(partes), ant


def job_exportar(ctx):
    v = ctx.dados['manifesto']
    ctx.dados.pop('diagnostico', None)
    W, H = ec.FORMATOS[v['formato']]
    chave = hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()[:20]
    pasta = PASTA / chave
    pasta.mkdir(parents=True, exist_ok=True)
    if 0 <= rd.livre_mb(pasta) < rd.MIN_LIVRE_MB:
        raise fila.Esperar(1800, 'Pouco espaço livre no celular. Tento de novo em 30 min.')
    qs = v['quadros']
    # duração da transição na entrada de cada quadro (0 = corte seco); o quadro anterior ganha essa "cauda" para a mistura
    tr = [0.0] + [min(TRANS, q['dur'] / 2) if q['entrada'] == 'fade' else 0.0 for q in qs[1:]]
    pedacos, refeitos = [], 0
    for i, q in enumerate(qs):
        cauda = tr[i + 1] if i + 1 < len(qs) else 0.0
        visual = {k: q[k] for k in ('dur', 'anim', 'de', 'brilho', 'contraste', 'saturacao', 'efeito')}
        h = hashlib.sha256(json.dumps([q['midia'] and q['midia']['sha256'], visual, W, H, cauda, 2], sort_keys=True).encode()).hexdigest()[:20]
        arq = pasta / f'q{i:03d}-{h}.mp4'
        if not (arq.exists() and arq.stat().st_size > 1000):
            ctx.progresso(5 + 65 * i / len(qs), f'Fazendo o quadro {i + 1} de {len(qs)}')
            cmd = comando_pedaco(q, W, H, cauda, arq.with_suffix('.tmp.mp4'))
            try:
                if q['midia']:   # abre 1 quadro da mídia antes: arquivo estragado falha em segundos, não em minutos
                    rd.rodar(['ffmpeg', '-nostdin', '-v', 'error', '-i', pj.asset(q['midia']['asset'])['caminho'], '-frames:v', '1', '-f', 'null', '-'],
                             ctx.cancelado, tempo_max=60)
                rd.rodar(cmd, ctx.cancelado, tempo_max=max(300, q['dur'] * 60))
                d = rd.duracao(arq.with_suffix('.tmp.mp4'))
                if d < (q['dur'] + cauda) * 0.9:
                    raise rd.ErroRender(f'o pedaço ficou com {d:.2f}s em vez de {q["dur"] + cauda:.2f}s')
            except InterruptedError:
                raise fila.Cancelado()
            except (rd.ErroRender, pj.ErroProjeto) as e:
                ctx.dados['diagnostico'] = _diag('quadro', q, cmd, str(e))
                ctx.salvar()
                raise RuntimeError(f'O quadro {q["n"]} ({ctx.dados["diagnostico"]["timecode"]}, {ctx.dados["diagnostico"]["midia"]}) falhou: {e}. '
                                   'Os outros quadros ficaram guardados; tentar de novo refaz só este.')
            arq.with_suffix('.tmp.mp4').replace(arq)
            refeitos += 1
        pedacos.append({'arq': arq, 'ini': q['ini'], 'tr': tr[i]})
    # junção em grupos (cada grupo vira um vídeo; no celular, abrir centenas de vídeos de uma vez gastaria memória demais)
    rodada = 0
    while len(pedacos) > GRUPO:
        rodada += 1
        novos = []
        for g in range(0, len(pedacos), GRUPO):
            grupo = pedacos[g:g + GRUPO]
            ctx.progresso(70 + 8 * g / len(pedacos), f'Juntando os quadros (parte {g // GRUPO + 1})')
            out = pasta / (f'grupo-{rodada}-{g // GRUPO:03d}-' + hashlib.sha256(''.join(p['arq'].name for p in grupo).encode()).hexdigest()[:12] + '.mp4')
            if not (out.exists() and out.stat().st_size > 1000):
                grafo, fim = _grafo_juntar(grupo, 0)
                cmd = ['ffmpeg', '-nostdin', '-y', '-v', 'error', *sum((['-i', str(p['arq'])] for p in grupo), []), '-filter_complex', grafo, '-map', fim,
                       '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', str(FPS), '-g', str(FPS * 2), str(out.with_suffix('.tmp.mp4'))]
                try:
                    rd.rodar(cmd, ctx.cancelado, tempo_max=1800)
                except InterruptedError:
                    raise fila.Cancelado()
                except rd.ErroRender as e:
                    ctx.dados['diagnostico'] = _diag('juncao', None, cmd, str(e))
                    ctx.salvar()
                    raise RuntimeError(f'A junção de uma parte falhou: {e}. Os quadros prontos ficaram guardados.')
                out.with_suffix('.tmp.mp4').replace(out)
            novos.append({'arq': out, 'ini': grupo[0]['ini'], 'tr': grupo[0]['tr']})
        pedacos = novos
    ctx.progresso(80, 'Juntando os quadros, os textos e o som')
    saida = pasta / 'final.mp4'
    tmp = pasta / 'final.tmp.mp4'
    ass = _ass(v, W, H, pasta / 'legendas.ass')
    cmd = ['ffmpeg', '-nostdin', '-y', '-v', 'error', *sum((['-i', str(p['arq'])] for p in pedacos), [])]
    grafo, fim = _grafo_juntar(pedacos, 0)
    if ass:
        grafo += f";{fim}subtitles=filename='{ec._esc(ass)}':fontsdir='{ec._esc(ec.FONTE.parent)}'[vs]"
        fim = '[vs]'
    na = len(pedacos)
    if v['audio']:
        cmd += ['-i', pj.asset(v['audio']['asset'])['caminho']]
        amap = ['-map', f'{na}:a', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2', '-af', f'apad=whole_dur={v["total"]:.3f}']
    else:
        cmd += ['-f', 'lavfi', '-t', f'{v["total"]:.3f}', '-i', 'anullsrc=r=48000:cl=stereo']
        amap = ['-map', f'{na}:a', '-c:a', 'aac', '-b:a', '128k']
    cmd += ['-filter_complex', grafo, '-map', fim, *amap, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p',
            '-r', str(FPS), '-g', str(FPS * 2), '-t', f'{v["total"]:.3f}', '-movflags', '+faststart', str(tmp)]
    try:
        rd.rodar(cmd, ctx.cancelado, tempo_max=max(900, v['total'] * 30), progresso=lambda x: ctx.progresso(80 + 12 * x, 'Juntando os quadros, os textos e o som'),
                 dur=v['total'])
    except InterruptedError:
        raise fila.Cancelado()
    except rd.ErroRender as e:
        ctx.dados['diagnostico'] = _diag('juncao', None, cmd, str(e))
        ctx.salvar()
        raise RuntimeError(f'A junção final falhou: {e}. Os quadros prontos ficaram guardados.')
    tmp.replace(saida)
    ctx.progresso(93, 'Conferindo o vídeo (tela preta, congelado, duração)')
    conf = rd.conferir(saida, pasta, {'largura': W, 'altura': H, 'duracao': v['total']}, ctx.cancelado)
    # imagem parada é normal em quadros "parado": só avisa se o congelamento não bate com nenhum deles
    parados = [q for q in qs if q['anim'] == 'parado' and q['midia'] and q['midia']['tipo'] == 'imagem']
    if parados:
        conf['avisos'] = [a for a in conf['avisos'] if not a.startswith('Imagem parada')] + \
                         [f'{len(parados)} quadro(s) com imagem parada de propósito (animação "Parado").']
    if not v['audio']:   # vídeo sem som foi pedido assim: silêncio não é defeito
        conf['avisos'] = [a for a in conf['avisos'] if not a.startswith('Silêncio')]
    if not conf['ok']:
        ctx.dados['diagnostico'] = {'etapa': 'conferencia', 'erro': '; '.join(conf['erros'])}
        ctx.salvar()
        raise RuntimeError('O vídeo não passou na conferência: ' + '; '.join(conf['erros']))
    a = pj.registrar_asset(saida, f'{v["nome"]}.mp4', 'video/mp4', '', 'exportacao')['asset']
    shutil.rmtree(pasta / 'quadros', ignore_errors=True)
    r = {'asset': a['id'], 'duracao': conf['duracao'], 'avisos': conf['avisos'], 'refeitos': refeitos, 'reaproveitados': len(pedacos) - refeitos,
         'tamanho_mb': round(saida.stat().st_size / 1048576, 1)}
    return {'resultado': r, 'etapa': 'Pronto para baixar'}


def estado(jid: str) -> dict:
    j = fila.obter(jid)
    if not j or j['tipo'] != 'manual.exportar':
        raise ErroExport(404, 'Exportação não encontrada.')
    dados = json.loads(j['dados'] or '{}')
    res = json.loads(j['resultado']) if j.get('resultado') else None
    return {'id': j['id'], 'status': j['status'], 'etapa': j['etapa'], 'progresso': j['progresso'], 'erro': j['erro'], 'resultado': res,
            'diagnostico': dados.get('diagnostico'), 'tentativas': j['tentativas']}


def iniciar():
    fila.registrar('manual.exportar', job_exportar, 'pesado')
