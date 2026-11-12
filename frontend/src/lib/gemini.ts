// Avaliação dos cortes com o Gemini (Google AI Studio), chave do próprio usuário, direto do navegador.
import type { Cue } from './captions';
import type { Candidate } from './analyze';
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
  properties:{id:S,gancho:N,fluxo:N,valor:N,tendencia:N,titulo:S,motivo:S,inicio:N,fim:N,gancho_texto:S},
  required:['id','gancho','fluxo','valor','tendencia','titulo','motivo','inicio','fim','gancho_texto']}}},required:['cortes']};

export async function avaliarComGemini(key:string, cands:(Candidate&{id:string})[], cues:Cue[], opts:OptsIA):Promise<AvaliacaoIA[]>{
  const parts:any[] = [{text:instrucoes(opts)}];
  for(const c of cands){
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
