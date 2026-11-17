import { ESTILOS } from '../lib/estilosVisuais';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Bot, Scissors, Send, Square, Play, Search, Link2, Loader2, CheckCircle2, AlertTriangle, Trash2, Mail, Download, Eye, Plus, X, KeyRound, Clock, RefreshCw, ExternalLink, CalendarClock, ShieldCheck } from 'lucide-react';
import { useApp } from '../state';
import { REDES } from '../lib/agenda';
import { useServidor } from '../components/Servidor2';
import { lerFila, pendentes, listarProjetos, catalogo, horaTexto } from '../lib/api';
import { verAgente, salvarAgente, salvarChaves, acaoCanal, rodarAgente, pararAgente, testarEmail, testarWhatsapp, acaoCorte, videoDoCorte, salvarPesos, aprenderAgora, DIAS, MOTIVOS, type VisaoAgente, type ConfigAgente, type Uso, type Canal, type CorteAgente } from '../lib/agente';

type Parte = 'cortes'|'postagem'|'agente3'|'desempenho'|'avisos'|'fila';
const num=(n:number)=>n.toLocaleString('pt-BR');
const tempo=(s:number)=>s<60?`${s} s`:`${Math.floor(s/60)} min${s%60?` e ${s%60} s`:''}`;
const quando=(ts:number)=>new Date(ts*1000).toLocaleString('pt-BR',{weekday:'short',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
const ST:Record<string,[string,string]>={pronto:['Aprovado pelo diretor, falta você','info'],reprovado:['Reprovado pelo diretor','bad'],agendado:['Agendado','warn'],postado:['Enviado','ok'],descartado:['Descartado','']};

/** Campo que só salva quando você sai dele (não manda um pedido a cada letra). */
function Campo({valor,salvar,tipo='text',...resto}:{valor:string|number;salvar:(v:string)=>void;tipo?:string}&Omit<React.InputHTMLAttributes<HTMLInputElement>,'value'|'onChange'|'type'>){
  const [v,setV]=useState(String(valor));
  useEffect(()=>{ setV(String(valor)); },[valor]);
  return <input {...resto} type={tipo} value={v} onChange={e=>setV(e.target.value)} onBlur={()=>{ if(v!==String(valor)) salvar(v); }} onKeyDown={e=>{ if(e.key==='Enter') (e.target as HTMLInputElement).blur(); }}/>;
}

function Lista({titulo,escolhidos,sugestoes,mudar,placeholder}:{titulo:string;escolhidos:string[];sugestoes:string[];mudar:(l:string[])=>void;placeholder:string}){
  const [novo,setNovo]=useState('');
  const tem=(s:string)=>escolhidos.some(e=>e.toLowerCase()===s.toLowerCase());
  const troca=(s:string)=>mudar(tem(s)?escolhidos.filter(e=>e.toLowerCase()!==s.toLowerCase()):[...escolhidos,s]);
  const extras=escolhidos.filter(e=>!sugestoes.some(s=>s.toLowerCase()===e.toLowerCase()));
  const add=()=>{ const t=novo.trim(); if(t&&!tem(t)) mudar([...escolhidos,t]); setNovo(''); };
  return <div className="ag-lista">
    <span className="field-label">{titulo}</span>
    <div className="chips">{[...sugestoes,...extras].map(s=><button key={s} type="button" className={'chip '+(tem(s)?'on':'')} aria-pressed={tem(s)} onClick={()=>troca(s)}>{s}</button>)}</div>
    <div className="ag-add"><input value={novo} onChange={e=>setNovo(e.target.value)} onKeyDown={e=>{ if(e.key==='Enter') add(); }} placeholder={placeholder}/><button type="button" className="subtle sm" onClick={add} disabled={!novo.trim()}><Plus size={14}/> Adicionar</button></div>
  </div>;
}

const COMERCIAL:[string,string][]=[['','Ainda não sei'],['sim','Sim, posso monetizar'],['nao','Não, sem uso comercial']];
function CanalLinha({c,fazer}:{c:Canal;fazer:(d:Parameters<typeof acaoCanal>[1])=>void}){
  const [abrir,setAbrir]=useState(false); const [motivo,setMotivo]=useState(''); const [editar,setEditar]=useState(false);
  const [com,setCom]=useState(c.comercial===true?'sim':c.comercial===false?'nao':''); const [onde,setOnde]=useState(c.origem_aut||''); const [restr,setRestr]=useState(c.restricoes||'');
  const direitos=()=>({comercial:com===''?null:com==='sim',origem_aut:onde.trim(),restricoes:restr.trim()});
  const campos=<>
    <label>Onde está a autorização (link, e-mail, data da conversa)<input value={onde} maxLength={300} onChange={e=>setOnde(e.target.value)} placeholder="Ex.: regra em youtube.com/@canal/about, ou e-mail de 10/11"/></label>
    <label>Pode usar para ganhar dinheiro (monetização)?<select value={com} onChange={e=>setCom(e.target.value)}>{COMERCIAL.map(([k,t])=><option key={k} value={k}>{t}</option>)}</select></label>
    <label>Restrições de uso<input value={restr} maxLength={300} onChange={e=>setRestr(e.target.value)} placeholder="Ex.: dar crédito no vídeo, só Shorts, não cortar lives"/></label>
  </>;
  return <li className={'ag-canal '+c.status}>
    <div className="grow">
      <a href={`https://www.youtube.com/channel/${c.id}`} target="_blank" rel="noreferrer"><strong>{c.nome||c.id}</strong> <ExternalLink size={12}/></a>
      <small>{c.media>0&&<>média de <b>{num(c.media)}</b> visualizações em {c.videos} vídeo(s) da semana · </>}{c.inscritos>0&&<>{num(c.inscritos)} inscritos · </>}{c.nicho}</small>
      {c.exemplo&&<small className="muted">Ex.: {c.exemplo}</small>}
      {c.ficha&&<details className="ficha"><summary>Ficha da oportunidade</summary>
       <p><b>Por quê:</b> {c.ficha.justificativa}</p>
       <p><b>Medido (números públicos):</b> média {num(c.ficha.medido.media_views)} views • {c.ficha.medido.videos_na_semana} vídeo(s) na semana • maior {num(c.ficha.medido.maior_views)}</p>
       {c.ficha.estimado.views_por_dia_do_melhor!=null&&<p><b>Estimativa:</b> o melhor vídeo ganha cerca de {num(c.ficha.estimado.views_por_dia_do_melhor)} views por dia (conta feita pela data de publicação; não é número do YouTube)</p>}
       <ul>{c.ficha.videos.map(v=><li key={v.url}><a href={v.url} target="_blank" rel="noreferrer">{v.titulo}</a> • {num(v.views)} views • {v.publicado}</li>)}</ul>
       <p className="muted"><b>Ainda não conferido:</b> {c.ficha.nao_verificado.join('; ')}.</p>
       <p className="muted"><b>Risco:</b> {c.ficha.risco}</p>
       <small className="muted">Fonte: {c.ficha.fonte} • filtros: {Object.entries(c.ficha.filtros).map(([k,v])=>`${k} ${v}`).join(', ')} • buscado em {new Date(c.ficha.buscado_em*1000).toLocaleString('pt-BR')}</small>
      </details>}
      {c.status==='aprovado'&&<span className="label-row"><span className="tag ok"><CheckCircle2 size={12}/> {MOTIVOS[c.motivo]||'Aprovado'}</span>
        <span className={'tag '+(c.comercial===true?'ok':c.comercial===false?'bad':'warn')}>{c.comercial===true?'Uso comercial permitido':c.comercial===false?'Sem uso comercial: o agente não publica':'Uso comercial não informado'}</span></span>}
      {c.status==='aprovado'&&c.origem_aut&&<small className="muted">Autorização: {c.origem_aut}</small>}
      {c.status==='aprovado'&&c.restricoes&&<small className="muted">Restrições: {c.restricoes}</small>}
    </div>
    <div className="ag-canal-acoes">
      {c.status!=='aprovado'&&!abrir&&<button className="primary sm" onClick={()=>setAbrir(true)}>Aprovar</button>}
      {c.status==='sugerido'&&!abrir&&<button className="subtle sm" onClick={()=>fazer({acao:'recusar',id:c.id})}>Recusar</button>}
      {c.status==='aprovado'&&!editar&&<button className="subtle sm" onClick={()=>setEditar(true)}>Permissões</button>}
      {c.status!=='sugerido'&&<button className="link-btn" onClick={()=>fazer({acao:'remover',id:c.id})}><Trash2 size={13}/> Tirar da lista</button>}
    </div>
    {editar&&<div className="ag-motivo">
      <b>Permissões de {c.nome||'este canal'}</b>
      {campos}
      <div className="row-gap left"><button className="primary sm" onClick={()=>{ fazer({acao:'editar',id:c.id,...direitos()}); setEditar(false); }}>Guardar</button><button className="subtle sm" onClick={()=>setEditar(false)}>Cancelar</button></div>
    </div>}
    {abrir&&<div className="ag-motivo">
      <b>Por que você pode cortar este canal?</b>
      {Object.entries(MOTIVOS).map(([k,t])=><label key={k} className="check"><input type="radio" name={'motivo'+c.id} checked={motivo===k} onChange={()=>setMotivo(k)}/> {t}</label>)}
      {campos}
      <p className="hint warn"><AlertTriangle size={13}/> Confira a permissão antes de marcar. Cortar canal de terceiros sem permissão pode derrubar as suas contas.</p>
      <div className="row-gap left"><button className="primary sm" disabled={!motivo} onClick={()=>{ fazer({acao:'aprovar',id:c.id,motivo,...direitos()}); setAbrir(false); }}>Confirmar aprovação</button><button className="subtle sm" onClick={()=>setAbrir(false)}>Cancelar</button></div>
    </div>}
  </li>;
}

function CorteLinha({c,fazer}:{c:CorteAgente;fazer:(acao:'descartar'|'agendar'|'liberar'|'email')=>void}){
  const {settings,toast}=useApp();
  const [url,setUrl]=useState(''); const [busy,setBusy]=useState(false);
  useEffect(()=>()=>{ if(url) URL.revokeObjectURL(url); },[url]);
  const trazer=async(baixar:boolean)=>{
    setBusy(true);
    try{
      const blob=await videoDoCorte(settings,c.id); const u=URL.createObjectURL(blob);
      if(baixar){ const a=document.createElement('a'); a.href=u; a.download=(c.titulo.replace(/[\\/:*?"<>|]+/g,'').slice(0,60)||'corte')+'.mp4'; a.click(); setTimeout(()=>URL.revokeObjectURL(u),30000); }
      else setUrl(u);
    }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }finally{ setBusy(false); }
  };
  const [rot,cls]=ST[c.status]||[c.status,''];
  return <li className="ag-corte">
    {url&&<video src={url} controls playsInline className="ag-video"/>}
    <div className="grow">
      <div className="label-row"><strong>{c.titulo}</strong><span className={'tag '+cls}>{rot}</span>{c.tipo==='manual'?<span className="tag">feito por você</span>:<span className="tag">pontuação {c.nota}/99</span>}<span className="tag">{c.modelo_nome||'Sem template'}</span>{c.espera&&c.status==='pronto'&&<span className="tag warn">guardado, fora da fila</span>}{c.email&&<span className="tag"><Mail size={11}/> enviado por e-mail</span>}</div>
      <small>{c.tipo==='manual'?'Enviado da edição manual':<>{Math.round(c.fim-c.ini)} s · de “{c.origem_titulo}” ({c.canal_nome})</>} · feito {quando(c.criado)}{c.quando&&c.status!=='pronto'?` · post ${quando(c.quando)}`:''}{typeof c.views==='number'?` · ${num(c.views)} visualizações no YouTube`:''}</small>
      {c.hashtags.length>0&&<small className="muted">{c.hashtags.join(' ')}</small>}
      {c.motivo&&<small className="muted">Por que este trecho: {c.motivo}</small>}
      {c.conferencia?.bloqueios.map(b=><p key={b} className="hint bad"><AlertTriangle size={13}/> {c.conferencia?.liberaveis?.includes(b)?'Restrição (você pode liberar): ':'Não pode ser publicado: '}{b}</p>)}
      {c.liberacao&&<p className="hint warn"><ShieldCheck size={13}/> Liberado por você apesar de: {c.liberacao.restricoes.join(' · ')}</p>}
      {c.conferencia?.avisos.map(b=><p key={b} className="hint warn"><AlertTriangle size={13}/> {b}</p>)}
      {c.metricas&&Object.entries(c.metricas).filter(([,m])=>m.views!==null||m.curtidas!==null).map(([r,m])=><small key={r} className="muted">{r}: {m.views!==null?`${num(m.views)} visualizações`:''}{m.curtidas!==null?` · ${num(m.curtidas)} curtidas · ${num(m.comentarios||0)} comentários`:''}</small>)}
      {c.qa?.diretor&&(c.qa.diretor.veredito==='aprovado'?<p className="hint ok">Diretor de qualidade aprovou{c.qa.diretor.tentativas>0?` depois de refazer ${c.qa.diretor.tentativas} vez(es)`:''}.</p>:<p className="hint bad"><AlertTriangle size={13}/> Diretor de qualidade reprovou mesmo depois de refazer {c.qa.diretor.tentativas} vez(es): {c.qa.diretor.motivos.join(' · ')}. Este corte não vai para você nem para as redes.</p>)}
      {c.erros&&Object.entries(c.erros).map(([r,m])=><p key={r} className="hint bad"><AlertTriangle size={13}/> {r}: {m}</p>)}
      {c.links&&Object.entries(c.links).filter(([,l])=>/^https?:/.test(l)).map(([r,l])=><a key={r} className="link-btn" href={l.split(' ')[0]} target="_blank" rel="noreferrer">{r} <ExternalLink size={12}/></a>)}
    </div>
    {c.video&&<div className="ag-canal-acoes">
      {!url&&<button className="subtle sm" disabled={busy} onClick={()=>trazer(false)}>{busy?<Loader2 size={14} className="spin"/>:<Eye size={14}/>} Ver</button>}
      <button className="subtle sm" disabled={busy} onClick={()=>trazer(true)}><Download size={14}/> Baixar</button>
      {c.status==='pronto'&&!c.conferencia?.bloqueios.length&&<button className="primary sm" onClick={()=>fazer('agendar')}><CalendarClock size={14}/> Aprovar e agendar</button>}
      {c.status==='pronto'&&!!c.conferencia?.bloqueios.length&&(c.conferencia.liberavel?<button className="primary sm" onClick={()=>fazer('liberar')}><ShieldCheck size={14}/> Liberar e agendar mesmo assim</button>:<button className="primary sm" disabled><CalendarClock size={14}/> Aprovar e agendar</button>)}
      <button className="subtle sm" onClick={()=>fazer('email')}><Mail size={14}/> E-mail</button>
      {c.status!=='descartado'&&c.status!=='postado'&&<button className="link-btn" onClick={()=>fazer('descartar')}><Trash2 size={13}/> Descartar</button>}
    </div>}
  </li>;
}

function PesosRede({rede,nome,ids,pesos,definido,guardar}:{rede:string;nome:string;ids:string[];pesos:Record<string,number>;definido:boolean;guardar:(p:Record<string,number>)=>void}){
  const [val,setVal]=useState<Record<string,string>>(()=>Object.fromEntries(ids.map(i=>[i,String(Math.round((pesos[i]??1/ids.length)*100))])));
  const mudou=ids.some(i=>val[i]!==String(Math.round((pesos[i]??1/ids.length)*100)));
  return <tr><td><b>{nome}</b>{!definido&&<small className="muted"> · iguais</small>}</td>
    {ids.map(i=><td key={i}><input className="ag-peso" type="number" min={0} max={100} value={val[i]??''} onChange={e=>setVal(x=>({...x,[i]:e.target.value}))} aria-label={`Peso em ${rede}`}/> %</td>)}
    <td>{mudou&&<button className="primary sm" onClick={()=>guardar(Object.fromEntries(ids.map(i=>[i,+val[i]||0])))}>Guardar</button>}</td></tr>;
}

/** Cartão do Agente 3 no topo da tela de agentes (mesmo jeito dos outros dois). */
function Agente3Cartao(){
  const {go}=useApp();
  const fila=useServidor(c=>lerFila(c),10); const pend=useServidor(pendentes,20);
  const j3=(fila.dados?.jobs||[]).filter(j=>j.agente==='agente3'&&['rodando','na_fila','agendado','aguardando_tentativa'].includes(j.status));
  const rodando=j3.find(j=>j.status==='rodando'); const esp=(pend.dados?.pendentes||[]).length;
  return <div className={'ag-card '+(j3.length?'on':'')}>
    <div className="label-row"><Bot size={18}/><strong>Agente 3 · Vídeos com IA</strong><span className={'tag '+(rodando?'ok':'')}>{rodando?'Trabalhando':j3.length?'Na fila':'Parado'}</span></div>
    <p>Cria vídeos originais: escreve o roteiro, narra, busca fotos, monta no estilo escolhido e manda para você aprovar.</p>
    <small>{rodando?<>Agora: <b>{rodando.titulo?.slice(0,40)}</b> · {rodando.etapa} · {Math.round(rodando.progresso||0)}%<br/></>:null}{j3.length} na fila · {esp} esperando você</small>
    <div className="row-gap left">
      <button className="primary sm" onClick={()=>go('ia','','criar')}><Play size={13}/> Criar um vídeo</button>
      <button className="subtle sm" onClick={()=>go('automatico','','criar')}><CalendarClock size={13}/> Vários / rotina</button>
      {esp>0&&<button className="subtle sm" onClick={()=>go('fila')}>Aprovar ({esp})</button>}
    </div>
  </div>;
}

/** Aba do Agente 3: o que está na fila e os vídeos que ele já fez. */
function Agente3Aba(){
  const {go}=useApp();
  const fila=useServidor(c=>lerFila(c),10);
  const proj=useServidor(c=>listarProjetos(c,'agente3'),20);
  const cat=useServidor(catalogo);
  const j3=(fila.dados?.jobs||[]).filter(j=>j.agente==='agente3'&&['rodando','na_fila','agendado','aguardando_tentativa','aguardando_aprovacao'].includes(j.status));
  return <>
    <section className="panel">
      <h3>Fazendo agora e na fila ({j3.length})</h3>
      {j3.length?<ul className="ag-cortes">{j3.map(j=><li key={j.id} className="ag-corte"><div className="grow">
        <div className="label-row"><strong>{j.titulo||'Vídeo'}</strong><span className="tag">{j.status==='rodando'?'Fazendo':j.status==='agendado'?'Agendado':j.status==='aguardando_aprovacao'?'Esperando você':'Na fila'}</span></div>
        <small>{j.etapa}{j.status==='rodando'?` · ${Math.round(j.progresso||0)}%`:''}{j.status==='agendado'?` · começa ${horaTexto(j.run_at)}`:''}</small>
        {j.status==='rodando'&&<div className="progress"><span style={{width:`${Math.min(100,j.progresso||0)}%`}}/></div>}</div>
        {j.projeto&&<button className="subtle sm" onClick={()=>go('revisar',j.projeto,'fila')}><Eye size={14}/> Abrir</button>}</li>)}</ul>
      :<div className="empty"><strong>Nada na fila</strong><p>Toque em Criar um vídeo, no cartão do Agente 3 acima.</p></div>}
    </section>
    <section className="panel">
      <h3>Vídeos do Agente 3 ({proj.dados?.projetos.length||0})</h3>
      {(proj.dados?.projetos||[]).length?<ul className="ag-cortes">{proj.dados!.projetos.slice(0,40).map(p=><li key={p.id} className="ag-corte"><div className="grow">
        <div className="label-row"><strong>{p.titulo}</strong><span className="tag">{cat.dados?.estados[p.status]||p.status}</span></div><small>{horaTexto(p.atualizado)}</small></div>
        <button className="subtle sm" onClick={()=>go('revisar',p.id,'fila')}><Eye size={14}/> Ver</button></li>)}</ul>:<p className="hint">Nenhum vídeo ainda.</p>}
    </section>
  </>;
}

export default function Agente(){
  const {settings,toast,go,rotaExtra}=useApp();
  const PARTES:Parte[]=['cortes','postagem','agente3','desempenho','avisos','fila'];
  const [v,setV]=useState<VisaoAgente|null>(null); const [erro,setErro]=useState(''); const [parte,setParte]=useState<Parte>(()=>PARTES.includes(rotaExtra as Parte)?rotaExtra as Parte:'cortes');
  useEffect(()=>{ if(PARTES.includes(rotaExtra as Parte)) setParte(rotaExtra as Parte); },[rotaExtra]);   // eslint-disable-line react-hooks/exhaustive-deps
  const [link,setLink]=useState(''); const [tema,setTema]=useState(''); const [canalLink,setCanalLink]=useState(''); const [canalMotivo,setCanalMotivo]=useState('');
  const [chaves,setChaves]=useState({gemini:'',gemini_pago:'',youtube:'',email_senha:'',pexels:'',pixabay:'',callmebot:''}); const [hora,setHora]=useState('18:00'); const [diasSel,setDiasSel]=useState<number[]>([0,1,2,3,4,5]);
  const vivo=useRef(true);
  useEffect(()=>{ vivo.current=true; return ()=>{ vivo.current=false; }; },[]);
  const carregar=useCallback(()=>{ if(!settings.servidor) return; verAgente(settings).then(x=>{ if(vivo.current){ setV(x); setErro(''); } }).catch(e=>{ if(vivo.current) setErro(e.message); }); },[settings]);
  const ocupado=!!v?.atual.ocupado;
  useEffect(()=>{ carregar(); const t=setInterval(carregar,ocupado?3000:12000); return ()=>clearInterval(t); },[carregar,ocupado]);
  const run=async(f:()=>Promise<unknown>,ok?:string)=>{ try{ const r=await f(); if(r&&typeof r==='object'&&'config' in r) setV(r as VisaoAgente); else carregar(); if(ok) toast(ok,'ok'); }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); } };
  const salvar=(p:Parameters<typeof salvarAgente>[1])=>run(()=>salvarAgente(settings,p));

  if(!settings.servidor) return <section className="panel empty-state"><Bot size={34}/><strong>Os agentes rodam no seu servidor</strong><p>Ligue o servidor no celular ou no computador e conecte o aplicativo a ele. Depois volte aqui para configurar os agentes.</p><button className="primary" onClick={()=>go('config')}>Abrir Chaves e ajustes</button></section>;
  if(!v) return <section className="panel empty-state">{erro?<><AlertTriangle size={30}/><strong>Não consegui abrir os agentes</strong><p>{erro}</p><button className="subtle" onClick={carregar}><RefreshCw size={14}/> Tentar de novo</button></>:<><Loader2 size={26} className="spin"/><p>Falando com o servidor...</p></>}</section>;

  const c:ConfigAgente=v.config; const co=c.cortes, po=c.postagem, em=c.email, de=v.desempenho;
  const nomeModelo=(id:string)=>v.modelos.find(m=>m.id===id)?.nome||'Template apagado';
  const trocarModelo=(k:number,id:string)=>{ const n=[...v.ativos]; if(id) n[k]=id; else n.splice(k,1); const lista=[...new Set(n.filter(Boolean))]; if(!lista.length){ toast('Deixe pelo menos um template.','erro'); return; } salvar({cortes:{modelos:lista}}); };
  const aprovados=v.canais.filter(x=>x.status==='aprovado'); const sugeridos=v.canais.filter(x=>x.status==='sugerido'); const recusados=v.canais.filter(x=>x.status==='recusado');
  const zap=v.config.whatsapp||{ligado:false,numero:'',avisos:{} as Record<string,boolean>};
  const prontos=v.cortes.filter(x=>x.status==='pronto').length;
  const faltas:string[]=[];
  if(!v.ffmpeg) faltas.push('Falta o FFmpeg no servidor (no Termux: pkg install ffmpeg).');
  if(!v.chaves.youtube) faltas.push('Falta a chave do YouTube (parte Avisos e chaves).');
  if(!v.chaves.gemini&&!v.chaves.gemini_pago) faltas.push('Falta a chave do Gemini (parte Avisos e chaves).');
  if(!aprovados.length) faltas.push('Nenhum canal aprovado ainda (parte Cortes).');
  if(!em.para||!em.de||!v.chaves.email_senha) faltas.push('O e-mail de avisos não está completo (parte Avisos e chaves).');
  const escolherEstilo=(id:string)=>{ const at=co.estilos||[]; const tem=at.includes(id); if(!tem&&at.length>=6){ toast('Escolha no máximo 6 estilos.','erro'); return; } salvar({cortes:{estilos:tem?at.filter(x=>x!==id):[...at,id]}}); };
  const variar=(k:string)=>{ const tem=co.variar.includes(k); if(!tem&&co.variar.length>=3){ toast('Escolha no máximo 3 elementos para variar.','erro'); return; } salvar({cortes:{variar:tem?co.variar.filter(x=>x!==k):[...co.variar,k]}}); };
  const addFaixas=()=>{ if(!/^\d\d:\d\d$/.test(hora)||!diasSel.length) return; salvar({postagem:{faixas:[...po.faixas,...diasSel.map(d=>({dia:d,hora}))]}}); };
  const guardarChaves=(k:Partial<typeof chaves>)=>run(async()=>{ const r=await salvarChaves(settings,k); setChaves({gemini:'',gemini_pago:'',youtube:'',email_senha:'',pexels:'',pixabay:'',callmebot:''}); return r; },'Guardado no servidor.');

  return <div className="agente">
    <section className="panel ag-topo">
      <div className={'ag-card '+(co.ligado?'on':'')}>
        <div className="label-row"><Scissors size={18}/><strong>Agente 1 · Cortes</strong><span className={'tag '+(co.ligado?'ok':'')}>{co.ligado?'Ligado':'Desligado'}</span></div>
        <p>Procura canais, acha vídeos novos dos canais aprovados, corta, edita no seu template e manda cada corte por e-mail.</p>
        <small>Nesta semana: <b>{v.semana}</b> de {co.por_semana} cortes · {aprovados.length} canal(is) aprovado(s){sugeridos.length?` · ${sugeridos.length} esperando você`:''}</small>
        <div className="row-gap left">
          <button className={co.ligado?'subtle sm':'primary sm'} onClick={()=>salvar({cortes:{ligado:!co.ligado}})}>{co.ligado?<><Square size={13}/> Desligar</>:<><Play size={13}/> Ligar</>}</button>
          <button className="subtle sm" disabled={ocupado} onClick={()=>run(()=>rodarAgente(settings,'cortar'),'Começando a cortar. Acompanhe aqui.')}><Scissors size={13}/> Cortar agora</button>
          <button className="subtle sm" disabled={ocupado} onClick={()=>run(()=>rodarAgente(settings,'buscar'),'Procurando canais em alta.')}><Search size={13}/> Procurar canais</button>
        </div>
      </div>
      <div className={'ag-card '+(po.ligado?'on':'')}>
        <div className="label-row"><Send size={18}/><strong>Agente 2 · Postagem</strong><span className={'tag '+(po.ligado?'ok':'')}>{po.ligado?'Ligado':'Desligado'}</span></div>
        <p>Pega os cortes prontos, agenda nas redes nos horários escolhidos, avisa por e-mail e aprende os melhores horários.</p>
        <small>{prontos} corte(s) pronto(s) na fila · {v.cortes.filter(x=>x.status==='agendado').length} agendado(s)</small>
        <div className="row-gap left">
          <button className={po.ligado?'subtle sm':'primary sm'} onClick={()=>salvar({postagem:{ligado:!po.ligado}})}>{po.ligado?<><Square size={13}/> Desligar</>:<><Play size={13}/> Ligar</>}</button>
          <button className="subtle sm" disabled={ocupado||!prontos} onClick={()=>run(()=>rodarAgente(settings,'postar'),'Agendando os cortes prontos.')}><CalendarClock size={13}/> Agendar prontos agora</button>
        </div>
      </div>
      <Agente3Cartao/>
      <div className="ag-geral">
        {v.atual.etapa?<div className="ag-etapa" role="status"><Loader2 size={15} className="spin"/> <span>{v.atual.etapa}</span><div className="barra"><i style={{width:Math.max(4,v.atual.pct)+'%'}}/></div></div>:<span className="muted">{co.ligado||po.ligado?'Agentes 1 e 2 esperando a próxima tarefa.':'Os agentes 1 e 2 estão parados.'}</span>}
        <button className="danger sm" onClick={()=>{ if(confirm('Parar os agentes 1 e 2 e tirar da agenda os posts que eles marcaram? (O Agente 3 se pausa na Fila.)')) run(()=>pararAgente(settings),'Tudo parado.'); }}><Square size={13}/> Parar agentes 1 e 2</button>
      </div>
      {faltas.length>0&&<ul className="ag-faltas">{faltas.map(f=><li key={f}><AlertTriangle size={13}/> {f}</li>)}</ul>}
      {erro&&<p className="hint bad"><AlertTriangle size={13}/> {erro}</p>}
    </section>

    <div className="ag-abas" role="tablist">{([['cortes','1 · Cortes'],['postagem','2 · Postagem'],['agente3','3 · Vídeos com IA'],['desempenho','Desempenho'],['avisos','Avisos e chaves'],['fila',`Cortes feitos e histórico${v.cortes.length?` (${v.cortes.length})`:''}`]] as [Parte,string][]).map(([k,t])=><button key={k} role="tab" aria-selected={parte===k} className={parte===k?'active':''} onClick={()=>setParte(k)}>{t}</button>)}</div>

    {parte==='agente3'&&<Agente3Aba/>}

    {parte==='cortes'&&<>
      <section className="panel">
        <h3>Canais</h3>
        <p className="hint tight">O agente só corta canais aprovados por você, com o motivo marcado.</p>
        {sugeridos.length>0&&<><span className="field-label">Sugeridos pelo agente ({sugeridos.length})</span><ul className="ag-canais">{sugeridos.map(x=><CanalLinha key={x.id} c={x} fazer={d=>run(()=>acaoCanal(settings,d))}/>)}</ul></>}
        <span className="field-label">Aprovados ({aprovados.length})</span>
        {aprovados.length?<ul className="ag-canais">{aprovados.map(x=><CanalLinha key={x.id} c={x} fazer={d=>run(()=>acaoCanal(settings,d))}/>)}</ul>:<p className="hint">Nenhum ainda. Aprove um sugerido, toque em Procurar canais ou cole o link de um canal abaixo.</p>}
        <div className="ag-add mt"><input value={canalLink} onChange={e=>setCanalLink(e.target.value)} placeholder="Link do canal: youtube.com/@nome"/>
          <select value={canalMotivo} onChange={e=>setCanalMotivo(e.target.value)} aria-label="Motivo"><option value="">Só adicionar à lista</option>{Object.entries(MOTIVOS).map(([k,t])=><option key={k} value={k}>Aprovar: {t}</option>)}</select>
          <button className="subtle sm" disabled={!canalLink.trim()} onClick={()=>run(async()=>{ const r=await acaoCanal(settings,{acao:'adicionar',link:canalLink,motivo:canalMotivo||undefined}); setCanalLink(''); return r; },'Canal adicionado.')}><Plus size={14}/> Adicionar canal</button></div>
        {recusados.length>0&&<details className="mt"><summary>Recusados ({recusados.length})</summary><ul className="ag-canais">{recusados.map(x=><CanalLinha key={x.id} c={x} fazer={d=>run(()=>acaoCanal(settings,d))}/>)}</ul></details>}
      </section>
      <section className="panel">
        <h3>O que procurar</h3>
        <div className="mt"><b>Temas específicos</b>
          <p className="hint">Quer vídeos só sobre um assunto? Escreva o tema (ex.: <i>Elden Ring</i>, <i>futebol</i>). Com temas, o agente só corta vídeos que falam deles, em vez de pegar o mais visto de qualquer assunto.</p>
          <Lista titulo="" escolhidos={co.temas||[]} sugestoes={[]} mudar={l=>salvar({cortes:{temas:l}})} placeholder="Escreva um tema e toque em adicionar"/>
          <label className="check mt"><input type="checkbox" checked={!!co.temas_outros} onChange={e=>salvar({cortes:{temas_outros:e.target.checked}})}/> Procurar também em outros canais do YouTube (não só nos aprovados)</label>
          <p className="hint">Vídeo de canal que você não aprovou fica sem origem registrada: ele passa pelo diretor de qualidade, mas só posta depois da sua liberação especial.</p>
          <div className="ag-add"><input value={tema} onChange={e=>setTema(e.target.value)} placeholder="Cortar agora um vídeo sobre... (só desta vez)"/><button className="subtle sm" disabled={ocupado||tema.trim().length<3} onClick={()=>run(async()=>{ await rodarAgente(settings,'tema',tema.trim()); setTema(''); setParte('fila'); },'Procurando um vídeo sobre esse tema. O resultado aparece na fila.')}><Search size={14}/> Procurar e cortar</button></div>
        </div>
        <Lista titulo="Nichos" escolhidos={co.nichos} sugestoes={v.opcoes.nichos} mudar={l=>salvar({cortes:{nichos:l}})} placeholder="Outro nicho"/>
        <div className="ag-grade">
          <label>Idioma dos canais<select value={co.idioma} onChange={e=>salvar({cortes:{idioma:e.target.value}})}>{Object.entries(v.opcoes.idiomas||{pt:'Português'}).map(([k,t])=><option key={k} value={k}>{t}</option>)}</select></label>
          <label>País dos canais<select value={co.regiao} onChange={e=>salvar({cortes:{regiao:e.target.value}})}>{Object.entries(v.opcoes.paises||{BR:'Brasil'}).map(([k,t])=><option key={k} value={k}>{t}</option>)}</select></label>
          <label>Média mínima de visualizações na semana<Campo tipo="number" min={0} step={50000} valor={co.min_views} salvar={x=>salvar({cortes:{min_views:+x}})}/></label>
          <label>Vídeos de até quantos dias atrás<Campo tipo="number" min={1} max={90} valor={co.dias_video} salvar={x=>salvar({cortes:{dias_video:+x}})}/></label>
          <label>Vídeo original: tamanho mínimo, em MINUTOS (não é o corte)<Campo tipo="number" min={1} valor={co.video_min} salvar={x=>salvar({cortes:{video_min:+x}})}/></label>
          <label>Vídeo original: tamanho máximo, em MINUTOS (não é o corte)<Campo tipo="number" min={2} valor={co.video_max} salvar={x=>salvar({cortes:{video_max:+x}})}/></label>
        </div>
        <p className="hint">O idioma vale para a busca de canais, para a leitura da fala e para a legenda dos cortes. O YouTube trata o idioma como preferência: confira o canal antes de aprovar.</p>
        <Lista titulo="Nunca postar (assuntos e palavras proibidas)" escolhidos={co.proibidos} sugestoes={v.opcoes.proibidos} mudar={l=>salvar({cortes:{proibidos:l}})} placeholder="Outra palavra ou assunto"/>
      </section>
      <section className="panel">
        <h3>Quantidade e tamanho</h3>
        <div className="ag-grade">
          <label>Cortes por semana<Campo tipo="number" min={1} max={21} valor={co.por_semana} salvar={x=>salvar({cortes:{por_semana:+x}})}/></label>
          <label>Cortes por vídeo<Campo tipo="number" min={1} max={6} valor={co.por_video} salvar={x=>salvar({cortes:{por_video:+x}})}/></label>
          <label>Cada corte dura no mínimo (em SEGUNDOS){' '}<small className="muted">= {tempo(co.dur_min)}</small><Campo tipo="number" min={10} max={175} valor={co.dur_min} salvar={x=>salvar({cortes:{dur_min:+x}})}/></label>
          <label>Cada corte dura no máximo (em SEGUNDOS){' '}<small className="muted">= {tempo(co.dur_max)}</small><Campo tipo="number" min={15} max={180} valor={co.dur_max} salvar={x=>salvar({cortes:{dur_max:+x}})}/></label>
          <label>Pontuação mínima (0 a 99)<Campo tipo="number" min={0} max={99} valor={co.nota_min} salvar={x=>salvar({cortes:{nota_min:+x}})}/></label>
          <label>Trabalhar das (hora)<Campo tipo="number" min={0} max={23} valor={co.hora_ini} salvar={x=>salvar({cortes:{hora_ini:+x}})}/></label>
          <label>até as (hora)<Campo tipo="number" min={1} max={24} valor={co.hora_fim} salvar={x=>salvar({cortes:{hora_fim:+x}})}/></label>
        </div>
        <p className="hint">Montar vídeo pesa no celular. Se ele esquenta de dia, deixe o agente trabalhar só de madrugada, por exemplo das 0 às 6.</p>
      </section>
      <section className="panel">
        <h3>Templates dos cortes</h3>
        <p className="hint">O agente sorteia um destes templates para cada corte. São os mesmos da aba <button className="link-btn" onClick={()=>go('templates')}>Templates</button>, onde você cria e edita cada um.</p>
        <div className="ag-grade">
          {[0,1,2].map(k=><label key={k}>Template {k+1}{v.ativos[k]&&<small className="muted"> · chance de {Math.round((de.chances[v.ativos[k]]||0)*100)}%</small>}
            <select value={v.ativos[k]||''} onChange={e=>trocarModelo(k,e.target.value)} aria-label={'Template '+(k+1)+' do agente'}>
              {k>0&&<option value="">Nenhum</option>}
              {v.modelos.map(m=><option key={m.id} value={m.id} disabled={v.ativos.includes(m.id)&&v.ativos[k]!==m.id}>{m.nome}</option>)}
            </select></label>)}
        </div>
        <label className="check mt"><input type="checkbox" checked={co.aprender} onChange={e=>salvar({cortes:{aprender:e.target.checked}})}/> Aprender sozinho: dar mais chance aos templates que rendem mais em cada rede</label>
        <p className="hint">No começo as chances são iguais. Nenhum template cai abaixo de 15%, para manter variedade. Veja os números na parte Desempenho.</p>
        <span className="field-label mt">Estilos visuais (opcional)</span>
        <div className="chips">{ESTILOS.map(e=><button key={e.id} type="button" className={'chip '+((co.estilos||[]).includes(e.id)?'on':'')} aria-pressed={(co.estilos||[]).includes(e.id)} title={e.desc} onClick={()=>escolherEstilo(e.id)}>{e.nome}</button>)}</div>
        <small className="hint">{(co.estilos||[]).length?'Cada corte sorteia um destes estilos (o que o FFmpeg do celular não souber fazer fica de fora e o histórico avisa). Um template com estilo próprio sempre vale.':'Sem escolha, os cortes saem só com o estilo do template.'}</small>
        <span className="field-label mt">O que pode variar de um corte para outro (até 3)</span>
        <div className="chips">{Object.entries(v.opcoes.variacoes).map(([k,t])=><button key={k} type="button" className={'chip '+(co.variar.includes(k)?'on':'')} aria-pressed={co.variar.includes(k)} onClick={()=>variar(k)}>{t}</button>)}</div>
        <p className="hint">Além do template, o agente sorteia esses elementos em cada corte para os vídeos não saírem todos iguais.</p>
        <div className="ag-add mt"><input value={link} onChange={e=>setLink(e.target.value)} placeholder="Testar o template: cole o link de um vídeo do YouTube"/><button className="subtle sm" disabled={ocupado||!link.trim()} onClick={()=>run(async()=>{ await rodarAgente(settings,'link',link.trim()); setLink(''); setParte('fila'); },'Cortando este vídeo. O resultado aparece na fila.')}><Link2 size={14}/> Cortar este link</button></div>
      </section>
    </>}

    {parte==='postagem'&&<>
      <section className="panel">
        <h3>Redes</h3>
        <div className="chips">{REDES.map(r=><button key={r.id} type="button" className={'chip '+(po.redes.includes(r.id)?'on':'')} aria-pressed={po.redes.includes(r.id)} onClick={()=>salvar({postagem:{redes:po.redes.includes(r.id)?po.redes.filter(x=>x!==r.id):[...po.redes,r.id]}})}>{r.nome}</button>)}</div>
        <p className="hint">Cada corte vai para todas as redes marcadas. As contas são as mesmas da aba Agendar posts. <button className="link-btn" onClick={()=>go('agendar')}>Conferir conexões</button></p>
        <div className="ag-grade">
          <label>YouTube chega como<select value={po.youtube_privacidade} onChange={e=>salvar({postagem:{youtube_privacidade:e.target.value}})}><option value="private">Privado (você deixa público no aplicativo)</option><option value="unlisted">Não listado</option><option value="public">Público</option></select></label>
          <label>TikTok chega como<select value={po.tiktok_modo} onChange={e=>salvar({postagem:{tiktok_modo:e.target.value}})}><option value="rascunho">Rascunho (você publica no aplicativo)</option><option value="direto">Direto no perfil</option></select></label>
        </div>
        <p className="hint">Instagram e Facebook saem públicos direto. O Kwai não aceita postagem automática: o corte chega no seu e-mail para você postar à mão.</p>
      </section>
      <section className="panel">
        <h3>Horários</h3>
        <p className="hint tight">Marque todos os horários que servem para você. O agente usa {co.por_semana} por semana: primeiro testa cada um, depois fica com os que renderam mais visualizações no YouTube.</p>
        <div className="ag-add"><input type="time" value={hora} onChange={e=>setHora(e.target.value)} aria-label="Horário"/>
          <div className="chips ag-dias">{DIAS.map((d,i)=><button key={d} type="button" className={'chip '+(diasSel.includes(i)?'on':'')} aria-pressed={diasSel.includes(i)} onClick={()=>setDiasSel(s=>s.includes(i)?s.filter(x=>x!==i):[...s,i])}>{d.slice(0,3)}</button>)}</div>
          <button className="subtle sm" onClick={addFaixas}><Plus size={14}/> Adicionar horário</button></div>
        <ul className="ag-faixas">{DIAS.map((d,i)=>{ const fs=po.faixas.filter(f=>f.dia===i).sort((a,b)=>a.hora.localeCompare(b.hora)); return <li key={d}><b>{d}</b><div className="chips">{fs.length?fs.map(f=>{ const h=v.horarios[`${f.dia}-${f.hora}`]; return <span key={f.hora} className="chip on"><Clock size={12}/> {f.hora}{h&&h.n>0?` · média ${num(Math.round(h.views/h.n))}`:''}<button aria-label={`Tirar ${d} ${f.hora}`} onClick={()=>salvar({postagem:{faixas:po.faixas.filter(x=>!(x.dia===f.dia&&x.hora===f.hora))}})}><X size={12}/></button></span>; }):<small className="muted">sem horário</small>}</div></li>; })}</ul>
        {po.faixas.length<co.por_semana&&<p className="hint warn"><AlertTriangle size={13}/> Há {po.faixas.length} horário(s) por semana para {co.por_semana} cortes. Marque mais horários ou os cortes vão acumular na fila.</p>}
      </section>
    </>}

    {parte==='desempenho'&&<>
      <section className="panel">
        <h3>Templates: uso e resultado</h3>
        <p className="hint">Conta os cortes dos agentes e os que você mandou da edição manual. Os números das redes são lidos dois dias depois de cada post. {de.medidos} medição(ões) até agora.</p>
        <div className="ag-tabela-rol"><table className="ag-tabela">
          <thead><tr><th>Template</th><th>Cortes</th><th>Postados</th>{po.redes.filter(r=>r!=='kwai').map(r=><th key={r}>{REDES.find(x=>x.id===r)?.nome||r}</th>)}</tr></thead>
          <tbody>{de.modelos.map(m=><tr key={m.id}>
            <td><b>{m.nome}</b>{m.ativo?<span className="tag ok">nos agentes · {Math.round((de.chances[m.id]||0)*100)}%</span>:<span className="tag">só manual</span>}</td>
            <td>{m.cortes}{m.manuais?<small className="muted"> ({m.manuais} manuais)</small>:null}</td><td>{m.postados}</td>
            {po.redes.filter(r=>r!=='kwai').map(r=>{ const x=m.redes[r]; return <td key={r}>{!x?<span className="muted">sem dados</span>:<>
              {x.com_views?<><b>{num(Math.round(x.views/x.com_views))}</b> visualizações por vídeo</>:<span className="muted">visualizações indisponíveis</span>}
              {x.com_eng?<small className="muted"> · {num(Math.round((x.curtidas+x.comentarios)/x.com_eng))} curtidas e comentários por vídeo</small>:null}
              <small className="muted"> · {x.n} vídeo(s)</small></>}</td>; })}
          </tr>)}</tbody>
        </table></div>
        {de.sem_modelo.cortes>0&&<p className="hint">{de.sem_modelo.cortes} corte(s) sem template registrado (feitos antes desta versão ou enviados sem template).</p>}
        <p className="hint"><AlertTriangle size={13}/> {de.indisponivel}</p>
      </section>
      <section className="panel">
        <h3>Pesos por rede</h3>
        <p className="hint">A chance no sorteio é a média dos pesos nas redes ligadas. O aprendizado só mexe em uma rede quando todos os templates ativos têm pelo menos 2 vídeos medidos nela. Escolher um template na edição manual não muda os pesos.</p>
        <label className="check"><input type="checkbox" checked={co.aprender} onChange={e=>salvar({cortes:{aprender:e.target.checked}})}/> Aprendizado automático ligado</label>
        <div className="ag-tabela-rol"><table className="ag-tabela">
          <thead><tr><th>Rede</th>{v.ativos.map(id=><th key={id}>{nomeModelo(id)}</th>)}<th></th></tr></thead>
          <tbody>{po.redes.filter(r=>r!=='kwai').map(r=><PesosRede key={r+JSON.stringify(de.pesos[r])} rede={r} nome={REDES.find(x=>x.id===r)?.nome||r} ids={v.ativos} pesos={de.pesos[r]||{}} definido={de.definidos.includes(r)} guardar={p=>run(()=>salvarPesos(settings,{rede:r,pesos:p}),'Pesos guardados.')}/>)}</tbody>
        </table></div>
        <div className="row-gap left mt">
          <button className="subtle sm" onClick={()=>run(async()=>{ const r=await aprenderAgora(settings); toast(r.redes.length?'Pesos ajustados em: '+r.redes.join(', ')+'.':'Ainda não há vídeos medidos suficientes para ajustar.','info'); return r; })}><RefreshCw size={13}/> Ajustar agora pelos resultados</button>
          <button className="subtle sm" onClick={()=>{ if(confirm('Voltar todos os templates a chances iguais?')) run(()=>salvarPesos(settings,{zerar:true}),'Chances iguais de novo.'); }}>Voltar a chances iguais</button>
        </div>
      </section>
      <section className="panel">
        <h3>Publicações por rede</h3>
        <div className="ag-tabela-rol"><table className="ag-tabela">
          <thead><tr><th>Rede</th><th>Na fila</th><th>Publicados</th><th>Com erro</th></tr></thead>
          <tbody>{REDES.map(r=>{ const f=de.filas[r.id]; if(!f) return null; return <tr key={r.id}><td><b>{r.nome}</b></td><td>{f.fila}{f.manual?<small className="muted"> · {f.manual} para postar à mão</small>:null}</td><td>{f.postados}</td><td>{f.erros?<span className="hint bad">{f.erros} · {f.ultimo_erro}</span>:0}</td></tr>; })}</tbody>
        </table></div>
        <p className="hint">Cada rede tem a sua fila: se uma falha, as outras seguem. Falhas passageiras são tentadas de novo sozinhas. O mesmo arquivo não é postado duas vezes na mesma rede. Para tentar de novo um erro, abra <button className="link-btn" onClick={()=>go('agendar')}>Agendar posts</button>.</p>
        {Object.keys(de.canais).length>0&&<><h3 className="mt">Por canal de origem</h3><ul className="ag-log">{Object.entries(de.canais).sort((a,b)=>b[1].views-a[1].views).map(([n,x])=><li key={n}><span><b>{n}</b>: {x.n} medição(ões), {num(x.views)} visualizações somadas</span></li>)}</ul></>}
      </section>
    </>}

    {parte==='avisos'&&<>
      <section className="panel">
        <h3>Avisos por e-mail</h3>
        <div className="ag-grade">
          <label>E-mail que recebe os avisos<Campo tipo="email" valor={em.para} placeholder="voce@exemplo.com" salvar={x=>salvar({email:{para:x.trim()}})}/></label>
          <label>E-mail que envia<Campo tipo="email" valor={em.de} placeholder="pode ser o mesmo" salvar={x=>salvar({email:{de:x.trim()}})}/></label>
          <label>Senha de aplicativo do e-mail que envia {v.chaves.email_senha&&<span className="tag ok">guardada</span>}<input type="password" autoComplete="off" value={chaves.email_senha} onChange={e=>setChaves(s=>({...s,email_senha:e.target.value}))} placeholder={v.chaves.email_senha?'Digite só para trocar':'16 letras, sem espaços'}/></label>
          <div className="row-gap left"><button className="primary sm" disabled={!chaves.email_senha.trim()} onClick={()=>guardarChaves({email_senha:chaves.email_senha.replace(/\s+/g,'')})}><KeyRound size={14}/> Guardar senha</button>
            <button className="subtle sm" onClick={()=>run(()=>testarEmail(settings),'E-mail de teste enviado. Confira a caixa de entrada.')}><Mail size={14}/> Enviar e-mail de teste</button></div>
        </div>
        <p className="hint">Não é a senha normal da conta. No Gmail: Conta Google &gt; Segurança &gt; Verificação em duas etapas &gt; Senhas de app. Ela fica guardada só no servidor e nunca volta para esta tela.</p>
        <span className="field-label mt">Quais avisos mandar</span>
        <div className="chips">{([['corte','Corte pronto (com o vídeo)'],['agendado','Post agendado'],['postado','Post enviado'],['falha','Falhas'],['canal','Canais novos sugeridos'],['semana','Resumo da semana']] as [string,string][]).map(([k,t])=><button key={k} type="button" className={'chip '+(em.avisos[k]?'on':'')} aria-pressed={!!em.avisos[k]} onClick={()=>salvar({email:{avisos:{[k]:!em.avisos[k]}}})}>{t}</button>)}</div>
        <label className="check mt"><input type="checkbox" checked={em.anexar} onChange={e=>salvar({email:{anexar:e.target.checked}})}/> Anexar o vídeo do corte no e-mail</label>
        <p className="hint">E-mail tem limite de anexo. Quando o corte passa do limite, o agente anexa uma cópia menor e deixa a versão completa na fila daqui.</p>
        <details className="mt"><summary>Outro provedor de e-mail</summary><div className="ag-grade mt">
          <label>Servidor SMTP<Campo valor={em.smtp} placeholder="Vazio = descobrir pelo e-mail" salvar={x=>salvar({email:{smtp:x.trim()}})}/></label>
          <label>Porta<Campo tipo="number" valor={em.porta} salvar={x=>salvar({email:{porta:+x}})}/></label></div></details>
      </section>
      <section className="panel">
        <h3>Avisos e aprovação pelo WhatsApp</h3>
        <p className="subtitle">O servidor manda para o seu WhatsApp os mesmos avisos do e-mail, em texto curto e com o link. Quando um vídeo passa pelo diretor de qualidade, chega a mensagem com o link da revisão: você assiste e dá a aprovação final com um toque no site.</p>
        <div className={'hint '+(v.whatsapp_ponte?'ok':'')}>{v.whatsapp_ponte?<><CheckCircle2 size={13}/> <b>Seu WhatsApp está ligado ao servidor.</b> Na conversa com você mesmo, mande <b>ajuda</b>, <b>pendentes</b>, <b>aprovar VID-…</b>, <b>corrigir VID-… o que mudar</b>, <b>agendar corte 2</b> ou escreva do seu jeito. O que publica pede um SIM.</>:<>Para <b>mandar comandos</b> pelo WhatsApp (aprovar, corrigir, agendar, cortar um link), ligue o seu WhatsApp no Termux, uma vez: <code>bash iniciar-termux.sh whatsapp 55DDDNUMERO</code>. Aparece um código: no WhatsApp, Aparelhos conectados &gt; Conectar com número de telefone. Os comandos e avisos ficam na conversa com você mesmo.</>}</div>
        <label className="check mt"><input type="checkbox" checked={!!zap.ligado} onChange={e=>salvar({whatsapp:{ligado:e.target.checked}})}/> Mandar avisos pelo WhatsApp (sem a ligação acima, usa o CallMeBot abaixo)</label>
        <div className="ag-grade mt">
          <label>Seu número com DDI e DDD<Campo valor={zap.numero} placeholder="55 11 91234-5678" salvar={x=>salvar({whatsapp:{numero:x}})}/></label>
          <label>Chave do CallMeBot (apikey) {v.chaves.callmebot&&<span className="tag ok">guardada</span>}<input type="password" autoComplete="off" value={chaves.callmebot} onChange={e=>setChaves(s=>({...s,callmebot:e.target.value}))} placeholder={v.chaves.callmebot?'Digite só para trocar':'o número que o robô respondeu'}/></label>
          <div className="row-gap left"><button className="primary sm" disabled={!chaves.callmebot.trim()} onClick={()=>guardarChaves({callmebot:chaves.callmebot.trim()})}><KeyRound size={14}/> Guardar chave</button>
            <button className="subtle sm" onClick={()=>run(()=>testarWhatsapp(settings),'Mensagem de teste enviada. Confira o WhatsApp.')}><Send size={14}/> Mandar mensagem de teste</button></div>
        </div>
        <details className="mt"><summary>Como pegar a chave (uma vez só, grátis)</summary><ol className="hint">
          <li>Abra <a href="https://www.callmebot.com/blog/free-api-whatsapp-messages/" target="_blank" rel="noreferrer">a página do CallMeBot</a> e salve nos contatos o número do robô que aparece lá.</li>
          <li>No WhatsApp, mande para esse contato: <b>I allow callmebot to send me messages</b></li>
          <li>Ele responde com a sua <b>apikey</b>. Cole aqui, guarde e toque em Mandar mensagem de teste.</li>
        </ol><p className="hint">O CallMeBot é um serviço de fora: o texto do aviso passa por ele. Por isso a mensagem leva só o título, o resumo e o link, nunca senha, código de aprovação ou o vídeo.</p></details>
        <span className="field-label mt">O que cada agente manda para o seu WhatsApp</span>
        {([
          ['Agente 1 · Cortes do Radar',[['a1_corte','Corte aprovado pelo diretor, esperando você'],['a1_reprovado','Corte reprovado pelo diretor'],['a1_canal','Canais novos sugeridos'],['a1_falha','Vídeo que não deu para cortar']]],
          ['Agente 2 · Postagem',[['a2_liberacao','Post esperando a sua liberação'],['a2_falha','Post que falhou'],['a2_postado','Post enviado'],['a2_agendado','Post agendado'],['a2_semana','Resumo da semana']]],
          ['Agente 3 · Vídeos com IA',[['a3_roteiro','Roteiro pronto para conferir'],['a3_aprovacao','Vídeo aprovado pelo diretor, esperando você'],['a3_refazendo','Diretor mandou refazer'],['a3_falha','Produção que parou']]],
        ] as [string,[string,string][]][]).map(([nome,itens])=><div key={nome} className="mt"><b>{nome}</b>
          <div className="chips">{itens.map(([k,t])=><button key={k} type="button" className={'chip '+(zap.avisos[k]?'on':'')} aria-pressed={!!zap.avisos[k]} onClick={()=>salvar({whatsapp:{avisos:{[k]:!zap.avisos[k]}}})}>{t}</button>)}</div></div>)}
        <p className="hint">Os pedidos de aprovação (corte e vídeo) trazem o código para você responder ali mesmo: <b>aprovar VID-…</b> ou <b>agendar corte 2</b>. Os avisos do e-mail continuam com as escolhas da parte de e-mail.</p>
      </section>
      <section className="panel">
        <h3>Chaves do Gemini: grátis e com saldo</h3>
        <p className="subtitle">Guarde as duas e escolha abaixo qual cada tarefa usa. A <b>grátis</b> vem de um projeto do Google sem cobrança (tem limite por minuto e por dia). A <b>com saldo</b> vem de um projeto com cobrança ligada (sem esse limite, mas gasta). As chaves ficam só no servidor e não voltam para esta tela.</p>
        <div className="ag-grade">
          <label>Chave grátis {v.chaves.gemini&&<span className="tag ok">guardada</span>}<input type="password" autoComplete="off" value={chaves.gemini} onChange={e=>setChaves(s=>({...s,gemini:e.target.value}))} placeholder={v.chaves.gemini?'Digite só para trocar':'Cole a chave (projeto sem cobrança)'}/></label>
          <label>Chave com saldo {v.chaves.gemini_pago&&<span className="tag ok">guardada</span>}<input type="password" autoComplete="off" value={chaves.gemini_pago} onChange={e=>setChaves(s=>({...s,gemini_pago:e.target.value}))} placeholder={v.chaves.gemini_pago?'Digite só para trocar':'Cole a chave (projeto com cobrança)'}/></label>
        </div>
        <div className="row-gap left mt"><button className="primary sm" disabled={!chaves.gemini.trim()&&!chaves.gemini_pago.trim()} onClick={()=>guardarChaves({...(chaves.gemini.trim()?{gemini:chaves.gemini.trim()}:{}),...(chaves.gemini_pago.trim()?{gemini_pago:chaves.gemini_pago.trim()}:{})})}><KeyRound size={14}/> Guardar chaves do Gemini</button>
          <a className="link-btn" href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">Criar chaves no Google AI Studio <ExternalLink size={12}/></a></div>
        <span className="field-label mt">Qual chave cada tarefa usa</span>
        <div className="usos-chave">{([['cortes','Agente 1: ouvir o vídeo e escolher os cortes'],['camera','Agente 1: achar a câmera do streamer'],['roteiro','Agente 3: assuntos e roteiros'],['voz','Agente 3: narração'],['imagens','Agente 3: imagens criadas por IA']] as [keyof ConfigAgente['chaves_uso'],string][]).map(([k,t])=>{ const atual=c.chaves_uso[k] as Uso;
          return <div key={k} className="uso-linha"><span>{t}</span><div className="seg">{(['gratis','paga'] as Uso[]).map(u=><button key={u} type="button" className={atual===u?'on':''} aria-pressed={atual===u} onClick={()=>salvar({chaves_uso:{[k]:u}})}>{u==='gratis'?'Grátis':'Com saldo'}</button>)}</div>
            {!(atual==='gratis'?v.chaves.gemini:v.chaves.gemini_pago)&&<small className="bad">falta esta chave</small>}</div>; })}</div>
        <label className="check mt"><input type="checkbox" checked={c.chaves_uso.reserva} onChange={e=>salvar({chaves_uso:{reserva:e.target.checked}})}/> Se a chave escolhida estiver sem cota ou sem saldo, usar a outra</label>
        <p className="hint">Sugestão: deixe tudo na grátis e só as imagens na com saldo. Com a reserva ligada, quando a grátis bate o limite do dia, o trabalho continua na com saldo (e passa a gastar). O teto de gasto abaixo vale só para a chave com saldo.</p>
      </section>
      <section className="panel">
        <h3>Outras chaves dos agentes</h3>
        <div className="ag-grade">
          <label>Chave do Pexels (fotos grátis para os vídeos) {v.chaves.pexels&&<span className="tag ok">guardada</span>}<input type="password" autoComplete="off" value={chaves.pexels} onChange={e=>setChaves(s=>({...s,pexels:e.target.value}))} placeholder={v.chaves.pexels?'Digite só para trocar':'Opcional: pexels.com/api'}/></label>
          <label>Chave do Pixabay (fotos grátis, chave na hora) {v.chaves.pixabay&&<span className="tag ok">guardada</span>}<input type="password" autoComplete="off" value={chaves.pixabay} onChange={e=>setChaves(s=>({...s,pixabay:e.target.value}))} placeholder={v.chaves.pixabay?'Digite só para trocar':'Opcional: pixabay.com/api/docs'}/></label>
          <label>Chave do YouTube {v.chaves.youtube&&<span className="tag ok">guardada</span>}<input type="password" autoComplete="off" value={chaves.youtube} onChange={e=>setChaves(s=>({...s,youtube:e.target.value}))} placeholder={v.chaves.youtube?'Digite só para trocar':'Cole a chave'}/></label>
        </div>
        <div className="row-gap left mt">
          <button className="primary sm" disabled={!chaves.youtube.trim()&&!chaves.pexels.trim()&&!chaves.pixabay.trim()} onClick={()=>guardarChaves({...(chaves.pexels.trim()?{pexels:chaves.pexels.trim()}:{}),...(chaves.pixabay.trim()?{pixabay:chaves.pixabay.trim()}:{}),...(chaves.youtube.trim()?{youtube:chaves.youtube.trim()}:{})})}><KeyRound size={14}/> Guardar</button>
          {settings.ytKey&&!v.chaves.youtube&&<button className="subtle sm" onClick={()=>guardarChaves({youtube:settings.ytKey})}>Usar a chave do YouTube deste aparelho</button>}
        </div>
      </section>
      <section className="panel">
        <h3>Orçamento da IA</h3>
        <div className="ag-grade">
          <label>Teto por mês da chave com saldo (R$)<Campo tipo="number" min={0} step={1} valor={c.orcamento.teto} salvar={x=>salvar({orcamento:{teto:+x}})}/></label>
          <div className="ag-gasto"><span>Gasto estimado neste mês</span><b>R$ {v.gasto.reais.toFixed(2).replace('.',',')}</b><small>{v.gasto.chamadas} pedido(s) à IA</small></div>
        </div>
        <p className="hint">Ao chegar no teto o agente para de usar a IA até o mês virar. O valor é uma estimativa feita pelo servidor; o valor cobrado de verdade aparece na sua conta do Google. Quando o vídeo tem legenda automática do YouTube, o agente usa a legenda e gasta bem menos.</p>
      </section>
    </>}

    {parte==='fila'&&<>
      <section className="panel">
        <h3>Cortes feitos pelo agente</h3>
        {v.cortes.length?<ul className="ag-cortes">{v.cortes.map(x=><CorteLinha key={x.id} c={x} fazer={a=>{ if(a==='descartar'&&!confirm('Descartar este corte? O arquivo é apagado do servidor.')) return; if(a==='liberar'&&!confirm('Liberar e agendar mesmo com estas restrições?\n\n'+(x.conferencia?.liberaveis||[]).join('\n')+'\n\nA decisão e a responsabilidade são suas. Fica registrado no corte e no post.')) return; run(()=>acaoCorte(settings,x.id,a),a==='email'?'E-mail enviado.':a==='agendar'?'Corte aprovado por você e agendado.':a==='liberar'?'Corte liberado por você (com as restrições registradas) e agendado.':'Corte descartado.'); }}/>)}</ul>:<div className="empty"><strong>Nenhum corte ainda</strong><p>Aprove um canal e toque em Cortar agora, ou cole o link de um vídeo na parte Cortes.</p></div>}
      </section>
      <section className="panel">
        <h3>Histórico</h3>
        {v.log.length?<ul className="ag-log">{v.log.map((l,i)=><li key={i} className={l.tipo}><time>{quando(l.t)}</time><span>{l.texto}</span></li>)}</ul>:<p className="hint">Nada aconteceu ainda.</p>}
      </section>
    </>}
  </div>;
}
