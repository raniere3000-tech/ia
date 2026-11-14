// Salvar no servidor do celular: as áreas de trabalho deste navegador (vídeo animado, montagem, vozes e preferências)
// viram projetos no servidor. Arquivos (imagens, áudios, vídeos) sobem uma vez só (pelo SHA-256).
// Nada é apagado do navegador. Quando dois aparelhos mexem na mesma área, aparece o aviso de conflito.
import { store } from './store';
import { assetsExistentes, baixarAsset, criarProjeto, enviarArquivo, ErroApi, listarProjetos, obterProjeto, salvarProjeto, sha256Hex, type CfgSrv } from './api';

export type AreaId='video'|'manual'|'vozes'|'preferencias';
type BancoDef={db:string;versao:number;lojas:string[]};
type Area={id:AreaId;tipo:string;titulo:string;ls:(k:string)=>boolean;idb:BancoDef[]};

const PREFS=['studio_tour','studio_agente3_briefing','studio_template','studio_radar_salvas','studio_tarja','studio_dub_voz','studio_dub_vol','studio_direitos','studio_direitos_origem','studio_direitos_nota'];
export const AREAS:Area[]=[
  {id:'video',tipo:'video',titulo:'Vídeo animado',ls:k=>k==='studio_video_codigo',idb:[{db:'video_codigo',versao:1,lojas:['midias']}]},
  {id:'manual',tipo:'manual',titulo:'Montagem manual',ls:k=>k.startsWith('studio_manual'),idb:[{db:'montagem_manual',versao:1,lojas:['arquivos']}]},
  {id:'vozes',tipo:'vozes',titulo:'Estúdio de vozes',ls:k=>k.startsWith('studio_vozes_'),idb:[{db:'estudio_vozes',versao:1,lojas:['projetos','personagens','falas','takes']}]},
  {id:'preferencias',tipo:'outro',titulo:'Preferências e pesquisas salvas',ls:k=>PREFS.includes(k),idb:[]},
];

export type EstadoArea={id?:string;rev?:number;sig?:string;quando?:number;remota?:number};
export type EstadoSinc={ligado:boolean;areas:Partial<Record<AreaId,EstadoArea>>};
export const lerEstado=():EstadoSinc=>({ligado:false,areas:{},...store.json<Partial<EstadoSinc>>('studio_sinc',{})});
export const gravarEstado=(e:EstadoSinc)=>store.setJson('studio_sinc',e);

/** Abre o banco do navegador com o MESMO esquema das ferramentas (nunca cria um banco diferente do que elas esperam). */
function abrir(b:BancoDef):Promise<IDBDatabase>{
  return new Promise((res,rej)=>{
    const r=indexedDB.open(b.db,b.versao);
    r.onupgradeneeded=()=>{ for(const l of b.lojas) if(!r.result.objectStoreNames.contains(l)) r.result.createObjectStore(l,{keyPath:'id'}); };
    r.onsuccess=()=>res(r.result); r.onerror=()=>rej(r.error||new Error('Banco do navegador indisponível.'));
  });
}
async function todos(b:BancoDef,loja:string):Promise<Record<string,unknown>[]>{
  const d=await abrir(b);
  try{ if(!d.objectStoreNames.contains(loja)) return [];
    return await new Promise((res,rej)=>{ const q=d.transaction(loja,'readonly').objectStore(loja).getAll(); q.onsuccess=()=>res(q.result as Record<string,unknown>[]); q.onerror=()=>rej(q.error); });
  }finally{ d.close(); }
}
async function gravarTodos(b:BancoDef,loja:string,itens:Record<string,unknown>[],limpar:boolean){
  const d=await abrir(b);
  try{ await new Promise<void>((res,rej)=>{ const t=d.transaction(loja,'readwrite'); const s=t.objectStore(loja); if(limpar) s.clear(); for(const it of itens) s.put(it); t.oncomplete=()=>res(); t.onerror=()=>rej(t.error); }); }
  finally{ d.close(); }
}

type RefArq={__arquivo:string;asset:string;mime:string;tamanho:number;buffer?:boolean};
const CACHE=new Map<string,string>();           // "banco/loja/id/caminho/tamanho" -> sha256 (evita recalcular)

/** Troca cada arquivo por uma referência ao asset do servidor (enviando os que ainda não estão lá). */
async function trocarArquivos(v:unknown,cfg:CfgSrv|null,chave:string,enviados:Map<string,string>,progresso?:(t:string)=>void):Promise<unknown>{
  if(v instanceof Blob||v instanceof ArrayBuffer){
    const b=v instanceof Blob?v:new Blob([v]);
    const ck=`${chave}/${b.size}`;
    let sha=CACHE.get(ck);
    if(!sha){ sha=await sha256Hex(b); CACHE.set(ck,sha); }
    let asset=enviados.get(sha)||'';
    if(cfg&&!asset){ progresso?.(`Enviando arquivo (${Math.round(b.size/1024)} KB)`); const a=await enviarArquivo(cfg,b,'arquivo',undefined,sha); asset=a.id; enviados.set(sha,asset); }
    const r:RefArq={__arquivo:sha,asset,mime:b.type||'',tamanho:b.size}; if(v instanceof ArrayBuffer) r.buffer=true;
    return r;
  }
  if(Array.isArray(v)){ const o=[]; for(let i=0;i<v.length;i++) o.push(await trocarArquivos(v[i],cfg,chave+'/'+i,enviados,progresso)); return o; }
  if(v&&typeof v==='object'&&!(v instanceof Date)){ const o:Record<string,unknown>={}; for(const [k,x] of Object.entries(v)) o[k]=await trocarArquivos(x,cfg,chave+'/'+k,enviados,progresso); return o; }
  return v;
}
async function voltarArquivos(v:unknown,cfg:CfgSrv,cache:Map<string,Blob>):Promise<unknown>{
  if(v&&typeof v==='object'&&!Array.isArray(v)&&'__arquivo' in (v as object)){
    const r=v as RefArq; let b=cache.get(r.__arquivo);
    if(!b){ b=await baixarAsset(cfg,r.asset); b=new Blob([b],{type:r.mime||''}); cache.set(r.__arquivo,b); }
    return r.buffer?await b.arrayBuffer():b;
  }
  if(Array.isArray(v)){ const o=[]; for(const x of v) o.push(await voltarArquivos(x,cfg,cache)); return o; }
  if(v&&typeof v==='object'){ const o:Record<string,unknown>={}; for(const [k,x] of Object.entries(v)) o[k]=await voltarArquivos(x,cfg,cache); return o; }
  return v;
}

export type Retrato={ls:Record<string,string>;idb:Record<string,Record<string,unknown[]>>;vazio:boolean};

/** Fotografia da área: chaves do armazenamento + registros dos bancos (arquivos viram referências). */
export async function retrato(a:Area,cfg:CfgSrv|null,progresso?:(t:string)=>void):Promise<Retrato>{
  const ls:Record<string,string>={};
  try{ const ks:string[]=[]; for(let i=0;i<localStorage.length;i++){ const k=localStorage.key(i)!; if(a.ls(k)) ks.push(k); }
    for(const k of ks.sort()) ls[k]=localStorage.getItem(k)||''; }catch{ /* sem armazenamento */ }
  const idb:Retrato['idb']={};
  let n=Object.keys(ls).length;
  const enviados=new Map<string,string>();
  if(cfg){   // o que o servidor já tem não sobe de novo
    const shas:string[]=[]; for(const [k,v] of CACHE) if(k.startsWith(a.id+':')) shas.push(v);
    if(shas.length){ try{ for(const [s,info] of Object.entries(await assetsExistentes(cfg,shas))) enviados.set(s,info.id); }catch{ /* segue */ } }
  }
  for(const b of a.idb){
    idb[b.db]={};
    for(const loja of b.lojas){
      const itens=await todos(b,loja).catch(()=>[]);
      n+=itens.length;
      const out=[];
      for(const it of itens) out.push(await trocarArquivos(it,cfg,`${a.id}:${b.db}/${loja}/${String(it.id)}`,enviados,progresso));
      idb[b.db][loja]=out;
    }
  }
  return {ls,idb,vazio:n===0};
}

function hashTexto(s:string){ let h=2166136261; for(let i=0;i<s.length;i++){ h^=s.charCodeAt(i); h=Math.imul(h,16777619); } return (h>>>0).toString(16)+':'+s.length; }
export const assinatura=(r:Retrato)=>hashTexto(JSON.stringify(r));

/** Escreve no navegador o que veio do servidor (substitui SÓ esta área; as outras não mudam). */
export async function aplicar(a:Area,dados:Retrato,cfg:CfgSrv){
  const cache=new Map<string,Blob>();
  const idb:Record<string,Record<string,unknown[]>>={};
  for(const [db,lojas] of Object.entries(dados.idb||{})){ idb[db]={}; for(const [l,itens] of Object.entries(lojas)) idb[db][l]=(await voltarArquivos(itens,cfg,cache)) as unknown[]; }
  try{ for(let i=localStorage.length-1;i>=0;i--){ const k=localStorage.key(i)!; if(a.ls(k)&&!(k in (dados.ls||{}))) localStorage.removeItem(k); } }catch{ /* ignora */ }
  for(const [k,v] of Object.entries(dados.ls||{})) store.set(k,v);
  for(const b of a.idb) for(const l of b.lojas) await gravarTodos(b,l,(idb[b.db]?.[l]||[]) as Record<string,unknown>[],true);
}

/** Cópia de segurança LOCAL (.zip) de tudo o que está neste navegador, antes de qualquer envio. Nada é apagado. */
export async function copiaLocal(progresso?:(t:string)=>void){
  const {default:JSZip}=await import('jszip');
  const z=new JSZip();
  const tudo:Record<string,string>={};
  try{ for(let i=0;i<localStorage.length;i++){ const k=localStorage.key(i)!; if(k.startsWith('studio_')&&!['studio_settings','studio_cofre','studio_yt_key'].includes(k)) tudo[k]=localStorage.getItem(k)||''; } }catch{ /* ignora */ }
  z.file('armazenamento.json',JSON.stringify(tudo,null,1));
  for(const a of AREAS) for(const b of a.idb) for(const l of b.lojas){
    progresso?.(`Copiando ${a.titulo}`);
    const itens=await todos(b,l).catch(()=>[]);
    const meta=[];
    for(const it of itens){
      const o:Record<string,unknown>={};
      for(const [k,v] of Object.entries(it)){
        if(v instanceof Blob){ const nome=`${b.db}/${l}/${String(it.id)}-${k}`; z.file(nome,v); o[k]={arquivo:nome,tipo:v.type}; }
        else if(v instanceof ArrayBuffer){ const nome=`${b.db}/${l}/${String(it.id)}-${k}.bin`; z.file(nome,v); o[k]={arquivo:nome}; }
        else o[k]=v;
      }
      meta.push(o);
    }
    z.file(`${b.db}/${l}.json`,JSON.stringify(meta));
  }
  z.file('LEIA.txt','Cópia de segurança do EstúdioClip feita no navegador em '+new Date().toLocaleString('pt-BR')+'.\nAs chaves e senhas NÃO entram nesta cópia.\n');
  const blob=await z.generateAsync({type:'blob'});
  const el=document.createElement('a'); el.href=URL.createObjectURL(blob); el.download=`estudioclip-navegador-${new Date().toISOString().slice(0,10)}.zip`; el.click();
  setTimeout(()=>URL.revokeObjectURL(el.href),5000);
}

// ---------------------------------------------------------------- ciclo de sincronização
export type Situacao='desligado'|'local'|'sincronizando'|'salvo'|'offline'|'conflito'|'erro';
export type Aviso={area:AreaId;tipo:'conflito'|'novidade';titulo:string};
export type Resultado={situacao:Situacao;avisos:Aviso[];detalhe?:string};

const chaveDe=(a:Area)=>'workspace:'+a.id;

/** Uma passada: envia o que mudou aqui e descobre o que mudou em outro aparelho. */
export async function sincronizar(cfg:CfgSrv,progresso?:(t:string)=>void,forcar:AreaId[]=[]):Promise<Resultado>{
  const est=lerEstado();
  if(!est.ligado) return {situacao:'desligado',avisos:[]};
  if(!navigator.onLine) return {situacao:'offline',avisos:[]};
  const avisos:Aviso[]=[];
  let remotos:Record<string,{revisao:number}>={};
  try{ remotos=Object.fromEntries((await listarProjetos(cfg)).projetos.map(p=>[p.id,{revisao:p.revisao}])); }
  catch(e){ return {situacao:e instanceof ErroApi&&e.status===0?'offline':'erro',avisos:[],detalhe:e instanceof Error?e.message:String(e)}; }
  for(const a of AREAS){
    const ea:EstadoArea=est.areas[a.id]||{};
    try{
      const r=await retrato(a,cfg,progresso);
      const sig=assinatura(r);
      const mudouAqui=sig!==ea.sig;
      if(!ea.id){
        if(r.vazio) continue;            // nada desta área neste navegador ainda
        const p=await criarProjeto(cfg,{tipo:a.tipo,titulo:a.titulo,dados:r,origem_chave:chaveDe(a),modo:'navegador'});
        if(p.duplicado&&assinatura(p.dados as Retrato)!==sig){ est.areas[a.id]={id:p.id,rev:-1,sig:'',remota:p.revisao}; avisos.push({area:a.id,tipo:'conflito',titulo:a.titulo}); continue; }
        est.areas[a.id]={id:p.id,rev:p.revisao,sig,quando:Date.now()/1000};
        continue;
      }
      const remota=remotos[ea.id]?.revisao;
      if(remota===undefined){ est.areas[a.id]={}; continue; }      // apagado no servidor: recria na próxima passada
      const mudouLa=remota!==ea.rev;
      if(mudouLa&&!mudouAqui){ est.areas[a.id]={...ea,remota}; avisos.push({area:a.id,tipo:'novidade',titulo:a.titulo}); continue; }
      if(mudouLa&&mudouAqui&&!forcar.includes(a.id)){ est.areas[a.id]={...ea,remota}; avisos.push({area:a.id,tipo:'conflito',titulo:a.titulo}); continue; }
      if(!mudouAqui) continue;
      const m=await salvarProjeto(cfg,ea.id,forcar.includes(a.id)?remota:ea.rev!,{dados:r});
      est.areas[a.id]={id:ea.id,rev:m.revisao,sig,quando:Date.now()/1000};
    }catch(e){
      if(e instanceof ErroApi&&e.status===409){ avisos.push({area:a.id,tipo:'conflito',titulo:a.titulo}); continue; }
      gravarEstado(est);
      return {situacao:e instanceof ErroApi&&e.status===0?'offline':'erro',avisos,detalhe:e instanceof Error?e.message:String(e)};
    }
  }
  gravarEstado(est);
  return {situacao:avisos.some(x=>x.tipo==='conflito')?'conflito':'salvo',avisos};
}

/** Traz para este navegador a versão do servidor de uma área (depois a página recarrega). */
export async function trazerDoServidor(cfg:CfgSrv,area:AreaId){
  const est=lerEstado(); const ea=est.areas[area]; const a=AREAS.find(x=>x.id===area)!;
  if(!ea?.id) throw new Error('Esta área ainda não está no servidor.');
  const p=await obterProjeto(cfg,ea.id);
  await aplicar(a,p.dados as Retrato,cfg);
  est.areas[area]={id:p.id,rev:p.revisao,sig:assinatura(p.dados as Retrato),quando:Date.now()/1000};
  gravarEstado(est);
}
