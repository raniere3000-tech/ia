// Exportar a Montagem manual no servidor do celular (alternativa a gravar no navegador).
// O site manda só DADOS: as mídias usadas (enviadas uma vez, pela impressão digital), o som já misturado aqui
// e um manifesto com o tempo, a animação, o efeito e os textos de cada bloco. O servidor faz o vídeo com o FFmpeg.
import { api, baixarAsset, enviarArquivo, type CfgSrv } from './api';
import { estiloDe, totalDe, type ClipT, type ClipV, type Proj } from './editor';
import type { Arquivo } from './montagem';

export type Diagnostico = {etapa:string;erro:string;comando?:string;quadro?:number;inicio?:number;fim?:number;midia?:string;timecode?:string};
export type EstadoExport = {id:string;status:string;etapa:string;progresso:number;erro:string|null;tentativas:number;diagnostico?:Diagnostico|null;
  resultado?:{asset:string;duracao:number;avisos:string[];refeitos:number;reaproveitados:number;tamanho_mb:number}|null};
type QuadroM = {n:number;asset?:string;dur:number;anim:string;de:number;entrada:'corte'|'fade';brilho:number;contraste:number;saturacao:number;efeito:string;visual:string};

/** WAV estéreo 16 bits do som misturado no navegador. */
export function wavEstereo(b:AudioBuffer):Blob{
  const n=b.length, ch=Math.min(2,b.numberOfChannels), L=b.getChannelData(0), R=ch>1?b.getChannelData(1):L;
  const buf=new ArrayBuffer(44+n*4); const v=new DataView(buf);
  const s=(o:number,t:string)=>{ for(let i=0;i<t.length;i++) v.setUint8(o+i,t.charCodeAt(i)); };
  s(0,'RIFF'); v.setUint32(4,36+n*4,true); s(8,'WAVE'); s(12,'fmt '); v.setUint32(16,16,true); v.setUint16(20,1,true); v.setUint16(22,2,true);
  v.setUint32(24,b.sampleRate,true); v.setUint32(28,b.sampleRate*4,true); v.setUint16(32,4,true); v.setUint16(34,16,true); s(36,'data'); v.setUint32(40,n*4,true);
  for(let i=0,o=44;i<n;i++,o+=4){ const a=Math.max(-1,Math.min(1,L[i])), c=Math.max(-1,Math.min(1,R[i]));
    v.setInt16(o,a<0?a*0x8000:a*0x7fff,true); v.setInt16(o+2,c<0?c*0x8000:c*0x7fff,true); }
  return new Blob([buf],{type:'audio/wav'});
}

/** Transforma os blocos de vídeo do editor em quadros em sequência (vão vazio vira tela escura; o que se sobrepõe é cortado). */
export function quadrosDe(p:Proj,ids:Map<string,string>):{quadros:QuadroM[];avisos:string[]}{
  const vs=p.clips.filter((c):c is ClipV=>c.faixa==='video').sort((a,b)=>a.ini-b.ini);
  const total=totalDe(p); const out:QuadroM[]=[]; const avisos:string[]=[]; let t=0;
  const vazio=(dur:number)=>out.push({n:out.length+1,dur:+dur.toFixed(3),anim:'parado',de:0,entrada:'corte',brilho:100,contraste:100,saturacao:100,efeito:'nenhum',visual:''});
  vs.forEach((c,i)=>{
    if(c.ini>t+0.05) vazio(c.ini-t);
    const ini=Math.max(c.ini,t); const prox=vs[i+1]; const fim=Math.min(c.ini+c.dur,prox?Math.max(prox.ini,ini):Infinity);
    const dur=fim-ini;
    if(dur<0.2){ if(dur>0.01) avisos.push(`Um bloco de ${dur.toFixed(2)} s ficou de fora (curto demais).`); t=Math.max(t,fim); return; }
    out.push({n:out.length+1,asset:c.midia?ids.get(c.midia):undefined,dur:+dur.toFixed(3),anim:c.anim,de:+(c.de+(ini-c.ini)).toFixed(3),entrada:c.entrada,
      brilho:c.brilho,contraste:c.contraste,saturacao:c.saturacao,efeito:c.efeito||'nenhum',visual:''});
    t=fim;
  });
  if(total>t+0.05) vazio(total-t);
  return {quadros:out,avisos};
}

export async function exportarNoServidor(cfg:CfgSrv,p:Proj,arquivos:Arquivo[],audio:AudioBuffer|null,nome:string,onStatus:(t:string)=>void):Promise<{job:string;avisos:string[]}>{
  const usados=[...new Set(p.clips.filter((c):c is ClipV=>c.faixa==='video'&&!!c.midia).map(c=>c.midia))];
  const ids=new Map<string,string>();
  for(const [k,id] of usados.entries()){
    const a=arquivos.find(x=>x.id===id); if(!a) continue;
    onStatus(`Enviando as mídias para o celular (${k+1} de ${usados.length})`);
    const info=await enviarArquivo(cfg,a.blob,a.nome,'',undefined,f=>onStatus(`Enviando ${a.nome}: ${Math.round(f*100)}%`));
    ids.set(id,info.id);
  }
  let somId:string|undefined;
  if(audio){ onStatus('Enviando o som misturado'); somId=(await enviarArquivo(cfg,wavEstereo(audio),'som-da-montagem.wav','',undefined,f=>onStatus(`Enviando o som: ${Math.round(f*100)}%`))).id; }
  const {quadros,avisos}=quadrosDe(p,ids);
  const ts=p.clips.filter((c):c is ClipT=>c.faixa==='texto'&&!!c.texto.trim());
  if(ts.some(x=>estiloDe(p,x))) avisos.push('Os estilos animados de legenda saem como texto simples no vídeo feito no celular.');
  if(p.clips.some(c=>c.faixa==='video'&&c.efeito==='blur-background'&&c.anim!=='parado')) avisos.push('Com "Fundo desfocado", o movimento da imagem fica parado no vídeo do celular.');
  const textos=ts.map(x=>({ini:x.ini,fim:x.ini+x.dur,texto:x.texto,pos:x.pos,tam:x.tam,cor:x.cor,fundo:x.fundo}));
  onStatus('Pedindo o vídeo ao celular');
  const r=await api<{job:string}>(cfg,'POST','/api/v1/exportar',{formato:p.formato,nome,audio:somId,legendas:false,textos,quadros});
  return {job:r.job,avisos};
}

export const estadoExport=(cfg:CfgSrv,id:string)=>api<EstadoExport>(cfg,'GET','/api/v1/exportar/'+id);
export const baixarVideo=(cfg:CfgSrv,asset:string)=>baixarAsset(cfg,asset);
