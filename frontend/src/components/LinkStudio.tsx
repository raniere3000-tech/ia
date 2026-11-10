import { useEffect, useRef, useState } from 'react';
import { Link2, Flag, FlagOff, Plus, Play, Trash2, ExternalLink, Upload, Info, Wand2, Loader2, X, Server } from 'lucide-react';
import { useApp } from '../state';
import { tm, uid } from '../lib/store';
import { baixarPeloServidor } from '../lib/servidor';

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
export default function LinkStudio({onUpload,onArquivo,direitos}:{onUpload:()=>void;onArquivo:(f:File)=>void;direitos:boolean}){
  const {linkRef,setLinkRef,marcas,setMarcas,toast,settings,go}=useApp();
  const [dl,setDl]=useState<{pct:number;etapa:string}|null>(null); const sinal=useRef<{cancelado:boolean}|null>(null);
  const iniciado=useRef('');
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
  async function cortarAuto(link=linkRef){
    if(!settings.servidor){ go('config'); toast('Primeiro ligue o servidor em Chaves e ajustes (botão "Como ligar?").','info'); return; }
    if(!direitos){ toast('Marque a declaração de direitos acima para cortar automático.','erro'); return; }
    if(sinal.current) return;
    const s={cancelado:false}; sinal.current=s; setDl({pct:0,etapa:'Pedindo o vídeo ao servidor'});
    try{
      const f=await baixarPeloServidor(settings.servidor,settings.servidorToken,link,(pct,etapa)=>{ if(!s.cancelado) setDl({pct,etapa}); },s);
      if(s.cancelado) return;
      setDl(null); sinal.current=null; onArquivo(f);
    }catch(e){ if(!s.cancelado) toast(e instanceof Error?e.message:String(e),'erro'); setDl(null); sinal.current=null; }
  }
  const cancelar=()=>{ if(sinal.current) sinal.current.cancelado=true; sinal.current=null; setDl(null); };
  // Abriu um vídeo com o servidor ligado: já começa a cortar sozinho.
  useEffect(()=>{ if(id&&settings.servidor&&direitos&&iniciado.current!==id){ iniciado.current=id; cortarAuto('https://www.youtube.com/watch?v='+id); } },[id]); // eslint-disable-line react-hooks/exhaustive-deps
  const tempo=()=>player.current?.getCurrentTime?.()||0;
  const abrir=()=>{ const v=youtubeId(campo); if(!v){ toast('Esse link não parece ser de um vídeo do YouTube.','erro'); return; } if(v!==id){ cancelar(); setLinkRef('https://www.youtube.com/watch?v='+v); setMarcas(()=>[]); setIni(null); } else if(settings.servidor&&!dl) cortarAuto(); };
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
   {id&&dl&&<div className="dl-box"><div className="row"><Loader2 size={16} className="spin"/><span><b>{dl.etapa}</b> {dl.pct>0&&dl.pct<100?`${Math.round(dl.pct)}%`:''}. Depois o site analisa e corta sozinho{marcas.length?` (usando os ${marcas.length} trechos marcados)`:''}.</span><button className="subtle sm" onClick={cancelar}><X size={14}/> Cancelar</button></div><div className="dl-bar"><i style={{width:Math.max(3,dl.pct)+'%'}}/></div></div>}
   {id&&!dl&&settings.servidor&&<div className="note-bar info"><Server size={16}/><span><b>Servidor ligado.</b> Clique em <b>Cortar automático</b> para baixar este vídeo e receber os melhores cortes com nota{marcas.length?`, ou só os ${marcas.length} trechos marcados`:''}. Use só vídeos seus ou autorizados.</span><button className="primary sm" onClick={()=>cortarAuto()}><Wand2 size={14}/> Cortar automático</button></div>}
   {id&&!settings.servidor&&<div className="note-bar info"><Info size={16}/><span><b>Quer que corte sozinho pelo link?</b> Ligue o servidor gratuito no seu computador (leva uns 5 minutos, uma vez só). Sem ele, envie o arquivo do vídeo: {marcas.length?`os ${marcas.length} trechos marcados serão usados.`:'o site acha os melhores trechos sozinho.'}</span><button className="primary sm" onClick={()=>go('config')}><Server size={14}/> Ligar cortes pelo link</button><button className="subtle sm" onClick={onUpload}><Upload size={14}/> Enviar arquivo</button></div>}
  </section>;
}
