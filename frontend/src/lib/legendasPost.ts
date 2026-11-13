// Texto (legenda) de cada post: preenchido automático com o que o site já sabe do corte,
// ou escrito pela IA (Gemini ou Claude) com base na fala do trecho.
import type { Settings } from '../state';
import { cuesDe, type Clip } from './analyze';
import type { Cue } from './captions';
import { iaAtiva } from './ia';

const PARADAS = new Set('a o e é de da do das dos em no na nos nas um uma uns umas que se por para pra com sem mais muito muita isso esse essa este esta ele ela eles elas eu voce você vc mas foi ser ter tem como quando onde qual quais porque pois ao aos à às sobre entre até seu sua seus suas meu minha nosso nossa the and of to in is it destaque versão versao corte parte video vídeo'.split(' '));

/** Transforma palavras em hashtag: sem acento, sem espaço, minúscula. */
export function hashtag(t:string){
  const s=t.normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'');
  return s.length>=3&&s.length<=30?'#'+s:'';
}

/** Fala do trecho (texto da legenda do vídeo), cortada num tamanho bom para o post. */
export function falaDoCorte(c:Clip,cues:Cue[],max=180){
  const t=cuesDe(c,cues).filter(q=>q.end>c.inicio&&q.start<c.fim).map(q=>q.text.trim()).join(' ').replace(/\s+/g,' ').trim();
  if(t.length<=max) return t;
  const corte=t.slice(0,max); const fim=Math.max(corte.lastIndexOf('. '),corte.lastIndexOf('? '),corte.lastIndexOf('! '));
  return (fim>60?corte.slice(0,fim+1):corte.slice(0,corte.lastIndexOf(' '))+'...');
}

/** Arruma uma lista de hashtags: com #, sem acento, sem repetir. */
export function limparHashtags(l:unknown,max=10){
  const txt=Array.isArray(l)?l.join(' '):String(l||'');
  const out:string[]=[]; for(const t of txt.split(/[\s,;]+/)){ const h=hashtag(t.replace(/^#+/,'')); if(h&&!out.includes(h)) out.push(h); }
  return out.slice(0,max);
}

/** Hashtags a partir do tema, do título e da fala, mais as gerais de vídeo curto. */
export function hashtagsDoCorte(c:Clip,cues:Cue[],tema:string,max=8){
  if(c.hashtags?.length) return c.hashtags.slice(0,Math.max(max,c.hashtags.length));
  const tags:string[]=[];
  const add=(t:string)=>{ const h=hashtag(t); if(h&&!tags.includes(h)) tags.push(h); };
  if(tema.trim()){ add(tema); tema.split(/[\s,;#]+/).forEach(add); }
  const palavras=(c.titulo+' '+falaDoCorte(c,cues,400)).split(/[^\p{L}\p{N}]+/u).filter(w=>w.length>=4&&!PARADAS.has(w.toLowerCase()));
  const freq=new Map<string,number>(); for(const w of palavras){ const k=w.toLowerCase(); freq.set(k,(freq.get(k)||0)+1+(c.titulo.toLowerCase().includes(k)?2:0)); }
  [...freq.entries()].sort((a,b)=>b[1]-a[1]).slice(0,4).forEach(([w])=>add(w));
  ['cortes','shorts','reels','fyp'].forEach(add);
  return tags.slice(0,max);
}

/** Legenda pronta, sem IA: título, um trecho da fala (ou o motivo) e hashtags. */
export function legendaAutomatica(c:Clip,cues:Cue[],tema:string){
  const fala=falaDoCorte(c,cues);
  const meio=fala?`"${fala}"`:(c.motivo&&!/^Vídeo inteiro/.test(c.motivo)&&c.fonte==='ia'?c.motivo:'');
  return [c.titulo,meio,hashtagsDoCorte(c,cues,tema).join(' ')].filter(Boolean).join('\n\n');
}

type Texto = {id:string;legenda:string;hashtags:string[]};

function pedido(itens:{id:string;titulo:string;fala:string;motivo:string}[],tema:string){
  return `Você escreve legendas de posts para vídeos curtos (Reels, Shorts, TikTok) em português do Brasil.
Para cada vídeo abaixo, escreva uma legenda curta e chamativa (1 a 3 frases, até 220 caracteres, pode ter 1 ou 2 emojis), que dê vontade de assistir sem entregar o final, e termine com uma pergunta ou chamada para comentar quando fizer sentido.
Depois, sugira de 5 a 8 hashtags relevantes (sem acento, minúsculas, com #), misturando o tema específico e hashtags amplas de vídeo curto.
Não invente fatos que não estejam no título ou na fala. Tema do canal: ${tema||'não informado'}.

${itens.map(i=>`ID ${i.id}\nTítulo: ${i.titulo}\nFala do trecho: ${i.fala||'(sem fala transcrita)'}\nPor que é bom: ${i.motivo||'-'}`).join('\n\n')}`;
}

/** Pede para a IA configurada escrever a legenda e as hashtags de cada corte. */
export async function escreverComIA(s:Settings,clips:Clip[],cues:Cue[],tema:string):Promise<Texto[]>{
  const itens=clips.map(c=>({id:c.id,titulo:c.titulo,fala:falaDoCorte(c,cues,600),motivo:c.motivo}));
  const texto=pedido(itens,tema);
  const q=iaAtiva(s);
  if(q==='gemini'){
    const {chamar,GEMINI_MODEL}=await import('./gemini');
    const SCHEMA={type:'OBJECT',properties:{posts:{type:'ARRAY',items:{type:'OBJECT',properties:{id:{type:'STRING'},legenda:{type:'STRING'},hashtags:{type:'ARRAY',items:{type:'STRING'}}},required:['id','legenda','hashtags']}}},required:['posts']};
    const res=await chamar(s.geminiKey,GEMINI_MODEL+':generateContent',{contents:[{role:'user',parts:[{text:texto}]}],generationConfig:{responseMimeType:'application/json',responseSchema:SCHEMA,temperature:0.8}});
    const t=(res?.candidates?.[0]?.content?.parts||[]).filter((p:any)=>!p.thought).map((p:any)=>p.text||'').join('');
    try{ return JSON.parse(t).posts; }catch{ throw new Error('A resposta do Gemini veio incompleta. Tente de novo.'); }
  }
  if(q==='claude'){
    const {escreverPostsClaude}=await import('./ai');
    return escreverPostsClaude(s.claudeKey,texto);
  }
  throw new Error('Configure a chave do Gemini (grátis) ou da Claude em Chaves e ajustes.');
}

/** Junta legenda e hashtags no texto final do post. */
export function montarTexto(t:Texto){
  const tags=(t.hashtags||[]).map(h=>hashtag(h.replace(/^#/,''))).filter(Boolean);
  return [t.legenda.trim(),[...new Set(tags)].join(' ')].filter(Boolean).join('\n\n');
}
