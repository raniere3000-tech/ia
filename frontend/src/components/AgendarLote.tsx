import { useState } from 'react';
import { ArrowUp, ArrowDown, CalendarClock, Loader2 } from 'lucide-react';
import { Modal } from './Help';
import { useApp } from '../state';
import { REDES, criarLote, previaLote, type PedidoLote, type Post, type PreviaLote, type Rede } from '../lib/agenda';

const local=(ts:number)=>{ const d=new Date(ts); d.setMinutes(d.getMinutes()-d.getTimezoneOffset()); return d.toISOString().slice(0,16); };
const hora=(ts:number)=>new Date(ts*1000).toLocaleString('pt-BR',{dateStyle:'short',timeStyle:'short'});
export default function AgendarLote({posts,ids,redeInicial,onClose,onAgendado}:{posts:Post[];ids:string[];redeInicial?:Rede;onClose:()=>void;onAgendado:()=>void}){
  const {settings,toast}=useApp();
  const [ordem,setOrdem]=useState(ids);
  const [redes,setRedes]=useState<Rede[]>(redeInicial?[redeInicial]:[]);
  const [inicio,setInicio]=useState(local(Date.now()+3600000));
  const [intervalo,setIntervalo]=useState(30);
  const [pausaApi,setPausaApi]=useState(30);
  const [modo,setModo]=useState<PedidoLote['modo']>('intervalo');
  const [reagendar,setReagendar]=useState(false);
  const [preview,setPreview]=useState<PreviaLote|null>(null);
  const [previsto,setPrevisto]=useState<PedidoLote|null>(null);
  const [chave]=useState(()=>crypto.randomUUID());
  const [busy,setBusy]=useState(false);
  const [erro,setErro]=useState('');
  const mudar=(f:()=>void)=>{ f(); setPreview(null); setPrevisto(null); setErro(''); };
  const mover=(i:number,d:number)=>mudar(()=>setOrdem(xs=>{ const ys=[...xs]; [ys[i],ys[i+d]]=[ys[i+d],ys[i]]; return ys; }));
  const prever=async()=>{
    setBusy(true); setErro(''); setPreview(null);
    const pedido:PedidoLote={posts:ordem,redes,inicio:new Date(inicio).getTime()/1000,intervalo_min:intervalo,intervalo_api_s:pausaApi,modo,reagendar};
    try{ setPreview(await previaLote(settings,pedido)); setPrevisto(pedido); }
    catch(e){ setErro(e instanceof Error?e.message:String(e)); }
    finally{ setBusy(false); }
  };
  const confirmar=async()=>{
    if(!previsto||!preview?.versao) return;
    setBusy(true); setErro('');
    try{
      const r=await criarLote(settings,{...previsto,chave,versao:preview.versao});
      toast(`${r.agendados.length} envio(s) agendado(s), ${r.ignorados.length} ignorado(s) e ${r.ajustes.length} precisa(m) de ajuste.`,'ok');
      onAgendado();
    }catch(e){ setErro(e instanceof Error?e.message:String(e)); }
    finally{ setBusy(false); }
  };
  return <Modal title={`Agendar ${ids.length} vídeo(s) em lote`} onClose={()=>{ if(!busy) onClose(); }} wide>
    <fieldset disabled={busy} className="lote-campos">
      <legend>Destinos e horários</legend>
      <div className="chips">{REDES.map(r=><button key={r.id} className={'chip '+(redes.includes(r.id)?'on':'')} aria-pressed={redes.includes(r.id)} onClick={()=>mudar(()=>setRedes(xs=>xs.includes(r.id)?xs.filter(x=>x!==r.id):[...xs,r.id]))}>{r.nome}</button>)}</div>
      <p className="hint">O que já foi publicado fica preservado. Kwai entra como lembrete para postar pelo app.</p>
      <div className="small-grid mt">
        <label>Data e hora inicial<input type="datetime-local" value={inicio} onChange={e=>mudar(()=>setInicio(e.target.value))}/></label>
        <label>Como distribuir<select value={modo} onChange={e=>mudar(()=>setModo(e.target.value as PedidoLote['modo']))}><option value="intervalo">Intervalo fixo</option><option value="programacao">Horários livres da programação</option></select></label>
        {modo==='intervalo'&&<label>Intervalo entre publicações (minutos)<input type="number" min={1} max={43200} value={intervalo} onChange={e=>mudar(()=>setIntervalo(Number(e.target.value)))}/></label>}
        <label>Pausa mínima entre envios na mesma rede (segundos)<input type="number" min={1} max={3600} value={pausaApi} onChange={e=>mudar(()=>setPausaApi(Number(e.target.value)))}/></label>
      </div>
      <label className="check mt"><input type="checkbox" checked={reagendar} onChange={e=>mudar(()=>setReagendar(e.target.checked))}/> Reagendar também os destinos que já têm horário</label>
      <p className="hint">As datas usam o fuso deste aparelho. A pausa controla os envios pela fila; os limites informados pela rede também serão respeitados.</p>
      {modo==='programacao'&&<p className="hint">Usa a programação ativa já configurada para cada rede. Se não houver vagas, a prévia mostrará os vídeos que ficaram sem horário.</p>}
      <details className="mt"><summary>Ordem dos vídeos ({ordem.length})</summary><ol className="lote-ordem">{ordem.map((id,i)=><li key={id}><span>{posts.find(p=>p.id===id)?.titulo||id}</span><button className="icon-btn" aria-label={`Subir vídeo ${i+1}`} disabled={busy||i===0} onClick={()=>mover(i,-1)}><ArrowUp size={14}/></button><button className="icon-btn" aria-label={`Descer vídeo ${i+1}`} disabled={busy||i===ordem.length-1} onClick={()=>mover(i,1)}><ArrowDown size={14}/></button></li>)}</ol></details>
      <button className="primary mt" disabled={busy||!redes.length||!inicio||intervalo<1||pausaApi<1} onClick={()=>void prever()}>{busy?<Loader2 size={15} className="spin"/>:<CalendarClock size={15}/>} Gerar prévia</button>
    </fieldset>
    {erro&&<p className="hint bad" role="alert">{erro}</p>}
    {preview&&<section className="lote-previa mt" aria-live="polite">
      <p><b>{preview.agendados.length}</b> envio(s) para agendar · <b>{preview.ignorados.length}</b> ignorado(s) · <b>{preview.ajustes.length}</b> precisa(m) de ajuste</p>
      <div className="lote-tabela"><table><thead><tr><th>Vídeo</th><th>Rede</th><th>Horário / resultado</th></tr></thead><tbody>{[...preview.agendados,...preview.ignorados,...preview.ajustes].map((x,i)=><tr key={i}><td>{x.titulo}</td><td>{REDES.find(r=>r.id===x.rede)?.nome}</td><td>{x.quando?hora(x.quando):x.motivo}</td></tr>)}</tbody></table></div>
      <p className="hint">Nenhum envio é feito ao gerar a prévia. A confirmação salva os horários e mantém as conferências normais antes de publicar.</p>
      <button className="primary mt" disabled={busy||!preview.agendados.length} onClick={()=>void confirmar()}>{busy?<Loader2 size={15} className="spin"/>:<CalendarClock size={15}/>} Agendar lote</button>
    </section>}
  </Modal>;
}
