import type { Post, Rede, StatusRede } from './agenda.ts';

export type FiltroPost='pendentes'|'nao_agendados'|'agendados'|'atrasados'|'erros'|'publicados'|'pausados'|'cancelados'|'todos';
export const FILTROS_POST:[FiltroPost,string][]=[['pendentes','Todos os pendentes'],['nao_agendados','Ainda não agendados'],['agendados','Agendados'],['atrasados','Atrasados'],['erros','Com erro'],['publicados','Publicados'],['pausados','Pausados'],['cancelados','Cancelados'],['todos','Todos']];
export const horaDaRede=(p:Post,r?:StatusRede)=>r?.quando??p.quando;
export const mesmoVideo=(a:Post,b:Post)=>a.video===b.video||!!a.hash&&a.hash===b.hash;
const prioridade:Record<string,number>={postado:7,postando:6,agendado:5,manual:4,liberacao:3,erro:2,cancelado:1};
export function donoDaRede(p:Post,rede:Rede,todos:Post[]){
  return todos.filter(x=>mesmoVideo(x,p)&&x.redes[rede]).sort((a,b)=>(prioridade[b.redes[rede]!.status]||0)-(prioridade[a.redes[rede]!.status]||0))[0]||p;
}
export function corresponde(p:Post,filtro:FiltroPost,rede:Rede|'',agora=Date.now()/1000){
  const estados=rede?(p.redes[rede]?[p.redes[rede]!]:[]):Object.values(p.redes).filter((x):x is StatusRede=>!!x);
  const disponivel=p.arquivo_disponivel!==false&&!p.preparando;
  if(filtro==='todos') return true;
  if(rede&&!estados.length) return disponivel&&(filtro==='pendentes'||filtro==='nao_agendados');
  return estados.some(s=>{
    if(filtro==='publicados') return s.status==='postado';
    if(filtro==='pendentes') return ['agendado','postando','manual','liberacao','erro'].includes(s.status);
    if(filtro==='pausados') return !!s.lote_pausado&&s.status!=='postado'&&s.status!=='cancelado';
    if(filtro==='cancelados') return s.status==='cancelado';
    if(filtro==='erros') return s.status==='erro';
    if(filtro==='agendados') return ['agendado','manual'].includes(s.status)&&!s.lote_pausado&&horaDaRede(p,s)>agora;
    if(filtro==='atrasados') return ['agendado','manual'].includes(s.status)&&!s.lote_pausado&&horaDaRede(p,s)<=agora;
    return false;
  });
}
export function filtrarPosts(posts:Post[],rede:Rede|'',filtro:FiltroPost,agora=Date.now()/1000){
  const vistos=new Set<string>();
  return posts.map(p=>rede?donoDaRede(p,rede,posts):p).filter(p=>{
    if(vistos.has(p.id)) return false;
    vistos.add(p.id);
    return corresponde(p,filtro,rede,agora);
  }).sort((a,b)=>horaDaRede(a,rede?a.redes[rede]:undefined)-horaDaRede(b,rede?b.redes[rede]:undefined));
}
