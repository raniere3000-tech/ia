// Diretor de cena: mapa de palco (visto de cima), animatic leve e prévia A/B com quadros desenhados de verdade pelo servidor.
import { api, type CfgSrv, type Plano } from './api';

export type Ator={id:string;nome:string;x:number;x_fim:number;cor:string;fala:boolean};
export type CenaMapa={id:string;titulo:string;cenario:string;atores:Ator[];eixo:[number,number]|null;planos:{id:string;plano:Plano['plano'];personagem?:string;peso?:number}[]};
export type AvisoDiretor={tipo:string;severidade:string;cena:string;plano?:string;descricao:string;correcao:string};
export type Animatic={asset:string;versao:string;duracao:number;segundos_para_fazer:number;fps:number;criado:number;desatualizado?:boolean};
export type Mapa={estilo:string;formato:string;cenas:CenaMapa[];avisos:AvisoDiretor[];animatic:Animatic|null};
export type QuadroAB={plano:Plano['plano'];personagem:string;t:number;img:string};
export type EstadoDiretor={id:string;status:string;etapa:string;progresso:number;erro:string|null;resultado:(Animatic|{a:QuadroAB[];b:QuadroAB[]})|null};

export const obterMapa=(cfg:CfgSrv,pid:string)=>api<Mapa>(cfg,'GET',`/api/v1/projetos/${pid}/diretor`);
export const pedirAnimatic=(cfg:CfgSrv,pid:string)=>api<{job:string;status:string}>(cfg,'POST',`/api/v1/projetos/${pid}/animatic`,{});
export const pedirAB=(cfg:CfgSrv,pid:string,i:number,a:Partial<Plano>[],b:Partial<Plano>[])=>api<{job:string;status:string}>(cfg,'POST',`/api/v1/projetos/${pid}/cenas/${i}/previa-ab`,{a,b});
export const estadoDiretor=(cfg:CfgSrv,id:string)=>api<EstadoDiretor>(cfg,'GET','/api/v1/diretor/'+id);

/** Espera um trabalho do diretor terminar (a fila do celular faz um trabalho pesado por vez). */
export async function esperar(cfg:CfgSrv,id:string,onEtapa:(e:EstadoDiretor)=>void,parar:()=>boolean):Promise<EstadoDiretor>{
  for(;;){
    const e=await estadoDiretor(cfg,id); onEtapa(e);
    if(['concluido','falhou','cancelado'].includes(e.status)||parar()) return e;
    await new Promise(r=>setTimeout(r,1500));
  }
}
