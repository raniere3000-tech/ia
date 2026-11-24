import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Download, Loader2, RefreshCw, X } from 'lucide-react';
import { Modal } from './Help';
import { useApp } from '../state';
import { FORMATOS, cancelarDownload, criarDownload, lerDownload, mb, tentarDeNovo, urlDownload, type FormatoDownload, type JobDownload } from '../lib/download';

/** Baixar vídeos selecionados em Publicações. Não publica, não reagenda e não mexe no status de nenhum post. */
export default function DownloadLote({ids,escopo,onClose}:{ids:string[];escopo:string;onClose:()=>void}){
  const {settings,toast}=useApp();
  const [formato,setFormato]=useState<FormatoDownload>('pacote');
  const [job,setJob]=useState<JobDownload|null>(null);
  const [busy,setBusy]=useState(false);
  const [fila,setFila]=useState<number|null>(null);      // MP4 individuais: índice do próximo da fila
  const viva=useRef(true);
  useEffect(()=>{ viva.current=true; return ()=>{ viva.current=false; }; },[]);

  const atualizar=useCallback(async(id:string)=>{ try{ const j=await lerDownload(settings,id); if(viva.current) setJob(j); return j; }catch(e){ if(viva.current) toast(e instanceof Error?e.message:String(e),'erro'); return null; } },[settings,toast]);
  useEffect(()=>{
    if(!job||job.estado!=='preparando') return;
    const t=setInterval(()=>{ void atualizar(job.id); },1000);
    return ()=>clearInterval(t);
  },[job?.id,job?.estado,atualizar]);   // eslint-disable-line react-hooks/exhaustive-deps

  async function preparar(){ setBusy(true); try{ setJob(await criarDownload(settings,ids,formato)); }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }finally{ setBusy(false); } }
  async function cancelar(){ if(!job) return; setBusy(true); try{ setJob(await cancelarDownload(settings,job.id)); }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }finally{ setBusy(false); } }
  async function repetir(){ if(!job) return; setBusy(true); try{ setJob(await tentarDeNovo(settings,job.id)); }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }finally{ setBusy(false); } }
  function abrir(caminho:string){ const a=document.createElement('a'); a.href=urlDownload(settings,caminho); a.rel='noopener'; document.body.appendChild(a); a.click(); a.remove(); }

  // MP4 individuais: um download por vez, com pausa (o Android bloqueia vários ao mesmo tempo).
  useEffect(()=>{
    if(fila===null||!job) return;
    const lista=job.itens.filter(i=>i.disponivel&&i.url);
    if(fila>=lista.length){ setFila(null); toast('Todos os MP4 foram entregues ao navegador.','ok'); return; }
    abrir(lista[fila].url!);
    const t=setTimeout(()=>setFila(f=>f===null?null:f+1),3000);
    return ()=>clearTimeout(t);
  },[fila]);   // eslint-disable-line react-hooks/exhaustive-deps

  const prog=job&&job.disponiveis?Math.round(100*job.preparados/job.disponiveis):0;
  const fechar=()=>{ if(!busy&&!(job&&job.estado==='preparando')) onClose(); };
  return <Modal title={`Baixar ${ids.length} vídeo(s)`} onClose={fechar} wide>
    {!job&&<>
      <p className="hint">{escopo}</p>
      <div className="seg big" role="radiogroup" aria-label="Formato do download">{FORMATOS.map(([k,t,d])=><button key={k} role="radio" aria-checked={formato===k} className={formato===k?'on':''} onClick={()=>setFormato(k)}><b>{t}{k==='pacote'?' · recomendado':''}</b><small>{d}</small></button>)}</div>
      <p className="hint">Usa os arquivos finais já prontos no servidor: nada é renderizado de novo, nada é publicado e o status dos posts não muda.</p>
      <div className="row-gap left mt"><button className="primary" disabled={busy||!ids.length} onClick={preparar}>{busy?<Loader2 size={14} className="spin"/>:<Download size={14}/>} Preparar download</button><button className="subtle" onClick={onClose}><X size={14}/> Fechar</button></div>
    </>}
    {job&&<>
      <p><b>{FORMATOS.find(f=>f[0]===job.formato)?.[1]}</b> · {job.disponiveis} de {job.total} vídeo(s) disponíveis{job.bytes_total?` · ${mb(job.bytes_total)}`:''}</p>
      {job.estado==='preparando'&&<div role="status"><div className="progresso"><div className="progresso-barra"><div style={{width:Math.max(prog,2)+'%'}}/></div></div>
        <p className="hint"><Loader2 size={13} className="spin"/> Preparando {job.preparados} de {job.disponiveis} ({prog}%) · {mb(job.bytes_feitos)}</p>
        <button className="subtle sm" disabled={busy} onClick={cancelar}><X size={14}/> Cancelar preparo</button></div>}
      {job.estado==='cancelado'&&<p className="hint warn">Preparo cancelado. Os arquivos temporários foram apagados; nenhum vídeo original foi tocado.</p>}
      {job.estado==='falhou'&&<p className="hint bad" role="alert"><AlertTriangle size={14}/> {job.erro||'Não consegui preparar o download.'}</p>}
      {(job.estado==='pronto'||job.estado==='parcial')&&job.formato!=='mp4'&&job.arquivo&&<p>
        {job.estado==='parcial'&&<span className="hint warn" role="alert"><AlertTriangle size={14}/> Resultado parcial: {job.falhas.length+job.itens.filter(i=>!i.disponivel).length} vídeo(s) não entraram. O relatório está dentro do ZIP.<br/></span>}
        {job.estado==='pronto'&&<span className="hint ok"><CheckCircle2 size={14}/> Pronto, completo.<br/></span>}
        <button className="primary" onClick={()=>abrir(job.arquivo!.url)}><Download size={14}/> Baixar {job.arquivo.nome} ({mb(job.arquivo.tamanho)})</button></p>}
      {(job.estado==='pronto'||job.estado==='parcial')&&job.formato==='mp4'&&<div>
        <div className="row-gap left"><button className="primary" disabled={fila!==null} onClick={()=>setFila(0)}>{fila!==null?<Loader2 size={14} className="spin"/>:<Download size={14}/>} Baixar todos, um por vez</button>
          {fila!==null&&<button className="subtle sm" onClick={()=>setFila(null)}>Parar a fila</button>}</div>
        <p className="hint">Se o Android bloquear a fila, toque em cada vídeo abaixo ou escolha o ZIP.</p></div>}
      {job.sem_capa>0&&job.formato==='pacote'&&<p className="hint warn">{job.sem_capa} vídeo(s) sem capa aprovada para a versão final: o MP4 e o texto foram incluídos, a capa não.</p>}
      <ul className="thumb-redes">{job.itens.map(i=><li key={i.n}><b>{i.nome}</b>
        {!i.disponivel&&<span className="tag bad"> indisponível: {i.motivo}</span>}
        {i.disponivel&&i.capa!=='ok'&&job.formato==='pacote'&&<span className="tag warn"> capa {i.capa==='ausente'?'ausente':'desatualizada'}</span>}
        {job.formato==='mp4'&&i.disponivel&&i.url&&<> <button className="link-btn" onClick={()=>abrir(i.url!)}>Baixar este</button></>}</li>)}</ul>
      {job.falhas.length>0&&<><h4>Falhas</h4><ul>{job.falhas.map(f=><li key={f.n}>{f.nome}: {f.motivo}</li>)}</ul></>}
      <div className="row-gap left mt">
        {(job.estado==='parcial'||job.estado==='falhou'||job.estado==='cancelado')&&<button className="primary sm" disabled={busy} onClick={repetir}><RefreshCw size={14}/> Tentar novamente</button>}
        {job.estado!=='preparando'&&<button className="subtle sm" onClick={onClose}><X size={14}/> Fechar</button>}
      </div>
    </>}
  </Modal>;
}
