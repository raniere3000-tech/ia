// Biblioteca de templates (modelos de vídeo): a mesma para a edição manual e para os agentes do servidor.
import type { Clip, Formato, Tarja } from './analyze';
import type { Cue, Preset } from './captions';
import { TEMPLATE_PADRAO, type RenderOpts, type Regiao, type Saida, type Template, type Visual } from './render';
import { store } from './store';

export type Layout = Visual['layout'];
export type Qualidade = 'alta'|'media'|'leve';
/** Um template completo: composição, legenda, efeito, gancho, tarjas, marca e exportação. */
export type Modelo = {
  id:string; nome:string;
  layout:Layout; formato:Formato; zoom:number; posX:number; posY:number;
  jogo:Regiao; camera:Regiao; divisao:number;
  legenda:string; legendaPos:'baixo'|'meio';
  efeito:string;
  gancho:boolean; ganchoPos:'topo'|'alto';
  tarja:Tarja|null;
  cor:string; logo:string; logoPos:Template['logoPos']; moldura:boolean; credito:string;
  resolucao:1080|720; qualidade:Qualidade;
  /** Cores da legenda já resolvidas, para o servidor montar igual sem conhecer os estilos do site. */
  leg?:{estilo:'destaque'|'simples'|'caixa'|'nenhuma';cor:string;corDestaque:string;maiusculas:boolean};
};
/** Cópia dos ajustes do template dentro de um corte. */
export type VisualClip = Visual & {legendaPos:'baixo'|'meio'; marca:Template; resolucao:1080|720; qualidade:Qualidade};
export type Biblioteca = {atualizado:number; modelos:Modelo[]};

export const LAYOUTS:[Layout,string,string][] = [
  ['desfoque','Fundo desfocado','O vídeo inteiro no meio e o fundo preenchido com ele mesmo desfocado.'],
  ['cheio','Tela cheia','O vídeo preenche a tela toda; você escolhe o zoom e para onde olhar.'],
  ['gameplay-streamer','Gameplay + Streamer','Gameplay em cima e a câmera do streamer embaixo, os dois sempre visíveis.'],
];
/** Efeitos que o site e o servidor dos agentes sabem fazer igual. */
export const EFEITOS_MODELO:[string,string][] = [['nenhum','Sem efeito'],['zoom-acao','Zoom lento (aproxima aos poucos)'],['transicao-fade','Transição: escurece no começo e no fim'],['virada-cena','Transição: clarão no começo']];
export const QUALIDADES:Record<Qualidade,[string,number]> = {alta:['Alta (arquivo maior)',10_000_000],media:['Média',6_500_000],leve:['Leve (arquivo menor)',3_500_000]};
const UPPER = new Set(['gta-impacto','impacto-vermelho','neon-gamer','frase-chave','karaoke-amarelo']);
const SIMPLES = new Set(['minimal-branco','classico-contorno']);

const BASE:Modelo = {
  id:'', nome:'Template', layout:'desfoque', formato:'9:16', zoom:1, posX:0.5, posY:0.5,
  jogo:{x:0,y:0,w:1,h:1}, camera:{x:0.72,y:0.62,w:0.28,h:0.38}, divisao:62,
  legenda:'karaoke-amarelo', legendaPos:'baixo', efeito:'nenhum', gancho:true, ganchoPos:'topo', tarja:null,
  cor:'#7758ef', logo:'', logoPos:'top-right', moldura:false, credito:'', resolucao:1080, qualidade:'media',
};
export const MODELOS_PADRAO:Modelo[] = [
  {...BASE,id:'padrao',nome:'Fundo desfocado'},
  {...BASE,id:'tela-cheia',nome:'Tela cheia',layout:'cheio',legenda:'impacto-vermelho',efeito:'transicao-fade'},
  {...BASE,id:'gameplay-streamer',nome:'Gameplay + Streamer',layout:'gameplay-streamer',legenda:'neon-gamer',legendaPos:'meio'},
];
export const novoId=()=> 'm'+Date.now().toString(36)+Math.random().toString(36).slice(2,6);
export const novoModelo=(base?:Modelo):Modelo=>({...(base||BASE),id:novoId(),nome:base?base.nome+' (cópia)':'Novo template'});

/** Preenche `leg` com as cores do estilo de legenda escolhido. */
export function comLeg(m:Modelo,presets:Preset[]):Modelo{
  const p=presets.find(x=>x.id===m.legenda);
  if(!p) return {...m,legenda:'',leg:{estilo:'nenhuma',cor:'#FFFFFF',corDestaque:'#FFE14D',maiusculas:true}};
  return {...m,leg:{estilo:p.id==='legenda-caixa'?'caixa':SIMPLES.has(p.id)?'simples':'destaque',cor:p.textColor,corDestaque:p.highlightColor,maiusculas:UPPER.has(p.id)}};
}

const K='studio_modelos';
function completar(m:Partial<Modelo>):Modelo{ return {...BASE,...m,jogo:{...BASE.jogo,...(m.jogo||{})},camera:{...BASE.camera,...(m.camera||{})}} as Modelo; }
/** Lê a biblioteca deste navegador. Na primeira vez cria os três de partida, já com a marca antiga (logo, @, cor). */
export function lerModelos():Biblioteca{
  const b=store.json<Partial<Biblioteca>>(K,{});
  if(Array.isArray(b.modelos)&&b.modelos.length) return {atualizado:+(b.atualizado||0),modelos:b.modelos.map(completar)};
  return {atualizado:0,modelos:comMarcaAntiga(MODELOS_PADRAO)};
}
/** Quem já tinha logo e @ configurados continua com eles em todos os templates de partida. */
export function comMarcaAntiga(ms:Modelo[]):Modelo[]{
  const t={...TEMPLATE_PADRAO,...store.json<Partial<Template>>('studio_template',{})};
  if(!t.ativo&&!t.logo&&!t.credito) return ms;
  return ms.map(m=>m.logo||m.credito?m:{...m,logo:t.logo,logoPos:t.logoPos,credito:t.credito,cor:t.cor,moldura:t.moldura});
}
export function gravarModelos(b:Biblioteca){
  try{ localStorage.setItem(K,JSON.stringify(b)); return true; }catch{ return false; }
}

type Cfg = {servidor:string;servidorToken:string};
async function chamar(cfg:Cfg,metodo:string,corpo?:unknown):Promise<Biblioteca>{
  const h:Record<string,string>={}; if(cfg.servidorToken) h['X-Token']=cfg.servidorToken;
  if(corpo!==undefined) h['Content-Type']='application/json';
  const r=await fetch(cfg.servidor+'/modelos',{method:metodo,headers:h,body:corpo!==undefined?JSON.stringify(corpo):undefined});
  const j=await r.json().catch(()=>({}));
  if(r.status===404) throw new Error('O servidor está em uma versão antiga, sem a biblioteca de templates. No celular, rode "git pull" na pasta do projeto e inicie o servidor de novo.');
  if(!r.ok) throw new Error(j.detail||`O servidor respondeu com erro ${r.status}.`);
  return {atualizado:+(j.atualizado||0),modelos:(j.modelos||[]).map(completar)};
}
export const enviarModelos=(cfg:Cfg,b:Biblioteca,presets:Preset[])=>chamar(cfg,'POST',{atualizado:b.atualizado,modelos:b.modelos.map(m=>comLeg(m,presets))});
/**
 * Deixa o navegador e o servidor com a mesma biblioteca: vale a que foi mexida por último.
 * Devolve a biblioteca que ficou valendo.
 */
export async function sincronizar(cfg:Cfg,local:Biblioteca,presets:Preset[]):Promise<Biblioteca>{
  const remoto=await chamar(cfg,'GET');
  if(remoto.modelos.length&&remoto.atualizado>local.atualizado) return remoto;
  if(local.atualizado>remoto.atualizado) return enviarModelos(cfg,local,presets);
  if(!local.atualizado&&remoto.modelos.length){
    // Nenhum dos dois foi mexido ainda: fica com o do servidor (traz o template antigo do agente) e leva a marca do navegador.
    const junto={atualizado:Date.now()/1000,modelos:comMarcaAntiga(remoto.modelos)};
    return enviarModelos(cfg,junto,presets);
  }
  return local;
}

// ---------------------------------------------------------------- aplicar nos cortes
export const marcaDe=(m:Modelo):Template=>({ativo:!!(m.logo||m.credito.trim()||m.moldura),logo:m.logo,logoPos:m.logoPos,credito:m.credito,cor:m.cor,moldura:m.moldura});
export const visualDe=(m:Modelo):VisualClip=>({layout:m.layout,zoom:m.zoom,posX:m.posX,posY:m.posY,jogo:{...m.jogo},camera:{...m.camera},divisao:m.divisao,gancho:m.gancho,ganchoPos:m.ganchoPos,legendaPos:m.legendaPos,marca:marcaDe(m),resolucao:m.resolucao,qualidade:m.qualidade});
/** O que muda em um corte quando ele recebe um template. É uma cópia: ajustar o corte depois não altera o template. */
export function aplicarModelo(m:Modelo):Partial<Clip>{
  return {modelo:m.id,visual:visualDe(m),formato:m.formato,legenda:m.legenda,efeito:m.efeito,tarja:m.tarja?{...m.tarja}:null,semTemplate:false};
}
export const semModelo=():Partial<Clip>=>({modelo:'',visual:null,semTemplate:true});
/** Leva os ajustes feitos em um corte de volta para o template (só quando a pessoa pede). */
export function modeloDoCorte(m:Modelo,c:Clip):Modelo{
  const v=c.visual;
  return {...m,formato:c.formato,legenda:c.legenda,efeito:EFEITOS_MODELO.some(([id])=>id===c.efeito)?c.efeito:m.efeito,tarja:c.tarja?{...c.tarja}:null,
    ...(v?{layout:v.layout,zoom:v.zoom,posX:v.posX,posY:v.posY,jogo:{...v.jogo},camera:{...v.camera},divisao:v.divisao,gancho:v.gancho,ganchoPos:v.ganchoPos,legendaPos:v.legendaPos}:{})};
}

/**
 * Tudo o que o desenho de um corte precisa. A prévia do editor, a prévia da edição em lote e a exportação
 * chamam esta mesma função, por isso mostram o mesmo resultado.
 */
export function optsDoClip(c:Clip,cues:Cue[],template:Template,presets:Preset[]):Omit<RenderOpts,'logoImg'|'rosto'>{
  const v=c.visual||null;
  let legenda=presets.find(p=>p.id===c.legenda)||null;
  if(legenda&&v) legenda={...legenda,position:v.legendaPos==='meio'?'center':legenda.position==='center'?'center-bottom':legenda.position};
  const marca=c.semTemplate?{...template,ativo:false}:v?v.marca:template;
  return {legenda,efeito:c.efeito,cues,gancho:c.gancho_texto,accent:legenda?.highlightColor||marca.cor,template:marca,tarja:c.tarja,visual:v};
}
export function saidaDoClip(c:Clip):Saida|null{
  const v=c.visual; if(!v) return null;
  return {escala:v.resolucao===720?2/3:1,bitrate:Math.round(QUALIDADES[v.qualidade||'media'][1]*(v.resolucao===720?0.6:1))};
}
