import { useState } from 'react';
import { Gauge, Play, Sparkles } from 'lucide-react';
import { useApp } from '../state';
import { api, cabAuth, urlServidor } from '../lib/api';
import { COMPONENTES, ESTILOS, estiloInfo, usoPadrao, type EstiloUso } from '../lib/estilosVisuais';
import { useCfg, useServidor, erroTexto } from './Servidor2';

type Status = {id:string;status:'ready'|'beta'|'unavailable';motivo:string;custo:string;pipelines:string[];componentes:string[];medido:{por_segundo_de_video:number;resolucao:string}|null};
const ROTULO={ready:'pronto',beta:'beta',unavailable:'indisponível neste aparelho'} as const;

/**
 * Escolha do estilo visual (biblioteca compartilhada). Mostra o estado de verdade, vindo do servidor: pronto, beta ou
 * indisponível. Sem servidor ligado, o estilo ainda vale para a prévia e a exportação no navegador.
 */
export default function EstiloVisual({valor,onChange,aoVerSem}:{valor:EstiloUso|null|undefined;onChange:(e:EstiloUso|null)=>void;aoVerSem?:(ver:boolean)=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const st=useServidor(c=>api<{estilos:Status[]}>(c,'GET','/estilos-visuais'),0,[]);
  const [demo,setDemo]=useState<{id:string;url:string}|null>(null);
  const [trab,setTrab]=useState('');
  const info=valor?estiloInfo(valor.id):null;
  const s=valor?st.dados?.estilos.find(x=>x.id===valor.id):undefined;
  const comp=s?.componentes?.length?s.componentes:Object.keys(COMPONENTES);
  async function verDemo(){
    if(!valor) return; setTrab('demo');
    try{ const r=await fetch(urlServidor(cfg,`/estilos-visuais/${valor.id}/demo`),{headers:cabAuth(cfg.servidorToken)});
      if(!r.ok) throw new Error((await r.json().catch(()=>({}))).detail||'O celular não conseguiu montar a demonstração.');
      setDemo({id:valor.id,url:URL.createObjectURL(await r.blob())});
    }catch(e){ toast(erroTexto(e),'erro'); } finally{ setTrab(''); }
  }
  async function medir(){
    if(!valor) return; setTrab('medir');
    try{ await api(cfg,'POST','/estilos-visuais/medir',{id:valor.id}); st.recarregar(); toast('Custo medido neste aparelho.','ok'); }
    catch(e){ toast(erroTexto(e),'erro'); } finally{ setTrab(''); }
  }
  return <div className="estilo-visual">
    <label><span className="label-row"><Sparkles size={14}/> Estilo visual</span>
      <select value={valor?.id||''} onChange={e=>onChange(e.target.value?usoPadrao(e.target.value):null)} aria-label="Estilo visual">
        <option value="">Sem estilo visual</option>
        {ESTILOS.map(e=>{ const x=st.dados?.estilos.find(y=>y.id===e.id); return <option key={e.id} value={e.id} disabled={x?.status==='unavailable'}>{e.nome}{x?` (${ROTULO[x.status]})`:''}</option>; })}
      </select></label>
    {valor&&info&&<div className="estilo-detalhe">
      <p className="hint tight"><b>{info.nome}</b>: {info.desc}</p>
      {(s?.motivo||info.beta)&&<p className="hint tight">{s?.status==='unavailable'?'Não dá para usar no servidor: ':'Aviso: '}{s?.motivo||info.beta}</p>}
      {!s&&<p className="hint tight">Servidor não conferido: a prévia e a exportação no navegador funcionam; para o servidor, ligue o celular.</p>}
      <label>Força: {Math.round(valor.forca*100)}%<input type="range" min={0} max={100} value={Math.round(valor.forca*100)} onChange={e=>onChange({...valor,forca:+e.target.value/100})}/></label>
      <div className="estilo-comps">{comp.map(c=><label key={c} className="check"><input type="checkbox" checked={!valor.off.includes(c)} onChange={e=>onChange({...valor,off:e.target.checked?valor.off.filter(x=>x!==c):[...valor.off,c]})}/> {COMPONENTES[c]||c}</label>)}</div>
      {valor.id==='sports_replay'&&<label>Texto do selo<input value={valor.texto} maxLength={24} placeholder="REPLAY" onChange={e=>onChange({...valor,texto:e.target.value})}/></label>}
      <div className="row-gap left">
        {aoVerSem&&<button className="subtle sm" onPointerDown={()=>aoVerSem(true)} onPointerUp={()=>aoVerSem(false)} onPointerLeave={()=>aoVerSem(false)}>Segure para ver sem o estilo</button>}
        {cfg.servidor&&<button className="subtle sm" onClick={verDemo} disabled={!!trab||s?.status==='unavailable'}><Play size={13}/> {trab==='demo'?'Montando…':'Ver demonstração'}</button>}
        {cfg.servidor&&<button className="subtle sm" onClick={medir} disabled={!!trab||s?.status==='unavailable'}><Gauge size={13}/> {trab==='medir'?'Medindo…':'Medir neste celular'}</button>}
      </div>
      <small className="hint">Custo: {s?.medido?`${s.medido.por_segundo_de_video} s de trabalho para cada 1 s de vídeo (medido em ${s.medido.resolucao})`:'não medido neste aparelho'}. A demonstração usa um vídeo de teste gerado pelo servidor, não o seu corte.</small>
      {demo&&demo.id===valor.id&&<video src={demo.url} controls playsInline className="estilo-demo"/>}
    </div>}
  </div>;
}
