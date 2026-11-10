import { useMemo, useState } from 'react';
import { Copy, Download, Save, Minus, Plus, Crosshair } from 'lucide-react';
import { Modal } from './Help';
import Preview from './Preview';
import { useApp, captionPresets, effectPresets } from '../state';
import { notaFinal, nota10, type Clip, type Formato } from '../lib/analyze';
import { tm, parseTime } from '../lib/store';
import type { Cue } from '../lib/captions';

export default function Editor({clip,onClose,onSave,onDuplicate,onExport}:{clip:Clip;onClose:()=>void;onSave:(c:Clip,cues:Cue[])=>void;onDuplicate:(c:Clip)=>void;onExport:(c:Clip)=>void}){
  const {projeto,template}=useApp();
  const [c,setC]=useState<Clip>(clip);
  const [cues,setCues]=useState<Cue[]>(projeto.cues);
  const set=(p:Partial<Clip>)=>setC(x=>({...x,...p}));
  const dur=projeto.duracao;
  const setIni=(v:number)=>set({inicio:Math.max(0,Math.min(v,c.fim-1))});
  const setFim=(v:number)=>set({fim:Math.min(dur,Math.max(v,c.inicio+1))});
  const legenda=captionPresets.find(p=>p.id===c.legenda)||null;
  const opts=useMemo(()=>({legenda,efeito:c.efeito,cues,gancho:c.gancho_texto,accent:legenda?.highlightColor||template.cor,template}),[legenda,c.efeito,cues,c.gancho_texto,template]);
  const falas=cues.map((q,i)=>({q,i})).filter(({q})=>q.end>c.inicio&&q.start<c.fim);
  const salvar=()=>{ onSave({...c,nota_final:notaFinal(c.notas),nota_10:nota10(notaFinal(c.notas))},cues); };
  const TimeInput=({label,value,onChange}:{label:string;value:number;onChange:(v:number)=>void})=><label>{label}<div className="time-row"><button className="icon-btn" onClick={()=>onChange(value-1)} aria-label="Menos 1 segundo"><Minus size={14}/></button><input key={value} defaultValue={tm(value)} onBlur={e=>{const v=parseTime(e.target.value); if(!isNaN(v)) onChange(v);}} onKeyDown={e=>{if(e.key==='Enter')(e.target as HTMLInputElement).blur()}}/><button className="icon-btn" onClick={()=>onChange(value+1)} aria-label="Mais 1 segundo"><Plus size={14}/></button></div></label>;
  return <Modal title="Editar corte" onClose={onClose} wide>
   <div className="editor">
    <div className="editor-left">
     <Preview url={projeto.url} inicio={c.inicio} fim={c.fim} formato={c.formato} opts={opts}/>
     <div className="seg">{(['9:16','1:1','16:9'] as Formato[]).map(f=><button key={f} className={c.formato===f?'on':''} onClick={()=>set({formato:f})}>{f}</button>)}</div>
    </div>
    <div className="editor-right">
     <label>Título<input value={c.titulo} maxLength={80} onChange={e=>set({titulo:e.target.value})}/></label>
     <div className="small-grid">
      <TimeInput label="Início" value={c.inicio} onChange={setIni}/>
      <TimeInput label="Fim" value={c.fim} onChange={setFim}/>
     </div>
     <p className="hint tight"><Crosshair size={13}/> Duração: {Math.round(c.fim-c.inicio)} s • Use os botões − e + para ajustar de 1 em 1 segundo, ou digite o tempo (min:seg).</p>
     <div className="small-grid">
      <label>Estilo da legenda<select value={c.legenda} onChange={e=>set({legenda:e.target.value})}><option value="">Sem legenda</option>{captionPresets.map(p=><option key={p.id} value={p.id}>{p.nome}</option>)}</select></label>
      <label>Efeito<select value={c.efeito} onChange={e=>set({efeito:e.target.value})}><option value="nenhum">Sem efeito (preencher a tela)</option>{effectPresets.map(p=><option key={p.id} value={p.id}>{p.nome}</option>)}</select></label>
     </div>
     <label>Texto de gancho no topo (opcional)<input value={c.gancho_texto} maxLength={80} placeholder="Ex.: ELE NÃO ESPERAVA ISSO" onChange={e=>set({gancho_texto:e.target.value})}/></label>
     <div className="cue-edit">
      <div className="cue-head"><strong>Legenda deste corte</strong><small>{falas.length?'Clique no texto para corrigir uma palavra.':'Sem falas neste trecho. Gere legendas automáticas ou envie um .srt.'}</small></div>
      {falas.map(({q,i})=><div key={i} className="cue-line"><span>{tm(q.start-c.inicio)}</span><input value={q.text} onChange={e=>setCues(cs=>cs.map((x,j)=>j===i?{...x,text:e.target.value}:x))}/></div>)}
     </div>
     <div className="editor-actions">
      <button className="primary" onClick={salvar}><Save size={16}/> Salvar alterações</button>
      <button className="subtle" onClick={()=>{ salvar(); onExport({...c}); }}><Download size={16}/> Salvar e exportar</button>
      <button className="subtle" onClick={()=>onDuplicate({...c})}><Copy size={16}/> Duplicar como nova versão</button>
     </div>
    </div>
   </div>
  </Modal>;
}
