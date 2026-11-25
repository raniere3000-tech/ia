import { useState } from 'react';
import { Copy, History, Plus, Save, Trash2, UserCircle2 } from 'lucide-react';
import { useApp } from '../state';
import { ESTILOS } from '../lib/estilosVisuais';
import { acaoPerfil, lerPerfil, listarPerfis, PERFIL_VAZIO, resolverPerfil, salvarPerfil, validarPerfil, type Perfil, type PerfilCampos } from '../lib/estudio3';
import { useCfg, useServidor, erroTexto } from './Servidor2';

const REDES=['youtube','instagram','tiktok','facebook','kwai'];
const lista=(t:string)=>t.split(/[,\n]/).map(x=>x.trim()).filter(Boolean);

/**
 * Perfis de canal: a identidade de cada página. Camadas: padrão do site < perfil < projeto < corte. Um corte usa UM perfil, sem misturar
 * voz, logo, cores ou redes de perfis diferentes. O servidor tem uma conta por rede: o perfil escolhe quais redes usar.
 */
export default function Perfis({atual,escolher,modelos}:{atual:string;escolher:(id:string)=>void;modelos:{id:string;nome:string}[]}){
  const {toast}=useApp(); const cfg=useCfg();
  const ps=useServidor(c=>listarPerfis(c),0,[]);
  const [ed,setEd]=useState<(PerfilCampos&{id?:string;versao?:number;historico?:Perfil['historico']})|null>(null);
  const [info,setInfo]=useState<{problemas:string[];origem:Record<string,string>}|null>(null);
  async function abrir(id:string){ try{ const p=await lerPerfil(cfg,id); setEd(p); const [v,r]=await Promise.all([validarPerfil(cfg,id),resolverPerfil(cfg,id)]); setInfo({problemas:v.problemas,origem:r.origem}); }catch(e){ toast(erroTexto(e),'erro'); } }
  async function salvar(){ if(!ed) return; try{ const p=await salvarPerfil(cfg,ed); setEd(p); ps.recarregar(); toast(`Perfil salvo (versão ${p.versao}).`,'ok'); const v=await validarPerfil(cfg,p.id); setInfo(i=>({origem:i?.origem||{},problemas:v.problemas})); }catch(e){ toast(erroTexto(e),'erro'); } }
  async function acao(a:'duplicar'|'apagar'|'restaurar',extra?:{versao:number}){ if(!ed?.id) return; if(a==='apagar'&&!confirm('Apagar este perfil? Os cortes já feitos continuam com o que foi aplicado.')) return;
    try{ const r=await acaoPerfil(cfg,ed.id,a,extra); ps.recarregar(); if(a==='apagar'){ setEd(null); if(atual===ed.id) escolher(''); } else setEd(r); }catch(e){ toast(erroTexto(e),'erro'); } }
  if(!cfg.servidor) return null;
  const up=<K extends keyof PerfilCampos>(k:K,v:PerfilCampos[K])=>setEd(e=>e?{...e,[k]:v}:e);
  return <section className="panel perfis">
    <div className="section-head"><h2><UserCircle2 size={17}/> Produzindo para: perfil do canal</h2></div>
    <div className="row-gap left">
      <select value={atual} onChange={e=>escolher(e.target.value)} aria-label="Perfil usado pelo Agente 1"><option value="">Sem perfil (padrão do site)</option>{(ps.dados?.perfis||[]).map(p=><option key={p.id} value={p.id}>{p.nome}</option>)}</select>
      <button className="subtle sm" onClick={()=>{ setEd({...PERFIL_VAZIO}); setInfo(null); }}><Plus size={13}/> Novo perfil</button>
      {(ps.dados?.perfis||[]).map(p=><button key={p.id} className="link-btn" onClick={()=>abrir(p.id)}>{p.nome}</button>)}
    </div>
    <small className="hint">O Agente 1 e o Gameplay usam o perfil escolhido: templates, cor, logo, estilos, hashtags base, redes de destino e modo. Camadas: padrão do site &lt; perfil &lt; projeto &lt; corte. Um perfil nunca herda nada de outro.</small>
    {ed&&<div className="mt">
      {info&&info.problemas.length>0&&<ul className="diretor-avisos">{info.problemas.map((x,k)=><li key={k}>⚠ {x}</li>)}</ul>}
      <div className="small-grid"><label>Nome do canal<input value={ed.nome} maxLength={40} onChange={e=>up('nome',e.target.value)}/></label><label>Nicho<input value={ed.nicho} onChange={e=>up('nicho',e.target.value)}/></label></div>
      <div className="small-grid"><label>Público<input value={ed.publico} onChange={e=>up('publico',e.target.value)}/></label><label>Tom de voz<input value={ed.tom} onChange={e=>up('tom',e.target.value)}/></label></div>
      <div className="small-grid"><label>Cor da marca<input type="color" value={ed.cores.primaria||'#7758ef'} onChange={e=>up('cores',{...ed.cores,primaria:e.target.value})}/></label>
        <label>Modo de montagem<select value={ed.modo_qualidade} onChange={e=>up('modo_qualidade',e.target.value as PerfilCampos['modo_qualidade'])}><option value="">Padrão do site</option><option value="rapido">Rápido</option><option value="caprichado">Caprichado</option></select></label></div>
      <span className="field-label">Templates do canal</span>
      <div className="chips">{modelos.map(m=><button key={m.id} type="button" className={'chip '+(ed.templates.includes(m.id)?'on':'')} onClick={()=>up('templates',ed.templates.includes(m.id)?ed.templates.filter(x=>x!==m.id):[...ed.templates,m.id].slice(0,3))}>{m.nome}</button>)}</div>
      {ps.dados?.dna_corte_habilitado&&<fieldset className="mt"><legend>DNA dos cortes</legend>
        <small className="hint">Usa os templates e a cor do canal acima. O ritmo muda a quantidade de palavras por bloco da legenda, preservando a velocidade da fala.</small>
        <div className="small-grid">
          <label>Fonte<select value={ed.dna_corte?.fonte||''} onChange={e=>up('dna_corte',{...ed.dna_corte,fonte:(e.target.value||undefined) as 'Inter'|undefined})}><option value="">Do template</option><option value="Inter">Inter (incluída no servidor)</option></select></label>
          <label>Legenda<select value={ed.dna_corte?.legenda||''} onChange={e=>up('dna_corte',{...ed.dna_corte,legenda:(e.target.value||undefined) as NonNullable<PerfilCampos['dna_corte']>['legenda']})}><option value="">Do template</option><option value="destaque">Palavra em destaque</option><option value="simples">Simples</option><option value="caixa">Caixa</option><option value="nenhuma">Sem legenda</option></select></label>
          <label>Zoom<input type="number" min={1} max={1.6} step={.05} placeholder="Do template" value={ed.dna_corte?.zoom??''} onChange={e=>up('dna_corte',{...ed.dna_corte,zoom:e.target.value===''?undefined:Number(e.target.value)})}/></label>
          <label>Ritmo da legenda<select value={ed.dna_corte?.ritmo||''} onChange={e=>up('dna_corte',{...ed.dna_corte,ritmo:(e.target.value||undefined) as NonNullable<PerfilCampos['dna_corte']>['ritmo']})}><option value="">Do template</option><option value="calmo">Calmo (até 4 palavras)</option><option value="padrao">Padrão (até 3 palavras)</option><option value="dinamico">Dinâmico (até 2 palavras)</option></select></label>
        </div></fieldset>}
      <span className="field-label mt">Estilos visuais permitidos</span>
      <div className="chips">{ESTILOS.map(s=><button key={s.id} type="button" className={'chip '+(ed.estilos_permitidos.includes(s.id)?'on':'')} onClick={()=>up('estilos_permitidos',ed.estilos_permitidos.includes(s.id)?ed.estilos_permitidos.filter(x=>x!==s.id):[...ed.estilos_permitidos,s.id])}>{s.nome}</button>)}</div>
      <span className="field-label mt">Redes de destino (só as conectadas em Postagem funcionam)</span>
      <div className="chips">{REDES.map(r=><button key={r} type="button" className={'chip '+(ed.redes.includes(r)?'on':'')} onClick={()=>up('redes',ed.redes.includes(r)?ed.redes.filter(x=>x!==r):[...ed.redes,r])}>{r}</button>)}</div>
      <label className="mt">Hashtags base (separe por vírgula)<input defaultValue={ed.hashtags_base.join(', ')} onBlur={e=>up('hashtags_base',lista(e.target.value))}/></label>
      <label>Temas frequentes (separe por vírgula)<input defaultValue={ed.temas_frequentes.join(', ')} onBlur={e=>up('temas_frequentes',lista(e.target.value))}/></label>
      <label>Regras de marca<textarea rows={3} value={ed.regras_de_marca} onChange={e=>up('regras_de_marca',e.target.value)}/></label>
      <label>Política de fonte (nota)<input value={ed.politica_fonte.nota} onChange={e=>up('politica_fonte',{...ed.politica_fonte,nota:e.target.value})}/></label>
      <div className="row-gap left"><button className="primary sm" onClick={salvar}><Save size={13}/> Salvar perfil</button>
        {ed.id&&<><button className="subtle sm" onClick={()=>acao('duplicar')}><Copy size={13}/> Duplicar</button><button className="subtle sm danger" onClick={()=>acao('apagar')}><Trash2 size={13}/> Apagar</button></>}</div>
      {ed.id&&ed.historico&&ed.historico.length>1&&<details className="mt"><summary><History size={13}/> Versões ({ed.versao} agora)</summary><ul className="hint">{[...ed.historico].reverse().map(h=><li key={h.versao}>v{h.versao}: {h.o_que} <button className="link-btn" disabled={h.versao===ed.versao} onClick={()=>acao('restaurar',{versao:h.versao})}>voltar para esta</button></li>)}</ul></details>}
      {info&&<small className="hint">Camadas: {Object.entries(info.origem).filter(([,o])=>o==='perfil').map(([k])=>k).join(', ')||'nenhum campo definido'} vêm deste perfil; o resto, do padrão do site.</small>}
      <small className="hint">Logo, elenco, séries e conta do Meta por perfil existem no servidor; a tela deles ainda não foi feita.</small>
    </div>}
  </section>;
}
