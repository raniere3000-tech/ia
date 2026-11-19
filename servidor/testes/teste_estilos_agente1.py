"""Agente 1 com estilos visuais: sorteio entre os escolhidos, respeita estilo do template e estilo indisponível."""
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import sys, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agente as ag, visual_presets as vp
ok = falhas = 0
def check(c, m):
    global ok, falhas
    if c: ok += 1
    else: falhas += 1; print('  FALHOU:', m)
rnd = random.Random(1)
t = {}
n = ag._sortear_estilo(t, {'estilos': []}, rnd); check(n == [] and 'estilo_visual' not in t, 'sem escolha: nada muda')
t = {}; n = ag._sortear_estilo(t, {'estilos': ['retro_vhs', 'comic_gameplay']}, rnd)
check(t['estilo_visual'] in ('retro_vhs', 'comic_gameplay') and n and n[0].startswith('Estilo visual:'), 'sorteia entre os escolhidos')
vistos = set()
for i in range(40):
    t = {}; ag._sortear_estilo(t, {'estilos': ['retro_vhs', 'comic_gameplay']}, rnd); vistos.add(t['estilo_visual'])
check(vistos == {'retro_vhs', 'comic_gameplay'}, 'os dois aparecem')
t = {'estilo_visual': 'pixel_stream'}; check(ag._sortear_estilo(t, {'estilos': ['retro_vhs']}, rnd) == [] and t['estilo_visual'] == 'pixel_stream', 'o template com estilo próprio vale')
orig = vp._faltam; vp._faltam = lambda pid: ['xyz']
t = {}; n = ag._sortear_estilo(t, {'estilos': ['retro_vhs']}, rnd); vp._faltam = orig
check('estilo_visual' not in t and 'nenhum dos escolhidos' in n[0], 'indisponível: sai sem estilo e avisa')
c = ag._limpar_cfg({**ag.config(), 'cortes': {**ag.config()['cortes'], 'estilos': ['retro_vhs', 'naoexiste', 'retro_vhs']}})
check(c['cortes']['estilos'] == ['retro_vhs'], 'limpeza da configuração')
print('TUDO OK' if not falhas else f'{falhas} FALHAS', f'({ok} ok)'); sys.exit(1 if falhas else 0)
