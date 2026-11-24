// Download de vídeos em lote (Publicações): o servidor prepara os arquivos; o site só pede, acompanha e abre o link assinado.
import { chamar, type Cfg } from './agenda';

export type FormatoDownload='pacote'|'zip'|'mp4';
export type CapaDownload='ok'|'ausente'|'desatualizada';
export type ItemDownload={n:number;post:string;nome:string;titulo:string;disponivel:boolean;motivo:string;capa:CapaDownload;tamanho:number;url?:string;preparado?:boolean};
export type EstadoDownload='preparando'|'pronto'|'parcial'|'falhou'|'cancelado';
export type JobDownload={id:string;formato:FormatoDownload;estado:EstadoDownload;total:number;disponiveis:number;preparados:number;bytes_feitos:number;bytes_total:number;
  itens:ItemDownload[];arquivo?:{nome:string;tamanho:number;url:string}|null;erro?:string;falhas:{n:number;nome:string;motivo:string}[];sem_capa:number;criado:number;fim?:number|null};

export const FORMATOS:[FormatoDownload,string,string][]=[
  ['pacote','Pacote completo (ZIP)','Uma pasta por vídeo, com o MP4, a capa aprovada e o texto de publicação de cada rede. Recomendado.'],
  ['zip','ZIP só com vídeos','Todos os MP4 num único arquivo, com os nomes organizados.'],
  ['mp4','MP4 individuais','Um arquivo por vídeo, baixados um de cada vez (no Android, o ZIP costuma ser mais seguro).'],
];

export const criarDownload=(c:Cfg,posts:string[],formato:FormatoDownload)=>chamar<JobDownload>(c,'POST','/api/v1/downloads',{posts,formato});
export const lerDownload=(c:Cfg,id:string)=>chamar<JobDownload>(c,'GET',`/api/v1/downloads/${id}`);
export const cancelarDownload=(c:Cfg,id:string)=>chamar<JobDownload>(c,'POST',`/api/v1/downloads/${id}/cancelar`,{});
export const tentarDeNovo=(c:Cfg,id:string)=>chamar<JobDownload>(c,'POST',`/api/v1/downloads/${id}/tentar-novamente`,{});

/** Endereço completo do link assinado (o servidor devolve só o caminho). */
export const urlDownload=(c:Cfg,caminho:string)=>c.servidor.replace(/\/+$/,'')+caminho;
export const mb=(b:number)=>b>=1024*1024*1024?`${(b/1024/1024/1024).toFixed(2)} GB`:`${Math.max(0.1,b/1024/1024).toFixed(b>=10*1024*1024?0:1)} MB`;
