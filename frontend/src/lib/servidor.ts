// Cliente do servidor opcional (pasta servidor/) que baixa o vídeo do YouTube pelo link.
export type Saude = {ok:boolean;versao:string;yt_dlp:string;senha:boolean;max_minutos:number};

const base=(u:string)=>u.trim().replace(/\/+$/,'');
function headers(token:string){ const h:Record<string,string>={'Content-Type':'application/json'}; if(token) h['X-Token']=token; return h; }

async function pedir(url:string,init?:RequestInit){
  let r:Response;
  try{ r=await fetch(url,init); }
  catch{ throw new Error('Não consegui falar com o servidor. Ele está aberto? Confira o endereço em Chaves e ajustes (ex.: http://localhost:8787).'); }
  if(!r.ok){ let msg=''; try{ msg=(await r.json()).detail; }catch{ /* sem json */ } throw new Error(msg||`O servidor respondeu com erro ${r.status}.`); }
  return r;
}

export async function testarServidor(url:string,token:string):Promise<Saude>{
  if(!/^https?:\/\//i.test(url.trim())) throw new Error('O endereço precisa começar com http:// ou https://');
  const s=await (await pedir(base(url)+'/saude')).json() as Saude;
  if(!s.ok) throw new Error('O servidor não respondeu direito.');
  if(s.senha){ await pedir(base(url)+'/baixar/teste',{headers:headers(token)}).catch(e=>{ if(String(e.message).includes('Senha')) throw e; }); }
  return s;
}

/** Pede ao servidor para baixar o link e devolve o vídeo como arquivo, com progresso de 0 a 100. */
export async function baixarPeloServidor(url:string,token:string,link:string,onPct:(pct:number,etapa:string)=>void,sinal?:{cancelado:boolean}):Promise<File>{
  const b=base(url);
  const {id}=await (await pedir(b+'/baixar',{method:'POST',headers:headers(token),body:JSON.stringify({url:link})})).json();
  onPct(0,'Baixando o vídeo do YouTube');
  let titulo='video';
  for(;;){
    await new Promise(r=>setTimeout(r,1000));
    if(sinal?.cancelado) throw new Error('Cancelado.');
    const s=await (await pedir(`${b}/baixar/${id}`,{headers:headers(token)})).json();
    if(s.status==='erro') throw new Error(s.erro||'O servidor não conseguiu baixar o vídeo.');
    if(s.status==='pronto'){ titulo=s.titulo||titulo; break; }
    onPct(Math.min(99,s.pct||0),'Baixando o vídeo do YouTube');
  }
  onPct(100,'Trazendo o vídeo para o navegador');
  const r=await pedir(`${b}/baixar/${id}/arquivo`,{headers:headers(token)});
  const blob=await r.blob();
  const tipo=blob.type||'video/mp4'; const ext=tipo.includes('webm')?'webm':'mp4';
  const nome=(titulo.replace(/[\\/:*?"<>|]+/g,'').trim().slice(0,80)||'video')+'.'+ext;
  return new File([blob],nome,{type:tipo});
}
