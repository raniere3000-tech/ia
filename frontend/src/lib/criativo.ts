// Núcleo criativo: a mesma Modelagem com IA, biblioteca e pesquisa de tendências para todas as telas (o servidor monta e confere tudo).
import { api, type CfgSrv } from './api';
import type { Video } from './radar';

export type TipoModelo='ideia'|'historia'|'serie'|'episodio'|'personagem'|'cenario'|'objeto'|'movimento'|'estilo'|'cena'|'pacote';
export type Destino='biblioteca'|'personagem'|'cenario'|'serie'|'episodio'|'video'|'projeto';
export type Referencia={plataforma:string;video_id:string;url:string;canal_id:string;canal_nome:string;titulo:string;publicado_em:string;coletado_em:string;
  views:number|null;likes:number|null;comentarios:number|null;duracao_seg:number|null;periodo_dias:number;consulta:string;tipo_evidencia:string;confianca:string;
  caracteristicas_abstratas:string[];restricoes_direitos:string[];views_dia_desde_publicacao?:number|null;engajamento?:number|null};
export type Tendencias={disponivel:boolean;fonte:string|null;motivo:string;referencias:Referencia[];amostra:number;limites:string;criterio:string;coletado_em?:string|null;cache:boolean;consultas:string[]};
export type PersonagemP={nome:string;descricao:string;personalidade?:string;pele:string;cabelo:string;olhos:string;roupa:string;calca:string;sapato:string;cabelo_tipo:string;corpo:string;acessorio:string;altura:number;voz:string};
export type CenarioP={nome:string;descricao:string;tipo:string;horario:string;clima?:string;ceu:string;ceu2:string;chao:string};
export type Campos={titulo:string;sinopse:string;premissa:string;publico:string;genero:string;gancho:string;tom:string;visual:string;formato:string;duracao_seg:number;
  estilo:string;porque:string;regras_mundo:string[];hashtags:string[];personagens:PersonagemP[];cenarios:CenarioP[];
  objetos:{nome:string;descricao:string;catalogo:string;animavel:boolean}[];movimentos:{nome:string;descricao:string;pose:string;acao:string;animavel:boolean}[];
  cenas:{titulo:string;texto:string;personagem:string}[]};
export type Proposta={id:string;lote:string;status:string;tipo:TipoModelo;contexto:string;modo:string;origem:'ia'|'codigo';rotulo:string;campos:Campos;
  compatibilidade:{engine:string;aplicavel:boolean;avisos:string[]};tendencia:'medida'|'indisponivel'|'nao_pesquisada';fontes_pesquisadas:Referencia[];
  skills_usadas:{perfil:string;skill:string}[];previa:{status:string};pronto_para_aplicar:boolean;revisao:number;favorita?:boolean;editada?:boolean};
export type Capacidades={ia:{disponivel:boolean;motivo:string};tendencias:Record<string,{disponivel:boolean;motivo:string}>;
  motores:Record<string,{disponivel:boolean;nota:string;estado?:string}>;tipos:Record<TipoModelo,string>};
export type Filtros={plataforma:string;nicho:string;idioma:string;regiao:string;periodo_dias:number;views_min:number;duracao:string;ordem:string};
export type PedidoModelagem={contexto:string;modo:'descricao'|'surpresa'|'sorteio';tipo_modelo:TipoModelo;descricao?:string;surpresa?:'equilibrada'|'ousada';
  filtros_tendencias?:Filtros;somente_verificadas?:boolean;sem_tendencias?:boolean;evidencias_radar?:Partial<Video>[];projeto_id?:string;serie_id?:string;
  assets_selecionados?:{id:string;tipo:string;nome:string;descricao?:string}[];regras?:{formato?:string;estilo?:string;orcamento_max?:number};quantas?:number};
export type Resultado={propostas:Proposta[];tendencias:Tendencias|null;precisa_confirmar?:boolean;mensagem?:string};
export type ItemBiblioteca={id:string;tipo:string;nome:string;descricao:string;versao:number;status:string;serie_id?:string;origem:string;modalidades:string[];dados:Record<string,unknown>};
export type Aplicado={destino:string;criados?:{id:string;tipo:string;nome:string}[];serie_id?:string;episodio_id?:string;projeto_id?:string;personagens?:string[];repetido?:boolean};

export const capacidades=(cfg:CfgSrv)=>api<Capacidades>(cfg,'GET','/api/v1/criativo/capacidades');
export const propor=(cfg:CfgSrv,d:PedidoModelagem)=>api<Resultado>(cfg,'POST','/api/v1/criativo/modelagem/propor',d);
export const pesquisarTendencias=(cfg:CfgSrv,filtros:Partial<Filtros>,evidencias_radar?:Partial<Video>[])=>api<Tendencias>(cfg,'POST','/api/v1/criativo/tendencias/pesquisar',{filtros,evidencias_radar});
export const editarProposta=(cfg:CfgSrv,id:string,d:{revisao:number;campos?:Partial<Campos>;favorita?:boolean;status?:string})=>api<Proposta>(cfg,'PATCH','/api/v1/criativo/propostas/'+id,d);
export const aplicarProposta=(cfg:CfgSrv,id:string,d:{destino:Destino;serie_id?:string;projeto_id?:string;so_primeiro?:boolean;campos?:string[];chave?:string})=>
  api<Aplicado>(cfg,'POST',`/api/v1/criativo/propostas/${id}/aplicar`,d);
export const previaProposta=(cfg:CfgSrv,id:string,d:{indice?:number;o_que?:'personagem'|'cenario'})=>api<{status:string;png?:string;motivo?:string;limites?:string}>(cfg,'POST',`/api/v1/criativo/propostas/${id}/previa`,d);
export const listarPropostas=(cfg:CfgSrv,favoritas=false)=>api<{propostas:Proposta[]}>(cfg,'GET','/api/v1/criativo/propostas'+(favoritas?'?favoritas=1':''));
export const biblioteca=(cfg:CfgSrv,tipo='',q='')=>api<{itens:ItemBiblioteca[];total:number}>(cfg,'GET',`/api/v1/criativo/biblioteca?tipo=${encodeURIComponent(tipo)}&q=${encodeURIComponent(q)}`);
export const usarNoProjeto=(cfg:CfgSrv,projeto_id:string,personagens:string[],cenarios:string[]=[])=>
  api<{ok:boolean;serie:{personagens:Record<string,{nome:string}>;versoes:Record<string,number>}}>(cfg,'POST','/api/v1/criativo/usar-no-projeto',{projeto_id,personagens,cenarios});
export const duplicarProposta=(cfg:CfgSrv,id:string)=>api<Proposta>(cfg,'POST',`/api/v1/criativo/propostas/${id}/duplicar`,{});
export const transformarEmSerie=(cfg:CfgSrv,projeto_id:string)=>api<{serie:{id:string;titulo:string};repetido?:boolean}>(cfg,'POST','/api/v1/criativo/transformar-em-serie',{projeto_id});
export const previaAsset=(cfg:CfgSrv,id:string)=>api<{png?:string;status?:string;motivo?:string}>(cfg,'POST',`/api/v1/criativo/assets/${id}/previa`,{});

export type ConfigFormato=Pick<import('./api').Briefing,'tipo'|'estilo'|'duracao_alvo'|'cenas_qtd'|'ritmo'|'formato'>;
export type FormatoIA={id:string;nome:string;descricao:string;versao?:number;dados:{formato_ia:string;briefing:ConfigFormato}};
export const formatosIA=(cfg:CfgSrv)=>api<{habilitado:boolean;padroes:FormatoIA[];salvos:FormatoIA[]}>(cfg,'GET','/api/v1/criativo/formatos');
export const salvarFormatoIA=(cfg:CfgSrv,modelo:FormatoIA,nome:string,briefing:ConfigFormato)=>api<FormatoIA>(cfg,
  modelo.versao?'PATCH':'POST',modelo.versao?`/api/v1/criativo/assets/${modelo.id}`:'/api/v1/criativo/biblioteca',
  {tipo:'template_pack',nome,descricao:modelo.descricao,versao:modelo.versao,origem:'manual',
   dados:{formato_ia:modelo.dados.formato_ia,briefing}});

export const NOME_TIPO:Record<TipoModelo,string>={ideia:'Ideia de vídeo',historia:'História / roteiro',serie:'Série',episodio:'Episódio',personagem:'Personagem',cenario:'Cenário',
  objeto:'Objeto / acessório',movimento:'Movimento / atuação',estilo:'Estilo visual',cena:'Cena / storyboard',pacote:'Pacote completo'};
export const NOME_DESTINO:Record<Destino,string>={biblioteca:'Salvar como modelo',personagem:'Criar personagem',cenario:'Criar cenário',serie:'Criar série',
  episodio:'Criar episódio',video:'Criar vídeo (rascunho)',projeto:'Usar neste projeto'};
// leva a pesquisa do Radar (feita no navegador) para a Modelagem com IA em outra tela
const CHAVE_RADAR='estudio_radar_para_modelagem';
export function guardarDoRadar(videos:Partial<Video>[],consulta:string){ try{ sessionStorage.setItem(CHAVE_RADAR,JSON.stringify({videos:videos.slice(0,20).map(v=>({...v,consulta,coletado_em:new Date().toISOString()})),t:Date.now()})); }catch{ /* sem armazenamento: segue sem */ } }
export function lerDoRadar():Partial<Video>[]|null{ try{ const r=JSON.parse(sessionStorage.getItem(CHAVE_RADAR)||'null'); sessionStorage.removeItem(CHAVE_RADAR); return r&&Date.now()-r.t<3600000?r.videos:null; }catch{ return null; } }
