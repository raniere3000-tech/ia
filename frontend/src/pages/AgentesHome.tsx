import { useState } from 'react';
import { Scissors, Send, Bot, Gauge, Clapperboard, Image as ImgIcon, MessagesSquare, Loader2, AlertTriangle, ArrowRight, Settings2, Activity, Clock } from 'lucide-react';
import { useApp } from '../state';
import { useCfg, useServidor, PrecisaServidor } from '../components/Servidor2';
import { useVisaoAgente } from '../components/PainelAgentes';
import { lerCfgThumb } from '../lib/thumbnails';
import { duracaoTexto } from '../lib/api';
import { AGENTES_INFO, ESTADO_AGENTE, PERIODOS, nd, useResumo, type AgenteResumo, type Periodo } from '../lib/dashboard';
import { MediaDuracao, TrabalhoAtual, SeletorPeriodo, AvisoDados } from '../components/PainelPartes';
import type { Tab } from '../state';

const ICONES:Record<string,typeof Bot>={agente1:Scissors,agente2:Send,agente3:Bot,agente4:Gauge,agente5:Clapperboard,agente6:ImgIcon,agente7:MessagesSquare};
type Ir=[Tab,string,string?];
/** Para onde cada botão leva (telas que já existem; nada novo é ligado por aqui). */
const DESTINO:Record<string,{abrir:Ir;configurar:Ir;atividade:Ir}>={
  agente1:{abrir:['agente','fila'],configurar:['agente','cortes'],atividade:['fila','']},
  agente2:{abrir:['agendar','','publicacoes'],configurar:['agente','postagem'],atividade:['agendar','','publicacoes']},
  agente3:{abrir:['ia','','estudio-ia'],configurar:['agente','agente3'],atividade:['fila','']},
  agente4:{abrir:['agente','esteira'],configurar:['agente','esteira'],atividade:['central','qualidade']},
  agente5:{abrir:['agente','esteira'],configurar:['agente','esteira'],atividade:['fila','']},
  agente6:{abrir:['thumbnails','fila'],configurar:['thumbnails','autonomia'],atividade:['thumbnails','desempenho']},
  agente7:{abrir:['coordenador','conversar'],configurar:['coordenador','config'],atividade:['coordenador','ordens']},
};

function Cartao({a,ligado,periodo,parcial}:{a:AgenteResumo;ligado:{txt:string;cls:string}|null;periodo:string;parcial?:boolean}){
  const {go}=useApp();
  const info=AGENTES_INFO[a.id]; const I=ICONES[a.id]||Bot; const d=DESTINO[a.id];
  const agora=Date.now()/1000;
  const [est,cls]=a.estado?ESTADO_AGENTE[a.estado]||[a.estado,'']:['Não disponível',''];
  const ir=(x:Ir)=>go(x[0],x[1],x[2]||'agentes');
  const ehA7=a.id==='agente7';
  return <article className={'agente-card'+(a.estado==='trabalhando'||a.estado==='coordenando'?' ocupado':'')} aria-labelledby={'ac-'+a.id}>
    <header className="ac-topo">
      <span className="ac-icone"><I size={18}/></span>
      <div className="grow"><h3 id={'ac-'+a.id}>Agente {info.n} · {info.nome}</h3><small className="muted">{info.funcao}</small></div>
    </header>
    <div className="ac-tags">
      {a.id!=='agente2'&&<span className={'tag '+cls}>{est}</span>}
      {ligado&&<span className={'tag '+ligado.cls}>{ligado.txt}</span>}
    </div>
    <TrabalhoAtual a={a} agora={agora}/>
    {!a.atual.length&&!ehA7&&<p className="ac-atual muted">{a.estado==='na_fila'?'Trabalhos esperando a vez':'Nenhum trabalho rodando agora'}</p>}
    {ehA7?<div className="ac-nums">
      <span><b>{nd(a.ordens_ativas)}</b>pedidos em andamento</span>
      <span><b>{nd(a.esperando_voce)}</b>esperando você liberar</span>
      <span><b>{nd(a.concluidas_periodo)}</b>pedidos concluídos ({periodo})</span>
      <span><b>{a.modo==='automatico'?'Automático':a.modo==='supervisionado'?'Supervisionado':nd(null)}</b>modo</span>
    </div>:<div className="ac-nums">
      <span><b>{nd(a.concluidas_periodo)}</b>{a.unidade==='posts por rede'?'posts feitos':'concluídas'} ({periodo})</span>
      <span><b>{nd(a.falhas_periodo)}</b>{a.unidade==='posts por rede'?'posts com erro (agora)':'falhas'}</span>
      {a.id!=='agente2'&&<span><b>{nd(a.na_fila)}</b>na fila</span>}
      {a.id!=='agente2'&&<span title="Soma do tempo medido rodando (sem a espera)"><b>{nd(a.tempo_ativo_s,duracaoTexto)}</b>tempo trabalhado</span>}
      <MediaDuracao t={a.tempos_medios}/>
    </div>}
    {parcial&&<p className="hint">Contagens por período aparecem depois de atualizar o servidor.</p>}
    <div className="ac-acoes">
      {ehA7?<button className="primary sm" onClick={()=>ir(d.abrir)}><MessagesSquare size={14}/> Conversar</button>:<button className="primary sm" onClick={()=>ir(d.abrir)}>Abrir <ArrowRight size={13}/></button>}
      <button className="subtle sm" onClick={()=>ir(d.configurar)}><Settings2 size={14}/> Configurar</button>
      <button className="subtle sm" onClick={()=>ir(d.atividade)}><Activity size={14}/> Ver atividade</button>
    </div>
  </article>;
}

/** Área Agentes, MODELO B: o painel dos sete agentes abre primeiro. */
export default function AgentesHome(){
  const {settings,go}=useApp(); const cfg=useCfg();
  const [periodo,setPeriodo]=useState<Periodo>('7d');
  const res=useResumo(cfg,periodo,20);
  const {v}=useVisaoAgente();
  const thumb=useServidor(c=>lerCfgThumb(c).catch(()=>null),60);
  if(!settings.servidor) return <PrecisaServidor oque="A Central de Agentes"/>;
  const r=res.dados;
  const nomeP=PERIODOS.find(x=>x[0]===periodo)![1].toLowerCase();
  const esteira=r?.esteira_ligada;
  const ligado=(id:string):{txt:string;cls:string}|null=>{
    if(id==='agente1'&&v) return v.config.cortes.ligado?{txt:'Ligado',cls:'ok'}:{txt:'Desligado',cls:''};
    if(id==='agente2'&&v) return v.config.postagem.ligado?{txt:'Ligado',cls:'ok'}:{txt:'Desligado',cls:''};
    if(id==='agente3') return {txt:'Disponível',cls:''};
    if((id==='agente4'||id==='agente5')&&esteira!=null) return esteira?{txt:'Esteira ligada',cls:'ok'}:{txt:'Esteira desligada',cls:''};
    if(id==='agente6'&&thumb.dados) return {txt:thumb.dados.criar_sozinho?'Cria sozinho':'Só quando pedir',cls:thumb.dados.criar_sozinho?'ok':''};
    return null;
  };
  const trabalhando=r?.agentes.filter(a=>a.atual.length).length??0;
  return <div className="agentes-home">
    <section className="panel ah-topo">
      <h2 className="sr-only">Situação geral</h2>{res.carregando&&<Loader2 size={14} className="spin ah-carregando" aria-label="Atualizando"/>}
      <div className="ah-status" aria-live="polite">
        {r?<span className={'tag '+(trabalhando?'info':'')}>{trabalhando?`${trabalhando} agente(s) trabalhando agora`:'Nenhum agente trabalhando agora'}</span>:null}
        {r&&<span className="tag">{r.totais.esperando_decisao!=null?`${r.totais.esperando_decisao} esperando você`:'Decisões: não disponível'}</span>}
        <button className="link-btn" onClick={()=>go('central','geral','agentes')}>Automação <ArrowRight size={13}/></button>
        <button className="link-btn" onClick={()=>go('coordenador','conversar','agentes')}>Coordenador <ArrowRight size={13}/></button>
      </div>
      <SeletorPeriodo p={periodo} setP={setPeriodo}/>
    </section>
    <AvisoDados r={r} erro={res.erro} antigo={res.antigo}/>
    {!r&&!res.erro&&<p className="hint"><Loader2 size={14} className="spin"/> Lendo os agentes no servidor...</p>}
    {r&&<div className="agentes-grade">{['agente1','agente2','agente3','agente4','agente5','agente6','agente7'].map(id=>{
      const a=r.agentes.find(x=>x.id===id)||{id,estado:null,atual:[],na_fila:null,concluidas_periodo:null,falhas_periodo:null,tempo_ativo_s:null,tempos_medios:{}};
      return <Cartao key={id} a={a} ligado={ligado(id)} periodo={nomeP} parcial={r.parcial}/>; })}</div>}
    {r&&<p className="hint"><Clock size={13}/> Números do servidor às {new Date(r.gerado_em*1000).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}. "Não disponível" = o servidor ainda não mede isso. Tempo trabalhado não conta a espera na fila.</p>}
    {r&&r.alertas.length>0&&<section className="panel"><div className="section-head"><h2><AlertTriangle size={17}/> Atenção</h2></div>
      <ul className="plain">{r.alertas.map(x=><li key={x.tipo}>{x.texto}</li>)}</ul></section>}
  </div>;
}
