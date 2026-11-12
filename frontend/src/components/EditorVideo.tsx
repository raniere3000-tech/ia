import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeftRight, Maximize2, Copy, Download, Film, Headphones, Loader2, Minus, Pause, Play, Plus, Redo2, Scissors, Trash2, Type, Undo2, Upload, Volume2, VolumeX } from 'lucide-react';
import { useApp, captionPresets } from '../state';
import { drawCaption, type Preset } from '../lib/captions';
import { baixar } from '../lib/exporter';
import { CATEGORIAS_SOM, gerarSom, receitaDe } from '../lib/sons';
import { ANIMS, TAMANHO, audioDe, midias, type Anim, type Arquivo, type Formato, type TipoArq } from '../lib/montagem';
import {
  CAMADAS, EFEITOS_VIDEO, FAIXAS, PPS_ONDA, acertarDuracoes, apagar, bufferDe, camadaDe, clipsDeVideo, empurrar, ganhoCamada, picosDe, desenharProj, dividir, duplicar, durMax, ehAudio, fimDe, gravarProj, mixarProj, novoId, sincronizarVideosProj, tocarProj, totalDe,
  type Camada, type Clip, type ClipA, type ClipV, type EfeitoV, type Faixa, type FaixaAudio, type Picos, type Proj, type Sessao,
} from '../lib/editor';

const fmt=(s:number)=>{ s=Math.max(0,s); const m=Math.floor(s/60); const x=s-m*60; return `${m}:${x<10?'0':''}${x.toFixed(1)}`; };
type Arrasto={id:string;modo:'mover'|'esq'|'dir';x0:number;orig:Clip;antes:Proj;mexeu:boolean};

const COR_CAMADA:Record<string,string>={narracao:'#2fc592',trilha:'#9b78f0',efeito:'#e56a6a'};
/** Visão do vídeo inteiro: a onda de cada camada do começo ao fim, com a janela que está aberta na linha do tempo. Toque ou arraste para ir até um ponto. */
function Resumo({p,arquivos,total,tempo,janela,onIr}:{p:Proj;arquivos:Arquivo[];total:number;tempo:number;janela:[number,number];onIr:(t:number)=>void}){
  const ref=useRef<HTMLCanvasElement>(null); const [larg,setLarg]=useState(600); const [pk,setPk]=useState<Map<string,Picos>>(new Map()); const seg=useRef(false);
  const sons=p.clips.filter(ehAudio); const fontes=[...new Set(sons.map(c=>c.fonte))].sort().join('|');
  useEffect(()=>{ const c=ref.current; if(!c) return; const ro=new ResizeObserver(()=>setLarg(Math.max(200,Math.round(c.clientWidth)))); ro.observe(c); return ()=>ro.disconnect(); },[]);
  useEffect(()=>{ let vivo=true; (async()=>{ const m=new Map<string,Picos>(); for(const f of fontes?fontes.split('|'):[]){ const x=await picosDe(f,arquivos); if(x) m.set(f,x); } if(vivo) setPk(m); })(); return ()=>{ vivo=false; }; },[fontes,arquivos.length]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(()=>{ const c=ref.current; if(!c) return; const x=c.getContext('2d')!; const W=c.width, H=c.height, lin=H/3; x.clearRect(0,0,W,H);
    x.fillStyle='rgba(255,255,255,.06)'; for(const v of p.clips) if(v.faixa==='video') x.fillRect(Math.round(v.ini/total*W),0,1,H);
    CAMADAS.forEach(([f],k)=>{ const g=ganhoCamada(p,f); x.globalAlpha=g<=0?0.25:1; x.fillStyle=COR_CAMADA[f]; const meio=k*lin+lin/2;
      for(const c2 of sons) if(c2.faixa===f){ const q=pk.get(c2.fonte); const x0=c2.ini/total*W, x1=Math.min(W,(c2.ini+c2.dur)/total*W);
        if(!q){ x.fillRect(x0,meio-1,Math.max(1,x1-x0),2); continue; }
        const ganho=Math.max(0.1,Math.min(1,c2.vol/100*Math.max(g,0.4)))/q.max; const passo=total/W;
        for(let i=Math.floor(x0);i<x1;i++){ let t=c2.de+(i/W*total-c2.ini); if(t<0) continue; let m=0; for(let j=0;j<4;j++){ let tt=t+passo*j/4; if(c2.loop&&q.dur>0) tt%=q.dur; const v=q.p[Math.floor(tt*PPS_ONDA)]||0; if(v>m) m=v; } const h=Math.max(1,m*ganho*(lin-2)); x.fillRect(i,meio-h/2,1,h); } } });
    x.globalAlpha=1; const a=janela[0]/total*W, b=Math.min(W,janela[1]/total*W); x.fillStyle='rgba(255,255,255,.10)'; x.fillRect(a,0,Math.max(2,b-a),H); x.strokeStyle='rgba(255,255,255,.7)'; x.lineWidth=1; x.strokeRect(a+0.5,0.5,Math.max(2,b-a)-1,H-1);
    x.fillStyle='#ff4d6d'; x.fillRect(Math.round(tempo/total*W),0,2,H); },[p,pk,total,tempo,janela[0],janela[1],larg]); // eslint-disable-line react-hooks/exhaustive-deps
  const ir=(e:React.PointerEvent<HTMLCanvasElement>)=>{ const r=e.currentTarget.getBoundingClientRect(); onIr(Math.max(0,Math.min(total,(e.clientX-r.left)/r.width*total))); };
  return <div className="ed-resumo"><div className="ed-resumo-nomes">{CAMADAS.map(([f,n])=><span key={f} style={{color:COR_CAMADA[f]}}>{n}</span>)}</div>
   <canvas ref={ref} width={larg} height={66} aria-label="Áudio completo do vídeo" data-ondas={pk.size} onPointerDown={e=>{ seg.current=true; e.currentTarget.setPointerCapture(e.pointerId); ir(e); }} onPointerMove={e=>{ if(seg.current) ir(e); }} onPointerUp={()=>{ seg.current=false; }} onPointerCancel={()=>{ seg.current=false; }}/></div>;
}

/** Amostra de um estilo de legenda. */
function Amostra({p}:{p:Preset}){
  const ref=useRef<HTMLCanvasElement>(null);
  useEffect(()=>{ const c=ref.current; if(!c) return; const x=c.getContext('2d')!; const g=x.createLinearGradient(0,0,c.width,c.height); g.addColorStop(0,'#2a3350'); g.addColorStop(1,'#151a28'); x.fillStyle=g; x.fillRect(0,0,c.width,c.height);
    x.save(); x.scale(0.5,0.5); drawCaption(x,{...p,position:'center',safeAreaBottomPercent:0},'esse é o melhor momento',0.5,2.4,c.width*2,c.height*2); x.restore(); },[p]);
  return <canvas ref={ref} width={540} height={180} className="ed-amostra"/>;
}

/** Onda do som dentro do bloco: mostra o trecho usado e encolhe junto com o volume. */
function Onda({fonte,arquivos,de,dur,loop,vol,larg}:{fonte:string;arquivos:Arquivo[];de:number;dur:number;loop:boolean;vol:number;larg:number}){
  const ref=useRef<HTMLCanvasElement>(null); const [pk,setPk]=useState<Picos|null>(null); const tem=fonte.startsWith('site:')||arquivos.some(a=>a.id===fonte);
  useEffect(()=>{ let vivo=true; picosDe(fonte,arquivos).then(x=>{ if(vivo) setPk(x); }); return ()=>{ vivo=false; }; },[fonte,tem]); // eslint-disable-line react-hooks/exhaustive-deps
  const w=Math.max(4,Math.min(6000,Math.round(larg)));
  useEffect(()=>{ const c=ref.current; if(!c) return; const x=c.getContext('2d')!; const h=c.height; x.clearRect(0,0,c.width,h); if(!pk) return; x.fillStyle='rgba(255,255,255,.55)';
    const g=Math.max(0.12,Math.min(1,vol/100))/pk.max;
    for(let i=0;i<c.width;i++){ let t=de+i/c.width*dur; if(loop&&pk.dur>0) t%=pk.dur; const a=(pk.p[Math.floor(t*PPS_ONDA)]||0)*g; const y=Math.max(1,a*h); x.fillRect(i,(h-y)/2,1,y); } },[pk,de,dur,loop,vol,w]);
  return <canvas ref={ref} className="ed-onda" width={w} height={36} data-onda={pk?'ok':''}/>;
}

export default function EditorVideo({inicial,arquivos,onChange,onEnviar}:{inicial:Proj;arquivos:Arquivo[];onChange:(p:Proj,manual:boolean)=>void;onEnviar?:(tipo:TipoArq,fs:FileList|null)=>Promise<Arquivo[]>}){
  const {toast}=useApp();
  const [p,setP]=useState<Proj>(inicial); const pRef=useRef(p); pRef.current=p;
  const desfazer=useRef<Proj[]>([]); const refazer=useRef<Proj[]>([]); const [,forca]=useState(0);
  const [sel,setSel]=useState<string>(''); const [tempo,setTempo]=useState(0); const [pps,setPps]=useState(50);
  const [tocando,setTocando]=useState(false); const [ocupado,setOcupado]=useState(''); const [aba,setAba]=useState<'ajustes'|'sons'|'midia'|'camadas'|'estilo'>('sons'); const [empurra,setEmpurra]=useState(false);
  const [video,setVideo]=useState<{url:string;blob:Blob;ext:string}|null>(null);
  const cv=useRef<HTMLCanvasElement>(null); const sessao=useRef<Sessao|null>(null); const arr=useRef<Arrasto|null>(null);
  const rolo=useRef<HTMLDivElement>(null); const [vista,setVista]=useState<[number,number]>([0,600]);
  const audioCache=useRef<{chave:string;buf:AudioBuffer|null}|null>(null);
  const total=totalDe(p); const clipSel=p.clips.find(c=>c.id===sel);

  function commit(n:Proj,antes:Proj=pRef.current){ desfazer.current.push(antes); if(desfazer.current.length>80) desfazer.current.shift(); refazer.current=[]; setP(n); onChange(n,true); forca(x=>x+1); }
  const voltar=()=>{ const a=desfazer.current.pop(); if(!a) return; refazer.current.push(pRef.current); setP(a); onChange(a,true); forca(x=>x+1); };
  const avancar=()=>{ const a=refazer.current.pop(); if(!a) return; desfazer.current.push(pRef.current); setP(a); onChange(a,true); forca(x=>x+1); };
  const mudarClip=(id:string,m:Partial<Clip>)=>commit({...p,clips:p.clips.map(c=>c.id===id?{...c,...m} as Clip:c)});

  // Duração real dos sons feitos pelo site.
  useEffect(()=>{ let vivo=true; acertarDuracoes(pRef.current,arquivos).then(n=>{ if(n&&vivo){ setP(n); onChange(n,false); } }); return ()=>{ vivo=false; }; },[p.clips.length,arquivos.length,p.clips.filter(c=>ehAudio(c)&&!c.fonteDur).length]); // eslint-disable-line react-hooks/exhaustive-deps
  // Prévia parada.
  useEffect(()=>{ const c=cv.current; if(!c||tocando) return; const [w,h]=TAMANHO[p.formato]; if(c.width!==w/2){ c.width=w/2; c.height=h/2; }
    sincronizarVideosProj(p,tempo,false); const x=c.getContext('2d')!; desenharProj(x,p,Math.min(tempo,total-0.01)); const t=setTimeout(()=>desenharProj(x,p,Math.min(tempo,total-0.01)),80); return ()=>clearTimeout(t); },[p,tempo,tocando,total]);
  useEffect(()=>()=>{ sessao.current?.parar(); },[]);

  async function audio(){
    const chave=JSON.stringify([p.abaixarTrilha,p.mix||0,arquivos.length,p.clips.filter(ehAudio)]);
    if(audioCache.current?.chave===chave) return audioCache.current.buf;
    setOcupado('Preparando o áudio'); try{ const buf=await mixarProj(p,arquivos,setOcupado); audioCache.current={chave,buf}; return buf; } finally{ setOcupado(''); }
  }
  function parar(){ sessao.current?.parar(); sessao.current=null; setTocando(false); }
  async function play(){
    if(tocando){ parar(); return; }
    try{ const a=await audio(); const c=cv.current!; const de=tempo>=total-0.1?0:tempo; setTocando(true);
      const se=tocarProj(c,p,a,{inicio:de,onTempo:t=>setTempo(Math.min(t,total))}); sessao.current=se; se.fim.then(()=>{ if(sessao.current===se){ sessao.current=null; setTocando(false); } }); }
    catch(e){ setTocando(false); toast(e instanceof Error?e.message:String(e),'erro'); }
  }
  async function exportar(){
    parar();
    try{ const a=await audio(); setOcupado('Gravando: 0%');
      const r=await gravarProj(p,a,t=>setOcupado(`Gravando: ${Math.min(99,Math.round(t/total*100))}% (grava em tempo real, deixe esta aba aberta)`));
      if(video) URL.revokeObjectURL(video.url); setVideo({url:URL.createObjectURL(r.blob),blob:r.blob,ext:r.ext}); toast('Vídeo pronto. Baixe abaixo da prévia.','ok'); }
    catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); } finally{ setOcupado(''); }
  }

  // Teclado: espaço toca/para, S divide, Delete apaga, Ctrl+Z / Ctrl+Y.
  useEffect(()=>{ const h=(e:KeyboardEvent)=>{ const alvo=e.target as HTMLElement; if(/INPUT|TEXTAREA|SELECT/.test(alvo.tagName)) return;
    if(e.key===' '){ e.preventDefault(); play(); }
    else if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){ e.preventDefault(); if(e.shiftKey) avancar(); else voltar(); }
    else if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='y'){ e.preventDefault(); avancar(); }
    else if((e.key==='Delete'||e.key==='Backspace')&&sel){ e.preventDefault(); commit(apagar(p,sel)); setSel(''); }
    else if(e.key.toLowerCase()==='s'&&sel){ commit(dividir(p,sel,tempo)); } };
    window.addEventListener('keydown',h); return ()=>window.removeEventListener('keydown',h); });

  // Arrastar blocos e pontas, com ímã nas bordas dos outros blocos e no cursor.
  function iniciar(e:React.PointerEvent,c:Clip,modo:Arrasto['modo']){ e.stopPropagation(); e.preventDefault(); parar(); setSel(c.id); setAba('ajustes'); arr.current={id:c.id,modo,x0:e.clientX,orig:c,antes:p,mexeu:false}; }
  useEffect(()=>{
    const mover=(e:PointerEvent)=>{ const a=arr.current; if(!a) return; const dx=(e.clientX-a.x0)/pps; if(Math.abs(e.clientX-a.x0)>2) a.mexeu=true; if(!a.mexeu) return;
      const o=a.orig; const pts=[0,tempo,...a.antes.clips.filter(c=>c.id!==o.id).flatMap(c=>[c.ini,fimDe(c)])]; const ima=(t:number)=>{ for(const q of pts) if(Math.abs(q-t)*pps<8) return q; return null; };
      let n:Clip=o;
      if(a.modo==='mover'){ let ini=Math.max(0,o.ini+dx); const s1=ima(ini), s2=ima(ini+o.dur); if(s1!=null) ini=s1; else if(s2!=null) ini=s2-o.dur; n={...o,ini:+Math.max(0,ini).toFixed(3)}; }
      else if(a.modo==='dir'){ let f=o.ini+o.dur+dx; const s=ima(f); if(s!=null) f=s; n={...o,dur:+Math.min(durMax(o),Math.max(0.2,f-o.ini)).toFixed(3)}; }
      else { let ini=o.ini+dx; const s=ima(ini); if(s!=null) ini=s; const fim=fimDe(o); const temDe=ehAudio(o)?!o.loop:o.faixa==='video'&&!!o.midia&&midias.get(o.midia)?.tipo==='video';
        const minIni=Math.max(0,temDe&&'de' in o?o.ini-o.de:0); ini=Math.min(fim-0.2,Math.max(minIni,ini));
        n={...o,ini:+ini.toFixed(3),dur:+(fim-ini).toFixed(3),...('de' in o?{de:+Math.max(0,o.de+(ini-o.ini)).toFixed(3)}:{})} as Clip; }
      setP(x=>({...x,clips:x.clips.map(c=>c.id===o.id?n:c)})); };
    const soltar=()=>{ const a=arr.current; arr.current=null; if(!a?.mexeu) return; let n=pRef.current; const novo=n.clips.find(c=>c.id===a.id); if(empurra&&a.modo==='dir'&&novo) n=empurrar(n,a.id,fimDe(a.orig),fimDe(novo)-fimDe(a.orig)); commit(n,a.antes); };
    window.addEventListener('pointermove',mover); window.addEventListener('pointerup',soltar);
    return ()=>{ window.removeEventListener('pointermove',mover); window.removeEventListener('pointerup',soltar); }; });

  const irPara=(e:React.PointerEvent<HTMLDivElement>)=>{ const r=e.currentTarget.getBoundingClientRect(); parar(); setTempo(Math.max(0,Math.min(total,(e.clientX-r.left)/pps))); };
  function addSom(nome:string,fonte:string,dur:number){ const c:ClipA={faixa:'efeito',id:novoId(),ini:+tempo.toFixed(3),dur,fonte,nome,de:0,fonteDur:fonte.startsWith('site:')?0:dur,vol:80,fadeIn:0,fadeOut:0,loop:false}; commit({...p,clips:[...p.clips,c]}); setSel(c.id); toast(`"${nome}" entrou em ${fmt(tempo)}.`,'ok'); }
  function addAudio(a:Arquivo,faixa:'narracao'|'trilha'|'efeito'){ const loop=faixa==='trilha'; const c:ClipA={faixa,id:novoId(),ini:+tempo.toFixed(3),dur:loop?Math.max(1,total-tempo):a.duracao,fonte:a.id,nome:a.nome,de:0,fonteDur:a.duracao,vol:faixa==='trilha'?30:faixa==='efeito'?80:100,fadeIn:loop?0.8:0,fadeOut:loop?1.2:0,loop}; commit({...p,clips:[...p.clips,c]}); setSel(c.id); }
  function addImagem(a:Arquivo){ if(a.midia==='video'){ addVideoPronto(a); return; } const c:Clip={faixa:'video',id:novoId(),ini:+tempo.toFixed(3),dur:3,midia:a.id,de:0,anim:'zoom-in',entrada:'fade',brilho:100,contraste:100,saturacao:100}; commit({...p,clips:[...p.clips,c]}); setSel(c.id); }
  function addTexto(){ const c:Clip={faixa:'texto',id:novoId(),ini:+tempo.toFixed(3),dur:3,texto:'Seu texto aqui',pos:'meio',tam:120,cor:'#ffffff',fundo:true}; commit({...p,clips:[...p.clips,c]}); setSel(c.id); setAba('ajustes'); }
  function mudarDur(c:Clip,d:number){ d=Math.min(durMax(c),Math.max(0.2,d)); let n:Proj={...p,clips:p.clips.map(x=>x.id===c.id?{...x,dur:d} as Clip:x)}; if(empurra) n=empurrar(n,c.id,fimDe(c),d-c.dur); commit(n); }
  function mudarCamada(f:FaixaAudio,m:Partial<Camada>){ commit({...p,mix:{...p.mix,[f]:{...camadaDe(p,f),...m}}}); }
  /** Troca o som de um bloco por outro (da biblioteca do site ou um arquivo seu), sem tirar do lugar. */
  function trocarSom(c:ClipA,fonte:string,nome:string,dur:number){ const site=fonte.startsWith('site:'); const curto=c.faixa==='efeito'||dur<c.dur;
    mudarClip(c.id,{fonte,nome,de:0,fonteDur:site?0:dur,dur:c.loop?c.dur:curto?dur:c.dur} as Partial<ClipA>); toast(`Agora este bloco toca "${nome}".`,'ok'); }
  const vidSel=clipSel&&clipSel.faixa==='video'?clipSel as ClipV:null; const txtSel=clipSel&&clipSel.faixa==='texto'?clipSel:null;
  /** Estilo de legenda: no texto selecionado, ou em todas as legendas do vídeo. */
  function usarLegenda(id:string){ if(txtSel){ mudarClip(txtSel.id,{estilo:id}); return; } commit({...p,legenda:id,clips:p.clips.map(c=>c.faixa==='texto'?{...c,estilo:undefined}:c)}); toast('Estilo aplicado em todas as legendas.','ok'); }
  function usarEfeito(id:EfeitoV){ if(vidSel){ mudarClip(vidSel.id,{efeito:id}); return; } commit({...p,clips:p.clips.map(c=>c.faixa==='video'?{...c,efeito:id}:c)}); toast('Efeito aplicado em todos os blocos de vídeo.','ok'); }
  const legAtual=txtSel?(txtSel.estilo||p.legenda||'simples'):(p.legenda||'simples'); const nTextos=p.clips.filter(c=>c.faixa==='texto').length;
  const efSel=clipSel&&clipSel.faixa==='efeito'?clipSel as ClipA:null;
  async function enviarAqui(tipo:TipoArq,fs:FileList|null,depois?:(a:Arquivo)=>void|Promise<void>){ if(!onEnviar||!fs?.length) return; const novos=await onEnviar(tipo,fs); for(const a of novos) await depois?.(a); }
  /** Vídeo pronto: entra inteiro, com o som dele numa camada para abaixar, cortar ou cobrir com outros sons. */
  async function addVideoPronto(a:Arquivo){ let som=false; setOcupado('Lendo o som do vídeo'); try{ await audioDe(a); som=true; }catch{ /* vídeo sem som */ } setOcupado('');
    const vazio=!pRef.current.clips.length; const el=midias.get(a.id)?.el as HTMLVideoElement|undefined; let formato=pRef.current.formato;
    if(vazio&&el?.videoWidth){ const r=el.videoWidth/el.videoHeight; formato=r>1.3?'16:9':r<0.8?'9:16':'1:1'; }
    const novos=clipsDeVideo(a,vazio?0:+tempo.toFixed(3),som); commit({...pRef.current,formato,clips:[...pRef.current.clips,...novos]}); setSel(novos[novos.length-1].id); setAba('camadas');
    toast(som?'Vídeo aberto. O som dele está na camada Vozes: abaixe, corte ou coloque efeitos e música por cima.':'Vídeo aberto. Ele não tem som: coloque vozes, música e efeitos nas camadas.','ok'); }
  const trecho=useRef<{ac:AudioContext}|null>(null);
  async function ouvirClip(c:ClipA){ try{ trecho.current?.ac.close().catch(()=>{}); const b=await bufferDe(c.fonte,arquivos); if(!b) return; const ac=new AudioContext(); trecho.current={ac}; const n=ac.createBufferSource(); n.buffer=b; n.loop=c.loop; const g=ac.createGain(); g.gain.value=Math.max(0,c.vol)/100; n.connect(g).connect(ac.destination); n.start(0,Math.min(c.de,b.duration)); n.stop(ac.currentTime+Math.min(c.dur,15)); }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); } }
  const ouvir=useRef<HTMLAudioElement|null>(null);
  async function tocarSom(nome:string){ try{ const g=await gerarSom(nome,'site'); ouvir.current?.pause(); const a=new Audio(URL.createObjectURL(g.wav)); ouvir.current=a; await a.play(); }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); } }

  // Blocos que se sobrepõem na mesma faixa vão para linhas de baixo (como nos editores de vídeo).
  const linhas=useMemo(()=>{ const lane=new Map<string,number>(); const alt:Record<string,number>={};
    for(const [f] of FAIXAS){ const fins:number[]=[]; for(const c of p.clips.filter(x=>x.faixa===f).sort((a,b)=>a.ini-b.ini)){ let k=fins.findIndex(e=>e<=c.ini+0.001); if(k<0){ k=fins.length; fins.push(0); } fins[k]=fimDe(c); lane.set(c.id,k); } alt[f]=Math.max(1,fins.length)*40+4; }
    return {lane,alt}; },[p.clips]);
  const largura=Math.max(600,total*pps+120);
  // Janela visível da linha do tempo (para o resumo do vídeo inteiro).
  const medir=()=>{ const r=rolo.current; if(r) setVista(v=>v[0]===r.scrollLeft&&v[1]===r.clientWidth?v:[r.scrollLeft,r.clientWidth]); };
  useEffect(()=>{ const r=rolo.current; if(!r) return; medir(); const ro=new ResizeObserver(medir); ro.observe(r); return ()=>ro.disconnect(); },[]); // eslint-disable-line react-hooks/exhaustive-deps
  const verTudo=()=>{ const r=rolo.current; if(!r) return; setPps(Math.max(1.5,Math.min(300,(r.clientWidth-130)/total))); r.scrollLeft=0; setTimeout(medir,50); };
  const irResumo=(t:number)=>{ parar(); setTempo(t); const r=rolo.current; if(r){ r.scrollLeft=Math.max(0,t*pps-r.clientWidth/2); medir(); } };
  const passoRegua=pps>=80?1:pps>=40?2:pps>=20?5:pps>=8?10:pps>=3?30:60;
  const marcas=useMemo(()=>Array.from({length:Math.ceil((total+120/pps)/passoRegua)+1},(_,i)=>i*passoRegua),[total,passoRegua]);
  const nomeMidia=(id:string)=>arquivos.find(a=>a.id===id)?.nome||'sem imagem';
  const imgSrc=(id:string)=>{ const m=id?midias.get(id):undefined; return m?.tipo==='imagem'?(m.el as HTMLImageElement).src:''; };

  return <div className="ed">
   <div className="ed-topo">
    <div className="ed-previa">
     <canvas ref={cv} className={'ed-canvas f'+p.formato.replace(':','x')}/>
     {video&&<div className="ed-pronto"><video src={video.url} controls/><button className="primary sm" onClick={()=>baixar(video.blob,`video-editado-${p.formato.replace(':','x')}.${video.ext}`)}><Download size={14}/> Baixar ({video.ext.toUpperCase()})</button></div>}
    </div>
    <div className="ed-painel">
     <div className="ed-abas">{([['sons','Efeitos sonoros'],['camadas','Camadas de áudio'],['estilo','Legendas e efeitos'],['midia','Mídia'],['ajustes','Ajustes']] as const).map(([k,n])=><button key={k} className={aba===k?'on':''} onClick={()=>setAba(k)}>{n}</button>)}</div>
     {aba==='sons'&&<div className="ed-lib">
      <p className="hint">Toque no ▶ para ouvir e em + para colocar no cursor ({fmt(tempo)}). Todos são feitos pelo site, grátis.{efSel?<> Com um efeito selecionado, o botão <ArrowLeftRight size={11}/> troca o som dele por outro.</>:' Para trocar um efeito que já está no vídeo, toque nele na linha do tempo.'}</p>
      {efSel&&<p className="ed-trocando">Trocando: <b>{efSel.nome}</b> em {fmt(efSel.ini)}</p>}
      {CATEGORIAS_SOM.map(([cat,nomes])=><div key={cat}><h4>{cat}</h4><div className="ed-sons">{nomes.map(n=><div key={n} className="ed-som"><button className="icon-btn" onClick={()=>tocarSom(n)} aria-label={'Ouvir '+n}><Play size={12}/></button><span>{n}</span>{efSel&&<button className="icon-btn" onClick={()=>trocarSom(efSel,'site:'+n,n,receitaDe(n)?.dur||1.5)} aria-label={'Trocar por '+n} title="Trocar o efeito selecionado por este"><ArrowLeftRight size={12}/></button>}<button className="icon-btn" onClick={()=>addSom(n,'site:'+n,receitaDe(n)?.dur||1.5)} aria-label={'Adicionar '+n}><Plus size={13}/></button></div>)}</div></div>)}
      <h4>Meus efeitos</h4>{onEnviar&&<label className="subtle sm vc-upload"><Upload size={13}/> Enviar um efeito meu<input type="file" accept="audio/*,video/*" multiple hidden data-ed="efeito" onChange={e=>{ const fs=e.target.files; enviarAqui('efeito',fs,a=>efSel?trocarSom(efSel,a.id,a.nome,a.duracao):addAudio(a,'efeito')); e.target.value=''; }}/></label>}
      {arquivos.some(a=>a.tipo==='efeito')&&<><div className="ed-sons mt">{arquivos.filter(a=>a.tipo==='efeito').map(a=><div key={a.id} className="ed-som"><Volume2 size={12}/><span title={a.nome}>{a.nome}</span>{efSel&&<button className="icon-btn" onClick={()=>trocarSom(efSel,a.id,a.nome,a.duracao)} aria-label={'Trocar por '+a.nome}><ArrowLeftRight size={12}/></button>}<button className="icon-btn" onClick={()=>addAudio(a,'efeito')} aria-label={'Adicionar '+a.nome}><Plus size={13}/></button></div>)}</div></>}
     </div>}
     {aba==='midia'&&<div className="ed-lib">
      <p className="hint">Entra no cursor ({fmt(tempo)}). Um vídeo entra inteiro, com o som dele numa camada.</p>
      {onEnviar&&<div className="row-gap left">
       <label className="subtle sm vc-upload"><Upload size={13}/> Imagem ou vídeo<input type="file" accept="image/*,video/*" multiple hidden data-ed="quadro" onChange={e=>{ const fs=e.target.files; enviarAqui('quadro',fs,a=>addImagem(a)); e.target.value=''; }}/></label>
       <label className="subtle sm vc-upload"><Upload size={13}/> Voz<input type="file" accept="audio/*,video/*" multiple hidden data-ed="narracao" onChange={e=>{ const fs=e.target.files; enviarAqui('narracao',fs,a=>addAudio(a,'narracao')); e.target.value=''; }}/></label>
       <label className="subtle sm vc-upload"><Upload size={13}/> Música<input type="file" accept="audio/*,video/*" multiple hidden data-ed="trilha" onChange={e=>{ const fs=e.target.files; enviarAqui('trilha',fs,a=>addAudio(a,'trilha')); e.target.value=''; }}/></label>
      </div>}
      <h4>Imagens e vídeos</h4><div className="ed-midias">{arquivos.filter(a=>a.tipo==='quadro').map(a=><button key={a.id} className="ed-mid" onClick={()=>clipSel?.faixa==='video'?mudarClip(clipSel.id,{midia:a.id}):addImagem(a)} title={clipSel?.faixa==='video'?'Trocar a imagem do bloco selecionado':'Adicionar no cursor'}>{imgSrc(a.id)?<img src={imgSrc(a.id)} alt=""/>:<span>vídeo</span>}<small>{a.nome}</small></button>)}</div>
      {(['narracao','trilha'] as const).map(f=>arquivos.some(a=>a.tipo===f)&&<div key={f}><h4>{f==='trilha'?'Trilhas':'Narrações'}</h4><div className="ed-sons">{arquivos.filter(a=>a.tipo===f).map(a=><div key={a.id} className="ed-som"><Volume2 size={12}/><span title={a.nome}>{a.nome}</span><button className="icon-btn" onClick={()=>addAudio(a,f)} aria-label={'Adicionar '+a.nome}><Plus size={13}/></button></div>)}</div></div>)}
     </div>}
     {aba==='estilo'&&<div className="ed-lib">
      <h4>Estilo das legendas</h4>
      <p className="hint">{txtSel?<>Vale só para o texto selecionado. Toque fora dele na linha do tempo para mudar todas de uma vez.</>:nTextos?`Vale para as ${nTextos} legendas e textos do vídeo. Para mudar só uma, toque nela na linha do tempo antes.`:'Este vídeo ainda não tem legenda. Sincronize um roteiro com falas ou use o botão Texto.'}</p>
      <div className="ed-estilos">
       <button className={'ed-estilo'+(legAtual==='simples'?' on':'')} onClick={()=>usarLegenda('simples')} aria-label="Legenda Simples"><span className="ed-amostra simples">esse é o melhor momento</span><b>Simples</b></button>
       {captionPresets.map(c=><button key={c.id} className={'ed-estilo'+(legAtual===c.id?' on':'')} onClick={()=>usarLegenda(c.id)} aria-label={'Legenda '+c.nome}><Amostra p={c}/><b>{c.nome}</b></button>)}
      </div>
      <h4>Efeitos de vídeo</h4>
      <p className="hint">{vidSel?'Vale para o bloco de vídeo selecionado.':'Sem bloco selecionado, vale para todos os blocos de vídeo. Para mudar só um, toque nele antes.'} Movimento, brilho e cor ficam em Ajustes.</p>
      <div className="ed-efeitos">{EFEITOS_VIDEO.map(([id,n,d])=><button key={id} className={'ed-efeito'+(vidSel&&(vidSel.efeito||'nenhum')===id?' on':'')} onClick={()=>usarEfeito(id)} aria-label={'Efeito '+n}><b>{n}</b><small>{d}</small></button>)}</div>
     </div>}
     {aba==='camadas'&&<div className="ed-lib ed-camadas">
      <p className="hint">Cada camada de som do vídeo. Abaixe, deixe muda ou ouça só uma para conferir. Os blocos de cada camada estão na linha do tempo, com o desenho da onda.</p>
      {CAMADAS.map(([f,n])=>{ const c=camadaDe(p,f); const blocos=p.clips.filter(x=>x.faixa===f) as ClipA[]; return <div key={f} className={'ed-camada '+f+(ganhoCamada(p,f)<=0?' off':'')} data-camada={f}>
       <div className="ed-camada-topo"><b>{n}</b><small>{blocos.length} bloco(s)</small>
        <button className={'icon-btn'+(c.mudo?' on':'')} onClick={()=>mudarCamada(f,{mudo:!c.mudo})} aria-label={(c.mudo?'Ligar ':'Deixar muda ')+n} title={c.mudo?'Ligar':'Deixar muda'}>{c.mudo?<VolumeX size={15}/>:<Volume2 size={15}/>}</button>
        <button className={'icon-btn'+(c.solo?' on':'')} onClick={()=>mudarCamada(f,{solo:!c.solo})} aria-label={'Ouvir só '+n} title="Ouvir só esta camada"><Headphones size={15}/></button></div>
       <label className="ed-camada-vol">Volume {c.vol}%<input type="range" min={0} max={200} step={5} value={c.vol} onChange={e=>mudarCamada(f,{vol:+e.target.value})} aria-label={'Volume de '+n}/></label>
       {blocos.length>0&&<ul className="ed-camada-lista">{[...blocos].sort((a,b)=>a.ini-b.ini).map(b=><li key={b.id} className={b.id===sel?'sel':''}><button className="link-btn" onClick={()=>{ setSel(b.id); parar(); setTempo(b.ini); }} title="Ir para este bloco">{fmt(b.ini)}</button><span title={b.nome}>{b.nome}</span><small>{b.vol}%</small><button className="icon-btn" onClick={()=>ouvirClip(b)} aria-label={'Ouvir '+b.nome}><Play size={11}/></button></li>)}</ul>}
      </div>; })}
      <label className="check"><input type="checkbox" checked={p.abaixarTrilha} onChange={e=>commit({...p,abaixarTrilha:e.target.checked})}/> Abaixar a música sozinha quando houver voz</label>
     </div>}
     {aba==='ajustes'&&<div className="ed-ajustes">
      {!clipSel&&<p className="hint">Toque num bloco da linha do tempo para ajustar.</p>}
      {clipSel&&<>
       <h4>{FAIXAS.find(f=>f[0]===clipSel.faixa)?.[1]} • {fmt(clipSel.ini)} – {fmt(fimDe(clipSel))}</h4>
       <div className="ed-campos">
        <label>Começa (s)<input type="number" step={0.1} min={0} value={+clipSel.ini.toFixed(2)} onChange={e=>mudarClip(clipSel.id,{ini:Math.max(0,+e.target.value||0)})}/></label>
        <label>Dura (s)<input type="number" step={0.1} min={0.2} value={+clipSel.dur.toFixed(2)} onChange={e=>mudarDur(clipSel,+e.target.value||0.2)}/></label>
       </div>
       {clipSel.faixa==='video'&&<div className="ed-campos">
        <label>Imagem<select value={clipSel.midia} onChange={e=>mudarClip(clipSel.id,{midia:e.target.value})}><option value="">Sem imagem</option>{arquivos.filter(a=>a.tipo==='quadro').map(a=><option key={a.id} value={a.id}>{a.nome}</option>)}</select></label>
        <label>Movimento<select value={clipSel.anim} onChange={e=>mudarClip(clipSel.id,{anim:e.target.value as Anim})}>{ANIMS.map(([k,n])=><option key={k} value={k}>{n}</option>)}</select></label>
        <label>Efeito<select value={clipSel.efeito||'nenhum'} aria-label="Efeito do bloco" onChange={e=>mudarClip(clipSel.id,{efeito:e.target.value as EfeitoV})}>{EFEITOS_VIDEO.map(([k,n])=><option key={k} value={k}>{n}</option>)}</select></label>
        <label>Entrada<select value={clipSel.entrada} onChange={e=>mudarClip(clipSel.id,{entrada:e.target.value as 'corte'|'fade'})}><option value="fade">Suave</option><option value="corte">Corte seco</option></select></label>
        {(['brilho','contraste','saturacao'] as const).map(k=><label key={k}>{k==='saturacao'?'Cor':k[0].toUpperCase()+k.slice(1)} {clipSel[k]}%<input type="range" min={0} max={200} value={clipSel[k]} onChange={e=>mudarClip(clipSel.id,{[k]:+e.target.value})}/></label>)}
       </div>}
       {clipSel.faixa==='texto'&&<div className="ed-campos">
        <label className="full">Texto<textarea rows={3} value={clipSel.texto} onChange={e=>mudarClip(clipSel.id,{texto:e.target.value})}/></label>
        <label>Estilo<select value={clipSel.estilo||''} aria-label="Estilo do texto" onChange={e=>mudarClip(clipSel.id,{estilo:e.target.value||undefined})}><option value="">O mesmo do vídeo</option><option value="simples">Simples</option>{captionPresets.map(c=><option key={c.id} value={c.id}>{c.nome}</option>)}</select></label>
        <label>Posição<select value={clipSel.pos} onChange={e=>mudarClip(clipSel.id,{pos:e.target.value as 'topo'|'meio'|'baixo'})}><option value="topo">Em cima</option><option value="meio">No meio</option><option value="baixo">Embaixo</option></select></label>
        <label>Tamanho {clipSel.tam}%<input type="range" min={50} max={250} value={clipSel.tam} onChange={e=>mudarClip(clipSel.id,{tam:+e.target.value})}/></label>
        <label>Cor<input type="color" value={clipSel.cor} onChange={e=>mudarClip(clipSel.id,{cor:e.target.value})}/></label>
        <label className="check"><input type="checkbox" checked={clipSel.fundo} onChange={e=>mudarClip(clipSel.id,{fundo:e.target.checked})}/> Fundo escuro</label>
       </div>}
       {ehAudio(clipSel)&&<div className="ed-campos">
        <p className="hint full">{clipSel.nome}{clipSel.fonte.startsWith('site:')?' (feito pelo site)':''} <button className="link-btn" onClick={()=>ouvirClip(clipSel)}>▶ ouvir só este</button></p>
        <label className="full">Trocar o som por<select value={clipSel.fonte} aria-label="Trocar o som" onChange={e=>{ const v=e.target.value; if(v.startsWith('site:')){ const n=v.slice(5); trocarSom(clipSel,v,n,receitaDe(n)?.dur||1.5); } else { const a=arquivos.find(x=>x.id===v); if(a) trocarSom(clipSel,a.id,a.nome,a.duracao); } }}>
         {!clipSel.fonte.startsWith('site:')&&!arquivos.some(a=>a.id===clipSel.fonte)&&<option value={clipSel.fonte}>{clipSel.nome}</option>}
         {clipSel.fonte.startsWith('site:')&&!receitaDe(clipSel.fonte.slice(5))&&<option value={clipSel.fonte}>{clipSel.nome}</option>}
         {arquivos.some(a=>a.tipo!=='quadro'||a.midia==='video')&&<optgroup label="Meus arquivos">{arquivos.filter(a=>a.tipo!=='quadro'||a.midia==='video').map(a=><option key={a.id} value={a.id}>{a.nome}</option>)}</optgroup>}
         {clipSel.faixa==='efeito'&&CATEGORIAS_SOM.map(([cat,nomes])=><optgroup key={cat} label={cat+' (do site)'}>{nomes.map(n=><option key={n} value={'site:'+n}>{n}</option>)}</optgroup>)}
        </select></label>
        <label>Volume {clipSel.vol}%<input type="range" min={0} max={200} step={5} value={clipSel.vol} onChange={e=>mudarClip(clipSel.id,{vol:+e.target.value})}/></label>
        <label>Aparecer aos poucos (s)<input type="number" min={0} max={10} step={0.1} value={clipSel.fadeIn} onChange={e=>mudarClip(clipSel.id,{fadeIn:Math.max(0,+e.target.value||0)})}/></label>
        <label>Sumir aos poucos (s)<input type="number" min={0} max={10} step={0.1} value={clipSel.fadeOut} onChange={e=>mudarClip(clipSel.id,{fadeOut:Math.max(0,+e.target.value||0)})}/></label>
        <label className="check"><input type="checkbox" checked={clipSel.loop} onChange={e=>mudarClip(clipSel.id,{loop:e.target.checked})}/> Repetir até o fim do bloco</label>
       </div>}
       <div className="row-gap left mt"><button className="subtle sm" onClick={()=>commit(dividir(p,clipSel.id,tempo))}><Scissors size={13}/> Dividir no cursor</button><button className="subtle sm" onClick={()=>commit(duplicar(p,clipSel.id))}><Copy size={13}/> Duplicar</button><button className="subtle sm" onClick={()=>{ commit(apagar(p,clipSel.id)); setSel(''); }}><Trash2 size={13}/> Apagar</button></div>
      </>}
     </div>}
    </div>
   </div>

   <div className="ed-barra">
    <button className="primary sm" onClick={play} disabled={!!ocupado&&!tocando} aria-label={tocando?'Pausar':'Tocar'}>{tocando?<Pause size={15}/>:<Play size={15}/>}</button>
    <span className="ed-tempo">{fmt(tempo)} / {fmt(total)}</span>
    <button className="icon-btn" onClick={voltar} disabled={!desfazer.current.length} title="Desfazer (Ctrl+Z)" aria-label="Desfazer"><Undo2 size={16}/></button>
    <button className="icon-btn" onClick={avancar} disabled={!refazer.current.length} title="Refazer (Ctrl+Y)" aria-label="Refazer"><Redo2 size={16}/></button>
    <button className="icon-btn" onClick={()=>clipSel&&commit(dividir(p,clipSel.id,tempo))} disabled={!clipSel} title="Dividir no cursor (S)" aria-label="Dividir"><Scissors size={16}/></button>
    <button className="icon-btn" onClick={()=>{ if(clipSel){ commit(apagar(p,clipSel.id)); setSel(''); } }} disabled={!clipSel} title="Apagar (Delete)" aria-label="Apagar"><Trash2 size={16}/></button>
    <button className="subtle sm" onClick={addTexto}><Type size={14}/> Texto</button>
    <button className="subtle sm" onClick={()=>{ setAba('sons'); document.querySelector('.ed-painel')?.scrollIntoView({behavior:'smooth',block:'nearest'}); }}><Volume2 size={14}/> Efeito</button>
    {onEnviar&&<label className="subtle sm vc-upload" title="Abre um vídeo que já está pronto para mexer nas camadas de som"><Film size={14}/> Vídeo pronto<input type="file" accept="video/*" hidden data-ed="pronto" onChange={e=>{ const fs=e.target.files; enviarAqui('quadro',fs,a=>addVideoPronto(a)); e.target.value=''; }}/></label>}
    <span className="grow"/>
    <label className="check sm" title="Ao mudar a duração de um bloco, leva junto tudo que vem depois"><input type="checkbox" checked={empurra} onChange={e=>setEmpurra(e.target.checked)}/> Empurrar o que vem depois</label>
    <select value={p.formato} onChange={e=>commit({...p,formato:e.target.value as Formato})} aria-label="Formato"><option value="9:16">9:16</option><option value="16:9">16:9</option><option value="1:1">1:1</option></select>
    <button className="subtle sm" onClick={verTudo} title="Encaixa o vídeo inteiro na largura da tela"><Maximize2 size={13}/> Ver tudo</button>
    <button className="icon-btn" onClick={()=>setPps(x=>Math.max(1.5,x/1.5))} aria-label="Diminuir zoom"><Minus size={16}/></button>
    <button className="icon-btn" onClick={()=>setPps(x=>Math.min(300,x*1.5))} aria-label="Aumentar zoom"><Plus size={16}/></button>
    <button className="primary sm" onClick={exportar} disabled={!!ocupado}>{ocupado?<Loader2 size={14} className="spin"/>:<Download size={14}/>} Exportar vídeo</button>
   </div>
   {ocupado&&<p className="hint"><Loader2 size={13} className="spin"/> {ocupado}</p>}

   {p.clips.some(ehAudio)&&<Resumo p={p} arquivos={arquivos} total={total} tempo={tempo} janela={[vista[0]/pps,(vista[0]+vista[1])/pps]} onIr={irResumo}/>}
   <div className="ed-linha">
    <div className="ed-nomes"><div className="ed-regua-nome"/>{FAIXAS.map(([f,n])=>{ const au=f==='narracao'||f==='trilha'||f==='efeito'; const mudo=au&&ganhoCamada(p,f as FaixaAudio)<=0; return <div key={f} className={'ed-nome '+f+(mudo?' off':'')} style={{height:linhas.alt[f]}}><span>{f==='narracao'?'Vozes':f==='trilha'?'Música':n}</span>{au&&<button className="icon-btn" onClick={()=>mudarCamada(f as FaixaAudio,{mudo:!camadaDe(p,f as FaixaAudio).mudo})} aria-label={(camadaDe(p,f as FaixaAudio).mudo?'Ligar faixa ':'Silenciar faixa ')+n}>{mudo?<VolumeX size={13}/>:<Volume2 size={13}/>}</button>}</div>; })}</div>
    <div className="ed-scroll" ref={rolo} onScroll={medir}>
     <div className="ed-trilhos" style={{width:largura}}>
      <div className="ed-regua" onPointerDown={irPara}>{marcas.map(m=><span key={m} style={{left:m*pps}}>{fmt(m).replace(/\.0$/,'')}</span>)}</div>
      {FAIXAS.map(([f])=><div key={f} className={'ed-faixa '+f+((f==='narracao'||f==='trilha'||f==='efeito')&&ganhoCamada(p,f)<=0?' off':'')} style={{height:linhas.alt[f]}} onPointerDown={e=>{ setSel(''); irPara(e); }}>
       {p.clips.filter(c=>c.faixa===f).map(c=><div key={c.id} className={'ed-clip '+f+(c.id===sel?' sel':'')} style={{left:c.ini*pps,width:Math.max(6,c.dur*pps),top:4+(linhas.lane.get(c.id)||0)*40}} onPointerDown={e=>iniciar(e,c,'mover')} data-clip={c.id}>
        {ehAudio(c)&&<Onda fonte={c.fonte} arquivos={arquivos} de={c.de} dur={c.dur} loop={c.loop} vol={c.vol} larg={c.dur*pps}/>}
        {c.faixa==='video'&&imgSrc(c.midia)&&<img src={imgSrc(c.midia)} alt=""/>}
        <span>{c.faixa==='video'?nomeMidia(c.midia):c.faixa==='texto'?c.texto:(c as ClipA).nome}</span>
        <i className="ed-borda esq" onPointerDown={e=>iniciar(e,c,'esq')}/><i className="ed-borda dir" onPointerDown={e=>iniciar(e,c,'dir')}/>
       </div>)}
      </div>)}
      <div className="ed-cursor" style={{left:tempo*pps}}/>
     </div>
    </div>
   </div>
   {!p.clips.length&&<p className="ed-vazio">A linha do tempo está vazia. Sincronize o roteiro em Preparar, toque em <b>Vídeo pronto</b> para abrir um vídeo que já existe, ou coloque imagens e sons pela aba Mídia.</p>}
   <p className="hint">Arraste os blocos para mudar o momento e puxe as pontas para cortar. Eles grudam nas bordas dos outros blocos e no cursor. Atalhos: espaço toca, S divide, Delete apaga, Ctrl+Z desfaz.</p>
  </div>;
}

export type { Faixa };
