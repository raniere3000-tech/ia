// Gravação quadro a quadro (não depende do tempo real nem de a aba estar na frente), relógio de segundo plano
// e o aviso de "trabalho em andamento" que aparece no menu.
import { useSyncExternalStore } from 'react';

// ---------------------------------------------------------------- trabalho em andamento (menu)

const ativos=new Map<string,number>(); const ouvintes=new Set<()=>void>(); let foto='';
const avisar=()=>{ foto=[...ativos.keys()].sort().join(','); ouvintes.forEach(f=>f()); };
/** Marca que uma aba do site está trabalhando. Devolve a função que desmarca. */
export function ocupar(aba:string){ ativos.set(aba,(ativos.get(aba)||0)+1); avisar(); let feito=false;
  return ()=>{ if(feito) return; feito=true; const n=(ativos.get(aba)||1)-1; if(n>0) ativos.set(aba,n); else ativos.delete(aba); avisar(); }; }
export async function comTrabalho<T>(aba:string,f:()=>Promise<T>):Promise<T>{ const fim=ocupar(aba); try{ return await f(); } finally{ fim(); } }
/** Abas do site com trabalho rodando agora (separadas por vírgula). */
export function useTrabalhos(){ return useSyncExternalStore(f=>{ ouvintes.add(f); return ()=>{ ouvintes.delete(f); }; },()=>foto); }

// ---------------------------------------------------------------- relógio de segundo plano

let relogio:Worker|null=null; let reserva=0; const batidas=new Set<()=>void>();
const bater=()=>{ if(document.hidden) batidas.forEach(f=>{ try{ f(); }catch(e){ console.warn(e); } }); };
/**
 * Com a aba do navegador escondida, o navegador para o requestAnimationFrame e segura os timers em 1 por segundo.
 * Um timer dentro de um Worker não é segurado: ele chama `f` cerca de 30 vezes por segundo enquanto a aba está escondida.
 */
export function relogioFundo(f:()=>void){
  batidas.add(f);
  if(!relogio&&!reserva){
    try{ relogio=new Worker(URL.createObjectURL(new Blob(['setInterval(()=>postMessage(0),33)'],{type:'text/javascript'}))); relogio.onmessage=bater; relogio.onerror=()=>{ relogio=null; if(!reserva) reserva=window.setInterval(bater,250); }; }
    catch{ reserva=window.setInterval(bater,250); }
  }
  return ()=>{ batidas.delete(f); if(batidas.size) return; relogio?.terminate(); relogio=null; clearInterval(reserva); reserva=0; };
}

/** Devolve o controle ao navegador sem usar timer (timers ficam lentos com a aba escondida). */
const canal=typeof MessageChannel!=='undefined'?new MessageChannel():null; const fila:(()=>void)[]=[];
if(canal) canal.port1.onmessage=()=>fila.shift()?.();
export const ceder=()=>new Promise<void>(r=>{ if(!canal){ setTimeout(r,0); return; } fila.push(r); canal.port2.postMessage(0); });

/** Leva um vídeo para o instante exato e espera o quadro chegar. */
export function irPara(v:HTMLVideoElement,alvo:number){
  if(!v.paused) v.pause();
  if(v.readyState>=2&&!v.seeking&&Math.abs(v.currentTime-alvo)<0.012) return Promise.resolve();
  return new Promise<void>(r=>{ let ok=false; const fim=()=>{ if(ok) return; ok=true; v.removeEventListener('seeked',fim); v.removeEventListener('error',fim); clearTimeout(t); r(); };
    const t=setTimeout(fim,4000); v.addEventListener('seeked',fim); v.addEventListener('error',fim); try{ v.currentTime=alvo; }catch{ fim(); } });
}

// ---------------------------------------------------------------- gravação quadro a quadro

export type Quadros = {
  w:number; h:number; fps?:number; total:number; audio:AudioBuffer|null; bitrate?:number;
  /** Desenha o quadro do instante `t`. Pode esperar (por exemplo, o vídeo chegar no ponto certo). */
  desenhar:(ctx:CanvasRenderingContext2D,t:number)=>void|Promise<void>;
  onPct?:(p:number)=>void;
};
export type Gravado = {blob:Blob;ext:string};

async function em48k(a:AudioBuffer){ const c=new OfflineAudioContext(a.numberOfChannels,Math.ceil(a.duration*48000),48000); const n=c.createBufferSource(); n.buffer=a; n.connect(c.destination); n.start(); return c.startRendering(); }
function pedaco(a:AudioBuffer,de:number,ate:number){ const n=ate-de; const b=new AudioBuffer({length:n,numberOfChannels:a.numberOfChannels,sampleRate:a.sampleRate});
  for(let c=0;c<a.numberOfChannels;c++) b.copyToChannel(a.getChannelData(c).subarray(de,ate),c); return b; }

/**
 * Grava o vídeo desenhando e codificando um quadro por vez: nenhum quadro é perdido, o som fica no ponto exato
 * e continua mesmo com a aba escondida. Devolve null quando o navegador não tem o codificador (aí vale a gravação em tempo real).
 */
export async function gravarQuadros(q:Quadros):Promise<Gravado|null>{
  if(typeof VideoEncoder==='undefined'||typeof VideoFrame==='undefined') return null;
  const fps=q.fps||30, bitrate=q.bitrate||8_000_000; let audio=q.audio;
  let mb:typeof import('mediabunny');
  try{ mb=await import('mediabunny'); }catch{ return null; }
  const medida={width:q.w,height:q.h,bitrate};
  const podeAudio=(codec:'aac'|'opus',a:AudioBuffer)=>mb.canEncodeAudio(codec,{numberOfChannels:a.numberOfChannels,sampleRate:a.sampleRate,bitrate:192_000}).catch(()=>false);
  let video:'avc'|'vp9'|'vp8'|null=null, som:'aac'|'opus'|null=null, mp4=false;
  try{
    if(await mb.canEncodeVideo('avc',medida)&&(!audio||await podeAudio('aac',audio))){ video='avc'; som=audio?'aac':null; mp4=true; }
    else{
      for(const c of ['vp9','vp8'] as const) if(await mb.canEncodeVideo(c,medida)){ video=c; break; }
      if(video&&audio){ if(!(await podeAudio('opus',audio))) audio=await em48k(audio); if(!(await podeAudio('opus',audio))) video=null; else som='opus'; }
    }
  }catch{ return null; }
  if(!video) return null;

  const cv=document.createElement('canvas'); cv.width=q.w; cv.height=q.h; const ctx=cv.getContext('2d',{alpha:false})!;
  const saida=new mb.Output({format:mp4?new mb.Mp4OutputFormat({fastStart:'in-memory'}):new mb.WebMOutputFormat(),target:new mb.BufferTarget()});
  const fv=new mb.CanvasSource(cv,{codec:video,bitrate,keyFrameInterval:2}); saida.addVideoTrack(fv,{frameRate:fps});
  const fa=audio&&som?new mb.AudioBufferSource({codec:som,bitrate:192_000}):null; if(fa) saida.addAudioTrack(fa);
  const pend:Promise<unknown>[]=[];
  try{
    await saida.start();
    const n=Math.max(1,Math.round(q.total*fps)); let somAte=0, ultimo=performance.now();
    const mandarSom=(ateSeg:number)=>{ if(!fa||!audio) return; const ate=Math.min(audio.length,Math.round(ateSeg*audio.sampleRate)); if(ate>somAte){ pend.push(fa.add(pedaco(audio,somAte,ate))); somAte=ate; } };
    for(let i=0;i<n;i++){
      const t=Math.min(q.total-0.001,i/fps);
      ctx.setTransform(1,0,0,1,0,0); ctx.globalAlpha=1; ctx.filter='none';
      await q.desenhar(ctx,t);
      await fv.add(i/fps,1/fps);
      if(i%fps===fps-1) mandarSom((i+1)/fps);
      if(i%3===0) q.onPct?.(Math.min(99,Math.round(i/n*100)));
      if(performance.now()-ultimo>24){ await ceder(); ultimo=performance.now(); }
    }
    mandarSom(Infinity); await Promise.all(pend);
    await saida.finalize();
  }catch(e){ console.warn('Gravação quadro a quadro falhou, usando a gravação em tempo real',e); try{ await saida.cancel(); }catch{ /* já encerrou */ } return null; }
  const buf=saida.target.buffer; if(!buf||buf.byteLength<1000) return null;
  q.onPct?.(100);
  return {blob:new Blob([buf],{type:mp4?'video/mp4':'video/webm'}),ext:mp4?'mp4':'webm'};
}
