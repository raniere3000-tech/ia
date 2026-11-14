import { useEffect, useState } from 'react';
import { CalendarClock, Loader2, Send } from 'lucide-react';
import { useApp } from '../state';
import { Modal } from './Help';
import { REDES, lerContas, enviarVideo, criarPost, type Contas, type Rede } from '../lib/agenda';

const doisDigitos=(n:number)=>String(n).padStart(2,'0');
function proximaHora(){ const d=new Date(Date.now()+60*60*1000); d.setMinutes(0,0,0); return `${d.getFullYear()}-${doisDigitos(d.getMonth()+1)}-${doisDigitos(d.getDate())}T${doisDigitos(d.getHours())}:00`; }

/** Janela para agendar um corte (ou vídeo pronto) nas redes conectadas. */
export default function AgendarPost({titulo:t0,legenda:l0,gerar,onClose,modelo}:{titulo:string;legenda:string;modelo?:string;gerar:(onPct:(p:number)=>void)=>Promise<{blob:Blob;nome:string}>;onClose:()=>void}){
  const {settings,toast,go}=useApp();
  const [contas,setContas]=useState<Contas|null>(null); const [erro,setErro]=useState('');
  const [titulo,setTitulo]=useState(t0); const [legenda,setLegenda]=useState(l0);
  const [redes,setRedes]=useState<Set<Rede>>(new Set());
  const [agora,setAgora]=useState(false); const [quando,setQuando]=useState(proximaHora());
  const [privac,setPrivac]=useState('public'); const [ttModo,setTtModo]=useState('rascunho');
  const [etapa,setEtapa]=useState<{txt:string;pct:number}|null>(null);
  useEffect(()=>{ lerContas(settings).then(c=>{ setContas(c); setRedes(new Set(REDES.filter(r=>r.prov&&c[r.prov].conectado&&(r.id!=='instagram'||c.meta.paginas.find(p=>p.id===c.meta.pagina)?.instagram)).map(r=>r.id))); }).catch(e=>setErro(e.message)); },[settings]);
  const disponivel=(r:typeof REDES[number])=>!r.prov||!!contas?.[r.prov].conectado;
  async function confirmar(){
    const ts=agora?Date.now()/1000:new Date(quando).getTime()/1000;
    if(!agora&&(isNaN(ts)||ts<Date.now()/1000-60)){ toast('Escolha uma data e hora no futuro.','erro'); return; }
    try{
      setEtapa({txt:'Preparando o vídeo',pct:0});
      const {blob,nome}=await gerar(p=>setEtapa({txt:'Preparando o vídeo',pct:p}));
      setEtapa({txt:'Enviando para o servidor',pct:0});
      const video=await enviarVideo(settings,blob,nome,p=>setEtapa({txt:'Enviando para o servidor',pct:p}));
      await criarPost(settings,{video,redes:[...redes],titulo,legenda,quando:ts,youtube_privacidade:privac,tiktok_modo:ttModo,modelo:modelo||''});
      toast(agora?'Enviado! Acompanhe em Agendar posts.':`Agendado para ${new Date(ts*1000).toLocaleString('pt-BR',{dateStyle:'short',timeStyle:'short'})}.`,'ok');
      onClose(); go('agendar');
    }catch(e){ setEtapa(null); toast(e instanceof Error?e.message:String(e),'erro'); }
  }
  return <Modal title="Agendar post" onClose={()=>{ if(!etapa) onClose(); }} wide>
   {erro?<div className="note-bar"><span>{erro}</span><button className="primary sm" onClick={()=>{onClose();go('config');}}>Ligar servidor</button></div>
   :!contas?<p className="hint"><Loader2 size={14} className="spin"/> Lendo suas contas...</p>
   :<div className="agendar-form">
     <label>Título (YouTube)<input value={titulo} maxLength={100} onChange={e=>setTitulo(e.target.value)}/></label>
     <label>Legenda e hashtags<textarea rows={4} value={legenda} maxLength={2200} onChange={e=>setLegenda(e.target.value)} placeholder="Escreva a legenda. Ex.: Que jogada! #gta #shorts"/></label>
     <div className="field-label">Onde postar</div>
     <div className="redes-grid">{REDES.map(r=>{ const ok=disponivel(r); return <label key={r.id} className={'rede-opt '+(ok?'':'off')}><input type="checkbox" disabled={!ok} checked={redes.has(r.id)} onChange={e=>{ const n=new Set(redes); e.target.checked?n.add(r.id):n.delete(r.id); setRedes(n); }}/> <span>{r.nome}{!ok&&<small> (não conectado)</small>}{r.id==='kwai'&&<small> você baixa e posta no app</small>}</span></label>; })}</div>
     <div className="small-grid mt">
      <label className="check"><input type="checkbox" checked={agora} onChange={e=>setAgora(e.target.checked)}/> Postar agora</label>
      {!agora&&<label>Data e hora<input type="datetime-local" value={quando} onChange={e=>setQuando(e.target.value)}/></label>}
     </div>
     <div className="small-grid mt">
      {redes.has('youtube')&&<label>YouTube<select value={privac} onChange={e=>setPrivac(e.target.value)}><option value="public">Público</option><option value="unlisted">Não listado</option><option value="private">Privado</option></select></label>}
      {redes.has('tiktok')&&<label>TikTok<select value={ttModo} onChange={e=>setTtModo(e.target.value)}><option value="rascunho">Mandar para rascunhos (você toca em Postar)</option><option value="direto">Postar direto (app aprovado pelo TikTok)</option></select></label>}
     </div>
     <p className="hint">O vídeo fica guardado no servidor e é postado na hora marcada, mesmo com o site fechado. O servidor (celular) precisa estar ligado nesse horário.</p>
     {etapa?<div className="dl-box"><div className="row"><Loader2 size={16} className="spin"/><span><b>{etapa.txt}</b> {etapa.pct}%</span></div><div className="dl-bar"><i style={{width:Math.max(3,etapa.pct)+'%'}}/></div></div>
     :<button className="primary lg full" disabled={!redes.size} onClick={confirmar}>{agora?<><Send size={17}/> Postar agora</>:<><CalendarClock size={17}/> Agendar</>}</button>}
    </div>}
  </Modal>;
}
