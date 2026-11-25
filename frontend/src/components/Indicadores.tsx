import { useState } from 'react';
import { lerIndicadores, valorMetrica, type FiltrosInteligencia } from '../lib/aprendizado';
import { useServidor } from './Servidor2';

export default function Indicadores(){
  const [f,setF]=useState<FiltrosInteligencia>({vertente:'',rede:'',canal:'',de:'',ate:'',metrica:'views'});
  const p=useServidor(c=>lerIndicadores(c,f),0,[f.vertente,f.rede,f.canal,f.de,f.ate,f.metrica]);
  const mudar=(k:keyof FiltrosInteligencia,v:string)=>setF(x=>({...x,[k]:v}));
  return <section className="panel"><h3>Inteligência — indicadores reais</h3>
    <div className="ag-grade">
      <label>Vertente<select value={f.vertente} onChange={e=>mudar('vertente',e.target.value)}><option value="">Todas</option><option value="cortes">Cortes</option><option value="criacao_ia">Criação IA</option><option value="manual">Manual</option><option value="indisponivel">Origem indisponível</option></select></label>
      <label>Plataforma<select value={f.rede} onChange={e=>mudar('rede',e.target.value)}><option value="">Todas</option>{['youtube','tiktok','instagram','facebook','kwai'].map(r=><option key={r}>{r}</option>)}</select></label>
      <label>Métrica do ranking<select value={f.metrica} onChange={e=>mudar('metrica',e.target.value)}>{['views','curtidas','comentarios','compartilhamentos'].map(m=><option key={m}>{m}</option>)}</select></label>
      <label>Perfil de canal<select value={f.canal} onChange={e=>mudar('canal',e.target.value)}><option value="">Todos</option>{p.dados?.canais.map(c=><option key={c}>{c}</option>)}</select></label>
      <label>Medições desde<input type="date" value={f.de} onChange={e=>mudar('de',e.target.value)}/></label>
      <label>Até<input type="date" value={f.ate} onChange={e=>mudar('ate',e.target.value)}/></label>
    </div>
    {p.erro?<p role="alert">{p.erro}</p>:!p.dados?<p>Lendo indicadores…</p>:<>
      <p>{p.dados.publicacoes} publicação(ões) por rede com medidas no recorte.</p>
      <ul className="skill-regras">{Object.entries(p.dados.medidas).map(([k,m])=><li key={k}>{k}: <b>{valorMetrica(m.valor)}</b> • {m.amostras} amostra(s)</li>)}</ul>
      <h4>Vídeos com maior resultado por plataforma</h4>
      {p.dados.destaques.map(g=><div key={g.rede}><h4>{g.rede} • {g.metrica}</h4>
        <p className="hint">{g.sem_metrica} sem esta métrica. Ranking descritivo; não prova causa.</p>
        {!g.videos.length?<p>Indisponível</p>:<ol>{g.videos.map(v=><li key={v.snapshot}>
          <b>{v.publicacao?.titulo||v.item}</b> • {valorMetrica(v.metricas[g.metrica])}
          <details style={{overflowWrap:"anywhere"}}><summary>Fonte e versão publicada</summary>
            <p>Fonte: {v.fonte} • {v.publicacao?.origem||'Indisponível'} • {v.publicacao?.projeto||v.publicacao?.corte||v.item}</p>
            <p>Render: {v.publicacao?.render_sha||'Indisponível'} • versão {v.publicacao?.render_versao??'Indisponível'}</p><p>Roteiro: {v.publicacao?.roteiro_sha||'Indisponível'}</p><p>Perfil de canal: {v.publicacao?.canal||'Indisponível'} • Canal de origem: {v.publicacao?.canal_origem||'Indisponível'}</p>
            <p>Gancho: {v.publicacao?.gancho??'Indisponível'} • Template: {v.publicacao?.modelo||'Indisponível'}</p>
            <p>Efeitos aplicados: {v.publicacao?.efeitos?v.publicacao.efeitos.efeitos.filter(e=>e.status==='aplicado').map(e=>e.tipo).join(', ')||'Nenhum':'Indisponível'}</p>
            <p>Capa selecionada: {v.publicacao?.capa_selecionada?.sha||'Indisponível'} (seleção não comprova aceite pela rede)</p>
            <p>Publicado: {v.publicacao?.publicado_em?new Date(v.publicacao.publicado_em*1000).toLocaleString('pt-BR'):'Indisponível'} • Medido: {v.medido_em?new Date(v.medido_em*1000).toLocaleString('pt-BR'):'Indisponível'}</p>
          </details>
        </li>)}</ol>}
      </div>)}
      <p className="hint">{p.dados.aviso}</p>
    </>}
  </section>;
}
