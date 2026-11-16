import { useState } from 'react';
import { CheckCircle2, XCircle, Pencil, Loader2, AlertTriangle, Mail, ArrowLeft, Lock, Film, ShieldCheck, Clock, RotateCcw } from 'lucide-react';
import { useApp } from '../state';
import { HelpButton } from '../components/Help';
import { useCfg, useServidor, PrecisaServidor, erroTexto } from '../components/Servidor2';
import { Etapas } from '../components/Prontidao';
import { lerRevisao, aprovar, pedirCorrecao, refazerCena, rejeitar, aprovarRoteiro, reenviarEmail, urlServidor, duracaoTexto, horaTexto, type Render, type Cena, type Briefing, type Qualidade } from '../lib/api';

const REDES:[string,string][]=[['youtube','YouTube'],['instagram','Instagram'],['facebook','Facebook'],['tiktok','TikTok'],['kwai','Kwai (manual)']];
const DECISAO:Record<string,string>={aprovado:'Aprovado',alterar:'Correção pedida',rejeitado:'Rejeitado'};

const ST_Q:Record<Qualidade['status'],[string,string,string]>={
  apto_para_revisao_humana:['Tudo certo','ok','Nenhum problema encontrado. Falta só você assistir e decidir.'],
  alerta_visual:['Vale olhar','warn','O vídeo está pronto, mas o diretor de qualidade achou pontos para você conferir. Nada disso bloqueia a aprovação.'],
  analise_indisponivel:['Não conferido','','Não deu para analisar os quadros desta vez.'],
  falha_tecnica:['Falha técnica','bad','O arquivo final tem um problema técnico.'],
};
const NOME_T:Record<string,string>={quadro_escuro:'Quadro escuro',sem_detalhe:'Imagem sem detalhe',plano_repetido:'Plano repetido',sem_imagem:'Cena sem foto',ritmo:'Ritmo',analise_indisponivel:'Sem análise'};
/** Relatório do diretor de qualidade: cada ponto com a cena, o instante (toque para pular até ele) e a sugestão. */
function QualidadePainel({q,cenas}:{q:Qualidade;cenas:Cena[]}){
  const [s,cls,txt]=ST_Q[q.status]||ST_Q.analise_indisponivel;
  const pular=(tc:string|null)=>{ if(!tc) return; const [m,ss]=tc.split(':'); const v=document.querySelector<HTMLVideoElement>('.rev-video video'); if(v){ v.currentTime=(+m)*60+(+ss); v.play().catch(()=>{}); v.scrollIntoView({behavior:'smooth',block:'center'}); } };
  const nCena=(id:string)=>{ const i=cenas.findIndex(c=>c.id===id); return i>=0?`Cena ${i+1}`:''; };
  return <section className="panel qualidade">
    <div className="section-head"><h2><ShieldCheck size={18}/> Diretor de qualidade <span className={'tag '+cls}>{s}</span></h2></div>
    <p className="subtitle">{txt}</p>
    {q.problemas.length>0&&<ul className="qd-lista">{q.problemas.map((p,k)=><li key={k} className={'qd-'+p.severidade}>
      <div><b>{NOME_T[p.tipo]||p.tipo}</b>{p.cena_id&&<span className="muted"> · {nCena(p.cena_id)}</span>}{p.timecode&&<button className="link-btn" onClick={()=>pular(p.timecode)}><Clock size={12}/> {p.timecode.replace(/^00:/,'').replace(/\.\d+$/,'')} s</button>}</div>
      <p>{p.descricao}</p>{p.correcao&&<small className="muted">Sugestão: {p.correcao}</small>}</li>)}</ul>}
    {q.tecnico.erros.length>0&&<p className="hint bad">{q.tecnico.erros.join(' ')}</p>}
  </section>;
}

export default function Revisar(){
  const {settings,rotaExtra,toast,go}=useApp(); const cfg=useCfg();
  const pid=rotaExtra;
  const rev=useServidor(c=>lerRevisao(c,pid),8,[pid]);
  const [texto,setTexto]=useState('');
  const [busy,setBusy]=useState('');
  const [redes,setRedes]=useState<string[]|null>(null);
  const [quando,setQuando]=useState<'proximo'|'agora'|'data'>('proximo');
  const [data,setData]=useState('');
  const [refazer,setRefazer]=useState<{i:number;imagem:boolean;voz:boolean}|null>(null);
  if(!settings.servidor) return <PrecisaServidor oque="A revisão"/>;
  if(!pid) return <section className="panel empty-state"><h2>Nenhum vídeo escolhido</h2><button className="primary" onClick={()=>go('fila')}>Abrir Fila e aprovações</button></section>;
  const r=rev.dados;
  if(!r) return <section className="panel">{rev.erro?<p className="hint bad">{rev.erro}</p>:<p className="hint"><Loader2 size={14} className="spin"/> Abrindo...</p>}</section>;
  const p=r.projeto; const d=p.dados as {briefing:Briefing;cenas:Cena[];render:Render|null;roteiro:{titulo:string;legenda:string;hashtags:string[];fontes:{titulo:string;url:string}[]}|null;producao?:{erro?:string};qualidade?:Qualidade};
  const render=d.render; const b=d.briefing;
  const destinos=redes??(b?.destinos?.redes||[]);
  const fazer=async(nome:string,f:()=>Promise<unknown>,ok:string)=>{ setBusy(nome); try{ await f(); toast(ok,'ok'); setTexto(''); rev.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } };
  const esperandoVideo=p.status==='ready_for_review';
  const esperandoRoteiro=p.status==='waiting_brief_approval'||(p.status==='storyboard_ready'&&!render);
  const st=r.estados[p.status]||p.status;
  return <div className="revisar">
   <button className="link-btn" onClick={()=>go('fila')}><ArrowLeft size={14}/> Fila e aprovações</button>
   <section className="panel">
    <div className="section-head"><h2>{p.titulo} <span className="tag">{r.ref}</span> <span className={'tag '+(esperandoVideo?'warn':p.status==='failed'?'bad':['approved','queued_to_publish','posted'].includes(p.status)?'ok':'')}>{st}</span> <HelpButton topic="aprovacao"/></h2></div>
    {!['failed','cancelled','paused'].includes(p.status)&&<Etapas status={p.status} detalhe={r.job&&!['concluido','cancelado'].includes(r.job.status)?(p.status==='waiting_brief_approval'?'Esperando você aprovar':r.job.status==='rodando'?`${r.job.etapa} • ${Math.round(r.job.progresso)}%`:r.job.etapa):undefined}/>}
    {!render&&!esperandoRoteiro&&!['failed','cancelled','rejected'].includes(p.status)&&<p className="hint">O celular está trabalhando. Pode fechar esta tela: quando o vídeo ficar pronto ele aparece aqui e em Fila e aprovações{' '}(e chega um e-mail, se estiver configurado).</p>}
    {p.status==='failed'&&<div className="row-gap left"><button className="primary sm" onClick={()=>go('fila')}>Abrir a fila para tentar de novo</button></div>}
    {d.producao?.erro&&p.status==='failed'&&<p className="hint bad"><AlertTriangle size={14}/> {d.producao.erro}</p>}
    {render&&<div className="rev-video">
     {r.links.video?<video src={urlServidor(cfg,r.links.preview||r.links.video)} controls playsInline preload="metadata" poster={r.links.thumb?urlServidor(cfg,r.links.thumb):undefined} className={render.altura>render.largura?'vertical':''}/>:<p className="hint">Prévia indisponível.</p>}
     <div className="rev-info">
      <p><b>Versão {render.versao}</b> • {Math.round(render.duracao)} s • {render.largura}x{render.altura} • {render.codec} • {(render.tamanho/1048576).toFixed(1)} MB</p>
      <p className="hint">Conferido automaticamente: abre, tem imagem e som, tamanho e duração certos, quadros do começo, meio e fim.</p>
      {render.avisos.length>0&&<ul className="avisos">{render.avisos.map(a=><li key={a}><AlertTriangle size={13}/> {a}</li>)}</ul>}
            {r.links.video&&<a className="subtle sm" href={urlServidor(cfg,r.links.video)+'&baixar=1'} download><Film size={14}/> Baixar o vídeo final</a>}
     </div>
    </div>}
   </section>

   {render&&d.qualidade&&<QualidadePainel q={d.qualidade} cenas={d.cenas||[]}/>}

   {esperandoVideo&&render&&<section className="panel decisao">
    <div className="section-head"><h2>Sua decisão</h2></div>
    <p className="subtitle">Assista ao vídeo acima. Gostou? Toque em Aprovar. Quer mudar algo? Escreva o que mudar e toque em Pedir correção. Nada é publicado antes de você aprovar.</p>
    <div className="field-label">Publicar em</div>
    <div className="chips">{REDES.map(([id,nome])=><button key={id} className={'chip '+(destinos.includes(id)?'on':'')} onClick={()=>setRedes(destinos.includes(id)?destinos.filter(x=>x!==id):[...destinos,id])}>{nome}</button>)}</div>
    {r.contas.faltam.length>0&&redes===null&&<p className="hint warn">Falta conectar: {r.contas.faltam.join(', ')}. Conecte em Publicações ou tire da lista.</p>}
    <div className="row-gap left mt">
     <label className="check"><input type="radio" checked={quando==='proximo'} onChange={()=>setQuando('proximo')}/> Próximo horário livre</label>
     <label className="check"><input type="radio" checked={quando==='agora'} onChange={()=>setQuando('agora')}/> Agora</label>
     <label className="check"><input type="radio" checked={quando==='data'} onChange={()=>setQuando('data')}/> Data e hora</label>
     {quando==='data'&&<input type="datetime-local" value={data} onChange={e=>setData(e.target.value)}/>}
    </div>
    <div className="row-gap left mt">
     <button className="primary" disabled={!!busy||(quando==='data'&&!data)} onClick={()=>fazer('ok',()=>aprovar(cfg,pid,render.sha,{redes:destinos,quando,data:quando==='data'?new Date(data).getTime()/1000:undefined}),destinos.length?'Aprovado e entregue ao Agente 2.':'Aprovado. Sem rede escolhida: o vídeo fica salvo.')}>
      {busy==='ok'?<Loader2 size={15} className="spin"/>:<CheckCircle2 size={15}/>} Aprovar{destinos.length?' e agendar':''}</button>
     <button className="subtle" disabled={!!busy} onClick={()=>fazer('mail',()=>reenviarEmail(cfg,pid),'E-mail com código novo enviado (o anterior deixou de valer).')}><Mail size={15}/> Reenviar e-mail</button>
    </div>
    <label className="mt">O que precisa mudar? (a IA muda só isso; cenas bloqueadas ficam iguais)<textarea rows={3} value={texto} onChange={e=>setTexto(e.target.value)} placeholder="Ex.: deixe a cena 2 mais curta e troque o destaque da cena 4 por 'Fato real'"/></label>
    <div className="row-gap left">
     <button className="subtle" disabled={!!busy||texto.trim().length<3} onClick={()=>fazer('alt',()=>pedirCorrecao(cfg,pid,render.sha,texto),'Correção pedida. O vídeo vai ser refeito e chega um novo e-mail.')}><Pencil size={15}/> Pedir correção</button>
     <button className="subtle danger" disabled={!!busy} onClick={()=>{ if(window.confirm('Rejeitar este vídeo? Nada será publicado.')) fazer('rej',()=>rejeitar(cfg,pid,render.sha,texto),'Vídeo rejeitado.'); }}><XCircle size={15}/> Rejeitar</button>
    </div>
   </section>}

   {esperandoRoteiro&&<section className="panel decisao">
    <div className="section-head"><h2>Aprovar o roteiro <HelpButton topic="storyboard"/></h2></div>
    <p className="subtitle">Leia as cenas abaixo. Se estiver bom, toque em Aprovar e o celular começa a fazer o vídeo. Se quiser mexer, edite as cenas ou peça uma correção.</p>
    <div className="row-gap left">
     <button className="primary" disabled={!!busy} onClick={()=>fazer('rot',()=>aprovarRoteiro(cfg,pid,p.revisao),'Roteiro aprovado. A produção continua no servidor.')}><CheckCircle2 size={15}/> Aprovar e fazer o vídeo</button>
     <button className="subtle" onClick={()=>go('ia',pid,'criar')}><Pencil size={15}/> Editar as cenas</button>
    </div>
    <label className="mt">Ou peça uma correção para a IA<textarea rows={2} value={texto} onChange={e=>setTexto(e.target.value)}/></label>
    <button className="subtle" disabled={!!busy||texto.trim().length<3} onClick={()=>fazer('alt',()=>pedirCorrecao(cfg,pid,'',texto),'Correção pedida. Você recebe o roteiro novo para aprovar.')}><Pencil size={15}/> Pedir correção do roteiro</button>
   </section>}

   <section className="panel">
    <div className="section-head"><h2>Roteiro ({d.cenas?.length||0} cenas)</h2></div>
    {d.roteiro?.legenda&&<p><b>Legenda:</b> {d.roteiro.legenda} <span className="muted">{d.roteiro.hashtags?.join(' ')}</span></p>}
    <ol className="cenas-lista">{(d.cenas||[]).map((c,i)=><li key={c.id}><b>{c.titulo}</b>{c.bloqueada&&<Lock size={12}/>} {c.destaque&&<span className="tag">{c.destaque}</span>}<p>{c.texto}</p>{c.clipe?.dur?<small className="muted">{c.clipe.dur.toFixed(1)} s</small>:null}
      {esperandoVideo&&render&&(refazer?.i===i?<div className="refazer-box">
        <p className="hint">O celular faz de novo só esta cena; as outras ficam iguais. Depois o vídeo volta para você aprovar.</p>
        <label className="check"><input type="checkbox" checked={refazer.imagem} onChange={e=>setRefazer({...refazer,imagem:e.target.checked})}/> Trocar a foto ou imagem</label>
        <label className="check"><input type="checkbox" checked={refazer.voz} onChange={e=>setRefazer({...refazer,voz:e.target.checked})}/> Gravar a narração de novo</label>
        <div className="row-gap left"><button className="primary sm" disabled={!!busy} onClick={()=>fazer('cena',async()=>{ await refazerCena(cfg,pid,i,refazer); setRefazer(null); },`Refazendo a cena ${i+1}.`)}>{busy==='cena'?<Loader2 size={14} className="spin"/>:<RotateCcw size={14}/>} Refazer a cena {i+1}</button>
         <button className="link-btn" onClick={()=>setRefazer(null)}>Cancelar</button></div>
       </div>:<button className="link-btn" onClick={()=>setRefazer({i,imagem:false,voz:false})}><RotateCcw size={12}/> Refazer só esta cena</button>)}</li>)}</ol>
    {d.roteiro?.fontes?.length?<><div className="field-label">Fontes para conferir</div><ul>{d.roteiro.fontes.map(f=><li key={f.url}><a className="help-link" href={f.url} target="_blank" rel="noreferrer">{f.titulo||f.url}</a></li>)}</ul></>:null}
    <p className="hint">Estilo: {b?.estilo} • formato {b?.formato} • voz {b?.voz} • modo {b?.modo_aprovacao==='assistido'?'assistido':'supervisionado'}</p>
   </section>

   {r.historico.length>0&&<section className="panel">
    <div className="section-head"><h2>Histórico de decisões</h2></div>
    <ul className="historico">{r.historico.map(h=><li key={h.id}><b>{DECISAO[h.decisao]||h.decisao}</b> • {horaTexto(h.criado)} • {h.origem==='email'?'por e-mail':'pelo site'} ({h.por}){h.texto&&<> • “{h.texto}”</>}</li>)}</ul>
   </section>}
   {r.job&&<p className="hint">Trabalho: {r.job.status} • decorrido {duracaoTexto(r.job.decorrido)}</p>}
  </div>;
}
