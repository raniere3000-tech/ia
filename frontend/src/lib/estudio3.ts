// Storyboard visual (3ª porta de aprovação), Gameplay Narrativa e modos Rápido/Caprichado: cliente da API do servidor.
import { api, type CfgSrv } from './api';

export type QuadroSB={asset:string;t:number;plano:string;personagem:string;angulo:string};
export type CenaSB={id:string;n:number;titulo:string;hash:string;quadros:QuadroSB[];quadros_desatualizados:boolean;status:'aprovada'|'pronta_para_conferir'|'mudou_depois_de_aprovar'|'sem_miniatura';ja_aprovada_antes?:boolean;camera:string;duracao:number|null;personagem:string;estilo:string;aprovada_por:string};
export type EstadoSB={ativa:boolean;cenas:CenaSB[];todas_aprovadas:boolean;versao:string;faltam:number[];aviso_final:string};
export const lerStoryboard=(cfg:CfgSrv,pid:string)=>api<EstadoSB>(cfg,'GET',`/api/v1/projetos/${pid}/storyboard-visual`);
export const gerarQuadros=(cfg:CfgSrv,pid:string,cenas?:string[])=>api<{job:string;status:string}>(cfg,'POST',`/api/v1/projetos/${pid}/storyboard-visual/quadros`,{cenas});
export const aprovarQuadros=(cfg:CfgSrv,pid:string,cenas?:string[])=>api<EstadoSB>(cfg,'POST',`/api/v1/projetos/${pid}/storyboard-visual/aprovar`,{cenas});
export const corrigirCena=(cfg:CfgSrv,pid:string,cena:string,mudancas:Record<string,unknown>)=>api<EstadoSB&{job:string}>(cfg,'POST',`/api/v1/projetos/${pid}/storyboard-visual/corrigir`,{cena,mudancas});

export type Evento={id:string;tipo:'mudanca_de_cena'|'pico_de_audio'|'fala_forte';t:number;fim:number;descricao:string;confianca:number;observado:boolean;visual?:string;texto?:string};
export type Gancho={tipo:string;abertura_falada:string;texto_na_tela:string;primeiro_quadro_t:number;eventos:string[];justificativa:string};
export type Destaque={id:string;ini:number;fim:number;eventos:string[];score:number;confianca:number;porque:string;ganchos:Gancho[];ganchos_origem:'ia'|'regras';ganchos_aviso:string};
export type Analise={id:string;titulo:string;historia:string;historias:Record<string,string>;fonte:string;direitos:{origem:string;nota:string};duracao:number;analise:'parcial'|'completa';analise_motivo:string;
  sinais:{n_cenas:number;n_picos:number;n_falas:number;audio:boolean};eventos:Evento[];destaques:Destaque[];aviso:string;tem_video:boolean};
export type ResumoAnalise={id:string;titulo:string;criado:number;analise:string;destaques:number;fonte:string};
export const listarAnalises=(cfg:CfgSrv)=>api<{analises:ResumoAnalise[];historias:Record<string,string>}>(cfg,'GET','/agente/gameplay');
export const lerAnalise=(cfg:CfgSrv,id:string)=>api<Analise>(cfg,'GET','/agente/gameplay/'+id);
export const pedirAnalise=(cfg:CfgSrv,d:{link:string;origem:string;nota:string;titulo:string;historia:string;usar_ia:boolean})=>api<{job:string}>(cfg,'POST','/agente/gameplay/analisar',d);
export const novaHistoria=(cfg:CfgSrv,id:string,historia:string)=>api<Analise>(cfg,'POST',`/agente/gameplay/${id}/historia`,{historia,usar_ia:true});
export const cortarDestaque=(cfg:CfgSrv,d:{gid:string;destaque:string;gancho:Gancho|null;ini:number;fim:number;modelo?:string;estilo?:string;modo?:string})=>api<{job:string}>(cfg,'POST','/agente/gameplay/cortar',d);
export const compararModos=(cfg:CfgSrv,d:{gid:string;destaque:string;estilo?:string})=>api<{job:string}>(cfg,'POST','/agente/gameplay/comparar',d);
export type Comparacao=Record<string,{nome:string;segundos_de_render:number;tamanho_bytes:number;operacoes:string[];volume:{lufs:number;pico_dbfs:number|null}|null;duracao:number}>;
export type Modo={nome:string;desc:string;estimativa:{segundos:number|null;motivo:string;amostras?:number}};
export const lerModos=(cfg:CfgSrv)=>api<{modos:Record<string,Modo>}>(cfg,'GET','/agente/modos');
export const mmss=(t:number)=>`${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`;
