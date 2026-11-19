/**
 * Registro único das 5 áreas e de cada tela (seção) dentro delas, e o roteador de endereços (#...).
 *
 * - Endereço novo: #<área>/<seção>[/<extra>]   ex.: #agentes/visao-geral, #agentes/coordenador/ordens:abc, #edicao/manual
 * - Endereço antigo continua valendo: #<aba>[/<extra>]   ex.: #coordenador/ordens:abc, #thumbnails/galeria:j1, #revisar/<projeto>
 * - A "aba" (Tab) continua sendo a identidade técnica da tela: as páginas chamam go('coordenador', ...) como antes.
 *
 * Este arquivo não importa nada de React: é testado sozinho (frontend/testes/rotas.test.ts).
 */

export type Area = 'inicio'|'agentes'|'edicao'|'estudio-ia'|'publicacoes';
/** Telas (mesma lista de `Tab` em state.ts). */
export type Aba = 'inicio'|'radar'|'cortes'|'video'|'vozes'|'manual'|'agendar'|'agente'|'estilos'|'templates'|'config'|'ia'|'automatico'|'projetos'|'galeria'|'fila'|'revisar'|'series'|'central'|'live'|'thumbnails'|'coordenador'
  |'agentes'|'edicao'|'estudioIA';

export const AREAS:{id:Area;nome:string;curto:string;descricao:string}[] = [
  {id:'inicio',nome:'Início',curto:'Início',descricao:'Resumo da produção'},
  {id:'agentes',nome:'Agentes',curto:'Agentes',descricao:'Os sete agentes, o Coordenador e a automação'},
  {id:'edicao',nome:'Estúdio de Edição',curto:'Edição',descricao:'Montagem manual, radar, cortes, templates e legendas'},
  {id:'estudio-ia',nome:'Estúdio IA',curto:'IA',descricao:'Criar com IA, séries, produção em lote e biblioteca criativa'},
  {id:'publicacoes',nome:'Publicações',curto:'Posts',descricao:'Calendário, posts, contas e resultados'},
];

/** Página inicial de cada área. Agentes: MODELO B (painel dos sete agentes primeiro, nunca o chat). */
export const INICIOS:Record<Area,string> = {
  inicio:'inicio', agentes:'agentes/visao-geral', edicao:'edicao/inicio', 'estudio-ia':'estudio-ia/inicio', publicacoes:'publicacoes/calendario',
};

export type Secao = {
  area:Area;
  /** Caminho dentro da área (pode ter "/", ex.: "agente/6"). */
  secao:string;
  aba:Aba;
  /** Extra fixo desta seção (ex.: Memória = Coordenador na subaba "memoria"). */
  extra?:string;
  nome:string;
  /** Aparece no submenu da área. */
  menu:boolean;
  /** Abre em outra área (atalho). */
  irPara?:Area;
};

export const SECOES:Secao[] = [
  {area:'inicio',secao:'',aba:'inicio',nome:'Início',menu:false},
  // ---- Agentes (Modelo B)
  {area:'agentes',secao:'visao-geral',aba:'agentes',nome:'Visão geral',menu:true},
  {area:'agentes',secao:'coordenador',aba:'coordenador',nome:'Coordenador-Geral',menu:true},
  {area:'agentes',secao:'esteira',aba:'coordenador',extra:'esteira',nome:'Esteira dos 7 agentes',menu:true},
  {area:'agentes',secao:'configurar',aba:'agente',nome:'Configurar agentes',menu:true},
  {area:'agentes',secao:'execucoes',aba:'fila',nome:'Execuções',menu:true},
  {area:'agentes',secao:'aprovacoes',aba:'revisar',nome:'Aprovações',menu:true},
  {area:'agentes',secao:'automacao',aba:'central',nome:'Automação',menu:true},
  {area:'agentes',secao:'memoria',aba:'coordenador',extra:'memoria',nome:'Memória e aprendizado',menu:true},
  {area:'agentes',secao:'skills',aba:'central',extra:'historico',nome:'Skills e ferramentas',menu:true},
  {area:'agentes',secao:'agente/6',aba:'thumbnails',nome:'Capas (Agente 6)',menu:true},
  // ---- Estúdio de Edição
  {area:'edicao',secao:'inicio',aba:'edicao',nome:'Começar',menu:true},
  {area:'edicao',secao:'manual',aba:'manual',nome:'Montagem manual',menu:true},
  {area:'edicao',secao:'radar',aba:'radar',nome:'Radar de vídeos',menu:true},
  {area:'edicao',secao:'cortes',aba:'cortes',nome:'Gerar cortes',menu:true},
  {area:'edicao',secao:'templates',aba:'templates',nome:'Templates',menu:true},
  {area:'edicao',secao:'legendas-efeitos',aba:'estilos',nome:'Legendas e efeitos',menu:true},
  {area:'edicao',secao:'vozes',aba:'vozes',nome:'Áudio e vozes',menu:true},
  {area:'edicao',secao:'live',aba:'live',nome:'Live',menu:true},
  {area:'edicao',secao:'projetos',aba:'projetos',nome:'Meus projetos',menu:true},
  // ---- Estúdio IA
  {area:'estudio-ia',secao:'inicio',aba:'estudioIA',nome:'Começar',menu:true},
  {area:'estudio-ia',secao:'criar',aba:'ia',nome:'Criar com IA',menu:true},
  {area:'estudio-ia',secao:'series',aba:'series',nome:'Séries e personagens',menu:true},
  {area:'estudio-ia',secao:'lote',aba:'automatico',nome:'Produção em lote',menu:true},
  {area:'estudio-ia',secao:'biblioteca',aba:'galeria',nome:'Biblioteca criativa',menu:true},
  {area:'estudio-ia',secao:'vozes',aba:'vozes',nome:'Vozes',menu:true},
  {area:'estudio-ia',secao:'animado',aba:'video',nome:'Animado no navegador',menu:true},
  {area:'estudio-ia',secao:'projetos',aba:'projetos',nome:'Projetos IA',menu:true},
  // ---- Publicações
  {area:'publicacoes',secao:'calendario',aba:'agendar',nome:'Posts e contas',menu:true},
  {area:'publicacoes',secao:'programacao',aba:'agente',extra:'programacao',nome:'Programação diária',menu:true},
  {area:'publicacoes',secao:'linhas',aba:'central',extra:'calendario',nome:'Calendário das linhas',menu:true},
  {area:'publicacoes',secao:'resultados',aba:'agente',extra:'desempenho',nome:'Resultados',menu:true},
  {area:'publicacoes',secao:'agente2',aba:'agente',extra:'postagem',nome:'Ajustes do Agente 2',menu:true,irPara:'agentes'},
  // ---- fora das 5 áreas
  {area:'inicio',secao:'config',aba:'config',nome:'Ajustes',menu:false},
];

/** Telas antigas → seção onde moram agora (a primeira seção de cada aba na lista acima, sem extra fixo). */
const PRINCIPAL:Partial<Record<Aba,Secao>> = {};
for(const s of SECOES) if(!s.irPara&&!s.extra&&!PRINCIPAL[s.aba]) PRINCIPAL[s.aba]=s;
// Vozes, animado e projetos: o destino canônico fica no Estúdio IA (o atalho do Estúdio de Edição mantém a volta).
PRINCIPAL.vozes=SECOES.find(s=>s.area==='estudio-ia'&&s.aba==='vozes');
PRINCIPAL.projetos=SECOES.find(s=>s.area==='estudio-ia'&&s.aba==='projetos');

export const ABAS:Aba[] = [...new Set(SECOES.map(s=>s.aba))];
export const ehAba=(x:string):x is Aba=>(ABAS as string[]).includes(x);
export const ehArea=(x:string):x is Area=>AREAS.some(a=>a.id===x);

/** Nomes de área usados pelo código antigo em go(aba, extra, área). */
const AREA_ANTIGA:Record<string,Area> = {automacao:'agentes',fila:'agentes',posts:'publicacoes',radar:'edicao'};

export type Rota = {area:Area; aba:Aba; extra:string; secao:Secao};

const primeiro=(extra:string)=>extra.split(/[/:]/)[0];
/** A seção encaixa nesta aba/extra? (sem extra fixo encaixa em qualquer extra; com extra fixo, só nele) */
const encaixa=(s:Secao,aba:Aba,extra:string)=>s.aba===aba&&!s.irPara&&(!s.extra||s.extra===primeiro(extra));

/** Escolhe a seção de uma aba: primeiro na área preferida; senão uma com o mesmo extra fixo; senão a principal. */
export function secaoDe(aba:Aba,extra='',preferida?:Area|string):Secao{
  const pref=preferida&&ehArea(preferida)?preferida:preferida?AREA_ANTIGA[preferida]:undefined;
  const naArea=pref?SECOES.filter(s=>s.area===pref&&encaixa(s,aba,extra)):[];
  const exata=(l:Secao[])=>l.find(s=>s.extra&&s.extra===primeiro(extra))||l.find(s=>!s.extra);
  return exata(naArea)||SECOES.find(s=>s.aba===aba&&!s.irPara&&!!s.extra&&s.extra===primeiro(extra))||PRINCIPAL[aba]||SECOES[0];
}

/** Lê o endereço (com ou sem "#"). Endereço desconhecido abre o Início. */
export function lerRota(hash:string):Rota{
  let h=hash.replace(/^#/,'');
  try{ h=decodeURIComponent(h); }catch{ /* endereço quebrado: usa como veio */ }
  const partes=h.split('/').filter((x,i)=>i===0||x!=='');
  const [p0='',...resto]=partes;
  if(ehArea(p0)&&p0!=='inicio'){
    // a seção mais comprida que casa com o começo do caminho (ex.: "agente/6" antes de "agente")
    const doArea=SECOES.filter(s=>s.area===p0&&s.secao).sort((a,b)=>b.secao.length-a.secao.length);
    const caminho=resto.join('/');
    const s=doArea.find(x=>caminho===x.secao||caminho.startsWith(x.secao+'/'));
    if(s){
      const extra=caminho.slice(s.secao.length+1);
      if(s.irPara){ const alvo=secaoDe(s.aba,s.extra,s.irPara); return {area:alvo.area,aba:s.aba,extra:extra||s.extra||'',secao:alvo}; }
      return {area:s.area,aba:s.aba,extra:extra||s.extra||'',secao:s};
    }
    // só a área (ou seção desconhecida): abre a página inicial da área
    return lerRota(INICIOS[p0]);
  }
  if(ehAba(p0)){
    const extra=resto.join('/');
    const s=secaoDe(p0,extra);
    return {area:s.area,aba:p0,extra,secao:s};
  }
  return {area:'inicio',aba:'inicio',extra:'',secao:SECOES[0]};
}

/** Monta o endereço novo de uma aba (o extra vai codificado, como antes). */
export function enderecoDe(aba:Aba,extra='',preferida?:Area|string):string{
  if(aba==='inicio') return '#inicio';
  if(aba==='config') return '#config'+(extra?'/'+encodeURIComponent(extra):'');
  const s=secaoDe(aba,extra,preferida);
  const resto=extra&&extra!==s.extra?'/'+encodeURIComponent(extra):'';
  return '#'+s.area+'/'+s.secao+resto;
}

/** Endereço antigo → novo (para links e favoritos guardados). */
export const legadoParaCanonico=(hash:string)=>{ const r=lerRota(hash); return enderecoDe(r.aba,r.extra,r.area); };

/** Seções que aparecem no submenu da área. */
export const menuDa=(area:Area)=>SECOES.filter(s=>s.area===area&&s.menu);

/** A seção do submenu que fica marcada para esta tela. */
export function secaoAtiva(area:Area,aba:Aba,extra:string):Secao|undefined{
  const l=SECOES.filter(s=>s.area===area&&s.aba===aba&&!s.irPara);
  return l.find(s=>s.extra&&s.extra===primeiro(extra))||l.find(s=>!s.extra);
}

/** Área preferida num go(aba, extra, área): área nova, nome antigo convertido, ou (sem nada) a área onde a pessoa está. */
export const areaPreferida=(param:string|undefined,atual:Area):Area=>param&&ehArea(param)?param:(param&&AREA_ANTIGA[param])||atual;
