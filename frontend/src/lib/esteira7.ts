import { api, type CfgSrv } from './api';

/** Esteira obrigatória dos 7 agentes (GET/PUT /api/v1/esteira/...): um registro por vídeo, uma linha por etapa, com prova e tempo medido. */
export type EtapaEsteira={etapa:string;nome:string;agente:string;estado:string;nome_estado:string;inicio:number|null;fim:number|null;
  segundos_ativos:number|null;segundos_fila:number|null;tentativas:number;correcoes:number;recibo:Record<string,unknown>|null;entrada_sha:string|null;
  saida_sha:string|null;erro:string|null;motivo:string|null;executor:string|null;atualizado:number};
export type VideoEsteira={id:string;origem:'corte'|'render';ref:string;titulo:string;ordem_id:string|null;run:string|null;estado:string;etapa_atual:string;
  motivo:string;criado:number;atualizado:number;etapas:EtapaEsteira[];progresso:number;segundos_total:number;politica:Record<string,unknown>;
  historico?:{n:number;etapa:string;estado:string;detalhe:Record<string,unknown>;t:number}[]};
export type Politica={completa:boolean;capa_obrigatoria:boolean;liberacao_automatica:boolean;versao:number};
export type ResumoEsteira={por_estado:Record<string,number>;por_etapa:Record<string,number>;nomes_etapa:Record<string,string>;politica?:Politica};
export type ItemRecuperacao={video:string;origem:string;ref:string;titulo:string;registrado:boolean;estado:string;falta:string|null;acao:string|null;motivo:string;feito?:string};
export type Diagnostico={politica:Politica;esteira_ligada:boolean;coordenador:{modo?:string;exigir_liberacao?:boolean;liberacao_efetiva?:boolean;erro?:string};
  central:string|null;agente6?:{modo:string;criar_sozinho:boolean};resumo:ResumoEsteira;incompletos:ItemRecuperacao[]};

const B='/api/v1/esteira';
const idUrl=(id:string)=>id.replace(':','-');
export const lerEsteira=(c:CfgSrv,estado='',limite=30)=>api<{resumo:ResumoEsteira;politica:Politica;videos:VideoEsteira[]}>(c,'GET',`${B}?estado=${estado}&limite=${limite}`);
export const lerTimeline=(c:CfgSrv,id:string)=>api<VideoEsteira>(c,'GET',`${B}/execucoes/${idUrl(id)}/timeline`);
export const avancarVideo=(c:CfgSrv,id:string)=>api<VideoEsteira>(c,'POST',`${B}/execucoes/${idUrl(id)}/avancar`,{});
export const lerDiagnostico=(c:CfgSrv)=>api<Diagnostico>(c,'GET',`${B}/diagnostico`);
export const salvarPolitica=(c:CfgSrv,d:Partial<Politica>)=>api<Politica>(c,'PUT',`${B}/politica`,d);
export const simularRecuperacao=(c:CfgSrv)=>api<{itens:ItemRecuperacao[];total:number;nota:string}>(c,'POST',`${B}/conciliar/simular`,{});
export const recuperar=(c:CfgSrv,videos:string[])=>api<{feitos:ItemRecuperacao[];total:number}>(c,'POST',`${B}/conciliar`,{confirmar:true,videos});

export const AGENTE_ETAPA:Record<string,string>={agente1:'A1',agente2:'A2',agente3:'A3',agente4:'A4',agente5:'A5',agente6:'A6',agente7:'A7'};
/** Cor da etiqueta de cada estado de etapa (as classes já existem no site: ok, warn, bad, info). */
export const COR_ESTADO:Record<string,string>={concluida:'ok',pulada_justificada:'',executando:'info',corrigindo:'info',na_fila:'info',pendente:'',
  aguardando_dependencia:'',aguardando_usuario:'warn',revisao_manual:'warn',aguardando_recurso:'bad',falhou:'bad',reprovada:'warn',cancelada:''};
export const ESTADO_VIDEO:Record<string,[string,string]>={em_andamento:['Em andamento','info'],corrigindo:['Corrigindo','info'],aguardando_voce:['Esperando você','warn'],
  bloqueado:['Bloqueado','bad'],publicado:['Publicado','ok'],cancelado:['Cancelado',''],descartado:['Descartado na avaliação','']};
export const ESTADO_REAL:Record<string,[string,string]>={ativo:['Trabalhando','info'],na_fila:['Na fila','info'],aguardando_voce:['Esperando você','warn'],
  bloqueado:['Bloqueado','bad'],aguardando_etapa:['Esperando a etapa anterior',''],sem_demanda:['Sem trabalho agora','']};
