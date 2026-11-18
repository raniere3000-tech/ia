// Sino do site: os mesmos avisos que o servidor manda por e-mail e WhatsApp.
import { api, type CfgSrv } from './api';

export type Alerta={n:number;t:number;tipo:string;nivel:'erro'|'ok'|'info';assunto:string;corpo:string;destino:string};
export type ListaAlertas={alertas:Alerta[];nao_lidas:number;ultimo:number;lido:number};
export const lerAlertas=(c:CfgSrv,desde=0)=>api<ListaAlertas>(c,'GET',`/api/v1/alertas?desde=${desde}&limite=50`);
export const marcarLidas=(c:CfgSrv,ate?:number)=>api<ListaAlertas>(c,'POST','/api/v1/alertas/lidas',ate!=null?{ate}:{});

/** Aviso do navegador (aparece na barra do celular). No Android só funciona pelo service worker. */
export async function avisarNoNavegador(a:Alerta){
  if(typeof Notification==='undefined'||Notification.permission!=='granted') return;
  const op={body:a.corpo.split('\n').filter(Boolean).slice(0,3).join('\n'),icon:'icones/icone-192.png',tag:'alerta-'+a.n,data:{destino:a.destino}};
  try{ const reg=await navigator.serviceWorker?.getRegistration(); if(reg){ await reg.showNotification(a.assunto,op); return; } }catch{ /* sem service worker */ }
  try{ new Notification(a.assunto,op); }catch{ /* navegador não deixa */ }
}

/** Tempo que falta, em palavras simples. */
export function tempoTexto(s?:number|null){
  if(s==null||!isFinite(s)) return '';
  if(s<60) return 'menos de 1 min';
  const m=Math.round(s/60);
  if(m<60) return `~${m} min`;
  return `~${Math.floor(m/60)} h ${m%60?`${m%60} min`:''}`.trim();
}
