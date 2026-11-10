"""MVP local do Estúdio de Cortes; NÃO expor publicamente sem autenticação."""
from __future__ import annotations
import json, math, os, re, shutil, subprocess, threading, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

load_dotenv()
ROOT = Path(os.getenv('DATA_DIR', './data')).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
PRESETS = json.loads((Path(__file__).resolve().parent.parent/'config/presets.json').read_text(encoding='utf-8'))
JOB: dict[str, dict] = {}
app = FastAPI(title='Estúdio de Cortes API', version='0.1.0')
origins=[x.strip() for x in os.getenv('CORS_ORIGINS','http://localhost:5173').split(',') if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=['GET','POST'],allow_headers=['*'])

def run(*cmd):
    p=subprocess.run(cmd, text=True, capture_output=True, timeout=600)
    if p.returncode: raise RuntimeError(p.stderr[-1200:])
    return p.stdout

def duration(path):
    return float(json.loads(run('ffprobe','-v','quiet','-show_format','-of','json',str(path)))['format']['duration'])

def srt_time(sec):
    ms=int(round(sec*1000)); return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'

def captions(path, out, base):
    """Whisper local com segmentos (legenda estilo básico; se falhar, registra sem inventar)."""
    try:
        from faster_whisper import WhisperModel
        model=WhisperModel(os.getenv('WHISPER_MODEL','tiny'), device='cpu', compute_type='int8')
        segs,_=model.transcribe(str(path), beam_size=1, vad_filter=True)
        with open(out,'w',encoding='utf-8') as f:
            for i,seg in enumerate(segs,1):
                f.write(f'{i}\n{srt_time(seg.start)} --> {srt_time(seg.end)}\n{seg.text.strip()}\n\n')
        return out.stat().st_size>0
    except Exception as e:
        (base/'transcription-error.txt').write_text(str(e), encoding='utf-8')
        return False

def analyze(job_id):
    j=JOB[job_id]; base=ROOT/job_id
    try:
        j['status']='processando'; src=base/'original.mp4'; dur=duration(src)
        j['duracao_original']=round(dur,1)
        j['progresso']=15
        low,high=j['duracao_min'],j['duracao_max']
        # Escolhe janelas sem sobreposição. Nota heurística baseada no RMS de áudio.
        frames=base/'audioraw.bin'
        run('ffmpeg','-y','-i',str(src),'-vn','-ac','1','-ar','8000','-f','s16le',str(frames))
        audio=frames.read_bytes(); import array
        a=array.array('h');a.frombytes(audio[:len(audio)//2*2]);frames.unlink(missing_ok=True)
        window=max(4,min(high,round((low+high)/2)))
        segments=[];start=0.0
        while start+low<=dur and len(segments)<60:
            end=min(dur,start+window)
            if end-start<low:break
            sample=a[int(start*8000):int(end*8000):max(1,int((end-start)*8000/15000))]
            rms=math.sqrt(sum(v*v for v in sample)/max(1,len(sample)))/32768 if sample else 0
            segments.append({'inicio':round(start,2),'fim':round(end,2),'energia':rms})
            start=end
        peak=max([s['energia'] for s in segments] or [1]) or 1
        # Base 35-95, não é avaliação semântica nem nota comparável ao OpusClip.
        for idx,s in enumerate(segments):
            score=min(95,max(10,round(35+60*s['energia']/peak)))
            s.update(id=str(idx+1),nota_final=score,nota_10=round(score/9.9,1),titulo=f'Destaque {idx+1}',motivo='Estimativa inicial por energia sonora; revise manualmente.')
        j['cortes']=sorted(segments,key=lambda x:-x['nota_final'])[:min(30,j['max_cortes'])]
        j['progresso']=52
        sub=base/'legendas.srt';j['tem_legendas']=captions(src,sub,base)
        j['progresso']=100;j['status']='pronto'
    except Exception as e:
        j['status']='erro';j['erro']=str(e)[:700]

@app.get('/api/health')
def health(): return {'ok':True,'ffmpeg':shutil.which('ffmpeg') is not None,'radar_configurado':bool(os.getenv('YOUTUBE_API_KEY'))}

@app.get('/api/presets')
def presets(): return PRESETS

@app.get('/api/radar')
async def radar(tema:str=Query(''),dias:int=Query(30,ge=1,le=3650),views:int=Query(100000,ge=0),minutos:int=Query(20,ge=0),ordem:str='velocidade',regiao:str='BR',idioma:str='pt'):
    key=os.getenv('YOUTUBE_API_KEY','')
    if not key:raise HTTPException(503,'Configure YOUTUBE_API_KEY no backend para pesquisar canais reais.')
    import datetime
    since=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(days=dias)).isoformat().replace('+00:00','Z')
    async with httpx.AsyncClient(timeout=20) as cl:
        params={'part':'snippet','type':'video','maxResults':50,'q':tema or 'podcast','publishedAfter':since,'key':key,'regionCode':regiao,'relevanceLanguage':idioma,'videoDuration':'long' if minutos>=20 else 'any'}
        r=await cl.get('https://www.googleapis.com/youtube/v3/search',params=params)
        if r.status_code!=200:raise HTTPException(502,'YouTube Data API: '+r.text[:250])
        items=r.json().get('items',[]);ids=[i['id']['videoId'] for i in items if 'videoId' in i.get('id',{})]
        if not ids:return {'itens':[]}
        rr=await cl.get('https://www.googleapis.com/youtube/v3/videos',params={'part':'statistics,contentDetails','id':','.join(ids),'key':key})
        if rr.status_code!=200:raise HTTPException(502,'Falha ao obter estatísticas do YouTube')
        meta={i['id']:i for i in rr.json().get('items',[])}
    from datetime import datetime as dt
    import re
    def secs(iso):
        m=re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?',iso)
        if not m:return 0
        return int(m[1] or 0)*3600+int(m[2] or 0)*60+int(m[3] or 0)
    out=[]
    for i in items:
        vid=i.get('id',{}).get('videoId'); m=meta.get(vid)
        if not m:continue
        n=int(m.get('statistics',{}).get('viewCount',0));t=secs(m.get('contentDetails',{}).get('duration',''))
        if n<views or t<minutos*60:continue
        age=max(1,(dt.now(timezone.utc)-dt.fromisoformat(i['snippet']['publishedAt'].replace('Z','+00:00'))).total_seconds()/86400)
        out.append({'id':vid,'titulo':i['snippet']['title'],'canal':i['snippet']['channelTitle'],'canal_id':i['snippet']['channelId'],'link':'https://www.youtube.com/watch?v='+vid,'link_canal':'https://www.youtube.com/channel/'+i['snippet']['channelId'],'thumbnail':i['snippet']['thumbnails'].get('medium',{}).get('url'),'views':n,'velocidade':round(n/age),'duracao_segundos':t})
    out.sort(key=lambda x:x['views'] if ordem=='views' else x['velocidade'],reverse=True)
    return {'itens':out,'nota':'Velocidade estimada = visualizações acumuladas / idade do vídeo em dias; resultados restritos pela API.'}

@app.post('/api/trabalhos')
async def create_trabalho(file:UploadFile=File(...),direitos:bool=Form(False),duracao_min:int=Form(30),duracao_max:int=Form(60),max_cortes:int=Form(15)):
    if not direitos:raise HTTPException(400,'Confirme que você tem direito de editar e publicar este vídeo.')
    if duracao_min<5 or duracao_max>180 or duracao_max<duracao_min:raise HTTPException(400,'Duração inválida (5–180s).')
    if not 1<=max_cortes<=30:raise HTTPException(400,'Quantidade deve ser de 1 a 30.')
    if not (file.filename or '').lower().endswith(('.mp4','.mov','.mkv','.webm')):raise HTTPException(400,'Use arquivo MP4, MOV, MKV ou WEBM.')
    id=str(uuid.uuid4());b=ROOT/id;b.mkdir();target=b/'original.mp4'
    max_bytes=int(os.getenv('MAX_UPLOAD_MB','500'))*1024*1024;size=0
    with open(target,'wb') as dest:
        while chunk:=await file.read(1024*1024):
            size+=len(chunk)
            if size>max_bytes:
                shutil.rmtree(b);raise HTTPException(413,'Arquivo maior que o limite configurado.')
            dest.write(chunk)
    try:duration(target)
    except Exception:
        shutil.rmtree(b);raise HTTPException(400,'Não foi possível abrir o arquivo de vídeo.')
    JOB[id]={'id':id,'status':'na_fila','progresso':0,'cortes':[],'max_cortes':max_cortes,'duracao_min':duracao_min,'duracao_max':duracao_max,'tem_legendas':False,'criado_em':time.time()}
    threading.Thread(target=analyze,args=(id,),daemon=True).start()
    return {'id':id}

@app.get('/api/trabalhos/{id}')
def trabalho(id:str):
    if id not in JOB:raise HTTPException(404,'Trabalho não encontrado; reiniciar a API perde jobs da memória.')
    return JOB[id]

@app.post('/api/trabalhos/{id}/render/{clip_id}')
def render(id:str,clip_id:str,legenda:str='classico-contorno',efeito:str='blur-background'):
    if id not in JOB:raise HTTPException(404,'Trabalho não encontrado.')
    j=JOB[id]; c=next((x for x in j.get('cortes',[]) if x['id']==clip_id),None)
    if c is None:raise HTTPException(404,'Corte não encontrado.')
    base=ROOT/id;src=base/'original.mp4';out=base/f'corte-{clip_id}.mp4';srt=base/'legendas.srt'
    # O motor atual garante estilos ASS simples, não animações CSS avançadas.
    allowed={'classico-contorno','minimal-branco','podcast-clean','legenda-caixa','karaoke-amarelo'}
    if legenda not in allowed:raise HTTPException(400,'Estilo cadastrado, mas ainda não renderizável nesta versão; selecione um estilo clássico.')
    if efeito not in {'blur-background','nenhum'}:raise HTTPException(400,'Efeito cadastrado, mas ainda não renderizável nesta versão.')
    filters=('[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v]' if efeito=='nenhum' else
             '[0:v]split=2[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:2[bg];[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[v]')
    if j['tem_legendas'] and srt.exists():
        # Recorta e desloca tempos da transcrição para sincronizar com o clipe.
        def parse_stamp(st):
            h,m,rest=st.split(':'); sec,ms=rest.split(',')
            return int(h)*3600+int(m)*60+int(sec)+int(ms)/1000
        blocks=[]
        text=srt.read_text(encoding='utf-8')
        for block in re.split(r'\n\s*\n',text):
            lines=block.splitlines()
            match=next((re.match(r'(\d\d:\d\d:\d\d,\d{3}) --> (\d\d:\d\d:\d\d,\d{3})',line) for line in lines if ' --> ' in line),None)
            if not match:continue
            a,b=map(parse_stamp, match.groups())
            if b<=c['inicio'] or a>=c['fim']:continue
            start=max(0,a-c['inicio']);end=min(c['fim']-c['inicio'],b-c['inicio'])
            subtitle='\n'.join(lines[lines.index(next(l for l in lines if ' --> ' in l))+1:]).strip()
            if subtitle and end>start:blocks.append(f'{len(blocks)+1}\n{srt_time(start)} --> {srt_time(end)}\n{subtitle}\n')
        clip_srt=base/f'legendas-corte-{clip_id}.srt'
        clip_srt.write_text('\n'.join(blocks),encoding='utf-8')
        # Sanitiza caminho usado no filtergraph, limita à pasta gerenciada.
        escaped=str(clip_srt).replace('\\','\\\\').replace(':','\\:').replace("'","\\'")
        filters+=';[v]subtitles=filename='+escaped+':force_style=\'FontName=DejaVu Sans,FontSize=22,Outline=2,Shadow=1,MarginV=200\'[final]'
        mapv='[final]'
    else:mapv='[v]'
    try:run('ffmpeg','-y','-ss',str(c['inicio']),'-t',str(c['fim']-c['inicio']),'-i',str(src),'-filter_complex',filters,'-map',mapv,'-map','0:a?','-r','30','-c:v','libx264','-preset','veryfast','-crf','24','-c:a','aac','-movflags','+faststart',str(out))
    except Exception as e:raise HTTPException(500,'FFmpeg: '+str(e)[:600])
    return {'download':f'/api/trabalhos/{id}/arquivos/{out.name}','legendas_embutidas':j['tem_legendas']}

@app.get('/api/trabalhos/{id}/arquivos/{name}')
def arquivo(id:str,name:str):
    if id not in JOB or not name.startswith('corte-') or not name.endswith('.mp4'):raise HTTPException(404,'Arquivo não encontrado')
    p=ROOT/id/name
    if not p.is_file():raise HTTPException(404,'Arquivo não encontrado')
    return FileResponse(p,media_type='video/mp4',filename=name)
