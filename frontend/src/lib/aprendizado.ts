// Aprendizado dos agentes: cliente da API do servidor (retratos das redes, importação, pesos com versão, teste A/B).
import { api, type CfgSrv } from './api';

export type ValorVar={valor:string;n:number;media:number;mediana:number;dp:number};
export type VarAprend={variavel:string;nome:string;rede:string;minimo:number;valores:ValorVar[];aplicavel:boolean;aviso:string;estado:'dados insuficientes'|'tendência'|'sem diferença clara';mensagem:string;melhor?:string;
  peso_ativo:Record<string,number>;versao_pesos:number|null;pode_desfazer:boolean;pode_aplicar:boolean;pesos_calculados:Record<string,number>};
export type Experimento={contexto?:{canal:string;vertente:string;rede:string;metrica:string}|null;id:string;nome:string;variavel:string;a:string;b:string;fixos:Record<string,string>;min_amostras:number;status:string;resultado:string;mensagem:string;
  lados:Record<'a'|'b',{valor:string;n:number;media?:number}>;aviso_frequencia:string};
export type PainelAprend={retratos:number;minimo:number;fontes:{fonte:string;rede:string;retratos:number;de:number|null;ate:number|null}[];variaveis:VarAprend[];experimentos:Experimento[];
  importacoes:{id:string;nome:string;formato:string;linhas:number;recusadas:number;t:number}[];historico_pesos:{versao:number;t:number;variavel:string;motivo:string;ativo:number}[];
  aviso_causa:string;aviso_frequencia:string;boas_praticas:string[];como_voltar:string};
export type ResImport={importacao:string;aceitas:number;repetidas:number;recusadas:{linha:number;motivo:string}[];total_recusadas:number;aviso?:string};
export const lerAprendizado=(c:CfgSrv)=>api<PainelAprend>(c,'GET','/agente/aprendizado');
export const importarAprendizado=(c:CfgSrv,nome:string,formato:'csv'|'json',conteudo:string)=>api<ResImport>(c,'POST','/agente/aprendizado/importar',{nome,formato,conteudo});
export const capturarAprendizado=(c:CfgSrv)=>api<{novos:number;painel:PainelAprend}>(c,'POST','/agente/aprendizado/capturar',{});
export const apagarAprendizado=(c:CfgSrv,d:{alvo:'tudo'|'rede'|'importacao';id?:string})=>api<{apagados:number;painel:PainelAprend}>(c,'POST','/agente/aprendizado/apagar',d);
export const aplicarPesos=(c:CfgSrv,variavel:string)=>api<PainelAprend>(c,'POST','/agente/aprendizado/aplicar',{variavel});
export const desfazerPesos=(c:CfgSrv,variavel:string)=>api<PainelAprend>(c,'POST','/agente/aprendizado/desfazer',{variavel});
export const criarTeste=(c:CfgSrv,d:{variavel:string;a:string;b:string;fixos:Record<string,string>;min_amostras?:number})=>api<Experimento>(c,'POST','/agente/aprendizado/experimento',d);
export const encerrarTeste=(c:CfgSrv,id:string)=>api<Experimento>(c,'POST','/agente/aprendizado/experimento/encerrar',{id});

export type FiltrosInteligencia={vertente:string;rede:string;canal:string;de:string;ate:string;metrica:string};
export type PublicacaoContexto={titulo:string|null;origem:string;render_sha:string|null;gancho:string|null;modelo:string|null;publicado_em:number|null;projeto:string|null;corte:string|null;
  capa_selecionada:{sha:string|null;tempo_ms:number|null}|null;efeitos:{efeitos:{tipo:string;status:string}[]}|null};
export type VideoMedido={snapshot:string;fonte:string;rede:string;item:string;medido_em:number|null;metricas:Record<string,number>;publicacao:PublicacaoContexto|null};
export type Indicadores={destaques:{rede:string;metrica:string;sem_metrica:number;videos:VideoMedido[]}[];publicacoes:number;medidas:Record<string,{valor:number|null;amostras:number}>;canais:string[];aviso:string};
export const lerIndicadores=(c:CfgSrv,f:FiltrosInteligencia)=>api<Indicadores>(c,'GET','/agente/aprendizado/indicadores?'+new URLSearchParams(f));
export const valorMetrica=(v:number|null|undefined)=>v==null?'Indisponível':v.toLocaleString('pt-BR');
