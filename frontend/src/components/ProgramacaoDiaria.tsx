import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CalendarClock, Copy, Eye, Loader2, Plus, Save, Trash2, X } from 'lucide-react';
import { useApp } from '../state';
import { apagarAgenda, cancelarSlot, criarAgenda, listarAgendas, listarSlots, metricasAgenda, mudarAgenda, previaAgenda, type Agenda, type ConfigAgenda, type Modo, type Previa, type Slot } from '../lib/esteira';
import { useCfg, useServidor, erroTexto } from './Servidor2';

const DIAS=['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'];
const REDES:[string,string][]=[['youtube','YouTube Shorts'],['instagram','Instagram Reels'],['facebook','Facebook Reels'],['tiktok','TikTok'],['kwai','Kwai (só manual)']];
const MODOS:[Modo,string,string][]=[['fixed','Horários fixos','Cada horário é um post. A meta do dia é a quantidade de horários.'],
  ['automatic','Automático','Você diz quantos por dia; o agente espalha dentro da janela com o intervalo mínimo.'],
  ['mixed','Misto','Horários fixos + alguns flexíveis espalhados na janela.']];
const ESTADO:Record<string,string>={vazio:'Vazio',reservado:'Reservado',agendado:'Agendado',publicando:'Publicando',publicado:'Publicado',erro:'Erro',perdido:'Perdido',
  aguardando_aprovacao:'Esperando você',manual:'Manual'};
const NOVA:ConfigAgenda={account_id:'principal',platform:'youtube',timezone:'America/Sao_Paulo',mode:'fixed',enabled:true,
  weekly_rules:{'0':['09:00','12:00','18:00'],'1':['09:00','12:00','18:00'],'2':['09:00','12:00','18:00'],'3':['09:00','12:00','18:00'],'4':['09:00','12:00','18:00']},
  flex_slots_per_day:0,automatic_window:{start:'09:00',end:'22:00'},minimum_gap_minutes:60,missed_slot_policy:'next_slot',max_delay_minutes:60,selection_policy:'oldest_approved',exceptions:{}};

function Editor({base,id,version,fechar,salvo}:{base:ConfigAgenda;id?:string;version?:number;fechar:()=>void;salvo:()=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const [c,setC]=useState<ConfigAgenda>(base);
  const [pv,setPv]=useState<Previa|null>(null); const [erro,setErro]=useState(''); const [busy,setBusy]=useState(false);
  const [exc,setExc]=useState('');
  const set=(p:Partial<ConfigAgenda>)=>setC(x=>({...x,...p}));
  const dia=(k:string)=>c.weekly_rules[k];
  const setDia=(k:string,v:string[]|null)=>setC(x=>{ const w={...x.weekly_rules}; if(v===null) delete w[k]; else w[k]=v; return {...x,weekly_rules:w}; });
  useEffect(()=>{ const t=setTimeout(()=>{ previaAgenda(cfg,c).then(r=>{ setPv(r); setErro(''); }).catch(e=>{ setPv(null); setErro(erroTexto(e)); }); },400); return ()=>clearTimeout(t); },[c,cfg]);
  async function salvar(){
    setBusy(true);
    try{ if(id) await mudarAgenda(cfg,id,{...c,version:version||1}); else await criarAgenda(cfg,c); toast('Programação guardada.','ok'); salvo(); fechar(); }
    catch(e){ toast(erroTexto(e),'erro'); } finally{ setBusy(false); }
  }
  const usaFixos=c.mode!=='automatic';
  return <div className="pd-editor">
    <div className="grid2">
      <label>Rede<select value={c.platform} disabled={!!id} onChange={e=>set({platform:e.target.value})}>{REDES.map(([k,n])=><option key={k} value={k}>{n}</option>)}</select></label>
      <label>Fuso horário<input value={c.timezone} onChange={e=>set({timezone:e.target.value})}/></label>
    </div>
    <div className="pd-modos" role="radiogroup">{MODOS.map(([k,n,d])=><label key={k} className={'pd-modo'+(c.mode===k?' on':'')}><input type="radio" checked={c.mode===k} onChange={()=>set({mode:k})}/><b>{n}</b><small>{d}</small></label>)}</div>
    {usaFixos&&<div className="pd-dias">{DIAS.map((n,i)=>{ const k=String(i); const hs=dia(k); return <div key={k} className={'pd-dia'+(hs?' on':'')}>
      <label className="check"><input type="checkbox" checked={!!hs} onChange={e=>setDia(k,e.target.checked?(c.weekly_rules['0']||['12:00']).slice():null)}/> {n}</label>
      {hs&&<div className="pd-horas">{hs.map((h,j)=><span key={j} className="pd-hora">
        <input type="time" value={h} aria-label={`${n} horário ${j+1}`} onChange={e=>setDia(k,hs.map((x,q)=>q===j?e.target.value:x))}/>
        <button className="icon sm" aria-label="Tirar horário" onClick={()=>setDia(k,hs.filter((_,q)=>q!==j))}><X size={12}/></button></span>)}
        <button className="sm" onClick={()=>setDia(k,[...hs,'20:00'])}><Plus size={12}/> horário</button>
        <button className="sm" title="Copiar estes horários para todos os dias marcados" onClick={()=>setC(x=>({...x,weekly_rules:Object.fromEntries(Object.keys(x.weekly_rules).map(q=>[q,hs.slice()]))}))}><Copy size={12}/> igual nos outros</button>
      </div>}
    </div>; })}</div>}
    {!usaFixos&&<div className="pd-dias">{DIAS.map((n,i)=>{ const k=String(i); return <label key={k} className="check"><input type="checkbox" checked={!!dia(k)} onChange={e=>setDia(k,e.target.checked?[]:null)}/> {n}</label>; })}</div>}
    <div className="grid2">
      {c.mode!=='fixed'&&<label>{c.mode==='mixed'?'Posts flexíveis por dia (além dos fixos)':'Posts por dia'}<input type="number" min={0} max={24} value={c.flex_slots_per_day} onChange={e=>set({flex_slots_per_day:+e.target.value})}/></label>}
      {c.mode!=='fixed'&&<label>Janela<span className="row"><input type="time" value={c.automatic_window.start} onChange={e=>set({automatic_window:{...c.automatic_window,start:e.target.value}})}/> até <input type="time" value={c.automatic_window.end} onChange={e=>set({automatic_window:{...c.automatic_window,end:e.target.value}})}/></span></label>}
      <label>Intervalo mínimo entre posts (min)<input type="number" min={5} max={720} value={c.minimum_gap_minutes} onChange={e=>set({minimum_gap_minutes:+e.target.value})}/></label>
      <label>Se o servidor estiver desligado na hora<select value={c.missed_slot_policy} onChange={e=>set({missed_slot_policy:e.target.value as ConfigAgenda['missed_slot_policy']})}>
        <option value="next_slot">Não posta atrasado (vai no próximo horário)</option><option value="publish_when_online">Posta quando voltar, até um atraso máximo</option><option value="manual_review">Espera eu decidir</option></select></label>
      {c.missed_slot_policy==='publish_when_online'&&<label>Atraso máximo (min)<input type="number" min={15} max={360} value={c.max_delay_minutes} onChange={e=>set({max_delay_minutes:+e.target.value})}/></label>}
      <label>Qual vídeo vai primeiro<select value={c.selection_policy} onChange={e=>set({selection_policy:e.target.value as ConfigAgenda['selection_policy']})}>
        <option value="oldest_approved">O aprovado mais antigo</option><option value="best_score">A maior nota do diretor</option></select></label>
    </div>
    <div className="pd-exc"><b>Datas especiais</b>
      {Object.entries(c.exceptions).map(([d,v])=><span key={d} className="tag">{new Date(d+'T12:00').toLocaleDateString('pt-BR')}: {v==='pausado'?'sem posts':(v as string[]).join(', ')}
        <button className="icon sm" aria-label="Tirar data" onClick={()=>setC(x=>{ const e={...x.exceptions}; delete e[d]; return {...x,exceptions:e}; })}><X size={11}/></button></span>)}
      <span className="row"><input type="date" value={exc} onChange={e=>setExc(e.target.value)}/><button className="sm" disabled={!exc} onClick={()=>{ set({exceptions:{...c.exceptions,[exc]:'pausado'}}); setExc(''); }}>Pausar esta data</button></span>
    </div>
    <label className="check"><input type="checkbox" checked={c.enabled} onChange={e=>set({enabled:e.target.checked})}/> Programação ligada</label>
    {erro&&<p className="hint bad"><AlertTriangle size={13}/> {erro}</p>}
    {pv&&<div className="pd-previa"><h4><Eye size={14}/> Próximos 7 dias: {pv.total} post(s)</h4>
      {pv.avisos.map(a=><p key={a} className="hint"><AlertTriangle size={12}/> {a}</p>)}
      <ul>{pv.dias.map(d=><li key={d.data}><b>{d.dia} {new Date(d.data+'T12:00').toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit'})}</b>{' '}
        {d.excecao==='pausado'?<span className="muted">pausado</span>:d.horarios.length?d.horarios.map(h=><span key={h.hora} className={'tag'+(h.tipo==='flexivel'?' flex':'')}>{h.hora}</span>):<span className="muted">sem posts</span>}</li>)}</ul></div>}
    <div className="row"><button className="primary sm" disabled={busy||!!erro} onClick={salvar}><Save size={14}/> Guardar</button><button className="sm" onClick={fechar}>Fechar</button></div>
  </div>;
}

/** Agente 2 > Programação diária: horários por rede, prévia de 7 dias, horários com o vídeo de cada um e o resumo do dia. */
export default function ProgramacaoDiaria(){
  const {toast}=useApp(); const cfg=useCfg();
  const ags=useServidor(c=>listarAgendas(c),30);
  const sl=useServidor(c=>listarSlots(c),30);
  const mt=useServidor(c=>metricasAgenda(c,new Date().toLocaleDateString('sv-SE')),60);
  const [ed,setEd]=useState<{base:ConfigAgenda;id?:string;version?:number}|null>(null);
  const porDia=useMemo(()=>{ const m:Record<string,Slot[]>={}; for(const s of sl.dados?.slots||[]) (m[s.data_local]=m[s.data_local]||[]).push(s); return Object.entries(m).slice(0,8); },[sl.dados]);
  if(!cfg.servidor) return null;
  const recarregar=()=>{ ags.recarregar(); sl.recarregar(); mt.recarregar(); };
  const nomeRede=(r:string)=>REDES.find(x=>x[0]===r)?.[1]||r;
  return <section className="panel programacao">
    <div className="section-head"><h2><CalendarClock size={18}/> Programação diária</h2>{(ags.carregando||sl.carregando)&&<Loader2 size={14} className="spin"/>}</div>
    <p className="hint">Para cada rede, escolha os dias e os horários. Cada horário só recebe vídeo <b>aprovado pelo diretor</b> (certificado do arquivo atual) e com direitos confirmados. Sem vídeo aprovado, o horário fica vazio: nada é inventado nem repetido. Os posts que você já agendou à mão continuam como estão.</p>
    {ags.dados&&!ags.dados.esteira&&<p className="hint bad"><AlertTriangle size={13}/> A esteira dos 5 agentes está desligada: sem o certificado do diretor, nenhum horário recebe vídeo. Ligue em Agentes &gt; 5 agentes.</p>}
    {(ags.erro||sl.erro)&&<p className="hint bad">{ags.erro||sl.erro}</p>}
    {mt.dados&&Object.keys(mt.dados.por_rede).length>0&&<div className="pd-metricas">{Object.entries(mt.dados.por_rede).map(([r,m])=><div key={r} className="es-ag">
      <b>{m.publicados}/{m.meta}</b><span>{nomeRede(r)} hoje</span><small>{m.agendados} agendado(s) · {m.livres} vazio(s){m.falhas?` · ${m.falhas} erro(s)`:''} · {mt.dados?.disponiveis[r]??0} aprovado(s) esperando</small></div>)}</div>}
    <ul className="pd-agendas">{(ags.dados?.agendas||[]).map(a=><li key={a.id}>
      <b>{a.nome_rede}</b> <span className={'tag '+(a.enabled?'ok':'')}>{a.enabled?'ligada':'desligada'}</span> <span className="muted">{MODOS.find(m=>m[0]===a.mode)?.[1]} · {a.meta_semana} post(s) por semana</span>
      <span className="row"><button className="sm" onClick={()=>setEd({base:a as Agenda,id:a.id,version:a.version})}>Editar</button>
        <button className="icon sm" aria-label="Apagar programação" onClick={async()=>{ if(!confirm('Apagar esta programação? Os horários vazios somem; os posts já agendados continuam.')) return; try{ await apagarAgenda(cfg,a.id); recarregar(); }catch(e){ toast(erroTexto(e),'erro'); } }}><Trash2 size={13}/></button></span>
    </li>)}</ul>
    {!ed&&<button className="sm" onClick={()=>setEd({base:{...NOVA,platform:REDES.map(r=>r[0]).find(r=>!(ags.dados?.agendas||[]).some(a=>a.platform===r))||'youtube'}})}><Plus size={14}/> Programar uma rede</button>}
    {ed&&<Editor base={ed.base} id={ed.id} version={ed.version} fechar={()=>setEd(null)} salvo={recarregar}/>}
    {porDia.length>0&&<><h3>Próximos horários</h3>
      <div className="pd-calendario">{porDia.map(([d,ss])=><div key={d} className="pd-cal-dia"><b>{new Date(d+'T12:00').toLocaleDateString('pt-BR',{weekday:'short',day:'2-digit',month:'2-digit'})}</b>
        <ul>{ss.map(s=><li key={s.id} className={'pd-slot '+s.estado}><span>{s.hora_local}</span> <span>{nomeRede(s.rede)}</span> <span className="tag">{ESTADO[s.estado]||s.estado}</span>
          {s.motivo&&s.estado!=='agendado'&&<small className="muted"> {s.motivo}</small>}
          {['vazio','agendado','reservado','aguardando_aprovacao'].includes(s.estado)&&s.quando_utc*1000>Date.now()&&<button className="icon sm" aria-label="Cancelar este horário" onClick={async()=>{
            if(!confirm('Cancelar este horário? Se tiver vídeo, ele volta para a fila de prontos.')) return; try{ await cancelarSlot(cfg,s.id); recarregar(); }catch(e){ toast(erroTexto(e),'erro'); } }}><X size={12}/></button>}
        </li>)}</ul></div>)}</div></>}
  </section>;
}
