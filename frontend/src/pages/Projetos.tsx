import { useState } from 'react';
import { FolderOpen, Cloud, Download, Copy, Trash2, History, Loader2, Eye, ShieldCheck, RefreshCw } from 'lucide-react';
import { useApp } from '../state';
import { HelpButton, Modal } from '../components/Help';
import { useCfg, useServidor, PrecisaServidor, erroTexto } from '../components/Servidor2';
import { listarProjetos, versoesProjeto, restaurarVersao, duplicarProjeto, apagarProjeto, baixarExportacao, horaTexto, type ProjetoMeta } from '../lib/api';
import { AREAS, lerEstado, gravarEstado, copiaLocal, retrato } from '../lib/sincronia';

const TIPO:Record<string,string>={video:'Vídeo animado',manual:'Montagem',vozes:'Vozes',agente3:'Agente 3',outro:'Preferências'};

function Versoes({p,fechar}:{p:ProjetoMeta;fechar:()=>void}){
  const cfg=useCfg(); const {toast}=useApp();
  const v=useServidor(c=>versoesProjeto(c,p.id));
  return <Modal title={'Versões de '+p.titulo} onClose={fechar}>
    <p className="hint">As 40 últimas versões ficam guardadas. Restaurar cria uma versão nova igual à escolhida (nada é apagado).</p>
    <ul className="versoes">{(v.dados?.versoes||[]).map(x=><li key={x.revisao}><b>Versão {x.revisao}</b> • {horaTexto(x.criado)} • {x.dispositivo||x.origem}{x.tamanho?` • ${Math.round(x.tamanho/1024)} KB`:''}
      {x.revisao!==p.revisao&&<button className="subtle sm" onClick={async()=>{ try{ await restaurarVersao(cfg,p.id,x.revisao); toast('Versão restaurada no servidor. Em Vídeo animado, Montagem ou Vozes, carregue a versão nova pelo aviso do topo.','ok'); fechar(); }catch(e){ toast(erroTexto(e),'erro'); } }}>Restaurar</button>}</li>)}</ul>
  </Modal>;
}

function Migracao(){
  const {toast,sinc}=useApp();
  const [est,setEst]=useState(lerEstado);
  const [busy,setBusy]=useState('');
  const [resumo,setResumo]=useState<{titulo:string;itens:number;vazio:boolean}[]|null>(null);
  const contar=async()=>{ setBusy('contar'); try{ const r=[]; for(const a of AREAS){ const x=await retrato(a,null); r.push({titulo:a.titulo,itens:Object.keys(x.ls).length+Object.values(x.idb).reduce((n,l)=>n+Object.values(l).reduce((m,i)=>m+i.length,0),0),vazio:x.vazio}); } setResumo(r); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } };
  const ligar=async()=>{
    setBusy('ligar');
    try{
      await copiaLocal();
      const e={...lerEstado(),ligado:true}; gravarEstado(e); setEst(e);
      toast('Cópia de segurança baixada. Enviando para o servidor...','ok');
      sinc.passar();
    }catch(x){ toast(erroTexto(x),'erro'); }finally{ setBusy(''); }
  };
  return <section className="panel">
    <div className="section-head"><h2><Cloud size={17}/> Salvar este navegador no servidor <HelpButton topic="sincronia"/></h2>{est.ligado?<span className="tag ok">ligado</span>:<span className="tag warn">desligado</span>}</div>
    {!est.ligado?<>
     <p className="subtitle">Seus trabalhos de Vídeo animado, Montagem, Vozes e as preferências estão só neste navegador. Ao ligar, o site primeiro baixa uma <b>cópia de segurança (.zip)</b> para você guardar, depois envia tudo ao servidor do celular. Nada é apagado deste navegador. Chaves e senhas não vão.</p>
     <div className="row-gap left"><button className="subtle" disabled={!!busy} onClick={contar}>{busy==='contar'?<Loader2 size={15} className="spin"/>:<Eye size={15}/>} Ver o que tem aqui</button>
      <button className="primary" disabled={!!busy} onClick={ligar}>{busy==='ligar'?<Loader2 size={15} className="spin"/>:<ShieldCheck size={15}/>} Fazer cópia e ligar o salvamento</button></div>
     {resumo&&<ul className="hint">{resumo.map(r=><li key={r.titulo}>{r.titulo}: {r.vazio?'vazio':`${r.itens} item(ns)`}</li>)}</ul>}
    </>:<>
     <p className="subtitle">Salvando sozinho a cada 25 segundos e quando você sai da aba. Situação agora: <b>{sinc.situacao}</b>{sinc.detalhe?` (${sinc.detalhe})`:''}.</p>
     <ul className="hint">{AREAS.map(a=>{ const x=est.areas[a.id]; return <li key={a.id}>{a.titulo}: {x?.id?`no servidor, versão ${x.rev}${x.quando?' • salvo '+horaTexto(x.quando):''}`:'ainda não enviado (vazio aqui)'}</li>; })}</ul>
     <div className="row-gap left"><button className="subtle" onClick={()=>{ sinc.passar(); setEst(lerEstado()); }}><RefreshCw size={15}/> Salvar agora</button>
      <button className="subtle" onClick={()=>copiaLocal().catch(e=>toast(erroTexto(e),'erro'))}><Download size={15}/> Baixar cópia deste navegador</button>
      <button className="link-btn" onClick={()=>{ if(window.confirm('Desligar o salvamento neste aparelho? O que já está no servidor continua lá.')){ const e={...lerEstado(),ligado:false}; gravarEstado(e); setEst(e); sinc.passar(); } }}>Desligar neste aparelho</button></div>
    </>}
  </section>;
}

export default function Projetos(){
  const {settings,toast,go}=useApp(); const cfg=useCfg();
  const lista=useServidor(c=>listarProjetos(c),20);
  const [vendo,setVendo]=useState<ProjetoMeta|null>(null);
  if(!settings.servidor) return <PrecisaServidor oque="Meus projetos"/>;
  const ps=lista.dados?.projetos||[];
  return <div className="projetos">
    <Migracao/>
    <section className="panel">
     <div className="section-head"><h2><FolderOpen size={17}/> No servidor ({ps.length})</h2>{lista.dados&&<span className="hint">{(lista.dados.livre_mb/1024).toFixed(1)} GB livres no celular</span>}</div>
     {lista.erro&&<p className="hint bad">{lista.erro}</p>}
     {ps.length===0&&<p className="hint">Nada ainda.</p>}
     <ul className="proj-lista">{ps.map(p=><li key={p.id}>
      <div className="grow"><b>{p.titulo}</b><small className="muted"> {TIPO[p.tipo]||p.tipo} • versão {p.revisao} • {horaTexto(p.atualizado)}{p.dispositivo?` • ${p.dispositivo}`:''}</small></div>
      {p.tipo==='agente3'&&<button className="subtle sm" onClick={()=>go('revisar',p.id,'fila')}><Eye size={14}/> Abrir</button>}
      <button className="subtle sm" onClick={()=>setVendo(p)}><History size={14}/> Versões</button>
      <button className="subtle sm" onClick={()=>baixarExportacao(cfg,p.id,p.titulo).catch(e=>toast(erroTexto(e),'erro'))}><Download size={14}/> .zip</button>
      {p.tipo==='agente3'&&<button className="subtle sm" onClick={async()=>{ try{ await duplicarProjeto(cfg,p.id); lista.recarregar(); toast('Cópia criada.','ok'); }catch(e){ toast(erroTexto(e),'erro'); } }}><Copy size={14}/> Duplicar</button>}
      <button className="icon-btn" aria-label="Apagar" onClick={async()=>{ if(!window.confirm(`Mandar "${p.titulo}" para a lixeira do servidor? (dá para recuperar pelo backup)`)) return; try{ await apagarProjeto(cfg,p.id); lista.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); } }}><Trash2 size={15}/></button>
     </li>)}</ul>
    </section>
    {vendo&&<Versoes p={vendo} fechar={()=>{ setVendo(null); lista.recarregar(); }}/>}
  </div>;
}
