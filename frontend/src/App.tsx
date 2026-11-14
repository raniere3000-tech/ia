import ErroTela from './components/ErroTela';
import { Suspense, lazy, memo, useCallback, useEffect, useMemo, useState, type ComponentType } from 'react';
import { Home, Search, Clapperboard, CalendarClock, Captions, LayoutTemplate, Settings as Gear, Sparkles, Mic, Film, Bot, CheckCircle2, AlertTriangle, Info, X, Circle } from 'lucide-react';
import { AppCtx, PROJETO_VAZIO, type Marca, type Projeto, type Settings, type Tab } from './state';
import { store } from './lib/store';
import { salvos, temCofre, cofreAberto, separar, atualizarCofre } from './lib/cofre';
import Cadeado from './components/Cadeado';
import { TEMPLATE_PADRAO, type Template } from './lib/render';
import Inicio from './pages/Inicio';

// Cada aba é baixada só quando é aberta (a primeira tela abre mais rápido).
// Se o site foi atualizado com a aba aberta, o pedaço antigo some do servidor: recarrega uma vez para pegar a versão nova.
type Mod = Promise<{default:ComponentType}>;
const CARGA:Partial<Record<Tab,()=>Mod>> = {
  radar:()=>import('./pages/Radar'), cortes:()=>import('./pages/Cortes'), agendar:()=>import('./pages/Agendar'), agente:()=>import('./pages/Agente'), video:()=>import('./pages/VideoCodigo'), vozes:()=>import('./pages/Vozes'),
  manual:()=>import('./pages/Manual'), estilos:()=>import('./pages/Estilos'), templates:()=>import('./pages/Templates'), config:()=>import('./pages/Config'),
};
const seguro=(f:()=>Mod)=>()=>f().then(m=>{ try{ sessionStorage.removeItem('studio_recarregou'); }catch{ /* sem armazenamento */ } return m; },()=>{
  let ja=true; try{ ja=!!sessionStorage.getItem('studio_recarregou'); sessionStorage.setItem('studio_recarregou','1'); }catch{ /* sem armazenamento */ }
  if(!ja&&navigator.onLine){ location.reload(); return new Promise<{default:ComponentType}>(()=>{}); }
  throw new Error(navigator.onLine?'Não consegui abrir esta tela. Recarregue a página.':'Sem internet: esta tela ainda não foi baixada neste aparelho.'); });
const TELAS=Object.fromEntries(Object.entries(CARGA).map(([k,f])=>[k,memo(lazy(seguro(f)))])) as unknown as Record<Exclude<Tab,'inicio'>,ComponentType>;
const InicioM=memo(Inicio);
/** Começa a baixar a aba quando o dedo ou o mouse chega no botão. */
const adiantar=(t:Tab)=>{ CARGA[t]?.().catch(()=>{}); };

const SETTINGS_PADRAO:Settings = {ytKey:'',claudeKey:'',whisperModel:'onnx-community/whisper-base',idioma:'portuguese',api:'',legendaPadrao:'classico-contorno',efeitoPadrao:'seguir-rosto',servidor:'',servidorToken:'',servidorCanal:'',geminiKey:'',ia:''};
const NAV:[Tab,string,typeof Home][] = [['inicio','Início',Home],['radar','Radar de vídeos',Search],['cortes','Gerar cortes',Clapperboard],['video','Criar vídeo animado',Sparkles],['vozes','Estúdio de vozes',Mic],['manual','Montagem manual',Film],['agendar','Agendar posts',CalendarClock],['agente','Agentes',Bot],['estilos','Legendas e efeitos',Captions],['templates','Template da marca',LayoutTemplate],['config','Chaves e ajustes',Gear]];
/** Nome curto de cada aba para a barra de baixo do telefone. */
const CURTO:Record<Tab,string> = {inicio:'Início',radar:'Radar',cortes:'Cortes',video:'Animado',vozes:'Vozes',manual:'Montagem',agendar:'Agendar',agente:'Agentes',estilos:'Legendas',templates:'Template',config:'Ajustes'};
/** Menu por etapa do trabalho. */
const GRUPOS:[string,Tab[]][] = [['',['inicio']],['Descobrir',['radar']],['Produzir',['cortes','video','vozes','manual','estilos','templates']],['Publicar',['agendar','agente']],['Configurações',['config']]];
const TITLES:Record<Tab,[string,string]> = {
  inicio:['Bem-vindo ao EstúdioClip','Descubra vídeos em alta, transforme vídeos longos em cortes curtos e exporte com legenda, tudo no navegador.'],
  radar:['Descubra vídeos em alta','Pesquise qualquer nicho no YouTube e encontre canais e vídeos com muitas visualizações.'],
  cortes:['Transforme vídeos em cortes','Envie um vídeo seu (ou autorizado), escolha a duração e receba os melhores trechos com nota.'],
  vozes:['Estúdio de vozes','Crie personagens, teste e compare vozes do Gemini, aplique no roteiro e baixe o áudio pronto para o vídeo.'],
  manual:['Montagem manual','Mande as imagens dos quadros, a narração, a trilha e os efeitos. O site lê o roteiro de quadros, sincroniza tudo e grava o vídeo.'],
  video:['Criar vídeo animado','Digite um tema: a IA escreve o roteiro e o site monta um vídeo vertical animado, com narração e batida, pronto para postar.'],
  agendar:['Agendar posts','Conecte suas contas uma vez e agende os cortes no YouTube, Instagram, Facebook e TikTok. O Kwai fica com o botão de baixar.'],
  agente:['Agentes','Dois agentes trabalham sozinhos no seu servidor: um procura vídeos e faz os cortes, o outro agenda e posta. Você aprova os canais e recebe tudo por e-mail.'],
  estilos:['Legendas e efeitos','Escolha o visual padrão das legendas e o efeito aplicado nos cortes.'],
  templates:['Template da marca','Logo, cor, moldura e crédito aplicados automaticamente em todos os cortes.'],
  config:['Chaves e ajustes','Cole aqui as chaves que ativam cada função. Clique no ? para ver como conseguir cada uma.'],
};

export default function App(){
  const [settings,setS]=useState<Settings>(()=>{ const saved=salvos(); return {...SETTINGS_PADRAO,...saved,ytKey:saved.ytKey||(temCofre()?'':store.get('studio_yt_key'))||''}; });
  const [trancado,setTrancado]=useState(()=>temCofre()&&!cofreAberto());
  const setSettings=useCallback((p:Partial<Settings>)=>setS(s=>{ const n={...s,...p};
    // Com o cofre ligado, as chaves nunca vão em texto puro para o armazenamento do navegador.
    if(temCofre()){ store.setJson('studio_settings',separar(n).publico); atualizarCofre(n); } else store.setJson('studio_settings',n);
    return n; }),[]);
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
  // Volta do login das redes (?code=...&state=google_...): entrega o código ao servidor.
  // Normalmente isso acontece na janelinha de login: ela avisa a aba principal e fecha sozinha.
  useEffect(()=>{
    const q=new URLSearchParams(location.search); const state=q.get('state')||''; const m=/^(google|meta|tiktok)_/.exec(state);
    if(!m) return;
    const code=q.get('code'); const erro=q.get('error_description')||q.get('error_message')||q.get('error');
    history.replaceState(null,'',location.pathname+'#agendar'); setTab('agendar');
    const nome={google:'YouTube',meta:'Facebook e Instagram',tiktok:'TikTok'}[m[1]]!;
    const t0=+(store.get('studio_login_popup')||0); const ehJanela=!!window.opener||(t0>0&&Date.now()-t0<30*60*1000);
    const avisar=(msg:object)=>{ try{ const bc=new BroadcastChannel('estudioclip-contas'); bc.postMessage(msg); bc.close(); }catch{ /* navegador antigo */ } };
    const fim=(msg:{tipo:string;nome?:string;msg?:string})=>{
      if(!ehJanela) return;
      store.set('studio_login_popup',''); avisar(msg);
      setTimeout(()=>{ try{ window.close(); }catch{ /* ignora */ } },msg.tipo==='erro'?4000:800);
    };
    if(!code){ const t='Login cancelado'+(erro?': '+erro:'.'); toast(t,'erro'); fim({tipo:'erro',msg:t}); return; }
    const cfg=salvos();
    import('./lib/agenda').then(({enviarCodigo})=>enviarCodigo({servidor:cfg.servidor||'',servidorToken:cfg.servidorToken||''},code,state))
      .then(()=>{ toast(nome+' conectado!'+(ehJanela?' Pode fechar esta janela.':''),'ok'); fim({tipo:'conectado',nome}); })
      .catch(e=>{ const t=e instanceof Error?e.message:String(e); toast(t,'erro'); fim({tipo:'erro',msg:t}); });
  },[toast]);
  // Link gerado pelo servidor (?canal=...&senha=..., ou o antigo ?servidor=...&senha=...): liga o servidor neste aparelho.
  // Com o "canal", o site acha sozinho o endereço novo do servidor toda vez que ele reinicia (link fixo).
  useEffect(()=>{
    const q=new URLSearchParams(location.search); const srv=q.get('servidor'); const canalQ=q.get('canal');
    // A senha vem depois do # (não é enviada a nenhum servidor). Links antigos traziam em ?senha=.
    const noHash=/^#senha=(.*)$/.exec(location.hash); const senhaLink=noHash?decodeURIComponent(noHash[1]):q.get('senha');
    if(srv||canalQ||noHash) history.replaceState(null,'',location.pathname+(noHash?'':location.hash));
    const atual=salvos();
    // Um link não troca o servidor escondido: quem recebe um link de outra pessoa precisa confirmar.
    const troca=!!(srv||canalQ)&&((!!srv&&srv.replace(/\/+$/,'')!==atual.servidor)||(!!canalQ&&canalQ!==atual.servidorCanal));
    if(troca&&!window.confirm('Este link quer ligar o aplicativo a um servidor'+(atual.servidor?' DIFERENTE do que você usa hoje':'')+'.\n\nSó aceite se o link foi gerado pelo SEU servidor (no seu Termux ou computador). Um link de outra pessoa pode receber seus vídeos e suas chaves.\n\nLigar a este servidor?')) return;
    if(srv&&!/^https:\/\/[a-z0-9.-]+(:\d+)?$|^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(srv.replace(/\/+$/,''))){ toast('O endereço do servidor neste link não é válido.','erro'); return; }
    const canal=canalQ||atual.servidorCanal||''; const senha=senhaLink??atual.servidorToken??'';
    const doLink=!!(srv||canalQ);
    if(!srv&&!canal) return;
    (async()=>{
      const {testarServidor,enderecoDoCanal}=await import('./lib/servidor');
      let url=srv?srv.replace(/\/+$/,''):'';
      if(canal){ const u=await enderecoDoCanal(canal,senha,atual.servidor||'').catch(()=>null); if(u) url=u; }
      if(!url){ if(doLink) toast('O servidor do celular ainda não avisou o endereço. Ligue o servidor no Termux e abra o link de novo.','erro'); return; }
      if(!doLink&&url===atual.servidor) return;
      try{
        await testarServidor(url,senha);
        setSettings({servidor:url,servidorToken:senha,servidorCanal:canal});
        toast(doLink?'Servidor do celular conectado! Guarde este link: ele funciona sempre.':'Servidor do celular reconectado no endereço novo.','ok');
      }catch(e){ if(doLink) toast('Não consegui conectar ao servidor do link: '+(e instanceof Error?e.message:String(e)),'erro'); }
    })();
  },[setSettings,toast]);
  const ctx=useMemo(()=>({settings,setSettings,tab,go,toast,projeto,setProjeto,template,setTemplate,linkRef,setLinkRef,marcas,setMarcas}),[settings,setSettings,tab,go,toast,projeto,setProjeto,template,setTemplate,linkRef,marcas,setMarcas]);
  const status=[{ok:!!settings.ytKey,label:'Radar (YouTube)',opt:false},{ok:true,label:'Cortes e exportação',opt:false},{ok:!!(settings.claudeKey||settings.geminiKey),label:'Notas com IA',opt:true},{ok:!!settings.servidor,label:'Cortes pelo link',opt:true}];
  const [t,sub]=TITLES[tab];
  return <AppCtx.Provider value={ctx}>
   {trancado&&<Cadeado aoAbrir={seg=>{ setS(s=>({...s,...seg})); setTrancado(false); }} aoPular={()=>setTrancado(false)}/>}
   <div className="app">
    <aside className="sidebar">
     <div className="brand"><span className="brand-icon"><Clapperboard size={22}/></span><div><strong>ESTÚDIO<span>CLIP</span></strong><small>RADAR + EDITOR</small></div></div>
     <nav>{GRUPOS.map(([g,tabs])=><div key={g||'ini'} className="nav-grupo">{g&&<small className="nav-titulo">{g}</small>}{tabs.map(key=>{ const [,label,Icon]=NAV.find(n=>n[0]===key)!; return <button key={key} className={'nav '+(tab===key?'active':'')} onClick={()=>go(key)} onPointerEnter={()=>adiantar(key)} onFocus={()=>adiantar(key)} aria-current={tab===key?'page':undefined} title={label}><Icon size={18}/><span>{label}</span><b className="nav-curto" aria-hidden="true">{CURTO[key]}</b>{key==='cortes'&&projeto.clips.length>0&&<em className="nav-badge">{projeto.clips.filter(c=>!c.descartado).length}</em>}</button>; })}</div>)}</nav>
     <div className="sidebar-bottom">
      <div className="side-title">STATUS</div>
      {status.map(s=><button key={s.label} className={'status-row '+(s.ok?'ok':s.opt?'opt':'no')} onClick={()=>go('config')}>{s.ok?<CheckCircle2 size={14}/>:<Circle size={14}/>}<span>{s.label}</span><small>{s.ok?'pronto':s.opt?'opcional':'falta chave'}</small></button>)}
     </div>
    </aside>
    <main>
     <header className="page-head"><div><div className="eyebrow">PAINEL DE PRODUÇÃO</div><h1>{t}</h1><p className="subtitle">{sub}</p></div></header>
     <ErroTela chave={tab}>
     <Suspense fallback={<p className="hint carregando-tela" role="status">Abrindo...</p>}>
     {tab==='inicio'?<InicioM/>:(()=>{ const T=TELAS[tab]; return <T/>; })()}
     </Suspense>
     </ErroTela>
     <footer>EstúdioClip • Use apenas vídeos próprios ou com autorização • Seus vídeos e chaves ficam neste navegador</footer>
    </main>
   </div>
   <div className="toasts" aria-live="polite">{toasts.map(x=><div key={x.id} className={'toast '+x.kind}>{x.kind==='ok'?<CheckCircle2 size={17}/>:x.kind==='erro'?<AlertTriangle size={17}/>:<Info size={17}/>}<span>{x.msg}</span><button onClick={()=>setToasts(t=>t.filter(y=>y.id!==x.id))} aria-label="Fechar"><X size={15}/></button></div>)}</div>
  </AppCtx.Provider>;
}
