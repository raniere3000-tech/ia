import { useCallback, useEffect, useMemo, useState } from 'react';
import { Home, Search, Clapperboard, Captions, LayoutTemplate, Settings as Gear, CheckCircle2, AlertTriangle, Info, X, Circle } from 'lucide-react';
import { AppCtx, PROJETO_VAZIO, type Marca, type Projeto, type Settings, type Tab } from './state';
import { store } from './lib/store';
import { TEMPLATE_PADRAO, type Template } from './lib/render';
import Inicio from './pages/Inicio';
import Radar from './pages/Radar';
import Cortes from './pages/Cortes';
import Estilos from './pages/Estilos';
import Templates from './pages/Templates';
import Config from './pages/Config';
import './style.css';

const SETTINGS_PADRAO:Settings = {ytKey:'',claudeKey:'',whisperModel:'onnx-community/whisper-base',idioma:'portuguese',api:'',legendaPadrao:'classico-contorno',efeitoPadrao:'blur-background',servidor:'',servidorToken:''};
const NAV:[Tab,string,typeof Home][] = [['inicio','Como funciona',Home],['radar','Radar de vídeos',Search],['cortes','Gerar cortes',Clapperboard],['estilos','Legendas e efeitos',Captions],['templates','Template da marca',LayoutTemplate],['config','Chaves e ajustes',Gear]];
const TITLES:Record<Tab,[string,string]> = {
  inicio:['Bem-vindo ao EstúdioClip','Descubra vídeos em alta, transforme vídeos longos em cortes curtos e exporte com legenda, tudo no navegador.'],
  radar:['Descubra vídeos em alta','Pesquise qualquer nicho no YouTube e encontre canais e vídeos com muitas visualizações.'],
  cortes:['Transforme vídeos em cortes','Envie um vídeo seu (ou autorizado), escolha a duração e receba os melhores trechos com nota.'],
  estilos:['Legendas e efeitos','Escolha o visual padrão das legendas e o efeito aplicado nos cortes.'],
  templates:['Template da marca','Logo, cor, moldura e crédito aplicados automaticamente em todos os cortes.'],
  config:['Chaves e ajustes','Cole aqui as chaves que ativam cada função. Clique no ? para ver como conseguir cada uma.'],
};

export default function App(){
  const [settings,setS]=useState<Settings>(()=>{ const saved=store.json<Partial<Settings>>('studio_settings',{}); return {...SETTINGS_PADRAO,...saved,ytKey:saved.ytKey||store.get('studio_yt_key')||''}; });
  const setSettings=useCallback((p:Partial<Settings>)=>setS(s=>{ const n={...s,...p}; store.setJson('studio_settings',n); return n; }),[]);
  const [tab,setTab]=useState<Tab>(()=>{ const h=location.hash.slice(1) as Tab; return NAV.some(n=>n[0]===h)?h:'inicio'; });
  const go=useCallback((t:Tab)=>{ setTab(t); history.replaceState(null,'','#'+t); window.scrollTo({top:0}); },[]);
  const [toasts,setToasts]=useState<{id:number;msg:string;kind:string}[]>([]);
  const toast=useCallback((msg:string,kind:'ok'|'erro'|'info'='info')=>{ const id=Date.now()+Math.random(); setToasts(t=>[...t.slice(-2),{id,msg,kind}]); setTimeout(()=>setToasts(t=>t.filter(x=>x.id!==id)),kind==='erro'?9000:5500); },[]);
  const [projeto,setP]=useState<Projeto>(PROJETO_VAZIO);
  const setProjeto=useCallback((f:(p:Projeto)=>Projeto)=>setP(f),[]);
  const [template,setT]=useState<Template>(()=>({...TEMPLATE_PADRAO,...store.json<Partial<Template>>('studio_template',{})}));
  const setTemplate=useCallback((t:Template)=>{ setT(t); store.setJson('studio_template',t); },[]);
  const [linkRef,setLinkRef]=useState('');
  const [marcas,setM]=useState<Marca[]>([]);
  const setMarcas=useCallback((f:(m:Marca[])=>Marca[])=>setM(f),[]);
  useEffect(()=>()=>{ if(projeto.url) URL.revokeObjectURL(projeto.url); },[projeto.url]);
  // Link gerado pelo servidor (?servidor=...&senha=...): liga o servidor neste aparelho sozinho.
  useEffect(()=>{
    const q=new URLSearchParams(location.search); const srv=q.get('servidor'); if(!srv) return;
    const senha=q.get('senha')||'';
    history.replaceState(null,'',location.pathname+location.hash);
    import('./lib/servidor').then(({testarServidor})=>testarServidor(srv,senha)).then(()=>{ setSettings({servidor:srv.replace(/\/+$/,''),servidorToken:senha}); toast('Servidor do celular conectado! Cole um link em Gerar cortes.','ok'); })
      .catch(e=>toast('Não consegui conectar ao servidor do link: '+(e instanceof Error?e.message:String(e)),'erro'));
  },[setSettings,toast]);
  const ctx=useMemo(()=>({settings,setSettings,tab,go,toast,projeto,setProjeto,template,setTemplate,linkRef,setLinkRef,marcas,setMarcas}),[settings,setSettings,tab,go,toast,projeto,setProjeto,template,setTemplate,linkRef,marcas,setMarcas]);
  const status=[{ok:!!settings.ytKey,label:'Radar (YouTube)',opt:false},{ok:true,label:'Cortes e exportação',opt:false},{ok:!!settings.claudeKey,label:'Notas com IA',opt:true},{ok:!!settings.servidor,label:'Cortes pelo link',opt:true}];
  const [t,sub]=TITLES[tab];
  return <AppCtx.Provider value={ctx}>
   <div className="app">
    <aside className="sidebar">
     <div className="brand"><span className="brand-icon"><Clapperboard size={22}/></span><div><strong>ESTÚDIO<span>CLIP</span></strong><small>RADAR + EDITOR</small></div></div>
     <nav>{NAV.map(([key,label,Icon])=><button key={key} className={'nav '+(tab===key?'active':'')} onClick={()=>go(key)} title={label}><Icon size={18}/><span>{label}</span>{key==='cortes'&&projeto.clips.length>0&&<em className="nav-badge">{projeto.clips.filter(c=>!c.descartado).length}</em>}</button>)}</nav>
     <div className="sidebar-bottom">
      <div className="side-title">STATUS</div>
      {status.map(s=><button key={s.label} className={'status-row '+(s.ok?'ok':s.opt?'opt':'no')} onClick={()=>go('config')}>{s.ok?<CheckCircle2 size={14}/>:<Circle size={14}/>}<span>{s.label}</span><small>{s.ok?'pronto':s.opt?'opcional':'falta chave'}</small></button>)}
     </div>
    </aside>
    <main>
     <header className="page-head"><div><div className="eyebrow">PAINEL DE PRODUÇÃO</div><h1>{t}</h1><p className="subtitle">{sub}</p></div></header>
     {tab==='inicio'&&<Inicio/>}
     {tab==='radar'&&<Radar/>}
     {tab==='cortes'&&<Cortes/>}
     {tab==='estilos'&&<Estilos/>}
     {tab==='templates'&&<Templates/>}
     {tab==='config'&&<Config/>}
     <footer>EstúdioClip • Use apenas vídeos próprios ou com autorização • Seus vídeos e chaves ficam neste navegador</footer>
    </main>
   </div>
   <div className="toasts" aria-live="polite">{toasts.map(x=><div key={x.id} className={'toast '+x.kind}>{x.kind==='ok'?<CheckCircle2 size={17}/>:x.kind==='erro'?<AlertTriangle size={17}/>:<Info size={17}/>}<span>{x.msg}</span><button onClick={()=>setToasts(t=>t.filter(y=>y.id!==x.id))} aria-label="Fechar"><X size={15}/></button></div>)}</div>
  </AppCtx.Provider>;
}
