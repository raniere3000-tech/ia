import { useEffect, useState } from 'react';
import { Play, Loader2, Server, Box, CheckCircle2 } from 'lucide-react';
import { useApp } from '../state';
import { HelpButton } from '../components/Help';
import { useCfg, useServidor, erroTexto } from '../components/Servidor2';
import { catalogo, pedirDemo, lerFila, urlServidor, assinarAsset, lerVideos3d, testar3d, horaTexto, type EstiloInfo, type DemoInfo } from '../lib/api';

const STATUS:Record<string,[string,string]>={operacional:['Operacional','ok'],beta:['Beta / em teste','warn'],indisponivel:['Indisponível','bad']};
/** Os estilos, também sem servidor (lista fixa igual à do servidor, para mostrar a situação honesta). */
const OFFLINE:Pick<EstiloInfo,'id'|'nome'|'status'|'descricao'>[]=[
  {id:'lousa_giz',nome:'Lousa de giz',status:'operacional',descricao:''},{id:'traco_neon',nome:'Traço neon',status:'operacional',descricao:''},
  {id:'quadrinhos',nome:'Quadrinhos',status:'operacional',descricao:''},{id:'vetor_chapado',nome:'Vetor chapado',status:'operacional',descricao:''},
  {id:'pixel_art',nome:'Pixel art',status:'operacional',descricao:''},{id:'papel_recortado',nome:'Papel recortado',status:'operacional',descricao:''},
  {id:'motion_graphics',nome:'Motion graphics',status:'operacional',descricao:''},{id:'quadro_branco',nome:'Quadro branco',status:'operacional',descricao:''},
  {id:'palitinho',nome:'Palitinho',status:'beta',descricao:''},{id:'cartoon2d',nome:'Desenho animado 2D',status:'beta',descricao:''},{id:'parallax_25d',nome:'2.5D / Parallax',status:'beta',descricao:''},
  {id:'cinema3d',nome:'3D de cinema',status:'indisponivel',descricao:''},{id:'brinquedo_blocos',nome:'Blocos de brinquedo',status:'indisponivel',descricao:''},
  {id:'plastico3d',nome:'Bonequinho de plástico',status:'indisponivel',descricao:''},{id:'retro3d_2000',nome:'3D anos 2000',status:'indisponivel',descricao:''},{id:'mapas_animados',nome:'Mapas animados',status:'indisponivel',descricao:''},{id:'documentario',nome:'Documentário (fotos reais)',status:'operacional',descricao:''},{id:'animado2d',nome:'Desenho animado com personagens',status:'beta',descricao:''},{id:'animado3d',nome:'Personagens em 3D',status:'beta',descricao:''},
];

const DESC_EFEITO:Record<string,string>={chuva_noite:'Partículas de chuva por cima da cena e luz azulada de noite.',neve_fria:'Flocos caindo devagar e luz fria.',
  poeira_quente:'Poeira subindo no ar com luz de fim de tarde.',neblina_dramatica:'Neblina passando e contraste forte com cantos escuros.',
  angulos:'Câmera de cima, de baixo e inclinada, e um movimento livre do começo ao fim do plano.'};

function Cartao({e,demo,formato,escolher,variante=''}:{e:EstiloInfo;demo?:DemoInfo;formato:string;escolher?:(id:string)=>void;variante?:string}){
  const cfg=useCfg(); const {toast}=useApp();
  const [url,setUrl]=useState('');
  const [esperando,setEsperando]=useState('');
  const [st,cls]=STATUS[e.status]||STATUS.indisponivel;
  useEffect(()=>{ setUrl(''); },[formato]);
  // a demonstração entra na fila do servidor; quando fica pronta, aparece aqui
  useEffect(()=>{
    if(!esperando) return;
    const iv=setInterval(async()=>{
      try{ const f=await lerFila(cfg); const j=f.jobs.find(x=>x.id===esperando);
        if(j?.status==='concluido'){ const r=await pedirDemo(cfg,e.id,formato,variante); if(r.url){ setUrl(urlServidor(cfg,r.url)); setEsperando(''); } }
        else if(j?.status==='falhou'){ setEsperando(''); toast(j.erro||'A demonstração falhou.','erro'); } }catch{ /* tenta de novo */ }
    },3000);
    return ()=>clearInterval(iv);
  },[esperando,cfg,e.id,formato,toast,variante]);
  const ver=async()=>{
    try{
      if(demo){ setUrl(urlServidor(cfg,await assinarAsset(cfg,demo.asset))); return; }
      const r=await pedirDemo(cfg,e.id,formato,variante);
      if(r.url) setUrl(urlServidor(cfg,r.url)); else if(r.job){ setEsperando(r.job.id); toast('Demonstração na fila do servidor. Leva de alguns segundos a 1 minuto no celular.','info'); }
    }catch(x){ toast(erroTexto(x),'erro'); }
  };
  return <article className={'estilo-card '+e.status}>
    <div className={'estilo-previa f'+formato.replace(':','x')} style={{background:`linear-gradient(135deg,${(e.paleta||['#222','#444'])[0]},${(e.paleta||['#222','#444'])[1]||'#333'})`}}>
     {url?<video src={url} autoPlay loop muted playsInline controls/>:<span className="estilo-nome-grande" style={{color:(e.paleta||[])[2]||'#fff'}}>{e.nome}</span>}
     {esperando&&<span className="estilo-carregando"><Loader2 size={18} className="spin"/> renderizando no celular...</span>}
    </div>
    <div className="estilo-corpo">
     <div className="row-gap left"><b className="grow">{e.nome}</b><span className={'tag '+cls}>{st}</span></div>
     <p className="hint">{e.descricao}</p>
     {e.tecnica&&<p className="hint"><b>Técnica:</b> {e.tecnica}</p>}
     {e.tecnologia&&<p className="hint"><b>Como é feito:</b> {e.tecnologia}</p>}
     {e.limites&&<p className="hint"><b>Limites:</b> {e.limites}</p>}
     {demo?.segundos!=null&&<p className="hint">Demonstração real: 5 s de vídeo feitos em {demo.segundos} s{demo.onde?` (${demo.onde})`:''}.</p>}
     <p className="hint">{e.servidor?<><Server size={12}/> Roda no celular • {e.formatos.join(', ')} • {e.custo}</>:<><Box size={12}/> Ainda não roda no celular (sem teste do motor no Android).</>}</p>
     <div className="row-gap left">
      {e.servidor&&!e.precisa_imagem&&<button className="subtle sm" disabled={!!esperando} onClick={ver}><Play size={14}/> {demo?'Ver demonstração':'Gerar demonstração'}</button>}
      {e.precisa_imagem&&<span className="hint">Precisa de imagens de IA (Gemini) para cada cena; sem demonstração grátis.</span>}
      {escolher&&e.servidor&&<button className="primary sm" onClick={()=>escolher(e.id)}><CheckCircle2 size={14}/> Usar este estilo</button>}
     </div>
    </div>
  </article>;
}

export function GradeEstilos({escolher,selecionado}:{escolher?:(id:string)=>void;selecionado?:string}){
  const {settings}=useApp();
  const [formato,setFormato]=useState('9:16');
  const cat=useServidor(catalogo);
  // Primeiro o que funciona hoje, depois beta, por último o que ainda não está disponível.
  const ORDEM=(e:EstiloInfo)=>e.status==='operacional'?0:e.status==='beta'?1:2;
  const anim=cat.dados?.estilos.find(x=>x.id==='animado2d');
  const lista:EstiloInfo[]=cat.dados?.estilos||OFFLINE.map(o=>({...o,tecnica:'',prioridade:'',paleta:['#1b2030','#2a3045','#fff'],precisa_imagem:o.id==='cartoon2d',servidor:false,formatos:[],custo:''}));
  return <>
    {!settings.servidor&&<p className="hint warn">Sem o servidor do celular ligado, só a lista aparece. As demonstrações e a produção rodam no servidor.</p>}
    {cat.dados&&!cat.dados.ffmpeg&&<p className="hint bad">O servidor está sem FFmpeg (Termux: pkg install ffmpeg). Nenhum estilo renderiza até instalar.</p>}
    <div className="row-gap left"><span className="field-label">Formato da demonstração</span>{['9:16','16:9','1:1'].map(f=><button key={f} className={'chip '+(formato===f?'on':'')} onClick={()=>setFormato(f)}>{f}</button>)}</div>
    <div className="estilos-grade">{[...lista].sort((a,b)=>ORDEM(a)-ORDEM(b)).map(e=><div key={e.id} className={selecionado===e.id?'estilo-sel':''}><Cartao e={e} formato={formato} demo={cat.dados?.demos[`${e.id}:${formato}`]} escolher={escolher}/></div>)}</div>
    {!escolher&&anim&&anim.servidor&&cat.dados?.efeitos?.length?<>
     <div className="section-head mt"><h2>Efeitos de cena</h2></div>
     <p className="hint">Clima, luz e ângulos de câmera que você escolhe em cada cena (e em cada plano) do Agente 3. A demonstração usa o desenho animado com dois personagens e é renderizada de verdade no celular.</p>
     <div className="estilos-grade">{cat.dados.efeitos.map(x=><Cartao key={x.id} variante={x.id} formato={formato} demo={x.demos[formato]}
       e={{...anim,nome:x.nome,status:'beta',descricao:DESC_EFEITO[x.id]||'',tecnica:''}}/>)}</div></>:null}
  </>;
}

/** 3D: os vídeos já feitos neste celular (o primeiro em destaque) e o teste que compara 2D, 3D e o loop 3D. */
function Revisao3D(){
  const cfg=useCfg(); const {toast}=useApp();
  const [vigiar,setVigiar]=useState(false);
  const r=useServidor(lerVideos3d,vigiar?5:0,[vigiar]);
  const [tocar,setTocar]=useState('');
  const j=r.dados?.job; const andando=!!j&&['na_fila','agendado','rodando'].includes(j.status);
  useEffect(()=>{ if(r.dados&&andando!==vigiar) setVigiar(andando); },[andando,vigiar,r.dados]);
  if(!r.dados) return null;
  const l=r.dados.laudo; const vs=r.dados.videos;
  const ver=async(a:string)=>{ try{ setTocar(urlServidor(cfg,await assinarAsset(cfg,a))); }catch(e){ toast(erroTexto(e),'erro'); } };
  return <section className="panel mt">
    <div className="section-head"><h2>3D: vídeos já feitos e teste no celular</h2>{l?<span className={'tag '+(l.ambiente==='android'?(l.estado==='beta'?'ok':'warn'):'warn')}>{l.ambiente==='android'?`3D ${l.estado.replace('_',' ')}`:'medido fora do celular'}</span>:<span className="tag warn">3D não medido no celular</span>}</div>
    {vs.length?<ul className="aparelhos">{vs.map(v=><li key={v.asset}><span><Play size={14}/> {v.primeiro&&<b>Primeiro vídeo 3D: </b>}{v.tipo} • {v.duracao!=null?`${v.duracao} s • `:''}{v.tamanho_kb} KB • {horaTexto(v.criado)}</span>
      <button className="subtle sm" onClick={()=>ver(v.asset)}>Assistir</button></li>)}</ul>:<p className="hint">Nenhum vídeo 3D foi feito neste servidor ainda.</p>}
    {tocar&&<video className="video-3d" src={tocar} autoPlay controls playsInline loop/>}
    <div className="row-gap left mt"><button className="subtle" disabled={andando} onClick={async()=>{ try{ await testar3d(cfg); setVigiar(true); r.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); } }}>{andando?<Loader2 size={15} className="spin"/>:<Play size={15}/>} {andando?`${j?.etapa||'Testando'} (${Math.round(j?.progresso||0)}%)`:'Testar o 3D neste celular (pode levar vários minutos)'}</button></div>
    {l&&<><p className="hint">{l.conclusao||l.erro}</p>
     <ul className="diag">{l.testes.map(t=><li key={t.estilo}>{t.ok?<CheckCircle2 size={14} className="ok"/>:<Box size={14}/>} <b>{t.nome}</b> {t.ok?`${t.segundos} s para 5 s (${t.seg_por_seg} s por segundo) • ${t.tamanho_kb} KB${t.memoria?.ffmpeg_pico_mb?` • FFmpeg até ${Math.round(t.memoria.ffmpeg_pico_mb)} MB`:''}${t.memoria?.programa_pico_mb?` • servidor até ${Math.round(t.memoria.programa_pico_mb)} MB`:''}`:t.erro}
      {t.asset&&<button className="link-btn" onClick={()=>ver(t.asset!)}>assistir</button>}</li>)}</ul></>}
    <p className="hint">O 3D só sai do beta depois de medido no celular. Se ficar lento demais, continua beta (só cenas curtas) ou indisponível.</p>
  </section>;
}

export default function Galeria(){
  return <><section className="panel">
    <div className="section-head"><h2>17 estilos de animação <HelpButton topic="estilos3"/></h2></div>
    <p className="subtitle">A demonstração usa a mesma cena em todos os estilos para comparar. Ela é renderizada de verdade no seu celular (não é imagem ilustrativa). Os 3D foram testados no celular: são beta e lentos (o 3D é um fundo em loop, guardado depois da primeira vez). Os personagens em 3D são beta: o tempo no celular aparece abaixo depois do teste. Os mapas seguem indisponíveis. Nenhum pedido vira outro estilo escondido.</p>
    <GradeEstilos/>
  </section><Revisao3D/></>;
}
