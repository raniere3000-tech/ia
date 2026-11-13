import { useEffect, useRef, useState } from 'react';
import { Link2, Flag, FlagOff, Plus, Play, Trash2, ExternalLink, Upload, Info, Wand2, Loader2, X, Server, Sparkles } from 'lucide-react';
import { useApp } from '../state';
import { tm, uid } from '../lib/store';
import { baixarPeloServidor, testarServidor } from '../lib/servidor';

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
export default function LinkStudio({onUpload,onArquivo,direitos,opcoes}:{onUpload:()=>void;onArquivo:(f:File)=>void;direitos:boolean;opcoes:{min:number;max:number;limite:number;tema:string;pedido:string;acao:boolean}}){
  const {linkRef,setLinkRef,marcas,setMarcas,toast,settings,go}=useApp();
  const [dl,setDl]=useState<{pct:number;etapa:string}|null>(null); const [bot,setBot]=useState(''); const sinal=useRef<{cancelado:boolean}|null>(null);
  const [campo,setCampo]=useState(linkRef);
  // Servidor do link: confere se está no ar assim que um vídeo é aberto, para avisar antes de a pessoa esperar à toa.
  const [srv,setSrv]=useState<'vendo'|'ok'|'fora'>('vendo');
  const [ia,setIa]=useState('');   // texto de progresso enquanto o Gemini assiste o vídeo
  // O que estiver escolhido na hora em que o vídeo terminar de chegar (não na hora do clique).
  const aoChegar=useRef(onArquivo); aoChegar.current=onArquivo;
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
  useEffect(()=>{ if(!id||!settings.servidor){ setSrv('vendo'); return; } let vivo=true; setSrv('vendo'); testarServidor(settings.servidor,settings.servidorToken).then(()=>{ if(vivo) setSrv('ok'); },()=>{ if(vivo) setSrv('fora'); }); return ()=>{ vivo=false; }; },[id,settings.servidor,settings.servidorToken]);
  /** O Gemini assiste o vídeo pelo link e marca os melhores trechos. Não baixa nada. */
  async function acharComIA(){
    if(!settings.geminiKey){ go('config'); toast('Cole a chave do Gemini (grátis) em Chaves e ajustes para a IA assistir o vídeo pelo link.','info'); return; }
    if(ia) return; setIa('O Gemini está assistindo o vídeo. Pode levar de 1 a 3 minutos');
    try{
      const {acharCortesNoLink,erroGemini}=await import('../lib/gemini');
      try{
        const l=await acharCortesNoLink(settings.geminiKey,'https://www.youtube.com/watch?v='+id,opcoes,s=>setIa(`O Gemini pediu para esperar ${s} s e continua sozinho`));
        if(!l.length){ toast('A IA não achou trechos bons com essa duração. Tente outra duração ou outro pedido nas opções acima.','info'); return; }
        setMarcas(m=>[...m.filter(x=>!x.ia),...l.map(c=>({id:uid(),inicio:c.inicio,fim:c.fim,titulo:c.titulo,nota:c.nota,motivo:c.motivo,gancho:c.gancho_texto,hashtags:c.hashtags,ia:true}))]);
        toast(`A IA achou ${l.length} cortes. Assista cada um no ▶ e apague os que não quiser.`,'ok');
      }catch(e){ toast(erroGemini(e),'erro'); }
    }finally{ setIa(''); }
  }
  async function cortarAuto(link=linkRef){
    if(!settings.servidor){ go('config'); toast('Primeiro ligue o servidor em Chaves e ajustes (botão "Como ligar?").','info'); return; }
    if(!direitos){ toast('Marque a declaração de direitos no passo 1 (Como você quer os cortes) para cortar automático.','erro'); return; }
    if(sinal.current) return;
    const s={cancelado:false}; sinal.current=s; setDl({pct:0,etapa:'Pedindo o vídeo ao servidor'});
    try{
      const f=await baixarPeloServidor(settings.servidor,settings.servidorToken,link,(pct,etapa)=>{ if(!s.cancelado) setDl({pct,etapa}); },s);
      if(s.cancelado) return;
      setDl(null); sinal.current=null; aoChegar.current(f);
    }catch(e){ const msg=e instanceof Error?e.message:String(e); if(!s.cancelado){ toast(msg,'erro'); if(msg.includes('robô')) setBot(msg); if(msg.includes('falar com o servidor')) setSrv('fora'); } setDl(null); sinal.current=null; }
  }
  const cancelar=()=>{ if(sinal.current) sinal.current.cancelado=true; sinal.current=null; setDl(null); };
  const tempo=()=>player.current?.getCurrentTime?.()||0;
  const abrir=()=>{ const v=youtubeId(campo); if(!v){ toast('Esse link não parece ser de um vídeo do YouTube.','erro'); return; } if(v!==id){ cancelar(); setLinkRef('https://www.youtube.com/watch?v='+v); setMarcas(()=>[]); setIni(null); } };
  const marcarFim=()=>{
    if(ini===null) return; const f=tempo();
    if(f-ini<1){ toast('O fim precisa ser depois do início.','erro'); return; }
    setMarcas(m=>[...m,{id:uid(),inicio:+ini.toFixed(1),fim:+f.toFixed(1),titulo:`Trecho ${m.length+1}`}]); setIni(null);
    toast('Trecho marcado.','ok');
  };
  return <section className="panel link-studio">
   {bot&&<div className="note-bar"><span>{bot}</span><button className="primary sm" onClick={()=>go('config')}>Enviar cookies do YouTube</button><button className="subtle sm" onClick={()=>setBot('')}>Fechar</button></div>}
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
     <button className="primary full" onClick={acharComIA} disabled={!!ia} title={settings.geminiKey?'':'Precisa da chave do Gemini (grátis)'}>{ia?<Loader2 size={15} className="spin"/>:<Sparkles size={15}/>} {ia?'Analisando...':marcas.some(m=>m.ia)?'Procurar de novo com IA':'Achar os melhores cortes com IA'}</button>
     {ia?<p className="hint">{ia}. Roda no Gemini (Google): só o link é enviado.</p>:<p className="hint">{settings.geminiKey?`A IA assiste o vídeo pelo link e marca até ${opcoes.limite} trechos de ${opcoes.min} a ${opcoes.max} s (mude nas opções acima). Não precisa baixar nada.`:<>Falta a chave do Gemini (grátis). <button className="link-btn inline" onClick={()=>go('config')}>Colar a chave</button></>}</p>}
     {marcas.length===0?<p className="hint">Ou assista e use <b>Marcar início</b> / <b>Marcar fim</b> nos momentos que quer cortar.</p>
     :marcas.map(m=><div key={m.id} className="mark-row">
       <input value={m.titulo} onChange={e=>setMarcas(ms=>ms.map(x=>x.id===m.id?{...x,titulo:e.target.value}:x))} aria-label="Nome do trecho"/>
       <small>{m.nota!=null&&<span className="tag ai">pontuação {m.nota}/99</span>} {tm(m.inicio)}–{tm(m.fim)} • {Math.round(m.fim-m.inicio)} s</small>
       {m.motivo&&<small className="mark-motivo">{m.motivo}</small>}
       <div className="mark-actions"><button className="icon-btn" title="Assistir trecho" onClick={()=>{ player.current?.seekTo?.(m.inicio,true); player.current?.playVideo?.(); }}><Play size={14}/></button>
       <a className="icon-btn" title="Abrir no YouTube neste ponto" href={`https://www.youtube.com/watch?v=${id}&t=${Math.floor(m.inicio)}s`} target="_blank" rel="noreferrer"><ExternalLink size={14}/></a>
       <button className="icon-btn" title="Remover" onClick={()=>setMarcas(ms=>ms.filter(x=>x.id!==m.id))}><Trash2 size={14}/></button></div>
     </div>)}
    </div>
   </div>}
   {id&&dl&&<div className="dl-box"><div className="row"><Loader2 size={16} className="spin"/><span><b>{dl.etapa}</b> {dl.pct>0&&dl.pct<100?`${Math.round(dl.pct)}%`:''}. Depois o site analisa e corta sozinho{marcas.length?` (usando os ${marcas.length} trechos marcados)`:''}.</span><button className="subtle sm" onClick={cancelar}><X size={14}/> Cancelar</button></div><div className="dl-bar"><i style={{width:Math.max(3,dl.pct)+'%'}}/></div></div>}
   {id&&!dl&&settings.servidor&&srv!=='fora'&&<div className="note-bar info"><Server size={16}/><span><b>{srv==='ok'?'Servidor ligado.':'Conferindo o servidor...'}</b> {marcas.length?`Toque em Baixar e cortar para receber os ${marcas.length} trechos marcados prontos para editar.`:'Toque em Baixar e começar para o site baixar o vídeo e achar os melhores cortes com nota.'} O download é feito pelo seu servidor; a análise e o corte rodam neste navegador. Use só vídeos seus ou autorizados.{!direitos&&<b> Marque a declaração de direitos no passo 1 para liberar.</b>}</span><button className="primary sm" onClick={()=>cortarAuto()} disabled={!direitos}><Wand2 size={14}/> {marcas.length?`Baixar e cortar ${marcas.length} trecho(s)`:'Baixar e começar'}</button></div>}
   {id&&!dl&&settings.servidor&&srv==='fora'&&<div className="note-bar"><Server size={16}/><span><b>O servidor do link não respondeu.</b> Por isso o vídeo abre aqui mas não é baixado nem cortado. Ligue o servidor de novo (no celular: abra o Termux e rode <code>bash iniciar-termux.sh</code>) e toque em Tentar de novo, ou envie o arquivo do vídeo. {marcas.length?`Os ${marcas.length} trechos marcados continuam guardados.`:'A IA ainda consegue marcar os trechos pelo link.'}</span><button className="primary sm" onClick={()=>{ setSrv('vendo'); testarServidor(settings.servidor,settings.servidorToken).then(()=>{ setSrv('ok'); toast('Servidor ligado.','ok'); },e=>{ setSrv('fora'); toast(e instanceof Error?e.message:String(e),'erro'); }); }}>Tentar de novo</button><button className="subtle sm" onClick={onUpload}><Upload size={14}/> Enviar arquivo</button></div>}
   {id&&!settings.servidor&&<div className="note-bar info"><Info size={16}/><span><b>O navegador não consegue baixar vídeo do YouTube sozinho.</b> {marcas.length?`Para transformar os ${marcas.length} trechos marcados em vídeo, envie o arquivo do vídeo`:'A IA marca os trechos pelo link, mas para gerar os vídeos cortados é preciso o arquivo: envie o arquivo do vídeo'} ou ligue o servidor gratuito (uns 5 minutos, uma vez só) para o site baixar sozinho.</span><button className="primary sm" onClick={onUpload}><Upload size={14}/> Enviar arquivo</button><button className="subtle sm" onClick={()=>go('config')}><Server size={14}/> Ligar cortes pelo link</button></div>}
  </section>;
}
