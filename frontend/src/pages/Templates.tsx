import { useEffect, useRef } from 'react';
import { ImagePlus, Trash2 } from 'lucide-react';
import { useApp } from '../state';
import { drawFrame, loadImage, type Template } from '../lib/render';

function Mock({t}:{t:Template}){
  const ref=useRef<HTMLCanvasElement>(null);
  useEffect(()=>{ let alive=true; (async()=>{
    const c=ref.current; if(!c) return; const ctx=c.getContext('2d')!;
    // Quadro fictício só para mostrar o template.
    const fake=document.createElement('canvas'); fake.width=1280; fake.height=720; const f=fake.getContext('2d')!;
    const g=f.createLinearGradient(0,0,1280,720); g.addColorStop(0,'#3b4a7a'); g.addColorStop(1,'#1c2033'); f.fillStyle=g; f.fillRect(0,0,1280,720);
    f.fillStyle='#ffffff22'; f.beginPath(); f.arc(640,360,150,0,Math.PI*2); f.fill(); f.fillStyle='#fff8'; f.font='700 60px sans-serif'; f.textAlign='center'; f.fillText('SEU VÍDEO',640,380);
    const logo=await loadImage(t.logo); if(!alive) return;
    Object.assign(fake,{videoWidth:1280,videoHeight:720});
    drawFrame(ctx,fake as unknown as HTMLVideoElement,document.createElement('canvas'),1,10,{legenda:null,efeito:'blur-background',cues:[],gancho:'',accent:t.cor,template:{...t,ativo:true},logoImg:logo},1080,1920);
  })(); return ()=>{alive=false}; },[t]);
  return <canvas ref={ref} width={1080} height={1920} className="preview-canvas f9x16"/>;
}

export default function Templates(){
  const {template:t,setTemplate,toast}=useApp();
  const set=(p:Partial<Template>)=>setTemplate({...t,ativo:true,...p});
  function logo(f:File|null){
    if(!f) return; if(f.size>1_500_000){ toast('Use uma imagem de até 1,5 MB (PNG com fundo transparente fica melhor).','erro'); return; }
    const r=new FileReader(); r.onload=()=>{ set({logo:String(r.result),ativo:true}); toast('Logo carregado.','ok'); }; r.readAsDataURL(f);
  }
  return <div className="two-cols">
   <section className="panel">
    <div className="section-head"><h2>Sua marca nos cortes</h2></div>
    <label className="check big"><input type="checkbox" checked={t.ativo} onChange={e=>set({ativo:e.target.checked})}/> Aplicar o template em todos os cortes exportados</label>
    <div className="field"><span className="field-label">Logo</span>
     <div className="logo-row">{t.logo?<img src={t.logo} alt="Logo" className="logo-prev"/>:<span className="logo-prev empty"><ImagePlus size={22}/></span>}
      <label className="subtle file-btn"><ImagePlus size={15}/> {t.logo?'Trocar logo':'Enviar logo'}<input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" hidden onChange={e=>logo(e.target.files?.[0]||null)}/></label>
      {t.logo&&<button className="subtle" onClick={()=>set({logo:''})}><Trash2 size={15}/> Remover</button>}</div></div>
    <label>Posição do logo<select value={t.logoPos} onChange={e=>set({logoPos:e.target.value as Template['logoPos']})}><option value="top-left">Topo à esquerda</option><option value="top-right">Topo à direita</option><option value="bottom-left">Embaixo à esquerda</option><option value="bottom-right">Embaixo à direita</option></select></label>
    <label>Crédito ou @ do canal<input value={t.credito} maxLength={40} placeholder="Ex.: @seucanal ou Crédito: Fulano" onChange={e=>set({credito:e.target.value})}/></label>
    <div className="small-grid"><label>Cor da marca<input type="color" value={t.cor} onChange={e=>set({cor:e.target.value})}/></label>
     <label className="check"><input type="checkbox" checked={t.moldura} onChange={e=>set({moldura:e.target.checked})}/> Moldura colorida</label></div>
    <p className="hint">O template fica salvo neste navegador e aparece na prévia do editor e nos vídeos exportados.</p>
   </section>
   <section className="panel center-col"><div className="section-head"><h2>Prévia</h2></div><Mock t={t}/></section>
  </div>;
}
