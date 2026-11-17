import { useEffect, useRef, useState } from 'react';
import { Film, Gauge, Loader2, Search, Scissors } from 'lucide-react';
import { useApp } from '../state';
import { esperar } from '../lib/diretor';
import { ESTILOS } from '../lib/estilosVisuais';
import { compararModos, cortarDestaque, lerAnalise, lerModos, listarAnalises, mmss, novaHistoria, pedirAnalise, type Analise, type Comparacao, type Destaque, type Gancho } from '../lib/estudio3';
import { parseTime } from '../lib/store';
import { useCfg, useServidor, erroTexto } from './Servidor2';

const ORIGENS:[string,string][]=[['meu','É meu (eu gravei)'],['autorizado','Autorizado pelo dono'],['regra','Canal com regra pública de cortes']];
const TIPO:Record<string,string>={mudanca_de_cena:'cena',pico_de_audio:'som',fala_forte:'fala'};

/**
 * Gameplay Narrativa: acha os destaques de um vídeo de jogo pelo que dá para MEDIR (cena, som, fala), propõe ganchos que só citam
 * eventos que existem e corta o destaque escolhido. Nada é publicado: o corte passa pelo diretor de qualidade e espera a sua aprovação.
 */
export default function GameplayNarrativa({modelos}:{modelos:{id:string;nome:string}[]}){
  const {toast}=useApp(); const cfg=useCfg();
  const lista=useServidor(c=>listarAnalises(c),0,[]);
  const modos=useServidor(c=>lerModos(c),0,[]);
  const [f,setF]=useState({link:'',origem:'meu',nota:'',titulo:'',historia:'documentario',usar_ia:true});
  const [a,setA]=useState<Analise|null>(null);
  const [trab,setTrab]=useState('');
  const [escolha,setEscolha]=useState<Record<string,{gancho:number;ini:string;fim:string;modelo:string;estilo:string;modo:string}>>({});
  const [comp,setComp]=useState<Comparacao|null>(null);
  const vivo=useRef(true); useEffect(()=>()=>{ vivo.current=false; },[]);
  async function rodar(job:string,msg:string){
    const e=await esperar(cfg,job,x=>setTrab(`${msg} (${Math.round(x.progresso)}%)`),()=>!vivo.current);
    if(e.status!=='concluido') throw new Error(e.erro||'O celular não terminou.');
    return e;
  }
  async function analisar(){
    setTrab('Enviando o pedido'); try{
      const r=await pedirAnalise(cfg,f); const e=await rodar(r.job,'Analisando o vídeo (baixa, mede cenas e sons)');
      const id=(e.resultado as unknown as {id:string}).id; setA(await lerAnalise(cfg,id)); lista.recarregar();
    }catch(er){ toast(erroTexto(er),'erro'); } finally{ if(vivo.current) setTrab(''); }
  }
  async function abrir(id:string){ try{ setA(await lerAnalise(cfg,id)); setComp(null); }catch(er){ toast(erroTexto(er),'erro'); } }
  async function historia(h:string){ if(!a) return; setTrab('Refazendo os ganchos'); try{ setA(await novaHistoria(cfg,a.id,h)); }catch(er){ toast(erroTexto(er),'erro'); } finally{ setTrab(''); } }
  const esc=(d:Destaque)=>escolha[d.id]||{gancho:0,ini:mmss(d.ini),fim:mmss(d.fim),modelo:modelos[0]?.id||'',estilo:'',modo:''};
  const set=(d:Destaque,p:Partial<ReturnType<typeof esc>>)=>setEscolha(x=>({...x,[d.id]:{...esc(d),...p}}));
  async function cortar(d:Destaque){
    if(!a) return; const e=esc(d); const ini=parseTime(e.ini), fim=parseTime(e.fim);
    if(isNaN(ini)||isNaN(fim)||fim-ini<3) { toast('Confira o começo e o fim do corte (mínimo 3 segundos).','erro'); return; }
    setTrab('Cortando o destaque'); try{
      const r=await cortarDestaque(cfg,{gid:a.id,destaque:d.id,gancho:d.ganchos[e.gancho]||null,ini,fim,modelo:e.modelo,estilo:e.estilo||undefined,modo:e.modo||undefined});
      const x=await rodar(r.job,'Cortando o destaque'); const res=x.resultado as unknown as {status:string};
      toast(res.status==='pronto'?'Corte pronto. Ele está em “Cortes” esperando a sua aprovação.':'O diretor de qualidade reprovou este corte. Veja o motivo em “Cortes”.',res.status==='pronto'?'ok':'erro');
    }catch(er){ toast(erroTexto(er),'erro'); } finally{ if(vivo.current) setTrab(''); }
  }
  async function comparar(d:Destaque){
    if(!a) return; setTrab('Montando o mesmo corte nos dois modos'); try{
      const r=await compararModos(cfg,{gid:a.id,destaque:d.id,estilo:esc(d).estilo||undefined}); const x=await rodar(r.job,'Comparando os modos');
      setComp(x.resultado as unknown as Comparacao); modos.recarregar();
    }catch(er){ toast(erroTexto(er),'erro'); } finally{ if(vivo.current) setTrab(''); }
  }
  if(!cfg.servidor) return null;
  return <section className="panel gameplay">
    <div className="section-head"><h2><Film size={17}/> Gameplay Narrativa</h2></div>
    <p className="hint">Para vídeos de jogo de qualquer tipo. O celular mede mudanças de cena, picos de som e falas, mostra a linha do tempo e propõe ganchos que só falam de coisas que foram medidas. Nada é publicado sem a sua aprovação.</p>
    <div className="small-grid">
      <label>Link do vídeo<input value={f.link} placeholder="https://…" onChange={e=>setF({...f,link:e.target.value})}/></label>
      <label>De quem é o vídeo<select value={f.origem} onChange={e=>setF({...f,origem:e.target.value})}>{ORIGENS.map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label>
    </div>
    <div className="small-grid">
      <label>Título (opcional)<input value={f.titulo} maxLength={80} onChange={e=>setF({...f,titulo:e.target.value})}/></label>
      <label>História<select value={f.historia} onChange={e=>setF({...f,historia:e.target.value})}>{Object.entries(lista.dados?.historias||{documentario:'Documentário de gameplay'}).map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label>
    </div>
    <label>Permissão de uso (anote de onde vem)<input value={f.nota} maxLength={300} placeholder="Ex.: gravação minha / autorizado por Fulano em 10/11" onChange={e=>setF({...f,nota:e.target.value})}/></label>
    <label className="check"><input type="checkbox" checked={f.usar_ia} onChange={e=>setF({...f,usar_ia:e.target.checked})}/> Usar a IA para olhar alguns quadros e escrever os ganchos (sem isso a análise sai “parcial”)</label>
    <div className="row-gap left"><button className="primary" disabled={!!trab||!/^https?:\/\//.test(f.link)} onClick={analisar}>{trab?<Loader2 size={15} className="spin"/>:<Search size={15}/>} Analisar o vídeo</button>
      {(lista.dados?.analises||[]).length>0&&<select value={a?.id||''} onChange={e=>e.target.value&&abrir(e.target.value)} aria-label="Análises anteriores"><option value="">Abrir uma análise anterior…</option>{lista.dados!.analises.map(x=><option key={x.id} value={x.id}>{x.titulo||x.fonte.slice(0,40)} ({x.destaques} destaques)</option>)}</select>}</div>
    {trab&&<p className="hint mt"><Loader2 size={13} className="spin"/> {trab}</p>}
    {a&&<div className="mt">
      <p className="hint"><b>{a.titulo||'Análise'}</b> · fonte: {a.fonte} · direitos: {ORIGENS.find(o=>o[0]===a.direitos.origem)?.[1]}{a.direitos.nota?` (${a.direitos.nota})`:''} · {mmss(a.duracao)} de vídeo</p>
      <p className="hint">Medi {a.sinais.n_cenas} mudança(s) de cena, {a.sinais.n_picos} pico(s) de som e {a.sinais.n_falas} fala(s). Análise <b>{a.analise}</b>{a.analise==='parcial'?` (${a.analise_motivo}).`:'.'}</p>
      <label>História dos ganchos<select value={a.historia} disabled={!!trab} onChange={e=>historia(e.target.value)}>{Object.entries(a.historias).map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label>
      {a.destaques.map(d=>{ const e=esc(d); return <article key={d.id} className="gp-destaque">
        <b>Destaque {d.id.slice(1)}: {mmss(d.ini)} a {mmss(d.fim)}</b> <small className="hint">confiança {Math.round(d.confianca*100)}%</small>
        <p className="hint tight">{d.porque}</p>
        <div className="gp-eventos">{d.eventos.map(id=>a.eventos.find(x=>x.id===id)).filter(Boolean).map(x=><span key={x!.id}>• [{TIPO[x!.tipo]}] {x!.descricao}{x!.visual?` — nos quadros: ${x!.visual}`:''}</span>)}</div>
        {d.ganchos_aviso&&<p className="hint">{d.ganchos_aviso}</p>}
        {d.ganchos.map((g:Gancho,k:number)=><label key={k} className={'gp-gancho '+(e.gancho===k?'on':'')}><input type="radio" name={'g'+d.id} checked={e.gancho===k} onChange={()=>set(d,{gancho:k})}/> <b>“{g.abertura_falada}”</b><br/><small>Na tela: {g.texto_na_tela} · primeiro quadro em {mmss(g.primeiro_quadro_t)} · baseado em {g.eventos.join(', ')}. {g.justificativa}</small></label>)}
        <div className="small-grid">
          <label>Começa em<input value={e.ini} onChange={x=>set(d,{ini:x.target.value})}/></label>
          <label>Termina em<input value={e.fim} onChange={x=>set(d,{fim:x.target.value})}/></label>
        </div>
        <div className="small-grid">
          <label>Template<select value={e.modelo} onChange={x=>set(d,{modelo:x.target.value})}>{modelos.map(m=><option key={m.id} value={m.id}>{m.nome}</option>)}</select></label>
          <label>Estilo visual<select value={e.estilo} onChange={x=>set(d,{estilo:x.target.value})}><option value="">Do template</option>{ESTILOS.map(s=><option key={s.id} value={s.id}>{s.nome}</option>)}</select></label>
        </div>
        <label>Modo<select value={e.modo} onChange={x=>set(d,{modo:x.target.value})}><option value="">Padrão</option>{Object.entries(modos.dados?.modos||{}).map(([v,m])=><option key={v} value={v}>{m.nome}: {m.desc} {m.estimativa.segundos!==null?`(cerca de ${m.estimativa.segundos} s para 30 s de vídeo)`:'(tempo não medido)'}</option>)}</select></label>
        <div className="row-gap left"><button className="primary sm" disabled={!!trab} onClick={()=>cortar(d)}><Scissors size={13}/> Cortar este destaque</button>
          <button className="subtle sm" disabled={!!trab} onClick={()=>comparar(d)}><Gauge size={13}/> Comparar Rápido e Caprichado</button></div>
      </article>; })}
      {comp&&<div className="modo-comp mt">{Object.entries(comp).map(([k,m])=><div key={k} className="gp-destaque"><b>{m.nome}</b>
        <p className="hint tight">{m.segundos_de_render} s de trabalho · {(m.tamanho_bytes/1048576).toFixed(2)} MB · {m.duracao} s de vídeo{m.volume?` · volume ${m.volume.lufs} LUFS`:''}</p>
        <ul className="hint">{m.operacoes.map((o,i)=><li key={i}>{o}</li>)}</ul></div>)}</div>}
      <small className="hint">{a.aviso}</small>
    </div>}
  </section>;
}
