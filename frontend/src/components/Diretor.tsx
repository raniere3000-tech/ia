import { useEffect, useRef, useState } from 'react';
import { Clapperboard, Columns2, Loader2, Plus, Trash2, TriangleAlert } from 'lucide-react';
import { useApp } from '../state';
import { assinarAsset, urlServidor, type Cena, type Plano } from '../lib/api';
import { esperar, obterMapa, pedirAB, pedirAnimatic, type Animatic, type CenaMapa, type QuadroAB } from '../lib/diretor';
import { useCfg, useServidor, erroTexto } from './Servidor2';

const NOME:Record<string,string>={WS:'Aberto',MS:'Médio',CU:'Close',ECU:'Close extremo'};
const ABERTURA:Record<string,number>={WS:150,MS:62,CU:34,ECU:22};
const CORES=['#7c6cf0','#2fc592','#f5a524','#e56a6a','#3fa7f5','#d36cf0'];

/** Palco visto de cima: quem está onde (e para onde anda), a linha do eixo e o que a câmera pega em cada plano. */
export function MapaPalco({c}:{c:CenaMapa}){
  const W=300, Y=64, CAM:[number,number]=[150,158];
  const alvo=(p:CenaMapa['planos'][number])=>{ if(p.plano==='WS') return 150; const a=c.atores.find(x=>x.id===p.personagem)||c.atores.find(x=>x.fala)||c.atores[0]; return a?a.x*W:150; };
  const planos=c.planos.length?c.planos:[{id:'p1',plano:'WS' as const}];
  return <figure className="palco">
   <svg viewBox="0 0 300 172" role="img" aria-label={`Mapa de palco da cena ${c.titulo}`}>
    <rect x="1" y="1" width="298" height="170" rx="10" className="palco-chao"/>
    <rect x="10" y="8" width="280" height="10" rx="3" className="palco-fundo"/><text x="150" y="16" className="palco-rot" textAnchor="middle">fundo do cenário</text>
    {c.eixo&&<><rect x="2" y="2" width="296" height={Y-2} className="palco-proibido"/>
     <line x1="6" y1={Y} x2="294" y2={Y} className="palco-eixo"/>
     <text x="8" y={Y-6} className="palco-rot eixo">eixo de 180°</text></>}
    {planos.map((p,k)=>{ const x=alvo(p), a=ABERTURA[p.plano]||60; return <polygon key={p.id} points={`${CAM[0]},${CAM[1]} ${x-a/2},${Y} ${x+a/2},${Y}`} className="palco-visao" style={{fill:CORES[k%CORES.length],stroke:CORES[k%CORES.length]}}/>; })}
    {c.atores.map(a=><g key={a.id}>
     {Math.abs(a.x_fim-a.x)>0.01&&<line x1={a.x*W} y1={Y+18} x2={a.x_fim*W} y2={Y+18} className="palco-passo" markerEnd="url(#seta)"/>}
     <circle cx={a.x*W} cy={Y} r="11" fill={a.cor} className={a.fala?'palco-ator fala':'palco-ator'}/>
     <text x={a.x*W} y={Y+32} className="palco-nome" textAnchor="middle">{a.nome}{a.fala?' (fala)':''}</text></g>)}
    <defs><marker id="seta" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" className="palco-seta"/></marker></defs>
    <g transform={`translate(${CAM[0]-11},${CAM[1]-9})`}><rect width="16" height="12" rx="2" className="palco-cam"/><path d="M16 3l6-3v12l-6-3z" className="palco-cam"/></g>
   </svg>
   {c.eixo&&<p className="hint palco-dica">A câmera fica sempre do lado de baixo da linha vermelha. Se alguém trocar de lado, mostre a pessoa andando.</p>}
   <figcaption>{planos.map((p,k)=><span key={p.id} className="palco-chip" style={{borderColor:CORES[k%CORES.length]}}>{k+1}. {NOME[p.plano]}{p.plano!=='WS'&&p.personagem?` em ${c.atores.find(a=>a.id===p.personagem)?.nome||p.personagem}`:''}</span>)}</figcaption>
  </figure>;
}

function ListaPlanos({ps,set,atores}:{ps:Partial<Plano>[];set:(n:Partial<Plano>[])=>void;atores:CenaMapa['atores']}){
  return <div className="ab-planos">{ps.map((p,k)=><div key={k} className="plano-linha">
   <b>{k+1}</b>
   <select value={p.plano||'WS'} onChange={e=>set(ps.map((x,j)=>j===k?{...x,plano:e.target.value as Plano['plano']}:x))} aria-label={`Enquadramento do plano ${k+1}`}>{Object.entries(NOME).map(([v,n])=><option key={v} value={v}>{n}</option>)}</select>
   {atores.length>0&&<select value={p.personagem||''} onChange={e=>set(ps.map((x,j)=>j===k?{...x,personagem:e.target.value}:x))} aria-label={`Em quem fica o plano ${k+1}`}><option value="">Quem fala</option>{atores.map(a=><option key={a.id} value={a.id}>{a.nome}</option>)}</select>}
   <select value={p.angulo||'normal'} onChange={e=>set(ps.map((x,j)=>j===k?{...x,angulo:e.target.value as Plano['angulo']}:x))} aria-label={`Ângulo do plano ${k+1}`}><option value="normal">De frente</option><option value="baixo">De baixo</option><option value="alto">De cima</option><option value="inclinado">Inclinado</option></select>
   <button className="icon-btn" onClick={()=>set(ps.filter((_,j)=>j!==k))} disabled={ps.length<2} aria-label="Tirar plano"><Trash2 size={14}/></button>
  </div>)}
  {ps.length<6&&<button className="link-btn" onClick={()=>set([...ps,{plano:'MS'}])}><Plus size={13}/> Plano</button>}</div>;
}

/** Direção das cenas de um projeto salvo: avisos de eixo/olhar, mapa de palco, prévia A/B e animatic. */
export default function Diretor({pid,cenas,salvar,mudar}:{pid:string;cenas:Cena[];salvar:()=>Promise<unknown>;mudar:(i:number,p:Partial<Cena>)=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const m=useServidor(c=>obterMapa(c,pid),0,[pid]);
  const [sel,setSel]=useState(0);
  const [trab,setTrab]=useState<{oque:'animatic'|'ab';etapa:string}|null>(null);
  const [video,setVideo]=useState<{url:string;info:Animatic}|null>(null);
  const [a,setA]=useState<Partial<Plano>[]>([]); const [b,setB]=useState<Partial<Plano>[]>([]);
  const [ab,setAb]=useState<{a:QuadroAB[];b:QuadroAB[]}|null>(null);
  const vivo=useRef(true); useEffect(()=>()=>{ vivo.current=false; },[]);
  const cena=cenas[sel]; const cm=m.dados?.cenas[sel];
  useEffect(()=>{ const ps:Partial<Plano>[]=(cena?.planos?.length?cena.planos:[{id:'p1',plano:'WS'} as Plano]).map(p=>({plano:p.plano,personagem:p.personagem||'',angulo:p.angulo,luz:p.luz,chaves:p.chaves}));
    setA(ps); setB(ps.length>1?ps.map((p,k)=>k===ps.length-1?{...p,plano:p.plano==='CU'?'MS':'CU'}:p):[...ps,{plano:'CU'}]); setAb(null); },[sel,pid]); // eslint-disable-line react-hooks/exhaustive-deps
  const an=m.dados?.animatic;
  useEffect(()=>{ if(!an||an.desatualizado||video?.info.asset===an.asset) return; assinarAsset(cfg,an.asset).then(u=>{ if(vivo.current) setVideo({url:urlServidor(cfg,u),info:an}); }).catch(()=>{}); },[an?.asset]); // eslint-disable-line react-hooks/exhaustive-deps

  async function rodar(oque:'animatic'|'ab'){
    setTrab({oque,etapa:'Salvando as cenas'});
    try{ await salvar();
      const r=oque==='animatic'?await pedirAnimatic(cfg,pid):await pedirAB(cfg,pid,sel,a,b);
      const e=await esperar(cfg,r.job,x=>setTrab({oque,etapa:`${x.etapa} (${Math.round(x.progresso)}%)`}),()=>!vivo.current);
      if(e.status!=='concluido'||!e.resultado) throw new Error(e.erro||'O celular não terminou a prévia.');
      if(oque==='animatic'){ const info=e.resultado as Animatic; setVideo({url:urlServidor(cfg,await assinarAsset(cfg,info.asset)),info}); m.recarregar(); }
      else setAb(e.resultado as {a:QuadroAB[];b:QuadroAB[]});
    }catch(er){ toast(erroTexto(er),'erro'); } finally{ if(vivo.current) setTrab(null); }
  }
  const avisos=m.dados?.avisos||[];
  const comAtores=!!m.dados?.cenas.some(c=>c.atores.length);
  return <section className="panel diretor">
   <div className="section-head"><h2><Clapperboard size={17}/> Direção: conferir antes de produzir</h2></div>
   <p className="hint">Prévias pequenas desenhadas pelo celular com o mesmo desenho do vídeo final, só que menores e com menos quadros. Servem para ver ritmo e enquadramento sem esperar o vídeo inteiro.</p>
   {avisos.length>0&&<ul className="diretor-avisos">{avisos.map((x,k)=><li key={k}><TriangleAlert size={14}/> <span>{x.descricao} <small>{x.correcao}</small></span></li>)}</ul>}

   <div className="row-gap left mt">
    <button className="primary" disabled={!!trab} onClick={()=>rodar('animatic')}>{trab?.oque==='animatic'?<Loader2 size={15} className="spin"/>:<Clapperboard size={15}/>} {video&&!an?.desatualizado?'Refazer o animatic':'Ver o animatic'}</button>
    {an?.desatualizado&&<small className="hint">As cenas mudaram depois do último animatic.</small>}
   </div>
   {trab&&<p className="hint mt"><Loader2 size={13} className="spin"/> {trab.etapa}</p>}
   {video&&<div className="diretor-animatic mt"><video src={video.url} controls playsInline className={'f'+(m.dados?.formato||'9:16').replace(':','x')}/>
    <small className="hint">Animatic de {video.info.duracao.toFixed(1)} s, {video.info.fps} quadros por segundo, feito em {Math.round(video.info.segundos_para_fazer)} s. Sem narração ainda: confira o tempo de cada cena e os cortes.</small></div>}

   <div className="diretor-cena mt">
    <label>Cena<select value={sel} onChange={e=>setSel(+e.target.value)}>{cenas.map((c,i)=><option key={c.id} value={i}>{i+1}. {(c.titulo||c.texto||'').slice(0,40)}</option>)}</select></label>
    {comAtores&&cm&&cm.atores.length>0&&<MapaPalco c={cm}/>}
    <div className="ab-editor">
     <div><b>A (como está)</b><ListaPlanos ps={a} set={setA} atores={cm?.atores||[]}/></div>
     <div><b>B (outra ideia)</b><ListaPlanos ps={b} set={setB} atores={cm?.atores||[]}/></div>
    </div>
    <button className="subtle" disabled={!!trab} onClick={()=>rodar('ab')}>{trab?.oque==='ab'?<Loader2 size={15} className="spin"/>:<Columns2 size={15}/>} Desenhar A e B</button>
    {ab&&<div className="ab-res mt">{(['a','b'] as const).map(k=><div key={k} className="ab-col"><b>{k.toUpperCase()}</b>
      <div className="ab-quadros">{ab[k].map((q,j)=><figure key={j}><img src={q.img} alt={`${k.toUpperCase()}, plano ${j+1}: ${NOME[q.plano]}`}/><figcaption>{j+1}. {NOME[q.plano]} · {q.t.toFixed(1)} s</figcaption></figure>)}</div>
      {k==='b'&&<button className="primary sm" onClick={()=>{ mudar(sel,{planos:b.map((p,j)=>({...p,id:'p'+(j+1),plano:(p.plano||'WS') as Plano['plano'],personagem:p.personagem||''}))}); toast('A cena agora usa os planos de B. Salve o rascunho para guardar.','ok'); }}>Usar B nesta cena</button>}
     </div>)}</div>}
   </div>
  </section>;
}
