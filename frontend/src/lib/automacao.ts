// Central de Automação: estoque decide quando os agentes trabalham, linhas de conteúdo do Agente 3, simulação e histórico.
import { api, type CfgSrv } from './api';

export type EstadoCentral='desligada'|'ativa'|'pausada';
export type ConfigCentral={estado:EstadoCentral;modo:'economico'|'equilibrado'|'intensivo'|'personalizado';versao:number;atualizado:number;por:string;
  cortes:{controle_estoque:boolean;minimo:number;alvo:number;busca_horas:number;cooldown_min:number};linhas:{cooldown_min:number}};
export type EstoqueCortes={disponiveis:number;reservados:number;em_producao_previsto:number;taxa_aprovacao:number;taxa_amostra:number;taxa_estimada:boolean;
  efetivo:number;demanda_dia:number;demanda_fonte:string;cobertura_dias:number|null;erro?:string};
export type EstoqueLinha={linha:string;livres:number;reservados:number;em_producao:number;esperando_voce:number;minimo:number;alvo:number};
export type ResumoLinha={id:string;titulo:string;estado:'ativa'|'pausada';versao:number;estilo:string;modo_execucao:string;publicacao:string;redes:string[];
  estoque:EstoqueLinha;pautas:Record<string,number>;episodios:number};
export type Evento={n:number;t:number;agente:string;tipo:string;decisao:string;motivo:string;dados:string};
export type Decisao={acao:string;motivo:string;repondo?:boolean;quantos?:number;n?:number};
export type ResumoCentral={config:ConfigCentral;nomes_modo:Record<string,string>;presets:Record<string,Record<string,number>>;esteira_ligada:boolean;
  indicadores:{estoque_cortes:number;estoque_linhas:number;rodando:number;na_fila:number;revisao_manual:number;esperando_voce:number;falhas_24h:number};
  proximas:{id:string;rede:string;data_local:string;hora_local:string;quando_utc:number;estado:string;ref:string|null}[];
  estoque_cortes:EstoqueCortes;linhas:ResumoLinha[];eventos:Evento[]};
export type Simulacao={estado:EstadoCentral;aviso:string;cortes:{estoque:EstoqueCortes;decisao:Decisao;agente_ligado:boolean}|{erro:string}|null;
  linhas:{linha:string;titulo:string;estoque:EstoqueLinha;decisao:Decisao}[]};
export type Sugestao={id:string;titulo:string;porque:string;mudanca:Record<string,unknown>|null};

export const resumoCentral=(c:CfgSrv)=>api<ResumoCentral>(c,'GET','/api/v1/automacao/resumo');
export const salvarCentral=(c:CfgSrv,d:Partial<Omit<ConfigCentral,'cortes'|'linhas'>>&{cortes?:Partial<ConfigCentral['cortes']>;linhas?:Partial<ConfigCentral['linhas']>})=>
  api<ConfigCentral>(c,'PUT','/api/v1/automacao/config',d);
export const simularCentral=(c:CfgSrv)=>api<Simulacao>(c,'POST','/api/v1/automacao/simular',{});
export const pausarCentral=(c:CfgSrv)=>api<ConfigCentral>(c,'POST','/api/v1/automacao/pausar',{});
export const retomarCentral=(c:CfgSrv)=>api<ConfigCentral>(c,'POST','/api/v1/automacao/retomar',{});
export const eventosCentral=(c:CfgSrv,agente='')=>api<{eventos:Evento[]}>(c,'GET','/api/v1/automacao/eventos?limite=150'+(agente?'&agente='+agente:''));
export const sugestoesCentral=(c:CfgSrv)=>api<{sugestoes:Sugestao[];aviso:string}>(c,'GET','/api/v1/automacao/sugestoes');
export const aplicarSugestoes=(c:CfgSrv,ids:string[])=>api<ConfigCentral>(c,'POST','/api/v1/automacao/aplicar-sugestoes',{ids});

// ---- linhas de conteúdo
export type ConfigLinha={titulo:string;tema:string;subtemas:string[];excluir:string[];publico:string;idioma:string;objetivo:string;tom:string;ideia_geral:string;
  referencias:string;ideia_roteiro:string;gancho_preferido:string;restricoes:string;tipo:string;quantidade_lote:number;duracao_seg:number;formato:string;estilo:string;
  confirmar_beta:boolean;voz:string;ritmo:string;imagens:string;personagens:{modo:string;ids:{id:string;versao:number}[];descricao:string};
  cenarios:{ids:string[];descricao:string};modo_pautas:'automatico'|'supervisionado'|'manual';aprovar_roteiro:'voce'|'automatico';publicacao:'voce'|'automatica';
  agenda:{redes:string[]};estoque:{minimo:number;alvo:number};modo_execucao:'lote_unico'|'continuo';limite_dia:number;orcamento_video:number;travas:string[]};
export type Pauta={id:string;status:string;lote:string|null;titulo:string;subtema?:string;resumo?:string;gancho?:string;classificacao?:string;
  fontes?:{url:string;titulo?:string;abre?:boolean}[];verificacao?:string;editada?:boolean};
export type Episodio={id:string;projeto:string;lote?:string;titulo:string;status:string;nome_status:string;nota?:number|null;veredito?:string|null;correcoes?:number|null;
  sha?:string;publicacoes?:{rede:string;estado:string;quando_utc:number}[];erro?:string};
export type Linha=ConfigLinha&{id:string;estado:'ativa'|'pausada';versao:number;resumo:ResumoLinha;pautas:Pauta[];episodios:Episodio[];
  lotes:{id:string;meta:number;status:string;motivo:string;iniciado:number}[]};

export const listarLinhas=(c:CfgSrv)=>api<{linhas:ResumoLinha[]}>(c,'GET','/api/v1/linhas-conteudo');
export const obterLinha=(c:CfgSrv,id:string)=>api<Linha>(c,'GET','/api/v1/linhas-conteudo/'+id);
export const criarLinha=(c:CfgSrv,d:Partial<ConfigLinha>)=>api<Linha>(c,'POST','/api/v1/linhas-conteudo',d);
export const mudarLinha=(c:CfgSrv,id:string,d:Partial<ConfigLinha>&{versao?:number;estado?:string})=>api<Linha>(c,'PATCH','/api/v1/linhas-conteudo/'+id,d);
export const apagarLinha=(c:CfgSrv,id:string)=>api(c,'DELETE','/api/v1/linhas-conteudo/'+id);
export const planejarPautas=(c:CfgSrv,id:string,quantidade?:number)=>
  api<{pautas:Pauta[];repetidas:{titulo:string;parecida_com:string}[];aviso:string}>(c,'POST',`/api/v1/linhas-conteudo/${id}/planejar-pautas`,{quantidade});
export const escreverPautas=(c:CfgSrv,id:string,titulos:string[])=>
  api<{pautas:Pauta[];repetidas:{titulo:string;parecida_com:string}[]}>(c,'POST',`/api/v1/linhas-conteudo/${id}/pautas`,{titulos});
export const mudarPauta=(c:CfgSrv,id:string,acao:'aceitar'|'bloquear'|'trocar'|'editar',dados?:Partial<Pauta>)=>
  api<Pauta>(c,'PATCH','/api/v1/linhas-conteudo/pautas/'+id,{acao,dados});
export const iniciarLote=(c:CfgSrv,id:string,quantidade?:number)=>
  api<{lote:string;episodios:{episodio:string;projeto:string;titulo:string}[]}>(c,'POST',`/api/v1/linhas-conteudo/${id}/iniciar-lote`,{quantidade});
export const pausarLinha=(c:CfgSrv,id:string,pausar:boolean)=>api<Linha>(c,'POST',`/api/v1/linhas-conteudo/${id}/${pausar?'pausar':'retomar'}`,{});
