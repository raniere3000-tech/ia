import { useMemo, useRef, useState } from 'react';
import { Upload, Film, Sparkles, Loader2, CheckCircle2, Circle, AlertTriangle, Pencil, Download, Copy, Trash2, Undo2, FileText, Wand2, Package, ExternalLink, X, Play } from 'lucide-react';
import { useApp, captionPresets, PROJETO_VAZIO, type Job } from '../state';
import { HelpButton } from '../components/Help';
import Editor from '../components/Editor';
import { videoInfo, decodeAudio, energyProfile, captureFrames, type AudioData } from '../lib/media';
import { gerarCandidatos, notaFinal, nota10, type Clip, type Candidate } from '../lib/analyze';
import { parseLegendas, type Cue } from '../lib/captions';
import { transcrever, IDIOMAS } from '../lib/transcribe';
import { formatoSuportado } from '../lib/render';
import { renderClip, baixar, zipar, nomeArquivo, srtDoCorte } from '../lib/exporter';
import { tm, parseTime, uid } from '../lib/store';

// Cache do áudio decodificado, para refazer a análise sem ler o arquivo de novo.
let cache:{file:File|null;audio:AudioData|null;energy:Float32Array|null} = {file:null,audio:null,energy:null};
const STEP=0.5;
const DURACOES:[string,number,number][] = [['Até 30 s',15,30],['30–60 s',30,60],['61–90 s',61,90],['90–180 s',90,180]];

export default function Cortes(){
  const {settings,toast,projeto,setProjeto,template,linkRef,setLinkRef,go}=useApp();
  const [direitos,setDireitos]=useState(false);
  const [modelo,setModelo]=useState<'falas'|'acao'>('falas');
  const [faixa,setFaixa]=useState<[number,number]>([61,90]);
  const [custom,setCustom]=useState(false);
  const [trechoIni,setTrechoIni]=useState(''); const [trechoFim,setTrechoFim]=useState('');
  const [limite,setLimite]=useState(15); const [minimo,setMinimo]=useState(3);
  const [legSrc,setLegSrc]=useState<'auto'|'arquivo'|'nenhuma'>('auto'); const [idioma,setIdioma]=useState(settings.idioma);
  const [prompt,setPrompt]=useState(''); const [tema,setTema]=useState('');
  const [srtFile,setSrtFile]=useState<File|null>(null);
  const [mostrarTodos,setMostrarTodos]=useState(false); const [ordem,setOrdem]=useState<'nota'|'tempo'>('nota');
  const [sel,setSel]=useState<Set<string>>(new Set());
  const [editando,setEditando]=useState<Clip|null>(null);
  const [exp,setExp]=useState<{id:string;pct:number;fila?:string}|null>(null);
  const [drag,setDrag]=useState(false);
  const [novoPrompt,setNovoPrompt]=useState('');
  const fileInput=useRef<HTMLInputElement>(null);
  const job=projeto.job; const rodando=job.status==='rodando';
  const temIA=!!settings.claudeKey;
  const recSupport=formatoSuportado();

  function escolherArquivo(f:File|null){
    if(!f) return;
    if(!f.type.startsWith('video/') && !/\.(mp4|mov|mkv|webm|m4v)$/i.test(f.name)){ toast('Escolha um arquivo de vídeo (MP4, MOV, WEBM).','erro'); return; }
    if(projeto.url) URL.revokeObjectURL(projeto.url);
    cache={file:null,audio:null,energy:null};
    const url=URL.createObjectURL(f);
    setProjeto(()=>({...PROJETO_VAZIO,file:f,url,nome:f.name}));
    setSel(new Set());
    videoInfo(url).then(i=>setProjeto(p=>p.url===url?{...p,duracao:i.duration}:p)).catch(e=>toast(e.message,'erro'));
  }
  const setJob=(j:Partial<Job>)=>setProjeto(p=>({...p,job:{...p.job,...j}}));

  async function avaliarIA(cands:(Candidate&{id:string})[],cues:Cue[],promptTxt:string,temaTxt:string){
    const {avaliarComIA}=await import('../lib/ai');
    const top=cands.slice(0,Math.min(30,Math.max(10,limite*2)));
    let frames:Record<string,string[]>|undefined;
    if(modelo==='acao'){
      frames={};
      for(const c of top.slice(0,20)){ frames[c.id]=await captureFrames(projeto.url,[c.inicio+(c.fim-c.inicio)*0.25,c.inicio+(c.fim-c.inicio)*0.65],512); }
    }
    const res=await avaliarComIA(settings.claudeKey,top,cues,{prompt:promptTxt,tema:temaTxt,frames});
    return new Map(res.map(r=>[r.id,r]));
  }

  function montarClips(cands:(Candidate&{id:string})[],ia:Map<string,any>|null,dur:number):Clip[]{
    const out=cands.map(c=>{
      const r=ia?.get(c.id);
      const notas=r?{gancho:clamp(r.gancho),fluxo:clamp(r.fluxo),valor:clamp(r.valor),tendencia:clamp(r.tendencia)}:c.notas;
      const ini=r&&Math.abs(r.inicio-c.inicio)<=3?Math.max(0,r.inicio):c.inicio; const fim=r&&Math.abs(r.fim-c.fim)<=3?Math.min(dur,r.fim):c.fim;
      const nf=notaFinal(notas);
      return {id:c.id,titulo:r?.titulo||'',inicio:+ini.toFixed(2),fim:+fim.toFixed(2),notas,nota_final:nf,nota_10:nota10(nf),motivo:r?.motivo||c.motivo,fonte:r?'ia':'heuristica',legenda:legSrc==='nenhuma'?'':settings.legendaPadrao,efeito:settings.efeitoPadrao,formato:'9:16',gancho_texto:''} as Clip;
    });
    out.sort((a,b)=>b.nota_final-a.nota_final||b.notas.gancho-a.notas.gancho||a.inicio-b.inicio);
    out.forEach((c,i)=>{ if(!c.titulo) c.titulo=`Destaque ${i+1}`; });
    return out;
  }

  async function gerar(){
    if(!projeto.file||!direitos) return;
    const etapas=['Lendo o vídeo','Analisando o áudio',...(legSrc!=='nenhuma'?['Preparando a legenda']:[]),'Montando candidatos',...(temIA?['Avaliando com IA (Claude)']:[]),'Gerando miniaturas'];
    setProjeto(p=>({...p,clips:[],candidatos:0,prompt,tema,job:{status:'rodando',etapa:etapas[0],pct:0,etapas}}));
    setSel(new Set());
    try{
      const info=await videoInfo(projeto.url);
      setJob({etapa:'Analisando o áudio',pct:0});
      if(cache.file!==projeto.file){ const audio=await decodeAudio(projeto.file); cache={file:projeto.file,audio,energy:audio?energyProfile(audio,STEP):null}; }
      if(!cache.audio) toast('O navegador não conseguiu ler o áudio deste vídeo. Os cortes serão sugeridos em sequência e sem legenda automática.','erro');
      let cues:Cue[]=projeto.cues; let fonte=projeto.cuesFonte;
      if(legSrc==='arquivo'){
        if(!srtFile) throw new Error('Escolha o arquivo de legenda (.srt ou .vtt) ou mude a opção de legenda.');
        setJob({etapa:'Preparando a legenda'}); cues=parseLegendas(await srtFile.text()); fonte='arquivo';
        if(!cues.length) toast('Não encontramos falas no arquivo de legenda.','erro');
      }else if(legSrc==='auto' && cache.audio && fonte!=='whisper'){
        setJob({etapa:'Preparando a legenda',pct:0});
        try{
          cues=await transcrever(cache.audio.samples,settings.whisperModel,idioma,(s,pct)=>setJob({etapa:'Preparando a legenda',pct,erro:s}));
          fonte='whisper';
          if(!cues.length) toast('O Whisper não encontrou fala neste vídeo.','info');
        }catch(e){
          cues=[]; fonte='';
          toast((e instanceof Error?e.message:String(e))+' Os cortes serão gerados sem legenda; você pode enviar um .srt.','erro');
        }
      }else if(legSrc==='nenhuma'){ cues=[]; fonte=''; }
      setProjeto(p=>({...p,cues,cuesFonte:fonte,duracao:info.duration}));
      setJob({etapa:'Montando candidatos',pct:0,erro:undefined});
      const ini=trechoIni?parseTime(trechoIni):0, fimT=trechoFim?parseTime(trechoFim):0;
      const cands=gerarCandidatos(cache.energy,STEP,info.duration,modelo==='falas'?cues:cues.length?cues:[],{min:faixa[0],max:faixa[1],limite,inicio:isNaN(ini)?0:ini,fim:isNaN(fimT)?0:fimT}).map(c=>({...c,id:uid()}));
      if(!cands.length) throw new Error('O vídeo (ou o trecho escolhido) é mais curto que a duração mínima dos cortes. Escolha uma duração menor.');
      let ia:Map<string,any>|null=null;
      if(temIA){
        setJob({etapa:'Avaliando com IA (Claude)'});
        try{ ia=await avaliarIA(cands,cues,prompt,tema); }
        catch(e){ const {erroAmigavel}=await import('../lib/ai'); toast('A avaliação com IA falhou, usando notas automáticas. '+erroAmigavel(e),'erro'); }
      }
      let clips=montarClips(cands,ia,info.duration);
      setProjeto(p=>({...p,clips,candidatos:cands.length}));
      setJob({etapa:'Gerando miniaturas'});
      const top=clips.slice(0,30);
      const thumbs=await captureFrames(projeto.url,top.map(c=>Math.min(c.fim-0.1,c.inicio+1.5)),320).catch(()=>[] as string[]);
      clips=clips.map(c=>{ const i=top.indexOf(c); return i>=0&&thumbs[i]?{...c,thumb:thumbs[i]}:c; });
      setProjeto(p=>({...p,clips,job:{...p.job,status:'pronto',etapa:'',pct:100,erro:undefined}}));
      toast(`${cands.length} trechos avaliados. Confira os melhores abaixo.`,'ok');
    }catch(e){
      const msg=e instanceof Error?e.message:String(e);
      setJob({status:'erro',erro:msg}); toast(msg,'erro');
    }
  }

  async function refazer(){
    if(!temIA||!novoPrompt.trim()) return;
    const cands=projeto.clips.filter(c=>!c.versao_de).map(c=>({id:c.id,inicio:c.inicio,fim:c.fim,notas:c.notas,motivo:c.motivo}));
    const prev=new Map(projeto.clips.map(c=>[c.id,c]));
    setJob({status:'rodando',etapa:'Avaliando com IA (Claude)',etapas:['Avaliando com IA (Claude)'],pct:0});
    try{
      const ia=await avaliarIA(cands,projeto.cues,novoPrompt,projeto.tema);
      const clips=montarClips(cands,ia,projeto.duracao).map(c=>({...c,thumb:prev.get(c.id)?.thumb,legenda:prev.get(c.id)?.legenda??c.legenda,efeito:prev.get(c.id)?.efeito??c.efeito,formato:prev.get(c.id)?.formato??c.formato}));
      setProjeto(p=>({...p,clips,prompt:novoPrompt,job:{...p.job,status:'pronto',etapa:''}}));
      toast('Cortes reavaliados com o novo pedido.','ok');
    }catch(e){ const {erroAmigavel}=await import('../lib/ai'); setJob({status:'pronto'}); toast(erroAmigavel(e),'erro'); }
  }

  const atualizar=(c:Clip)=>setProjeto(p=>({...p,clips:p.clips.map(x=>x.id===c.id?c:x)}));
  const duplicar=(c:Clip)=>{ const n:Clip={...c,id:uid(),versao_de:c.versao_de||c.id,titulo:c.titulo+' (versão 2)'}; setProjeto(p=>{ const i=p.clips.findIndex(x=>x.id===c.id); const cl=[...p.clips]; cl.splice(i+1,0,n); return {...p,clips:cl}; }); toast('Nova versão criada logo abaixo do original.','ok'); return n; };

  async function exportar(c:Clip){
    if(exp) return;
    setExp({id:c.id,pct:0});
    try{
      const {blob,ext}=await renderClip(projeto.url,c,projeto.cues,captionPresets,template,pct=>setExp({id:c.id,pct}));
      baixar(blob,nomeArquivo(c,visiveis.indexOf(c),ext));
      toast(`Corte exportado em ${ext.toUpperCase()}.`,'ok');
    }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }
    finally{ setExp(null); }
  }
  async function exportarZip(){
    const lista=visiveis.filter(c=>sel.has(c.id)); if(!lista.length||exp) return;
    const arquivos:{nome:string;blob:Blob}[]=[]; const extras:Record<string,string>={};
    try{
      for(let i=0;i<lista.length;i++){
        const c=lista[i];
        const {blob,ext}=await renderClip(projeto.url,c,projeto.cues,captionPresets,template,pct=>setExp({id:c.id,pct,fila:`${i+1} de ${lista.length}`}));
        const nome=nomeArquivo(c,i,ext); arquivos.push({nome,blob});
        const srt=srtDoCorte(c,projeto.cues); if(srt) extras[nome.replace(/\.\w+$/,'.srt')]=srt;
      }
      extras['cortes.csv']='arquivo;titulo;inicio;fim;nota_0_99;nota_0_10;gancho;fluxo;valor;tendencia;motivo\n'+lista.map((c,i)=>[arquivos[i].nome,c.titulo,tm(c.inicio),tm(c.fim),c.nota_final,c.nota_10,c.notas.gancho,c.notas.fluxo,c.notas.valor,c.notas.tendencia,c.motivo].map(x=>`"${String(x).replace(/"/g,'""')}"`).join(';')).join('\n');
      setExp({id:'zip',pct:100,fila:'Compactando'});
      baixar(await zipar(arquivos,extras),`cortes-${projeto.nome.replace(/\.\w+$/,'')}.zip`);
      toast(`${lista.length} cortes exportados em ZIP.`,'ok');
    }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }
    finally{ setExp(null); }
  }

  const ativos=projeto.clips.filter(c=>!c.descartado);
  const aprovados=ativos.filter(c=>c.nota_10>minimo);
  const visiveis=useMemo(()=>{ let l=mostrarTodos?ativos:aprovados.slice(0,limite); if(!mostrarTodos){ const ids=new Set(l.map(c=>c.id)); l=[...l,...ativos.filter(c=>c.versao_de&&ids.has(c.versao_de)&&!ids.has(c.id))]; } return ordem==='tempo'?[...l].sort((a,b)=>a.inicio-b.inicio):l; },[ativos,aprovados,mostrarTodos,limite,ordem]);
  const descartados=projeto.clips.filter(c=>c.descartado);

  // ---------- Tela: sem vídeo ----------
  if(!projeto.file) return <>
   <Stepper atual={1}/>
   <section className={'panel dropzone '+(drag?'drag':'')} onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);escolherArquivo(e.dataTransfer.files?.[0]||null)}} onClick={()=>fileInput.current?.click()} role="button" tabIndex={0}>
    <span className="drop-icon"><Upload size={30}/></span>
    <h2>Arraste o vídeo aqui ou clique para escolher</h2>
    <p>MP4, MOV ou WEBM. O arquivo não sai do seu computador.</p>
    <input ref={fileInput} type="file" accept="video/*,.mkv,.mov" hidden onChange={e=>escolherArquivo(e.target.files?.[0]||null)}/>
   </section>
   {linkRef&&<div className="note-bar"><ExternalLink size={15}/><span>Referência do Radar: <a href={linkRef} target="_blank" rel="noreferrer">{linkRef}</a>. O site não baixa vídeos de terceiros: baixe o arquivo (se for seu ou autorizado) e envie acima.</span><button className="icon-btn" onClick={()=>setLinkRef('')}><X size={14}/></button></div>}
   <p className="hint center">Ainda sem vídeo? Ache inspiração no <button className="link-btn inline" onClick={()=>go('radar')}>Radar</button>.</p>
  </>;

  // ---------- Tela: configurar / resultados ----------
  return <>
   <Stepper atual={job.status==='pronto'&&projeto.clips.length?3:2}/>
   <section className="panel file-bar"><Film size={20}/><div className="grow"><strong>{projeto.nome}</strong><small>{projeto.duracao?`${tm(projeto.duracao)} de vídeo`:'Lendo...'}{projeto.cuesFonte&&` • ${projeto.cues.length} falas na legenda`}</small></div><button className="subtle" disabled={rodando||!!exp} onClick={()=>{ if(projeto.url) URL.revokeObjectURL(projeto.url); cache={file:null,audio:null,energy:null}; setProjeto(()=>PROJETO_VAZIO); }}>Trocar vídeo</button></section>

   {job.status!=='pronto'||!projeto.clips.length?<section className="panel">
    <div className="section-head"><h2><Sparkles size={18}/> Como você quer os cortes?</h2></div>
    <div className="form-grid">
     <div className="field"><span className="field-label">Tipo de vídeo <HelpButton topic="modelo"/></span><div className="seg big">
      <button className={modelo==='falas'?'on':''} onClick={()=>setModelo('falas')}><strong>Falas</strong><small>Podcast, entrevista, aula</small></button>
      <button className={modelo==='acao'?'on':''} onClick={()=>setModelo('acao')}><strong>Gameplay / ação</strong><small>Jogos, esportes, pouca fala</small></button></div></div>
     <div className="field"><span className="field-label">Duração de cada corte</span><div className="seg">{DURACOES.map(([l,a,b])=><button key={l} className={!custom&&faixa[0]===a&&faixa[1]===b?'on':''} onClick={()=>{setCustom(false);setFaixa([a,b])}}>{l}</button>)}<button className={custom?'on':''} onClick={()=>setCustom(true)}>Personalizada</button></div>
      {custom&&<div className="small-grid mt"><label>Mínimo (s)<input type="number" min={5} max={600} value={faixa[0]} onChange={e=>{const v=Math.max(5,+e.target.value);setFaixa([v,Math.max(v,faixa[1])])}}/></label><label>Máximo (s)<input type="number" min={5} max={600} value={faixa[1]} onChange={e=>setFaixa([faixa[0],Math.max(faixa[0],+e.target.value)])}/></label></div>}</div>
     <div className="field"><span className="field-label">Legenda <HelpButton topic="whisper"/></span><div className="seg">
      <button className={legSrc==='auto'?'on':''} onClick={()=>setLegSrc('auto')}>Automática</button><button className={legSrc==='arquivo'?'on':''} onClick={()=>setLegSrc('arquivo')}>Tenho um .srt/.vtt</button><button className={legSrc==='nenhuma'?'on':''} onClick={()=>setLegSrc('nenhuma')}>Sem legenda</button></div>
      {legSrc==='auto'&&<label className="mt">Idioma da fala<select value={idioma} onChange={e=>setIdioma(e.target.value)}>{IDIOMAS.map(i=><option key={i.id} value={i.id}>{i.nome}</option>)}</select></label>}
      {legSrc==='arquivo'&&<label className="mt"><span className="label-row">Arquivo de legenda <HelpButton topic="srt"/></span><input type="file" accept=".srt,.vtt" onChange={e=>setSrtFile(e.target.files?.[0]||null)}/></label>}
     </div>
     <div className="field"><span className="field-label">Quantidade e qualidade <HelpButton topic="nota"/></span><div className="small-grid">
      <label>Máximo de cortes<select value={limite} onChange={e=>setLimite(+e.target.value)}>{[3,5,10,15,20,30].map(n=><option key={n} value={n}>{n}</option>)}</select></label>
      <label>Nota mínima (0–10)<input type="number" min={0} max={10} step={0.5} value={minimo} onChange={e=>setMinimo(Math.min(10,Math.max(0,+e.target.value)))}/></label></div></div>
     <details className="field more"><summary>Mais opções: trecho do vídeo, tema e pedido para a IA</summary>
      <div className="small-grid mt"><label>Começar em (min:seg)<input placeholder="0:00" value={trechoIni} onChange={e=>setTrechoIni(e.target.value)}/></label><label>Terminar em (min:seg)<input placeholder={projeto.duracao?tm(projeto.duracao):'fim'} value={trechoFim} onChange={e=>setTrechoFim(e.target.value)}/></label></div>
      <label className="mt">Tema do vídeo<input placeholder="Ex.: GTA RP, podcast de finanças" value={tema} onChange={e=>setTema(e.target.value)}/></label>
      <label className="mt"><span className="label-row">Pedido para a IA {!temIA&&<span className="tag">precisa da chave da Claude</span>}</span><input disabled={!temIA} placeholder={temIA?'Ex.: ache onde ele fala de preço; perseguições policiais':'Configure a chave da Claude para usar'} value={prompt} onChange={e=>setPrompt(e.target.value)}/></label>
     </details>
    </div>
    <label className="check big"><input type="checkbox" checked={direitos} onChange={e=>setDireitos(e.target.checked)}/> Declaro que tenho direito de usar e publicar este vídeo (é meu ou tenho autorização do dono).</label>
    <button className="primary lg full" disabled={!direitos||rodando||!projeto.duracao} onClick={gerar}>{rodando?<Loader2 size={18} className="spin"/>:<Sparkles size={18}/>} {rodando?'Gerando cortes...':'Gerar cortes'}</button>
    {!temIA&&<p className="hint center">Notas automáticas pelo áudio e pelas frases. Para notas e títulos feitos por IA, <button className="link-btn inline" onClick={()=>go('config')}>configure a chave da Claude</button>.</p>}
    {job.status!=='idle'&&<JobView job={job}/>}
   </section>
   :<>
    <section className="panel results-bar">
     <div className="result-summary"><strong>{aprovados.length>limite?limite:aprovados.length} cortes aprovados</strong> de {projeto.candidatos} candidatos • nota mínima &gt; {minimo.toFixed(1)}/10 • máximo {limite} {projeto.clips.some(c=>c.fonte==='ia')?<span className="tag ai"><Sparkles size={12}/> notas da IA</span>:<span className="tag">notas automáticas</span>}</div>
     <div className="result-controls">
      <label className="inline">Nota mínima<input type="number" min={0} max={10} step={0.5} value={minimo} onChange={e=>setMinimo(Math.min(10,Math.max(0,+e.target.value)))}/></label>
      <label className="inline">Máximo<select value={limite} onChange={e=>setLimite(+e.target.value)}>{[3,5,10,15,20,30].map(n=><option key={n}>{n}</option>)}</select></label>
      <label className="inline">Ordenar<select value={ordem} onChange={e=>setOrdem(e.target.value as 'nota'|'tempo')}><option value="nota">Melhores notas</option><option value="tempo">Ordem no vídeo</option></select></label>
      <button className="subtle" onClick={()=>setMostrarTodos(!mostrarTodos)}>{mostrarTodos?'Só aprovados':'Mostrar todos'}</button>
      <button className="subtle" onClick={()=>setProjeto(p=>({...p,clips:[],job:{status:'idle',etapa:'',pct:0,etapas:[]}}))}>Alterar opções e refazer</button>
     </div>
     {temIA&&<div className="redo"><Wand2 size={16}/><input placeholder="Refazer com outro pedido, ex.: momentos engraçados" value={novoPrompt} onChange={e=>setNovoPrompt(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')refazer()}}/><button className="subtle" disabled={!novoPrompt.trim()||rodando} onClick={refazer}>{rodando?<Loader2 size={15} className="spin"/>:null} Refazer com IA</button></div>}
     {rodando&&<JobView job={job}/>}
    </section>

    <div className="bulk-bar">
     <label className="check"><input type="checkbox" checked={visiveis.length>0&&visiveis.every(c=>sel.has(c.id))} onChange={e=>setSel(e.target.checked?new Set(visiveis.map(c=>c.id)):new Set())}/> Selecionar todos</label>
     <span>{sel.size} selecionado(s)</span>
     <button className="primary" disabled={!sel.size||!!exp||!recSupport} onClick={exportarZip}><Package size={16}/> Baixar selecionados (ZIP)</button>
     <HelpButton topic="exportar"/>
    </div>
    {exp&&<div className="export-bar"><Loader2 size={16} className="spin"/><span>{exp.fila?`Exportando ${exp.fila}`:'Exportando corte'} • {exp.pct}% — mantenha esta aba aberta e visível</span><div className="progress"><div style={{width:exp.pct+'%'}}/></div></div>}

    {visiveis.length===0?<div className="empty"><Sparkles size={30}/><strong>Nenhum corte acima da nota mínima</strong><p>Reduza a nota mínima ou clique em “Mostrar todos”. O site não inventa cortes para completar a quantidade.</p></div>
    :<div className="clip-grid">{visiveis.map(c=><article key={c.id} className={'clip-card '+(sel.has(c.id)?'selected':'')+(c.nota_10<=minimo?' below':'')}>
      <div className="clip-thumb" onClick={()=>setEditando(c)}>{c.thumb?<img src={c.thumb} alt=""/>:<Film size={28}/>}<span className="play"><Play size={18}/></span><span className="dur">{tm(c.inicio)}–{tm(c.fim)} • {Math.round(c.fim-c.inicio)} s</span>
       <label className="sel" onClick={e=>e.stopPropagation()}><input type="checkbox" checked={sel.has(c.id)} onChange={e=>{const s=new Set(sel); e.target.checked?s.add(c.id):s.delete(c.id); setSel(s);}}/></label></div>
      <div className="clip-body">
       <div className="score-row"><div className="score big"><strong>{c.nota_10.toFixed(1)}</strong><small>/10</small></div><div className="sub-scores">{(['gancho','fluxo','valor','tendencia'] as const).map(k=><span key={k} title={`${k}: ${c.notas[k]}/99`}><i style={{width:c.notas[k]+'%'}}/>{k==='tendencia'?'tendência':k} {c.notas[k]}</span>)}</div></div>
       <input className="title-input" value={c.titulo} onChange={e=>atualizar({...c,titulo:e.target.value})} aria-label="Título"/>
       <p className="motivo">{c.motivo} <small>Nota {c.nota_final}/99{c.versao_de?' • versão duplicada':''}</small></p>
       {exp?.id===c.id&&<div className="progress"><div style={{width:exp.pct+'%'}}/></div>}
       <div className="clip-actions">
        <button className="primary sm" onClick={()=>setEditando(c)}><Pencil size={14}/> Editar e ver</button>
        <button className="subtle sm" disabled={!!exp||!recSupport} onClick={()=>exportar(c)}>{exp?.id===c.id?<><Loader2 size={14} className="spin"/> {exp.pct}%</>:<><Download size={14}/> Baixar</>}</button>
        <button className="icon-btn" title="Duplicar" onClick={()=>duplicar(c)}><Copy size={15}/></button>
        <button className="icon-btn" title="Descartar" onClick={()=>atualizar({...c,descartado:true})}><Trash2 size={15}/></button>
       </div>
      </div>
     </article>)}</div>}
    {descartados.length>0&&<details className="discarded"><summary>{descartados.length} descartado(s)</summary>{descartados.map(c=><div key={c.id} className="discard-row"><span>{c.titulo} ({tm(c.inicio)}–{tm(c.fim)})</span><button className="link-btn" onClick={()=>atualizar({...c,descartado:false})}><Undo2 size={13}/> Restaurar</button></div>)}</details>}
    {!recSupport&&<p className="hint center"><AlertTriangle size={13}/> Este navegador não grava vídeo. Use Chrome, Edge ou Safari atualizados para exportar.</p>}
   </>}
   {editando&&<Editor clip={editando} onClose={()=>setEditando(null)}
     onSave={(c,cues)=>{ atualizar(c); setProjeto(p=>({...p,cues})); setEditando(null); toast('Alterações salvas.','ok'); }}
     onDuplicate={c=>{ const n=duplicar(c); setEditando(n); }}
     onExport={c=>{ setEditando(null); exportar(c); }}/>}
  </>;
}

function clamp(n:number){ return Math.max(0,Math.min(99,Math.round(n||0))); }

function Stepper({atual}:{atual:number}){
  const s=['Enviar vídeo','Escolher opções','Revisar e exportar'];
  return <ol className="stepper">{s.map((t,i)=><li key={t} className={i+1<atual?'done':i+1===atual?'on':''}><span>{i+1<atual?<CheckCircle2 size={16}/>:i+1}</span>{t}</li>)}</ol>;
}

function JobView({job}:{job:Job}){
  if(job.status==='erro') return <div className="job-status err"><AlertTriangle size={17}/><span>{job.erro}</span></div>;
  const idx=job.etapas.indexOf(job.etapa);
  return <div className="job-status"><ul className="stages">{job.etapas.map((e,i)=><li key={e} className={job.status==='pronto'||i<idx?'done':i===idx?'on':''}>{job.status==='pronto'||i<idx?<CheckCircle2 size={15}/>:i===idx?<Loader2 size={15} className="spin"/>:<Circle size={15}/>}{e}{i===idx&&job.status==='rodando'&&e==='Preparando a legenda'&&job.erro&&<small> — {job.erro} {job.pct?job.pct+'%':''}</small>}</li>)}</ul>
   {job.etapa==='Preparando a legenda'&&<p className="hint"><FileText size={13}/> A transcrição roda no seu computador. Pode levar alguns minutos em vídeos longos.</p>}</div>;
}
