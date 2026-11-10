import type { Cue } from './captions';

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
    const w = new Worker(new URL('./whisper.worker.ts',import.meta.url),{type:'module'});
    const files = new Map<string,number>();
    w.onmessage = (e)=>{
      const m = e.data;
      if(m.type==='download'){ files.set(m.file,m.progress||0); const v=[...files.values()]; onStatus('Baixando modelo de transcrição (só na primeira vez)',Math.round(v.reduce((a,b)=>a+b,0)/v.length)); }
      else if(m.type==='stage') onStatus('Transcrevendo a fala',0);
      else if(m.type==='progress') onStatus('Transcrevendo a fala',m.progress);
      else if(m.type==='done'){ w.terminate(); resolve(m.cues); }
      else if(m.type==='error'){ w.terminate(); reject(new Error('Transcrição falhou: '+m.error)); }
    };
    w.onerror = (e)=>{ w.terminate(); reject(new Error('Transcrição falhou: '+e.message)); };
    const copy = samples.slice();
    w.postMessage({samples:copy,model,language},[copy.buffer]);
  });
}
