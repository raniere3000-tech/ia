import { useState } from 'react';
import { Bot, ArrowRight, AlertTriangle, CalendarClock, Activity, BarChart3, Loader2, MessagesSquare, Film, Sparkles, CalendarDays, Workflow, CheckCircle2 } from 'lucide-react';
import { useApp, type Tab } from '../state';
import { useCfg } from './Servidor2';
import { duracaoTexto, horaTexto } from '../lib/api';
import { AGENTES_INFO, PERIODOS, nd, useResumo, type Periodo, type Resumo } from '../lib/dashboard';
import { ESTADO_REAL } from '../lib/esteira7';
import { SeletorPeriodo, AvisoDados, TrabalhoAtual } from './PainelPartes';

const REDE:Record<string,string>={youtube:'YouTube',instagram:'Instagram',facebook:'Facebook',tiktok:'TikTok',kwai:'Kwai'};
const qtd=(n:number,um:string,varios:string)=>`${n} ${n===1?um:varios}`;

/** Resumo do Coordenador montado SÓ com os números do servidor (sem texto de IA e sem número inventado). */
function resumoTexto(r:Resumo,periodo:string):string{
  const t=r.totais; const partes:string[]=[];
  const trab=r.agentes.filter(a=>a.atual.length);
  partes.push(trab.length?`${qtd(trab.length,'agente está','agentes estão')} trabalhando agora (${trab.map(a=>'Agente '+AGENTES_INFO[a.id]?.n).join(', ')}).`:'Nenhum agente está trabalhando agora.');
  if(t.videos_criados!=null) partes.push(`${qtd(t.videos_criados,'vídeo produzido','vídeos produzidos')} ${periodo}.`);
  if(t.publicados!=null) partes.push(`${qtd(t.publicados,'envio publicado','envios publicados')} ${periodo}.`);
  if(t.esperando_decisao) partes.push(`${qtd(t.esperando_decisao,'item espera','itens esperam')} a sua decisão.`);
  if(r.proxima_publicacao) partes.push(`Próximo post: ${horaTexto(r.proxima_publicacao.quando)}.`);
  else if(t.agendados===0) partes.push('Nada agendado para postar.');
  return partes.join(' ');
}

function Kpi({rotulo,valor,def,ir}:{rotulo:string;valor:number|null|undefined;def?:string;ir?:()=>void}){
  const C=ir?'button':'div';
  return <C className="kpi" onClick={ir} title={def}><b>{nd(valor)}</b><span>{rotulo}</span>{def&&<small>{def}</small>}</C>;
}

/** Início: o que está acontecendo, com números reais do servidor (GET /api/v1/dashboard/resumo). */
export default function PainelInicio(){
  const {go,abrirCoordenador}=useApp(); const cfg=useCfg();
  const [periodo,setPeriodo]=useState<Periodo>('hoje');
  const res=useResumo(cfg,periodo,5);
  const r=res.dados; const t=r?.totais;
  const nomeP=PERIODOS.find(x=>x[0]===periodo)![1].toLowerCase();
  const ir=(x:Tab,extra='',area?:string)=>()=>go(x,extra,area);
  const agora=Date.now()/1000;
  const trab=r?.agentes.filter(a=>a.atual.length)||[];
  const onde:Record<string,()=>void>={agendar:ir('agendar','','publicacoes'),fila:ir('revisar','','agentes'),'agente:esteira':ir('agente','esteira','agentes')};
  return <div className="painel-inicio">
    <section className="panel pi-coord">
      <div className="section-head"><h2><MessagesSquare size={18}/> Resumo do Coordenador</h2>{res.carregando&&<Loader2 size={14} className="spin" aria-label="Atualizando"/>}</div>
      <p aria-live="polite">{r?resumoTexto(r,nomeP==='hoje'?'hoje':`nos últimos ${nomeP}`):res.erro?'Sem resposta do servidor: nada a resumir agora.':'Lendo o servidor...'}</p>
      <div className="row-gap left"><button className="primary sm" onClick={abrirCoordenador}><MessagesSquare size={14}/> Falar com o Coordenador</button><button className="subtle sm" onClick={ir('coordenador','conversar','agentes')}>Abrir Coordenador <ArrowRight size={13}/></button></div>
    </section>
    <AvisoDados r={r} erro={res.erro} antigo={res.antigo}/>
    <section className="panel">
      <div className="section-head"><h2><BarChart3 size={18}/> Produção</h2><SeletorPeriodo p={periodo} setP={setPeriodo}/></div>
      {r?.parcial&&<p className="hint">O servidor ainda não tem o painel novo: atualize-o (git pull no Termux) para ver os números.</p>}
      <div className="kpis">
        <Kpi rotulo={`vídeos produzidos (${nomeP})`} valor={t?.videos_criados} def={r?.definicoes.videos_criados} ir={ir('projetos','','estudio-ia')}/>
        <Kpi rotulo="aprovados pelo diretor, sem post" valor={t?.aprovados_disponiveis} def={r?.definicoes.aprovados_disponiveis||'Só com a esteira ligada'} ir={ir('agente','esteira','agentes')}/>
        <Kpi rotulo="envios agendados (agora)" valor={t?.agendados} def={r?.definicoes.agendados} ir={ir('agendar','','publicacoes')}/>
        <Kpi rotulo={`envios publicados (${nomeP})`} valor={t?.publicados} def={r?.definicoes.publicados} ir={ir('agendar','','publicacoes')}/>
        <Kpi rotulo="tarefas em produção (agora)" valor={t?.em_producao} def={r?.definicoes.em_producao} ir={ir('fila','','agentes')}/>
        <Kpi rotulo="esperando sua decisão" valor={t?.esperando_decisao} def={r?.definicoes.esperando_decisao} ir={ir('revisar','','agentes')}/>
        <Kpi rotulo={`falhas (${nomeP})`} valor={t?.falhas} def={r?.definicoes.falhas} ir={ir('fila','','agentes')}/>
      </div>
      {r&&Object.keys(r.definicoes).length>0&&<details className="kpi-defs"><summary>Como cada número é contado</summary><ul className="plain muted">{Object.entries(r.definicoes).map(([k,v])=><li key={k}>{v}</li>)}</ul></details>}
    </section>
    <div className="two-cols even">
      <section className="panel">
        <div className="section-head"><h2><Activity size={18}/> Quem está trabalhando agora</h2><button className="link-btn" onClick={ir('agentes','','agentes')}>Agentes <ArrowRight size={13}/></button></div>
        {!r?<p className="hint">{res.erro?'Não disponível sem o servidor.':'Lendo...'}</p>:!trab.length?<p className="hint">Nenhum agente trabalhando agora.</p>:
          <div className="pi-trab">{trab.map(a=><div key={a.id} className="pi-trab-item"><b>Agente {AGENTES_INFO[a.id]?.n} · {AGENTES_INFO[a.id]?.nome}</b><TrabalhoAtual a={a} agora={agora}/>{(a.na_fila||0)>0&&<small className="muted">{a.na_fila} esperando a vez</small>}</div>)}</div>}
      </section>
      <section className="panel">
        <div className="section-head"><h2><CalendarClock size={18}/> Próxima publicação</h2><button className="link-btn" onClick={ir('agendar','','publicacoes')}>Calendário <ArrowRight size={13}/></button></div>
        {!r?<p className="hint">{res.erro?'Não disponível sem o servidor.':'Lendo...'}</p>:r.proxima_publicacao?<div className="pi-prox">
          <b>{r.proxima_publicacao.titulo||'Sem título'}</b>
          <span>{horaTexto(r.proxima_publicacao.quando)}</span>
          <span className="row-gap left">{r.proxima_publicacao.redes.map(x=><span key={x} className="tag info">{REDE[x]||x}: agendado</span>)}</span>
          <small className="muted">Agendado ainda não é publicado: o Agente 2 posta no horário, se o vídeo continuar liberado.</small>
        </div>:<p className="hint">{r.totais.agendados==null?'Não disponível.':'Nada agendado.'}</p>}
      </section>
    </div>
    <section className="panel">
      <div className="section-head"><h2><Bot size={18}/> Os 7 agentes agora</h2><button className="link-btn" onClick={ir('coordenador','esteira','agentes')}>Esteira <ArrowRight size={13}/></button></div>
      {!r?<p className="hint">{res.erro?'Não disponível sem o servidor.':'Lendo...'}</p>:<div className="pi-estados" role="list">{r.agentes.map(a=>{ const info=AGENTES_INFO[a.id];
        const [nome,cor]=a.estado_real?(ESTADO_REAL[a.estado_real]||[a.estado_real_nome||a.estado_real,'']):['Não disponível',''];
        return <div key={a.id} className="pi-estado" role="listitem"><b>{info?`${info.n} · ${info.nome}`:a.id}</b><span className={'tag '+cor}>{nome}</span>
          {a.esteira_agora?.[0]&&<small>{a.esteira_agora[0].etapa}: {a.esteira_agora[0].titulo}</small>}
          {!a.esteira_agora?.length&&a.atual[0]?.etapa&&<small>{a.atual[0].etapa}</small>}
          {a.motivo&&a.estado_real!=='ativo'&&<small className="muted">{a.motivo.slice(0,140)}</small>}
        </div>; })}</div>}
      {r?.esteira7&&<p className="hint">Esteira: {Object.entries(r.esteira7.por_etapa).length?Object.entries(r.esteira7.por_etapa).map(([k,n])=>`${n} em ${r.esteira7!.nomes_etapa[k]||k}`).join(' · '):'nenhum vídeo em andamento'}
        {r.esteira7.por_estado.publicado?` · ${r.esteira7.por_estado.publicado} publicado(s) pela esteira`:''}{r.esteira7.politica.completa?'':' · esteira completa DESLIGADA'}</p>}
    </section>
    <section className="panel">
      <div className="section-head"><h2><Bot size={18}/> Produção por agente ({nomeP})</h2></div>
      {!r?<p className="hint">{res.erro?'Não disponível sem o servidor.':'Lendo...'}</p>:<div className="pi-agentes" role="list">{r.agentes.map(a=>{ const info=AGENTES_INFO[a.id];
        return <div key={a.id} className="pi-ag" role="listitem"><b>{info?`${info.n} · ${info.nome}`:a.id}</b>
          <span><em>{nd(a.concluidas_periodo)}</em> {a.id==='agente2'?'posts':a.id==='agente7'?'pedidos':'concluídas'}</span>
          <span><em>{a.atual.length||(a.id==='agente7'?nd(a.ordens_ativas):0)}</em> em andamento</span>
          <span><em>{nd(a.falhas_periodo)}</em> {a.id==='agente2'?'com erro':'falhas'}</span>
          {a.id!=='agente2'&&a.id!=='agente7'&&<span><em>{nd(a.tempo_ativo_s,duracaoTexto)}</em> medido</span>}
          {a.esteira_periodo&&<span title="Etapas da esteira concluídas com prova (recibo) no período"><em>{a.esteira_periodo.concluidas}</em> etapas com prova{a.esteira_periodo.tempo_medio_s!=null?` · média ${duracaoTexto(a.esteira_periodo.tempo_medio_s)}`:''}</span>}
        </div>; })}</div>}
    </section>
    {r&&<section className="panel">
      <div className="section-head"><h2><AlertTriangle size={18}/> Atenção necessária</h2></div>
      {!r.alertas.length?<p className="hint"><CheckCircle2 size={14}/> Nada pedindo atenção.</p>:
        <ul className="pi-alertas">{r.alertas.map(x=><li key={x.tipo}><AlertTriangle size={14}/> <span className="grow">{x.texto}</span>{onde[x.onde]&&<button className="subtle sm" onClick={onde[x.onde]}>Ver</button>}</li>)}</ul>}
    </section>}
    <div className="pi-rapidas">
      <button className="subtle" onClick={ir('agentes','','agentes')}><Bot size={15}/> Ir para Agentes</button>
      <button className="subtle" onClick={ir('manual','','edicao')}><Film size={15}/> Criar vídeo manual</button>
      <button className="subtle" onClick={ir('ia','','estudio-ia')}><Sparkles size={15}/> Criar com IA</button>
      <button className="subtle" onClick={ir('agendar','','publicacoes')}><CalendarDays size={15}/> Ver calendário</button>
      <button className="subtle" onClick={ir('central','geral','agentes')}><Workflow size={15}/> Central de Automação</button>
    </div>
  </div>;
}
