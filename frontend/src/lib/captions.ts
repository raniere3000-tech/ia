// Leitura de legendas SRT/VTT e desenho dos 10 estilos de legenda em canvas.
export type Cue = {start:number;end:number;text:string};
export type Preset = {id:string;nome:string;tipo:string;fontWeight:string;textColor:string;highlightColor:string;outlineColor:string;outlineWidth:number;position:string;maxLines:number;animation:string;animationDurationSeconds:number;safeAreaBottomPercent:number};

function stamp(s:string){
  const p = s.trim().split(/\s+/)[0].replace(',','.').split(':').map(Number);
  if(p.some(isNaN)) return NaN;
  return p.length===3 ? p[0]*3600+p[1]*60+p[2] : p.length===2 ? p[0]*60+p[1] : p[0];
}

export function parseLegendas(text:string):Cue[]{
  const out:Cue[] = [];
  for(const block of text.replace(/\r/g,'').replace(/^﻿/,'').split(/\n\s*\n/)){
    const lines = block.split('\n');
    const i = lines.findIndex(l=>l.includes('-->'));
    if(i<0) continue;
    const [a,b] = lines[i].split('-->').map(stamp);
    const t = lines.slice(i+1).join(' ').replace(/<[^>]+>/g,'').replace(/\{[^}]+\}/g,'').trim();
    if(t && isFinite(a) && isFinite(b) && b>a) out.push({start:a,end:b,text:t});
  }
  return out.sort((x,y)=>x.start-y.start);
}

const WEIGHTS:Record<string,string> = {regular:'400',normal:'400',semibold:'600',bold:'700',black:'900'};
const UPPER = new Set(['gta-impacto','impacto-vermelho','neon-gamer','frase-chave','karaoke-amarelo']);
const NO_HIGHLIGHT = new Set(['minimal-branco','classico-contorno','legenda-caixa']);
export const FONT_STACK = '"DM Sans", "DejaVu Sans", Arial, sans-serif';

function wrap(ctx:CanvasRenderingContext2D,words:string[],max:number){
  const lines:string[][] = []; let cur:string[] = [];
  for(const w of words){
    const test = [...cur,w].join(' ');
    if(cur.length && ctx.measureText(test).width > max){ lines.push(cur); cur=[w]; } else cur.push(w);
  }
  if(cur.length) lines.push(cur);
  return lines;
}

function roundRect(ctx:CanvasRenderingContext2D,x:number,y:number,w:number,h:number,r:number){
  ctx.beginPath(); ctx.moveTo(x+r,y); ctx.arcTo(x+w,y,x+w,y+h,r); ctx.arcTo(x+w,y+h,x,y+h,r); ctx.arcTo(x,y+h,x,y,r); ctx.arcTo(x,y,x+w,y,r); ctx.closePath();
}

/** Desenha a legenda ativa. t = segundos desde o início da fala, dur = duração da fala. */
export function drawCaption(ctx:CanvasRenderingContext2D,p:Preset,text:string,t:number,dur:number,W:number,H:number){
  const words = (UPPER.has(p.id)?text.toUpperCase():text).split(/\s+/).filter(Boolean);
  if(!words.length) return;
  const size = p.id==='frase-chave' ? 88 : 72;
  ctx.save();
  ctx.font = `${WEIGHTS[p.fontWeight]||'700'} ${size}px ${FONT_STACK}`;
  ctx.textBaseline = 'middle'; ctx.lineJoin = 'round';
  const all = wrap(ctx,words,W*0.82);
  const per = Math.max(1,p.maxLines||2);
  const pages = Math.ceil(all.length/per);
  const frac = Math.min(0.999,Math.max(0,t/Math.max(0.01,dur)));
  const page = Math.floor(frac*pages);
  const lines = all.slice(page*per,page*per+per);
  const before = all.slice(0,page*per).reduce((n,l)=>n+l.length,0);
  const active = Math.floor(frac*words.length);
  const lh = size*1.18; const total = lines.length*lh;
  const ad = Math.max(0.08,p.animationDurationSeconds||0.15);
  const k = Math.min(1,t/ad);
  let cy = p.position==='center' ? H/2 - total/2 + lh/2 : H*(1-(p.safeAreaBottomPercent||17)/100) - total + lh/2;
  let scale = 1, alpha = 1, dx = 0;
  switch(p.animation){
    case 'fade': alpha = k; break;
    case 'pop': scale = k<1 ? 0.75+0.35*Math.sin(k*Math.PI/2)*(1+0.15*(1-k)) : 1; break;
    case 'zoom': scale = 1.35-0.35*k; break;
    case 'slide-up': cy += (1-k)*70; alpha = k; break;
    case 'shake': if(t<ad*3) dx = (Math.random()-0.5)*16; break;
  }
  ctx.globalAlpha = alpha;
  ctx.translate(W/2+dx,cy+total/2-lh/2); ctx.scale(scale,scale); ctx.translate(-W/2,-(cy+total/2-lh/2));
  if(p.id==='legenda-caixa'){
    const wmax = Math.max(...lines.map(l=>ctx.measureText(l.join(' ')).width));
    ctx.fillStyle = 'rgba(0,0,0,.72)'; roundRect(ctx,W/2-wmax/2-36,cy-lh/2-18,wmax+72,total+36,22); ctx.fill();
  }
  if(p.animation==='glow'){ ctx.shadowColor = p.highlightColor; ctx.shadowBlur = 28; }
  let idx = before;
  lines.forEach((line,li)=>{
    const y = cy + li*lh;
    const space = ctx.measureText(' ').width;
    const widths = line.map(w=>ctx.measureText(w).width);
    let x = W/2 - (widths.reduce((a,b)=>a+b,0)+space*(line.length-1))/2;
    line.forEach((w,wi)=>{
      let color = p.textColor;
      if(p.animation==='karaoke'){ if(idx<=active) color = p.highlightColor; }
      else if(!NO_HIGHLIGHT.has(p.id) && idx===active) color = p.highlightColor;
      if(p.id!=='legenda-caixa'){ ctx.lineWidth = (p.outlineWidth||3)*3.2; ctx.strokeStyle = p.outlineColor; ctx.textAlign='left'; ctx.strokeText(w,x,y); }
      ctx.fillStyle = color; ctx.textAlign='left'; ctx.fillText(w,x,y);
      x += widths[wi]+space; idx++;
    });
  });
  ctx.restore();
}

/** Texto de gancho fixo no topo do vídeo. */
export function drawHook(ctx:CanvasRenderingContext2D,text:string,accent:string,W:number,descer=0,extra=0){
  if(!text.trim()) return;
  ctx.save();
  ctx.font = `800 64px ${FONT_STACK}`; ctx.textBaseline='middle'; ctx.textAlign='center';
  const lines = wrap(ctx,text.trim().toUpperCase().split(/\s+/),W*0.8).slice(0,3).map(l=>l.join(' '));
  const lh = 78; const top = 190+extra+(descer>110?descer-110:0);   // com tarja em cima, o gancho fica logo abaixo dela
  const wmax = Math.max(...lines.map(l=>ctx.measureText(l).width));
  ctx.fillStyle = 'rgba(255,255,255,.96)'; roundRect(ctx,W/2-wmax/2-34,top-lh/2-16,wmax+68,lines.length*lh+32,20); ctx.fill();
  ctx.fillStyle = accent==='#FFFFFF' ? '#111' : '#111';
  lines.forEach((l,i)=>ctx.fillText(l,W/2,top+i*lh));
  ctx.fillStyle = accent; ctx.fillRect(W/2-wmax/2-34,top-lh/2-16,10,lines.length*lh+32);
  ctx.restore();
}
