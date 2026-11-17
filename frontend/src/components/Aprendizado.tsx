import { useRef, useState } from 'react';
import { BrainCircuit, FlaskConical, Loader2, Undo2, Upload } from 'lucide-react';
import { useApp } from '../state';
import { aplicarPesos, apagarAprendizado, capturarAprendizado, criarTeste, desfazerPesos, encerrarTeste, importarAprendizado, lerAprendizado, type PainelAprend, type ResImport } from '../lib/aprendizado';
import { useCfg, useServidor, erroTexto } from './Servidor2';

const dia=(t:number|null)=>t?new Date(t*1000).toLocaleDateString('pt-BR'):'—';
const NOME_REDE:Record<string,string>={youtube:'YouTube',instagram:'Instagram',facebook:'Facebook',tiktok:'TikTok',kwai:'Kwai'};

/**
 * Aprendizado dos agentes. Mostra o que as redes mediram (ou o que você importou), diz "dados insuficientes" quando falta amostra,
 * deixa aplicar pesos só no sorteio de estilo (com versão e desfazer) e testa UMA coisa por vez. Nunca prova causa e nunca mexe
 * em quantos posts saem por dia.
 */
export default function Aprendizado(){
  const {toast}=useApp(); const cfg=useCfg();
  const p=useServidor(c=>lerAprendizado(c),0,[]);
  const [busy,setBusy]=useState(''); const [imp,setImp]=useState<ResImport|null>(null);
  const [t,setT]=useState({variavel:'estilo',a:'',b:'',fixoVar:'',fixoVal:''});
  const arq=useRef<HTMLInputElement>(null);
  const d:PainelAprend|null=p.dados;
  async function rodar<T>(nome:string,f:()=>Promise<T>,ok:string){ setBusy(nome); try{ await f(); await p.recarregar(); toast(ok,'ok'); }catch(e){ toast(erroTexto(e),'erro'); } finally{ setBusy(''); } }
  async function escolher(f:File|undefined){
    if(!f) return;
    const formato=f.name.toLowerCase().endsWith('.json')?'json':'csv';
    setBusy('importar'); setImp(null);
    try{ const r=await importarAprendizado(cfg,f.name,formato,await f.text()); setImp(r); await p.recarregar(); toast(r.aceitas?`${r.aceitas} linha(s) guardada(s).`:(r.aviso||'Nada novo.'),'ok'); }
    catch(e){ toast(erroTexto(e),'erro'); } finally{ setBusy(''); if(arq.current) arq.current.value=''; }
  }
  if(!cfg.servidor) return null;
  if(!d) return <section className="panel"><h3><BrainCircuit size={16}/> Aprendizado dos agentes</h3>{p.erro?<p className="hint">{p.erro}</p>:<p className="hint"><Loader2 size={14} className="spin"/> Lendo...</p>}</section>;
  const ex=d.experimentos.find(e=>e.status==='ativo');
  return <section className="panel aprendizado">
    <div className="section-head"><h3><BrainCircuit size={16}/> Aprendizado dos agentes</h3></div>
    <p className="hint">{d.aviso_causa} {d.aviso_frequencia}</p>
    <p className="hint"><b>{d.retratos}</b> medida(s) guardada(s). Só comparo quando há pelo menos <b>{d.minimo}</b> vídeos medidos em cada valor.</p>
    <div className="row-gap left">
      <button className="subtle sm" disabled={!!busy} onClick={()=>rodar('capturar',()=>capturarAprendizado(cfg),'Números das redes lidos e guardados.')}>{busy==='capturar'?<Loader2 size={13} className="spin"/>:null} Ler números das redes agora</button>
      <button className="subtle sm" disabled={!!busy} onClick={()=>arq.current?.click()}><Upload size={13}/> Importar CSV ou JSON</button>
      <input ref={arq} type="file" accept=".csv,.json,text/csv,application/json" hidden onChange={e=>escolher(e.target.files?.[0])}/>
      {d.retratos>0&&<button className="subtle sm danger" disabled={!!busy} onClick={()=>{ if(confirm('Apagar TODAS as medidas guardadas? Os pesos que dependem delas são desligados.')) rodar('apagar',()=>apagarAprendizado(cfg,{alvo:'tudo'}),'Medidas apagadas e pesos desligados.'); }}>Apagar tudo</button>}
    </div>
    <p className="hint">Colunas do arquivo: <code>rede, data</code> (AAAA-MM-DD), <code>views</code> ou <code>curtidas</code>, e, se quiser comparar, <code>estilo, modelo, faixa, duracao, gancho, formato, perfil</code>.</p>
    {imp&&<p className="hint">Importação: {imp.aceitas} aceita(s), {imp.repetidas} já existia(m), {imp.total_recusadas} recusada(s){imp.recusadas.length>0&&<>: {imp.recusadas.slice(0,4).map(r=>`linha ${r.linha} (${r.motivo})`).join('; ')}</>}.</p>}
    {d.fontes.length>0&&<ul className="skill-regras">{d.fontes.map(f=><li key={f.fonte+f.rede}>{f.fonte==='rede'?'Lido da rede':'Importado por você'} • {NOME_REDE[f.rede]||f.rede} • {f.retratos} medida(s) • {dia(f.de)} a {dia(f.ate)}</li>)}</ul>}
    {d.importacoes.length>0&&<details><summary>Arquivos importados ({d.importacoes.length})</summary><ul className="skill-regras">{d.importacoes.map(i=><li key={i.id}>{i.nome} • {i.linhas} linha(s){i.recusadas?` • ${i.recusadas} recusada(s)`:''} • {dia(i.t)} <button className="subtle sm" onClick={()=>{ if(confirm('Apagar este arquivo importado e o efeito dele?')) rodar('apagar',()=>apagarAprendizado(cfg,{alvo:'importacao',id:i.id}),'Importação apagada.'); }}>Apagar</button></li>)}</ul></details>}

    <h4>O que dá para dizer hoje</h4>
    <ul className="ag-aprend">{d.variaveis.map(v=><li key={v.variavel}>
      <b>{v.nome}</b> <span className={'tag '+(v.estado==='tendência'?'ok':v.estado==='dados insuficientes'?'warn':'info')}>{v.estado==='tendência'?'tendência':v.estado==='dados insuficientes'?'dados insuficientes':'sem diferença clara'}</span>
      <div className="hint">{v.mensagem}</div>
      {v.valores.length>0&&<div className="hint">{v.valores.map(x=>`${x.valor}: ${x.media.toFixed(0)} por vídeo (${x.n} vídeo${x.n===1?'':'s'}${x.n<d.minimo?', poucos':''})`).join(' • ')}</div>}
      {v.aplicavel&&<div className="row-gap left">
        {v.pode_aplicar&&<button className="subtle sm" disabled={!!busy} onClick={()=>rodar('aplicar',()=>aplicarPesos(cfg,v.variavel),'Pesos ligados no sorteio de estilo.')}>Usar estes pesos no sorteio</button>}
        {v.pode_desfazer&&<button className="subtle sm" disabled={!!busy} onClick={()=>rodar('desfazer',()=>desfazerPesos(cfg,v.variavel),'Pesos desfeitos.')}><Undo2 size={13}/> Desfazer (versão {v.versao_pesos})</button>}
        {Object.keys(v.peso_ativo).length>0&&<span className="hint">Em uso: {Object.entries(v.peso_ativo).map(([k,x])=>`${k} ${Math.round(x*100)}%`).join(', ')}</span>}
      </div>}
      {!v.aplicavel&&<div className="hint">Só leitura: ainda não há sorteio que use esta variável. Para decidir, use o teste A/B.</div>}
    </li>)}</ul>

    <h4><FlaskConical size={15}/> Teste A/B (uma coisa por vez)</h4>
    {ex?<div className="ag-teste">
      <p><b>{ex.nome}</b> — {ex.resultado}</p><p className="hint">{ex.mensagem}</p>
      <p className="hint">A ({ex.lados.a.valor}): {ex.lados.a.n} vídeo(s) • B ({ex.lados.b.valor}): {ex.lados.b.n} vídeo(s){Object.keys(ex.fixos).length?` • fixo: ${Object.entries(ex.fixos).map(([k,x])=>`${k}=${x}`).join(', ')}`:''}</p>
      {ex.variavel==='estilo'&&<p className="hint">Enquanto o teste está ativo, o Agente 1 sorteia o estilo só entre A e B.</p>}
      <button className="subtle sm" disabled={!!busy} onClick={()=>rodar('encerrar',()=>encerrarTeste(cfg,ex.id),'Teste encerrado.')}>Encerrar teste</button>
    </div>:<div className="ag-grade">
      <label>Variável<select value={t.variavel} onChange={e=>setT({...t,variavel:e.target.value})}>{d.variaveis.map(v=><option key={v.variavel} value={v.variavel}>{v.nome}</option>)}</select></label>
      <label>A<input value={t.a} onChange={e=>setT({...t,a:e.target.value})} placeholder="ex.: neon"/></label>
      <label>B<input value={t.b} onChange={e=>setT({...t,b:e.target.value})} placeholder="ex.: vhs"/></label>
      <label>Manter fixo (opcional)<select value={t.fixoVar} onChange={e=>setT({...t,fixoVar:e.target.value})}><option value="">Nada</option>{d.variaveis.filter(v=>v.variavel!==t.variavel).map(v=><option key={v.variavel} value={v.variavel}>{v.nome}</option>)}</select></label>
      {t.fixoVar&&<label>Valor fixo<input value={t.fixoVal} onChange={e=>setT({...t,fixoVal:e.target.value})}/></label>}
      <button className="primary sm" disabled={!!busy||!t.a.trim()||!t.b.trim()} onClick={()=>rodar('teste',()=>criarTeste(cfg,{variavel:t.variavel,a:t.a.trim(),b:t.b.trim(),fixos:t.fixoVar&&t.fixoVal.trim()?{[t.fixoVar]:t.fixoVal.trim()}:{}}),'Teste criado. Nada é postado por ele.')}>Criar teste</button>
    </div>}
    {d.historico_pesos.length>0&&<details><summary>Versões dos pesos</summary><ul className="skill-regras">{d.historico_pesos.map(h=><li key={h.versao}>Versão {h.versao} • {h.variavel} • {h.motivo} • {dia(h.t)}{h.ativo?' • em uso':''}</li>)}</ul></details>}
    {d.boas_praticas.length>0&&<details><summary>Cuidados das skills de análise</summary><ul className="skill-regras">{d.boas_praticas.map((b,i)=><li key={i}>{b}</li>)}</ul></details>}
    <p className="hint">{d.como_voltar}</p>
  </section>;
}
