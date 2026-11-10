// Radar do YouTube executado direto no navegador (modo sem servidor).
// A chave é digitada pelo próprio usuário e fica salva apenas no navegador dele.
export type Video = {id:string;titulo:string;canal:string;link:string;link_canal:string;views:number;velocidade:number;duracao_segundos:number;thumbnail?:string};
export type RadarParams = {tema:string;dias:number;views:number;minutos:number;ordem:string;regiao?:string;idioma?:string};

const API = 'https://www.googleapis.com/youtube/v3';

function isoSeconds(iso:string){
  const m = /PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/.exec(iso || '');
  if(!m) return 0;
  return (+(m[1]||0))*3600 + (+(m[2]||0))*60 + (+(m[3]||0));
}

async function getJSON(url:string){
  const r = await fetch(url);
  const data = await r.json().catch(()=>({}));
  if(!r.ok){
    const msg = data?.error?.message || r.statusText;
    throw new Error('YouTube Data API: ' + msg);
  }
  return data;
}

export async function radarDireto(key:string, p:RadarParams){
  const since = new Date(Date.now() - p.dias*86400000).toISOString();
  const q = new URLSearchParams({part:'snippet',type:'video',maxResults:'50',q:p.tema || 'podcast',publishedAfter:since,key,regionCode:p.regiao||'BR',relevanceLanguage:p.idioma||'pt',videoDuration:p.minutos>=20?'long':'any',order:p.ordem==='views'?'viewCount':'relevance'});
  const search = await getJSON(`${API}/search?${q}`);
  const items:any[] = search.items || [];
  const ids = items.map(i=>i?.id?.videoId).filter(Boolean);
  if(!ids.length) return {itens:[] as Video[], nota:''};
  const stats = await getJSON(`${API}/videos?${new URLSearchParams({part:'statistics,contentDetails',id:ids.join(','),key})}`);
  const meta = new Map<string,any>((stats.items||[]).map((i:any)=>[i.id,i]));
  const out:Video[] = [];
  for(const i of items){
    const id = i?.id?.videoId; const m = meta.get(id);
    if(!m) continue;
    const n = +(m.statistics?.viewCount || 0); const t = isoSeconds(m.contentDetails?.duration);
    if(n < p.views || t < p.minutos*60) continue;
    const age = Math.max(1,(Date.now()-new Date(i.snippet.publishedAt).getTime())/86400000);
    out.push({id,titulo:decode(i.snippet.title),canal:decode(i.snippet.channelTitle),link:'https://www.youtube.com/watch?v='+id,link_canal:'https://www.youtube.com/channel/'+i.snippet.channelId,thumbnail:i.snippet.thumbnails?.medium?.url,views:n,velocidade:Math.round(n/age),duracao_segundos:t});
  }
  out.sort((a,b)=>p.ordem==='views'? b.views-a.views : b.velocidade-a.velocidade);
  return {itens:out, nota:'Velocidade estimada = visualizações acumuladas / idade do vídeo em dias; resultados limitados pela API do YouTube.'};
}

function decode(s:string){
  const t = document.createElement('textarea'); t.innerHTML = s; return t.value;
}
