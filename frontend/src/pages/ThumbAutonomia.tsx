// Agente 6 > Autonomia e Integração de Capas: como o Agente 6 trabalha sozinho, o que precisa de você e a capa em cada post/rede.
import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw, ShieldCheck, Wrench } from 'lucide-react';
import { useApp } from '../state';
import { useCfg, useServidor, erroTexto } from '../components/Servidor2';
import { ESTADO_CAPA, auditarEstoque, cancelarJob, ignorarVideo, lerAutonomia, reenviarCapa, salvarCfgThumb,
  type Auditoria, type CfgThumb, type Estrategia } from '../lib/thumbnails';

const REDES=['youtube','tiktok','instagram','facebook','kwai'];
const NOME:Record<string,string>={youtube:'YouTube',tiktok:'TikTok',instagram:'Instagram',facebook:'Facebook',kwai:'Kwai'};
const quando=(t?:number|null)=>t?new Date(t*1000).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'';

export default function ThumbAutonomia({abrir}:{abrir:(id:string)=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const r=useServidor(c=>lerAutonomia(c),20);
  const [c,setC]=useState<CfgThumb|null>(null); const [busy,setBusy]=useState('');
  const [aud,setAud]=useState<Auditoria|null>(null);
  useEffect(()=>{ if(r.dados&&!c) setC(r.dados.config); },[r.dados,c]);
  if(r.erro&&!r.dados) return <section className="panel"><p className="hint bad">{/rota não encontrada/i.test(r.erro)?
    <>O servidor do celular ainda não tem esta tela. No Termux rode <code>cd ~/ia &amp;&amp; git pull</code> e reinicie o servidor.</>:r.erro}</p></section>;
  if(!r.dados||!c) return <section className="panel"><p className="muted"><Loader2 size={14} className="spin"/> Carregando…</p></section>;
  const d=r.dados; const n=d.numeros;
  const m=(p:Partial<CfgThumb>)=>setC({...c,...p});
  async function acao(nome:string,f:()=>Promise<unknown>,ok:string){ setBusy(nome); try{ await f(); toast(ok,'ok'); r.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } }
  async function salvar(){ setBusy('salvar'); try{ setC(await salvarCfgThumb(cfg,c!)); toast('Configurações salvas no servidor.','ok'); r.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } }
  async function auditar(aplicar:boolean){ setBusy(aplicar?'aplicar':'simular'); try{ setAud(await auditarEstoque(cfg,aplicar)); if(aplicar) r.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } }
  const exige=(rede:string)=>c.exigir_capa&&c.redes_exigem_capa.includes(rede);
  const setExige=(rede:string,v:boolean)=>m({redes_exigem_capa:v?[...new Set([...c.redes_exigem_capa,rede])]:c.redes_exigem_capa.filter(x=>x!==rede),
    ...(rede==='youtube'?{exigir_capa_youtube:v}:{})});

  return <>
    <section className="panel"><h3><ShieldCheck size={16}/> Autonomia e Integração de Capas</h3>
      <p className="hint">O Agente 6 faz {c.variantes_padrao} capas por vídeo, o diretor dá nota, e no automático ele escolhe a melhor aprovada (nota mínima {c.nota_min}).
        Você só entra nas exceções. Números dos últimos {d.dias} dias, lidos do servidor.</p>
      <div className="thumb-grade">
        <div className="field"><span>Taxa real de autonomia</span><b style={{fontSize:22}}>{d.taxa_autonomia==null?'sem dados ainda':`${d.taxa_autonomia}%`}</b>
          <small className="muted">{n.escolhidas_automatico} de {n.capas_escolhidas} capas escolhidas sem você</small></div>
        <div className="field"><span>Capas geradas</span><b style={{fontSize:22}}>{n.capas_geradas}</b><small className="muted">{n.capas_aprovadas} aprovadas pelo diretor</small></div>
        <div className="field"><span>Capas usadas nos posts</span><b style={{fontSize:22}}>{n.capas_usadas}</b>
          <small className="muted">{n.capas_aplicadas_confirmadas} confirmadas · {n.capas_manual_no_app} no app · {n.capas_falharam} falharam</small></div>
        <div className="field"><span>Posts sem capa</span><b style={{fontSize:22}} className={n.posts_sem_capa?'bad':''}>{n.posts_sem_capa}</b>
          <small className="muted">esperando o Agente 6</small></div>
      </div>
    </section>

    <section className="panel"><h3><AlertTriangle size={16}/> Precisa de você ({d.pendencias.length})</h3>
      {!d.pendencias.length?<p className="muted"><CheckCircle2 size={14}/> Nada esperando você.</p>:
      <ul className="thumb-redes">{d.pendencias.map(p=><li key={p.origem+p.referencia}><b>{p.titulo}</b><br/><small className="muted">{p.motivo}</small>
        <div className="row-gap left">
          {p.job&&<button className="subtle sm" onClick={()=>abrir(p.job!)}>Abrir e escolher/substituir</button>}
          {p.job&&<button className="subtle sm" disabled={!!busy} onClick={()=>acao('canc'+p.job,()=>cancelarJob(cfg,p.job!),'Pedido cancelado.')}>Cancelar pedido</button>}
          <button className="subtle sm" disabled={!!busy} onClick={()=>acao('ign'+p.referencia,()=>ignorarVideo(cfg,p.origem,p.referencia),'O Agente 6 vai ignorar este vídeo.')}>Ignorar este vídeo</button>
        </div></li>)}</ul>}
      {d.a_fazer.criar+d.a_fazer.escolher>0&&<p className="hint">Na próxima passada o Agente 6 vai pedir capa para {d.a_fazer.criar} vídeo(s) e escolher para {d.a_fazer.escolher}.</p>}
      {Object.keys(d.ignorados).length>0&&<><h4>Ignorados por você</h4><ul>{Object.entries(d.ignorados).map(([k,x])=><li key={k}>{k} <small className="muted">{quando(x.t)}</small>{' '}
        <button className="link-btn" onClick={()=>{ const [o,...ref]=k.split(':'); acao('vol'+k,()=>ignorarVideo(cfg,o as 'corte',ref.join(':'),false),'Voltou para a recuperação automática.'); }}>voltar ao automático</button></li>)}</ul></>}
    </section>

    <section className="panel"><h3>Capa em cada post e rede</h3>
      {!d.aplicacoes.length?<p className="muted">Nenhum post com capa registrada ainda.</p>:
      <ul className="thumb-redes">{d.aplicacoes.map(a=>{ const [t,cl]=ESTADO_CAPA[a.estado]||[a.estado,''];
        return <li key={a.post+a.rede}><b>{a.titulo||a.post}</b> · {NOME[a.rede]||a.rede} <span className={'tag '+cl}>{t}</span>
          {a.tentativas>1&&<small className="muted"> {a.tentativas} tentativas</small>}
          {a.erro&&<><br/><small className="muted">{a.erro}</small></>}
          {a.rede==='youtube'&&a.estado!=='aplicada'&&<div className="row-gap left"><button className="subtle sm" disabled={!!busy}
            onClick={()=>acao('re'+a.post,()=>reenviarCapa(cfg,a.post),'Pedi ao YouTube para trocar só a capa.')}>Reenviar só a capa</button></div>}</li>; })}</ul>}
      {d.posts_sem_capa.length>0&&<><h4>Agendados ainda sem capa</h4><ul>{d.posts_sem_capa.map(p=><li key={p.post}>{p.titulo||p.post} · {p.redes.map(x=>NOME[x]||x).join(', ')} <small className="muted">{quando(p.quando)}</small></li>)}</ul></>}
    </section>

    <section className="panel"><h3><Wrench size={16}/> Recuperação e manutenção do estoque</h3>
      <p className="hint">Confere todos os vídeos e posts: escolhe capas aprovadas que ficaram sem escolha, refaz o que falhou, resolve pedidos repetidos,
        devolve à fila os posts que travaram por falta de capa e troca só a capa dos vídeos que já estão no YouTube. Nunca posta de novo.</p>
      <div className="row-gap left">
        <button className="subtle" disabled={!!busy} onClick={()=>auditar(false)}>{busy==='simular'?<Loader2 size={14} className="spin"/>:<RefreshCw size={14}/>} Simular</button>
        <button className="primary" disabled={!!busy} onClick={()=>auditar(true)}>{busy==='aplicar'&&<Loader2 size={14} className="spin"/>} Aplicar</button>
      </div>
      {d.ultima_auditoria&&<p className="muted">Última aplicação: {quando(Number(d.ultima_auditoria.t))}</p>}
      {aud&&<div className="hint"><b>{aud.aplicado?'Aplicado':'Simulação (nada mudou)'}</b>
        <ul>
          <li>Vídeos: {aud.videos.total} · com capa válida {aud.videos.com_capa} · sem {aud.videos.sem_capa}</li>
          <li>Capas {aud.aplicado?'escolhidas':'a escolher'}: {aud.recuperacao.selecionados.length} · pedidos {aud.aplicado?'criados':'a criar'}: {aud.recuperacao.criados.length} · exceções: {aud.recuperacao.excecoes.length}</li>
          <li>Pedidos redundantes: {aud.redundantes.length}</li>
          <li>Posts agendados sem capa: {aud.agendados_sem_capa.length} · voltaram para a fila: {aud.posts_reabertos.length}</li>
          <li>No YouTube sem capa confirmada: {aud.youtube_sem_capa.length}{aud.aplicado&&` · capas reenviadas: ${aud.youtube_reenviados.filter(x=>x.resultado==='aplicada').length}`}</li>
          <li>Já postados em redes onde a capa só muda no app: {aud.postados_capa_manual.length}</li>
        </ul></div>}
    </section>

    <section className="panel"><h3>Regras da autonomia</h3>
      <div className="thumb-grade">
        <label className="field"><span>Modo</span><select value={c.modo} onChange={e=>m({modo:e.target.value as CfgThumb['modo']})}>
          <option value="automatico">Automático (escolhe sozinho)</option><option value="supervisionado">Supervisionado (você escolhe)</option><option value="manual">Manual</option></select></label>
        <label className="field"><span>Capas por vídeo</span><select value={c.variantes_padrao} onChange={e=>m({variantes_padrao:Number(e.target.value)})}>{[1,2,3,4].map(x=><option key={x}>{x}</option>)}</select></label>
        <label className="field"><span>Nota mínima</span><input type="number" min={50} max={95} value={c.nota_min} onChange={e=>m({nota_min:Number(e.target.value)})}/></label>
        <label className="field"><span>Correções por etapa (máx.)</span><input type="number" min={0} max={5} value={c.max_correcoes} onChange={e=>m({max_correcoes:Number(e.target.value)})}/></label>
        <label className="field"><span>Pedidos de recuperação por vídeo</span><input type="number" min={0} max={10} value={c.max_recuperacoes} onChange={e=>m({max_recuperacoes:Number(e.target.value)})}/></label>
        <label className="field"><span>Tentativas de envio da capa</span><input type="number" min={1} max={10} value={c.max_envios_capa} onChange={e=>m({max_envios_capa:Number(e.target.value)})}/></label>
      </div>
      <label className="check"><input type="checkbox" checked={c.criar_sozinho} onChange={e=>m({criar_sozinho:e.target.checked})}/> Criar capas sozinho</label>
      <label className="check"><input type="checkbox" checked={c.recuperacao_automatica} onChange={e=>m({recuperacao_automatica:e.target.checked})}/> Recuperar sozinho (vídeo mudou, pedido falhou)</label>
      <label className="check"><input type="checkbox" checked={c.reenviar_capa} onChange={e=>m({reenviar_capa:e.target.checked})}/> Tentar de novo só a capa quando a rede recusar (sem repetir o post)</label>
      <label className="check"><input type="checkbox" checked={c.exigir_capa} onChange={e=>m({exigir_capa:e.target.checked})}/> Exigir capa válida antes de publicar</label>
      <h4>Estratégia por rede</h4>
      <ul className="thumb-redes">{REDES.map(rede=><li key={rede}><b>{NOME[rede]}</b>{' '}
        <select value={c.estrategia_rede[rede]||'manual'} onChange={e=>m({estrategia_rede:{...c.estrategia_rede,[rede]:e.target.value as Estrategia}})}>
          {(Object.entries(d.estrategias) as [Estrategia,string][]).filter(([k])=>k!=='imagem'||rede==='youtube').map(([k,t])=><option key={k} value={k}>{t}</option>)}</select>
        {' '}<label className="check sm"><input type="checkbox" checked={exige(rede)} disabled={!c.exigir_capa} onChange={e=>setExige(rede,e.target.checked)}/> exige capa</label>
        <br/><small className="muted">{rede==='youtube'?'A arte vai como capa. Se o YouTube recusar, o vídeo fica no ar e só a capa é tentada de novo.'
          :rede==='tiktok'?'A arte entra como quadro final curto e o TikTok recebe o tempo dele. No envio assistido (rascunho), você escolhe esse quadro no app.'
          :rede==='instagram'?'A arte entra como quadro final curto e o Instagram recebe o tempo dele (thumb_offset).'
          :'A integração não troca a capa: você aplica no app.'}</small></li>)}</ul>
      <div className="row-gap left"><button className="primary" disabled={!!busy} onClick={salvar}>Salvar</button></div>
    </section>
  </>;
}
