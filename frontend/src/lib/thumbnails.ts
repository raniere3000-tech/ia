// Agente 6: capas (thumbnails) dos cortes do Agente 1 e dos vídeos do Agente 3.
import { api, type CfgSrv } from './api';

export type Origem='corte'|'render'|'post';
export type Metodo='frame'|'editorial'|'ia'|'inteligente';
export type Fonte={origem:Origem;referencia:string;titulo:string;agente:string;status:string;criado:number;job:{id:string;estado:string}|null};
export type Criterios={fidelidade?:number;legibilidade?:number;area_segura?:number;tecnica?:number;identidade?:number;rede?:number;
  legibilidade_medida?:{contraste:number|null;altura_120:number|null;medido:boolean}};
export type Variante={id:string;numero:number;versao:number;sha256:string;formato:string;largura:number;altura:number;conceito:string;nota:number;
  estado:'aprovada'|'reprovada'|'substituida'|'rejeitada';criado:number;layout:string;quadro_t:number|null;metodo:string;custo:number;url:string;baixar:string;
  relatorio:{nota:number;aprovado:boolean;criterios:Criterios;bloqueios:string[];notas:string[];metodo:string;texto:string;layout:string}};
export type Selecao={id:string;variante:string;video_sha:string;thumb_sha:string;escolha:string;por:string;criado:number}|null;
export type Progresso={status:string;pct:number;etapa:string;restante_s:number|null;estimado:boolean;criado:number;iniciado:number|null;terminado:number|null;decorrido:number;tentativas:number}|null;
export type Job={rejeicao_habilitada?:boolean;id:string;origem:Origem;referencia:string;video_sha:string;estado:string;criado:number;atualizado:number;erro:string|null;titulo:string;metodo:string;
  correcoes:number;custo:number;por:string;config:{variantes:number;formato:string;texto_modo:string;texto:string;descricao:string;avisos?:string[]};
  progresso:Progresso;selecao:Selecao;variantes:Variante[]};
export type Perfil={id:string;nome:string;escopo:string;versao:number;config:{cor_texto:string;cor_destaque:string;cor_faixa:string;intensidade:number;maiusculas:boolean;logo_asset:string;nicho:string;exemplos:string}};
export type CfgThumb={modo:'automatico'|'supervisionado'|'manual';criar_sozinho:boolean;metodo_padrao:Metodo;variantes_padrao:number;max_variantes:number;max_correcoes:number;
  nota_min:number;ia:boolean;ia_max_por_pedido:number;ia_fallback_local:boolean;exigir_capa_youtube:boolean;formato_por_rede:Record<string,string>;
  exigir_capa:boolean;redes_exigem_capa:string[];recuperacao_automatica:boolean;max_recuperacoes:number;reenviar_capa:boolean;max_envios_capa:number;
  estrategia_rede:Record<string,Estrategia>};
export type Estrategia='imagem'|'quadro'|'manual'|'nenhuma';
export type Pendencia={origem:Origem;referencia:string;titulo:string;acao:string;motivo:string;job:string|null};
export type Aplicacao={post:string;rede:string;estrategia:string;estado:string;thumb_sha:string;ref_rede:string;tentativas:number;erro:string|null;atualizado:number;titulo:string};
export type PainelAutonomia={dias:number;config:CfgThumb;taxa_autonomia:number|null;pendencias:Pendencia[];a_fazer:{criar:number;escolher:number};
  numeros:{capas_geradas:number;capas_aprovadas:number;capas_escolhidas:number;escolhidas_automatico:number;escolhidas_por_voce:number;capas_usadas:number;
    capas_aplicadas_confirmadas:number;capas_manual_no_app:number;capas_falharam:number;posts_sem_capa:number;pedidos_automaticos:number;pedidos_total:number};
  posts_sem_capa:{post:string;titulo:string;redes:string[];quando:number}[];aplicacoes:Aplicacao[];ignorados:Record<string,{t:number;por:string;motivo:string}>;
  ultima_auditoria:Record<string,number|string|boolean>|null;estrategias:Record<Estrategia,string>};
export type Auditoria={aplicado:boolean;modo:string;videos:{total:number;com_capa:number;sem_capa:number};
  redundantes:{job:string;titulo:string;motivo:string;estado:string}[];recuperacao:{criados:Pendencia[];selecionados:Pendencia[];excecoes:Pendencia[]};
  agendados_sem_capa:{post:string;rede:string;titulo:string}[];posts_reabertos:{post:string;rede:string;titulo:string}[];
  youtube_sem_capa:{post:string;titulo:string;estado_capa:string;tem_capa_agora:boolean}[];youtube_reenviados:{post:string;titulo:string;resultado:string;erro?:string}[];
  postados_capa_manual:{post:string;rede:string;titulo:string;estado_capa:string}[]};
export type Capacidades={rejeicao_habilitada?:boolean;ffmpeg:boolean;pillow:boolean;fonte:boolean;ia:{disponivel:boolean;motivo:string};formatos:string[];aviso:string;
  redes:Record<string,{tipo:string;detalhe:string;testado:boolean;estado:string}>};
export type Desempenho={pedidos:number;por_estado:Record<string,number>;tempo_ativo_medio_s:number|null;espera_fila_media_s:number|null;tempo_total_medio_s:number|null;
  previsao_por_pedido_s:number|null;falhas:number;tentativas_fila:number;correcoes_criativas:number;custo_estimado_reais:number;
  escolhas:{total:number;por_layout:Record<string,number>;manuais:number};aviso:string};
export type Pedido={origem:Origem;referencia:string;metodo:Metodo;variantes:number;formato:string;texto_modo:'auto'|'exato'|'sem';texto:string;descricao:string;
  perfil_id?:string;fallback_local?:boolean;destino?:string};

const B='/api/v1/thumbnails';
export const lerFontes=(c:CfgSrv,origem='',termo='')=>api<{fontes:Fonte[]}>(c,'GET',`${B}/fontes?origem=${origem}&termo=${encodeURIComponent(termo)}`);
export const lerJobs=(c:CfgSrv,estado='')=>api<{jobs:Job[]}>(c,'GET',`${B}/jobs?estado=${estado}&limite=60`);
export const lerJob=(c:CfgSrv,id:string)=>api<Job>(c,'GET',`${B}/jobs/${id}`);
export const pedirCapas=(c:CfgSrv,d:Pedido)=>api<Job&{repetido?:boolean}>(c,'POST',`${B}/jobs`,{...d,chave_idempotencia:undefined});
export const cancelarJob=(c:CfgSrv,id:string)=>api<Job>(c,'POST',`${B}/jobs/${id}/cancelar`,{});
export const refazerCapa=(c:CfgSrv,id:string,numero:number,texto?:string)=>api<Job>(c,'POST',`${B}/jobs/${id}/refazer`,texto===undefined?{numero}:{numero,texto});
export const escolherCapa=(c:CfgSrv,id:string,v:Variante,confirmacao=false)=>api<Job>(c,'POST',`${B}/jobs/${id}/selecionar`,{variante_id:v.id,versao:v.versao,confirmacao});
export const rejeitarCapa=(c:CfgSrv,id:string,v:Variante)=>api<Job>(c,'POST',`${B}/jobs/${id}/rejeitar`,{variante_id:v.id,versao:v.versao});
export const lerPacote=(c:CfgSrv,id:string)=>api<{valido:boolean;motivo?:string;video_sha?:string;thumb_sha?:string;numero?:number;versao?:number}>(c,'GET',`${B}/jobs/${id}/pacote`);
export const lerPerfis=(c:CfgSrv)=>api<{perfis:Perfil[]}>(c,'GET',`${B}/perfis`);
export const criarPerfil=(c:CfgSrv,d:Partial<Perfil['config']>&{nome:string;escopo:string})=>api<Perfil>(c,'POST',`${B}/perfis`,d);
export const mudarPerfil=(c:CfgSrv,id:string,d:Partial<Perfil['config']>&{nome?:string})=>api<Perfil>(c,'PATCH',`${B}/perfis/${id}`,d);
export const lerCfgThumb=(c:CfgSrv)=>api<CfgThumb>(c,'GET',`${B}/config`);
export const salvarCfgThumb=(c:CfgSrv,d:Partial<CfgThumb>)=>api<CfgThumb>(c,'POST',`${B}/config`,d);
export const lerCapacidades=(c:CfgSrv)=>api<Capacidades>(c,'GET',`${B}/capacidades`);
export const lerAutonomia=(c:CfgSrv)=>api<PainelAutonomia>(c,'GET',`${B}/autonomia`);
export const auditarEstoque=(c:CfgSrv,aplicar:boolean)=>api<Auditoria>(c,'POST',`${B}/autonomia/auditar`,{aplicar});
export const ignorarVideo=(c:CfgSrv,origem:Origem,referencia:string,ignorar=true)=>api<{ignorados:Record<string,unknown>}>(c,'POST',`${B}/autonomia/ignorar`,{origem,referencia,ignorar});
export const reenviarCapa=(c:CfgSrv,post:string,rede='youtube')=>api<{estado:string;detalhe:string}>(c,'POST',`${B}/autonomia/reenviar-capa`,{post,rede});
export const ESTADO_CAPA:Record<string,[string,string]>={aplicada:['aplicada (a rede confirmou)','ok'],indicada:['quadro da capa aceito pela rede','ok'],
  falhou:['falhou: tenta de novo sozinho','warn'],bloqueada:['a rede recusou (veja o motivo)','bad'],manual:['aplicar no app','warn'],sem_capa:['sem capa','bad']};
export const lerDesempenho=(c:CfgSrv)=>api<Desempenho>(c,'GET',`${B}/desempenho`);

export const ESTADOS:Record<string,[string,string]>={aguardando_video:['esperando o diretor aprovar o vídeo','warn'],na_fila:['na fila',''],analisando:['olhando o vídeo','ok'],
  criando:['desenhando','ok'],validando:['diretor conferindo','ok'],aguardando_escolha:['escolha a capa','warn'],pronto:['pronta','ok'],falhou:['falhou','bad'],
  cancelado:['cancelado',''],revisao_manual:['precisa de você','bad']};
export const METODOS:[Metodo,string,string][]=[['inteligente','Automático','Quadros do vídeo com três composições diferentes.'],
  ['frame','Quadro do vídeo','O próprio quadro, com pouco enfeite.'],['editorial','Editorial','Faixas, painel e moldura, estilo revista.'],
  ['ia','Com IA','Fundo gerado pela IA (sem texto). O texto continua pelo nosso desenho, sem erro de escrita.']];
export const LAYOUT:Record<string,string>={cheia:'tela cheia',cheia_topo:'texto no topo',faixa:'faixa',dividido:'dividido',moldura:'moldura',caixa:'caixa de texto (correção)'};
