import { ArrowRight, PlayCircle } from 'lucide-react';
import { useApp } from '../state';

type Item={t:string;d:string;to:'cortes'|'manual'|'vozes'|'video'};
/** Trabalhos guardados neste navegador, para continuar de onde parou (mesma leitura que o Início sempre fez). */
export function trabalhosSalvos(nCortes:number):Item[]{
  const ler=(k:string)=>{ try{ return JSON.parse(localStorage.getItem(k)||'null'); }catch{ return null; } };
  const out:Item[]=[];
  if(nCortes) out.push({t:'Cortes',d:`${nCortes} corte(s) prontos para editar`,to:'cortes'});
  const man=ler('studio_manual'); if(man?.texto?.trim()) out.push({t:'Montagem manual',d:man.sinc?.quadros?.length?`${man.sinc.quadros.length} quadros sincronizados`:'Roteiro de quadros salvo',to:'manual'});
  let voz=false; try{ voz=!!localStorage.getItem('studio_vozes_projeto'); }catch{ /* sem armazenamento */ }
  if(voz) out.push({t:'Estúdio de vozes',d:'Projeto de vozes aberto por último',to:'vozes'});
  const vc=ler('studio_video_codigo'); if(vc?.cenas?.length) out.push({t:'Vídeo animado',d:`${vc.titulo||'Roteiro'} • ${vc.cenas.length} cenas`,to:'video'});
  return out;
}

export default function Continuar({filtro,area,vazio}:{filtro?:Item['to'][];area?:string;vazio?:string}){
  const {go,projeto}=useApp();
  const l=trabalhosSalvos(projeto.clips.filter(c=>!c.descartado).length).filter(x=>!filtro||filtro.includes(x.to));
  if(!l.length) return vazio?<p className="hint">{vazio}</p>:null;
  return <section className="panel">
    <div className="section-head"><h2><PlayCircle size={18}/> Continuar projeto</h2></div>
    <div className="inicio-cont">{l.map(c=><button key={c.t} className="inicio-cont-item" onClick={()=>go(c.to,'',area)}><b>{c.t}</b><small>{c.d}</small><ArrowRight size={15}/></button>)}</div>
  </section>;
}
