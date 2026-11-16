import { useEffect, useRef, useState } from 'react';
import { Plus, Loader2, Users, Map, BookOpen, Clapperboard, CheckCircle2, Eye, ArrowLeft, Save, Trash2, Bone, Mic, Play, Pause } from 'lucide-react';
import { useApp } from '../state';
import { useCfg, useServidor, PrecisaServidor, erroTexto } from '../components/Servidor2';
import { VOZES } from '../lib/dublagem';
import { listarSeries, criarSerie, obterSerie, criarPersonagem, salvarPersonagem, folhaPersonagem, previaPersonagem, criarCenario, previaCenario,
  salvarBiblia, criarEpisodio, trazerMudancas, criarTemporada, lerRig, pedirPose, lerJob, visemasDoAudio, nomePose, CABELOS, CORPOS, ACESSORIOS, TIPOS_CENARIO, HORARIOS,
  type Personagem, type Serie, type EntradaBiblia, type Rig, type PedidoPose, type Visemas } from '../lib/series';
import { enviarArquivo } from '../lib/api';
import ModelagemIA from '../components/ModelagemIA';

const NOVO_P:Personagem['dados']={nome:'',descricao:'',pele:'#e8b98f',cabelo:'#3b2a1a',olhos:'#2b1d0e',roupa:'#3a86ff',calca:'#1d3557',sapato:'#222222',cabelo_tipo:'curto',corpo:'medio',acessorio:'nenhum',altura:1,voz:'Puck'};
const ESTADO_B:Record<string,[string,string]>={proposta:['para aprovar','warn'],aprovada:['vale na história','ok'],rejeitada:['rejeitada','bad']};

function Cor({label,v,on}:{label:string;v:string;on:(v:string)=>void}){
  return <label className="cor-campo">{label}<input type="color" value={v} onChange={e=>on(e.target.value)}/></label>;
}

function EditorPersonagem({serie,p,onPronto}:{serie:string;p?:Personagem;onPronto:()=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const [d,setD]=useState<Personagem['dados']>(p?.dados||NOVO_P);
  const [png,setPng]=useState(''); const [busy,setBusy]=useState('');
  const set=(x:Partial<Personagem['dados']>)=>setD(v=>({...v,...x}));
  const ver=async(dd=d)=>{ setBusy('ver'); try{ setPng((await previaPersonagem(cfg,dd)).png); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } };
  useEffect(()=>{ ver(); },[]); // eslint-disable-line react-hooks/exhaustive-deps
  const salvar=async()=>{ if(!d.nome.trim()){ toast('Dê um nome ao personagem.','erro'); return; } setBusy('salvar');
    try{ if(p) await salvarPersonagem(cfg,p.id,{dados:d,versao:p.versao}); else await criarPersonagem(cfg,serie,d); toast(p?'Personagem salvo (versão nova; episódios já feitos não mudam).':'Personagem criado.','ok'); onPronto(); }
    catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } };
  return <div className="ser-editor">
    <div className="ser-editor-grid">
      <div>
        <div className="small-grid">
          <label>Nome<input value={d.nome} onChange={e=>set({nome:e.target.value})} placeholder="Ex.: Ana"/></label>
          <label>Voz<select value={d.voz} onChange={e=>set({voz:e.target.value})}>{VOZES.map(([v,n])=><option key={v} value={v}>{v}: {n}</option>)}</select></label>
        </div>
        <label className="mt">Quem é (a IA usa isto para escrever as falas)<input value={d.descricao} onChange={e=>set({descricao:e.target.value})} placeholder="Ex.: menina curiosa de 10 anos, corajosa mas com medo do escuro"/></label>
        <div className="cores mt"><Cor label="Pele" v={d.pele} on={v=>set({pele:v})}/><Cor label="Cabelo" v={d.cabelo} on={v=>set({cabelo:v})}/><Cor label="Olhos" v={d.olhos} on={v=>set({olhos:v})}/>
          <Cor label="Roupa" v={d.roupa} on={v=>set({roupa:v})}/><Cor label="Calça" v={d.calca} on={v=>set({calca:v})}/><Cor label="Sapato" v={d.sapato} on={v=>set({sapato:v})}/></div>
        <div className="small-grid mt">
          <label>Cabelo<select value={d.cabelo_tipo} onChange={e=>set({cabelo_tipo:e.target.value})}>{CABELOS.map(([k,n])=><option key={k} value={k}>{n}</option>)}</select></label>
          <label>Corpo<select value={d.corpo} onChange={e=>set({corpo:e.target.value})}>{CORPOS.map(([k,n])=><option key={k} value={k}>{n}</option>)}</select></label>
          <label>Acessório<select value={d.acessorio} onChange={e=>set({acessorio:e.target.value})}>{ACESSORIOS.map(([k,n])=><option key={k} value={k}>{n}</option>)}</select></label>
          <label>Altura<input type="range" min={0.75} max={1.15} step={0.05} value={d.altura} onChange={e=>set({altura:+e.target.value})}/></label>
        </div>
        <div className="row-gap left mt">
          <button className="subtle sm" disabled={!!busy} onClick={()=>ver()}>{busy==='ver'?<Loader2 size={14} className="spin"/>:<Eye size={14}/>} Ver como fica</button>
          <button className="primary sm" disabled={!!busy} onClick={salvar}>{busy==='salvar'?<Loader2 size={14} className="spin"/>:<Save size={14}/>} {p?'Salvar mudanças':'Criar personagem'}</button>
        </div>
      </div>
      <div className="ser-folha">{png?<img src={png} alt={`Folha de modelo de ${d.nome||'personagem'}`}/>:<div className="hint">{busy==='ver'?'Desenhando…':'Toque em "Ver como fica".'}</div>}</div>
    </div>
  </div>;
}

const espera=(ms:number)=>new Promise(r=>setTimeout(r,ms));
const textoPose=(d:PedidoPose)=>[d.pose&&nomePose(d.pose),d.objeto&&`segurando ${nomePose(d.objeto).toLowerCase()}`,`rosto ${nomePose(d.expressao).toLowerCase()}`].filter(Boolean).join(', ');

/** S3: o rig 2D do personagem (peças, poses, objetos), prévia real de pose pelo motor e prévia da boca com uma fala gravada. */
function RigPainel({s,p,recarregar}:{s:Serie;p:Personagem;recarregar:()=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const [rig,setRig]=useState<Rig|null>(null); const [erro,setErro]=useState('');
  const [ped,setPed]=useState<PedidoPose>({pose:'',objeto:'',expressao:'neutro'});
  const [png,setPng]=useState(''); const [etapa,setEtapa]=useState(''); const vivo=useRef(true);
  useEffect(()=>{ vivo.current=true; lerRig(cfg,p.id).then(setRig).catch(e=>setErro(erroTexto(e))); return ()=>{ vivo.current=false; }; },[p.id,p.versao]); // eslint-disable-line react-hooks/exhaustive-deps
  const aprovadas=s.biblia.filter(b=>b.tipo==='pose'&&b.alvo===p.id&&b.estado==='aprovada');
  const ver=async(d=ped)=>{ setPng(''); setEtapa('Pedindo ao servidor…');
    try{
      for(let i=0;i<150&&vivo.current;i++){
        const r=await pedirPose(cfg,p.id,d);
        if(r.png){ setPng(r.png); setEtapa(''); return; }
        if(r.status==='falhou'||r.status==='cancelado'){ setEtapa(''); toast('O motor não conseguiu desenhar: '+(r.erro||r.status),'erro'); return; }
        setEtapa(r.status==='rodando'?(r.etapa||'Desenhando com o motor 2D'):'Na fila do celular (um trabalho pesado por vez)');
        if(r.job){ for(let k=0;k<20&&vivo.current;k++){ await espera(1500); const j=await lerJob(cfg,r.job); if(['concluido','falhou','cancelado'].includes(j.status)) break; setEtapa(j.status==='rodando'?(j.etapa||'Desenhando'):'Na fila do celular'); } }
        else await espera(1500);
      }
    }catch(e){ setEtapa(''); toast(erroTexto(e),'erro'); } };
  const aprovar=async()=>{ try{ await salvarBiblia(cfg,s.id,[{tipo:'pose',alvo:p.id,texto:`Pose aprovada de ${p.nome}: ${textoPose(ped)}.`,estado:'aprovada'}]); toast('Pose guardada na história da série.','ok'); recarregar(); }catch(e){ toast(erroTexto(e),'erro'); } };
  const recuperar=(t:string)=>{ const b=rig?.biblioteca; if(!b) return;
    const pose=b.poses.find(x=>t.includes(nomePose(x)))||''; const objeto=b.objetos.find(x=>t.includes('segurando '+nomePose(x).toLowerCase()))||'';
    const expressao=['neutro','feliz','triste','bravo','surpreso','preocupado'].find(x=>t.includes('rosto '+nomePose(x).toLowerCase()))||'neutro';
    const d={pose,objeto,expressao}; setPed(d); ver(d); };
  if(erro) return <p className="hint bad">{erro}</p>;
  if(!rig) return <p className="hint"><Loader2 size={13} className="spin"/> Lendo o esqueleto do personagem…</p>;
  const b=rig.biblioteca;
  return <div className="rig-painel">
    <p className="hint">Esqueleto <b>{b.rig_id} v{b.versao_rig}</b> • {Object.keys(b.pecas).length} peças desenhadas • assinatura <code>{b.assinatura.slice(0,10)}</code> (mesma assinatura = mesmas peças em todo episódio).</p>
    <p className="hint warn">Modo não suportado: vista de perfil ou de 3/4, pernas com IK e leitura de fonemas. {b.limites}</p>
    <div className="small-grid">
      <label>Pose<select value={ped.pose} onChange={e=>setPed({...ped,pose:e.target.value})}><option value="">Em pé (normal)</option>{b.poses.map(x=><option key={x} value={x}>{nomePose(x)}</option>)}</select></label>
      <label>Segurando<select value={ped.objeto} onChange={e=>setPed({...ped,objeto:e.target.value})}><option value="">Nada</option>{b.objetos.map(x=><option key={x} value={x}>{nomePose(x)}</option>)}</select></label>
      <label>Rosto<select value={ped.expressao} onChange={e=>setPed({...ped,expressao:e.target.value})}>{['neutro','feliz','triste','bravo','surpreso','preocupado'].map(x=><option key={x} value={x}>{nomePose(x)}</option>)}</select></label>
    </div>
    <div className="row-gap left mt">
      <button className="subtle sm" disabled={!!etapa} onClick={()=>ver()}>{etapa?<Loader2 size={14} className="spin"/>:<Eye size={14}/>} Ver a pose (desenho real do motor)</button>
      {png&&<button className="subtle sm" onClick={aprovar}><CheckCircle2 size={14}/> Aprovar esta pose</button>}
    </div>
    {etapa&&<p className="hint">{etapa}</p>}
    {png&&<img className="rig-pose" src={png} alt={`${p.nome}: ${textoPose(ped)}`}/>}
    <div className="field-label mt">Ações que o motor sabe fazer</div>
    <p className="hint">{b.acoes.join(', ')}. Alcance do braço: {b.alcance.join(', ')}.</p>
    {aprovadas.length>0&&<><div className="field-label mt">Poses e figurino aprovados</div>
      <ul className="eps">{aprovadas.map(a=><li key={a.id}><span>{a.texto}</span><button className="link-btn" onClick={()=>recuperar(a.texto)}>Ver de novo</button></li>)}</ul></>}
    <Boca p={p}/>
  </div>;
}

/** Prévia da boca: envia uma fala gravada (WAV/MP3), o servidor calcula a abertura da boca quadro a quadro e o site mostra em sincronia com o áudio. */
function Boca({p}:{p:Personagem}){
  const {toast}=useApp(); const cfg=useCfg();
  const [arq,setArq]=useState<File|null>(null); const [texto,setTexto]=useState(''); const [v,setV]=useState<Visemas|null>(null);
  const [busy,setBusy]=useState(false); const [url,setUrl]=useState(''); const [t,setT]=useState(0); const [tocando,setTocando]=useState(false);
  const audio=useRef<HTMLAudioElement>(null);
  useEffect(()=>()=>{ if(url) URL.revokeObjectURL(url); },[url]);
  useEffect(()=>{ if(!tocando) return; let id=0; const f=()=>{ setT(audio.current?.currentTime||0); id=requestAnimationFrame(f); }; id=requestAnimationFrame(f); return ()=>cancelAnimationFrame(id); },[tocando]);
  const calcular=async()=>{ if(!arq) return; setBusy(true);
    try{ const a=await enviarArquivo(cfg,arq,arq.name); const r=await visemasDoAudio(cfg,a.id,texto); setV(r); setUrl(u=>{ if(u) URL.revokeObjectURL(u); return URL.createObjectURL(arq); }); }
    catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } };
  const i=v?Math.min(v.niveis.length-1,Math.floor(t/v.passo)):0; const nivel=v?.niveis[i]??0;
  return <div className="boca mt">
    <div className="field-label"><Mic size={13}/> Voz e boca de {p.nome}</div>
    <p className="hint">Voz ligada: <b>{p.dados.voz}</b>. Grave ou aprove a fala no Estúdio de Vozes, baixe o WAV do take e escolha aqui para ver como a boca vai mexer.</p>
    <div className="small-grid">
      <label>Fala gravada (WAV ou MP3)<input type="file" accept="audio/*" onChange={e=>{ setArq(e.target.files?.[0]||null); setV(null); }}/></label>
      <label>O que ela diz (ajuda nas vogais)<input value={texto} onChange={e=>setTexto(e.target.value)} placeholder="Ex.: Quem está aí?"/></label>
    </div>
    <div className="row-gap left mt"><button className="subtle sm" disabled={!arq||busy} onClick={calcular}>{busy?<Loader2 size={14} className="spin"/>:<Mic size={14}/>} Calcular a boca no servidor</button></div>
    {v&&<>
      <div className="visemas" role="img" aria-label={`Abertura da boca ao longo de ${v.dur} segundos`}>
        {v.niveis.map((n,k)=><span key={k} className={k===i&&tocando?'agora':''} style={{height:`${10+n*22}%`}}/>)}
      </div>
      <div className="row-gap left">
        <button className="subtle sm" onClick={()=>{ const a=audio.current; if(!a) return; if(a.paused){ a.play(); setTocando(true); } else { a.pause(); setTocando(false); } }}>{tocando?<Pause size={14}/>:<Play size={14}/>} {tocando?'Pausar':'Tocar com a boca'}</button>
        <span className="tag">boca: {v.formas[nivel]||nivel}</span><span className="muted">{t.toFixed(1)} s de {v.dur} s • {v.modo}</span>
      </div>
      <audio ref={audio} src={url} onEnded={()=>setTocando(false)} hidden/>
      <p className="hint">{v.limites}</p>
    </>}
  </div>;
}

function Personagens({s,recarregar}:{s:Serie;recarregar:()=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const [edit,setEdit]=useState<string>(''); const [rigAberto,setRigAberto]=useState('');
  const [folhas,setFolhas]=useState<Record<string,string>>({});
  useEffect(()=>{ s.personagens.forEach(p=>{ if(!folhas[p.id+p.versao]) folhaPersonagem(cfg,p.id).then(r=>setFolhas(f=>({...f,[p.id+p.versao]:r.png}))).catch(()=>{}); }); },[s.personagens]); // eslint-disable-line react-hooks/exhaustive-deps
  return <section className="panel">
    <div className="section-head"><h2><Users size={17}/> Personagens</h2><button className="subtle sm" onClick={()=>setEdit(edit==='novo'?'':'novo')}><Plus size={14}/> Novo</button></div>
    <p className="hint">Cada personagem é desenhado em partes com juntas: anda, aponta, acena, se assusta e mexe a boca com a própria voz. Por enquanto só de frente (sem perfil).</p>
    <ModelagemIA compacto titulo="Criar personagem com a IA" contexto="series.personagem" tipos={['personagem']} destinos={['personagem']} serieId={s.id} onAplicado={()=>recarregar()}/>
    {edit==='novo'&&<EditorPersonagem serie={s.id} onPronto={()=>{ setEdit(''); recarregar(); }}/>}
    <div className="ser-cards">{s.personagens.map(p=><div key={p.id} className={'ser-card'+(p.aprovado?' ok':'')}>
      {folhas[p.id+p.versao]?<img src={folhas[p.id+p.versao]} alt={`Folha de ${p.nome}`}/>:<div className="ser-img-vazia"><Loader2 size={16} className="spin"/></div>}
      <div className="ser-card-txt"><b>{p.nome}</b> <span className="muted">versão {p.versao} • voz {p.dados.voz}</span>
        {p.dados.descricao&&<small>{p.dados.descricao}</small>}
        <div className="row-gap left">
          <button className="link-btn" onClick={()=>setEdit(edit===p.id?'':p.id)}>Mudar</button>
          <button className="link-btn" onClick={()=>setRigAberto(rigAberto===p.id?'':p.id)}><Bone size={12}/> Esqueleto, poses e boca</button>
          <button className="link-btn" onClick={async()=>{ try{ await salvarPersonagem(cfg,p.id,{aprovado:!p.aprovado}); recarregar(); }catch(e){ toast(erroTexto(e),'erro'); } }}>{p.aprovado?'Tirar aprovação':'Aprovar o visual'}</button>
          {p.aprovado&&<span className="tag ok"><CheckCircle2 size={11}/> aprovado</span>}
        </div></div>
      {edit===p.id&&<EditorPersonagem serie={s.id} p={p} onPronto={()=>{ setEdit(''); recarregar(); }}/>}
      {rigAberto===p.id&&<RigPainel s={s} p={p} recarregar={recarregar}/>}
    </div>)}</div>
    {!s.personagens.length&&edit!=='novo'&&<p className="hint">Nenhum personagem ainda. Crie pelo menos um para fazer o primeiro episódio.</p>}
  </section>;
}

function Cenarios({s,recarregar}:{s:Serie;recarregar:()=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const [novo,setNovo]=useState(false); const [d,setD]=useState({nome:'',tipo:'parque',horario:'dia'}); const [png,setPng]=useState<Record<string,string>>({});
  useEffect(()=>{ s.cenarios.forEach(c=>{ const k=c.id+c.versao; if(!png[k]) previaCenario(cfg,c.dados,s.formato).then(r=>setPng(x=>({...x,[k]:r.png}))).catch(()=>{}); }); },[s.cenarios]); // eslint-disable-line react-hooks/exhaustive-deps
  return <section className="panel">
    <div className="section-head"><h2><Map size={17}/> Cenários</h2><button className="subtle sm" onClick={()=>setNovo(!novo)}><Plus size={14}/> Novo</button></div>
    <ModelagemIA compacto titulo="Criar cenário com a IA" contexto="series.cenario" tipos={['cenario']} destinos={['cenario']} serieId={s.id} onAplicado={()=>recarregar()}/>
    {novo&&<div className="small-grid">
      <label>Nome<input value={d.nome} onChange={e=>setD({...d,nome:e.target.value})} placeholder="Ex.: Sala da casa"/></label>
      <label>Lugar<select value={d.tipo} onChange={e=>setD({...d,tipo:e.target.value})}>{TIPOS_CENARIO.map(([k,n])=><option key={k} value={k}>{n}</option>)}</select></label>
      <label>Hora<select value={d.horario} onChange={e=>setD({...d,horario:e.target.value})}>{HORARIOS.map(([k,n])=><option key={k} value={k}>{n}</option>)}</select></label>
      <button className="primary sm" disabled={!d.nome.trim()} onClick={async()=>{ try{ await criarCenario(cfg,s.id,d); setNovo(false); setD({nome:'',tipo:'parque',horario:'dia'}); recarregar(); }catch(e){ toast(erroTexto(e),'erro'); } }}>Criar cenário</button>
    </div>}
    <div className="ser-cards">{s.cenarios.map(c=><div key={c.id} className="ser-card cen">
      {png[c.id+c.versao]?<img src={png[c.id+c.versao]} alt={`Cenário ${c.nome}`}/>:<div className="ser-img-vazia"><Loader2 size={16} className="spin"/></div>}
      <div className="ser-card-txt"><b>{c.nome}</b><span className="muted">{TIPOS_CENARIO.find(t=>t[0]===c.dados.tipo)?.[1]} • {HORARIOS.find(t=>t[0]===c.dados.horario)?.[1]}</span></div>
    </div>)}</div>
    {!s.cenarios.length&&!novo&&<p className="hint">Sem cenário, o primeiro episódio usa um parque.</p>}
  </section>;
}

function Biblia({s,recarregar}:{s:Serie;recarregar:()=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const [texto,setTexto]=useState(''); const [alvo,setAlvo]=useState('');
  const salvar=async(e:Partial<EntradaBiblia&{apagar:boolean}>[],msg='')=>{ try{ await salvarBiblia(cfg,s.id,e); if(msg) toast(msg,'ok'); recarregar(); }catch(x){ toast(erroTexto(x),'erro'); } };
  const lista=s.biblia.filter(b=>b.estado!=='rejeitada');
  return <section className="panel">
    <div className="section-head"><h2><BookOpen size={17}/> O que já é verdade na história</h2></div>
    <p className="hint">O Agente 3 lê só o que está aprovado aqui antes de escrever cada episódio. Se um fato aprovado mudar, o antigo fica guardado e o novo entra como mudança.</p>
    <ul className="biblia">{lista.map(b=><li key={b.id}>
      <span className={'tag '+(ESTADO_B[b.estado]?.[1]||'')}>{ESTADO_B[b.estado]?.[0]||b.estado}</span>
      <span className="biblia-txt">{b.alvo&&<b>{s.personagens.find(p=>p.id===b.alvo)?.nome||b.alvo}: </b>}{b.texto}{b.substitui&&<small className="muted"> (mudou)</small>}</span>
      {b.estado==='proposta'&&<><button className="link-btn" onClick={()=>salvar([{...b,estado:'aprovada'}],'Aprovado: vale para os próximos episódios.')}>Aprovar</button>
        <button className="link-btn" onClick={()=>salvar([{...b,estado:'rejeitada'}])}>Rejeitar</button></>}
      <button className="icon-btn sm" aria-label="Tirar da história" onClick={()=>salvar([{id:b.id,apagar:true}])}><Trash2 size={13}/></button>
    </li>)}</ul>
    <div className="ag-add mt">
      <select value={alvo} onChange={e=>setAlvo(e.target.value)} aria-label="Sobre quem"><option value="">Sobre a história</option>{s.personagens.map(p=><option key={p.id} value={p.id}>{p.nome}</option>)}</select>
      <input value={texto} onChange={e=>setTexto(e.target.value)} placeholder="Ex.: Ana tem medo do escuro"/>
      <button className="subtle sm" disabled={!texto.trim()} onClick={()=>{ salvar([{tipo:'fato',alvo,texto,estado:'aprovada'}]); setTexto(''); }}><Plus size={14}/> Anotar</button>
    </div>
  </section>;
}

function Episodios({s,recarregar}:{s:Serie;recarregar:()=>void}){
  const {toast,go}=useApp(); const cfg=useCfg();
  const [d,setD]=useState({titulo:'',resumo:'',produzir:true,modo_aprovacao:'assistido' as 'assistido'|'supervisionado',temporada_id:''}); const [busy,setBusy]=useState('');
  const temps=[...s.temporadas].sort((a,b)=>a.ordem-b.ordem);
  const grupos=[...temps.map(t=>({id:t.id,titulo:t.titulo,eps:s.episodios.filter(e=>e.temporada_id===t.id)})),
    {id:'',titulo:'Sem temporada',eps:s.episodios.filter(e=>!temps.some(t=>t.id===e.temporada_id))}].filter(g=>g.eps.length||(g.id&&g.id===d.temporada_id));
  return <section className="panel">
    <div className="section-head"><h2><Clapperboard size={17}/> Episódios</h2></div>
    <div className="row-gap left">
      <button className="subtle sm" disabled={!!busy} onClick={async()=>{ setBusy('temp'); try{ const t=await criarTemporada(cfg,s.id,{}); setD(x=>({...x,temporada_id:t.id})); toast(`${t.titulo} criada. Os próximos episódios entram nela.`,'ok'); recarregar(); }catch(x){ toast(erroTexto(x),'erro'); }finally{ setBusy(''); } }}><Plus size={14}/> Nova temporada</button>
      <span className="muted">{s.temporadas.length||1} temporada(s) • {s.episodios.length} episódio(s). Cada episódio é um projeto só (não copia nada).</span>
    </div>
    {grupos.map(g=><div key={g.id||'sem'}>
      {grupos.length>1&&<div className="field-label mt">{g.titulo}</div>}
      <ul className="eps">{g.eps.map(e=><li key={e.id}>
      <b>Ep. {e.ordem}: {e.titulo}</b><span className="muted">{e.resumo}</span>
      <span className="tag">{e.status_nome||'rascunho'}</span>
      <div className="row-gap left">
        <button className="link-btn" onClick={()=>go(['ready_for_review','approved','posted','queued_to_publish'].includes(e.status)?'revisar':'ia',e.projeto_id,'criar')}>Abrir</button>
        <button className="link-btn" disabled={!!busy} onClick={async()=>{ setBusy(e.id); try{ const r=await trazerMudancas(cfg,e.id); const n=r.biblia.filter(b=>b.estado==='proposta').length; toast(n?`${n} mudança(s) esperando você aprovar na história.`:'Este episódio não trouxe mudanças.','ok'); recarregar(); }catch(x){ toast(erroTexto(x),'erro'); }finally{ setBusy(''); } }}>Trazer mudanças para a história</button>
      </div>
    </li>)}</ul>
    </div>)}
    <ModelagemIA compacto titulo="Criar episódio com a IA" contexto="series.episodio" tipos={['episodio']} destinos={['episodio']} serieId={s.id}
      assets={s.personagens.map(p=>({id:p.id,tipo:'character',nome:p.nome,descricao:p.dados.descricao}))} onAplicado={()=>recarregar()}/>
    <div className="field-label mt">Novo episódio {s.episodios.length+1}</div>
    <label>Título<input value={d.titulo} onChange={e=>setD({...d,titulo:e.target.value})} placeholder={`Episódio ${s.episodios.length+1}`}/></label>
    <label className="mt">O que acontece<textarea rows={3} value={d.resumo} onChange={e=>setD({...d,resumo:e.target.value})} placeholder="Ex.: Ana ouve um barulho no sótão e convence Beto a subir com ela."/></label>
    {temps.length>0&&<label className="mt">Temporada<select value={d.temporada_id||temps[temps.length-1].id} onChange={e=>setD({...d,temporada_id:e.target.value})}>{temps.map(t=><option key={t.id} value={t.id}>{t.titulo}</option>)}</select></label>}
    <label className="check mt"><input type="checkbox" checked={d.produzir} onChange={e=>setD({...d,produzir:e.target.checked})}/> Já começar a produzir no celular</label>
    <label className="mt">Quem confere<select value={d.modo_aprovacao} onChange={e=>setD({...d,modo_aprovacao:e.target.value as 'assistido'|'supervisionado'})}><option value="assistido">Aprovo o roteiro e depois o vídeo</option><option value="supervisionado">Aprovo só o vídeo pronto</option></select></label>
    <div className="row-gap left mt"><button className="primary" disabled={!!busy||!d.resumo.trim()||!s.personagens.length} onClick={async()=>{ setBusy('ep');
      try{ await criarEpisodio(cfg,s.id,d); toast(d.produzir?'Episódio criado. O Agente 3 já começou.':'Episódio criado.','ok'); setD({...d,titulo:'',resumo:''}); recarregar(); }catch(x){ toast(erroTexto(x),'erro'); }finally{ setBusy(''); } }}>
      {busy==='ep'?<Loader2 size={15} className="spin"/>:<Plus size={15}/>} Criar episódio</button></div>
    {!s.personagens.length&&<p className="hint warn">Crie um personagem antes do primeiro episódio.</p>}
  </section>;
}

export default function Series(){
  const {settings,toast,rotaExtra:extra,go}=useApp(); const cfg=useCfg();
  const lista=useServidor(listarSeries,0,[settings.servidorSessao]);
  const aberta=useServidor(c=>extra?obterSerie(c,extra):Promise.resolve(null),0,[extra]);
  const [nova,setNova]=useState({titulo:'',genero:'',tom:'',publico:'',formato:'9:16',estilo:'animado2d' as 'animado2d'|'animado3d'});
  const [busy,setBusy]=useState(false);
  if(!settings.servidor) return <PrecisaServidor oque="as séries animadas"/>;
  const s=aberta.dados;
  if(extra){
    if(!s) return <section className="panel">{aberta.erro?<p className="hint bad">{aberta.erro}</p>:<p className="hint"><Loader2 size={14} className="spin"/> Abrindo a série…</p>}</section>;
    const rec=()=>aberta.recarregar();
    return <>
      <section className="panel"><button className="link-btn" onClick={()=>go('series','','criar')}><ArrowLeft size={13}/> Todas as séries</button>
        <h2 className="mt">{s.titulo}</h2><p className="hint">{[s.genero,s.tom&&`tom ${s.tom}`,s.publico&&`para ${s.publico}`,s.formato,s.estilo==='animado3d'?'personagens em 3D (beta)':'desenho 2D'].filter(Boolean).join(' • ')}</p></section>
      <Personagens s={s} recarregar={rec}/>
      <Cenarios s={s} recarregar={rec}/>
      <Biblia s={s} recarregar={rec}/>
      <Episodios s={s} recarregar={rec}/>
    </>;
  }
  return <>
    <section className="panel">
      <div className="section-head"><h2>Nova série</h2></div>
      <p className="hint">Uma série tem elenco fixo, cenários e uma história que continua. Cada episódio vira um vídeo do Agente 3 com os mesmos personagens.</p>
      <ModelagemIA contexto="series.nova" tipos={['serie','pacote']} destinos={['serie','biblioteca']} onAplicado={r=>{ if(r.serie_id) go('series',r.serie_id,'criar'); }}/>
      <div className="field-label mt">Ou preencha você mesmo</div>
      <div className="small-grid">
        <label>Nome da série<input value={nova.titulo} onChange={e=>setNova({...nova,titulo:e.target.value})} placeholder="Ex.: A Casa do Sótão"/></label>
        <label>Gênero<input value={nova.genero} onChange={e=>setNova({...nova,genero:e.target.value})} placeholder="Ex.: mistério infantil"/></label>
        <label>Tom<input value={nova.tom} onChange={e=>setNova({...nova,tom:e.target.value})} placeholder="Ex.: leve e engraçado"/></label>
        <label>Público<input value={nova.publico} onChange={e=>setNova({...nova,publico:e.target.value})} placeholder="Ex.: crianças de 8 a 12 anos"/></label>
        <label>Formato<select value={nova.formato} onChange={e=>setNova({...nova,formato:e.target.value})}><option value="9:16">Vertical (Shorts, Reels, TikTok)</option><option value="16:9">Deitado (YouTube)</option><option value="1:1">Quadrado</option></select></label>
        <label>Visual dos personagens<select value={nova.estilo} onChange={e=>setNova({...nova,estilo:e.target.value as 'animado2d'|'animado3d'})}><option value="animado2d">Desenho 2D (mais rápido)</option><option value="animado3d">3D de blocos (beta, bem mais lento)</option></select></label>
      </div>
      <div className="row-gap left mt"><button className="primary" disabled={busy||!nova.titulo.trim()} onClick={async()=>{ setBusy(true); try{ const r=await criarSerie(cfg,nova); go('series',r.id,'criar'); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }}>{busy?<Loader2 size={15} className="spin"/>:<Plus size={15}/>} Criar série</button></div>
    </section>
    {lista.erro&&<section className="panel"><p className="hint bad">{lista.erro}</p></section>}
    {(lista.dados?.series||[]).length>0&&<section className="panel"><div className="section-head"><h2>Suas séries</h2></div>
      <ul className="eps">{lista.dados!.series.map(x=><li key={x.id}><button className="link-btn" onClick={()=>go('series',x.id,'criar')}><b>{x.titulo}</b></button>
        <span className="muted">{x.personagens} personagem(ns) • {x.episodios} episódio(s){x.genero?` • ${x.genero}`:''}</span></li>)}</ul></section>}
  </>;
}
