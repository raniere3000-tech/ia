import { useCallback, useMemo, useState } from 'react';
import { ArrowLeft, CalendarClock, CheckCircle2, Loader2, Send, Server } from 'lucide-react';
import { useApp } from '../state';
import { HelpButton } from './Help';
import { ContasPainel } from '../pages/Agendar';
import { REDES, enviarVideo, criarPost, type Contas, type Rede } from '../lib/agenda';
import type { Clip } from '../lib/analyze';

const dd=(n:number)=>String(n).padStart(2,'0');
function proximaHora(){ const d=new Date(Date.now()+60*60*1000); d.setMinutes(0,0,0); return `${d.getFullYear()}-${dd(d.getMonth()+1)}-${dd(d.getDate())}T${dd(d.getHours())}:00`; }
const INTERVALOS:[string,number][] = [['Todos juntos',0],['30 minutos',30],['1 hora',60],['2 horas',120],['3 horas',180],['6 horas',360],['12 horas',720],['1 dia',1440]];
const fmt=(ms:number)=>new Date(ms).toLocaleString('pt-BR',{weekday:'short',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});

type Props = { clips:Clip[]; tema:string; gerar:(c:Clip,onPct:(p:number)=>void)=>Promise<{blob:Blob;nome:string}>; onVoltar:()=>void };

/** Etapa 4: login nas redes e agendamento de todos os cortes escolhidos de uma vez. */
export default function PostarLote({clips,tema,gerar,onVoltar}:Props){
  const {settings,toast,go}=useApp();
  const [contas,setContas]=useState<Contas|null>(null);
  const [redes,setRedes]=useState<Set<Rede>|null>(null);
  const [agora,setAgora]=useState(false); const [quando,setQuando]=useState(proximaHora()); const [intervalo,setIntervalo]=useState(120);
  const [modelo,setModelo]=useState(`{titulo}\n\n${tema?'#'+tema.replace(/\s+/g,'').toLowerCase()+' ':''}#cortes #shorts`);
  const [privac,setPrivac]=useState('public'); const [ttModo,setTtModo]=useState('rascunho');
  const [prog,setProg]=useState<{i:number;txt:string;pct:number;feitos:string[]}|null>(null);
  const onContas=useCallback((c:Contas)=>{ setContas(c); setRedes(r=>r??new Set(REDES.filter(x=>x.prov&&c[x.prov].conectado&&(x.id!=='instagram'||c.meta.paginas.find(p=>p.id===c.meta.pagina)?.instagram)).map(x=>x.id))); },[]);
  const disponivel=(r:typeof REDES[number])=>!r.prov||!!contas?.[r.prov].conectado;
  const inicio=agora?Date.now():new Date(quando).getTime();
  const horarios=useMemo(()=>clips.map((_,k)=>inicio+k*intervalo*60000),[clips,inicio,intervalo]);
  const sel=redes||new Set<Rede>();

  if(!settings.servidor) return <section className="panel empty-state">
   <Server size={34}/><h2>Ligue o servidor para postar</h2>
   <p>Os posts ficam guardados no servidor (seu celular com Termux ou seu PC) e são publicados na hora certa, mesmo com o site fechado. Seus cortes continuam aqui enquanto você liga.</p>
   <div className="row-gap"><button className="subtle" onClick={onVoltar}><ArrowLeft size={15}/> Voltar à edição</button><button className="primary" onClick={()=>go('config')}>Ligar servidor</button> <HelpButton topic="servidor" label="Como ligar?"/></div>
  </section>;

  async function agendarTodos(){
    if(!agora&&(isNaN(inicio)||inicio<Date.now()-60000)){ toast('Escolha uma data e hora no futuro.','erro'); return; }
    const feitos:string[]=[];
    try{
      for(let k=0;k<clips.length;k++){
        const c=clips[k];
        setProg({i:k,txt:'Preparando o vídeo',pct:0,feitos:[...feitos]});
        const {blob,nome}=await gerar(c,p=>setProg({i:k,txt:'Preparando o vídeo',pct:p,feitos:[...feitos]}));
        setProg({i:k,txt:'Enviando para o servidor',pct:0,feitos:[...feitos]});
        const video=await enviarVideo(settings,blob,nome,p=>setProg({i:k,txt:'Enviando para o servidor',pct:p,feitos:[...feitos]}));
        await criarPost(settings,{video,redes:[...sel],titulo:c.titulo,legenda:modelo.replace(/\{titulo\}/g,c.titulo).trim(),quando:(agora&&intervalo===0?Date.now():horarios[k])/1000,youtube_privacidade:privac,tiktok_modo:ttModo});
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
    <div className="result-summary"><strong>Postar {clips.length} corte(s)</strong> • entre nas suas contas e escolha quando cada corte vai ao ar.</div>
    <div className="result-controls"><button className="subtle" disabled={!!prog} onClick={onVoltar}><ArrowLeft size={15}/> Voltar à edição</button></div>
   </section>
   <ContasPainel onContas={onContas}/>
   <section className="panel">
    <div className="section-head"><h2><CalendarClock size={18}/> Agendamento</h2></div>
    {!contas?<p className="hint"><Loader2 size={14} className="spin"/> Lendo suas contas...</p>:<div className="agendar-form">
     <div className="field-label">Onde postar</div>
     <div className="redes-grid">{REDES.map(r=>{ const ok=disponivel(r); return <label key={r.id} className={'rede-opt '+(ok?'':'off')}><input type="checkbox" disabled={!ok||!!prog} checked={sel.has(r.id)} onChange={e=>{ const n=new Set(sel); e.target.checked?n.add(r.id):n.delete(r.id); setRedes(n); }}/> <span>{r.nome}{!ok&&<small> (entre na conta acima)</small>}{r.id==='kwai'&&<small> você baixa e posta no app</small>}</span></label>; })}</div>
     <div className="small-grid mt">
      <label className="check"><input type="checkbox" checked={agora} onChange={e=>setAgora(e.target.checked)}/> Começar agora</label>
      {!agora&&<label>Primeiro post<input type="datetime-local" value={quando} onChange={e=>setQuando(e.target.value)}/></label>}
      <label>Intervalo entre os posts<select value={intervalo} onChange={e=>setIntervalo(+e.target.value)}>{INTERVALOS.map(([l,v])=><option key={v} value={v}>{l}</option>)}</select></label>
     </div>
     <label className="mt">Legenda do post (use {'{titulo}'} para o título de cada corte)<textarea rows={3} value={modelo} maxLength={2200} onChange={e=>setModelo(e.target.value)}/></label>
     <div className="small-grid mt">
      {sel.has('youtube')&&<label>YouTube<select value={privac} onChange={e=>setPrivac(e.target.value)}><option value="public">Público</option><option value="unlisted">Não listado</option><option value="private">Privado</option></select></label>}
      {sel.has('tiktok')&&<label>TikTok<select value={ttModo} onChange={e=>setTtModo(e.target.value)}><option value="rascunho">Mandar para rascunhos (você toca em Postar)</option><option value="direto">Postar direto (app aprovado pelo TikTok)</option></select></label>}
     </div>
     <div className="fila-posts">{clips.map((c,k)=><div key={c.id} className={'fila-item '+(prog?.i===k?'on':'')}>
       <span className="fila-n">{prog?.feitos.includes(c.id)?<CheckCircle2 size={15}/>:k+1}</span>
       <span className="grow"><b>{c.titulo}</b><small>{isNaN(horarios[k])?'—':fmt(horarios[k])}</small></span>
       {prog?.i===k&&<small><Loader2 size={13} className="spin"/> {prog.txt} {prog.pct}%</small>}
      </div>)}</div>
     <p className="hint">Os vídeos ficam guardados no servidor e são postados na hora marcada, mesmo com o site fechado. O servidor (celular) precisa estar ligado nesses horários. Mantenha esta aba aberta até terminar de enviar.</p>
     <button className="primary lg full" disabled={!sel.size||!!prog} onClick={agendarTodos}>{prog?<><Loader2 size={17} className="spin"/> Enviando {prog.i+1} de {clips.length}...</>:agora&&intervalo===0?<><Send size={17}/> Postar os {clips.length} agora</>:<><CalendarClock size={17}/> Agendar os {clips.length} cortes</>}</button>
    </div>}
   </section>
  </>;
}
