import { useState } from 'react';
import { CheckCircle2, Circle, Loader2, Play, Lightbulb, AlertTriangle } from 'lucide-react';
import { useApp } from '../state';
import { store } from '../lib/store';
import { useCfg, useServidor, erroTexto } from './Servidor2';
import { catalogo, novoVideo, ideias as pedirIdeias, type Briefing, type Catalogo, type Ideia } from '../lib/api';

/** O que falta no servidor para o Agente 3 fazer vídeos, com o botão que leva ao lugar certo. Some quando está tudo pronto. */
export function Prontidao({cat}:{cat:Catalogo|null}){
  const {go}=useApp();
  const r=cat?.requisitos;
  if(!r) return null;
  const itens:{ok:boolean;t:string;d:string;obrig:boolean;btn:string;ir:()=>void}[]=[
    {ok:r.ffmpeg,t:'FFmpeg no celular',d:'É ele que monta o vídeo. No Termux: pkg install -y ffmpeg',obrig:true,btn:'Ver diagnóstico',ir:()=>go('config')},
    {ok:r.gemini,t:'Chave do Gemini no servidor',d:'A IA escreve o roteiro e narra com ela. É grátis.',obrig:true,btn:'Colar a chave',ir:()=>go('agente','avisos','radar')},
    {ok:r.email,t:'E-mail de avisos',d:'Para receber o vídeo pronto e aprovar respondendo o e-mail.',obrig:false,btn:'Configurar e-mail',ir:()=>go('agente','avisos','radar')},
    {ok:r.pexels,t:'Chave de fotos (Pixabay ou Pexels)',d:'Deixa o vídeo bem mais bonito: uma foto boa em cada cena. Grátis. Sem ela, o servidor acha bem menos fotos.',obrig:false,btn:'Colar a chave',ir:()=>go('agente','avisos','radar')},
  ];
  const faltam=itens.filter(i=>!i.ok);
  if(!faltam.length) return null;
  const trava=faltam.some(i=>i.obrig);
  return <section className={'panel prontidao'+(trava?' trava':'')}>
    <div className="section-head"><h2>{trava?<AlertTriangle size={17}/>:<CheckCircle2 size={17}/>} {trava?'Falta pouco para criar vídeos':'Pronto para criar. Para ficar melhor:'}</h2></div>
    <div className="check-list">{itens.filter(i=>!i.ok||trava).map(i=><div key={i.t} className={'check-item '+(i.ok?'ok':'')}>{i.ok?<CheckCircle2 size={20}/>:<Circle size={20}/>}
      <div><strong>{i.t}</strong><p>{i.d}</p></div>
      {i.ok?<span className="tag ok">Pronto</span>:<><span className={'tag '+(i.obrig?'warn':'')}>{i.obrig?'Obrigatório':'Opcional'}</span><button className="subtle sm" onClick={i.ir}>{i.btn}</button></>}</div>)}</div>
  </section>;
}

const DURACOES:[number,string][]=[[30,'30 s'],[45,'45 s'],[60,'1 min'],[90,'1 min e meio']];
type Rapido={estilo:string;duracao:number;voz:string;conferir:boolean};

/** Jeito rápido: um tema e um botão. O servidor escreve o roteiro, busca as fotos, narra e monta. */
export function CriarRapido({compacto=false}:{compacto?:boolean}){
  const {toast,go}=useApp(); const cfg=useCfg();
  const cat=useServidor(catalogo);
  const [tema,setTema]=useState('');
  const [op,setOp]=useState<Rapido>(()=>{ const g=store.json<Partial<Rapido>&{v?:number}>('studio_criar_rapido',{});
    // versão 2: o visual padrão passou a ser o documentário com fotos reais (o antigo ficava com cara de desenho simples)
    return {duracao:45,voz:'Puck',conferir:false,...g,estilo:g.v===2&&g.estilo?g.estilo:'documentario'}; });
  const mudar=(p:Partial<Rapido>)=>setOp(o=>{ const n={...o,...p}; store.setJson('studio_criar_rapido',{...n,v:2}); return n; });
  const [ideias,setIdeias]=useState<Ideia[]>([]);
  const [busy,setBusy]=useState('');
  const r=cat.dados?.requisitos;
  const pode=!!cat.dados&&(!r||(r.ffmpeg&&r.gemini));
  const estilos=(cat.dados?.estilos||[]).filter(e=>e.servidor&&!e.precisa_imagem);
  const criar=async()=>{
    setBusy('criar');
    try{
      const b:Partial<Briefing>={tema:tema.trim(),nicho:'Curiosidades',tipo:'curiosidades',duracao_alvo:op.duracao,cenas_qtd:Math.max(4,Math.round(op.duracao/7)),formato:'9:16',
        estilo:op.estilo,voz:op.voz,imagens:'busca',modo_aprovacao:op.conferir?'assistido':'supervisionado',destinos:{redes:[],quando:'proximo'}};
      const p=await novoVideo(cfg,{briefing:b,produzir:true,quando:'agora',modo:'ia'});
      toast('Começou! O celular está fazendo o vídeo. Pode fechar o site: chega um e-mail quando ficar pronto.','ok');
      setTema(''); go('revisar',p.id,'fila');
    }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); }
  };
  const sugerir=async()=>{ setBusy('ideias'); try{ const x=await pedirIdeias(cfg,{nicho:tema.trim()||'Curiosidades',tema:'',quantidade:6}); setIdeias(x.ideias); if(!x.ideias.length) toast('A IA não trouxe ideias agora. Tente de novo.','info'); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } };
  return <section className="panel criar-rapido">
    <div className="section-head"><h2><Play size={17}/> Criar um vídeo agora</h2></div>
    <p className="subtitle">Escreva o assunto e toque em Criar. O celular escreve o roteiro, busca as fotos, narra e monta o vídeo sozinho. Você só assiste e aprova no final.</p>
    <label>Sobre o que é o vídeo?<input value={tema} onChange={e=>setTema(e.target.value)} placeholder="Ex.: Por que o céu é azul?" onKeyDown={e=>{ if(e.key==='Enter'&&tema.trim().length>2&&pode&&!busy) criar(); }}/></label>
    {ideias.length>0&&<div className="ideias">{ideias.map(x=><button key={x.titulo} className={'ideia'+(tema===x.titulo?' on':'')} onClick={()=>setTema(x.titulo)}><b>{x.titulo}</b><small>{x.gancho||x.porque}</small></button>)}</div>}
    {!compacto&&<>
     <div className="field-label">Duração</div>
     <div className="chips">{DURACOES.map(([s,n])=><button key={s} className={'chip '+(op.duracao===s?'on':'')} onClick={()=>mudar({duracao:s})}>{n}</button>)}</div>
     <div className="small-grid mt">
      <label>Visual<select value={op.estilo} onChange={e=>mudar({estilo:e.target.value})}>{(estilos.length?estilos:[{id:op.estilo,nome:'Documentário (fotos reais)',status:'operacional'}]).map(e=><option key={e.id} value={e.id}>{e.nome}{e.status==='beta'?' (em teste)':''}</option>)}</select></label>
      <label>Voz<select value={op.voz} onChange={e=>mudar({voz:e.target.value})}>{(cat.dados?.vozes||['Puck']).map(v=><option key={v}>{v}</option>)}</select></label>
     </div>
     <label className="check mt"><input type="checkbox" checked={op.conferir} onChange={e=>mudar({conferir:e.target.checked})}/> Quero ler e aprovar o roteiro antes de o vídeo ser feito</label>
    </>}
    <div className="row-gap left mt">
     <button className="primary lg" disabled={!!busy||tema.trim().length<3||!pode} onClick={criar}>{busy==='criar'?<Loader2 size={16} className="spin"/>:<Play size={16}/>} Criar meu vídeo</button>
     <button className="subtle" disabled={!!busy||!pode} onClick={sugerir}>{busy==='ideias'?<Loader2 size={15} className="spin"/>:<Lightbulb size={15}/>} Sem ideia? Sugerir assuntos</button>
    </div>
    {cat.erro&&<p className="hint bad">{cat.erro}</p>}
    {cat.dados&&!pode&&<p className="hint bad">Ainda falta configurar o servidor (veja a lista acima).</p>}
    {compacto&&<button className="link-btn mt" onClick={()=>go('ia','','criar')}>Escolher duração, visual e voz</button>}
  </section>;
}

const PASSOS:[string,string,string[]][]=[
  ['Roteiro','A IA escreve as cenas',['queued','scheduled','draft','researching','script_ready','storyboard_ready','waiting_brief_approval']],
  ['Narração','A voz grava cada cena',['narrating']],
  ['Imagens','Busca e remodela as fotos',['generating_assets']],
  ['Montagem','O celular desenha o vídeo',['rendering','assembling','validating']],
  ['Pronto','Você assiste e decide',['ready_for_review','approved','queued_to_publish','posted','changes_requested','rejected']],
];
/** Em que passo a produção está, em linguagem simples. */
export function Etapas({status,detalhe}:{status:string;detalhe?:string}){
  const atual=PASSOS.findIndex(p=>p[2].includes(status));
  if(atual<0) return null;
  const fim=atual===PASSOS.length-1;
  return <div className="etapas" role="list" aria-label="Andamento do vídeo">
    {PASSOS.map(([t,d],i)=><div key={t} role="listitem" className={'etapa '+(i<atual||fim?'feita':i===atual?'atual':'')}>
      <span className="etapa-bola">{i<atual||fim?<CheckCircle2 size={16}/>:i===atual?<Loader2 size={16} className={status==='waiting_brief_approval'?'':'spin'}/>:<Circle size={16}/>}</span>
      <b>{t}</b><small>{i===atual&&!fim&&detalhe?detalhe:d}</small></div>)}
  </div>;
}
