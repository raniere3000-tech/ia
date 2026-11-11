// Reenquadramento que segue o rosto: detecta rostos (MediaPipe, no navegador) em quadros do trecho
// e gera uma trilha suave do centro da câmera.
export type Trilha = {t:number;cx:number;cy:number}[];   // t relativo ao início do corte; cx/cy de 0 a 1
const BASE = import.meta.env.BASE_URL;
let detectorP:Promise<any>|null = null;

async function detector(){
  if(!detectorP) detectorP = (async()=>{
    const {FilesetResolver,FaceDetector} = await import('@mediapipe/tasks-vision');
    const files = await FilesetResolver.forVisionTasks(BASE+'mediapipe');
    const opts = (delegate:'GPU'|'CPU')=>({baseOptions:{modelAssetPath:BASE+'models/blaze_face_short_range.tflite',delegate},runningMode:'IMAGE' as const,minDetectionConfidence:0.45});
    try{ return await FaceDetector.createFromOptions(files,opts('GPU')); }
    catch{ return await FaceDetector.createFromOptions(files,opts('CPU')); }
  })().catch(e=>{ detectorP=null; throw e; });
  return detectorP;
}

const cache = new Map<string,Trilha|null>();

/** Analisa o trecho (uma amostra a cada `passo` s). Devolve null se quase não achar rosto. */
export async function rastrearRosto(url:string,inicio:number,fim:number,onPct?:(p:number)=>void,passo=0.4):Promise<Trilha|null>{
  const chave=`${url}|${inicio}|${fim}`; if(cache.has(chave)) return cache.get(chave)!;
  const det = await detector();
  const v=document.createElement('video'); v.src=url; v.muted=true; v.playsInline=true; v.preload='auto';
  await new Promise<void>((res,rej)=>{ v.onloadeddata=()=>res(); v.onerror=()=>rej(new Error('Não deu para ler o vídeo para achar o rosto.')); });
  // O detector enxerga melhor rostos grandes: analisa o quadro em blocos quadrados que se sobrepõem.
  const vw=v.videoWidth, vh=v.videoHeight, lado=Math.min(vw,vh), TAM=320;
  const nb=Math.max(1,Math.ceil(Math.max(vw,vh)/lado*1.5)), blocos:number[]=[];
  for(let k=0;k<nb;k++) blocos.push(nb===1?0:Math.round((Math.max(vw,vh)-lado)*k/(nb-1)));
  const c=document.createElement('canvas'); c.width=c.height=TAM; const ctx=c.getContext('2d')!;
  const pts:{t:number;cx:number;cy:number;ok:boolean}[]=[];
  const n=Math.max(1,Math.ceil((fim-inicio)/passo));
  for(let i=0;i<=n;i++){
    const t=Math.min(fim-inicio,i*passo);
    v.currentTime=inicio+t; await new Promise<void>(r=>{ const f=()=>{ v.removeEventListener('seeked',f); r(); }; v.addEventListener('seeked',f); });
    // Escolhe o maior rosto (quem está falando costuma estar mais perto).
    let best:{cx:number;cy:number;area:number}|null=null;
    for(const off of blocos){
      const sx=vw>=vh?off:0, sy=vw>=vh?0:off;
      ctx.drawImage(v,sx,sy,lado,lado,0,0,TAM,TAM);
      for(const d of det.detect(c).detections||[]){
        const b=d.boundingBox; if(!b) continue; const k=lado/TAM;
        const f={cx:(sx+(b.originX+b.width/2)*k)/vw,cy:(sy+(b.originY+b.height/2)*k)/vh,area:b.width*b.height*k*k};
        if(!best||f.area>best.area) best=f;
      }
    }
    pts.push(best?{t,cx:best.cx,cy:best.cy,ok:true}:{t,cx:.5,cy:.5,ok:false});
    onPct?.(Math.round(i/n*100));
  }
  v.removeAttribute('src'); v.load();
  console.info('Segue o rosto: rosto em',pts.filter(p=>p.ok).length,'de',pts.length,'quadros');
  const trilha=suavizar(pts);
  cache.set(chave,trilha); return trilha;
}

/** Preenche buracos, ignora tremidas pequenas e suaviza o movimento. Exportada para testes. */
export function suavizar(pts:{t:number;cx:number;cy:number;ok:boolean}[]):Trilha|null{
  const achados=pts.filter(p=>p.ok).length;
  if(!pts.length || achados/pts.length<0.25) return null;
  // buracos: repete o último rosto visto (ou o próximo, no começo)
  const cheio=pts.map(p=>({...p}));
  let ult=cheio.find(p=>p.ok)!;
  for(const p of cheio){ if(p.ok) ult=p; else { p.cx=ult.cx; p.cy=ult.cy; } }
  // zona morta: só move a câmera se o rosto andar mais de 6% da largura
  let alvo={cx:cheio[0].cx,cy:cheio[0].cy}; const comZona=cheio.map(p=>{ if(Math.abs(p.cx-alvo.cx)>0.06||Math.abs(p.cy-alvo.cy)>0.08) alvo={cx:p.cx,cy:p.cy}; return {t:p.t,...alvo}; });
  // suavização exponencial nos dois sentidos (sem atraso)
  const ida=comZona.map(p=>({...p})); for(let i=1;i<ida.length;i++){ ida[i].cx=ida[i-1].cx*0.7+ida[i].cx*0.3; ida[i].cy=ida[i-1].cy*0.7+ida[i].cy*0.3; }
  for(let i=ida.length-2;i>=0;i--){ ida[i].cx=ida[i+1].cx*0.7+ida[i].cx*0.3; ida[i].cy=ida[i+1].cy*0.7+ida[i].cy*0.3; }
  return ida.map(p=>({t:p.t,cx:+p.cx.toFixed(4),cy:+p.cy.toFixed(4)}));
}

/** Posição da câmera no tempo t (interpolada). */
export function posicao(tr:Trilha,t:number){
  if(t<=tr[0].t) return tr[0];
  for(let i=1;i<tr.length;i++){ if(t<=tr[i].t){ const a=tr[i-1],b=tr[i],k=(t-a.t)/Math.max(1e-6,b.t-a.t); return {t,cx:a.cx+(b.cx-a.cx)*k,cy:a.cy+(b.cy-a.cy)*k}; } }
  return tr[tr.length-1];
}
