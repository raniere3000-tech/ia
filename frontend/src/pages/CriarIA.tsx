import { useEffect, useState } from 'react';
import { Wand2, Lightbulb, Loader2, ArrowUp, ArrowDown, Copy, Trash2, Lock, Unlock, Plus, Play, CalendarClock, Save, ClipboardPaste, ExternalLink } from 'lucide-react';
import { useApp } from '../state';
import { HelpButton } from '../components/Help';
import { useCfg, useServidor, PrecisaServidor, erroTexto } from '../components/Servidor2';
import { GradeEstilos } from './Galeria';
import { Prontidao, CriarRapido } from '../components/Prontidao';
import SkillPicker from '../components/SkillPicker';
import VozGravada from '../components/VozGravada';
import Diretor from '../components/Diretor';
import { catalogo, ideias as pedirIdeias, gerarRoteiro, novoVideo, obterProjeto, salvarStoryboard, aprovarRoteiro, type Briefing, type Cena, type Roteiro, type Ideia, type Plano, type Chave } from '../lib/api';

const REDES:[string,string][]=[['youtube','YouTube'],['instagram','Instagram'],['facebook','Facebook'],['tiktok','TikTok'],['kwai','Kwai']];
let seq=0; const novaId=()=>'n'+Date.now().toString(36)+(seq++);

/** Campos do briefing usados também no modo Automático. */
export function CamposBriefing({b,set,cat}:{b:Partial<Briefing>;set:(p:Partial<Briefing>)=>void;cat:{vozes:string[];tipos:string[]}|null}){
  return <><div className="small-grid">
    <label>Duração final (segundos)<input type="number" min={10} max={600} value={b.duracao_alvo||45} onChange={e=>set({duracao_alvo:+e.target.value})}/></label>
    <label>Formato<select value={b.formato||'9:16'} onChange={e=>set({formato:e.target.value})}><option value="9:16">Em pé (Shorts, Reels, TikTok)</option><option value="16:9">Deitado (YouTube)</option><option value="1:1">Quadrado (feed)</option></select></label>
    <label>Voz do narrador<select value={b.voz||'Puck'} onChange={e=>set({voz:e.target.value})}>{[...(cat?.vozes||['Puck']),'nenhuma'].map(v=><option key={v} value={v}>{v==='nenhuma'?'Sem narração':v}</option>)}</select></label>
    <label>Ritmo da fala<select value={b.ritmo||'agil'} onChange={e=>set({ritmo:e.target.value})}><option value="calmo">Calmo</option><option value="normal">Normal</option><option value="agil">Ágil (bom para vídeo curto)</option><option value="rapido">Rápido</option></select></label>
    <label>Imagens de cada cena<select value={b.imagens||'nenhuma'} onChange={e=>set({imagens:e.target.value})}><option value="busca">Fotos reais remodeladas no estilo (grátis)</option><option value="nenhuma">Sem fotos (só desenhos do estilo)</option><option value="gemini">Imagem criada por IA em cada cena (tem custo)</option></select></label>
    <label>Quem confere<select value={b.modo_aprovacao||'assistido'} onChange={e=>set({modo_aprovacao:e.target.value as Briefing['modo_aprovacao']})}><option value="assistido">Aprovo o roteiro e depois o vídeo</option><option value="supervisionado">Aprovo só o vídeo pronto</option></select></label>
   </div>
   <details className="mt"><summary>Mais opções (nicho, público, número de cenas, limite de gasto)</summary><div className="small-grid">
    <label>Nicho<input value={b.nicho||''} onChange={e=>set({nicho:e.target.value})} placeholder="Curiosidades, Games, História..."/></label>
    <label>Tipo<select value={b.tipo||'curiosidades'} onChange={e=>set({tipo:e.target.value})}>{(cat?.tipos||['curiosidades']).map(t=><option key={t}>{t}</option>)}</select></label>
    <label>Público<input value={b.publico||''} onChange={e=>set({publico:e.target.value})} placeholder="Ex.: jovens que gostam de ciência"/></label>
    <label>Cenas<input type="number" min={2} max={30} value={b.cenas_qtd||6} onChange={e=>set({cenas_qtd:+e.target.value})}/></label>
    <label>Limite de gasto com IA por vídeo (R$)<input type="number" min={0} step={0.5} value={b.orcamento_max??2} onChange={e=>set({orcamento_max:+e.target.value})}/></label>
   </div></details></>;
}

export function Destinos({b,set}:{b:Partial<Briefing>;set:(p:Partial<Briefing>)=>void}){
  const d=b.destinos||{redes:[],quando:'proximo'};
  return <>
    <div className="field-label">Depois de aprovado, publicar em</div>
    <div className="chips">{REDES.map(([id,nome])=><button key={id} className={'chip '+(d.redes.includes(id)?'on':'')} onClick={()=>set({destinos:{...d,redes:d.redes.includes(id)?d.redes.filter(x=>x!==id):[...d.redes,id]}})}>{nome}</button>)}</div>
    <p className="hint">Nada é publicado sem a sua aprovação do vídeo final. As redes podem ser trocadas na hora de aprovar.</p>
  </>;
}

const TIPOS_PLANO:[Plano['plano'],string][]=[['WS','Aberto'],['MS','Médio'],['CU','Close'],['ECU','Close extremo']];
/** Planos da cena: a câmera corta entre eles enquanto o narrador fala (estilo documentário). Vazio = o servidor escolhe. */
const PONTO_PADRAO:[Chave,Chave]=[{t:0,zoom:1,x:0.5,y:0.45},{t:1,zoom:1.6,x:0.5,y:0.4}];
/** Ângulo da câmera, luz e movimento livre (do começo ao fim do plano) de um plano. */
function PlanoMais({p,mudar}:{p:Plano;mudar:(n:Partial<Plano>)=>void}){
  const ch=p.chaves&&p.chaves.length>=2?p.chaves:null;
  const ponto=(k:number,campo:keyof Chave,v:number)=>{ const base=ch||PONTO_PADRAO; mudar({chaves:base.map((x,j)=>j===k?{...x,[campo]:v}:x)}); };
  const resumo=[p.angulo&&p.angulo!=='normal'?ANGULO_NOME[p.angulo]:'',p.luz?'luz '+LUZ_NOME[p.luz]:'',ch?'movimento livre':''].filter(Boolean).join(', ');
  return <details className="plano-mais"><summary>Ângulo, luz e movimento{resumo?`: ${resumo}`:''}</summary>
   <div className="plano-mais-campos">
    <label>Ângulo<select value={p.angulo||'normal'} onChange={e=>mudar({angulo:e.target.value as Plano['angulo']})}>{Object.entries(ANGULO_NOME).map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label>
    <label>Luz deste plano<select value={p.luz||''} onChange={e=>mudar({luz:e.target.value as Plano['luz']})}><option value="">Igual à cena</option>{Object.entries(LUZ_NOME).map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label>
    <label className="check"><input type="checkbox" checked={!!ch} onChange={e=>mudar({chaves:e.target.checked?PONTO_PADRAO:[]})}/> Movimento livre (escolho onde a câmera começa e termina)</label>
    {ch&&(['Começo','Fim'] as const).map((nome,k)=><div key={nome} className="plano-ponto"><b>{nome}</b>
     <label>Zoom {ch[k].zoom.toFixed(1)}x<input type="range" min={1} max={3} step={0.1} value={ch[k].zoom} onChange={e=>ponto(k,'zoom',+e.target.value)}/></label>
     <label>Esquerda ↔ direita<input type="range" min={0} max={1} step={0.05} value={ch[k].x} onChange={e=>ponto(k,'x',+e.target.value)}/></label>
     <label>Cima ↕ baixo<input type="range" min={0} max={1} step={0.05} value={ch[k].y} onChange={e=>ponto(k,'y',+e.target.value)}/></label>
    </div>)}
   </div></details>;
}
const ANGULO_NOME:Record<string,string>={normal:'De frente',baixo:'De baixo (deixa imponente)',alto:'De cima (deixa pequeno)',inclinado:'Inclinado (tensão)'};
const LUZ_NOME:Record<string,string>={neutra:'Normal',quente:'Quente',fria:'Fria',noite:'Noite',dramatica:'Dramática'};

function EditorPlanos({c,mudar}:{c:Cena;mudar:(p:Partial<Cena>)=>void}){
  const ps=c.planos||[];
  const set=(n:Plano[])=>mudar({planos:n});
  return <div className="sb-planos larga">
    <div className="field-label">Planos da câmera {ps.length?`(${ps.length})`:'(automático: aberto, médio e close)'}</div>
    {ps.map((p,k)=><div key={p.id}><div className="plano-linha">
      <b>{k+1}</b>
      <select value={p.plano} onChange={e=>set(ps.map((x,j)=>j===k?{...x,plano:e.target.value as Plano['plano']}:x))} aria-label="Enquadramento">{TIPOS_PLANO.map(([v,n])=><option key={v} value={v}>{n}</option>)}</select>
      {c.elenco?.length?<select value={p.personagem||''} onChange={e=>set(ps.map((x,j)=>j===k?{...x,personagem:e.target.value}:x))} aria-label="Em quem fica o plano"><option value="">Em quem fala</option>{c.elenco.map(e=><option key={e.personagem_id} value={e.personagem_id}>{e.personagem_id}</option>)}</select>
      :<input value={p.busca||''} onChange={e=>set(ps.map((x,j)=>j===k?{...x,busca:e.target.value}:x))} placeholder="Outra foto (em inglês, opcional)" maxLength={60}/>}
      <button className="icon-btn" onClick={()=>set(ps.filter((_,j)=>j!==k))} aria-label="Tirar plano"><Trash2 size={14}/></button>
    </div><PlanoMais p={p} mudar={n=>set(ps.map((x,j)=>j===k?{...x,...n}:x))}/></div>)}
    {ps.length<6&&<button className="link-btn" onClick={()=>set([...ps,{id:'p'+Math.random().toString(36).slice(2,7),plano:(['WS','MS','CU'] as const)[ps.length%3],busca:''}])}><Plus size={13}/> Plano</button>}
  </div>;
}

function EditorCenas({cenas,set,pid}:{cenas:Cena[];set:(c:Cena[])=>void;pid:string}){
  const mudar=(i:number,p:Partial<Cena>)=>set(cenas.map((c,k)=>k===i?{...c,...p}:c));
  const mover=(i:number,d:number)=>{ const j=i+d; if(j<0||j>=cenas.length) return; const n=[...cenas]; [n[i],n[j]]=[n[j],n[i]]; set(n); };
  return <div className="sb-lista">{cenas.map((c,i)=><div key={c.id} className={'sb-cena'+(c.bloqueada?' bloqueada':'')}>
    <div className="sb-topo"><b>Cena {i+1}</b>
     <span className="grow"/>
     <button className="icon-btn" onClick={()=>mover(i,-1)} disabled={i===0} aria-label="Subir"><ArrowUp size={15}/></button>
     <button className="icon-btn" onClick={()=>mover(i,1)} disabled={i===cenas.length-1} aria-label="Descer"><ArrowDown size={15}/></button>
     <button className="icon-btn" onClick={()=>{ const n=[...cenas]; n.splice(i+1,0,{...c,id:novaId(),bloqueada:false,audio:null,clipe:null}); set(n); }} aria-label="Duplicar"><Copy size={15}/></button>
     <button className="icon-btn" onClick={()=>mudar(i,{bloqueada:!c.bloqueada})} aria-label={c.bloqueada?'Desbloquear':'Bloquear'} title={c.bloqueada?'Bloqueada: a IA não muda esta cena':'Bloquear esta cena'}>{c.bloqueada?<Lock size={15}/>:<Unlock size={15}/>}</button>
     <button className="icon-btn" onClick={()=>set(cenas.filter((_,k)=>k!==i))} disabled={cenas.length<2} aria-label="Apagar"><Trash2 size={15}/></button>
    </div>
    <div className="sb-campos">
     <label>Título na tela<input value={c.titulo} onChange={e=>mudar(i,{titulo:e.target.value})} maxLength={70}/></label>
     <label>Palavra em destaque<input value={c.destaque||''} onChange={e=>mudar(i,{destaque:e.target.value})} maxLength={24}/></label>
     <label className="larga">O que o narrador fala<textarea rows={2} value={c.texto} onChange={e=>mudar(i,{texto:e.target.value})} maxLength={600}/></label>
     <label>Número (opcional)<input type="number" value={c.numero??''} onChange={e=>mudar(i,{numero:e.target.value===''?null:+e.target.value})}/></label>
     <label>Duração em segundos (0 = o tempo da fala)<input type="number" min={0} max={60} value={c.duracao_alvo||0} onChange={e=>mudar(i,{duracao_alvo:+e.target.value})}/></label>
     <label>Foto da cena (busca em inglês)<input value={c.busca||''} onChange={e=>mudar(i,{busca:e.target.value})} maxLength={60} placeholder="Ex.: blue sky sunlight"/></label>
     <label>Clima<select value={c.clima||'nenhum'} onChange={e=>mudar(i,{clima:e.target.value as Cena['clima']})}><option value="nenhum">Nenhum</option><option value="chuva">Chuva</option><option value="neve">Neve</option><option value="poeira">Poeira no ar</option><option value="neblina">Neblina</option></select></label>
     <label>Luz<select value={c.luz||'neutra'} onChange={e=>mudar(i,{luz:e.target.value as Cena['luz']})}><option value="neutra">Normal</option><option value="quente">Quente (fim de tarde)</option><option value="fria">Fria</option><option value="noite">Noite</option><option value="dramatica">Dramática</option></select></label>
     <VozGravada c={c} mudar={p=>mudar(i,p)} pid={pid}/>
     <EditorPlanos c={c} mudar={p=>mudar(i,p)}/>
    </div>
  </div>)}
  <button className="subtle" onClick={()=>set([...cenas,{id:novaId(),titulo:'Nova cena',texto:'',destaque:''}])}><Plus size={15}/> Cena</button>
  </div>;
}

export default function CriarIA(){
  const {settings,toast,go,rotaExtra}=useApp(); const cfg=useCfg();
  const cat=useServidor(catalogo);
  const [b,setB]=useState<Partial<Briefing>>({tema:'',nicho:'Curiosidades',tipo:'curiosidades',duracao_alvo:45,formato:'9:16',cenas_qtd:6,voz:'Puck',imagens:'busca',modo_aprovacao:'assistido',estilo:'documentario',destinos:{redes:[],quando:'proximo'}});
  const set=(p:Partial<Briefing>)=>setB(x=>({...x,...p}));
  const [ideias,setIdeias]=useState<Ideia[]>([]);
  const [roteiro,setRoteiro]=useState<Roteiro|null>(null);
  const [colar,setColar]=useState(false); const [texto,setTexto]=useState(''); const [extrasSk,setExtrasSk]=useState<string[]>([]);
  const [busy,setBusy]=useState('');
  const [quando,setQuando]=useState('');
  const [pid,setPid]=useState(''); const [rev,setRev]=useState(0);
  const [aberto,setAberto]=useState(false);
  // abrir um projeto existente (vindo da revisão: "Editar as cenas")
  useEffect(()=>{ if(!rotaExtra||!settings.servidor) return; obterProjeto(cfg,rotaExtra).then(p=>{
    const d=p.dados as {briefing:Briefing;cenas:Cena[];roteiro:Roteiro|null};
    if(p.tipo!=='agente3') return;
    setPid(p.id); setRev(p.revisao); setB(d.briefing); setRoteiro({...(d.roteiro||{titulo:p.titulo,alternativas:[],gancho:'',publico:'',legenda:'',hashtags:[],fontes:[]}),cenas:d.cenas||[]});
  }).catch(e=>toast(erroTexto(e),'erro')); },[rotaExtra,settings.servidor,cfg,toast]);
  if(!settings.servidor) return <PrecisaServidor oque="A criação com IA"/>;
  const fazer=async(n:string,f:()=>Promise<void>)=>{ setBusy(n); try{ await f(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } };
  const salvarExistente=async()=>{ const m=await salvarStoryboard(cfg,pid,rev,{cenas:roteiro!.cenas,briefing:b,roteiro:{titulo:roteiro!.titulo,legenda:roteiro!.legenda,hashtags:roteiro!.hashtags}}); setRev(m.revisao); return m.revisao; };
  const produzirAgora=(agendar:boolean)=>fazer('prod',async()=>{
    if(!roteiro) return;
    const q=agendar?{quando:'data' as const,data:new Date(quando).getTime()/1000}:{quando:'agora' as const};
    if(pid){ const r=await salvarExistente(); await aprovarRoteiro(cfg,pid,r); if(agendar) toast('Para mudar o horário de um projeto já criado, use Reagendar na Fila.','info'); go('revisar',pid,'fila'); return; }
    const p=await novoVideo(cfg,{briefing:b,roteiro,produzir:true,aprovar_roteiro:true,...q});
    toast(agendar?'Agendado no servidor do celular. Acompanhe em Fila e aprovações.':'Produzindo no servidor do celular. Você recebe um e-mail quando ficar pronto.','ok');
    go('revisar',p.id,'fila');
  });
  const detalhado=aberto||!!pid||!!roteiro;
  return <div className="criar-ia">
   <Prontidao cat={cat.dados}/>
   {!pid&&!roteiro&&<CriarRapido/>}
   {!detalhado&&<button className="subtle" onClick={()=>setAberto(true)}><Wand2 size={15}/> Prefiro ver e editar o roteiro, cena por cena, antes de produzir</button>}
   {detalhado&&<><section className="panel">
    <div className="section-head"><h2><Lightbulb size={17}/> 1. Assunto do vídeo</h2></div>
    <label>Tema ou ideia<input value={b.tema||''} onChange={e=>set({tema:e.target.value})} placeholder="Ex.: Por que o céu é azul?"/></label>
    <div className="row-gap left mt">
     <button className="subtle" disabled={!!busy} onClick={()=>fazer('ideias',async()=>{ const r=await pedirIdeias(cfg,{...b,quantidade:6}); setIdeias(r.ideias); if(!r.ideias.length) toast('A IA não trouxe ideias. Tente outro nicho.','info'); })}>{busy==='ideias'?<Loader2 size={15} className="spin"/>:<Lightbulb size={15}/>} Sugerir pautas originais</button>
    </div>
    {ideias.length>0&&<div className="ideias">{ideias.map(x=><button key={x.titulo} className={'ideia'+(b.tema===x.titulo?' on':'')} onClick={()=>set({tema:x.titulo})}><b>{x.titulo}</b><small>{x.gancho||x.porque}</small>{x.fontes.length>0&&<small className="muted">{x.fontes.length} fonte(s) para conferir</small>}{!x.fato&&<span className="tag warn">opinião</span>}</button>)}</div>}
    <div className="mt"><CamposBriefing b={b} set={set} cat={cat.dados}/></div>
   </section>

   <section className="panel">
    <div className="section-head"><h2><Wand2 size={17}/> 2. Roteiro, cena por cena <HelpButton topic="storyboard"/></h2></div>
    <div className="row-gap left">
     <button className="primary" disabled={!!busy||!b.tema?.trim()} onClick={()=>fazer('rot',async()=>{ const r=await gerarRoteiro(cfg,b,'',extrasSk); setRoteiro(r); setPid(''); })}>{busy==='rot'?<Loader2 size={15} className="spin"/>:<Wand2 size={15}/>} {roteiro?'Gerar outro roteiro':'Gerar roteiro com IA'}</button>
     <button className="subtle" onClick={()=>setColar(!colar)}><ClipboardPaste size={15}/> Colar meu roteiro</button>
    </div>
    <SkillPicker perfil="agente3.roteiro" valor={extrasSk} onChange={setExtrasSk}/>
    {colar&&<div className="mt"><textarea rows={6} value={texto} onChange={e=>setTexto(e.target.value)} placeholder={'Um parágrafo por cena, ou linhas "NOME: fala".\n\nNARRADOR: Você sabia que...'}/>
     <button className="subtle mt" disabled={!texto.trim()||!!busy} onClick={()=>fazer('colar',async()=>{ setRoteiro(await gerarRoteiro(cfg,b,texto)); setPid(''); setColar(false); })}>Montar cenas do meu texto (sem IA)</button></div>}
    {roteiro&&<>
     <div className="small-grid mt"><label>Título<input value={roteiro.titulo} onChange={e=>setRoteiro({...roteiro,titulo:e.target.value})}/></label>
      <label>Legenda do post<input value={roteiro.legenda} onChange={e=>setRoteiro({...roteiro,legenda:e.target.value})}/></label></div>
     {roteiro.fontes?.length>0&&<p className="hint">Fontes para conferir: {roteiro.fontes.map(f=><a key={f.url} className="help-link" href={f.url} target="_blank" rel="noreferrer">{f.titulo||'fonte'} <ExternalLink size={11}/></a>)}</p>}
     {roteiro.skills_usadas&&roteiro.skills_usadas.length>0&&<p className="hint">Boas práticas consultadas: {roteiro.skills_usadas.join(', ')}.</p>}
     {roteiro.avisos&&roteiro.avisos.length>0&&<ul className="avisos-roteiro">{roteiro.avisos.map(a=><li key={a}>{a}</li>)}</ul>}
     <EditorCenas cenas={roteiro.cenas} set={c=>setRoteiro({...roteiro,cenas:c})} pid={pid}/>
    </>}
   </section>

   {roteiro&&pid&&<Diretor pid={pid} cenas={roteiro.cenas} salvar={salvarExistente} mudar={(i,p)=>setRoteiro({...roteiro,cenas:roteiro.cenas.map((c,k)=>k===i?{...c,...p}:c)})}/>}

   {roteiro&&<section className="panel">
    <div className="section-head"><h2>3. Visual do vídeo <HelpButton topic="estilos3"/></h2><span className="tag ok">{cat.dados?.estilos.find(e=>e.id===b.estilo)?.nome||b.estilo}</span></div>
    <details><summary>Trocar o visual (ver os estilos com demonstração)</summary><GradeEstilos selecionado={b.estilo} escolher={id=>{ set({estilo:id}); toast('Estilo escolhido.','ok'); }}/></details>
   </section>}

   {roteiro&&<section className="panel">
    <div className="section-head"><h2>4. Fazer o vídeo</h2></div>
    <Destinos b={b} set={set}/>
    <div className="row-gap left mt">
     <button className="primary" disabled={!!busy||!cat.dados?.ffmpeg} onClick={()=>produzirAgora(false)}>{busy==='prod'?<Loader2 size={15} className="spin"/>:<Play size={15}/>} Fazer o vídeo agora</button>
     {!pid&&<><input type="datetime-local" value={quando} onChange={e=>setQuando(e.target.value)} aria-label="Data e hora"/>
     <button className="subtle" disabled={!!busy||!quando} onClick={()=>produzirAgora(true)}><CalendarClock size={15}/> Agendar</button></>}
     <button className="subtle" disabled={!!busy} onClick={()=>fazer('rasc',async()=>{ if(pid){ await salvarExistente(); toast('Storyboard salvo no servidor.','ok'); return; } const p=await novoVideo(cfg,{briefing:b,roteiro}); setPid(p.id); setRev(p.revisao); toast('Rascunho salvo em Meus projetos.','ok'); })}><Save size={15}/> Salvar rascunho</button>
    </div>
    {cat.dados&&!cat.dados.ffmpeg&&<p className="hint bad">O servidor está sem FFmpeg. No Termux: pkg install ffmpeg.</p>}
    <p className="hint">A produção roda no celular com o navegador fechado. Ao terminar, o vídeo passa pela conferência automática, chega um e-mail com o código e ele espera você em Fila e aprovações.</p>
   </section>}
   </>}
  </div>;
}
