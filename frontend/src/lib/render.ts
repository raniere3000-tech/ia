// Exportação de cortes 1080x1920 no navegador (canvas + MediaRecorder), sem servidor.
import type { Clip } from './analyze';
import { drawCaption, drawHook, type Cue, type Preset } from './captions';

export const W = 1080, H = 1920, FPS = 30;

export function formatoSuportado(){
  const tipos = ['video/mp4;codecs=avc1.640028,mp4a.40.2','video/mp4;codecs=avc1,mp4a','video/webm;codecs=vp9,opus','video/webm;codecs=vp8,opus','video/webm','video/mp4'];
  if(typeof MediaRecorder==='undefined') return null;
  return tipos.find(t=>MediaRecorder.isTypeSupported(t)) || null;
}

type Opts = {legenda:Preset|null;efeito:string;cues:Cue[];gancho:string;accent:string};

export function drawFrame(ctx:CanvasRenderingContext2D,v:HTMLVideoElement,small:HTMLCanvasElement,t:number,clipDur:number,o:Opts){
  const vw = v.videoWidth||16, vh = v.videoHeight||9;
  ctx.fillStyle = '#000'; ctx.fillRect(0,0,W,H);
  const cover = Math.max(W/vw,H/vh), fit = Math.min(W/vw,H/vh);
  if(o.efeito==='nenhum'){
    ctx.drawImage(v,(W-vw*cover)/2,(H-vh*cover)/2,vw*cover,vh*cover);
  }else{
    // Fundo desfocado: reduz para um canvas minúsculo e amplia (funciona em todos os navegadores).
    const s = small.getContext('2d')!;
    s.drawImage(v,(small.width-vw*cover/20)/2,(small.height-vh*cover/20)/2,vw*cover/20,vh*cover/20);
    ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
    ctx.globalAlpha = 1; ctx.drawImage(small,0,0,W,H);
    ctx.fillStyle = 'rgba(0,0,0,.35)'; ctx.fillRect(0,0,W,H);
    let z = 1, dx = 0, dy = 0;
    if(o.efeito==='zoom-acao') z = 1 + 0.18*Math.min(1,t/Math.max(1,clipDur));
    if(o.efeito==='camera-shake'){ const burst = (t%4) < 0.22; if(burst){ dx=(Math.random()-.5)*28; dy=(Math.random()-.5)*28; } }
    const fw = vw*fit*z, fh = vh*fit*z;
    ctx.drawImage(v,(W-fw)/2+dx,(H-fh)/2+dy,fw,fh);
  }
  if(o.legenda){
    const cue = o.cues.find(c=>t>=c.start&&t<c.end);
    if(cue) drawCaption(ctx,o.legenda,cue.text,t-cue.start,cue.end-cue.start,W,H);
  }
  drawHook(ctx,o.gancho,o.accent,W);
  if(o.efeito==='transicao-fade'){
    const a = Math.max(0,1-t/0.4, 1-(clipDur-t)/0.4);
    if(a>0){ ctx.fillStyle = `rgba(0,0,0,${Math.min(1,a)})`; ctx.fillRect(0,0,W,H); }
  }
  if(o.efeito==='virada-cena' && t<0.35){ ctx.fillStyle = `rgba(255,255,255,${1-t/0.35})`; ctx.fillRect(0,0,W,H); }
}

/** Grava o corte em tempo real. Mantenha a aba visível durante a exportação. */
export async function exportarCorte(url:string,clip:Clip,cuesAbs:Cue[],o:Omit<Opts,'cues'>,progress:(n:number)=>void){
  const mime = formatoSuportado();
  if(!mime) throw new Error('Este navegador não grava vídeo. Use Chrome, Edge ou Safari atualizados.');
  const dur = clip.fim-clip.inicio;
  const cues = cuesAbs.filter(c=>c.end>clip.inicio&&c.start<clip.fim).map(c=>({start:Math.max(0,c.start-clip.inicio),end:Math.min(dur,c.end-clip.inicio),text:c.text}));
  const v = document.createElement('video');
  v.src = url; v.playsInline = true; v.preload = 'auto';
  await new Promise<void>((res,rej)=>{v.onloadedmetadata=()=>res();v.onerror=()=>rej(new Error('Não foi possível abrir o vídeo.'));});
  const canvas = document.createElement('canvas'); canvas.width=W; canvas.height=H;
  const ctx = canvas.getContext('2d')!;
  const small = document.createElement('canvas'); small.width=54; small.height=96;
  const stream = canvas.captureStream(FPS);
  const ac = new AudioContext();
  await ac.resume();
  const src = ac.createMediaElementSource(v); const dest = ac.createMediaStreamDestination();
  src.connect(dest);
  dest.stream.getAudioTracks().forEach(t=>stream.addTrack(t));
  const rec = new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:8_000_000,audioBitsPerSecond:160_000});
  const chunks:Blob[] = [];
  rec.ondataavailable = e=>{ if(e.data.size) chunks.push(e.data); };
  const done = new Promise<void>(res=>{ rec.onstop=()=>res(); });
  v.currentTime = clip.inicio;
  await new Promise<void>(res=>{ v.onseeked=()=>res(); });
  const opts:Opts = {...o,cues};
  drawFrame(ctx,v,small,0,dur,opts);
  rec.start(1000);
  try{ await v.play(); }catch{ rec.stop(); ac.close(); throw new Error('O navegador bloqueou a reprodução. Clique novamente em Exportar.'); }
  await new Promise<void>(res=>{
    const tick = ()=>{
      const t = v.currentTime-clip.inicio;
      if(o.efeito==='speed-ramp') v.playbackRate = (t>dur*0.4&&t<dur*0.6) ? 1.5 : 1;
      if(t>=dur || v.ended){ res(); return; }
      drawFrame(ctx,v,small,t,dur,opts);
      progress(Math.min(99,Math.round(t/dur*100)));
      if('requestVideoFrameCallback' in v) (v as any).requestVideoFrameCallback(tick); else requestAnimationFrame(tick);
    };
    v.onended = ()=>res();
    tick();
    // Garantia caso o navegador pare de entregar quadros.
    setTimeout(res,(dur*1.2+10)*1000);
  });
  v.pause(); rec.stop(); await done;
  stream.getTracks().forEach(t=>t.stop()); ac.close(); v.removeAttribute('src'); v.load();
  progress(100);
  const type = mime.split(';')[0];
  return {blob:new Blob(chunks,{type}),ext:type==='video/mp4'?'mp4':'webm'};
}
