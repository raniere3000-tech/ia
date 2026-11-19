import { useEffect, useRef, useState } from 'react';
import { Bot, Brain, CheckCircle2, History, Lightbulb, ListChecks, Loader2, MessageSquare, Pause, Play, Send, Settings2, ShieldCheck, Undo2, Users, XCircle } from 'lucide-react';
import { useApp } from '../state';
import { useCfg, useServidor, erroTexto } from '../components/Servidor2';
import Progresso from '../components/Progresso';
import { urlServidor } from '../lib/api';
import { tempoTexto } from '../lib/alertas';
import { ESCOPOS, ESTADO_ORDEM, ESTADO_TAREFA, REDES, acaoMemoria, acaoOrdem, acaoSugestao, confirmarOrdem, conferirHistorico, criarMemoria, decidir, escolherCapaPacote,
  interpretar, lerAgentes, lerAprovacoes, lerCfgCoord, lerConversa, lerEventos, lerMemoria, lerMemorias, lerOrdem, lerOrdens, lerSugestoes, mudarParametros, salvarCfgCoord,
  type Aprovacao, type CfgCoord, type Evento, type Memoria, type Ordem, type Resposta } from '../lib/coordenador';

type Aba='conversar'|'ordens'|'aprovacoes'|'agentes'|'memoria'|'aprendizado'|'historico'|'config';
const ABAS:[Aba,string,typeof Bot][]=[['conversar','Conversar',MessageSquare],['ordens','Ordens',ListChecks],['aprovacoes','Liberar',ShieldCheck],['agentes','Agentes',Users],
  ['memoria','Memória',Brain],['aprendizado','Aprendizado',Lightbulb],['historico','Histórico',History],['config','Configurações',Settings2]];
const quando=(t?:number|null)=>t?new Date(t*1000).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'';
const EXEMPLOS=['Faça 3 vídeos sobre a história do café, voz masculina, estilo documentário, 2 capas por vídeo, postar no YouTube amanhã às 18h',
  'Como está?','Quanto falta?','O que espera por mim?','Corta vídeos sobre Minecraft','Lembre que eu prefiro voz masculina'];
const SEM_ROTA=<>O servidor do celular ainda não tem o Coordenador. No Termux rode: <code>cd ~/ia &amp;&amp; git pull</code> e depois <code>cd servidor &amp;&amp; bash iniciar-termux.sh link</code>.</>;
const Erro=({e}:{e:string})=>e?<p className="hint bad">{/rota não encontrada/i.test(e)?SEM_ROTA:e}</p>:null;
function Tag({mapa,estado}:{mapa:Record<string,[string,string]>;estado:string}){ const [t,c]=mapa[estado]||[estado,'']; return <span className={'tag '+c}>{t}</span>; }

export default function Coordenador(){
  const {rotaExtra,go}=useApp(); const cfg=useCfg();
  const [aba,setAba]=useState<Aba>((ABAS.find(a=>a[0]===rotaExtra.split(':')[0])?.[0])||'conversar');
  const [ordemSel,setOrdemSel]=useState(rotaExtra.startsWith('ordens:')?rotaExtra.slice(7):'');
  useEffect(()=>{ const a=ABAS.find(x=>x[0]===rotaExtra.split(':')[0])?.[0]; if(a) setAba(a); if(rotaExtra.startsWith('ordens:')) setOrdemSel(rotaExtra.slice(7)); },[rotaExtra]);
  if(!cfg.servidor) return <section className="panel"><p className="hint">Conecte o servidor do celular em Ajustes para falar com o Coordenador.</p></section>;
  const trocar=(a:Aba,extra='')=>{ setAba(a); go('coordenador',extra?`${a}:${extra}`:a,'automacao'); };
  const abrirOrdem=(id:string)=>{ setOrdemSel(id); trocar('ordens',id); };
  return <div className="coord">
    <div className="ag-abas" role="tablist">{ABAS.map(([k,t,I])=><button key={k} role="tab" aria-selected={aba===k} className={aba===k?'active':''} onClick={()=>trocar(k)}><I size={14}/> {t}</button>)}</div>
    {aba==='conversar'&&<Conversar abrirOrdem={abrirOrdem}/>}
    {aba==='ordens'&&(ordemSel?<OrdemTela id={ordemSel} voltar={()=>{ setOrdemSel(''); trocar('ordens'); }} irLiberar={()=>trocar('aprovacoes')}/>:<Ordens abrir={abrirOrdem}/>)}
    {aba==='aprovacoes'&&<Liberar abrirOrdem={abrirOrdem}/>}
    {aba==='agentes'&&<Agentes/>}
    {aba==='memoria'&&<MemoriaTela/>}
    {aba==='aprendizado'&&<Aprendizado/>}
    {aba==='historico'&&<Historico/>}
    {aba==='config'&&<Config/>}
  </div>;
}

// ---------------------------------------------------------------- conversa
// O rascunho é o mesmo na tela do Coordenador e no atalho rápido (fica nesta aba do navegador).
const RASCUNHO='coord_rascunho';
const lerRascunho=()=>{ try{ return sessionStorage.getItem(RASCUNHO)||''; }catch{ return ''; } };
const gravarRascunho=(t:string)=>{ try{ if(t) sessionStorage.setItem(RASCUNHO,t); else sessionStorage.removeItem(RASCUNHO); }catch{ /* sem armazenamento */ } };

/** O chat do Coordenador. Também é usado pelo atalho rápido (mesmas mensagens do servidor, mesmo rascunho). */
export function Conversar({abrirOrdem,compacto=false}:{abrirOrdem:(id:string)=>void;compacto?:boolean}){
  const {toast}=useApp(); const cfg=useCfg();
  const conv=useServidor(c=>lerConversa(c),0);
  const [texto,setTextoE]=useState(lerRascunho); const [busy,setBusy]=useState(false);
  const setTexto=(t:string)=>{ setTextoE(t); gravarRascunho(t); };
  const [ultima,setUltima]=useState<Resposta|null>(null);
  const fim=useRef<HTMLDivElement>(null);
  useEffect(()=>{ fim.current?.scrollIntoView({block:'end'}); },[conv.dados,ultima]);
  async function enviar(t=texto){
    const s=t.trim(); if(!s||busy) return;
    setBusy(true);
    try{ const r=await interpretar(cfg,s,`chat:${Date.now()}`); setUltima(r); setTexto(''); await conv.recarregar(); }
    catch(e){ toast(erroTexto(e),'erro'); } finally{ setBusy(false); }
  }
  const msgs=conv.dados?.mensagens||[];
  return <section className={'panel coord-chat'+(compacto?' compacto':'')}>
    <p className="hint">Peça do seu jeito. Eu monto um plano com os agentes 1 a 6 e <b>nada começa sem você confirmar</b>. Nada é postado sem você liberar o pacote final (vídeo + capa).</p>
    <Erro e={conv.erro}/>
    <div className="coord-msgs" aria-live="polite">
      {!msgs.length&&<p className="muted">{compacto?'Ainda não conversamos. Escreva o que você quer, por exemplo: "Como está?" ou "Faça 3 vídeos sobre café".':'Ainda não conversamos. Experimente um dos exemplos abaixo.'}</p>}
      {msgs.map(m=>{ const ev=m.evento as {de?:string;texto?:string;ordem?:string;memoria?:string}; const meu=ev.de==='voce';
        return <div key={m.id} className={'coord-msg '+(meu?'meu':'dele')}><p>{ev.texto}</p>
          <small className="muted">{quando(m.criado)}{ev.ordem&&!meu&&<> · <button className="link-btn" onClick={()=>abrirOrdem(ev.ordem!)}>abrir a ordem</button></>}</small></div>; })}
      {ultima?.tipo==='ordem'&&ultima.ordem&&['rascunho','aguardando_confirmacao'].includes(ultima.ordem.status)&&
        <Proposta ordem={ultima.ordem} mudou={o=>setUltima({...ultima,ordem:o})} abrir={()=>abrirOrdem(ultima.ordem!.id)}/>}
      {ultima?.tipo==='memoria'&&ultima.memoria&&ultima.memoria.status==='proposta'&&<MemoriaProposta m={ultima.memoria} feita={m=>setUltima({...ultima,memoria:m})}/>}
      <div ref={fim}/>
    </div>
    {!compacto&&<div className="coord-exemplos">{EXEMPLOS.map(e=><button key={e} className="subtle sm" onClick={()=>enviar(e)} disabled={busy}>{e.length>48?e.slice(0,46)+'…':e}</button>)}</div>}
    <form className="coord-enviar" onSubmit={e=>{ e.preventDefault(); enviar(); }}>
      <textarea rows={2} value={texto} aria-label="Mensagem para o Coordenador" data-coord-texto onChange={e=>setTexto(e.target.value)} maxLength={2000} placeholder="Ex.: faça 5 vídeos sobre o espaço, 1 por dia no TikTok às 19h"
        onKeyDown={e=>{ if(e.key==='Enter'&&!e.shiftKey){ e.preventDefault(); enviar(); } }}/>
      <button className="primary" disabled={busy||!texto.trim()} aria-label="Enviar">{busy?<Loader2 size={16} className="spin"/>:<Send size={16}/>}</button>
    </form>
  </section>;
}

function Proposta({ordem,mudou,abrir}:{ordem:Ordem;mudou:(o:Ordem)=>void;abrir:()=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const p=ordem.plano; const par=p.parametros as Record<string,unknown>;
  const [extra,setExtra]=useState<Record<string,unknown>>({}); const [busy,setBusy]=useState(false);
  const falta=new Set(p.faltando.map(f=>f.campo));
  const redes=(extra.redes as string[]|undefined)??(par.redes as string[]|undefined)??[];
  async function salvar(){ setBusy(true); try{ mudou(await mudarParametros(cfg,ordem.id,extra,ordem.versao_plano)); setExtra({}); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }
  async function confirmar(){ setBusy(true); try{ const o=await confirmarOrdem(cfg,ordem.id,ordem.versao_plano); toast('Confirmado. Os agentes começaram.','ok'); mudou(o); abrir(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }
  async function cancelar(){ setBusy(true); try{ mudou(await acaoOrdem(cfg,ordem.id,'cancelar')); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }
  return <div className="coord-proposta">
    <b>{ordem.ref} · plano</b>
    <ol>{p.plano.map((x,i)=><li key={i}><b>{x.agente}:</b> {x.o_que}</li>)}</ol>
    {!!p.memorias_usadas.length&&<p className="hint">Usei a memória: {p.memorias_usadas.map(m=>`"${m.texto}"`).join(', ')}</p>}
    {!!p.faltando.length&&<div className="coord-falta">
      {falta.has('tema')&&<label className="field"><span>Sobre o que são os vídeos?</span><input value={String(extra.tema??'')} onChange={e=>setExtra({...extra,tema:e.target.value})}/></label>}
      {falta.has('redes')&&<div className="field"><span className="field-label">Em quais redes?</span><div className="row-gap left">{REDES.map(r=>
        <label key={r} className="check"><input type="checkbox" checked={redes.includes(r)} onChange={e=>setExtra({...extra,redes:e.target.checked?[...redes,r]:redes.filter(x=>x!==r)})}/> {r}</label>)}</div></div>}
      {falta.has('inicio')&&<label className="field"><span>Começa em que dia?</span><input type="date" value={String(extra.inicio??'')} onChange={e=>setExtra({...extra,inicio:e.target.value})}/></label>}
      {falta.has('hora_local')&&<label className="field"><span>Que horas?</span><input type="time" value={String(extra.hora_local??'')} onChange={e=>setExtra({...extra,hora_local:e.target.value})}/></label>}
      {falta.has('link')&&<label className="field"><span>Link do vídeo</span><input value={String(extra.link??'')} onChange={e=>setExtra({...extra,link:e.target.value,modo:'link'})}/></label>}
      {falta.has('ref')&&<label className="field"><span>Código do vídeo (VID-XXXXXX)</span><input value={String(extra.ref??'')} onChange={e=>setExtra({...extra,ref:e.target.value.toUpperCase()})}/></label>}
      <button className="subtle sm" disabled={busy||!Object.keys(extra).length} onClick={salvar}>Atualizar o plano</button>
    </div>}
    {!!p.bloqueios.length&&<ul className="coord-bloqueios">{p.bloqueios.map(b=><li key={b} className="bad">{b}</li>)}</ul>}
    {!!p.horarios.length&&!p.faltando.length&&<p className="hint">Horários: {p.horarios.slice(0,8).join(' · ')}{p.horarios.length>8?' …':''}</p>}
    <div className="row-gap left">
      <button className="primary sm" disabled={busy||ordem.status!=='aguardando_confirmacao'} onClick={confirmar}>{busy?<Loader2 size={14} className="spin"/>:<CheckCircle2 size={14}/>} Confirmar e começar</button>
      <button className="subtle sm" disabled={busy} onClick={cancelar}><XCircle size={14}/> Cancelar</button>
    </div>
  </div>;
}

function MemoriaProposta({m,feita}:{m:Memoria;feita:(m:Memoria)=>void}){
  const {toast}=useApp(); const cfg=useCfg(); const [busy,setBusy]=useState(false);
  async function fazer(a:'confirmar'|'desativar'){ setBusy(true); try{ feita(await acaoMemoria(cfg,m.id,a,m.versao)); toast(a==='confirmar'?'Memória confirmada.':'Descartada.','ok'); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }
  return <div className="coord-proposta"><b>Guardar como memória?</b><p>"{m.texto}" <small className="muted">({m.escopo})</small></p>
    <div className="row-gap left"><button className="primary sm" disabled={busy} onClick={()=>fazer('confirmar')}>Confirmar</button><button className="subtle sm" disabled={busy} onClick={()=>fazer('desativar')}>Não guardar</button></div></div>;
}

// ---------------------------------------------------------------- ordens
function Ordens({abrir}:{abrir:(id:string)=>void}){
  const [filtro,setFiltro]=useState('ativas');
  const r=useServidor(c=>lerOrdens(c,filtro),6,[filtro]);
  return <section className="panel">
    <h3><ListChecks size={16}/> Ordens</h3>
    <Erro e={r.erro}/>
    <div className="seg" role="radiogroup">{([['ativas','Em andamento'],['','Todas'],['concluida','Concluídas'],['falhou','Com falha']] as const).map(([k,t])=>
      <button key={k} role="radio" aria-checked={filtro===k} className={filtro===k?'on':''} onClick={()=>setFiltro(k)}>{t}</button>)}</div>
    {!r.dados?<p className="muted"><Loader2 size={14} className="spin"/> Carregando…</p>:!r.dados.ordens.length?<p className="muted">Nenhuma ordem aqui.</p>:
    <ul className="coord-lista">{r.dados.ordens.map(o=><li key={o.id}><button className="coord-item" onClick={()=>abrir(o.id)}>
      <span><b>{o.ref}</b> <Tag mapa={ESTADO_ORDEM} estado={o.status}/></span>
      <small>{o.texto||o.resposta}</small>
      <small className="muted">{o.tarefas.concluidas}/{o.tarefas.total} etapas{o.tarefas.falhas?` · ${o.tarefas.falhas} com problema`:''}{o.tarefas.esperando_voce?` · ${o.tarefas.esperando_voce} esperando você`:''} · {o.eta.texto} · {quando(o.criado)}</small>
    </button></li>)}</ul>}
  </section>;
}

function OrdemTela({id,voltar,irLiberar}:{id:string;voltar:()=>void;irLiberar:()=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const r=useServidor(c=>lerOrdem(c,id),5,[id]); const [busy,setBusy]=useState(false);
  const o=r.dados;
  async function fazer(a:'pausar'|'retomar'|'cancelar'){ if(a==='cancelar'&&!confirm('Cancelar esta ordem? O que já está pronto continua salvo.')) return;
    setBusy(true); try{ await acaoOrdem(cfg,id,a); await r.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }
  if(!o) return <section className="panel"><button className="link-btn" onClick={voltar}>← Ordens</button>{r.erro?<Erro e={r.erro}/>:<p className="muted"><Loader2 size={14} className="spin"/> Carregando…</p>}</section>;
  return <section className="panel">
    <button className="link-btn" onClick={voltar}>← Ordens</button>
    <h3>{o.ref} <Tag mapa={ESTADO_ORDEM} estado={o.status}/></h3>
    {o.texto&&<p className="muted">"{o.texto}"</p>}
    {['rascunho','aguardando_confirmacao'].includes(o.status)&&<Proposta ordem={o} mudou={()=>r.recarregar()} abrir={()=>r.recarregar()}/>}
    {!['rascunho','aguardando_confirmacao','cancelada'].includes(o.status)&&<p className="hint">Falta: {o.eta.texto}{o.eta.base?` (${o.eta.base})`:''}</p>}
    {o.status==='aguardando_voce'&&o.aprovacoes.some(a=>a.decisao==='pendente'&&!a.revogado)&&<button className="primary sm" onClick={irLiberar}><ShieldCheck size={14}/> Liberar pacotes</button>}
    <ul className="coord-tarefas">{o.tarefas.map(t=><li key={t.id} className={'coord-tarefa '+t.estado}>
      <span><b>{t.titulo}</b> <Tag mapa={ESTADO_TAREFA} estado={t.estado}/></span>
      <small className="muted">{t.agente_nome}{t.correcoes?` · ${t.correcoes} correção(ões)`:''}{typeof t.resultado.ref==='string'?` · ${t.resultado.ref}`:''}</small>
      {t.job&&<Progresso pct={t.job.progresso} restante={t.job.restante_s} estimado={t.job.restante_s!=null} status={t.job.status}/>}
      {t.erro&&<small className={t.estado==='falhou'||t.estado==='bloqueada'?'bad':'muted'}>{t.erro}</small>}
      {typeof t.resultado.nota==='string'&&t.resultado.nota&&<small className="warn">{t.resultado.nota}</small>}
    </li>)}</ul>
    <div className="row-gap left">
      {['em_execucao','aguardando_voce'].includes(o.status)&&<button className="subtle sm" disabled={busy} onClick={()=>fazer('pausar')}><Pause size={14}/> Pausar</button>}
      {o.status==='pausada'&&<button className="subtle sm" disabled={busy} onClick={()=>fazer('retomar')}><Play size={14}/> Retomar</button>}
      {!['concluida','cancelada','falhou','parcial','rascunho','aguardando_confirmacao'].includes(o.status)&&<button className="subtle sm" disabled={busy} onClick={()=>fazer('cancelar')}><XCircle size={14}/> Cancelar</button>}
    </div>
    <details><summary>Histórico desta ordem ({o.eventos.length})</summary><ListaEventos eventos={o.eventos}/></details>
  </section>;
}

// ---------------------------------------------------------------- liberação final
function Liberar({abrirOrdem}:{abrirOrdem:(id:string)=>void}){
  const r=useServidor(c=>lerAprovacoes(c,'pendente'),8);
  return <section className="panel">
    <h3><ShieldCheck size={16}/> Liberar pacotes</h3>
    <p className="hint">Cada pacote é o vídeo final + a capa escolhida, presos pelo hash dos dois. Se o vídeo ou a capa mudarem, a liberação cai e volta para cá.</p>
    <Erro e={r.erro}/>
    {!r.dados?<p className="muted"><Loader2 size={14} className="spin"/> Carregando…</p>:!r.dados.aprovacoes.length?<p className="muted">Nada esperando você.</p>:
      r.dados.aprovacoes.map(a=><Pacote key={a.id+a.pacote_hash} a={a} mudou={()=>r.recarregar()} abrirOrdem={abrirOrdem}/>)}
  </section>;
}

function Pacote({a,mudou,abrirOrdem}:{a:Aprovacao;mudou:()=>void;abrirOrdem:(id:string)=>void}){
  const {toast,go}=useApp(); const cfg=useCfg();
  const [busy,setBusy]=useState(false); const [semCapa,setSemCapa]=useState(false);
  const [alvo,setAlvo]=useState<'video'|'capa'>('video'); const [com,setCom]=useState(''); const [reprovar,setReprovar]=useState(false);
  const rel=a.relatorio;
  async function fazer(f:()=>Promise<unknown>,msg:string){ setBusy(true); try{ await f(); toast(msg,'ok'); mudou(); }catch(e){ toast(erroTexto(e),'erro'); mudou(); }finally{ setBusy(false); } }
  const pode=rel.itens.every(i=>i.ok||(i.item==='capa'&&semCapa));
  return <div className="coord-pacote">
    <b>{rel.titulo}</b> <small className="muted">{rel.ref} · <button className="link-btn" onClick={()=>abrirOrdem(a.ordem_id)}>{a.ordem_ref}</button> · <button className="link-btn" onClick={()=>go('revisar',rel.projeto)}>assistir</button></small>
    <ul className="coord-conf">{rel.itens.map(i=><li key={i.item} className={i.ok?'ok':'bad'}>{i.ok?'✓':'✗'} {i.detalhe}</li>)}</ul>
    {!!rel.destino?.redes?.length&&<p className="hint">Vai para {rel.destino.redes.join(', ')}{rel.destino.quando?` em ${quando(rel.destino.quando)}`:''}.</p>}
    {rel.capa_por_rede&&Object.entries(rel.capa_por_rede).filter(([,c])=>c.tipo!=='custom_image_upload').map(([r,c])=><p key={r} className="hint warn">{r}: {c.nota}</p>)}
    {!!a.capas?.length&&<div className="coord-capas">{a.capas.map(v=><button key={v.id} className={'coord-capa'+(a.thumbnail_sha256===v.sha256?' on':'')} disabled={busy}
      onClick={()=>fazer(()=>escolherCapaPacote(cfg,a.id,v,v.estado!=='aprovada'||undefined),'Capa escolhida.')}>
      <img src={urlServidor(cfg,v.url)} alt={`Capa ${v.numero}`} className={v.formato==='9:16'?'vert':''} loading="lazy"/>
      <small>Nota {v.nota}{v.estado!=='aprovada'?' (abaixo do mínimo)':''}</small></button>)}</div>}
    {rel.capas_pedidas>0&&!a.thumbnail_sha256&&<label className="check"><input type="checkbox" checked={semCapa} onChange={e=>setSemCapa(e.target.checked)}/> Liberar sem capa</label>}
    <div className="row-gap left">
      <button className="primary sm" disabled={busy||!pode} onClick={()=>fazer(()=>decidir(cfg,a.id,{decisao:'aprovar',pacote_hash:a.pacote_hash,sem_capa:semCapa}),'Pacote liberado.')}><CheckCircle2 size={14}/> Liberar</button>
      <button className="subtle sm" disabled={busy} onClick={()=>setReprovar(!reprovar)}><Undo2 size={14}/> Pedir correção</button>
    </div>
    {reprovar&&<div className="coord-falta">
      <div className="seg" role="radiogroup">{([['video','Refazer o vídeo'],['capa','Refazer só a capa']] as const).map(([k,t])=>
        <button key={k} role="radio" aria-checked={alvo===k} className={alvo===k?'on':''} onClick={()=>setAlvo(k)} disabled={k==='capa'&&!rel.capas_pedidas}>{t}</button>)}</div>
      <textarea rows={2} value={com} onChange={e=>setCom(e.target.value)} placeholder="O que precisa mudar?"/>
      <button className="primary sm" disabled={busy||com.trim().length<3} onClick={()=>fazer(()=>decidir(cfg,a.id,{decisao:'reprovar',alvo,comentario:com,pacote_hash:a.pacote_hash}),'Correção pedida.')}>Mandar corrigir</button>
    </div>}
  </div>;
}

// ---------------------------------------------------------------- agentes
function Agentes(){
  const r=useServidor(c=>lerAgentes(c),6);
  return <section className="panel">
    <h3><Users size={16}/> Os agentes agora</h3>
    <p className="hint">Tempo e custo só aparecem quando foram medidos neste servidor. Sem medida, aparece "sem medida ainda".</p>
    <Erro e={r.erro}/>
    {r.dados&&<p className="muted">Central: {r.dados.central==='pausada'?'pausada':r.dados.central||'—'}</p>}
    <div className="coord-agentes">{(r.dados?.agentes||[]).map(a=><div key={a.id} className="coord-agente">
      <b>{a.nome}</b> <span className={'tag '+(a.estado==='trabalhando'||a.estado==='coordenando'?'ok':'')}>{a.estado.replace('_',' ')}</span>
      {a.atual.map(j=><div key={j.job}><small>{j.titulo}</small><Progresso pct={j.progresso} restante={j.restante_s} estimado={j.restante_s!=null} status="rodando"/></div>)}
      <small className="muted">{a.id==='agente7'?`${a.ordens_ativas} ordem(ns) · ${a.esperando_voce} esperando você · modo ${a.modo}`:
        `Na fila: ${a.na_fila} · feitos em 24 h: ${a.feitos_24h} · falhas em 24 h: ${a.falhas_24h}`}</small>
      {a.tempos_medios&&(Object.keys(a.tempos_medios).length?<small className="muted">Tempo médio: {Object.entries(a.tempos_medios).map(([k,v])=>`${k} ${tempoTexto(v.segundos)} (${v.amostras})`).join(' · ')}</small>
        :<small className="muted">Tempo médio: sem medida ainda</small>)}
      {a.custo_30d&&<small className="muted">Custo registrado em 30 dias: {a.custo_30d.registros?`${a.custo_30d.valor} ${a.custo_30d.moeda}`:'nenhum registro'}</small>}
      {a.custo_capas_30d_usd!=null&&<small className="muted">Capas com IA em 30 dias: US$ {a.custo_capas_30d_usd}</small>}
      {a.posts_agendados!=null&&<small className="muted">Posts agendados: {a.posts_agendados}</small>}
    </div>)}</div>
  </section>;
}

// ---------------------------------------------------------------- memória
function MemoriaTela(){
  const {toast}=useApp(); const cfg=useCfg();
  const [filtro,setFiltro]=useState(''); const r=useServidor(c=>lerMemorias(c,filtro),0,[filtro]);
  const [novo,setNovo]=useState({texto:'',escopo:'global',tipo:'preferencia'}); const [busy,setBusy]=useState(false); const [aberta,setAberta]=useState('');
  async function fazer(f:()=>Promise<unknown>,msg:string){ setBusy(true); try{ await f(); toast(msg,'ok'); await r.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }
  return <section className="panel">
    <h3><Brain size={16}/> Memória</h3>
    <p className="hint">Preferências que o Coordenador usa nas próximas ordens. Só valem depois de confirmadas. O que você diz no pedido sempre vence a memória. Memória nunca dá permissão para postar ou gastar.</p>
    <Erro e={r.erro}/>
    <div className="coord-falta">
      <textarea rows={2} value={novo.texto} onChange={e=>setNovo({...novo,texto:e.target.value})} placeholder="Ex.: prefiro vídeos com até 45 segundos"/>
      <div className="row-gap left"><select value={novo.escopo} onChange={e=>setNovo({...novo,escopo:e.target.value})}>{ESCOPOS.map(([k,t])=><option key={k} value={k}>{t}</option>)}</select>
        <button className="primary sm" disabled={busy||novo.texto.trim().length<3} onClick={()=>fazer(()=>criarMemoria(cfg,{...novo,confirmar:true}).then(()=>setNovo({...novo,texto:''})),'Guardado.')}>Guardar</button></div>
    </div>
    <div className="seg" role="radiogroup">{([['','Todas'],['confirmada','Valendo'],['proposta','Para confirmar'],['desativada','Desativadas']] as const).map(([k,t])=>
      <button key={k} role="radio" aria-checked={filtro===k} className={filtro===k?'on':''} onClick={()=>setFiltro(k)}>{t}</button>)}</div>
    <ul className="coord-lista">{(r.dados?.memorias||[]).map(m=><li key={m.id} className="coord-item">
      <span>"{m.texto}" <span className={'tag '+(m.status==='confirmada'?'ok':m.status==='proposta'?'warn':'')}>{m.status}</span></span>
      <small className="muted">{m.escopo} · versão {m.versao} · {m.origem==='sugestao'?'sugerida pelo aprendizado':'sua'}{Object.keys(m.dados).length?` · ${JSON.stringify(m.dados)}`:''}</small>
      <div className="row-gap left">
        {m.status!=='confirmada'&&<button className="subtle sm" disabled={busy} onClick={()=>fazer(()=>acaoMemoria(cfg,m.id,'confirmar',m.versao),'Confirmada.')}>Confirmar</button>}
        {m.status!=='desativada'&&<button className="subtle sm" disabled={busy} onClick={()=>fazer(()=>acaoMemoria(cfg,m.id,'desativar',m.versao),'Desativada.')}>Desativar</button>}
        <button className="link-btn" onClick={()=>setAberta(aberta===m.id?'':m.id)}>versões</button>
      </div>
      {aberta===m.id&&<Versoes id={m.id} reverter={v=>fazer(()=>acaoMemoria(cfg,m.id,'reverter',v),`Voltou para a versão ${v}.`)}/>}
    </li>)}</ul>
  </section>;
}

function Versoes({id,reverter}:{id:string;reverter:(v:number)=>void}){
  const r=useServidor(c=>lerMemoria(c,id),0,[id]);
  return <ul className="coord-versoes">{(r.dados?.versoes||[]).map(v=><li key={v.versao}><small>v{v.versao} · {v.motivo} · {v.autor} · {quando(v.criado)} · "{String(v.depois.texto||'')}" ({String(v.depois.status||'')})</small>
    {v.versao!==r.dados?.versao&&<button className="link-btn" onClick={()=>reverter(v.versao)}>voltar para esta</button>}</li>)}</ul>;
}

// ---------------------------------------------------------------- aprendizado
function Aprendizado(){
  const {toast}=useApp(); const cfg=useCfg(); const r=useServidor(c=>lerSugestoes(c),0); const [busy,setBusy]=useState(false);
  async function fazer(id:string,a:'propor'|'dispensar'){ setBusy(true); try{ await acaoSugestao(cfg,id,a); toast(a==='propor'?'Virou proposta em Memória. Confirme lá se concordar.':'Dispensada.','ok'); await r.recarregar(); }
    catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }
  return <section className="panel">
    <h3><Lightbulb size={16}/> Aprendizado</h3>
    <p className="hint">{r.dados?.nota||'Padrões encontrados no que aconteceu de verdade neste servidor.'} Nada muda sozinho.</p>
    <Erro e={r.erro}/>
    {r.dados&&!r.dados.sugestoes.length&&<p className="muted">Ainda não há evidência suficiente para sugerir algo.</p>}
    <ul className="coord-lista">{(r.dados?.sugestoes||[]).map(s=><li key={s.id} className="coord-item">
      <b>{s.titulo}</b>
      <small className="muted">Evidência: {JSON.stringify(s.evidencia)}{s.confianca!=null?` · confiança ${Math.round(s.confianca*100)}%`:''}</small>
      <small>Proposta: "{s.proposta.texto}"</small>
      <div className="row-gap left"><button className="subtle sm" disabled={busy} onClick={()=>fazer(s.id,'propor')}>Propor como memória</button>
        <button className="link-btn" disabled={busy} onClick={()=>fazer(s.id,'dispensar')}>dispensar</button></div>
    </li>)}</ul>
  </section>;
}

// ---------------------------------------------------------------- histórico e configurações
const CAT:Record<string,string>={conversa:'Conversa',ordem:'Ordem',delegado:'Mandou para',concluida:'Concluiu',falhou:'Falhou',liberacao:'Liberação',liberacao_revogada:'Liberação caiu',
  correcao:'Correção',agendado:'Agendado',memoria:'Memória',aprendizado:'Aprendizado',feedback:'Avaliação',config:'Configuração',aviso:'Aviso',capa_escolhida:'Capa escolhida'};
function ListaEventos({eventos}:{eventos:Evento[]}){
  return <ul className="coord-eventos">{eventos.map(e=><li key={e.id}><small className="muted">{quando(e.criado)} · {e.fonte}</small> <b>{CAT[e.categoria]||e.categoria}</b>{' '}
    <small>{String((e.evento as Record<string,unknown>).texto||(e.evento as Record<string,unknown>).acao||(e.evento as Record<string,unknown>).erro||(e.evento as Record<string,unknown>).agente||'')}</small></li>)}</ul>;
}
function Historico(){
  const {toast}=useApp(); const cfg=useCfg(); const r=useServidor(c=>lerEventos(c),10);
  async function conferir(){ try{ const x=await conferirHistorico(cfg); toast(x.ok?`Histórico íntegro (${x.conferidos} registros).`:`Registro ${x.quebrado_em} foi mexido por fora.`,x.ok?'ok':'erro'); }catch(e){ toast(erroTexto(e),'erro'); } }
  return <section className="panel">
    <h3><History size={16}/> Histórico</h3>
    <p className="hint">Tudo o que o Coordenador fez e decidiu, em ordem. Cada registro carrega o código do anterior: dá para ver se alguém mexeu.</p>
    <button className="subtle sm" onClick={conferir}>Conferir o histórico</button>
    <Erro e={r.erro}/>
    <ListaEventos eventos={r.dados?.eventos||[]}/>
  </section>;
}
function Config(){
  const {toast}=useApp(); const cfg=useCfg(); const r=useServidor(c=>lerCfgCoord(c),0); const [c,setC]=useState<CfgCoord|null>(null);
  useEffect(()=>{ if(r.dados) setC(r.dados); },[r.dados]);
  async function salvar(){ if(!c) return; try{ setC(await salvarCfgCoord(cfg,c)); toast('Salvo.','ok'); }catch(e){ toast(erroTexto(e),'erro'); } }
  if(!c) return <section className="panel"><Erro e={r.erro}/>{!r.erro&&<p className="muted"><Loader2 size={14} className="spin"/> Carregando…</p>}</section>;
  const num=(k:keyof CfgCoord,t:string,min:number,max:number)=><label className="field"><span>{t}</span><input type="number" min={min} max={max} value={Number(c[k])} onChange={e=>setC({...c,[k]:Number(e.target.value)})}/></label>;
  return <section className="panel">
    <h3><Settings2 size={16}/> Configurações do Coordenador</h3>
    <div className="field"><span className="field-label">Modo</span><div className="seg" role="radiogroup">{([['supervisionado','Supervisionado (você libera cada pacote)'],['automatico','Automático (libera sozinho o que passou)']] as const).map(([k,t])=>
      <button key={k} role="radio" aria-checked={c.modo===k} className={c.modo===k?'on':''} onClick={()=>setC({...c,modo:k})}>{t}</button>)}</div>
      {c.modo==='automatico'&&<small className="warn">No automático, o pacote aprovado pelo diretor e com capa escolhida vai para a postagem sem passar por você.</small>}</div>
    <label className="check"><input type="checkbox" checked={c.exigir_liberacao} onChange={e=>setC({...c,exigir_liberacao:e.target.checked})}/> O Agente 2 só posta vídeo liberado aqui (vale para todos os posts)</label>
    <label className="check"><input type="checkbox" checked={c.usar_ia} onChange={e=>setC({...c,usar_ia:e.target.checked})}/> Usar a IA para entender pedidos que as regras não entendem</label>
    <div className="thumb-grade">{num('max_videos','Máximo de vídeos por pedido',1,30)}{num('correcoes_por_etapa','Correções por etapa',1,10)}{num('capas_padrao','Capas por vídeo (padrão)',0,4)}{num('intervalo_horas','Horas entre posts do mesmo dia',1,12)}</div>
    <label className="check"><input type="checkbox" checked={c.reposicao_automatica} onChange={e=>setC({...c,reposicao_automatica:e.target.checked})}/> Quando faltar vídeo para um horário, pedir mais cortes ao Agente 1 sozinho</label>
    <div className="thumb-grade">{num('reposicao_intervalo_min','Minutos entre pedidos de mais cortes',10,1440)}</div>
    <button className="primary sm" onClick={salvar}>Salvar</button>
  </section>;
}
