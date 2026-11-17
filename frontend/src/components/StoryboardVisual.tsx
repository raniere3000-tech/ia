import { useEffect, useRef, useState } from 'react';
import { CheckCheck, Image as Img, Loader2, Wrench } from 'lucide-react';
import { useApp } from '../state';
import { assinarAsset, urlServidor } from '../lib/api';
import { esperar } from '../lib/diretor';
import { aprovarQuadros, corrigirCena, gerarQuadros, lerStoryboard, type CenaSB } from '../lib/estudio3';
import { useCfg, useServidor, erroTexto } from './Servidor2';

const ROTULO:Record<CenaSB['status'],string>={aprovada:'Aprovada',pronta_para_conferir:'Confira o quadro',mudou_depois_de_aprovar:'Mudou depois de aprovada',sem_miniatura:'Sem quadro ainda'};
const CAMERAS:[string,string][]=[['parado','Parada'],['aproximar','Aproxima'],['afastar','Afasta'],['panoramica','Panorâmica']];

/**
 * 3ª porta de aprovação: Pauta → Roteiro → Storyboard visual → Vídeo final.
 * As miniaturas vêm de uma prévia REAL de cada cena. Mudar uma cena derruba só a aprovação dela, e só ela é redesenhada.
 * Aprovar aqui NÃO publica nada: o vídeo final continua precisando da sua aprovação.
 */
export default function StoryboardVisual({pid}:{pid:string}){
  const {toast}=useApp(); const cfg=useCfg();
  const sb=useServidor(c=>lerStoryboard(c,pid),0,[pid]);
  const [urls,setUrls]=useState<Record<string,string>>({});
  const [trab,setTrab]=useState('');
  const vivo=useRef(true); useEffect(()=>()=>{ vivo.current=false; },[]);
  const cenas=sb.dados?.cenas||[];
  useEffect(()=>{ (async()=>{
    for(const c of cenas) for(const q of c.quadros){ if(urls[q.asset]) continue;
      try{ const u=urlServidor(cfg,await assinarAsset(cfg,q.asset)); if(vivo.current) setUrls(x=>({...x,[q.asset]:u})); }catch{ /* tenta de novo na próxima atualização */ } }
  })(); },[sb.dados?.versao,cenas.map(c=>c.hash).join()]); // eslint-disable-line react-hooks/exhaustive-deps
  async function aguardar(job:string,msg:string){
    const e=await esperar(cfg,job,x=>setTrab(`${msg} (${Math.round(x.progresso)}%)`),()=>!vivo.current);
    if(e.status!=='concluido') throw new Error(e.erro||'O celular não terminou os quadros.');
    await sb.recarregar();
  }
  async function gerar(ids?:string[]){ setTrab('Desenhando os quadros'); try{ const r=await gerarQuadros(cfg,pid,ids); await aguardar(r.job,'Desenhando os quadros'); }catch(e){ toast(erroTexto(e),'erro'); } finally{ if(vivo.current) setTrab(''); } }
  async function aprovar(ids?:string[]){ try{ sb.setDados(await aprovarQuadros(cfg,pid,ids)); toast(ids?'Cena aprovada.':'Todas as cenas aprovadas. O vídeo final ainda espera a sua aprovação.','ok'); }catch(e){ toast(erroTexto(e),'erro'); } }
  async function corrigir(c:CenaSB,m:Record<string,unknown>){ setTrab('Corrigindo e redesenhando só esta cena'); try{ const r=await corrigirCena(cfg,pid,c.id,m); sb.setDados(r); await aguardar(r.job,'Redesenhando só a cena '+c.n); }catch(e){ toast(erroTexto(e),'erro'); } finally{ if(vivo.current) setTrab(''); } }
  if(!cfg.servidor||!sb.dados) return null;
  const s=sb.dados;
  return <section className="panel storyboard-visual">
    <div className="section-head"><h2><Img size={17}/> Storyboard visual: conferir os quadros</h2></div>
    <p className="hint">Terceira porta de aprovação (Pauta → Roteiro → <b>Storyboard visual</b> → Vídeo final). Os quadros são tirados de uma prévia pequena e real de cada cena. {s.ativa?'Esta porta está LIGADA neste projeto: o vídeo final espera você aprovar os quadros.':'Esta porta está desligada neste projeto (ligue em “Quem confere”, no briefing).'}</p>
    <div className="row-gap left">
      <button className="primary" disabled={!!trab} onClick={()=>gerar()}>{trab?<Loader2 size={15} className="spin"/>:<Img size={15}/>} {cenas.some(c=>c.quadros.length)?'Atualizar quadros':'Gerar quadros'}</button>
      <button className="subtle" disabled={!!trab||s.todas_aprovadas||cenas.some(c=>!c.quadros.length)} onClick={()=>aprovar()}><CheckCheck size={15}/> Aprovar todas as cenas</button>
    </div>
    {trab&&<p className="hint mt"><Loader2 size={13} className="spin"/> {trab}</p>}
    <div className="sb-grade mt">{cenas.map(c=><article key={c.id} className={'sb-cena '+c.status}>
      <header><b>{c.n}. {c.titulo||'Cena'}</b><span className={'chip '+(c.status==='aprovada'?'on':'')}>{ROTULO[c.status]}</span></header>
      <div className="sb-quadros">{c.quadros.map((q,k)=>urls[q.asset]?<figure key={k}><img src={urls[q.asset]} alt={`Quadro ${k+1} da cena ${c.n}: plano ${q.plano}`}/><figcaption>{q.plano}{q.personagem?` · ${q.personagem}`:''} · {q.t.toFixed(1)} s</figcaption></figure>:<div key={k} className="sb-vazio">carregando…</div>)}
        {!c.quadros.length&&<div className="sb-vazio">{c.quadros_desatualizados?'A cena mudou: gere o quadro de novo.':'Sem quadro ainda.'}</div>}</div>
      <small className="hint">Câmera: {c.camera||'padrão'}{c.duracao?` · ${c.duracao} s`:''}{c.personagem?` · fala: ${c.personagem}`:''}{c.ja_aprovada_antes?' · já tinha sido aprovada antes da mudança':''}</small>
      <div className="row-gap left">
        <label className="sm">Câmera<select value={CAMERAS.some(x=>x[0]===c.camera)?c.camera:'parado'} disabled={!!trab} onChange={e=>corrigir(c,{camera:e.target.value})}>{CAMERAS.map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label>
        <button className="subtle sm" disabled={!!trab} onClick={()=>gerar([c.id])}><Wrench size={13}/> Refazer só esta</button>
        <button className="primary sm" disabled={!!trab||c.status==='aprovada'||!c.quadros.length} onClick={()=>aprovar([c.id])}>Aprovar esta</button>
      </div>
    </article>)}</div>
    <small className="hint">{s.aviso_final} A aprovação vale para a versão atual de cada cena: mudou algo, ela pede de novo.</small>
  </section>;
}
