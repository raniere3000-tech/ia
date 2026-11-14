// Cofre do navegador: guarda as chaves de API e a senha do servidor criptografadas com um PIN.
// Sem o PIN ninguém que pegue o aparelho (ou uma cópia dos dados do navegador) lê as chaves.
// Depois de aberto, as chaves ficam só na memória desta aba (sessionStorage) e somem quando ela fecha.
import { store } from './store';
import type { Settings } from '../state';

export const SEGREDOS = ['ytKey','claudeKey','geminiKey','muapiKey','servidorToken'] as const;
export type Segredos = Partial<Record<typeof SEGREDOS[number],string>>;
type Guardado = {v:1;salt:string;iv:string;dados:string};
const CHAVE='studio_cofre', SESSAO='studio_aberto', VOLTAS=600000;

const b64=(b:ArrayBuffer|Uint8Array)=>{ const u=b instanceof Uint8Array?b:new Uint8Array(b); let s=''; for(const x of u) s+=String.fromCharCode(x); return btoa(s); };
const de64=(s:string)=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
const sessao={
  ler():{seg:Segredos;chave:string}|null{ try{ const v=sessionStorage.getItem(SESSAO); return v?JSON.parse(v):null; }catch{ return null; } },
  gravar(v:{seg:Segredos;chave:string}){ try{ sessionStorage.setItem(SESSAO,JSON.stringify(v)); }catch{ /* sem armazenamento */ } },
  apagar(){ try{ sessionStorage.removeItem(SESSAO); }catch{ /* ignora */ } },
};

export const temCofre=()=>!!store.get(CHAVE);
export const cofreAberto=()=>temCofre()&&!!sessao.ler();
export const podeCofre=()=>typeof crypto!=='undefined'&&!!crypto.subtle;
export function separar(s:Partial<Settings>):{publico:Partial<Settings>;seg:Segredos}{
  const publico:Record<string,unknown>={...s}; const seg:Segredos={};
  for(const k of SEGREDOS){ const v=(s as Record<string,unknown>)[k]; if(typeof v==='string'&&v) seg[k]=v; if(k in publico) publico[k]=''; }
  return {publico:publico as Partial<Settings>,seg};
}
/** Ajustes como estão guardados: com cofre, as chaves vêm só da sessão aberta (ou vazias, se trancado). */
export function salvos():Partial<Settings>{
  const base=store.json<Partial<Settings>>('studio_settings',{});
  if(!temCofre()) return base;
  return {...separar(base).publico,...(sessao.ler()?.seg||{})};
}

async function derivar(pin:string,salt:Uint8Array):Promise<ArrayBuffer>{
  const base=await crypto.subtle.importKey('raw',new TextEncoder().encode(pin),'PBKDF2',false,['deriveBits']);
  return crypto.subtle.deriveBits({name:'PBKDF2',hash:'SHA-256',salt:salt as BufferSource,iterations:VOLTAS},base,256);
}
async function cifrar(bruta:ArrayBuffer,salt:string,seg:Segredos){
  const k=await crypto.subtle.importKey('raw',bruta,'AES-GCM',false,['encrypt']);
  const iv=crypto.getRandomValues(new Uint8Array(12));
  const dados=await crypto.subtle.encrypt({name:'AES-GCM',iv},k,new TextEncoder().encode(JSON.stringify(seg)));
  store.setJson(CHAVE,{v:1,salt,iv:b64(iv),dados:b64(dados)} satisfies Guardado);
}
export async function criarCofre(pin:string,settings:Settings){
  if(!podeCofre()) throw new Error('Este navegador não tem a criptografia necessária (abra o site por https).');
  if(pin.length<6) throw new Error('Use um PIN ou frase com pelo menos 6 caracteres.');
  const salt=crypto.getRandomValues(new Uint8Array(16)); const bruta=await derivar(pin,salt); const {publico,seg}=separar(settings);
  await cifrar(bruta,b64(salt),seg);
  if(!temCofre()) throw new Error('O navegador não deixou guardar o cofre.');
  store.setJson('studio_settings',publico); store.del('studio_yt_key');
  sessao.gravar({seg,chave:b64(bruta)});
}
export async function abrirCofre(pin:string):Promise<Segredos>{
  const g=store.json<Guardado|null>(CHAVE,null); if(!g) throw new Error('Não há cofre neste aparelho.');
  const bruta=await derivar(pin,de64(g.salt));
  try{
    const k=await crypto.subtle.importKey('raw',bruta,'AES-GCM',false,['decrypt']);
    const claro=await crypto.subtle.decrypt({name:'AES-GCM',iv:de64(g.iv)},k,de64(g.dados));
    const seg=JSON.parse(new TextDecoder().decode(claro)) as Segredos;
    sessao.gravar({seg,chave:b64(bruta)}); return seg;
  }catch{ throw new Error('PIN errado.'); }
}
/** Regrava o cofre quando uma chave muda (só com o cofre aberto). Devolve false se está trancado. */
export function atualizarCofre(settings:Settings):boolean{
  const s=sessao.ler(); const g=store.json<Guardado|null>(CHAVE,null); if(!s||!g) return false;
  const {seg}=separar(settings); sessao.gravar({seg,chave:s.chave});
  cifrar(de64(s.chave).buffer as ArrayBuffer,g.salt,seg).catch(()=>{ /* mantém o cofre anterior */ });
  return true;
}
export function trancarCofre(){ sessao.apagar(); }
/** Tira a proteção: as chaves voltam a ficar guardadas sem PIN (precisa estar aberto). */
export function removerCofre(settings:Settings){ store.setJson('studio_settings',settings); store.del(CHAVE); sessao.apagar(); }
/** Esqueceu o PIN: apaga o cofre e as chaves guardadas nele. */
export function apagarCofre(){ store.del(CHAVE); sessao.apagar(); }
