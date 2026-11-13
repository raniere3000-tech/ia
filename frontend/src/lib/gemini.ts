// Avaliação dos cortes com o Gemini (Google AI Studio), chave do próprio usuário, direto do navegador.
import type { Cue } from './captions';
import { fatorEscala, type Candidate } from './analyze';
import { instrucoes, textoCandidato, type AvaliacaoIA, type OptsIA } from './promptCortes';

export const GEMINI_MODEL = 'gemini-flash-latest';
const API = 'https://generativelanguage.googleapis.com/v1beta/models/';

export class ErroGemini extends Error { constructor(public status:number, msg:string, public motivo='', public esperaSeg=0, public diario=false){ super(msg); } }

/** Depois de um erro do Gemini: quantos ms esperar antes de tentar de novo, ou null se não adianta esperar. */
export function esperaGemini(e:unknown,tentativa:number):number|null{
  if(!(e instanceof ErroGemini)) return null;
  if(e.status===429&&e.diario) return null;
  if(e.status!==429&&e.status<500) return null;
  if(tentativa>=4) return null;
  const s=e.esperaSeg>0?e.esperaSeg+2:20*(tentativa+1);
  return Math.min(90,s)*1000;
}

export async function chamar(key:string, caminho:string, body?:unknown){
  let r:Response;
  try{ r = await fetch(caminho.startsWith('?')?API.slice(0,-1)+caminho:API+caminho,{method:body?'POST':'GET',headers:{'x-goog-api-key':key.trim(),...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined}); }
  catch{ throw new ErroGemini(0,'Não foi possível conectar ao Gemini. Verifique sua internet.'); }
  const dados = await r.json().catch(()=>({}));
  if(!r.ok){
    const e = dados?.error||{}; const det:any[] = e.details||[]; const motivo = det.map((d:any)=>d.reason).filter(Boolean).join(',') || e.status || '';
    const atraso = det.find((d:any)=>d.retryDelay)?.retryDelay; const esperaSeg = atraso?parseFloat(String(atraso))||0:0;
    const cotas = det.flatMap((d:any)=>d.violations||[]).map((v:any)=>String(v.quotaId||v.quotaMetric||''));
    const diario = r.status===429 && (cotas.some(c=>/PerDay/i.test(c)) || /per day|daily/i.test(String(e.message||'')));
    if(diario) throw new ErroGemini(429,'Acabou a cota grátis de hoje deste modelo do Gemini. Ela volta por volta das 5h da manhã (horário de Brasília). Para continuar agora: troque o modelo da voz (Flash e Pro têm cotas separadas) ou ative o faturamento no Google AI Studio.',motivo,0,true);
    throw new ErroGemini(r.status, e.message||`Erro ${r.status} do Gemini.`, motivo, esperaSeg);
  }
  return dados;
}

export async function testarChaveGemini(key:string){
  if(!key.trim()) throw new ErroGemini(400,'Cole a chave.');
  await chamar(key, GEMINI_MODEL);
}

const N = {type:'NUMBER'}, S = {type:'STRING'};
const SCHEMA = {type:'OBJECT',properties:{cortes:{type:'ARRAY',items:{type:'OBJECT',
  properties:{id:S,gancho:N,fluxo:N,valor:N,tendencia:N,titulo:S,motivo:S,inicio:N,fim:N,gancho_texto:S,hashtags:{type:'ARRAY',items:S}},
  required:['id','gancho','fluxo','valor','tendencia','titulo','motivo','inicio','fim','gancho_texto']}}},required:['cortes']};

export async function avaliarComGemini(key:string, cands:(Candidate&{id:string})[], cues:Cue[], opts:OptsIA):Promise<AvaliacaoIA[]>{
  const parts:any[] = [{text:opts.escolha??instrucoes(opts)}];
  for(const c of opts.escolha?[]:cands){
    parts.push({text:textoCandidato(c,cues)});
    for(const f of opts.frames?.[c.id]||[]) parts.push({inline_data:{mime_type:'image/jpeg',data:f.split(',')[1]}});
  }
  const res = await chamar(key, GEMINI_MODEL+':generateContent', {
    contents:[{role:'user',parts}],
    generationConfig:{responseMimeType:'application/json',responseSchema:SCHEMA,temperature:0.4},
  });
  if(res.promptFeedback?.blockReason) throw new ErroGemini(200,'O Gemini recusou avaliar este conteúdo.','BLOCKED');
  const cand = res.candidates?.[0];
  if(!cand || cand.finishReason==='SAFETY' || cand.finishReason==='PROHIBITED_CONTENT') throw new ErroGemini(200,'O Gemini recusou avaliar este conteúdo.','BLOCKED');
  const texto = (cand.content?.parts||[]).filter((p:any)=>!p.thought).map((p:any)=>p.text||'').join('');
  let json:any;
  try{ json = JSON.parse(texto); }catch{ throw new ErroGemini(200,'A resposta do Gemini veio incompleta. Tente novamente.'); }
  if(!Array.isArray(json?.cortes)) throw new ErroGemini(200,'A resposta do Gemini veio incompleta. Tente novamente.');
  return json.cortes.map((x:any)=>({...x,id:String(x.id)}));
}

export function erroGemini(e:unknown){
  if(!(e instanceof ErroGemini)) return e instanceof Error ? e.message : String(e);
  const m = (e.motivo+' '+e.message).toLowerCase();
  if(m.includes('api_key_invalid')||m.includes('api key not valid')) return 'Chave do Gemini inválida. Confira em Chaves e ajustes.';
  if(m.includes('service_disabled')||m.includes('has not been used')||m.includes('is disabled')) return 'Esta chave é do Google Cloud mas a "Generative Language API" não está ativada nela. Ative em console.cloud.google.com (APIs e serviços) ou crie uma chave em aistudio.google.com.';
  if(m.includes('api_key_service_blocked')||m.includes('blocked')&&e.status===403) return 'Esta chave tem restrição e não pode usar o Gemini. No Google Cloud, em Credenciais, libere a "Generative Language API" para ela, ou crie outra em aistudio.google.com.';
  if(m.includes('referer')) return 'A chave só aceita certos sites. Adicione raniere3000-tech.github.io nas restrições da chave no Google Cloud.';
  if(e.status===429) return 'Limite grátis do Gemini atingido por agora. Aguarde um minuto (ou até amanhã) e tente de novo.';
  if(e.status===404) return 'O modelo do Gemini não está disponível para esta chave.';
  if(e.status===0) return e.message;
  return 'Erro do Gemini: '+e.message;
}

// ---------------------------------------------------------------- cortes direto pelo link do YouTube

export type CorteLink = {inicio:number;fim:number;titulo:string;motivo:string;nota:number;gancho_texto:string;hashtags:string[]};
const SCHEMA_LINK = {type:'OBJECT',properties:{duracao_video:N,cortes:{type:'ARRAY',items:{type:'OBJECT',
  properties:{inicio:N,fim:N,titulo:S,motivo:S,nota:N,gancho_texto:S,hashtags:{type:'ARRAY',items:S}},required:['inicio','fim','titulo','motivo','nota','gancho_texto']}}},required:['cortes']};

/** O Gemini assiste o vídeo público do YouTube pelo link e devolve os melhores trechos, sem precisar baixar nada. */
export async function acharCortesNoLink(key:string, url:string, o:{min:number;max:number;limite:number;tema?:string;pedido?:string;acao?:boolean}, onEspera?:(seg:number)=>void):Promise<CorteLink[]>{
  const texto = `Você é um editor sênior de vídeos curtos (TikTok, Reels, Shorts). Assista a este vídeo inteiro, com imagem e áudio, e escolha os ${o.limite} melhores trechos para virar cortes.
${o.tema?`Tema informado: ${o.tema}\n`:''}${o.pedido?`Pedido do usuário (priorize isto): ${o.pedido}\n`:''}${o.acao?'O vídeo é de gameplay ou ação: valorize jogadas, reações, sustos e viradas, mesmo com pouca fala.\n':''}
Regras de cada corte:
- Duração entre ${o.min} e ${o.max} segundos.
- Quem nunca viu o vídeo entende e se importa, sem precisar do contexto anterior.
- Começa no início de uma frase (ou da ação) e termina logo depois do fechamento: piada, lição, revelação, resposta ou reação forte. Nunca corte no meio da frase.
- Evite abertura, despedida, propaganda, pedido de inscrição, enrolação e repetição.
- Os cortes não podem se sobrepor. Espalhe pelo vídeo quando houver bons momentos em partes diferentes.
- Devolva exatamente ${o.limite} cortes sempre que o vídeo tiver duração para isso. Os mais fracos entram com nota menor. Não invente falas nem cenas.
Para cada corte devolva:
- inicio e fim: segundos desde o começo do vídeo, como número (ex.: 754.5 para 12:34,5). Não use formato de minutos.
- nota: pontuação de viralidade, número inteiro de 0 a 99 (não use escala de 0 a 10). O melhor costuma ficar entre 80 e 95, um razoável entre 55 e 70.
- titulo: até 60 caracteres, em português.
- gancho_texto: 3 a 7 palavras para aparecer escritas no topo do vídeo, sem emoji, sem hashtag.
- motivo: 1 frase dizendo o que acontece ou é dito no trecho e por que funciona.
- hashtags: de 5 a 8 hashtags para o post, com #, minúsculas e sem acento. Misture as específicas do assunto do trecho com 2 ou 3 amplas de vídeo curto (ex.: #shorts, #reels, #fyp).
Devolva também duracao_video em segundos.`;
  const corpo = (baixa:boolean)=>({contents:[{role:'user',parts:[{file_data:{file_uri:url}},{text:texto}]}],generationConfig:{responseMimeType:'application/json',responseSchema:SCHEMA_LINK,temperature:0.3,...(baixa?{mediaResolution:'MEDIA_RESOLUTION_LOW'}:{})}});
  const pedir = async(baixa:boolean)=>{ for(let t=0;;t++){ try{ return await chamar(key,GEMINI_MODEL+':generateContent',corpo(baixa)); }catch(e){ const ms=esperaGemini(e,t+2); if(ms==null) throw e; onEspera?.(Math.round(ms/1000)); await new Promise(r=>setTimeout(r,ms)); } } };
  let res:any;
  try{ res = await pedir(true); }
  catch(e){
    if(e instanceof ErroGemini && e.status===400 && /mediaresolution|media_resolution|unknown name/i.test(e.message)) res = await pedir(false);
    else if(e instanceof ErroGemini && (e.status===400||e.status===403||e.status===404) && /video|youtube|url|uri|permission|private|unavailable|not found/i.test(e.message)) throw new ErroGemini(e.status,'O Gemini não conseguiu abrir este vídeo. Ele só assiste vídeos públicos do YouTube (não funciona com privado, com restrição de idade ou ao vivo em andamento). Detalhe: '+e.message.slice(0,160),'LINK');
    else if(e instanceof ErroGemini && /token|too large|exceeds/i.test(e.message)) throw new ErroGemini(e.status,'Este vídeo é longo demais para o Gemini assistir de uma vez. Use "Mais opções" para escolher um trecho, ou baixe o vídeo e envie o arquivo.','LINK');
    else throw e;
  }
  if(res.promptFeedback?.blockReason) throw new ErroGemini(200,'O Gemini recusou analisar este vídeo.','BLOCKED');
  const cand = res.candidates?.[0];
  const txt = (cand?.content?.parts||[]).filter((p:any)=>!p.thought).map((p:any)=>p.text||'').join('');
  let json:any; try{ json = JSON.parse(txt); }catch{ throw new ErroGemini(200,'A resposta do Gemini veio incompleta. Tente de novo.'); }
  return limparCortesLink(json?.cortes, o, Number(json?.duracao_video)||0);
}
/** Confere os tempos devolvidos pela IA: ordem, duração dentro do pedido, sem sobreposição, melhores primeiro. */
export function limparCortesLink(lista:unknown, o:{min:number;max:number;limite:number}, duracao=0):CorteLink[]{
  if(!Array.isArray(lista)) return [];
  const k = fatorEscala(lista.map((x:any)=>Number(x?.nota)));   // a IA às vezes responde de 0 a 10
  const bons:CorteLink[] = [];
  for(const x of [...lista].sort((a:any,b:any)=>(Number(b?.nota)||0)-(Number(a?.nota)||0))){
    let ini = Number(x?.inicio), fim = Number(x?.fim); if(!isFinite(ini)||!isFinite(fim)) continue;
    if(duracao>0){ ini = Math.min(ini,duracao); fim = Math.min(fim,duracao); }
    if(ini<0||fim-ini<Math.max(3,o.min*0.5)) continue;
    if(fim-ini>o.max*1.5) fim = ini+o.max;
    if(bons.some(b=>Math.min(b.fim,fim)-Math.max(b.inicio,ini)>2)) continue;   // já tem um corte melhor nesse pedaço
    bons.push({inicio:+ini.toFixed(1),fim:+fim.toFixed(1),titulo:String(x.titulo||'Corte').slice(0,80),motivo:String(x.motivo||''),nota:Math.max(0,Math.min(99,Math.round((Number(x.nota)||0)*k))),gancho_texto:String(x.gancho_texto||''),hashtags:Array.isArray(x.hashtags)?x.hashtags.map(String):[]});
    if(bons.length>=o.limite) break;
  }
  return bons;
}
