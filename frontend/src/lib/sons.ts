// Efeitos sonoros grátis: feitos pelo próprio site (síntese no navegador)
// ou a partir de um arquivo enviado pela pessoa. Tudo sai como mono 24 kHz, igual às vozes, para entrar no arquivo final.
import { wav } from './vozes';

export const RATE = 24000;
export type FonteSom = 'auto'|'site'|'arquivo';

const semAcento=(t:string)=>t.normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase();

// ---------------------------------------------------------------- síntese
type Ctx = OfflineAudioContext;
function ruido(ctx:Ctx,seg:number){
  const b=ctx.createBuffer(1,Math.max(1,Math.round(seg*RATE)),RATE); const d=b.getChannelData(0);
  for(let i=0;i<d.length;i++) d[i]=Math.random()*2-1;
  const s=ctx.createBufferSource(); s.buffer=b; return s;
}
function env(ctx:Ctx,ini:number,ataque:number,dur:number,pico=1){
  const g=ctx.createGain(); g.gain.setValueAtTime(0.0001,ini); g.gain.exponentialRampToValueAtTime(pico,ini+Math.max(0.002,ataque));
  g.gain.exponentialRampToValueAtTime(0.0001,ini+ataque+dur); return g;
}
function filtro(ctx:Ctx,tipo:BiquadFilterType,f:number,q=0.8){ const b=ctx.createBiquadFilter(); b.type=tipo; b.frequency.value=f; b.Q.value=q; return b; }
function batida(ctx:Ctx,out:AudioNode,t:number,{grave=70,corpo=900,forca=1,dur=0.25}={}){
  const o=ctx.createOscillator(); o.frequency.setValueAtTime(grave*2,t); o.frequency.exponentialRampToValueAtTime(grave*0.6,t+dur);
  const g=env(ctx,t,0.003,dur,0.9*forca); o.connect(g).connect(out); o.start(t); o.stop(t+dur+0.05);
  const n=ruido(ctx,dur); const f=filtro(ctx,'lowpass',corpo); const g2=env(ctx,t,0.001,dur*0.5,0.7*forca); n.connect(f).connect(g2).connect(out); n.start(t);
}
function ping(ctx:Ctx,out:AudioNode,t:number,freq:number,dur:number,vol=0.3,tipo:OscillatorType='sine'){
  const o=ctx.createOscillator(); o.type=tipo; o.frequency.value=freq; const g=env(ctx,t,0.002,dur,vol); o.connect(g).connect(out); o.start(t); o.stop(t+dur+0.05);
}
function chiado(ctx:Ctx,out:AudioNode,t:number,dur:number,tipo:BiquadFilterType,f:number,vol=0.5,ataque=0.01){
  const n=ruido(ctx,dur+0.1); const fl=filtro(ctx,tipo,f); const g=env(ctx,t,ataque,dur,vol); n.connect(fl).connect(g).connect(out); n.start(t); return fl;
}

type Receita = {chaves:RegExp;nome:string;dur:number;fazer:(ctx:Ctx,out:AudioNode,forca:number)=>void};
export const RECEITAS:Receita[] = [
  {chaves:/explos|bomba|estour|detona|kaboom/,nome:'explosão',dur:2.6,fazer:(c,o,k)=>{ const f=chiado(c,o,0,2.4,'lowpass',900,1*k,0.005); f.frequency.exponentialRampToValueAtTime(120,2.4); batida(c,o,0,{grave:45,corpo:300,forca:k,dur:1.2}); }},
  {chaves:/trova|relamp|tempest/,nome:'trovão',dur:3.2,fazer:(c,o,k)=>{ chiado(c,o,0,0.25,'highpass',1500,0.5*k,0.002); for(let i=0;i<6;i++) chiado(c,o,0.1+i*0.35+Math.random()*0.2,1.2,'lowpass',180+Math.random()*120,0.8*k,0.05); }},
  {chaves:/soco|murro|pancad|tapa|chute|golpe|acert|porrada|bofet/,nome:'soco',dur:0.5,fazer:(c,o,k)=>{ batida(c,o,0,{grave:60,corpo:1400,forca:k,dur:0.25}); chiado(c,o,0,0.06,'bandpass',2500,0.4*k,0.001); }},
  {chaves:/porta.*(range|abr)|rang/,nome:'porta rangendo',dur:1.6,fazer:(c,o,k)=>{ const s=c.createOscillator(); s.type='sawtooth'; s.frequency.setValueAtTime(110,0); for(let i=0;i<14;i++) s.frequency.setValueAtTime(90+Math.random()*80,i*0.1); const f=filtro(c,'bandpass',900,6); const g=env(c,0,0.15,1.3,0.35*k); s.connect(f).connect(g).connect(o); s.start(0); s.stop(1.6); }},
  {chaves:/porta|bat(e|eu|endo) a porta|fech/,nome:'porta batendo',dur:0.9,fazer:(c,o,k)=>{ batida(c,o,0,{grave:55,corpo:600,forca:k,dur:0.35}); chiado(c,o,0.02,0.4,'bandpass',300,0.4*k,0.002); }},
  {chaves:/caneca|mesa|madeira|bate(u|ndo)? na|toc|bater/,nome:'batida na madeira',dur:0.5,fazer:(c,o,k)=>{ batida(c,o,0,{grave:180,corpo:1800,forca:0.8*k,dur:0.12}); ping(c,o,0,420,0.15,0.2*k,'triangle'); }},
  {chaves:/passo|anda|corre|pisad/,nome:'passos',dur:2,fazer:(c,o,k)=>{ for(let i=0;i<5;i++){ const t=i*0.38; batida(c,o,t,{grave:90,corpo:700,forca:0.5*k,dur:0.09}); chiado(c,o,t,0.07,'bandpass',1800,0.15*k,0.002); } }},
  {chaves:/vidro|quebr|estilha|garraf|cristal/,nome:'vidro quebrando',dur:1.4,fazer:(c,o,k)=>{ chiado(c,o,0,0.5,'highpass',2500,0.8*k,0.001); for(let i=0;i<14;i++) ping(c,o,0.02+Math.random()*0.6,2200+Math.random()*4000,0.2+Math.random()*0.5,0.12*k); }},
  {chaves:/espada|metal|lamina|lâmina|escudo|armadura|clang|tilint/,nome:'espadas',dur:1.6,fazer:(c,o,k)=>{ for(const [f,v] of [[1180,0.35],[1730,0.25],[2650,0.2],[3420,0.15],[4890,0.1]] as const) ping(c,o,0,f,1.4,v*k); chiado(c,o,0,0.05,'highpass',3000,0.6*k,0.001); }},
  {chaves:/moeda|ouro|dinheiro|tesouro/,nome:'moedas',dur:1.2,fazer:(c,o,k)=>{ for(let i=0;i<7;i++){ const t=i*0.12+Math.random()*0.05; ping(c,o,t,3200+Math.random()*1800,0.25,0.18*k); ping(c,o,t,5200+Math.random()*900,0.15,0.08*k); } }},
  {chaves:/sino|campainh|badal/,nome:'sino',dur:3,fazer:(c,o,k)=>{ for(const [f,v] of [[520,0.4],[1040,0.2],[1340,0.15],[2080,0.08]] as const) ping(c,o,0,f,2.8,v*k); }},
  {chaves:/magia|feitic|brilho|encant|cintil|portal|teleport/,nome:'magia',dur:2,fazer:(c,o,k)=>{ const notas=[880,1109,1319,1760,2217,2637]; notas.forEach((f,i)=>ping(c,o,i*0.09,f,1.2,0.15*k)); const fl=chiado(c,o,0,1.6,'bandpass',2000,0.25*k,0.3); fl.frequency.exponentialRampToValueAtTime(6000,1.6); }},
  {chaves:/whoosh|vento|rapido|rápido|passa|vulto|zum|sopro|lança|flecha/,nome:'whoosh',dur:0.9,fazer:(c,o,k)=>{ const fl=chiado(c,o,0,0.7,'bandpass',400,0.7*k,0.3); fl.Q.value=2; fl.frequency.setValueAtTime(300,0); fl.frequency.exponentialRampToValueAtTime(3000,0.35); fl.frequency.exponentialRampToValueAtTime(300,0.7); }},
  {chaves:/multid|taverna|murmur|conversa|gente|plateia|bar\b|festa/,nome:'murmúrio de multidão',dur:4,fazer:(c,o,k)=>{ for(let i=0;i<10;i++){ const t=Math.random()*1.5; const fl=chiado(c,o,t,2.5,'bandpass',300+Math.random()*900,0.12*k,0.6); fl.Q.value=3; } }},
  {chaves:/aplau|palma/,nome:'aplausos',dur:3,fazer:(c,o,k)=>{ for(let i=0;i<70;i++) chiado(c,o,Math.random()*2.6,0.05,'bandpass',1500+Math.random()*1500,0.25*k,0.001); }},
  {chaves:/fogo|chama|fogueira|queima|lareira/,nome:'fogo',dur:3,fazer:(c,o,k)=>{ chiado(c,o,0,2.9,'lowpass',500,0.3*k,0.3); for(let i=0;i<40;i++) chiado(c,o,Math.random()*2.8,0.02,'highpass',2000,0.3*k,0.001); }},
  {chaves:/chuva|garoa/,nome:'chuva',dur:4,fazer:(c,o,k)=>{ chiado(c,o,0,3.8,'highpass',1200,0.35*k,0.5); for(let i=0;i<80;i++) chiado(c,o,Math.random()*3.8,0.01,'bandpass',4000,0.15*k,0.001); }},
  {chaves:/queda|tomb|cai|caiu|desab|derrub/,nome:'queda',dur:1.2,fazer:(c,o,k)=>{ batida(c,o,0,{grave:50,corpo:500,forca:k,dur:0.4}); for(let i=0;i<5;i++) batida(c,o,0.15+i*0.11,{grave:120+Math.random()*80,corpo:1500,forca:0.3*k,dur:0.08}); }},
  {chaves:/rugid|rosna|monstro|fera|grunh|lobo/,nome:'rugido',dur:1.8,fazer:(c,o,k)=>{ const s=c.createOscillator(); s.type='sawtooth'; s.frequency.setValueAtTime(70,0); s.frequency.linearRampToValueAtTime(110,0.5); s.frequency.linearRampToValueAtTime(60,1.6); const f=filtro(c,'lowpass',700); const g=env(c,0,0.2,1.4,0.5*k); s.connect(f).connect(g).connect(o); s.start(0); s.stop(1.8); chiado(c,o,0,1.5,'bandpass',400,0.3*k,0.2); }},
  {chaves:/suspens|tens|misteri|drone|sombra/,nome:'tensão',dur:4,fazer:(c,o,k)=>{ for(const f of [55,82.4,116.5]){ const s=c.createOscillator(); s.type='sawtooth'; s.frequency.value=f; const fl=filtro(c,'lowpass',300); const g=env(c,0,1.5,2.4,0.15*k); s.connect(fl).connect(g).connect(o); s.start(0); s.stop(4); } }},
  {chaves:/\bpop\b|bolha|estalo/,nome:'pop',dur:0.3,fazer:(c,o,k)=>{ const s=c.createOscillator(); s.frequency.setValueAtTime(380,0); s.frequency.exponentialRampToValueAtTime(1400,0.06); const g=env(c,0,0.002,0.12,0.5*k); s.connect(g).connect(o); s.start(0); s.stop(0.2); }},
  {chaves:/clique|click|tecla|mouse/,nome:'clique',dur:0.2,fazer:(c,o,k)=>{ chiado(c,o,0,0.015,'highpass',3000,0.6*k,0.0005); ping(c,o,0,2400,0.03,0.15*k,'square'); }},
  {chaves:/\bding\b|acerto|certo|correto|notifica|sucesso/,nome:'ding (acerto)',dur:1.2,fazer:(c,o,k)=>{ ping(c,o,0,1318,1,0.3*k); ping(c,o,0.09,1760,1,0.25*k); }},
  {chaves:/erro|errado|buzz|falha|negad/,nome:'erro',dur:0.7,fazer:(c,o,k)=>{ for(const t of [0,0.28]) ping(c,o,t,140,0.22,0.35*k,'square'); }},
  {chaves:/subida|riser|suspense subindo|crescend/,nome:'subida (riser)',dur:3,fazer:(c,o,k)=>{ const fl=chiado(c,o,0,2.9,'bandpass',300,0.5*k,2.6); fl.Q.value=3; fl.frequency.exponentialRampToValueAtTime(6000,2.9); const s=c.createOscillator(); s.type='sawtooth'; s.frequency.setValueAtTime(110,0); s.frequency.exponentialRampToValueAtTime(880,2.9); const g=env(c,0,2.6,0.2,0.12*k); s.connect(g).connect(o); s.start(0); s.stop(3); }},
  {chaves:/descida|drop|queda de tom|desce/,nome:'descida (drop)',dur:1.5,fazer:(c,o,k)=>{ const s=c.createOscillator(); s.type='sine'; s.frequency.setValueAtTime(900,0); s.frequency.exponentialRampToValueAtTime(40,1.2); const g=env(c,0,0.01,1.3,0.5*k); s.connect(g).connect(o); s.start(0); s.stop(1.5); batida(c,o,1.1,{grave:40,corpo:300,forca:0.8*k,dur:0.4}); }},
  {chaves:/glitch|falha digital|chiado|estatica|estática|interfer/,nome:'glitch',dur:0.8,fazer:(c,o,k)=>{ for(let i=0;i<10;i++){ const t=i*0.07; if(Math.random()<0.7) ping(c,o,t,200+Math.random()*3000,0.04,0.2*k,'square'); chiado(c,o,t,0.03,'bandpass',800+Math.random()*5000,0.3*k,0.001); } }},
  {chaves:/foto|camera|câmera|flash|obturador/,nome:'foto (câmera)',dur:0.5,fazer:(c,o,k)=>{ chiado(c,o,0,0.03,'highpass',2500,0.7*k,0.001); chiado(c,o,0.12,0.05,'bandpass',1800,0.5*k,0.001); }},
  {chaves:/coracao|coração|batimento|pulsa/,nome:'batida de coração',dur:2.4,fazer:(c,o,k)=>{ for(const t of [0,0.28,1.2,1.48]) batida(c,o,t,{grave:48,corpo:200,forca:(t%1.2===0?0.9:0.6)*k,dur:0.18}); }},
  {chaves:/rufar|tambor|suspense de tambor|drumroll/,nome:'rufar de tambor',dur:2.6,fazer:(c,o,k)=>{ for(let i=0;i<48;i++){ const t=i*0.045; chiado(c,o,t,0.04,'bandpass',900,(0.1+0.3*i/48)*k,0.001); } batida(c,o,2.2,{grave:70,corpo:2500,forca:k,dur:0.35}); chiado(c,o,2.2,0.4,'highpass',4000,0.4*k,0.002); }},
  {chaves:/impacto|baque|boom|tum|pum/,nome:'impacto',dur:1.5,fazer:(c,o,k)=>{ batida(c,o,0,{grave:40,corpo:400,forca:k,dur:0.9}); }},
];
const PADRAO = RECEITAS.find(r=>r.nome==='impacto')!;
/** Qual som feito pelo site combina com a descrição. */
/** Categorias para a biblioteca de efeitos. */
export const CATEGORIAS_SOM:[string,string[]][] = [
  ['Transição',['whoosh','subida (riser)','descida (drop)','glitch']],
  ['Interface e redes',['pop','clique','ding (acerto)','erro','foto (câmera)']],
  ['Ação',['soco','impacto','explosão','queda','espadas','vidro quebrando']],
  ['Ambiente',['chuva','fogo','trovão','murmúrio de multidão','tensão']],
  ['Objetos',['porta batendo','porta rangendo','batida na madeira','passos','moedas','sino']],
  ['Emoção e humor',['aplausos','rufar de tambor','batida de coração','magia','rugido']],
];
export function receitaDe(desc:string){ const d=semAcento(desc); return RECEITAS.find(r=>r.chaves.test(d))||null; }
export function forcaDe(desc:string){ const d=semAcento(desc); return /muito forte|enorme|gigante|alto/.test(d)?1.4:/forte|grande/.test(d)?1.15:/fraco|leve|baixo|distante|longe|suave/.test(d)?0.55:1; }

async function sintetizar(desc:string){
  const r=receitaDe(desc)||PADRAO; const k=forcaDe(desc);
  const ctx=new OfflineAudioContext(1,Math.round(r.dur*RATE),RATE);
  const master=ctx.createGain(); master.gain.value=0.9; const comp=ctx.createDynamicsCompressor(); master.connect(comp).connect(ctx.destination);
  r.fazer(ctx,master,k);
  const b=await ctx.startRendering(); const s=b.getChannelData(0).slice();
  let pico=0; for(const v of s) pico=Math.max(pico,Math.abs(v)); if(pico>0.98) for(let i=0;i<s.length;i++) s[i]=s[i]/pico*0.98;
  return {samples:s,nome:r.nome,generico:!receitaDe(desc)};
}

// ---------------------------------------------------------------- arquivo e IA
async function decodificar(buf:ArrayBuffer){
  const ctx=new OfflineAudioContext(1,1,RATE);
  const b=await ctx.decodeAudioData(buf).catch(()=>{ throw new Error('Não consegui ler esse áudio. Use MP3, WAV ou OGG.'); });
  const out=new Float32Array(b.length); for(let c=0;c<b.numberOfChannels;c++){ const d=b.getChannelData(c); for(let i=0;i<d.length;i++) out[i]+=d[i]/b.numberOfChannels; }
  return out.length>RATE*30?out.slice(0,RATE*30):out;
}

/** Gera um efeito sonoro. Devolve o WAV, a duração e de onde veio. */
export async function gerarSom(desc:string,fonte:FonteSom,o:{arquivo?:File}={}):Promise<{wav:Blob;duracao:number;origem:string}>{
  let s:Float32Array; let origem:string;
  if(fonte==='arquivo'){ if(!o.arquivo) throw new Error('Escolha o arquivo de som.'); s=await decodificar(await o.arquivo.arrayBuffer()); origem='arquivo: '+o.arquivo.name; }
  else { const r=await sintetizar(desc); s=r.samples; origem=`site: ${r.nome}${r.generico?' (genérico)':''}`; }
  return {wav:wav(s,RATE),duracao:s.length/RATE,origem};
}

