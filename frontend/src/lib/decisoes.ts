// Faixa "Espera a sua decisão": tudo o que está parado esperando você, numa lista só (servidor/decisoes.py).
import { api, ErroApi, type CfgSrv } from './api';

export type Decisao={chave:string;tipo:string;titulo:string;detalhe:string;desde:number|null;ir:{aba:string;extra:string;area:string};botao:string;urgente:boolean;quem:string};
export type ListaDecisoes={itens:Decisao[];urgentes:number;depois:number;total:number;fontes_com_erro:string[];gerado_em:number;
  /** Servidor antigo (sem a lista): só o número do painel, sem os itens. */
  antigo?:boolean};

/** Lê a lista. Servidor sem a rota nova: cai para o número do painel do Início (pelo menos o alarme aparece). */
export async function lerDecisoes(c:CfgSrv):Promise<ListaDecisoes>{
  try{ return await api<ListaDecisoes>(c,'GET','/api/v1/alertas/decisoes'); }
  catch(e){
    if(!(e instanceof ErroApi)||e.status!==404) throw e;
    const r=await api<{totais?:{esperando_decisao?:number|null}}>(c,'GET','/api/v1/dashboard/resumo?periodo=hoje');
    const n=Number(r.totais?.esperando_decisao||0);
    const itens:Decisao[]=n?[{chave:'antigo',tipo:'video',titulo:`${n} ${n===1?'item espera':'itens esperam'} a sua decisão`,
      detalhe:'Atualize o servidor do celular para ver aqui o que é cada um.',desde:null,ir:{aba:'revisar',extra:'',area:'agentes'},botao:'Abrir aprovações',urgente:true,quem:''}]:[];
    return {itens,urgentes:n,depois:0,total:itens.length,fontes_com_erro:[],gerado_em:Date.now()/1000,antigo:true};
  }
}

/** "há 5 min", "há 2 h", "há 3 dias". */
export function haQuanto(t:number|null,agora=Date.now()/1000){
  if(!t) return '';
  const s=Math.max(0,agora-t);
  if(s<90) return 'há menos de 1 min';
  if(s<3600) return `há ${Math.round(s/60)} min`;
  if(s<86400*2) return `há ${Math.round(s/3600)} h`;
  return `há ${Math.round(s/86400)} dias`;
}

/** Aviso na barra do celular para uma decisão nova (só com o site aberto e o aviso permitido). */
export async function avisarDecisao(d:Decisao){
  if(typeof Notification==='undefined'||Notification.permission!=='granted') return;
  const op={body:[d.detalhe,d.quem].filter(Boolean).join(' · '),icon:'icones/icone-192.png',tag:'decisao-'+d.chave,requireInteraction:true,data:{destino:d.ir.aba}};
  const titulo='⚠️ Espera a sua decisão: '+d.titulo;
  try{ const reg=await navigator.serviceWorker?.getRegistration(); if(reg){ await reg.showNotification(titulo,op); return; } }catch{ /* sem service worker */ }
  try{ new Notification(titulo,op); }catch{ /* navegador não deixa */ }
}
