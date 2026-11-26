// Storyboard visual (3ª porta de aprovação), Gameplay Narrativa e modos Rápido/Caprichado: cliente da API do servidor.
import { api, type CfgSrv } from './api';

export type QuadroSB={asset:string;t:number;plano:string;personagem:string;angulo:string};
export type CenaSB={id:string;n:number;titulo:string;hash:string;quadros:QuadroSB[];quadros_desatualizados:boolean;status:'aprovada'|'pronta_para_conferir'|'mudou_depois_de_aprovar'|'sem_miniatura';ja_aprovada_antes?:boolean;camera:string;duracao:number|null;personagem:string;estilo:string;aprovada_por:string};
export type EstadoSB={ativa:boolean;cenas:CenaSB[];todas_aprovadas:boolean;versao:string;faltam:number[];aviso_final:string;boas_praticas?:string[]};
export const lerStoryboard=(cfg:CfgSrv,pid:string)=>api<EstadoSB>(cfg,'GET',`/api/v1/projetos/${pid}/storyboard-visual`);
export const gerarQuadros=(cfg:CfgSrv,pid:string,cenas?:string[])=>api<{job:string;status:string}>(cfg,'POST',`/api/v1/projetos/${pid}/storyboard-visual/quadros`,{cenas});
export const aprovarQuadros=(cfg:CfgSrv,pid:string,cenas?:string[])=>api<EstadoSB>(cfg,'POST',`/api/v1/projetos/${pid}/storyboard-visual/aprovar`,{cenas});
export const corrigirCena=(cfg:CfgSrv,pid:string,cena:string,mudancas:Record<string,unknown>)=>api<EstadoSB&{job:string}>(cfg,'POST',`/api/v1/projetos/${pid}/storyboard-visual/corrigir`,{cena,mudancas});

export type Evento={id:string;tipo:'mudanca_de_cena'|'pico_de_audio'|'fala_forte';t:number;fim:number;descricao:string;confianca:number;observado:boolean;visual?:string;texto?:string};
export type Gancho={tipo:string;abertura_falada:string;texto_na_tela:string;primeiro_quadro_t:number;eventos:string[];justificativa:string};
export type Destaque={id:string;ini:number;fim:number;eventos:string[];score:number;confianca:number;porque:string;ganchos:Gancho[];ganchos_origem:'ia'|'regras';ganchos_aviso:string};
export type Analise={id:string;titulo:string;historia:string;historias:Record<string,string>;fonte:string;direitos:{origem:string;nota:string};duracao:number;analise:'parcial'|'completa';analise_motivo:string;
  sinais:{n_cenas:number;n_picos:number;n_falas:number;audio:boolean};eventos:Evento[];destaques:Destaque[];aviso:string;tem_video:boolean};
export type ResumoAnalise={id:string;titulo:string;criado:number;analise:string;destaques:number;fonte:string};
export const listarAnalises=(cfg:CfgSrv)=>api<{analises:ResumoAnalise[];historias:Record<string,string>}>(cfg,'GET','/agente/gameplay');
export const lerAnalise=(cfg:CfgSrv,id:string)=>api<Analise>(cfg,'GET','/agente/gameplay/'+id);
export const pedirAnalise=(cfg:CfgSrv,d:{link:string;origem:string;nota:string;titulo:string;historia:string;usar_ia:boolean})=>api<{job:string}>(cfg,'POST','/agente/gameplay/analisar',d);
export const novaHistoria=(cfg:CfgSrv,id:string,historia:string)=>api<Analise>(cfg,'POST',`/agente/gameplay/${id}/historia`,{historia,usar_ia:true});
export const cortarDestaque=(cfg:CfgSrv,d:{gid:string;destaque:string;gancho:Gancho|null;ini:number;fim:number;modelo?:string;estilo?:string;modo?:string})=>api<{job:string}>(cfg,'POST','/agente/gameplay/cortar',d);
export const compararModos=(cfg:CfgSrv,d:{gid:string;destaque:string;estilo?:string})=>api<{job:string}>(cfg,'POST','/agente/gameplay/comparar',d);
export type Comparacao=Record<string,{nome:string;segundos_de_render:number;tamanho_bytes:number;operacoes:string[];volume:{lufs:number;pico_dbfs:number|null}|null;duracao:number}>;
export type Modo={nome:string;desc:string;estimativa:{segundos:number|null;motivo:string;amostras?:number}};
export const lerModos=(cfg:CfgSrv)=>api<{modos:Record<string,Modo>}>(cfg,'GET','/agente/modos');
export const mmss=(t:number)=>`${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`;

// ---------------------------------------------------------------- perfis de canal
export type DnaCorte={fonte?:'Inter';legenda?:'destaque'|'simples'|'caixa'|'nenhuma';zoom?:number;ritmo?:'calmo'|'padrao'|'dinamico'};
export type PerfilCampos={dna_corte?:DnaCorte;nome:string;nicho:string;publico:string;tom:string;voz:string;elenco:string[];series:string[];cores:{primaria:string;secundaria:string};logo:string;templates:string[];estilos_permitidos:string[];hashtags_base:string[];
  politica_fonte:{origens:string[];nota:string};redes:string[];contas:{meta_pagina:string};modo_qualidade:''|'rapido'|'caprichado';orcamento:number;temas_frequentes:string[];regras_de_marca:string};
export type Perfil=PerfilCampos&{id:string;versao:number;atualizado:number;historico:{versao:number;t:number;o_que:string}[]};
export type PerfilResumo={id:string;nome:string;nicho:string;redes:string[];modo_qualidade:string;versao:number;atualizado:number;tem_logo:boolean};
export const PERFIL_VAZIO:PerfilCampos={nome:'',nicho:'',publico:'',tom:'',voz:'',elenco:[],series:[],cores:{primaria:'',secundaria:''},logo:'',templates:[],estilos_permitidos:[],hashtags_base:[],politica_fonte:{origens:[],nota:''},redes:[],contas:{meta_pagina:''},modo_qualidade:'',orcamento:0,temas_frequentes:[],regras_de_marca:''};
export const listarPerfis=(cfg:CfgSrv)=>api<{perfis:PerfilResumo[];dna_corte_habilitado?:boolean}>(cfg,'GET','/perfis');
export const lerPerfil=(cfg:CfgSrv,id:string)=>api<Perfil>(cfg,'GET','/perfis/'+id);
export const salvarPerfil=(cfg:CfgSrv,d:Partial<PerfilCampos>&{id?:string})=>api<Perfil>(cfg,'POST','/perfis',d);
export const acaoPerfil=(cfg:CfgSrv,id:string,acao:'duplicar'|'restaurar'|'apagar',extra?:{versao:number})=>api<Perfil>(cfg,'POST',`/perfis/${id}/${acao}`,extra||{});
export const validarPerfil=(cfg:CfgSrv,id:string)=>api<{problemas:string[]}>(cfg,'GET',`/perfis/${id}/validar`);
export const resolverPerfil=(cfg:CfgSrv,id:string)=>api<{valores:Record<string,unknown>;origem:Record<string,string>}>(cfg,'GET',`/perfis/${id}/resolvido`);

// ---------------------------------------------------------------- pacote de publicação
export type ItemConf={item:string;estado:'ok'|'aviso'|'erro'|'nao_verificado';detalhe:string;corrigir:string};
export type Pacote={corte:string;titulo:string;titulos_sugeridos:string[];descricao:string;descricao_editada:boolean;link_original:string;capas:{indice:number;t:number;bytes:number}[];capa_escolhida:number;redes:string[];
  fatos:{largura:number;altura:number;codec_video:string;codec_audio:string;duracao:number;tamanho_mb:number;tem_audio:boolean};
  conformidade:Record<string,{nome:string;manual:boolean;itens:ItemConf[];pode_aprovar:boolean;erros:string[]}>;comentario_fixado:{texto:string;aviso:string};direitos:{origem?:string;nota?:string};
  aprovado_agora:boolean;tudo_ok:boolean;aviso_limites:string;hash:string;boas_praticas?:string[]};
export const lerPacote=(cfg:CfgSrv,corte:string)=>api<Pacote>(cfg,'GET',`/agente/cortes/${corte}/pacote`);
export const montarPacote=(cfg:CfgSrv,corte:string,redes?:string[])=>api<Pacote>(cfg,'POST',`/agente/cortes/${corte}/pacote/montar`,{redes});
export const editarPacote=(cfg:CfgSrv,corte:string,d:{titulo?:string;descricao?:string;capa?:number;redes?:string[]})=>api<Pacote>(cfg,'POST',`/agente/cortes/${corte}/pacote/editar`,d);
export const aprovarPacote=(cfg:CfgSrv,corte:string)=>api<Pacote>(cfg,'POST',`/agente/cortes/${corte}/pacote/aprovar`,{});
