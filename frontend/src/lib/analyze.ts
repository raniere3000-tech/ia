// Análise de cortes no navegador: mesma heurística do backend (energia RMS do áudio).
export type Clip = {id:string;titulo:string;nota_final:number;nota_10:number;inicio:number;fim:number;motivo:string};

export function videoDuration(url:string){
  return new Promise<number>((resolve,reject)=>{
    const v = document.createElement('video');
    v.preload = 'metadata'; v.muted = true; v.src = url;
    v.onloadedmetadata = ()=>{ const d = v.duration; v.removeAttribute('src'); v.load(); isFinite(d)&&d>0 ? resolve(d) : reject(new Error('Duração do vídeo indisponível.')); };
    v.onerror = ()=>reject(new Error('O navegador não conseguiu abrir este vídeo. Tente um MP4 (H.264) ou WEBM.'));
  });
}

async function decodeAudio(file:File){
  const buf = await file.arrayBuffer();
  for(const rate of [8000,16000,22050,44100]){
    try{
      const ctx = new OfflineAudioContext(1,1,rate);
      return await ctx.decodeAudioData(buf.slice(0));
    }catch{ /* tenta outra taxa */ }
  }
  return null;
}

export async function analisarNoNavegador(file:File,url:string,opt:{min:number;max:number;limite:number},progress:(n:number)=>void){
  progress(5);
  const dur = await videoDuration(url);
  progress(15);
  const audio = await decodeAudio(file);
  progress(60);
  const low = opt.min, high = opt.max;
  const window = Math.max(4,Math.min(high,Math.round((low+high)/2)));
  const segs:{inicio:number;fim:number;energia:number}[] = [];
  let start = 0;
  const chans = audio ? Array.from({length:audio.numberOfChannels},(_,i)=>audio.getChannelData(i)) : [];
  const rate = audio?.sampleRate || 8000;
  while(start+Math.min(low,dur) <= dur && segs.length < 120){
    const end = Math.min(dur,start+window);
    if(end-start < Math.min(low,dur)) break;
    let energia = 0;
    if(chans.length){
      const a = Math.floor(start*rate), b = Math.min(chans[0].length,Math.floor(end*rate));
      const step = Math.max(1,Math.floor((b-a)/20000));
      let sum = 0, n = 0;
      for(let i=a;i<b;i+=step){ let v=0; for(const c of chans) v+=c[i]; v/=chans.length; sum+=v*v; n++; }
      energia = Math.sqrt(sum/Math.max(1,n));
    }
    segs.push({inicio:+start.toFixed(2),fim:+end.toFixed(2),energia});
    start = end;
  }
  progress(90);
  const peak = Math.max(...segs.map(s=>s.energia),0) || 1;
  const clips:Clip[] = segs.map((s,idx)=>{
    const nota = chans.length ? Math.min(95,Math.max(10,Math.round(35+60*s.energia/peak))) : 35;
    return {id:String(idx+1),titulo:`Destaque ${idx+1}`,inicio:s.inicio,fim:s.fim,nota_final:nota,nota_10:+(nota/9.9).toFixed(1),
      motivo: chans.length ? 'Estimativa inicial por energia sonora; revise manualmente.' : 'Áudio não pôde ser lido pelo navegador; trechos sugeridos em sequência.'};
  });
  clips.sort((a,b)=>b.nota_final-a.nota_final);
  progress(100);
  return {duracao:dur, cortes:clips.slice(0,Math.min(30,opt.limite)), audio_lido:!!audio};
}
