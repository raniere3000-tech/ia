import { useCallback, useEffect, useState } from 'react';
import { AlertOctagon, ArrowRight, BellRing, ChevronDown, ChevronUp, Clock } from 'lucide-react';
import { useApp, type Tab } from '../state';
import { useCfg } from './Servidor2';
import { avisarDecisao, haQuanto, lerDecisoes, type Decisao, type ListaDecisoes } from '../lib/decisoes';

const MINIMIZAR_MIN=30;
const ler=(k:string)=>{ try{ return localStorage.getItem(k)||''; }catch{ return ''; } };
const gravar=(k:string,v:string)=>{ try{ localStorage.setItem(k,v); }catch{ /* sem armazenamento */ } };
const K_VISTOS='studio_decisoes_vistas', K_MIN='studio_decisoes_min';
const TITULO_BASE=typeof document!=='undefined'?document.title.replace(/^\(\d+\+?\)\s*/,''):'';

/**
 * Faixa vermelha no topo de TODAS as telas: o que está parado esperando a sua decisão, com botão direto para cada item.
 * - pisca enquanto houver item urgente; "Depois" só encolhe a faixa por 30 min (volta na hora se chegar item novo);
 * - item novo ganha a marca NOVO e, se você permitiu, um aviso na barra do celular;
 * - o número também aparece no título da aba do navegador: (3) EstúdioClip.
 */
export default function FaixaDecisoes(){
  const cfg=useCfg(); const {go,tab,rotaExtra}=useApp();
  const [d,setD]=useState<ListaDecisoes|null>(null);
  const [aberta,setAberta]=useState(false);
  const [minAte,setMinAte]=useState(()=>Number(ler(K_MIN)||0));
  const [novas,setNovas]=useState<Set<string>>(new Set());
  const [agora,setAgora]=useState(Date.now());
  const carregar=useCallback(async()=>{
    if(!cfg.servidor) return;
    try{
      const r=await lerDecisoes(cfg); setD(r); setAgora(Date.now());
      const vistos=new Set(ler(K_VISTOS).split(',').filter(Boolean));
      const primeiraVez=!ler(K_VISTOS);
      const chegaram=r.itens.filter(x=>!vistos.has(x.chave));
      if(chegaram.length){
        setNovas(s=>new Set([...s,...chegaram.map(x=>x.chave)]));
        if(!primeiraVez){
          chegaram.filter(x=>x.urgente).slice(0,3).forEach(x=>{ void avisarDecisao(x); });
          if(chegaram.some(x=>x.urgente)){ setMinAte(0); gravar(K_MIN,'0'); }   // item urgente novo: a faixa volta grande
        }
      }
      gravar(K_VISTOS,r.itens.map(x=>x.chave).join(',')||'-');
    }catch{ /* servidor fora: tenta de novo daqui a pouco */ }
  },[cfg]);
  useEffect(()=>{ void carregar(); const t=setInterval(()=>{ if(document.visibilityState==='visible') void carregar(); },20000);
    const vis=()=>{ if(document.visibilityState==='visible') void carregar(); };
    const ev=()=>{ void carregar(); };
    document.addEventListener('visibilitychange',vis); addEventListener('focus',vis); addEventListener('estudio:decisoes',ev);
    return ()=>{ clearInterval(t); document.removeEventListener('visibilitychange',vis); removeEventListener('focus',vis); removeEventListener('estudio:decisoes',ev); }; },[carregar]);
  // trocou de tela (provavelmente depois de decidir algo): confere de novo em seguida
  useEffect(()=>{ const t=setTimeout(()=>{ void carregar(); },1500); return ()=>clearTimeout(t); },[tab,rotaExtra,carregar]);
  const urg=d?.urgentes||0, total=d?.total||0;
  useEffect(()=>{ document.title=urg?`(${urg>99?'99+':urg}) ${TITULO_BASE}`:TITULO_BASE; },[urg]);
  useEffect(()=>()=>{ document.title=TITULO_BASE; },[]);
  if(!cfg.servidor||!d||!total) return null;

  const minimizada=!aberta&&minAte>agora;
  const abrir=(x:Decisao)=>{ setAberta(false); setNovas(s=>{ const n=new Set(s); n.delete(x.chave); return n; }); go(x.ir.aba as Tab,x.ir.extra,x.ir.area); };
  const depois=()=>{ const ate=Date.now()+MINIMIZAR_MIN*60000; setMinAte(ate); gravar(K_MIN,String(ate)); setAberta(false); };
  const cls='faixa-dec '+(urg?'urgente':'calma')+(minimizada?' mini':'')+(aberta?' aberta':'');
  const primeira=d.itens[0];
  const frase=urg?<><b>{urg}</b> {urg===1?'coisa espera':'coisas esperam'} a <u>SUA</u> decisão</>:<><b>{total}</b> {total===1?'decisão sua':'decisões suas'} para quando puder</>;

  if(minimizada) return <div className={cls}>
    <button className="faixa-dec-mini" onClick={()=>setAberta(true)} aria-label={`${urg||total} itens esperando a sua decisão. Abrir a lista`}>
      <AlertOctagon size={16}/><span>{frase}</span><ChevronDown size={15}/></button></div>;

  const urgentes=d.itens.filter(x=>x.urgente), calmas=d.itens.filter(x=>!x.urgente);
  const linha=(x:Decisao)=><li key={x.chave} className={x.urgente?'urg':''}>
    <div className="fd-txt"><b>{x.titulo}{novas.has(x.chave)&&<em className="fd-novo">NOVO</em>}</b>
      {x.detalhe&&<span>{x.detalhe}</span>}
      <small>{x.quem}{x.quem&&x.desde?' · ':''}{x.desde?<><Clock size={11}/> esperando {haQuanto(x.desde,agora/1000)}</>:null}</small></div>
    <button className={x.urgente?'fd-ir':'subtle sm'} onClick={()=>abrir(x)}>{x.botao} <ArrowRight size={14}/></button></li>;

  return <div className={cls} role="region" aria-label="Espera a sua decisão">
    <div className="faixa-dec-topo">
      <span className="fd-icone" aria-hidden="true">{urg?<AlertOctagon size={26}/>:<BellRing size={22}/>}</span>
      <div className="fd-frase" aria-live="polite"><strong>{frase}</strong>
        {!aberta&&primeira&&<small>{primeira.titulo}{primeira.detalhe?`: ${primeira.detalhe.slice(0,90)}`:''}{d.itens.length>1?` (e mais ${d.itens.length-1})`:''}</small>}</div>
      <div className="fd-acoes">
        {!aberta&&d.itens.length===1?<button className="fd-ir" onClick={()=>abrir(primeira)}>{primeira.botao} <ArrowRight size={14}/></button>
          :<button className="fd-ir" onClick={()=>setAberta(!aberta)} aria-expanded={aberta}>{aberta?<>Fechar <ChevronUp size={14}/></>:<>Ver o que é <ChevronDown size={14}/></>}</button>}
        {urg>0&&<button className="fd-depois" onClick={depois} title={`Encolhe a faixa por ${MINIMIZAR_MIN} minutos. Item novo faz ela voltar.`}>Depois</button>}
      </div>
    </div>
    {aberta&&<div className="faixa-dec-lista">
      {urgentes.length>0&&<><div className="fd-grupo">Travando o trabalho agora</div><ul>{urgentes.map(linha)}</ul></>}
      {calmas.length>0&&<><div className="fd-grupo calmo">Quando puder</div><ul>{calmas.map(linha)}</ul></>}
      {d.fontes_com_erro.length>0&&<p className="fd-nota">Não consegui conferir: {d.fontes_com_erro.join(', ')}. Pode haver mais itens.</p>}
    </div>}
  </div>;
}
