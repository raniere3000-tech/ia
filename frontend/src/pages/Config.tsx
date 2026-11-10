import { useState } from 'react';
import { KeyRound, Youtube, Sparkles, Captions, CheckCircle2, Loader2, Eye, EyeOff, Trash2, ExternalLink } from 'lucide-react';
import { useApp } from '../state';
import { HelpButton } from '../components/Help';
import { testarChaveYouTube } from '../lib/radar';
import { WHISPER_MODELS, IDIOMAS } from '../lib/transcribe';

function KeyField({label,value,placeholder,onSave,onTest,help,link,linkLabel}:{label:string;value:string;placeholder:string;onSave:(v:string)=>void;onTest:(v:string)=>Promise<void>;help:'youtube'|'claude';link:string;linkLabel:string}){
  const {toast}=useApp();
  const [v,setV]=useState(value); const [show,setShow]=useState(false); const [busy,setBusy]=useState(false);
  const [estado,setEstado]=useState<''|'ok'|'erro'>('');
  async function salvar(){
    const k=v.trim(); setBusy(true); setEstado('');
    try{ await onTest(k); onSave(k); setEstado('ok'); toast('Chave testada e salva neste navegador.','ok'); }
    catch(e){ setEstado('erro'); toast(e instanceof Error?e.message:String(e),'erro'); }
    finally{ setBusy(false); }
  }
  return <div className="key-field">
   <label className="key-label">{label} <HelpButton topic={help} label="Onde consigo?"/></label>
   <div className="key-row">
    <div className="input-wrap"><KeyRound size={16}/><input type={show?'text':'password'} value={v} onChange={e=>{setV(e.target.value);setEstado('')}} placeholder={placeholder} autoComplete="off" spellCheck={false}/><button type="button" className="icon-btn" onClick={()=>setShow(!show)} aria-label={show?'Ocultar':'Mostrar'}>{show?<EyeOff size={16}/>:<Eye size={16}/>}</button></div>
    <button className="primary" disabled={!v.trim()||busy} onClick={salvar}>{busy?<Loader2 size={16} className="spin"/>:<CheckCircle2 size={16}/>} Testar e salvar</button>
    {value&&<button className="subtle" onClick={()=>{onSave('');setV('');setEstado('');toast('Chave apagada deste navegador.')}} title="Apagar chave"><Trash2 size={16}/></button>}
   </div>
   <div className="key-foot">{value?<span className="tag ok">Chave salva</span>:<span className="tag warn">Nenhuma chave salva</span>}{estado==='erro'&&<span className="tag bad">Não funcionou</span>}<a href={link} target="_blank" rel="noreferrer" className="help-link">{linkLabel} <ExternalLink size={12}/></a></div>
  </div>;
}

export default function Config(){
  const {settings,setSettings}=useApp();
  return <>
   <section className="panel config-card">
    <div className="config-icon yt"><Youtube size={22}/></div>
    <div className="config-body">
     <div className="section-head"><h2>Radar do YouTube <span className="tag warn">necessária para o Radar</span></h2></div>
     <p className="subtitle">Permite pesquisar vídeos e canais públicos. É grátis e leva uns 5 minutos para criar. Não sabe como? Clique em <b>Onde consigo?</b> e siga o passo a passo.</p>
     <KeyField label="Chave da YouTube Data API v3" value={settings.ytKey} placeholder="Cole aqui a chave que começa com AIza..." onSave={v=>setSettings({ytKey:v})} onTest={testarChaveYouTube} help="youtube" link="https://console.cloud.google.com/apis/credentials" linkLabel="Abrir Google Cloud"/>
    </div>
   </section>

   <section className="panel config-card">
    <div className="config-icon ai"><Sparkles size={22}/></div>
    <div className="config-body">
     <div className="section-head"><h2>Notas com IA (Claude) <span className="tag">opcional</span></h2></div>
     <p className="subtitle">Sem esta chave tudo funciona, mas as notas vêm só do áudio. Com ela, a IA lê o que é falado, dá notas de gancho, fluxo, valor e tendência, escreve títulos e encontra trechos pelo seu pedido. Custo por uso, pago à Anthropic.</p>
     <KeyField label="Chave da API da Claude" value={settings.claudeKey} placeholder="Cole aqui a chave que começa com sk-ant-..." onSave={v=>setSettings({claudeKey:v})} onTest={async k=>{ const {testarChaveClaude,erroAmigavel}=await import('../lib/ai'); try{ await testarChaveClaude(k); }catch(e){ throw new Error(erroAmigavel(e)); } }} help="claude" link="https://console.anthropic.com/settings/keys" linkLabel="Abrir console da Anthropic"/>
    </div>
   </section>

   <section className="panel config-card">
    <div className="config-icon cap"><Captions size={22}/></div>
    <div className="config-body">
     <div className="section-head"><h2>Legendas automáticas <span className="tag ok">sem chave</span> <HelpButton topic="whisper"/></h2></div>
     <p className="subtitle">A fala é transcrita no seu computador com o Whisper. Escolha a qualidade e o idioma padrão.</p>
     <div className="small-grid">
      <label>Qualidade da transcrição<select value={settings.whisperModel} onChange={e=>setSettings({whisperModel:e.target.value})}>{WHISPER_MODELS.map(m=><option key={m.id} value={m.id}>{m.nome}</option>)}</select></label>
      <label>Idioma da fala<select value={settings.idioma} onChange={e=>setSettings({idioma:e.target.value})}>{IDIOMAS.map(m=><option key={m.id} value={m.id}>{m.nome}</option>)}</select></label>
     </div>
    </div>
   </section>

  </>;
}
