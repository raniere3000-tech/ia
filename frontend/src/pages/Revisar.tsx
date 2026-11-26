import { useEffect, useState } from 'react';
import { CheckCircle2, XCircle, Pencil, Loader2, AlertTriangle, Mail, ArrowLeft, Lock, Film, ShieldCheck, Clock, RotateCcw, Eye } from 'lucide-react';
import { useApp } from '../state';
import { HelpButton } from '../components/Help';
import { useCfg, useServidor, PrecisaServidor, erroTexto } from '../components/Servidor2';
import { Etapas } from '../components/Prontidao';
import { lerAprovacoes } from '../lib/coordenador';
import { lerEsteira } from '../lib/esteira';
import { pendentes, lerRevisao, aprovar, pedirCorrecao, refazerCena, rejeitar, aprovarRoteiro, reenviarEmail, lerDescricao, salvarDescricao, type Descricao, urlServidor, duracaoTexto, horaTexto, type Render, type Cena, type Briefing, type Qualidade, type Problema, type QuadroVersao, type Correcao, quadrosRender } from '../lib/api';

const REDES:[string,string][]=[['youtube','YouTube'],['instagram','Instagram'],['facebook','Facebook'],['tiktok','TikTok'],['kwai','Kwai (manual)']];
const DECISAO:Record<string,string>={aprovado:'Aprovado',alterar:'Correção pedida',rejeitado:'Rejeitado'};

const ST_Q:Record<Qualidade['status'],[string,string,string]>={
  apto_para_revisao_humana:['Tudo certo','ok','Nenhum problema encontrado. Falta só você assistir e decidir.'],
  alerta_visual:['Apontamentos','warn','Confira abaixo as cenas e as correções indicadas pelo diretor.'],
  analise_indisponivel:['Não conferido','','Não deu para analisar os quadros desta vez.'],
  falha_tecnica:['Falha técnica','bad','O arquivo final tem um problema técnico.'],
};
const NOME_T:Record<string,string>={quadro_escuro:'Quadro escuro',sem_detalhe:'Imagem sem detalhe',plano_repetido:'Plano repetido',sem_imagem:'Cena sem foto',ritmo:'Ritmo',analise_indisponivel:'Sem análise',narrativa:'Roteiro',continuidade:'Continuidade da série',sai_do_quadro:'Sai do quadro',cabeca_cortada:'Cabeça cortada',sobreposicao:'Um esconde o outro',boca_parada:'Boca parada',visual_ia:'Opinião da IA'};
const SEV:Record<string,[string,string]>={alta:['grave','bad'],media:['médio','warn'],baixa:['leve','']};
const segDe=(tc:string|null)=>{ if(!tc) return null; const [m,ss]=tc.split(':'); return (+m)*60+(+ss); };
/** Em que categoria o apontamento cai: técnico que bloqueia, alerta visual, sem análise ou já com você (revisão humana). */
const categoria=(p:Problema)=>p.tipo==='analise_indisponivel'?['análise indisponível','']:p.status==='revisao_humana'?['revisão humana','warn']:['alerta visual','warn'];
const confianca=(p:Problema)=>{ const m=/confian[çc]a\s*([\d.,]+)/i.exec(p.evidencia||''); return p.natureza==='julgamento'?`opinião da IA${m?`, confiança ${Math.round(parseFloat(m[1].replace(',','.'))*100)}%`:''}`:'medido no vídeo (certeza alta)'; };

/** Quadros reais de uma ou mais versões do vídeo no mesmo instante. */
function Quadros({pid,t,renders}:{pid:string;t:number;renders:{id:string;versao:number}[]}){
  const cfg=useCfg(); const [q,setQ]=useState<Record<string,QuadroVersao>|null>(null); const [erro,setErro]=useState('');
  useEffect(()=>{ setQ(null); quadrosRender(cfg,pid,t,renders.map(r=>r.id)).then(r=>setQ(r.quadros)).catch(e=>setErro(erroTexto(e))); },[pid,t,renders.map(r=>r.id).join()]); // eslint-disable-line react-hooks/exhaustive-deps
  if(erro) return <p className="hint bad">{erro}</p>;
  if(!q) return <p className="hint"><Loader2 size={13} className="spin"/> Tirando o quadro do vídeo…</p>;
  return <div className="qd-quadros">{renders.map(r=>{ const x=q[r.id]; return <figure key={r.id}>
    {x?.jpg?<img src={x.jpg} alt={`Versão ${r.versao} em ${x.t} s`}/>:<div className="hint">{x?.erro||'Sem quadro.'}</div>}
    <figcaption>Versão {r.versao}{x?.t!=null?` • ${x.t} s`:''}</figcaption></figure>; })}</div>;
}

/** Relatório do diretor de qualidade por cena e plano: instante, tipo, gravidade, confiança, quadro de evidência, tentativas,
 *  versão e "corrigir só esta cena/plano". Corrigir nunca aprova: o vídeo novo volta para você. */
function QualidadePainel({q,cenas,pid,render,renders,correcoes,podeCorrigir,corrigido}:{q:Qualidade;cenas:Cena[];pid:string;render:Render;renders:{id:string;versao:number}[];correcoes:Correcao[];podeCorrigir:boolean;corrigido:()=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const [s,cls,txt]=ST_Q[q.status]||ST_Q.analise_indisponivel;
  const [ver,setVer]=useState<string>(''); const [busy,setBusy]=useState('');
  const pular=(tc:string|null)=>{ const t=segDe(tc); if(t==null) return; const v=document.querySelector<HTMLVideoElement>('.rev-video video'); if(v){ v.currentTime=t; v.play().catch(()=>{}); v.scrollIntoView({behavior:'smooth',block:'center'}); } };
  const idx=(id:string)=>cenas.findIndex(c=>c.id===id);
  const nPlano=(c:Cena|undefined,pl:string)=>{ if(!c||!pl) return ''; const k=(c.planos||[]).findIndex((x,j)=>(x.id||`p${j+1}`)===pl); return k>=0?`plano ${k+1}${c.planos![k].plano?` (${c.planos![k].plano})`:''}`:''; };
  const grupos=[...cenas.map((c,i)=>({chave:c.id,titulo:`Cena ${i+1}: ${c.titulo}`,lista:q.problemas.filter(p=>p.cena_id===c.id)})),
    {chave:'',titulo:'Vídeo inteiro',lista:q.problemas.filter(p=>!p.cena_id||idx(p.cena_id)<0)}].filter(g=>g.lista.length);
  const anterior=[...renders].filter(r=>r.versao<render.versao).sort((a,b)=>b.versao-a.versao)[0];
  const corrigir=async(p:Problema,k:string)=>{ const i=idx(p.cena_id); if(i<0) return; setBusy(k);
    try{ await refazerCena(cfg,pid,i,{imagem:false,voz:false,plano:p.plano_id||undefined,problema:{tipo:p.tipo,cena_id:p.cena_id,plano_id:p.plano_id||'',timecode:p.timecode}});
      toast(`Refazendo só ${p.plano_id?nPlano(cenas[i],p.plano_id):`a cena ${i+1}`}. O vídeo novo volta para você aprovar.`,'ok'); corrigido(); }
    catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } };
  const tec=q.tecnico.erros.length; const hum=q.problemas.filter(p=>p.status==='revisao_humana').length; const ind=q.problemas.filter(p=>p.tipo==='analise_indisponivel').length;
  return <section className="panel qualidade">
    <div className="section-head"><h2><ShieldCheck size={18}/> Diretor de qualidade <span className={'tag '+cls}>{s}</span></h2></div>
    <p className="subtitle">{txt} Relatório da versão {render.versao}.</p>
    <div className="row-gap left qd-resumo">
      <span className={'tag '+(tec?'bad':'ok')}>{tec?`${tec} erro(s) técnico(s) que bloqueiam`:'arquivo técnico ok'}</span>
      <span className="tag warn">{q.problemas.length-hum-ind} alerta(s) visual(is)</span>
      {ind>0&&<span className="tag">{ind} sem análise</span>}
      {hum>0&&<span className="tag warn">{hum} para sua revisão</span>}
    </div>
    {tec>0&&<p className="hint bad">{q.tecnico.erros.join(' ')}</p>}
    {grupos.map(g=><div key={g.chave||'tudo'} className="qd-grupo"><div className="field-label">{g.titulo}</div>
     <ul className="qd-lista">{g.lista.map((p,k)=>{ const chave=g.chave+k; const c=cenas[idx(p.cena_id)]; const t=segDe(p.timecode); const [cat,ccls]=categoria(p); const [sv,scls]=SEV[p.severidade]||SEV.baixa;
      return <li key={k} className={'qd-'+p.severidade}>
      <div><b>{NOME_T[p.tipo]||p.tipo}</b>{p.plano_id&&<span className="muted"> · {nPlano(c,p.plano_id)}</span>}
        {p.timecode&&<button className="link-btn" onClick={()=>pular(p.timecode)}><Clock size={12}/> {p.timecode.replace(/^00:/,'').replace(/\.\d+$/,'')} s</button>}
        <span className={'tag '+scls}>{sv}</span><span className={'tag '+ccls}>{cat}</span></div>
      <p>{p.descricao}</p>{p.correcao&&<small className="muted">Sugestão: {p.correcao}</small>}
      <small className="muted qd-extra">{confianca(p)} • {p.tentativas||0} tentativa(s) de correção • versão {render.versao}{p.evidencia?` • ${p.evidencia}`:''}</small>
      <div className="row-gap left">
        {t!=null&&<button className="link-btn" onClick={()=>setVer(ver===chave?'':chave)}><Eye size={12}/> {ver===chave?'Esconder o quadro':anterior?'Ver o quadro (agora e antes)':'Ver o quadro'}</button>}
        {podeCorrigir&&c&&!c.bloqueada&&p.tipo!=='analise_indisponivel'&&<button className="link-btn" disabled={!!busy} onClick={()=>corrigir(p,chave)}>{busy===chave?<Loader2 size={12} className="spin"/>:<RotateCcw size={12}/>} Corrigir apenas {p.plano_id?'este plano':'esta cena'}</button>}
      </div>
      {ver===chave&&t!=null&&<Quadros pid={pid} t={t} renders={[{id:render.id,versao:render.versao},...(anterior?[anterior]:[])]}/>}
     </li>; })}</ul></div>)}
    {!q.problemas.length&&!tec&&<p className="hint">Nenhum apontamento nesta versão.</p>}
    {correcoes.length>0&&<><div className="field-label mt">Correções feitas</div>
     <ul className="qd-lista">{[...correcoes].reverse().slice(0,8).map((x,k)=>{ const i=idx(x.cena_id); const t=segDe(x.timecode)??0; const chave='c'+k;
      return <li key={k}><div><b>{NOME_T[x.tipo]||x.tipo}</b> <span className="muted">· {i>=0?`Cena ${i+1}`:'cena'}{x.plano_id?` · ${nPlano(cenas[i],x.plano_id)}`:''} · a partir da versão {x.versao_antes??'?'} • {horaTexto(x.criado)}</span></div>
        {x.render_antes&&x.render_antes!==render.id&&<button className="link-btn" onClick={()=>setVer(ver===chave?'':chave)}><Eye size={12}/> Comparar versão {x.versao_antes} com a {render.versao}</button>}
        {ver===chave&&x.render_antes&&<Quadros pid={pid} t={t} renders={[{id:x.render_antes,versao:x.versao_antes||0},{id:render.id,versao:render.versao}]}/>}</li>; })}</ul></>}
  </section>;
}

// Descrição de publicação: o servidor monta (título, hashtags, três pontos e "Link original do vídeo []"); aqui só se vê e edita.
type DescEstado={txt:string;link:string;srv:Descricao|null};
function DescricaoPub({pid,redes,v,setV}:{pid:string;redes:string[];v:DescEstado;setV:(f:(x:DescEstado)=>DescEstado)=>void}){
  const cfg=useCfg(); const {toast}=useApp(); const [busy,setBusy]=useState(false);
  const chave=redes.join(',');
  const receber=(d:Descricao,trocarTexto:boolean)=>setV(x=>({txt:trocarTexto||!x.srv?d.legenda:x.txt,link:d.link_original,srv:d}));
  useEffect(()=>{ if(!cfg) return; let vivo=true;
    lerDescricao(cfg,pid,redes).then(d=>{ if(vivo) setV(x=>({txt:!x.srv||x.txt===x.srv.legenda?d.legenda:x.txt,link:x.srv?x.link:d.link_original,srv:d})); }).catch(()=>{});
    return ()=>{ vivo=false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[pid,chave]);
  const mandar=async(d:{legenda?:string;restaurar?:boolean;link_original?:string},trocar:boolean,ok:string)=>{ if(!cfg) return; setBusy(true);
    try{ receber(await salvarDescricao(cfg,pid,d),trocar); if(ok) toast(ok,'ok'); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } };
  if(!v.srv) return <p className="hint"><Loader2 size={14} className="spin"/> Montando a descrição...</p>;
  const mudou=v.txt!==v.srv.legenda;
  return <div className="descricao-pub">
    <label>Descrição da publicação (pode editar; o que você escrever vai do jeito que está)
     <textarea rows={8} value={v.txt} onChange={e=>{ const t=e.target.value; setV(x=>({...x,txt:t})); }}/></label>
    <small className="muted">{v.txt.length} caracteres{v.srv.editada||mudou?' • editada por você':' • modelo padrão'}</small>
    <label className="field-label">Link original do vídeo (opcional; só entra se for um endereço completo, começando com https://)
     <input type="url" value={v.link} placeholder="https://..." onChange={e=>{ const t=e.target.value; setV(x=>({...x,link:t})); }}
      onBlur={()=>{ if(v.link!==v.srv?.link_original) mandar({link_original:v.link},!v.srv?.editada&&!mudou,''); }}/></label>
    {v.srv.avisos.map(a=><p key={a} className="hint warn"><AlertTriangle size={13}/> {a}</p>)}
    <div className="row-gap left">
     <button className="subtle sm" disabled={busy||!mudou} onClick={()=>mandar({legenda:v.txt,link_original:v.link},true,'Descrição guardada.')}><CheckCircle2 size={14}/> Guardar a descrição</button>
     <button className="subtle sm" disabled={busy||(!v.srv.editada&&!mudou)} onClick={()=>mandar({restaurar:true,link_original:v.link},true,'Voltou ao modelo padrão.')}><RotateCcw size={14}/> Restaurar o modelo padrão</button>
    </div>
  </div>;
}

/** Agentes > Aprovações sem vídeo escolhido: o que espera a sua decisão, de onde já existia (nada é aprovado daqui). */
function ListaAprovacoes(){
  const {go}=useApp();
  const p=useServidor(pendentes,20);
  const co=useServidor(c=>lerAprovacoes(c,'pendente').catch(()=>null),30);
  const est=useServidor(c=>lerEsteira(c).catch(()=>null),30);
  const l=p.dados?.pendentes||[];
  const nCo=co.dados?.aprovacoes.length; const nEst=est.dados?.contagem?.manual_review_required;
  return <div className="aprovacoes">
    <section className="panel">
     <div className="section-head"><h2><ShieldCheck size={17}/> Vídeos e roteiros do Agente 3</h2>{p.carregando&&<Loader2 size={14} className="spin"/>}</div>
     {p.erro&&<p className="hint bad">{p.erro}</p>}
     {p.dados&&!l.length&&<p className="hint">Nada esperando você agora.</p>}
     <ul className="proj-lista">{l.map(x=><li key={x.projeto}><div className="grow"><b>{x.titulo||x.ref}</b><small className="muted"> {x.tipo==='video'?'Vídeo pronto para assistir':'Roteiro para aprovar'} • {horaTexto(x.atualizado)}</small></div>
       <button className="primary sm" onClick={()=>go('revisar',x.projeto,'agentes')}><Eye size={14}/> Abrir</button></li>)}</ul>
    </section>
    <section className="panel">
     <div className="section-head"><h2><ShieldCheck size={17}/> Outras liberações</h2></div>
     <ul className="proj-lista">
      <li><div className="grow"><b>Pacotes do Coordenador (vídeo + capa)</b><small className="muted"> {nCo==null?'não disponível':nCo===1?'1 esperando você':`${nCo} esperando você`}</small></div><button className="subtle sm" onClick={()=>go('coordenador','aprovacoes','agentes')}>Abrir</button></li>
      <li><div className="grow"><b>Revisão manual da esteira (diretor e editor)</b><small className="muted"> {nEst==null?'não disponível':`${nEst} esperando você`}</small></div><button className="subtle sm" onClick={()=>go('agente','esteira','agentes')}>Abrir</button></li>
      <li><div className="grow"><b>Fila do servidor</b><small className="muted"> o que está rodando e o que vem depois</small></div><button className="subtle sm" onClick={()=>go('fila','','agentes')}>Abrir</button></li>
     </ul>
    </section>
  </div>;
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
  const [refazer,setRefazer]=useState<{i:number;imagem:boolean;voz:boolean;plano?:string}|null>(null);
  const [desc,setDesc]=useState<DescEstado>({txt:'',link:'',srv:null});
  if(!settings.servidor) return <PrecisaServidor oque="A revisão"/>;
  if(!pid) return <ListaAprovacoes/>;
  const r=rev.dados;
  if(!r) return <section className="panel">{rev.erro?<p className="hint bad">{rev.erro}</p>:<p className="hint"><Loader2 size={14} className="spin"/> Abrindo...</p>}</section>;
  const p=r.projeto; const d=p.dados as {briefing:Briefing;cenas:Cena[];render:Render|null;roteiro:{titulo:string;legenda:string;hashtags:string[];fontes:{titulo:string;url:string}[]}|null;producao?:{erro?:string};qualidade?:Qualidade;pareceres_etapas?:Record<string,{aprovado:boolean;motivos:string[];reprovacoes:number}>;diretor?:{veredito:string;motivos:string[];tentativas:number};renders?:{id:string;versao:number}[];correcoes?:Correcao[]};
  const render=d.render; const b=d.briefing;
  const destinos=redes??(b?.destinos?.redes||[]);
  const fazer=async(nome:string,f:()=>Promise<unknown>,ok:string)=>{ setBusy(nome); try{ await f(); toast(ok,'ok'); setTexto(''); rev.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } };
  const esperandoVideo=p.status==='ready_for_review';
  const esperandoRoteiro=p.status==='waiting_brief_approval'||(p.status==='storyboard_ready'&&!render);
  const etapasPendentes=Object.values(d.pareceres_etapas||{}).some(etapa=>!etapa.aprovado);
  const liberado=esperandoVideo && r.parecer?.aprovado===true && !etapasPendentes;
  const manual=esperandoVideo && !liberado;
  const bloqueios=r.bloqueios_manuais||[];
  const st=manual?'Revisão manual disponível':r.estados[p.status]||p.status;
  return <div className="revisar">
   <button className="link-btn" onClick={()=>go('fila')}><ArrowLeft size={14}/> Fila e aprovações</button>
   <section className="panel">
    <div className="section-head"><h2>{p.titulo} <span className="tag">{r.ref}</span> <span className={'tag '+(esperandoVideo?'warn':p.status==='failed'?'bad':['approved','queued_to_publish','posted'].includes(p.status)?'ok':'')}>{st}</span> <HelpButton topic="aprovacao"/></h2></div>
    {!['failed','cancelled','paused'].includes(p.status)&&<Etapas status={p.status} detalhe={r.job&&!['concluido','cancelado'].includes(r.job.status)?(p.status==='waiting_brief_approval'?'Esperando você aprovar':r.job.status==='rodando'?`${r.job.etapa} • ${Math.round(r.job.progresso)}%`:r.job.etapa):undefined}/>}
    {!render&&!esperandoRoteiro&&!['failed','cancelled','rejected'].includes(p.status)&&<p className="hint">O celular está trabalhando. Pode fechar esta tela: quando o vídeo ficar pronto ele aparece aqui e em Fila e aprovações{' '}(e chega um e-mail, se estiver configurado).</p>}
    {p.status==='failed'&&<div className="row-gap left"><button className="primary sm" onClick={()=>go('fila')}>Abrir a fila para tentar de novo</button></div>}
    {d.producao?.erro&&p.status==='failed'&&<p className="hint bad"><AlertTriangle size={14}/> {d.producao.erro}</p>}
    {manual&&<p className="hint warn"><ShieldCheck size={14}/> Parecer do diretor pendente ou desfavorável. {r.parecer?.motivos.join(' ')} Você pode decidir sobre esta versão manualmente.</p>}
    {liberado&&d.diretor&&render&&<p className="hint ok"><ShieldCheck size={14}/> Aprovado pelo diretor de qualidade{d.diretor.tentativas>0?` depois de refazer ${d.diretor.tentativas} vez(es)`:''}. Agora falta a sua aprovação final.</p>}
    {d.diretor?.veredito==='refazendo'&&<p className="hint warn"><ShieldCheck size={14}/> O diretor de qualidade mandou refazer (tentativa {d.diretor.tentativas}): {d.diretor.motivos.join(' · ')}</p>}
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

   {d.pareceres_etapas&&<section className="panel"><h2>Revisões do Diretor de Qualidade</h2>
    <ul>{Object.entries(d.pareceres_etapas).map(([etapa,parecer])=><li key={etapa}>
     <b>{({pauta:'Pauta',roteiro:'Roteiro e storyboard',narracao:'Narração',visual:'Imagens',render:'Cenas renderizadas',creative_preedit:'Revisão criativa',final:'Vídeo final'} as Record<string,string>)[etapa]||etapa}</b>
     {' • '}{parecer.aprovado?'Aprovado':'Com pendências'}{parecer.reprovacoes>0&&` • Reprovações: ${parecer.reprovacoes}`}
     {parecer.motivos.length>0&&<p>{parecer.motivos.join(' · ')}</p>}
    </li>)}</ul></section>}

   {render&&d.qualidade&&<QualidadePainel q={d.qualidade} cenas={d.cenas||[]} pid={pid} render={render} renders={d.renders||[]} correcoes={d.correcoes||[]} podeCorrigir={esperandoVideo} corrigido={()=>rev.recarregar()}/>}

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
    {manual&&bloqueios.length>0&&<p className="hint bad">{bloqueios.join(' · ')}</p>}
    <DescricaoPub pid={pid} redes={destinos} v={desc} setV={setDesc}/>
    <div className="row-gap left mt">
     <button className="primary" disabled={!!busy||(quando==='data'&&!data)||(!desc.srv&&destinos.length>0)||(manual&&bloqueios.length>0)} onClick={()=>{
       if(manual&&!window.confirm(`Aprovar manualmente a versão ${render.versao}${destinos.length?' e encaminhar para publicação':''}?`)) return;
       return fazer('ok',()=>aprovar(cfg,pid,render.sha,{redes:destinos,quando,data:quando==='data'?new Date(data).getTime()/1000:undefined,
       link_original:desc.link,legenda:desc.srv&&(desc.srv.editada||desc.txt!==desc.srv.legenda)?desc.txt:undefined},manual),destinos.length?'Aprovado e entregue ao Agente 2.':'Aprovado. Sem rede escolhida: o vídeo fica salvo.'); }}>
      {busy==='ok'?<Loader2 size={15} className="spin"/>:<CheckCircle2 size={15}/>} {manual?'Aprovar manualmente':'Aprovar'}{destinos.length?' e agendar':''}</button>
     <button className="subtle" disabled={!!busy} hidden={manual} onClick={()=>fazer('mail',()=>reenviarEmail(cfg,pid),'E-mail com código novo enviado (o anterior deixou de valer).')}><Mail size={15}/> Reenviar e-mail</button>
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
    <ol className="cenas-lista">{(d.cenas||[]).map((c,i)=><li key={c.id}><b>{c.titulo}</b>{c.bloqueada&&<Lock size={12}/>} {c.destaque&&<span className="tag">{c.destaque}</span>}<p>{c.texto}</p>{c.clipe?.dur?<small className="muted">{c.clipe.dur.toFixed(1)} s</small>:null}
      {esperandoVideo&&render&&(refazer?.i===i?<div className="refazer-box">
        <p className="hint">O celular faz de novo só esta cena; as outras ficam iguais. Depois o vídeo volta para você aprovar.</p>
        {(c.planos||[]).length>1&&<label className="field-label">O que refazer
         <select value={refazer.plano||''} onChange={e=>setRefazer({...refazer,plano:e.target.value})}><option value="">A cena toda</option>{(c.planos||[]).map((p,k)=><option key={k} value={p.id||`p${k+1}`}>Só o plano {k+1} ({p.plano}{p.personagem?` em ${p.personagem}`:''}): o resto vem pronto</option>)}</select></label>}
        <label className="check"><input type="checkbox" checked={refazer.imagem} onChange={e=>setRefazer({...refazer,imagem:e.target.checked})}/> Trocar a foto ou imagem</label>
        <label className="check"><input type="checkbox" checked={refazer.voz} onChange={e=>setRefazer({...refazer,voz:e.target.checked})}/> Gravar a narração de novo</label>
        <div className="row-gap left"><button className="primary sm" disabled={!!busy} onClick={()=>fazer('cena',async()=>{ await refazerCena(cfg,pid,i,refazer); setRefazer(null); },`Refazendo a cena ${i+1}.`)}>{busy==='cena'?<Loader2 size={14} className="spin"/>:<RotateCcw size={14}/>} Refazer a cena {i+1}</button>
         <button className="link-btn" onClick={()=>setRefazer(null)}>Cancelar</button></div>
       </div>:<div className="refazer-acao"><button className="link-btn" onClick={()=>setRefazer({i,imagem:false,voz:false})}><RotateCcw size={12}/> Refazer só esta cena</button></div>)}</li>)}</ol>
    {d.roteiro?.fontes?.length?<><div className="field-label">Fontes para conferir</div><ul>{d.roteiro.fontes.map(f=><li key={f.url}><a className="help-link" href={f.url} target="_blank" rel="noreferrer">{f.titulo||f.url}</a></li>)}</ul></>:null}
    <p className="hint">Estilo: {b?.estilo} • formato {b?.formato} • voz {b?.voz} • modo {b?.modo_aprovacao==='assistido'?'assistido':'supervisionado'}</p>
   </section>

   {r.historico.length>0&&<section className="panel">
    <div className="section-head"><h2>Histórico de decisões</h2></div>
    <ul className="historico">{r.historico.map(h=><li key={h.id}><b>{DECISAO[h.decisao]||h.decisao}</b> • {horaTexto(h.criado)} • {h.origem==='site_manual'?'por aprovação manual':h.origem==='email'?'por e-mail':'pelo site'} ({h.por}){h.texto&&<> • “{h.texto}”</>}</li>)}</ul>
   </section>}
   {r.job&&<p className="hint">Trabalho: {r.job.status} • decorrido {duracaoTexto(r.job.decorrido)}</p>}
  </div>;
}
