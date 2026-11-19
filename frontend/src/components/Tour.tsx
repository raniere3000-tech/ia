import { useEffect, useLayoutEffect, useState } from 'react';
import { X, Sparkles } from 'lucide-react';
import { store } from '../lib/store';
import type { Tab } from '../state';

/** Versão do tour: muda quando houver novidade que vale mostrar de novo. */
const VERSAO=3;
type Passo={alvo:string[];aba?:Tab;titulo:string;texto:string;exemplo:string};
const PASSOS:Passo[]=[
  {alvo:['area-inicio'],aba:'inicio',titulo:'1. Início',texto:'O resumo da produção com números reais do servidor: vídeos produzidos, agendados, publicados, quem está trabalhando agora, a próxima publicação e o que precisa da sua atenção.',exemplo:'Troque Hoje / 7 dias / 30 dias para ver outro período.'},
  {alvo:['area-agentes'],aba:'agentes',titulo:'2. Agentes',texto:'Abre no painel dos sete agentes: o que cada um faz agora, quanto trabalhou e onde configurar. No submenu ficam o Coordenador-Geral, Configurar agentes, Execuções, Aprovações, Automação, Memória e Skills.',exemplo:'Agentes > cartão do Agente 7 > Conversar.'},
  {alvo:['area-edicao'],aba:'edicao',titulo:'3. Estúdio de Edição',texto:'Para criar à mão: novo projeto, continuar projeto, editor (montagem manual), Radar e cortes, templates, legendas e efeitos, vozes e Live.',exemplo:'Estúdio de Edição > Radar e Cortes.'},
  {alvo:['area-estudio-ia'],aba:'estudioIA',titulo:'4. Estúdio IA',texto:'Para criar a partir de uma ideia: Criar com IA (Agente 3), Séries e personagens, Produção em lote e Biblioteca criativa.',exemplo:'Estúdio IA > Criar com IA > escreva "Por que o céu é azul?".'},
  {alvo:['area-publicacoes'],aba:'agendar',titulo:'5. Publicações',texto:'Posts agendados e publicados, contas das redes, programação diária e resultados. Vídeo do Agente 3 só chega aqui depois da sua aprovação.',exemplo:'Conecte o YouTube uma vez em Publicações > Posts e contas.'},
  {alvo:['ajustes','ajustes-movel'],aba:'config',titulo:'6. Ajustes (engrenagem)',texto:'Servidor do celular, aparelhos conectados (código de uso único), chaves, e-mail, backups e diagnóstico. O balão de conversa no topo abre o Coordenador em qualquer tela.',exemplo:'Conectar o notebook: Ajustes > Aparelhos > Gerar código.'},
  {alvo:[],titulo:'7. Pronto!',texto:'Cada tela tem um botão ? com a explicação daquela parte. O tutorial fica em Ajustes e no ? do topo. O que depende de configuração ou de teste no aparelho aparece marcado, nunca como pronto.',exemplo:'Endereços antigos salvos nos favoritos continuam abrindo a tela certa.'},
];

type Estado={versao:number;resposta:'concluido'|'depois'|'nunca'|''};
const ler=():Estado=>({versao:0,resposta:'',...store.json<Partial<Estado>>('studio_tour',{})});

export default function Tour({aberto,fechar,abrir,go,naInicio}:{aberto:boolean;fechar:()=>void;abrir:()=>void;go:(t:Tab)=>void;naInicio:boolean}){
  const [convite,setConvite]=useState(false);
  const [i,setI]=useState(0);
  const [caixa,setCaixa]=useState<DOMRect|null>(null);
  useEffect(()=>{ const e=ler(); if(e.resposta!=='nunca'&&e.versao<VERSAO&&!/^#(par|senha)=/.test(location.hash)){ const t=setTimeout(()=>setConvite(true),1800); return ()=>clearTimeout(t); } },[]);
  useEffect(()=>{ if(aberto){ setConvite(false); setI(0); } },[aberto]);
  const p=PASSOS[i];
  useEffect(()=>{ if(aberto&&p.aba) go(p.aba); },[aberto,i]);   // eslint-disable-line react-hooks/exhaustive-deps
  useLayoutEffect(()=>{
    if(!aberto){ setCaixa(null); return; }
    const medir=()=>{ const el=p.alvo.map(a=>document.querySelector<HTMLElement>(`[data-tour="${a}"]`)).find(e=>e&&e.offsetParent!==null); setCaixa(el?el.getBoundingClientRect():null); };
    medir(); const t=setTimeout(medir,250); addEventListener('resize',medir);
    return ()=>{ clearTimeout(t); removeEventListener('resize',medir); };
  },[aberto,i,p]);
  const responder=(r:Estado['resposta'])=>{ store.setJson('studio_tour',{versao:VERSAO,resposta:r}); setConvite(false); };
  // O convite só aparece no Início, para não cobrir botões enquanto você trabalha.
  if(convite&&!aberto&&naInicio) return <div className="tour-convite" role="dialog" aria-label="Conhecer o novo EstúdioClip">
    <Sparkles size={20}/><div><b>Quer conhecer o novo EstúdioClip?</b><p>Agora são cinco áreas e o servidor do celular guarda seus projetos. O tour leva 1 minuto.</p>
    <div className="row-gap left"><button className="primary sm" onClick={()=>{ responder('concluido'); abrir(); }}>Começar</button><button className="subtle sm" onClick={()=>responder('depois')}>Agora não</button><button className="link-btn" onClick={()=>responder('nunca')}>Não mostrar novamente</button></div></div>
  </div>;
  if(!aberto) return null;
  const alto=typeof window!=='undefined'?window.innerHeight:800;
  const pos:React.CSSProperties=caixa?(caixa.top>alto/2?{bottom:alto-caixa.top+12}:{top:caixa.bottom+12}):{top:'50%',transform:'translateY(-50%)'};
  const sair=()=>{ store.setJson('studio_tour',{versao:VERSAO,resposta:'concluido'}); fechar(); };
  return <div className="tour-fundo" onMouseDown={sair}>
    {caixa&&<div className="tour-luz" style={{left:caixa.left-6,top:caixa.top-6,width:caixa.width+12,height:caixa.height+12}}/>}
    <div className="tour-caixa" style={pos} role="dialog" aria-modal="true" aria-label={p.titulo} onMouseDown={e=>e.stopPropagation()}>
     <div className="tour-topo"><small>{i+1} de {PASSOS.length}</small><button className="icon-btn" onClick={sair} aria-label="Fechar"><X size={17}/></button></div>
     <h3>{p.titulo}</h3><p>{p.texto}</p><p className="tour-ex"><b>Exemplo:</b> {p.exemplo}</p>
     <div className="row-gap left">{i>0&&<button className="subtle sm" onClick={()=>setI(i-1)}>Voltar</button>}
      {i<PASSOS.length-1?<><button className="link-btn" onClick={sair}>Pular</button><button className="primary sm" onClick={()=>setI(i+1)}>Próximo</button></>:<button className="primary sm" onClick={sair}>Concluir</button>}</div>
    </div>
  </div>;
}
