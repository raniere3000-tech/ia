import { useCallback, useEffect, useRef, useState } from 'react';
import { api, type CfgSrv } from './api';
import { lerAgentes, type AgenteInfo } from './coordenador';

/** Painel do Início e da Central de Agentes: o que o servidor mediu (GET /api/v1/dashboard/resumo). null = o servidor não sabe. */
export type Periodo='hoje'|'7d'|'30d';
export const PERIODOS:[Periodo,string][]=[['hoje','Hoje'],['7d','7 dias'],['30d','30 dias']];
export type AtualJob={job:string;titulo:string;progresso:number;etapa:string;restante_s:number|null;desde:number};
export type AgenteResumo={id:string;estado:string|null;atual:AtualJob[];na_fila:number|null;concluidas_periodo:number|null;falhas_periodo:number|null;
  tempo_ativo_s:number|null;tempos_medios:Record<string,{segundos:number;amostras:number}>;unidade?:string;ordens_ativas?:number|null;esperando_voce?:number|null;modo?:string|null};
export type Resumo={gerado_em:number;periodo:Periodo;inicio:number;backend_disponivel:boolean;esteira_ligada:boolean|null;
  totais:{videos_criados:number|null;videos_por_origem:{agente1:number|null;agente3:number|null};aprovados_disponiveis:number|null;agendados:number|null;publicados:number|null;
    em_producao:number|null;esperando_decisao:number|null;falhas:number|null;posts_com_erro:number|null};
  definicoes:Record<string,string>;agentes:AgenteResumo[];
  proxima_publicacao:{post:string;titulo:string;quando:number;redes:string[];status:string}|null;
  alertas:{tipo:string;texto:string;onde:string}[];
  /** true quando o servidor ainda não tem o painel novo e os dados vieram só do Coordenador (sem contagem por período). */
  parcial?:boolean};

export const lerResumo=(c:CfgSrv,p:Periodo)=>api<Resumo>(c,'GET',`/api/v1/dashboard/resumo?periodo=${p}`);

/** Servidor antigo (sem o painel): monta o que dá a partir do Coordenador, deixando o resto como "não disponível". */
function deAgentes(ags:AgenteInfo[],p:Periodo):Resumo{
  const n=null;
  return {gerado_em:Date.now()/1000,periodo:p,inicio:0,backend_disponivel:true,esteira_ligada:n,parcial:true,definicoes:{},proxima_publicacao:n,alertas:[],
    totais:{videos_criados:n,videos_por_origem:{agente1:n,agente3:n},aprovados_disponiveis:n,agendados:n,publicados:n,em_producao:n,esperando_decisao:n,falhas:n,posts_com_erro:n},
    agentes:ags.map(a=>({id:a.id,estado:a.estado,atual:a.atual||[],na_fila:a.na_fila??n,concluidas_periodo:n,falhas_periodo:n,tempo_ativo_s:n,
      tempos_medios:(a as unknown as {tempos_medios?:AgenteResumo['tempos_medios']}).tempos_medios||{},
      ordens_ativas:(a as unknown as {ordens_ativas?:number}).ordens_ativas??n,esperando_voce:(a as unknown as {esperando_voce?:number}).esperando_voce??n,
      modo:(a as unknown as {modo?:string}).modo??n}))};
}

// Última resposta boa de cada servidor (só nesta aba do navegador): mostrada com a hora quando o servidor some.
const ULTIMO=new Map<string,Resumo>();

/** Lê o painel a cada `seg` segundos com a tela visível. Troca de servidor descarta respostas atrasadas do anterior. */
export function useResumo(cfg:CfgSrv,periodo:Periodo,seg=30){
  const chave=cfg.servidor+'|'+periodo;
  const [dados,setDados]=useState<Resumo|null>(()=>ULTIMO.get(chave)||null);
  const [erro,setErro]=useState('');
  const [carregando,setCarregando]=useState(false);
  const [antigo,setAntigo]=useState(false);
  const pedido=useRef(0);
  const ler=useCallback(async()=>{
    if(!cfg.servidor) return;
    const meu=++pedido.current; setCarregando(true);
    try{
      let r:Resumo;
      try{ r=await lerResumo(cfg,periodo); }
      catch(e){ if(!/rota não encontrada|404/i.test(String(e instanceof Error?e.message:e))) throw e; r=deAgentes((await lerAgentes(cfg)).agentes,periodo); }
      if(meu!==pedido.current) return;
      ULTIMO.set(chave,r); setDados(r); setErro(''); setAntigo(false);
    }catch(e){
      if(meu!==pedido.current) return;
      setErro(e instanceof Error?e.message:String(e)); setAntigo(!!ULTIMO.get(chave)); setDados(ULTIMO.get(chave)||null);
    }finally{ if(meu===pedido.current) setCarregando(false); }
  },[cfg,periodo,chave]);
  useEffect(()=>{
    setDados(ULTIMO.get(chave)||null); setErro(''); setAntigo(false);
    ler(); if(!seg) return;
    const iv=setInterval(()=>{ if(document.visibilityState==='visible') ler(); },seg*1000);
    return ()=>{ clearInterval(iv); pedido.current++; };
  },[ler,seg,chave]);
  return {dados,erro,carregando,antigo,recarregar:ler};
}

export const AGENTES_INFO:Record<string,{n:number;nome:string;funcao:string}>={
  agente1:{n:1,nome:'Radar e Cortes',funcao:'Acha vídeos dos canais aprovados e faz os cortes'},
  agente2:{n:2,nome:'Publicador',funcao:'Agenda e posta nas redes, só com o que foi aprovado'},
  agente3:{n:3,nome:'Criador Original',funcao:'Cria vídeos com IA a partir de um assunto'},
  agente4:{n:4,nome:'Diretor de Qualidade',funcao:'Dá nota de 0 a 100 e só aprova o que passa'},
  agente5:{n:5,nome:'Editor Inteligente',funcao:'Edita, corrige e exporta o vídeo'},
  agente6:{n:6,nome:'Thumbnails',funcao:'Faz as capas a partir de quadros reais do vídeo'},
  agente7:{n:7,nome:'Coordenador-Geral',funcao:'Recebe seus pedidos e coordena os outros seis'},
};
export const ESTADO_AGENTE:Record<string,[string,string]>={trabalhando:['Trabalhando','info'],na_fila:['Com fila','info'],parado:['Parado',''],coordenando:['Coordenando','info']};

/** "Não disponível" quando o servidor não sabe (nunca troca null por 0). */
export const nd=(v:number|null|undefined,f:(x:number)=>string=String)=>v==null?'Não disponível':f(v);
