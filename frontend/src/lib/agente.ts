// Cliente dos agentes que rodam no servidor (celular/PC): agente de cortes e agente de postagem.
import type { Rede } from './agenda';

export type Template = {legenda:'destaque'|'simples'|'caixa'|'nenhuma';cor:string;cor_destaque:string;maiusculas:boolean;tamanho:'pequeno'|'medio'|'grande';legenda_pos:'baixo'|'meio';enquadramento:'desfoque'|'cortar';zoom:number;gancho:boolean;gancho_pos:'topo'|'alto';tarja_topo:string;tarja_base:string;cor_tarja:string;cor_tarja_texto:string;qualidade:number};
export type Faixa = {dia:number;hora:string};
export type ConfigAgente = {
  cortes:{ligado:boolean;nichos:string[];proibidos:string[];min_views:number;idioma:string;regiao:string;por_semana:number;por_video:number;dur_min:number;dur_max:number;nota_min:number;video_min:number;video_max:number;dias_video:number;hora_ini:number;hora_fim:number;template:Template;variar:string[]};
  postagem:{ligado:boolean;redes:Rede[];faixas:Faixa[];youtube_privacidade:string;tiktok_modo:string;antecedencia:number};
  email:{para:string;de:string;smtp:string;porta:number;anexar:boolean;avisos:Record<string,boolean>};
  orcamento:{teto:number;dolar:number;preco_texto:number;preco_audio:number;preco_saida:number};
};
export type Canal = {id:string;nome:string;status:'sugerido'|'aprovado'|'recusado';motivo:string;nicho:string;media:number;videos:number;inscritos:number;exemplo:string};
export type CorteAgente = {id:string;video:string;titulo:string;gancho:string;hashtags:string[];motivo:string;nota:number;ini:number;fim:number;criado:number;status:'pronto'|'agendado'|'postado'|'descartado';post:string;quando?:number;origem:string;origem_titulo:string;canal_nome:string;variacoes:string[];fala:string;tamanho:number;email:boolean;links?:Record<string,string>;erros?:Record<string,string>;views?:number|null};
export type VisaoAgente = {
  config:ConfigAgente; chaves:{gemini:boolean;youtube:boolean;email_senha:boolean}; canais:Canal[]; cortes:CorteAgente[];
  log:{t:number;tipo:string;texto:string}[]; gasto:{reais:number;chamadas:number}; semana:number; horarios:Record<string,{n:number;views:number}>;
  atual:{etapa:string;pct:number;ocupado:boolean}; opcoes:{nichos:string[];proibidos:string[];variacoes:Record<string,string>;motivos:string[]}; ffmpeg:boolean; agora:number;
};
type Parcial<T> = {[K in keyof T]?:T[K] extends (infer _U)[]?T[K]:T[K] extends object?Parcial<T[K]>:T[K]};

type Cfg = {servidor:string;servidorToken:string};
async function chamar<T=VisaoAgente>(cfg:Cfg,metodo:string,caminho:string,corpo?:unknown):Promise<T>{
  if(!cfg.servidor) throw new Error('Ligue o servidor primeiro (Chaves e ajustes > Cortes direto pelo link).');
  const h:Record<string,string>={}; if(cfg.servidorToken) h['X-Token']=cfg.servidorToken;
  if(corpo!==undefined) h['Content-Type']='application/json';
  let r:Response;
  try{ r=await fetch(cfg.servidor+caminho,{method:metodo,headers:h,body:corpo!==undefined?JSON.stringify(corpo):undefined}); }
  catch{ throw new Error('Não consegui falar com o servidor. Ele está aberto? (No celular: bash iniciar-termux.sh link)'); }
  const j=await r.json().catch(()=>({}));
  if(r.status===404) throw new Error('O servidor está em uma versão antiga, sem os agentes. No celular, rode "git pull" na pasta do projeto e inicie o servidor de novo.');
  if(!r.ok) throw new Error(j.detail||`O servidor respondeu com erro ${r.status}.`);
  return j as T;
}

export const verAgente=(c:Cfg)=>chamar(c,'GET','/agente');
export const salvarAgente=(c:Cfg,parte:Parcial<ConfigAgente>)=>chamar(c,'POST','/agente/config',parte);
export const salvarChaves=(c:Cfg,chaves:{gemini?:string;youtube?:string;email_senha?:string})=>chamar(c,'POST','/agente/chaves',chaves);
export const acaoCanal=(c:Cfg,d:{acao:'aprovar'|'recusar'|'remover'|'adicionar';id?:string;link?:string;motivo?:string})=>chamar(c,'POST','/agente/canais',d);
export const rodarAgente=(c:Cfg,oque:'buscar'|'cortar'|'postar'|'link',link?:string)=>chamar<{ok:boolean}>(c,'POST','/agente/rodar',{oque,link});
export const pararAgente=(c:Cfg)=>chamar(c,'POST','/agente/parar',{});
export const testarEmail=(c:Cfg)=>chamar<{ok:boolean}>(c,'POST','/agente/email/teste',{});
export const acaoCorte=(c:Cfg,id:string,acao:'descartar'|'agendar'|'email')=>chamar(c,'POST',`/agente/cortes/${id}/${acao}`,{});
/** Traz o arquivo do corte para o navegador (para ver ou baixar). */
export async function videoDoCorte(c:Cfg,id:string):Promise<Blob>{
  const h:Record<string,string>={}; if(c.servidorToken) h['X-Token']=c.servidorToken;
  const r=await fetch(`${c.servidor}/agente/cortes/${id}/video`,{headers:h}).catch(()=>null);
  if(!r||!r.ok) throw new Error('Não consegui trazer o vídeo do servidor.');
  return r.blob();
}

export const DIAS=['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo'];
export const MOTIVOS:Record<string,string>={meu:'O canal é meu',autorizado:'O dono me autorizou',regra:'O canal tem regra pública que permite cortes'};
