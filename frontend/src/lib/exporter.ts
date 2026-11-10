import JSZip from 'jszip';
import { exportarCorte, loadImage, type Template } from './render';
import type { Clip } from './analyze';
import type { Cue, Preset } from './captions';

export function nomeArquivo(c:Clip,i:number,ext:string){
  const slug=c.titulo.normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^a-zA-Z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,40).toLowerCase()||'corte';
  return `${String(i+1).padStart(2,'0')}-${slug}-${c.formato.replace(':','x')}.${ext}`;
}

export async function renderClip(url:string,c:Clip,cues:Cue[],presets:Preset[],template:Template,progress:(n:number)=>void){
  const legenda=presets.find(p=>p.id===c.legenda)||null;
  const logoImg=template.ativo? await loadImage(template.logo) : null;
  return exportarCorte(url,{inicio:c.inicio,fim:c.fim,formato:c.formato},cues,{legenda,efeito:c.efeito,gancho:c.gancho_texto,accent:legenda?.highlightColor||template.cor,template,logoImg},progress);
}

export function baixar(blob:Blob,nome:string){
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=nome; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(a.href),60000);
}

export async function zipar(arquivos:{nome:string;blob:Blob}[],extras:Record<string,string>){
  const z=new JSZip();
  for(const a of arquivos) z.file(a.nome,a.blob);
  for(const [n,t] of Object.entries(extras)) z.file(n,t);
  return z.generateAsync({type:'blob',compression:'STORE'});
}

const srtTime=(s:number)=>{ const ms=Math.round(s*1000); return `${String(Math.floor(ms/3600000)).padStart(2,'0')}:${String(Math.floor(ms/60000)%60).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')},${String(ms%1000).padStart(3,'0')}`; };
export function srtDoCorte(c:Clip,cues:Cue[]){
  return cues.filter(q=>q.end>c.inicio&&q.start<c.fim).map((q,i)=>`${i+1}\n${srtTime(Math.max(0,q.start-c.inicio))} --> ${srtTime(Math.min(c.fim,q.end)-c.inicio)}\n${q.text}\n`).join('\n');
}
