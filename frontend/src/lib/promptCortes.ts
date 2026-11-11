// Texto enviado à IA (Claude ou Gemini) para avaliar os candidatos a corte.
import type { Cue } from './captions';
import type { Candidate } from './analyze';

export type OptsIA = {prompt:string;tema:string;frames?:Record<string,string[]>};
export type AvaliacaoIA = {id:string;gancho:number;fluxo:number;valor:number;tendencia:number;titulo:string;motivo:string;inicio:number;fim:number;gancho_texto?:string};

const tt = (s:number)=>`${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}`;

export const AJUSTE_MAX = 8;   // segundos que a IA pode mover o início/fim para fechar a frase

export function instrucoes(opts:OptsIA){
  return `Você é um editor sênior de vídeos curtos (TikTok, Reels, Shorts) de qualquer nicho. Abaixo estão trechos candidatos de um mesmo vídeo; compare uns com os outros e dê notas que separem bem os bons dos fracos.
${opts.tema?`Tema informado pelo usuário: ${opts.tema}\n`:''}${opts.prompt?`Pedido do usuário (priorize trechos que atendem a isto): ${opts.prompt}\n`:''}
Cada candidato traz início, fim, os sinais de áudio (0 a 99) e as falas com horário, inclusive algumas falas logo antes e logo depois (marcadas com "fora").${opts.frames?' Também traz quadros do vídeo.':''}

O que faz um bom corte:
- Quem nunca viu o vídeo entende e se importa, sem precisar do contexto anterior.
- Tem gancho, desenvolvimento e um fechamento (piada, lição, revelação, resposta, reação forte).
- É concreto: números, opinião forte, história, erro e aprendizado, antes e depois, surpresa, humor, emoção.
- Corte fraco: abertura, despedida, propaganda, "se inscreve no canal", enrolação, repetição, frase solta que depende do que veio antes, ou trecho em que a fala diz que a imagem caiu ou travou.
- Não penalize um trecho só porque o assunto é polêmico ou sensível; avalie só a qualidade como corte.

Notas de 0 a 99:
- gancho: os 2 ou 3 primeiros segundos fazem a pessoa parar de rolar? Abertura com "e", "mas", "então", "aí", "porque", "tipo", "né", "sim", "isso", resposta de uma palavra ou pronome sem a pessoa apresentada ("ele", "ela") é gancho fraco.
- fluxo: começa no início de uma frase e termina depois do fechamento, sem cortar no meio?
- valor: diverte, surpreende, emociona ou ensina algo que pouca gente sabe?
- tendência: tem a ver com o que está em alta e é algo que a pessoa mandaria para um amigo?
Espalhe as notas: o melhor candidato costuma ficar entre 80 e 95, e os fracos abaixo de 50. Seja honesto.

Limites do corte (inicio e fim, em segundos do vídeo):
- O início deve ser o começo de uma frase que se entende sozinha. Se o trecho depende da frase anterior, volte para incluí-la. Pule enrolação antes do ponto principal.
- O fim deve ser o fim da frase que fecha a ideia, sem deixar o começo da próxima.
- Use os horários das falas e mova no máximo ${AJUSTE_MAX} segundos em relação ao recebido. Se já estiver bom, repita os valores.

Escreva também:
- titulo: título em português de até 60 caracteres para o post.
- gancho_texto: frase curta de 3 a 7 palavras para aparecer escrita no topo do vídeo, que faça parar de rolar (promessa, curiosidade, número ou tensão tirados do próprio trecho). Sem hashtag, sem emoji, sem aspas, sem inventar nada. Não repita a primeira fala; transforme em manchete.
- motivo: 1 frase explicando a nota com base no que realmente é dito.
Não invente fatos que não estejam nas falas. Responda para todos os candidatos, usando o mesmo id.`;
}

export function textoCandidato(c:Candidate&{id:string},cues:Cue[]){
  const perto = cues.filter(q=>q.end>c.inicio-AJUSTE_MAX&&q.start<c.fim+AJUSTE_MAX);
  const linhas = perto.map(q=>`[${q.start.toFixed(1)}s-${q.end.toFixed(1)}s]${q.end<=c.inicio||q.start>=c.fim?' (fora)':''} ${q.text}`).join('\n').slice(0,2500);
  return `\n--- Candidato ${c.id} | início ${c.inicio.toFixed(1)}s (${tt(c.inicio)}) | fim ${c.fim.toFixed(1)}s (${tt(c.fim)})\nSinais de áudio: gancho ${c.notas.gancho}, energia ${c.notas.valor}\nFalas:\n${linhas||'(sem fala transcrita)'}`;
}
