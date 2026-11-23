import { useState } from 'react';
import { Pause, Play, X, RotateCcw, CalendarClock, Eye, Loader2, Mail, Cpu, HardDrive, BatteryMedium, Thermometer, CheckCircle2, AlertTriangle, Clock } from 'lucide-react';
import { useApp } from '../state';
import { HelpButton } from '../components/Help';
import { useCfg, useServidor, PrecisaServidor, erroTexto } from '../components/Servidor2';
import { lerFila, acaoFila, pendentes, lerCapacidade, estadoEmail, salvarEmail, lerRespostasAgora, duracaoTexto, horaTexto, type Job } from '../lib/api';

const FILTROS:[string,string][]=[['','Tudo'],['produzindo','Produzindo'],['agendados','Agendados'],['pausados','Pausados'],['erros','Erros'],['concluidos','Concluídos']];
const NOME_AGENTE:Record<string,string>={agente3:'Agente 3',agente1:'Agente 1',galeria:'Estilos'};
const SIT:Record<string,string>={rodando:'Rodando',na_fila:'Na fila',agendado:'Agendado',aguardando_tentativa:'Nova tentativa em breve',aguardando_aprovacao:'Esperando você',concluido:'Concluído',falhou:'Falhou',cancelado:'Cancelado'};

function CartaoJob({j,agora,acao}:{j:Job;agora:number;acao:(id:string,a:'pausar'|'retomar'|'cancelar'|'tentar'|'reagendar',corpo?:unknown)=>void}){
  const {go}=useApp();
  const [quando,setQuando]=useState('');
  const ativo=['rodando','na_fila','agendado','aguardando_tentativa','aguardando_aprovacao'].includes(j.status);
  const decorrido=j.decorrido_total??j.decorrido;
  return <article className={'job-card '+j.status+(j.pausado?' pausado':'')}>
    <div className="job-topo">
     <span className="tag">{NOME_AGENTE[j.agente]||j.agente}</span>
     <b className="grow">{j.titulo||j.tipo}</b>
     <span className={'tag '+(j.status==='falhou'?'bad':j.status==='concluido'?'ok':j.status==='aguardando_aprovacao'?'warn':'')}>{j.pausado&&ativo?'Pausado':SIT[j.status]||j.status}</span>
    </div>
    <p className="job-etapa">{j.etapa}{j.status==='rodando'&&<> • {Math.round(j.progresso||0)}%</>}</p>
    {j.status==='rodando'&&<div className="progress"><span style={{width:`${Math.min(100,j.progresso||0)}%`}}/></div>}
    <div className="job-tempos">
     {decorrido>0&&<span title="Tempo de trabalho até agora"><Clock size={13}/> decorrido {duracaoTexto(decorrido)}</span>}
     {ativo&&j.restante!=null&&j.status!=='aguardando_aprovacao'&&<span title={j.estimativa_medida?'Medido neste celular':'Ainda sem medida neste celular'}>falta ~{duracaoTexto(j.restante)}{!j.estimativa_medida&&' (estimativa inicial)'}</span>}
     {j.status==='agendado'&&<span><CalendarClock size={13}/> começa {horaTexto(j.run_at)}</span>}
     {['na_fila','aguardando_tentativa'].includes(j.status)&&j.inicio_previsto&&<span>início previsto {j.inicio_previsto<=agora+60?'já':horaTexto(j.inicio_previsto)}{j.posicao?` • posição ${j.posicao}`:''}</span>}
     {ativo&&j.fim_previsto&&j.status!=='aguardando_aprovacao'&&<span>pronto ~{horaTexto(j.fim_previsto)}</span>}
     {j.tentativas>0&&<span>tentativa {j.tentativas} de {j.max_tentativas}</span>}
    </div>
    {j.erro&&j.status!=='concluido'&&<p className="hint bad">{j.erro}</p>}
    <div className="row-gap left">
     {j.tipo==='agente1.pesado'&&<button className="subtle sm" onClick={()=>go('agente','corte-job-'+j.id,'agentes')}><Eye size={14}/> Acompanhar corte</button>}
     {j.projeto&&<button className="subtle sm" onClick={()=>go('revisar',j.projeto,'fila')}><Eye size={14}/> Ver projeto</button>}
     {ativo&&!j.pausado&&j.status!=='aguardando_aprovacao'&&<button className="subtle sm" onClick={()=>acao(j.id,'pausar')}><Pause size={14}/> Pausar</button>}
     {ativo&&!!j.pausado&&<button className="subtle sm" onClick={()=>acao(j.id,'retomar')}><Play size={14}/> Retomar</button>}
     {['falhou','cancelado','aguardando_tentativa'].includes(j.status)&&<button className="subtle sm" onClick={()=>acao(j.id,'tentar')}><RotateCcw size={14}/> Tentar de novo</button>}
     {['agendado','na_fila','aguardando_tentativa'].includes(j.status)&&<span className="reagendar"><input type="datetime-local" value={quando} onChange={e=>setQuando(e.target.value)} aria-label="Nova data"/>
      <button className="subtle sm" disabled={!quando} onClick={()=>acao(j.id,'reagendar',{quando:'data',data:new Date(quando).getTime()/1000})}><CalendarClock size={14}/> Reagendar</button></span>}
     {ativo&&<button className="subtle sm" onClick={()=>{ if(window.confirm('Cancelar este trabalho? O que já foi feito fica salvo no projeto.')) acao(j.id,'cancelar'); }}><X size={14}/> Cancelar</button>}
    </div>
  </article>;
}

function Capacidade(){
  const {dados:c}=useServidor(lerCapacidade,30);
  if(!c) return null;
  const nd='não disponível';
  return <section className="panel">
    <div className="section-head"><h2><Cpu size={17}/> Celular servidor</h2></div>
    <div className="cap-grade">
     <span><Cpu size={14}/> Processadores: <b>{c.cpus??nd}</b>{c.carga_cpu!=null&&<> • carga {c.carga_cpu.toFixed(1)}</>}</span>
     <span><HardDrive size={14}/> Livre: <b>{c.disco_livre_mb!=null?`${(c.disco_livre_mb/1024).toFixed(1)} GB`:nd}</b></span>
     <span>Memória livre: <b>{c.memoria?`${c.memoria.livre_mb} de ${c.memoria.total_mb} MB`:nd}</b></span>
     <span><BatteryMedium size={14}/> Bateria: <b>{c.bateria!=null?c.bateria+'%':nd}</b></span>
     <span><Thermometer size={14}/> Temperatura: <b>{c.temperatura!=null?c.temperatura+' °C':nd}</b></span>
     <span>Ao mesmo tempo: <b>{c.limites.pesado} pesado + {c.limites.leve} leves</b> • rodando agora: {c.rodando.length}</span>
    </div>
    <p className="hint">O Android esconde alguns números do Termux; o que ele não mostra aparece como "não disponível".</p>
  </section>;
}

function RespostasEmail(){
  const cfg=useCfg(); const {toast}=useApp();
  const {dados:e,recarregar,setDados}=useServidor(estadoEmail);
  const [busy,setBusy]=useState(false);
  const [extra,setExtra]=useState('');
  if(!e) return null;
  const salvar=async(d:Parameters<typeof salvarEmail>[1])=>{ setBusy(true); try{ setDados(await salvarEmail(cfg,d)); toast('Salvo no servidor.','ok'); }catch(x){ toast(erroTexto(x),'erro'); }finally{ setBusy(false); } };
  return <section className="panel">
    <div className="section-head"><h2><Mail size={17}/> Aprovar respondendo o e-mail <HelpButton topic="aprovacao"/></h2></div>
    <p className="subtitle">O servidor lê a caixa <b>{e.caixa||'(configure o e-mail em Publicações > Agente de postagem)'}</b> por IMAP, com a mesma senha de aplicativo do envio. Só aceita respostas de: {e.remetentes_autorizados.join(', ')||'ninguém ainda'}.</p>
    <label className="check"><input type="checkbox" checked={e.ativo} disabled={busy} onChange={x=>salvar({ativo:x.target.checked})}/> Ler respostas a cada {Math.round(e.intervalo/60)} min</label>
    <div className="small-grid mt">
     <label>Servidor IMAP (vazio = automático)<input defaultValue={e.imap} placeholder="imap.gmail.com" onBlur={x=>x.target.value!==e.imap&&salvar({imap:x.target.value})}/></label>
     <label>Outro remetente autorizado<input value={extra} onChange={x=>setExtra(x.target.value)} placeholder="outro@email.com"/></label>
    </div>
    <div className="row-gap left mt">
     <button className="subtle sm" disabled={busy||!extra.includes('@')} onClick={()=>{ salvar({remetentes:[...e.remetentes,extra.trim()]}); setExtra(''); }}>Autorizar remetente</button>
     {e.remetentes.map(r=><button key={r} className="subtle sm" onClick={()=>salvar({remetentes:e.remetentes.filter(x=>x!==r)})} title="Tirar">{r} <X size={12}/></button>)}
     <button className="primary sm" disabled={busy||!e.ativo} onClick={async()=>{ setBusy(true); try{ const r=await lerRespostasAgora(cfg); toast(r.erro||`Li ${r.lidos} e-mail(s), apliquei ${r.aplicados}.`,r.erro?'erro':'ok'); recarregar(); }catch(x){ toast(erroTexto(x),'erro'); }finally{ setBusy(false); } }}>{busy?<Loader2 size={14} className="spin"/>:<Mail size={14}/>} Ler agora</button>
    </div>
    <p className="hint">{e.ultimo?`Última leitura: ${horaTexto(e.ultimo)} • ${e.lidos} lidos, ${e.aplicados} aplicados.`:'Ainda não leu nenhuma vez.'} {e.erro&&<span className="bad">{e.erro}</span>}</p>
    <p className="hint">Gmail API (OAuth) não foi implementada; a leitura usa IMAP. No Gmail, ative o IMAP em Configurações &gt; Encaminhamento e POP/IMAP.</p>
  </section>;
}

export default function Fila(){
  const {settings,toast,go}=useApp(); const cfg=useCfg();
  const [filtro,setFiltro]=useState('');
  const fila=useServidor(c=>lerFila(c,filtro),5,[filtro]);
  const pend=useServidor(pendentes,10);
  if(!settings.servidor) return <PrecisaServidor oque="A fila"/>;
  const acao=async(id:string,a:'pausar'|'retomar'|'cancelar'|'tentar'|'reagendar',corpo:unknown={})=>{
    try{ await acaoFila(cfg,id,a,corpo); fila.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); }
  };
  const f=fila.dados;
  const lista=pend.dados?.pendentes||[];
  return <div className="fila-pagina">
    <section className="panel">
     <div className="section-head"><h2><CheckCircle2 size={17}/> Esperando a sua decisão {lista.length>0&&<span className="tag warn">{lista.length}</span>} <HelpButton topic="aprovacao"/></h2></div>
     {lista.length===0?<p className="hint">Nada esperando você agora. Quando um vídeo ficar pronto, ele aparece aqui e chega um e-mail.</p>
     :<div className="aprov-lista">{lista.map(p=><button key={p.projeto} className="aprov-item" onClick={()=>go('revisar',p.projeto,'fila')}>
       <span className={'tag '+(p.tipo==='video'?'ok':'warn')}>{p.tipo==='video'?'Vídeo pronto':p.status==='changes_requested'?'Correção pedida':'Roteiro para aprovar'}</span>
       <b>{p.titulo}</b><small>{p.ref}{p.render?.duracao?` • ${Math.round(p.render.duracao)} s`:''} • {horaTexto(p.atualizado)}</small>
       <span className="primary sm">{p.tipo==='video'?'Assistir e decidir':'Conferir roteiro'}</span>
      </button>)}</div>}
    </section>
    <section className="panel">
     <div className="section-head"><h2>O que o celular está fazendo <HelpButton topic="fila"/></h2>{fila.carregando&&<Loader2 size={15} className="spin"/>}</div>
     <div className="chips">{FILTROS.map(([id,nome])=><button key={id} className={'chip '+(filtro===id?'on':'')} onClick={()=>setFiltro(id)}>{nome}{f&&id&&f.contagem[id]?` (${f.contagem[id]})`:''}</button>)}</div>
     {fila.erro&&<p className="hint bad"><AlertTriangle size={14}/> {fila.erro}</p>}
     {f&&f.jobs.length===0&&<div className="row-gap left"><p className="hint">Nada aqui agora.</p><button className="primary sm" onClick={()=>go('ia','','criar')}>Criar um vídeo</button></div>}
     <div className="job-lista">{f?.jobs.slice(0,80).map(j=><CartaoJob key={j.id} j={j} agora={f.agora} acao={acao}/>)}</div>
    </section>
    <details className="recolhido"><summary>Aprovar respondendo o e-mail (configuração)</summary><RespostasEmail/></details>
    <details className="recolhido"><summary>Saúde do celular servidor</summary><Capacidade/></details>
  </div>;
}
