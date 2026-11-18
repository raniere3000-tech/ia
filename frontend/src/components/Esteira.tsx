import { useState } from 'react';
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, Gauge, Loader2, ShieldCheck, Workflow, XCircle } from 'lucide-react';
import { useApp } from '../state';
import { decidirExecucao, lerEsteira, ligarEsteira, verExecucao, type Achado, type DetalheExecucao, type Execucao, type Relatorio } from '../lib/esteira';
import { useCfg, useServidor, erroTexto } from './Servidor2';

const AGENTES:[string,string][]=[['agent1','1 · Cortes'],['agent3','3 · Criação'],['agent5','5 · Editor'],['agent4','4 · Diretor'],['agent2','2 · Postagem']];
const MOD:Record<string,string>={creative_preedit:'Cenas e roteiro',final_release:'Vídeo final'};
const SEV:Record<string,string>={bloqueio:'Bloqueio',alta:'Alta',media:'Média',baixa:'Baixa'};
const seg=(ms?:number|null)=>ms==null?'':`${(ms/1000).toFixed(1)}s`;
const ach=(a:Achado)=>({cat:a.category||a.categoria||'',sev:a.severity||a.severidade||'',ev:a.evidence||a.evidencia||'',ins:a.instruction||a.instrucao||'',
  alvo:a.target_agent||a.alvo||'',ini:a.time_start_ms??a.ini_ms,fim:a.time_end_ms??a.fim_ms,cena:a.scene||a.cena||''});
const NOME_ALVO:Record<string,string>={agent5:'Editor',agent3:'Agente 3',pessoa:'Você'};

/** Relatório do diretor: nota, partes da nota, bloqueios e o que cada um precisa corrigir (com o instante no vídeo). */
export function RelatorioQualidade({r}:{r:Relatorio}){
  return <div className="rq">
    <div className="rq-topo">
      <span className={'rq-nota '+(r.passed?'ok':'bad')}>{r.score}<small>/100</small></span>
      <div><b>{MOD[r.modalidade]||r.modalidade}</b> · {r.passed?'aprovado':'reprovado'}
        {r.attempts_limit!=null&&<span className="muted"> · correções usadas {r.attempts_used||0} de {r.attempts_limit}</span>}
        <br/><small className="muted">Regra fixa: nota 70 ou mais e nenhum bloqueio · {r.evaluator_version} · {new Date(r.created_at*1000).toLocaleString('pt-BR')}</small></div>
    </div>
    <div className="rq-partes">{Object.entries(r.partes).map(([k,p])=><div key={k} className="rq-parte">
      <span>{p.nome}</span><div className="barra"><i style={{width:`${p.maximo?100*p.pontos/p.maximo:0}%`}}/></div><b>{p.pontos}/{p.maximo}</b></div>)}</div>
    {r.blocking_findings.length>0&&<><h4 className="bad"><XCircle size={14}/> Bloqueios (nenhuma nota passa por cima)</h4>
      <ul className="rq-lista">{r.blocking_findings.map((a,i)=>{ const x=ach(a); return <li key={i} className="bad"><b>{x.ev}</b>{(x.ini!=null)&&<span className="tag">{seg(x.ini)}{x.fim!=null?`–${seg(x.fim)}`:''}</span>}<br/><small>{x.ins} → {NOME_ALVO[x.alvo]||x.alvo}</small></li>; })}</ul></>}
    {r.findings.filter(a=>ach(a).sev!=='bloqueio').length>0&&<><h4>Pontos a melhorar</h4>
      <ul className="rq-lista">{r.findings.filter(a=>ach(a).sev!=='bloqueio').map((a,i)=>{ const x=ach(a); return <li key={i}>
        <span className="tag">{SEV[x.sev]||x.sev}</span> {x.ev}{x.ini!=null&&<span className="tag">{seg(x.ini)}</span>}{x.cena&&<span className="tag">cena {x.cena}</span>}
        <br/><small className="muted">{x.ins} → {NOME_ALVO[x.alvo]||x.alvo}</small></li>; })}</ul></>}
    {(r.avisos||[]).length>0&&<details><summary>Observações ({(r.avisos||[]).length})</summary><ul className="rq-lista">{(r.avisos||[]).map((a,i)=><li key={i} className="muted">{a}</li>)}</ul></details>}
  </div>;
}

function Detalhe({id,fechar}:{id:string;fechar:()=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const d=useServidor<DetalheExecucao>(c=>verExecucao(c,id),0,[id]);
  const [motivo,setMotivo]=useState(''); const [busy,setBusy]=useState(false);
  const x=d.dados;
  async function decidir(dec:'aprovar'|'cancelar'){
    setBusy(true);
    try{ await decidirExecucao(cfg,id,dec,motivo); toast(dec==='aprovar'?'Liberado com o seu motivo registrado.':'Cancelado.','ok'); await d.recarregar(); }
    catch(e){ toast(erroTexto(e),'erro'); } finally{ setBusy(false); }
  }
  if(!x) return <p className="hint"><Loader2 size={13} className="spin"/> Lendo...</p>;
  return <div className="es-detalhe">
    <div className="es-contadores">{Object.entries(x.etapas).map(([m,s])=><span key={m} className="tag">{MOD[m]||m}: {s.avaliacoes} avaliação(ões), {s.correcoes} de {s.limite} correções · {s.estado}</span>)}</div>
    {x.relatorios.length?[...x.relatorios].reverse().map(r=><RelatorioQualidade key={r.id} r={r}/>):<p className="hint">O diretor ainda não conferiu.</p>}
    {x.planos.length>0&&<details><summary>Planos de edição ({x.planos.length} versão(ões))</summary><ul className="rq-lista">{x.planos.map(p=><li key={p.versao}>
      v{p.versao}: {p.motivo||'—'} {p.arquivo_sha&&<code>{p.arquivo_sha.slice(0,10)}</code>}</li>)}</ul></details>}
    {x.estado==='manual_review_required'&&<div className="es-manual">
      <p><AlertTriangle size={14}/> A esteira parou e precisa de você. Você pode liberar um vídeo com nota baixa (fica registrado), mas <b>não</b> dá para liberar bloqueio de direitos, arquivo quebrado, áudio faltando ou outro bloqueio técnico.</p>
      <input value={motivo} onChange={e=>setMotivo(e.target.value)} placeholder="Motivo da sua decisão (obrigatório)"/>
      <div className="row"><button className="primary sm" disabled={busy||motivo.trim().length<5} onClick={()=>decidir('aprovar')}><ShieldCheck size={14}/> Liberar</button>
        <button className="sm" disabled={busy||motivo.trim().length<5} onClick={()=>decidir('cancelar')}><XCircle size={14}/> Cancelar</button></div>
    </div>}
    <button className="link-btn" onClick={fechar}>Fechar</button>
  </div>;
}

function Linha({e}:{e:Execucao}){
  const [aberto,setAberto]=useState(false);
  const ok=e.estado==='final_approved'||e.estado==='published'||e.estado==='awaiting_human_publish_approval';
  const precisa=e.estado==='manual_review_required';
  return <li className={'es-linha'+(precisa?' alerta':'')}>
    <button className="es-cab" onClick={()=>setAberto(a=>!a)} aria-expanded={aberto}>
      {ok?<CheckCircle2 size={15} className="ok"/>:precisa?<AlertTriangle size={15} className="bad"/>:<Loader2 size={15} className={e.estado.endsWith('pending')||e.estado==='rendering'?'spin':''}/>}
      <span className="es-titulo">{e.titulo||e.ref}</span>
      <span className="tag">{e.nome_estado}</span>
      {e.nota!=null&&<span className={'tag '+(e.aprovado?'ok':'bad')}>nota {e.nota}</span>}
      {aberto?<ChevronUp size={14}/>:<ChevronDown size={14}/>}
    </button>
    {e.etapa&&<small className="muted">{e.etapa}</small>}
    {aberto&&<Detalhe id={e.id} fechar={()=>setAberto(false)}/>}
  </li>;
}

/** Esteira dos 5 agentes: chave liga/desliga, regra fixa, quanto tem em cada agente e cada vídeo com nota, correções e revisão manual. */
export default function Esteira(){
  const {toast}=useApp(); const cfg=useCfg();
  const p=useServidor(c=>lerEsteira(c),15);
  const [busy,setBusy]=useState(false);
  const d=p.dados;
  if(!cfg.servidor) return null;
  async function chave(on:boolean){
    if(on&&!confirm('Ligar a esteira? A partir de agora NENHUM vídeo é postado sem o certificado do diretor (nota 70 ou mais, sem bloqueios) para o arquivo exato. Vídeos já agendados sem certificado vão parar na conferência.')) return;
    setBusy(true);
    try{ await ligarEsteira(cfg,on); await p.recarregar(); toast(on?'Esteira ligada.':'Esteira desligada: vale a conferência de antes.','ok'); }
    catch(e){ toast(erroTexto(e),'erro'); } finally{ setBusy(false); }
  }
  const por=(a:string)=>(d?.execucoes||[]).filter(x=>x.agente===a&&!['final_approved','published','cancelled','failed_technical'].includes(x.estado)).length;
  return <section className="panel esteira">
    <div className="section-head"><h2><Workflow size={18}/> Esteira dos 5 agentes</h2>{p.carregando&&<Loader2 size={14} className="spin"/>}</div>
    {p.erro&&<p className="hint bad"><AlertTriangle size={14}/> {p.erro}</p>}
    {d&&<>
      <label className="check"><input type="checkbox" checked={d.ligado} disabled={busy} onChange={e=>chave(e.target.checked)}/> Esteira ligada {d.ligado?<span className="tag ok">ligada</span>:<span className="tag">desligada</span>}</label>
      <p className="hint"><Gauge size={13}/> Regra fixa: o diretor (Agente 4) dá uma nota de 0 a 100 medindo o vídeo exportado. Aprova com <b>{d.politica.nota_minima} ou mais e nenhum bloqueio</b>. A primeira avaliação não conta; cada etapa tem até <b>{d.politica.max_correcoes} correções</b>. Depois disso, o vídeo espera a sua revisão. O certificado vale só para aquele arquivo: exportou de novo, o diretor confere de novo. Opinião de IA nunca muda a nota.</p>
      {!d.ligado&&<p className="hint">Desligada, tudo funciona como antes. Recomendo testar ligada no celular com alguns vídeos antes de deixar no automático.</p>}
      <div className="es-agentes">{AGENTES.map(([k,n])=><div key={k} className="es-ag"><b>{por(k)}</b><span>{n}</span></div>)}
        <div className="es-ag pessoa"><b>{d.contagem.manual_review_required||0}</b><span>Esperando você</span></div></div>
      {d.execucoes.length?<ul className="es-lista">{d.execucoes.map(e=><Linha key={e.id} e={e}/>)}</ul>:<p className="hint">Nada passou pela esteira ainda.</p>}
    </>}
  </section>;
}
