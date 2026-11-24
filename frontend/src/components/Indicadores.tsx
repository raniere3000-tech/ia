import { useState } from 'react';
import { lerIndicadores, valorMetrica, type FiltrosInteligencia } from '../lib/aprendizado';
import { useServidor } from './Servidor2';

export default function Indicadores(){
  const [f,setF]=useState<FiltrosInteligencia>({vertente:'',rede:'',canal:'',de:'',ate:''});
  const p=useServidor(c=>lerIndicadores(c,f),0,[f.vertente,f.rede,f.canal,f.de,f.ate]);
  const mudar=(k:keyof FiltrosInteligencia,v:string)=>setF(x=>({...x,[k]:v}));
  return <section className="panel"><h3>Inteligência — indicadores reais</h3>
    <div className="ag-grade">
      <label>Vertente<select value={f.vertente} onChange={e=>mudar('vertente',e.target.value)}><option value="">Todas</option><option value="cortes">Cortes</option><option value="criacao_ia">Criação IA</option><option value="manual">Manual</option><option value="indisponivel">Origem indisponível</option></select></label>
      <label>Plataforma<select value={f.rede} onChange={e=>mudar('rede',e.target.value)}><option value="">Todas</option>{['youtube','tiktok','instagram','facebook','kwai'].map(r=><option key={r}>{r}</option>)}</select></label>
      <label>Canal<select value={f.canal} onChange={e=>mudar('canal',e.target.value)}><option value="">Todos</option>{p.dados?.canais.map(c=><option key={c}>{c}</option>)}</select></label>
      <label>Medições desde<input type="date" value={f.de} onChange={e=>mudar('de',e.target.value)}/></label>
      <label>Até<input type="date" value={f.ate} onChange={e=>mudar('ate',e.target.value)}/></label>
    </div>
    {p.erro?<p role="alert">{p.erro}</p>:!p.dados?<p>Lendo indicadores…</p>:<>
      <p>{p.dados.publicacoes} publicação(ões) por rede com medidas no recorte.</p>
      <ul className="skill-regras">{Object.entries(p.dados.medidas).map(([k,m])=><li key={k}>{k}: <b>{valorMetrica(m.valor)}</b> • {m.amostras} amostra(s)</li>)}</ul>
      <p className="hint">{p.dados.aviso}</p>
    </>}
  </section>;
}
