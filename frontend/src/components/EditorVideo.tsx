import { useEffect, useMemo, useRef, useState } from 'react';
import { Copy, Download, Loader2, Minus, Pause, Play, Plus, Redo2, Scissors, Trash2, Type, Undo2, Volume2 } from 'lucide-react';
import { useApp } from '../state';
import { baixar } from '../lib/exporter';
import { CATEGORIAS_SOM, gerarSom, receitaDe } from '../lib/sons';
import { ANIMS, TAMANHO, midias, type Anim, type Arquivo, type Formato } from '../lib/montagem';
import {
  FAIXAS, acertarDuracoes, apagar, desenharProj, dividir, duplicar, durMax, ehAudio, fimDe, gravarProj, mixarProj, novoId, sincronizarVideosProj, tocarProj, totalDe,
  type Clip, type ClipA, type Faixa, type Proj, type Sessao,
} from '../lib/editor';

const fmt=(s:number)=>{ s=Math.max(0,s); const m=Math.floor(s/60); const x=s-m*60; return `${m}:${x<10?'0':''}${x.toFixed(1)}`; };
type Arrasto={id:string;modo:'mover'|'esq'|'dir';x0:number;orig:Clip;antes:Proj;mexeu:boolean};

export default function EditorVideo({inicial,arquivos,onChange}:{inicial:Proj;arquivos:Arquivo[];onChange:(p:Proj)=>void}){
  const {toast}=useApp();
  const [p,setP]=useState<Proj>(inicial); const pRef=useRef(p); pRef.current=p;
  const desfazer=useRef<Proj[]>([]); const refazer=useRef<Proj[]>([]); const [,forca]=useState(0);
  const [sel,setSel]=useState<string>(''); const [tempo,setTempo]=useState(0); const [pps,setPps]=useState(50);
  const [tocando,setTocando]=useState(false); const [ocupado,setOcupado]=useState(''); const [aba,setAba]=useState<'ajustes'|'sons'|'midia'>('sons');
  const [video,setVideo]=useState<{url:string;blob:Blob;ext:string}|null>(null);
  const cv=useRef<HTMLCanvasElement>(null); const sessao=useRef<Sessao|null>(null); const arr=useRef<Arrasto|null>(null);
  const audioCache=useRef<{chave:string;buf:AudioBuffer|null}|null>(null);
  const total=totalDe(p); const clipSel=p.clips.find(c=>c.id===sel);

  function commit(n:Proj,antes:Proj=pRef.current){ desfazer.current.push(antes); if(desfazer.current.length>80) desfazer.current.shift(); refazer.current=[]; setP(n); onChange(n); forca(x=>x+1); }
  const voltar=()=>{ const a=desfazer.current.pop(); if(!a) return; refazer.current.push(pRef.current); setP(a); onChange(a); forca(x=>x+1); };
  const avancar=()=>{ const a=refazer.current.pop(); if(!a) return; desfazer.current.push(pRef.current); setP(a); onChange(a); forca(x=>x+1); };
  const mudarClip=(id:string,m:Partial<Clip>)=>commit({...p,clips:p.clips.map(c=>c.id===id?{...c,...m} as Clip:c)});

  // Duração real dos sons feitos pelo site.
  useEffect(()=>{ let vivo=true; acertarDuracoes(p,arquivos).then(n=>{ if(n&&vivo){ setP(n); onChange(n); } }); return ()=>{ vivo=false; }; },[p.clips.length]); // eslint-disable-line react-hooks/exhaustive-deps
  // Prévia parada.
  useEffect(()=>{ const c=cv.current; if(!c||tocando) return; const [w,h]=TAMANHO[p.formato]; if(c.width!==w/2){ c.width=w/2; c.height=h/2; }
    sincronizarVideosProj(p,tempo,false); const x=c.getContext('2d')!; desenharProj(x,p,Math.min(tempo,total-0.01)); const t=setTimeout(()=>desenharProj(x,p,Math.min(tempo,total-0.01)),80); return ()=>clearTimeout(t); },[p,tempo,tocando,total]);
  useEffect(()=>()=>{ sessao.current?.parar(); },[]);

  async function audio(){
    const chave=JSON.stringify([p.abaixarTrilha,p.clips.filter(ehAudio)]);
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
    const soltar=()=>{ const a=arr.current; arr.current=null; if(a?.mexeu) commit(pRef.current,a.antes); };
    window.addEventListener('pointermove',mover); window.addEventListener('pointerup',soltar);
    return ()=>{ window.removeEventListener('pointermove',mover); window.removeEventListener('pointerup',soltar); }; });

  const irPara=(e:React.PointerEvent<HTMLDivElement>)=>{ const r=e.currentTarget.getBoundingClientRect(); parar(); setTempo(Math.max(0,Math.min(total,(e.clientX-r.left)/pps))); };
  function addSom(nome:string,fonte:string,dur:number){ const c:ClipA={faixa:'efeito',id:novoId(),ini:+tempo.toFixed(3),dur,fonte,nome,de:0,fonteDur:fonte.startsWith('site:')?0:dur,vol:80,fadeIn:0,fadeOut:0,loop:false}; commit({...p,clips:[...p.clips,c]}); setSel(c.id); toast(`"${nome}" entrou em ${fmt(tempo)}.`,'ok'); }
  function addAudio(a:Arquivo,faixa:'narracao'|'trilha'|'efeito'){ const loop=faixa==='trilha'; const c:ClipA={faixa,id:novoId(),ini:+tempo.toFixed(3),dur:loop?Math.max(1,total-tempo):a.duracao,fonte:a.id,nome:a.nome,de:0,fonteDur:a.duracao,vol:faixa==='trilha'?30:faixa==='efeito'?80:100,fadeIn:loop?0.8:0,fadeOut:loop?1.2:0,loop}; commit({...p,clips:[...p.clips,c]}); setSel(c.id); }
  function addImagem(a:Arquivo){ const c:Clip={faixa:'video',id:novoId(),ini:+tempo.toFixed(3),dur:a.midia==='video'&&a.duracao?Math.min(a.duracao,30):3,midia:a.id,de:0,anim:'zoom-in',entrada:'fade',brilho:100,contraste:100,saturacao:100}; commit({...p,clips:[...p.clips,c]}); setSel(c.id); }
  function addTexto(){ const c:Clip={faixa:'texto',id:novoId(),ini:+tempo.toFixed(3),dur:3,texto:'Seu texto aqui',pos:'meio',tam:120,cor:'#ffffff',fundo:true}; commit({...p,clips:[...p.clips,c]}); setSel(c.id); setAba('ajustes'); }
  const ouvir=useRef<HTMLAudioElement|null>(null);
  async function tocarSom(nome:string){ try{ const g=await gerarSom(nome,'site'); ouvir.current?.pause(); const a=new Audio(URL.createObjectURL(g.wav)); ouvir.current=a; await a.play(); }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); } }

  // Blocos que se sobrepõem na mesma faixa vão para linhas de baixo (como nos editores de vídeo).
  const linhas=useMemo(()=>{ const lane=new Map<string,number>(); const alt:Record<string,number>={};
    for(const [f] of FAIXAS){ const fins:number[]=[]; for(const c of p.clips.filter(x=>x.faixa===f).sort((a,b)=>a.ini-b.ini)){ let k=fins.findIndex(e=>e<=c.ini+0.001); if(k<0){ k=fins.length; fins.push(0); } fins[k]=fimDe(c); lane.set(c.id,k); } alt[f]=Math.max(1,fins.length)*40+4; }
    return {lane,alt}; },[p.clips]);
  const largura=Math.max(600,(total+8)*pps);
  const passoRegua=pps>=80?1:pps>=40?2:pps>=20?5:10;
  const marcas=useMemo(()=>Array.from({length:Math.ceil((total+8)/passoRegua)+1},(_,i)=>i*passoRegua),[total,passoRegua]);
  const nomeMidia=(id:string)=>arquivos.find(a=>a.id===id)?.nome||'sem imagem';
  const imgSrc=(id:string)=>{ const m=id?midias.get(id):undefined; return m?.tipo==='imagem'?(m.el as HTMLImageElement).src:''; };

  return <div className="ed">
   <div className="ed-topo">
    <div className="ed-previa">
     <canvas ref={cv} className={'ed-canvas f'+p.formato.replace(':','x')}/>
     {video&&<div className="ed-pronto"><video src={video.url} controls/><button className="primary sm" onClick={()=>baixar(video.blob,`video-editado-${p.formato.replace(':','x')}.${video.ext}`)}><Download size={14}/> Baixar ({video.ext.toUpperCase()})</button></div>}
    </div>
    <div className="ed-painel">
     <div className="ed-abas">{([['sons','Efeitos sonoros'],['midia','Mídia'],['ajustes','Ajustes']] as const).map(([k,n])=><button key={k} className={aba===k?'on':''} onClick={()=>setAba(k)}>{n}</button>)}</div>
     {aba==='sons'&&<div className="ed-lib">
      <p className="hint">Toque no ▶ para ouvir e em + para colocar no cursor ({fmt(tempo)}). Todos são feitos pelo site, grátis.</p>
      {CATEGORIAS_SOM.map(([cat,nomes])=><div key={cat}><h4>{cat}</h4><div className="ed-sons">{nomes.map(n=><div key={n} className="ed-som"><button className="icon-btn" onClick={()=>tocarSom(n)} aria-label={'Ouvir '+n}><Play size={12}/></button><span>{n}</span><button className="icon-btn" onClick={()=>addSom(n,'site:'+n,receitaDe(n)?.dur||1.5)} aria-label={'Adicionar '+n}><Plus size={13}/></button></div>)}</div></div>)}
      {arquivos.some(a=>a.tipo==='efeito')&&<><h4>Meus efeitos</h4><div className="ed-sons">{arquivos.filter(a=>a.tipo==='efeito').map(a=><div key={a.id} className="ed-som"><Volume2 size={12}/><span title={a.nome}>{a.nome}</span><button className="icon-btn" onClick={()=>addAudio(a,'efeito')} aria-label={'Adicionar '+a.nome}><Plus size={13}/></button></div>)}</div></>}
     </div>}
     {aba==='midia'&&<div className="ed-lib">
      <p className="hint">Entra no cursor ({fmt(tempo)}). Para enviar arquivos novos, use a parte 2 acima.</p>
      <h4>Imagens e vídeos</h4><div className="ed-midias">{arquivos.filter(a=>a.tipo==='quadro').map(a=><button key={a.id} className="ed-mid" onClick={()=>clipSel?.faixa==='video'?mudarClip(clipSel.id,{midia:a.id}):addImagem(a)} title={clipSel?.faixa==='video'?'Trocar a imagem do bloco selecionado':'Adicionar no cursor'}>{imgSrc(a.id)?<img src={imgSrc(a.id)} alt=""/>:<span>vídeo</span>}<small>{a.nome}</small></button>)}</div>
      {(['narracao','trilha'] as const).map(f=>arquivos.some(a=>a.tipo===f)&&<div key={f}><h4>{f==='trilha'?'Trilhas':'Narrações'}</h4><div className="ed-sons">{arquivos.filter(a=>a.tipo===f).map(a=><div key={a.id} className="ed-som"><Volume2 size={12}/><span title={a.nome}>{a.nome}</span><button className="icon-btn" onClick={()=>addAudio(a,f)} aria-label={'Adicionar '+a.nome}><Plus size={13}/></button></div>)}</div></div>)}
     </div>}
     {aba==='ajustes'&&<div className="ed-ajustes">
      {!clipSel&&<p className="hint">Toque num bloco da linha do tempo para ajustar.</p>}
      {clipSel&&<>
       <h4>{FAIXAS.find(f=>f[0]===clipSel.faixa)?.[1]} • {fmt(clipSel.ini)} – {fmt(fimDe(clipSel))}</h4>
       <div className="ed-campos">
        <label>Começa (s)<input type="number" step={0.1} min={0} value={+clipSel.ini.toFixed(2)} onChange={e=>mudarClip(clipSel.id,{ini:Math.max(0,+e.target.value||0)})}/></label>
        <label>Dura (s)<input type="number" step={0.1} min={0.2} value={+clipSel.dur.toFixed(2)} onChange={e=>mudarClip(clipSel.id,{dur:Math.min(durMax(clipSel),Math.max(0.2,+e.target.value||0.2))})}/></label>
       </div>
       {clipSel.faixa==='video'&&<div className="ed-campos">
        <label>Imagem<select value={clipSel.midia} onChange={e=>mudarClip(clipSel.id,{midia:e.target.value})}><option value="">Sem imagem</option>{arquivos.filter(a=>a.tipo==='quadro').map(a=><option key={a.id} value={a.id}>{a.nome}</option>)}</select></label>
        <label>Movimento<select value={clipSel.anim} onChange={e=>mudarClip(clipSel.id,{anim:e.target.value as Anim})}>{ANIMS.map(([k,n])=><option key={k} value={k}>{n}</option>)}</select></label>
        <label>Entrada<select value={clipSel.entrada} onChange={e=>mudarClip(clipSel.id,{entrada:e.target.value as 'corte'|'fade'})}><option value="fade">Suave</option><option value="corte">Corte seco</option></select></label>
        {(['brilho','contraste','saturacao'] as const).map(k=><label key={k}>{k==='saturacao'?'Cor':k[0].toUpperCase()+k.slice(1)} {clipSel[k]}%<input type="range" min={0} max={200} value={clipSel[k]} onChange={e=>mudarClip(clipSel.id,{[k]:+e.target.value})}/></label>)}
       </div>}
       {clipSel.faixa==='texto'&&<div className="ed-campos">
        <label className="full">Texto<textarea rows={3} value={clipSel.texto} onChange={e=>mudarClip(clipSel.id,{texto:e.target.value})}/></label>
        <label>Posição<select value={clipSel.pos} onChange={e=>mudarClip(clipSel.id,{pos:e.target.value as 'topo'|'meio'|'baixo'})}><option value="topo">Em cima</option><option value="meio">No meio</option><option value="baixo">Embaixo</option></select></label>
        <label>Tamanho {clipSel.tam}%<input type="range" min={50} max={250} value={clipSel.tam} onChange={e=>mudarClip(clipSel.id,{tam:+e.target.value})}/></label>
        <label>Cor<input type="color" value={clipSel.cor} onChange={e=>mudarClip(clipSel.id,{cor:e.target.value})}/></label>
        <label className="check"><input type="checkbox" checked={clipSel.fundo} onChange={e=>mudarClip(clipSel.id,{fundo:e.target.checked})}/> Fundo escuro</label>
       </div>}
       {ehAudio(clipSel)&&<div className="ed-campos">
        <p className="hint full">{clipSel.nome}{clipSel.fonte.startsWith('site:')?' (feito pelo site)':''}</p>
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
    <span className="grow"/>
    <label className="check sm"><input type="checkbox" checked={p.abaixarTrilha} onChange={e=>commit({...p,abaixarTrilha:e.target.checked})}/> Abaixar trilha na fala</label>
    <select value={p.formato} onChange={e=>commit({...p,formato:e.target.value as Formato})} aria-label="Formato"><option value="9:16">9:16</option><option value="16:9">16:9</option><option value="1:1">1:1</option></select>
    <button className="icon-btn" onClick={()=>setPps(x=>Math.max(10,x/1.5))} aria-label="Diminuir zoom"><Minus size={16}/></button>
    <button className="icon-btn" onClick={()=>setPps(x=>Math.min(300,x*1.5))} aria-label="Aumentar zoom"><Plus size={16}/></button>
    <button className="primary sm" onClick={exportar} disabled={!!ocupado}>{ocupado?<Loader2 size={14} className="spin"/>:<Download size={14}/>} Exportar vídeo</button>
   </div>
   {ocupado&&<p className="hint"><Loader2 size={13} className="spin"/> {ocupado}</p>}

   <div className="ed-linha">
    <div className="ed-nomes"><div className="ed-regua-nome"/>{FAIXAS.map(([f,n])=><div key={f} className={'ed-nome '+f} style={{height:linhas.alt[f]}}>{n}</div>)}</div>
    <div className="ed-scroll">
     <div className="ed-trilhos" style={{width:largura}}>
      <div className="ed-regua" onPointerDown={irPara}>{marcas.map(m=><span key={m} style={{left:m*pps}}>{fmt(m).replace(/\.0$/,'')}</span>)}</div>
      {FAIXAS.map(([f])=><div key={f} className={'ed-faixa '+f} style={{height:linhas.alt[f]}} onPointerDown={e=>{ setSel(''); irPara(e); }}>
       {p.clips.filter(c=>c.faixa===f).map(c=><div key={c.id} className={'ed-clip '+f+(c.id===sel?' sel':'')} style={{left:c.ini*pps,width:Math.max(6,c.dur*pps),top:4+(linhas.lane.get(c.id)||0)*40}} onPointerDown={e=>iniciar(e,c,'mover')} data-clip={c.id}>
        {c.faixa==='video'&&imgSrc(c.midia)&&<img src={imgSrc(c.midia)} alt=""/>}
        <span>{c.faixa==='video'?nomeMidia(c.midia):c.faixa==='texto'?c.texto:(c as ClipA).nome}</span>
        <i className="ed-borda esq" onPointerDown={e=>iniciar(e,c,'esq')}/><i className="ed-borda dir" onPointerDown={e=>iniciar(e,c,'dir')}/>
       </div>)}
      </div>)}
      <div className="ed-cursor" style={{left:tempo*pps}}/>
     </div>
    </div>
   </div>
   <p className="hint">Arraste os blocos para mudar o momento e puxe as pontas para cortar. Eles grudam nas bordas dos outros blocos e no cursor. Atalhos: espaço toca, S divide, Delete apaga, Ctrl+Z desfaz.</p>
  </div>;
}

export type { Faixa };
