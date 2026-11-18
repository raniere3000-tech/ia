// Parte Live: grava a live em blocos, o Agente 1 acha os melhores momentos, editor e diretor conferem, e o aprovado posta na hora.
import { api, type CfgSrv } from './api';

export type CfgLive={bloco_min:number;cortes_por_bloco:number;nota_min:number;max_horas:number;max_posts:number;intervalo_min:number;redes:string[];postar:boolean};
export type BlocoLive={n:number;estado:'na_fila'|'cortando'|'feito'|'erro';ini:number;cortes:string[];msg:string};
export type CorteLive={id:string;titulo:string;status:string;nota:number|null;post:string;quando:number|null;links:Record<string,string>};
export type Live={id:string;link:string;titulo:string;canal_nome:string;estado:'gravando'|'terminando'|'terminada'|'erro';inicio:number;fim:number|null;
  motivo_fim?:string;erro:string;cfg:CfgLive;blocos:BlocoLive[];postados:number;direitos:{origem:string};log:{t:number;tipo:string;texto:string}[];cortes:CorteLive[];gravando_bloco?:number;altura?:number;gravando_desde?:number};
export type VerLive={config:CfgLive;lives:Live[];ativa:string;esteira:boolean;ocupando?:string};
export const verLive=(c:CfgSrv)=>api<VerLive>(c,'GET','/api/v1/live');
export const salvarCfgLive=(c:CfgSrv,d:Partial<CfgLive>)=>api<CfgLive>(c,'PUT','/api/v1/live/config',d);
export const comecarLive=(c:CfgSrv,d:Partial<CfgLive>&{link:string;origem:string})=>api<Live>(c,'POST','/api/v1/live/comecar',d);
export const pararLive=(c:CfgSrv,id:string)=>api<Live>(c,'POST',`/api/v1/live/${id}/parar`,{});
