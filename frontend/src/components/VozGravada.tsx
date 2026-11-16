import { useEffect, useMemo, useState } from 'react';
import { Loader2, Mic, Upload, X } from 'lucide-react';
import { useApp } from '../state';
import { useCfg, erroTexto } from './Servidor2';
import { enviarArquivo, type Cena } from '../lib/api';
import { listar, type Personagem, type Take } from '../lib/vozes';

function Ouvir({blob}:{blob:Blob}){
  const url=useMemo(()=>URL.createObjectURL(blob),[blob]);
  useEffect(()=>()=>URL.revokeObjectURL(url),[url]);
  return <audio src={url} controls preload="none" className="take-audio"/>;
}

/** Fala gravada no Estúdio de vozes (ou um arquivo de áudio) no lugar da voz da IA. A boca do personagem segue esse áudio. */
export default function VozGravada({c,mudar,pid}:{c:Cena;mudar:(p:Partial<Cena>)=>void;pid:string}){
  const {settings,toast}=useApp(); const cfg=useCfg();
  const [aberto,setAberto]=useState(false); const [busy,setBusy]=useState('');
  const [takes,setTakes]=useState<Take[]|null>(null); const [pers,setPers]=useState<Record<string,string>>({});
  const [busca,setBusca]=useState('');
  useEffect(()=>{ if(!aberto||takes) return;
    Promise.all([listar<Take>('takes'),listar<Personagem>('personagens')]).then(([t,p])=>{
      setTakes(t.sort((a,b)=>Number(b.aprovado)-Number(a.aprovado)||b.data-a.data)); setPers(Object.fromEntries(p.map(x=>[x.id,x.nome])));
    }).catch(()=>setTakes([])); },[aberto,takes]);
  if(!settings.servidor) return null;
  const usar=async(b:Blob,nome:string,id:string)=>{ setBusy(id); try{ const a=await enviarArquivo(cfg,b,nome,pid); mudar({audio_manual:{asset:a.id,nome}}); setAberto(false); toast('A cena vai usar esta voz. Salve e faça o vídeo.','ok'); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } };
  if(c.audio_manual) return <div className="voz-gravada larga"><Mic size={13}/> Voz gravada: <b>{c.audio_manual.nome||'arquivo'}</b>
    <button className="link-btn" onClick={()=>mudar({audio_manual:null})}><X size={12}/> Voltar para a voz da IA</button></div>;
  const q=busca.trim().toLowerCase();
  const lista=(takes||[]).filter(t=>!q||(t.texto+' '+(pers[t.personagemId]||'')).toLowerCase().includes(q)).slice(0,15);
  return <div className="voz-gravada larga">
   <button className="link-btn" onClick={()=>setAberto(!aberto)}><Mic size={13}/> Usar uma voz gravada (Estúdio de vozes ou arquivo)</button>
   {aberto&&<div className="voz-box">
    <p className="hint">A fala gravada entra no lugar da voz da IA, e a boca do personagem acompanha o som.</p>
    <label className="subtle sm file-btn">{busy==='arq'?<Loader2 size={14} className="spin"/>:<Upload size={14}/>} Enviar arquivo de áudio
     <input type="file" accept="audio/*" hidden onChange={e=>{ const f=e.target.files?.[0]; if(f) usar(f,f.name,'arq'); e.target.value=''; }}/></label>
    {takes===null?<p className="hint"><Loader2 size={13} className="spin"/> Lendo o Estúdio de vozes...</p>
     :takes.length===0?<p className="hint">Nenhuma fala gravada no Estúdio de vozes deste aparelho.</p>
     :<><input value={busca} onChange={e=>setBusca(e.target.value)} placeholder="Procurar pela fala ou pelo personagem"/>
      <ul className="voz-takes">{lista.map(t=><li key={t.id}><div><b>{pers[t.personagemId]||'Personagem'}</b>{t.aprovado&&<span className="tag ok">aprovado</span>} <small>{t.duracao.toFixed(1)} s</small><p>{t.texto.slice(0,120)}</p></div>
       <Ouvir blob={t.wav}/><button className="primary sm" disabled={!!busy} onClick={()=>usar(t.wav,`take-${(pers[t.personagemId]||'voz').toLowerCase()}-${t.id.slice(0,6)}.wav`,t.id)}>{busy===t.id?<Loader2 size={14} className="spin"/>:null} Usar nesta cena</button></li>)}</ul></>}
   </div>}
  </div>;
}
