"""Teste da exportação da Montagem manual no servidor (FFmpeg de verdade, sem internet).

Rodar: cd servidor && PYTHONPATH=. python3 testes/teste_exportacao.py
Cobre: manifesto inválido recusado, exportação com transição e legenda, quadro que falha com diagnóstico
(quadro, segundo, mídia, comando) e nova tentativa que refaz só o quadro que falhou.
"""
import json
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import subprocess
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='export-teste-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import banco as db  # noqa: E402
import exportacao as ex  # noqa: E402
import fila  # noqa: E402
import projetos as pj  # noqa: E402
import renderizador as rd  # noqa: E402

db.migrar()
ex.iniciar()
ok_n = falhas = 0


def confere(cond, nome):
    global ok_n, falhas
    ok_n += bool(cond)
    falhas += not cond
    print('  ok ' if cond else '  FALHOU', nome)


def gerar(nome, args):
    arq = TMP / nome
    subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', *args, str(arq)], check=True)
    return arq


img1 = gerar('a.png', ['-f', 'lavfi', '-i', 'testsrc2=s=800x600:d=1', '-frames:v', '1'])
img2 = gerar('b.jpg', ['-f', 'lavfi', '-i', 'mandelbrot=s=600x900', '-frames:v', '1'])
vid = gerar('c.mp4', ['-f', 'lavfi', '-i', 'testsrc=s=640x360:r=25:d=1.5', '-pix_fmt', 'yuv420p'])
som = gerar('s.wav', ['-f', 'lavfi', '-i', 'sine=f=440:d=6', '-ac', '2'])
A = {k: pj.registrar_asset(p, p.name, m)['asset']['id'] for k, p, m in
     (('a', img1, 'image/png'), ('b', img2, 'image/jpeg'), ('c', vid, 'video/mp4'), ('s', som, 'audio/wav'))}


def rodar(jid):
    j = fila.obter(jid)
    ctx = fila.Contexto(j)
    try:
        r = ex.job_exportar(ctx)
        return r, None
    except Exception as e:  # noqa: BLE001
        return None, e


print('Manifesto')
for ruim, nome in (({'quadros': []}, 'sem quadros'), ({'quadros': [{'dur': 0}]}, 'duração zero'),
                   ({'quadros': [{'dur': 2, 'asset': A['s']}]}, 'áudio no lugar de imagem'),
                   ({'quadros': [{'dur': 2, 'asset': '../../etc'}]}, 'caminho estranho'),
                   ({'quadros': [{'dur': 2}], 'audio': A['a']}, 'imagem no lugar do áudio')):
    try:
        ex.validar(ruim)
        confere(False, f'recusa {nome}')
    except pj.ErroProjeto as e:
        confere(e.status in (400, 404), f'recusa {nome}')

M = {'formato': '9:16', 'transicao': 'fade', 'nome': 'Minha montagem', 'audio': A['s'],
     'quadros': [{'asset': A['a'], 'dur': 2, 'anim': 'zoom-in', 'legendas': [{'ini': 0.1, 'fim': 1.8, 'texto': 'Primeira parte'}]},
                 {'asset': A['c'], 'dur': 1.5, 'anim': 'tremer'},
                 {'asset': A['b'], 'dur': 2.5, 'anim': 'parado', 'legendas': [{'ini': 0, 'fim': 2, 'texto': 'Fim {com} chaves'}]}]}
v = ex.validar(M)
confere(v['total'] == 6.0 and v['quadros'][1]['midia']['tipo'] == 'video', 'manifesto válido: total e tipos certos')
confere('{' not in v['quadros'][2]['legendas'][0]['texto'], 'legenda sem chaves (não vira comando de estilo)')

print('Exportação com quadro que falha')
caminho_b = Path(pj.asset(A['b'])['caminho'])
guardado = caminho_b.read_bytes()
caminho_b.write_bytes(b'isto nao e uma imagem')   # o arquivo continua existindo, mas o FFmpeg não consegue ler
p = ex.pedir(M, 'teste')
confere(p['quadros'] == 3 and p['total'] == 6.0, 'pedido entra na fila')
r, erro = rodar(p['job'])
d = json.loads(fila.obter(p['job'])['dados']).get('diagnostico') or {}
confere(erro is not None and 'quadro 3' in str(erro), 'falha diz qual quadro')
confere(d.get('quadro') == 3 and d.get('timecode') == '00:03.50' and d.get('midia') == 'b.jpg' and 'ffmpeg' in d.get('comando', ''),
        'diagnóstico tem quadro, segundo, mídia e comando')
st = ex.estado(p['job'])
confere(st['diagnostico'] and st['diagnostico']['quadro'] == 3, 'estado devolve o diagnóstico')

print('Nova tentativa refaz só o quadro que falhou')
caminho_b.write_bytes(guardado)
r, erro = rodar(p['job'])
confere(erro is None and r, f'exportação termina ({erro})')
if r:
    res = r['resultado']
    confere(res['refeitos'] == 1 and res['reaproveitados'] == 2, 'só 1 quadro refeito, 2 reaproveitados')
    final = Path(pj.asset(res['asset'])['caminho'])
    info = rd.sonda(final)
    vs = [s for s in info['streams'] if s['codec_type'] == 'video'][0]
    confere((vs['width'], vs['height']) == (1080, 1920), 'vídeo 1080x1920')
    confere(abs(res['duracao'] - 6.0) < 0.3, f'duração certa ({res["duracao"]}s)')
    confere(any(s['codec_type'] == 'audio' for s in info['streams']), 'tem som')
    confere(any('de propósito' in a for a in res['avisos']), 'aviso de imagem parada explica que foi de propósito')

print('Corte seco, sem áudio e sem legenda')
M2 = {'formato': '1:1', 'transicao': 'corte', 'legendas': False,
      'quadros': [{'asset': A['a'], 'dur': 1, 'anim': 'pan-dir'}, {'dur': 1}, {'asset': A['c'], 'dur': 1}]}
p2 = ex.pedir(M2, 'teste')
r, erro = rodar(p2['job'])
confere(erro is None and r and abs(r['resultado']['duracao'] - 3) < 0.3, f'corte seco funciona ({erro})')

print('Editor: corte e transição misturados, efeitos, textos e junção em partes')
ex.GRUPO = 2
M3 = {'formato': '16:9', 'nome': 'Editor', 'audio': A['s'],
      'textos': [{'ini': 0.2, 'fim': 2.5, 'texto': 'Título no topo', 'pos': 'topo', 'tam': 140, 'cor': '#ffd400', 'fundo': True},
                 {'ini': 1, 'fim': 4, 'texto': 'Linha 1\nLinha 2', 'pos': 'baixo', 'tam': 100, 'cor': 'vermelho', 'fundo': False}],
      'quadros': [{'asset': A['a'], 'dur': 1.2, 'anim': 'zoom-out', 'efeito': 'virada-cena', 'brilho': 130},
                  {'asset': A['b'], 'dur': 1.2, 'entrada': 'fade', 'efeito': 'blur-background'},
                  {'asset': A['c'], 'dur': 1.0, 'entrada': 'corte', 'de': 0.5, 'efeito': 'pb'},
                  {'asset': A['a'], 'dur': 1.0, 'entrada': 'fade', 'efeito': 'camera-shake', 'saturacao': 40, 'contraste': 120},
                  {'asset': A['b'], 'dur': 1.0, 'entrada': 'corte', 'efeito': 'vinheta'},
                  {'dur': 0.6, 'entrada': 'fade', 'efeito': 'transicao-fade'}]}
v3 = ex.validar(M3)
confere(v3['textos'][1]['cor'] == '#ffffff' and v3['quadros'][0]['entrada'] == 'corte', 'cor estranha vira branco; 1º quadro sempre entra seco')
p3 = ex.pedir(M3, 'teste')
r, erro = rodar(p3['job'])
confere(erro is None and r and abs(r['resultado']['duracao'] - 6.0) < 0.3, f'exporta com todos os efeitos e junção em partes ({erro})')
if r:
    final = Path(pj.asset(r['resultado']['asset'])['caminho'])
    for t, nome in ((0.6, 'inicio'), (2.0, 'fade'), (2.9, 'pb'), (3.6, 'shake')):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(t), '-i', str(final), '-frames:v', '1', str(TMP / f'q-{nome}.png')], check=True)
    print('     quadros em', TMP)
ass = (ex.PASTA / next(d.name for d in ex.PASTA.iterdir() if (d / 'legendas.ass').exists() and 'Título' in (d / 'legendas.ass').read_text())) / 'legendas.ass'
txt = ass.read_text()
confere('Style: TF' in txt and '\\c&H0000D4FF' in txt and 'Linha 1\\NLinha 2' in txt, 'textos com posição, cor, fundo e quebra de linha')

print('Pedir de novo o mesmo vídeo')
if r:
    db.executar("UPDATE jobs SET status='concluido', resultado=? WHERE id=?", json.dumps(r['resultado']), p3['job'])
    confere(ex.pedir(M3, 'teste')['job'] == p3['job'], 'vídeo já pronto: devolve o mesmo, sem refazer')
db.executar("UPDATE jobs SET status='falhou' WHERE id=?", p['job'])
p4 = ex.pedir(M, 'teste')
confere(p4['job'] == p['job'] and fila.obter(p['job'])['status'] == 'na_fila', 'vídeo que falhou: o mesmo trabalho volta para a fila')

print(f'\n{ok_n} ok, {falhas} falha(s)')
sys.exit(1 if falhas else 0)
