// Leitura de áudio e captura de quadros do vídeo, tudo no navegador.
export type AudioData = { samples:Float32Array; rate:number; duration:number };

export function videoInfo(url:string){
  return new Promise<{duration:number;width:number;height:number}>((resolve,reject)=>{
    const v = document.createElement('video');
    v.preload='metadata'; v.muted=true; v.src=url;
    v.onloadedmetadata=()=>{ const r={duration:v.duration,width:v.videoWidth,height:v.videoHeight}; v.removeAttribute('src'); v.load(); isFinite(r.duration)&&r.duration>0?resolve(r):reject(new Error('Não foi possível ler a duração do vídeo.')); };
    v.onerror=()=>reject(new Error('O navegador não conseguiu abrir este vídeo. Use MP4 (H.264), MOV ou WEBM.'));
  });
}

/** Decodifica o áudio em mono 16 kHz (formato que o Whisper usa). Retorna null se não houver áudio legível. */
export async function decodeAudio(file:File):Promise<AudioData|null>{
  const buf = await file.arrayBuffer();
  const rate = 16000;
  try{
    const ctx = new OfflineAudioContext(1,1,rate);
    const decoded = await ctx.decodeAudioData(buf);
    const n = decoded.length, ch = decoded.numberOfChannels;
    const out = new Float32Array(n);
    for(let c=0;c<ch;c++){ const d=decoded.getChannelData(c); for(let i=0;i<n;i++) out[i]+=d[i]/ch; }
    return {samples:out,rate:decoded.sampleRate,duration:n/decoded.sampleRate};
  }catch{
    return null;
  }
}

/** Energia RMS por quadro de `step` segundos. */
export function energyProfile(a:AudioData,step=0.5){
  const hop = Math.round(a.rate*step); const n = Math.ceil(a.samples.length/hop);
  const out = new Float32Array(n);
  for(let i=0;i<n;i++){
    let s=0,c=0; const end=Math.min(a.samples.length,(i+1)*hop);
    for(let j=i*hop;j<end;j+=4){ const v=a.samples[j]; s+=v*v; c++; }
    out[i]=Math.sqrt(s/Math.max(1,c));
  }
  return out;
}

/** Captura quadros (JPEG) em instantes específicos. */
export async function captureFrames(url:string,times:number[],maxSide=360):Promise<string[]>{
  const v = document.createElement('video'); v.muted=true; v.preload='auto'; v.src=url; v.playsInline=true;
  await new Promise<void>((res,rej)=>{ v.onloadeddata=()=>res(); v.onerror=()=>rej(new Error('Falha ao abrir vídeo')); });
  const scale = Math.min(1,maxSide/Math.max(v.videoWidth,v.videoHeight));
  const c = document.createElement('canvas'); c.width=Math.round(v.videoWidth*scale); c.height=Math.round(v.videoHeight*scale);
  const ctx = c.getContext('2d')!;
  const out:string[] = [];
  for(const t of times){
    v.currentTime = Math.min(Math.max(0,t),Math.max(0,v.duration-0.05));
    await new Promise<void>(res=>{ const done=()=>{v.removeEventListener('seeked',done);res();}; v.addEventListener('seeked',done); setTimeout(done,3000); });
    ctx.drawImage(v,0,0,c.width,c.height);
    out.push(c.toDataURL('image/jpeg',0.72));
  }
  v.removeAttribute('src'); v.load();
  return out;
}
