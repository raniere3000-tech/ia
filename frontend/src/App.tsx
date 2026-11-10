import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Search, Clapperboard, Captions, Sparkles, Download, Settings, ExternalLink, RefreshCcw, CheckCircle2, AlertTriangle, Play, Square, FileText } from 'lucide-react';
import presets from '../../config/presets.json';
import { radarDireto, type Video } from './lib/radar';
import { analisarNoNavegador, type Clip } from './lib/analyze';
import { parseLegendas, type Cue, type Preset } from './lib/captions';
import { drawFrame, exportarCorte, formatoSuportado, W, H } from './lib/render';
import './style.css';

type Job = {id:string;status:string;progresso:number;erro?:string;tem_legendas:boolean;cortes:Clip[]};
const niches=['Todos os nichos','Games e lives','Podcasts e entrevistas','Humor','Esportes','Tecnologia e IA','Educação','Ciência','História','Finanças','Empreendedorismo','Culinária','Viagens','Música','Cinema e séries','Cultura pop','Automóveis','Beleza e moda','Notícias'];
const store = {
  get:(k:string)=>{try{return localStorage.getItem(k)}catch{return null}},
  set:(k:string,v:string)=>{try{localStorage.setItem(k,v)}catch{/* armazenamento indisponível */}},
};
const defaultAPI = store.get('studio_api') || '';
const fmt = (n:number)=>Intl.NumberFormat('pt-BR').format(n);
const tm = (s:number)=>`${Math.floor(s/60)}:${Math.floor(s%60).toString().padStart(2,'0')}`;
const allPresets = presets.presets as unknown as Preset[];
const captionPresets = allPresets.filter(p=>p.tipo==='legenda');
const effectPresets = allPresets.filter(p=>p.tipo==='efeito');
// Estilos que o servidor Python consegue renderizar (o navegador renderiza todos).
const serverCaptions=['classico-contorno','minimal-branco','podcast-clean','legenda-caixa','karaoke-amarelo'];

export default function App(){
 const [tab,setTab]=useState<'radar'|'estudio'|'modelos'|'config'>('radar');
 const [api,setApi]=useState(defaultAPI); const [online,setOnline]=useState(false);
 const [ytKey,setYtKey]=useState(store.get('studio_yt_key')||'');
 const [niche,setNiche]=useState('Todos os nichos');const [topic,setTopic]=useState('');
 const [days,setDays]=useState(30);const [views,setViews]=useState(100000);const [duration,setDuration]=useState(20);const [order,setOrder]=useState('velocidade');
 const [list,setList]=useState<Video[]>([]);const [loading,setLoading]=useState(false);const [message,setMessage]=useState('');
 const [source,setSource]=useState('');const [file,setFile]=useState<File|null>(null);const [rights,setRights]=useState(false);
 const [minLen,setMinLen]=useState(30);const [maxLen,setMaxLen]=useState(60);const [limit,setLimit]=useState(15);const [minimum,setMinimum]=useState(3);const [job,setJob]=useState<Job|null>(null);
 const [preset,setPreset]=useState('classico-contorno');const [effect,setEffect]=useState('blur-background');const [rendering,setRendering]=useState('');const [renderPct,setRenderPct]=useState(0);
 const [cues,setCues]=useState<Cue[]>([]);const [cueName,setCueName]=useState('');const [hook,setHook]=useState('');
 const [previewing,setPreviewing]=useState('');
 const local = !online; // sem servidor: tudo roda no navegador
 const videoUrl = useMemo(()=>file?URL.createObjectURL(file):'',[file]);
 useEffect(()=>()=>{ if(videoUrl) URL.revokeObjectURL(videoUrl); },[videoUrl]);
 const pv = useRef<HTMLVideoElement>(null); const pc = useRef<HTMLCanvasElement>(null); const small = useRef<HTMLCanvasElement|null>(null);
 const stopAt = useRef<number>(0); const clipStart = useRef<number>(0);
 const endpoint=(s:string)=>api.replace(/\/$/,'')+s;
 const checkApi=useCallback((url:string)=>{ if(!url){setOnline(false);return} fetch(url.replace(/\/$/,'')+'/api/health').then(r=>setOnline(r.ok)).catch(()=>setOnline(false)); },[]);
 useEffect(()=>{ checkApi(api); },[]); // eslint-disable-line
 useEffect(()=>{if(local||!job || job.status==='pronto' || job.status==='erro')return;const t=setInterval(()=>fetch(endpoint('/api/trabalhos/'+job.id)).then(r=>r.json()).then(setJob).catch(()=>{}),1600);return()=>clearInterval(t)},[job,api,local]);

 const captionPreset = captionPresets.find(p=>p.id===preset) || null;
 const accent = captionPreset?.highlightColor || '#FACC15';
 const opts = useCallback(()=>({legenda:captionPreset,efeito:effect,cues,gancho:hook,accent}),[captionPreset,effect,cues,hook,accent]);

 // Prévia real 9:16 no canvas usando o mesmo desenho da exportação.
 const paint = useCallback(()=>{
  const v=pv.current, c=pc.current; if(!v||!c||!v.videoWidth) return;
  if(!small.current){ small.current=document.createElement('canvas'); small.current.width=54; small.current.height=96; }
  const ctx=c.getContext('2d')!; const o=opts();
  const t=v.currentTime-clipStart.current; const dur=Math.max(1,(stopAt.current||v.duration)-clipStart.current);
  const shifted=o.cues.map(q=>({start:q.start-clipStart.current,end:q.end-clipStart.current,text:q.text}));
  drawFrame(ctx,v,small.current,t,dur,{...o,cues:shifted});
 },[opts]);
 useEffect(()=>{ paint(); },[paint,tab,file]);
 useEffect(()=>{
  const v=pv.current; if(!v) return;
  let id=0; const loop=()=>{ paint(); if(stopAt.current && v.currentTime>=stopAt.current){ v.pause(); setPreviewing(''); } if(!v.paused) id=requestAnimationFrame(loop); };
  const onPlay=()=>{ id=requestAnimationFrame(loop); }; const onSeeked=()=>paint();
  v.addEventListener('play',onPlay); v.addEventListener('seeked',onSeeked); v.addEventListener('loadeddata',onSeeked);
  return ()=>{ cancelAnimationFrame(id); v.removeEventListener('play',onPlay); v.removeEventListener('seeked',onSeeked); v.removeEventListener('loadeddata',onSeeked); };
 },[paint,videoUrl]);
 function preview(c:Clip){
  const v=pv.current; if(!v) return;
  if(previewing===c.id){ v.pause(); setPreviewing(''); return; }
  clipStart.current=c.inicio; stopAt.current=c.fim; v.currentTime=c.inicio; v.play().catch(()=>{}); setPreviewing(c.id);
 }

 async function search(){setLoading(true);setMessage('');setList([]);try{const p={tema:topic.trim() || (niche==='Todos os nichos'?'':niche),dias:days,views,minutos:duration,ordem:order};let data:{itens:Video[];nota:string};
  if(online){const r=await fetch(endpoint('/api/radar?'+new URLSearchParams({tema:p.tema,dias:String(days),views:String(views),minutos:String(duration),ordem:order})));const d=await r.json();if(!r.ok)throw Error(d.detail || 'Falha de consulta');data=d}
  else{ if(!ytKey){setTab('config');throw Error('Para pesquisar sem servidor, cole sua chave da YouTube Data API em Configurações.')} data=await radarDireto(ytKey,p) }
  setList(data.itens||[]);setMessage(data.itens?.length? data.nota:'Não encontramos resultados nos filtros selecionados. Tente ampliar o período ou reduzir as visualizações mínimas.')}catch(e){setMessage(e instanceof Error?e.message:String(e))}finally{setLoading(false)}}

 async function upload(){if(!file){setMessage('Selecione um vídeo próprio ou autorizado.');return}if(!rights){setMessage('Marque a declaração de direitos antes de enviar.');return}
  if(local){
   setLoading(true);setMessage('');const j:Job={id:'local',status:'processando',progresso:0,tem_legendas:cues.length>0,cortes:[]};setJob(j);
   try{const r=await analisarNoNavegador(file,videoUrl,{min:minLen,max:maxLen,limite:limit},n=>setJob(x=>x?{...x,progresso:n}:x));setJob({...j,status:'pronto',progresso:100,cortes:r.cortes});
    setMessage(r.audio_lido?`Análise concluída no seu navegador (${tm(r.duracao)} de vídeo). Clique em Prévia para assistir a um corte.`:'O navegador não conseguiu ler o áudio deste arquivo; os cortes foram sugeridos em sequência.')}
   catch(e){setJob({...j,status:'erro',erro:e instanceof Error?e.message:String(e)})}finally{setLoading(false)}
   return;
  }
  setLoading(true);setMessage('Enviando arquivo e criando análise...');const form=new FormData();form.set('file',file);form.set('direitos','true');form.set('duracao_min',String(minLen));form.set('duracao_max',String(maxLen));form.set('max_cortes',String(limit));try{const r=await fetch(endpoint('/api/trabalhos'),{method:'POST',body:form});const d=await r.json();if(!r.ok)throw Error(d.detail||'Erro ao enviar');setJob({id:d.id,status:'na_fila',progresso:0,tem_legendas:false,cortes:[]});setMessage('Vídeo enviado. Análise em andamento.')}catch(e){setMessage(String(e))}finally{setLoading(false)}}

 async function render(clip:Clip){setRendering(clip.id);setRenderPct(0);
  if(local){
   if(!file) return;
   pv.current?.pause(); setPreviewing('');
   setMessage('Gerando o vídeo em tempo real. Mantenha esta aba aberta e visível até terminar.');
   try{const {blob,ext}=await exportarCorte(videoUrl,clip,cues,{legenda:captionPreset,efeito:effect,gancho:hook,accent},setRenderPct);
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`corte-${clip.id}.${ext}`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),60000);
    setMessage(`Corte exportado em ${ext.toUpperCase()} 1080x1920. `+(cues.length?'Legendas incorporadas.':'Sem legendas: envie um arquivo .srt ou .vtt para incorporá-las.'))}
   catch(e){setMessage(e instanceof Error?e.message:String(e))}finally{setRendering('')}
   return;
  }
  setMessage('Exportando MP4...');try{const r=await fetch(endpoint(`/api/trabalhos/${job!.id}/render/${clip.id}?legenda=${preset}&efeito=${effect}`),{method:'POST'});const d=await r.json();if(!r.ok)throw Error(d.detail || 'Erro ao exportar');const a=document.createElement('a');a.href=endpoint(d.download);a.download='corte-'+clip.id+'.mp4';a.click();setMessage('MP4 disponível. '+(d.legendas_embutidas?'Legendas incorporadas.':'Transcrição indisponível: arquivo exportado sem legendas.'))}catch(e){setMessage(String(e))}finally{setRendering('')}}

 async function loadCues(f:File|null){ if(!f){setCues([]);setCueName('');return} const c=parseLegendas(await f.text()); setCues(c); setCueName(f.name); setMessage(c.length?`${c.length} falas carregadas de ${f.name}.`:'Não encontramos falas nesse arquivo. Use o formato SRT ou VTT.'); }
 const recSupport = formatoSuportado();
 const captionNote=(id:string)=>local?'Exportação suportada no navegador':serverCaptions.includes(id)?'Exportação básica suportada':'Configuração cadastrada • renderização pendente no servidor';
 const effectNote=(id:string)=>local?'Exportação suportada no navegador':id==='blur-background'?'Exportação suportada':'Efeito cadastrado • renderização pendente no servidor';

 return <div className="app"><aside className="sidebar"><div className="brand"><span className="brand-icon"><Clapperboard size={24}/></span><div><strong>ESTÚDIO<span>CLIP</span></strong><small>RADAR + EDITOR</small></div></div><div className="side-title">WORKSPACE</div>
 {([['radar','Radar de canais',Search],['estudio','Gerar cortes',Clapperboard],['modelos','Legendas e efeitos',Captions],['config','Configurações',Settings]] as const).map(([key,label,Icon])=><button key={key} className={'nav '+(tab===key?'active':'')} onClick={()=>setTab(key)}><Icon size={18}/>{label}</button>)}
 <div className="sidebar-bottom"><div className={'online yes'}><i/>{online?'Servidor conectado':'Motor no navegador'}</div><small>{online?'Processando na API Python':'Seus vídeos não saem do computador'}</small></div></aside>
 <main><header><div><div className="eyebrow">PAINEL DE PRODUÇÃO</div><h1>{tab==='radar'?'Descubra vídeos em alta':tab==='estudio'?'Transforme vídeos em cortes':tab==='modelos'?'Biblioteca de estilos':'Conecte suas ferramentas'}</h1><p className="subtitle">{tab==='radar'?'Pesquise qualquer nicho, compare visualizações e encontre oportunidades.':tab==='estudio'?'Importe conteúdo autorizado, avalie candidatos e exporte destaques.':tab==='modelos'?'Legendas e efeitos pré-cadastrados para personalizar seus vídeos.':'Configure a busca no YouTube e, se quiser, um servidor de processamento.'}</p></div><span className="state-pill">{online?'Servidor':'Funciona sem servidor'}</span></header>
 {message&&<div className="message"><AlertTriangle size={17}/><span>{message}</span><button onClick={()=>setMessage('')}>×</button></div>}
 {tab==='radar'&&<><section className="panel"><div className="section-head"><h2><Search size={18}/> Filtros do Radar</h2><span>Dados públicos • YouTube</span></div><div className="filter-grid"><label className="wide">Nicho<select value={niche} onChange={e=>setNiche(e.target.value)}>{niches.map(n=><option key={n}>{n}</option>)}</select></label><label className="wide">Tema / palavra-chave<input placeholder="Ex.: GTA, entrevistas, futebol, ciência..." value={topic} onChange={e=>setTopic(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')search()}}/></label><label>Período<select value={days} onChange={e=>setDays(+e.target.value)}><option value={7}>7 dias</option><option value={30}>30 dias</option><option value={90}>90 dias</option><option value={365}>1 ano</option></select></label><label>Views mínimas<select value={views} onChange={e=>setViews(+e.target.value)}><option value={0}>Qualquer</option><option value={10000}>10 mil</option><option value={100000}>100 mil</option><option value={500000}>500 mil</option><option value={1000000}>1 milhão</option></select></label><label>Duração mínima<select value={duration} onChange={e=>setDuration(+e.target.value)}><option value={0}>Qualquer</option><option value={10}>10 minutos</option><option value={20}>20 minutos</option><option value={40}>40 minutos</option></select></label><label>Ordenação<select value={order} onChange={e=>setOrder(e.target.value)}><option value="velocidade">Views por dia (estimativa)</option><option value="views">Total de views</option></select></label></div><div className="actions"><button className="primary" onClick={search} disabled={loading}><Search size={17}/>{loading?'Pesquisando...':'Pesquisar canais e vídeos'}</button><button className="subtle" onClick={()=>{setNiche('Todos os nichos');setTopic('');setDays(30);setViews(100000);setDuration(20);setOrder('velocidade')}}><RefreshCcw size={16}/> Restaurar</button></div></section><section className="results"><div className="section-head"><h2>Resultados encontrados <span className="count">{list.length}</span></h2><span>{online||ytKey?'Dados reais do YouTube':'Chave do YouTube não configurada'}</span></div>{list.length? <div className="video-grid">{list.map(v=><article className="video-card" key={v.id}><a href={v.link} target="_blank" rel="noreferrer"><img src={v.thumbnail} alt="Miniatura do vídeo"/></a><div className="video-body"><h3>{v.titulo}</h3><a className="channel" href={v.link_canal} target="_blank" rel="noreferrer">{v.canal} <ExternalLink size={13}/></a><div className="metrics"><span>▶ {fmt(v.views)} views</span><span>⚡ {fmt(v.velocidade)}/dia</span><span>◷ {tm(v.duracao_segundos)}</span></div><button className="action-link" onClick={()=>{setSource(v.link);setTab('estudio');setMessage('Link preenchido. Para processar, envie o arquivo de vídeo autorizado — não há download automático de terceiros.') }}>Usar no estúdio →</button></div></article>)}</div>:<div className="empty"><Search size={35}/><strong>Comece sua pesquisa</strong><p>{online||ytKey?'Escolha um nicho e clique em Pesquisar.':'Cole sua chave gratuita da YouTube Data API em Configurações para pesquisar direto do navegador.'}</p>{!online&&!ytKey&&<button className="subtle" onClick={()=>setTab('config')}><Settings size={15}/> Abrir Configurações</button>}</div>}</section></>}
 {tab==='estudio'&&<><div className="two-cols"><section className="panel"><div className="section-head"><h2><Clapperboard size={18}/> Novo trabalho</h2></div><label>Link de referência<input value={source} onChange={e=>setSource(e.target.value)} placeholder="Cole o link do canal ou vídeo"/></label>{source&&<a className="ref-link" href={source} target="_blank" rel="noreferrer">Abrir conteúdo de referência <ExternalLink size={13}/></a>}<label>Arquivo de vídeo autorizado<input type="file" accept="video/*" onChange={e=>{setFile(e.target.files?.[0]||null);setJob(null);setPreviewing('')}}/></label><label>Legendas (opcional, .srt ou .vtt)<input type="file" accept=".srt,.vtt,text/vtt" onChange={e=>loadCues(e.target.files?.[0]||null)}/></label>{file&&<p className="hint tight">Vídeo selecionado: {file.name}</p>}{cueName&&<p className="hint tight"><FileText size={13}/> {cues.length} falas de {cueName}</p>}<div className="small-grid"><label>Duração mínima<select value={minLen} onChange={e=>{const n=+e.target.value;setMinLen(n);if(n>maxLen)setMaxLen(n)}}>{[15,30,45,60,90,120].map(n=><option key={n} value={n}>{n}s</option>)}</select></label><label>Duração máxima<select value={maxLen} onChange={e=>{setMaxLen(Math.max(minLen,+e.target.value))}}>{[30,45,60,90,120,180].map(n=><option key={n} value={n}>{n}s</option>)}</select></label><label>Máximo de cortes<select value={limit} onChange={e=>setLimit(+e.target.value)}>{[3,5,10,15,20,30].map(n=><option key={n}>{n}</option>)}</select></label><label>Nota mínima (0 a 10)<input type="number" min={0} max={10} step={0.5} value={minimum} onChange={e=>setMinimum(Math.min(10,Math.max(0,+e.target.value)))}/></label></div><label className="check"><input type="checkbox" checked={rights} onChange={e=>setRights(e.target.checked)}/> Declaro possuir direitos e autorização para editar/publicar o vídeo.</label><button className="primary full" disabled={loading||!file||!rights} onClick={upload}><Sparkles size={17}/> {loading?'Analisando...':'Analisar e sugerir cortes'}</button><p className="hint">{local?'A análise roda no seu navegador e o vídeo não é enviado para nenhum servidor. ':''}A nota é estimada pela energia do áudio, não é uma previsão de viralização.</p></section>
 <section className="panel"><div className="section-head"><h2><Captions size={18}/> Configuração de exportação</h2></div><label>Estilo de legenda<select value={preset} onChange={e=>setPreset(e.target.value)}>{captionPresets.map(p=><option value={p.id} key={p.id}>{p.nome}{!local&&!serverCaptions.includes(p.id)?' • em desenvolvimento':''}</option>)}</select></label><label>Efeito de vídeo<select value={effect} onChange={e=>setEffect(e.target.value)}><option value="nenhum">Sem efeito (cortar para 9:16)</option>{effectPresets.map(p=><option value={p.id} key={p.id}>{p.nome}{!local&&p.id!=='blur-background'?' • em desenvolvimento':''}</option>)}</select></label>{local&&<label>Texto de gancho no topo (opcional)<input value={hook} maxLength={80} onChange={e=>setHook(e.target.value)} placeholder="Ex.: ELE NÃO ESPERAVA ISSO"/></label>}
 <div className="preview"><span>{file?'PRÉVIA REAL • 9:16':'PRÉVIA CONCEITUAL • 9:16'}</span>{file?<canvas ref={pc} width={W} height={H} className="preview-canvas"/>:<div className="phone"><div className="play-icon">▶</div><div className="caption-demo" style={{color:captionPreset?.highlightColor}}>SEU MELHOR MOMENTO</div></div>}</div>
 <p className="hint">{local?(recSupport?`Exportação em ${recSupport.startsWith('video/mp4')?'MP4':'WEBM'} 1080x1920, gravada em tempo real (um corte de 60 s leva cerca de 60 s).`:'Este navegador não suporta gravação de vídeo. Use Chrome, Edge ou Safari atualizados.'):'O arquivo final é gerado pelo FFmpeg no servidor.'}</p></section></div>
 <section className="panel job-panel"><div className="section-head"><h2>Melhores cortes</h2><span>Nota interna 0–99 • Exibição 0–10</span></div>{job&&<div className="job-status"><strong>{job.status==='pronto'?'Análise concluída':job.status==='erro'?'Ocorreu um erro':'Processando vídeo...'}</strong><span>{job.progresso}%</span><div className="progress"><div style={{width:job.progresso+'%'}}/></div>{job.erro&&<p>{job.erro}</p>}</div>}{job?.status==='pronto'?<>{job.cortes.filter(c=>c.nota_10>minimum).length===0&&<p className="hint">Nenhum corte acima da nota mínima. Reduza o filtro para ver mais candidatos.</p>}<div className="clips">{job.cortes.filter(c=>c.nota_10>minimum).map(c=><div className="clip" key={c.id}><div className="score"><strong>{c.nota_10.toFixed(1)}</strong><small>/10</small></div><div className="clip-detail"><strong>{c.titulo}</strong><small>{tm(c.inicio)} — {tm(c.fim)} • {Math.round(c.fim-c.inicio)} s • Nota original {c.nota_final}/99</small><p>{c.motivo}</p>{rendering===c.id&&local&&<div className="progress"><div style={{width:renderPct+'%'}}/></div>}</div>{local&&<button className="subtle" disabled={!!rendering} onClick={()=>preview(c)}>{previewing===c.id?<><Square size={14}/> Parar</>:<><Play size={14}/> Prévia</>}</button>}<button className="primary" disabled={!!rendering||(local&&!recSupport)} onClick={()=>render(c)}><Download size={16}/>{rendering===c.id?(local?`${renderPct}%`:'Gerando...'):'Exportar'}</button></div>)}</div></>:<div className="empty small"><Sparkles size={30}/><strong>Os melhores momentos aparecerão aqui</strong><p>Envie um vídeo próprio/autorizado para gerar sugestões.</p></div>}</section></>}
 {tab==='modelos'&&<><section className="panel"><div className="section-head"><h2>Estilos de legenda <span className="count">{captionPresets.length}</span></h2></div><div className="preset-grid">{captionPresets.map(p=><button key={p.id} className={'preset'+(preset===p.id?' selected':'')} onClick={()=>{setPreset(p.id);setTab('estudio')}}><div className="preset-preview" style={{color:p.highlightColor,background:p.id==='legenda-caixa'?'#000c':undefined}}>{p.nome.toUpperCase()}</div><strong>{p.nome}</strong><small>{captionNote(p.id)}</small></button>)}</div></section><section className="panel"><div className="section-head"><h2>Efeitos de vídeo <span className="count">{effectPresets.length}</span></h2></div><div className="preset-grid">{effectPresets.map(p=><button key={p.id} className={'preset'+(effect===p.id?' selected':'')} onClick={()=>{setEffect(p.id);setTab('estudio')}}><div className="preset-preview violet">✦</div><strong>{p.nome}</strong><small>{effectNote(p.id)}</small></button>)}</div></section></>}
 {tab==='config'&&<><section className="panel"><h2>Radar do YouTube</h2><p className="subtitle">Cole uma chave da YouTube Data API v3 (gratuita no Google Cloud Console). Ela fica salva apenas neste navegador e é usada direto com o YouTube. Restrinja a chave ao endereço deste site no Google Cloud.</p><label>Chave da YouTube Data API<input type="password" autoComplete="off" value={ytKey} onChange={e=>setYtKey(e.target.value.trim())} placeholder="AIza..."/></label><div className="actions"><button className="primary" onClick={()=>{store.set('studio_yt_key',ytKey);setMessage(ytKey?'Chave salva neste navegador. Já pode pesquisar no Radar.':'Chave removida.')}}><CheckCircle2 size={16}/> Salvar chave</button><a className="subtle" href="https://console.cloud.google.com/apis/library/youtube.googleapis.com" target="_blank" rel="noreferrer"><ExternalLink size={15}/> Criar chave no Google Cloud</a></div></section>
 <section className="panel"><h2>Servidor de processamento (opcional)</h2><p className="subtitle">Sem servidor, a análise e a exportação rodam no seu navegador. Se você tiver a API Python do projeto rodando (com FFmpeg e transcrição automática pelo Whisper), informe o endereço para usá-la no lugar.</p><label>Endereço da API<input value={api} onChange={e=>setApi(e.target.value)} placeholder="https://api.seu-dominio.com"/></label><div className="actions"><button className="primary" onClick={()=>{store.set('studio_api',api);checkApi(api);setMessage(api?'Endereço salvo. Confira o indicador no menu.':'Servidor removido: usando o motor do navegador.') }}><CheckCircle2 size={16}/> Salvar e testar</button></div><div className="notice"><strong>Antes de publicar o servidor</strong><p>O backend de demonstração não possui login, fila persistente ou isolamento por usuário. Não exponha na internet sem implementar esses recursos.</p></div></section></>}
 <video ref={pv} src={videoUrl||undefined} preload="auto" playsInline hidden/>
 <footer>EstúdioClip • Use apenas conteúdo próprio ou autorizado</footer></main></div>
}
