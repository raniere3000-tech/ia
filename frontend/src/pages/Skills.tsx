import { useEffect, useMemo, useState } from 'react';
import { BookOpen, Download, ShieldCheck, RefreshCw, RotateCcw, Loader2, ExternalLink, ChevronDown } from 'lucide-react';
import { useApp } from '../state';
import { useCfg, useServidor, erroTexto } from '../components/Servidor2';
import { listarSkills, lerPerfis, salvarPerfil, instalarSkills, conferirSkills, procurarAtualizacoes, acaoSkill, obterSkill, historicoSkills, NOME_AGENTE,
  desfazerPerfil, pontaAPonta, desfazerLote,
  type Skill, type PerfilSkills } from '../lib/skills';

const ESTADOS:[string,string][]=[['','Todas'],['usavel','Prontas para usar'],['nao_instalada','Não instaladas'],['dep_externa_pendente','Dependem de programa externo'],
  ['definicao_instalada','Só texto'],['falha_integridade','Com problema'],['incompativel','Incompatíveis']];
const tagEstado=(s:Skill)=>s.usavel?'ok':s.estado==='falha_integridade'||s.estado==='incompativel'?'bad':s.estado==='nao_instalada'?'':'warn';
const quando=(t:number|null)=>t?new Date(t*1000).toLocaleString('pt-BR',{dateStyle:'short',timeStyle:'short'}):'nunca';

function Detalhe({id,onMudou}:{id:string;onMudou:()=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const d=useServidor(c=>obterSkill(c,id),0,[id]);
  const [busy,setBusy]=useState('');
  const x=d.dados; if(!x) return d.erro?<p className="hint bad">{d.erro}</p>:<p className="hint"><Loader2 size={13} className="spin"/> Abrindo…</p>;
  const run=async(a:'ativar'|'desativar'|'rollback'|'atualizar'|'testar-atualizacao',msg:string)=>{ setBusy(a); try{ d.setDados(await acaoSkill(cfg,id,a)); toast(msg,'ok'); onMudou(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } };
  return <div className="skill-det">
    {x.descricao&&<p className="hint">{x.descricao}</p>}
    <p className="hint">Origem: <a className="help-link" href={`${x.origem}/blob/${x.commit}/${x.arquivo}`} target="_blank" rel="noreferrer">{x.origem.replace('https://github.com/','')} <ExternalLink size={11}/></a> • versão {x.versao} • licença {x.licenca||'não confirmada'} • conferida {quando(x.ultimo_teste)}</p>
    {x.motivo&&<p className="hint warn">{x.motivo}</p>}
    <p className="hint">Programa da skill: {x.servico_externo?'depende de serviço externo (não conectado): só o texto é lido':'nenhum roda aqui; só o texto é lido'}.</p>
    {x.teste&&<p className={'hint '+(x.teste.ok?'':'bad')}>{x.teste.ok?`Versão nova testada: ${x.teste.regras} regra(s); ${x.teste.novas?.length||0} nova(s), ${x.teste.removidas?.length||0} saíram. Ainda não está valendo.`:`A versão nova não passou no teste: ${x.teste.motivo}`}</p>}
    {x.regras&&x.regras.length>0&&<details><summary>{x.n_regras} regra(s) que podem entrar nos pedidos à IA{x.descartadas?` (${x.descartadas} frase(s) descartadas por segurança)`:''}</summary>
      <ul className="skill-regras">{x.regras.map(r=><li key={r}>{r}</li>)}</ul></details>}
    <div className="row-gap left mt">
      {x.estado!=='nao_instalada'&&(x.ativa?<button className="subtle sm" disabled={!!busy} onClick={()=>run('desativar','Skill desligada.')}>Desligar</button>
        :<button className="subtle sm" disabled={!!busy} onClick={()=>run('ativar','Skill ligada.')}>Ligar</button>)}
      {x.nova_versao&&<button className="subtle sm" disabled={!!busy} onClick={()=>run('testar-atualizacao','Teste da versão nova feito. Veja o resultado abaixo.')}><ShieldCheck size={13}/> Testar versão nova</button>}
      {x.nova_versao&&x.versao_testada&&<button className="subtle sm" disabled={!!busy} onClick={()=>run('atualizar','Versão nova ativada. Dá para voltar se não gostar.')}><Download size={13}/> Ativar versão testada</button>}
      {x.tem_anterior&&<button className="subtle sm" disabled={!!busy} onClick={()=>run('rollback','Voltei para a versão anterior.')}><RotateCcw size={13}/> Voltar versão</button>}
    </div>
  </div>;
}

function Perfil({p,todas,onSalvo}:{p:PerfilSkills;todas:Skill[];onSalvo:()=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const [add,setAdd]=useState('');
  const salvar=async(d:Parameters<typeof salvarPerfil>[2])=>{ try{ await salvarPerfil(cfg,p.id,d); onSalvo(); }catch(e){ toast(erroTexto(e),'erro'); } };
  const desfazer=async()=>{ try{ await desfazerPerfil(cfg,p.id); toast('Perfil voltou como estava.','ok'); onSalvo(); }catch(e){ toast(erroTexto(e),'erro'); } };
  const opc=todas.filter(s=>!p.skills.includes(s.id)&&(p.agente==='desenvolvimento'?true:s.tipo==='producao'));
  return <li className="perfil-linha">
    <div className="perfil-top"><label className="check"><input type="checkbox" checked={p.ligado} onChange={e=>salvar({ligado:e.target.checked})}/> <b>{p.rotulo}</b></label>
      <span className={'tag '+(p.usado_em?'info':'')}>{p.usado_em?`usado no ${p.usado_em}`:'perfil pronto, ainda sem pedido à IA nesta etapa'}</span>
      <label className="perfil-lim">até<select value={p.limite} onChange={e=>salvar({limite:+e.target.value})}>{[1,2,3,4,5,6].map(n=><option key={n} value={n}>{n}</option>)}</select></label></div>
    <div className="chips">{p.skills.map(s=><button key={s} className={'chip '+(p.prontas.includes(s)?'on':'')} title={p.prontas.includes(s)?'Pronta. Toque para tirar do perfil.':'Ainda não está pronta. Toque para tirar do perfil.'} onClick={()=>salvar({skills:p.skills.filter(x=>x!==s)})}>{s} ×</button>)}
      <select className="chip-add" value={add} onChange={e=>{ const v=e.target.value; setAdd(''); if(v) salvar({skills:[...p.skills,v]}); }}><option value="">+ adicionar</option>{opc.map(s=><option key={s.id} value={s.id}>{s.id}</option>)}</select>
      {p.skills.join()!==p.padrao.join()&&<button className="link-btn" onClick={()=>salvar({skills:p.padrao})}>voltar ao padrão</button>}
      {p.pode_desfazer&&<button className="link-btn" onClick={desfazer}><RotateCcw size={12}/> desfazer</button>}</div>
    {p.fallback&&p.ligado&&p.prontas.length===0&&<p className="hint">Sem skill pronta: {p.fallback}</p>}
  </li>;
}

export function SkillsCard(){
  const {settings,toast}=useApp(); const cfg=useCfg();
  const [aberto,setAberto]=useState(false);
  const [f,setF]=useState({agente:'',estado:'',busca:''});
  const [f2,setF2]=useState({prioridade:'',licenca:'',tipo:'',perfil:''});
  const [abrir,setAbrir]=useState('');
  const [busy,setBusy]=useState('');
  const [poll,setPoll]=useState(0);
  const lista=useServidor(c=>listarSkills(c,aberto?f:{}),poll,[aberto,f.agente,f.estado,f.busca,settings.servidorSessao]);
  const t=lista.dados?.resumo.trabalho;
  const rodando=!!t&&['na_fila','rodando','agendado','aguardando_tentativa'].includes(t.status);
  useEffect(()=>{ setPoll(rodando?3:0); },[rodando]);
  const perfis=useServidor(c=>aberto?lerPerfis(c):Promise.resolve(null),0,[aberto]);
  const hist=useServidor(c=>aberto?historicoSkills(c,{etapa:'utilizada'}):Promise.resolve(null),0,[aberto]);
  const pap=useServidor(c=>aberto?pontaAPonta(c):Promise.resolve(null),0,[aberto]);
  const todasSem=useMemo(()=>lista.dados?.skills||[],[lista.dados]);
  const todas=useMemo(()=>{ const pf=perfis.dados?.perfis.find(x=>x.id===f2.perfil);
    return todasSem.filter(s=>(!f2.prioridade||s.prioridade===f2.prioridade)&&(!f2.tipo||s.tipo===f2.tipo)
      &&(!f2.licenca||(f2.licenca==='sim'?!!s.licenca:!s.licenca))&&(!pf||pf.skills.includes(s.id))); },[todasSem,f2,perfis.dados]);
  if(!settings.servidor) return null;
  const r=lista.dados?.resumo; const job=t;
  const run=async(k:string,fn:()=>Promise<unknown>,msg:(x:any)=>string)=>{ setBusy(k); try{ const x=await fn(); toast(msg(x),'ok'); lista.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } };
  return <section className="panel config-card">
    <div className="config-icon ai"><BookOpen size={22}/></div>
    <div className="config-body">
     <div className="section-head"><h2>Skills: boas práticas para os agentes {r&&<span className={'tag '+(r.usaveis?'ok':'')}>{r.usaveis} de {r.total} prontas</span>}</h2></div>
     <p className="subtitle">São guias de texto (de diretores, editores e animadores) que os agentes consultam antes de pedir algo à IA. O servidor baixa só o texto, de versões fixas, confere cada arquivo e <b>nunca roda programa nenhum</b> que venha delas. Cada tarefa usa poucas skills, e elas não aprovam nem publicam nada.</p>
     {lista.erro&&<p className="hint bad">{lista.erro}</p>}
     {r&&<>
      {rodando&&job&&<p className="hint"><Loader2 size={13} className="spin"/> {job.etapa} ({Math.round(job.progresso)}%)</p>}
      {!rodando&&job?.status==='falhou'&&<p className="hint bad">A última instalação falhou: {job.erro}</p>}
      {r.ultima_instalacao&&<p className="hint">Última instalação {quando(r.ultima_instalacao.t)}: {r.ultima_instalacao.instaladas} baixada(s), {r.ultima_instalacao.ja_estavam} já estavam certas{r.ultima_instalacao.falhas.length>0&&<>, <b>{r.ultima_instalacao.falhas.length} com problema</b> ({r.ultima_instalacao.falhas.slice(0,3).map(x=>`${x.id}: ${x.motivo}`).join('; ')})</>}.</p>}
      {(r.estados.dep_externa_pendente||0)>0&&<p className="hint">{r.estados.dep_externa_pendente} skill(s) dependem de programas que não estão no celular: só as regras de texto delas são usadas.</p>}
      <div className="row-gap left mt">
       <button className="primary sm" disabled={!!busy||rodando} onClick={()=>run('inst',()=>instalarSkills(cfg),()=>'Instalação começou no servidor. Pode sair desta tela.')}>{busy==='inst'?<Loader2 size={14} className="spin"/>:<Download size={14}/>} {r.usaveis?'Instalar o que falta':'Instalar as skills'}</button>
       <button className="subtle sm" disabled={!!busy} onClick={()=>run('conf',()=>conferirSkills(cfg),(x)=>x.problemas.length?`${x.problemas.length} arquivo(s) com problema: ${x.problemas.slice(0,2).map((p:any)=>p.id).join(', ')}.`:`${x.conferidas} arquivo(s) conferidos, tudo certo.`)}><ShieldCheck size={14}/> Conferir arquivos</button>
       <button className="subtle sm" disabled={!!busy||rodando} onClick={()=>run('atu',()=>procurarAtualizacoes(cfg),()=>'Procurando versões novas. Nada muda sem você mandar.')}><RefreshCw size={14}/> Procurar versões novas{r.candidatas?` (${r.candidatas})`:''}</button>
       {r.ultima_instalacao&&<button className="subtle sm" disabled={!!busy||rodando} onClick={()=>run('lote',()=>desfazerLote(cfg),(x)=>`Voltaram ${x.voltaram.length} skill(s) para como estavam antes da última instalação.`)}><RotateCcw size={14}/> Desfazer a última instalação</button>}
       <button className="subtle sm" onClick={()=>setAberto(!aberto)}><ChevronDown size={14}/> {aberto?'Fechar a biblioteca':'Abrir a biblioteca e os perfis'}</button>
      </div>
     </>}
     {aberto&&<>
      <div className="field-label mt">Quais skills cada tarefa usa sozinha</div>
      {perfis.dados&&<ul className="perfis">{perfis.dados.perfis.map(p=><Perfil key={p.id} p={p} todas={todas.length?todas:[]} onSalvo={()=>perfis.recarregar()}/>)}</ul>}
      <div className="field-label mt">Biblioteca</div>
      <div className="small-grid">
       <label>Agente<select value={f.agente} onChange={e=>setF({...f,agente:e.target.value})}><option value="">Todos</option>{Object.entries(NOME_AGENTE).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
       <label>Situação<select value={f.estado} onChange={e=>setF({...f,estado:e.target.value})}>{ESTADOS.map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
       <label>Procurar<input value={f.busca} onChange={e=>setF({...f,busca:e.target.value})} placeholder="ex.: storyboard, legenda, câmera"/></label>
       <label>Tarefa<select value={f2.perfil} onChange={e=>setF2({...f2,perfil:e.target.value})}><option value="">Todas</option>{perfis.dados?.perfis.map(p=><option key={p.id} value={p.id}>{p.rotulo}</option>)}</select></label>
       <label>Prioridade<select value={f2.prioridade} onChange={e=>setF2({...f2,prioridade:e.target.value})}><option value="">Todas</option>{['P0','P1','P2','P3'].map(x=><option key={x} value={x}>{x}{x==='P0'?' (mais importante)':''}</option>)}</select></label>
       <label>Licença<select value={f2.licenca} onChange={e=>setF2({...f2,licenca:e.target.value})}><option value="">Todas</option><option value="sim">Confirmada</option><option value="nao">Não confirmada</option></select></label>
       <label>Tipo<select value={f2.tipo} onChange={e=>setF2({...f2,tipo:e.target.value})}><option value="">Todos</option><option value="producao">Produção de vídeo</option><option value="desenvolvimento">Desenvolvimento do site</option></select></label>
      </div>
      <p className="hint">{todas.length} de {todasSem.length} skill(s) com esse filtro.</p>
      <ul className="skills-lista">{todas.map(s=><li key={s.id}>
        <button className="skill-linha" onClick={()=>setAbrir(abrir===s.id?'':s.id)} aria-expanded={abrir===s.id}>
          <b>{s.id}</b><span className="muted">{s.agentes.map(a=>NOME_AGENTE[a]||a).join(', ')} • {s.gatilho} • {s.prioridade} • versão {s.versao||'—'} • {s.licenca||'licença não confirmada'} • {s.origem.replace('https://github.com/','')} • conferida {quando(s.ultimo_teste)}</span>
          <span className={'tag '+tagEstado(s)}>{s.ativa||s.estado==='nao_instalada'?s.estado_nome:'Desligada'}</span>{s.nova_versao&&<span className="tag info">versão nova</span>}</button>
        {abrir===s.id&&<Detalhe id={s.id} onMudou={()=>lista.recarregar()}/>}
      </li>)}</ul>
      {todas.length===0&&!lista.carregando&&<p className="hint">Nenhuma skill com esse filtro.</p>}
      {pap.dados&&<><div className="field-label mt">O que cada agente fez com as skills</div>
        <ul className="diag">{pap.dados.consumidores.map(c=><li key={c.id}><b>{c.nome}</b>{' '}
          {c.ultimo?<>{quando(c.ultimo)}: {c.saida} <span className="muted">({c.skills.map(s=>`${s.id} → ${s.decisao}`).join('; ')})</span></>:<span className="muted">ainda não usou skill em nada produzido</span>}
          {c.fallback&&(!c.ultimo||c.fallback.t>c.ultimo)&&<span className="muted"> • última vez sem skill: {c.fallback.motivo}</span>}</li>)}</ul></>}
      {hist.dados&&hist.dados.historico.length>0&&<details className="mt"><summary>Registro de uso (só quando virou algo de verdade)</summary>
        <ul className="skill-regras">{hist.dados.historico.slice(0,30).map(h=><li key={h.id}>{quando(h.t)} • {h.skill_id} (versão {h.versao||'?'}) • {h.decisao||h.origem} • {h.resultado}{h.artefato?` • ${h.artefato}`:''}</li>)}</ul></details>}
     </>}
    </div>
  </section>;
}
