// Coisas de "aplicativo": instalar no telefone, registrar o service worker e manter a tela acesa em tarefas longas.

type PedidoInstalar = Event & { prompt:()=>Promise<void>; userChoice:Promise<{outcome:'accepted'|'dismissed'}> };
let pedido:PedidoInstalar|null = null;
const ouvintes = new Set<()=>void>();
const avisar = ()=>ouvintes.forEach(f=>f());

/** Já está aberto como aplicativo instalado? */
export const instalado = ()=>typeof window!=='undefined' && (window.matchMedia?.('(display-mode: standalone)').matches || (navigator as any).standalone===true);
/** iPhone/iPad: não tem botão de instalar, é pelo menu Compartilhar do Safari. */
export const ehIOS = ()=>/iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform==='MacIntel' && navigator.maxTouchPoints>1);
export const podeInstalar = ()=>!!pedido;
export function aoMudarInstalacao(f:()=>void){ ouvintes.add(f); return ()=>{ ouvintes.delete(f); }; }

/** Abre a janela do navegador para instalar. Devolve true se a pessoa aceitou. */
export async function instalar(){
  if(!pedido) return false;
  const p=pedido; pedido=null;
  await p.prompt();
  const r=await p.userChoice.catch(()=>({outcome:'dismissed' as const}));
  avisar();
  return r.outcome==='accepted';
}

export function iniciarApp(){
  window.addEventListener('beforeinstallprompt',e=>{ e.preventDefault(); pedido=e as PedidoInstalar; avisar(); });
  window.addEventListener('appinstalled',()=>{ pedido=null; avisar(); });
  if(import.meta.env.PROD && 'serviceWorker' in navigator){
    window.addEventListener('load',()=>{ navigator.serviceWorker.register(import.meta.env.BASE_URL+'sw.js',{scope:import.meta.env.BASE_URL}).catch(()=>{ /* sem service worker o site funciona igual */ }); });
  }
}

/** Mantém a tela do telefone acesa enquanto a tarefa roda (se a tela apaga, a gravação do vídeo para). */
export async function comTelaAcesa<T>(f:()=>Promise<T>):Promise<T>{
  let trava:any=null;
  const pedir=async()=>{ try{ trava=await (navigator as any).wakeLock?.request('screen'); }catch{ trava=null; } };
  const voltar=()=>{ if(document.visibilityState==='visible') pedir(); };
  await pedir(); document.addEventListener('visibilitychange',voltar);
  try{ return await f(); }
  finally{ document.removeEventListener('visibilitychange',voltar); try{ await trava?.release(); }catch{ /* já solta */ } }
}
