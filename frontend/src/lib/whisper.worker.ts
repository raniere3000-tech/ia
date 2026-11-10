// Transcrição automática com Whisper rodando no navegador (transformers.js).
// O modelo é baixado uma única vez do Hugging Face e fica em cache no navegador.
import { pipeline, env } from '@huggingface/transformers';

env.allowLocalModels = false;

type Msg = {samples:Float32Array; model:string; language:string};
let asr:any = null; let loaded = '';

self.onmessage = async (e:MessageEvent<Msg>)=>{
  const {samples,model,language} = e.data;
  try{
    if(!asr || loaded!==model){
      const device = (self as any).navigator?.gpu ? 'webgpu' : 'wasm';
      asr = await pipeline('automatic-speech-recognition',model,{
        device: device as any,
        dtype: device==='webgpu' ? {encoder_model:'fp32',decoder_model_merged:'q4'} as any : 'q8' as any,
        progress_callback:(p:any)=>{ if(p.status==='progress') self.postMessage({type:'download',file:p.file,progress:p.progress}); },
      });
      loaded = model;
    }
    self.postMessage({type:'stage',stage:'transcrevendo'});
    // Processa em blocos de ~5 minutos para mostrar progresso.
    const rate = 16000, block = rate*300; const chunks:{start:number;end:number;text:string}[] = [];
    for(let off=0; off<samples.length; off+=block){
      const part = samples.subarray(off,Math.min(samples.length,off+block));
      const out:any = await asr(part,{language:language==='auto'?undefined:language,task:'transcribe',return_timestamps:true,chunk_length_s:30,stride_length_s:5});
      const base = off/rate;
      for(const c of (out.chunks||[])){
        const [s,t] = c.timestamp||[0,0];
        const text = String(c.text||'').trim();
        if(text) chunks.push({start:base+(s??0),end:base+(t ?? (s??0)+3),text});
      }
      self.postMessage({type:'progress',progress:Math.min(100,Math.round((off+block)/samples.length*100))});
    }
    self.postMessage({type:'done',cues:chunks});
  }catch(err:any){
    self.postMessage({type:'error',error:String(err?.message||err)});
  }
};
