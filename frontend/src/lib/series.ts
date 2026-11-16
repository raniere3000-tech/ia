import { api, type CfgSrv, type Job } from './api';

export type Personagem={id:string;serie_id:string;nome:string;versao:number;aprovado:boolean;rig_id:string;versoes?:number[];
  dados:{nome:string;descricao:string;pele:string;cabelo:string;olhos:string;roupa:string;calca:string;sapato:string;cabelo_tipo:string;corpo:string;acessorio:string;altura:number;voz:string}};
export type Cenario={id:string;serie_id:string;nome:string;versao:number;dados:{nome:string;descricao:string;tipo:string;horario:string;ceu:string;ceu2:string;chao:string}};
export type EntradaBiblia={id:string;serie_id:string;tipo:string;alvo:string;texto:string;episodio_id:string;estado:'proposta'|'aprovada'|'rejeitada'|'substituida';substitui:string|null;criado:number};
export type Episodio={id:string;serie_id:string;temporada_id:string;ordem:number;titulo:string;resumo:string;projeto_id:string;status:string;status_nome:string};
export type SerieResumo={id:string;titulo:string;versao:number;genero:string;formato:string;publico:string;tom:string;regras:string;duracao_alvo:number;cenas_qtd:number;estilo?:'animado2d'|'animado3d';episodios:number;personagens:number};
export type Serie=Omit<SerieResumo,'episodios'|'personagens'>&{temporadas:{id:string;ordem:number;titulo:string}[];episodios:Episodio[];personagens:Personagem[];cenarios:Cenario[];biblia:EntradaBiblia[]};

export const listarSeries=(cfg:CfgSrv)=>api<{series:SerieResumo[];acoes:Record<string,string>;expressoes:string[]}>(cfg,'GET','/api/v1/series');
export const criarSerie=(cfg:CfgSrv,d:Partial<SerieResumo>)=>api<Serie>(cfg,'POST','/api/v1/series',d);
export const obterSerie=(cfg:CfgSrv,id:string)=>api<Serie>(cfg,'GET','/api/v1/series/'+id);
export const atualizarSerie=(cfg:CfgSrv,id:string,d:Partial<SerieResumo>)=>api<Serie>(cfg,'PATCH','/api/v1/series/'+id,d);
export const criarPersonagem=(cfg:CfgSrv,serie_id:string,dados:Partial<Personagem['dados']>)=>api<Personagem>(cfg,'POST','/api/v1/personagens',{serie_id,dados});
export const salvarPersonagem=(cfg:CfgSrv,id:string,d:{dados?:Partial<Personagem['dados']>;aprovado?:boolean;versao?:number})=>api<Personagem>(cfg,'PUT',`/api/v1/personagens/${id}/rig`,d);
export const folhaPersonagem=(cfg:CfgSrv,id:string)=>api<{png:string;limites:string}>(cfg,'GET',`/api/v1/personagens/${id}/folha`);
export const previaPersonagem=(cfg:CfgSrv,dados:Partial<Personagem['dados']>)=>api<{png:string;limites:string}>(cfg,'POST','/api/v1/personagens/previa',{dados});
export const criarCenario=(cfg:CfgSrv,serie_id:string,dados:Partial<Cenario['dados']>)=>api<Cenario>(cfg,'POST','/api/v1/cenarios',{serie_id,dados});
export const previaCenario=(cfg:CfgSrv,dados:Partial<Cenario['dados']>,formato='9:16')=>api<{png:string}>(cfg,'POST','/api/v1/cenarios/previa',{dados,formato});
export const salvarBiblia=(cfg:CfgSrv,id:string,entradas:Partial<EntradaBiblia&{apagar:boolean}>[])=>api<{biblia:EntradaBiblia[]}>(cfg,'PUT',`/api/v1/series/${id}/biblia`,{entradas});
export const criarEpisodio=(cfg:CfgSrv,id:string,d:{titulo:string;resumo:string;produzir:boolean;modo_aprovacao:'assistido'|'supervisionado';temporada_id?:string})=>api<Episodio>(cfg,'POST',`/api/v1/series/${id}/episodios`,d);
export const trazerMudancas=(cfg:CfgSrv,episodio:string)=>api<{biblia:EntradaBiblia[]}>(cfg,'POST',`/api/v1/series/episodios/${episodio}/propostas`,{});

export const CABELOS:[string,string][]=[['curto','Curto'],['longo','Longo'],['cacheado','Cacheado'],['coque','Coque'],['careca','Careca']];
export const CORPOS:[string,string][]=[['magro','Magro'],['medio','Médio'],['forte','Forte']];
export const ACESSORIOS:[string,string][]=[['nenhum','Nenhum'],['oculos','Óculos'],['bone','Boné'],['laco','Laço']];
export const TIPOS_CENARIO:[string,string][]=[['parque','Parque'],['rua','Rua'],['casa','Casa'],['escola','Escola'],['escritorio','Escritório'],['vazio','Fundo liso']];
export const HORARIOS:[string,string][]=[['dia','Dia'],['tarde','Fim de tarde'],['noite','Noite']];

// S3: temporadas, rig 2D, prévia de pose e boca
export const criarTemporada=(cfg:CfgSrv,id:string,d:{titulo?:string;arco?:string})=>api<{id:string;ordem:number;titulo:string}>(cfg,'POST',`/api/v1/series/${id}/temporadas`,d);
export type Rig={rig_id:string;versao:number;aprovado:boolean;biblioteca:{rig_id:string;versao_rig:number;assinatura:string;pecas:Record<string,string>;poses:string[];acoes:string[];objetos:string[];alcance:string[];
  proporcoes:Record<string,number|string>;limites:string}};
export const lerRig=(cfg:CfgSrv,id:string)=>api<Rig>(cfg,'GET',`/api/v1/personagens/${id}/rig`);
export type PedidoPose={pose:string;objeto:string;expressao:string};
export const pedirPose=(cfg:CfgSrv,id:string,d:PedidoPose)=>api<{png?:string;job?:string;status?:string;etapa?:string;erro?:string}>(cfg,'POST',`/api/v1/personagens/${id}/pose`,d);
export const lerJob=(cfg:CfgSrv,id:string)=>api<Job&{resultado?:Record<string,unknown>|null}>(cfg,'GET','/api/v1/fila/'+id);
export type Visemas={dur:number;passo:number;niveis:number[];modo:string;formas:string[];limites:string};
export const visemasDoAudio=(cfg:CfgSrv,asset:string,texto:string)=>api<Visemas>(cfg,'POST','/api/v1/personagens/visemas',{asset,texto});
export const NOME_POSE:Record<string,string>={bracos_cruzados:'Braços cruzados',maos_na_cintura:'Mãos na cintura',pensativo:'Pensativo',explicando:'Explicando',comemorar:'Comemorando',timido:'Tímido',
  bola:'Bola',caixa:'Caixa',livro:'Livro',copo:'Copo',celular:'Celular',flor:'Flor',neutro:'Neutro',feliz:'Feliz',triste:'Triste',bravo:'Bravo',surpreso:'Surpreso',preocupado:'Preocupado'};
export const nomePose=(k:string)=>NOME_POSE[k]||k.replace(/_/g,' ');
