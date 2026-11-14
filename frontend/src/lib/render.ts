// Renderização dos cortes no navegador (canvas + MediaRecorder): prévia e exportação.
import { drawCaption, drawHook, FONT_STACK, type Cue, type Preset } from './captions';
import type { Formato, Tarja } from './analyze';
import fixWebmDuration from 'fix-webm-duration';

export const FPS = 30;
export const DIMS:Record<Formato,[number,number]> = {'9:16':[1080,1920],'1:1':[1080,1080],'16:9':[1920,1080]};

export type Template = {ativo:boolean; logo:string; logoPos:'top-left'|'top-right'|'bottom-left'|'bottom-right'; credito:string; cor:string; moldura:boolean};
export const TEMPLATE_PADRAO:Template = {ativo:false,logo:'',logoPos:'top-right',credito:'',cor:'#7758ef',moldura:false};

import { posicao, type Trilha } from './rosto';
/** Parte do vídeo original, em frações de 0 a 1 (x, y, largura, altura). */
export type Regiao = {x:number;y:number;w:number;h:number};
/** Composição vinda de um template: enquadramento, zoom e posição. Sem isso vale o comportamento antigo (pelo efeito). */
export type Visual = {layout:'desfoque'|'cheio'|'gameplay-streamer'; zoom:number; posX:number; posY:number; jogo:Regiao; camera:Regiao; divisao:number; gancho:boolean; ganchoPos:'topo'|'alto'};
export type RenderOpts = {legenda:Preset|null; efeito:string; cues:Cue[]; gancho:string; accent:string; template:Template; logoImg?:HTMLImageElement|null; rosto?:Trilha|null; tarja?:Tarja|null; visual?:Visual|null};
/** Tamanho e peso do arquivo exportado. escala 1 = 1080p; 2/3 = 720p. */
export type Saida = {escala:number; bitrate:number};

/** Desenha uma parte do vídeo preenchendo um retângulo do quadro (corta o que sobra, sem distorcer). */
function drawRegiao(ctx:CanvasRenderingContext2D,v:HTMLVideoElement,r:Regiao,vw:number,vh:number,dx:number,dy:number,dw:number,dh:number){
  let sx=vw*r.x, sy=vh*r.y, sw=Math.max(2,vw*r.w), sh=Math.max(2,vh*r.h);
  const alvo=dw/dh;
  if(sw/sh>alvo){ const n=sh*alvo; sx+=(sw-n)/2; sw=n; } else { const n=sw/alvo; sy+=(sh-n)/2; sh=n; }
  ctx.drawImage(v,sx,sy,sw,sh,dx,dy,dw,dh);
}

export function formatoSuportado(){
  if(typeof MediaRecorder==='undefined') return null;
  const tipos = ['video/mp4;codecs=avc1.640028,mp4a.40.2','video/mp4;codecs=avc1,mp4a','video/webm;codecs=vp9,opus','video/webm;codecs=vp8,opus','video/webm','video/mp4'];
  return tipos.find(t=>MediaRecorder.isTypeSupported(t)) || null;
}

export function loadImage(src:string){
  return new Promise<HTMLImageElement|null>(res=>{ if(!src) return res(null); const i=new Image(); i.onload=()=>res(i); i.onerror=()=>res(null); i.src=src; });
}

/** Desenha um quadro. `t` = segundos desde o início do corte. */
export function drawFrame(ctx:CanvasRenderingContext2D,v:HTMLVideoElement,small:HTMLCanvasElement,t:number,dur:number,o:RenderOpts,W:number,H:number){
  const vw=v.videoWidth||16, vh=v.videoHeight||9;
  ctx.save();
  ctx.fillStyle='#000'; ctx.fillRect(0,0,W,H);
  const cover=Math.max(W/vw,H/vh), fit=Math.min(W/vw,H/vh);
  let z=1,dx=0,dy=0;
  if(o.efeito==='zoom-acao') z=1+0.18*Math.min(1,t/Math.max(1,dur));
  if(o.efeito==='camera-shake' && (t%4)<0.22){ dx=(Math.random()-.5)*28; dy=(Math.random()-.5)*28; }
  const vis=o.visual||null;
  if(vis){ z*=Math.max(1,vis.zoom||1); }
  if(vis?.layout==='gameplay-streamer'){
    // Gameplay em cima e câmera do streamer embaixo, tirados do mesmo quadro (sempre sincronizados).
    const h1=Math.round(H*Math.max(35,Math.min(80,vis.divisao||62))/100/2)*2;
    drawRegiao(ctx,v,vis.jogo,vw,vh,0,0,W,h1);
    drawRegiao(ctx,v,vis.camera,vw,vh,0,h1,W,H-h1);
  }else if(o.efeito==='seguir-rosto' && o.rosto && Math.abs(W/H - vw/vh) >= 0.05){
    // Corta o quadro inteiro (sem bordas) e move a janela para manter o rosto no centro.
    const p=posicao(o.rosto,t); const w=vw*cover, h=vh*cover;
    const x=Math.min(0,Math.max(W-w,W/2-p.cx*w)), y=Math.min(0,Math.max(H-h,H*0.42-p.cy*h));
    ctx.drawImage(v,x,y,w,h);
  }else if(vis ? vis.layout==='cheio' : (o.efeito==='nenhum' || (o.efeito==='seguir-rosto' && o.rosto===undefined) || Math.abs(W/H - vw/vh) < 0.05)){
    const w=vw*cover*z, h=vh*cover*z; ctx.drawImage(v,(W-w)*(vis?vis.posX:0.5)+dx,(H-h)*(vis?vis.posY:0.5)+dy,w,h);
  }else{
    // Fundo desfocado: reduz para um canvas minúsculo e amplia (funciona em todos os navegadores).
    small.width = W>H?96:54; small.height = W>H?54:(W===H?54:96);
    const s=small.getContext('2d')!; const sc=Math.max(small.width/vw,small.height/vh);
    s.drawImage(v,(small.width-vw*sc)/2,(small.height-vh*sc)/2,vw*sc,vh*sc);
    ctx.imageSmoothingEnabled=true; ctx.imageSmoothingQuality='high';
    ctx.drawImage(small,0,0,W,H);
    ctx.fillStyle='rgba(0,0,0,.35)'; ctx.fillRect(0,0,W,H);
    const w=vw*fit*z, h=vh*fit*z; ctx.drawImage(v,(W-w)/2+dx,(H-h)/2+dy,w,h);
  }
  const hTarja=o.tarja?drawTarjas(ctx,o.tarja,W,H):0;
  if(o.legenda){ const cue=o.cues.find(c=>t>=c.start&&t<c.end); if(cue) drawCaption(ctx,o.legenda,cue.text,t-cue.start,cue.end-cue.start,W,H); }
  if(!vis||vis.gancho) drawHook(ctx,o.gancho,o.accent,W,o.tarja?.topo?hTarja:0,vis?.ganchoPos==='alto'?H*0.14:0);
  if(o.template.ativo) drawTemplate(ctx,o.template,o.logoImg||null,W,H);
  if(o.efeito==='transicao-fade'){ const a=Math.max(0,1-t/0.4,1-(dur-t)/0.4); if(a>0){ ctx.fillStyle=`rgba(0,0,0,${Math.min(1,a)})`; ctx.fillRect(0,0,W,H);} }
  if(o.efeito==='virada-cena' && t<0.35){ ctx.fillStyle=`rgba(255,255,255,${1-t/0.35})`; ctx.fillRect(0,0,W,H); }
  ctx.restore();
}

/** Tarjas (faixas) em cima e embaixo do vídeo. Devolve a altura de cada faixa em pixels. */
export function drawTarjas(ctx:CanvasRenderingContext2D,tj:Tarja,W:number,H:number){
  const h=Math.round(H*Math.max(4,Math.min(25,tj.altura||12))/100);
  const faixa=(y:number,texto:string)=>{
    ctx.fillStyle=tj.cor; ctx.fillRect(0,y,W,h);
    const txt=texto.trim(); if(!txt) return;
    ctx.textAlign='center'; ctx.textBaseline='middle'; ctx.fillStyle=tj.corTexto;
    let fs=Math.round(h*0.42); ctx.font=`800 ${fs}px ${FONT_STACK}`;
    const larg=ctx.measureText(txt).width; if(larg>W*0.92){ fs=Math.max(14,Math.floor(fs*W*0.92/larg)); ctx.font=`800 ${fs}px ${FONT_STACK}`; }
    ctx.fillText(txt,W/2,y+h/2,W*0.94);
  };
  ctx.save();
  if(tj.topo) faixa(0,tj.textoTopo);
  if(tj.base) faixa(H-h,tj.textoBase);
  ctx.restore();
  return h;
}

export function drawTemplate(ctx:CanvasRenderingContext2D,tp:Template,logo:HTMLImageElement|null,W:number,H:number){
  const m = Math.round(Math.min(W,H)*0.04);
  if(tp.moldura){ ctx.strokeStyle=tp.cor; ctx.lineWidth=m*0.6; ctx.strokeRect(m*0.3,m*0.3,W-m*0.6,H-m*0.6); }
  if(logo){
    const lw=Math.min(W,H)*0.16, lh=lw*logo.height/logo.width;
    const x = tp.logoPos.endsWith('left') ? m : W-m-lw; const y = tp.logoPos.startsWith('top') ? m : H-m-lh;
    ctx.globalAlpha=0.92; ctx.drawImage(logo,x,y,lw,lh); ctx.globalAlpha=1;
  }
  if(tp.credito.trim()){
    ctx.font=`700 ${Math.round(Math.min(W,H)*0.032)}px ${FONT_STACK}`; ctx.textBaseline='middle'; ctx.textAlign='center';
    const text=tp.credito.trim(); const w=ctx.measureText(text).width+48, h=Math.round(Math.min(W,H)*0.055);
    const y=H-m*1.6-h/2;
    ctx.fillStyle=tp.cor; ctx.fillRect(W/2-w/2,y-h/2,w,h);
    ctx.fillStyle='#fff'; ctx.fillText(text,W/2,y);
  }
}

export type ExportClip = {inicio:number;fim:number;formato:Formato};

/** Grava o corte em tempo real. Mantenha a aba visível durante a exportação. */
export async function exportarCorte(url:string,clip:ExportClip,cuesAbs:Cue[],o:Omit<RenderOpts,'cues'>,progress:(n:number)=>void,dub?:{samples:Float32Array;rate:number;volumeOriginal:number}|null,saida?:Saida|null){
  const mime=formatoSuportado();
  if(!mime) throw new Error('Este navegador não grava vídeo. Use Chrome, Edge ou Safari atualizados.');
  const [W,H]=DIMS[clip.formato];
  const dur=clip.fim-clip.inicio;
  const cues=cuesAbs.filter(c=>c.end>clip.inicio&&c.start<clip.fim).map(c=>({start:Math.max(0,c.start-clip.inicio),end:Math.min(dur,c.end-clip.inicio),text:c.text}));
  const v=document.createElement('video'); v.src=url; v.playsInline=true; v.preload='auto';
  await new Promise<void>((res,rej)=>{v.onloadedmetadata=()=>res();v.onerror=()=>rej(new Error('Não foi possível abrir o vídeo.'));});
  // O desenho é sempre feito na medida de 1080p; para 720p o quadro inteiro é reduzido por igual.
  const esc=saida?.escala&&saida.escala>0&&saida.escala<1?saida.escala:1;
  const canvas=document.createElement('canvas'); canvas.width=Math.round(W*esc/2)*2; canvas.height=Math.round(H*esc/2)*2;
  const ctx=canvas.getContext('2d')!; const small=document.createElement('canvas');
  if(esc!==1) ctx.setTransform(canvas.width/W,0,0,canvas.height/H,0,0);
  const stream=canvas.captureStream(FPS);
  const ac=new AudioContext(); await ac.resume();
  const src=ac.createMediaElementSource(v); const dest=ac.createMediaStreamDestination();
  // Com dublagem, o áudio original fica baixinho e a voz em português entra por cima.
  let voz:AudioBufferSourceNode|null=null; let vozIniciada=false;
  if(dub){
    const g=ac.createGain(); g.gain.value=dub.volumeOriginal; src.connect(g); g.connect(dest);
    const buf=ac.createBuffer(1,dub.samples.length,dub.rate); buf.copyToChannel(dub.samples as Float32Array<ArrayBuffer>,0);
    voz=ac.createBufferSource(); voz.buffer=buf; voz.connect(dest);
  } else src.connect(dest);
  dest.stream.getAudioTracks().forEach(t=>stream.addTrack(t));
  const rec=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:saida?.bitrate||8_000_000,audioBitsPerSecond:160_000});
  const chunks:Blob[]=[]; rec.ondataavailable=e=>{ if(e.data.size) chunks.push(e.data); };
  const done=new Promise<void>(res=>{ rec.onstop=()=>res(); });
  v.currentTime=clip.inicio;
  await new Promise<void>(res=>{ v.onseeked=()=>res(); });
  const opts:RenderOpts={...o,cues};
  drawFrame(ctx,v,small,0,dur,opts,W,H);
  rec.start(1000);
  try{ await v.play(); }catch{ rec.stop(); ac.close(); throw new Error('O navegador bloqueou a reprodução. Clique novamente em Exportar.'); }
  await new Promise<void>(res=>{
    const tick=()=>{
      const t=v.currentTime-clip.inicio;
      // A voz começa junto com o primeiro quadro que anda de verdade, no mesmo ponto do vídeo.
      if(voz&&!vozIniciada&&t>0){ vozIniciada=true; voz.start(0,Math.max(0,t)); }
      if(o.efeito==='speed-ramp'&&!dub) v.playbackRate=(t>dur*0.4&&t<dur*0.6)?1.5:1;
      if(t>=dur||v.ended){ res(); return; }
      drawFrame(ctx,v,small,t,dur,opts,W,H);
      progress(Math.min(99,Math.round(t/dur*100)));
      if('requestVideoFrameCallback' in v) (v as any).requestVideoFrameCallback(tick); else requestAnimationFrame(tick);
    };
    v.onended=()=>res();
    tick();
    setTimeout(res,(dur*1.3+10)*1000);
  });
  v.pause(); rec.stop(); await done;
  stream.getTracks().forEach(t=>t.stop()); ac.close(); v.removeAttribute('src'); v.load();
  progress(100);
  const type=mime.split(';')[0];
  let blob=new Blob(chunks,{type});
  // O WEBM gravado pelo navegador sai sem duração no cabeçalho; corrigimos para os players.
  if(type==='video/webm'){ try{ blob=await fixWebmDuration(blob,dur*1000,{logger:false}); }catch{ /* mantém o original */ } }
  return {blob,ext:type==='video/mp4'?'mp4':'webm'};
}
