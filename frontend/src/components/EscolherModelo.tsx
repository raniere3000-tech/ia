import { LayoutTemplate, RotateCcw, Save } from 'lucide-react';
import { useApp } from '../state';
import type { Clip } from '../lib/analyze';
import { LAYOUTS, aplicarModelo, modeloDoCorte, semModelo, type Layout, type VisualClip } from '../lib/modelos';

/**
 * "Selecionar template" da edição manual. Escolher aplica uma cópia do template no corte;
 * os ajustes feitos depois ficam só no corte, a não ser que a pessoa peça para salvar no template.
 */
export default function EscolherModelo({clip,aplicar,ajustar,escopo}:{clip:Clip;aplicar:(p:Partial<Clip>)=>void;ajustar:(p:Partial<Clip>)=>void;escopo?:string}){
  const {modelos,setModelos,template,toast,go}=useApp();
  const m=modelos.find(x=>x.id===clip.modelo);
  const antiga=!clip.modelo&&!clip.semTemplate&&template.ativo;
  const valor=clip.modelo&&clip.visual?clip.modelo:antiga?'_antiga':clip.semTemplate||!template.ativo?'_sem':'_antiga';
  const v=clip.visual||null;
  const setV=(p:Partial<VisualClip>)=>{ if(v) ajustar({visual:{...v,...p}}); };
  function escolher(id:string){
    if(id==='_sem') aplicar(semModelo());
    else if(id==='_antiga') aplicar({modelo:'',visual:null,semTemplate:false});
    else{ const novo=modelos.find(x=>x.id===id); if(novo) aplicar(aplicarModelo(novo)); }
  }
  function salvarNoModelo(){
    if(!m) return;
    if(!confirm(`Salvar os ajustes deste corte no template "${m.nome}"? Os próximos cortes com este template (manuais e dos agentes) passam a sair assim.`)) return;
    setModelos(modelos.map(x=>x.id===m.id?modeloDoCorte(x,clip):x));
    toast(`Template "${m.nome}" atualizado com os ajustes deste corte.`,'ok');
  }
  return <div className="escolher-modelo">
    <label><span className="label-row"><LayoutTemplate size={14}/> Selecionar template {escopo&&<small className="hint">{escopo}</small>}</span>
      <select value={valor} onChange={e=>escolher(e.target.value)} aria-label="Selecionar template">
        <option value="_sem">Sem template</option>
        {template.ativo&&<option value="_antiga">Só a marca antiga (logo e @)</option>}
        {modelos.map(x=><option key={x.id} value={x.id}>{x.nome}</option>)}
        {clip.modelo&&!m&&clip.visual&&<option value={clip.modelo}>Template apagado (ajustes mantidos)</option>}
      </select></label>
    {v&&<div className="modelo-ajustes">
      <span className="field-label">Ajustes só deste corte</span>
      <div className="small-grid">
        <label>Composição<select value={v.layout} onChange={e=>setV({layout:e.target.value as Layout})}>{LAYOUTS.map(([id,n])=><option key={id} value={id}>{n}</option>)}</select></label>
        <label>Altura da legenda<select value={v.legendaPos} onChange={e=>setV({legendaPos:e.target.value as VisualClip['legendaPos']})}><option value="baixo">Embaixo</option><option value="meio">No meio</option></select></label>
      </div>
      {v.layout!=='gameplay-streamer'&&<label>Zoom: {Math.round(v.zoom*100)}%<input type="range" min={100} max={160} step={5} value={Math.round(v.zoom*100)} onChange={e=>setV({zoom:+e.target.value/100})}/></label>}
      {v.layout==='cheio'&&<label>Olhar para: {v.posX<0.4?'esquerda':v.posX>0.6?'direita':'centro'}<input type="range" min={0} max={100} value={Math.round(v.posX*100)} onChange={e=>setV({posX:+e.target.value/100})}/></label>}
      {v.layout==='gameplay-streamer'&&<label>Altura do gameplay: {v.divisao}%<input type="range" min={35} max={80} value={v.divisao} onChange={e=>setV({divisao:+e.target.value})}/></label>}
      <label className="check"><input type="checkbox" checked={v.gancho} onChange={e=>setV({gancho:e.target.checked})}/> Mostrar o texto de gancho</label>
      <div className="row-gap left">
        {m&&<button className="subtle sm" onClick={salvarNoModelo}><Save size={13}/> Salvar estes ajustes no template</button>}
        {m&&<button className="subtle sm" onClick={()=>ajustar(aplicarModelo(m))}><RotateCcw size={13}/> Voltar ao template salvo</button>}
      </div>
      <small className="hint">Mexer aqui não muda o template salvo. Para criar ou editar templates, abra <button className="link-btn" onClick={()=>go('templates')}>Templates</button>.</small>
    </div>}
  </div>;
}
