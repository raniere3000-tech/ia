import { useState } from 'react';
import { Lock, Loader2 } from 'lucide-react';
import { abrirCofre, apagarCofre, type Segredos } from '../lib/cofre';

/** Tela de entrada quando as chaves estão guardadas com PIN. */
export default function Cadeado({aoAbrir,aoPular}:{aoAbrir:(s:Segredos)=>void;aoPular:()=>void}){
  const [pin,setPin]=useState(''); const [erro,setErro]=useState(''); const [busy,setBusy]=useState(false); const [erros,setErros]=useState(0);
  const abrir=async()=>{
    if(!pin||busy) return; setBusy(true); setErro('');
    try{ aoAbrir(await abrirCofre(pin)); }
    catch(e){ const n=erros+1; setErros(n); setPin(''); await new Promise(r=>setTimeout(r,Math.min(8000,400*2**n))); setErro(e instanceof Error?e.message:String(e)); }
    finally{ setBusy(false); }
  };
  return <div className="modal-bg cadeado" role="dialog" aria-modal="true" aria-labelledby="cadeado-t">
    <div className="modal cadeado-caixa">
      <Lock size={30}/>
      <h3 id="cadeado-t">Chaves protegidas</h3>
      <p>Digite o seu PIN para abrir as chaves de API e a senha do servidor neste aparelho.</p>
      <input type="password" autoFocus autoComplete="off" value={pin} onChange={e=>setPin(e.target.value)} onKeyDown={e=>{ if(e.key==='Enter') abrir(); }} placeholder="PIN" aria-label="PIN" disabled={busy}/>
      {erro&&<p className="hint bad" role="alert">{erro}</p>}
      <button className="primary full" disabled={!pin||busy} onClick={abrir}>{busy?<Loader2 size={15} className="spin"/>:<Lock size={15}/>} Abrir</button>
      <button className="link-btn" onClick={aoPular}>Usar agora sem as chaves</button>
      <button className="link-btn" onClick={()=>{ if(window.confirm('Apagar as chaves guardadas neste aparelho? Você vai precisar colar todas de novo.')){ apagarCofre(); location.reload(); } }}>Esqueci o PIN</button>
    </div>
  </div>;
}
