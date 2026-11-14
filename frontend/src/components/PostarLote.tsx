import { useCallback, useMemo, useState } from 'react';
import { ArrowLeft, Bot, CalendarClock, CheckCircle2, Download, Loader2, Save, Send, Server, Sparkles, RotateCcw } from 'lucide-react';
import { useApp } from '../state';
import { HelpButton } from './Help';
import { ContasPainel } from '../pages/Agendar';
import { REDES, enviarVideo, criarPost, type Contas, type Rede } from '../lib/agenda';
import { enviarCorteManual, MOTIVOS } from '../lib/agente';
import { baixar } from '../lib/exporter';
import type { Clip } from '../lib/analyze';
import { legendaAutomatica, escreverComIA, montarTexto } from '../lib/legendasPost';
import { iaAtiva, nomeIA, erroIA } from '../lib/ia';

const dd=(n:number)=>String(n).padStart(2,'0');
function proximaHora(){ const d=new Date(Date.now()+60*60*1000); d.setMinutes(0,0,0); return `${d.getFullYear()}-${dd(d.getMonth()+1)}-${dd(d.getDate())}T${dd(d.getHours())}:00`; }
const INTERVALOS:[string,number][] = [['Todos juntos',0],['30 minutos',30],['1 hora',60],['2 horas',120],['3 horas',180],['6 horas',360],['12 horas',720],['1 dia',1440]];
const fmt=(ms:number)=>new Date(ms).toLocaleString('pt-BR',{weekday:'short',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});

type Destino = 'agendar'|'fila'|'pronto'|'baixar';
const DESTINOS:[Destino,string,string][] = [
  ['agendar','Agendar','Você escolhe data, hora e redes'],
  ['fila','Enviar à fila do agente','O Agente de Postagem escolhe o horário'],
  ['pronto','Salvar como pronto','Fica guardado no servidor até você mandar postar'],
  ['baixar','Só baixar','Baixa os vídeos para este aparelho'],
];
const lerLs=(k:string)=>{ try{ return localStorage.getItem(k)||''; }catch{ return ''; } };
const gravarLs=(k:string,v:string)=>{ try{ localStorage.setItem(k,v); }catch{ /* sem armazenamento */ } };

type Props = { clips:Clip[]; tema:string; gerar:(c:Clip,onPct:(p:number)=>void)=>Promise<{blob:Blob;nome:string}>; onVoltar:()=>void };

/** Etapa 4: login nas redes e agendamento de todos os cortes escolhidos de uma vez. */
export default function PostarLote({clips:todosClips,tema,gerar,onVoltar}:Props){
  const {settings,toast,go,projeto,modelos}=useApp();
  const [destino,setDestino]=useState<Destino>('agendar');
  // Aprovar ou descartar cada vídeo antes de mandar: os desmarcados não são produzidos nem enviados.
  const [fora,setFora]=useState<Set<string>>(new Set());
  const clips=useMemo(()=>todosClips.filter(c=>!fora.has(c.id)),[todosClips,fora]);
  const [origem,setOrigem]=useState(()=>lerLs('studio_direitos_origem')); const [nota,setNota]=useState(()=>lerLs('studio_direitos_nota'));
  const nomeModelo=(c:Clip)=>c.modelo&&c.visual?(modelos.find(m=>m.id===c.modelo)?.nome||'Template apagado'):'Sem template';
  const [contas,setContas]=useState<Contas|null>(null);
  const [redes,setRedes]=useState<Set<Rede>|null>(null);
  const [agora,setAgora]=useState(false); const [quando,setQuando]=useState(proximaHora()); const [intervalo,setIntervalo]=useState(120);
  // Legenda de cada post, já preenchida com título, fala do corte e hashtags.
  const automatico=()=>Object.fromEntries(todosClips.map(c=>[c.id,legendaAutomatica(c,projeto.cues,tema)]));
  const [textos,setTextos]=useState<Record<string,string>>(automatico);
  const [escrevendo,setEscrevendo]=useState(false);
  const qualIA=iaAtiva(settings);
  async function comIA(){
    setEscrevendo(true);
    try{
      const r=await escreverComIA(settings,clips,projeto.cues,tema);
      setTextos(t=>{ const n={...t}; for(const x of r) if(n[x.id]!==undefined) n[x.id]=montarTexto(x); return n; });
      toast(`Legendas escritas pela IA (${nomeIA(qualIA)}). Confira e ajuste se quiser.`,'ok');
    }catch(e){ toast(await erroIA(settings,e),'erro'); }
    finally{ setEscrevendo(false); }
  }
  const [privac,setPrivac]=useState('public'); const [ttModo,setTtModo]=useState('rascunho');
  const [prog,setProg]=useState<{i:number;txt:string;pct:number;feitos:string[]}|null>(null);
  const onContas=useCallback((c:Contas)=>{ setContas(c); setRedes(r=>r??new Set(REDES.filter(x=>x.prov&&c[x.prov].conectado&&(x.id!=='instagram'||c.meta.paginas.find(p=>p.id===c.meta.pagina)?.instagram)).map(x=>x.id))); },[]);
  const disponivel=(r:typeof REDES[number])=>!r.prov||!!contas?.[r.prov].conectado;
  const inicio=agora?Date.now():new Date(quando).getTime();
  const horarios=useMemo(()=>clips.map((_,k)=>inicio+k*intervalo*60000),[clips,inicio,intervalo]);
  const sel=redes||new Set<Rede>();

  if(!settings.servidor&&destino!=='baixar') return <section className="panel empty-state">
   <Server size={34}/><h2>Ligue o servidor para postar</h2>
   <p>Os posts ficam guardados no servidor (seu celular com Termux ou seu PC) e são publicados na hora certa, mesmo com o site fechado. Seus cortes continuam aqui enquanto você liga.</p>
   <div className="row-gap"><button className="subtle" onClick={onVoltar}><ArrowLeft size={15}/> Voltar à edição</button><button className="primary" onClick={()=>go('config')}>Ligar servidor</button><button className="subtle" onClick={()=>setDestino('baixar')}><Download size={15}/> Só baixar os vídeos</button> <HelpButton topic="servidor" label="Como ligar?"/></div>
  </section>;

  /** Baixar, salvar como pronto ou mandar à fila do agente. */
  async function entregar(){
    if(destino!=='baixar'&&!origem){ toast('Diga de quem é o vídeo antes de continuar.','erro'); return; }
    const feitos:string[]=[];
    try{
      for(let k=0;k<clips.length;k++){
        const c=clips[k];
        setProg({i:k,txt:'Preparando o vídeo',pct:0,feitos:[...feitos]});
        const {blob,nome}=await gerar(c,p=>setProg({i:k,txt:'Preparando o vídeo',pct:p,feitos:[...feitos]}));
        if(destino==='baixar'){ baixar(blob,nome); }
        else{
          setProg({i:k,txt:'Enviando para o servidor',pct:0,feitos:[...feitos]});
          const video=await enviarVideo(settings,blob,nome,p=>setProg({i:k,txt:'Enviando para o servidor',pct:p,feitos:[...feitos]}));
          await enviarCorteManual(settings,{video,titulo:c.titulo,legenda:(textos[c.id]??legendaAutomatica(c,projeto.cues,tema)).trim(),hashtags:c.hashtags||[],modelo:c.modelo&&c.visual?c.modelo:'',destino:destino==='fila'?'fila':'pronto',direitos:{origem,nota},gancho:c.gancho_texto,nota:c.nota_final,origem_titulo:projeto.nome});
        }
        feitos.push(c.id);
      }
      setProg(null);
      if(destino==='baixar') toast(`${clips.length} vídeo(s) baixado(s).`,'ok');
      else{ toast(destino==='fila'?`${clips.length} corte(s) na fila do Agente de Postagem.`:`${clips.length} corte(s) guardado(s) como prontos. Eles só são postados quando você mandar, em Agentes.`,'ok'); go('agente'); }
    }catch(e){
      toast((feitos.length?`${feitos.length} de ${clips.length} já foram. `:'')+(e instanceof Error?e.message:String(e)),'erro');
      setProg(null);
    }
  }

  async function agendarTodos(){
    if(!origem){ toast('Diga de quem é o vídeo antes de agendar.','erro'); return; }
    if(!agora&&(isNaN(inicio)||inicio<Date.now()-60000)){ toast('Escolha uma data e hora no futuro.','erro'); return; }
    const feitos:string[]=[];
    try{
      for(let k=0;k<clips.length;k++){
        const c=clips[k];
        setProg({i:k,txt:'Preparando o vídeo',pct:0,feitos:[...feitos]});
        const {blob,nome}=await gerar(c,p=>setProg({i:k,txt:'Preparando o vídeo',pct:p,feitos:[...feitos]}));
        setProg({i:k,txt:'Enviando para o servidor',pct:0,feitos:[...feitos]});
        const video=await enviarVideo(settings,blob,nome,p=>setProg({i:k,txt:'Enviando para o servidor',pct:p,feitos:[...feitos]}));
        await criarPost(settings,{video,redes:[...sel],titulo:c.titulo,legenda:(textos[c.id]??legendaAutomatica(c,projeto.cues,tema)).trim(),quando:(agora&&intervalo===0?Date.now():horarios[k])/1000,youtube_privacidade:privac,tiktok_modo:ttModo,modelo:c.modelo&&c.visual?c.modelo:'',direitos:{origem,nota}});
        feitos.push(c.id);
      }
      toast(`${clips.length} corte(s) agendado(s)! Confira na agenda.`,'ok');
      go('agendar');
    }catch(e){
      toast((feitos.length?`${feitos.length} de ${clips.length} já foram agendados. `:'')+(e instanceof Error?e.message:String(e)),'erro');
      setProg(null);
    }
  }

  return <>
   <section className="panel results-bar">
    <div className="result-summary"><strong>{clips.length} corte(s) editado(s)</strong> • baixe, guarde como pronto, mande à fila do agente ou agende você mesmo.</div>
    <div className="result-controls"><button className="subtle" disabled={!!prog} onClick={onVoltar}><ArrowLeft size={15}/> Voltar à edição</button></div>
   </section>
   <section className="panel destino-post">
    <div className="section-head"><h2>O que fazer com os cortes editados</h2></div>
    <div className="destinos" role="radiogroup" aria-label="Destino dos cortes">{DESTINOS.map(([id,n,d])=><button key={id} role="radio" aria-checked={destino===id} disabled={!!prog} className={'destino '+(destino===id?'on':'')} onClick={()=>setDestino(id)}><b>{n}</b><small>{d}</small></button>)}</div>
    <div className="field mt"><span className="field-label">Aprovar cada vídeo ({clips.length} de {todosClips.length} marcados)</span>
     <ul className="aprovar-lista">{todosClips.map((c,k)=><li key={c.id} className={fora.has(c.id)?'fora':''}><label className="check"><input type="checkbox" disabled={!!prog} checked={!fora.has(c.id)} onChange={e=>setFora(f=>{ const n=new Set(f); e.target.checked?n.delete(c.id):n.add(c.id); return n; })}/> <span><b>{k+1}. {c.titulo}</b> <small className="muted">{Math.round(c.fim-c.inicio)} s · {nomeModelo(c)}</small></span></label></li>)}</ul>
     <small className="hint">Os desmarcados ficam de fora: não são produzidos, enviados nem postados.</small></div>
    {destino!=='baixar'&&<div className="direitos mt">
     <span className="field-label">De quem é este vídeo? (conferido antes de qualquer publicação)</span>
     <div className="small-grid">
      <label>Origem<select value={origem} onChange={e=>{ setOrigem(e.target.value); gravarLs('studio_direitos_origem',e.target.value); }} aria-label="Origem do vídeo"><option value="">Escolha...</option>{Object.entries(MOTIVOS).map(([k,t])=><option key={k} value={k}>{t.replace('O canal é meu','O vídeo é meu').replace('O canal tem','O canal de origem tem')}</option>)}</select></label>
      <label>Onde está a autorização (opcional)<input value={nota} maxLength={300} placeholder="Link, e-mail ou data da conversa" onChange={e=>{ setNota(e.target.value); gravarLs('studio_direitos_nota',e.target.value); }}/></label>
     </div>
     <small className="hint">Fica registrado junto do post. Isso é o seu registro, não substitui a autorização do dono nem a análise de cada rede.</small>
    </div>}
    {destino==='fila'&&<p className="hint mt"><Bot size={13}/> O agente usa as redes e os horários da aba Agentes, parte Postagem. O template de cada corte fica registrado para o painel de desempenho. Isso não muda os critérios do Agente de Cortes nem os pesos dos templates.</p>}
    {destino==='pronto'&&<p className="hint mt"><Save size={13}/> O vídeo fica guardado no servidor, fora da fila. Para postar, abra Agentes, parte Fila e histórico, e toque em Agendar.</p>}
    {destino!=='agendar'&&<>
     {destino!=='baixar'&&<><div className="section-head mt"><h3>Legenda de cada post</h3></div>
      <div className="fila-posts">{clips.map((c,k)=><div key={c.id} className={'fila-item col '+(prog?.i===k?'on':'')}>
       <div className="fila-top"><span className="fila-n">{prog?.feitos.includes(c.id)?<CheckCircle2 size={15}/>:k+1}</span><span className="grow"><b>{c.titulo}</b></span>{prog?.i===k&&<small><Loader2 size={13} className="spin"/> {prog.txt} {prog.pct}%</small>}</div>
       <textarea rows={3} maxLength={2200} value={textos[c.id]??''} disabled={!!prog} onChange={e=>{ const v=e.target.value; setTextos(t=>({...t,[c.id]:v})); }} aria-label={'Legenda do post '+(k+1)}/>
      </div>)}</div></>}
     {destino==='baixar'&&prog&&<p className="hint"><Loader2 size={13} className="spin"/> {prog.txt} {prog.i+1} de {clips.length}: {prog.pct}%</p>}
     <button className="primary lg full mt" disabled={!clips.length||!!prog||(destino!=='baixar'&&!origem)} onClick={entregar}>{prog?<><Loader2 size={17} className="spin"/> Cuidando do {prog.i+1} de {clips.length}...</>:destino==='baixar'?<><Download size={17}/> Baixar {clips.length} vídeo(s)</>:destino==='fila'?<><Bot size={17}/> Enviar {clips.length} à fila do agente</>:<><Save size={17}/> Salvar {clips.length} como prontos</>}</button>
    </>}
   </section>
   {destino==='agendar'&&<ContasPainel onContas={onContas}/>}
   {destino==='agendar'&&<section className="panel">
    <div className="section-head"><h2><CalendarClock size={18}/> Agendamento</h2></div>
    {!contas?<p className="hint"><Loader2 size={14} className="spin"/> Lendo suas contas...</p>:<div className="agendar-form">
     <div className="field-label">Onde postar</div>
     <div className="redes-grid">{REDES.map(r=>{ const ok=disponivel(r); return <label key={r.id} className={'rede-opt '+(ok?'':'off')}><input type="checkbox" disabled={!ok||!!prog} checked={sel.has(r.id)} onChange={e=>{ const n=new Set(sel); e.target.checked?n.add(r.id):n.delete(r.id); setRedes(n); }}/> <span>{r.nome}{!ok&&<small> (entre na conta acima)</small>}{r.id==='kwai'&&<small> você baixa e posta no app</small>}</span></label>; })}</div>
     {REDES.filter(r=>r.prov&&sel.has(r.id)&&contas[r.prov].erro).map(r=><p key={r.id} className="hint bad"><b>{r.nome}:</b> {contas[r.prov!].erro} Sem isso o post desta rede vai falhar.</p>)}
     {sel.has('kwai')&&<p className="hint">O Kwai não tem como postar automático: na hora marcada o vídeo fica pronto na agenda para você baixar e postar no app.</p>}
     <div className="small-grid mt">
      <label className="check"><input type="checkbox" checked={agora} onChange={e=>setAgora(e.target.checked)}/> Começar agora</label>
      {!agora&&<label>Primeiro post<input type="datetime-local" value={quando} onChange={e=>setQuando(e.target.value)}/></label>}
      <label>Intervalo entre os posts<select value={intervalo} onChange={e=>setIntervalo(+e.target.value)}>{INTERVALOS.map(([l,v])=><option key={v} value={v}>{l}</option>)}</select></label>
     </div>
     <div className="small-grid mt">
      {sel.has('youtube')&&<label>YouTube<select value={privac} onChange={e=>setPrivac(e.target.value)}><option value="public">Público</option><option value="unlisted">Não listado</option><option value="private">Privado</option></select></label>}
      {sel.has('tiktok')&&<label>TikTok<select value={ttModo} onChange={e=>setTtModo(e.target.value)}><option value="rascunho">Mandar para rascunhos (você toca em Postar)</option><option value="direto">Postar direto (app aprovado pelo TikTok)</option></select></label>}
     </div>
     <div className="section-head mt"><h3>Legenda de cada post</h3><div className="row-gap">
      {qualIA&&<button className="primary sm" disabled={escrevendo||!!prog} onClick={comIA}>{escrevendo?<Loader2 size={14} className="spin"/>:<Sparkles size={14}/>} Escrever com IA ({nomeIA(qualIA)})</button>}
      <button className="subtle sm" disabled={escrevendo||!!prog} onClick={()=>setTextos(automatico())}><RotateCcw size={14}/> Preencher de novo</button></div></div>
     <p className="hint">Já vem preenchida com o título, um trecho da fala e hashtags do tema. Edite à vontade.{!qualIA&&' Com a chave do Gemini em Chaves e ajustes, a IA escreve legendas mais chamativas.'}</p>
     <div className="fila-posts">{clips.map((c,k)=><div key={c.id} className={'fila-item col '+(prog?.i===k?'on':'')}>
       <div className="fila-top"><span className="fila-n">{prog?.feitos.includes(c.id)?<CheckCircle2 size={15}/>:k+1}</span>
       <span className="grow"><b>{c.titulo}</b><small>{isNaN(horarios[k])?'—':fmt(horarios[k])}</small></span>
       {prog?.i===k&&<small><Loader2 size={13} className="spin"/> {prog.txt} {prog.pct}%</small>}</div>
       <textarea rows={4} maxLength={2200} value={textos[c.id]??''} disabled={!!prog} onChange={e=>{ const v=e.target.value; setTextos(t=>({...t,[c.id]:v})); }} aria-label={'Legenda do post '+(k+1)}/>
       <small className="conta-chars">{(textos[c.id]??'').length}/2200 • {((textos[c.id]??'').match(/#\w+/g)||[]).length} hashtags</small>
      </div>)}</div>
     <p className="hint">Os vídeos ficam guardados no servidor e são postados na hora marcada, mesmo com o site fechado. O servidor (celular) precisa estar ligado nesses horários. Mantenha esta aba aberta até terminar de enviar.</p>
     <button className="primary lg full" disabled={!sel.size||!!prog||!clips.length||!origem} onClick={agendarTodos}>{prog?<><Loader2 size={17} className="spin"/> Enviando {prog.i+1} de {clips.length}...</>:agora&&intervalo===0?<><Send size={17}/> Postar os {clips.length} agora</>:<><CalendarClock size={17}/> Agendar os {clips.length} cortes</>}</button>
    </div>}
   </section>}
  </>;
}
