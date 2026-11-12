import { useEffect, useMemo, useRef, useState } from 'react';
import { Clapperboard, Download, FileText, ImagePlus, Loader2, Mic, Music, Play, Sparkles, Square, Trash2, Volume2, Wand2, SlidersHorizontal, RotateCcw } from 'lucide-react';
import { useApp } from '../state';
import { baixar } from '../lib/exporter';
import { transcrever, transcreverGemini } from '../lib/transcribe';
import type { Cue } from '../lib/captions';
import EditorVideo from '../components/EditorVideo';
import { deSinc, type Proj } from '../lib/editor';
import {
  ANIMS, MODELO_ROTEIRO, OPCOES_PADRAO, TAMANHO, apagarArquivo, audioDe, batidas, conferirImagensIA, desenhar, gravar, guardarArquivo, lerQuadros,
  listarArquivos, midias, mixar, mono16k, prepararMidia, reencadear, sincronizar, sincronizarVideos, tocar,
  type Anim, type Arquivo, type Formato, type Opcoes, type Sessao, type Sinc, type TipoArq,
} from '../lib/montagem';

const CHAVE='studio_manual';
type Salvo={texto:string;o:Opcoes;sinc:Sinc|null;cues:Cue[]|null;cuesDe:string};
function ler():Salvo{ try{ const j=JSON.parse(localStorage.getItem(CHAVE)||'null'); if(j) return {texto:j.texto||'',o:{...OPCOES_PADRAO,...j.o},sinc:j.sinc||null,cues:j.cues||null,cuesDe:j.cuesDe||''}; }catch{ /* vazio */ } return {texto:'',o:OPCOES_PADRAO,sinc:null,cues:null,cuesDe:''}; }
const fmt=(s:number)=>{ s=Math.max(0,s); const m=Math.floor(s/60); const x=s-m*60; return `${m}:${x<10?'0':''}${x.toFixed(1)}`; };

const AREAS:[TipoArq,string,string,string,typeof ImagePlus][]=[
  ['quadro','Imagens e vídeos dos quadros','image/*,video/*','Dê nomes com o número do quadro (quadro-01.png, 2.jpg...). Sem número, entram na ordem.',ImagePlus],
  ['narracao','Narração / vozes','audio/*,video/*','Um arquivo só (o site transcreve e acha onde cada quadro começa) ou um por quadro com fala (quadro-01.mp3...).',Mic],
  ['trilha','Trilha sonora','audio/*','Toca do começo ao fim e abaixa sozinha quando alguém fala. Com [TRILHA: nome] no roteiro, troca de música naquele quadro.',Music],
  ['efeito','Efeitos sonoros','audio/*','O nome do arquivo é comparado com as marcações [SOM: ...] (ex.: porta-batendo.mp3). O que faltar, o site cria.',Volume2],
];

export default function Manual(){
  const {settings,toast}=useApp();
  const ini=useMemo(ler,[]);
  const [texto,setTexto]=useState(ini.texto); const [o,setO]=useState<Opcoes>(ini.o);
  const [sinc,setSinc]=useState<Sinc|null>(ini.sinc); const [cues,setCues]=useState<{de:string;lista:Cue[]}|null>(ini.cues?{de:ini.cuesDe,lista:ini.cues}:null);
  const [arqs,setArqs]=useState<Arquivo[]>([]); const [carregado,setCarregado]=useState(false);
  const [usarIA,setUsarIA]=useState(false); const [ocupado,setOcupado]=useState(''); const [audio,setAudio]=useState<AudioBuffer|null>(null);
  const [proj,setProj]=useState<Proj|null>(()=>{ try{ return JSON.parse(localStorage.getItem(CHAVE+'_editor')||'null'); }catch{ return null; } });
  const [versao,setVersao]=useState(0);
  const salvarProj=(n:Proj|null)=>{ try{ if(n) localStorage.setItem(CHAVE+'_editor',JSON.stringify(n)); else localStorage.removeItem(CHAVE+'_editor'); }catch{ /* cheio */ } };
  function abrirEditor(){ if(!sinc) return; parar(); const n=deSinc(sinc,arqs,o); setProj(n); salvarProj(n); setVersao(v=>v+1); setTimeout(()=>document.querySelector('.ed')?.scrollIntoView({behavior:'smooth'}),100); }
  const [tempo,setTempo]=useState(0); const [tocando,setTocando]=useState(false); const [video,setVideo]=useState<{url:string;blob:Blob;ext:string}|null>(null);
  const cv=useRef<HTMLCanvasElement>(null); const sessao=useRef<Sessao|null>(null);
  const quadros=useMemo(()=>lerQuadros(texto),[texto]);

  useEffect(()=>{ (async()=>{ try{ const l=await listarArquivos(); for(const a of l) if(a.tipo==='quadro'){ try{ await prepararMidia(a); }catch{ /* arquivo estragado */ } } setArqs(l); }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); } setCarregado(true); })(); },[]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(()=>{ try{ localStorage.setItem(CHAVE,JSON.stringify({texto,o,sinc,cues:cues?.lista||null,cuesDe:cues?.de||''})); }catch{ /* cheio */ } },[texto,o,sinc,cues]);
  useEffect(()=>{ setAudio(null); },[sinc,o.volTrilha,arqs]);
  useEffect(()=>()=>{ sessao.current?.parar(); },[]);
  // Prévia parada: desenha o quadro no tempo escolhido.
  useEffect(()=>{ const c=cv.current; if(!c||!sinc||tocando) return; const [w,h]=TAMANHO[o.formato]; c.width=w/2; c.height=h/2; const x=c.getContext('2d')!;
    sincronizarVideos(sinc,tempo,false); const t=setTimeout(()=>desenhar(x,sinc,Math.min(tempo,Math.max(0,sinc.total-0.01)),o),60); desenhar(x,sinc,Math.min(tempo,Math.max(0,sinc.total-0.01)),o); return ()=>clearTimeout(t); },[sinc,tempo,o,tocando,arqs]);

  async function enviar(tipo:TipoArq,fs:FileList|null){
    if(!fs?.length) return; const novos:Arquivo[]=[]; const erros:string[]=[];
    for(const f of Array.from(fs)){ setOcupado(`Guardando ${f.name}`); try{ novos.push(await guardarArquivo(f,tipo)); }catch(e){ erros.push(e instanceof Error?e.message:String(e)); } }
    setOcupado(''); setArqs(x=>[...x,...novos]);
    if(erros.length) toast(erros.slice(0,2).join(' | '),'erro'); else toast(`${novos.length} arquivo(s) guardados. Quando terminar de enviar, toque em Analisar e sincronizar.`,'ok');
  }
  async function remover(a:Arquivo){ await apagarArquivo(a.id); setArqs(x=>x.filter(y=>y.id!==a.id)); }
  async function limpar(tipo:TipoArq){ for(const a of arqs.filter(x=>x.tipo===tipo)) await apagarArquivo(a.id); setArqs(x=>x.filter(y=>y.tipo!==tipo)); }

  async function analisar(){
    if(!quadros.length){ toast('Cole o roteiro de quadros primeiro.','erro'); return; }
    parar();
    try{
      const nars=arqs.filter(a=>a.tipo==='narracao'); let lista:Cue[]|null=null;
      if(nars.length===1&&quadros.some(q=>q.falas.length)){
        if(cues&&cues.de===nars[0].id) lista=cues.lista;
        else{
          setOcupado('Preparando a narração para ouvir'); const sm=await mono16k(await audioDe(nars[0]));
          try{ lista=await transcrever(sm,settings.whisperModel,settings.idioma||'portuguese',(s,p)=>setOcupado(`Ouvindo a narração: ${s}${p?` ${p}%`:''}`)); }
          catch(e){ if(!settings.geminiKey) throw e; lista=await transcreverGemini(sm,settings.geminiKey,settings.idioma||'portuguese',(s,p)=>setOcupado(`${s} ${p}%`)); }
          setCues({de:nars[0].id,lista});
        }
      }
      const trs=arqs.filter(a=>a.tipo==='trilha'); let bt:number[]|null=null;
      if(trs.length&&o.naBatida&&!nars.length){ setOcupado('Procurando a batida da música'); bt=batidas(await audioDe(trs[0])); }
      let ia:Map<number,string>|undefined;
      if(usarIA){ if(!settings.geminiKey) toast('Para a IA conferir as imagens, coloque a chave do Gemini em Chaves e ajustes.','info');
        else{ setOcupado('A IA está olhando as imagens'); try{ ia=await conferirImagensIA(settings.geminiKey,quadros,arqs.filter(a=>a.tipo==='quadro')); }catch(e){ toast('A IA não conseguiu conferir as imagens: '+(e instanceof Error?e.message:String(e)),'info'); } } }
      const s=sincronizar({quadros,arquivos:arqs,cues:lista,batidas:bt,opcoes:o,imagensIA:ia});
      if(ia?.size) s.notas.unshift(`A IA escolheu a imagem de ${ia.size} quadro(s) pelo que aparece nelas.`);
      setSinc(s); setTempo(0); setVideo(null);
      toast(`Pronto: ${s.quadros.length} quadros em ${fmt(s.total)}. Confira a linha do tempo e toque em Prévia.`,'ok');
    }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }
    finally{ setOcupado(''); }
  }
  async function garantirAudio(){ if(!sinc) return null; if(audio) return audio; setOcupado('Preparando o áudio'); try{ const a=await mixar(sinc,arqs,o,t=>setOcupado(t)); setAudio(a); return a; } finally{ setOcupado(''); } }
  function parar(){ sessao.current?.parar(); sessao.current=null; setTocando(false); }
  async function previa(de=0){
    if(!sinc||!cv.current) return; parar();
    try{ const a=await garantirAudio(); const [w,h]=TAMANHO[o.formato]; cv.current.width=w/2; cv.current.height=h/2;
      setTocando(true); const se=tocar(cv.current,sinc,a,o,{inicio:de,onTempo:setTempo}); sessao.current=se; se.fim.then(()=>{ if(sessao.current===se){ sessao.current=null; setTocando(false); } }); }
    catch(e){ setTocando(false); toast(e instanceof Error?e.message:String(e),'erro'); }
  }
  async function gerarVideo(){
    if(!sinc) return; parar();
    try{ const a=await garantirAudio(); setOcupado('Gravando o vídeo: 0%');
      const r=await gravar(sinc,a,o,t=>setOcupado(`Gravando o vídeo: ${Math.min(99,Math.round(t/sinc.total*100))}% (grava em tempo real, deixe esta aba aberta)`));
      if(video) URL.revokeObjectURL(video.url); setVideo({url:URL.createObjectURL(r.blob),blob:r.blob,ext:r.ext}); toast('Vídeo pronto. Baixe logo abaixo.','ok'); }
    catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }
    finally{ setOcupado(''); }
  }
  const mudarQ=(i:number,p:Partial<Sinc['quadros'][number]>)=>{ if(!sinc) return; const qs=sinc.quadros.map((q,k)=>k===i?{...q,...p}:q); setSinc(p.dur!=null?reencadear({...sinc,quadros:qs}):{...sinc,quadros:qs}); };
  const mudarSom=(i:number,j:number,p:Partial<Sinc['quadros'][number]['sons'][number]>)=>{ if(!sinc) return; mudarQ(i,{sons:sinc.quadros[i].sons.map((s,k)=>k===j?{...s,...p}:s)}); };
  const imgs=arqs.filter(a=>a.tipo==='quadro'), efs=arqs.filter(a=>a.tipo==='efeito');
  const nome=(id:string)=>arqs.find(a=>a.id===id)?.nome||'';
  const resumo=`${quadros.length} quadros • ${quadros.reduce((a,q)=>a+q.falas.length,0)} falas • ${quadros.reduce((a,q)=>a+q.sons.length,0)} efeitos • ${quadros.filter(q=>q.trilha).length} marcações de trilha`;

  return <div className="manual">
   <section className="panel">
    <div className="section-head"><h2><FileText size={18}/> 1. Roteiro de quadros</h2><button className="subtle sm" onClick={()=>setTexto(t=>t.trim()?t:MODELO_ROTEIRO)} disabled={!!texto.trim()}>Usar modelo</button></div>
    <p className="hint">Um bloco por quadro, começando com <b>QUADRO 1</b>. Dentro: <b>VISUAL:</b> o que aparece, falas <b>NOME: texto</b>, <b>[SOM: porta batendo]</b> (com <b>@1.5</b> para tocar 1,5 s depois do início do quadro), <b>[TRILHA: tensa]</b>, <b>MOVIMENTO: aproximar</b> e, se quiser, o tempo no título: <b>QUADRO 2 (0:04–0:09)</b> ou <b>(4 s)</b>. Sem tempo, o site calcula pela narração, pelos vídeos ou pela duração padrão.</p>
    <textarea className="roteiro-quadros" rows={12} value={texto} onChange={e=>setTexto(e.target.value)} placeholder={MODELO_ROTEIRO} aria-label="Roteiro de quadros"/>
    {quadros.length>0&&<p className="hint">Li: <b>{resumo}</b></p>}
   </section>

   <section className="panel">
    <div className="section-head"><h2><ImagePlus size={18}/> 2. Arquivos</h2></div>
    {!carregado&&<p className="hint"><Loader2 size={14} className="spin"/> Abrindo os arquivos guardados...</p>}
    <div className="manual-areas">{AREAS.map(([tipo,tit,acc,dica,I])=>{ const l=arqs.filter(a=>a.tipo===tipo); return <div key={tipo} className="manual-area">
     <div className="manual-area-top"><b><I size={15}/> {tit}</b>{l.length>0&&<button className="link-btn" onClick={()=>limpar(tipo)}>Tirar todos</button>}</div>
     <small className="hint">{dica}</small>
     <label className="subtle sm vc-upload mt">Enviar<input type="file" accept={acc} multiple hidden data-area={tipo} onChange={e=>{ enviar(tipo,e.target.files); e.target.value=''; }}/></label>
     {l.length>0&&<ul className="manual-lista">{l.map(a=><li key={a.id}>{a.tipo==='quadro'&&midias.get(a.id)?.tipo==='imagem'?<img src={(midias.get(a.id)!.el as HTMLImageElement).src} alt=""/>:null}<span title={a.nome}>{a.nome}</span><small>{a.duracao?fmt(a.duracao):''}</small><button className="icon-btn" onClick={()=>remover(a)} aria-label={'Tirar '+a.nome}><Trash2 size={13}/></button></li>)}</ul>}
    </div>; })}</div>
   </section>

   <section className="panel">
    <div className="section-head"><h2><Wand2 size={18}/> 3. Analisar e sincronizar</h2></div>
    <div className="small-grid">
     <label>Formato<select value={o.formato} onChange={e=>setO({...o,formato:e.target.value as Formato})}><option value="9:16">Vertical 9:16 (Reels, TikTok, Shorts)</option><option value="16:9">Horizontal 16:9 (YouTube)</option><option value="1:1">Quadrado 1:1</option></select></label>
     <label>Duração padrão do quadro (s)<input type="number" min={0.5} max={60} step={0.5} value={o.durPadrao} onChange={e=>setO({...o,durPadrao:Math.max(0.5,+e.target.value||3)})}/></label>
     <label>Transição<select value={o.transicao} onChange={e=>setO({...o,transicao:e.target.value as Opcoes['transicao']})}><option value="fade">Suave (0,4 s)</option><option value="corte">Corte seco</option></select></label>
     <label>Volume da trilha (%)<input type="number" min={0} max={100} step={5} value={o.volTrilha} onChange={e=>setO({...o,volTrilha:Math.max(0,Math.min(100,+e.target.value||0))})}/></label>
     <label>Volume dos efeitos (%)<input type="number" min={0} max={200} step={5} value={o.volEfeitos} onChange={e=>setO({...o,volEfeitos:Math.max(0,Math.min(200,+e.target.value||0))})}/></label>
    </div>
    <div className="row-gap left mt">
     <label className="check"><input type="checkbox" checked={o.legendas} onChange={e=>setO({...o,legendas:e.target.checked})}/> Legenda com as falas</label>
     <label className="check"><input type="checkbox" checked={o.naBatida} onChange={e=>setO({...o,naBatida:e.target.checked})}/> Cortar na batida da música (quando não há narração)</label>
     <label className="check"><input type="checkbox" checked={usarIA} onChange={e=>setUsarIA(e.target.checked)}/> <Sparkles size={13}/> IA confere qual imagem é de cada quadro (Gemini)</label>
    </div>
    <button className="primary lg mt" disabled={!!ocupado||!quadros.length} onClick={analisar}>{ocupado?<Loader2 size={17} className="spin"/>:<Wand2 size={17}/>} Analisar e sincronizar</button>
    {ocupado&&<p className="hint mt"><Loader2 size={14} className="spin"/> {ocupado}</p>}
    {sinc&&sinc.notas.length>0&&<ul className="manual-notas">{sinc.notas.map(n=><li key={n}>{n}</li>)}</ul>}
   </section>

   {sinc&&<section className="panel">
    <div className="section-head"><h2><Clapperboard size={18}/> 4. Linha do tempo e vídeo</h2><span className="hint">{sinc.quadros.length} quadros • {fmt(sinc.total)}{sinc.narracao!=='nenhuma'?` • narração ${sinc.narracao==='unica'?'em um arquivo':'por quadro'}`:''}{sinc.trilhas.length?` • ${sinc.trilhas.length} trilha(s)`:''}</span></div>
    <div className="manual-player">
     <canvas ref={cv} className={'manual-canvas f'+o.formato.replace(':','x')}/>
     <div className="manual-ctl">
      <input type="range" min={0} max={sinc.total} step={0.05} value={Math.min(tempo,sinc.total)} onChange={e=>{ parar(); setTempo(+e.target.value); }} aria-label="Posição"/>
      <span className="hint">{fmt(tempo)} / {fmt(sinc.total)}</span>
      <div className="row-gap left">
       {tocando?<button className="subtle" onClick={parar}><Square size={15}/> Parar</button>:<button className="subtle" disabled={!!ocupado} onClick={()=>previa(tempo>=sinc.total-0.1?0:tempo)}><Play size={15}/> Prévia com som</button>}
       <button className="primary" disabled={!!ocupado} onClick={gerarVideo}><Clapperboard size={15}/> Gerar vídeo</button>
      </div>
      {video&&<div className="final-ok mt"><video src={video.url} controls className="manual-video"/><button className="primary mt" onClick={()=>baixar(video.blob,`montagem-${o.formato.replace(':','x')}.${video.ext}`)}><Download size={15}/> Baixar vídeo ({video.ext.toUpperCase()})</button></div>}
     </div>
    </div>
    <div className="manual-quadros">{sinc.quadros.map((q,i)=>{ const m=q.midia?midias.get(q.midia):undefined; const ativo=tempo>=q.ini&&tempo<q.ini+q.dur;
     return <article key={i} className={'manual-q'+(ativo?' on':'')}>
      <button className="manual-thumb" onClick={()=>{ parar(); setTempo(q.ini+Math.min(0.5,q.dur/2)); }} title="Ver este quadro">{m?.tipo==='imagem'?<img src={(m.el as HTMLImageElement).src} alt=""/>:m?<span>vídeo</span>:<span>sem imagem</span>}</button>
      <div className="manual-q-info">
       <b>Quadro {q.n}{q.titulo?` — ${q.titulo}`:''}</b>
       <small>{fmt(q.ini)} – {fmt(q.ini+q.dur)}{q.visual?` • ${q.visual.slice(0,90)}`:''}</small>
       <div className="manual-q-ctl">
        <label className="manual-num">Dura<input type="number" min={0.3} max={120} step={0.1} value={+q.dur.toFixed(2)} onChange={e=>mudarQ(i,{dur:Math.max(0.3,+e.target.value||0.3)})} aria-label={`Duração do quadro ${q.n}`}/>s</label>
        <select value={q.midia} onChange={e=>mudarQ(i,{midia:e.target.value})} aria-label={`Imagem do quadro ${q.n}`}><option value="">Sem imagem</option>{imgs.map(a=><option key={a.id} value={a.id}>{a.nome}</option>)}</select>
        <select value={q.anim} onChange={e=>mudarQ(i,{anim:e.target.value as Anim})} aria-label={`Movimento do quadro ${q.n}`}>{ANIMS.map(([k,n])=><option key={k} value={k}>{n}</option>)}</select>
        <button className="link-btn" onClick={()=>previa(q.ini)} disabled={!!ocupado}>▶ tocar daqui</button>
       </div>
       {q.legenda.length>0&&<small className="manual-fala">“{q.legenda.map(l=>l.texto).join(' ')}”</small>}
       {q.sons.map((s,j)=><div key={j} className="manual-som"><Volume2 size={13}/><span>{s.desc}</span>
        <select value={s.arquivo} onChange={e=>mudarSom(i,j,{arquivo:e.target.value})} aria-label={`Arquivo do som ${s.desc}`}><option value="">Feito pelo site</option>{efs.map(a=><option key={a.id} value={a.id}>{a.nome}</option>)}</select>
        <label className="manual-num">aos<input type="number" min={0} step={0.1} value={s.em} onChange={e=>mudarSom(i,j,{em:Math.max(0,+e.target.value||0)})}/>s</label>
        <label className="manual-num">vol<input type="number" min={0} max={200} step={5} value={s.vol} onChange={e=>mudarSom(i,j,{vol:Math.max(0,+e.target.value||0)})}/>%</label>
       </div>)}
      </div>
     </article>; })}</div>
    {sinc.trilhas.length>0&&<p className="hint mt">Trilha: {sinc.trilhas.map(t=>`${nome(t.arquivo)} (${fmt(t.ini)}–${fmt(t.fim)})`).join(' • ')}</p>}
   </section>}

   {sinc&&<section className="panel">
    <div className="section-head"><h2><SlidersHorizontal size={18}/> 5. Editor (linha do tempo)</h2>
     {proj?<button className="subtle sm" onClick={abrirEditor} title="Joga fora a edição e começa de novo pela sincronização"><RotateCcw size={14}/> Recomeçar pela sincronização</button>:null}</div>
    {!proj?<><p className="hint">Abre o vídeo sincronizado numa linha do tempo com faixas de vídeo, texto, narração, trilha e efeitos. Lá você arrasta, corta, divide, coloca efeitos sonoros prontos, textos e ajusta cada parte do jeito que quiser.</p>
     <button className="primary lg" onClick={abrirEditor}><SlidersHorizontal size={17}/> Abrir no editor</button></>
    :carregado&&<EditorVideo key={versao} inicial={proj} arquivos={arqs} onChange={n=>{ setProj(n); salvarProj(n); }}/>}
   </section>}
  </div>;
}
