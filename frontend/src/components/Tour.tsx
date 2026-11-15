import { useEffect, useLayoutEffect, useState } from 'react';
import { X, Sparkles } from 'lucide-react';
import { store } from '../lib/store';
import type { Tab } from '../state';

/** Versão do tour: muda quando houver novidade que vale mostrar de novo. */
const VERSAO=2;
type Passo={alvo:string[];aba?:Tab;titulo:string;texto:string;exemplo:string};
const PASSOS:Passo[]=[
  {alvo:['area-inicio'],aba:'inicio',titulo:'1. Início',texto:'O resumo do dia: servidor do celular ligado ou não, vídeos produzindo, prontos para revisar e posts agendados. Daqui você continua de onde parou.',exemplo:'Toque em um vídeo pronto para revisar direto.'},
  {alvo:['area-criar'],aba:'ia',titulo:'2. Criar vídeos',texto:'O jeito mais fácil é o Agente 3: escreva o assunto, toque em Criar meu vídeo e o celular faz tudo. Vários de uma vez faz vídeos em série ou todo dia. Animado no navegador e Montagem manual são para quem quer montar à mão. Aqui também ficam Meus projetos, Vozes, Estilos e Templates.',exemplo:'Criar vídeos > Agente 3 > escreva "Por que o céu é azul?" > Criar meu vídeo.'},
  {alvo:['area-radar'],aba:'radar',titulo:'3. Radar e cortes',texto:'Descubra vídeos em alta, faça cortes de vídeos seus ou autorizados e configure o Agente 1, que procura e corta sozinho só de canais aprovados.',exemplo:'Use um assunto do Radar como tema de um vídeo ORIGINAL em Criar > Com IA.'},
  {alvo:['area-fila'],aba:'fila',titulo:'4. Fila e aprovações',texto:'Tudo o que o servidor está fazendo, com tempo decorrido e previsão medida no seu celular. Os vídeos prontos esperam aqui a sua decisão: aprovar, pedir correção ou rejeitar.',exemplo:'Revisar e aprovar pelo e-mail: responda APROVAR com o código que veio no e-mail.'},
  {alvo:['area-posts'],aba:'agendar',titulo:'5. Publicações',texto:'Contas das redes, agenda dos posts e o Agente 2, que publica nos horários marcados. Vídeo do Agente 3 só chega aqui depois da sua aprovação.',exemplo:'Conecte o YouTube uma vez em Agenda e contas.'},
  {alvo:['ajustes','ajustes-movel'],aba:'config',titulo:'6. Ajustes (engrenagem)',texto:'Servidor do celular, aparelhos conectados (código de uso único), chaves, e-mail, backups e diagnóstico.',exemplo:'Conectar o notebook: Ajustes > Aparelhos > Gerar código.'},
  {alvo:[],titulo:'7. Pronto!',texto:'Cada tela tem um botão ? com a explicação daquela parte. O tutorial fica em Ajustes e no ? do topo. O que depende de configuração ou de teste no aparelho aparece marcado, nunca como pronto.',exemplo:'Agendar o Agente 3 para 21h: Criar vídeos > Automático > Rotinas.'},
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
