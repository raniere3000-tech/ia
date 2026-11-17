"""Estilos visuais dentro do corte de verdade (agente.editar): cada estilo x cada layout, com legenda, tarja e moldura."""
import sys, subprocess, tempfile, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agente as ag, modelos as mo, visual_presets as vp
ok = falhas = 0
def check(c, m):
    global ok, falhas
    if c: ok += 1
    else: falhas += 1; print('  FALHOU:', m)
def dur(p):
    r = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(p)],capture_output=True,text=True); return float(r.stdout)
def quadro(p):
    return subprocess.run(['ffmpeg','-nostdin','-v','error','-ss','1','-i',str(p),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True).stdout
with tempfile.TemporaryDirectory() as d:
    d = Path(d); base = d/'in.mp4'
    subprocess.run(['ffmpeg','-nostdin','-y','-v','error','-f','lavfi','-i','testsrc2=s=1280x720:r=30:d=6','-f','lavfi','-i','sine=frequency=440:d=6','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(base)],check=True)
    palavras = [(1+i*0.4, 1.35+i*0.4, w) for i, w in enumerate('isso muda tudo no jogo de hoje'.split())]
    corte = {'ini': 0.0, 'fim': 5.0, 'gancho': 'ISSO MUDA TUDO'}
    ref = {}
    for layout in ('desfoque', 'cheio', 'gameplay-streamer'):
        m = mo.limpar(dict(mo.BASE, id='t', layout=layout, resolucao=720, moldura=True, tarja={'topo': True, 'base': False, 'textoTopo': 'TESTE', 'altura': 8}))
        o = d/f'ref_{layout}.mp4'; ag.editar(base, corte, palavras, mo.tpl(m), o, d); ref[layout] = quadro(o)
        for pid in vp.PRESETS:
            m2 = mo.limpar(dict(m, estiloVisual=pid)); o2 = d/f'{layout}_{pid}.mp4'
            try: ag.editar(base, corte, palavras, mo.tpl(m2), o2, d)
            except Exception as e: check(False, f'{layout}/{pid}: {str(e)[-150:]}'); continue
            check(abs(dur(o2)-5.0) < 0.3, f'{layout}/{pid} duração')
            q = quadro(o2); n = min(len(q), len(ref[layout]))
            df = sum(abs(q[i]-ref[layout][i]) for i in range(0, n, 97))/max(1, n//97)
            check(df > 0.8, f'{layout}/{pid} igual ao sem estilo ({df:.2f})')
    # modelo antigo (sem campo) continua igual
    m = mo.limpar({'id': 'x'}); check(m['estiloVisual'] == '' and m['estiloForca'] == 1.0, 'modelo antigo sem estilo')
    check(mo.limpar({'id': 'x', 'estiloVisual': 'invalido'})['estiloVisual'] == '', 'estilo inválido some')
print('TUDO OK' if not falhas else f'{falhas} FALHAS', f'({ok} ok)'); sys.exit(1 if falhas else 0)
