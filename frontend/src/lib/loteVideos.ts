// Lote de vídeos curtos (Shorts do Radar ou links do TikTok): baixa cada um pelo servidor
// e transforma em um "corte" com o vídeo inteiro, pronto para template, legenda e postagem.
import type { Settings } from '../state';
import type { Clip } from './analyze';
import { baixarPeloServidor } from './servidor';
import { videoInfo, captureFrames } from './media';
import { uid } from './store';

export type ItemLote = {link:string;titulo?:string};

/** Lê vários links colados (um por linha), só YouTube e TikTok, sem repetir. */
export function lerLinks(txt:string):ItemLote[]{
  const vistos=new Set<string>(); const out:ItemLote[]=[];
  for(const m of txt.matchAll(/https?:\/\/[^\s<>"']+/g)){
    const l=m[0].replace(/[),.;]+$/,'');
    if(!/(youtube\.com|youtu\.be|tiktok\.com)\//i.test(l)||vistos.has(l)) continue;
    vistos.add(l); out.push({link:l});
  }
  return out;
}

export async function baixarLote(s:Settings,itens:ItemLote[],onStatus:(txt:string,pct:number)=>void,sinal:{cancelado:boolean}){
  const clips:Clip[]=[]; const erros:string[]=[];
  for(let i=0;i<itens.length;i++){
    const it=itens[i]; const pre=`Vídeo ${i+1} de ${itens.length}`;
    if(sinal.cancelado) break;
    try{
      const file=await baixarPeloServidor(s.servidor,s.servidorToken,it.link,(p,e)=>onStatus(`${pre}: ${e}`,Math.round((i+p/100)/itens.length*100)),sinal);
      const url=URL.createObjectURL(file);
      const info=await videoInfo(url);
      const [thumb]=await captureFrames(url,[Math.min(Math.max(0,info.duration-0.1),1.5)],320).catch(()=>[] as string[]);
      const titulo=(it.titulo||file.name.replace(/\.\w+$/,'')).slice(0,90);
      clips.push({id:uid(),titulo,inicio:0,fim:+info.duration.toFixed(2),notas:{gancho:0,fluxo:0,valor:0,tendencia:0},nota_final:0,nota_10:0,
        motivo:'Vídeo inteiro, sem cortes.',fonte:'heuristica',legenda:s.legendaPadrao,efeito:s.efeitoPadrao,formato:'9:16',gancho_texto:'',thumb,
        video:{url,file,cues:[],duracao:info.duration,link:it.link}});
    }catch(e){
      if(sinal.cancelado) break;
      erros.push(`${it.titulo||it.link}: ${e instanceof Error?e.message:String(e)}`);
    }
  }
  onStatus('Pronto',100);
  return {clips,erros};
}
