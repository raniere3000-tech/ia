import { useEffect, useRef, useState } from 'react';
import { Link2, Flag, FlagOff, Plus, Play, Trash2, ExternalLink, Upload, Info } from 'lucide-react';
import { useApp } from '../state';
import { tm, uid } from '../lib/store';

/** Extrai o ID de um link do YouTube (watch, youtu.be, shorts, live, embed). */
export function youtubeId(url:string){
  const m = /(?:youtube\.com\/(?:watch\?(?:.*&)?v=|shorts\/|live\/|embed\/)|youtu\.be\/)([\w-]{11})/.exec(url||'');
  return m ? m[1] : (/^[\w-]{11}$/.test(url.trim()) ? url.trim() : '');
}

declare global { interface Window { YT?:any; onYouTubeIframeAPIReady?:()=>void } }
let apiPromise:Promise<any>|null = null;
function loadYT(){
  if(window.YT?.Player) return Promise.resolve(window.YT);
  if(!apiPromise) apiPromise = new Promise(res=>{
    const prev = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = ()=>{ prev?.(); res(window.YT); };
    const s = document.createElement('script'); s.src = 'https://www.youtube.com/iframe_api'; s.async = true; document.head.appendChild(s);
  });
  return apiPromise;
}

/** Abre o vídeo do link dentro do estúdio: assistir, marcar início/fim e guardar os trechos. */
export default function LinkStudio({onUpload}:{onUpload:()=>void}){
  const {linkRef,setLinkRef,marcas,setMarcas,toast}=useApp();
  const [campo,setCampo]=useState(linkRef);
  const [info,setInfo]=useState<{titulo:string;canal:string}|null>(null);
  const [ini,setIni]=useState<number|null>(null);
  const [agora,setAgora]=useState(0);
  const holder=useRef<HTMLDivElement>(null); const player=useRef<any>(null);
  const id=youtubeId(linkRef);
  useEffect(()=>{ setCampo(linkRef); },[linkRef]);
  useEffect(()=>{
    if(!id) return; let alive=true; setInfo(null);
    fetch(`https://www.youtube.com/oembed?format=json&url=${encodeURIComponent('https://www.youtube.com/watch?v='+id)}`).then(r=>r.ok?r.json():null).then(d=>{ if(alive&&d) setInfo({titulo:d.title,canal:d.author_name}); }).catch(()=>{});
    loadYT().then(YT=>{
      if(!alive||!holder.current) return;
      holder.current.innerHTML=''; const el=document.createElement('div'); holder.current.appendChild(el);
      player.current=new YT.Player(el,{videoId:id,width:'100%',height:'100%',playerVars:{rel:0,modestbranding:1,playsinline:1}});
    });
    const t=setInterval(()=>{ const p=player.current; if(p?.getCurrentTime) setAgora(p.getCurrentTime()||0); },250);
    return ()=>{ alive=false; clearInterval(t); try{ player.current?.destroy?.(); }catch{ /* ignore */ } player.current=null; };
  },[id]);
  const tempo=()=>player.current?.getCurrentTime?.()||0;
  const abrir=()=>{ const v=youtubeId(campo); if(!v){ toast('Esse link não parece ser de um vídeo do YouTube.','erro'); return; } setLinkRef('https://www.youtube.com/watch?v='+v); setMarcas(()=>[]); setIni(null); };
  const marcarFim=()=>{
    if(ini===null) return; const f=tempo();
    if(f-ini<1){ toast('O fim precisa ser depois do início.','erro'); return; }
    setMarcas(m=>[...m,{id:uid(),inicio:+ini.toFixed(1),fim:+f.toFixed(1),titulo:`Trecho ${m.length+1}`}]); setIni(null);
    toast('Trecho marcado.','ok');
  };
  return <section className="panel link-studio">
   <div className="section-head"><h2><Link2 size={18}/> Abrir vídeo por link do YouTube</h2></div>
   <div className="key-row"><div className="input-wrap"><Link2 size={16}/><input value={campo} onChange={e=>setCampo(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')abrir()}} placeholder="Cole o link do vídeo (youtube.com/watch?v=... ou youtu.be/...)"/></div><button className="primary" onClick={abrir} disabled={!campo.trim()}>Abrir vídeo</button></div>
   {id&&<div className="ls-grid">
    <div>
     <div className="yt-frame" ref={holder}/>
     {info&&<p className="yt-info"><strong>{info.titulo}</strong> • {info.canal}</p>}
     <div className="mark-bar">
      <span className="time-chip">{tm(agora)}</span>
      {ini===null?<button className="primary" onClick={()=>setIni(tempo())}><Flag size={15}/> Marcar início</button>
       :<><span className="tag ai">Início em {tm(ini)}</span><button className="primary" onClick={marcarFim}><Plus size={15}/> Marcar fim e salvar trecho</button><button className="subtle" onClick={()=>setIni(null)}><FlagOff size={15}/> Cancelar</button></>}
     </div>
    </div>
    <div className="marks">
     <strong>Trechos marcados <span className="count">{marcas.length}</span></strong>
     {marcas.length===0?<p className="hint">Assista e use <b>Marcar início</b> / <b>Marcar fim</b> nos momentos que quer cortar.</p>
     :marcas.map(m=><div key={m.id} className="mark-row">
       <input value={m.titulo} onChange={e=>setMarcas(ms=>ms.map(x=>x.id===m.id?{...x,titulo:e.target.value}:x))} aria-label="Nome do trecho"/>
       <small>{tm(m.inicio)}–{tm(m.fim)} • {Math.round(m.fim-m.inicio)} s</small>
       <div className="mark-actions"><button className="icon-btn" title="Assistir trecho" onClick={()=>{ player.current?.seekTo?.(m.inicio,true); player.current?.playVideo?.(); }}><Play size={14}/></button>
       <a className="icon-btn" title="Abrir no YouTube neste ponto" href={`https://www.youtube.com/watch?v=${id}&t=${Math.floor(m.inicio)}s`} target="_blank" rel="noreferrer"><ExternalLink size={14}/></a>
       <button className="icon-btn" title="Remover" onClick={()=>setMarcas(ms=>ms.filter(x=>x.id!==m.id))}><Trash2 size={14}/></button></div>
     </div>)}
    </div>
   </div>}
   {id&&<div className="note-bar info"><Info size={16}/><span><b>Para exportar com legenda e efeitos, falta o arquivo do vídeo.</b> O YouTube não deixa sites baixarem vídeos, e baixar vídeo de terceiros só é permitido com autorização. Se o vídeo é seu, baixe pelo <a href="https://studio.youtube.com/" target="_blank" rel="noreferrer">YouTube Studio</a> (Conteúdo → ⋮ → Baixar) e envie abaixo: {marcas.length?`os ${marcas.length} trechos marcados serão usados automaticamente.`:'o site acha os melhores trechos sozinho.'}</span><button className="subtle sm" onClick={onUpload}><Upload size={14}/> Enviar arquivo</button></div>}
  </section>;
}
