"""Renderiza de verdade os 12 estilos visuais com FFmpeg e confere: roda, muda a imagem, mantém duração e áudio."""
import sys, os, subprocess, tempfile, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import visual_presets as vp

ok = falhas = 0
def check(c, msg):
    global ok, falhas
    if c: ok += 1
    else: falhas += 1; print('  FALHOU:', msg)

def info(p):
    r = subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type,width,height,nb_frames:format=duration','-of','json',str(p)],capture_output=True,text=True)
    import json; return json.loads(r.stdout)
def md5_frame(p, t=1.0):
    r = subprocess.run(['ffmpeg','-nostdin','-v','error','-ss',str(t),'-i',str(p),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True)
    return r.stdout
def diff(a,b):
    n=min(len(a),len(b)); 
    return sum(abs(a[i]-b[i]) for i in range(0,n,97))/max(1,n//97)

assert len(vp.PRESETS)==12, len(vp.PRESETS)
check(len(vp.PRESETS)==12, '12 estilos')
with tempfile.TemporaryDirectory() as d:
    d=Path(d); base=d/'base.mp4'; vp._gerar_base(base, 3.0)
    ib=info(base); fb=md5_frame(base)
    for pid in vp.PRESETS:
        sai=d/f'{pid}.mp4'
        try:
            vp.aplicar_arquivo(base, sai, pid)
        except vp.ErroEstilo as e:
            print(' ',pid,'indisponível:',e); continue
        i=info(sai); dur=float(i['format']['duration']); tipos=[s['codec_type'] for s in i['streams']]
        check(abs(dur-3.0)<0.3, f'{pid}: duração {dur}')
        check('audio' in tipos, f'{pid}: áudio mantido')
        v=[s for s in i['streams'] if s['codec_type']=='video'][0]
        check((v['width'],v['height'])==(360,640), f'{pid}: tamanho')
        df=diff(fb, md5_frame(sai))
        check(df>1.0, f'{pid}: imagem não mudou ({df:.2f})')
        # força 0 = imagem igual
        z=d/f'{pid}_0.mp4'; vp.aplicar_arquivo(base, z, pid, forca=0.0)
        dz=diff(fb, md5_frame(z)); check(dz<3.0, f'{pid}: força 0 deveria deixar igual ({dz:.2f})')
        print(f'  {pid}: ok dif={df:.1f} força0={dz:.1f}')
    # peças desligadas
    p0=list(vp.PRESETS)[0]
    comp=[c for c,_,_ in vp.PRESETS[p0]['pecas'](360,640,1.0,'')]
    check(len(comp)>0, 'tem peças')
    g=vp.grafo(p0,360,640,'[0:v]','[v]',1.0,tuple(comp))
    check(g=='[0:v]null[v]', 'tudo desligado passa direto')
    try: vp.grafo('naoexiste',360,640,'[0:v]','[v]'); check(False,'estilo desconhecido deve falhar')
    except vp.ErroEstilo: check(True,'')
    l=vp.listar(); check(len(l)==12 and all('status' in x for x in l), 'listar com status')
print('TUDO OK' if not falhas else f'{falhas} FALHAS', f'({ok} ok)')
sys.exit(1 if falhas else 0)
