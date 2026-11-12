// Editor com linha do tempo (faixas de vídeo, texto, narração, trilha e efeitos) para a Montagem manual.
// Tudo roda no navegador: o desenho é feito num canvas e o áudio é misturado com a Web Audio API.
import fixWebmDuration from 'fix-webm-duration';
import { formatoSuportado } from './render';
import { FONT_STACK, drawCaption } from './captions';
import { captionPresets } from '../state';
import { gerarSom } from './sons';
import { SR, TAMANHO, audioDe, cobrir, midias, narracoesDe, quebrar, type Anim, type Arquivo, type Formato, type Opcoes, type Sinc } from './montagem';

/** Efeitos de imagem de cada bloco de vídeo (os mesmos nomes da aba Legendas e efeitos, mais dois). */
export type EfeitoV = 'nenhum'|'blur-background'|'virada-cena'|'transicao-fade'|'camera-shake'|'pb'|'vinheta';
export const EFEITOS_VIDEO:[EfeitoV,string,string][] = [['nenhum','Sem efeito','A imagem preenche a tela toda.'],['blur-background','Fundo desfocado','A imagem aparece inteira no centro e o fundo é uma cópia desfocada dela. Bom para imagem deitada em vídeo em pé.'],
  ['virada-cena','Flash na entrada','Clarão branco quando o quadro começa.'],['transicao-fade','Entra e sai do preto','Aparece e some suavemente.'],['camera-shake','Tremores','Pequenos tremores a cada 4 segundos.'],['pb','Preto e branco','Tira a cor da imagem.'],['vinheta','Bordas escuras','Escurece os cantos e chama o olhar para o centro.']];
export type Faixa = 'video'|'texto'|'narracao'|'trilha'|'efeito';
export const FAIXAS:[Faixa,string][] = [['video','Vídeo'],['texto','Texto'],['narracao','Narração'],['trilha','Trilha'],['efeito','Efeitos']];
type Base = {id:string;ini:number;dur:number};
export type ClipV = Base&{faixa:'video';midia:string;de:number;anim:Anim;entrada:'corte'|'fade';brilho:number;contraste:number;saturacao:number;efeito?:EfeitoV};
export type ClipT = Base&{faixa:'texto';texto:string;pos:'topo'|'meio'|'baixo';tam:number;cor:string;fundo:boolean;estilo?:string};
export type ClipA = Base&{faixa:'narracao'|'trilha'|'efeito';fonte:string;nome:string;de:number;fonteDur:number;vol:number;fadeIn:number;fadeOut:number;loop:boolean};
export type Clip = ClipV|ClipT|ClipA;
export type FaixaAudio = 'narracao'|'trilha'|'efeito';
/** Camada inteira: volume geral, mudo e "só esta". */
export type Camada = {vol:number;mudo:boolean;solo:boolean};
export type Proj = {clips:Clip[];formato:Formato;abaixarTrilha:boolean;mix?:Partial<Record<FaixaAudio,Camada>>;
  /** Estilo das legendas do projeto (id de um estilo pronto). Vazio = texto simples. */
  legenda?:string};
export const CAMADAS:[FaixaAudio,string][] = [['narracao','Vozes'],['trilha','Música'],['efeito','Efeitos']];
export const camadaDe = (p:Proj,f:FaixaAudio):Camada=>({vol:100,mudo:false,solo:false,...p.mix?.[f]});
/** Ganho final da camada (0 quando está muda ou quando outra camada está em "só esta"). */
export function ganhoCamada(p:Proj,f:FaixaAudio){ const c=camadaDe(p,f); const algumSolo=CAMADAS.some(([k])=>camadaDe(p,k).solo); return c.mudo||(algumSolo&&!c.solo)?0:Math.max(0,c.vol)/100; }

export const novoId = ()=>Math.random().toString(36).slice(2,9);
export const fimDe = (c:Clip)=>c.ini+c.dur;
export const totalDe = (p:Proj)=>Math.max(1,...p.clips.map(fimDe));
export const ehAudio = (c:Clip):c is ClipA=>c.faixa==='narracao'||c.faixa==='trilha'||c.faixa==='efeito';

/** Monta o projeto do editor a partir da sincronização automática. */
export function deSinc(s:Sinc,arquivos:Arquivo[],o:Opcoes):Proj{
  const clips:Clip[] = [];
  const dur = (id:string)=>arquivos.find(a=>a.id===id)?.duracao||0;
  for(const q of s.quadros){
    clips.push({faixa:'video',id:novoId(),ini:q.ini,dur:q.dur,midia:q.midia,de:0,anim:q.anim,entrada:o.transicao==='fade'?'fade':'corte',brilho:100,contraste:100,saturacao:100});
    if(o.legendas) for(const l of q.legenda) clips.push({faixa:'texto',id:novoId(),ini:+(q.ini+l.ini).toFixed(3),dur:+Math.max(0.3,l.fim-l.ini).toFixed(3),texto:l.texto,pos:'baixo',tam:100,cor:'#ffffff',fundo:false});
    for(const sm of q.sons){ const fonte=sm.arquivo||'site:'+sm.desc; const d=sm.arquivo?dur(sm.arquivo):0;
      clips.push({faixa:'efeito',id:novoId(),ini:+(q.ini+sm.em).toFixed(3),dur:d||1.5,fonte,nome:sm.desc,de:0,fonteDur:d,vol:sm.vol,fadeIn:0,fadeOut:0,loop:false}); }
  }
  const nars = arquivos.filter(a=>a.tipo==='narracao');
  if(s.narracao==='unica'&&nars[0]) clips.push({faixa:'narracao',id:novoId(),ini:0,dur:nars[0].duracao,fonte:nars[0].id,nome:nars[0].nome,de:0,fonteDur:nars[0].duracao,vol:100,fadeIn:0,fadeOut:0,loop:false});
  if(s.narracao==='separada') for(const q of s.quadros) for(const n of narracoesDe(q)){ const a=nars.find(x=>x.id===n.arquivo); if(a) clips.push({faixa:'narracao',id:novoId(),ini:+(q.ini+n.em).toFixed(3),dur:a.duracao,fonte:a.id,nome:a.nome,de:0,fonteDur:a.duracao,vol:100,fadeIn:0,fadeOut:0,loop:false}); }
  for(const t of s.trilhas){ const a=arquivos.find(x=>x.id===t.arquivo); if(a) clips.push({faixa:'trilha',id:novoId(),ini:t.ini,dur:+(t.fim-t.ini).toFixed(3),fonte:a.id,nome:a.nome,de:0,fonteDur:a.duracao,vol:o.volTrilha,fadeIn:0.8,fadeOut:1.2,loop:true}); }
  return {clips,formato:o.formato,abaixarTrilha:true};
}

/** O som de um clipe: arquivo enviado ou "site:descrição" (feito pelo próprio site). */
export async function bufferDe(fonte:string,arquivos:Arquivo[]):Promise<AudioBuffer|null>{
  if(fonte.startsWith('site:')){ const desc=fonte.slice(5); const g=await gerarSom(desc,'site'); return audioDe({id:fonte,blob:g.wav,nome:desc}); }
  const a=arquivos.find(x=>x.id===fonte); return a?audioDe(a):null;
}
/** Desenho da onda de cada som (40 picos por segundo), guardado para não recalcular. */
export type Picos = {p:Float32Array;dur:number;max:number};
const PICOS=new Map<string,Promise<Picos|null>>(); export const PPS_ONDA=40;
export function picosDe(fonte:string,arquivos:Arquivo[]):Promise<Picos|null>{
  if(!fonte.startsWith('site:')&&!arquivos.some(a=>a.id===fonte)) return Promise.resolve(null);
  let r=PICOS.get(fonte);
  if(!r){ r=(async()=>{ try{ const b=await bufferDe(fonte,arquivos); if(!b) return null; const d=b.getChannelData(0); const h=Math.max(1,Math.floor(b.sampleRate/PPS_ONDA)); const n=Math.ceil(d.length/h); const p=new Float32Array(n); let max=0.001;
      for(let i=0;i<n;i++){ let m=0; const f=Math.min(d.length,(i+1)*h); for(let k=i*h;k<f;k+=4){ const v=Math.abs(d[k]); if(v>m) m=v; } p[i]=m; if(m>max) max=m; }
      return {p,dur:b.duration,max}; }catch{ return null; } })(); PICOS.set(fonte,r); r.then(x=>{ if(!x) PICOS.delete(fonte); }); }
  return r;
}
/** Descobre a duração dos sons feitos pelo site (para o tamanho do bloco na linha do tempo). */
export async function acertarDuracoes(p:Proj,arquivos:Arquivo[]):Promise<Proj|null>{
  let mudou=false; const clips:Clip[]=[];
  for(const c of p.clips){
    if(ehAudio(c)&&!c.fonteDur){ try{ const b=await bufferDe(c.fonte,arquivos); if(b){ mudou=true; clips.push({...c,fonteDur:b.duration,dur:c.loop?c.dur:b.duration}); continue; } }catch{ /* fica como está */ } }
    clips.push(c);
  }
  return mudou?{...p,clips}:null;
}

// ---------------------------------------------------------------- edição

export function dividir(p:Proj,id:string,t:number):Proj{
  const c=p.clips.find(x=>x.id===id); if(!c||t<=c.ini+0.1||t>=fimDe(c)-0.1) return p;
  const a={...c,dur:+(t-c.ini).toFixed(3)} as Clip; const b={...c,id:novoId(),ini:+t.toFixed(3),dur:+(fimDe(c)-t).toFixed(3)} as Clip;
  if(b.faixa==='video') b.de=c.faixa==='video'?c.de+(t-c.ini):0;
  if(ehAudio(b)&&ehAudio(c)){ b.de=c.de+(t-c.ini); (a as ClipA).fadeOut=0; b.fadeIn=0; }
  return {...p,clips:p.clips.flatMap(x=>x.id===id?[a,b]:[x])};
}
export function duplicar(p:Proj,id:string):Proj{ const c=p.clips.find(x=>x.id===id); if(!c) return p; return {...p,clips:[...p.clips,{...c,id:novoId(),ini:+fimDe(c).toFixed(3)} as Clip]}; }
/** Depois de mudar o fim de um bloco, leva junto tudo que começava dali em diante. */
export function empurrar(p:Proj,id:string,fimAntigo:number,delta:number):Proj{ if(Math.abs(delta)<0.001) return p; return {...p,clips:p.clips.map(c=>c.id!==id&&c.ini>=fimAntigo-0.01?{...c,ini:+Math.max(0,c.ini+delta).toFixed(3)} as Clip:c)}; }
/** Coloca um vídeo pronto na linha do tempo, com o som dele numa camada própria para poder mexer. */
export function clipsDeVideo(a:Arquivo,ini:number,temSom:boolean):Clip[]{
  const d=Math.max(0.5,a.duracao||3); const r:Clip[]=[{faixa:'video',id:novoId(),ini,dur:d,midia:a.id,de:0,anim:'parado' as Anim,entrada:'corte',brilho:100,contraste:100,saturacao:100}];
  if(temSom) r.push({faixa:'narracao',id:novoId(),ini,dur:d,fonte:a.id,nome:'Som de '+a.nome,de:0,fonteDur:d,vol:100,fadeIn:0,fadeOut:0,loop:false});
  return r;
}
export function apagar(p:Proj,id:string):Proj{ return {...p,clips:p.clips.filter(x=>x.id!==id)}; }
/** Limite do corte pela direita: sons sem repetição não passam do fim do arquivo. */
export function durMax(c:Clip){ return ehAudio(c)&&!c.loop&&c.fonteDur>0?Math.max(0.1,c.fonteDur-c.de):600; }

// ---------------------------------------------------------------- desenhar

const ativo = (c:Clip,t:number)=>t>=c.ini&&t<fimDe(c);
function clipVideoEm(vs:ClipV[],t:number){ let r:ClipV|undefined; for(const c of vs) if(ativo(c,t)&&(!r||c.ini>=r.ini)) r=c; return r; }

let fundo:HTMLCanvasElement|null=null;
/** Estilo pronto usado por um texto: o do próprio bloco, senão o do projeto. "simples" (ou nada) = texto simples com cor e fundo do bloco. */
export function estiloDe(p:Proj,x:ClipT){ const id=x.estilo||p.legenda||''; return id&&id!=='simples'?captionPresets.find(c=>c.id===id)||null:null; }
export function desenharProj(ctx:CanvasRenderingContext2D,p:Proj,t:number){
  const W=ctx.canvas.width, H=ctx.canvas.height; ctx.fillStyle='#000'; ctx.fillRect(0,0,W,H);
  const vs=p.clips.filter((c):c is ClipV=>c.faixa==='video');
  const pinta=(c:ClipV,alpha:number)=>{ const m=c.midia?midias.get(c.midia):undefined; const pr=Math.min(1,Math.max(0,(t-c.ini)/Math.max(0.1,c.dur)));
    const ef=c.efeito||'nenhum', tc=t-c.ini; const f=[c.brilho!==100?`brightness(${c.brilho}%)`:'',c.contraste!==100?`contrast(${c.contraste}%)`:'',c.saturacao!==100?`saturate(${c.saturacao}%)`:'',ef==='pb'?'grayscale(100%)':''].filter(Boolean).join(' ');
    ctx.save(); ctx.filter=f||'none';
    if(ef==='camera-shake'&&tc%4<0.22) ctx.translate(Math.sin(tc*91)*W*0.012,Math.cos(tc*77)*H*0.01);
    if(!m){ ctx.globalAlpha=alpha; ctx.fillStyle='#16161d'; ctx.fillRect(0,0,W,H); ctx.globalAlpha=1; }
    else if(ef==='blur-background'){
      // Fundo: a própria imagem bem pequena e ampliada (desfoque barato, não trava a gravação). Frente: a imagem inteira.
      const b=(fundo ||= document.createElement('canvas')); b.width=Math.max(16,Math.round(W/24)); b.height=Math.max(16,Math.round(H/24)); const bx=b.getContext('2d')!; bx.filter='blur(2px)'; cobrir(bx,m.el,b.width,b.height,'parado',0,1);
      ctx.globalAlpha=alpha; ctx.imageSmoothingQuality='high'; ctx.drawImage(b,-W*0.04,-H*0.04,W*1.08,H*1.08); ctx.fillStyle='rgba(0,0,0,.35)'; ctx.fillRect(0,0,W,H);
      const iw=(m.el as HTMLVideoElement).videoWidth||(m.el as HTMLImageElement).naturalWidth||W, ih=(m.el as HTMLVideoElement).videoHeight||(m.el as HTMLImageElement).naturalHeight||H;
      const k=Math.min(W/iw,H/ih)*(c.anim==='zoom-in'?1+0.06*pr:c.anim==='zoom-out'?1.06-0.06*pr:1); ctx.drawImage(m.el,(W-iw*k)/2,(H-ih*k)/2,iw*k,ih*k); ctx.globalAlpha=1; }
    else cobrir(ctx,m.el,W,H,c.anim,pr,alpha);
    ctx.restore();
    if(ef==='vinheta'){ const g=ctx.createRadialGradient(W/2,H/2,Math.min(W,H)*0.35,W/2,H/2,Math.hypot(W,H)/2); g.addColorStop(0,'rgba(0,0,0,0)'); g.addColorStop(1,`rgba(0,0,0,${0.7*alpha})`); ctx.fillStyle=g; ctx.fillRect(0,0,W,H); }
    if(ef==='transicao-fade'){ const a=Math.max(0,1-tc/0.4,1-(c.dur-tc)/0.4); if(a>0){ ctx.fillStyle=`rgba(0,0,0,${Math.min(1,a)*alpha})`; ctx.fillRect(0,0,W,H); } }
    if(ef==='virada-cena'&&tc>=0&&tc<0.35){ ctx.fillStyle=`rgba(255,255,255,${(1-tc/0.35)*alpha})`; ctx.fillRect(0,0,W,H); } };
  const c=clipVideoEm(vs,t);
  if(c){ const tr=Math.min(0.4,c.dur/2); const ant=c.entrada==='fade'&&t-c.ini<tr?clipVideoEm(vs.filter(x=>x.id!==c.id),c.ini-0.001):undefined;
    if(ant){ pinta(ant,1); pinta(c,(t-c.ini)/tr); } else pinta(c,1); }
  for(const x of p.clips) if(x.faixa==='texto'&&ativo(x,t)&&x.texto.trim()){
    const pre=estiloDe(p,x);
    if(pre){ const k=W/TAMANHO[p.formato][0]*x.tam/100; ctx.save(); ctx.scale(k,k); const w2=W/k, h2=H/k; if(x.pos==='topo') ctx.translate(0,-h2*0.34);
      drawCaption(ctx,{...pre,position:x.pos==='baixo'?'bottom':'center'},x.texto,t-x.ini,x.dur,w2,h2); ctx.restore(); continue; }
    const fs=Math.round(Math.min(W,H)*0.052*x.tam/100); ctx.font=`800 ${fs}px ${FONT_STACK}`; ctx.textAlign='center'; ctx.lineJoin='round';
    const ls=quebrar(ctx,x.texto,W*0.84).slice(0,5); const alt=ls.length*fs*1.2;
    const y0=x.pos==='topo'?H*0.12:x.pos==='meio'?H/2-alt/2+fs:H*(H>W?0.8:0.86)-alt+fs;
    if(x.fundo){ const lw=Math.max(...ls.map(l=>ctx.measureText(l).width)); ctx.fillStyle='rgba(0,0,0,.6)'; ctx.fillRect(W/2-lw/2-fs*0.4,y0-fs*1.05,lw+fs*0.8,alt+fs*0.35); }
    ls.forEach((l,k)=>{ const y=y0+k*fs*1.2; if(!x.fundo){ ctx.lineWidth=fs*0.16; ctx.strokeStyle='rgba(0,0,0,.9)'; ctx.strokeText(l,W/2,y); } ctx.fillStyle=x.cor; ctx.fillText(l,W/2,y); });
  }
}
export function sincronizarVideosProj(p:Proj,t:number,tocando:boolean){
  for(const c of p.clips){ if(c.faixa!=='video'||!c.midia) continue; const m=midias.get(c.midia); if(!m||m.tipo!=='video') continue; const v=m.el as HTMLVideoElement;
    const on=t>=c.ini-0.05&&t<fimDe(c)+0.45; if(!on) continue;
    const alvo=m.duracao>0?(c.de+Math.max(0,t-c.ini))%m.duracao:0;
    if(tocando){ if(Math.abs(v.currentTime-alvo)>0.35) v.currentTime=alvo; if(v.paused) v.play().catch(()=>{}); } else { if(!v.paused) v.pause(); if(Math.abs(v.currentTime-alvo)>0.05) v.currentTime=alvo; } }
  if(!tocando||t<0) for(const [,m] of midias) if(m.tipo==='video'&&t<0) (m.el as HTMLVideoElement).pause();
}

// ---------------------------------------------------------------- áudio

export async function mixarProj(p:Proj,arquivos:Arquivo[],onStatus:(t:string)=>void):Promise<AudioBuffer|null>{
  const as=p.clips.filter(ehAudio); if(!as.length) return null;
  const total=totalDe(p); const c=new OfflineAudioContext(2,Math.ceil(total*SR),SR);
  const comp=c.createDynamicsCompressor(); comp.threshold.value=-6; comp.ratio.value=8; comp.attack.value=0.003; comp.release.value=0.2; comp.connect(c.destination);
  const bufs=new Map<string,AudioBuffer|null>();
  for(const a of as) if(!bufs.has(a.fonte)){ onStatus('Preparando o som: '+a.nome); try{ bufs.set(a.fonte,await bufferDe(a.fonte,arquivos)); }catch{ bufs.set(a.fonte,null); } }
  // Onde tem voz (para abaixar a trilha).
  const passo=0.05, nP=Math.ceil(total/passo); const fala=new Uint8Array(nP);
  if(p.abaixarTrilha&&ganhoCamada(p,'narracao')>0) for(const a of as.filter(x=>x.faixa==='narracao')){ const b=bufs.get(a.fonte); if(!b) continue; const d=b.getChannelData(0); const h=Math.round(passo*b.sampleRate);
    for(let i=0;i*passo<a.dur;i++){ const s0=Math.floor((a.de+i*passo)*b.sampleRate); let m=0; for(let k=s0;k<Math.min(d.length,s0+h);k+=8) m=Math.max(m,Math.abs(d[k])); if(m>0.04){ const q=Math.floor((a.ini+i*passo)/passo); for(let x=q-3;x<=q+4;x++) if(x>=0&&x<nP) fala[x]=1; } } }
  for(const a of as){
    const b=bufs.get(a.fonte); if(!b||a.dur<0.05) continue;
    const n=c.createBufferSource(); n.buffer=b; const g=c.createGain(); n.connect(g).connect(comp);
    const gc=ganhoCamada(p,a.faixa); if(gc<=0) continue;
    const vol=Math.max(0,a.vol)/100*gc, ini=a.ini, fim=a.ini+a.dur;
    const fi=Math.min(a.fadeIn,a.dur/2), fo=Math.min(a.fadeOut,a.dur/2);
    g.gain.setValueAtTime(fi>0?0:vol,ini); if(fi>0) g.gain.linearRampToValueAtTime(vol,ini+fi);
    if(a.faixa==='trilha'&&p.abaixarTrilha){ let ult=-1; for(let q=Math.ceil((ini+fi+0.05)/passo);q<Math.floor((fim-fo-0.05)/passo);q++){ const st=fala[q]; if(st!==ult){ g.gain.setTargetAtTime(st?vol*0.35:vol,q*passo,st?0.06:0.25); ult=st; } } }
    if(fo>0){ g.gain.setTargetAtTime(0,fim-fo,fo/3); }
    if(a.loop){ n.loop=true; n.start(ini,a.de%b.duration); n.stop(fim); } else n.start(ini,Math.min(a.de,b.duration),Math.max(0.01,a.dur));
  }
  onStatus('Misturando o áudio');
  return c.startRendering();
}

// ---------------------------------------------------------------- tocar e gravar

export type Sessao = {parar:()=>void;fim:Promise<void>};
export function tocarProj(canvas:HTMLCanvasElement,p:Proj,audio:AudioBuffer|null,cb:{inicio?:number;onTempo?:(t:number)=>void;gravar?:(r:{blob:Blob;ext:string})=>void}={}):Sessao{
  const ctx=canvas.getContext('2d')!; const total=totalDe(p); const ac=new AudioContext(); const t00=cb.gravar?0:Math.min(cb.inicio||0,Math.max(0,total-0.2));
  let parado=false, raf=0, fonte:AudioBufferSourceNode|null=null, rec:MediaRecorder|null=null; const chunks:Blob[]=[]; let mime='';
  let resolver:()=>void=()=>{}; const fim=new Promise<void>(r=>{ resolver=r; });
  const destino=cb.gravar?ac.createMediaStreamDestination():null;
  if(audio){ fonte=ac.createBufferSource(); fonte.buffer=audio; fonte.connect(destino||ac.destination); }
  if(cb.gravar){
    mime=formatoSuportado()||''; if(!mime){ ac.close(); throw new Error('Este navegador não grava vídeo. Use Chrome, Edge ou Safari atualizados.'); }
    const st=canvas.captureStream(30); if(audio) destino!.stream.getAudioTracks().forEach(tk=>st.addTrack(tk));
    rec=new MediaRecorder(st,{mimeType:mime,videoBitsPerSecond:8_000_000,audioBitsPerSecond:192_000}); rec.ondataavailable=e=>{ if(e.data.size) chunks.push(e.data); };
  }
  let ok=false, t0=0;
  const encerrar=async()=>{ if(parado) return; parado=true; cancelAnimationFrame(raf); clearInterval(reserva); try{ fonte?.stop(); }catch{ /* já parou */ }
    sincronizarVideosProj(p,-1,false);
    if(rec&&rec.state!=='inactive'){ await new Promise<void>(r=>{ rec!.onstop=()=>r(); rec!.stop(); }); rec.stream.getTracks().forEach(tk=>tk.stop());
      const type=mime.split(';')[0]; let blob=new Blob(chunks,{type}); if(type==='video/webm'){ try{ blob=await fixWebmDuration(blob,total*1000,{logger:false}); }catch{ /* mantém */ } }
      if(ok) cb.gravar?.({blob,ext:type==='video/mp4'?'mp4':'webm'}); }
    ac.close().catch(()=>{}); resolver(); };
  const passo=()=>{ if(parado) return; const t=t00+ac.currentTime-t0;
    if(t>=total){ desenharProj(ctx,p,total-0.001); cb.onTempo?.(total); ok=true; encerrar(); return; }
    sincronizarVideosProj(p,Math.max(0,t),true); desenharProj(ctx,p,Math.max(0,t)); cb.onTempo?.(t); };
  const loop=()=>{ passo(); if(!parado) raf=requestAnimationFrame(loop); };
  const reserva=setInterval(()=>{ if(document.hidden) passo(); },250);
  (async()=>{ await ac.resume(); desenharProj(ctx,p,t00); rec?.start(1000); t0=ac.currentTime+0.05; fonte?.start(t0,t00); loop(); })();
  return {parar:()=>{ encerrar(); },fim};
}
export function gravarProj(p:Proj,audio:AudioBuffer|null,onTempo:(t:number)=>void){
  return new Promise<{blob:Blob;ext:string}>((res,rej)=>{ const [w,h]=TAMANHO[p.formato]; const cv=document.createElement('canvas'); cv.width=w; cv.height=h; let pronto=false;
    try{ const se=tocarProj(cv,p,audio,{onTempo,gravar:x=>{ pronto=true; res(x); }}); se.fim.then(()=>{ if(!pronto) rej(new Error('A gravação foi interrompida.')); }); }catch(e){ rej(e); } });
}
