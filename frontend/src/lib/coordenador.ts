// Agente 7: Coordenador-Geral. Você pede em português, ele propõe um plano, você confirma e ele distribui aos agentes.
import { api, type CfgSrv } from './api';

export type Faltando={campo:string;pergunta:string};
export type Plano={schema:number;intencao:string;parametros:Record<string,unknown>;explicitos:string[];faltando:Faltando[];bloqueios:string[];
  plano:{agente:string;o_que:string}[];memorias_usadas:{id:string;versao:number;texto:string;escopo:string}[];resposta:string;modo:string;
  limites:{correcoes_por_etapa:number;qualidade_minima:number;gasto_max_por_video:string};horarios:string[]};
export type Eta={segundos:number|null;texto:string;depende_de_voce:number;base?:string};
export type Tarefa={id:string;agente:string;agente_nome:string;acao:string;titulo:string;estado:string;deps:string[];job_id:string|null;criado:number;atualizado:number;
  inicio:number|null;fim:number|null;erro:string|null;resultado:Record<string,unknown>;memorias:string[];correcoes:number;
  job?:{status:string;progresso:number;etapa:string;restante_s:number|null}};
export type Evento={id:number;ordem_id:string|null;tarefa_id:string|null;fonte:string;categoria:string;evento:Record<string,unknown>;criado:number;hash:string};
export type ItemConf={item:string;ok:boolean;detalhe:string};
export type CapaOpcao={job:string;id:string;numero:number;versao:number;nota:number;estado:string;layout:string;formato:string;url:string;sha256:string};
export type Aprovacao={id:string;ordem_id:string;ordem_ref:string;tarefa_id:string;origem:string;referencia:string;video_sha256:string;thumbnail_sha256:string|null;
  pacote_hash:string;decisao:'pendente'|'aprovado'|'reprovado';por:string|null;criado:number;decidido:number|null;revogado:number|null;motivo:string|null;
  relatorio:{itens:ItemConf[];titulo:string;ref:string;projeto:string;destino:{redes:string[];quando:number|null};capas_pedidas:number;
    capa_por_rede?:Record<string,{tipo:string;nota:string;estado:string}>};capas?:CapaOpcao[]};
export type Ordem={id:string;ref:string;autor:string;texto:string;plano:Plano;versao_plano:number;status:string;criado:number;atualizado:number;
  tarefas:Tarefa[];aprovacoes:Aprovacao[];eta:Eta;eventos:Evento[];repetido?:boolean};
export type OrdemResumo={id:string;ref:string;texto:string;status:string;intencao:string;resposta:string;criado:number;atualizado:number;
  tarefas:{total:number;concluidas:number;falhas:number;esperando_voce:number};eta:Eta};
export type Memoria={id:string;tipo:string;escopo:string;chave:string;texto:string;dados:Record<string,unknown>;status:'proposta'|'confirmada'|'desativada';
  confianca:number;confirmada_por:string|null;versao:number;criada:number;atualizada:number;origem:string;travada:number;
  versoes?:{versao:number;antes:Record<string,unknown>|null;depois:Record<string,unknown>;motivo:string;autor:string;criado:number}[];
  evidencias?:{evento_id:number|null;feedback_id:string|null;relacao:string;peso:number|null}[]};
export type Resposta={tipo:'resposta'|'ordem'|'memoria';resposta:string;ordem?:Ordem;memoria?:Memoria;via:string;aviso?:string;repetido?:boolean};
export type AgenteInfo={id:string;nome:string;estado:string;atual:{job:string;titulo:string;progresso:number;etapa:string;restante_s:number|null;desde:number}[];
  na_fila:number;feitos_24h?:number;falhas_24h?:number;tempos_medios?:Record<string,{segundos:number;amostras:number}>;
  custo_30d?:{valor:number;moeda:string;registros:number};custo_capas_30d_usd?:number;posts_agendados?:number;ordens_ativas?:number;esperando_voce?:number;modo?:string};
export type Sugestao={id:string;tipo:string;titulo:string;evidencia:Record<string,unknown>;confianca:number|null;proposta:{texto:string;escopo:string;chave:string}};
export type CfgCoord={modo:'supervisionado'|'automatico';exigir_liberacao:boolean;max_videos:number;correcoes_por_etapa:number;qualidade_minima:number;
  usar_ia:boolean;capas_padrao:number;intervalo_horas:number;reposicao_automatica:boolean;reposicao_intervalo_min:number};

const B='/api/v1/coordenador';
export const interpretar=(c:CfgSrv,texto:string,chave='')=>api<Resposta>(c,'POST',`${B}/interpretar`,{texto,chave});
export const lerConversa=(c:CfgSrv)=>api<{mensagens:Evento[]}>(c,'GET',`${B}/conversa?limite=80`);
export const lerOrdens=(c:CfgSrv,status='')=>api<{ordens:OrdemResumo[]}>(c,'GET',`${B}/ordens?status=${status}`);
export const lerOrdem=(c:CfgSrv,id:string)=>api<Ordem>(c,'GET',`${B}/ordens/${id}`);
export const mudarParametros=(c:CfgSrv,id:string,parametros:Record<string,unknown>,versao_plano:number)=>api<Ordem>(c,'POST',`${B}/ordens/${id}/parametros`,{parametros,versao_plano});
export const confirmarOrdem=(c:CfgSrv,id:string,versao_plano:number)=>api<Ordem>(c,'POST',`${B}/ordens/${id}/confirmar`,{versao_plano});
export const acaoOrdem=(c:CfgSrv,id:string,acao:'pausar'|'retomar'|'cancelar')=>api<Ordem>(c,'POST',`${B}/ordens/${id}/${acao}`,{});
export const lerAgentes=(c:CfgSrv)=>api<{agentes:AgenteInfo[];central:string}>(c,'GET',`${B}/agentes`);
export const lerAprovacoes=(c:CfgSrv,estado='')=>api<{aprovacoes:Aprovacao[]}>(c,'GET',`${B}/aprovacoes?estado=${estado}`);
export const decidir=(c:CfgSrv,id:string,d:{decisao:'aprovar'|'reprovar';pacote_hash:string;alvo?:'video'|'capa';comentario?:string;sem_capa?:boolean})=>
  api<{aprovacao:Aprovacao}>(c,'POST',`${B}/aprovacoes/${id}/decidir`,d);
export const escolherCapaPacote=(c:CfgSrv,id:string,v:CapaOpcao,confirmacao=false)=>api<{aprovacao:Aprovacao}>(c,'POST',`${B}/aprovacoes/${id}/capa`,{variante_id:v.id,versao:v.versao,confirmacao});
export const lerMemorias=(c:CfgSrv,status='')=>api<{memorias:Memoria[]}>(c,'GET',`${B}/memorias?status=${status}`);
export const lerMemoria=(c:CfgSrv,id:string)=>api<Memoria>(c,'GET',`${B}/memorias/${id}`);
export const criarMemoria=(c:CfgSrv,d:{texto:string;escopo:string;tipo:string;confirmar:boolean})=>api<Memoria>(c,'POST',`${B}/memorias`,d);
export const acaoMemoria=(c:CfgSrv,id:string,acao:'confirmar'|'desativar'|'reverter',versao?:number)=>api<Memoria>(c,'POST',`${B}/memorias/${id}/${acao}`,versao===undefined?{}:{versao});
export const editarMemoria=(c:CfgSrv,id:string,d:{texto?:string;escopo?:string;travada?:boolean;versao:number})=>api<Memoria>(c,'PATCH',`${B}/memorias/${id}`,d);
export const lerSugestoes=(c:CfgSrv)=>api<{sugestoes:Sugestao[];nota:string}>(c,'GET',`${B}/aprendizado/sugestoes`);
export const acaoSugestao=(c:CfgSrv,id:string,acao:'propor'|'dispensar')=>api<Memoria|{ok:boolean}>(c,'POST',`${B}/aprendizado/sugestoes/${encodeURIComponent(id)}/${acao}`,{});
export const lerEventos=(c:CfgSrv,ordem='')=>api<{eventos:Evento[]}>(c,'GET',`${B}/eventos?ordem=${ordem}&limite=150`);
export const conferirHistorico=(c:CfgSrv)=>api<{ok:boolean;conferidos:number;quebrado_em?:number}>(c,'GET',`${B}/historico/conferir`);
export const lerCfgCoord=(c:CfgSrv)=>api<CfgCoord>(c,'GET',`${B}/config`);
export const salvarCfgCoord=(c:CfgSrv,d:Partial<CfgCoord>)=>api<CfgCoord>(c,'POST',`${B}/config`,d);

export const ESTADO_ORDEM:Record<string,[string,string]>={rascunho:['Faltam dados','warn'],aguardando_confirmacao:['Esperando você confirmar','warn'],em_execucao:['Em andamento',''],
  aguardando_voce:['Esperando você','warn'],pausada:['Pausada',''],concluida:['Concluída','ok'],parcial:['Concluída com falhas','warn'],falhou:['Falhou','bad'],cancelada:['Cancelada','']};
export const ESTADO_TAREFA:Record<string,[string,string]>={pendente:['Na espera',''],executando:['Trabalhando',''],aguardando_voce:['Esperando você','warn'],concluida:['Pronta','ok'],
  falhou:['Falhou','bad'],bloqueada:['Bloqueada','bad'],cancelada:['Cancelada',''],pulada:['Pulada','']};
export const REDES=['youtube','tiktok','instagram','facebook','kwai'];
export const ESCOPOS:[string,string][]=[['global','Tudo'],['plataforma:youtube','Só no YouTube'],['plataforma:tiktok','Só no TikTok'],['plataforma:instagram','Só no Instagram']];
