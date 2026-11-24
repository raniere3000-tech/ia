import { useCallback, useEffect, useRef, useState } from 'react';
import { ShieldCheck, Youtube, Instagram, Music2, CalendarClock, LogIn, LogOut, Loader2, Server, Copy, ExternalLink, Download, Send, Trash2, RefreshCw, Upload, CheckCircle2, AlertTriangle, Clock, Hand, Pencil, X, ChevronDown } from 'lucide-react';
import { useApp } from '../state';
import { HelpButton } from '../components/Help';
import AgendarPost from '../components/AgendarPost';
import AgendarLote from '../components/AgendarLote';
import { FILTROS_POST, filtrarPosts, filtrarTikTok, horaDaRede, type FiltroPost } from '../lib/filtrosPosts';
import ConferenciaPost from '../components/ConferenciaPost';
import TikTokInfoPainel from '../components/TikTokInfo';
import { ESTADOS_TIKTOK, type EstadoTikTok, REDES, lerContas, verificarContas, salvarApp, entrar, sair, escolherPagina, listarPosts, postarAgora, editarPost, publicarEmOutrasRedes, cancelarPost, marcarFeito, baixarVideoPost, enderecoRetorno, listarLotes, acaoLote, type LotePosts, type Contas, type Prov, type Post, type Rede, type StatusRede, liberarPost, AVISO_LIBERAR } from '../lib/agenda';

const PROVS:{id:Prov;nome:string;redes:string;icone:typeof Youtube;help:'app_google'|'app_meta'|'app_tiktok';idLabel:string;segLabel:string}[] = [
  {id:'google',nome:'YouTube',redes:'Shorts no seu canal',icone:Youtube,help:'app_google',idLabel:'ID do cliente OAuth',segLabel:'Chave secreta do cliente'},
  {id:'meta',nome:'Facebook + Instagram',redes:'Reels na Página e no Instagram profissional',icone:Instagram,help:'app_meta',idLabel:'ID do app (Meta)',segLabel:'Chave secreta do app'},
  {id:'tiktok',nome:'TikTok',redes:'Vídeo nos rascunhos ou direto',icone:Music2,help:'app_tiktok',idLabel:'Client key',segLabel:'Client secret'},
];
const ST:Record<string,[string,string]> = {agendado:['Agendado','info'],postando:['Postando...','info'],postado:['Postado','ok'],erro:['Erro','bad'],manual:['Postar no app','warn'],liberacao:['Esperando sua liberação','warn'],cancelado:['Cancelado','']};
const fmtData=(ts:number)=>new Date(ts*1000).toLocaleString('pt-BR',{weekday:'short',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
const dia=(ts:number)=>new Date(ts*1000).toLocaleDateString('pt-BR',{weekday:'long',day:'2-digit',month:'long',year:'numeric'});

function ContaCard({p,conta,recarregar}:{p:typeof PROVS[number];conta:Contas[Prov];recarregar:()=>void}){
  const {settings,toast}=useApp();
  const [id,setId]=useState(''); const [seg,setSeg]=useState(''); const [busy,setBusy]=useState(false); const [editar,setEditar]=useState(false);
  const run=async(f:()=>Promise<unknown>,ok?:string)=>{ setBusy(true); try{ await f(); if(ok) toast(ok,'ok'); recarregar(); }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }finally{ setBusy(false); } };
  const Icone=p.icone;
  return <article className={'conta-card '+(conta.conectado?'on':'')}>
   <div className="conta-head"><span className={'conta-ic '+p.id}><Icone size={20}/></span><div className="grow"><strong>{p.nome}</strong><small>{p.redes}</small></div>
    {conta.conectado&&conta.erro?<span className="tag bad"><AlertTriangle size={12}/> Entrar de novo</span>:conta.conectado?<span className="tag ok"><CheckCircle2 size={12}/> Conectado</span>:conta.app?<span className="tag warn">Falta entrar</span>:<span className="tag">Falta o app</span>}</div>
   {conta.erro&&<p className="hint bad"><AlertTriangle size={13}/> {conta.erro}</p>}
   {conta.conectado&&<p className="conta-nome">Conta: <b>{conta.nome}</b></p>}
   {p.id==='meta'&&conta.conectado&&<label className="mt">Página usada<select value={conta.pagina} onChange={e=>run(()=>escolherPagina(settings,e.target.value),'Página escolhida.')}>{conta.paginas.map(pg=><option key={pg.id} value={pg.id}>{pg.nome}{pg.instagram?` + Instagram @${pg.instagram}`:' (sem Instagram ligado)'}</option>)}</select></label>}
   {(!conta.app||editar)&&<div className="conta-app">
     <div className="label-row">Dados do app de desenvolvedor <HelpButton topic={p.help} label="Como criar?"/></div>
     <input placeholder={p.idLabel} value={id} onChange={e=>setId(e.target.value)} autoComplete="off" spellCheck={false}/>
     <input placeholder={p.segLabel} type="password" value={seg} onChange={e=>setSeg(e.target.value)} autoComplete="off"/>
     <button className="primary sm" disabled={busy||!id.trim()||!seg.trim()} onClick={()=>run(async()=>{ await salvarApp(settings,p.id,id,seg); setId(''); setSeg(''); setEditar(false); },'App salvo no servidor. Agora clique em Entrar.')}>Salvar no servidor</button>
   </div>}
   <div className="conta-acoes">
    {conta.app&&(!conta.conectado||!!conta.erro)&&<button className="primary sm" disabled={busy} onClick={()=>run(()=>entrar(settings,p.id))}>{busy?<Loader2 size={14} className="spin"/>:<LogIn size={14}/>} {conta.conectado?'Entrar de novo':'Entrar com minha conta'}</button>}
    {conta.conectado&&<button className="subtle sm" disabled={busy} onClick={()=>run(()=>sair(settings,p.id),'Desconectado.')}><LogOut size={14}/> Sair</button>}
    {conta.app&&!editar&&<button className="link-btn" onClick={()=>setEditar(true)}>Trocar app</button>}
    {conta.app&&<HelpButton topic={p.help}/>}
   </div>
  </article>;
}

/** Painel com as contas das redes (login e app). Usado na aba Agendar e na etapa Postar dos cortes. */
export function ContasPainel({aoMudar,onContas}:{aoMudar?:()=>void;onContas?:(c:Contas)=>void}){
  const {settings,toast}=useApp();
  const [contas,setContas]=useState<Contas|null>(null); const [erro,setErro]=useState(''); const [conferindo,setConferindo]=useState(false);
  const recarregar=useCallback(()=>{
    if(!settings.servidor) return;
    lerContas(settings).then(c=>{ setContas(c); onContas?.(c); setErro(''); }).catch(e=>setErro(e.message));
    aoMudar?.();
  },[settings,aoMudar,onContas]);
  useEffect(()=>{ recarregar(); },[recarregar]);
  // O login abre numa janelinha; quando ela termina, avisa esta aba para atualizar.
  useEffect(()=>{
    if(typeof BroadcastChannel==='undefined') return;
    const bc=new BroadcastChannel('estudioclip-contas');
    bc.onmessage=e=>{ if(e.data?.tipo==='conectado'){ toast(e.data.nome+' conectado!','ok'); recarregar(); } else if(e.data?.tipo==='erro'){ toast(e.data.msg,'erro'); recarregar(); } };
    return ()=>bc.close();
  },[recarregar,toast]);
  return <section className="panel">
    {erro&&<div className="note-bar"><AlertTriangle size={16}/><span>{erro}</span><button className="subtle sm" onClick={recarregar}><RefreshCw size={14}/> Tentar de novo</button></div>}
    <div className="section-head"><h2><LogIn size={18}/> Suas contas</h2><button className="subtle sm" disabled={conferindo} onClick={async()=>{ setConferindo(true); try{ const c=await verificarContas(settings); setContas(c); onContas?.(c); const ruins=(Object.values(c) as Contas[Prov][]).filter(x=>x.conectado&&x.erro).length; toast(ruins?`${ruins} conexão(ões) precisam de novo login.`:'Conexões conferidas: tudo certo para postar.',ruins?'erro':'ok'); }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }finally{ setConferindo(false); } }}>{conferindo?<Loader2 size={14} className="spin"/>:<RefreshCw size={14}/>} Conferir conexões</button></div>
    <p className="subtitle">Para postar na sua conta, cada rede pede um "app de desenvolvedor" seu (grátis e só para você). Faça uma vez: clique em <b>Como criar?</b>, siga o passo a passo, cole os dados e clique em <b>Entrar com minha conta</b>. O login abre numa janelinha, e o seu trabalho continua aqui.</p>
    <div className="retorno"><span>Endereço de retorno (cole no app de cada rede):</span><code>{enderecoRetorno()}</code><button className="icon-btn" title="Copiar" onClick={()=>{ navigator.clipboard?.writeText(enderecoRetorno()); toast('Copiado.','ok'); }}><Copy size={14}/></button></div>
    {!contas?<p className="hint"><Loader2 size={14} className="spin"/> Lendo contas do servidor...</p>
    :<div className="contas-grid">{PROVS.map(p=><ContaCard key={p.id} p={p} conta={contas[p.id]} recarregar={recarregar}/>)}
      <article className="conta-card"><div className="conta-head"><span className="conta-ic kwai"><Hand size={20}/></span><div className="grow"><strong>Kwai</strong><small>Sem API pública para postar</small></div><span className="tag">Manual</span></div>
       <p className="hint">Marque o Kwai ao agendar: na hora, o post aparece aqui com <b>Baixar vídeo</b>. É só postar no app do Kwai e clicar em <b>Já postei</b>. <HelpButton topic="kwai"/></p></article>
     </div>}
   </section>;
}

const EV:Record<string,string>={outra_rede:'incluído para publicação',enviando:'conferido e enviando',postado:'publicado',tentar_de_novo:'falhou, vai tentar de novo',erro:'falhou',bloqueado:'barrado na conferência',pede_liberacao:'esperando sua liberação especial',liberado:'liberado por você'};
const paraInput=(ts:number)=>{ const d=new Date(ts*1000); d.setMinutes(d.getMinutes()-d.getTimezoneOffset()); return d.toISOString().slice(0,16); };
const pendente=(p:Post)=>Object.values(p.redes).some(s=>s&&(s.status==='agendado'||s.status==='erro'||s.status==='postando'||s.status==='manual'||s.status==='liberacao'));

/** Uma linha da agenda: hora, redes e o que dá para fazer com o post (postar agora, mudar hora e redes, baixar, cancelar). */
function PostLinha({p,acao,redeFiltro='',selecionado,onSelecionar,onAgendar}:{p:Post;redeFiltro?:Rede|'';selecionado:boolean;onSelecionar?:()=>void;onAgendar:()=>void;acao:(f:()=>Promise<unknown>,ok:string)=>Promise<void>}){
  const {settings}=useApp();
  const [editar,setEditar]=useState(false);
  const [outras,setOutras]=useState<Rede[]|null>(null);
  const [enviando,setEnviando]=useState(false);
  const disponiveis=REDES.filter(r=>!p.redes[r.id]);
  const publicar=async()=>{
    if(!outras?.length||enviando) return;
    setEnviando(true);
    try{
      await acao(async()=>{
        await publicarEmOutrasRedes(settings,p.id,outras);
        setOutras(null);
      },'Redes adicionadas. Acompanhe o envio em Para postar.');
    }finally{ setEnviando(false); }
  };
  const [hora,setHora]=useState(paraInput(p.quando));
  const [redes,setRedes]=useState<Rede[]>(Object.keys(p.redes) as Rede[]);
  const feitas=(Object.entries(p.redes) as [Rede,StatusRede][]).filter(([,s])=>s.status==='postado').map(([r])=>r);
  const abrir=()=>{ setHora(paraInput(p.quando)); setRedes(Object.keys(p.redes) as Rede[]); setEditar(true); };
  const salvar=()=>{ const q=new Date(hora).getTime()/1000; acao(async()=>{ await editarPost(settings,p.id,{quando:Math.abs(q-p.quando)>30?q:undefined,redes}); setEditar(false); },'Post atualizado.'); };
  const alvo=redeFiltro?p.redes[redeFiltro]:undefined;
  const quando=horaDaRede(p,alvo);
  const atrasado=(redeFiltro?[alvo]:Object.values(p.redes)).some(s=>s&&['agendado','manual'].includes(s.status)&&!s.lote_pausado&&horaDaRede(p,s)<Date.now()/1000-120);
  return <div className="post-row">
    <div className="post-hora">{onSelecionar&&<input type="checkbox" aria-label={`Selecionar ${p.titulo||p.id}`} checked={selecionado} onChange={onSelecionar}/>}<Clock size={14}/> {redeFiltro&&!alvo?'Sem horário nesta rede':fmtData(quando).split(', ').pop()}</div>
    <div className="post-info"><strong>{p.titulo||p.legenda.slice(0,60)||'Sem título'}</strong>
     {p.preparando&&<p className="hint"><Loader2 size={13} className="spin"/> Preparando o vídeo no servidor (convertendo para MP4). No celular isso pode levar alguns minutos.</p>}
     {atrasado&&<p className="hint warn">Passou da hora e ainda não saiu. O servidor está ligado? Use Postar agora.</p>}
     <div className="post-redes">{redeFiltro&&!alvo&&<span className="tag warn">{REDES.find(r=>r.id===redeFiltro)?.nome}: Ainda não agendado</span>}{(Object.entries(p.redes) as [Rede,StatusRede][]).map(([r,s])=><span key={r} className={'tag '+(ST[s.status]||['Não disponível',''])[1]} title={s.erro||s.link}>{REDES.find(x=>x.id===r)?.nome.replace(' (manual)','')}: {s.lote_pausado?'Pausado':(ST[s.status]||[s.status,''])[0]}{s.quando&&s.status!=='postado'&&<small> · {fmtData(s.quando)}</small>}{s.status==='postado'&&s.link.startsWith('http')&&<a href={s.link.split(' ')[0]} target="_blank" rel="noreferrer"> <ExternalLink size={11}/></a>}</span>)}</div>
     {Object.entries(p.redes).filter(([r,s])=>(!redeFiltro||r===redeFiltro)&&s&&(s.status==='erro'||s.status==='liberacao'||(s.status==='agendado'&&!!s.erro)||(s.status==='postado'&&!s.link.startsWith('http'))||s.link.includes('('))).map(([r,s])=><p key={r} className={'hint '+(s!.status==='erro'?'bad':s!.status==='agendado'?'warn':'')}><b>{REDES.find(x=>x.id===r)?.nome}:</b> {s!.erro||s!.link}
       {s!.status==='erro'&&<> <button className="subtle sm" onClick={()=>acao(()=>postarAgora(settings,p.id,r),`Tentando de novo no ${REDES.find(x=>x.id===r)?.nome}...`)}><RefreshCw size={13}/> Tentar de novo no {REDES.find(x=>x.id===r)?.nome.replace(' (manual)','')}</button></>}</p>)}
     {settings.servidor&&pendente(p)&&<ConferenciaPost id={p.id} rede={redeFiltro||undefined} onLiberado={()=>acao(async()=>{},'Liberado. Postando...')}/>}
     <TikTokInfoPainel p={p} acao={acao}/>
     {!!p.relatorio?.length&&<details className="post-rel"><summary>Relatório da publicação</summary><ul>{p.relatorio.slice().reverse().map((e,k)=><li key={k}><small className="muted">{fmtData(e.t)}</small> <b>{REDES.find(x=>x.id===e.rede)?.nome.replace(' (manual)','')||e.rede}</b>: {EV[e.evento]||e.evento}{e.detalhe&&e.evento!=='postado'?` — ${e.detalhe}`:''}{e.evento==='postado'&&e.detalhe.startsWith('http')&&<a href={e.detalhe} target="_blank" rel="noreferrer"> abrir</a>}</li>)}</ul></details>}
     {outras&&<div className="post-editar">
       <div className="field-label">Escolha as redes para este vídeo</div>
       <div className="chips">{disponiveis.map(r=><button key={r.id} type="button" disabled={enviando}
         className={'chip '+(outras.includes(r.id)?'on':'')} aria-pressed={outras.includes(r.id)}
         onClick={()=>setOutras(outras.includes(r.id)?outras.filter(x=>x!==r.id):[...outras,r.id])}>{r.nome}</button>)}</div>
       <p className="hint">As redes escolhidas recebem o vídeo agora. No Kwai, baixe o vídeo e publique pelo app.</p>
       <div className="row-gap left mt">
        <button className="primary sm" disabled={enviando||!outras.some(r=>!p.redes[r])} onClick={()=>void publicar()}><Send size={14}/> Confirmar redes</button>
        <button className="subtle sm" disabled={enviando} onClick={()=>setOutras(null)}><X size={14}/> Fechar</button>
       </div>
     </div>}
     {editar&&<div className="post-editar">
       <label>Novo dia e hora<input type="datetime-local" value={hora} onChange={e=>setHora(e.target.value)}/></label>
       <div className="field-label">Redes</div>
       <div className="chips">{REDES.map(r=>{ const on=redes.includes(r.id); const travada=feitas.includes(r.id); return <button key={r.id} type="button" disabled={travada} title={travada?'Já postado nesta rede':''} className={'chip '+(on?'on':'')} aria-pressed={on} onClick={()=>setRedes(x=>on?x.filter(y=>y!==r.id):[...x,r.id])}>{r.nome.replace(' (manual)','')}{travada?' ✓':''}</button>; })}</div>
       <div className="row-gap left mt"><button className="primary sm" disabled={!redes.length||!hora} onClick={salvar}>Salvar</button><button className="subtle sm" onClick={()=>setEditar(false)}><X size={14}/> Fechar</button></div>
     </div>}
    </div>
    <div className="post-acoes">
     {redeFiltro&&(!alvo||!['postado','postando'].includes(alvo.status))&&<button className="subtle sm" onClick={onAgendar}><CalendarClock size={14}/> {alvo?'Reagendar':'Agendar'} no {REDES.find(r=>r.id===redeFiltro)?.nome}</button>}
     {(redeFiltro?[alvo]:Object.values(p.redes)).some(s=>s&&!s.lote_pausado&&(s.status==='agendado'||s.status==='erro'))&&<button className="primary sm" onClick={()=>acao(()=>postarAgora(settings,p.id,redeFiltro||undefined),'Envio colocado na fila.')}>{<><Send size={14}/> {redeFiltro?`Postar agora no ${REDES.find(r=>r.id===redeFiltro)?.nome}`:'Postar agora nas redes pendentes'}</>}</button>}
     {!redeFiltro&&Object.values(p.redes).some(s=>s?.status==='liberacao'||(s?.status==='erro'&&s.erro.includes('de quem é o vídeo')))&&<button className="primary sm" onClick={()=>{ if(window.confirm(AVISO_LIBERAR)) acao(()=>liberarPost(settings,p.id),'Liberado. Postando...'); }}><ShieldCheck size={14}/> Liberar e postar</button>}
     {!redeFiltro&&feitas.length>0&&disponiveis.length>0&&!editar&&!outras&&!p.preparando&&<button className="subtle sm" onClick={()=>setOutras([])}><Send size={14}/> Publicar em outras redes</button>}
     {!redeFiltro&&pendente(p)&&!editar&&!outras&&<button className="subtle sm" onClick={abrir}><Pencil size={14}/> Mudar hora ou redes</button>}
     <button className="subtle sm" onClick={()=>acao(()=>baixarVideoPost(settings,p.id,p.titulo||'corte'),'Vídeo baixado.')}><Download size={14}/> Baixar</button>
     {(!redeFiltro||redeFiltro==='kwai')&&p.redes.kwai?.status==='manual'&&<button className="subtle sm" onClick={()=>acao(()=>marcarFeito(settings,p.id,'kwai'),'Kwai marcado como postado.')}><CheckCircle2 size={14}/> Já postei no Kwai</button>}
     {!redeFiltro&&<button className="icon-btn" title="Cancelar e apagar" aria-label="Cancelar post" onClick={()=>{ if(window.confirm('Cancelar este post e apagar o vídeo do servidor?')) acao(()=>cancelarPost(settings,p.id),'Post cancelado.'); }}><Trash2 size={15}/></button>}
    </div>
  </div>;
}

export default function Agendar(){
  const {settings,toast,go}=useApp();
  const [posts,setPosts]=useState<Post[]|null>(null);
  const [rede,setRede]=useState<Rede|''>('');
  const [filtro,setFiltro]=useState<FiltroPost>('pendentes');
  const [filtroTk,setFiltroTk]=useState<EstadoTikTok|''>('');
  const [selecionados,setSelecionados]=useState<Set<string>>(new Set());
  const [abrirLote,setAbrirLote]=useState(false);
  const [lotes,setLotes]=useState<LotePosts[]>([]);
  const [busyLote,setBusyLote]=useState('');
  const [erro,setErro]=useState('');
  const [novo,setNovo]=useState<File|null>(null); const arq=useRef<HTMLInputElement>(null);
  const recarregar=useCallback(()=>{
    if(!settings.servidor) return;
    listarPosts(settings).then(r=>{setPosts(r.posts);setErro('');}).catch(e=>setErro(e.message));
    listarLotes(settings).then(r=>setLotes(r.lotes)).catch(()=>{});
  },[settings]);
  useEffect(()=>{ recarregar(); const t=setInterval(recarregar,10000); return ()=>clearInterval(t); },[recarregar,settings]);
  const acao=async(f:()=>Promise<unknown>,ok:string)=>{ try{ await f(); toast(ok,'ok'); recarregar(); }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); } };

  if(!settings.servidor) return <section className="panel empty-state">
   <Server size={34}/><h2>Ligue o servidor para agendar</h2>
   <p>Os posts ficam guardados no servidor (seu celular com Termux ou seu PC) e são publicados na hora certa, mesmo com o site fechado.</p>
   <button className="primary" onClick={()=>go('config')}>Ligar servidor em Chaves e ajustes</button> <HelpButton topic="servidor" label="Como ligar?"/>
  </section>;

  const lista=filtrarTikTok(filtrarPosts(posts||[],rede,filtroTk?'todos':filtro),filtroTk);
  const podeSelecionar=(p:Post)=>p.arquivo_disponivel!==false&&!p.preparando&&(!rede||!['postado','postando'].includes(p.redes[rede]?.status||''));
  const elegiveis=lista.filter(podeSelecionar);
  const porDia=new Map<string,Post[]>(); for(const p of lista){ const d=rede&&!p.redes[rede]?'Ainda não agendados nesta rede':dia(horaDaRede(p,rede?p.redes[rede]:undefined)); porDia.set(d,[...(porDia.get(d)||[]),p]); }
  const escolher=(id:string)=>setSelecionados(xs=>{const n=new Set(xs);if(n.has(id))n.delete(id);else if(n.size<200)n.add(id);return n;});
  const agirLote=async(id:string,a:'pausar'|'retomar'|'cancelar')=>{
    setBusyLote(id);
    try{setLotes((await acaoLote(settings,id,a)).lotes);recarregar();toast(a==='cancelar'?'Restante do lote cancelado. Envios já iniciados terminam normalmente.':'Lote atualizado.','ok');}
    catch(e){toast(e instanceof Error?e.message:String(e),'erro');}
    finally{setBusyLote('');}
  };
  return <>
   <section className="panel">
    <div className="section-head"><h2><CalendarClock size={18}/> Posts por rede</h2>
     <button className="subtle sm" onClick={()=>arq.current?.click()}><Upload size={14}/> Agendar vídeo pronto</button>
     <input ref={arq} type="file" accept="video/*" hidden onChange={e=>{ const f=e.target.files?.[0]; if(f) setNovo(f); e.target.value=''; }}/></div>
    <p className="subtitle">Filtre por rede para encontrar o que falta publicar. Um vídeo publicado no YouTube continua pendente no TikTok. Os horários e as ações valem para a rede selecionada.</p>
    <div className="chips mt" aria-label="Filtrar por rede"><button className={'chip '+(!rede?'on':'')} aria-pressed={!rede} onClick={()=>{setRede('');if(filtro==='nao_agendados')setFiltro('pendentes');setSelecionados(new Set());}}>Todas as redes</button>{REDES.map(r=><button key={r.id} className={'chip '+(rede===r.id?'on':'')} aria-pressed={rede===r.id} onClick={()=>{setRede(r.id);setSelecionados(new Set());}}>{r.nome.replace(' (manual)','')} ({filtrarPosts(posts||[],r.id,'pendentes').length})</button>)}</div>
    <label className="mt">Situação<select value={filtro} onChange={e=>{setFiltro(e.target.value as FiltroPost);setSelecionados(new Set());}}>{FILTROS_POST.map(([v,n])=><option key={v} value={v} disabled={v==='nao_agendados'&&!rede}>{n}</option>)}</select></label>
    <label className="mt">Status do TikTok<select value={filtroTk} onChange={e=>{setFiltroTk(e.target.value as EstadoTikTok|'');setSelecionados(new Set());}}><option value="">Todos</option>{ESTADOS_TIKTOK.map(([v,n])=><option key={v} value={v}>{n} ({(posts||[]).filter(p=>p.tiktok?.estado===v).length})</option>)}</select></label>
    {filtroTk&&<p className="hint">Filtrando pelo status do TikTok: a lista mostra o vídeo em qualquer situação das outras redes.</p>}
    {!rede&&<p className="hint">Escolha uma rede para incluir os vídeos que ainda não foram agendados nela. Os números dos botões contam pendências de cada rede.</p>}
    {erro&&<p className="hint bad" role="alert">{erro}</p>}
    {!!elegiveis.length&&<div className="posts-lote-barra mt"><label className="check"><input type="checkbox" checked={elegiveis.slice(0,200).every(p=>selecionados.has(p.id))} onChange={e=>setSelecionados(e.target.checked?new Set(elegiveis.slice(0,200).map(p=>p.id)):new Set())}/> Selecionar resultados do filtro (até 200)</label><span>{selecionados.size} selecionado(s)</span><button className="primary sm" disabled={!selecionados.size} onClick={()=>setAbrirLote(true)}><CalendarClock size={14}/> Agendar selecionados</button>{!!selecionados.size&&<button className="subtle sm" onClick={()=>setSelecionados(new Set())}>Limpar seleção</button>}</div>}
    {!posts?<p className="hint"><Loader2 size={14} className="spin"/> Carregando...</p>
    :!lista.length?<p className="hint center">Nenhum vídeo nesta combinação de rede e situação.</p>
    :[...porDia].map(([d,ls])=><div key={d} className="agenda-dia"><h3>{d}</h3>{ls.map(p=><PostLinha key={p.id+'-'+rede} p={p} redeFiltro={rede} selecionado={selecionados.has(p.id)} onSelecionar={podeSelecionar(p)?()=>escolher(p.id):undefined} onAgendar={()=>{setSelecionados(new Set([p.id]));setAbrirLote(true);}} acao={acao}/>)}</div>)}
   </section>
   {!!lotes.length&&<section className="panel"><h2>Lotes de publicação</h2>{lotes.map(l=><article className="post-row" key={l.id}><div className="grow"><b>Lote{l.inicio?` · ${fmtData(l.inicio)}`:""} · {l.redes.map(r=>REDES.find(x=>x.id===r)?.nome).join(', ')}</b><p className="hint">{l.publicados} publicado(s) · {l.pendentes} restante(s) · {l.cancelados} cancelado(s){l.pausado?' · Pausado':''}</p></div>{l.pendentes>0&&<div className="row-gap"><button className="subtle sm" disabled={!!busyLote} onClick={()=>void agirLote(l.id,l.pausado?'retomar':'pausar')}>{l.pausado?'Retomar':'Pausar'} lote</button><button className="subtle sm" disabled={!!busyLote} onClick={()=>void agirLote(l.id,'cancelar')}>Cancelar restante</button></div>}</article>)}</section>}
   {abrirLote&&<AgendarLote posts={posts||[]} ids={[...selecionados]} redeInicial={rede||undefined} onClose={()=>setAbrirLote(false)} onAgendado={()=>{setAbrirLote(false);setSelecionados(new Set());recarregar();}}/>}

   <details className="recolhido contas-dobra" open={!posts?.length}>
    <summary><ChevronDown size={16}/> Contas das redes (YouTube, Facebook, Instagram, TikTok)</summary>
    <ContasPainel aoMudar={recarregar}/>
   </details>
   {novo&&<AgendarPost titulo={novo.name.replace(/\.\w+$/,'')} legenda="" gerar={async()=>({blob:novo,nome:novo.name})} onClose={()=>{ setNovo(null); recarregar(); }}/>}
  </>;
}
