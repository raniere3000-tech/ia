import { ClipboardList } from 'lucide-react';

/** Ficha de oportunidade: de onde veio, quando, com quais filtros, o que foi medido e o que é estimativa, e o risco. */
export type FichaView={coletado:string;fontes:{descricao:string;url?:string}[];filtros:[string,string][];observado:[string,string][];estimado:[string,string][];notaEstimado:string;risco:'baixo'|'medio'|'alto';riscos:string[]};

export type FichaServidor={id:string;coletado_em:number;fontes:{tipo:string;descricao:string;url?:string}[];filtros:{nicho:string;tema:string;dias:number;idioma:string;usou_youtube:boolean};
  observado:{titulos_em_alta_consultados:number;titulos_parecidos:number;exemplos:string[]};estimado:{interesse:string;como:string};risco:'baixo'|'medio'|'alto';riscos:string[]};

export function fichaDoServidor(f:FichaServidor):FichaView{
  return {coletado:new Date(f.coletado_em*1000).toLocaleString('pt-BR'),fontes:f.fontes,
    filtros:[['Nicho',f.filtros.nicho||'-'],['Tema',f.filtros.tema||'livre'],['Período',`${f.filtros.dias} dias`],['Idioma',f.filtros.idioma],['Dados do YouTube',f.filtros.usou_youtube?'sim':'não']],
    observado:[['Títulos em alta consultados',String(f.observado.titulos_em_alta_consultados)],['Títulos parecidos com a pauta',String(f.observado.titulos_parecidos)],...f.observado.exemplos.map((e,k)=>[`Exemplo ${k+1}`,e] as [string,string])],
    estimado:[['Interesse',f.estimado.interesse]],notaEstimado:f.estimado.como,risco:f.risco,riscos:f.riscos};
}

const COR={baixo:'ok',medio:'warn',alto:'bad'} as const;

export default function Ficha({f}:{f:FichaView}){
  return <details className="ficha"><summary><ClipboardList size={13}/> Ficha da oportunidade <span className={'tag '+COR[f.risco]}>risco {f.risco==='medio'?'médio':f.risco}</span></summary>
   <div className="ficha-corpo">
    <p className="hint">Coletado em {f.coletado}.</p>
    <div><b>Fontes</b><ul>{f.fontes.map((x,k)=><li key={k}>{x.url?<a className="help-link" href={x.url} target="_blank" rel="noreferrer">{x.descricao}</a>:x.descricao}</li>)}</ul></div>
    <div><b>Filtros usados</b><dl>{f.filtros.map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl></div>
    <div><b>Medido (dado real)</b><dl>{f.observado.map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl></div>
    <div><b>Estimado (conta, não é medição)</b><dl>{f.estimado.map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl><small className="hint">{f.notaEstimado}</small></div>
    {f.riscos.length>0&&<div><b>Riscos</b><ul>{f.riscos.map(r=><li key={r}>{r}</li>)}</ul></div>}
   </div></details>;
}
