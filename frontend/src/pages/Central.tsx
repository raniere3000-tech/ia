import { useEffect, useState } from 'react';
import { AlertTriangle, BookOpen, CalendarClock, CheckCircle2, FlaskConical, History, Layers, Loader2, Lock, Pause, Play, Plus, Power, RefreshCw, ShieldCheck, Sparkles, Trash2, Wand2, Workflow, Wrench } from 'lucide-react';
import { useApp } from '../state';
import { useCfg, useServidor, erroTexto } from '../components/Servidor2';
import Esteira from '../components/Esteira';
import ProgramacaoDiaria from '../components/ProgramacaoDiaria';
import { catalogo, type Catalogo } from '../lib/api';
import { lerCapacidades } from '../lib/esteira';
import { aplicarSugestoes, apagarLinha, apagarItemBiblioteca, criarItemBiblioteca, criarLinha, ligarFerramenta, listarBiblioteca, listarFerramentas, mudarItemBiblioteca, sugerirLinha, testarFerramenta, type ItemBiblioteca, type Sugestao_Linha, escreverPautas, eventosCentral, iniciarLote, mudarLinha, mudarPauta, obterLinha, pausarCentral, planejarPautas,
  resumoCentral, retomarCentral, salvarCentral, simularCentral, sugestoesCentral, type ConfigCentral, type ConfigLinha, type Linha, type Simulacao } from '../lib/automacao';

type Aba='geral'|'agentes'|'linhas'|'calendario'|'qualidade'|'historico';
const ABAS:[Aba,string][]=[['geral','Visão geral'],['agentes','Agentes'],['linhas','Linhas de conteúdo'],['calendario','Calendário'],['qualidade','Qualidade e revisões'],['historico','Histórico e skills']];
const ESTADO_NOME={desligada:'Desligada',ativa:'Ligada',pausada:'Pausada'};
const ACAO:Record<string,string>={nada:'Parado',esperar:'Esperando o intervalo',cortar:'Cortar',buscar_canais:'Procurar canais',planejar:'Planejar pautas e produzir',lote:'Começar lote',meta_semanal:'Meta semanal'};
const AGENTE:Record<string,string>={agente1:'Agente 1',agente2:'Agente 2',agente3:'Agente 3',central:'Central'};
const REDES:[string,string][]=[['youtube','YouTube'],['instagram','Instagram'],['facebook','Facebook'],['tiktok','TikTok'],['kwai','Kwai']];
const quando=(t:number)=>new Date(t*1000).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});

export default function Central(){
  const {rotaExtra,go}=useApp(); const cfg=useCfg();
  const [aba,setAba]=useState<Aba>((ABAS.find(a=>a[0]===rotaExtra)?.[0])||'geral');
  const r=useServidor(c=>resumoCentral(c),30);
  if(!cfg.servidor) return <section className="panel"><p className="hint">Conecte o servidor do celular em Ajustes para usar a Central de Automação.</p></section>;
  const trocar=(a:Aba)=>{ setAba(a); go('central',a); };
  return <div className="central">
    <div className="ag-abas" role="tablist">{ABAS.map(([k,t])=><button key={k} role="tab" aria-selected={aba===k} className={aba===k?'active':''} onClick={()=>trocar(k)}>{t}</button>)}</div>
    {r.erro&&<p className="hint bad"><AlertTriangle size={13}/> {r.erro}</p>}
    {aba==='geral'&&<Geral r={r}/>}
    {aba==='agentes'&&r.dados&&<Agentes conf={r.dados.config} est={r.dados.estoque_cortes} esteira={r.dados.esteira_ligada} salvo={r.recarregar}/>}
    {aba==='linhas'&&<Linhas/>}
    {aba==='calendario'&&<ProgramacaoDiaria/>}
    {aba==='qualidade'&&<Esteira/>}
    {aba==='historico'&&<Historico/>}
  </div>;
}

function Geral({r}:{r:ReturnType<typeof useServidor<import('../lib/automacao').ResumoCentral>>}){
  const {toast}=useApp(); const cfg=useCfg();
  const [sim,setSim]=useState<Simulacao|null>(null); const [busy,setBusy]=useState(false);
  const sug=useServidor(c=>sugestoesCentral(c),0);
  const x=r.dados;
  async function fazer(f:()=>Promise<unknown>,msg:string){ setBusy(true); try{ await f(); toast(msg,'ok'); await r.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }
  if(!x) return <p className="hint"><Loader2 size={13} className="spin"/> Lendo...</p>;
  const st=x.config.estado; const i=x.indicadores;
  return <>
    <section className="panel">
      <div className="section-head"><h2><Workflow size={18}/> Central de Automação</h2><span className={'tag '+(st==='ativa'?'ok':st==='pausada'?'bad':'')}>{ESTADO_NOME[st]}</span></div>
      <p className="hint">Ligada, o <b>estoque</b> decide quando os agentes trabalham: o Agente 1 só procura e corta quando os cortes aprovados caem abaixo do mínimo, e para quando chega no alvo. As linhas de conteúdo do Agente 3 em modo contínuo seguem a mesma regra. Nada é postado sem o certificado do diretor. Desligada, tudo funciona como antes.</p>
      {!x.esteira_ligada&&<p className="hint bad"><AlertTriangle size={13}/> A esteira (diretor e editor) está desligada: sem certificado, a programação diária não recebe vídeo. Ligue em Qualidade e revisões.</p>}
      <div className="row">
        {st!=='ativa'&&<button className="primary sm" disabled={busy} onClick={()=>fazer(()=>st==='pausada'?retomarCentral(cfg):salvarCentral(cfg,{estado:'ativa'}),'Central ligada.')}><Play size={14}/> {st==='pausada'?'Retomar':'Ligar'}</button>}
        {st==='ativa'&&<button className="subtle sm" disabled={busy} onClick={()=>fazer(()=>pausarCentral(cfg),'Pausada. O que já está rodando termina; nada novo começa.')}><Pause size={14}/> Pausar</button>}
        {st!=='desligada'&&<button className="subtle sm" disabled={busy} onClick={()=>fazer(()=>salvarCentral(cfg,{estado:'desligada'}),'Desligada: os agentes voltam à regra antiga.')}><Power size={14}/> Desligar</button>}
        <button className="subtle sm" disabled={busy} onClick={async()=>{ setBusy(true); try{ setSim(await simularCentral(cfg)); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }}><FlaskConical size={14}/> Simular agora</button>
        <button className="icon-btn" aria-label="Atualizar" onClick={()=>r.recarregar()}><RefreshCw size={13}/></button>
      </div>
      <div className="pd-metricas">
        <div className="es-ag"><b>{i.estoque_cortes}</b><span>cortes aprovados</span><small>mínimo {x.config.cortes.minimo} · alvo {x.config.cortes.alvo}</small></div>
        <div className="es-ag"><b>{i.estoque_linhas}</b><span>vídeos das linhas</span><small>aprovados, sem horário</small></div>
        <div className="es-ag"><b>{i.rodando}</b><span>rodando agora</span><small>{i.na_fila} na fila</small></div>
        <div className={'es-ag'+(i.esperando_voce+i.revisao_manual?' bad':'')}><b>{i.esperando_voce+i.revisao_manual}</b><span>esperando você</span><small>{i.revisao_manual} na revisão manual</small></div>
        <div className={'es-ag'+(i.falhas_24h?' bad':'')}><b>{i.falhas_24h}</b><span>falhas em 24 h</span><small>trabalhos e horários</small></div>
      </div>
    </section>
    {sim&&<section className="panel">
      <h3><FlaskConical size={16}/> O que a automação faria agora</h3>
      <p className="hint">Com os seus números reais. A simulação não grava nada e não chama nenhum agente.</p>
      {sim.aviso&&<p className="hint">{sim.aviso}</p>}
      {sim.cortes&&'decisao' in sim.cortes&&<p><b>Agente 1:</b> <span className="tag">{ACAO[sim.cortes.decisao.acao]||sim.cortes.decisao.acao}</span> {sim.cortes.decisao.motivo}</p>}
      {sim.cortes&&'erro' in sim.cortes&&<p className="hint bad">Agente 1: {sim.cortes.erro}</p>}
      {sim.linhas.map(l=><p key={l.linha}><b>{l.titulo}:</b> <span className="tag">{ACAO[l.decisao.acao]||l.decisao.acao}</span> {l.decisao.motivo}</p>)}
      {!sim.linhas.length&&<p className="muted">Nenhuma linha de conteúdo criada.</p>}
    </section>}
    <section className="panel">
      <h3><CalendarClock size={16}/> Próximas postagens</h3>
      {x.proximas.length?<ul className="rq-lista">{x.proximas.map(s=><li key={s.id}>{quando(s.quando_utc)} · {REDES.find(q=>q[0]===s.rede)?.[1]||s.rede} <span className="tag">{s.estado==='vazio'?'sem vídeo ainda':s.estado}</span></li>)}</ul>
        :<p className="muted">Nenhum horário programado. Crie a programação na aba Calendário.</p>}
    </section>
    {(sug.dados?.sugestoes||[]).length>0&&<section className="panel">
      <h3><Wand2 size={16}/> Sugestões</h3><p className="hint">{sug.dados?.aviso}</p>
      <ul className="rq-lista">{sug.dados!.sugestoes.map(s=><li key={s.id}><b>{s.titulo}</b><br/><small className="muted">{s.porque}</small>
        {s.mudanca&&<div><button className="subtle sm" disabled={busy} onClick={()=>fazer(()=>aplicarSugestoes(cfg,[s.id]),'Sugestão aplicada.').then(()=>sug.recarregar())}>Aplicar</button></div>}</li>)}</ul>
    </section>}
    <section className="panel">
      <h3><History size={16}/> Últimas decisões</h3>
      {x.eventos.length?<ul className="rq-lista">{x.eventos.map(e=><li key={e.n}><small className="muted">{quando(e.t)} · {AGENTE[e.agente]||e.agente}</small> <span className="tag">{ACAO[e.decisao]||e.decisao}</span> {e.motivo}</li>)}</ul>
        :<p className="muted">Nada ainda. Quando a central decidir algo, aparece aqui com o motivo.</p>}
    </section>
  </>;
}

function Agentes({conf,est,esteira,salvo}:{conf:ConfigCentral;est:import('../lib/automacao').EstoqueCortes;esteira:boolean;salvo:()=>void}){
  const {toast,go}=useApp(); const cfg=useCfg();
  const [c,setC]=useState(conf.cortes); const [li,setLi]=useState(conf.linhas); const [busy,setBusy]=useState(false);
  const [ed,setEd]=useState(conf.editor?.modo||'automatico');
  useEffect(()=>{ setC(conf.cortes); setLi(conf.linhas); setEd(conf.editor?.modo||'automatico'); },[conf]);
  async function salvar(d:Parameters<typeof salvarCentral>[1]){ setBusy(true); try{ await salvarCentral(cfg,{...d,versao:conf.versao}); toast('Salvo.','ok'); salvo(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }
  const num=(k:keyof typeof c,rot:string,dica:string)=><label>{rot}<input type="number" value={Number(c[k])} onChange={e=>setC({...c,[k]:Number(e.target.value)})}/><small className="muted">{dica}</small></label>;
  return <>
    <section className="panel">
      <h3>Agente 1 · Cortes</h3>
      <label className="check"><input type="checkbox" checked={c.controle_estoque} onChange={e=>setC({...c,controle_estoque:e.target.checked})}/> Cortar só quando o estoque precisar (desmarcado: segue a meta de cortes por semana)</label>
      <div className="row">{(['economico','equilibrado','intensivo'] as const).map(m=><button key={m} className={(conf.modo===m?'primary':'subtle')+' sm'} disabled={busy} onClick={()=>salvar({modo:m})}>{({economico:'Econômico',equilibrado:'Equilibrado',intensivo:'Intensivo'})[m]}</button>)}
        {conf.modo==='personalizado'&&<span className="tag">Personalizado</span>}</div>
      <div className="grid2">
        {num('minimo','Estoque mínimo','Abaixo disso o Agente 1 volta a trabalhar.')}
        {num('alvo','Estoque alvo','Chegou aqui, ele para.')}
        {num('busca_horas','Procurar canais a cada (horas)','Só quando está repondo.')}
        {num('cooldown_min','Intervalo entre rodadas (min)','Evita cortar sem parar.')}
        <label>Quando trabalhar<select value={c.frequencia||'estoque'} onChange={e=>setC({...c,frequencia:e.target.value as typeof c.frequencia})}>
          <option value="estoque">Pelo estoque (mínimo e alvo)</option><option value="agenda">Só pela meta de cortes por semana (Agentes 1, 2 e 3)</option>
          <option value="hibrido">Os dois: estoque e meta da semana</option></select><small className="muted">No modo "os dois", ele também corta se a meta da semana estiver atrasada.</small></label>
        {num('fontes_rodada','Vídeos-fonte por rodada (1 a 5)','Quantos vídeos longos ele lê em cada rodada de reposição.')}
      </div>
      <button className="primary sm" disabled={busy} onClick={()=>salvar({cortes:c})}>Salvar</button>
      <p className="hint">Agora: <b>{est.disponiveis}</b> corte(s) aprovado(s) sem horário, {est.reservados} agendado(s). A programação pede cerca de <b>{est.demanda_dia}</b> vídeo(s) por dia ({est.demanda_fonte})
        {est.cobertura_dias!=null&&<> : o estoque cobre <b>{est.cobertura_dias}</b> dia(s)</>}. Taxa de aprovação do diretor: {Math.round(est.taxa_aprovacao*100)}%{est.taxa_estimada?' (estimativa: menos de 5 cortes julgados)':` (últimos ${est.taxa_amostra} cortes)`}.</p>
      <p className="hint">Ligar e desligar o Agente 1, os canais e o horário de trabalho continuam em <button className="link-btn" onClick={()=>go('agente')}>Agentes 1, 2 e 3</button>.</p>
    </section>
    <section className="panel">
      <h3>Agente 3 · Linhas de conteúdo</h3>
      <label>Intervalo mínimo entre lotes automáticos (min)<input type="number" value={li.cooldown_min} onChange={e=>setLi({cooldown_min:Number(e.target.value)})}/></label>
      <button className="primary sm" disabled={busy} onClick={()=>salvar({linhas:li})}>Salvar</button>
      <p className="hint">Cada linha tem o seu mínimo, alvo e limite por dia. Configure na aba Linhas de conteúdo.</p>
    </section>
    <section className="panel">
      <h3>Agentes 4 e 5 · Diretor e editor</h3>
      <p className="hint"><ShieldCheck size={13}/> Regra fixa: nota 70 ou mais e nenhum bloqueio. A primeira avaliação não conta; até 5 correções por etapa; depois disso, a sua revisão. {esteira?'Esteira ligada.':'Esteira desligada.'}</p>
      <label>Como o editor trabalha<select value={ed} onChange={e=>setEd(e.target.value as typeof ed)}>
        <option value="automatico">Automático: corrige e o diretor aprova sozinho</option>
        <option value="supervisionado">Supervisionado: corrige, mas eu dou o ok final em Qualidade e revisões</option>
        <option value="manual">Manual: não corrige nada sozinho, vai direto para mim</option></select></label>
      <button className="primary sm" disabled={busy} onClick={()=>salvar({editor:{modo:ed}})}>Salvar</button>
    </section>
    <section className="panel">
      <h3>Agente 2 · Postagem</h3>
      <p className="hint">Os horários de cada rede ficam na aba Calendário. Um horário só recebe vídeo com certificado do diretor para o arquivo atual. O mesmo vídeo pode ir para várias redes, uma publicação por rede, nunca duas vezes na mesma.</p>
    </section>
  </>;
}

const NOVA:Partial<ConfigLinha>={titulo:'',tema:'',quantidade_lote:6,duracao_seg:45,estilo:'documentario',modo_pautas:'supervisionado',aprovar_roteiro:'voce',publicacao:'voce',
  modo_execucao:'lote_unico',limite_dia:3,estoque:{minimo:3,alvo:7},agenda:{redes:[],horarios:[],dias:[0,1,2,3,4,5,6]},prioridade:3,orcamento_dia:0,orcamento_video:2,personagens:{modo:'nenhum',ids:[],descricao:''},cenarios:{ids:[],descricao:''},travas:[]};

function Linhas(){
  const ls=useServidor(c=>import('../lib/automacao').then(m=>m.listarLinhas(c)),30);
  const [aberta,setAberta]=useState(''); const [nova,setNova]=useState(false); const [inicial,setInicial]=useState<Partial<ConfigLinha>|undefined>();
  return <>
    {!nova&&<Descricao usar={p=>{ setInicial(p); setNova(true); }}/>}
    <section className="panel">
      <div className="section-head"><h2><Layers size={18}/> Linhas de conteúdo</h2>{ls.carregando&&<Loader2 size={14} className="spin"/>}</div>
      <p className="hint">Uma linha é uma ideia livre (ex.: "Curiosidades Científicas") que vira várias pautas diferentes, e cada pauta vira um vídeo independente. Pautas parecidas com outras já feitas são barradas.</p>
      {ls.erro&&<p className="hint bad">{ls.erro}</p>}
      <ul className="pd-agendas">{(ls.dados?.linhas||[]).map(l=><li key={l.id}>
        <b>{l.titulo}</b> <span className={'tag '+(l.estado==='ativa'?'ok':'')}>{l.estado==='ativa'?'ativa':'pausada'}</span>
        <span className="muted">{l.modo_execucao==='continuo'?'contínuo':'lote único'} · {l.estoque.livres} pronto(s) · {l.estoque.em_producao} em produção · {l.estoque.esperando_voce} esperando você</span>
        <button className="subtle sm" onClick={()=>setAberta(aberta===l.id?'':l.id)}>{aberta===l.id?'Fechar':'Abrir'}</button>
      </li>)}</ul>
      {!nova&&<button className="subtle sm" onClick={()=>{ setInicial(undefined); setNova(true); }}><Plus size={14}/> Nova linha em branco</button>}
    </section>
    {nova&&<FormLinha inicial={inicial} fechar={()=>setNova(false)} salvo={(id)=>{ setNova(false); setAberta(id); ls.recarregar(); }}/>}
    {aberta&&<DetalheLinha id={aberta} mudou={ls.recarregar} fechar={()=>{ setAberta(''); ls.recarregar(); }}/>}
    <Biblioteca/>
  </>;
}

const CAMPO_NOME:Record<string,string>={titulo:'Nome',tema:'Tema',subtemas:'Subtemas',excluir:'Assuntos proibidos',publico:'Público',tom:'Tom',ideia_geral:'Ideia geral',ideia_roteiro:'Roteiro',
  estilo:'Estilo',formato:'Formato',voz:'Voz',ritmo:'Ritmo',duracao_seg:'Duração (s)',quantidade_lote:'Vídeos por lote',modo_pautas:'Pautas',aprovar_roteiro:'Roteiro',publicacao:'Publicação',
  agenda:'Agenda',prioridade:'Prioridade',modo_execucao:'Execução',limite_dia:'Limite por dia',objetivo:'Objetivo',idioma:'Idioma',gancho_preferido:'Gancho'};
const mostrar=(v:unknown)=>v==null||v===''?'—':typeof v==='object'?JSON.stringify(v).replace(/[{}"[\]]/g,'').replace(/,/g,', ').slice(0,120):String(v);

function Descricao({usar}:{usar:(p:Partial<ConfigLinha>)=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const [txt,setTxt]=useState(''); const [busy,setBusy]=useState(false); const [r,setR]=useState<Sugestao_Linha|null>(null);
  return <section className="panel">
    <h3><Sparkles size={16}/> Criar uma linha a partir de uma descrição</h3>
    <p className="hint">Escreva do seu jeito (ex.: "6 vídeos de curiosidades sobre o corpo humano, tom leve, para o TikTok às 12h e 19h, eu aprovo cada um"). A IA monta a configuração, você confere cada campo e só depois salva. Nada é gravado antes de você salvar.</p>
    <label>Descrição<textarea rows={3} value={txt} onChange={e=>setTxt(e.target.value)} placeholder="Descreva a linha de conteúdo"/></label>
    <div className="row"><button className="primary sm" disabled={busy||txt.trim().length<10} onClick={async()=>{ setBusy(true); setR(null);
      try{ setR(await sugerirLinha(cfg,txt)); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }}>{busy?<Loader2 size={14} className="spin"/>:<Wand2 size={14}/>} Montar proposta</button></div>
    {r&&<>
      {r.avisos.map((a,i)=><p key={i} className="hint bad"><AlertTriangle size={13}/> {a}</p>)}
      <p className="hint">A IA preencheu {r.mudancas.length} campo(s):</p>
      <ul className="mudancas">{r.mudancas.map(m=><li key={m.campo}><b>{CAMPO_NOME[m.campo]||m.campo}:</b> {mostrar(m.para)}</li>)}</ul>
      <div className="row"><button className="primary sm" onClick={()=>{ usar(r.proposta); setR(null); setTxt(''); }}><CheckCircle2 size={14}/> Conferir e salvar</button>
        <button className="subtle sm" onClick={()=>setR(null)}>Descartar</button></div>
    </>}
  </section>;
}

const DIAS=['seg','ter','qua','qui','sex','sáb','dom'];
function FormLinha({base,inicial,fechar,salvo}:{base?:Linha;inicial?:Partial<ConfigLinha>;fechar:()=>void;salvo:(id:string)=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const [d,setD]=useState<Partial<ConfigLinha>>(base?{...base}:{...NOVA,...(inicial||{})});
  const [hora,setHora]=useState('');
  const bib=useServidor(c=>listarBiblioteca(c),0);
  const ag=d.agenda||{redes:[],horarios:[],dias:[0,1,2,3,4,5,6]};
  const setAg=(p:Partial<ConfigLinha['agenda']>)=>setD(x=>({...x,agenda:{...{redes:[],horarios:[],dias:[0,1,2,3,4,5,6]},...(x.agenda||{}),...p}}));
  const [cat,setCat]=useState<Catalogo|null>(null); const [busy,setBusy]=useState(false);
  const pers=useServidor(c=>import('../lib/api').then(m=>m.api<{personagens:{id:string;nome:string;versao:number}[]}>(c,'GET','/api/v1/personagens')),0);
  useEffect(()=>{ catalogo(cfg).then(setCat).catch(()=>{}); },[cfg]);
  const set=(p:Partial<ConfigLinha>)=>setD(x=>({...x,...p}));
  const est=cat?.estilos.find(e=>e.id===d.estilo);
  const animado=d.estilo==='animado2d'||d.estilo==='animado3d';
  const trava=(k:string)=><button type="button" className={'icon-btn'+((d.travas||[]).includes(k)?' on':'')} aria-label={'Travar '+k} title="Travado: sugestão automática não muda"
    onClick={()=>set({travas:(d.travas||[]).includes(k)?(d.travas||[]).filter(x=>x!==k):[...(d.travas||[]),k]})}><Lock size={11}/></button>;
  async function salvar(){
    setBusy(true);
    try{ const r=base?await mudarLinha(cfg,base.id,{...d,versao:base.versao}):await criarLinha(cfg,d);
      const ap=(r.agenda_aplicada||[]).map(a=>`${REDES.find(q=>q[0]===a.rede)?.[1]||a.rede}: ${a.acao}`).join(' · ');
      toast('Linha salva.'+(ap?' Horários: '+ap:''),'ok'); salvo(r.id); }
    catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); }
  }
  return <section className="panel">
    <h3>{base?'Editar linha':'Nova linha de conteúdo'}</h3>
    <div className="grid2">
      <label>Nome<input value={d.titulo||''} onChange={e=>set({titulo:e.target.value})} placeholder="Curiosidades Científicas"/></label>
      <label>Tema principal<input value={d.tema||''} onChange={e=>set({tema:e.target.value})} placeholder="ciência do dia a dia"/></label>
      <label>Subtemas (separe com vírgula)<input value={(d.subtemas||[]).join(', ')} onChange={e=>set({subtemas:e.target.value.split(',').map(s=>s.trim()).filter(Boolean)})}/></label>
      <label>Assuntos proibidos<input value={(d.excluir||[]).join(', ')} onChange={e=>set({excluir:e.target.value.split(',').map(s=>s.trim()).filter(Boolean)})}/></label>
      <label>Público<input value={d.publico||''} onChange={e=>set({publico:e.target.value})}/></label>
      <label>Tom<input value={d.tom||''} onChange={e=>set({tom:e.target.value})} placeholder="leve e curioso"/></label>
    </div>
    <label>Ideia geral<textarea rows={3} value={d.ideia_geral||''} onChange={e=>set({ideia_geral:e.target.value})}/></label>
    <label>Como deve ser o roteiro {trava('ideia_roteiro')}<textarea rows={2} value={d.ideia_roteiro||''} onChange={e=>set({ideia_roteiro:e.target.value})}/></label>
    <div className="grid2">
      <label>Estilo {trava('estilo')}<select value={d.estilo} onChange={e=>set({estilo:e.target.value})}>
        {(cat?.estilos||[{id:'documentario',nome:'Documentário',status:'operacional'}]).map(e=><option key={e.id} value={e.id} disabled={e.status==='indisponivel'}>
          {e.nome}{e.status==='beta'?' (em teste)':e.status==='indisponivel'?' (não roda aqui)':''}</option>)}</select></label>
      <label>Formato {trava('formato')}<select value={d.formato||'9:16'} onChange={e=>set({formato:e.target.value})}>{(cat?.formatos||['9:16']).map(f=><option key={f}>{f}</option>)}</select></label>
      <label>Voz {trava('voz')}<select value={d.voz||'Charon'} onChange={e=>set({voz:e.target.value})}>{[...(cat?.vozes||['Charon']),'nenhuma'].map(v=><option key={v}>{v}</option>)}</select></label>
      <label>Duração (segundos) {trava('duracao_seg')}<input type="number" value={d.duracao_seg} onChange={e=>set({duracao_seg:Number(e.target.value)})}/></label>
    </div>
    {est?.status==='beta'&&<label className="check"><input type="checkbox" checked={!!d.confirmar_beta} onChange={e=>set({confirmar_beta:e.target.checked})}/> Aceito usar um estilo em teste (beta)</label>}
    <label>Personagens {trava('personagens')}<select value={d.personagens?.modo||'nenhum'} disabled={!animado} onChange={e=>set({personagens:{...(d.personagens||{ids:[],descricao:''}),modo:e.target.value}})}>
      <option value="nenhum">Sem personagem</option><option value="fixo">Fixo (o mesmo em todos)</option><option value="variavel">Variável</option><option value="misto">Misto</option></select>
      {!animado&&<small className="muted">Personagem só existe nos estilos animados (Desenho animado 2D/3D).</small>}</label>
    {animado&&d.personagens?.modo!=='nenhum'&&<div className="row">{(pers.dados?.personagens||[]).map(p=>{ const on=(d.personagens?.ids||[]).some(x=>x.id===p.id);
      return <label key={p.id} className="check"><input type="checkbox" checked={on} onChange={()=>set({personagens:{...d.personagens!,ids:on?d.personagens!.ids.filter(x=>x.id!==p.id):[...d.personagens!.ids,{id:p.id,versao:p.versao}]}})}/> {p.nome} (v{p.versao})</label>; })}
      {!(pers.dados?.personagens||[]).length&&<small className="muted">Nenhum personagem na biblioteca. Crie em Séries animadas, ou descreva abaixo.</small>}
      <input value={d.personagens?.descricao||''} onChange={e=>set({personagens:{...d.personagens!,descricao:e.target.value}})} placeholder="Ou descreva o personagem"/></div>}
    <div className="grid2">
      <label>Pautas<select value={d.modo_pautas} onChange={e=>set({modo_pautas:e.target.value as ConfigLinha['modo_pautas']})}>
        <option value="supervisionado">A IA propõe, eu aceito</option><option value="automatico">A IA escolhe sozinha</option><option value="manual">Eu escrevo</option></select></label>
      <label>Roteiro<select value={d.aprovar_roteiro} onChange={e=>set({aprovar_roteiro:e.target.value as ConfigLinha['aprovar_roteiro']})}>
        <option value="voce">Eu aprovo cada roteiro</option><option value="automatico">Segue direto (o diretor confere)</option></select></label>
      <label>Vídeos por lote<input type="number" value={d.quantidade_lote} onChange={e=>set({quantidade_lote:Number(e.target.value)})}/></label>
      <label>Vídeos começados por dia (limite)<input type="number" value={d.limite_dia} onChange={e=>set({limite_dia:Number(e.target.value)})}/></label>
      <label>Execução<select value={d.modo_execucao} onChange={e=>set({modo_execucao:e.target.value as ConfigLinha['modo_execucao']})}>
        <option value="lote_unico">Lote único (quando eu pedir)</option><option value="continuo">Contínuo (repõe o estoque)</option></select></label>
      <label>Publicação<select value={d.publicacao} onChange={e=>set({publicacao:e.target.value as ConfigLinha['publicacao']})}>
        <option value="voce">Eu aprovo cada vídeo</option><option value="automatica">Automática com certificado do diretor</option></select></label>
      {d.modo_execucao==='continuo'&&<><label>Estoque mínimo<input type="number" value={d.estoque?.minimo} onChange={e=>set({estoque:{...d.estoque!,minimo:Number(e.target.value)}})}/></label>
        <label>Estoque alvo<input type="number" value={d.estoque?.alvo} onChange={e=>set({estoque:{...d.estoque!,alvo:Number(e.target.value)}})}/></label></>}
    </div>
    <h3><CalendarClock size={16}/> Onde e quando postar</h3>
    <div className="row">Redes: {REDES.map(([k,n])=>{ const on=ag.redes.includes(k);
      return <label key={k} className="check"><input type="checkbox" checked={on} onChange={()=>setAg({redes:on?ag.redes.filter(x=>x!==k):[...ag.redes,k]})}/> {n}</label>; })}</div>
    <div className="row">Horários: {(ag.horarios||[]).map(h=><span key={h} className="tag">{h} <button type="button" className="link-btn" aria-label={'Tirar '+h} onClick={()=>setAg({horarios:(ag.horarios||[]).filter(x=>x!==h)})}>×</button></span>)}
      <input type="time" value={hora} onChange={e=>setHora(e.target.value)} style={{width:120}}/>
      <button type="button" className="subtle sm" disabled={!hora} onClick={()=>{ setAg({horarios:[...new Set([...(ag.horarios||[]),hora])].sort()}); setHora(''); }}><Plus size={12}/> horário</button></div>
    <div className="row">Dias: {DIAS.map((n,i)=>{ const on=(ag.dias||[]).includes(i);
      return <label key={i} className="check"><input type="checkbox" checked={on} onChange={()=>setAg({dias:on?(ag.dias||[]).filter(x=>x!==i):[...(ag.dias||[]),i].sort()})}/> {n}</label>; })}</div>
    <p className="hint">Ao salvar, estes horários entram na programação diária de cada rede marcada (se a rede já tiver programação fixa, os horários são somados). Os vídeos aprovados ocupam esses horários sozinhos: um vídeo pode ir para várias redes, uma vez em cada, nunca duas vezes na mesma.</p>
    <div className="grid2">
      <label>Prioridade na agenda (1 a 5)<input type="number" min={1} max={5} value={d.prioridade??3} onChange={e=>set({prioridade:Number(e.target.value)})}/><small className="muted">Quando duas linhas disputam o mesmo horário, a de número maior entra primeiro.</small></label>
      <label>Orçamento por dia (R$, 0 = sem limite)<input type="number" min={0} step="0.5" value={d.orcamento_dia??0} onChange={e=>set({orcamento_dia:Number(e.target.value)})}/><small className="muted">Soma o custo estimado dos vídeos começados nas últimas 24 h.</small></label>
      <label>Gasto máximo por vídeo (R$)<input type="number" min={0} step="0.5" value={d.orcamento_video??2} onChange={e=>set({orcamento_video:Number(e.target.value)})}/></label>
    </div>
    <h3><BookOpen size={16}/> Biblioteca criativa</h3>
    <div className="grid2">{([['modelo_roteiro','Modelo de roteiro'],['pacote_visual','Pacote visual'],['perfil_narracao','Perfil de narração']] as const).map(([k,n])=>
      <label key={k}>{n}<select value={d.biblioteca?.[k]||''} onChange={e=>set({biblioteca:{modelo_roteiro:'',pacote_visual:'',perfil_narracao:'',...(d.biblioteca||{}),[k]:e.target.value}})}>
        <option value="">Nenhum</option>{(bib.dados?.itens||[]).filter(i=>i.tipo===k).map(i=><option key={i.id} value={i.id}>{i.nome} (v{i.versao})</option>)}</select></label>)}</div>
    <p className="hint">Cada vídeo guarda a versão do item que usou. Mudar o item depois não altera vídeo já feito.</p>
    <div className="row"><button className="primary sm" disabled={busy} onClick={salvar}>{busy?<Loader2 size={14} className="spin"/>:<CheckCircle2 size={14}/>} Salvar</button><button className="subtle sm" onClick={fechar}>Cancelar</button></div>
  </section>;
}

const PAUTA_NOME:Record<string,string>={proposta:'proposta',aceita:'aceita',precisa_voce:'precisa de você',bloqueada:'bloqueada',usada:'virou vídeo',repetida:'repetida'};

function DetalheLinha({id,mudou,fechar}:{id:string;mudou:()=>void;fechar:()=>void}){
  const {toast,go}=useApp(); const cfg=useCfg();
  const l=useServidor(c=>obterLinha(c,id),30,[id]);
  const [busy,setBusy]=useState(false); const [editar,setEditar]=useState(false); const [minhas,setMinhas]=useState('');
  const x=l.dados;
  async function fazer(f:()=>Promise<unknown>,msg:string|((r:unknown)=>string)){ setBusy(true); try{ const r=await f(); toast(typeof msg==='string'?msg:msg(r),'ok'); await l.recarregar(); mudou(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }
  if(!x) return <section className="panel"><p className="hint"><Loader2 size={13} className="spin"/> Lendo a linha...</p></section>;
  if(editar) return <FormLinha base={x} fechar={()=>setEditar(false)} salvo={()=>{ setEditar(false); l.recarregar(); mudou(); }}/>;
  const aceitas=x.pautas.filter(p=>p.status==='aceita').length;
  return <section className="panel">
    <div className="section-head"><h2>{x.titulo}</h2><span className={'tag '+(x.estado==='ativa'?'ok':'')}>{x.estado}</span></div>
    <p className="hint">{x.tema} · estilo {x.estilo} · {x.quantidade_lote} por lote · até {x.limite_dia} por dia · {x.modo_execucao==='continuo'?`contínuo (mínimo ${x.estoque.minimo}, alvo ${x.estoque.alvo})`:'lote único'}</p>
    <div className="row">
      <button className="subtle sm" disabled={busy||x.modo_pautas==='manual'} onClick={()=>fazer(()=>planejarPautas(cfg,id),r=>{ const q=r as {pautas:unknown[];aviso:string}; return q.aviso||`${q.pautas.length} pauta(s) nova(s).`; })}><Wand2 size={14}/> Planejar pautas</button>
      <button className="primary sm" disabled={busy||!aceitas||x.estado!=='ativa'} onClick={()=>fazer(()=>iniciarLote(cfg,id),r=>`${(r as {episodios:unknown[]}).episodios.length} vídeo(s) começado(s).`)}><Play size={14}/> Produzir lote ({Math.min(aceitas,x.quantidade_lote)})</button>
      <button className="subtle sm" disabled={busy} onClick={()=>fazer(()=>import('../lib/automacao').then(m=>m.pausarLinha(cfg,id,x.estado==='ativa')),x.estado==='ativa'?'Linha pausada.':'Linha retomada.')}>{x.estado==='ativa'?<><Pause size={14}/> Pausar</>:<><Play size={14}/> Retomar</>}</button>
      <button className="subtle sm" onClick={()=>setEditar(true)}>Editar</button>
      <button className="icon-btn" aria-label="Apagar linha" onClick={async()=>{ if(!confirm('Apagar esta linha? Os vídeos já feitos continuam em Meus projetos.')) return; try{ await apagarLinha(cfg,id); fechar(); }catch(e){ toast(erroTexto(e),'erro'); } }}><Trash2 size={13}/></button>
    </div>
    <h3>Pautas ({x.pautas.length})</h3>
    <div className="row"><input value={minhas} onChange={e=>setMinhas(e.target.value)} placeholder="Escreva pautas suas (uma por linha ou separadas por ;)"/>
      <button className="subtle sm" disabled={busy||!minhas.trim()} onClick={()=>fazer(()=>escreverPautas(cfg,id,minhas.split(/[;\n]/).map(s=>s.trim()).filter(Boolean)).then(r=>{ setMinhas(''); return r; }),
        r=>{ const q=r as {pautas:unknown[];repetidas:unknown[]}; return `${q.pautas.length} aceita(s)${q.repetidas.length?`, ${q.repetidas.length} repetida(s)`:''}.`; })}>Adicionar</button></div>
    <ul className="rq-lista">{x.pautas.map(p=><li key={p.id}>
      <span className="tag">{PAUTA_NOME[p.status]||p.status}</span> <b>{p.titulo}</b>{p.resumo&&<small className="muted"> — {p.resumo}</small>}
      {p.verificacao&&p.verificacao!=='não se aplica'&&<><br/><small className={p.verificacao==='não verificado'?'bad':'muted'}>Conferência: {p.verificacao}{p.risco==='alto'?' · assunto sensível (saúde, dinheiro ou lei): só entra com o seu ok':''}</small></>}
      {(p.conferencia||[]).length>0&&<ul className="conf">{p.conferencia!.map((c,i)=><li key={i} className={c.ok?'':'bad'}>{c.ok?'✓':'✗'} {c.afirmacao}
        {c.ok?<small className="muted"> — trecho achado: "{c.trecho.slice(0,140)}"</small>:<small> — {c.motivo}</small>}</li>)}</ul>}
      {(p.fontes||[]).length>0&&<small> · {(p.fontes||[]).map((f,i)=><a key={i} href={f.url} target="_blank" rel="noreferrer">fonte {i+1}</a>)}</small>}
      {['proposta','precisa_voce','aceita'].includes(p.status)&&<span className="row">
        {p.status!=='aceita'&&<button className="subtle sm" disabled={busy} onClick={()=>fazer(()=>mudarPauta(cfg,p.id,'aceitar'),'Aceita.')}>Aceitar</button>}
        <button className="subtle sm" disabled={busy} onClick={()=>fazer(()=>mudarPauta(cfg,p.id,'trocar'),'Trocada.')}>Trocar</button>
        <button className="subtle sm" disabled={busy} onClick={()=>fazer(()=>mudarPauta(cfg,p.id,'bloquear'),'Bloqueada.')}>Bloquear</button></span>}
    </li>)}</ul>
    <h3>Episódios ({x.episodios.length})</h3>
    {x.episodios.length?<ul className="rq-lista">{x.episodios.map(e=><li key={e.id}>
      <b>{e.titulo}</b> <span className="tag">{e.nome_status}</span>{e.nota!=null&&<span className="tag">nota {e.nota}</span>}
      {(e.publicacoes||[]).map((p,i)=><span key={i} className="tag ok">{p.rede} {quando(p.quando_utc)}</span>)}
      {e.erro&&<><br/><small className="bad">{e.erro}</small></>}
      <button className="link-btn" onClick={()=>go('revisar',e.projeto)}>abrir</button>
    </li>)}</ul>:<p className="muted">Nenhum vídeo ainda. Aceite pautas e produza um lote.</p>}
  </section>;
}

function Historico(){
  const ev=useServidor(c=>eventosCentral(c),60);
  const fer=useServidor(c=>listarFerramentas(c),0);
  const {toast}=useApp(); const cfg=useCfg(); const [busy,setBusy]=useState(''); const [lic,setLic]=useState<Record<string,boolean>>({});
  async function fazer(id:string,f:()=>Promise<unknown>,msg:(r:unknown)=>string){ setBusy(id); try{ toast(msg(await f()),'ok'); await fer.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } }
  const cap=useServidor(c=>lerCapacidades(c),0);
  return <>
    <section className="panel">
      <h3><History size={16}/> Histórico de decisões</h3>
      <p className="hint">Cada vez que a central muda de ideia (começar, parar, esperar), fica registrado com o motivo e os números do estoque naquela hora.</p>
      {ev.dados?.eventos.length?<ul className="rq-lista">{ev.dados.eventos.map(e=><li key={e.n}><small className="muted">{quando(e.t)} · {AGENTE[e.agente]||e.agente}</small> <span className="tag">{ACAO[e.decisao]||e.decisao}</span> {e.motivo}</li>)}</ul>
        :<p className="muted">Nada ainda.</p>}
    </section>
    <section className="panel">
      <h3>Ferramentas detectadas no servidor</h3>
      <p className="hint">{cap.dados?.regra||'O servidor só detecta as ferramentas. Nada é instalado sozinho, e código de fora só entra depois de conferir a licença.'}</p>
      <ul className="rq-lista">{(cap.dados?.capacidades||[]).map(k=><li key={k.id}><b>{k.nome}</b> <span className={'tag '+(k.estado==='disponivel'||k.estado==='instalado'?'ok':'')}>{k.estado}</span> <small className="muted">{k.uso}</small></li>)}</ul>
    </section>
    <section className="panel">
      <h3><Wrench size={16}/> Ferramentas externas (registro)</h3>
      <p className="hint">{fer.dados?.regra}</p>
      {fer.erro&&<p className="hint bad">{fer.erro}</p>}
      <ul className="rq-lista">{(fer.dados?.ferramentas||[]).map(f=><li key={f.id}>
        <b>{f.capacidade}</b> <span className={'tag '+(f.habilitada?'ok':f.status==='nao_adotado'?'bad':'')}>{f.habilitada?'ligada':f.nome_status}</span>
        <br/><small className="muted">{f.repo} · licença: {f.licenca_declarada||'não informada'}{f.licenca_auditada?' (conferida)':' (não conferida)'} · roda em: {f.so} · se não der: {f.fallback}</small>
        {f.limite&&<><br/><small className="bad">{f.limite}</small></>}
        {f.teste_smoke&&<><br/><small className={f.teste_smoke.ok?'muted':'bad'}>Último teste: {f.teste_smoke.ok?'passou':'falhou'} — {f.teste_smoke.detalhe}</small></>}
        <div className="row">
          {f.testavel&&<button className="subtle sm" disabled={!!busy} onClick={()=>fazer(f.id,()=>testarFerramenta(cfg,f.id),r=>(r as {detalhe:string}).detalhe)}>{busy===f.id?<Loader2 size={13} className="spin"/>:<FlaskConical size={13}/>} Testar aqui</button>}
          {f.testavel&&!f.habilitada&&<><label className="check"><input type="checkbox" checked={!!lic[f.id]} onChange={e=>setLic({...lic,[f.id]:e.target.checked})}/> Conferi a licença</label>
            <button className="primary sm" disabled={!!busy||!lic[f.id]} onClick={()=>fazer(f.id,()=>ligarFerramenta(cfg,f.id,true,{licenca_conferida:true}),()=>'Ligada.')}>Ligar</button></>}
          {f.habilitada&&<button className="subtle sm" disabled={!!busy} onClick={()=>fazer(f.id,()=>ligarFerramenta(cfg,f.id,false),()=>'Desligada.')}>Desligar</button>}
        </div>
      </li>)}</ul>
    </section>
  </>;
}

const TIPO_BIB:[ItemBiblioteca['tipo'],string,[string,string][]][]=[
  ['modelo_roteiro','Modelo de roteiro',[['estrutura','Estrutura'],['gancho','Gancho'],['instrucoes','Instruções'],['final','Final']]],
  ['pacote_visual','Pacote visual',[['estilo','Estilo (id do catálogo)'],['formato','Formato (9:16, 16:9, 1:1)'],['imagens','Imagens (nenhuma, gemini ou busca)'],['observacoes','Observações']]],
  ['perfil_narracao','Perfil de narração',[['voz','Voz'],['ritmo','Ritmo (calmo, normal, agil, rapido)'],['emocao','Emoção'],['idioma','Idioma'],['observacoes','Observações']]]];

function Biblioteca(){
  const {toast}=useApp(); const cfg=useCfg();
  const b=useServidor(c=>listarBiblioteca(c),0);
  const [ed,setEd]=useState<{tipo:ItemBiblioteca['tipo'];nome:string;dados:Record<string,string>;travas:string[];id?:string;versao?:number}|null>(null); const [busy,setBusy]=useState(false);
  async function salvar(){ if(!ed) return; setBusy(true);
    try{ if(ed.id) await mudarItemBiblioteca(cfg,ed.id,{versao:ed.versao!,nome:ed.nome,dados:ed.dados,travas:ed.travas}); else await criarItemBiblioteca(cfg,ed);
      toast(ed.id?'Nova versão salva.':'Item criado.','ok'); setEd(null); b.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }
  const campos=ed?TIPO_BIB.find(t=>t[0]===ed.tipo)![2]:[];
  return <section className="panel">
    <h3><BookOpen size={16}/> Biblioteca criativa</h3>
    <p className="hint">Modelos de roteiro, pacotes visuais e perfis de narração que várias linhas podem usar. Cada mudança vira uma versão nova; o cadeado protege o campo de mudanças automáticas. Personagens e cenários continuam em Séries animadas.</p>
    {b.erro&&<p className="hint bad">{b.erro}</p>}
    <ul className="rq-lista">{(b.dados?.itens||[]).map(i=><li key={i.id}><span className="tag">{i.nome_tipo}</span> <b>{i.nome}</b> <small className="muted">v{i.versao} · usado em {i.episodios||0} vídeo(s)</small>
      <span className="row"><button className="subtle sm" onClick={()=>setEd({tipo:i.tipo,nome:i.nome,dados:{...i.dados},travas:[...i.travas],id:i.id,versao:i.versao})}>Editar</button>
        <button className="icon-btn" aria-label="Apagar item" onClick={async()=>{ if(!confirm('Apagar este item? Os vídeos já feitos guardam a versão que usaram.')) return; try{ await apagarItemBiblioteca(cfg,i.id); b.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); } }}><Trash2 size={13}/></button></span></li>)}</ul>
    {!ed&&<div className="row">{TIPO_BIB.map(([t,n])=><button key={t} className="subtle sm" onClick={()=>setEd({tipo:t,nome:'',dados:{},travas:[]})}><Plus size={12}/> {n}</button>)}</div>}
    {ed&&<div>
      <h3>{ed.id?'Editar':'Novo'}: {TIPO_BIB.find(t=>t[0]===ed.tipo)![1]}</h3>
      <label>Nome<input value={ed.nome} onChange={e=>setEd({...ed,nome:e.target.value})}/></label>
      {campos.map(([k,n])=>{ const lk=ed.travas.includes(k); return <label key={k}><span>{n} <button type="button" className={'icon-btn'+(lk?' on':'')} aria-label={'Cadeado '+n} title="Com cadeado, só muda se você tirar o cadeado"
        onClick={()=>setEd({...ed,travas:lk?ed.travas.filter(x=>x!==k):[...ed.travas,k]})}><Lock size={11}/></button></span>
        {k==='estrutura'||k==='instrucoes'||k==='observacoes'?<textarea rows={2} value={ed.dados[k]||''} onChange={e=>setEd({...ed,dados:{...ed.dados,[k]:e.target.value}})}/>
          :<input value={ed.dados[k]||''} onChange={e=>setEd({...ed,dados:{...ed.dados,[k]:e.target.value}})}/>}</label>; })}
      <div className="row"><button className="primary sm" disabled={busy||ed.nome.trim().length<2} onClick={salvar}>Salvar</button><button className="subtle sm" onClick={()=>setEd(null)}>Cancelar</button></div>
    </div>}
  </section>;
}
