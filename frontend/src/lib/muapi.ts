// Muapi.ai: um serviço pago que dá acesso a vários modelos de imagem e vídeo
// (Seedance, Kling, Wan, Nano Banana, Seedream...). A ideia veio do projeto
// Open-Higgsfield-AI (licença MIT); aqui só chamamos a mesma API direto do navegador.
// A chave fica só no navegador da pessoa (localStorage), como a do Gemini.

const BASE = 'https://api.muapi.ai/api/v1';

export type ModeloMuapi = {id:string;nome:string;dica:string;corpo:(o:{prompt:string;imagem?:string;duracao:number})=>Record<string,unknown>};

/** Modelos que transformam uma imagem em vídeo (imagem → vídeo). */
export const MODELOS_ANIMAR:ModeloMuapi[] = [
  {id:'seedance-lite-i2v',nome:'Seedance Lite',dica:'mais barato, bom para testar',corpo:o=>({prompt:o.prompt,image_url:o.imagem,resolution:'720p',duration:o.duracao,camera_fixed:false})},
  {id:'kling-v2.5-turbo-pro-i2v',nome:'Kling 2.5 Turbo Pro',dica:'movimento mais bonito, custa mais',corpo:o=>({prompt:o.prompt,image_url:o.imagem,duration:o.duracao})},
  {id:'wan2.5-image-to-video-fast',nome:'Wan 2.5 rápido',dica:'sai mais rápido',corpo:o=>({prompt:o.prompt,image_url:o.imagem,resolution:'720p',duration:o.duracao})},
  {id:'seedance-pro-i2v',nome:'Seedance Pro',dica:'qualidade alta',corpo:o=>({prompt:o.prompt,image_url:o.imagem,resolution:'720p',duration:o.duracao,camera_fixed:false})},
];
/** Modelos que criam uma imagem a partir de um texto. */
export const MODELOS_IMAGEM:ModeloMuapi[] = [
  {id:'nano-banana',nome:'Nano Banana',dica:'Google, rápido',corpo:o=>({prompt:o.prompt,aspect_ratio:'9:16'})},
  {id:'seedream-5.0',nome:'Seedream 5.0',dica:'ByteDance, bem detalhado',corpo:o=>({prompt:o.prompt,aspect_ratio:'9:16',quality:'basic'})},
];

function erroMuapi(status:number,txt:string){
  if(status===401||status===403) return new Error('A chave do Muapi não foi aceita. Confira em Chaves e ajustes.');
  if(status===402||/credit|balance|insufficient/i.test(txt)) return new Error('Acabaram os créditos do Muapi. Recarregue em muapi.ai.');
  if(status===429) return new Error('O Muapi pediu para esperar um pouco (muitos pedidos). Tente de novo em 1 minuto.');
  let msg=txt; try{ const j=JSON.parse(txt); msg=j.detail||j.error||j.message||txt; }catch{ /* texto puro */ }
  return new Error(`O Muapi recusou o pedido (${status}): ${String(msg).slice(0,200)}`);
}
async function req(key:string,caminho:string,init:RequestInit={}){
  let r:Response;
  try{ r=await fetch(BASE+caminho,{...init,headers:{'x-api-key':key,...(init.body&&!(init.body instanceof FormData)?{'Content-Type':'application/json'}:{}),...init.headers}}); }
  catch{ throw new Error('Não consegui falar com o Muapi. Confira a internet.'); }
  const txt=await r.text();
  if(!r.ok) throw erroMuapi(r.status,txt);
  try{ return JSON.parse(txt); }catch{ return {}; }
}

/** Testa a chave pedindo um resultado que não existe: chave errada dá 401/403. */
export async function testarChaveMuapi(key:string){
  if(key.length<10) throw new Error('A chave parece incompleta.');
  try{ await req(key,'/predictions/teste-estudioclip/result'); }
  catch(e){ if(e instanceof Error&&/não foi aceita|internet/.test(e.message)) throw e; }
}

/** Envia um arquivo para o Muapi e devolve o link dele. */
export async function enviarArquivo(key:string,blob:Blob,nome:string):Promise<string>{
  const fd=new FormData(); fd.append('file',blob,nome);
  const d=await req(key,'/upload_file',{method:'POST',body:fd});
  const url=d.url||d.file_url||d.data?.url;
  if(!url) throw new Error('O Muapi não devolveu o link do arquivo enviado.');
  return url;
}

/** Pede uma geração e espera ficar pronta. Devolve o link do resultado. */
export async function gerarMuapi(key:string,modelo:string,corpo:Record<string,unknown>,onStatus:(t:string)=>void,sinal?:AbortSignal,maxMin=20):Promise<string>{
  const d=await req(key,'/'+modelo,{method:'POST',body:JSON.stringify(corpo)});
  const pronto=(x:Record<string,any>)=>x.outputs?.[0]||x.url||x.output?.url||x.video?.url||x.images?.[0]?.url;
  const id=d.request_id||d.id;
  if(!id){ const u=pronto(d); if(u) return u; throw new Error('O Muapi não devolveu o número do pedido.'); }
  const ini=Date.now();
  while(Date.now()-ini<maxMin*60000){
    if(sinal?.aborted) throw new Error('Cancelado.');
    await new Promise(r=>setTimeout(r,3000));
    let x:Record<string,any>;
    try{ x=await req(key,`/predictions/${id}/result`); }catch(e){ if(e instanceof Error&&/internet/.test(e.message)) continue; throw e; }
    const st=String(x.status||'').toLowerCase();
    if(['completed','succeeded','success'].includes(st)){ const u=pronto(x); if(u) return u; throw new Error('O Muapi terminou, mas sem arquivo.'); }
    if(['failed','error','cancelled','canceled'].includes(st)) throw new Error('O Muapi não conseguiu gerar: '+String(x.error||'erro sem detalhe').slice(0,200));
    const s=Math.round((Date.now()-ini)/1000);
    onStatus(st==='processing'||st==='running'?`Gerando... ${s} s`:`Na fila do Muapi... ${s} s`);
  }
  throw new Error('Demorou demais. O pedido pode terminar depois no painel do muapi.ai.');
}

/** Baixa o resultado para dentro do site. Se o servidor do arquivo bloquear, devolve null. */
export async function baixarResultado(url:string):Promise<Blob|null>{
  try{ const r=await fetch(url); if(!r.ok) return null; return await r.blob(); }catch{ return null; }
}
