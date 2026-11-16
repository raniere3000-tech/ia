import { useState } from 'react';
import { CheckCircle2, Loader2, ShieldCheck, TriangleAlert, XCircle } from 'lucide-react';
import { api } from '../lib/api';
import { useCfg, erroTexto } from './Servidor2';

type Item={item:string;ok:boolean;bloqueia:boolean;detalhe:string};
const NOME:Record<string,string>={arquivo:'Arquivo',versao:'Versão',conta:'Conta',duracao:'Duração',direitos:'Direitos',origem_do_corte:'Origem do corte',aprovacao:'Aprovação',qualidade:'Qualidade',creditos:'Créditos',boas_praticas:'Boas práticas'};

/** Portões do Agente 2: o mesmo que o servidor confere na hora de postar, para ver antes. */
export default function ConferenciaPost({id}:{id:string}){
  const cfg=useCfg();
  const [res,setRes]=useState<Record<string,Item[]>|null>(null); const [busy,setBusy]=useState(false); const [erro,setErro]=useState('');
  const conferir=async()=>{ setBusy(true); setErro(''); try{ setRes((await api<{redes:Record<string,Item[]>}>(cfg,'GET',`/api/v1/posts/${id}/conferencia`)).redes); }catch(e){ setErro(erroTexto(e)); }finally{ setBusy(false); } };
  return <div className="conf-post">
   <button className="link-btn" disabled={busy} onClick={conferir}>{busy?<Loader2 size={13} className="spin"/>:<ShieldCheck size={13}/>} Conferir antes de postar</button>
   {erro&&<p className="hint bad">{erro}</p>}
   {res&&Object.entries(res).map(([rede,itens])=><div key={rede} className="conf-rede"><b>{rede.charAt(0).toUpperCase()+rede.slice(1)}</b>
    <ul>{itens.map(x=><li key={x.item} className={x.ok?'ok':x.bloqueia?'bad':'warn'}>{x.ok?<CheckCircle2 size={13}/>:x.bloqueia?<XCircle size={13}/>:<TriangleAlert size={13}/>} <span><b>{NOME[x.item]||x.item}:</b> {x.detalhe}</span></li>)}</ul>
    {itens.some(x=>x.bloqueia)?<p className="hint bad">Não vai postar nesta rede até resolver o que está em vermelho.</p>:<p className="hint">Pronto para postar nesta rede.</p>}
   </div>)}
  </div>;
}
