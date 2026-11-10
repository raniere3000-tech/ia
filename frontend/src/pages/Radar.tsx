import { useMemo, useState } from 'react';
import { Search, RefreshCcw, ExternalLink, Bookmark, X, KeyRound, Loader2, Users, PlaySquare, Scissors } from 'lucide-react';
import { useApp } from '../state';
import { HelpButton } from '../components/Help';
import { radarDireto, canaisDe, ordenar, testarChaveYouTube, type Video, type Canal, type RadarParams } from '../lib/radar';
import { store, fmt, tm } from '../lib/store';

const NICHOS:[string,string][] = [['Todos os nichos',''],['Games e lives','gameplay'],['Podcasts e entrevistas','podcast entrevista'],['Humor','humor comédia'],['Esportes','esportes'],['Tecnologia e IA','tecnologia inteligência artificial'],['Educação e curiosidades','curiosidades'],['Ciência','ciência'],['História','história'],['Finanças e negócios','finanças investimentos'],['Empreendedorismo','empreendedorismo'],['Saúde e bem-estar','saúde bem-estar'],['Culinária','receita culinária'],['Viagens','viagem'],['Música','música'],['Cinema e séries','filmes séries'],['Cultura pop','cultura pop'],['Automóveis','carros'],['Beleza e moda','beleza moda'],['Notícias e análise','notícias análise']];
type Filtros = {nicho:string;tema:string;dias:number;views:number;minutos:number;ordem:string;regiao:string;idioma:string};
type Salva = {nome:string;f:Filtros};
const PADRAO:Filtros = {nicho:'Todos os nichos',tema:'',dias:30,views:100000,minutos:20,ordem:'velocidade',regiao:'BR',idioma:'pt'};
const PRESET_GTA:Salva = {nome:'Radar GTA — teste',f:{...PADRAO,tema:'GTA'}};

export default function Radar(){
  const {settings,setSettings,go,toast,setLinkRef}=useApp();
  const [f,setF]=useState<Filtros>(PADRAO);
  const set=(p:Partial<Filtros>)=>setF(x=>({...x,...p}));
  const [salvas,setSalvas]=useState<Salva[]>(()=>store.json('studio_radar_salvas',[PRESET_GTA]));
  const persist=(s:Salva[])=>{ setSalvas(s); store.setJson('studio_radar_salvas',s); };
  const [videos,setVideos]=useState<Video[]>([]); const [canais,setCanais]=useState<Canal[]>([]);
  const [aba,setAba]=useState<'videos'|'canais'>('videos');
  const [loading,setLoading]=useState(false); const [buscou,setBuscou]=useState(false); const [coleta,setColeta]=useState('');
  const [chave,setChave]=useState('');
  const ordenados=useMemo(()=>ordenar(videos,f.ordem),[videos,f.ordem]);

  async function pesquisar(){
    if(!settings.ytKey){ toast('Cole a chave do YouTube para pesquisar.','erro'); return; }
    const nichoQ=NICHOS.find(n=>n[0]===f.nicho)?.[1]||'';
    const tema=[f.tema.trim(),nichoQ].filter(Boolean).join(' ');
    const p:RadarParams={tema,dias:f.dias,views:f.views,minutos:f.minutos,ordem:f.ordem,regiao:f.regiao,idioma:f.idioma};
    setLoading(true); setBuscou(true);
    try{
      const v=await radarDireto(settings.ytKey,p); setVideos(v); setColeta(new Date().toLocaleString('pt-BR'));
      setCanais(v.length? await canaisDe(settings.ytKey,v):[]);
      if(!v.length) toast('Nenhum vídeo passou nos filtros. Tente ampliar o período ou reduzir as views mínimas.','info');
    }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); setVideos([]); setCanais([]); }
    finally{ setLoading(false); }
  }
  function salvar(){
    const nome=[f.tema,f.nicho!=='Todos os nichos'?f.nicho:'',`${f.dias===3650?'sempre':f.dias+'d'}`].filter(Boolean).join(' • ');
    persist([...salvas.filter(s=>s.nome!==nome),{nome,f}]); toast('Pesquisa salva.','ok');
  }
  const usar=(link:string)=>{ setLinkRef(link); go('cortes'); toast('Link anotado como referência. Para gerar cortes, envie o arquivo do vídeo (seu ou autorizado).'); };

  if(!settings.ytKey) return <section className="panel setup-callout">
   <span className="setup-icon"><KeyRound size={26}/></span>
   <h2>Para usar o Radar, cole sua chave do YouTube</h2>
   <p>É gratuita e leva uns 5 minutos. Clique no botão de ajuda para ver o passo a passo com links diretos.</p>
   <div className="key-row narrow"><div className="input-wrap"><KeyRound size={16}/><input type="password" value={chave} onChange={e=>setChave(e.target.value)} placeholder="Cole aqui a chave (começa com AIza...)" autoComplete="off"/></div>
   <button className="primary" disabled={!chave.trim()} onClick={async()=>{ try{ await testarChaveYouTube(chave.trim()); setSettings({ytKey:chave.trim()}); toast('Chave salva! Já pode pesquisar.','ok'); }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); } }}>Testar e salvar</button></div>
   <HelpButton topic="youtube" label="Como conseguir a chave do YouTube"/>
  </section>;

  return <>
   <section className="panel">
    <div className="section-head"><h2><Search size={18}/> O que você quer encontrar?</h2><span>Dados públicos do YouTube</span></div>
    <div className="chips">{NICHOS.map(([n])=><button key={n} className={'chip '+(f.nicho===n?'on':'')} onClick={()=>set({nicho:n})}>{n}</button>)}</div>
    <div className="filter-grid">
     <label className="wide">Palavra-chave (opcional)<input placeholder="Ex.: GTA, entrevista com atleta, futebol, ciência..." value={f.tema} onChange={e=>set({tema:e.target.value})} onKeyDown={e=>{if(e.key==='Enter')pesquisar()}}/></label>
     <label>Publicados nos últimos<select value={f.dias} onChange={e=>set({dias:+e.target.value})}><option value={7}>7 dias</option><option value={30}>30 dias</option><option value={90}>90 dias</option><option value={365}>1 ano</option><option value={3650}>Qualquer período</option></select></label>
     <label>Views mínimas<select value={f.views} onChange={e=>set({views:+e.target.value})}><option value={0}>Qualquer</option><option value={10000}>10 mil</option><option value={100000}>100 mil</option><option value={500000}>500 mil</option><option value={1000000}>1 milhão</option><option value={5000000}>5 milhões</option></select></label>
     <label>Duração do vídeo<select value={f.minutos} onChange={e=>set({minutos:+e.target.value})}><option value={0}>Qualquer</option><option value={4}>Mais de 4 min</option><option value={10}>Mais de 10 min</option><option value={20}>Mais de 20 min</option><option value={40}>Mais de 40 min</option></select></label>
     <label><span className="label-row">Ordenar por <HelpButton topic="velocidade"/></span><select value={f.ordem} onChange={e=>set({ordem:e.target.value})}><option value="velocidade">Views por dia (média)</option><option value="views">Total de views</option><option value="recentes">Mais recentes</option><option value="engajamento">Engajamento (likes+comentários/views)</option></select></label>
     <label>País<select value={f.regiao} onChange={e=>set({regiao:e.target.value})}><option value="BR">Brasil</option><option value="PT">Portugal</option><option value="US">Estados Unidos</option><option value="">Qualquer</option></select></label>
     <label>Idioma<select value={f.idioma} onChange={e=>set({idioma:e.target.value})}><option value="pt">Português</option><option value="en">Inglês</option><option value="es">Espanhol</option><option value="">Qualquer</option></select></label>
    </div>
    <div className="actions"><button className="primary lg" onClick={pesquisar} disabled={loading}>{loading?<Loader2 size={17} className="spin"/>:<Search size={17}/>}{loading?'Pesquisando...':'Pesquisar'}</button><button className="subtle" onClick={salvar}><Bookmark size={16}/> Salvar pesquisa</button><button className="subtle" onClick={()=>setF(PADRAO)}><RefreshCcw size={16}/> Restaurar filtros gerais</button></div>
    {salvas.length>0&&<div className="saved"><span>Pesquisas salvas:</span>{salvas.map(s=><span key={s.nome} className="saved-chip"><button onClick={()=>{setF(s.f);toast(`Filtros de “${s.nome}” aplicados. Clique em Pesquisar.`)}}>{s.nome}</button><button aria-label="Apagar" onClick={()=>persist(salvas.filter(x=>x.nome!==s.nome))}><X size={12}/></button></span>)}</div>}
   </section>

   <section className="results">
    <div className="section-head"><div className="tabs"><button className={aba==='videos'?'on':''} onClick={()=>setAba('videos')}><PlaySquare size={15}/> Vídeos <span className="count">{videos.length}</span></button><button className={aba==='canais'?'on':''} onClick={()=>setAba('canais')}><Users size={15}/> Canais <span className="count">{canais.length}</span></button></div>{coleta&&<span>Coletado em {coleta}</span>}</div>
    {!buscou?<div className="empty"><Search size={34}/><strong>Escolha um nicho e clique em Pesquisar</strong><p>Os resultados mostram views, views por dia, duração e data de publicação.</p></div>
    :loading?<div className="empty"><Loader2 size={30} className="spin"/><strong>Buscando no YouTube...</strong></div>
    :aba==='videos'?(ordenados.length?<div className="video-grid">{ordenados.map(v=><article className="video-card" key={v.id}>
      <a href={v.link} target="_blank" rel="noreferrer" className="thumb"><img src={v.thumbnail} alt="" loading="lazy"/><span className="dur">{tm(v.duracao_segundos)}</span></a>
      <div className="video-body"><h3 title={v.titulo}>{v.titulo}</h3><a className="channel" href={v.link_canal} target="_blank" rel="noreferrer">{v.canal} <ExternalLink size={12}/></a>
       <div className="metrics"><span>▶ {v.views===null?'Não informado':fmt(v.views)+' views'}</span><span>⚡ {v.velocidade===null?'Não informado':fmt(v.velocidade)+'/dia'}</span><span>📅 {new Date(v.publicado).toLocaleDateString('pt-BR')}</span></div>
       <div className="card-actions"><a className="subtle sm" href={v.link} target="_blank" rel="noreferrer"><ExternalLink size={13}/> Assistir</a><button className="action-link" onClick={()=>usar(v.link)}><Scissors size={13}/> Abrir em Gerar cortes</button></div></div></article>)}</div>
      :<div className="empty"><Search size={30}/><strong>Nenhum vídeo encontrado</strong><p>Amplie o período, reduza as views mínimas ou mude a duração.</p></div>)
    :(canais.length?<div className="channel-list">{canais.map(c=><article key={c.id} className="channel-row">{c.thumbnail?<img src={c.thumbnail} alt=""/>:<span className="avatar"><Users size={18}/></span>}<div className="grow"><a href={c.link} target="_blank" rel="noreferrer"><strong>{c.nome}</strong> <ExternalLink size={12}/></a><small>{c.inscritos===null?'Inscritos: não informado':fmt(c.inscritos)+' inscritos'} • {c.videos} vídeo(s) nesta pesquisa • {fmt(c.views)} views somadas</small><small className="muted">Destaque: {c.melhor.titulo}</small></div><a className="subtle sm" href={c.melhor.link} target="_blank" rel="noreferrer">Ver destaque</a></article>)}</div>
      :<div className="empty"><Users size={30}/><strong>Nenhum canal</strong></div>)}
   </section>
  </>;
}
