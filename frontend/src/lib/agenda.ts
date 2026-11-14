// Cliente do agendador que roda no servidor (celular/PC): contas, envio do vídeo e posts.
export type Prov = 'google'|'meta'|'tiktok';
export type Rede = 'youtube'|'facebook'|'instagram'|'tiktok'|'kwai';
export type Conta = {app:boolean;conectado:boolean;nome:string;client_id:string;paginas:{id:string;nome:string;instagram:string}[];pagina:string;erro:string;verificado?:number};
export type Contas = Record<Prov,Conta>;
export type StatusRede = {status:'agendado'|'postando'|'postado'|'erro'|'manual';link:string;erro:string};
export type Post = {id:string;video:string;criado:number;quando:number;titulo:string;legenda:string;opcoes:{youtube_privacidade:string;tiktok_modo:string};redes:Partial<Record<Rede,StatusRede>>;preparando?:boolean};

export const REDES:{id:Rede;nome:string;prov:Prov|null}[] = [
  {id:'youtube',nome:'YouTube Shorts',prov:'google'},
  {id:'instagram',nome:'Instagram Reels',prov:'meta'},
  {id:'facebook',nome:'Facebook Reels',prov:'meta'},
  {id:'tiktok',nome:'TikTok',prov:'tiktok'},
  {id:'kwai',nome:'Kwai (manual)',prov:null},
];

/** Endereço fixo para onde as redes devolvem o login (cadastre igual no app de cada rede). */
export const enderecoRetorno = ()=>location.origin+location.pathname;

type Cfg = {servidor:string;servidorToken:string};
async function chamar<T=any>(cfg:Cfg,metodo:string,caminho:string,corpo?:unknown,raw?:Blob):Promise<T>{
  if(!cfg.servidor) throw new Error('Ligue o servidor primeiro (Chaves e ajustes > Cortes direto pelo link).');
  const h:Record<string,string>={}; if(cfg.servidorToken) h['X-Token']=cfg.servidorToken;
  if(corpo!==undefined) h['Content-Type']='application/json';
  let r:Response;
  try{ r=await fetch(cfg.servidor+caminho,{method:metodo,headers:h,body:raw??(corpo!==undefined?JSON.stringify(corpo):undefined)}); }
  catch{ throw new Error('Não consegui falar com o servidor. Ele está aberto? (No celular: bash iniciar-termux.sh link)'); }
  const j=await r.json().catch(()=>({}));
  if(!r.ok) throw new Error(j.detail||`O servidor respondeu com erro ${r.status}.`);
  return j as T;
}

/** Pede para o servidor conferir agora se os logins ainda valem. */
export const verificarContas=(c:Cfg)=>chamar<Contas>(c,'POST','/contas/verificar',{});
export const lerContas=(c:Cfg)=>chamar<Contas>(c,'GET','/contas');
export const salvarApp=(c:Cfg,p:Prov,client_id:string,client_secret:string)=>chamar(c,'POST',`/contas/${p}/app`,{client_id,client_secret});
/** Abre o login da rede numa janelinha, para não perder os cortes que estão nesta aba. */
export async function entrar(c:Cfg,p:Prov){
  // Abre a janela já no clique (o navegador bloqueia janelas abertas depois de esperar o servidor).
  const jan=window.open('','login_rede','width=520,height=720');
  try{
    const {url}=await chamar<{url:string}>(c,'POST',`/contas/${p}/login`,{volta:enderecoRetorno()});
    if(jan&&!jan.closed){ try{ localStorage.setItem('studio_login_popup',String(Date.now())); }catch{ /* ignora */ } jan.location.href=url; jan.focus(); }
    else { try{ localStorage.removeItem('studio_login_popup'); }catch{ /* ignora */ } location.href=url; }
  }catch(e){ jan?.close(); throw e; }
}
export const enviarCodigo=(c:Cfg,code:string,state:string)=>chamar<{rede:Prov}>(c,'POST','/contas/codigo',{code,state});
export const escolherPagina=(c:Cfg,pagina:string)=>chamar(c,'POST','/contas/meta/pagina',{pagina});
export const sair=(c:Cfg,p:Prov)=>chamar(c,'POST',`/contas/${p}/sair`,{});

/** Manda o vídeo para o servidor em pedaços de 16 MB (o túnel não aceita arquivos grandes de uma vez). */
export async function enviarVideo(c:Cfg,blob:Blob,nome:string,onPct:(p:number)=>void):Promise<string>{
  const PEDACO=16*1024*1024; let vid='';
  for(let off=0;off<blob.size||off===0;off+=PEDACO){
    const q=new URLSearchParams({offset:String(off),nome}); if(vid) q.set('video',vid);
    const r=await chamar<{video:string}>(c,'POST','/video?'+q,undefined,blob.slice(off,off+PEDACO));
    vid=r.video; onPct(Math.min(99,Math.round((off+PEDACO)/blob.size*100)));
    if(blob.size===0) break;
  }
  onPct(99);
  await chamar(c,'POST',`/video/${vid}/fim`);
  onPct(100);
  return vid;
}

export const criarPost=(c:Cfg,d:{video:string;redes:Rede[];titulo:string;legenda:string;quando:number;youtube_privacidade:string;tiktok_modo:string;modelo?:string;direitos?:{origem:string;nota:string}})=>chamar<Post>(c,'POST','/posts',d);
export const listarPosts=(c:Cfg)=>chamar<{posts:Post[];agora:number}>(c,'GET','/posts');
export const postarAgora=(c:Cfg,id:string)=>chamar(c,'POST',`/posts/${id}/agora`,{});
export const cancelarPost=(c:Cfg,id:string)=>chamar(c,'POST',`/posts/${id}/cancelar`,{});
export const marcarFeito=(c:Cfg,id:string,rede:Rede)=>chamar(c,'POST',`/posts/${id}/feito`,{rede});
/** Baixa o vídeo do post. A senha vai no cabeçalho, nunca no endereço (endereços ficam no histórico). */
export async function baixarVideoPost(c:Cfg,id:string,nome:string){
  const h:Record<string,string>={}; if(c.servidorToken) h['X-Token']=c.servidorToken;
  const r=await fetch(`${c.servidor}/posts/${id}/video`,{headers:h}).catch(()=>null);
  if(!r||!r.ok) throw new Error('Não consegui baixar o vídeo do servidor.');
  const u=URL.createObjectURL(await r.blob()); const a=document.createElement('a'); a.href=u; a.download=(nome.replace(/[\\/:*?"<>|]+/g,'').slice(0,60)||'corte')+'.mp4'; a.click(); setTimeout(()=>URL.revokeObjectURL(u),30000);
}
