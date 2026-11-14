import { useEffect, useMemo, useRef, useState } from 'react';
import { Bot, Copy, Film, ImagePlus, LayoutTemplate, Plus, Server, Trash2, CheckCircle2, AlertTriangle } from 'lucide-react';
import { useApp, captionPresets } from '../state';
import { drawFrame, loadImage, DIMS } from '../lib/render';
import { TARJA_PADRAO, type Formato, type Tarja } from '../lib/analyze';
import { EFEITOS_MODELO, LAYOUTS, QUALIDADES, marcaDe, novoModelo, visualDe, type Modelo, type Qualidade } from '../lib/modelos';
import { verAgente, salvarAgente } from '../lib/agente';
import type { Regiao } from '../lib/render';

const MAX_AGENTE=3;
const CANTOS:[string,Regiao][] = [['Canto inferior direito',{x:0.72,y:0.62,w:0.28,h:0.38}],['Canto inferior esquerdo',{x:0,y:0.62,w:0.28,h:0.38}],['Canto superior direito',{x:0.72,y:0,w:0.28,h:0.38}],['Canto superior esquerdo',{x:0,y:0,w:0.28,h:0.38}]];

/** Quadro de exemplo: um "gameplay" com a câmera do streamer no lugar marcado, para a divisão aparecer na prévia. */
function quadroFalso(m:Modelo){
  const f=document.createElement('canvas'); f.width=1280; f.height=720; const c=f.getContext('2d')!;
  const g=c.createLinearGradient(0,0,1280,720); g.addColorStop(0,'#3b4a7a'); g.addColorStop(1,'#1c2033'); c.fillStyle=g; c.fillRect(0,0,1280,720);
  c.fillStyle='#ffffff18'; for(let i=0;i<6;i++){ c.fillRect(80+i*200,120+((i*97)%300),140,90); }
  c.fillStyle='#fff9'; c.font='700 64px sans-serif'; c.textAlign='center'; c.textBaseline='middle';
  c.fillText(m.layout==='gameplay-streamer'?'GAMEPLAY':'SEU VÍDEO',640*(m.layout==='gameplay-streamer'?0.8:1),330);
  if(m.layout==='gameplay-streamer'){
    const r=m.camera, x=r.x*1280, y=r.y*720, w=r.w*1280, h=r.h*720;
    c.fillStyle='#a8456b'; c.fillRect(x,y,w,h); c.fillStyle='#ffd9c2'; c.beginPath(); c.arc(x+w/2,y+h*0.45,Math.min(w,h)*0.24,0,Math.PI*2); c.fill();
    c.fillStyle='#fff'; c.font='700 26px sans-serif'; c.fillText('CÂMERA',x+w/2,y+h*0.88);
  }
  Object.assign(f,{videoWidth:1280,videoHeight:720});
  return f as unknown as HTMLVideoElement;
}

/** Prévia do template, desenhada pelo mesmo código que monta a prévia do editor e o vídeo exportado. */
export function PreviaModelo({m,video}:{m:Modelo;video?:HTMLVideoElement|null}){
  const ref=useRef<HTMLCanvasElement>(null);
  const [W,H]=DIMS[m.formato];
  useEffect(()=>{ let vivo=true; (async()=>{
    const cv=ref.current; if(!cv) return;
    const marca=marcaDe(m); const logo=await loadImage(marca.logo); if(!vivo) return;
    let legenda=captionPresets.find(p=>p.id===m.legenda)||null;
    if(legenda) legenda={...legenda,position:m.legendaPos==='meio'?'center':legenda.position==='center'?'center-bottom':legenda.position};
    drawFrame(cv.getContext('2d')!,video||quadroFalso(m),document.createElement('canvas'),1.2,10,{legenda,efeito:m.efeito,cues:[{start:0,end:4,text:'É assim que a legenda aparece'}],gancho:'Seu gancho aqui',accent:legenda?.highlightColor||m.cor,template:marca,logoImg:logo,tarja:m.tarja,visual:visualDe(m)},W,H);
  })(); return ()=>{ vivo=false; }; },[m,video,W,H]);
  return <canvas ref={ref} width={W} height={H} className={'preview-canvas f'+m.formato.replace(':','x')} aria-label={'Prévia do template '+m.nome}/>;
}

function CampoRegiao({titulo,r,mudar}:{titulo:string;r:Regiao;mudar:(r:Regiao)=>void}){
  const pct=(v:number)=>Math.round(v*100);
  const set=(k:keyof Regiao,v:number)=>{ const n={...r,[k]:v/100}; n.w=Math.min(n.w,1-n.x); n.h=Math.min(n.h,1-n.y); mudar(n); };
  return <fieldset className="tpl-regiao"><legend>{titulo}</legend>
    {([['x','Distância da esquerda'],['y','Distância do topo'],['w','Largura'],['h','Altura']] as [keyof Regiao,string][]).map(([k,n])=>
      <label key={k}>{n}: {pct(r[k])}%<input type="range" min={k==='w'||k==='h'?5:0} max={k==='w'||k==='h'?100:95} value={pct(r[k])} onChange={e=>set(k,+e.target.value)}/></label>)}
  </fieldset>;
}

/** Formulário de um template. Usado na aba Templates. */
function FormModelo({m,set}:{m:Modelo;set:(p:Partial<Modelo>)=>void}){
  const {toast}=useApp();
  function logo(f:File|null){
    if(!f) return; if(f.size>1_000_000){ toast('Use uma imagem de até 1 MB (PNG com fundo transparente fica melhor).','erro'); return; }
    if(f.type==='image/svg+xml'){ toast('Use PNG, JPG ou WEBP: o servidor dos agentes não lê SVG.','erro'); return; }
    const r=new FileReader(); r.onload=()=>{ set({logo:String(r.result)}); toast('Logo carregado.','ok'); }; r.readAsDataURL(f);
  }
  const tj:Tarja=m.tarja||TARJA_PADRAO;
  const onde=!m.tarja?'nao':m.tarja.topo&&m.tarja.base?'duas':m.tarja.topo?'topo':'base';
  const setTarja=(p:Partial<Tarja>|null)=>set({tarja:p?{...tj,...p}:null});
  return <div className="tpl-form">
    <label>Nome do template<input value={m.nome} maxLength={40} onChange={e=>set({nome:e.target.value})}/></label>

    <h3>Composição e enquadramento</h3>
    <div className="tpl-layouts" role="radiogroup" aria-label="Composição">{LAYOUTS.map(([id,n,d])=><button key={id} role="radio" aria-checked={m.layout===id} className={'tpl-layout '+(m.layout===id?'on':'')} onClick={()=>set({layout:id})}><b>{n}</b><small>{d}</small></button>)}</div>
    <div className="field"><span className="field-label">Proporção</span><div className="seg">{(['9:16','1:1','16:9'] as Formato[]).map(f=><button key={f} className={m.formato===f?'on':''} onClick={()=>set({formato:f})}>{f}</button>)}</div></div>
    {m.layout!=='gameplay-streamer'&&<label>Zoom: {Math.round(m.zoom*100)}%<input type="range" min={100} max={160} step={5} value={Math.round(m.zoom*100)} onChange={e=>set({zoom:+e.target.value/100})}/></label>}
    {m.layout==='cheio'&&<div className="small-grid">
      <label>Olhar para: {m.posX<0.4?'esquerda':m.posX>0.6?'direita':'centro'}<input type="range" min={0} max={100} value={Math.round(m.posX*100)} onChange={e=>set({posX:+e.target.value/100})}/></label>
      <label>Altura: {m.posY<0.4?'em cima':m.posY>0.6?'embaixo':'centro'}<input type="range" min={0} max={100} value={Math.round(m.posY*100)} onChange={e=>set({posY:+e.target.value/100})}/></label>
    </div>}
    {m.layout==='gameplay-streamer'&&<>
      <label>Altura do gameplay: {m.divisao}% (a câmera fica com {100-m.divisao}%)<input type="range" min={35} max={80} value={m.divisao} onChange={e=>set({divisao:+e.target.value})}/></label>
      <div className="field"><span className="field-label">Onde a câmera do streamer aparece no vídeo original</span>
        <div className="chips">{CANTOS.map(([n,r])=><button key={n} className={'chip '+(JSON.stringify(m.camera)===JSON.stringify(r)?'on':'')} onClick={()=>set({camera:r})}>{n}</button>)}</div></div>
      <details><summary>Ajuste fino das duas áreas</summary>
        <CampoRegiao titulo="Câmera do streamer" r={m.camera} mudar={r=>set({camera:r})}/>
        <CampoRegiao titulo="Gameplay" r={m.jogo} mudar={r=>set({jogo:r})}/>
      </details>
      <p className="hint">As duas partes saem do mesmo quadro do vídeo, então ficam sempre sincronizadas. Use "Testar com um vídeo seu", ao lado, para acertar o lugar da câmera.</p>
    </>}

    <h3>Legenda, efeito e transição</h3>
    <div className="small-grid">
      <label>Estilo da legenda<select value={m.legenda} onChange={e=>set({legenda:e.target.value})}><option value="">Sem legenda</option>{captionPresets.map(p=><option key={p.id} value={p.id}>{p.nome}</option>)}</select></label>
      <label>Altura da legenda<select value={m.legendaPos} onChange={e=>set({legendaPos:e.target.value as Modelo['legendaPos']})}><option value="baixo">Embaixo</option><option value="meio">No meio</option></select></label>
    </div>
    <label>Efeito ou transição<select value={m.efeito} onChange={e=>set({efeito:e.target.value})}>{EFEITOS_MODELO.map(([id,n])=><option key={id} value={id}>{n}</option>)}</select></label>

    <h3>Gancho e tarjas</h3>
    <div className="small-grid">
      <label className="check"><input type="checkbox" checked={m.gancho} onChange={e=>set({gancho:e.target.checked})}/> Mostrar o texto de gancho</label>
      {m.gancho&&<label>Posição do gancho<select value={m.ganchoPos} onChange={e=>set({ganchoPos:e.target.value as Modelo['ganchoPos']})}><option value="topo">No topo</option><option value="alto">Um pouco abaixo</option></select></label>}
    </div>
    <div className="seg" role="radiogroup" aria-label="Tarjas">{([['nao','Sem tarjas'],['duas','Em cima e embaixo'],['topo','Só em cima'],['base','Só embaixo']] as const).map(([id,n])=><button key={id} role="radio" aria-checked={onde===id} className={onde===id?'on':''} onClick={()=>id==='nao'?setTarja(null):setTarja({topo:id!=='base',base:id!=='topo'})}>{n}</button>)}</div>
    {m.tarja&&<>
      {m.tarja.topo&&<label>Texto da tarja de cima<input value={tj.textoTopo} maxLength={60} placeholder="Ex.: PARTE 1" onChange={e=>setTarja({textoTopo:e.target.value})}/></label>}
      {m.tarja.base&&<label>Texto da tarja de baixo<input value={tj.textoBase} maxLength={60} placeholder="Ex.: siga para a parte 2" onChange={e=>setTarja({textoBase:e.target.value})}/></label>}
      <div className="small-grid">
        <label>Altura<select value={tj.altura} onChange={e=>setTarja({altura:+e.target.value})}><option value={8}>Fina</option><option value={12}>Média</option><option value={16}>Grossa</option><option value={22}>Bem grossa</option></select></label>
        <label>Cor da tarja<input type="color" value={tj.cor} onChange={e=>setTarja({cor:e.target.value})}/></label>
        <label>Cor do texto<input type="color" value={tj.corTexto} onChange={e=>setTarja({corTexto:e.target.value})}/></label>
      </div>
    </>}

    <h3>Cores, logo, moldura e créditos</h3>
    <div className="field"><span className="field-label">Logo</span>
      <div className="logo-row">{m.logo?<img src={m.logo} alt="Logo" className="logo-prev"/>:<span className="logo-prev empty"><ImagePlus size={22}/></span>}
        <label className="subtle file-btn"><ImagePlus size={15}/> {m.logo?'Trocar logo':'Enviar logo'}<input type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={e=>logo(e.target.files?.[0]||null)}/></label>
        {m.logo&&<button className="subtle" onClick={()=>set({logo:''})}><Trash2 size={15}/> Remover</button>}</div></div>
    <div className="small-grid">
      <label>Posição do logo<select value={m.logoPos} onChange={e=>set({logoPos:e.target.value as Modelo['logoPos']})}><option value="top-left">Topo à esquerda</option><option value="top-right">Topo à direita</option><option value="bottom-left">Embaixo à esquerda</option><option value="bottom-right">Embaixo à direita</option></select></label>
      <label>Cor da marca<input type="color" value={m.cor} onChange={e=>set({cor:e.target.value})}/></label>
    </div>
    <label>Crédito ou @ do canal<input value={m.credito} maxLength={40} placeholder="Ex.: @seucanal ou Crédito: Fulano" onChange={e=>set({credito:e.target.value})}/></label>
    <label className="check"><input type="checkbox" checked={m.moldura} onChange={e=>set({moldura:e.target.checked})}/> Moldura colorida em volta do vídeo</label>

    <h3>Exportação</h3>
    <div className="small-grid">
      <label>Resolução<select value={m.resolucao} onChange={e=>set({resolucao:+e.target.value as 1080|720})}><option value={1080}>1080p (recomendado)</option><option value={720}>720p (mais leve e rápido)</option></select></label>
      <label>Qualidade<select value={m.qualidade} onChange={e=>set({qualidade:e.target.value as Qualidade})}>{(Object.keys(QUALIDADES) as Qualidade[]).map(q=><option key={q} value={q}>{QUALIDADES[q][0]}</option>)}</select></label>
    </div>
  </div>;
}

export default function Templates(){
  const {modelos,setModelos,modelosSinc,settings,toast,go}=useApp();
  const [sel,setSel]=useState(modelos[0]?.id||'');
  const atual=modelos.find(m=>m.id===sel)||modelos[0];
  const [ativos,setAtivos]=useState<string[]|null>(null);
  const [video,setVideo]=useState<HTMLVideoElement|null>(null);
  const cfg=useMemo(()=>({servidor:settings.servidor,servidorToken:settings.servidorToken}),[settings.servidor,settings.servidorToken]);
  useEffect(()=>{ if(!cfg.servidor){ setAtivos(null); return; } let vivo=true; verAgente(cfg).then(v=>{ if(vivo) setAtivos(v.ativos||[]); }).catch(()=>{ if(vivo) setAtivos(null); }); return ()=>{ vivo=false; }; },[cfg,modelosSinc]);
  useEffect(()=>()=>{ if(video?.src) URL.revokeObjectURL(video.src); },[video]);
  if(!atual) return null;
  const set=(p:Partial<Modelo>)=>setModelos(modelos.map(m=>m.id===atual.id?{...m,...p}:m));
  const criar=(base?:Modelo)=>{ if(modelos.length>=30){ toast('A biblioteca aceita até 30 templates.','erro'); return; } const n=novoModelo(base); setModelos([...modelos,n]); setSel(n.id); };
  const apagar=()=>{ if(modelos.length<=1){ toast('A biblioteca precisa de pelo menos um template.','erro'); return; } if(!confirm(`Apagar o template "${atual.nome}"? Os cortes já feitos com ele não mudam.`)) return; const resto=modelos.filter(m=>m.id!==atual.id); setModelos(resto); setSel(resto[0].id); if(ativos?.includes(atual.id)) marcarAgente(atual.id,false); };
  async function marcarAgente(id:string,ligar:boolean){
    const base=ativos||[];
    if(ligar&&base.length>=MAX_AGENTE&&!base.includes(id)){ toast(`Os agentes usam até ${MAX_AGENTE} templates. Desmarque um para trocar.`,'erro'); return; }
    const novo=ligar?[...new Set([...base,id])]:base.filter(x=>x!==id);
    if(!novo.length){ toast('Deixe pelo menos um template para os agentes.','erro'); return; }
    setAtivos(novo);     // mostra na hora; se o servidor recusar, volta ao que era
    try{ const v=await salvarAgente(cfg,{cortes:{modelos:novo}}); setAtivos(v.ativos||novo); }
    catch(e){ setAtivos(base); toast(e instanceof Error?e.message:String(e),'erro'); }
  }
  function testar(f:File|null){
    if(!f) return;
    const v=document.createElement('video'); v.muted=true; v.playsInline=true; v.preload='auto'; v.src=URL.createObjectURL(f);
    v.onloadedmetadata=()=>{ v.currentTime=Math.min(v.duration*0.3,60); };
    v.onseeked=()=>setVideo(v);
    v.onerror=()=>toast('Não consegui abrir este vídeo.','erro');
  }
  return <div className="tpl-pagina">
    <section className="panel tpl-lista">
      <div className="section-head"><h2><LayoutTemplate size={18}/> Seus templates</h2><button className="primary sm" onClick={()=>criar()}><Plus size={14}/> Novo</button></div>
      <p className={'hint '+(modelosSinc==='erro'?'bad':'')}>
        {modelosSinc==='servidor'&&<><CheckCircle2 size={13}/> Salvos neste navegador e no servidor. Os agentes usam estes mesmos templates.</>}
        {modelosSinc==='local'&&<><Server size={13}/> Salvos só neste navegador. <button className="link-btn" onClick={()=>go('config')}>Ligue o servidor</button> para os agentes usarem.</>}
        {modelosSinc==='erro'&&<><AlertTriangle size={13}/> Não consegui falar com o servidor agora. As mudanças ficam neste navegador e sobem quando ele voltar.</>}
      </p>
      <ul className="tpl-cartoes">{modelos.map(m=>{ const noAgente=!!ativos?.includes(m.id); return <li key={m.id} className={'tpl-cartao '+(m.id===atual.id?'on':'')}>
        <button className="tpl-abrir" onClick={()=>setSel(m.id)} aria-pressed={m.id===atual.id}><b>{m.nome}</b><small>{LAYOUTS.find(l=>l[0]===m.layout)?.[1]} • {m.formato} • {m.resolucao}p</small></button>
        {ativos&&<label className={'tpl-agente '+(noAgente?'on':'')} title="Usar este template nos agentes"><input type="checkbox" checked={noAgente} onChange={e=>marcarAgente(m.id,e.target.checked)}/> <Bot size={13}/> Agentes</label>}
      </li>; })}</ul>
      {ativos?<p className="hint">{ativos.length} de {MAX_AGENTE} templates ativos nos agentes. O Agente de Cortes sorteia um deles para cada corte.</p>
        :<p className="hint">Com o servidor ligado, você marca aqui até {MAX_AGENTE} templates para os agentes.</p>}
    </section>
    <section className="panel tpl-editor">
      <div className="section-head"><h2>Editar: {atual.nome}</h2><div className="row-gap">
        <button className="subtle sm" onClick={()=>criar(atual)}><Copy size={14}/> Duplicar</button>
        <button className="subtle sm" onClick={apagar}><Trash2 size={14}/> Apagar</button></div></div>
      <FormModelo m={atual} set={set}/>
    </section>
    <section className="panel tpl-previa center-col">
      <div className="section-head"><h2>Prévia</h2></div>
      <PreviaModelo m={atual} video={video}/>
      <label className="subtle file-btn mt"><Film size={15}/> {video?'Trocar o vídeo da prévia':'Testar com um vídeo seu'}<input type="file" accept="video/*" hidden onChange={e=>testar(e.target.files?.[0]||null)}/></label>
      {video&&<button className="link-btn" onClick={()=>setVideo(null)}>Voltar ao exemplo</button>}
      <p className="hint">A prévia usa o mesmo desenho do editor e do vídeo exportado. O vídeo de teste não sai do seu aparelho.</p>
    </section>
  </div>;
}
