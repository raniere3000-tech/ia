// Radar do YouTube executado direto no navegador com a chave do próprio usuário.
export type Video = {id:string;titulo:string;canal:string;canal_id:string;link:string;link_canal:string;views:number|null;velocidade:number|null;duracao_segundos:number;publicado:string;thumbnail?:string;likes:number|null;comentarios:number|null};
export type Canal = {id:string;nome:string;link:string;videos:number;views:number;melhor:Video;inscritos:number|null;thumbnail?:string};
export type RadarParams = {tema:string;dias:number;views:number;minutos:number;ordem:string;regiao:string;idioma:string};

const API='https://www.googleapis.com/youtube/v3';

function isoSeconds(iso:string){
  const m=/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/.exec(iso||'');
  return m? (+(m[1]||0))*3600+(+(m[2]||0))*60+(+(m[3]||0)) : 0;
}
async function getJSON(url:string){
  const r=await fetch(url); const data=await r.json().catch(()=>({}));
  if(!r.ok){
    const reason=data?.error?.errors?.[0]?.reason||'';
    if(reason==='quotaExceeded') throw new Error('A cota diária gratuita da YouTube Data API acabou. Ela renova à meia-noite (horário do Pacífico).');
    if(reason==='keyInvalid'||/API key not valid/i.test(data?.error?.message||'')) throw new Error('Chave do YouTube inválida. Confira em Configurações.');
    if(reason==='accessNotConfigured') throw new Error('A YouTube Data API v3 não está ativada no seu projeto do Google Cloud. Veja o passo 3 da ajuda em Configurações.');
    if(r.status===403) throw new Error('O Google recusou a chave (403). Se você restringiu a chave por site, inclua este endereço na lista. Detalhe: '+(data?.error?.message||''));
    throw new Error('YouTube Data API: '+(data?.error?.message||r.statusText));
  }
  return data;
}
const num=(v:any)=>v===undefined||v===null?null:+v;
function decode(s:string){ const t=document.createElement('textarea'); t.innerHTML=s; return t.value; }

export async function testarChaveYouTube(key:string){
  await getJSON(`${API}/videos?${new URLSearchParams({part:'id',chart:'mostPopular',maxResults:'1',regionCode:'BR',key})}`);
}

export async function radarDireto(key:string,p:RadarParams){
  const since=new Date(Date.now()-p.dias*86400000).toISOString();
  const q:Record<string,string>={part:'snippet',type:'video',maxResults:'50',q:p.tema||'',publishedAfter:since,key,order:p.ordem==='views'?'viewCount':p.ordem==='recentes'?'date':'relevance'};
  if(p.regiao) q.regionCode=p.regiao;
  if(p.idioma) q.relevanceLanguage=p.idioma;
  if(p.minutos>=20) q.videoDuration='long'; else if(p.minutos>=4) q.videoDuration='medium';
  const search=await getJSON(`${API}/search?${new URLSearchParams(q)}`);
  const items:any[]=search.items||[];
  const ids=items.map(i=>i?.id?.videoId).filter(Boolean);
  if(!ids.length) return [] as Video[];
  const stats=await getJSON(`${API}/videos?${new URLSearchParams({part:'statistics,contentDetails',id:ids.join(','),key})}`);
  const meta=new Map<string,any>((stats.items||[]).map((i:any)=>[i.id,i]));
  const out:Video[]=[];
  for(const i of items){
    const id=i?.id?.videoId; const m=meta.get(id); if(!m) continue;
    const views=num(m.statistics?.viewCount); const t=isoSeconds(m.contentDetails?.duration);
    if((views??0)<p.views || t<p.minutos*60) continue;
    const age=Math.max(1,(Date.now()-new Date(i.snippet.publishedAt).getTime())/86400000);
    out.push({id,titulo:decode(i.snippet.title),canal:decode(i.snippet.channelTitle),canal_id:i.snippet.channelId,link:'https://www.youtube.com/watch?v='+id,link_canal:'https://www.youtube.com/channel/'+i.snippet.channelId,thumbnail:i.snippet.thumbnails?.medium?.url,views,velocidade:views===null?null:Math.round(views/age),duracao_segundos:t,publicado:i.snippet.publishedAt,likes:num(m.statistics?.likeCount),comentarios:num(m.statistics?.commentCount)});
  }
  return ordenar(out,p.ordem);
}

export function ordenar(v:Video[],ordem:string){
  const k=(x:Video)=>ordem==='views'?(x.views??-1):ordem==='recentes'?new Date(x.publicado).getTime():ordem==='engajamento'?((x.likes??0)+(x.comentarios??0))/Math.max(1,x.views??1):(x.velocidade??-1);
  return [...v].sort((a,b)=>k(b)-k(a));
}

/** Agrupa os vídeos por canal e busca os inscritos (1 chamada extra, custo baixo de cota). */
export async function canaisDe(key:string,videos:Video[]):Promise<Canal[]>{
  const map=new Map<string,Canal>();
  for(const v of videos){
    const c=map.get(v.canal_id);
    if(!c) map.set(v.canal_id,{id:v.canal_id,nome:v.canal,link:v.link_canal,videos:1,views:v.views??0,melhor:v,inscritos:null});
    else{ c.videos++; c.views+=v.views??0; if((v.views??0)>(c.melhor.views??0)) c.melhor=v; }
  }
  const ids=[...map.keys()];
  for(let i=0;i<ids.length;i+=50){
    try{
      const d=await getJSON(`${API}/channels?${new URLSearchParams({part:'statistics,snippet',id:ids.slice(i,i+50).join(','),key})}`);
      for(const it of d.items||[]){ const c=map.get(it.id); if(c){ c.inscritos=it.statistics?.hiddenSubscriberCount?null:num(it.statistics?.subscriberCount); c.thumbnail=it.snippet?.thumbnails?.default?.url; } }
    }catch{ /* inscritos ficam como não informado */ }
  }
  return [...map.values()].sort((a,b)=>b.views-a.views);
}
