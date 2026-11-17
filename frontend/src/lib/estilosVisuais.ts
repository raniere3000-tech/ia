// Biblioteca visual compartilhada, lado do site: desenha no canvas os mesmos 12 estilos que o servidor monta com FFmpeg
// (servidor/visual_presets.py). Os ids e os componentes são os mesmos. A prévia e a exportação do navegador usam
// esta função; o resultado é muito parecido com o do servidor, mas não idêntico pixel a pixel (cada um usa o seu motor).
// São tratamentos sobre o vídeo real: nada aqui vira 3D nem refaz a filmagem.

export type EstiloUso = {id:string; forca:number; off:string[]; texto:string};
export type Custo = 'leve'|'medio'|'pesado';
export type EstiloInfo = {id:string; nome:string; desc:string; custo:Custo; beta?:string; cor:string};
export const COMPONENTES:Record<string,string> = {grade:'Cor e contraste',brilho:'Brilho (glow)',vinheta:'Vinheta',textura:'Grão e ruído',moldura:'Moldura',hud:'Faixas e HUD',distorcao:'Distorção de cor',foco:'Desfoque de foco',pixel:'Borda pixelada',flash:'Clarão de entrada'};

/** Catálogo local (nomes e descrições). O estado real (pronto, beta, indisponível, tempo medido) vem do servidor. */
export const ESTILOS:EstiloInfo[] = [
  {id:'gamer_neon',nome:'Gamer Neon',desc:'Brilho, moldura neon, vinheta e cores fortes.',custo:'medio',cor:'#00F0FF'},
  {id:'cinema_noturno',nome:'Cinema Noturno',desc:'Tons frios, contraste, vinheta e barras de cinema.',custo:'leve',cor:'#2B4C8C'},
  {id:'golden_cinematic',nome:'Cinemático Dourado',desc:'Luz quente simulada, grão leve e barras finas.',custo:'leve',cor:'#D9A441'},
  {id:'miniatura_isometrica',nome:'Miniatura Isométrica',desc:'Efeito maquete: foco só no meio, cores vivas e moldura de madeira.',custo:'pesado',cor:'#C89B5E',beta:'É um falso tilt-shift (desfoque em faixas); não muda a perspectiva da imagem.'},
  {id:'maquete_papel',nome:'Maquete de Papel',desc:'Moldura de papel com sombra, cores vivas e grão.',custo:'leve',cor:'#F3EBDD'},
  {id:'acrilico_glass',nome:'Acrílico / Glass',desc:'Painéis translúcidos, reflexo e brilho suave.',custo:'medio',cor:'#BFD9FF',beta:'Os painéis são simulados (faixas translúcidas); o vídeo atrás não é desfocado.'},
  {id:'porcelana_suave',nome:'Porcelana Suave',desc:'Cores claras e suaves, brilho delicado e moldura limpa.',custo:'medio',cor:'#FAF7F2'},
  {id:'industrial_impacto',nome:'Industrial',desc:'Contraste duro, cores frias, ruído e faixas amarelas de aviso.',custo:'leve',cor:'#F2C200'},
  {id:'comic_gameplay',nome:'Quadrinhos Gamer',desc:'Cores chapadas, retícula de quadrinhos e borda grossa.',custo:'leve',cor:'#FF4D6D'},
  {id:'retro_vhs',nome:'Retro VHS',desc:'Linhas de varredura, ruído e deslocamento de cor.',custo:'leve',cor:'#9B6BFF'},
  {id:'pixel_stream',nome:'Pixel Stream',desc:'Borda pixelada e faixas verdes estilo 8-bit.',custo:'medio',cor:'#39FF6A'},
  {id:'sports_replay',nome:'Replay Esportivo',desc:'Selo vermelho de replay, mais contraste e clarão de entrada.',custo:'leve',cor:'#E10600'},
];
export const estiloInfo=(id:string)=>ESTILOS.find(e=>e.id===id)||null;
export const estiloNenhum=():EstiloUso|null=>null;
export const usoPadrao=(id:string):EstiloUso=>({id,forca:1,off:[],texto:''});

const lerp=(a:number,b:number,f:number)=>a+(b-a)*Math.max(0,Math.min(1,f));
let tmp:HTMLCanvasElement|null=null, tmp2:HTMLCanvasElement|null=null, ruido:HTMLCanvasElement|null=null;
const canvasAux=(n:1|2,W:number,H:number)=>{
  let c=n===1?tmp:tmp2; if(!c){ c=document.createElement('canvas'); if(n===1) tmp=c; else tmp2=c; }
  if(c.width!==W||c.height!==H){ c.width=W; c.height=H; }
  return c;
};
const suportaFiltro=(ctx:CanvasRenderingContext2D)=>'filter' in ctx;

function grade(ctx:CanvasRenderingContext2D,W:number,H:number,css:string){
  if(!suportaFiltro(ctx)) return;                 // navegador sem ctx.filter (ex.: Safari antigo): fica sem este componente
  const c=canvasAux(1,W,H); const x=c.getContext('2d')!; x.clearRect(0,0,W,H); x.drawImage(ctx.canvas,0,0,W,H);
  ctx.save(); ctx.filter=css; ctx.drawImage(c,0,0,W,H); ctx.restore();
}
function tom(ctx:CanvasRenderingContext2D,W:number,H:number,cor:string,a:number,modo:GlobalCompositeOperation='soft-light'){
  if(a<=0.005) return; ctx.save(); ctx.globalCompositeOperation=modo; ctx.globalAlpha=a; ctx.fillStyle=cor; ctx.fillRect(0,0,W,H); ctx.restore();
}
function brilho(ctx:CanvasRenderingContext2D,W:number,H:number,sigma:number,a:number){
  if(a<=0.005||!suportaFiltro(ctx)) return;
  const c=canvasAux(1,W,H); const x=c.getContext('2d')!; x.clearRect(0,0,W,H); x.drawImage(ctx.canvas,0,0,W,H);
  ctx.save(); ctx.filter=`blur(${sigma}px)`; ctx.globalCompositeOperation='screen'; ctx.globalAlpha=a; ctx.drawImage(c,0,0,W,H); ctx.restore();
}
function vinheta(ctx:CanvasRenderingContext2D,W:number,H:number,forca:number){
  if(forca<=0.01) return;
  const g=ctx.createRadialGradient(W/2,H/2,Math.min(W,H)*0.3,W/2,H/2,Math.hypot(W,H)/2);
  g.addColorStop(0,'rgba(0,0,0,0)'); g.addColorStop(1,`rgba(0,0,0,${0.75*forca})`);
  ctx.save(); ctx.fillStyle=g; ctx.fillRect(0,0,W,H); ctx.restore();
}
function grao(ctx:CanvasRenderingContext2D,W:number,H:number,qtd:number){
  if(qtd<=0.5) return;
  if(!ruido){ ruido=document.createElement('canvas'); ruido.width=ruido.height=160; const r=ruido.getContext('2d')!, im=r.createImageData(160,160);
    for(let i=0;i<im.data.length;i+=4){ const v=Math.random()*255; im.data[i]=im.data[i+1]=im.data[i+2]=v; im.data[i+3]=255; } r.putImageData(im,0,0); }
  ctx.save(); ctx.globalCompositeOperation='overlay'; ctx.globalAlpha=Math.min(0.6,qtd/40);
  const ox=Math.floor(Math.random()*160), oy=Math.floor(Math.random()*160);
  for(let y=-oy;y<H;y+=160) for(let x=-ox;x<W;x+=160) ctx.drawImage(ruido,x,y);
  ctx.restore();
}
function faixas(ctx:CanvasRenderingContext2D,W:number,H:number,cor:string,a:number,topo:number,base:number){
  if(a<=0.005) return; ctx.save(); ctx.globalAlpha=a; ctx.fillStyle=cor; ctx.fillRect(0,0,W,H*topo); ctx.fillRect(0,H*(1-base),W,H*base); ctx.restore();
}
function borda(ctx:CanvasRenderingContext2D,W:number,H:number,cor:string,a:number,esp:number,desl=0){
  if(a<=0.005) return; ctx.save(); ctx.globalAlpha=a; ctx.strokeStyle=cor; ctx.lineWidth=esp;
  ctx.strokeRect(desl+esp/2,desl+esp/2,W-2*desl-esp,H-2*desl-esp); ctx.restore();
}
function linhas(ctx:CanvasRenderingContext2D,W:number,H:number,passo:number,a:number,cor='#000'){
  if(a<=0.005) return; ctx.save(); ctx.globalAlpha=a; ctx.fillStyle=cor; for(let y=0;y<H;y+=passo) ctx.fillRect(0,y,W,1); ctx.restore();
}
function reticula(ctx:CanvasRenderingContext2D,W:number,H:number,passo:number,a:number){
  if(a<=0.005) return; ctx.save(); ctx.globalAlpha=a; ctx.fillStyle='#000';
  for(let y=0;y<H;y+=passo) for(let x=(y/passo%2)*passo/2;x<W;x+=passo) { ctx.beginPath(); ctx.arc(x,y,passo*0.14,0,6.283); ctx.fill(); } ctx.restore();
}
function focoFaixa(ctx:CanvasRenderingContext2D,W:number,H:number,sigma:number,f:number){
  if(f<=0.01||!suportaFiltro(ctx)) return;
  const nitido=canvasAux(1,W,H); const n=nitido.getContext('2d')!; n.clearRect(0,0,W,H); n.drawImage(ctx.canvas,0,0,W,H);
  ctx.save(); ctx.filter=`blur(${sigma*Math.max(0.3,f)}px)`; ctx.drawImage(nitido,0,0,W,H); ctx.restore();   // tudo desfocado
  const m=canvasAux(2,W,H); const x=m.getContext('2d')!; x.globalCompositeOperation='source-over'; x.clearRect(0,0,W,H); x.drawImage(nitido,0,0);
  x.globalCompositeOperation='destination-in'; const g=x.createLinearGradient(0,0,0,H);
  g.addColorStop(0,'rgba(0,0,0,0)'); g.addColorStop(0.375,'rgba(0,0,0,1)'); g.addColorStop(0.625,'rgba(0,0,0,1)'); g.addColorStop(1,'rgba(0,0,0,0)');
  x.fillStyle=g; x.fillRect(0,0,W,H); x.globalCompositeOperation='source-over';
  ctx.drawImage(m,0,0);                              // devolve o meio nítido
}
function bordaPixel(ctx:CanvasRenderingContext2D,W:number,H:number,bloco:number,marg:number){
  const c=canvasAux(1,W,H); const x=c.getContext('2d')!; x.clearRect(0,0,W,H); x.drawImage(ctx.canvas,0,0,W,H);
  const p=canvasAux(2,Math.ceil(W/bloco),Math.ceil(H/bloco)); const px=p.getContext('2d')!; px.imageSmoothingEnabled=false; px.clearRect(0,0,p.width,p.height); px.drawImage(c,0,0,p.width,p.height);
  ctx.save(); ctx.imageSmoothingEnabled=false; ctx.drawImage(p,0,0,W,H);                         // tudo pixelado
  ctx.drawImage(c,marg,marg,W-2*marg,H-2*marg,marg,marg,W-2*marg,H-2*marg); ctx.restore();       // centro nítido
}

/** Desenha o estilo sobre o quadro já montado (antes de tarjas, legenda e gancho). `t` = segundos desde o início do corte. */
export function desenharEstilo(ctx:CanvasRenderingContext2D,e:EstiloUso|null|undefined,W:number,H:number,t:number){
  if(!e||!e.id) return;
  const f=Math.max(0,Math.min(1,e.forca)); if(f<=0.005) return;
  const on=(c:string)=>!e.off.includes(c);
  const L=(a:number,b:number)=>lerp(a,b,f);
  const m=Math.min(W,H)/360;                                        // as medidas do servidor foram pensadas em ~360 px de largura x 640
  switch(e.id){
    case 'gamer_neon':
      if(on('grade')) grade(ctx,W,H,`contrast(${L(1,1.12)}) saturate(${L(1,1.45)}) brightness(${L(1,1.02)})`);
      if(on('brilho')) brilho(ctx,W,H,18*m*1.6,L(0,0.42));
      if(on('vinheta')) vinheta(ctx,W,H,f);
      if(on('moldura')){ borda(ctx,W,H,'#00F0FF',L(0,0.9),10*m*1.6); borda(ctx,W,H,'#FF2BD6',L(0,0.8),5*m*1.6,14*m*1.6); }
      break;
    case 'cinema_noturno':
      if(on('grade')){ tom(ctx,W,H,'#1E3C8C',L(0,0.22)); grade(ctx,W,H,`contrast(${L(1,1.15)}) saturate(${L(1,0.85)}) brightness(${L(1,0.96)})`); }
      if(on('vinheta')) vinheta(ctx,W,H,f);
      if(on('hud')) faixas(ctx,W,H,'#000',L(0,1),0.07,0.07);
      break;
    case 'golden_cinematic':
      if(on('grade')){ tom(ctx,W,H,'#FFB347',L(0,0.28)); grade(ctx,W,H,`contrast(${L(1,1.08)}) saturate(${L(1,1.15)})`); }
      if(on('textura')) grao(ctx,W,H,L(0,8));
      if(on('vinheta')) vinheta(ctx,W,H,f*0.8);
      if(on('hud')) faixas(ctx,W,H,'#000',L(0,1),0.05,0.05);
      break;
    case 'miniatura_isometrica':
      if(on('grade')) grade(ctx,W,H,`contrast(${L(1,1.1)}) saturate(${L(1,1.4)})`);
      if(on('foco')) focoFaixa(ctx,W,H,10*m*1.6,f);
      if(on('moldura')){ borda(ctx,W,H,'#C89B5E',L(0,1),26*m*1.6); borda(ctx,W,H,'#5B3A1A',L(0,0.9),4*m*1.6,26*m*1.6); }
      break;
    case 'maquete_papel':
      if(on('grade')) grade(ctx,W,H,`saturate(${L(1,1.25)}) contrast(${L(1,1.05)})`);
      if(on('textura')) grao(ctx,W,H,L(0,7));
      if(on('moldura')){ borda(ctx,W,H,'#F3EBDD',L(0,1),34*m*1.6); borda(ctx,W,H,'#000',L(0,0.28),8*m*1.6,34*m*1.6); borda(ctx,W,H,'#D8CCB8',L(0,0.8),3*m*1.6,42*m*1.6); }
      break;
    case 'acrilico_glass':
      if(on('grade')) grade(ctx,W,H,`contrast(${L(1,1.05)}) saturate(${L(1,1.1)}) brightness(${L(1,1.02)})`);
      if(on('hud')){ faixas(ctx,W,H,'#fff',L(0,0.14),0.09,0.09); ctx.save(); ctx.globalAlpha=L(0,0.55); ctx.fillStyle='#fff'; ctx.fillRect(0,H*0.09,W,2); ctx.fillRect(0,H*0.91,W,2); ctx.restore(); }
      if(on('moldura')) borda(ctx,W,H,'#fff',L(0,0.45),3*m*1.6,10*m*1.6);
      if(on('brilho')) brilho(ctx,W,H,22*m*1.6,L(0,0.18));
      break;
    case 'porcelana_suave':
      if(on('grade')){ tom(ctx,W,H,'#FFE9DC',L(0,0.1)); grade(ctx,W,H,`brightness(${L(1,1.05)}) contrast(${L(1,0.95)}) saturate(${L(1,0.8)})`); }
      if(on('brilho')) brilho(ctx,W,H,16*m*1.6,L(0,0.28));
      if(on('moldura')){ borda(ctx,W,H,'#FAF7F2',L(0,1),22*m*1.6); borda(ctx,W,H,'#E8DFD2',L(0,0.9),3*m*1.6,22*m*1.6); }
      break;
    case 'industrial_impacto':
      if(on('grade')){ tom(ctx,W,H,'#3A5F8F',L(0,0.14)); grade(ctx,W,H,`contrast(${L(1,1.3)}) saturate(${L(1,0.55)})`); }
      if(on('textura')) grao(ctx,W,H,L(0,14));
      if(on('vinheta')) vinheta(ctx,W,H,f*0.9);
      if(on('hud')) faixas(ctx,W,H,'#F2C200',L(0,1),0.035,0.035);
      break;
    case 'comic_gameplay':
      if(on('grade')) grade(ctx,W,H,`contrast(${L(1,1.25)}) saturate(${L(1,1.6)})`);
      if(on('textura')) reticula(ctx,W,H,Math.max(8,W/60*1.0),L(0,0.2));
      if(on('moldura')) borda(ctx,W,H,'#000',L(0,1),16*m*1.6);
      break;
    case 'retro_vhs':
      if(on('grade')) grade(ctx,W,H,`saturate(${L(1,1.3)}) contrast(${L(1,1.05)}) blur(${L(0,0.8)}px)`);
      if(on('distorcao')&&f>0.05){ // separa um pouco o vermelho e o azul
        const c=canvasAux(1,W,H); const x=c.getContext('2d')!; x.clearRect(0,0,W,H); x.drawImage(ctx.canvas,0,0,W,H);
        ctx.save(); ctx.globalCompositeOperation='screen'; ctx.globalAlpha=0.28*f; ctx.drawImage(c,-4*m*1.6,0,W,H); ctx.drawImage(c,4*m*1.6,0,W,H); ctx.restore(); }
      if(on('textura')){ grao(ctx,W,H,L(0,20)); linhas(ctx,W,H,4,L(0,0.35)); }
      if(on('vinheta')) vinheta(ctx,W,H,f);
      break;
    case 'pixel_stream':
      if(on('grade')) grade(ctx,W,H,`saturate(${L(1,1.3)}) contrast(${L(1,1.08)})`);
      if(on('pixel')) bordaPixel(ctx,W,H,Math.max(4,Math.round(14*m*1.6)),Math.round(Math.min(W,H)*0.05));
      if(on('hud')) faixas(ctx,W,H,'#39FF6A',L(0,1),0.03,0.03);
      break;
    case 'sports_replay':{
      if(on('grade')) grade(ctx,W,H,`contrast(${L(1,1.12)}) saturate(${L(1,1.2)})`);
      if(on('hud')){
        ctx.save(); ctx.globalAlpha=L(0,0.95); ctx.fillStyle='#E10600'; ctx.fillRect(W*0.04,H*0.045,W*0.4,H*0.045);
        ctx.globalAlpha=L(0,1); ctx.fillStyle='#fff'; ctx.font=`700 ${Math.round(H*0.03)}px system-ui,sans-serif`; ctx.textBaseline='middle';
        ctx.fillText((e.texto||'REPLAY').slice(0,24),W*0.055,H*0.0675); ctx.restore();
      }
      if(on('flash')&&t<0.25){ ctx.save(); ctx.globalAlpha=Math.max(0,1-t/Math.max(0.01,L(0.01,0.25))); ctx.fillStyle='#fff'; ctx.fillRect(0,0,W,H); ctx.restore(); }
      break;
    }
  }
}
