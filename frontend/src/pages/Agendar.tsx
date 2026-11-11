import { useCallback, useEffect, useRef, useState } from 'react';
import { Youtube, Instagram, Music2, CalendarClock, LogIn, LogOut, Loader2, Server, Copy, ExternalLink, Download, Send, Trash2, RefreshCw, Upload, CheckCircle2, AlertTriangle, Clock, Hand } from 'lucide-react';
import { useApp } from '../state';
import { HelpButton } from '../components/Help';
import AgendarPost from '../components/AgendarPost';
import { REDES, lerContas, salvarApp, entrar, sair, escolherPagina, listarPosts, postarAgora, cancelarPost, marcarFeito, linkVideo, enderecoRetorno, type Contas, type Prov, type Post, type Rede } from '../lib/agenda';

const PROVS:{id:Prov;nome:string;redes:string;icone:typeof Youtube;help:'app_google'|'app_meta'|'app_tiktok';idLabel:string;segLabel:string}[] = [
  {id:'google',nome:'YouTube',redes:'Shorts no seu canal',icone:Youtube,help:'app_google',idLabel:'ID do cliente OAuth',segLabel:'Chave secreta do cliente'},
  {id:'meta',nome:'Facebook + Instagram',redes:'Reels na Página e no Instagram profissional',icone:Instagram,help:'app_meta',idLabel:'ID do app (Meta)',segLabel:'Chave secreta do app'},
  {id:'tiktok',nome:'TikTok',redes:'Vídeo nos rascunhos ou direto',icone:Music2,help:'app_tiktok',idLabel:'Client key',segLabel:'Client secret'},
];
const ST:Record<string,[string,string]> = {agendado:['Agendado','info'],postando:['Postando...','info'],postado:['Postado','ok'],erro:['Erro','bad'],manual:['Postar no app','warn']};
const fmtData=(ts:number)=>new Date(ts*1000).toLocaleString('pt-BR',{weekday:'short',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
const dia=(ts:number)=>new Date(ts*1000).toLocaleDateString('pt-BR',{weekday:'long',day:'2-digit',month:'long',year:'numeric'});

function ContaCard({p,conta,recarregar}:{p:typeof PROVS[number];conta:Contas[Prov];recarregar:()=>void}){
  const {settings,toast}=useApp();
  const [id,setId]=useState(''); const [seg,setSeg]=useState(''); const [busy,setBusy]=useState(false); const [editar,setEditar]=useState(false);
  const run=async(f:()=>Promise<unknown>,ok?:string)=>{ setBusy(true); try{ await f(); if(ok) toast(ok,'ok'); recarregar(); }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }finally{ setBusy(false); } };
  const Icone=p.icone;
  return <article className={'conta-card '+(conta.conectado?'on':'')}>
   <div className="conta-head"><span className={'conta-ic '+p.id}><Icone size={20}/></span><div className="grow"><strong>{p.nome}</strong><small>{p.redes}</small></div>
    {conta.conectado?<span className="tag ok"><CheckCircle2 size={12}/> Conectado</span>:conta.app?<span className="tag warn">Falta entrar</span>:<span className="tag">Falta o app</span>}</div>
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
    {conta.app&&!conta.conectado&&<button className="primary sm" disabled={busy} onClick={()=>run(()=>entrar(settings,p.id))}>{busy?<Loader2 size={14} className="spin"/>:<LogIn size={14}/>} Entrar com minha conta</button>}
    {conta.conectado&&<button className="subtle sm" disabled={busy} onClick={()=>run(()=>sair(settings,p.id),'Desconectado.')}><LogOut size={14}/> Sair</button>}
    {conta.app&&!editar&&<button className="link-btn" onClick={()=>setEditar(true)}>Trocar app</button>}
    {conta.app&&<HelpButton topic={p.help}/>}
   </div>
  </article>;
}

/** Painel com as contas das redes (login e app). Usado na aba Agendar e na etapa Postar dos cortes. */
export function ContasPainel({aoMudar,onContas}:{aoMudar?:()=>void;onContas?:(c:Contas)=>void}){
  const {settings,toast}=useApp();
  const [contas,setContas]=useState<Contas|null>(null); const [erro,setErro]=useState('');
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
    <div className="section-head"><h2><LogIn size={18}/> Suas contas</h2><button className="subtle sm" onClick={recarregar}><RefreshCw size={14}/> Atualizar</button></div>
    <p className="subtitle">Para postar na sua conta, cada rede pede um "app de desenvolvedor" seu (grátis e só para você). Faça uma vez: clique em <b>Como criar?</b>, siga o passo a passo, cole os dados e clique em <b>Entrar com minha conta</b>. O login abre numa janelinha, e o seu trabalho continua aqui.</p>
    <div className="retorno"><span>Endereço de retorno (cole no app de cada rede):</span><code>{enderecoRetorno()}</code><button className="icon-btn" title="Copiar" onClick={()=>{ navigator.clipboard?.writeText(enderecoRetorno()); toast('Copiado.','ok'); }}><Copy size={14}/></button></div>
    {!contas?<p className="hint"><Loader2 size={14} className="spin"/> Lendo contas do servidor...</p>
    :<div className="contas-grid">{PROVS.map(p=><ContaCard key={p.id} p={p} conta={contas[p.id]} recarregar={recarregar}/>)}
      <article className="conta-card"><div className="conta-head"><span className="conta-ic kwai"><Hand size={20}/></span><div className="grow"><strong>Kwai</strong><small>Sem API pública para postar</small></div><span className="tag">Manual</span></div>
       <p className="hint">Marque o Kwai ao agendar: na hora, o post aparece aqui com <b>Baixar vídeo</b>. É só postar no app do Kwai e clicar em <b>Já postei</b>. <HelpButton topic="kwai"/></p></article>
     </div>}
   </section>;
}

export default function Agendar(){
  const {settings,toast,go}=useApp();
  const [posts,setPosts]=useState<Post[]|null>(null);
  const [novo,setNovo]=useState<File|null>(null); const arq=useRef<HTMLInputElement>(null);
  const recarregar=useCallback(()=>{
    if(!settings.servidor) return;
    listarPosts(settings).then(r=>setPosts(r.posts)).catch(()=>{});
  },[settings]);
  useEffect(()=>{ recarregar(); const t=setInterval(()=>listarPosts(settings).then(r=>setPosts(r.posts)).catch(()=>{}),10000); return ()=>clearInterval(t); },[recarregar,settings]);
  const acao=async(f:()=>Promise<unknown>,ok:string)=>{ try{ await f(); toast(ok,'ok'); recarregar(); }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); } };

  if(!settings.servidor) return <section className="panel empty-state">
   <Server size={34}/><h2>Ligue o servidor para agendar</h2>
   <p>Os posts ficam guardados no servidor (seu celular com Termux ou seu PC) e são publicados na hora certa, mesmo com o site fechado.</p>
   <button className="primary" onClick={()=>go('config')}>Ligar servidor em Chaves e ajustes</button> <HelpButton topic="servidor" label="Como ligar?"/>
  </section>;

  const porDia=new Map<string,Post[]>(); for(const p of posts||[]){ const d=dia(p.quando); porDia.set(d,[...(porDia.get(d)||[]),p]); }
  return <>
   <ContasPainel aoMudar={recarregar}/>

   <section className="panel">
    <div className="section-head"><h2><CalendarClock size={18}/> Agenda de posts</h2>
     <button className="primary sm" onClick={()=>arq.current?.click()}><Upload size={14}/> Agendar vídeo pronto</button>
     <input ref={arq} type="file" accept="video/*" hidden onChange={e=>{ const f=e.target.files?.[0]; if(f) setNovo(f); e.target.value=''; }}/></div>
    <p className="subtitle">Para agendar um corte, use o botão <b>Agendar</b> em cada corte, na aba Gerar cortes. Aqui você confere tudo o que está marcado.</p>
    {!posts?<p className="hint"><Loader2 size={14} className="spin"/> Carregando...</p>
    :!posts.length?<p className="hint center">Nenhum post agendado ainda.</p>
    :[...porDia].map(([d,lista])=><div key={d} className="agenda-dia"><h3>{d}</h3>{lista.map(p=><div key={p.id} className="post-row">
       <div className="post-hora"><Clock size={14}/> {fmtData(p.quando).split(', ').pop()}</div>
       <div className="post-info"><strong>{p.titulo||p.legenda.slice(0,60)||'Sem título'}</strong>
        {p.preparando&&<p className="hint"><Loader2 size={13} className="spin"/> Preparando o vídeo no servidor (convertendo para MP4). No celular isso pode levar alguns minutos.</p>}
        <div className="post-redes">{(Object.entries(p.redes) as [Rede,NonNullable<Post['redes'][Rede]>][]).map(([r,s])=><span key={r} className={'tag '+ST[s.status][1]} title={s.erro||s.link}>{REDES.find(x=>x.id===r)?.nome.replace(' (manual)','')}: {ST[s.status][0]}{s.status==='postado'&&s.link.startsWith('http')&&<a href={s.link.split(' ')[0]} target="_blank" rel="noreferrer"> <ExternalLink size={11}/></a>}</span>)}</div>
        {Object.entries(p.redes).filter(([,s])=>s.status==='erro'||(s.status==='postado'&&!s.link.startsWith('http'))||s.link.includes('(')).map(([r,s])=><p key={r} className={'hint '+(s.status==='erro'?'bad':'')}><b>{REDES.find(x=>x.id===r)?.nome}:</b> {s.erro||s.link}</p>)}
       </div>
       <div className="post-acoes">
        {Object.values(p.redes).some(s=>s.status==='agendado'||s.status==='erro')&&<button className="subtle sm" onClick={()=>acao(()=>postarAgora(settings,p.id),'Postando agora...')}>{Object.values(p.redes).some(s=>s.status==='erro')?<><RefreshCw size={14}/> Tentar de novo</>:<><Send size={14}/> Postar agora</>}</button>}
        <a className="subtle sm" href={linkVideo(settings,p.id)}><Download size={14}/> Baixar vídeo</a>
        {p.redes.kwai?.status==='manual'&&<button className="subtle sm" onClick={()=>acao(()=>marcarFeito(settings,p.id,'kwai'),'Kwai marcado como postado.')}><CheckCircle2 size={14}/> Já postei no Kwai</button>}
        <button className="icon-btn" title="Cancelar e apagar" onClick={()=>{ if(window.confirm('Cancelar este post e apagar o vídeo do servidor?')) acao(()=>cancelarPost(settings,p.id),'Post cancelado.'); }}><Trash2 size={15}/></button>
       </div>
      </div>)}</div>)}
   </section>
   {novo&&<AgendarPost titulo={novo.name.replace(/\.\w+$/,'')} legenda="" gerar={async()=>({blob:novo,nome:novo.name})} onClose={()=>{ setNovo(null); recarregar(); }}/>}
  </>;
}
