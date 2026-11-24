import { useState } from 'react';
import { Music2, Copy, ExternalLink, Pencil, X, Save, CheckCircle2, Loader2 } from 'lucide-react';
import { useApp } from '../state';
import { editarTikTok, acaoTikTok, type Post, type TikTokInfo } from '../lib/agenda';

const COR:Record<string,string>={publicado:'ok',falha:'bad',cancelado:'',agendado:'info',enviado_tiktok:'info',aguardando_publicacao_manual:'warn',aguardando_confirmacao:'warn',pendente_envio:'warn'};
export const TIKTOK_UPLOAD='https://www.tiktok.com/upload';

async function copiar(t:string){
  try{ await navigator.clipboard.writeText(t); return; }catch{ /* tenta o jeito antigo */ }
  const a=document.createElement('textarea'); a.value=t; a.style.position='fixed'; a.style.opacity='0'; document.body.appendChild(a); a.select();
  const ok=document.execCommand('copy'); a.remove();
  if(!ok) throw new Error('Não consegui copiar. Segure o texto e copie à mão.');
}

/** Informações do TikTok de um vídeo: ver, editar, copiar, copiar e abrir o TikTok, e confirmar que publicou. */
export default function TikTokInfoPainel({p,acao}:{p:Post;acao:(f:()=>Promise<unknown>,ok:string)=>Promise<void>}){
  const {settings}=useApp();
  const [aberto,setAberto]=useState(false);
  const [editando,setEditando]=useState(false);
  const [busy,setBusy]=useState(false);
  const info:TikTokInfo|undefined=p.tiktok;
  const [titulo,setTitulo]=useState('');
  const [desc,setDesc]=useState('');
  const [tags,setTags]=useState('');
  const [links,setLinks]=useState('');
  if(!info) return null;
  const m=info.meta;
  const comecar=()=>{ setTitulo(m.titulo); setDesc(m.descricao); setTags(m.hashtags.join(' ')); setLinks(m.links.map(l=>l.rotulo?`${l.rotulo} | ${l.url}`:l.url).join('\n')); setEditando(true); };
  const salvar=()=>acao(async()=>{
    setBusy(true);
    try{
      await editarTikTok(settings,p.id,{titulo,descricao:desc,hashtags:tags.split(/\s+/).filter(Boolean),
        links:links.split('\n').map(x=>x.trim()).filter(Boolean).map(x=>{ const [a,...b]=x.split('|'); return b.length?{rotulo:a.trim(),url:b.join('|').trim()}:{rotulo:'',url:x}; })});
      setEditando(false);
    } finally{ setBusy(false); }
  },'Informações do TikTok salvas.');
  const copiarTudo=()=>acao(async()=>{ await copiar(info.texto); await acaoTikTok(settings,p.id,'copiado'); },'Tudo copiado. Cole na descrição do TikTok.');
  const copiarEAbrir=()=>{
    // a janela abre já no clique (o navegador bloqueia janelas abertas depois de esperar o servidor)
    const jan=window.open('about:blank','_blank');
    void acao(async()=>{
      try{ await copiar(info.texto); }catch(e){ jan?.close(); throw e; }
      await acaoTikTok(settings,p.id,'abrir');
      if(jan) jan.location.href=TIKTOK_UPLOAD; else location.href=TIKTOK_UPLOAD;
    },'Copiado. Cole no TikTok e depois toque em "Já publiquei".');
  };
  const confirmar=()=>{
    const link=window.prompt('Cole o link do vídeo no TikTok (pode deixar em branco):','')??null;
    if(link===null) return;
    void acao(()=>acaoTikTok(settings,p.id,'confirmar',link.trim()||undefined),'Marcado como publicado no TikTok.');
  };
  const podeConfirmar=!['publicado','cancelado'].includes(info.estado);
  return <div className="post-tiktok">
    <div className="row-gap left">
      <span className={'tag '+(COR[info.estado]||'')}><Music2 size={12}/> TikTok: {info.rotulo}</span>
      <button className="subtle sm" aria-expanded={aberto} onClick={()=>setAberto(!aberto)}>{aberto?'Fechar informações':'Informações do TikTok'}</button>
    </div>
    {aberto&&<div className="post-editar">
      {!editando?<>
        <div className="field-label">Título</div><p>{m.titulo||<span className="muted">Sem título</span>}</p>
        <div className="field-label">Descrição</div><p style={{whiteSpace:'pre-wrap'}}>{m.descricao||<span className="muted">Sem descrição</span>}</p>
        <div className="field-label">Hashtags</div><p>{m.hashtags.join(' ')||<span className="muted">Sem hashtags</span>}</p>
        <div className="field-label">Links</div>{m.links.length?<ul>{m.links.map(l=><li key={l.url}>{l.rotulo&&<b>{l.rotulo}: </b>}<a href={l.url} target="_blank" rel="noreferrer">{l.url}</a></li>)}</ul>:<p className="muted">Sem links</p>}
        {Object.values(info.origem).includes('gerado')&&<p className="hint">O que estava faltando foi preparado automaticamente a partir do título. Confira antes de publicar.</p>}
        {info.ja_enviado&&<p className="hint">O vídeo já foi encaminhado ao TikTok. Aqui só mudam as informações, o vídeo não é enviado de novo.</p>}
        <div className="row-gap left mt">
          <button className="subtle sm" onClick={comecar}><Pencil size={14}/> Editar</button>
          <button className="subtle sm" onClick={copiarTudo}><Copy size={14}/> Copiar tudo</button>
          <button className="primary sm" onClick={copiarEAbrir}><ExternalLink size={14}/> Copiar e abrir TikTok</button>
          {podeConfirmar&&<button className="subtle sm" onClick={confirmar}><CheckCircle2 size={14}/> Já publiquei</button>}
        </div>
      </>:<>
        <label>Título<input value={titulo} maxLength={150} onChange={e=>setTitulo(e.target.value)}/></label>
        <label>Descrição<textarea rows={6} value={desc} onChange={e=>setDesc(e.target.value)}/></label>
        <label>Hashtags (separadas por espaço)<input value={tags} onChange={e=>setTags(e.target.value)}/></label>
        <label>Links (um por linha; use "Nome | endereço" se quiser um nome)<textarea rows={3} value={links} onChange={e=>setLinks(e.target.value)}/></label>
        <div className="row-gap left mt">
          <button className="primary sm" disabled={busy} onClick={salvar}>{busy?<Loader2 size={14} className="spin"/>:<Save size={14}/>} Salvar</button>
          <button className="subtle sm" disabled={busy} onClick={()=>setEditando(false)}><X size={14}/> Cancelar</button>
        </div>
      </>}
    </div>}
  </div>;
}
