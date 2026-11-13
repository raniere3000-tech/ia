// Escolhe qual IA avalia os cortes (Gemini ou Claude), conforme as chaves salvas.
import type { Settings } from '../state';
import type { Cue } from './captions';
import { validarEscolhidos, type Candidate, type Escolhido } from './analyze';
import type { AvaliacaoIA, OptsIA } from './promptCortes';

export type QualIA = 'gemini'|'claude';
export function iaAtiva(s:Settings):QualIA|null{
  if(s.ia==='claude'&&s.claudeKey) return 'claude';
  if(s.ia==='gemini'&&s.geminiKey) return 'gemini';
  return s.geminiKey?'gemini':s.claudeKey?'claude':null;
}
export const nomeIA = (q:QualIA|null)=>q==='gemini'?'Gemini':q==='claude'?'Claude':'';

export async function avaliar(s:Settings, cands:(Candidate&{id:string})[], cues:Cue[], opts:OptsIA):Promise<AvaliacaoIA[]>{
  const q = iaAtiva(s);
  if(q==='gemini'){ const {avaliarComGemini}=await import('./gemini'); return avaliarComGemini(s.geminiKey,cands,cues,opts); }
  if(q==='claude'){ const {avaliarComIA}=await import('./ai'); return avaliarComIA(s.claudeKey,cands,cues,opts); }
  throw new Error('Nenhuma chave de IA configurada.');
}
export async function erroIA(s:Settings, e:unknown){
  if(iaAtiva(s)==='gemini'){ const {erroGemini}=await import('./gemini'); return erroGemini(e); }
  const {erroAmigavel}=await import('./ai'); return erroAmigavel(e);
}

/**
 * A IA lê a transcrição inteira e escolhe os melhores trechos (o jeito que os apps de corte trabalham).
 * Vídeo longo vai em pedaços de até 30 minutos, com 1 minuto repetido entre eles para não perder frase na emenda.
 */
export async function escolherNaTranscricao(s:Settings, cues:Cue[], o:{limite:number;min:number;max:number;tema:string;prompt:string;ini:number;fim:number;duracao:number}, onPct?:(p:number)=>void):Promise<Escolhido[]>{
  const {instrucoesEscolha,textoTranscricao}=await import('./promptCortes');
  const a=o.ini, b=o.fim>0?Math.min(o.fim,o.duracao):o.duracao;
  const n=Math.max(1,Math.ceil((b-a)/1800)), tam=(b-a)/n;
  const quantos=Math.min(20,Math.ceil(o.limite*1.4/n)+(n>1?1:0));
  const todos:any[]=[]; let erro:unknown=null;
  for(let i=0;i<n;i++){
    const de=a+i*tam, ate=Math.min(b,de+tam+(i<n-1?60:0));
    const parte=cues.filter(c=>c.start>=de-0.01&&c.end<=ate+0.01);
    onPct?.(Math.round(i/n*100));
    if(parte.length<4) continue;
    const texto=instrucoesEscolha({quantos,min:o.min,max:o.max,tema:o.tema,prompt:o.prompt,de,ate},textoTranscricao(parte).slice(0,400000));
    for(let t=0;;t++){
      try{ todos.push(...await avaliar(s,[],parte,{prompt:o.prompt,tema:o.tema,escolha:texto})); break; }
      catch(e){
        const {esperaGemini}=await import('./gemini'); const ms=esperaGemini(e,t+2);
        if(ms==null){ erro=e; break; }
        await new Promise(r=>setTimeout(r,ms));
      }
    }
  }
  if(!todos.length&&erro) throw erro;
  return validarEscolhidos(todos,cues,{min:o.min,max:o.max,duracao:o.duracao,ini:a,fim:b});
}
