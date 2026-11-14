import { useCallback, useEffect, useRef, useState } from 'react';
import { Bot, Scissors, Send, Square, Play, Search, Link2, Loader2, CheckCircle2, AlertTriangle, Trash2, Mail, Download, Eye, Plus, X, KeyRound, Clock, RefreshCw, ExternalLink, CalendarClock } from 'lucide-react';
import { useApp } from '../state';
import { REDES } from '../lib/agenda';
import { verAgente, salvarAgente, salvarChaves, acaoCanal, rodarAgente, pararAgente, testarEmail, acaoCorte, videoDoCorte, DIAS, MOTIVOS, type VisaoAgente, type ConfigAgente, type Canal, type CorteAgente, type Template } from '../lib/agente';

type Parte = 'cortes'|'postagem'|'avisos'|'fila';
const num=(n:number)=>n.toLocaleString('pt-BR');
const quando=(ts:number)=>new Date(ts*1000).toLocaleString('pt-BR',{weekday:'short',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
const ST:Record<string,[string,string]>={pronto:['Pronto','info'],agendado:['Agendado','warn'],postado:['Enviado','ok'],descartado:['Descartado','']};

/** Campo que só salva quando você sai dele (não manda um pedido a cada letra). */
function Campo({valor,salvar,tipo='text',...resto}:{valor:string|number;salvar:(v:string)=>void;tipo?:string}&Omit<React.InputHTMLAttributes<HTMLInputElement>,'value'|'onChange'|'type'>){
  const [v,setV]=useState(String(valor));
  useEffect(()=>{ setV(String(valor)); },[valor]);
  return <input {...resto} type={tipo} value={v} onChange={e=>setV(e.target.value)} onBlur={()=>{ if(v!==String(valor)) salvar(v); }} onKeyDown={e=>{ if(e.key==='Enter') (e.target as HTMLInputElement).blur(); }}/>;
}

function Lista({titulo,escolhidos,sugestoes,mudar,placeholder}:{titulo:string;escolhidos:string[];sugestoes:string[];mudar:(l:string[])=>void;placeholder:string}){
  const [novo,setNovo]=useState('');
  const tem=(s:string)=>escolhidos.some(e=>e.toLowerCase()===s.toLowerCase());
  const troca=(s:string)=>mudar(tem(s)?escolhidos.filter(e=>e.toLowerCase()!==s.toLowerCase()):[...escolhidos,s]);
  const extras=escolhidos.filter(e=>!sugestoes.some(s=>s.toLowerCase()===e.toLowerCase()));
  const add=()=>{ const t=novo.trim(); if(t&&!tem(t)) mudar([...escolhidos,t]); setNovo(''); };
  return <div className="ag-lista">
    <span className="field-label">{titulo}</span>
    <div className="chips">{[...sugestoes,...extras].map(s=><button key={s} type="button" className={'chip '+(tem(s)?'on':'')} aria-pressed={tem(s)} onClick={()=>troca(s)}>{s}</button>)}</div>
    <div className="ag-add"><input value={novo} onChange={e=>setNovo(e.target.value)} onKeyDown={e=>{ if(e.key==='Enter') add(); }} placeholder={placeholder}/><button type="button" className="subtle sm" onClick={add} disabled={!novo.trim()}><Plus size={14}/> Adicionar</button></div>
  </div>;
}

function CanalLinha({c,fazer}:{c:Canal;fazer:(d:Parameters<typeof acaoCanal>[1])=>void}){
  const [abrir,setAbrir]=useState(false); const [motivo,setMotivo]=useState('');
  return <li className={'ag-canal '+c.status}>
    <div className="grow">
      <a href={`https://www.youtube.com/channel/${c.id}`} target="_blank" rel="noreferrer"><strong>{c.nome||c.id}</strong> <ExternalLink size={12}/></a>
      <small>{c.media>0&&<>média de <b>{num(c.media)}</b> visualizações em {c.videos} vídeo(s) da semana · </>}{c.inscritos>0&&<>{num(c.inscritos)} inscritos · </>}{c.nicho}</small>
      {c.exemplo&&<small className="muted">Ex.: {c.exemplo}</small>}
      {c.status==='aprovado'&&<span className="tag ok"><CheckCircle2 size={12}/> {MOTIVOS[c.motivo]||'Aprovado'}</span>}
    </div>
    <div className="ag-canal-acoes">
      {c.status!=='aprovado'&&!abrir&&<button className="primary sm" onClick={()=>setAbrir(true)}>Aprovar</button>}
      {c.status==='sugerido'&&!abrir&&<button className="subtle sm" onClick={()=>fazer({acao:'recusar',id:c.id})}>Recusar</button>}
      {c.status!=='sugerido'&&<button className="link-btn" onClick={()=>fazer({acao:'remover',id:c.id})}><Trash2 size={13}/> Tirar da lista</button>}
    </div>
    {abrir&&<div className="ag-motivo">
      <b>Por que você pode cortar este canal?</b>
      {Object.entries(MOTIVOS).map(([k,t])=><label key={k} className="check"><input type="radio" name={'motivo'+c.id} checked={motivo===k} onChange={()=>setMotivo(k)}/> {t}</label>)}
      <p className="hint warn"><AlertTriangle size={13}/> Confira a permissão antes de marcar. Cortar canal de terceiros sem permissão pode derrubar as suas contas.</p>
      <div className="row-gap left"><button className="primary sm" disabled={!motivo} onClick={()=>{ fazer({acao:'aprovar',id:c.id,motivo}); setAbrir(false); }}>Confirmar aprovação</button><button className="subtle sm" onClick={()=>setAbrir(false)}>Cancelar</button></div>
    </div>}
  </li>;
}

function CorteLinha({c,fazer}:{c:CorteAgente;fazer:(acao:'descartar'|'agendar'|'email')=>void}){
  const {settings,toast}=useApp();
  const [url,setUrl]=useState(''); const [busy,setBusy]=useState(false);
  useEffect(()=>()=>{ if(url) URL.revokeObjectURL(url); },[url]);
  const trazer=async(baixar:boolean)=>{
    setBusy(true);
    try{
      const blob=await videoDoCorte(settings,c.id); const u=URL.createObjectURL(blob);
      if(baixar){ const a=document.createElement('a'); a.href=u; a.download=(c.titulo.replace(/[\\/:*?"<>|]+/g,'').slice(0,60)||'corte')+'.mp4'; a.click(); setTimeout(()=>URL.revokeObjectURL(u),30000); }
      else setUrl(u);
    }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }finally{ setBusy(false); }
  };
  const [rot,cls]=ST[c.status]||[c.status,''];
  return <li className="ag-corte">
    {url&&<video src={url} controls playsInline className="ag-video"/>}
    <div className="grow">
      <div className="label-row"><strong>{c.titulo}</strong><span className={'tag '+cls}>{rot}</span><span className="tag">pontuação {c.nota}/99</span>{c.email&&<span className="tag"><Mail size={11}/> enviado por e-mail</span>}</div>
      <small>{Math.round(c.fim-c.ini)} s · de “{c.origem_titulo}” ({c.canal_nome}) · feito {quando(c.criado)}{c.quando&&c.status!=='pronto'?` · post ${quando(c.quando)}`:''}{typeof c.views==='number'?` · ${num(c.views)} visualizações no YouTube`:''}</small>
      {c.hashtags.length>0&&<small className="muted">{c.hashtags.join(' ')}</small>}
      {c.motivo&&<small className="muted">Por que este trecho: {c.motivo}</small>}
      {c.erros&&Object.entries(c.erros).map(([r,m])=><p key={r} className="hint bad"><AlertTriangle size={13}/> {r}: {m}</p>)}
      {c.links&&Object.entries(c.links).filter(([,l])=>/^https?:/.test(l)).map(([r,l])=><a key={r} className="link-btn" href={l.split(' ')[0]} target="_blank" rel="noreferrer">{r} <ExternalLink size={12}/></a>)}
    </div>
    {c.video&&<div className="ag-canal-acoes">
      {!url&&<button className="subtle sm" disabled={busy} onClick={()=>trazer(false)}>{busy?<Loader2 size={14} className="spin"/>:<Eye size={14}/>} Ver</button>}
      <button className="subtle sm" disabled={busy} onClick={()=>trazer(true)}><Download size={14}/> Baixar</button>
      {c.status==='pronto'&&<button className="primary sm" onClick={()=>fazer('agendar')}><CalendarClock size={14}/> Agendar</button>}
      <button className="subtle sm" onClick={()=>fazer('email')}><Mail size={14}/> E-mail</button>
      {c.status!=='descartado'&&c.status!=='postado'&&<button className="link-btn" onClick={()=>fazer('descartar')}><Trash2 size={13}/> Descartar</button>}
    </div>}
  </li>;
}

export default function Agente(){
  const {settings,toast,go}=useApp();
  const [v,setV]=useState<VisaoAgente|null>(null); const [erro,setErro]=useState(''); const [parte,setParte]=useState<Parte>('cortes');
  const [link,setLink]=useState(''); const [canalLink,setCanalLink]=useState(''); const [canalMotivo,setCanalMotivo]=useState('');
  const [chaves,setChaves]=useState({gemini:'',youtube:'',email_senha:''}); const [hora,setHora]=useState('18:00'); const [diasSel,setDiasSel]=useState<number[]>([0,1,2,3,4,5]);
  const vivo=useRef(true);
  useEffect(()=>{ vivo.current=true; return ()=>{ vivo.current=false; }; },[]);
  const carregar=useCallback(()=>{ if(!settings.servidor) return; verAgente(settings).then(x=>{ if(vivo.current){ setV(x); setErro(''); } }).catch(e=>{ if(vivo.current) setErro(e.message); }); },[settings]);
  const ocupado=!!v?.atual.ocupado;
  useEffect(()=>{ carregar(); const t=setInterval(carregar,ocupado?3000:12000); return ()=>clearInterval(t); },[carregar,ocupado]);
  const run=async(f:()=>Promise<unknown>,ok?:string)=>{ try{ const r=await f(); if(r&&typeof r==='object'&&'config' in r) setV(r as VisaoAgente); else carregar(); if(ok) toast(ok,'ok'); }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); } };
  const salvar=(p:Parameters<typeof salvarAgente>[1])=>run(()=>salvarAgente(settings,p));

  if(!settings.servidor) return <section className="panel empty-state"><Bot size={34}/><strong>Os agentes rodam no seu servidor</strong><p>Ligue o servidor no celular ou no computador e conecte o aplicativo a ele. Depois volte aqui para configurar os agentes.</p><button className="primary" onClick={()=>go('config')}>Abrir Chaves e ajustes</button></section>;
  if(!v) return <section className="panel empty-state">{erro?<><AlertTriangle size={30}/><strong>Não consegui abrir os agentes</strong><p>{erro}</p><button className="subtle" onClick={carregar}><RefreshCw size={14}/> Tentar de novo</button></>:<><Loader2 size={26} className="spin"/><p>Falando com o servidor...</p></>}</section>;

  const c:ConfigAgente=v.config; const co=c.cortes, po=c.postagem, em=c.email, tpl=co.template;
  const aprovados=v.canais.filter(x=>x.status==='aprovado'); const sugeridos=v.canais.filter(x=>x.status==='sugerido'); const recusados=v.canais.filter(x=>x.status==='recusado');
  const prontos=v.cortes.filter(x=>x.status==='pronto').length;
  const faltas:string[]=[];
  if(!v.ffmpeg) faltas.push('Falta o FFmpeg no servidor (no Termux: pkg install ffmpeg).');
  if(!v.chaves.youtube) faltas.push('Falta a chave do YouTube (parte Avisos e chaves).');
  if(!v.chaves.gemini) faltas.push('Falta a chave do Gemini (parte Avisos e chaves).');
  if(!aprovados.length) faltas.push('Nenhum canal aprovado ainda (parte Cortes).');
  if(!em.para||!em.de||!v.chaves.email_senha) faltas.push('O e-mail de avisos não está completo (parte Avisos e chaves).');
  const tp=(p:Partial<Template>)=>salvar({cortes:{template:p}});
  const variar=(k:string)=>{ const tem=co.variar.includes(k); if(!tem&&co.variar.length>=3){ toast('Escolha no máximo 3 elementos para variar.','erro'); return; } salvar({cortes:{variar:tem?co.variar.filter(x=>x!==k):[...co.variar,k]}}); };
  const addFaixas=()=>{ if(!/^\d\d:\d\d$/.test(hora)||!diasSel.length) return; salvar({postagem:{faixas:[...po.faixas,...diasSel.map(d=>({dia:d,hora}))]}}); };
  const guardarChaves=(k:Partial<typeof chaves>)=>run(async()=>{ const r=await salvarChaves(settings,k); setChaves({gemini:'',youtube:'',email_senha:''}); return r; },'Guardado no servidor.');

  return <div className="agente">
    <section className="panel ag-topo">
      <div className={'ag-card '+(co.ligado?'on':'')}>
        <div className="label-row"><Scissors size={18}/><strong>Agente de cortes</strong><span className={'tag '+(co.ligado?'ok':'')}>{co.ligado?'Ligado':'Desligado'}</span></div>
        <p>Procura canais, acha vídeos novos dos canais aprovados, corta, edita no seu template e manda cada corte por e-mail.</p>
        <small>Nesta semana: <b>{v.semana}</b> de {co.por_semana} cortes · {aprovados.length} canal(is) aprovado(s){sugeridos.length?` · ${sugeridos.length} esperando você`:''}</small>
        <div className="row-gap left">
          <button className={co.ligado?'subtle sm':'primary sm'} onClick={()=>salvar({cortes:{ligado:!co.ligado}})}>{co.ligado?<><Square size={13}/> Desligar</>:<><Play size={13}/> Ligar</>}</button>
          <button className="subtle sm" disabled={ocupado} onClick={()=>run(()=>rodarAgente(settings,'cortar'),'Começando a cortar. Acompanhe aqui.')}><Scissors size={13}/> Cortar agora</button>
          <button className="subtle sm" disabled={ocupado} onClick={()=>run(()=>rodarAgente(settings,'buscar'),'Procurando canais em alta.')}><Search size={13}/> Procurar canais</button>
        </div>
      </div>
      <div className={'ag-card '+(po.ligado?'on':'')}>
        <div className="label-row"><Send size={18}/><strong>Agente de postagem</strong><span className={'tag '+(po.ligado?'ok':'')}>{po.ligado?'Ligado':'Desligado'}</span></div>
        <p>Pega os cortes prontos, agenda nas redes nos horários escolhidos, avisa por e-mail e aprende os melhores horários.</p>
        <small>{prontos} corte(s) pronto(s) na fila · {v.cortes.filter(x=>x.status==='agendado').length} agendado(s)</small>
        <div className="row-gap left">
          <button className={po.ligado?'subtle sm':'primary sm'} onClick={()=>salvar({postagem:{ligado:!po.ligado}})}>{po.ligado?<><Square size={13}/> Desligar</>:<><Play size={13}/> Ligar</>}</button>
          <button className="subtle sm" disabled={ocupado||!prontos} onClick={()=>run(()=>rodarAgente(settings,'postar'),'Agendando os cortes prontos.')}><CalendarClock size={13}/> Agendar prontos agora</button>
        </div>
      </div>
      <div className="ag-geral">
        {v.atual.etapa?<div className="ag-etapa" role="status"><Loader2 size={15} className="spin"/> <span>{v.atual.etapa}</span><div className="barra"><i style={{width:Math.max(4,v.atual.pct)+'%'}}/></div></div>:<span className="muted">{co.ligado||po.ligado?'Esperando a próxima tarefa.':'Os dois agentes estão parados.'}</span>}
        <button className="danger sm" onClick={()=>{ if(confirm('Parar os dois agentes e tirar da agenda os posts que eles marcaram?')) run(()=>pararAgente(settings),'Tudo parado.'); }}><Square size={13}/> Parar tudo</button>
      </div>
      {faltas.length>0&&<ul className="ag-faltas">{faltas.map(f=><li key={f}><AlertTriangle size={13}/> {f}</li>)}</ul>}
      {erro&&<p className="hint bad"><AlertTriangle size={13}/> {erro}</p>}
    </section>

    <div className="ag-abas" role="tablist">{([['cortes','Cortes'],['postagem','Postagem'],['avisos','Avisos e chaves'],['fila',`Fila e histórico${v.cortes.length?` (${v.cortes.length})`:''}`]] as [Parte,string][]).map(([k,t])=><button key={k} role="tab" aria-selected={parte===k} className={parte===k?'active':''} onClick={()=>setParte(k)}>{t}</button>)}</div>

    {parte==='cortes'&&<>
      <section className="panel">
        <h3>Canais</h3>
        <p className="hint tight">O agente só corta canais aprovados por você, com o motivo marcado.</p>
        {sugeridos.length>0&&<><span className="field-label">Sugeridos pelo agente ({sugeridos.length})</span><ul className="ag-canais">{sugeridos.map(x=><CanalLinha key={x.id} c={x} fazer={d=>run(()=>acaoCanal(settings,d))}/>)}</ul></>}
        <span className="field-label">Aprovados ({aprovados.length})</span>
        {aprovados.length?<ul className="ag-canais">{aprovados.map(x=><CanalLinha key={x.id} c={x} fazer={d=>run(()=>acaoCanal(settings,d))}/>)}</ul>:<p className="hint">Nenhum ainda. Aprove um sugerido, toque em Procurar canais ou cole o link de um canal abaixo.</p>}
        <div className="ag-add mt"><input value={canalLink} onChange={e=>setCanalLink(e.target.value)} placeholder="Link do canal: youtube.com/@nome"/>
          <select value={canalMotivo} onChange={e=>setCanalMotivo(e.target.value)} aria-label="Motivo"><option value="">Só adicionar à lista</option>{Object.entries(MOTIVOS).map(([k,t])=><option key={k} value={k}>Aprovar: {t}</option>)}</select>
          <button className="subtle sm" disabled={!canalLink.trim()} onClick={()=>run(async()=>{ const r=await acaoCanal(settings,{acao:'adicionar',link:canalLink,motivo:canalMotivo||undefined}); setCanalLink(''); return r; },'Canal adicionado.')}><Plus size={14}/> Adicionar canal</button></div>
        {recusados.length>0&&<details className="mt"><summary>Recusados ({recusados.length})</summary><ul className="ag-canais">{recusados.map(x=><CanalLinha key={x.id} c={x} fazer={d=>run(()=>acaoCanal(settings,d))}/>)}</ul></details>}
      </section>
      <section className="panel">
        <h3>O que procurar</h3>
        <Lista titulo="Nichos" escolhidos={co.nichos} sugestoes={v.opcoes.nichos} mudar={l=>salvar({cortes:{nichos:l}})} placeholder="Outro nicho"/>
        <div className="ag-grade">
          <label>Idioma dos canais<select value={co.idioma} onChange={e=>salvar({cortes:{idioma:e.target.value}})}>{Object.entries(v.opcoes.idiomas||{pt:'Português'}).map(([k,t])=><option key={k} value={k}>{t}</option>)}</select></label>
          <label>País dos canais<select value={co.regiao} onChange={e=>salvar({cortes:{regiao:e.target.value}})}>{Object.entries(v.opcoes.paises||{BR:'Brasil'}).map(([k,t])=><option key={k} value={k}>{t}</option>)}</select></label>
          <label>Média mínima de visualizações na semana<Campo tipo="number" min={0} step={50000} valor={co.min_views} salvar={x=>salvar({cortes:{min_views:+x}})}/></label>
          <label>Vídeos de até quantos dias atrás<Campo tipo="number" min={1} max={90} valor={co.dias_video} salvar={x=>salvar({cortes:{dias_video:+x}})}/></label>
          <label>Duração do vídeo de origem, mínimo (min)<Campo tipo="number" min={1} valor={co.video_min} salvar={x=>salvar({cortes:{video_min:+x}})}/></label>
          <label>Duração do vídeo de origem, máximo (min)<Campo tipo="number" min={2} valor={co.video_max} salvar={x=>salvar({cortes:{video_max:+x}})}/></label>
        </div>
        <p className="hint">O idioma vale para a busca de canais, para a leitura da fala e para a legenda dos cortes. O YouTube trata o idioma como preferência: confira o canal antes de aprovar.</p>
        <Lista titulo="Nunca postar (assuntos e palavras proibidas)" escolhidos={co.proibidos} sugestoes={v.opcoes.proibidos} mudar={l=>salvar({cortes:{proibidos:l}})} placeholder="Outra palavra ou assunto"/>
      </section>
      <section className="panel">
        <h3>Quantidade e tamanho</h3>
        <div className="ag-grade">
          <label>Cortes por semana<Campo tipo="number" min={1} max={21} valor={co.por_semana} salvar={x=>salvar({cortes:{por_semana:+x}})}/></label>
          <label>Cortes por vídeo<Campo tipo="number" min={1} max={6} valor={co.por_video} salvar={x=>salvar({cortes:{por_video:+x}})}/></label>
          <label>Duração mínima do corte (s)<Campo tipo="number" min={8} valor={co.dur_min} salvar={x=>salvar({cortes:{dur_min:+x}})}/></label>
          <label>Duração máxima do corte (s)<Campo tipo="number" min={15} valor={co.dur_max} salvar={x=>salvar({cortes:{dur_max:+x}})}/></label>
          <label>Pontuação mínima (0 a 99)<Campo tipo="number" min={0} max={99} valor={co.nota_min} salvar={x=>salvar({cortes:{nota_min:+x}})}/></label>
          <label>Trabalhar das (hora)<Campo tipo="number" min={0} max={23} valor={co.hora_ini} salvar={x=>salvar({cortes:{hora_ini:+x}})}/></label>
          <label>até as (hora)<Campo tipo="number" min={1} max={24} valor={co.hora_fim} salvar={x=>salvar({cortes:{hora_fim:+x}})}/></label>
        </div>
        <p className="hint">Montar vídeo pesa no celular. Se ele esquenta de dia, deixe o agente trabalhar só de madrugada, por exemplo das 0 às 6.</p>
      </section>
      <section className="panel">
        <h3>Template padrão dos cortes</h3>
        <div className="ag-grade">
          <label>Legenda<select value={tpl.legenda} onChange={e=>tp({legenda:e.target.value as Template['legenda']})}><option value="destaque">Palavra em destaque</option><option value="simples">Simples com contorno</option><option value="caixa">Caixa escura</option><option value="nenhuma">Sem legenda</option></select></label>
          <label>Tamanho da letra<select value={tpl.tamanho} onChange={e=>tp({tamanho:e.target.value as Template['tamanho']})}><option value="pequeno">Pequena</option><option value="medio">Média</option><option value="grande">Grande</option></select></label>
          <label>Altura da legenda<select value={tpl.legenda_pos} onChange={e=>tp({legenda_pos:e.target.value as Template['legenda_pos']})}><option value="baixo">Embaixo</option><option value="meio">No meio</option></select></label>
          <label>Cor da letra<input type="color" value={tpl.cor} onChange={e=>tp({cor:e.target.value})}/></label>
          <label>Cor da palavra em destaque<input type="color" value={tpl.cor_destaque} onChange={e=>tp({cor_destaque:e.target.value})}/></label>
          <label className="check"><input type="checkbox" checked={tpl.maiusculas} onChange={e=>tp({maiusculas:e.target.checked})}/> Letras maiúsculas</label>
          <label>Enquadramento<select value={tpl.enquadramento} onChange={e=>tp({enquadramento:e.target.value as Template['enquadramento']})}><option value="desfoque">Vídeo inteiro com fundo desfocado</option><option value="cortar">Cortar as laterais (tela cheia)</option></select></label>
          <label>Zoom do vídeo<select value={String(tpl.zoom)} onChange={e=>tp({zoom:+e.target.value})}><option value="1">Sem zoom</option><option value="1.15">Leve</option><option value="1.3">Médio</option><option value="1.6">Forte</option></select></label>
          <label>Qualidade<select value={String(tpl.qualidade)} onChange={e=>tp({qualidade:+e.target.value})}><option value="1080">1080 x 1920 (melhor)</option><option value="720">720 x 1280 (mais rápido e leve)</option></select></label>
          <label className="check"><input type="checkbox" checked={tpl.gancho} onChange={e=>tp({gancho:e.target.checked})}/> Mostrar o gancho nos 3 primeiros segundos</label>
          <label>Posição do gancho<select value={tpl.gancho_pos} onChange={e=>tp({gancho_pos:e.target.value as Template['gancho_pos']})}><option value="topo">No topo</option><option value="alto">Um pouco abaixo</option></select></label>
          <label>Texto da tarja de cima<Campo valor={tpl.tarja_topo} maxLength={40} placeholder="Vazio = sem tarja" salvar={x=>tp({tarja_topo:x})}/></label>
          <label>Texto da tarja de baixo<Campo valor={tpl.tarja_base} maxLength={40} placeholder="Vazio = sem tarja" salvar={x=>tp({tarja_base:x})}/></label>
          <label>Cor das tarjas<input type="color" value={tpl.cor_tarja} onChange={e=>tp({cor_tarja:e.target.value})}/></label>
          <label>Cor do texto das tarjas<input type="color" value={tpl.cor_tarja_texto} onChange={e=>tp({cor_tarja_texto:e.target.value})}/></label>
        </div>
        <span className="field-label mt">O que pode variar de um corte para outro (até 3)</span>
        <div className="chips">{Object.entries(v.opcoes.variacoes).map(([k,t])=><button key={k} type="button" className={'chip '+(co.variar.includes(k)?'on':'')} aria-pressed={co.variar.includes(k)} onClick={()=>variar(k)}>{t}</button>)}</div>
        <p className="hint">O agente sorteia esses elementos em cada corte para os vídeos não saírem todos iguais. O resto segue o template acima.</p>
        <div className="ag-add mt"><input value={link} onChange={e=>setLink(e.target.value)} placeholder="Testar o template: cole o link de um vídeo do YouTube"/><button className="subtle sm" disabled={ocupado||!link.trim()} onClick={()=>run(async()=>{ await rodarAgente(settings,'link',link.trim()); setLink(''); setParte('fila'); },'Cortando este vídeo. O resultado aparece na fila.')}><Link2 size={14}/> Cortar este link</button></div>
      </section>
    </>}

    {parte==='postagem'&&<>
      <section className="panel">
        <h3>Redes</h3>
        <div className="chips">{REDES.map(r=><button key={r.id} type="button" className={'chip '+(po.redes.includes(r.id)?'on':'')} aria-pressed={po.redes.includes(r.id)} onClick={()=>salvar({postagem:{redes:po.redes.includes(r.id)?po.redes.filter(x=>x!==r.id):[...po.redes,r.id]}})}>{r.nome}</button>)}</div>
        <p className="hint">Cada corte vai para todas as redes marcadas. As contas são as mesmas da aba Agendar posts. <button className="link-btn" onClick={()=>go('agendar')}>Conferir conexões</button></p>
        <div className="ag-grade">
          <label>YouTube chega como<select value={po.youtube_privacidade} onChange={e=>salvar({postagem:{youtube_privacidade:e.target.value}})}><option value="private">Privado (você deixa público no aplicativo)</option><option value="unlisted">Não listado</option><option value="public">Público</option></select></label>
          <label>TikTok chega como<select value={po.tiktok_modo} onChange={e=>salvar({postagem:{tiktok_modo:e.target.value}})}><option value="rascunho">Rascunho (você publica no aplicativo)</option><option value="direto">Direto no perfil</option></select></label>
        </div>
        <p className="hint">Instagram e Facebook saem públicos direto. O Kwai não aceita postagem automática: o corte chega no seu e-mail para você postar à mão.</p>
      </section>
      <section className="panel">
        <h3>Horários</h3>
        <p className="hint tight">Marque todos os horários que servem para você. O agente usa {co.por_semana} por semana: primeiro testa cada um, depois fica com os que renderam mais visualizações no YouTube.</p>
        <div className="ag-add"><input type="time" value={hora} onChange={e=>setHora(e.target.value)} aria-label="Horário"/>
          <div className="chips ag-dias">{DIAS.map((d,i)=><button key={d} type="button" className={'chip '+(diasSel.includes(i)?'on':'')} aria-pressed={diasSel.includes(i)} onClick={()=>setDiasSel(s=>s.includes(i)?s.filter(x=>x!==i):[...s,i])}>{d.slice(0,3)}</button>)}</div>
          <button className="subtle sm" onClick={addFaixas}><Plus size={14}/> Adicionar horário</button></div>
        <ul className="ag-faixas">{DIAS.map((d,i)=>{ const fs=po.faixas.filter(f=>f.dia===i).sort((a,b)=>a.hora.localeCompare(b.hora)); return <li key={d}><b>{d}</b><div className="chips">{fs.length?fs.map(f=>{ const h=v.horarios[`${f.dia}-${f.hora}`]; return <span key={f.hora} className="chip on"><Clock size={12}/> {f.hora}{h&&h.n>0?` · média ${num(Math.round(h.views/h.n))}`:''}<button aria-label={`Tirar ${d} ${f.hora}`} onClick={()=>salvar({postagem:{faixas:po.faixas.filter(x=>!(x.dia===f.dia&&x.hora===f.hora))}})}><X size={12}/></button></span>; }):<small className="muted">sem horário</small>}</div></li>; })}</ul>
        {po.faixas.length<co.por_semana&&<p className="hint warn"><AlertTriangle size={13}/> Há {po.faixas.length} horário(s) por semana para {co.por_semana} cortes. Marque mais horários ou os cortes vão acumular na fila.</p>}
      </section>
    </>}

    {parte==='avisos'&&<>
      <section className="panel">
        <h3>Avisos por e-mail</h3>
        <div className="ag-grade">
          <label>E-mail que recebe os avisos<Campo tipo="email" valor={em.para} placeholder="voce@exemplo.com" salvar={x=>salvar({email:{para:x.trim()}})}/></label>
          <label>E-mail que envia<Campo tipo="email" valor={em.de} placeholder="pode ser o mesmo" salvar={x=>salvar({email:{de:x.trim()}})}/></label>
          <label>Senha de aplicativo do e-mail que envia {v.chaves.email_senha&&<span className="tag ok">guardada</span>}<input type="password" autoComplete="off" value={chaves.email_senha} onChange={e=>setChaves(s=>({...s,email_senha:e.target.value}))} placeholder={v.chaves.email_senha?'Digite só para trocar':'16 letras, sem espaços'}/></label>
          <div className="row-gap left"><button className="primary sm" disabled={!chaves.email_senha.trim()} onClick={()=>guardarChaves({email_senha:chaves.email_senha.replace(/\s+/g,'')})}><KeyRound size={14}/> Guardar senha</button>
            <button className="subtle sm" onClick={()=>run(()=>testarEmail(settings),'E-mail de teste enviado. Confira a caixa de entrada.')}><Mail size={14}/> Enviar e-mail de teste</button></div>
        </div>
        <p className="hint">Não é a senha normal da conta. No Gmail: Conta Google &gt; Segurança &gt; Verificação em duas etapas &gt; Senhas de app. Ela fica guardada só no servidor e nunca volta para esta tela.</p>
        <span className="field-label mt">Quais avisos mandar</span>
        <div className="chips">{([['corte','Corte pronto (com o vídeo)'],['agendado','Post agendado'],['postado','Post enviado'],['falha','Falhas'],['canal','Canais novos sugeridos'],['semana','Resumo da semana']] as [string,string][]).map(([k,t])=><button key={k} type="button" className={'chip '+(em.avisos[k]?'on':'')} aria-pressed={!!em.avisos[k]} onClick={()=>salvar({email:{avisos:{[k]:!em.avisos[k]}}})}>{t}</button>)}</div>
        <label className="check mt"><input type="checkbox" checked={em.anexar} onChange={e=>salvar({email:{anexar:e.target.checked}})}/> Anexar o vídeo do corte no e-mail</label>
        <p className="hint">E-mail tem limite de anexo. Quando o corte passa do limite, o agente anexa uma cópia menor e deixa a versão completa na fila daqui.</p>
        <details className="mt"><summary>Outro provedor de e-mail</summary><div className="ag-grade mt">
          <label>Servidor SMTP<Campo valor={em.smtp} placeholder="Vazio = descobrir pelo e-mail" salvar={x=>salvar({email:{smtp:x.trim()}})}/></label>
          <label>Porta<Campo tipo="number" valor={em.porta} salvar={x=>salvar({email:{porta:+x}})}/></label></div></details>
      </section>
      <section className="panel">
        <h3>Chaves usadas pelos agentes</h3>
        <p className="hint tight">Os agentes trabalham com o aplicativo fechado, então as chaves precisam ficar no servidor. Elas não voltam para esta tela.</p>
        <div className="ag-grade">
          <label>Chave do Gemini {v.chaves.gemini&&<span className="tag ok">guardada</span>}<input type="password" autoComplete="off" value={chaves.gemini} onChange={e=>setChaves(s=>({...s,gemini:e.target.value}))} placeholder={v.chaves.gemini?'Digite só para trocar':'Cole a chave'}/></label>
          <label>Chave do YouTube {v.chaves.youtube&&<span className="tag ok">guardada</span>}<input type="password" autoComplete="off" value={chaves.youtube} onChange={e=>setChaves(s=>({...s,youtube:e.target.value}))} placeholder={v.chaves.youtube?'Digite só para trocar':'Cole a chave'}/></label>
        </div>
        <div className="row-gap left mt">
          <button className="primary sm" disabled={!chaves.gemini.trim()&&!chaves.youtube.trim()} onClick={()=>guardarChaves({...(chaves.gemini.trim()?{gemini:chaves.gemini.trim()}:{}),...(chaves.youtube.trim()?{youtube:chaves.youtube.trim()}:{})})}><KeyRound size={14}/> Guardar no servidor</button>
          {(settings.geminiKey||settings.ytKey)&&<button className="subtle sm" onClick={()=>guardarChaves({...(settings.geminiKey?{gemini:settings.geminiKey}:{}),...(settings.ytKey?{youtube:settings.ytKey}:{})})}>Usar as chaves já salvas neste aparelho</button>}
        </div>
      </section>
      <section className="panel">
        <h3>Orçamento da IA</h3>
        <div className="ag-grade">
          <label>Teto por mês (R$)<Campo tipo="number" min={0} step={1} valor={c.orcamento.teto} salvar={x=>salvar({orcamento:{teto:+x}})}/></label>
          <div className="ag-gasto"><span>Gasto estimado neste mês</span><b>R$ {v.gasto.reais.toFixed(2).replace('.',',')}</b><small>{v.gasto.chamadas} pedido(s) à IA</small></div>
        </div>
        <p className="hint">Ao chegar no teto o agente para de usar a IA até o mês virar. O valor é uma estimativa feita pelo servidor; o valor cobrado de verdade aparece na sua conta do Google. Quando o vídeo tem legenda automática do YouTube, o agente usa a legenda e gasta bem menos.</p>
      </section>
    </>}

    {parte==='fila'&&<>
      <section className="panel">
        <h3>Cortes feitos pelo agente</h3>
        {v.cortes.length?<ul className="ag-cortes">{v.cortes.map(x=><CorteLinha key={x.id} c={x} fazer={a=>{ if(a==='descartar'&&!confirm('Descartar este corte? O arquivo é apagado do servidor.')) return; run(()=>acaoCorte(settings,x.id,a),a==='email'?'E-mail enviado.':a==='agendar'?'Corte agendado.':'Corte descartado.'); }}/>)}</ul>:<div className="empty"><strong>Nenhum corte ainda</strong><p>Aprove um canal e toque em Cortar agora, ou cole o link de um vídeo na parte Cortes.</p></div>}
      </section>
      <section className="panel">
        <h3>Histórico</h3>
        {v.log.length?<ul className="ag-log">{v.log.map((l,i)=><li key={i} className={l.tipo}><time>{quando(l.t)}</time><span>{l.texto}</span></li>)}</ul>:<p className="hint">Nada aconteceu ainda.</p>}
      </section>
    </>}
  </div>;
}
