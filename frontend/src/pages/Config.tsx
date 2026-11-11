import { useEffect, useState } from 'react';
import { KeyRound, Youtube, Sparkles, Captions, Server, CheckCircle2, Loader2, Eye, EyeOff, Trash2, ExternalLink, Upload } from 'lucide-react';
import { useApp } from '../state';
import { HelpButton } from '../components/Help';
import { testarChaveYouTube } from '../lib/radar';
import { WHISPER_MODELS, IDIOMAS } from '../lib/transcribe';
import { testarServidor, enviarCookies } from '../lib/servidor';
import { iaAtiva } from '../lib/ia';

function KeyField({label,value,placeholder,onSave,onTest,help,link,linkLabel}:{label:string;value:string;placeholder:string;onSave:(v:string)=>void;onTest:(v:string)=>Promise<void>;help:'youtube'|'claude'|'gemini';link:string;linkLabel:string}){
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

function ServidorCard(){
  const {settings,setSettings,toast}=useApp();
  const [url,setUrl]=useState(settings.servidor||'http://localhost:8787'); const [tok,setTok]=useState(settings.servidorToken);
  const [busy,setBusy]=useState(false); const [info,setInfo]=useState('');
  const [cookies,setCookies]=useState<boolean|null>(null);
  useEffect(()=>{ if(settings.servidor) testarServidor(settings.servidor,settings.servidorToken).then(s=>setCookies(s.cookies??null)).catch(()=>{}); },[settings.servidor,settings.servidorToken]);
  async function salvar(){
    setBusy(true); setInfo('');
    try{ const s=await testarServidor(url,tok); setSettings({servidor:url.trim().replace(/\/+$/,''),servidorToken:tok.trim()}); setInfo(`Conectado (versão ${s.versao}, vídeos até ${Math.round(s.max_minutos)} min).`); toast('Servidor conectado! Agora é só colar o link em Gerar cortes.','ok'); }
    catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }
    finally{ setBusy(false); }
  }
  return <section className="panel config-card">
    <div className="config-icon srv"><Server size={22}/></div>
    <div className="config-body">
     <div className="section-head"><h2>Cortes direto pelo link do YouTube <span className="tag">opcional</span></h2></div>
     <p className="subtitle">Com o servidor aberto no seu computador, você cola o link e o site baixa, analisa e corta sozinho. Sem ele, envie o arquivo do vídeo. Não sabe como? Clique em <b>Como ligar?</b>.</p>
     <div className="key-field">
      <label className="key-label">Endereço do servidor <HelpButton topic="servidor" label="Como ligar?"/></label>
      <div className="key-row">
       <div className="input-wrap"><Server size={16}/><input value={url} onChange={e=>setUrl(e.target.value)} placeholder="http://localhost:8787" spellCheck={false}/></div>
       <button className="primary" disabled={!url.trim()||busy} onClick={salvar}>{busy?<Loader2 size={16} className="spin"/>:<CheckCircle2 size={16}/>} Testar e salvar</button>
       {settings.servidor&&<button className="subtle" title="Desligar servidor" onClick={()=>{setSettings({servidor:'',servidorToken:''});setInfo('');toast('Servidor desligado neste navegador.')}}><Trash2 size={16}/></button>}
      </div>
      <label className="mt">Senha do servidor (só se você definiu uma)<input type="password" value={tok} onChange={e=>setTok(e.target.value)} placeholder="Deixe vazio no servidor do seu computador" autoComplete="off"/></label>
      <div className="key-foot">{settings.servidor?<span className="tag ok">Servidor salvo: {settings.servidor}</span>:<span className="tag warn">Nenhum servidor</span>}{info&&<span className="tag ok">{info}</span>}</div>
     </div>
     {settings.servidor&&<div className="key-field cookies-box">
      <label className="key-label">YouTube pede login ("confirme que não é robô")? <HelpButton topic="cookies" label="Como resolver?"/></label>
      <p className="hint">Envie o arquivo <b>cookies.txt</b> do YouTube. Ele fica só no seu servidor e faz o download entrar como se fosse você no navegador. {cookies===true?<span className="tag ok">Cookies enviados</span>:cookies===false?<span className="tag">Sem cookies</span>:null}</p>
      <div className="key-row">
       <label className="subtle file-btn"><Upload size={15}/> Enviar cookies.txt<input type="file" accept=".txt,text/plain" hidden onChange={async e=>{ const f=e.target.files?.[0]; e.target.value=''; if(!f) return; try{ const r=await enviarCookies(settings.servidor,settings.servidorToken,await f.text()); setCookies(r.cookies); toast('Cookies salvos no servidor. Tente o link de novo.','ok'); }catch(er){ toast(er instanceof Error?er.message:String(er),'erro'); } }}/></label>
       {cookies&&<button className="subtle" onClick={async()=>{ try{ await enviarCookies(settings.servidor,settings.servidorToken,null); setCookies(false); toast('Cookies apagados do servidor.'); }catch(er){ toast(er instanceof Error?er.message:String(er),'erro'); } }}><Trash2 size={15}/> Apagar cookies</button>}
      </div>
     </div>}
    </div>
   </section>;
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
     <div className="section-head"><h2>Notas com IA <span className="tag">opcional</span></h2></div>
     <p className="subtitle">Sem chave tudo funciona, mas as notas vêm só do áudio. Com uma IA, ela lê o que é falado, dá notas de gancho, fluxo, valor e tendência, escreve títulos e encontra trechos pelo seu pedido. Use o <b>Gemini</b> (Google, tem cota grátis) ou a <b>Claude</b> (Anthropic, paga por uso).</p>
     <KeyField label="Chave do Gemini (Google AI Studio)" value={settings.geminiKey} placeholder="Cole aqui a chave do Gemini (começa com AIza...)" onSave={v=>setSettings({geminiKey:v})} onTest={async k=>{ const {testarChaveGemini,erroGemini}=await import('../lib/gemini'); try{ await testarChaveGemini(k); }catch(e){ throw new Error(erroGemini(e)); } }} help="gemini" link="https://aistudio.google.com/apikey" linkLabel="Abrir Google AI Studio"/>
     <KeyField label="Chave da API da Claude" value={settings.claudeKey} placeholder="Cole aqui a chave que começa com sk-ant-..." onSave={v=>setSettings({claudeKey:v})} onTest={async k=>{ const {testarChaveClaude,erroAmigavel}=await import('../lib/ai'); try{ await testarChaveClaude(k); }catch(e){ throw new Error(erroAmigavel(e)); } }} help="claude" link="https://console.anthropic.com/settings/keys" linkLabel="Abrir console da Anthropic"/>
     {settings.geminiKey&&settings.claudeKey&&<label className="mt">Qual IA dá as notas?<select value={iaAtiva(settings)||''} onChange={e=>setSettings({ia:e.target.value as 'gemini'|'claude'})}><option value="gemini">Gemini (Google)</option><option value="claude">Claude (Anthropic)</option></select></label>}
    </div>
   </section>

   <ServidorCard/>

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
