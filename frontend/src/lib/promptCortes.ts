// Texto enviado à IA (Claude ou Gemini) para avaliar os candidatos a corte.
import type { Cue } from './captions';
import type { Candidate } from './analyze';

export type OptsIA = {prompt:string;tema:string;frames?:Record<string,string[]>};
export type AvaliacaoIA = {id:string;gancho:number;fluxo:number;valor:number;tendencia:number;titulo:string;motivo:string;inicio:number;fim:number};

const tt = (s:number)=>`${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}`;

export function instrucoes(opts:OptsIA){
  return `Você avalia trechos de vídeos de qualquer nicho para virar cortes curtos (TikTok, Reels, Shorts). Adapte gancho, fluxo, valor e tendência ao tema e ao contexto do vídeo.
${opts.tema?`Tema informado pelo usuário: ${opts.tema}\n`:''}${opts.prompt?`Pedido do usuário (priorize trechos que atendem a isto): ${opts.prompt}\n`:''}
Para cada candidato abaixo você recebe início, fim, a transcrição do trecho e as notas dos sinais de áudio (0 a 99).${opts.frames?' Também recebe quadros do vídeo de cada candidato.':''}
Dê notas de 0 a 99 para gancho (os 3 primeiros segundos prendem?), fluxo (tem começo, meio e fim?), valor (diverte, surpreende ou ensina?) e tendência (tem a ver com o que está em alta?).
Escreva um título em português de até 60 caracteres e o motivo em 1 frase.
Sugira ajustes de início/fim de até 3 segundos se melhorarem o gancho; senão repita os valores recebidos.
Seja honesto: trechos fracos devem receber notas baixas. Responda para todos os candidatos, usando o mesmo id.`;
}

export function textoCandidato(c:Candidate&{id:string},cues:Cue[]){
  const fala = cues.filter(q=>q.end>c.inicio&&q.start<c.fim).map(q=>q.text).join(' ').slice(0,1500) || '(sem fala transcrita)';
  return `\n--- Candidato ${c.id} | início ${c.inicio.toFixed(1)}s (${tt(c.inicio)}) | fim ${c.fim.toFixed(1)}s (${tt(c.fim)})\nSinais de áudio: gancho ${c.notas.gancho}, energia ${c.notas.valor}\nTranscrição: ${fala}`;
}
