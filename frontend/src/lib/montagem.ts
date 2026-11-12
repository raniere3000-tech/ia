// "Montagem manual": a pessoa manda as imagens/vídeos dos quadros, a narração, a trilha e os efeitos,
// cola o roteiro de quadros e o site encaixa tudo no tempo certo (nome dos arquivos, ordem,
// transcrição da narração, batida da música) e grava o vídeo no navegador.
import fixWebmDuration from 'fix-webm-duration';
import { formatoSuportado } from './render';
import { FONT_STACK, type Cue } from './captions';
import { gerarSom } from './sons';
import { chamar, GEMINI_MODEL } from './gemini';

export const SR = 44100;
export type Anim = 'zoom-in'|'zoom-out'|'pan-esq'|'pan-dir'|'tremer'|'parado';
export const ANIMS:[Anim,string][] = [['zoom-in','Aproximar'],['zoom-out','Afastar'],['pan-esq','Deslizar para a esquerda'],['pan-dir','Deslizar para a direita'],['tremer','Tremor'],['parado','Parado']];
export type Formato = '9:16'|'16:9'|'1:1';
export const TAMANHO:Record<Formato,[number,number]> = {'9:16':[1080,1920],'16:9':[1920,1080],'1:1':[1080,1080]};

export type TipoArq = 'quadro'|'narracao'|'trilha'|'efeito';
export type Arquivo = {id:string;nome:string;tipo:TipoArq;blob:Blob;midia?:'imagem'|'video';duracao:number;criado:number};
export type QuadroRot = {n:number;titulo:string;visual:string;falas:{nome:string;texto:string}[];sons:{desc:string;pos:number;offset?:number}[];trilha?:string;anim?:Anim;ini?:number;fim?:number;dur?:number;linhas:number};
export type SomSinc = {desc:string;arquivo:string;em:number;vol:number};
export type QuadroSinc = {n:number;titulo:string;visual:string;midia:string;ini:number;dur:number;anim:Anim;sons:SomSinc[];legenda:{ini:number;fim:number;texto:string}[];narracao?:string};
export type Sinc = {quadros:QuadroSinc[];trilhas:{arquivo:string;ini:number;fim:number}[];narracao:'unica'|'separada'|'nenhuma';total:number;notas:string[]};
export type Opcoes = {durPadrao:number;naBatida:boolean;legendas:boolean;volTrilha:number;volEfeitos:number;transicao:'corte'|'fade';formato:Formato};
export const OPCOES_PADRAO:Opcoes = {durPadrao:3,naBatida:true,legendas:true,volTrilha:30,volEfeitos:80,transicao:'fade',formato:'9:16'};

const uid = ()=>Math.random().toString(36).slice(2,9);
const semAcento = (s:string)=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
const PARADAS = new Set(['som','sfx','efeito','de','da','do','das','dos','um','uma','the','com','para','pra','que','mp3','wav','ogg','m4a','aac','flac','webm','final','audio']);
export const palavras = (s:string)=>semAcento(s).replace(/\.[a-z0-9]{2,4}$/,'').replace(/[^a-z0-9]+/g,' ').split(' ').filter(w=>w.length>=3&&!PARADAS.has(w)&&!/^\d+$/.test(w));
/** Quanto um nome de arquivo combina com uma descrição (0 a 1). */
export function parecido(desc:string,nome:string){
  const a=palavras(desc), b=palavras(nome); if(!a.length||!b.length) return 0;
  let n=0; for(const w of a) if(b.some(x=>x===w||(w.length>=4&&x.length>=4&&(x.startsWith(w.slice(0,4))||w.startsWith(x.slice(0,4)))))) n++;
  return n/a.length;
}

// ---------------------------------------------------------------- roteiro de quadros

function lerHora(t:string){ t=t.trim().replace(',','.').replace(/s(eg)?$/i,''); const m=t.match(/^(\d+):(\d{1,2}(?:\.\d+)?)$/); if(m) return +m[1]*60+ +m[2]; const n=parseFloat(t); return Number.isFinite(n)?n:NaN; }
const RX_INTERVALO = /(\d+:\d{2}(?:[.,]\d+)?|\d+(?:[.,]\d+)?)\s*s?\s*(?:-|–|—|a|até)\s*(\d+:\d{2}(?:[.,]\d+)?|\d+(?:[.,]\d+)?)\s*s?\b/i;
const RX_DUR = /(\d+(?:[.,]\d+)?)\s*(?:s|seg|segundos?)\b/i;
function tempoDe(txt:string):{ini?:number;fim?:number;dur?:number}{
  const m=txt.match(RX_INTERVALO); if(m&&(/:/.test(m[1])||/:/.test(m[2])||/s\b/i.test(txt))){ const a=lerHora(m[1]), b=lerHora(m[2]); if(Number.isFinite(a)&&Number.isFinite(b)&&b>a) return {ini:a,fim:b}; }
  const d=txt.match(RX_DUR); if(d){ const v=lerHora(d[1]); if(v>0) return {dur:v}; }
  return {};
}
export function animDe(t:string):Anim|undefined{
  const d=semAcento(t);
  if(/aproxim|zoom.?in|chega perto|close/.test(d)) return 'zoom-in';
  if(/afast|zoom.?out|abre/.test(d)) return 'zoom-out';
  if(/esquerda/.test(d)) return 'pan-esq';
  if(/direita|pan/.test(d)) return 'pan-dir';
  if(/trem|chacoalh|impacto|sacud/.test(d)) return 'tremer';
  if(/parad|fix|estatic/.test(d)) return 'parado';
  return undefined;
}
const RX_CAB = /^\s*(?:#+\s*)?(?:\*\*)?\s*(quadro|cena|frame|plano|take|cena)\s*(?:n[ºo°.]?\s*)?(\d+)\s*(?:\*\*)?\s*(.*)$/i;
const RX_MARCA = /^\s*[[(]\s*([^\]:)]+?)\s*:\s*(.+?)\s*[\])]\s*$/;
const RX_ROTULO = /^\s*(?:[-•*]\s*)?(?:\*\*)?([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9 ]{0,28}?)(?:\s*\(([^)]*)\))?(?:\*\*)?\s*:\s*(?:\*\*)?\s*(.+)$/;

/** Lê o roteiro de quadros. Aceita "QUADRO 1 (0:00–0:04)", falas "NOME: texto", [SOM: ...], [TRILHA: ...], [MOVIMENTO: ...], "Duração: 4 s". */
export function lerQuadros(texto:string):QuadroRot[]{
  const linhas=texto.replace(/\r/g,'').split('\n');
  const temCab=linhas.some(l=>RX_CAB.test(l));
  const out:QuadroRot[]=[]; let q:QuadroRot|null=null;
  const novo=(n:number,titulo:string)=>{ q={n,titulo,visual:'',falas:[],sons:[],linhas:0}; out.push(q); return q; };
  const add=(l:string)=>{
    if(!q) return;
    const s=l.trim().replace(/^[-•*]\s+/,''); if(!s) return;
    q.linhas++; const pos=q.falas.length;
    let chave='', valor='';
    const mk=s.match(RX_MARCA); if(mk){ chave=mk[1]; valor=mk[2]; }
    else{ const r=s.match(RX_ROTULO); if(r){ chave=r[1]; valor=r[3]; } }
    const k=semAcento(chave.trim());
    if(k&&/^(som|sons|sfx|efeito|efeitos|efeito sonoro|efeitos sonoros|fx|audio)$/.test(k)){
      for(const parte of valor.split(/\s*[;|]\s*|\s+\+\s+/)){ const off=parte.match(/@\s*(\d+(?:[.,]\d+)?)\s*s?/); const desc=parte.replace(/@\s*\d+(?:[.,]\d+)?\s*s?/,'').trim(); if(desc) q.sons.push({desc,pos,...(off?{offset:+off[1].replace(',','.')}:{})}); }
      return;
    }
    if(k&&/^(trilha|trilha sonora|musica|música|bgm|fundo musical)$/.test(k)){ q.trilha=valor.trim(); return; }
    if(k&&/^(movimento|camera|câmera|anim|animacao|animação|efeito visual|transicao)$/.test(k)){ q.anim=animDe(valor)||q.anim; return; }
    if(k&&/^(tempo|duracao|duração|tempo de tela|timing)$/.test(k)){ Object.assign(q,tempoDe(valor)); return; }
    if(k&&/^(visual|imagem|descricao|descrição|tela|cenario|cenário|cena|acao|ação|frame|quadro|texto na tela|obs|observacao)$/.test(k)){ q.visual+=(q.visual?' ':'')+valor.trim(); return; }
    const narra=/^(narracao|narração|narrador|locucao|locução|voz|off|vo|fala|voz off)$/.test(k);
    if(k&&(narra||chave.trim()===chave.trim().toUpperCase())&&chave.trim().length<=28){
      const nome=chave.trim().toUpperCase();
      const fala=valor.trim().replace(/^["“”']|["“”']$/g,'');
      if(fala) q.falas.push({nome:narra?'NARRADOR':nome,texto:fala}); return;
    }
    const aspas=s.match(/^["“](.+)["”]$/); if(aspas){ q.falas.push({nome:'NARRADOR',texto:aspas[1]}); return; }
    q.visual+=(q.visual?' ':'')+s.replace(/\*\*/g,'');
  };
  if(temCab){
    for(const l of linhas){
      const c=l.match(RX_CAB);
      if(c){ const resto=c[3].replace(/^[\s:\-–—.)]+/,'').replace(/\*\*/g,''); const qq=novo(+c[2],resto); Object.assign(qq,tempoDe(resto));
        const an=animDe(resto); if(an&&/movimento|camera|câmera|zoom/i.test(resto)) qq.anim=an;
        qq.titulo=resto.replace(RX_INTERVALO,'').replace(RX_DUR,'').replace(/[()[\]]/g,'').replace(/^[\s:\-–—.]+|[\s:\-–—.]+$/g,'').trim(); continue; }
      add(l);
    }
  } else {
    let bloco:string[]=[]; let n=0;
    const fecha=()=>{ if(bloco.some(x=>x.trim())){ novo(++n,''); bloco.forEach(add); } bloco=[]; };
    for(const l of linhas){ if(!l.trim()) fecha(); else bloco.push(l); }
    fecha();
  }
  // Números repetidos ou fora de ordem: renumera na ordem em que aparecem.
  const vistos=new Set<number>(); if(out.some(x=>vistos.has(x.n)||!vistos.add(x.n))) out.forEach((x,i)=>{ x.n=i+1; });
  return out;
}

export const MODELO_ROTEIRO = `QUADRO 1 (0:00–0:04)
VISUAL: Taverna escura, chuva na janela.
[TRILHA: tensa]
[SOM: chuva]
NARRADOR: Era uma noite tranquila na taverna.

QUADRO 2
VISUAL: A porta se abre com força. Thorgar entra.
MOVIMENTO: tremor
[SOM: porta batendo, forte]
THORGAR: Desde que cheguei, ninguém me serviu!

QUADRO 3 (4 s)
VISUAL: Close na garçonete assustada.
MOVIMENTO: aproximar
[SOM: vidro quebrando @1.5]
GARÇONETE: Mil perdões, senhor!`;

// ---------------------------------------------------------------- arquivos (guardados no navegador)

let dbp:Promise<IDBDatabase>|null=null;
function db(){ if(!dbp) dbp=new Promise((res,rej)=>{ const r=indexedDB.open('montagem_manual',1); r.onupgradeneeded=()=>{ r.result.createObjectStore('arquivos',{keyPath:'id'}); }; r.onsuccess=()=>res(r.result); r.onerror=()=>rej(new Error('O navegador não deixou guardar os arquivos (modo anônimo?).')); }); return dbp; }
async function loja<T>(modo:IDBTransactionMode,f:(s:IDBObjectStore)=>IDBRequest|void):Promise<T>{ const d=await db(); return new Promise((res,rej)=>{ const t=d.transaction('arquivos',modo); const q=f(t.objectStore('arquivos')); t.oncomplete=()=>res((q as IDBRequest)?.result); t.onerror=()=>rej(t.error); }); }
export const listarArquivos = ()=>loja<Arquivo[]>('readonly',s=>s.getAll()).then(l=>(l||[]).sort((a,b)=>a.criado-b.criado));
export const apagarArquivo = (id:string)=>loja<void>('readwrite',s=>{ s.delete(id); }).then(()=>{ const m=midias.get(id); if(m) URL.revokeObjectURL(m.el.src); midias.delete(id); buffers.delete(id); });

/** Imagens/vídeos abertos, prontos para desenhar. */
export const midias=new Map<string,{tipo:'imagem'|'video';el:HTMLImageElement|HTMLVideoElement;duracao:number}>();
const buffers=new Map<string,AudioBuffer>();
function abrirMidia(a:Arquivo){
  return new Promise<{tipo:'imagem'|'video';el:HTMLImageElement|HTMLVideoElement;duracao:number}>((res,rej)=>{
    const url=URL.createObjectURL(a.blob);
    if(a.midia==='imagem'){ const i=new Image(); i.onload=()=>res({tipo:'imagem',el:i,duracao:0}); i.onerror=()=>rej(new Error('Não consegui abrir a imagem '+a.nome)); i.src=url; return; }
    const v=document.createElement('video'); v.muted=true; v.playsInline=true; v.loop=true; v.preload='auto'; v.src=url;
    v.onloadeddata=()=>res({tipo:'video',el:v,duracao:v.duration||0}); v.onerror=()=>rej(new Error('Não consegui abrir o vídeo '+a.nome));
  });
}
export async function prepararMidia(a:Arquivo){ if(!midias.has(a.id)) midias.set(a.id,await abrirMidia(a)); return midias.get(a.id)!; }

let ctxDecod:OfflineAudioContext|null=null;
/** Decodifica um áudio para 44,1 kHz estéreo. */
export async function audioDe(a:{id:string;blob:Blob;nome:string}):Promise<AudioBuffer>{
  const c=buffers.get(a.id); if(c) return c;
  ctxDecod ||= new OfflineAudioContext(2,1,SR);
  let b:AudioBuffer;
  try{ b=await ctxDecod.decodeAudioData(await a.blob.arrayBuffer()); }
  catch{ throw new Error(`Não consegui ler o áudio "${a.nome}". Use MP3, WAV, OGG ou M4A.`); }
  buffers.set(a.id,b); return b;
}

/** Recebe um arquivo enviado e guarda no navegador. */
export async function guardarArquivo(f:File,tipo:TipoArq):Promise<Arquivo>{
  const ehImg=f.type.startsWith('image/')||/\.(png|jpe?g|webp|gif|bmp|avif)$/i.test(f.name);
  const ehVid=f.type.startsWith('video/')||/\.(mp4|mov|webm|m4v|mkv)$/i.test(f.name);
  const ehAud=f.type.startsWith('audio/')||/\.(mp3|wav|ogg|m4a|aac|flac|opus|weba)$/i.test(f.name);
  if(tipo==='quadro'&&!ehImg&&!ehVid) throw new Error(`"${f.name}" não é imagem nem vídeo.`);
  if(tipo!=='quadro'&&!ehAud&&!ehVid) throw new Error(`"${f.name}" não é um arquivo de áudio.`);
  const a:Arquivo={id:uid(),nome:f.name,tipo,blob:new Blob([await f.arrayBuffer()],{type:f.type||''}),duracao:0,criado:Date.now()+Math.random()};
  if(tipo==='quadro'){ a.midia=ehImg?'imagem':'video'; const m=await prepararMidia(a); a.duracao=m.duracao; }
  else a.duracao=(await audioDe(a)).duration;
  await loja('readwrite',s=>{ s.put(a); });
  return a;
}

// ---------------------------------------------------------------- análise

/** Número do quadro no nome do arquivo: "quadro-03.png", "frame_3.jpg", "03 porta.png", "3.jpg". */
export function numeroDoNome(nome:string){
  const b=semAcento(nome).replace(/\.[a-z0-9]{2,4}$/,'');
  const m=b.match(/(?:quadro|frame|cena|plano|take|shot|q|f)[\s_\-.]*0*(\d{1,3})(?!\d)/); if(m) return +m[1];
  const i=b.match(/^0*(\d{1,3})(?!\d)/); if(i) return +i[1];
  const f=b.match(/[\s_\-.]0*(\d{1,3})$/); if(f) return +f[1];
  return 0;
}
const ordemNatural=(a:string,b:string)=>a.localeCompare(b,'pt-BR',{numeric:true,sensitivity:'base'});

/** Áudio mono 16 kHz para transcrever. */
export async function mono16k(b:AudioBuffer){
  const c=new OfflineAudioContext(1,Math.ceil(b.duration*16000),16000); const s=c.createBufferSource(); s.buffer=b; s.connect(c.destination); s.start();
  return (await c.startRendering()).getChannelData(0);
}

/** Batidas da música (picos de energia), em segundos. */
export function batidas(b:AudioBuffer){
  const d=b.getChannelData(0), h=1024, n=Math.floor(d.length/h); const e=new Float32Array(n);
  for(let i=0;i<n;i++){ let s=0; for(let k=0;k<h;k++){ const v=d[i*h+k]; s+=v*v; } e[i]=Math.sqrt(s/h); }
  const fl=new Float32Array(n); for(let i=1;i<n;i++) fl[i]=Math.max(0,e[i]-e[i-1]);
  const out:number[]=[]; const jan=43, dist=Math.round(0.25*SR/h); let ult=-dist;
  for(let i=1;i<n-1;i++){
    let m=0,q=0,c=0; for(let k=Math.max(0,i-jan);k<Math.min(n,i+jan);k++){ m+=fl[k]; q+=fl[k]*fl[k]; c++; } m/=c; const dp=Math.sqrt(Math.max(0,q/c-m*m));
    if(fl[i]>m+1.4*dp&&fl[i]>=fl[i-1]&&fl[i]>=fl[i+1]&&fl[i]>0.004&&i-ult>=dist){ out.push(i*h/SR); ult=i; }
  }
  return out;
}

/** Acha onde cada quadro começa na fala transcrita. */
function ancorasDasFalas(qs:QuadroRot[],cues:Cue[]){
  const ws:{w:string;t:number}[]=[];
  for(const c of cues){ const p=palavrasFala(c.text); p.forEach((w,i)=>ws.push({w,t:c.start+(c.end-c.start)*i/Math.max(1,p.length)})); }
  const res=new Map<number,number>(); let ptr=0;
  for(let qi=0;qi<qs.length;qi++){
    const alvo=palavrasFala(qs[qi].falas.map(f=>f.texto).join(' ')).slice(0,8); if(!alvo.length) continue;
    const precisa=alvo.length<=2?1:Math.max(2,Math.ceil(alvo.length*0.4));
    let best=-1,bi=-1;
    for(let i=ptr;i<Math.min(ws.length,ptr+4000);i++){
      let sc=0; for(let j=0;j<alvo.length&&i+j<ws.length;j++){ const a=alvo[j], b=ws[i+j].w; if(a===b||(a.length>=4&&b.length>=4&&a.slice(0,4)===b.slice(0,4))) sc++; }
      if(sc>best){ best=sc; bi=i; } if(sc===alvo.length) break;
    }
    if(bi>=0&&best>=precisa){ res.set(qi,Math.max(0,ws[bi].t-0.15)); ptr=bi+1; }
  }
  return res;
}
const palavrasFala=(s:string)=>semAcento(s).replace(/[^a-z0-9]+/g,' ').split(' ').filter(w=>w.length>=2);

export type Entrada = {quadros:QuadroRot[];arquivos:Arquivo[];cues:Cue[]|null;batidas:number[]|null;opcoes:Opcoes;imagensIA?:Map<number,string>};

/** Junta tudo: qual imagem vai em cada quadro, quando cada quadro começa, onde entra cada som e cada trilha. */
export function sincronizar(e:Entrada):Sinc{
  const {quadros:qs,arquivos,opcoes:o}=e; const notas:string[]=[];
  const imgs=arquivos.filter(a=>a.tipo==='quadro'), nars=arquivos.filter(a=>a.tipo==='narracao'), trs=arquivos.filter(a=>a.tipo==='trilha'), efs=arquivos.filter(a=>a.tipo==='efeito');
  // 1) Imagem de cada quadro: IA > número no nome > ordem.
  const midiaDe=new Map<number,string>(); const usadas=new Set<string>();
  if(e.imagensIA) for(const [qi,id] of e.imagensIA) if(qs[qi]&&imgs.some(a=>a.id===id)){ midiaDe.set(qi,id); usadas.add(id); }
  for(const a of [...imgs].sort((x,y)=>ordemNatural(x.nome,y.nome))){ if(usadas.has(a.id)) continue; const n=numeroDoNome(a.nome); const qi=qs.findIndex(q=>q.n===n); if(n&&qi>=0&&!midiaDe.has(qi)){ midiaDe.set(qi,a.id); usadas.add(a.id); } }
  const sobra=imgs.filter(a=>!usadas.has(a.id)).sort((x,y)=>ordemNatural(x.nome,y.nome));
  qs.forEach((_,qi)=>{ if(!midiaDe.has(qi)&&sobra.length){ const a=sobra.shift()!; midiaDe.set(qi,a.id); usadas.add(a.id); } });
  if(sobra.length) notas.push(`${sobra.length} imagem(ns) sobraram (mais imagens do que quadros): ${sobra.slice(0,4).map(a=>a.nome).join(', ')}.`);
  const semImg=qs.filter((_,qi)=>!midiaDe.has(qi)); if(semImg.length) notas.push(`Quadro(s) sem imagem: ${semImg.map(q=>q.n).join(', ')}.`);
  // 2) Narração separada (um arquivo por quadro com fala) ou única (um arquivo para tudo).
  const modo:Sinc['narracao']=nars.length>1?'separada':nars.length===1?'unica':'nenhuma';
  const narDe=new Map<number,string>();
  if(modo==='separada'){
    const comFala=qs.map((q,qi)=>({q,qi})).filter(x=>x.q.falas.length);
    const alvo=comFala.length?comFala:qs.map((q,qi)=>({q,qi}));
    const livres=[...nars].sort((x,y)=>ordemNatural(x.nome,y.nome)); const usados=new Set<string>();
    for(const a of livres){ const n=numeroDoNome(a.nome); const x=n?alvo.find(y=>y.q.n===n&&!narDe.has(y.qi)):undefined; if(x){ narDe.set(x.qi,a.id); usados.add(a.id); } }
    for(const x of alvo){ if(narDe.has(x.qi)) continue; const a=livres.find(y=>!usados.has(y.id)); if(a){ narDe.set(x.qi,a.id); usados.add(a.id); } }
    if(livres.some(a=>!usados.has(a.id))) notas.push('Sobrou arquivo de narração sem quadro com fala.');
  }
  // 3) Tempo de cada quadro.
  const durPropria=(qi:number)=>{ const q=qs[qi]; if(q.dur) return q.dur; if(q.ini!=null&&q.fim!=null) return q.fim-q.ini;
    const n=narDe.get(qi); if(n){ const a=nars.find(x=>x.id===n); if(a) return a.duracao+0.35; }
    const m=midiaDe.get(qi); const ar=m?imgs.find(x=>x.id===m):undefined; if(ar?.midia==='video'&&ar.duracao>0) return Math.min(ar.duracao,30);
    return Math.max(0.5,o.durPadrao); };
  const inicio:(number|undefined)[]=qs.map(q=>q.ini);
  if(modo==='unica'&&e.cues?.length){ const anc=ancorasDasFalas(qs,e.cues); anc.forEach((t,qi)=>{ if(inicio[qi]==null) inicio[qi]=t; });
    const falando=qs.filter(q=>q.falas.length).length; if(anc.size<falando) notas.push(`Achei na narração o começo de ${anc.size} de ${falando} quadros com fala; os outros ficaram no meio do caminho. Confira e ajuste se precisar.`); }
  if(inicio[0]==null) inicio[0]=0;
  if(modo==='unica'&&!e.cues?.length&&nars.length) notas.push('A narração não foi transcrita, então os quadros usam a duração do roteiro (ou a padrão).');
  const ini:number[]=[]; const dur:number[]=[];
  for(let i=0;i<qs.length;i++){
    if(inicio[i]!=null){ ini[i]=Math.max(i?ini[i-1]+0.3:0,inicio[i]!); continue; }
    let j=i; while(j<qs.length&&inicio[j]==null) j++;
    const ant=ini[i-1]+durPropria(i-1);
    if(j<qs.length&&inicio[j]!=null&&modo==='unica'){
      const a=ini[i-1], b=Math.max(inicio[j]!,a+0.3*(j-i+1)), passo=(b-a)/(j-i+1);
      for(let k=i;k<j;k++) ini[k]=a+passo*(k-i+1);
      i=j-1; continue;
    }
    ini[i]=i?Math.max(ant,ini[i-1]+0.3):0;
  }
  for(let i=0;i<qs.length;i++) dur[i]=i<qs.length-1?ini[i+1]-ini[i]:durPropria(i);
  // Último quadro: vai até o fim da narração única.
  if(modo==='unica'&&qs.length){ const n=nars[0]; const fimN=(e.cues?.length?Math.max(n.duracao,...e.cues.map(c=>c.end)):n.duracao)+0.5; const ul=qs.length-1; if(qs[ul].fim==null&&!qs[ul].dur) dur[ul]=Math.max(dur[ul],fimN-ini[ul],1); }
  // Cortes na batida da música (só quando a fala não manda no tempo).
  if(o.naBatida&&e.batidas?.length&&modo==='nenhuma'){
    let mov=0; for(let i=1;i<qs.length;i++){ if(qs[i].ini!=null) continue; const t=ini[i]; let best=t,bd=0.4; for(const b of e.batidas){ const d=Math.abs(b-t); if(d<bd&&b>ini[i-1]+0.4){ bd=d; best=b; } } if(best!==t){ ini[i]=best; mov++; } }
    for(let i=0;i<qs.length;i++) dur[i]=i<qs.length-1?Math.max(0.4,ini[i+1]-ini[i]):dur[i];
    if(mov) notas.push(`${mov} corte(s) encaixados na batida da música.`);
  }
  // 4) Efeitos: arquivo de nome parecido; se não tiver, o site cria.
  const efUsado=new Set<string>(); const pendentes:SomSinc[]=[];
  const quadros:QuadroSinc[]=qs.map((q,i)=>{
    const sons=q.sons.map(s=>{
      let best='',bs=0; for(const a of efs){ const sc=parecido(s.desc,a.nome); if(sc>bs){ bs=sc; best=a.id; } }
      const arq=bs>=0.34?best:''; if(arq) efUsado.add(arq);
      const frac=q.falas.length?Math.min(0.9,s.pos/q.falas.length):0;
      const som:SomSinc={desc:s.desc,arquivo:arq,em:+(s.offset!=null?Math.min(s.offset,dur[i]):frac*dur[i]).toFixed(2),vol:o.volEfeitos};
      if(!arq) pendentes.push(som); return som;
    });
    // Legenda: trechos transcritos dentro do quadro, ou o texto das falas dividido no tempo.
    let legenda:QuadroSinc['legenda']=[];
    if(modo==='unica'&&e.cues?.length) legenda=e.cues.filter(c=>c.start>=ini[i]-0.2&&c.start<ini[i]+dur[i]-0.1).map(c=>({ini:Math.max(0,c.start-ini[i]),fim:Math.min(dur[i],c.end-ini[i]),texto:c.text.trim()}));
    else if(q.falas.length){ const tot=q.falas.reduce((a,f)=>a+f.texto.length,0)||1; let t=0; legenda=q.falas.map(f=>{ const d=dur[i]*f.texto.length/tot; const x={ini:t,fim:t+d,texto:f.texto}; t+=d; return x; }); }
    return {n:q.n,titulo:q.titulo,visual:q.visual,midia:midiaDe.get(i)||'',ini:+ini[i].toFixed(3),dur:+dur[i].toFixed(3),anim:q.anim||(['zoom-in','zoom-out','pan-dir','pan-esq'] as Anim[])[i%4],sons,legenda,narracao:narDe.get(i)};
  });
  const efLivres=efs.filter(a=>!efUsado.has(a.id)).sort((x,y)=>ordemNatural(x.nome,y.nome));
  let pelaOrdem=0; for(const s of pendentes){ const a=efLivres.shift(); if(!a) break; s.arquivo=a.id; pelaOrdem++; }
  if(pelaOrdem) notas.push(`${pelaOrdem} efeito(s) sem nome parecido foram colocados pela ordem dos arquivos. Confira na lista.`);
  const feitos=pendentes.filter(s=>!s.arquivo).length; if(feitos) notas.push(`${feitos} efeito(s) sem arquivo serão feitos pelo site: ${pendentes.filter(s=>!s.arquivo).slice(0,4).map(s=>s.desc).join(', ')}.`);
  if(efLivres.length) notas.push(`Efeito(s) enviados que não têm marcação [SOM] no roteiro: ${efLivres.map(a=>a.nome).slice(0,4).join(', ')}.`);
  // 5) Trilha: [TRILHA: ...] troca a música naquele quadro; sem marcação, toca do começo ao fim.
  const total=quadros.length?quadros[quadros.length-1].ini+quadros[quadros.length-1].dur:0;
  const trilhas:Sinc['trilhas']=[];
  const marcas=qs.map((q,i)=>({q,i})).filter(x=>x.q.trilha);
  if(trs.length){
    if(!marcas.length){ let t=0; const lista=[...trs].sort((x,y)=>ordemNatural(x.nome,y.nome)); for(const a of lista){ if(t>=total) break; trilhas.push({arquivo:a.id,ini:t,fim:lista.length===1?total:Math.min(total,t+a.duracao)}); t+=a.duracao; }
      if(t<total&&trilhas.length) trilhas[trilhas.length-1].fim=total; }
    else{ const usadas2=new Set<string>(); let ordem=0;
      marcas.forEach((m,k)=>{ const desc=m.q.trilha!; const ini2=quadros[m.i].ini, fim2=k<marcas.length-1?quadros[marcas[k+1].i].ini:total;
        if(/^(nenhuma|silencio|silêncio|para|parar|sem|fim|off)$/i.test(semAcento(desc).trim())) return;
        let best='',bs=0; for(const a of trs){ const sc=parecido(desc,a.nome); if(sc>bs){ bs=sc; best=a.id; } }
        if(bs<0.34){ const livre=[...trs].sort((x,y)=>ordemNatural(x.nome,y.nome)).filter(a=>!usadas2.has(a.id)); best=(livre[0]||trs[ordem%trs.length]).id; ordem++; }
        usadas2.add(best); trilhas.push({arquivo:best,ini:ini2,fim:fim2}); });
      if(quadros[marcas[0].i].ini>0.5) notas.push('A trilha só começa no quadro com a primeira marcação [TRILHA].');
    }
  } else if(marcas.length) notas.push('O roteiro pede trilha, mas nenhum arquivo de trilha foi enviado.');
  return {quadros,trilhas,narracao:modo,total:+total.toFixed(3),notas};
}

/** Recalcula os inícios depois que a pessoa mudou a duração de algum quadro (o resto anda junto). */
export function reencadear(s:Sinc):Sinc{
  let t=0; const qs=s.quadros.map(q=>{ const x={...q,ini:+t.toFixed(3)}; t+=q.dur; return x; });
  const desloc=(tt:number)=>{ for(let i=s.quadros.length-1;i>=0;i--) if(tt>=s.quadros[i].ini) return qs[i].ini+(tt-s.quadros[i].ini); return tt; };
  const total=t;
  return {...s,quadros:qs,total:+total.toFixed(3),trilhas:s.trilhas.map((x,i,arr)=>({...x,ini:desloc(x.ini),fim:i===arr.length-1?total:desloc(x.fim)}))};
}

/** A IA (Gemini) olha as imagens e diz qual combina com cada quadro. */
export async function conferirImagensIA(key:string,qs:QuadroRot[],imgs:Arquivo[]):Promise<Map<number,string>>{
  const lista=imgs.filter(a=>a.midia==='imagem').slice(0,40); if(!lista.length) return new Map();
  const partes:unknown[]=[{text:`Você monta vídeos. Abaixo está o roteiro de quadros e depois ${lista.length} imagens numeradas a partir de 0, na ordem.\nDiga qual imagem combina com cada quadro, pelo que aparece nela. Cada imagem só pode ir em um quadro. Se nenhuma combinar, não inclua o quadro.\n\nQUADROS:\n${qs.map((q,i)=>`${i}: ${[q.titulo,q.visual,q.falas.map(f=>f.nome+': '+f.texto).join(' / ')].filter(Boolean).join(' — ').slice(0,300)}`).join('\n')}`}];
  for(let i=0;i<lista.length;i++){ partes.push({text:`Imagem ${i} (arquivo ${lista[i].nome}):`}); partes.push({inlineData:{mimeType:'image/jpeg',data:await miniatura(lista[i].blob)}}); }
  const r=await chamar(key,GEMINI_MODEL+':generateContent',{contents:[{role:'user',parts:partes}],generationConfig:{responseMimeType:'application/json',temperature:0.1,responseSchema:{type:'OBJECT',properties:{pares:{type:'ARRAY',items:{type:'OBJECT',properties:{quadro:{type:'INTEGER'},imagem:{type:'INTEGER'}},required:['quadro','imagem']}}},required:['pares']}}});
  const txt=r?.candidates?.[0]?.content?.parts?.map((p:{text?:string})=>p.text||'').join('')||'{}';
  let j:{pares?:{quadro:number;imagem:number}[]}={}; try{ j=JSON.parse(txt); }catch{ throw new Error('A IA respondeu num formato que não entendi. Tente de novo.'); }
  const m=new Map<number,string>(); const usadas=new Set<number>();
  for(const p of j.pares||[]) if(qs[p.quadro]&&lista[p.imagem]&&!usadas.has(p.imagem)&&!m.has(p.quadro)){ m.set(p.quadro,lista[p.imagem].id); usadas.add(p.imagem); }
  return m;
}
async function miniatura(b:Blob){
  const bmp=await createImageBitmap(b); const k=320/Math.max(bmp.width,bmp.height); const c=document.createElement('canvas'); c.width=Math.round(bmp.width*k); c.height=Math.round(bmp.height*k);
  c.getContext('2d')!.drawImage(bmp,0,0,c.width,c.height); bmp.close?.();
  return c.toDataURL('image/jpeg',0.6).split(',')[1];
}

// ---------------------------------------------------------------- áudio final

/** Mistura narração, efeitos e trilha (com a trilha baixando quando alguém fala). */
export async function mixar(s:Sinc,arquivos:Arquivo[],o:Opcoes,onStatus:(t:string)=>void):Promise<AudioBuffer|null>{
  const total=Math.max(0.5,s.total); const c=new OfflineAudioContext(2,Math.ceil(total*SR),SR);
  const comp=c.createDynamicsCompressor(); comp.threshold.value=-6; comp.ratio.value=8; comp.attack.value=0.003; comp.release.value=0.2; comp.connect(c.destination);
  const por=(id:string)=>arquivos.find(a=>a.id===id);
  let algo=false;
  // Narração
  const voz:{b:AudioBuffer;em:number}[]=[];
  if(s.narracao==='unica'){ const a=arquivos.find(x=>x.tipo==='narracao'); if(a) voz.push({b:await audioDe(a),em:0}); }
  else if(s.narracao==='separada') for(const q of s.quadros){ const a=q.narracao?por(q.narracao):undefined; if(a) voz.push({b:await audioDe(a),em:q.ini+0.1}); }
  for(const v of voz){ const n=c.createBufferSource(); n.buffer=v.b; n.connect(comp); n.start(v.em); algo=true; }
  // Efeitos
  const feitos=new Map<string,AudioBuffer>();
  for(const q of s.quadros) for(const sm of q.sons){
    let b:AudioBuffer|undefined;
    if(sm.arquivo){ const a=por(sm.arquivo); if(a) b=await audioDe(a); }
    else{ onStatus('Criando o som: '+sm.desc); b=feitos.get(sm.desc); if(!b){ const g=await gerarSom(sm.desc,'site'); b=await audioDe({id:'site:'+sm.desc,blob:g.wav,nome:sm.desc}); feitos.set(sm.desc,b); } }
    if(!b) continue;
    const n=c.createBufferSource(); n.buffer=b; const g=c.createGain(); g.gain.value=Math.max(0,sm.vol)/100; n.connect(g).connect(comp); n.start(Math.max(0,q.ini+sm.em)); algo=true;
  }
  // Trilha, com "ducking": abaixa quando tem voz.
  if(s.trilhas.length){
    const passo=0.05, nP=Math.ceil(total/passo); const fala=new Uint8Array(nP);
    for(const v of voz){ const d=v.b.getChannelData(0); const h=Math.round(passo*v.b.sampleRate); for(let i=0;i*h<d.length;i++){ let m=0; for(let k=i*h;k<Math.min(d.length,(i+1)*h);k+=8) m=Math.max(m,Math.abs(d[k])); if(m>0.04){ const p=Math.floor((v.em+i*passo)/passo); for(let x=p-3;x<=p+4;x++) if(x>=0&&x<nP) fala[x]=1; } } }
    const base=Math.max(0,o.volTrilha)/100, baixo=base*0.35;
    for(const tr of s.trilhas){
      const a=por(tr.arquivo); if(!a) continue; const b=await audioDe(a);
      const n=c.createBufferSource(); n.buffer=b; n.loop=true; const g=c.createGain(); n.connect(g).connect(comp);
      const ini=tr.ini, fim=Math.min(total,tr.fim); if(fim-ini<0.2) continue;
      g.gain.setValueAtTime(0,ini); g.gain.linearRampToValueAtTime(fala[Math.floor(ini/passo)]?baixo:base,ini+Math.min(0.8,(fim-ini)/3));
      let ult=-1; for(let p=Math.ceil((ini+0.9)/passo);p<Math.floor((fim-1.2)/passo);p++){ const st=fala[p]; if(st!==ult){ const t=p*passo; g.gain.setTargetAtTime(st?baixo:base,t,st?0.06:0.25); ult=st; } }
      g.gain.setTargetAtTime(0,Math.max(ini,fim-1.2),0.3);
      n.start(ini); n.stop(fim); algo=true;
    }
  }
  if(!algo) return null;
  onStatus('Misturando o áudio');
  return c.startRendering();
}

// ---------------------------------------------------------------- desenhar, tocar e gravar

function cobrir(ctx:CanvasRenderingContext2D,el:HTMLImageElement|HTMLVideoElement,W:number,H:number,anim:Anim,p:number,alpha:number){
  const iw=(el as HTMLVideoElement).videoWidth||(el as HTMLImageElement).naturalWidth||W, ih=(el as HTMLVideoElement).videoHeight||(el as HTMLImageElement).naturalHeight||H;
  const base=Math.max(W/iw,H/ih); let s=1, dx=0, dy=0;
  if(anim==='zoom-in') s=1+0.12*p; else if(anim==='zoom-out') s=1.12-0.12*p;
  else if(anim==='pan-esq'||anim==='pan-dir'){ s=1.14; const r=(iw*base*s-W)/2; dx=(anim==='pan-esq'?1:-1)*r*(p*2-1)*0.9; }
  else if(anim==='tremer'){ s=1.06; const f=Math.max(0,1-p*3); dx=Math.sin(p*90)*W*0.012*f; dy=Math.cos(p*77)*H*0.01*f; }
  const w=iw*base*s, h=ih*base*s; ctx.globalAlpha=alpha; ctx.drawImage(el,(W-w)/2+dx,(H-h)/2+dy,w,h); ctx.globalAlpha=1;
}
function quebrar(ctx:CanvasRenderingContext2D,t:string,max:number){ const out:string[]=[]; let l=''; for(const w of t.split(/\s+/)){ const x=l?l+' '+w:w; if(ctx.measureText(x).width>max&&l){ out.push(l); l=w; } else l=x; } if(l) out.push(l); return out; }

export function desenhar(ctx:CanvasRenderingContext2D,s:Sinc,t:number,o:Opcoes){
  const W=ctx.canvas.width, H=ctx.canvas.height; ctx.fillStyle='#000'; ctx.fillRect(0,0,W,H);
  const i=s.quadros.findIndex((q,k)=>t>=q.ini&&(t<q.ini+q.dur||k===s.quadros.length-1)); if(i<0) return;
  const q=s.quadros[i]; const p=Math.min(1,Math.max(0,(t-q.ini)/Math.max(0.1,q.dur)));
  const pinta=(qq:QuadroSinc,pp:number,a:number)=>{ const m=qq.midia?midias.get(qq.midia):undefined;
    if(m) cobrir(ctx,m.el,W,H,qq.anim,pp,a);
    else{ ctx.globalAlpha=a; ctx.fillStyle='#111'; ctx.fillRect(0,0,W,H); ctx.fillStyle='#777'; ctx.font=`600 ${Math.round(W*0.04)}px ${FONT_STACK}`; ctx.textAlign='center';
      quebrar(ctx,`Quadro ${qq.n} sem imagem${qq.visual?': '+qq.visual:''}`,W*0.8).slice(0,6).forEach((l,k)=>ctx.fillText(l,W/2,H*0.42+k*W*0.055)); ctx.globalAlpha=1; } };
  const tr=0.4;
  if(o.transicao==='fade'&&i>0&&t-q.ini<tr){ pinta(s.quadros[i-1],1,1); pinta(q,p,(t-q.ini)/tr); } else pinta(q,p,1);
  if(o.legendas){ const lg=q.legenda.find(x=>t-q.ini>=x.ini&&t-q.ini<x.fim); if(lg){
    const fs=Math.round(Math.min(W,H)*0.052); ctx.font=`800 ${fs}px ${FONT_STACK}`; ctx.textAlign='center'; ctx.lineJoin='round';
    const ls=quebrar(ctx,lg.texto,W*0.84).slice(-3); const y0=H*(H>W?0.78:0.84)-(ls.length-1)*fs*1.2;
    ls.forEach((l,k)=>{ ctx.lineWidth=fs*0.16; ctx.strokeStyle='rgba(0,0,0,.9)'; ctx.strokeText(l,W/2,y0+k*fs*1.2); ctx.fillStyle='#fff'; ctx.fillText(l,W/2,y0+k*fs*1.2); }); } }
}
/** Vídeos dos quadros: toca o do quadro atual (e o anterior durante a transição), pausa os outros. */
export function sincronizarVideos(s:Sinc,t:number,tocando:boolean){
  s.quadros.forEach((q,i)=>{ const m=q.midia?midias.get(q.midia):undefined; if(!m||m.tipo!=='video') return; const v=m.el as HTMLVideoElement;
    const ativo=t>=q.ini-0.05&&(t<q.ini+q.dur+0.45||i===s.quadros.length-1); if(!ativo){ if(!v.paused) v.pause(); return; }
    const alvo=m.duracao>0?Math.max(0,t-q.ini)%m.duracao:0;
    if(tocando){ if(Math.abs(v.currentTime-alvo)>0.35) v.currentTime=alvo; if(v.paused) v.play().catch(()=>{}); } else { if(!v.paused) v.pause(); if(Math.abs(v.currentTime-alvo)>0.05) v.currentTime=alvo; } });
}

export type Sessao = {parar:()=>void;fim:Promise<void>};
export function tocar(canvas:HTMLCanvasElement,s:Sinc,audio:AudioBuffer|null,o:Opcoes,cb:{onTempo?:(t:number)=>void;gravar?:(r:{blob:Blob;ext:string})=>void;inicio?:number}={}):Sessao{
  const ctx=canvas.getContext('2d')!; const total=s.total; const ac=new AudioContext(); const t00=cb.gravar?0:Math.min(cb.inicio||0,Math.max(0,total-0.2));
  let parado=false, raf=0, fonte:AudioBufferSourceNode|null=null, rec:MediaRecorder|null=null; const chunks:Blob[]=[]; let mime='';
  let resolver:()=>void=()=>{}; const fim=new Promise<void>(r=>{ resolver=r; });
  const destino=cb.gravar?ac.createMediaStreamDestination():null;
  if(audio){ fonte=ac.createBufferSource(); fonte.buffer=audio; fonte.connect(destino||ac.destination); }
  if(cb.gravar){
    mime=formatoSuportado()||''; if(!mime){ ac.close(); throw new Error('Este navegador não grava vídeo. Use Chrome, Edge ou Safari atualizados.'); }
    const st=canvas.captureStream(30); if(audio) destino!.stream.getAudioTracks().forEach(tk=>st.addTrack(tk));
    rec=new MediaRecorder(st,{mimeType:mime,videoBitsPerSecond:8_000_000,audioBitsPerSecond:192_000}); rec.ondataavailable=e=>{ if(e.data.size) chunks.push(e.data); };
  }
  let ok=false, t0=0;
  const encerrar=async()=>{ if(parado) return; parado=true; cancelAnimationFrame(raf); clearInterval(reserva); try{ fonte?.stop(); }catch{ /* já parou */ }
    sincronizarVideos(s,-1,false);
    if(rec&&rec.state!=='inactive'){ await new Promise<void>(r=>{ rec!.onstop=()=>r(); rec!.stop(); }); rec.stream.getTracks().forEach(tk=>tk.stop());
      const type=mime.split(';')[0]; let blob=new Blob(chunks,{type}); if(type==='video/webm'){ try{ blob=await fixWebmDuration(blob,total*1000,{logger:false}); }catch{ /* mantém */ } }
      if(ok) cb.gravar?.({blob,ext:type==='video/mp4'?'mp4':'webm'}); }
    ac.close().catch(()=>{}); resolver(); };
  const passo=()=>{ if(parado) return; const t=t00+ac.currentTime-t0;
    if(t>=total){ desenhar(ctx,s,total-0.001,o); ok=true; encerrar(); return; }
    sincronizarVideos(s,Math.max(0,t),true); desenhar(ctx,s,Math.max(0,t),o); cb.onTempo?.(t); };
  const loop=()=>{ passo(); if(!parado) raf=requestAnimationFrame(loop); };
  const reserva=setInterval(()=>{ if(document.hidden) passo(); },250);
  (async()=>{ await ac.resume(); desenhar(ctx,s,t00,o); rec?.start(1000); t0=ac.currentTime+0.05; fonte?.start(t0,t00); loop(); })();
  return {parar:()=>{ encerrar(); },fim};
}
export function gravar(s:Sinc,audio:AudioBuffer|null,o:Opcoes,onTempo:(t:number)=>void){
  return new Promise<{blob:Blob;ext:string}>((res,rej)=>{ const [w,h]=TAMANHO[o.formato]; const cv=document.createElement('canvas'); cv.width=w; cv.height=h; let pronto=false;
    try{ const se=tocar(cv,s,audio,o,{onTempo,gravar:x=>{ pronto=true; res(x); }}); se.fim.then(()=>{ if(!pronto) rej(new Error('A gravação foi interrompida.')); }); }catch(e){ rej(e); } });
}
