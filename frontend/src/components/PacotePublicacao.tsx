import { useEffect, useRef, useState } from 'react';
import { CheckCheck, Copy, Loader2, Package, Save } from 'lucide-react';
import { useApp } from '../state';
import { cabAuth, urlServidor } from '../lib/api';
import { aprovarPacote, editarPacote, lerPacote, montarPacote, type Pacote } from '../lib/estudio3';
import { Modal } from './Help';
import { useCfg, erroTexto } from './Servidor2';

const REDES:[string,string][]=[['youtube','YouTube Shorts'],['instagram','Instagram Reels'],['tiktok','TikTok'],['facebook','Facebook Reels'],['kwai','Kwai (manual)']];
const ICONE={ok:'✓',aviso:'!',erro:'✗',nao_verificado:'?'} as const;

/** Pacote de publicação de um corte: capa, título, descrição no formato fixo, conformidade por rede e aprovação presa ao hash. Nada é publicado aqui. */
export default function PacotePublicacao({corte,onClose}:{corte:string;onClose:()=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const [p,setP]=useState<Pacote|null>(null); const [desc,setDesc]=useState(''); const [busy,setBusy]=useState('');
  const [capas,setCapas]=useState<Record<string,string>>({}); const vivo=useRef(true);
  useEffect(()=>()=>{ vivo.current=false; },[]);
  const aplicar=(x:Pacote)=>{ setP(x); setDesc(x.descricao); };
  useEffect(()=>{ lerPacote(cfg,corte).then(aplicar).catch(()=>setP(null)); },[corte]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(()=>{ (async()=>{ if(!p) return; for(const c of p.capas){ const k=p.hash+c.indice; if(capas[k]) continue;
    try{ const r=await fetch(urlServidor(cfg,`/agente/cortes/${corte}/pacote/capa/${c.indice}`),{headers:cabAuth(cfg.servidorToken)}); if(r.ok){ const b=await r.blob(); if(vivo.current) setCapas(x=>({...x,[k]:URL.createObjectURL(b)})); } }catch{ /* sem miniatura */ } } })(); },[p?.hash]); // eslint-disable-line react-hooks/exhaustive-deps
  async function rodar(nome:string,f:()=>Promise<Pacote>,ok?:string){ setBusy(nome); try{ aplicar(await f()); if(ok) toast(ok,'ok'); }catch(e){ toast(erroTexto(e),'erro'); } finally{ setBusy(''); } }
  return <Modal title="Pacote de publicação" onClose={onClose} wide>
    {!p&&<div><p className="hint">Este corte ainda não tem pacote. O pacote junta capa, título, descrição, conferência por rede e a sua aprovação antes de publicar.</p>
      <button className="primary" disabled={!!busy} onClick={()=>rodar('montar',()=>montarPacote(cfg,corte))}>{busy?<Loader2 size={15} className="spin"/>:<Package size={15}/>} Montar o pacote</button></div>}
    {p&&<div className="pacote">
      <p className="hint">{p.aprovado_agora?<b>✓ Pacote aprovado nesta versão ({p.hash}).</b>:'Ainda não aprovado nesta versão.'} Mudou texto ou capa? A aprovação cai e as redes são conferidas de novo, sem refazer o vídeo.</p>
      <span className="field-label">Capas sugeridas (quadros reais do vídeo, escolhidos pelo maior detalhe)</span>
      <div className="row-gap left">{p.capas.map(c=><label key={c.indice} className={'gp-gancho '+(p.capa_escolhida===c.indice?'on':'')}><input type="radio" name="capa" checked={p.capa_escolhida===c.indice} onChange={()=>rodar('capa',()=>editarPacote(cfg,corte,{capa:c.indice}))}/> {capas[p.hash+c.indice]&&<img src={capas[p.hash+c.indice]} alt={`Capa ${c.indice+1}`} style={{height:120,borderRadius:8,display:'block'}}/>} Capa {c.indice+1} · {c.t.toFixed(1)} s · {(c.bytes/1024).toFixed(0)} KB</label>)}</div>
      <small className="hint">O envio automático da capa para as redes ainda não está ligado: a capa escolhida fica guardada com o pacote.</small>
      <label>Título<input value={p.titulo} maxLength={150} onChange={e=>setP({...p,titulo:e.target.value})} onBlur={()=>rodar('titulo',()=>editarPacote(cfg,corte,{titulo:p.titulo}))}/></label>
      {p.titulos_sugeridos.length>1&&<div className="chips">{p.titulos_sugeridos.map(t=><button key={t} type="button" className="chip" onClick={()=>rodar('titulo',()=>editarPacote(cfg,corte,{titulo:t}))}>{t.slice(0,50)}</button>)}</div>}
      <label>Descrição (termina sempre em “Link original do vídeo []”; nada vem depois)<textarea rows={8} value={desc} onChange={e=>setDesc(e.target.value)}/></label>
      <div className="row-gap left"><button className="subtle sm" disabled={!!busy||desc===p.descricao} onClick={()=>rodar('desc',()=>editarPacote(cfg,corte,{descricao:desc}),'Descrição salva e redes conferidas de novo.')}><Save size={13}/> Salvar descrição</button>
        <button className="subtle sm" onClick={()=>rodar('montar',()=>montarPacote(cfg,corte,p.redes))}>Refazer o pacote</button></div>
      <span className="field-label mt">Redes de destino</span>
      <div className="chips">{REDES.map(([id,n])=><button key={id} type="button" className={'chip '+(p.redes.includes(id)?'on':'')} aria-pressed={p.redes.includes(id)} onClick={()=>rodar('redes',()=>editarPacote(cfg,corte,{redes:p.redes.includes(id)?p.redes.filter(x=>x!==id):[...p.redes,id]}))}>{n}</button>)}</div>
      {Object.entries(p.conformidade).map(([r,c])=><details key={r} className="gp-destaque" open={!c.pode_aprovar}><summary><b>{c.nome}</b> — {c.pode_aprovar?'pode aprovar':'tem erro para corrigir'}</summary>
        <ul className="hint">{c.itens.map((i,k)=><li key={k}><b>{ICONE[i.estado]}</b> {i.item}: {i.detalhe}{i.estado!=='ok'&&i.estado!=='nao_verificado'&&i.corrigir?` — ${i.corrigir}`:''}</li>)}</ul></details>)}
      <small className="hint">{p.aviso_limites} Itens com “?” o EstúdioClip não consegue conferir sozinho.</small>
      <span className="field-label mt">Comentário fixado (para copiar)</span>
      <div className="row-gap left"><small className="grow">{p.comentario_fixado.texto}</small><button className="subtle sm" onClick={()=>{ navigator.clipboard?.writeText(p.comentario_fixado.texto); toast('Copiado.','ok'); }}><Copy size={13}/> Copiar</button></div>
      <small className="hint">{p.comentario_fixado.aviso}</small>
      <div className="row-gap left mt"><button className="primary" disabled={!!busy||p.aprovado_agora} onClick={()=>rodar('aprovar',()=>aprovarPacote(cfg,corte),'Pacote aprovado. O Agente 2 vai usar exatamente este texto e este arquivo.')}>{busy==='aprovar'?<Loader2 size={15} className="spin"/>:<CheckCheck size={15}/>} Aprovar este pacote</button></div>
    </div>}
  </Modal>;
}
