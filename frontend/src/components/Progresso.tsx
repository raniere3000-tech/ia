import { tempoTexto } from '../lib/alertas';

/** Barra de progresso com a porcentagem e a previsão do que falta (calculada pelo ritmo real deste celular). */
export default function Progresso({pct,restante,comecaEm,estimado,status}:{pct?:number|null;restante?:number|null;comecaEm?:number|null;estimado?:boolean;status?:string}){
  const rodando=status!=='na_fila'&&status!=='agendado'&&status!=='aguardando_tentativa';
  const p=Math.max(0,Math.min(100,Math.round(pct||0)));
  return <div className="progresso">
    <div className="progresso-barra"><div style={{width:`${rodando?Math.max(p,2):0}%`}}/></div>
    <small className="muted">{rodando?<><b>{p}%</b>{restante!=null&&restante>0?<> · falta {tempoTexto(restante)}{estimado?' (estimativa)':''}</>:null}</>
      :<>na fila{comecaEm?<> · começa em {tempoTexto(comecaEm)}</>:null}{restante?<> · leva {tempoTexto(restante)}</>:null}</>}</small>
  </div>;
}
