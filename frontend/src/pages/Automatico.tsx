import { useState } from 'react';
import { Bot, Play, Repeat, Trash2, Loader2, Eye, Plus } from 'lucide-react';
import { useApp } from '../state';
import { HelpButton } from '../components/Help';
import { useCfg, useServidor, PrecisaServidor, erroTexto } from '../components/Servidor2';
import { CamposBriefing, Destinos } from './CriarIA';
import { Prontidao } from '../components/Prontidao';
import { catalogo, produzirLote, rotinas as lerRotinas, criarRotina, mudarRotina, apagarRotina, listarProjetos, horaTexto, type Briefing } from '../lib/api';
import { store } from '../lib/store';

const DIAS=['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'];
const PADRAO:Partial<Briefing>={nicho:'Curiosidades',tipo:'curiosidades',duracao_alvo:45,formato:'9:16',cenas_qtd:6,voz:'Puck',imagens:'busca',modo_aprovacao:'supervisionado',estilo:'documentario',orcamento_max:2,destinos:{redes:[],quando:'proximo'},temas:[]};

export default function Automatico(){
  const {settings,toast,go}=useApp(); const cfg=useCfg();
  const cat=useServidor(catalogo);
  const rot=useServidor(lerRotinas,30);
  const proj=useServidor(c=>listarProjetos(c,'agente3'),15);
  const [b,setB]=useState<Partial<Briefing>>(()=>({...PADRAO,...store.json<Partial<Briefing>>('studio_agente3_briefing',{})}));
  const set=(p:Partial<Briefing>)=>setB(x=>{ const n={...x,...p}; store.setJson('studio_agente3_briefing',n); return n; });
  const [temas,setTemas]=useState(()=>(b.temas||[]).join('\n'));
  const [qtd,setQtd]=useState(1); const [intervalo,setIntervalo]=useState(0);
  const [quando,setQuando]=useState<'agora'|'daqui'|'data'>('agora'); const [minutos,setMinutos]=useState(60); const [data,setData]=useState('');
  const [nome,setNome]=useState('Rotina da noite'); const [dias,setDias]=useState<number[]>([0,1,2,3,4]); const [hora,setHora]=useState('21:00'); const [qtdR,setQtdR]=useState(1);
  const [busy,setBusy]=useState('');
  if(!settings.servidor) return <PrecisaServidor oque="O Agente 3"/>;
  const listaTemas=temas.split('\n').map(x=>x.trim()).filter(Boolean);
  const briefing={...b,temas:listaTemas};
  const fazer=async(n:string,f:()=>Promise<void>)=>{ setBusy(n); try{ await f(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } };
  return <div className="automatico">
   <Prontidao cat={cat.dados}/>
   <section className="panel">
    <div className="section-head"><h2><Bot size={17}/> 1. Como devem ser os vídeos</h2></div>
    <p className="subtitle">Aqui o celular faz vários vídeos sozinho: escolhe o assunto (se você não der), escreve, narra, monta e avisa por e-mail. Nada é publicado sem a sua aprovação.</p>
    <label>Assuntos (um por linha; se deixar vazio, o agente escolhe dentro do nicho)<textarea rows={3} value={temas} onChange={e=>{ setTemas(e.target.value); set({temas:e.target.value.split('\n').map(x=>x.trim()).filter(Boolean)}); }} placeholder={'Por que o céu é azul\nO animal mais rápido do mundo'}/></label>
    <CamposBriefing b={b} set={set} cat={cat.dados}/>
    <label className="mt">Visual<select value={b.estilo} onChange={e=>set({estilo:e.target.value})}>{(cat.dados?.estilos||[]).filter(e=>e.servidor).map(e=><option key={e.id} value={e.id}>{e.nome}{e.status==='beta'?' (em teste)':''}</option>)}</select></label>
    <button className="link-btn" onClick={()=>go('galeria','','criar')}>Ver os estilos com demonstração</button>
    <Destinos b={b} set={set}/>
   </section>

   <section className="panel">
    <div className="section-head"><h2><Play size={17}/> 2. Quando fazer</h2><HelpButton topic="fila"/></div>
    <div className="row-gap left">
     <label className="check"><input type="radio" checked={quando==='agora'} onChange={()=>setQuando('agora')}/> Agora</label>
     <label className="check"><input type="radio" checked={quando==='daqui'} onChange={()=>setQuando('daqui')}/> Daqui a</label>
     {quando==='daqui'&&<input type="number" min={1} value={minutos} onChange={e=>setMinutos(+e.target.value)} style={{width:90}} aria-label="minutos"/>}{quando==='daqui'&&'min'}
     <label className="check"><input type="radio" checked={quando==='data'} onChange={()=>setQuando('data')}/> Data e hora</label>
     {quando==='data'&&<input type="datetime-local" value={data} onChange={e=>setData(e.target.value)}/>}
    </div>
    <div className="small-grid mt">
     <label>Quantos vídeos<input type="number" min={1} max={12} value={qtd} onChange={e=>setQtd(+e.target.value)}/></label>
     <label>Intervalo entre eles (min, 0 = em sequência na fila)<input type="number" min={0} value={intervalo} onChange={e=>setIntervalo(+e.target.value)}/></label>
    </div>
    <p className="hint">O celular faz um render por vez; os outros esperam na fila. A previsão de término aparece em Fila e aprovações e melhora com as medidas deste celular.</p>
    <button className="primary" disabled={!!busy||(quando==='data'&&!data)||!cat.dados?.ffmpeg} onClick={()=>fazer('lote',async()=>{
      const r=await produzirLote(cfg,{briefing,quantidade:qtd,temas:listaTemas,intervalo_min:intervalo,quando,minutos,data:quando==='data'?new Date(data).getTime()/1000:undefined});
      toast(`${r.criados.length} vídeo(s) na fila do servidor.`,'ok'); proj.recarregar(); go('fila'); })}>
     {busy==='lote'?<Loader2 size={15} className="spin"/>:<Play size={15}/>} {quando==='agora'?'Produzir agora':'Agendar'} {qtd>1?`${qtd} vídeos`:''}</button>
   </section>

   <section className="panel">
    <div className="section-head"><h2><Repeat size={17}/> 3. Repetir sozinho (opcional)</h2><span className="hint">fuso: {rot.dados?.fuso||'America/Sao_Paulo'}</span></div>
    {(rot.dados?.rotinas||[]).length===0&&<p className="hint">Uma rotina faz vídeos nos dias e na hora que você marcar, com as escolhas do passo 1. Nenhuma criada ainda.</p>}
    <ul className="rotinas">{(rot.dados?.rotinas||[]).map(r=><li key={r.id} className={r.ativo?'':'off'}>
      <label className="check"><input type="checkbox" checked={!!r.ativo} onChange={e=>fazer('r',async()=>{ await mudarRotina(cfg,r.id,{ativo:e.target.checked}); rot.recarregar(); })}/> <b>{r.nome}</b></label>
      <span>{r.dias.map(d=>DIAS[d]).join(', ')} às {r.hora} • {r.quantidade} vídeo(s) • {r.briefing?.estilo}</span>
      <small className="muted">{r.ativo?'próxima: '+horaTexto(r.proxima):'desligada'}</small>
      <button className="icon-btn" onClick={()=>{ if(window.confirm('Apagar esta rotina? Os vídeos já feitos continuam.')) fazer('r',async()=>{ await apagarRotina(cfg,r.id); rot.recarregar(); }); }} aria-label="Apagar"><Trash2 size={15}/></button>
    </li>)}</ul>
    <div className="nova-rotina">
     <label>Nome<input value={nome} onChange={e=>setNome(e.target.value)}/></label>
     <div className="chips">{DIAS.map((d,i)=><button key={d} className={'chip '+(dias.includes(i)?'on':'')} onClick={()=>setDias(dias.includes(i)?dias.filter(x=>x!==i):[...dias,i].sort())}>{d}</button>)}</div>
     <div className="row-gap left"><label>Hora<input type="time" value={hora} onChange={e=>setHora(e.target.value)}/></label><label>Vídeos por vez<input type="number" min={1} max={6} value={qtdR} onChange={e=>setQtdR(+e.target.value)}/></label></div>
     <button className="subtle" disabled={!!busy||!dias.length} onClick={()=>fazer('nr',async()=>{ await criarRotina(cfg,{nome,dias,hora,quantidade:qtdR,briefing}); toast('Rotina criada.','ok'); rot.recarregar(); })}><Plus size={15}/> Criar rotina com as escolhas do passo 1</button>
     <p className="hint">Se o servidor estiver desligado na hora, a produção começa quando ele ligar de novo (sem duplicar).</p>
    </div>
   </section>

   <section className="panel">
    <div className="section-head"><h2>Vídeos já feitos ou em produção</h2></div>
    {(proj.dados?.projetos||[]).length===0?<p className="hint">Nenhum ainda.</p>:
    <ul className="proj-lista">{proj.dados!.projetos.slice(0,30).map(p=><li key={p.id}><button className="link-btn" onClick={()=>go('revisar',p.id,'fila')}><Eye size={14}/> {p.titulo}</button><span className="tag">{cat.dados?.estados[p.status]||p.status}</span><small className="muted">{horaTexto(p.atualizado)}</small></li>)}</ul>}
   </section>
  </div>;
}
