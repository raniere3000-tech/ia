// Avaliação dos cortes com Claude (chave do próprio usuário, chamada direto do navegador).
import Anthropic from '@anthropic-ai/sdk';
import { betaZodOutputFormat } from '@anthropic-ai/sdk/helpers/beta/zod';
import { z } from 'zod';
import type { Cue } from './captions';
import type { Candidate } from './analyze';

export const CLAUDE_MODEL = 'claude-opus-5-5';

const Avaliacao = z.object({
  cortes: z.array(z.object({
    id: z.string(),
    gancho: z.number(), fluxo: z.number(), valor: z.number(), tendencia: z.number(),
    titulo: z.string(), motivo: z.string(), inicio: z.number(), fim: z.number(),
  })),
});
export type AvaliacaoIA = z.infer<typeof Avaliacao>['cortes'][number];

function client(key:string){ return new Anthropic({apiKey:key,dangerouslyAllowBrowser:true}); }

export async function testarChaveClaude(key:string){
  await client(key).models.retrieve(CLAUDE_MODEL);
}

const tt = (s:number)=>`${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}`;

export async function avaliarComIA(key:string, cands:(Candidate&{id:string})[], cues:Cue[], opts:{prompt:string;tema:string;frames?:Record<string,string[]>}){
  const content:Anthropic.Beta.BetaContentBlockParam[] = [];
  content.push({type:'text',text:
`Você avalia trechos de vídeos de qualquer nicho para virar cortes curtos (TikTok, Reels, Shorts). Adapte gancho, fluxo, valor e tendência ao tema e ao contexto do vídeo.
${opts.tema?`Tema informado pelo usuário: ${opts.tema}\n`:''}${opts.prompt?`Pedido do usuário (priorize trechos que atendem a isto): ${opts.prompt}\n`:''}
Para cada candidato abaixo você recebe início, fim, a transcrição do trecho e as notas dos sinais de áudio (0 a 99).${opts.frames?' Também recebe quadros do vídeo de cada candidato.':''}
Dê notas de 0 a 99 para gancho (os 3 primeiros segundos prendem?), fluxo (tem começo, meio e fim?), valor (diverte, surpreende ou ensina?) e tendência (tem a ver com o que está em alta?).
Escreva um título em português de até 60 caracteres e o motivo em 1 frase.
Sugira ajustes de início/fim de até 3 segundos se melhorarem o gancho; senão repita os valores recebidos.
Seja honesto: trechos fracos devem receber notas baixas. Responda para todos os candidatos, usando o mesmo id.`});
  for(const c of cands){
    const fala = cues.filter(q=>q.end>c.inicio&&q.start<c.fim).map(q=>q.text).join(' ').slice(0,1500) || '(sem fala transcrita)';
    content.push({type:'text',text:`\n--- Candidato ${c.id} | início ${c.inicio.toFixed(1)}s (${tt(c.inicio)}) | fim ${c.fim.toFixed(1)}s (${tt(c.fim)})\nSinais de áudio: gancho ${c.notas.gancho}, energia ${c.notas.valor}\nTranscrição: ${fala}`});
    for(const f of opts.frames?.[c.id]||[]) content.push({type:'image',source:{type:'base64',media_type:'image/jpeg',data:f.split(',')[1]}});
  }
  const res = await client(key).beta.messages.parse({
    model: CLAUDE_MODEL,
    max_tokens: 16000,
    betas: ['server-side-fallback-2026-07-01'],
    fallbacks: 'default',
    messages: [{role:'user',content}],
    output_config: { format: betaZodOutputFormat(Avaliacao) },
  } as any);
  if(res.stop_reason==='refusal') throw new Error('A IA recusou avaliar este conteúdo.');
  const parsed = (res as any).parsed_output as z.infer<typeof Avaliacao> | null;
  if(!parsed) throw new Error('A resposta da IA veio incompleta. Tente novamente.');
  return parsed.cortes;
}

export function erroAmigavel(e:unknown){
  if(e instanceof Anthropic.AuthenticationError) return 'Chave da Claude inválida. Confira em Configurações.';
  if(e instanceof Anthropic.PermissionDeniedError) return 'A chave da Claude não tem permissão para este modelo.';
  if(e instanceof Anthropic.RateLimitError) return 'Limite de uso da Claude atingido. Aguarde um pouco e tente de novo.';
  if(e instanceof Anthropic.APIConnectionError) return 'Não foi possível conectar à Claude. Verifique sua internet.';
  if(e instanceof Anthropic.APIError) return 'Erro da Claude: '+e.message;
  return e instanceof Error ? e.message : String(e);
}
