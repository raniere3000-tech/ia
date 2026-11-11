// Escolhe qual IA avalia os cortes (Gemini ou Claude), conforme as chaves salvas.
import type { Settings } from '../state';
import type { Cue } from './captions';
import type { Candidate } from './analyze';
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
