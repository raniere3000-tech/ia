import { useEffect, useState } from 'react';
import { Scissors, Send, Bot, Loader2, Eye, Download, ArrowRight, AlertTriangle } from 'lucide-react';
import { useApp } from '../state';
import { useServidor } from './Servidor2';
import { verAgente, videoDoCorte, type CorteAgente, type VisaoAgente } from '../lib/agente';
import { catalogo, listarProjetos, horaTexto } from '../lib/api';

const ST:Record<string,[string,string]>={pronto:['Pronto','info'],agendado:['Agendado','warn'],postado:['Publicado','ok'],descartado:['Descartado','']};

/** Um corte com Ver e Baixar, direto do Início. */
function CorteMini({c}:{c:CorteAgente}){
  const {settings,toast}=useApp();
  const [url,setUrl]=useState(''); const [busy,setBusy]=useState(false);
  useEffect(()=>()=>{ if(url) URL.revokeObjectURL(url); },[url]);
  const trazer=async(baixar:boolean)=>{
    setBusy(true);
    try{
      const u=URL.createObjectURL(await videoDoCorte(settings,c.id));
      if(baixar){ const a=document.createElement('a'); a.href=u; a.download=(c.titulo.replace(/[\\/:*?"<>|]+/g,'').slice(0,60)||'corte')+'.mp4'; a.click(); setTimeout(()=>URL.revokeObjectURL(u),30000); }
      else setUrl(u);
    }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }finally{ setBusy(false); }
  };
  const [rot,cls]=ST[c.status]||[c.status,''];
  return <li className="pa-item">
    {url&&<video src={url} controls autoPlay playsInline className="pa-video"/>}
    <div className="pa-linha"><b>{c.titulo}</b><span className={'tag '+cls}>{rot}</span></div>
    <small className="muted">feito {horaTexto(c.criado)}{c.status==='agendado'&&c.quando?` · posta ${horaTexto(c.quando)}`:''}</small>
    {c.video&&<div className="row-gap left">
      {!url&&<button className="subtle sm" disabled={busy} onClick={()=>trazer(false)}>{busy?<Loader2 size={14} className="spin"/>:<Eye size={14}/>} Ver</button>}
      <button className="subtle sm" disabled={busy} onClick={()=>trazer(true)}><Download size={14}/> Baixar</button>
    </div>}
  </li>;
}

/** O que os três agentes estão fazendo agora e o que já fizeram, com o caminho para ver tudo. */
export default function PainelAgentes(){
  const {settings,go}=useApp();
  const [v,setV]=useState<VisaoAgente|null>(null); const [erro,setErro]=useState('');
  useEffect(()=>{
    let vivo=true;
    const ler=()=>{ if(document.visibilityState!=='visible') return; verAgente(settings).then(x=>{ if(vivo){ setV(x); setErro(''); } }).catch(e=>{ if(vivo) setErro(e instanceof Error?e.message:String(e)); }); };
    ler(); const t=setInterval(ler,15000); return ()=>{ vivo=false; clearInterval(t); };
  },[settings]);
  const proj=useServidor(c=>listarProjetos(c,'agente3'),20);
  const cat=useServidor(catalogo);
  const cortes=(v?.cortes||[]).filter(c=>c.status!=='descartado').sort((a,b)=>b.criado-a.criado);
  const prontos=cortes.filter(c=>c.status==='pronto').length;
  const agendados=cortes.filter(c=>c.status==='agendado').sort((a,b)=>(a.quando||0)-(b.quando||0));
  const postados=cortes.filter(c=>c.status==='postado').length;
  const v3=(proj.dados?.projetos||[]).slice(0,3);
  const fazendo3=(proj.dados?.projetos||[]).filter(p=>['queued','researching','narrating','generating_assets','rendering','assembling','validating'].includes(p.status)).length;
  const co=v?.config.cortes, po=v?.config.postagem;
  return <section className="panel painel-agentes">
    <div className="section-head"><h2><Bot size={18}/> Seus agentes</h2></div>
    {erro&&<p className="hint bad"><AlertTriangle size={14}/> {erro}</p>}
    <div className="pa-grade">
     <article className="pa-card">
      <div className="pa-topo"><Scissors size={17}/><b>Agente de cortes</b>{v&&<span className={'tag '+(co?.ligado?'ok':'')}>{co?.ligado?'Ligado':'Desligado'}</span>}</div>
      <p className="pa-agora">{!v?'Lendo...':v.atual.ocupado?<><Loader2 size={13} className="spin"/> {v.atual.etapa||'Trabalhando'}{v.atual.pct?` · ${Math.round(v.atual.pct)}%`:''}</>:co?.ligado?'Esperando a próxima busca':'Parado. Ligue em Agentes para ele começar.'}</p>
      <p className="pa-num"><b>{cortes.length}</b> corte(s) feitos · <b>{prontos}</b> pronto(s) para postar</p>
      {cortes.length>0?<ul className="pa-lista">{cortes.slice(0,3).map(c=><CorteMini key={c.id} c={c}/>)}</ul>:v&&<p className="hint">Nenhum corte ainda. Em Agentes, aprove um canal ou cole o link de um vídeo.</p>}
      <button className="primary sm" onClick={()=>go('agente','fila','radar')}>Ver todos os cortes <ArrowRight size={14}/></button>
     </article>

     <article className="pa-card">
      <div className="pa-topo"><Send size={17}/><b>Agente de postagem</b>{v&&<span className={'tag '+(po?.ligado?'ok':'')}>{po?.ligado?'Ligado':'Desligado'}</span>}</div>
      <p className="pa-num"><b>{agendados.length}</b> agendado(s) · <b>{postados}</b> publicado(s)</p>
      {agendados[0]?<p className="pa-agora">Próximo post: <b>{agendados[0].titulo}</b> em {horaTexto(agendados[0].quando)}</p>:<p className="pa-agora">{prontos?`${prontos} corte(s) esperando horário livre.`:'Nada agendado agora.'}</p>}
      <button className="subtle sm" onClick={()=>go('agente','postagem','posts')}>Ver postagem <ArrowRight size={14}/></button>
     </article>

     <article className="pa-card">
      <div className="pa-topo"><Bot size={17}/><b>Agente 3 (vídeos com IA)</b>{fazendo3>0&&<span className="tag warn">fazendo {fazendo3}</span>}</div>
      {v3.length>0?<ul className="pa-lista">{v3.map(p=><li key={p.id} className="pa-item"><button className="link-btn" onClick={()=>go('revisar',p.id,'fila')}>{p.titulo}</button><span className="tag">{cat.dados?.estados[p.status]||p.status}</span><small className="muted">{horaTexto(p.atualizado)}</small></li>)}</ul>
       :<p className="hint">Nenhum vídeo ainda. Use Criar um vídeo agora, logo acima.</p>}
      <button className="subtle sm" onClick={()=>go('automatico','','criar')}>Ver todos os vídeos <ArrowRight size={14}/></button>
     </article>
    </div>
    {v&&v.log.length>0&&<details className="pa-log"><summary>O que aconteceu por último</summary>
     <ul className="ag-log">{v.log.slice(0,8).map((l,i)=><li key={i} className={l.tipo}><time>{horaTexto(l.t)}</time><span>{l.texto}</span></li>)}</ul></details>}
  </section>;
}
