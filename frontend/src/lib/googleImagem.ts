// Imagens das cenas com a chave do Google (Gemini), direto do navegador.
// Dois caminhos:
//  1. Modelos de imagem do Google (Nano Banana e parentes): imagem de verdade. Na API eles não têm cota grátis,
//     então a chave precisa ter o faturamento ativado no Google AI Studio.
//  2. Desenho por código: o Gemini de texto (que tem cota grátis) escreve um desenho em SVG e o site transforma em imagem.
// Os nomes dos modelos mudam com frequência, por isso a lista vem da própria chave (GET /models).
import { ErroGemini, GEMINI_MODEL, chamar, erroGemini, esperaGemini } from './gemini';

export type ModeloG = {id:string;nome:string;tipo:'gemini'|'imagen'};
/** Usados só se a chave não conseguir listar os modelos. */
const RESERVA:ModeloG[] = [{id:'gemini-nano-banana-2.1',nome:'Nano Banana 2.1',tipo:'gemini'},{id:'gemini-3.1-flash-image',nome:'Gemini 3.1 Flash Image',tipo:'gemini'},{id:'gemini-2.5-flash-image',nome:'Gemini 2.5 Flash Image',tipo:'gemini'}];
const cache=new Map<string,ModeloG[]>();
const peso=(id:string)=>(/banana/.test(id)?0:/flash-image/.test(id)&&!/lite/.test(id)?1:/lite/.test(id)?2:/pro/.test(id)?3:/imagen/.test(id)?4:5);
const versao=(id:string)=>parseFloat((id.match(/(\d+(?:\.\d+)?)/)||['0','0'])[1])||0;

/** Modelos de imagem que esta chave enxerga, do mais indicado para o menos. */
export async function modelosImagem(key:string):Promise<ModeloG[]>{
  const k=key.trim(); if(!k) return []; const c=cache.get(k); if(c) return c;
  let lista:ModeloG[]=[];
  try{
    const r=await chamar(k,'?pageSize=1000');
    for(const m of (r.models||[]) as {name?:string;displayName?:string;supportedGenerationMethods?:string[]}[]){
      const id=String(m.name||'').replace(/^models\//,''); const met=m.supportedGenerationMethods||[];
      if(/tts|audio|live|embed|video|veo/i.test(id)) continue;
      if(/image|banana/i.test(id)&&!/imagen/i.test(id)&&met.includes('generateContent')) lista.push({id,nome:m.displayName||id,tipo:'gemini'});
      else if(/imagen/i.test(id)&&met.includes('predict')) lista.push({id,nome:m.displayName||id,tipo:'imagen'});
    }
  }catch{ /* sem lista: usa a reserva */ }
  lista.sort((a,b)=>peso(a.id)-peso(b.id)||versao(b.id)-versao(a.id)||a.id.localeCompare(b.id));
  if(!lista.length) lista=RESERVA; else cache.set(k,lista);
  return lista;
}

const b64=(s:string,mime:string)=>{ const bin=atob(s); const u=new Uint8Array(bin.length); for(let i=0;i<bin.length;i++) u[i]=bin.charCodeAt(i); return new Blob([u],{type:mime||'image/png'}); };
async function paraB64(b:Blob){ const u=new Uint8Array(await b.arrayBuffer()); let s=''; for(let i=0;i<u.length;i+=0x8000) s+=String.fromCharCode(...u.subarray(i,i+0x8000)); return btoa(s); }

const SEM_COTA='Criar imagem com a IA de imagem do Google não tem cota grátis na API: a chave precisa ter o faturamento ativado em aistudio.google.com (Configurações, Faturamento). Enquanto isso, escolha "Desenho por código (grátis)", que usa a mesma chave sem custo.';
function traduzir(e:unknown,modelo:string):Error{
  if(e instanceof ErroGemini){
    const m=(e.motivo+' '+e.message).toLowerCase();
    if(e.status===429&&(e.diario||/limit: 0|free.?tier|billing|plan/.test(m))) return new Error(SEM_COTA);
    if(e.status===429) return new Error('O Google pediu para esperar um pouco (muitas imagens seguidas). Tente de novo em 1 minuto.');
    if(e.status===403&&/billing|paid|permission/.test(m)) return new Error(SEM_COTA);
    if(e.status===404) return new Error(`O modelo de imagem "${modelo}" não está disponível para esta chave. Escolha outro em "Criar imagem com".`);
    if(m.includes('blocked')||m.includes('safety')) return new Error('O Google recusou criar esta imagem. Mude o pedido da cena e tente de novo.');
    return new Error(erroGemini(e));
  }
  return e instanceof Error?e:new Error(String(e));
}
async function comEspera<T>(f:()=>Promise<T>,onEspera?:(seg:number)=>void):Promise<T>{
  for(let t=0;;t++){ try{ return await f(); }catch(e){ const ms=e instanceof ErroGemini&&e.status===429&&/limit: 0|free.?tier/i.test(e.message)?null:esperaGemini(e,t+2); if(ms==null) throw e; onEspera?.(Math.round(ms/1000)); await new Promise(r=>setTimeout(r,ms)); } }
}

/** Cria uma imagem vertical com um modelo de imagem do Google. "auto" tenta os modelos da chave em ordem. */
export async function criarImagemGoogle(key:string,prompt:string,modelo:string,o:{aspecto?:string;referencia?:Blob|null;onStatus?:(t:string)=>void}={}):Promise<Blob>{
  const todos=await modelosImagem(key); const fila=modelo&&modelo!=='auto'?[todos.find(m=>m.id===modelo)||{id:modelo,nome:modelo,tipo:/imagen/.test(modelo)?'imagen' as const:'gemini' as const}]:todos.slice(0,4);
  const aspecto=o.aspecto||'9:16'; let ultimo:unknown=new Error('Nenhum modelo de imagem do Google disponível para esta chave.');
  const ref=o.referencia?{inline_data:{mime_type:o.referencia.type||'image/png',data:await paraB64(o.referencia)}}:null;
  for(const m of fila){
    o.onStatus?.(`Criando a imagem com ${m.nome}`);
    try{
      if(m.tipo==='imagen'){
        const r=await comEspera(()=>chamar(key,m.id+':predict',{instances:[{prompt}],parameters:{sampleCount:1,aspectRatio:aspecto}}),s=>o.onStatus?.(`O Google pediu para esperar ${s} s`));
        const p=r.predictions?.[0]; if(p?.bytesBase64Encoded) return b64(p.bytesBase64Encoded,p.mimeType||'image/png');
        throw new ErroGemini(200,'O Google não devolveu a imagem (pedido recusado).','BLOCKED');
      }
      const corpo=(comConfig:boolean)=>({contents:[{role:'user',parts:[...(ref?[ref]:[]),{text:prompt}]}],generationConfig:{responseModalities:['TEXT','IMAGE'],...(comConfig?{imageConfig:{aspectRatio:aspecto}}:{})}});
      let r:any;
      try{ r=await comEspera(()=>chamar(key,m.id+':generateContent',corpo(true)),s=>o.onStatus?.(`O Google pediu para esperar ${s} s`)); }
      catch(e){ if(e instanceof ErroGemini&&e.status===400&&/imageconfig|aspect|unknown name|invalid json/i.test(e.message)) r=await chamar(key,m.id+':generateContent',corpo(false)); else throw e; }
      for(const p of r.candidates?.[0]?.content?.parts||[]){ const d=p.inlineData||p.inline_data; if(d?.data) return b64(d.data,d.mimeType||d.mime_type||'image/png'); }
      throw new ErroGemini(200,'O Google não devolveu a imagem (pedido recusado).','BLOCKED');
    }catch(e){ ultimo=traduzir(e,m.id); if(!(e instanceof ErroGemini)||e.status!==404||fila.length===1) throw ultimo; }
  }
  throw ultimo;
}

// ---------------------------------------------------------------- desenho por código (SVG)

const PROIBIDAS=['script','foreignObject','iframe','object','embed','audio','video','a','animate','animateTransform','animateMotion','set','style'];
/** Tira do SVG tudo que não é desenho: scripts, links externos, eventos. */
export function limparSvg(texto:string,W:number,H:number):string{
  const m=texto.match(/<svg[\s\S]*<\/svg>/i); if(!m) throw new Error('O Gemini não devolveu um desenho. Tente de novo.');
  const doc=new DOMParser().parseFromString(m[0],'image/svg+xml'); const svg=doc.documentElement;
  if(doc.querySelector('parsererror')||svg.nodeName.toLowerCase()!=='svg') throw new Error('O desenho veio com defeito. Tente de novo.');
  for(const t of PROIBIDAS) for(const el of [...svg.getElementsByTagName(t)]) el.remove();
  for(const el of [svg,...svg.querySelectorAll('*')]) for(const a of [...el.attributes]){
    const n=a.name.toLowerCase(), v=a.value.trim();
    if(n.startsWith('on')) el.removeAttribute(a.name);
    else if((n==='href'||n==='xlink:href')&&!v.startsWith('#')) el.removeAttribute(a.name);
    else if(/url\(\s*['"]?\s*(?!#)/i.test(v)||/javascript:/i.test(v)) el.removeAttribute(a.name);
  }
  for(const el of [...svg.getElementsByTagName('image')]) if(!el.getAttribute('href')&&!el.getAttribute('xlink:href')) el.remove();
  svg.setAttribute('xmlns','http://www.w3.org/2000/svg'); if(!svg.getAttribute('viewBox')) svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
  svg.setAttribute('width',String(W)); svg.setAttribute('height',String(H)); svg.setAttribute('preserveAspectRatio','xMidYMid slice');
  return new XMLSerializer().serializeToString(svg);
}
export async function svgParaPng(svg:string,W:number,H:number):Promise<Blob>{
  const url=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml'}));
  try{
    const img=new Image(); await new Promise<void>((ok,erro)=>{ img.onload=()=>ok(); img.onerror=()=>erro(new Error('O navegador não conseguiu abrir o desenho. Tente de novo.')); img.src=url; });
    const c=document.createElement('canvas'); c.width=W; c.height=H; const x=c.getContext('2d')!; x.fillStyle='#101018'; x.fillRect(0,0,W,H); x.drawImage(img,0,0,W,H);
    return await new Promise<Blob>((ok,erro)=>c.toBlob(b=>b?ok(b):erro(new Error('Não consegui salvar o desenho.')),'image/png'));
  }finally{ URL.revokeObjectURL(url); }
}
/** O Gemini de texto escreve a ilustração em SVG; o site transforma em imagem. Funciona na cota grátis. */
export async function desenharPorCodigo(key:string,pedido:string,estilo:string,o:{W?:number;H?:number;onStatus?:(t:string)=>void}={}):Promise<Blob>{
  const W=o.W||1080, H=o.H||1920;
  const instr=`Você é um ilustrador que desenha em SVG. Desenhe UMA ilustração vertical para a cena de um vídeo curto.
Cena: ${pedido}
Estilo: ${estilo||'ilustração flat colorida, formas simples e limpas, cores fortes, boa leitura no celular'}
Regras:
- Responda SÓ com o código, começando em <svg e terminando em </svg>. Sem explicação e sem markdown.
- Use exatamente viewBox="0 0 ${W} ${H}" e preencha a tela toda com um fundo (degradê ou cenário).
- Composição rica: fundo, plano do meio e personagem ou objeto principal grande no centro, com sombras e detalhes.
- Só formas vetoriais (rect, circle, ellipse, path, polygon, line, g, defs, linearGradient, radialGradient). Sem <text>, <image>, <script>, <style>, animação, fontes ou links.
- Deixe o terço de baixo sem elementos importantes (ali entra a legenda).
- No máximo 180 elementos.`;
  o.onStatus?.('O Gemini está desenhando a cena');
  let ultimo:unknown;
  for(let tentativa=0;tentativa<2;tentativa++){
    try{
      const r=await comEspera(()=>chamar(key,GEMINI_MODEL+':generateContent',{contents:[{role:'user',parts:[{text:instr}]}],generationConfig:{temperature:tentativa?1:0.8,maxOutputTokens:16000}}),s=>o.onStatus?.(`O Gemini pediu para esperar ${s} s`));
      const cand=r.candidates?.[0]; if(!cand||r.promptFeedback?.blockReason) throw new Error('O Gemini recusou desenhar esta cena. Mude o pedido.');
      const texto=(cand.content?.parts||[]).filter((p:any)=>!p.thought).map((p:any)=>p.text||'').join('');
      return await svgParaPng(limparSvg(texto,W,H),W,H);
    }catch(e){ ultimo=e; if(e instanceof ErroGemini) throw new Error(erroGemini(e)); o.onStatus?.('O desenho veio incompleto, tentando de novo'); }
  }
  throw ultimo instanceof Error?ultimo:new Error(String(ultimo));
}
