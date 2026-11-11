import { useEffect, useRef } from 'react';
import { CheckCircle2, Wand2 } from 'lucide-react';
import { useApp, captionPresets, effectPresets } from '../state';
import { drawCaption, type Preset } from '../lib/captions';

const EFEITOS:Record<string,string> = {
  'blur-background':'O vídeo horizontal fica no centro e o fundo é preenchido com uma versão desfocada dele.',
  'seguir-rosto':'Tela cheia na vertical: a câmera acompanha o rosto de quem fala (detecção de rosto no seu navegador). Sem rosto no trecho, usa fundo desfocado.',
  'zoom-acao':'Aproxima a imagem devagar durante o corte, dando sensação de tensão.',
  'camera-shake':'Pequenos tremores a cada 4 segundos, bom para ação e reações.',
  'transicao-fade':'Entra e sai suavemente do preto.',
  'virada-cena':'Flash branco no começo do corte.',
  'speed-ramp':'Acelera 1,5× no meio do corte.',
  'nenhum':'Corta o vídeo para preencher a tela toda, sem fundo desfocado.',
};

function Sample({p}:{p:Preset}){
  const ref=useRef<HTMLCanvasElement>(null);
  useEffect(()=>{ const c=ref.current; if(!c) return; const ctx=c.getContext('2d')!;
    const g=ctx.createLinearGradient(0,0,c.width,c.height); g.addColorStop(0,'#2a3350'); g.addColorStop(1,'#151a28'); ctx.fillStyle=g; ctx.fillRect(0,0,c.width,c.height);
    drawCaption(ctx,{...p,position:'center',safeAreaBottomPercent:0},'esse é o melhor momento do vídeo',0.5,2.4,c.width,c.height);
  },[p]);
  return <canvas ref={ref} width={1080} height={700} className="preset-canvas"/>;
}

export default function Estilos(){
  const {settings,setSettings,projeto,setProjeto,toast}=useApp();
  const aplicar=(campo:'legenda'|'efeito',v:string)=>{ setProjeto(pj=>({...pj,clips:pj.clips.map(c=>({...c,[campo]:v}))})); toast('Aplicado a todos os cortes do vídeo atual.','ok'); };
  return <>
   <section className="panel">
    <div className="section-head"><h2>Estilos de legenda <span className="count">{captionPresets.length}</span></h2><span>Clique para usar como padrão nos próximos cortes</span></div>
    <div className="preset-grid">{captionPresets.map(p=><button key={p.id} className={'preset'+(settings.legendaPadrao===p.id?' selected':'')} onClick={()=>{setSettings({legendaPadrao:p.id});toast(`“${p.nome}” é o novo estilo padrão.`,'ok')}}>
      <Sample p={p}/><strong>{settings.legendaPadrao===p.id&&<CheckCircle2 size={14}/>} {p.nome}</strong><small>{p.animation==='none'?'Sem animação':'Animação: '+p.animation} • até {p.maxLines} linhas</small></button>)}</div>
    {projeto.clips.length>0&&<button className="subtle mt" onClick={()=>aplicar('legenda',settings.legendaPadrao)}><Wand2 size={15}/> Aplicar o estilo padrão a todos os cortes atuais</button>}
   </section>
   <section className="panel">
    <div className="section-head"><h2>Efeitos de vídeo <span className="count">{effectPresets.length}</span></h2><span>O efeito padrão vale para os próximos cortes</span></div>
    <div className="effect-grid">{[...effectPresets.map(p=>({id:p.id,nome:p.nome})),{id:'nenhum',nome:'Sem efeito'}].map(p=><button key={p.id} className={'effect'+(settings.efeitoPadrao===p.id?' selected':'')} onClick={()=>{setSettings({efeitoPadrao:p.id});toast(`“${p.nome}” é o novo efeito padrão.`,'ok')}}>
      <span className={'fx-demo fx-'+p.id}><i/></span><div><strong>{settings.efeitoPadrao===p.id&&<CheckCircle2 size={14}/>} {p.nome}</strong><small>{EFEITOS[p.id]}</small></div></button>)}</div>
    {projeto.clips.length>0&&<button className="subtle mt" onClick={()=>aplicar('efeito',settings.efeitoPadrao)}><Wand2 size={15}/> Aplicar o efeito padrão a todos os cortes atuais</button>}
   </section>
  </>;
}
