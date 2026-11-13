import { useMemo, useState } from 'react';
import { ArrowLeft, ArrowRight, ChevronLeft, ChevronRight, Film, Loader2, Package, Pencil, Type, Wand2, LayoutTemplate, Captions, CheckCircle2, Languages, Play, RectangleHorizontal } from 'lucide-react';
import { VOZES, pegarDub, wavDaDub } from '../lib/dublagem';
import { useApp, captionPresets, effectPresets } from '../state';
import Preview from './Preview';
import { TemplateForm } from '../pages/Templates';
import { TARJA_PADRAO, type Clip, type Formato, type Tarja } from '../lib/analyze';
import { tm } from '../lib/store';

type Props = {
  clips:Clip[];
  mudar:(ids:string[],p:Partial<Clip>)=>void;
  onEditar:(c:Clip)=>void;
  onVoltar:()=>void; onProximo:(ids:string[])=>void; onZip:()=>void;
  exportando:boolean;
  gerarLegendas:(ids:string[],via:'auto'|'gemini',onStatus:(s:string,pct:number)=>void)=>Promise<number>;
  dublar:(ids:string[],voz:string,volumeOriginal:number,onStatus:(s:string,pct:number)=>void)=>Promise<number>;
};
const ler=(k:string,p:string)=>{ try{ return localStorage.getItem(k)||p; }catch{ return p; } };
const gravar=(k:string,v:string)=>{ try{ localStorage.setItem(k,v); }catch{ /* sem armazenamento */ } };

/** Etapa 3: edição em lote dos cortes escolhidos (template, @, legenda, efeito e formato). */
export default function EdicaoLote({clips,mudar,onEditar,onVoltar,onProximo,onZip,exportando,gerarLegendas,dublar}:Props){
  const [dub,setDub]=useState<{txt:string;pct:number}|null>(null);
  const [voz,setVoz]=useState(()=>ler('studio_dub_voz','Kore')); const [volOrig,setVolOrig]=useState(()=>+ler('studio_dub_vol','0.12'));
  const [ouvir,setOuvir]=useState<string>('');
  const {projeto,template,settings,toast}=useApp();
  const [leg,setLeg]=useState<{txt:string;pct:number}|null>(null);
  const [i,setI]=useState(0); const [todos,setTodos]=useState(true);
  // Cortes desmarcados ficam fora das mudanças em lote e da postagem.
  const [fora,setFora]=useState<Set<string>>(new Set());
  const marcados=clips.filter(c=>!fora.has(c.id)).map(c=>c.id);
  const marcar=(id:string,v:boolean)=>setFora(f=>{ const n=new Set(f); v?n.delete(id):n.add(id); return n; });
  const atual=clips[Math.min(i,clips.length-1)];
  const legenda=captionPresets.find(p=>p.id===atual?.legenda)||null;
  const opts=useMemo(()=>({legenda,efeito:atual?.efeito||'nenhum',cues:atual?.video?.cues??projeto.cues,gancho:atual?.gancho_texto||'',accent:legenda?.highlightColor||template.cor,template:atual?.semTemplate?{...template,ativo:false}:template,tarja:atual?.tarja}),[atual?.tarja,legenda,atual?.semTemplate,atual?.efeito,atual?.gancho_texto,atual?.video,projeto.cues,template]);
  if(!atual) return <section className="panel empty-state"><h2>Nenhum corte escolhido</h2><button className="primary" onClick={onVoltar}><ArrowLeft size={16}/> Voltar e escolher</button></section>;
  const alvo=()=>todos&&marcados.length?marcados:[atual.id];
  const igual=(k:keyof Clip)=>clips.every(c=>c[k]===atual[k]);
  const semLegenda=clips.filter(c=>!c.legendaOk&&!(c.video?.cues??projeto.cues).some(q=>q.end>c.inicio&&q.start<c.fim));
  async function legendar(via:'auto'|'gemini'){
    const ids=(semLegenda.length?semLegenda:clips).map(c=>c.id);
    setLeg({txt:'Começando',pct:0});
    try{
      const n=await gerarLegendas(ids,via,(txt,pct)=>setLeg({txt,pct}));
      toast(n?`Legenda pronta em ${ids.length} corte(s).`:'Não encontramos fala nesses cortes.',n?'ok':'info');
    }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }
    finally{ setLeg(null); }
  }
  async function dublarTodos(){
    if(semLegenda.length){ toast('Gere a legenda dos cortes primeiro (quadro Legenda, acima). A dublagem usa essa fala.','erro'); return; }
    const ids=alvo();
    setDub({txt:'Começando',pct:0}); setOuvir('');
    try{
      const n=await dublar(ids,voz,volOrig,(txt,pct)=>setDub({txt,pct}));
      toast(`Dublagem pronta em ${n} corte(s). A legenda já está em português e a voz entra no vídeo final.`,'ok');
    }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }
    finally{ setDub(null); }
  }
  function tocar(){ const d=pegarDub(atual.id); if(!d) return; if(ouvir) URL.revokeObjectURL(ouvir); setOuvir(URL.createObjectURL(wavDaDub(d))); }
  // Tarjas: a última escolha fica guardada para os próximos vídeos.
  const tj:Tarja=atual.tarja||(()=>{ try{ return {...TARJA_PADRAO,...JSON.parse(ler('studio_tarja','{}'))}; }catch{ return TARJA_PADRAO; } })();
  const mudarTarja=(pt:Partial<Tarja>|null)=>{ if(!pt){ mudar(alvo(),{tarja:null}); return; } const n={...tj,...pt}; gravar('studio_tarja',JSON.stringify(n)); mudar(alvo(),{tarja:n.topo||n.base?n:null}); };
  const ondeTarja=!atual.tarja?'nao':atual.tarja.topo&&atual.tarja.base?'duas':atual.tarja.topo?'topo':'base';
  const efeitos=[...effectPresets.map(p=>({id:p.id,nome:p.nome})),{id:'nenhum',nome:'Sem efeito'}];
  return <>
   <section className="panel results-bar">
    <div className="result-summary"><strong>Edição de {clips.length} corte(s)</strong> • escolha o tipo de legenda, as tarjas, o template e o @. Tudo aqui aparece na prévia e no vídeo final.</div>
    <div className="result-controls">
     <button className="subtle" onClick={onVoltar}><ArrowLeft size={15}/> Voltar aos cortes</button>
     <button className="subtle" disabled={exportando} onClick={onZip}>{exportando?<Loader2 size={15} className="spin"/>:<Package size={15}/>} Baixar todos (ZIP)</button>
     <button className="primary" disabled={!marcados.length} onClick={()=>onProximo(marcados)}>Próximo: postar {marcados.length<clips.length?`os ${marcados.length} marcados`:''} <ArrowRight size={15}/></button>
    </div>
   </section>
   <div className="edicao">
    <section className="panel edicao-prev">
     <div className="edicao-nav">
      <button className="icon-btn" disabled={i===0} onClick={()=>setI(i-1)} aria-label="Corte anterior"><ChevronLeft size={18}/></button>
      <span><b>Corte {i+1} de {clips.length}</b> • {tm(atual.inicio)}–{tm(atual.fim)}</span>
      <button className="icon-btn" disabled={i>=clips.length-1} onClick={()=>setI(i+1)} aria-label="Próximo corte"><ChevronRight size={18}/></button>
     </div>
     <Preview key={atual.id} url={atual.video?.url||projeto.url} inicio={atual.inicio} fim={atual.fim} formato={atual.formato} opts={opts}/>
     <label className="mt">Título deste corte<input value={atual.titulo} maxLength={100} onChange={e=>mudar([atual.id],{titulo:e.target.value})}/></label>
     <label className="mt">Hashtags do post<input value={(atual.hashtags||[]).join(' ')} placeholder="#shorts #reels" onChange={e=>mudar([atual.id],{hashtags:e.target.value.split(/\s+/).filter(Boolean).map(h=>h.startsWith('#')?h:'#'+h)})}/></label>
     <label className="mt">Texto de gancho no topo (opcional)<input value={atual.gancho_texto} maxLength={60} placeholder="Ex.: ELE NÃO ESPERAVA ISSO" onChange={e=>mudar([atual.id],{gancho_texto:e.target.value})}/></label>
     <button className="subtle mt" onClick={()=>onEditar(atual)}><Pencil size={14}/> Ajustar início, fim e legenda deste corte</button>
     <div className="tira-head"><span><b>{marcados.length} de {clips.length}</b> marcados para mudar em lote e postar</span><button className="link-btn" onClick={()=>setFora(new Set())}>Marcar todos</button><button className="link-btn" onClick={()=>setFora(new Set(clips.map(c=>c.id)))}>Desmarcar todos</button></div>
     <div className="edicao-tira">{clips.map((c,k)=><div key={c.id} className={'mini-wrap '+(fora.has(c.id)?'fora':'')}><button className={'edicao-mini '+(k===i?'on':'')} onClick={()=>setI(k)} title={c.titulo}>{c.thumb?<img src={c.thumb} alt=""/>:<Film size={16}/>}<small>{k+1}</small></button><input type="checkbox" className="mini-check" checked={!fora.has(c.id)} onChange={e=>marcar(c.id,e.target.checked)} aria-label={'Marcar corte '+(k+1)}/></div>)}</div>
    </section>
    <div className="edicao-lado">
     <section className="panel legenda-lote">
      <div className="section-head"><h2><Captions size={18}/> Legenda</h2>{!semLegenda.length&&<span className="tag ok"><CheckCircle2 size={12}/> Todos com legenda</span>}</div>
      <p className="hint">{semLegenda.length?`${semLegenda.length} de ${clips.length} corte(s) ainda sem legenda. A legenda é feita só desses trechos, por isso é rápida.`:'Se quiser, gere de novo para refazer a legenda dos cortes.'}</p>
      {leg?<div className="dl-box"><div className="row"><Loader2 size={16} className="spin"/><span><b>{leg.txt}</b> {leg.pct}%</span></div><div className="dl-bar"><i style={{width:Math.max(3,leg.pct)+'%'}}/></div></div>
      :<div className="row-gap left">
        {settings.geminiKey&&<button className="primary" onClick={()=>legendar('gemini')}><Captions size={15}/> Gerar legenda pelo Gemini (rápido)</button>}
        <button className={settings.geminiKey?'subtle':'primary'} onClick={()=>legendar('auto')}><Captions size={15}/> Gerar legenda no aparelho</button>
      </div>}
      <div className="field mt"><span className="field-label"><Type size={14}/> Tipo de legenda {!igual('legenda')&&<span className="tag">varia entre os cortes</span>}</span>
       <div className="leg-tipos" role="radiogroup" aria-label="Tipo de legenda">
        {captionPresets.map(p=><button key={p.id} role="radio" aria-checked={atual.legenda===p.id} className={'leg-tipo '+(atual.legenda===p.id?'on':'')} onClick={()=>mudar(alvo(),{legenda:p.id})} title={p.nome}>
          <span className="leg-amostra" style={{color:p.textColor,fontWeight:+p.fontWeight||800,WebkitTextStroke:p.outlineWidth?`1px ${p.outlineColor}`:undefined}}>Sua <i style={{color:p.highlightColor}}>fala</i> aqui</span><small>{p.nome}</small></button>)}
        <button role="radio" aria-checked={!atual.legenda} className={'leg-tipo '+(!atual.legenda?'on':'')} onClick={()=>mudar(alvo(),{legenda:''})}><span className="leg-amostra sem">—</span><small>Sem legenda</small></button>
       </div>
       <small className="hint">{todos?`Vale para os ${marcados.length} corte(s) marcados.`:`Só o corte ${i+1}.`} A prévia ao lado já mostra como fica.</small>
      </div>
      {semLegenda.some(c=>c.id===atual.id)&&atual.legenda&&<p className="hint">Este corte ainda não tem legenda. Gere nos botões acima.</p>}
     </section>
     <section className="panel tarjas">
      <div className="section-head"><h2><RectangleHorizontal size={18}/> Tarjas no vídeo</h2>{!igual('tarja')&&clips.some(c=>c.tarja)&&<span className="tag">varia entre os cortes</span>}</div>
      <p className="hint">Faixas de cor em cima e embaixo do vídeo, com texto se você quiser. {todos?`Vale para os ${marcados.length} corte(s) marcados.`:`Só o corte ${i+1}.`}</p>
      <div className="seg" role="radiogroup" aria-label="Onde colocar as tarjas">
       {([['nao','Sem tarjas'],['duas','Em cima e embaixo'],['topo','Só em cima'],['base','Só embaixo']] as const).map(([id,n])=><button key={id} role="radio" aria-checked={ondeTarja===id} className={ondeTarja===id?'on':''} onClick={()=>id==='nao'?mudarTarja(null):mudarTarja({topo:id!=='base',base:id!=='topo'})}>{n}</button>)}
      </div>
      {atual.tarja&&<>
       {atual.tarja.topo&&<label className="mt">Texto da tarja de cima (opcional)<input value={tj.textoTopo} maxLength={60} placeholder="Ex.: PARTE 1" onChange={e=>mudarTarja({textoTopo:e.target.value})}/></label>}
       {atual.tarja.base&&<label className="mt">Texto da tarja de baixo (opcional)<input value={tj.textoBase} maxLength={60} placeholder="Ex.: @seucanal • siga para a parte 2" onChange={e=>mudarTarja({textoBase:e.target.value})}/></label>}
       <div className="small-grid mt">
        <label>Altura<select value={tj.altura} onChange={e=>mudarTarja({altura:+e.target.value})}><option value={8}>Fina</option><option value={12}>Média</option><option value={16}>Grossa</option><option value={22}>Bem grossa</option></select></label>
        <label>Cor da tarja<input type="color" value={tj.cor} onChange={e=>mudarTarja({cor:e.target.value})}/></label>
        <label>Cor do texto<input type="color" value={tj.corTexto} onChange={e=>mudarTarja({corTexto:e.target.value})}/></label>
       </div>
       {atual.tarja.topo&&atual.gancho_texto&&<p className="hint">O texto de gancho desce para ficar logo abaixo da tarja de cima.</p>}
      </>}
     </section>
     <section className="panel dub-lote">
      <div className="section-head"><h2><Languages size={18}/> Dublar em português</h2>{clips.every(c=>c.dublado)&&<span className="tag ok"><CheckCircle2 size={12}/> Todos dublados</span>}</div>
      <p className="hint">O Gemini traduz a fala, troca a legenda para português e grava uma voz em português por cima do áudio original abaixado. {todos?`Vale para os ${marcados.length} corte(s) marcados.`:`Só o corte ${i+1}.`}</p>
      {!settings.geminiKey?<p className="hint">Coloque a chave do Gemini (grátis) em Chaves e ajustes para dublar.</p>
      :dub?<div className="dl-box"><div className="row"><Loader2 size={16} className="spin"/><span><b>{dub.txt}</b> {dub.pct}%</span></div><div className="dl-bar"><i style={{width:Math.max(3,dub.pct)+'%'}}/></div></div>
      :<>
       <div className="small-grid">
        <label>Voz<select value={voz} onChange={e=>{ setVoz(e.target.value); gravar('studio_dub_voz',e.target.value); }}>{VOZES.map(([id,n])=><option key={id} value={id}>{n} ({id})</option>)}</select></label>
        <label>Áudio original<select value={volOrig} onChange={e=>{ setVolOrig(+e.target.value); gravar('studio_dub_vol',e.target.value); }}><option value={0}>Sem áudio original</option><option value={0.12}>Bem baixinho (12%)</option><option value={0.25}>Baixo (25%)</option><option value={0.4}>Médio (40%)</option></select></label>
       </div>
       <div className="row-gap left mt">
        <button className="primary" onClick={dublarTodos}><Languages size={15}/> {atual.dublado||(todos&&clips.some(c=>c.dublado))?'Dublar de novo':'Dublar em português'}</button>
        {atual.dublado&&pegarDub(atual.id)&&<button className="subtle" onClick={tocar}><Play size={15}/> Ouvir a voz deste corte</button>}
       </div>
       {ouvir&&<audio className="mt" src={ouvir} controls autoPlay style={{width:'100%'}}/>}
       {atual.dublado&&!pegarDub(atual.id)&&<p className="hint">A voz deste corte se perdeu ao recarregar a página. Toque em Dublar de novo.</p>}
      </>}
      <p className="hint">Cada dublagem gasta alguns pedidos da cota grátis do Gemini. A voz não aparece na prévia, só no vídeo exportado e no botão Ouvir.</p>
     </section>
     <section className="panel">
      <div className="section-head"><h2><Wand2 size={18}/> Estilo dos cortes</h2></div>
      <label className="check big"><input type="checkbox" checked={todos} onChange={e=>setTodos(e.target.checked)}/> Aplicar nos {marcados.length} corte(s) marcados na tira (desmarque para mudar só o corte {i+1})</label>
      <label className="mt"><span className="label-row">Efeito e enquadramento {!igual('efeito')&&<span className="tag">varia entre os cortes</span>}</span>
       <select value={atual.efeito} onChange={e=>mudar(alvo(),{efeito:e.target.value})}>{efeitos.map(p=><option key={p.id} value={p.id}>{p.nome}</option>)}</select></label>
      <label className="mt"><span className="label-row">Template e @ {!igual('semTemplate')&&<span className="tag">varia entre os cortes</span>}</span>
       <select value={atual.semTemplate?'nao':'sim'} onChange={e=>mudar(alvo(),{semTemplate:e.target.value==='nao'})}><option value="sim">Usar o template</option><option value="nao">Sem template</option></select></label>
      <div className="field mt"><span className="field-label">Formato</span><div className="seg">{(['9:16','1:1','16:9'] as Formato[]).map(f=><button key={f} className={atual.formato===f?'on':''} onClick={()=>mudar(alvo(),{formato:f})}>{f}</button>)}</div></div>
     </section>
     <TemplateForm titulo="Template e @ do canal"/>
     <p className="hint"><LayoutTemplate size={13}/> O template fica salvo para os próximos vídeos. Para tirar de alguns cortes, marque-os na tira e escolha Sem template acima.</p>
    </div>
   </div>
  </>;
}
