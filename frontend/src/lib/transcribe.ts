import type { Cue } from './captions';
import { chamar, GEMINI_MODEL, ErroGemini } from './gemini';

export const WHISPER_MODELS = [
  {id:'onnx-community/whisper-tiny',nome:'Rápido (tiny, ~40 MB)'},
  {id:'onnx-community/whisper-base',nome:'Equilibrado (base, ~80 MB)'},
  {id:'onnx-community/whisper-small',nome:'Mais preciso (small, ~250 MB)'},
];
export const IDIOMAS = [
  {id:'portuguese',nome:'Português'},{id:'english',nome:'Inglês'},{id:'spanish',nome:'Espanhol'},{id:'auto',nome:'Detectar automaticamente'},
];

/** Transcreve o áudio (mono 16 kHz) num Web Worker para não travar a página. */
export function transcrever(samples:Float32Array,model:string,language:string,onStatus:(s:string,pct:number)=>void):Promise<Cue[]>{
  return new Promise((resolve,reject)=>{
    let w:Worker;
    try{ w = new Worker(new URL('./whisper.worker.ts',import.meta.url),{type:'module'}); }
    catch(e){ reject(new Error('Este navegador não consegue rodar a transcrição ('+(e instanceof Error?e.message:String(e))+').')); return; }
    const files = new Map<string,number>();
    w.onmessage = (e)=>{
      const m = e.data;
      if(m.type==='download'){ files.set(m.file,m.progress||0); const v=[...files.values()]; onStatus('Baixando modelo de transcrição (só na primeira vez)',Math.round(v.reduce((a,b)=>a+b,0)/v.length)); }
      else if(m.type==='stage') onStatus('Transcrevendo a fala',0);
      else if(m.type==='progress') onStatus('Transcrevendo a fala',m.progress);
      else if(m.type==='retry'){ files.clear(); onStatus('Tentando de outro jeito',0); console.warn('Whisper: tentando de novo', m.error); }
      else if(m.type==='done'){ w.terminate(); resolve(m.cues); }
      else if(m.type==='error'){ w.terminate(); reject(new Error(traduzir(m.error))); }
    };
    w.onerror = (e)=>{ w.terminate(); reject(new Error(traduzir(e.message||'o processo de transcrição parou'))); };
    const copy = samples.slice();
    w.postMessage({samples:copy,model,language},[copy.buffer]);
  });
}

function traduzir(err:string){
  const m = err.toLowerCase();
  if(m.includes('fetch')||m.includes('network')||m.includes('load')) return 'A legenda automática não conseguiu baixar o modelo de transcrição (precisa de internet na primeira vez). Detalhe: '+err;
  if(m.includes('memory')||m.includes('allocation')||m.includes('out of')) return 'Faltou memória no aparelho para a legenda automática. Use o modelo "Rápido" em Chaves e ajustes, ou a legenda pelo Gemini. Detalhe: '+err;
  return 'A legenda automática falhou. Detalhe: '+err;
}

// ---------- Transcrição pelo Gemini (usa a chave do Google, roda na nuvem) ----------

/** Junta um pedaço do áudio num WAV 16 kHz mono 16 bits. */
function wav(s:Float32Array,rate=16000){
  const buf = new ArrayBuffer(44+s.length*2); const v = new DataView(buf);
  const str = (o:number,t:string)=>{ for(let i=0;i<t.length;i++) v.setUint8(o+i,t.charCodeAt(i)); };
  str(0,'RIFF'); v.setUint32(4,36+s.length*2,true); str(8,'WAVE'); str(12,'fmt '); v.setUint32(16,16,true); v.setUint16(20,1,true); v.setUint16(22,1,true);
  v.setUint32(24,rate,true); v.setUint32(28,rate*2,true); v.setUint16(32,2,true); v.setUint16(34,16,true); str(36,'data'); v.setUint32(40,s.length*2,true);
  for(let i=0;i<s.length;i++){ const x=Math.max(-1,Math.min(1,s[i])); v.setInt16(44+i*2,x<0?x*0x8000:x*0x7fff,true); }
  return new Uint8Array(buf);
}
function base64(b:Uint8Array){ let s=''; for(let i=0;i<b.length;i+=0x8000) s+=String.fromCharCode(...b.subarray(i,i+0x8000)); return btoa(s); }
const espera = (ms:number)=>new Promise(r=>setTimeout(r,ms));

const SCHEMA = {type:'OBJECT',properties:{falas:{type:'ARRAY',items:{type:'OBJECT',properties:{inicio:{type:'NUMBER'},fim:{type:'NUMBER'},texto:{type:'STRING'}},required:['inicio','fim','texto']}}},required:['falas']};
const NOME_IDIOMA:Record<string,string> = {portuguese:'português do Brasil',english:'inglês',spanish:'espanhol',auto:'o idioma falado'};

/** Transcreve com o Gemini em pedaços de 2 minutos. Devolve as falas com horário em segundos. */
export async function transcreverGemini(samples:Float32Array,key:string,language:string,onStatus:(s:string,pct:number)=>void):Promise<Cue[]>{
  const rate = 16000, bloco = rate*120; const out:Cue[] = [];
  const total = Math.ceil(samples.length/bloco);
  for(let i=0;i<total;i++){
    const ini = i*bloco, parte = samples.subarray(ini,Math.min(samples.length,ini+bloco));
    const dur = parte.length/rate, base = ini/rate;
    // Pula trechos em silêncio.
    let pico = 0; for(let j=0;j<parte.length;j+=160) pico=Math.max(pico,Math.abs(parte[j]));
    onStatus('Transcrevendo com o Gemini',Math.round(i/total*100));
    if(pico<0.01) continue;
    const corpo = {contents:[{role:'user',parts:[
      {text:`Transcreva a fala deste áudio de ${dur.toFixed(0)} segundos em ${NOME_IDIOMA[language]||'o idioma falado'}, palavra por palavra, sem resumir. Divida em frases curtas (no máximo 12 palavras cada) com o segundo de início e de fim de cada frase, contados a partir do começo deste áudio (de 0 a ${dur.toFixed(0)}). Se não houver fala, devolva a lista vazia.`},
      {inline_data:{mime_type:'audio/wav',data:base64(wav(parte))}},
    ]}],generationConfig:{responseMimeType:'application/json',responseSchema:SCHEMA,temperature:0}};
    let res:any = null;
    for(let t=0;t<4&&!res;t++){
      try{ res = await chamar(key,GEMINI_MODEL+':generateContent',corpo); }
      catch(e){
        if(e instanceof ErroGemini && (e.status===429||e.status>=500) && t<3){ onStatus('Limite do Gemini, aguardando para continuar',Math.round(i/total*100)); await espera(20000*(t+1)); continue; }
        throw e;
      }
    }
    const texto = (res?.candidates?.[0]?.content?.parts||[]).filter((p:any)=>!p.thought).map((p:any)=>p.text||'').join('');
    let falas:any[] = [];
    try{ falas = JSON.parse(texto).falas||[]; }catch{ continue; }
    for(const f of falas){
      const s = Math.max(0,Math.min(dur,+f.inicio||0)), e = Math.max(s+0.3,Math.min(dur,+f.fim||s+2));
      const txt = String(f.texto||'').trim();
      if(txt) out.push({start:+(base+s).toFixed(2),end:+(base+e).toFixed(2),text:txt});
    }
  }
  onStatus('Transcrevendo com o Gemini',100);
  return out.sort((a,b)=>a.start-b.start);
}
