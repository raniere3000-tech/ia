import { Loader2, WifiOff } from 'lucide-react';
import { duracaoTexto, horaTexto } from '../lib/api';
import { PERIODOS, type AgenteResumo, type Periodo, type Resumo } from '../lib/dashboard';

export function MediaDuracao({t}:{t:AgenteResumo['tempos_medios']}){
  const l=Object.values(t||{}); if(!l.length) return null;
  const tot=l.reduce((a,x)=>a+x.segundos*x.amostras,0), n=l.reduce((a,x)=>a+x.amostras,0);
  return <span title={`Média medida de ${n} trabalho(s) concluído(s) neste servidor`}><b>{duracaoTexto(tot/n)}</b>média medida</span>;
}

/** Texto do trabalho atual: etapa, % só quando o servidor mede, tempo ativo e previsão só quando medida. */
export function TrabalhoAtual({a,agora}:{a:AgenteResumo;agora:number}){
  const j=a.atual[0];
  if(!j) return null;
  return <div className="ac-atual">
    <p><Loader2 size={13} className="spin"/> <b>{j.titulo||'Trabalho'}</b>{j.etapa?` · ${j.etapa}`:''}</p>
    {j.progresso>0&&<div className="progress" role="progressbar" aria-valuenow={j.progresso} aria-valuemin={0} aria-valuemax={100} aria-label="Progresso medido"><span style={{width:`${Math.min(100,j.progresso)}%`}}/></div>}
    <small className="muted">{j.progresso>0?`${j.progresso}% · `:''}{j.desde?`ativo há ${duracaoTexto(agora-j.desde)}`:''}
      {' · '}{j.restante_s!=null?`termina em ~${duracaoTexto(j.restante_s)} (pelas medidas deste celular)`:'sem previsão confiável'}</small>
    {a.atual.length>1&&<small className="muted"> +{a.atual.length-1} rodando junto</small>}
  </div>;
}

export function SeletorPeriodo({p,setP}:{p:Periodo;setP:(p:Periodo)=>void}){
  return <div className="periodo" role="radiogroup" aria-label="Período">{PERIODOS.map(([k,t])=><button key={k} role="radio" aria-checked={p===k} className={'chip-aba '+(p===k?'active':'')} onClick={()=>setP(k)}>{t}</button>)}</div>;
}

export function AvisoDados({r,erro,antigo}:{r:Resumo|null;erro:string;antigo:boolean}){
  if(erro&&antigo&&r) return <p className="note-bar warn" role="status"><WifiOff size={15}/> <span>Servidor sem resposta. Mostrando os dados de {horaTexto(r.gerado_em)} (os últimos que chegaram).</span></p>;
  if(erro) return <p className="note-bar bad" role="status"><WifiOff size={15}/> <span>Servidor sem resposta: {erro} Nenhum número é mostrado sem o servidor.</span></p>;
  return null;
}

