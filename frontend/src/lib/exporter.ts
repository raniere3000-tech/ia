import { rastrearRosto, type Trilha } from './rosto';
import { pegarDub } from './dublagem';
import { exportarCorte, loadImage, type Template } from './render';
import { cuesDe, urlDe, type Clip } from './analyze';
import type { Cue, Preset } from './captions';

export function nomeArquivo(c:Clip,i:number,ext:string){
  const slug=c.titulo.normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^a-zA-Z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,40).toLowerCase()||'corte';
  return `${String(i+1).padStart(2,'0')}-${slug}-${c.formato.replace(':','x')}.${ext}`;
}

export async function renderClip(urlProj:string,c:Clip,cuesProj:Cue[],presets:Preset[],template:Template,progress:(n:number)=>void){
  const url=urlDe(c,urlProj), cues=cuesDe(c,cuesProj);
  if(c.semTemplate) template={...template,ativo:false};
  const legenda=presets.find(p=>p.id===c.legenda)||null;
  const logoImg=template.ativo? await loadImage(template.logo) : null;
  let rosto:Trilha|null|undefined;
  if(c.efeito==='seguir-rosto'){
    // 1ª parte da barra: achar o rosto; 2ª: gravar.
    try{ rosto=await rastrearRosto(url,c.inicio,c.fim,p=>progress(Math.round(p*0.25))); }
    catch(e){ console.warn('Segue o rosto: falhou, usando fundo desfocado.',e); rosto=null; }
  }
  const k=c.efeito==='seguir-rosto'?0.75:1, base=c.efeito==='seguir-rosto'?25:0;
  return exportarCorte(url,{inicio:c.inicio,fim:c.fim,formato:c.formato},cues,{legenda,efeito:c.efeito,gancho:c.gancho_texto,accent:legenda?.highlightColor||template.cor,template,logoImg,rosto},p=>progress(p>=100?100:Math.round(base+p*k)),pegarDub(c.id));
}

export function baixar(blob:Blob,nome:string){
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=nome; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(a.href),60000);
}

export async function zipar(arquivos:{nome:string;blob:Blob}[],extras:Record<string,string>){
  const {default:JSZip}=await import('jszip'); const z=new JSZip();
  for(const a of arquivos) z.file(a.nome,a.blob);
  for(const [n,t] of Object.entries(extras)) z.file(n,t);
  return z.generateAsync({type:'blob',compression:'STORE'});
}

const srtTime=(s:number)=>{ const ms=Math.round(s*1000); return `${String(Math.floor(ms/3600000)).padStart(2,'0')}:${String(Math.floor(ms/60000)%60).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')},${String(ms%1000).padStart(3,'0')}`; };
export function srtDoCorte(c:Clip,cuesProj:Cue[]){
  return cuesDe(c,cuesProj).filter(q=>q.end>c.inicio&&q.start<c.fim).map((q,i)=>`${i+1}\n${srtTime(Math.max(0,q.start-c.inicio))} --> ${srtTime(Math.min(c.fim,q.end)-c.inicio)}\n${q.text}\n`).join('\n');
}
