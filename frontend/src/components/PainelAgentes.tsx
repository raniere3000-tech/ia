import { useEffect, useState } from 'react';
import { Scissors, Send, Bot, Loader2, ArrowRight, AlertTriangle } from 'lucide-react';
import { useApp } from '../state';
import { useServidor } from './Servidor2';
import { verAgente, type VisaoAgente } from '../lib/agente';
import { lerFila, pendentes, listarProjetos, type Job } from '../lib/api';

const ATIVOS=['rodando','na_fila','agendado','aguardando_tentativa'];
const FAZENDO3:Record<string,string>={researching:'Escolhendo o assunto',narrating:'Narrando',generating_assets:'Buscando as imagens',rendering:'Montando o vídeo',assembling:'Juntando as cenas',validating:'Conferindo o vídeo'};

/** Os dados do agente de cortes e de postagem (lidos a cada 15 s enquanto a tela está aberta). */
export function useVisaoAgente(){
  const {settings}=useApp();
  const [v,setV]=useState<VisaoAgente|null>(null); const [erro,setErro]=useState('');
  useEffect(()=>{
    if(!settings.servidor) return;
    let vivo=true;
    const ler=()=>{ if(document.visibilityState!=='visible') return; verAgente(settings).then(x=>{ if(vivo){ setV(x); setErro(''); } }).catch(e=>{ if(vivo) setErro(e instanceof Error?e.message:String(e)); }); };
    ler(); const t=setInterval(ler,15000); return ()=>{ vivo=false; clearInterval(t); };
  },[settings]);
  return {v,erro};
}

type Linha={n:string;nome:string;Icon:typeof Bot;ligado:boolean|null;agora:string;ocupado:boolean;numeros:[number,string][];alerta?:string;ir:()=>void};

function Cartao({l}:{l:Linha}){
  return <button className={'ar-card'+(l.ocupado?' ocupado':'')} onClick={l.ir}>
    <div className="ar-topo"><l.Icon size={16}/><b>{l.n}</b><span className="ar-nome">{l.nome}</span>
      {l.ligado!==null&&<span className={'tag '+(l.ligado?'ok':'')}>{l.ligado?'Ligado':'Desligado'}</span>}</div>
    <p className="ar-agora">{l.ocupado&&<Loader2 size={13} className="spin"/>}{l.agora}</p>
    <div className="ar-nums">{l.numeros.map(([n,t])=><span key={t}><b>{n}</b>{t}</span>)}</div>
    {l.alerta&&<p className="ar-alerta"><AlertTriangle size={12}/> {l.alerta}</p>}
    <span className="ar-ir">Abrir <ArrowRight size={13}/></span>
  </button>;
}

/** Resumo curto dos três agentes: o que cada um faz agora e quantos processos tem. Tocar abre o agente. */
export default function PainelAgentes({titulo=true}:{titulo?:boolean}){
  const {go}=useApp();
  const {v,erro}=useVisaoAgente();
  const fila=useServidor(c=>lerFila(c),15);
  const pend=useServidor(pendentes,20);
  const proj=useServidor(c=>listarProjetos(c,'agente3'),30);
  const jobs:Job[]=fila.dados?.jobs||[];
  const ativos=(a:string)=>jobs.filter(j=>j.agente===a&&ATIVOS.includes(j.status));
  const cortes=(v?.cortes||[]).filter(c=>c.status!=='descartado');
  const co=v?.config.cortes, po=v?.config.postagem;
  const agendados=cortes.filter(c=>c.status==='agendado').sort((a,b)=>(a.quando||0)-(b.quando||0));
  const j1=ativos('agente1'), j3=ativos('agente3');
  const rodando3=j3.filter(j=>j.status==='rodando');
  const esperando3=(pend.dados?.pendentes||[]).length;
  const prontos3=(proj.dados?.projetos||[]).filter(p=>['ready_for_review','approved','queued_to_publish','posted'].includes(p.status)).length;
  const linhas:Linha[]=[
    {n:'Agente 1',nome:'Cortes',Icon:Scissors,ligado:co?co.ligado:null,ocupado:!!v?.atual.ocupado,
     agora:!v?'Lendo...':v.atual.ocupado?(v.atual.etapa||'Trabalhando'):co?.ligado?'Esperando a próxima busca':'Parado',
     numeros:[[j1.length+(v?.atual.ocupado&&!j1.some(j=>j.status==='rodando')?1:0),'na fila'],[v?.semana??0,'nesta semana'],[cortes.filter(c=>c.status==='pronto').length,'prontos']],
     ir:()=>go('agente','fila','radar')},
    {n:'Agente 2',nome:'Postagem',Icon:Send,ligado:po?po.ligado:null,ocupado:false,
     agora:agendados[0]?`Próximo post ${new Date((agendados[0].quando||0)*1000).toLocaleString('pt-BR',{weekday:'short',hour:'2-digit',minute:'2-digit'})}`:po?.ligado?'Nada agendado agora':'Parado',
     numeros:[[agendados.length,'agendados'],[cortes.filter(c=>c.status==='postado').length,'publicados'],[cortes.filter(c=>c.erros&&Object.keys(c.erros).length).length,'com erro']],
     ir:()=>go('agendar','','posts')},
    {n:'Agente 3',nome:'Vídeos com IA',Icon:Bot,ligado:null,ocupado:rodando3.length>0,
     agora:rodando3[0]?`${rodando3[0].titulo?.slice(0,40)||'Vídeo'}: ${rodando3[0].etapa||FAZENDO3.rendering}`:j3.length?'Vídeos esperando a vez na fila':'Parado',
     numeros:[[j3.length,'na fila'],[esperando3,'esperando você'],[prontos3,'prontos']],
     alerta:esperando3?`${esperando3} para você aprovar`:undefined,
     ir:()=>go('agente','agente3','radar')},
  ];
  return <section className="panel resumo-agentes">
    {titulo&&<div className="section-head"><h2><Bot size={18}/> Seus agentes</h2>{(fila.carregando)&&<Loader2 size={14} className="spin"/>}</div>}
    {(erro||fila.erro)&&<p className="hint bad"><AlertTriangle size={14}/> {erro||fila.erro}</p>}
    <div className="ar-grade">{linhas.map(l=><Cartao key={l.n} l={l}/>)}</div>
  </section>;
}
