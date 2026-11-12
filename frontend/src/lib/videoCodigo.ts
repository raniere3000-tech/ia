// "Vídeo com código": a IA escreve um roteiro curto e o navegador desenha um vídeo vertical
// animado (textos que pulam, emojis, fundo em movimento, barra de progresso), com narração
// opcional pela voz do Gemini e uma batida de fundo criada por código. Grava com MediaRecorder.
import fixWebmDuration from 'fix-webm-duration';
import { FONT_STACK } from './captions';
import { formatoSuportado, drawTemplate, type Template } from './render';
import { chamar, ErroGemini, GEMINI_MODEL } from './gemini';
import { falar } from './dublagem';

export const W = 1080, H = 1920, FPS = 30, RATE = 44100;

export type Anim = 'zoom-in'|'zoom-out'|'pan-esq'|'pan-dir'|'sobe'|'tremer'|'parado';
export const ANIMS:[Anim,string][] = [['zoom-in','Aproximar devagar'],['zoom-out','Afastar devagar'],['pan-esq','Deslizar para a esquerda'],['pan-dir','Deslizar para a direita'],['sobe','Subir'],['tremer','Tremor (ação/susto)'],['parado','Parado']];
export type Cena = {id:string; texto:string; destaque:string; emoji:string; numero:string; contagem:boolean; midia?:string; anim?:Anim; personagem?:string; pedidoIA?:string};
export const MAX_SEG = 120;   // vídeo final e cada vídeo enviado: no máximo 2 minutos
export type Roteiro = {titulo:string; selo:string; formato:Formato; tema:TemaId; cenas:Cena[]; legenda:string; hashtags:string[]};
export type Formato = 'curiosidade'|'top'|'quiz'|'motivacional'|'historia'|'livre';
export type TemaId = 'neon'|'fogo'|'oceano'|'dinheiro'|'claro';

export const FORMATOS:{id:Formato;nome:string;selo:string;dica:string}[] = [
  {id:'curiosidade',nome:'Você sabia?',selo:'VOCÊ SABIA?',dica:'Fatos curiosos e surpreendentes, um por cena.'},
  {id:'top',nome:'Top 5',selo:'TOP 5',dica:'Lista numerada contando do último para o primeiro.'},
  {id:'quiz',nome:'Quiz',selo:'QUIZ',dica:'Pergunta com contagem regressiva e depois a resposta.'},
  {id:'motivacional',nome:'Motivacional',selo:'',dica:'Frases fortes, ritmo mais calmo.'},
  {id:'historia',nome:'História real',selo:'HISTÓRIA REAL',dica:'Uma história curta com suspense até o final.'},
  {id:'livre',nome:'Livre',selo:'',dica:'A IA escolhe o melhor jeito para o seu tema.'},
];

export type Tema = {id:TemaId;nome:string;bg:[string,string];texto:string;acento:string;acento2:string;sombra:string};
export const TEMAS:Tema[] = [
  {id:'neon',nome:'Neon',bg:['#0b0820','#2a0b4a'],texto:'#ffffff',acento:'#ff3df2',acento2:'#22e1ff',sombra:'rgba(0,0,0,.55)'},
  {id:'fogo',nome:'Fogo',bg:['#1a0500','#4a1200'],texto:'#ffffff',acento:'#ffb300',acento2:'#ff4d00',sombra:'rgba(0,0,0,.55)'},
  {id:'oceano',nome:'Oceano',bg:['#00141f','#004466'],texto:'#ffffff',acento:'#00f5d4',acento2:'#4cc9f0',sombra:'rgba(0,0,0,.5)'},
  {id:'dinheiro',nome:'Dinheiro',bg:['#021a0b','#0a4a24'],texto:'#ffffff',acento:'#39ff88',acento2:'#e7ff3a',sombra:'rgba(0,0,0,.5)'},
  {id:'claro',nome:'Claro',bg:['#fff6e8','#ffd9c2'],texto:'#17151f',acento:'#ff2d6f',acento2:'#7c3aed',sombra:'rgba(255,255,255,0)'},
];
export const temaDe = (id:TemaId)=>TEMAS.find(t=>t.id===id)||TEMAS[0];

export const novoId = ()=>Math.random().toString(36).slice(2,9);
export const cenaVazia = (p:Partial<Cena>={}):Cena => ({id:novoId(),texto:'',destaque:'',emoji:'',numero:'',contagem:false,...p});

export const EXEMPLO:Roteiro = {
  titulo:'5 fatos sobre o polvo que parecem mentira', selo:'VOCÊ SABIA?', formato:'curiosidade', tema:'neon',
  legenda:'O polvo é praticamente um alienígena 🐙 Qual desses você não sabia?', hashtags:['#curiosidades','#vocesabia','#polvo','#natureza','#shorts'],
  cenas:[
    cenaVazia({texto:'O polvo tem TRÊS corações e sangue azul',destaque:'TRÊS corações',emoji:'🐙'}),
    cenaVazia({texto:'Cada braço pensa sozinho: dois terços dos neurônios ficam nos braços',destaque:'pensa sozinho',emoji:'🧠'}),
    cenaVazia({texto:'Ele muda de cor em menos de um segundo, mesmo sendo daltônico',destaque:'daltônico',emoji:'🎨'}),
    cenaVazia({texto:'Já foram vistos abrindo potes de dentro para fora',destaque:'abrindo potes',emoji:'🫙'}),
    cenaVazia({texto:'Segue para mais curiosidades que ninguém te conta!',destaque:'Segue',emoji:'👉'}),
  ],
};

// ---------------------------------------------------------------- roteiro pela IA

export type PedidoRoteiro = {ideia:string; formato:Formato; cenas:number};

function instrucoesRoteiro(p:PedidoRoteiro){
  const f = FORMATOS.find(x=>x.id===p.formato)!;
  return `Você é roteirista de vídeos curtos virais (TikTok, Reels, Shorts) em português do Brasil.
Escreva o roteiro de um vídeo vertical feito só de textos animados e emojis (sem filmagem) sobre: "${p.ideia}".
Formato: ${f.nome}. ${f.dica}
Regras:
- Exatamente ${p.cenas} cenas. Cada cena é uma frase curta (no máximo 16 palavras) que aparece na tela e é narrada.
- A cena 1 é o GANCHO: precisa prender nos primeiros 2 segundos (promessa, choque, pergunta ou número forte). Não comece com "Olá" ou "Neste vídeo".
- A última cena é uma chamada curta para seguir/comentar, ligada ao tema.
- "destaque": 1 a 3 palavras que aparecem exatamente no texto da cena e serão pintadas de cor.
- "emoji": um único emoji que combine com a cena.
- "numero": só no formato Top (ex.: "#5", "#4"... até "#1"); nas outras, deixe vazio.
- "contagem": true só nas cenas de pergunta do Quiz (o público tenta responder antes da contagem acabar); a cena seguinte traz a resposta.
- "selo": rótulo curto em MAIÚSCULAS no topo do vídeo (ex.: "VOCÊ SABIA?", "TOP 5", "QUIZ"). Pode ser vazio.
- Fatos precisam ser verdadeiros. Nada de promessa enganosa.
- "titulo": título chamativo para o post (até 70 caracteres). "legenda": legenda do post com 1 ou 2 frases e uma pergunta para gerar comentários. "hashtags": 4 a 6 hashtags relevantes, com #.`;
}

const S = {type:'STRING'}, B = {type:'BOOLEAN'};
const SCHEMA = {type:'OBJECT',properties:{titulo:S,selo:S,legenda:S,hashtags:{type:'ARRAY',items:S},
  cenas:{type:'ARRAY',items:{type:'OBJECT',properties:{texto:S,destaque:S,emoji:S,numero:S,contagem:B},required:['texto','destaque','emoji','numero','contagem']}}},
  required:['titulo','selo','legenda','hashtags','cenas']};

type Bruto = {titulo:string;selo:string;legenda:string;hashtags:string[];cenas:{texto:string;destaque:string;emoji:string;numero:string;contagem:boolean}[]};

export function montarRoteiro(b:Bruto,p:PedidoRoteiro,tema:TemaId):Roteiro{
  const cenas = (b.cenas||[]).filter(c=>c&&String(c.texto||'').trim()).map(c=>cenaVazia({texto:String(c.texto).trim(),destaque:String(c.destaque||'').trim(),emoji:String(c.emoji||'').trim(),numero:String(c.numero||'').trim(),contagem:!!c.contagem}));
  if(!cenas.length) throw new Error('A IA não devolveu nenhuma cena. Tente de novo.');
  return {titulo:String(b.titulo||p.ideia).trim(),selo:String(b.selo||'').trim().toUpperCase(),formato:p.formato,tema,cenas,legenda:String(b.legenda||'').trim(),
    hashtags:(b.hashtags||[]).map(h=>String(h).trim()).filter(Boolean).map(h=>h.startsWith('#')?h:'#'+h)};
}

export async function roteiroGemini(key:string,p:PedidoRoteiro,tema:TemaId){
  const res:any = await chamar(key,GEMINI_MODEL+':generateContent',{contents:[{role:'user',parts:[{text:instrucoesRoteiro(p)}]}],generationConfig:{responseMimeType:'application/json',responseSchema:SCHEMA,temperature:0.9}});
  const cand = res?.candidates?.[0];
  if(res?.promptFeedback?.blockReason||!cand||cand.finishReason==='SAFETY'||cand.finishReason==='PROHIBITED_CONTENT') throw new ErroGemini(200,'O Gemini recusou escrever sobre este tema.','BLOCKED');
  const t = (cand.content?.parts||[]).filter((x:any)=>!x.thought).map((x:any)=>x.text||'').join('');
  let json:Bruto; try{ json = JSON.parse(t); }catch{ throw new ErroGemini(200,'A resposta do Gemini veio incompleta. Tente novamente.'); }
  return montarRoteiro(json,p,tema);
}

export async function roteiroClaude(key:string,p:PedidoRoteiro,tema:TemaId){
  const {escreverRoteiroClaude} = await import('./ai');
  return montarRoteiro(await escreverRoteiroClaude(key,instrucoesRoteiro(p)),p,tema);
}

// ---------------------------------------------------------------- som (narração + batida)

/** Narração de cada cena, com o texto e a voz usados (se o texto mudar, a voz fica velha). */
export type Narracao = Record<string,{texto:string;voz:string;samples:Float32Array;rate:number}>;
/** A voz de uma cena depende da voz padrão e do personagem que fala. */
export const chaveVoz = (c:Cena,padrao:string)=>c.personagem?.trim()?`${padrao}|${c.personagem.trim().toUpperCase()}`:padrao;
/** Gera a voz de uma cena. `falarCena` permite usar a voz do personagem (Estúdio de vozes). */
export type FalarCena = (c:Cena,onEspera:()=>void)=>Promise<{samples:Float32Array;rate:number}>;

export async function narrar(key:string,r:Roteiro,voz:string,atual:Narracao,onStatus:(s:string,pct:number)=>void,falarCena?:FalarCena,refazer=false):Promise<Narracao>{
  const out:Narracao = {};
  for(let i=0;i<r.cenas.length;i++){
    const c = r.cenas[i]; const n = atual[c.id]; const ch = chaveVoz(c,voz);
    if(!refazer&&n&&n.texto===c.texto&&n.voz===ch){ out[c.id]=n; continue; }
    if(!c.texto.trim()) continue;
    onStatus(`Gravando a voz (${i+1} de ${r.cenas.length})`,Math.round(i/r.cenas.length*100));
    const espera = ()=>onStatus('O Gemini pediu uma pausa (limite de pedidos por minuto do plano grátis). Continuo sozinho em instantes',Math.round(i/r.cenas.length*100));
    const v = falarCena ? await falarCena(c,espera) : await falar(key,c.texto,voz,espera);
    out[c.id] = {texto:c.texto,voz:ch,samples:v.samples,rate:v.rate};
  }
  onStatus('Voz pronta',100);
  return out;
}
export const vozValida = (n:Narracao|null,c:Cena,voz:string)=>!!(n&&n[c.id]&&n[c.id].texto===c.texto&&n[c.id].voz===chaveVoz(c,voz));

// ---------------------------------------------------------------- imagens e vídeos das cenas

export type Midia = {id:string;nome:string;tipo:'imagem'|'video';blob:Blob;duracao:number};
/** Imagens/vídeos carregados nesta aba, prontos para desenhar. */
export const midias = new Map<string,{tipo:'imagem'|'video';el:HTMLImageElement|HTMLVideoElement;duracao:number;nome:string}>();
let dbm:Promise<IDBDatabase>|null = null;
function dbMidias(){
  if(!dbm) dbm = new Promise((res,rej)=>{ const r=indexedDB.open('video_codigo',1); r.onupgradeneeded=()=>{ r.result.createObjectStore('midias',{keyPath:'id'}); }; r.onsuccess=()=>res(r.result); r.onerror=()=>rej(new Error('O navegador não deixou guardar as imagens (modo anônimo?).')); });
  return dbm;
}
async function lojaMidia<T>(modo:IDBTransactionMode,f:(s:IDBObjectStore)=>IDBRequest|void):Promise<T>{
  const d=await dbMidias(); return new Promise((res,rej)=>{ const t=d.transaction('midias',modo); const q=f(t.objectStore('midias')); t.oncomplete=()=>res((q as IDBRequest)?.result); t.onerror=()=>rej(t.error); });
}
function abrirEl(m:Midia){
  return new Promise<{tipo:'imagem'|'video';el:HTMLImageElement|HTMLVideoElement;duracao:number;nome:string}>((res,rej)=>{
    const url = URL.createObjectURL(m.blob);
    if(m.tipo==='imagem'){ const i=new Image(); i.onload=()=>res({tipo:'imagem',el:i,duracao:0,nome:m.nome}); i.onerror=()=>rej(new Error('Não consegui abrir a imagem '+m.nome)); i.src=url; return; }
    const v=document.createElement('video'); v.muted=true; v.playsInline=true; v.loop=true; v.preload='auto'; v.src=url;
    v.onloadeddata=()=>res({tipo:'video',el:v,duracao:v.duration||m.duracao,nome:m.nome}); v.onerror=()=>rej(new Error('Não consegui abrir o vídeo '+m.nome));
  });
}
/** Guarda uma imagem ou vídeo enviado (vídeo de até 2 minutos) e já deixa pronto para desenhar. */
export async function adicionarMidia(f:File):Promise<string>{
  const tipo = f.type.startsWith('image/')?'imagem':f.type.startsWith('video/')||/\.(mp4|mov|webm|m4v)$/i.test(f.name)?'video':null;
  if(!tipo) throw new Error('Envie uma imagem (JPG, PNG, GIF, WEBP) ou um vídeo (MP4, MOV, WEBM).');
  const blob = new Blob([await f.arrayBuffer()],{type:f.type||(tipo==='video'?'video/mp4':'image/png')});
  const m:Midia = {id:novoId(),nome:f.name,tipo,blob,duracao:0};
  const pronto = await abrirEl(m);
  if(tipo==='video'&&pronto.duracao>MAX_SEG+0.5){ URL.revokeObjectURL(pronto.el.src); throw new Error(`O vídeo tem ${Math.round(pronto.duracao)} s. O máximo é 2 minutos.`); }
  m.duracao = pronto.duracao;
  await lojaMidia('readwrite',s=>{ s.put(m); });
  midias.set(m.id,pronto);
  return m.id;
}
/** Carrega do navegador as mídias usadas no roteiro (depois de recarregar a página). */
export async function carregarMidias(r:Roteiro){
  for(const c of r.cenas){
    if(!c.midia||midias.has(c.midia)) continue;
    try{ const m = await lojaMidia<Midia|undefined>('readonly',s=>s.get(c.midia!)); if(m) midias.set(m.id,await abrirEl(m)); }catch{ /* some do roteiro */ }
  }
}
/** O arquivo original guardado de uma mídia (para enviar à IA). */
export const blobDaMidia = (id:string)=>lojaMidia<Midia|undefined>('readonly',s=>s.get(id)).then(m=>m?.blob||null);
export const apagarMidia = (id:string)=>lojaMidia<void>('readwrite',s=>{ s.delete(id); }).then(()=>{ midias.delete(id); });

/** Deixa os vídeos das cenas no ponto certo: toca o da cena atual e pausa os outros. */
export function sincronizarMidias(r:Roteiro,ts:{ini:number;fim:number}[],t:number,tocando:boolean){
  r.cenas.forEach((c,i)=>{
    const m = c.midia?midias.get(c.midia):null; if(!m||m.tipo!=='video') return;
    const v = m.el as HTMLVideoElement; const s = ts[i]; if(!s) return;
    const atual = t>=s.ini&&t<s.fim;
    if(!atual){ if(!v.paused) v.pause(); return; }
    const alvo = m.duracao>0?(t-s.ini)%m.duracao:0;
    if(tocando){ if(Math.abs(v.currentTime-alvo)>0.35) v.currentTime=alvo; if(v.paused) v.play().catch(()=>{}); }
    else{ if(!v.paused) v.pause(); if(Math.abs(v.currentTime-alvo)>0.05) v.currentTime=alvo; }
  });
}

/** Quanto tempo cada cena fica na tela. */
export function tempos(r:Roteiro,nar:Narracao|null,voz:string){
  let t = 0;
  return r.cenas.map(c=>{
    const palavras = c.texto.split(/\s+/).filter(Boolean).length;
    const fala = vozValida(nar,c,voz) ? nar![c.id].samples.length/nar![c.id].rate : 0;
    const m = c.midia?midias.get(c.midia):null;
    let d = fala ? fala+0.45 : Math.max(2.2,0.95+palavras*0.36);
    if(!fala&&m?.tipo==='video') d = Math.max(d,Math.min(MAX_SEG,m.duracao));
    if(c.contagem) d = Math.max(d,fala+3.2,4.2);
    const ini = t; t += d;
    return {ini,fim:t,fala};
  });
}

function reamostrar(s:Float32Array,de:number,para:number){
  if(de===para) return s;
  const f = de/para, n = Math.floor(s.length/f), out = new Float32Array(n);
  for(let i=0;i<n;i++){ const x=i*f, a=Math.floor(x), k=x-a; out[i]=(s[a]||0)*(1-k)+(s[a+1]||0)*k; }
  return out;
}

/** Batida simples (bumbo, chimbal e grave) criada por código, em loop, ~105 BPM. */
async function batida(dur:number){
  const n = Math.ceil(dur*RATE);
  const ac = new OfflineAudioContext(1,n,RATE);
  const bpm = 105, beat = 60/bpm;
  const ruido = ac.createBuffer(1,RATE*0.1,RATE); const d = ruido.getChannelData(0); for(let i=0;i<d.length;i++) d[i]=Math.random()*2-1;
  const notas = [55,55,65.41,49];
  for(let k=0,t=0;t<dur;k++,t=k*beat){
    // bumbo
    const o = ac.createOscillator(), g = ac.createGain();
    o.frequency.setValueAtTime(140,t); o.frequency.exponentialRampToValueAtTime(42,t+0.16);
    g.gain.setValueAtTime(0.9,t); g.gain.exponentialRampToValueAtTime(0.001,t+0.32);
    o.connect(g).connect(ac.destination); o.start(t); o.stop(t+0.34);
    // chimbal no contratempo
    const h = ac.createBufferSource(); h.buffer = ruido; const hf = ac.createBiquadFilter(); hf.type='highpass'; hf.frequency.value=7000;
    const hg = ac.createGain(); hg.gain.setValueAtTime(0.22,t+beat/2); hg.gain.exponentialRampToValueAtTime(0.001,t+beat/2+0.06);
    h.connect(hf).connect(hg).connect(ac.destination); h.start(t+beat/2); h.stop(t+beat/2+0.08);
    // grave a cada compasso
    if(k%4===0){
      const b = ac.createOscillator(), bg = ac.createGain(); b.type='triangle'; b.frequency.value = notas[(k/4)%notas.length];
      bg.gain.setValueAtTime(0.0001,t); bg.gain.exponentialRampToValueAtTime(0.35,t+0.05); bg.gain.exponentialRampToValueAtTime(0.0001,t+beat*3.8);
      b.connect(bg).connect(ac.destination); b.start(t); b.stop(t+beat*4);
    }
  }
  const buf = await ac.startRendering();
  return buf.getChannelData(0);
}

/** Junta a narração (no começo de cada cena) com a batida. Devolve null se não houver som. */
export async function mixar(r:Roteiro,nar:Narracao|null,voz:string,comBatida:boolean):Promise<Float32Array|null>{
  const ts = tempos(r,nar,voz); const dur = ts.length?ts[ts.length-1].fim:0;
  const temVoz = r.cenas.some(c=>vozValida(nar,c,voz));
  if(!temVoz&&!comBatida) return null;
  const out = new Float32Array(Math.ceil(dur*RATE));
  if(comBatida){
    const b = await batida(dur); const vol = temVoz?0.16:0.4;
    for(let i=0;i<out.length;i++){ const fade = Math.min(1,(dur-i/RATE)/1.2); out[i]+=b[i]*vol*Math.max(0,fade); }
  }
  r.cenas.forEach((c,i)=>{
    if(!vozValida(nar,c,voz)) return;
    const s = reamostrar(nar![c.id].samples,nar![c.id].rate,RATE); const o = Math.round((ts[i].ini+0.12)*RATE);
    for(let k=0;k<s.length&&o+k<out.length;k++) out[o+k]+=s[k];
  });
  for(let i=0;i<out.length;i++) out[i]=Math.max(-1,Math.min(1,out[i]));
  return out;
}

// ---------------------------------------------------------------- desenho

const easeOutBack = (x:number)=>{ const c1=1.70158, c3=c1+1; return 1+c3*Math.pow(x-1,3)+c1*Math.pow(x-1,2); };
const clamp01 = (x:number)=>Math.max(0,Math.min(1,x));
const norm = (s:string)=>s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^a-z0-9]/g,'');

type Palavra = {txt:string;destaque:boolean};
function palavras(c:Cena):Palavra[]{
  const ws = c.texto.split(/\s+/).filter(Boolean);
  const alvo = c.destaque.split(/\s+/).map(norm).filter(Boolean);
  const marca = new Array(ws.length).fill(false);
  if(alvo.length){
    for(let i=0;i+alvo.length<=ws.length;i++){
      if(alvo.every((a,k)=>norm(ws[i+k])===a)){ for(let k=0;k<alvo.length;k++) marca[i+k]=true; break; }
    }
    if(!marca.some(Boolean)) ws.forEach((w,i)=>{ if(alvo.includes(norm(w))) marca[i]=true; });
  }
  return ws.map((txt,i)=>({txt,destaque:marca[i]}));
}

function quebrar(ctx:CanvasRenderingContext2D,ps:Palavra[],max:number){
  const linhas:Palavra[][] = [[]]; let w = 0; const esp = ctx.measureText(' ').width;
  for(const p of ps){
    const pw = ctx.measureText(p.txt).width;
    if(linhas[linhas.length-1].length && w+esp+pw>max){ linhas.push([]); w=0; }
    const l = linhas[linhas.length-1]; w += (l.length?esp:0)+pw; l.push(p);
  }
  return linhas;
}

function fundo(ctx:CanvasRenderingContext2D,tm:Tema,t:number){
  const g = ctx.createLinearGradient(0,0,W*0.3,H); g.addColorStop(0,tm.bg[0]); g.addColorStop(1,tm.bg[1]);
  ctx.fillStyle = g; ctx.fillRect(0,0,W,H);
  // Manchas de luz que flutuam devagar.
  const bolas:[number,number,number,string][] = [[0.2,0.25,0.55,tm.acento],[0.85,0.6,0.5,tm.acento2],[0.4,0.9,0.45,tm.acento]];
  ctx.save(); ctx.globalCompositeOperation = tm.id==='claro'?'multiply':'screen';
  bolas.forEach(([x,y,r,cor],i)=>{
    const cx = W*(x+0.12*Math.sin(t*0.35+i*2.1)), cy = H*(y+0.06*Math.cos(t*0.28+i*1.3)), rr = W*r;
    const rg = ctx.createRadialGradient(cx,cy,0,cx,cy,rr); rg.addColorStop(0,cor+(tm.id==='claro'?'55':'66')); rg.addColorStop(1,cor+'00');
    ctx.fillStyle = rg; ctx.fillRect(0,0,W,H);
  });
  ctx.restore();
  // Partículas subindo.
  ctx.save(); ctx.fillStyle = tm.id==='claro'?'rgba(0,0,0,.08)':'rgba(255,255,255,.18)';
  for(let i=0;i<28;i++){
    const sx = ((i*137.5)%100)/100, vel = 40+((i*53)%60), y = H-((t*vel+i*311)%(H+80))+40;
    ctx.beginPath(); ctx.arc(W*sx+Math.sin(t+i)*14,y,3+(i%4),0,Math.PI*2); ctx.fill();
  }
  ctx.restore();
}

function caixaArredondada(ctx:CanvasRenderingContext2D,x:number,y:number,w:number,h:number,r:number){
  ctx.beginPath(); ctx.moveTo(x+r,y); ctx.arcTo(x+w,y,x+w,y+h,r); ctx.arcTo(x+w,y+h,x,y+h,r); ctx.arcTo(x,y+h,x,y,r); ctx.arcTo(x,y,x+w,y,r); ctx.closePath();
}

/** Imagem ou vídeo da cena, preenchendo a tela, com o movimento escolhido. */
function desenharMidia(ctx:CanvasRenderingContext2D,el:HTMLImageElement|HTMLVideoElement,anim:Anim,lt:number,dur:number){
  const iw = (el as HTMLVideoElement).videoWidth||(el as HTMLImageElement).naturalWidth, ih = (el as HTMLVideoElement).videoHeight||(el as HTMLImageElement).naturalHeight;
  if(!iw||!ih) return;
  const p = clamp01(lt/Math.max(0.1,dur));
  let s = 1, tx = 0, ty = 0;
  if(anim==='zoom-in') s = 1+0.16*p;
  else if(anim==='zoom-out') s = 1.16-0.16*p;
  else if(anim==='pan-esq'){ s = 1.18; tx = W*0.07*(1-2*p); }
  else if(anim==='pan-dir'){ s = 1.18; tx = -W*0.07*(1-2*p); }
  else if(anim==='sobe'){ s = 1.14; ty = H*0.05*(1-2*p); }
  else if(anim==='tremer'){ s = 1.1; const k = Math.max(0.25,1-lt/1.2); tx = Math.sin(lt*47)*16*k; ty = Math.cos(lt*39)*12*k; }
  const base = Math.max(W/iw,H/ih)*s; const dw = iw*base, dh = ih*base;
  ctx.save(); ctx.globalAlpha = clamp01(lt/0.25)||0.001;
  ctx.drawImage(el,(W-dw)/2+tx,(H-dh)/2+ty,dw,dh);
  ctx.restore();
}

/** Desenha o quadro do tempo `t` (segundos desde o começo do vídeo). */
export function desenhar(ctx:CanvasRenderingContext2D,r:Roteiro,ts:{ini:number;fim:number;fala:number}[],t:number,template?:Template|null,logo?:HTMLImageElement|null){
  const tm = temaDe(r.tema);
  ctx.save(); ctx.textAlign='center'; ctx.textBaseline='middle';
  fundo(ctx,tm,t);
  const total = ts.length?ts[ts.length-1].fim:1;
  let i = ts.findIndex(x=>t>=x.ini&&t<x.fim); if(i<0) i = t<=0?0:ts.length-1;
  const c = r.cenas[i]; const s = ts[i];
  if(!c||!s){ ctx.restore(); return; }
  const lt = t-s.ini, dur = s.fim-s.ini;
  const m = c.midia?midias.get(c.midia):null;
  if(m){
    desenharMidia(ctx,m.el,c.anim||'zoom-in',lt,dur);
    // Escurece embaixo para a legenda ler bem.
    const g = ctx.createLinearGradient(0,H*0.5,0,H); g.addColorStop(0,'rgba(0,0,0,0)'); g.addColorStop(1,'rgba(0,0,0,.78)');
    ctx.fillStyle = g; ctx.fillRect(0,H*0.5,W,H*0.5);
  }

  // Barrinhas de progresso no topo (estilo stories).
  const n = ts.length, gap = 12, bx = 60, bw = (W-bx*2-gap*(n-1))/n;
  ts.forEach((x,k)=>{
    const p = clamp01((t-x.ini)/(x.fim-x.ini));
    ctx.fillStyle = tm.id==='claro'?'rgba(0,0,0,.15)':'rgba(255,255,255,.25)'; caixaArredondada(ctx,bx+k*(bw+gap),70,bw,10,5); ctx.fill();
    if(p>0){ ctx.fillStyle = tm.acento; caixaArredondada(ctx,bx+k*(bw+gap),70,Math.max(10,bw*p),10,5); ctx.fill(); }
  });

  // Selo do topo.
  if(r.selo.trim()){
    ctx.font = `900 54px ${FONT_STACK}`; const sw = ctx.measureText(r.selo).width+70;
    const pulso = 1+0.03*Math.sin(t*4);
    ctx.save(); ctx.translate(W/2,190); ctx.scale(pulso,pulso); ctx.rotate(-0.025);
    ctx.fillStyle = tm.acento; caixaArredondada(ctx,-sw/2,-50,sw,100,22); ctx.fill();
    ctx.fillStyle = tm.id==='claro'?'#fff':'#0b0b12'; ctx.fillText(r.selo,0,4);
    ctx.restore();
  }

  // Entrada da cena: sobe e aparece; saída: some rápido.
  const entra = easeOutBack(clamp01(lt/0.45)), sai = clamp01((dur-lt)/0.18);
  ctx.globalAlpha = Math.min(clamp01(lt/0.2),sai);
  const dy = (1-entra)*120;

  // Número grande (Top).
  let yEmoji = H*0.33;
  if(!m&&c.numero.trim()){
    ctx.save(); ctx.font = `900 230px ${FONT_STACK}`; ctx.translate(W/2,H*0.25+dy); const k = 0.6+0.4*entra; ctx.scale(k,k);
    ctx.lineWidth = 14; ctx.strokeStyle = tm.id==='claro'?'#fff':'#000'; ctx.strokeText(c.numero,0,0);
    ctx.fillStyle = tm.acento2; ctx.fillText(c.numero,0,0); ctx.restore();
    yEmoji = H*0.40;
  }
  // Emoji pulando.
  if(!m&&c.emoji.trim()){
    const pop = easeOutBack(clamp01((lt-0.05)/0.5)); const flut = Math.sin(t*2.6)*14;
    ctx.save(); ctx.translate(W/2,yEmoji+flut+dy); ctx.rotate(Math.sin(t*1.8)*0.08); ctx.scale(pop,pop);
    ctx.font = `${c.numero.trim()?190:250}px "Noto Color Emoji","Apple Color Emoji","Segoe UI Emoji",sans-serif`;
    ctx.fillText(c.emoji,0,0); ctx.restore();
  }

  // Texto: palavra por palavra (no ritmo da fala, se houver).
  const ps = palavras(c);
  let fs = m?70:92; ctx.font = `900 ${fs}px ${FONT_STACK}`;
  let linhas = quebrar(ctx,ps,W*0.84);
  while(linhas.length>(m?4:5)&&fs>(m?46:56)){ fs-=6; ctx.font=`900 ${fs}px ${FONT_STACK}`; linhas=quebrar(ctx,ps,W*0.84); }
  const lh = fs*1.22, yTexto = m ? H*0.82-(linhas.length-1)*lh+dy : (c.numero.trim()||c.emoji.trim()?H*0.6:H*0.48)-(linhas.length-1)*lh/2+dy;
  // Nome de quem fala, acima do texto.
  const quem = c.personagem?.trim();
  if(quem){
    ctx.save(); ctx.font = `900 ${Math.round(fs*0.6)}px ${FONT_STACK}`; const nw = ctx.measureText(quem.toUpperCase()).width+44; const ny = yTexto-lh*0.95;
    ctx.fillStyle = tm.acento2; caixaArredondada(ctx,W/2-nw/2,ny-fs*0.42,nw,fs*0.84,14); ctx.fill();
    ctx.fillStyle = tm.id==='claro'?'#fff':'#0b0b12'; ctx.fillText(quem.toUpperCase(),W/2,ny+3); ctx.restore();
  }
  const janela = s.fala ? s.fala*0.92 : Math.min(dur*0.55,ps.length*0.2);
  const passo = ps.length?janela/ps.length:0;
  const esp = ctx.measureText(' ').width;
  let idx = 0;
  linhas.forEach((l,li)=>{
    const lw = l.reduce((a,p)=>a+ctx.measureText(p.txt).width,0)+esp*(l.length-1);
    let x = W/2-lw/2; const y = yTexto+li*lh;
    for(const p of l){
      const pw = ctx.measureText(p.txt).width; const t0 = 0.15+idx*passo; const k = clamp01((lt-t0)/0.22);
      if(k>0){
        const esc = 0.55+0.45*easeOutBack(k);
        ctx.save(); ctx.translate(x+pw/2,y); ctx.scale(esc,esc); ctx.globalAlpha *= k;
        if(p.destaque){
          ctx.fillStyle = tm.acento; caixaArredondada(ctx,-pw/2-14,-fs*0.62,pw+28,fs*1.2,16); ctx.fill();
          ctx.fillStyle = tm.id==='claro'?'#fff':'#0b0b12'; ctx.fillText(p.txt,0,4);
        }else{
          ctx.lineWidth = fs*0.16; ctx.lineJoin='round'; ctx.strokeStyle = tm.sombra; if(tm.id!=='claro') ctx.strokeText(p.txt,0,4);
          ctx.fillStyle = tm.texto; ctx.fillText(p.txt,0,4);
        }
        ctx.restore();
      }
      x += pw+esp; idx++;
    }
  });

  // Contagem regressiva (Quiz).
  if(c.contagem){
    const ini = Math.max(s.fala+0.2,0.8), fim = dur-0.25, p = clamp01((lt-ini)/(fim-ini));
    if(lt>=ini){
      const rest = Math.max(1,Math.ceil(3*(1-p))); const cy = H*0.82;
      ctx.lineWidth = 18; ctx.strokeStyle = tm.id==='claro'?'rgba(0,0,0,.12)':'rgba(255,255,255,.2)';
      ctx.beginPath(); ctx.arc(W/2,cy,95,0,Math.PI*2); ctx.stroke();
      ctx.strokeStyle = tm.acento2; ctx.lineCap='round'; ctx.beginPath(); ctx.arc(W/2,cy,95,-Math.PI/2,-Math.PI/2+Math.PI*2*(1-p)); ctx.stroke();
      ctx.font = `900 110px ${FONT_STACK}`; ctx.fillStyle = tm.texto; ctx.fillText(String(rest),W/2,cy+6);
    }
  }
  ctx.globalAlpha = 1;
  // Flash rápido na virada de cena (menos na primeira).
  if(i>0&&lt<0.12){ ctx.fillStyle = `rgba(255,255,255,${0.35*(1-lt/0.12)})`; ctx.fillRect(0,0,W,H); }
  // Barra fina de tempo total no rodapé.
  ctx.fillStyle = tm.acento2; ctx.fillRect(0,H-8,W*clamp01(t/total),8);
  ctx.restore();
  if(template?.ativo) drawTemplate(ctx,template,logo||null,W,H);
}

// ---------------------------------------------------------------- tocar e gravar

export type Sessao = {parar:()=>void; fim:Promise<void>};

/** Toca o vídeo num canvas (com som). Se `gravar` for passado, grava e devolve o arquivo. */
export function tocar(canvas:HTMLCanvasElement,r:Roteiro,ts:{ini:number;fim:number;fala:number}[],audio:Float32Array|null,o:{template?:Template|null;logo?:HTMLImageElement|null;onTempo?:(t:number)=>void;gravar?:(res:{blob:Blob;ext:string})=>void;onPct?:(p:number)=>void}={}):Sessao{
  const ctx = canvas.getContext('2d')!;
  const total = ts.length?ts[ts.length-1].fim:0;
  const ac = new AudioContext();
  let parado = false; let raf = 0; let fonte:AudioBufferSourceNode|null = null;
  let rec:MediaRecorder|null = null; const chunks:Blob[] = []; let mime = '';
  let resolver:()=>void = ()=>{};
  const fim = new Promise<void>(res=>{ resolver = res; });
  const destino = o.gravar ? ac.createMediaStreamDestination() : null;
  if(audio){
    const buf = ac.createBuffer(1,audio.length,RATE); buf.copyToChannel(audio as Float32Array<ArrayBuffer>,0);
    fonte = ac.createBufferSource(); fonte.buffer = buf; fonte.connect(destino||ac.destination);
  }
  if(o.gravar){
    mime = formatoSuportado()||'';
    if(!mime){ ac.close(); throw new Error('Este navegador não grava vídeo. Use Chrome, Edge ou Safari atualizados.'); }
    const stream = canvas.captureStream(FPS);
    if(audio) destino!.stream.getAudioTracks().forEach(t=>stream.addTrack(t));
    rec = new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:8_000_000,audioBitsPerSecond:160_000});
    rec.ondataavailable = e=>{ if(e.data.size) chunks.push(e.data); };
  }
  const encerrar = async()=>{
    if(parado) return; parado = true; cancelAnimationFrame(raf); clearInterval(reserva);
    try{ fonte?.stop(); }catch{ /* já parou */ }
    if(rec&&rec.state!=='inactive'){
      await new Promise<void>(res=>{ rec!.onstop=()=>res(); rec!.stop(); });
      rec.stream.getTracks().forEach(t=>t.stop());
      const type = mime.split(';')[0]; let blob = new Blob(chunks,{type});
      if(type==='video/webm'){ try{ blob = await fixWebmDuration(blob,total*1000,{logger:false}); }catch{ /* mantém */ } }
      if(gravouAteOFim) o.gravar?.({blob,ext:type==='video/mp4'?'mp4':'webm'});
    }
    ac.close().catch(()=>{}); resolver();
  };
  let gravouAteOFim = false; let t0 = 0;
  const quadro = ()=>{
    if(parado) return;
    const t = ac.currentTime-t0;
    if(t>=total){ desenhar(ctx,r,ts,total-0.001,o.template,o.logo); gravouAteOFim = true; sincronizarMidias(r,ts,-1,false); encerrar(); return; }
    sincronizarMidias(r,ts,Math.max(0,t),true);
    desenhar(ctx,r,ts,Math.max(0,t),o.template,o.logo); o.onTempo?.(t); o.onPct?.(Math.min(99,Math.round(t/total*100)));
  };
  const loop = ()=>{ quadro(); if(!parado) raf = requestAnimationFrame(loop); };
  // Reserva: se a aba ficar em segundo plano, ainda desenha (mais devagar).
  const reserva = setInterval(()=>{ if(document.hidden) quadro(); },250);
  (async()=>{
    await ac.resume();
    desenhar(ctx,r,ts,0,o.template,o.logo);
    rec?.start(1000);
    t0 = ac.currentTime+0.05; fonte?.start(t0);
    loop();
  })();
  return {parar:()=>{ sincronizarMidias(r,ts,-1,false); encerrar(); },fim};
}

/** Grava o vídeo inteiro e devolve o arquivo. */
export function gravar(r:Roteiro,ts:{ini:number;fim:number;fala:number}[],audio:Float32Array|null,template:Template|null,logo:HTMLImageElement|null,onPct:(p:number)=>void){
  return new Promise<{blob:Blob;ext:string}>((res,rej)=>{
    const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
    let pronto = false;
    try{
      const s = tocar(cv,r,ts,audio,{template,logo,onPct,gravar:x=>{ pronto=true; onPct(100); res(x); }});
      s.fim.then(()=>{ if(!pronto) rej(new Error('A gravação foi interrompida.')); });
    }catch(e){ rej(e); }
  });
}

export function nomeVideo(r:Roteiro,ext:string){
  const slug = r.titulo.normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^a-zA-Z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,40).toLowerCase()||'video';
  return `${slug}-9x16.${ext}`;
}
