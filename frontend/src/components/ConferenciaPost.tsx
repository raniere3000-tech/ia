import { useState } from 'react';
import { CheckCircle2, Loader2, ShieldCheck, TriangleAlert, XCircle } from 'lucide-react';
import { api } from '../lib/api';
import { useCfg, erroTexto } from './Servidor2';
import { AVISO_LIBERAR } from '../lib/agenda';

type Item={item:string;ok:boolean;bloqueia:boolean;detalhe:string;liberavel?:boolean;liberado?:boolean};
const NOME:Record<string,string>={arquivo:'Arquivo',versao:'Versão',conta:'Conta e permissões',duracao:'Duração',direitos:'Direitos',origem_do_corte:'Origem do corte',aprovacao:'Aprovação (mesmo arquivo aprovado)',qualidade:'Qualidade (QA)',creditos:'Créditos',boas_praticas:'Boas práticas',formato:'Formato da plataforma'};
const ESTADO:Record<string,[string,string]>={agendado:['agendado',''],postando:['postando agora','warn'],postado:['postado','ok'],erro:['deu erro','bad'],manual:['você posta no app',''],bloqueado:['bloqueado','bad'],cancelado:['cancelado',''],liberacao:['esperando sua liberação','warn']};
type Estado={status:string;erro:string;link:string};

/** Portões do Agente 2: o mesmo que o servidor confere na hora de postar, para ver antes. */
export default function ConferenciaPost({id,onLiberado}:{id:string;onLiberado?:()=>void}){
  const cfg=useCfg();
  const [res,setRes]=useState<Record<string,Item[]>|null>(null); const [est,setEst]=useState<Record<string,Estado>>({}); const [hash,setHash]=useState(''); const [busy,setBusy]=useState(false); const [erro,setErro]=useState('');
  const conferir=async()=>{ setBusy(true); setErro(''); try{ const r=await api<{redes:Record<string,Item[]>;estados?:Record<string,Estado>;hash?:string}>(cfg,'GET',`/api/v1/posts/${id}/conferencia`); setRes(r.redes); setEst(r.estados||{}); setHash(r.hash||''); }catch(e){ setErro(erroTexto(e)); }finally{ setBusy(false); } };
  const liberar=async()=>{ if(!window.confirm(AVISO_LIBERAR)) return; setBusy(true); try{ await api(cfg,'POST',`/posts/${id}/liberar`,{}); onLiberado?.(); await conferir(); }catch(e){ setErro(erroTexto(e)); setBusy(false); } };
  const pedeLib=!!res&&Object.values(res).some(i=>i.some(x=>x.liberavel));
  return <div className="conf-post">
   <button className="link-btn" disabled={busy} onClick={conferir}>{busy?<Loader2 size={13} className="spin"/>:<ShieldCheck size={13}/>} Conferir antes de postar</button>
   {erro&&<p className="hint bad">{erro}</p>}
   {res&&!Object.keys(res).length&&<p className="hint">Nada para o servidor conferir: as redes deste post são postadas por você no app.</p>}
   {res&&hash&&<p className="hint">Arquivo conferido: <code>{hash}</code> (se o vídeo mudar, a aprovação vale só para o arquivo novo depois de aprovado de novo).</p>}
   {res&&est.kwai&&<p className="hint">Kwai: você posta pelo app (o servidor não confere nem posta).</p>}
   {res&&Object.entries(res).map(([rede,itens])=><div key={rede} className="conf-rede"><b>{rede.charAt(0).toUpperCase()+rede.slice(1)}</b>
    {est[rede]&&<span className={'tag '+(ESTADO[est[rede].status]?.[1]||'')}>{ESTADO[est[rede].status]?.[0]||est[rede].status}</span>}
    {est[rede]?.erro&&<p className="hint bad">Motivo: {est[rede].erro}</p>}
    {est[rede]?.link&&<a className="help-link" href={est[rede].link} target="_blank" rel="noreferrer">ver o post</a>}
    <ul>{itens.map(x=><li key={x.item} className={x.ok?'ok':x.bloqueia?'bad':'warn'}>{x.ok?<CheckCircle2 size={13}/>:x.bloqueia?<XCircle size={13}/>:<TriangleAlert size={13}/>} <span><b>{NOME[x.item]||x.item}:</b> {x.detalhe}</span></li>)}</ul>
    {itens.some(x=>x.bloqueia&&!x.liberavel)?<p className="hint bad">Não vai postar nesta rede até resolver: {itens.filter(x=>x.bloqueia&&!x.liberavel).map(x=>NOME[x.item]||x.item).join(', ')}.</p>
     :itens.some(x=>x.liberavel)?<p className="hint warn">Só falta a sua liberação especial ({itens.filter(x=>x.liberavel).map(x=>NOME[x.item]||x.item).join(', ')}). Sem ela, nada é postado.</p>
     :<p className="hint">Pronto para postar nesta rede.</p>}
   </div>)}
   {pedeLib&&<button className="primary sm" disabled={busy} onClick={liberar}><ShieldCheck size={14}/> Liberar e postar mesmo assim</button>}
  </div>;
}
