import { useState } from 'react';
import { CheckCircle2, ChevronDown, ChevronRight, Loader2, RefreshCw, ShieldCheck, Workflow, Wrench } from 'lucide-react';
import { useApp } from '../state';
import { useCfg, useServidor, erroTexto } from './Servidor2';
import { duracaoTexto, horaTexto } from '../lib/api';
import { AGENTE_ETAPA, COR_ESTADO, ESTADO_VIDEO, avancarVideo, lerDiagnostico, lerEsteira, lerTimeline, recuperar, salvarPolitica, simularRecuperacao,
  type EtapaEsteira, type ItemRecuperacao, type Politica, type VideoEsteira } from '../lib/esteira7';

const curto=(s?:string|null)=>s?s.slice(0,12):'';

/** O que a etapa provou, em palavras simples (só o que está no recibo; nada inventado). */
function prova(e:EtapaEsteira):string{
  const r=(e.recibo||{}) as Record<string,unknown>; const p:string[]=[];
  if(r.nota!=null) p.push(`nota ${r.nota}`);
  if(r.certificado) p.push(`certificado ${curto(String(r.certificado))}`);
  if(r.relatorio) p.push(`laudo ${curto(String(r.relatorio))}`);
  if(r.plano_versao!=null) p.push(`plano v${r.plano_versao}`);
  if(r.render) p.push(`render ${curto(String(r.render))}`);
  if(r.corte) p.push(`corte ${curto(String(r.corte))}`);
  if(r.projeto) p.push(`projeto ${curto(String(r.projeto))}`);
  if(r.job) p.push(`trabalho ${curto(String(r.job))}`);
  if(r.capa_sha) p.push(`capa ${curto(String(r.capa_sha))}`);
  if(r.aprovacao) p.push(`pacote ${curto(String(r.aprovacao))}`);
  if(Array.isArray(r.posts)) p.push(`${r.posts.length} post(s)`);
  if(r.links&&typeof r.links==='object') Object.entries(r.links as Record<string,string>).forEach(([k,v])=>v&&p.push(`${k}: publicado`));
  if(e.saida_sha) p.push(`arquivo ${curto(e.saida_sha)}`);
  return p.join(' · ');
}

function Etapas({v}:{v:VideoEsteira}){
  return <ol className="esteira7-etapas">{v.etapas.map(e=><li key={e.etapa} className={'esteira7-etapa '+(COR_ESTADO[e.estado]||'')}>
    <div className="row-gap left"><b>{AGENTE_ETAPA[e.agente]||e.agente} · {e.nome}</b><span className={'tag '+(COR_ESTADO[e.estado]||'')}>{e.nome_estado}</span></div>
    <small className="muted">{e.segundos_ativos?`trabalho medido: ${duracaoTexto(e.segundos_ativos)}`:e.estado==='concluida'?'tempo não medido':''}
      {e.segundos_fila?` · esperou ${duracaoTexto(e.segundos_fila)}`:''}{e.correcoes?` · ${e.correcoes} correção(ões) de 5`:''}{e.fim?` · ${horaTexto(e.fim)}`:''}</small>
    {prova(e)&&<small>Prova: {prova(e)}</small>}
    {(e.motivo||e.erro)&&<small className={e.estado==='falhou'||e.estado==='aguardando_recurso'?'bad':'muted'}>{e.erro||e.motivo}</small>}
    {e.executor&&<small className="muted">Quem fez: {e.executor}</small>}
  </li>)}</ol>;
}

function Video({v,mudou}:{v:VideoEsteira;mudou:()=>void}){
  const cfg=useCfg(); const {toast}=useApp();
  const [aberto,setAberto]=useState(false); const [tl,setTl]=useState<VideoEsteira|null>(null); const [busy,setBusy]=useState(false);
  const [est,cor]=ESTADO_VIDEO[v.estado]||[v.estado,''];
  const atual=v.etapas.find(e=>e.etapa===v.etapa_atual);
  async function abrir(){ setAberto(!aberto); if(!aberto){ try{ setTl(await lerTimeline(cfg,v.id)); }catch(e){ toast(erroTexto(e),'erro'); } } }
  async function seguir(){ setBusy(true); try{ setTl(await avancarVideo(cfg,v.id)); mudou(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }
  return <div className="esteira7-video">
    <button className="esteira7-cab" onClick={abrir} aria-expanded={aberto}>
      {aberto?<ChevronDown size={14}/>:<ChevronRight size={14}/>}
      <span className="grow"><b>{v.titulo||v.ref}</b><small className="muted"> · {v.origem==='corte'?'corte (A1)':'vídeo próprio (A3)'}</small></span>
      <span className={'tag '+cor}>{est}</span>
    </button>
    <div className="esteira7-barra" aria-label={`${v.progresso}% das etapas`}><i style={{width:`${v.progresso}%`}}/></div>
    <small className="muted">Agora: {atual?.nome||'—'}{v.motivo?` — ${v.motivo}`:''} · trabalho medido no total: {duracaoTexto(v.segundos_total)}</small>
    {aberto&&<div>
      <Etapas v={tl||v}/>
      {!!tl?.historico?.length&&<details><summary>Histórico ({tl.historico.length} registros)</summary><ul className="plain muted esteira7-hist">
        {tl.historico.map(h=><li key={h.n}>{horaTexto(h.t)} · {h.etapa} → {h.estado}{(h.detalhe as {motivo?:string}).motivo?`: ${(h.detalhe as {motivo?:string}).motivo}`:''}</li>)}</ul></details>}
      <button className="subtle sm" disabled={busy} onClick={seguir}><RefreshCw size={13}/> Conferir agora</button>
    </div>}
  </div>;
}

function PoliticaCard({p,mudou}:{p:Politica;mudou:()=>void}){
  const cfg=useCfg(); const {toast}=useApp(); const [busy,setBusy]=useState(false);
  async function mudar(d:Partial<Politica>){ setBusy(true); try{ await salvarPolitica(cfg,{...d,versao:p.versao}); toast('Regra salva.','ok'); mudou(); }catch(e){ toast(erroTexto(e),'erro'); mudou(); }finally{ setBusy(false); } }
  return <div className="esteira7-politica">
    <label className="check"><input type="checkbox" checked={p.completa} disabled={busy} onChange={e=>mudar({completa:e.target.checked})}/> Esteira completa obrigatória (nada é postado sem diretor, capa e liberação)</label>
    <label className="check"><input type="checkbox" checked={p.capa_obrigatoria} disabled={busy} onChange={e=>mudar({capa_obrigatoria:e.target.checked})}/> Capa obrigatória</label>
    <label className="check"><input type="checkbox" checked={p.liberacao_automatica} disabled={busy} onChange={e=>mudar({liberacao_automatica:e.target.checked})}/> O Coordenador libera sozinho quando todos os itens do pacote passam</label>
    {!p.liberacao_automatica&&<p className="hint">Desligado: cada pacote espera você em Liberar.</p>}
  </div>;
}

function Recuperacao(){
  const cfg=useCfg(); const {toast}=useApp();
  const [itens,setItens]=useState<ItemRecuperacao[]|null>(null); const [sel,setSel]=useState<Set<string>>(new Set()); const [busy,setBusy]=useState(false);
  const [feitos,setFeitos]=useState<ItemRecuperacao[]|null>(null);
  async function simular(){ setBusy(true); setFeitos(null); try{ const r=await simularRecuperacao(cfg); setItens(r.itens); setSel(new Set(r.itens.filter(i=>i.acao).map(i=>i.video))); }
    catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }
  async function confirmar(){ if(!sel.size) return; setBusy(true); try{ const r=await recuperar(cfg,[...sel]); setFeitos(r.feitos); setItens(null); toast(`${r.total} vídeo(s) recuperado(s).`,'ok'); }
    catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }
  return <section className="panel">
    <h3><Wrench size={16}/> Recuperar produções incompletas</h3>
    <p className="hint">Primeiro eu só mostro o que falta em cada vídeo (nada muda). Depois você escolhe e confirma. Vídeos já postados e cancelados ficam de fora.</p>
    <button className="subtle sm" disabled={busy} onClick={simular}>{busy?<Loader2 size={13} className="spin"/>:<RefreshCw size={13}/>} Ver o que falta</button>
    {itens&&(!itens.length?<p className="muted">Nenhuma produção incompleta.</p>:<>
      <ul className="plain esteira7-rec">{itens.map(i=><li key={i.video}>
        <label className="check"><input type="checkbox" disabled={!i.acao} checked={sel.has(i.video)} onChange={e=>{ const s=new Set(sel); if(e.target.checked) s.add(i.video); else s.delete(i.video); setSel(s); }}/>
          <span><b>{i.titulo}</b> <small className="muted">({i.origem==='corte'?'corte':'vídeo próprio'})</small><br/><small>{i.motivo}</small></span></label></li>)}</ul>
      <button className="primary sm" disabled={busy||!sel.size} onClick={confirmar}><CheckCircle2 size={14}/> Confirmar recuperação de {sel.size}</button>
    </>)}
    {feitos&&<ul className="plain muted">{feitos.map(f=><li key={f.video}>{f.titulo}: {f.feito}</li>)}</ul>}
  </section>;
}

/** Tela da esteira dos 7 agentes (Agentes > Coordenador > Esteira): cada vídeo com as 8 etapas, prova e tempo. */
export default function EsteiraSete(){
  const [filtro,setFiltro]=useState('');
  const r=useServidor(c=>lerEsteira(c,filtro,40),10,[filtro]);
  const d=useServidor(c=>lerDiagnostico(c),0);
  const res=r.dados?.resumo;
  return <>
    <section className="panel">
      <h3><Workflow size={16}/> Esteira dos 7 agentes</h3>
      <p className="hint">A1 corta (ou A3 cria) → A4 avaliação inicial → A5 edita → A4 aprova o arquivo final → A6 capa → A7 libera → A2 publica. Cada etapa só conclui com prova.</p>
      {r.erro&&<p className="hint bad">{/rota não encontrada|404/i.test(r.erro)?'Atualize o servidor (git pull no Termux) para ver a esteira.':r.erro}</p>}
      {r.dados&&<PoliticaCard p={r.dados.politica} mudou={()=>{ r.recarregar(); d.recarregar(); }}/>}
      {d.dados&&<p className="muted"><ShieldCheck size={13}/> Editor e diretor: {d.dados.esteira_ligada?'ligados':'desligados'} · Agente 2 exige liberação: {d.dados.coordenador.liberacao_efetiva?'sim':'não'} · Agente 6: {d.dados.agente6?`modo ${d.dados.agente6.modo}${d.dados.agente6.criar_sozinho?', cria sozinho':''}`:'—'}</p>}
      {res&&<div className="row-gap left esteira7-filtros">
        {([['','Todos'],['em_andamento','Em andamento'],['aguardando_voce','Esperando você'],['bloqueado','Bloqueados'],['publicado','Publicados']] as const).map(([k,t])=>
          <button key={k} className={'subtle sm'+(filtro===k?' on':'')} onClick={()=>setFiltro(k)}>{t}{k&&res.por_estado[k]!=null?` (${res.por_estado[k]})`:''}</button>)}
      </div>}
      {!r.dados?(!r.erro&&<p className="muted"><Loader2 size={14} className="spin"/> Carregando…</p>):!r.dados.videos.length?<p className="muted">Nenhum vídeo na esteira{filtro?' com este filtro':''}.</p>:
        r.dados.videos.map(v=><Video key={v.id} v={v} mudou={()=>r.recarregar()}/>)}
    </section>
    <Recuperacao/>
  </>;
}
