"""Layout Comparação (tela dividida): template, biblioteca e o corte de verdade com o FFmpeg (agente.editar)."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
_tmp = tempfile.mkdtemp()
os.environ['DADOS'] = _tmp
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agente as ag, comparacao as cmp, modelos as mo, postagem as pg  # noqa: E402

ok = falhas = 0


def check(c, m):
    global ok, falhas
    if c:
        ok += 1
    else:
        falhas += 1
        print('  FALHOU:', m)


def info(p):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=width,height:format=duration', '-of', 'json', str(p)], capture_output=True, text=True)
    j = json.loads(r.stdout)
    v = next(s for s in j['streams'] if s.get('width'))
    return v['width'], v['height'], float(j['format']['duration'])


def pixel(p, t, x, y, L, A):
    raw = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-ss', str(t), '-i', str(p), '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    i = (int(y) * L + int(x)) * 3
    return tuple(raw[i:i + 3])


# --- template: limpar e tpl
m = mo.limpar(next(x for x in mo.PADROES if x['id'] == 'comparacao'))
check(m['layout'] == 'comparacao' and m['divisao'] == 50, 'layout e divisão padrão')
check(m['comp']['rotuloA'] == 'ANTES' and m['comp']['vs'], 'comp padrão')
lixo = mo.limpar(dict(m, comp={'a': {'x': 'x'}, 'rotuloA': 'A' * 99, 'corA': 'vermelho', 'textoVs': 'VERSUS'}))
check(lixo['comp']['a'] == cmp.PADRAO['a'] and len(lixo['comp']['rotuloA']) == 24 and lixo['comp']['corA'] == '#FF5A36' and lixo['comp']['textoVs'] == 'VERS',
      'comp inválido volta ao padrão / corta')
check(mo.tpl(m)['enquadramento'] == 'comparacao' and mo.tpl(m)['comp']['rotuloB'] == 'DEPOIS', 'tpl leva o comp')
velho = mo.limpar({'id': 'x', 'layout': 'desfoque'})
check(velho['comp'] == cmp.PADRAO or velho['comp']['rotuloA'] == 'ANTES', 'modelo antigo ganha comp padrão')

# --- biblioteca: o modelo novo entra uma vez em quem já tinha biblioteca; apagado não volta
pg._gravar(mo.ARQ, {'atualizado': 1, 'modelos': [mo.limpar(mo.PADROES[0])]})
b = mo.biblioteca()
check([x['id'] for x in b['modelos']] == ['padrao', 'comparacao'], f'entrou na biblioteca antiga: {[x["id"] for x in b["modelos"]]}')
mo.salvar({'atualizado': 2, 'modelos': [mo.limpar(mo.PADROES[0])]})
check([x['id'] for x in mo.biblioteca()['modelos']] == ['padrao'], 'apagado não volta')

# --- geometria
g = cmp.geometria({'divisao': 50}, 1080, 1920)
check(g['empilhado'] and g['pa'] == (1080, 960) and g['pb'] == (1080, 960), f'9:16 empilhado {g}')
g = cmp.geometria({'divisao': 50}, 1920, 1080)
check(not g['empilhado'] and g['pa'] == (960, 1080), f'16:9 lado a lado {g}')
g = cmp.geometria({'divisao': 99}, 1080, 1920)
check(g['pa'][1] == cmp._par(1920 * 0.65), 'divisão limitada a 65%')

# --- Agente 1: sorteio do arranjo
import random  # noqa: E402
vistos = set()
for sem in range(30):
    t = mo.tpl(m)
    arr = cmp.sortear_arranjo(t, random.Random(sem))
    vistos.add(arr)
    check(t['comp']['arranjo'] == arr, 'arranjo gravado no tpl')
check(vistos == {'empilhado', 'lado'}, f'sorteia os dois arranjos: {vistos}')
t = mo.tpl(m)
check(cmp.sortear_arranjo(t, random.Random(1), 'lado') == 'lado', 'refazer mantém o arranjo')
check(cmp.sortear_arranjo(mo.tpl(mo.limpar(dict(m, comp=dict(m['comp'], arranjo='empilhado')))), random.Random(1)) == 'empilhado', 'arranjo fixo não sorteia')
check(cmp.sortear_arranjo(mo.tpl(mo.limpar(mo.PADROES[0])), random.Random(1)) == '', 'outros templates não sorteiam')
g = cmp.geometria({'comp': {'arranjo': 'lado'}}, 1080, 1920)
check(not g['empilhado'] and g['pa'] == (540, 1920), f'lado a lado no 9:16: {g}')
import aprendizado as apr  # noqa: E402
check(apr.variaveis_do_corte({'arranjo': 'lado'})['arranjo'] == 'Lado a lado' and 'arranjo' in apr.VARIAVEIS, 'aprendizado compara o arranjo')

# --- corte de verdade: fonte lado a lado (esquerda vermelha, direita azul)
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    fonte = d / 'fonte.mp4'
    subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=0xC02020:s=640x720:r=30:d=6', '-f', 'lavfi', '-i', 'color=c=0x2040D0:s=640x720:r=30:d=6',
                    '-f', 'lavfi', '-i', 'sine=frequency=440:d=6', '-filter_complex', '[0:v][1:v]hstack=inputs=2[v]', '-map', '[v]', '-map', '2:a',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(fonte)], check=True)
    palavras = [(1 + i * 0.4, 1.35 + i * 0.4, w) for i, w in enumerate('olha a diferença da água'.split())]
    corte = {'ini': 0.0, 'fim': 5.0, 'gancho': 'QUAL FICOU MELHOR?'}
    for fmt, estilo, pos, arr in (('9:16', '', 'meio', 'empilhado'), ('1:1', 'cinema_noturno', 'baixo', 'sortear'), ('16:9', 'gamer_neon', 'baixo', 'sortear'),
                                  ('9:16', '', 'meio', 'lado')):
        mm = mo.limpar(dict(m, formato=fmt, resolucao=720, estiloVisual=estilo, legendaPos=pos,
                            comp=dict(m['comp'], rotuloA='Jogo antigo', rotuloB='Jogo novo', arranjo=arr)))
        t = mo.tpl(mm)
        o = d / f'saida-{fmt.replace(":", "x")}-{arr}.mp4'
        try:
            ag.editar(fonte, corte, palavras, t, o, d)
        except Exception as e:  # noqa: BLE001
            check(False, f'{fmt}: {str(e)[-300:]}')
            continue
        L, A, du = info(o)
        Le, Ae = ag._dims(t)
        check((L, A) == (Le, Ae), f'{fmt}: tamanho {L}x{A}')
        check(abs(du - 5.0) < 0.3, f'{fmt}: duração {du}')
        if fmt == '9:16' and arr == 'lado':
            esq, dir_ = pixel(o, 3, L * 0.25, A * 0.3, L, A), pixel(o, 3, L * 0.75, A * 0.3, L, A)
            check(esq[0] > esq[2] + 60 and dir_[2] > dir_[0] + 60, f'9:16 lado a lado: {esq} {dir_}')
        if fmt == '9:16' and arr == 'empilhado':
            cima, baixo = pixel(o, 3, L * 0.5, A * 0.3, L, A), pixel(o, 3, L * 0.5, A * 0.62, L, A)
            check(cima[0] > cima[2] + 60 and baixo[2] > baixo[0] + 60, f'A (vermelho) em cima e B (azul) embaixo: {cima} {baixo}')
            faixa = pixel(o, 3, L * 0.1, A * 0.5, L, A)
            check(min(faixa) > 200, f'faixa branca na divisa: {faixa}')
            vs = pixel(o, 0.6, L * 0.5 - (min(L, A) * 0.05), A * 0.5, L, A)
            check(vs[0] > 200 and vs[1] > 170 and vs[2] < 120, f'selo VS amarelo no meio na abertura: {vs}')
            vs = pixel(o, 3, L * 0.5 - (min(L, A) * 0.05), A * 0.5, L, A)
            check(not (vs[0] > 200 and vs[1] > 170 and vs[2] < 120), f'com legenda no meio o selo some depois: {vs}')
            ass = ag.montar_ass(palavras, 0, 5, t, 'X', L, A)
            check('JOGO ANTIGO' in ass and 'JOGO NOVO' in ass and 'CompVs' in ass, 'rótulos no ASS')
            leg = ass.split('Style: Leg')[1].split('\n')[0]
            check(leg.split(',')[18] == '5', f'legenda "no meio" fica no meio: {leg}')
            check('\\an7' in ass and '0:00:01.00,CompVs' in ass, 'legenda no meio: rótulo A no canto de cima e selo VS só no primeiro segundo')
        if fmt == '16:9':
            esq, dir_ = pixel(o, 3, L * 0.25, A * 0.5, L, A), pixel(o, 3, L * 0.75, A * 0.5, L, A)
            check(esq[0] > esq[2] and dir_[2] > dir_[0], f'16:9 lado a lado: {esq} {dir_}')

    # sem selo e sem rótulos também funciona
    mm = mo.limpar(dict(m, resolucao=720, comp=dict(m['comp'], vs=False, rotuloA='', rotuloB='')))
    o = d / 'limpo.mp4'
    ag.editar(fonte, corte, [], mo.tpl(mm), o, d)
    check(o.exists() and o.stat().st_size > 2000, 'sem selo e sem rótulos')
    check('CompVs' not in ag.montar_ass([], 0, 5, mo.tpl(mm), '', 720, 1280).split('[Events]')[1], 'sem selo no ASS')

print(f'{ok} ok, {falhas} falhas')
sys.exit(1 if falhas else 0)
