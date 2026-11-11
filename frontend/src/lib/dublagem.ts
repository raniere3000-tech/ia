// Dublagem em português: o Gemini traduz a fala de cada corte e lê em voz alta (TTS).
// A voz é misturada por cima do áudio original abaixado na hora de exportar o vídeo.
import type { Cue } from './captions';
import { chamar, ErroGemini, GEMINI_MODEL } from './gemini';

export const TTS_MODEL = 'gemini-2.5-flash-preview-tts';
export const VOZES:[string,string][] = [['Kore','Feminina firme'],['Aoede','Feminina leve'],['Leda','Feminina jovem'],['Puck','Masculina animada'],['Charon','Masculina informativa'],['Fenrir','Masculina empolgada'],['Orus','Masculina grave']];
const RATE = 24000;

/** Voz pronta de cada corte (amostras a partir do início do corte). Fica só nesta aba. */
export type Dub = {samples:Float32Array;rate:number;volumeOriginal:number};
const dubs = new Map<string,Dub>();
export const pegarDub = (id:string)=>dubs.get(id)||null;
export const apagarDub = (id:string)=>{ dubs.delete(id); };

const espera = (ms:number)=>new Promise(r=>setTimeout(r,ms));
async function comRetentativa<T>(f:()=>Promise<T>,onEspera:()=>void):Promise<T>{
  for(let t=0;;t++){
    try{ return await f(); }
    catch(e){
      if(e instanceof ErroGemini && (e.status===429||e.status>=500) && t<3){ onEspera(); await espera(25000*(t+1)); continue; }
      throw e;
    }
  }
}

/** Junta as falas em blocos (até ~18 s), cada bloco vira uma leitura da voz. */
export function blocos(cues:Cue[],max=18){
  const out:{start:number;end:number;cues:Cue[]}[] = [];
  for(const c of cues){
    const b = out[out.length-1];
    if(b && c.end-b.start<=max && c.start-b.end<1.5){ b.cues.push(c); b.end=Math.max(b.end,c.end); }
    else out.push({start:c.start,end:c.end,cues:[c]});
  }
  return out;
}

/** Traduz cada frase para o português do Brasil, mantendo a mesma quantidade de frases. */
export async function traduzirFrases(key:string,frases:string[],onEspera:()=>void):Promise<string[]>{
  if(!frases.length) return [];
  const SCHEMA = {type:'OBJECT',properties:{frases:{type:'ARRAY',items:{type:'STRING'}}},required:['frases']};
  const texto = `Traduza cada frase abaixo para português do Brasil, de forma natural e falada (como uma dublagem), curta o bastante para caber no mesmo tempo da original. Se já estiver em português, mantenha. Devolva exatamente ${frases.length} frases, na mesma ordem.\n\n${frases.map((f,i)=>`${i+1}. ${f}`).join('\n')}`;
  const res:any = await comRetentativa(()=>chamar(key,GEMINI_MODEL+':generateContent',{contents:[{role:'user',parts:[{text:texto}]}],generationConfig:{responseMimeType:'application/json',responseSchema:SCHEMA,temperature:0.3}}),onEspera);
  const t = (res?.candidates?.[0]?.content?.parts||[]).filter((p:any)=>!p.thought).map((p:any)=>p.text||'').join('');
  let lista:string[] = [];
  try{ lista = JSON.parse(t).frases||[]; }catch{ throw new Error('A tradução do Gemini veio incompleta. Tente de novo.'); }
  return frases.map((f,i)=>String(lista[i]??f).trim()||f);
}

/** PCM 16 bits (little-endian) em base64 → amostras de -1 a 1. */
export function pcmParaFloat(b64:string){
  const bin = atob(b64); const n = bin.length>>1; const out = new Float32Array(n);
  for(let i=0;i<n;i++){ let v = bin.charCodeAt(2*i)|(bin.charCodeAt(2*i+1)<<8); if(v>=0x8000) v-=0x10000; out[i]=v/0x8000; }
  return out;
}

/** Lê o texto em voz alta com o Gemini. Devolve as amostras a 24 kHz. */
export async function falar(key:string,texto:string,voz:string,onEspera:()=>void){
  const corpo = {contents:[{role:'user',parts:[{text:`Leia em português do Brasil, com tom natural de narração e ritmo um pouco acelerado: ${texto}`}]}],
    generationConfig:{responseModalities:['AUDIO'],speechConfig:{voiceConfig:{prebuiltVoiceConfig:{voiceName:voz}}}}};
  const res:any = await comRetentativa(()=>chamar(key,TTS_MODEL+':generateContent',corpo),onEspera);
  const p = (res?.candidates?.[0]?.content?.parts||[]).find((x:any)=>x.inlineData?.data||x.inline_data?.data);
  const d = p?.inlineData||p?.inline_data;
  if(!d) throw new Error('O Gemini não devolveu a voz. Tente de novo.');
  const m = /rate=(\d+)/.exec(d.mimeType||d.mime_type||''); const r = m?+m[1]:RATE;
  return {samples:pcmParaFloat(d.data),rate:r};
}

/** Acelera um pouco (sem passar de 1,2x) para a fala caber no espaço. */
function acelerar(s:Float32Array,f:number){
  if(f<=1.001) return s;
  const n = Math.floor(s.length/f); const out = new Float32Array(n);
  for(let i=0;i<n;i++){ const x=i*f, a=Math.floor(x), k=x-a; out[i]=(s[a]||0)*(1-k)+(s[a+1]||0)*k; }
  return out;
}
function reamostrar(s:Float32Array,de:number,para:number){ return de===para?s:acelerar(s,de/para); }

/**
 * Dubla um corte: traduz as falas, gera a voz por bloco e monta a faixa de áudio.
 * Devolve as legendas em português (com horário do vídeo) para trocar as originais.
 */
export async function dublarCorte(key:string,clip:{id:string;inicio:number;fim:number},cuesAbs:Cue[],voz:string,volumeOriginal:number,onStatus:(s:string,pct:number)=>void){
  const dur = clip.fim-clip.inicio;
  const cues = cuesAbs.filter(c=>c.end>clip.inicio&&c.start<clip.fim).map(c=>({start:Math.max(0,c.start-clip.inicio),end:Math.min(dur,c.end-clip.inicio),text:c.text}));
  if(!cues.length) throw new Error('Este corte ainda não tem legenda. Gere a legenda primeiro.');
  const aguardando = ()=>onStatus('Limite do Gemini, aguardando para continuar',0);
  onStatus('Traduzindo a fala',5);
  const pt = await traduzirFrases(key,cues.map(c=>c.text),aguardando);
  const trad = cues.map((c,i)=>({...c,text:pt[i]}));
  const bs = blocos(trad);
  const faixa = new Float32Array(Math.ceil(dur*RATE));
  const novas:Cue[] = []; let cursor = 0;
  for(let i=0;i<bs.length;i++){
    const b = bs[i];
    onStatus(`Gerando a voz (${i+1} de ${bs.length})`,Math.round(10+i/bs.length*85));
    const v = await falar(key,b.cues.map(c=>c.text).join(' '),voz,aguardando);
    let s = reamostrar(v.samples,v.rate,RATE);
    const ini = Math.max(b.start,cursor);
    const prox = i+1<bs.length?bs[i+1].start:dur;
    const espaco = Math.max(0.5,prox-ini);
    const falaDur = s.length/RATE;
    if(falaDur>espaco) s = acelerar(s,Math.min(1.2,falaDur/espaco));
    const o = Math.round(ini*RATE);
    for(let k=0;k<s.length&&o+k<faixa.length;k++) faixa[o+k]+=s[k];
    // Legendas acompanham a voz: cada frase ocupa um pedaço proporcional ao tamanho do texto.
    const total = b.cues.reduce((t,c)=>t+c.text.length,0)||1; const len = s.length/RATE; let t = ini;
    for(const c of b.cues){ const d = len*c.text.length/total; novas.push({start:+(clip.inicio+t).toFixed(2),end:+(clip.inicio+Math.min(dur,t+d)).toFixed(2),text:c.text}); t+=d; }
    cursor = ini+s.length/RATE;
  }
  dubs.set(clip.id,{samples:faixa,rate:RATE,volumeOriginal});
  onStatus('Dublagem pronta',100);
  return novas.filter(c=>c.start<clip.fim);
}

/** WAV para ouvir a dublagem na página. */
export function wavDaDub(d:Dub){
  const s = d.samples; const buf = new ArrayBuffer(44+s.length*2); const v = new DataView(buf);
  const str = (o:number,t:string)=>{ for(let i=0;i<t.length;i++) v.setUint8(o+i,t.charCodeAt(i)); };
  str(0,'RIFF'); v.setUint32(4,36+s.length*2,true); str(8,'WAVE'); str(12,'fmt '); v.setUint32(16,16,true); v.setUint16(20,1,true); v.setUint16(22,1,true);
  v.setUint32(24,d.rate,true); v.setUint32(28,d.rate*2,true); v.setUint16(32,2,true); v.setUint16(34,16,true); str(36,'data'); v.setUint32(40,s.length*2,true);
  for(let i=0;i<s.length;i++){ const x=Math.max(-1,Math.min(1,s[i])); v.setInt16(44+i*2,x<0?x*0x8000:x*0x7fff,true); }
  return new Blob([buf],{type:'audio/wav'});
}
