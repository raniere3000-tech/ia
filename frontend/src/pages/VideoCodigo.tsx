import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDown, ArrowUp, CalendarClock, Copy, Download, FileText, ImagePlus, Loader2, Mic, Music, Play, Plus, Sparkles, Square, Trash2, Wand2, X } from 'lucide-react';
import { listar, lerRoteiro, pedidoTTS, gerarVoz as gerarVozTTS, lerWav, vozDoNome, VOZES_TTS, type Personagem, type Projeto as ProjetoVoz } from '../lib/vozes';
import { falar } from '../lib/dublagem';
import { useApp } from '../state';
import { store } from '../lib/store';
import { iaAtiva, nomeIA } from '../lib/ia';
import { VOZES } from '../lib/dublagem';
import { loadImage } from '../lib/render';
import { baixar } from '../lib/exporter';
import AgendarPost from '../components/AgendarPost';
import {
  EXEMPLO, FORMATOS, TEMAS, W, H, cenaVazia, desenhar, gravar, mixar, narrar, nomeVideo, roteiroClaude, roteiroGemini, tempos, tocar, vozValida,
  ANIMS, MAX_SEG, adicionarMidia, carregarMidias, midias, sincronizarMidias,
  type Anim, type Cena, type FalarCena, type Formato, type Narracao, type Roteiro, type Sessao,
} from '../lib/videoCodigo';

const CHAVE = 'studio_video_codigo';
type Ajustes = {ideia:string;formato:Formato;cenas:number;voz:string;comVoz:boolean;batida:boolean;elenco:string};
const AJUSTES:Ajustes = {ideia:'',formato:'curiosidade',cenas:6,voz:'Puck',comVoz:true,batida:true,elenco:''};
const fmt = (s:number)=>`${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}`;

export default function VideoCodigo(){
  const {settings,toast,go,template}=useApp();
  const salvo = store.json<{roteiro?:Roteiro;ajustes?:Partial<Ajustes>}>(CHAVE,{});
  const [aj,setAj]=useState<Ajustes>({...AJUSTES,...salvo.ajustes});
  const [rot,setRot]=useState<Roteiro|null>(salvo.roteiro||null);
  const [nar,setNar]=useState<Narracao|null>(null);
  const [ocupado,setOcupado]=useState<{txt:string;pct:number}|null>(null);
  const [tocando,setTocando]=useState(false); const [tempo,setTempo]=useState(0);
  const [agendar,setAgendar]=useState(false);
  const canvas=useRef<HTMLCanvasElement>(null); const sessao=useRef<Sessao|null>(null);
  const ia=iaAtiva(settings);
  // Personagens do Estúdio de vozes (para cada cena falar com a voz do seu personagem).
  const [projVoz,setProjVoz]=useState<ProjetoVoz[]>([]); const [todosPers,setTodosPers]=useState<Personagem[]>([]);
  useEffect(()=>{ Promise.all([listar<ProjetoVoz>('projetos'),listar<Personagem>('personagens')]).then(([p,e])=>{ setProjVoz(p.sort((a,b)=>a.criado-b.criado)); setTodosPers(e); }).catch(()=>{}); },[]);
  const elencoProj=aj.elenco||projVoz[0]?.id||'';
  const elenco=todosPers.filter(p=>p.projetoId===elencoProj);
  const [colado,setColado]=useState(''); const [versao,setVersao]=useState(0);
  // Imagens e vídeos das cenas ficam no navegador; ao abrir a aba, carrega os do roteiro.
  useEffect(()=>{ if(rot) carregarMidias(rot).then(()=>setVersao(v=>v+1)); },[rot?.cenas.map(c=>c.midia).join()]); // eslint-disable-line react-hooks/exhaustive-deps
  const falarCena:FalarCena=async(c,espera)=>{
    const nome=c.personagem?.trim();
    if(nome){
      const p=elenco.find(x=>x.nome.trim().toUpperCase()===nome.toUpperCase());
      if(p){ const {wav}=await gerarVozTTS(settings.geminiKey,p.modelo,p.voz,pedidoTTS(p,c.texto,''),espera); return lerWav(wav); }
      const v=vozDoNome(nome); if(v) return falar(settings.geminiKey,c.texto,v,espera);
    }
    return falar(settings.geminiKey,c.texto,aj.voz,espera);
  };
  function cenasDoRoteiro(){
    const l=lerRoteiro(colado).filter(x=>x.tipo==='fala');
    if(!l.length){ toast('Não achei falas. Use uma por linha: NOME: texto.','erro'); return; }
    parar(); const base=rot||{titulo:aj.ideia||'Meu vídeo',selo:'',formato:'livre' as Formato,tema:'neon' as const,cenas:[],legenda:'',hashtags:[]};
    setRot({...base,cenas:l.map(x=>cenaVazia({texto:x.texto,personagem:x.nome==='NARRADOR'&&!elenco.some(p=>p.nome.toUpperCase()==='NARRADOR')?'':x.nome}))}); setNar(null); setTempo(0);
    const nomes=[...new Set(l.map(x=>x.nome))]; const sem=nomes.filter(n=>n!=='NARRADOR'&&!elenco.some(p=>p.nome.toUpperCase()===n)&&!vozDoNome(n));
    toast(`${l.length} cenas criadas.${sem.length?` Sem voz própria (vão usar a voz padrão): ${sem.join(', ')}.`:''}`,sem.length?'info':'ok');
  }
  async function enviarMidia(c:Cena,f:File|undefined){
    if(!f) return;
    setOcupado({txt:'Guardando '+f.name,pct:50});
    try{ const id=await adicionarMidia(f); mudaCena(c.id,{midia:id,anim:c.anim||(f.type.startsWith('video/')?'parado':'zoom-in')}); setVersao(v=>v+1); }
    catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }
    finally{ setOcupado(null); }
  }

  useEffect(()=>{ store.setJson(CHAVE,{roteiro:rot,ajustes:aj}); },[rot,aj]);
  useEffect(()=>()=>sessao.current?.parar(),[]);
  const ts=useMemo(()=>rot?tempos(rot,aj.comVoz?nar:null,aj.voz):[],[rot,nar,aj.comVoz,aj.voz]);
  const total=ts.length?ts[ts.length-1].fim:0;
  const logo=useRef<HTMLImageElement|null>(null);
  useEffect(()=>{ let vivo=true; loadImage(template.ativo?template.logo:'').then(i=>{ if(vivo) logo.current=i; }); return ()=>{ vivo=false; }; },[template]);
  // Quadro parado quando não está tocando.
  useEffect(()=>{ if(tocando||!rot||!canvas.current) return; const c=canvas.current.getContext('2d')!; const t=Math.min(tempo,Math.max(0,total-0.01))||Math.min(1.2,total*0.1); sincronizarMidias(rot,ts,t,false); desenhar(c,rot,ts,t,template,logo.current); const r=setTimeout(()=>desenhar(c,rot,ts,t,template,logo.current),250); return ()=>clearTimeout(r); },[rot,ts,tocando,tempo,total,template,versao]);

  const muda=(p:Partial<Ajustes>)=>setAj(a=>({...a,...p}));
  const mudaRot=(p:Partial<Roteiro>)=>setRot(r=>r?{...r,...p}:r);
  const mudaCena=(id:string,p:Partial<Cena>)=>setRot(r=>r?{...r,cenas:r.cenas.map(c=>c.id===id?{...c,...p}:c)}:r);
  const moveCena=(i:number,d:number)=>setRot(r=>{ if(!r) return r; const cs=[...r.cenas]; const j=i+d; if(j<0||j>=cs.length) return r; [cs[i],cs[j]]=[cs[j],cs[i]]; return {...r,cenas:cs}; });
  const parar=()=>{ sessao.current?.parar(); sessao.current=null; setTocando(false); };

  async function criar(){
    if(!aj.ideia.trim()){ toast('Escreva o tema do vídeo primeiro.','erro'); return; }
    if(!ia){ toast('Cole a chave do Gemini ou da Claude em Chaves e ajustes para a IA escrever o roteiro.','erro'); return; }
    parar(); setOcupado({txt:`${nomeIA(ia)} escrevendo o roteiro`,pct:30});
    try{
      const p={ideia:aj.ideia.trim(),formato:aj.formato,cenas:aj.cenas}; const tema=rot?.tema||'neon';
      const r=ia==='gemini'?await roteiroGemini(settings.geminiKey,p,tema):await roteiroClaude(settings.claudeKey,p,tema);
      setRot(r); setNar(null); setTempo(0); toast('Roteiro pronto! Confira as cenas e toque em Assistir.','ok');
    }catch(e){ const {erroIA}=await import('../lib/ia'); toast(await erroIA(settings,e),'erro'); }
    finally{ setOcupado(null); }
  }
  async function gerarVoz(){
    if(!rot) return;
    if(!settings.geminiKey){ toast('A narração usa a voz do Gemini. Cole a chave do Gemini em Chaves e ajustes.','erro'); return; }
    parar(); setOcupado({txt:'Gravando a voz',pct:0});
    try{ const n=await narrar(settings.geminiKey,rot,aj.voz,nar||{},(txt,pct)=>setOcupado({txt,pct}),falarCena); setNar(n); muda({comVoz:true}); toast('Narração pronta. Toque em Assistir.','ok'); }
    catch(e){ const {erroGemini}=await import('../lib/gemini'); toast(erroGemini(e),'erro'); }
    finally{ setOcupado(null); }
  }
  async function assistir(){
    if(!rot||!canvas.current) return;
    if(tocando){ parar(); return; }
    const audio=await mixar(rot,aj.comVoz?nar:null,aj.voz,aj.batida);
    setTocando(true);
    const s=tocar(canvas.current,rot,ts,audio,{template,logo:logo.current,onTempo:setTempo});
    sessao.current=s; s.fim.then(()=>{ if(sessao.current===s){ sessao.current=null; setTocando(false); setTempo(0); } });
  }
  async function exportar(onPct:(p:number)=>void){
    if(!rot) throw new Error('Crie o roteiro primeiro.');
    parar();
    const audio=await mixar(rot,aj.comVoz?nar:null,aj.voz,aj.batida);
    const {blob,ext}=await gravar(rot,ts,audio,template,logo.current,onPct);
    return {blob,nome:nomeVideo(rot,ext)};
  }
  async function baixarVideo(){
    if(total>MAX_SEG+0.5){ toast(`O vídeo tem ${fmt(total)}. O máximo é 2:00: tire ou encurte cenas.`,'erro'); return; }
    setOcupado({txt:'Gravando o vídeo (deixe esta aba aberta)',pct:0});
    try{ const {blob,nome}=await exportar(p=>setOcupado({txt:'Gravando o vídeo (deixe esta aba aberta)',pct:p})); baixar(blob,nome); toast('Vídeo baixado!','ok'); }
    catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }
    finally{ setOcupado(null); }
  }

  const textoPost=rot?[rot.legenda,rot.hashtags.join(' ')].filter(Boolean).join('\n\n'):'';
  const semVoz=rot&&aj.comVoz?rot.cenas.filter(c=>!vozValida(nar,c,aj.voz)).length:0;

  return <>
   <div className="two-cols vc">
    <div>
     <section className="panel">
      <div className="section-head"><h2>1. Ideia do vídeo</h2></div>
      <label>Sobre o que é o vídeo?<textarea rows={3} value={aj.ideia} onChange={e=>muda({ideia:e.target.value})} placeholder="Ex.: curiosidades sobre o espaço, 5 erros que fazem você perder dinheiro, quiz de futebol..."/></label>
      <div className="field-label mt">Formato</div>
      <div className="chips">{FORMATOS.map(f=><button key={f.id} className={'chip'+(aj.formato===f.id?' on':'')} onClick={()=>muda({formato:f.id})} title={f.dica}>{f.nome}</button>)}</div>
      <label>Tamanho<select value={aj.cenas} onChange={e=>muda({cenas:+e.target.value})}><option value={4}>Curto (uns 15 segundos, 4 cenas)</option><option value={6}>Médio (uns 25 segundos, 6 cenas)</option><option value={8}>Longo (uns 35 segundos, 8 cenas)</option><option value={10}>Bem longo (uns 45 segundos, 10 cenas)</option><option value={16}>Até 1 minuto e meio (16 cenas)</option><option value={20}>Até 2 minutos (20 cenas)</option></select></label>
      <div className="row-gap left mt">
       <button className="primary" onClick={criar} disabled={!!ocupado}>{ocupado?<Loader2 size={15} className="spin"/>:<Sparkles size={15}/>} Criar roteiro com IA</button>
       <button className="subtle" onClick={()=>{ parar(); setRot({...EXEMPLO,cenas:EXEMPLO.cenas.map(c=>({...c}))}); setNar(null); setTempo(0); }} disabled={!!ocupado}><Wand2 size={15}/> Ver exemplo</button>
       <button className="subtle" onClick={()=>{ parar(); setRot({titulo:aj.ideia||'Meu vídeo',selo:FORMATOS.find(f=>f.id===aj.formato)!.selo,formato:aj.formato,tema:rot?.tema||'neon',cenas:[cenaVazia({texto:'Escreva aqui a primeira frase'})],legenda:'',hashtags:[]}); setNar(null); }} disabled={!!ocupado}><Plus size={15}/> Escrever eu mesmo</button>
      </div>
      {!ia&&<p className="hint">Para a IA escrever, cole a chave do Gemini (grátis) ou da Claude em <button className="link-btn" onClick={()=>go('config')}>Chaves e ajustes</button>. Sem chave, use "Escrever eu mesmo".</p>}
     </section>

     <section className="panel">
      <div className="section-head"><h2><FileText size={18}/> Ou cole o seu roteiro com personagens</h2></div>
      <p className="hint">Uma fala por linha: <code>NOME: texto</code>. Cada fala vira uma cena e é dita pela voz daquele personagem: se o nome for igual a um personagem do <button className="link-btn inline" onClick={()=>go('vozes')}>Estúdio de vozes</button>, usa a ficha dele; se for igual a uma voz do Gemini (ex.: CHARON), usa essa voz; NARRADOR ou sem nome usa a voz padrão. Depois coloque imagem ou vídeo em cada cena.</p>
      <textarea rows={5} value={colado} onChange={e=>setColado(e.target.value)} placeholder={'NARRADOR: Era uma noite tranquila na taverna.\nTHORGAR: Você tem ideia do que acabou de fazer?!\nCHARON: O destino está em jogo.'} aria-label="Roteiro com personagens"/>
      <button className="primary mt" disabled={!colado.trim()||!!ocupado} onClick={cenasDoRoteiro}><Wand2 size={15}/> Criar cenas do roteiro</button>
     </section>

     {rot&&<section className="panel">
      <div className="section-head"><h2>2. Roteiro <span className="count">{rot.cenas.length}</span></h2><span>Toque nos textos para mudar</span></div>
      <div className="vc-linha"><label>Título do post<input value={rot.titulo} maxLength={100} onChange={e=>mudaRot({titulo:e.target.value})}/></label><label>Selo do topo<input value={rot.selo} maxLength={24} onChange={e=>mudaRot({selo:e.target.value.toUpperCase()})} placeholder="Ex.: VOCÊ SABIA?"/></label></div>
      <div className="vc-cenas">{rot.cenas.map((c,i)=><div key={c.id} className="vc-cena">
        <div className="vc-cena-head"><strong>{i===0?'Cena 1 (gancho)':`Cena ${i+1}`}</strong><small>{ts[i]?`${(ts[i].fim-ts[i].ini).toFixed(1)} s`:''}{aj.comVoz&&nar&&!vozValida(nar,c,aj.voz)?' • sem voz':''}</small>
         <span><button className="icon-btn" onClick={()=>moveCena(i,-1)} disabled={i===0} aria-label="Subir"><ArrowUp size={14}/></button><button className="icon-btn" onClick={()=>moveCena(i,1)} disabled={i===rot.cenas.length-1} aria-label="Descer"><ArrowDown size={14}/></button><button className="icon-btn" onClick={()=>setRot(r=>r&&r.cenas.length>1?{...r,cenas:r.cenas.filter(x=>x.id!==c.id)}:r)} aria-label="Apagar cena"><Trash2 size={14}/></button></span></div>
        <div className="vc-cena-campos">
         <input className="vc-emoji" value={c.emoji} maxLength={8} onChange={e=>mudaCena(c.id,{emoji:e.target.value})} placeholder="🙂" aria-label="Emoji"/>
         <textarea rows={2} value={c.texto} onChange={e=>mudaCena(c.id,{texto:e.target.value})} aria-label="Texto da cena"/>
        </div>
        <div className="vc-linha"><label>Palavra em destaque<input value={c.destaque} onChange={e=>mudaCena(c.id,{destaque:e.target.value})} placeholder="pintada de cor"/></label><label>Número<input value={c.numero} maxLength={4} onChange={e=>mudaCena(c.id,{numero:e.target.value})} placeholder="#1"/></label></div>
        <div className="vc-linha"><label>Quem fala<input list="vc-quem" value={c.personagem||''} onChange={e=>mudaCena(c.id,{personagem:e.target.value})} placeholder="Voz padrão"/></label>
         <label>Movimento da imagem<select value={c.anim||'zoom-in'} disabled={!c.midia} onChange={e=>mudaCena(c.id,{anim:e.target.value as Anim})}>{ANIMS.map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label></div>
        <div className="vc-midia">{c.midia&&midias.get(c.midia)?<><span className="tag ok">{midias.get(c.midia)!.tipo==='video'?'🎬':'🖼️'} {midias.get(c.midia)!.nome}{midias.get(c.midia)!.tipo==='video'?` • ${Math.round(midias.get(c.midia)!.duracao)} s`:''}</span><button className="icon-btn" onClick={()=>mudaCena(c.id,{midia:undefined})} aria-label="Tirar imagem"><X size={14}/></button></>:c.midia?<small className="hint">Carregando a imagem...</small>:null}
         <label className="subtle sm vc-upload"><ImagePlus size={14}/> {c.midia?'Trocar':'Imagem ou vídeo'}<input type="file" accept="image/*,video/*" hidden onChange={e=>{ enviarMidia(c,e.target.files?.[0]); e.target.value=''; }}/></label></div>
        <label className="vc-check"><input type="checkbox" checked={c.contagem} onChange={e=>mudaCena(c.id,{contagem:e.target.checked})}/> Contagem regressiva (pergunta de quiz)</label>
      </div>)}</div>
      <datalist id="vc-quem">{elenco.map(p=><option key={p.id} value={p.nome}/>)}{VOZES_TTS.map(([v])=><option key={v} value={v.toUpperCase()}/>)}</datalist>
      <button className="subtle mt" onClick={()=>setRot(r=>r?{...r,cenas:[...r.cenas,cenaVazia({texto:'Nova cena'})]}:r)}><Plus size={15}/> Adicionar cena</button>
     </section>}

     {rot&&<section className="panel">
      <div className="section-head"><h2>3. Visual e som</h2></div>
      <div className="field-label">Cores</div>
      <div className="vc-temas">{TEMAS.map(t=><button key={t.id} className={'vc-tema'+(rot.tema===t.id?' on':'')} onClick={()=>mudaRot({tema:t.id})} style={{background:`linear-gradient(160deg,${t.bg[0]},${t.bg[1]})`,color:t.texto}}><i style={{background:t.acento}}/><i style={{background:t.acento2}}/>{t.nome}</button>)}</div>
      <label className="vc-check mt"><input type="checkbox" checked={aj.comVoz} onChange={e=>muda({comVoz:e.target.checked})}/> <Mic size={14}/> Narração (voz do Gemini)</label>
      {aj.comVoz&&<div className="row-gap left mt">
       <select value={aj.voz} onChange={e=>muda({voz:e.target.value})} aria-label="Voz">{VOZES.map(([id,n])=><option key={id} value={id}>{n} ({id})</option>)}</select>
       <button className="primary" onClick={gerarVoz} disabled={!!ocupado}>{ocupado?<Loader2 size={15} className="spin"/>:<Mic size={15}/>} {nar&&!semVoz?'Voz pronta':semVoz<rot.cenas.length?`Gravar voz (${semVoz} cenas)`:'Gravar voz'}</button>
      </div>}
      {aj.comVoz&&<label className="mt">Vozes dos personagens (projeto do Estúdio de vozes)<select value={elencoProj} onChange={e=>muda({elenco:e.target.value})}>{!projVoz.length&&<option value="">Nenhum projeto ainda</option>}{projVoz.map(p=><option key={p.id} value={p.id}>{p.nome} ({todosPers.filter(x=>x.projetoId===p.id).length} personagens)</option>)}</select></label>}
      {aj.comVoz&&rot.cenas.some(c=>c.personagem?.trim())&&<p className="hint">A voz escolhida acima é a padrão (narrador e cenas sem personagem). As cenas com "Quem fala" usam a voz do personagem.</p>}
      {aj.comVoz&&semVoz>0&&<p className="hint">{nar?'Algumas cenas mudaram depois da voz. Toque em Gravar voz para atualizar só elas.':'Toque em Gravar voz. Sem voz, cada cena fica na tela pelo tempo de leitura.'}</p>}
      <label className="vc-check mt"><input type="checkbox" checked={aj.batida} onChange={e=>muda({batida:e.target.checked})}/> <Music size={14}/> Batida de fundo (criada pelo site, sem direitos autorais)</label>
      {template.ativo&&<p className="hint">O seu template da marca (logo e crédito) entra no vídeo.</p>}
     </section>}
    </div>

    <div className="vc-lado">
     <section className="panel">
      <div className="section-head"><h2>Prévia</h2>{rot&&<span>{fmt(tocando?tempo:0)} / {fmt(total)}</span>}</div>
      {rot?<canvas ref={canvas} width={W} height={H} className="vc-canvas" onClick={assistir}/>:<div className="empty-state vc-vazio"><Sparkles size={28}/><p>Escreva um tema e toque em <b>Criar roteiro com IA</b>, ou veja o exemplo.</p></div>}
      {ocupado&&<div className="export-bar mt"><Loader2 size={15} className="spin"/><span>{ocupado.txt}</span><b>{ocupado.pct?ocupado.pct+'%':''}</b><div className="progress"><div style={{width:ocupado.pct+'%'}}/></div></div>}
      {rot&&<div className="vc-acoes">
       <button className="primary" onClick={assistir} disabled={!!ocupado}>{tocando?<><Square size={15}/> Parar</>:<><Play size={15}/> Assistir</>}</button>
       <button className="subtle" onClick={baixarVideo} disabled={!!ocupado}><Download size={15}/> Baixar vídeo</button>
       <button className="subtle" onClick={()=>{ parar(); setAgendar(true); }} disabled={!!ocupado}><CalendarClock size={15}/> Agendar post</button>
      </div>}
      {rot&&total>MAX_SEG+0.5&&<p className="hint erro">O vídeo está com {fmt(total)}. O máximo é 2:00: tire ou encurte cenas para baixar.</p>}
      {rot&&<p className="hint">O vídeo é gravado em tempo real ({fmt(total)}). Deixe a aba aberta enquanto grava.</p>}
     </section>
     {rot&&<section className="panel">
      <div className="section-head"><h2>Legenda do post</h2><button className="icon-btn" onClick={()=>{ navigator.clipboard?.writeText(textoPost).then(()=>toast('Legenda copiada.','ok'),()=>toast('Não consegui copiar.','erro')); }} aria-label="Copiar legenda"><Copy size={15}/></button></div>
      <textarea rows={4} value={rot.legenda} onChange={e=>mudaRot({legenda:e.target.value})} placeholder="Legenda do post"/>
      <input className="mt" value={rot.hashtags.join(' ')} onChange={e=>mudaRot({hashtags:e.target.value.split(/\s+/).filter(Boolean)})} placeholder="#hashtags"/>
     </section>}
    </div>
   </div>
   {agendar&&rot&&<AgendarPost titulo={rot.titulo} legenda={textoPost} gerar={exportar} onClose={()=>setAgendar(false)}/>}
  </>;
}
