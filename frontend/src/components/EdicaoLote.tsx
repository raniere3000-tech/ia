import { useMemo, useState } from 'react';
import { ArrowLeft, ArrowRight, ChevronLeft, ChevronRight, Film, Loader2, Package, Pencil, Type, Wand2, LayoutTemplate, Captions, CheckCircle2 } from 'lucide-react';
import { useApp, captionPresets, effectPresets } from '../state';
import Preview from './Preview';
import { TemplateForm } from '../pages/Templates';
import type { Clip, Formato } from '../lib/analyze';
import { tm } from '../lib/store';

type Props = {
  clips:Clip[];
  mudar:(ids:string[],p:Partial<Clip>)=>void;
  onEditar:(c:Clip)=>void;
  onVoltar:()=>void; onProximo:()=>void; onZip:()=>void;
  exportando:boolean;
  gerarLegendas:(ids:string[],via:'auto'|'gemini',onStatus:(s:string,pct:number)=>void)=>Promise<number>;
};

/** Etapa 3: edição em lote dos cortes escolhidos (template, @, legenda, efeito e formato). */
export default function EdicaoLote({clips,mudar,onEditar,onVoltar,onProximo,onZip,exportando,gerarLegendas}:Props){
  const {projeto,template,settings,toast}=useApp();
  const [leg,setLeg]=useState<{txt:string;pct:number}|null>(null);
  const [i,setI]=useState(0); const [todos,setTodos]=useState(true);
  const atual=clips[Math.min(i,clips.length-1)];
  const legenda=captionPresets.find(p=>p.id===atual?.legenda)||null;
  const opts=useMemo(()=>({legenda,efeito:atual?.efeito||'nenhum',cues:projeto.cues,gancho:atual?.gancho_texto||'',accent:legenda?.highlightColor||template.cor,template}),[legenda,atual?.efeito,atual?.gancho_texto,projeto.cues,template]);
  if(!atual) return <section className="panel empty-state"><h2>Nenhum corte escolhido</h2><button className="primary" onClick={onVoltar}><ArrowLeft size={16}/> Voltar e escolher</button></section>;
  const alvo=()=>todos?clips.map(c=>c.id):[atual.id];
  const igual=(k:keyof Clip)=>clips.every(c=>c[k]===atual[k]);
  const semLegenda=clips.filter(c=>!c.legendaOk&&!projeto.cues.some(q=>q.end>c.inicio&&q.start<c.fim));
  async function legendar(via:'auto'|'gemini'){
    const ids=(semLegenda.length?semLegenda:clips).map(c=>c.id);
    setLeg({txt:'Começando',pct:0});
    try{
      const n=await gerarLegendas(ids,via,(txt,pct)=>setLeg({txt,pct}));
      toast(n?`Legenda pronta em ${ids.length} corte(s).`:'Não encontramos fala nesses cortes.',n?'ok':'info');
    }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }
    finally{ setLeg(null); }
  }
  const efeitos=[...effectPresets.map(p=>({id:p.id,nome:p.nome})),{id:'nenhum',nome:'Sem efeito'}];
  return <>
   <section className="panel results-bar">
    <div className="result-summary"><strong>Edição de {clips.length} corte(s)</strong> • coloque seu template, o @ e o estilo da legenda. Tudo aqui aparece na prévia e no vídeo final.</div>
    <div className="result-controls">
     <button className="subtle" onClick={onVoltar}><ArrowLeft size={15}/> Voltar aos cortes</button>
     <button className="subtle" disabled={exportando} onClick={onZip}>{exportando?<Loader2 size={15} className="spin"/>:<Package size={15}/>} Baixar todos (ZIP)</button>
     <button className="primary" onClick={onProximo}>Próximo: postar <ArrowRight size={15}/></button>
    </div>
   </section>
   <div className="edicao">
    <section className="panel edicao-prev">
     <div className="edicao-nav">
      <button className="icon-btn" disabled={i===0} onClick={()=>setI(i-1)} aria-label="Corte anterior"><ChevronLeft size={18}/></button>
      <span><b>Corte {i+1} de {clips.length}</b> • {tm(atual.inicio)}–{tm(atual.fim)}</span>
      <button className="icon-btn" disabled={i>=clips.length-1} onClick={()=>setI(i+1)} aria-label="Próximo corte"><ChevronRight size={18}/></button>
     </div>
     <Preview key={atual.id} url={projeto.url} inicio={atual.inicio} fim={atual.fim} formato={atual.formato} opts={opts}/>
     <label className="mt">Título deste corte<input value={atual.titulo} maxLength={100} onChange={e=>mudar([atual.id],{titulo:e.target.value})}/></label>
     <label className="mt">Texto de gancho no topo (opcional)<input value={atual.gancho_texto} maxLength={60} placeholder="Ex.: ELE NÃO ESPERAVA ISSO" onChange={e=>mudar([atual.id],{gancho_texto:e.target.value})}/></label>
     <button className="subtle mt" onClick={()=>onEditar(atual)}><Pencil size={14}/> Ajustar início, fim e legenda deste corte</button>
     <div className="edicao-tira">{clips.map((c,k)=><button key={c.id} className={'edicao-mini '+(k===i?'on':'')} onClick={()=>setI(k)} title={c.titulo}>{c.thumb?<img src={c.thumb} alt=""/>:<Film size={16}/>}<small>{k+1}</small></button>)}</div>
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
     </section>
     <section className="panel">
      <div className="section-head"><h2><Wand2 size={18}/> Estilo dos cortes</h2></div>
      <label className="check big"><input type="checkbox" checked={todos} onChange={e=>setTodos(e.target.checked)}/> Aplicar em todos os {clips.length} cortes (desmarque para mudar só o corte {i+1})</label>
      <label className="mt"><span className="label-row"><Type size={14}/> Estilo da legenda {!igual('legenda')&&<span className="tag">varia entre os cortes</span>}</span>
       <select value={atual.legenda} onChange={e=>mudar(alvo(),{legenda:e.target.value})}><option value="">Sem legenda</option>{captionPresets.map(p=><option key={p.id} value={p.id}>{p.nome}</option>)}</select></label>
      {semLegenda.some(c=>c.id===atual.id)&&atual.legenda&&<p className="hint">Este corte ainda não tem legenda. Gere no quadro Legenda, acima.</p>}
      <label className="mt"><span className="label-row">Efeito e enquadramento {!igual('efeito')&&<span className="tag">varia entre os cortes</span>}</span>
       <select value={atual.efeito} onChange={e=>mudar(alvo(),{efeito:e.target.value})}>{efeitos.map(p=><option key={p.id} value={p.id}>{p.nome}</option>)}</select></label>
      <div className="field mt"><span className="field-label">Formato</span><div className="seg">{(['9:16','1:1','16:9'] as Formato[]).map(f=><button key={f} className={atual.formato===f?'on':''} onClick={()=>mudar(alvo(),{formato:f})}>{f}</button>)}</div></div>
     </section>
     <TemplateForm titulo="Template e @ do canal"/>
     <p className="hint"><LayoutTemplate size={13}/> O template vale para todos os cortes e fica salvo para os próximos vídeos.</p>
    </div>
   </div>
  </>;
}
