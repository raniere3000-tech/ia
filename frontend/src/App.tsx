import ErroTela from './components/ErroTela';
import { Suspense, lazy, memo, useCallback, useEffect, useMemo, useRef, useState, type ComponentType } from 'react';
import { Home, Search, Clapperboard, CalendarClock, Captions, LayoutTemplate, Settings as Gear, Sparkles, Mic, Film, Bot, CheckCircle2, AlertTriangle, Info, X, Circle, ListChecks, Send, FolderOpen, Palette, CalendarRange, HelpCircle, Cloud, CloudOff, RefreshCw, ChevronDown } from 'lucide-react';
import { AppCtx, PROJETO_VAZIO, captionPresets, type Marca, type Projeto, type Settings, type Tab } from './state';
import { store } from './lib/store';
import { salvos, temCofre, cofreAberto, separar, atualizarCofre } from './lib/cofre';
import Cadeado from './components/Cadeado';
import { TEMPLATE_PADRAO, type Template } from './lib/render';
import { lerModelos, gravarModelos, enviarModelos, sincronizar, type Biblioteca, type Modelo } from './lib/modelos';
import Inicio from './pages/Inicio';
import { useTrabalhos } from './lib/gravador';
import { definirSessao } from './lib/api';
import Tour from './components/Tour';

// Cada aba é baixada só quando é aberta (a primeira tela abre mais rápido).
// Se o site foi atualizado com a aba aberta, o pedaço antigo some do servidor: recarrega uma vez para pegar a versão nova.
type Mod = Promise<{default:ComponentType}>;
const CARGA:Partial<Record<Tab,()=>Mod>> = {
  radar:()=>import('./pages/Radar'), cortes:()=>import('./pages/Cortes'), agendar:()=>import('./pages/Agendar'), agente:()=>import('./pages/Agente'), video:()=>import('./pages/VideoCodigo'), vozes:()=>import('./pages/Vozes'),
  manual:()=>import('./pages/Manual'), estilos:()=>import('./pages/Estilos'), templates:()=>import('./pages/Templates'), config:()=>import('./pages/Config'),
  ia:()=>import('./pages/CriarIA'), automatico:()=>import('./pages/Automatico'), projetos:()=>import('./pages/Projetos'), galeria:()=>import('./pages/Galeria'),
  fila:()=>import('./pages/Fila'), revisar:()=>import('./pages/Revisar'),
};
const seguro=(f:()=>Mod)=>()=>f().then(m=>{ try{ sessionStorage.removeItem('studio_recarregou'); }catch{ /* sem armazenamento */ } return m; },()=>{
  let ja=true; try{ ja=!!sessionStorage.getItem('studio_recarregou'); sessionStorage.setItem('studio_recarregou','1'); }catch{ /* sem armazenamento */ }
  if(!ja&&navigator.onLine){ location.reload(); return new Promise<{default:ComponentType}>(()=>{}); }
  throw new Error(navigator.onLine?'Não consegui abrir esta tela. Recarregue a página.':'Sem internet: esta tela ainda não foi baixada neste aparelho.'); });
const TELAS=Object.fromEntries(Object.entries(CARGA).map(([k,f])=>[k,memo(lazy(seguro(f)))])) as unknown as Record<Exclude<Tab,'inicio'>,ComponentType>;
const InicioM=memo(Inicio);
/** Abas de trabalho demorado: depois de abertas ficam vivas por trás, para a gravação e a geração continuarem enquanto você usa outra aba. */
const VIVAS:Tab[]=['cortes','video','vozes','manual'];
/** Começa a baixar a aba quando o dedo ou o mouse chega no botão. */
const adiantar=(t:Tab)=>{ CARGA[t]?.().catch(()=>{}); };

const SETTINGS_PADRAO:Settings = {ytKey:'',claudeKey:'',whisperModel:'onnx-community/whisper-base',idioma:'portuguese',api:'',legendaPadrao:'classico-contorno',efeitoPadrao:'seguir-rosto',servidor:'',servidorToken:'',servidorCanal:'',geminiKey:'',ia:''};
const NAV:[Tab,string,typeof Home][] = [['inicio','Início',Home],['video','Animado no navegador',Sparkles],['ia','Agente 3',Bot],['manual','Montagem manual',Film],['automatico','Vários de uma vez',CalendarRange],['projetos','Meus projetos',FolderOpen],
  ['vozes','Estúdio de vozes',Mic],['galeria','Estilos de animação',Palette],['templates','Templates',LayoutTemplate],['estilos','Legendas e efeitos',Captions],
  ['radar','Radar de vídeos',Search],['cortes','Gerar cortes',Clapperboard],['agente','Agentes 1, 2 e 3',Bot],['fila','Fila e aprovações',ListChecks],['revisar','Revisar vídeo',CheckCircle2],
  ['agendar','Agenda e contas',CalendarClock],['config','Ajustes',Gear]];
/** As cinco áreas (barra de baixo no celular, menu lateral no computador). A engrenagem fica fora delas. */
type AreaNav={id:string;nome:string;curto:string;Icon:typeof Home;abas:Tab[];extras?:[Tab,string][]};
const AREAS_NAV:AreaNav[] = [
  {id:'inicio',nome:'Início',curto:'Início',Icon:Home,abas:['inicio']},
  {id:'criar',nome:'Criar vídeos',curto:'Criar',Icon:Clapperboard,abas:['ia','automatico','video','manual','projetos','vozes','galeria','templates','estilos']},
  {id:'radar',nome:'Radar e cortes',curto:'Radar',Icon:Search,abas:['radar','cortes','agente']},
  {id:'fila',nome:'Fila e aprovações',curto:'Fila',Icon:ListChecks,abas:['fila','revisar']},
  {id:'posts',nome:'Publicações',curto:'Posts',Icon:Send,abas:['agendar','agente'],extras:[['agente','Agente 2 (postagem)']]},
];
/** Os quatro modos de criar ficam juntos no topo da área Criar. */
const MODOS:Tab[]=['ia','automatico','video','manual'];
const OCULTAS:Tab[]=['revisar'];
const areaDe=(t:Tab,pref='')=>AREAS_NAV.find(a=>a.id===pref&&a.abas.includes(t))||AREAS_NAV.find(a=>a.abas.includes(t))||AREAS_NAV[0];
const lerRota=():[Tab,string]=>{ const [h,...r]=decodeURIComponent(location.hash.slice(1)).split('/'); return NAV.some(n=>n[0]===h)?[h as Tab,r.join('/')]:['inicio','']; };
const TITLES:Record<Tab,[string,string]> = {
  inicio:['Bem-vindo ao EstúdioClip','Escreva um assunto e o celular faz o vídeo. Daqui você também acompanha o que está pronto para aprovar.'],
  radar:['Descubra vídeos em alta','Pesquise qualquer nicho no YouTube e encontre canais e vídeos com muitas visualizações.'],
  cortes:['Transforme vídeos em cortes','Envie um vídeo seu (ou autorizado), escolha a duração e receba os melhores trechos com nota.'],
  vozes:['Estúdio de vozes','Crie personagens, teste e compare vozes do Gemini, aplique no roteiro e baixe o áudio pronto para o vídeo.'],
  manual:['Montagem manual','Mande as imagens dos quadros, a narração, a trilha e os efeitos. O site lê o roteiro de quadros, sincroniza tudo e grava o vídeo.'],
  video:['Criar vídeo animado','Digite um tema: a IA escreve o roteiro e o site monta um vídeo vertical animado, com narração e batida, pronto para postar.'],
  agendar:['Agendar posts','Conecte suas contas uma vez e agende os cortes no YouTube, Instagram, Facebook e TikTok. O Kwai fica com o botão de baixar.'],
  agente:['Seus agentes','Três agentes trabalham sozinhos no celular: o Agente 1 faz cortes, o Agente 2 agenda e posta, o Agente 3 cria vídeos originais com IA. Você aprova e recebe tudo por e-mail.'],
  estilos:['Legendas e efeitos','Escolha o visual padrão das legendas e o efeito aplicado nos cortes.'],
  templates:['Templates','Modelos de vídeo usados na edição manual e pelos agentes: composição, legenda, tarjas, marca e exportação.'],
  config:['Ajustes','Servidor do celular, aparelhos conectados, chaves, e-mail, backups e tutorial.'],
  ia:['Agente 3: vídeos com IA','Escreva o assunto e o Agente 3 faz o vídeo no celular. Se preferir, veja e edite o roteiro antes.'],
  automatico:['Vários vídeos de uma vez','O celular faz vários vídeos sozinho: agora, em data marcada ou todo dia na hora que você escolher.'],
  projetos:['Meus projetos','Tudo o que está salvo no servidor do celular, com versões. Daqui você também envia os dados deste navegador.'],
  galeria:['Estilos de animação','Veja como fica cada visual antes de escolher. Os marcados como prontos já funcionam no celular.'],
  fila:['Fila e aprovações','O que o servidor está fazendo, o que vem depois e os vídeos esperando a sua decisão.'],
  revisar:['Revisar vídeo','Assista, confira e decida: aprovar, pedir correção ou rejeitar.'],
};

export default function App(){
  const [settings,setS]=useState<Settings>(()=>{ const saved=salvos(); return {...SETTINGS_PADRAO,...saved,ytKey:saved.ytKey||(temCofre()?'':store.get('studio_yt_key'))||''}; });
  const [trancado,setTrancado]=useState(()=>temCofre()&&!cofreAberto());
  const setSettings=useCallback((p:Partial<Settings>)=>setS(s=>{ const n={...s,...p};
    // Com o cofre ligado, as chaves nunca vão em texto puro para o armazenamento do navegador.
    if(temCofre()){ store.setJson('studio_settings',separar(n).publico); atualizarCofre(n); } else store.setJson('studio_settings',n);
    return n; }),[]);
  definirSessao(settings.servidorSessao||'');
  const [tab,setTab]=useState<Tab>(()=>lerRota()[0]);
  const [rotaExtra,setExtra]=useState(()=>lerRota()[1]);
  const [areaPref,setAreaPref]=useState('');
  const [abertas,setAbertas]=useState<Tab[]>(()=>VIVAS.includes(tab)?[tab]:[]);
  const go=useCallback((t:Tab,extra='',area='')=>{ setTab(t); setExtra(extra); setAreaPref(area); if(VIVAS.includes(t)) setAbertas(a=>a.includes(t)?a:[...a,t]);
    const novo='#'+t+(extra?'/'+encodeURIComponent(extra):''); if(location.hash!==novo) history.pushState(null,'',novo); window.scrollTo({top:0}); },[]);
  // Voltar e avançar do navegador trocam de tela.
  useEffect(()=>{ const f=()=>{ if(/^#(senha|par)=/.test(location.hash)) return; const [t,x]=lerRota(); setTab(t); setExtra(x); if(VIVAS.includes(t)) setAbertas(a=>a.includes(t)?a:[...a,t]); };
    addEventListener('popstate',f); addEventListener('hashchange',f); return ()=>{ removeEventListener('popstate',f); removeEventListener('hashchange',f); }; },[]);
  useEffect(()=>{ if(VIVAS.includes(tab)) setAbertas(a=>a.includes(tab)?a:[...a,tab]); },[tab]);
  const vivas=useRef<HTMLDivElement>(null);
  // Ao sair de uma aba que fica viva: param as prévias e os players dela (as gravações continuam).
  useEffect(()=>()=>{ if(!VIVAS.includes(tab)) return; window.dispatchEvent(new CustomEvent('estudioclip-saiu',{detail:tab}));
    vivas.current?.querySelectorAll<HTMLMediaElement>(`[data-tela="${tab}"] video, [data-tela="${tab}"] audio`).forEach(m=>{ try{ m.pause(); }catch{ /* ignora */ } }); },[tab]);
  const trabalhos=useTrabalhos().split(',');
  const [toasts,setToasts]=useState<{id:number;msg:string;kind:string}[]>([]);
  const toast=useCallback((msg:string,kind:'ok'|'erro'|'info'='info')=>{ const id=Date.now()+Math.random(); setToasts(t=>[...t.slice(-2),{id,msg,kind}]); setTimeout(()=>setToasts(t=>t.filter(x=>x.id!==id)),kind==='erro'?9000:5500); },[]);
  const [projeto,setP]=useState<Projeto>(PROJETO_VAZIO);
  const setProjeto=useCallback((f:(p:Projeto)=>Projeto)=>setP(f),[]);
  const [template,setT]=useState<Template>(()=>({...TEMPLATE_PADRAO,...store.json<Partial<Template>>('studio_template',{})}));
  const setTemplate=useCallback((t:Template)=>{ setT(t); store.setJson('studio_template',t); },[]);
  // Biblioteca de templates: guardada aqui e, com o servidor ligado, também lá (os agentes usam a mesma).
  const [bib,setBib]=useState<Biblioteca>(lerModelos);
  const [modelosSinc,setSinc]=useState<'local'|'servidor'|'erro'>('local');
  const srvRef=useRef({servidor:settings.servidor,servidorToken:settings.servidorToken}); srvRef.current={servidor:settings.servidor,servidorToken:settings.servidorToken};
  const envio=useRef(0);
  const setModelos=useCallback((ms:Modelo[])=>{
    const b={atualizado:Date.now()/1000,modelos:ms}; setBib(b);
    if(!gravarModelos(b)) toast('Não coube neste navegador (logo grande demais?). Use um logo menor.','erro');
    clearTimeout(envio.current);
    if(srvRef.current.servidor) envio.current=window.setTimeout(()=>{ enviarModelos(srvRef.current,b,captionPresets).then(()=>setSinc('servidor')).catch(()=>setSinc('erro')); },700);
  },[toast]);
  useEffect(()=>{
    if(!settings.servidor){ setSinc('local'); return; }
    let vivo=true;
    sincronizar({servidor:settings.servidor,servidorToken:settings.servidorToken},lerModelos(),captionPresets)
      .then(b=>{ if(!vivo) return; setBib(b); gravarModelos(b); setSinc('servidor'); }).catch(()=>{ if(vivo) setSinc('erro'); });
    return ()=>{ vivo=false; };
  },[settings.servidor,settings.servidorToken]);
  const modelos=bib.modelos;
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
    // Link de pareamento (?servidor=...&canal=...#par=CÓDIGO): código de uso único, a senha não vai no link.
    const par=/^#par=([A-Za-z0-9-]{8,10})$/.exec(location.hash);
    if(par){
      history.replaceState(null,'',location.pathname+'#inicio');
      const url=(srv||'').replace(/\/+$/,'');
      if(!/^https:\/\/[a-z0-9.-]+(:\d+)?$|^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(url)){ toast('Este link de conexão não tem o endereço do servidor. Gere outro no aparelho já conectado (Ajustes > Aparelhos).','erro'); return; }
      const atual0=salvos();
      if(atual0.servidor&&atual0.servidor!==url&&!window.confirm('Este link quer ligar o aplicativo a um servidor DIFERENTE do que você usa hoje.\n\nSó aceite se o link foi gerado pelo SEU servidor. Ligar a este servidor?')) return;
      (async()=>{
        try{ const {parear}=await import('./lib/api'); const s=await parear(url,par[1]);
          setSettings({servidor:url,servidorSessao:s.sessao,servidorAnuncio:s.anuncio,servidorCanal:canalQ||atual0.servidorCanal||'',servidorToken:''});
          toast(`Aparelho conectado ao servidor do celular como "${s.nome}".`,'ok'); }
        catch(e){ toast('Não consegui conectar: '+(e instanceof Error?e.message:String(e)),'erro'); }
      })();
      return;
    }
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
      if(canal){ const u=await enderecoDoCanal(canal,senha,atual.servidor||'',atual.servidorAnuncio||'').catch(()=>null); if(u) url=u; }
      if(!url){ if(doLink) toast('O servidor do celular ainda não avisou o endereço. Ligue o servidor no Termux e abra o link de novo.','erro'); return; }
      if(!doLink&&url===atual.servidor) return;
      try{
        await testarServidor(url,senha);
        setSettings(senhaLink?{servidor:url,servidorToken:senha,servidorCanal:canal}:{servidor:url,servidorCanal:canal});
        toast(doLink?'Servidor do celular conectado! Guarde este link: ele funciona sempre.':'Servidor do celular reconectado no endereço novo.','ok');
      }catch(e){ if(doLink) toast('Não consegui conectar ao servidor do link: '+(e instanceof Error?e.message:String(e)),'erro'); }
    })();
  },[setSettings,toast]);
  // Salvar no servidor: uma passada a cada 25 s e quando a aba fica em segundo plano.
  const [sincR,setSincR]=useState<{situacao:string;avisos:{area:string;tipo:string;titulo:string}[];detalhe?:string}>({situacao:'desligado',avisos:[]});
  const rodando=useRef(false);
  const passar=useCallback((forcar:string[]=[])=>{
    if(!settings.servidor||rodando.current) return;
    rodando.current=true;
    import('./lib/sincronia').then(async m=>{ if(!m.lerEstado().ligado){ setSincR({situacao:'desligado',avisos:[]}); return; }
      setSincR(r=>({...r,situacao:'sincronizando'}));
      const r=await m.sincronizar({servidor:settings.servidor,servidorToken:settings.servidorToken},undefined,forcar as never[]); setSincR(r); })
      .catch(e=>setSincR({situacao:'erro',avisos:[],detalhe:String(e)})).finally(()=>{ rodando.current=false; });
  },[settings.servidor,settings.servidorToken]);
  useEffect(()=>{
    if(!settings.servidor){ setSincR({situacao:'desligado',avisos:[]}); return; }
    const t0=setTimeout(()=>passar(),4000); const iv=setInterval(()=>passar(),25000);
    const vis=()=>{ if(document.visibilityState==='hidden') passar(); };
    const on=()=>passar(); document.addEventListener('visibilitychange',vis); addEventListener('online',on);
    return ()=>{ clearTimeout(t0); clearInterval(iv); document.removeEventListener('visibilitychange',vis); removeEventListener('online',on); };
  },[settings.servidor,passar]);
  const sinc=useMemo(()=>({...sincR,passar}),[sincR,passar]);
  const ctx=useMemo(()=>({settings,setSettings,tab,go,rotaExtra,sinc,toast,projeto,setProjeto,template,setTemplate,modelos,setModelos,modelosSinc,linkRef,setLinkRef,marcas,setMarcas}),[settings,setSettings,tab,go,rotaExtra,sinc,toast,projeto,setProjeto,template,setTemplate,modelos,setModelos,modelosSinc,linkRef,marcas,setMarcas]);
  const area=areaDe(tab,areaPref);
  const [aberto,setAberto]=useState<string>('');
  const [tourAberto,setTour]=useState(false);
  useEffect(()=>{ const f=()=>setTour(true); addEventListener('estudio:tour',f); return ()=>removeEventListener('estudio:tour',f); },[]);
  const resolver=async(a:string,manterAqui:boolean)=>{
    const m=await import('./lib/sincronia');
    try{ if(manterAqui){ passar([a]); toast('A versão deste aparelho vai para o servidor. A outra continua nas versões do projeto.','ok'); }
      else{ await m.trazerDoServidor({servidor:settings.servidor,servidorToken:settings.servidorToken},a as never); toast('Versão do servidor carregada. Recarregando...','ok'); setTimeout(()=>location.reload(),700); } }
    catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }
  };
  const SIT:Record<string,[string,string]>={desligado:['Só neste aparelho','muted'],sincronizando:['Sincronizando','info'],salvo:['Salvo no servidor','ok'],offline:['Offline: salvo localmente','warn'],conflito:['Conflito entre versões','bad'],erro:['Erro ao salvar','bad']};
  const [sitTexto,sitCls]=SIT[sincR.situacao]||SIT.desligado;
  const status=[{ok:!!settings.ytKey,label:'Radar (YouTube)',opt:false},{ok:true,label:'Cortes e exportação',opt:false},{ok:!!(settings.claudeKey||settings.geminiKey),label:'Notas com IA',opt:true},{ok:!!settings.servidor,label:'Cortes pelo link',opt:true}];
  const [t,sub]=TITLES[tab];
  return <AppCtx.Provider value={ctx}>
   {trancado&&<Cadeado aoAbrir={seg=>{ setS(s=>({...s,...seg})); setTrancado(false); }} aoPular={()=>setTrancado(false)}/>}
   <div className="app">
    <aside className="sidebar" aria-label="Menu">
     <div className="brand"><span className="brand-icon"><Clapperboard size={22}/></span><div><strong>ESTÚDIO<span>CLIP</span></strong><small>CRIAR • CORTAR • PUBLICAR</small></div></div>
     <nav className="areas">{AREAS_NAV.map(a=>{ const ativa=area.id===a.id; const expandida=ativa||aberto===a.id; const subs=a.abas.filter(t=>!OCULTAS.includes(t)&&t!=='inicio');
      const ocupado=a.abas.some(t=>trabalhos.includes(t));
      return <div key={a.id} className={'area-grupo'+(ativa?' ativa':'')}>
       <button className={'nav area-btn '+(ativa?'active':'')} data-tour={'area-'+a.id} aria-current={ativa?'page':undefined}
        onClick={()=>{ if(ativa&&subs.length){ setAberto(x=>x===a.id?'':a.id); return; } go(a.abas[0],'',a.id); setAberto(''); }}
        onPointerEnter={()=>adiantar(a.abas[0])} title={a.nome}>
        <a.Icon size={18}/><span>{a.nome}</span><b className="nav-curto" aria-hidden="true">{a.curto}</b>
        {a.id==='radar'&&projeto.clips.length>0&&<em className="nav-badge">{projeto.clips.filter(c=>!c.descartado).length}</em>}
        {ocupado&&<i className="nav-ocupado" role="status" aria-label="Trabalhando" title="Trabalhando"/>}
        {subs.length>1&&<ChevronDown size={14} className={'nav-seta'+(expandida?' aberta':'')} aria-hidden="true"/>}
       </button>
       {expandida&&subs.length>1&&<div className="nav-subs">{subs.map(t=>{ const [,label,Icon]=NAV.find(n=>n[0]===t)!; const nome=a.extras?.find(x=>x[0]===t)?.[1]||label;
         return <button key={t} className={'nav sub '+(tab===t&&ativa?'active':'')} onClick={()=>go(t,'',a.id)} onPointerEnter={()=>adiantar(t)}><Icon size={15}/><span>{nome}</span>{trabalhos.includes(t)&&<i className="nav-ocupado" aria-hidden="true"/>}</button>; })}</div>}
      </div>; })}</nav>
     <div className="sidebar-bottom">
      <button className={'nav '+(tab==='config'?'active':'')} data-tour="ajustes" onClick={()=>go('config')}><Gear size={18}/><span>Ajustes</span></button>
      <button className="nav" onClick={()=>setTour(true)}><HelpCircle size={18}/><span>Tutorial</span></button>
      <div className="side-title">STATUS</div>
      {status.map(s=><button key={s.label} className={'status-row '+(s.ok?'ok':s.opt?'opt':'no')} onClick={()=>go('config')}>{s.ok?<CheckCircle2 size={14}/>:<Circle size={14}/>}<span>{s.label}</span><small>{s.ok?'pronto':s.opt?'opcional':'falta chave'}</small></button>)}
     </div>
    </aside>
    <main>
     <div className="topo-movel"><span className="brand-mini"><Clapperboard size={18}/> ESTÚDIO<b>CLIP</b></span>
      <button className={'sinc-chip '+sitCls} onClick={()=>go('projetos')} title={sincR.detalhe||sitTexto}>{sincR.situacao==='offline'?<CloudOff size={14}/>:sincR.situacao==='sincronizando'?<RefreshCw size={14} className="spin"/>:<Cloud size={14}/>}<span>{sitTexto}</span></button>
      <button className="icon-btn" onClick={()=>setTour(true)} aria-label="Tutorial"><HelpCircle size={19}/></button>
      <button className="icon-btn" data-tour="ajustes-movel" onClick={()=>go('config')} aria-label="Ajustes"><Gear size={19}/></button></div>
     <header className="page-head"><div><div className="eyebrow">{area.id==='inicio'?'PAINEL DE PRODUÇÃO':area.nome.toUpperCase()}{(()=>{ const sub=area.extras?.find(x=>x[0]===tab)?.[1]||NAV.find(n=>n[0]===tab)?.[1]||''; return area.id!=='inicio'&&tab!=='config'&&sub&&sub!==area.nome?<> › {sub.toUpperCase()}</>:null; })()}</div><h1>{t}</h1><p className="subtitle">{sub}</p></div>
      <button className={'sinc-chip grande '+sitCls} onClick={()=>go('projetos')} title={sincR.detalhe||sitTexto}>{sincR.situacao==='offline'?<CloudOff size={15}/>:sincR.situacao==='sincronizando'?<RefreshCw size={15} className="spin"/>:<Cloud size={15}/>}<span>{sitTexto}</span></button></header>
     {sincR.avisos.length>0&&<div className="sinc-avisos">{sincR.avisos.map(a=><div key={a.area} className={'note-bar '+(a.tipo==='conflito'?'bad':'')}>
      {a.tipo==='conflito'?<><AlertTriangle size={16}/><span><b>Conflito em {a.titulo}:</b> outro aparelho salvou uma versão diferente. Escolha qual fica (a outra continua guardada nas versões do projeto).</span>
        <button className="subtle sm" onClick={()=>resolver(a.area,false)}>Usar a do servidor</button><button className="primary sm" onClick={()=>resolver(a.area,true)}>Manter a deste aparelho</button></>
      :<><Info size={16}/><span><b>{a.titulo}</b> mudou em outro aparelho.</span><button className="primary sm" onClick={()=>resolver(a.area,false)}>Carregar a versão nova</button></>}
     </div>)}</div>}
     {area.id!=='inicio'&&tab!=='config'&&<div className="sub-abas" role="tablist" aria-label={area.nome}>
      {area.id==='criar'&&<div className="modos">{MODOS.map(m=>{ const [,label,Icon]=NAV.find(n=>n[0]===m)!; return <button key={m} role="tab" aria-selected={tab===m} className={'modo '+(tab===m?'active':'')} onClick={()=>go(m,'',area.id)} onPointerEnter={()=>adiantar(m)}><Icon size={15}/> {label}</button>; })}</div>}
      <div className="chips-abas">{area.abas.filter(x=>!OCULTAS.includes(x)&&!(area.id==='criar'&&MODOS.includes(x))).filter((_x,_i,l)=>l.length>1).map(x=>{ const [,label,Icon]=NAV.find(n=>n[0]===x)!; const nome=area.extras?.find(e=>e[0]===x)?.[1]||label;
        return <button key={x} role="tab" aria-selected={tab===x} className={'chip-aba '+(tab===x?'active':'')} onClick={()=>go(x,'',area.id)} onPointerEnter={()=>adiantar(x)}><Icon size={14}/> {nome}</button>; })}</div>
     </div>}
     <div ref={vivas} style={{display:'contents'}}>{abertas.map(k=>{ const T=TELAS[k as Exclude<Tab,'inicio'>]; return <div key={k} data-tela={k} style={{display:tab===k?'contents':'none'}}>
      <ErroTela chave={k}><Suspense fallback={<p className="hint carregando-tela" role="status">Abrindo...</p>}><T/></Suspense></ErroTela></div>; })}</div>
     {!VIVAS.includes(tab)&&<ErroTela chave={tab}>
     <Suspense fallback={<p className="hint carregando-tela" role="status">Abrindo...</p>}>
     {tab==='inicio'?<InicioM/>:(()=>{ const T=TELAS[tab]; return <T/>; })()}
     </Suspense>
     </ErroTela>}
     <footer>EstúdioClip • Use apenas vídeos próprios ou com autorização • As chaves ficam neste navegador ou no seu servidor</footer>
    </main>
   </div>
   <Tour aberto={tourAberto} fechar={()=>setTour(false)} abrir={()=>setTour(true)} go={(t:Tab)=>go(t)} naInicio={tab==='inicio'}/>
   <div className="toasts" aria-live="polite">{toasts.map(x=><div key={x.id} className={'toast '+x.kind}>{x.kind==='ok'?<CheckCircle2 size={17}/>:x.kind==='erro'?<AlertTriangle size={17}/>:<Info size={17}/>}<span>{x.msg}</span><button onClick={()=>setToasts(t=>t.filter(y=>y.id!==x.id))} aria-label="Fechar"><X size={15}/></button></div>)}</div>
  </AppCtx.Provider>;
}
