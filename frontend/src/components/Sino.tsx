import { useCallback, useEffect, useRef, useState } from 'react';
import { Bell, BellRing, CheckCheck, X } from 'lucide-react';
import { useApp } from '../state';
import { useCfg } from './Servidor2';
import { avisarNoNavegador, lerAlertas, marcarLidas, type ListaAlertas } from '../lib/alertas';
import type { Tab } from '../state';

const hora=(t:number)=>new Date(t*1000).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
const lerVisto=()=>{ try{ return Number(localStorage.getItem('studio_alerta_visto')||0); }catch{ return 0; } };
const gravarVisto=(n:number)=>{ try{ localStorage.setItem('studio_alerta_visto',String(n)); }catch{ /* sem armazenamento */ } };

/** Sino de notificações: alertas do servidor (os mesmos do e-mail e do WhatsApp), com aviso do navegador. */
export default function Sino(){
  const cfg=useCfg(); const {go}=useApp();
  const [d,setD]=useState<ListaAlertas|null>(null); const [aberto,setAberto]=useState(false);
  const [perm,setPerm]=useState(typeof Notification==='undefined'?'indisponivel':Notification.permission);
  const ref=useRef<HTMLDivElement>(null);
  const ler=useCallback(async()=>{
    if(!cfg.servidor) return;
    try{
      const r=await lerAlertas(cfg); setD(r);
      const visto=lerVisto();
      if(visto&&r.ultimo>visto) r.alertas.filter(a=>a.n>visto).slice(0,3).reverse().forEach(a=>{ void avisarNoNavegador(a); });
      gravarVisto(r.ultimo);
    }catch{ /* servidor fora: tenta na próxima */ }
  },[cfg]);
  useEffect(()=>{ void ler(); const t=setInterval(()=>{ void ler(); },30000); return ()=>clearInterval(t); },[ler]);
  useEffect(()=>{ if(!aberto) return; const f=(e:MouseEvent)=>{ if(ref.current&&!ref.current.contains(e.target as Node)) setAberto(false); }; document.addEventListener('mousedown',f); return ()=>document.removeEventListener('mousedown',f); },[aberto]);
  if(!cfg.servidor) return null;
  const n=d?.nao_lidas||0;
  const lidas=async()=>{ try{ setD(await marcarLidas(cfg)); await ler(); }catch{ /* tenta depois */ } };
  const pedir=async()=>{ if(typeof Notification==='undefined') return; setPerm(await Notification.requestPermission()); };
  return <div className="sino" ref={ref}>
    <button className="icon-btn sino-btn" aria-label={`Notificações${n?`: ${n} nova(s)`:''}`} onClick={()=>{ setAberto(!aberto); if(!aberto) void ler(); }}>
      {n?<BellRing size={19}/>:<Bell size={19}/>}{n>0&&<span className="sino-num">{n>99?'99+':n}</span>}</button>
    {aberto&&<div className="sino-painel" role="dialog" aria-label="Notificações">
      <div className="sino-topo"><b>Notificações</b>
        {n>0&&<button className="link-btn" onClick={lidas}><CheckCheck size={14}/> Marcar como lidas</button>}
        <button className="icon-btn" aria-label="Fechar" onClick={()=>setAberto(false)}><X size={16}/></button></div>
      {perm==='default'&&<button className="primary sm sino-perm" onClick={pedir}><BellRing size={14}/> Avisar também na barra do celular</button>}
      {perm==='denied'&&<p className="hint">O navegador está bloqueando os avisos. Libere em Configurações do site &gt; Notificações.</p>}
      {!d?.alertas.length?<p className="muted">Nenhum alerta ainda.</p>
      :<ul className="sino-lista">{d.alertas.map(a=><li key={a.n} className={(a.n>(d.lido||0)?'nova ':'')+a.nivel}>
        <button onClick={()=>{ setAberto(false); if(a.destino) go(a.destino as Tab); }}>
          <b>{a.assunto}</b><small className="muted">{hora(a.t)}</small>
          {a.corpo&&<span>{a.corpo.split('\n').filter(Boolean).slice(0,3).join(' · ')}</span>}</button></li>)}</ul>}
      <p className="hint">Os avisos do navegador chegam enquanto o site estiver aberto (mesmo em outra aba). Com o site fechado, valem o e-mail e o WhatsApp.</p>
    </div>}
  </div>;
}
