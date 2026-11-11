// Avaliação dos cortes com Claude (chave do próprio usuário, chamada direto do navegador).
import Anthropic from '@anthropic-ai/sdk';
import { betaZodOutputFormat } from '@anthropic-ai/sdk/helpers/beta/zod';
import { z } from 'zod';
import type { Cue } from './captions';
import type { Candidate } from './analyze';
import { instrucoes, textoCandidato, type OptsIA } from './promptCortes';

export const CLAUDE_MODEL = 'claude-opus-5-5';

const Avaliacao = z.object({
  cortes: z.array(z.object({
    id: z.string(),
    gancho: z.number(), fluxo: z.number(), valor: z.number(), tendencia: z.number(),
    titulo: z.string(), motivo: z.string(), inicio: z.number(), fim: z.number(),
  })),
});

function client(key:string){ return new Anthropic({apiKey:key,dangerouslyAllowBrowser:true}); }

export async function testarChaveClaude(key:string){
  await client(key).models.retrieve(CLAUDE_MODEL);
}

export async function avaliarComIA(key:string, cands:(Candidate&{id:string})[], cues:Cue[], opts:OptsIA){
  const content:Anthropic.Beta.BetaContentBlockParam[] = [{type:'text',text:instrucoes(opts)}];
  for(const c of cands){
    content.push({type:'text',text:textoCandidato(c,cues)});
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

const Posts = z.object({ posts: z.array(z.object({ id: z.string(), legenda: z.string(), hashtags: z.array(z.string()) })) });

/** Legendas de post escritas pela Claude (usado na etapa Postar). */
export async function escreverPostsClaude(key:string, texto:string){
  const res = await client(key).beta.messages.parse({
    model: CLAUDE_MODEL,
    max_tokens: 8000,
    betas: ['server-side-fallback-2026-07-01'],
    fallbacks: 'default',
    messages: [{role:'user',content:texto}],
    output_config: { format: betaZodOutputFormat(Posts) },
  } as any);
  const parsed = (res as any).parsed_output as z.infer<typeof Posts> | null;
  if(!parsed) throw new Error('A resposta da IA veio incompleta. Tente novamente.');
  return parsed.posts;
}
