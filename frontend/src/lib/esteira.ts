// Esteira dos 5 agentes (editor + diretor com nota 0-100), capacidades, referências virais e programação diária do Agente 2.
import { api, type CfgSrv } from './api';

export type Parte={pontos:number;maximo:number;nome:string};
export type Achado={category?:string;categoria?:string;severity?:string;severidade?:string;evidence?:string;evidencia?:string;instruction?:string;instrucao?:string;
  target_agent?:string;alvo?:string;time_start_ms?:number|null;ini_ms?:number|null;time_end_ms?:number|null;fim_ms?:number|null;scene?:string;cena?:string;nature?:string;natureza?:string};
export type Relatorio={id:string;run:string;modalidade:'creative_preedit'|'final_release';ref:string;sha256:string;score:number;passed:boolean;blocking_findings:Achado[];
  partes:Record<string,Parte>;attempts_used:number|null;attempts_limit:number|null;reference_set_id:string|null;evaluator_version:string;policy_version:string;
  created_at:number;findings:Achado[];avisos?:string[];referencias_resumo?:Record<string,unknown>|null;medidas?:Record<string,unknown>};
export type Contador={avaliacoes:number;correcoes:number;limite:number;estado:string};
export type Execucao={id:string;origem:string;ref:string;titulo:string;estado:string;nome_estado:string;agente:string;etapa:string;atualizado:number;
  nota:number|null;aprovado:boolean|null;contadores:Record<string,Contador>;tentativas_tecnicas:number};
export type PainelEsteira={ligado:boolean;politica:{nota_minima:number;max_correcoes:number;versao:string;pesos:Record<string,Record<string,number>>;nomes:Record<string,string>};
  contagem:Record<string,number>;nomes_estado:Record<string,string>;execucoes:Execucao[]};
export type DetalheExecucao=Execucao&{relatorios:Relatorio[];planos:{versao:number;hash:string;motivo:string;arquivo_sha:string|null;criado:number}[];
  etapas:Record<string,Contador>;arquivo:string|null;sha256:string|null;dados:Record<string,unknown>};

export const lerEsteira=(c:CfgSrv)=>api<PainelEsteira>(c,'GET','/api/v1/pipeline');
export const ligarEsteira=(c:CfgSrv,ligado:boolean)=>api<{ligado:boolean}>(c,'PUT','/api/v1/pipeline/chave',{ligado});
export const verExecucao=(c:CfgSrv,id:string)=>api<DetalheExecucao>(c,'GET','/api/v1/pipeline/jobs/'+id);
export const decidirExecucao=(c:CfgSrv,id:string,decisao:'aprovar'|'cancelar',motivo:string)=>api<DetalheExecucao>(c,'POST',`/api/v1/pipeline/jobs/${id}/manual-review`,{decisao,motivo});
export const verRelatorio=(c:CfgSrv,id:string)=>api<Relatorio>(c,'GET','/api/v1/quality/reports/'+id);

export type Capacidade={id:string;nome:string;agentes:string[];tipo:string;uso:string;estado:string;versao?:string;detalhe?:string;fonte?:string;obrigatorio?:boolean;opcional?:boolean};
export const lerCapacidades=(c:CfgSrv,conferir=false)=>api<{capacidades:Capacidade[];conferido:number;regra:string}>(c,'GET','/api/v1/capabilities'+(conferir?'?conferir=1':''));
export type Referencias={id:string;tema:string;plataforma:string;capturado:number;origem:string;aviso:string;
  resumo:{n:number;estado:string;mensagem?:string;duracao_mediana?:number|null;views_dia_mediana?:number|null;seus_videos_duracao?:{estado:string;mensagem:string;melhor?:string}};
  itens:{titulo:string;url?:string;views:number;dur:number|null;views_dia:number|null;publicado?:string;fonte:string;licenca:string}[]};
export const lerReferencias=(c:CfgSrv,tema:string,plataforma='youtube',novo=false)=>
  api<Referencias>(c,'GET',`/api/v1/viral/references?topic=${encodeURIComponent(tema)}&platform=${plataforma}${novo?'&refresh=1':''}`);

// ---- Agente 2: programação diária
export type Modo='fixed'|'automatic'|'mixed';
export type Agenda={id:string;version:number;account_id:string;platform:string;timezone:string;mode:Modo;enabled:boolean;weekly_rules:Record<string,string[]>;
  flex_slots_per_day:number;automatic_window:{start:string;end:string};minimum_gap_minutes:number;missed_slot_policy:'next_slot'|'publish_when_online'|'manual_review';
  max_delay_minutes:number;selection_policy:'oldest_approved'|'best_score';exceptions:Record<string,'pausado'|string[]>;meta_semana?:number;nome_rede?:string};
export type ConfigAgenda=Omit<Agenda,'id'|'version'|'meta_semana'|'nome_rede'>;
export type Previa={config:Agenda;total:number;por_rede:Record<string,number>;avisos:string[];dias:{data:string;dia:string;excecao:string;horarios:{hora:string;tipo:string;utc:number;offset:string}[]}[]};
export type Slot={id:string;agenda:string;conta:string;rede:string;data_local:string;hora_local:string;quando_utc:number;tipo:string;estado:string;ref:string|null;post:string|null;motivo:string|null;titulo?:string};
export type Metricas={data:string;por_rede:Record<string,{meta:number;publicados:number;agendados:number;livres:number;falhas:number;perdidos:number}>;disponiveis:Record<string,number>};

export const listarAgendas=(c:CfgSrv)=>api<{agendas:Agenda[];redes:Record<string,string>;dias:string[];esteira:boolean}>(c,'GET','/api/v1/agent2/schedules');
export const criarAgenda=(c:CfgSrv,d:Partial<ConfigAgenda>)=>api<Agenda>(c,'POST','/api/v1/agent2/schedules',d);
export const mudarAgenda=(c:CfgSrv,id:string,d:Partial<ConfigAgenda>&{version:number})=>api<Agenda>(c,'PATCH','/api/v1/agent2/schedules/'+id,d);
export const apagarAgenda=(c:CfgSrv,id:string)=>api(c,'DELETE','/api/v1/agent2/schedules/'+id);
export const previaAgenda=(c:CfgSrv,d:Partial<ConfigAgenda>)=>api<Previa>(c,'POST','/api/v1/agent2/preview',d);
export const listarSlots=(c:CfgSrv,rede='')=>api<{slots:Slot[];agora:number}>(c,'GET','/api/v1/agent2/slots'+(rede?'?platform='+rede:''));
export const cancelarSlot=(c:CfgSrv,id:string)=>api<Slot>(c,'PATCH','/api/v1/agent2/slots/'+id,{acao:'cancelar'});
export const rodarAgenda=(c:CfgSrv)=>api<{agendados:number}>(c,'POST','/api/v1/agent2/run',{});
export const metricasAgenda=(c:CfgSrv,data='')=>api<Metricas>(c,'GET','/api/v1/agent2/metrics'+(data?'?date='+data:''));
