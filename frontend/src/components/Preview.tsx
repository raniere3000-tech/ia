import { useCallback, useEffect, useRef, useState } from 'react';
import { Play, Pause, RotateCcw } from 'lucide-react';
import { drawFrame, DIMS, loadImage, type RenderOpts } from '../lib/render';
import type { Formato } from '../lib/analyze';
import { tm } from '../lib/store';

/** Prévia real do corte, desenhada com o mesmo código da exportação. */
export default function Preview({url,inicio,fim,formato,opts,className}:{url:string;inicio:number;fim:number;formato:Formato;opts:Omit<RenderOpts,'logoImg'>;className?:string}){
  const v=useRef<HTMLVideoElement>(null); const c=useRef<HTMLCanvasElement>(null); const small=useRef<HTMLCanvasElement|null>(null);
  const logo=useRef<HTMLImageElement|null>(null);
  const [playing,setPlaying]=useState(false); const [t,setT]=useState(0);
  const [W,H]=DIMS[formato]; const dur=Math.max(0.1,fim-inicio);
  const optsRef=useRef(opts); optsRef.current=opts;
  const paint=useCallback(()=>{
    const vid=v.current, cv=c.current; if(!vid||!cv||!vid.videoWidth) return;
    if(!small.current) small.current=document.createElement('canvas');
    const o=optsRef.current;
    const cues=o.cues.filter(q=>q.end>inicio&&q.start<fim).map(q=>({start:q.start-inicio,end:q.end-inicio,text:q.text}));
    const tt=vid.currentTime-inicio; setT(tt);
    drawFrame(cv.getContext('2d')!,vid,small.current,tt,dur,{...o,cues,logoImg:logo.current},W,H);
  },[inicio,fim,dur,W,H]);
  useEffect(()=>{ loadImage(opts.template.logo).then(i=>{ logo.current=i; paint(); }); },[opts.template.logo,paint]);
  useEffect(()=>{ paint(); },[opts,formato,paint]);
  useEffect(()=>{ const vid=v.current; if(vid && vid.readyState>=1 && (vid.currentTime<inicio||vid.currentTime>fim)) vid.currentTime=inicio; },[inicio,fim]);
  useEffect(()=>{
    const vid=v.current; if(!vid) return; let id=0;
    const loop=()=>{ paint(); if(vid.currentTime>=fim){ vid.pause(); vid.currentTime=inicio; } if(!vid.paused) id=requestAnimationFrame(loop); };
    const onPlay=()=>{ setPlaying(true); id=requestAnimationFrame(loop); };
    const onPause=()=>{ setPlaying(false); cancelAnimationFrame(id); paint(); };
    const onLoaded=()=>{ vid.currentTime=inicio; };
    vid.addEventListener('play',onPlay); vid.addEventListener('pause',onPause); vid.addEventListener('seeked',paint); vid.addEventListener('loadedmetadata',onLoaded);
    if(vid.readyState>=1) onLoaded();
    return ()=>{ cancelAnimationFrame(id); vid.removeEventListener('play',onPlay); vid.removeEventListener('pause',onPause); vid.removeEventListener('seeked',paint); vid.removeEventListener('loadedmetadata',onLoaded); };
  },[paint,inicio,fim]);
  useEffect(()=>()=>{ v.current?.pause(); },[]);
  const toggle=()=>{ const vid=v.current; if(!vid) return; if(vid.paused){ if(vid.currentTime<inicio||vid.currentTime>=fim-0.05) vid.currentTime=inicio; vid.play().catch(()=>{}); } else vid.pause(); };
  return <div className={'preview-box '+(className||'')}>
   <canvas ref={c} width={W} height={H} className={'preview-canvas f'+formato.replace(':','x')} onClick={toggle}/>
   <video ref={v} src={url} preload="auto" playsInline hidden/>
   <div className="player-bar">
    <button className="icon-btn" onClick={toggle} aria-label={playing?'Pausar':'Reproduzir'}>{playing?<Pause size={16}/>:<Play size={16}/>}</button>
    <input type="range" min={0} max={dur} step={0.1} value={Math.min(dur,Math.max(0,t))} onChange={e=>{ const vid=v.current; if(vid) vid.currentTime=inicio+(+e.target.value); }}/>
    <span className="time">{tm(Math.max(0,t))} / {tm(dur)}</span>
    <button className="icon-btn" onClick={()=>{ const vid=v.current; if(vid){ vid.currentTime=inicio; } }} aria-label="Voltar ao início"><RotateCcw size={15}/></button>
   </div>
  </div>;
}
