import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Download, Image as ImgIcon, Loader2, Palette, Plus, RefreshCw, Settings2, Sparkles, XCircle, BarChart3, ListChecks, ShieldCheck } from 'lucide-react';
import { useApp } from '../state';
import { useCfg, useServidor, erroTexto } from '../components/Servidor2';
import Progresso from '../components/Progresso';
import ThumbAutonomia from './ThumbAutonomia';
import { urlServidor } from '../lib/api';
import { tempoTexto } from '../lib/alertas';
import { ESTADOS, LAYOUT, METODOS, cancelarJob, criarPerfil, escolherCapa, lerCapacidades, lerCfgThumb, lerDesempenho, lerFontes, lerJob, lerJobs, lerPerfis,
  mudarPerfil, pedirCapas, refazerCapa, rejeitarCapa, salvarCfgThumb, type CfgThumb, type Fonte, type Metodo, type Pedido, type Perfil, type Variante } from '../lib/thumbnails';

type Aba='fila'|'autonomia'|'criar'|'galeria'|'modelos'|'desempenho'|'config';
const ABAS:[Aba,string,typeof ImgIcon][]=[['fila','Fila',ListChecks],['autonomia','Autonomia e Integração',ShieldCheck],['criar','Criar',Plus],['galeria','Galeria',ImgIcon],['modelos','Modelos',Palette],['desempenho','Desempenho',BarChart3],['config','Configurações',Settings2]];
const RODANDO=['na_fila','analisando','criando','validando','aguardando_video'];
const quando=(t?:number|null)=>t?new Date(t*1000).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'';
const seg=(s?:number|null)=>s==null?'sem medida ainda':tempoTexto(s);

function Tag({estado}:{estado:string}){ const [t,c]=ESTADOS[estado]||[estado,'']; return <span className={'tag '+c}>{t}</span>; }

export default function Thumbnails(){
  const {rotaExtra,go}=useApp(); const cfg=useCfg();
  const [aba,setAba]=useState<Aba>((ABAS.find(a=>a[0]===rotaExtra.split(':')[0])?.[0])||'fila');
  const [jobSel,setJobSel]=useState<string>(rotaExtra.startsWith('galeria:')?rotaExtra.slice(8):'');
  useEffect(()=>{ const a=ABAS.find(x=>x[0]===rotaExtra.split(':')[0])?.[0]; if(a) setAba(a); if(rotaExtra.startsWith('galeria:')) setJobSel(rotaExtra.slice(8)); },[rotaExtra]);
  if(!cfg.servidor) return <section className="panel"><p className="hint">Conecte o servidor do celular em Ajustes para usar o Agente 6.</p></section>;
  const trocar=(a:Aba,extra='')=>{ setAba(a); go('thumbnails',extra?`${a}:${extra}`:a); };
  const abrir=(id:string)=>{ setJobSel(id); trocar('galeria',id); };
  return <div className="thumbs">
    <div className="ag-abas" role="tablist">{ABAS.map(([k,t,I])=><button key={k} role="tab" aria-selected={aba===k} className={aba===k?'active':''} onClick={()=>trocar(k)}><I size={14}/> {t}</button>)}</div>
    {aba==='fila'&&<FilaThumbs abrir={abrir} criar={()=>trocar('criar')}/>}
    {aba==='autonomia'&&<ThumbAutonomia abrir={abrir}/>}
    {aba==='criar'&&<Criar pronto={abrir}/>}
    {aba==='galeria'&&<Galeria id={jobSel} voltar={()=>trocar('fila')}/>}
    {aba==='modelos'&&<Modelos/>}
    {aba==='desempenho'&&<DesempenhoTela/>}
    {aba==='config'&&<Config/>}
  </div>;
}

function FilaThumbs({abrir,criar}:{abrir:(id:string)=>void;criar:()=>void}){
  const cfg=useCfg(); const r=useServidor(c=>lerJobs(c),5);
  const [filtro,setFiltro]=useState('');
  const jobs=(r.dados?.jobs||[]).filter(j=>!filtro||(filtro==='rodando'?RODANDO.includes(j.estado):j.estado===filtro));
  const grupos:[string,string][]=[['','Todos'],['rodando','Em processamento'],['aguardando_escolha','Esperando escolha'],['pronto','Prontas'],['revisao_manual','Precisam de você'],['falhou','Com erro']];
  return <section className="panel">
    <h3><ListChecks size={16}/> Capas pedidas</h3>
    {r.erro&&<p className="hint bad">{/rota não encontrada/i.test(r.erro)?<>O servidor do celular ainda não tem o Agente 6. No Termux rode: <code>cd ~/ia &amp;&amp; git pull</code> e depois <code>cd servidor &amp;&amp; bash iniciar-termux.sh link</code>.</>:r.erro}</p>}
    <div className="seg" role="radiogroup" aria-label="Filtro">{grupos.map(([k,t])=><button key={k} role="radio" aria-checked={filtro===k} className={filtro===k?'on':''} onClick={()=>setFiltro(k)}>{t}</button>)}</div>
    {!r.dados?<p className="muted"><Loader2 size={14} className="spin"/> Carregando…</p>
    :!jobs.length?<p className="muted">Nada aqui ainda. <button className="link-btn" onClick={criar}>Criar capas</button></p>
    :<ul className="thumb-jobs">{jobs.map(j=><li key={j.id}>
      <button className="thumb-job" onClick={()=>abrir(j.id)}>
        {(()=>{ const v=j.variantes.find(x=>x.id===j.selecao?.variante)||j.variantes.find(x=>x.estado==='aprovada')||j.variantes[0];
          return v?<img src={urlServidor(cfg,v.url)} alt="" loading="lazy" className={v.formato==='9:16'?'vert':''}/>:<span className="thumb-vazio"><ImgIcon size={20}/></span>; })()}
        <span className="thumb-job-txt"><b>{j.titulo}</b><small className="muted">{j.origem==='corte'?'Corte do Agente 1':j.origem==='render'?'Vídeo do Agente 3':'Post'} · {quando(j.criado)}</small>
          <span><Tag estado={j.estado}/> {j.variantes.filter(v=>v.estado!=='substituida'&&v.estado!=='rejeitada').length} capa(s)</span>
          {j.erro&&j.estado!=='pronto'&&<small className="muted">{j.erro}</small>}
          {j.progresso&&RODANDO.includes(j.estado)&&<Progresso pct={j.progresso.pct} restante={j.progresso.restante_s} estimado={j.progresso.estimado} status={j.progresso.status}/>}</span>
      </button></li>)}</ul>}
  </section>;
}
function Criar({pronto}:{pronto:(id:string)=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const [origem,setOrigem]=useState<'corte'|'render'|'post'>('corte'); const [termo,setTermo]=useState('');
  const fontes=useServidor(c=>lerFontes(c,origem,termo),0,[origem,termo]);
  const caps=useServidor(c=>lerCapacidades(c));
  const perfis=useServidor(c=>lerPerfis(c));
  const [ref,setRef]=useState<Fonte|null>(null);
  const [p,setP]=useState<Omit<Pedido,'origem'|'referencia'>>({metodo:'inteligente',variantes:3,formato:'auto',texto_modo:'auto',texto:'',descricao:'',perfil_id:'',fallback_local:false});
  const [busy,setBusy]=useState(false);
  const iaOk=caps.dados?.ia.disponivel;
  async function enviar(){
    if(!ref) return;
    setBusy(true);
    try{ const j=await pedirCapas(cfg,{...p,origem:ref.origem,referencia:ref.referencia}); toast(j.repetido?'Esse pedido já existe: abri ele.':'Pedido na fila. As capas aparecem na Galeria.','ok'); pronto(j.id); }
    catch(e){ toast(erroTexto(e),'erro'); } finally{ setBusy(false); }
  }
  return <section className="panel">
    <h3><Plus size={16}/> Criar capas</h3>
    <p className="hint">O Agente 6 usa o <b>arquivo final</b> do vídeo (depois do editor), tira quadros reais, escolhe os mais nítidos e diferentes, e desenha até 4 capas. O diretor confere cada uma (leitura no celular, área segura, arquivo).</p>
    <div className="field"><span className="field-label">1. Qual vídeo?</span>
      <div className="seg" role="radiogroup">{([['corte','Cortes do Agente 1'],['render','Vídeos do Agente 3'],['post','Posts']] as const).map(([k,t])=><button key={k} role="radio" aria-checked={origem===k} className={origem===k?'on':''} onClick={()=>{ setOrigem(k); setRef(null); }}>{t}</button>)}</div>
      <input placeholder="Procurar pelo título" value={termo} onChange={e=>setTermo(e.target.value)} style={{marginTop:8}}/>
      {fontes.erro&&<p className="hint bad">{fontes.erro}</p>}
      <ul className="thumb-fontes">{(fontes.dados?.fontes||[]).slice(0,30).map(f=><li key={f.origem+f.referencia}><label className={'check'+(ref?.referencia===f.referencia?' on':'')}>
        <input type="radio" name="fonte" checked={ref?.referencia===f.referencia} onChange={()=>setRef(f)}/> <span><b>{f.titulo}</b> <small className="muted">{f.agente} · {f.status}</small>
        {f.job&&<> · <Tag estado={f.job.estado}/></>}</span></label></li>)}
        {fontes.dados&&!fontes.dados.fontes.length&&<li className="muted">Nenhum vídeo pronto aqui.</li>}</ul>
    </div>
    <div className="field"><span className="field-label">2. Jeito de fazer</span>
      <div className="thumb-metodos">{METODOS.map(([k,t,d])=><button key={k} className={'thumb-metodo'+(p.metodo===k?' on':'')} onClick={()=>setP({...p,metodo:k as Metodo})} aria-pressed={p.metodo===k}>
        <b>{k==='ia'&&<Sparkles size={13}/>} {t}</b><small>{d}</small>{k==='ia'&&!iaOk&&<small className="warn">{caps.dados?.ia.motivo||'Desligada'}</small>}</button>)}</div>
      {p.metodo==='ia'&&!iaOk&&<label className="check"><input type="checkbox" checked={!!p.fallback_local} onChange={e=>setP({...p,fallback_local:e.target.checked})}/> Se a IA não der, fazer com quadros do vídeo</label>}
    </div>
    <label className="field"><span>3. Descreva a capa (opcional)</span><textarea rows={2} value={p.descricao} onChange={e=>setP({...p,descricao:e.target.value})} placeholder={'Ex.: Uma lua enorme no horizonte e o texto "POR QUÊ?" com contraste amarelo'}/>
      <small className="muted">Texto entre aspas vira o texto da capa no modo automático.</small></label>
    <div className="field"><span className="field-label">4. Texto da capa</span>
      <div className="seg" role="radiogroup">{([['auto','Automático (gancho completo)'],['exato','Texto exato'],['sem','Sem texto']] as const).map(([k,t])=><button key={k} role="radio" aria-checked={p.texto_modo===k} className={p.texto_modo===k?'on':''} onClick={()=>setP({...p,texto_modo:k})}>{t}</button>)}</div>
      {p.texto_modo==='exato'&&<textarea maxLength={500} value={p.texto} onChange={e=>setP({...p,texto:e.target.value})} placeholder="Escreva a frase completa da capa" style={{marginTop:8}}/>}
      {p.texto_modo!=='sem'&&<small className="muted">O texto é desenhado pelo EstúdioClip (nunca pela IA), então sai sem erro de escrita. Emoji não aparece: a fonte não tem.</small>}
    </div>
    <div className="thumb-grade">
      <label className="field"><span>Formato</span><select value={p.formato} onChange={e=>setP({...p,formato:e.target.value})}>
        <option value="auto">Automático (pelo vídeo)</option><option value="16:9">16:9 (YouTube)</option><option value="9:16">9:16 (vertical)</option><option value="4:5">4:5</option><option value="1:1">1:1</option></select></label>
      <label className="field"><span>Quantas capas</span><select value={p.variantes} onChange={e=>setP({...p,variantes:Number(e.target.value)})}>{[1,2,3,4].map(n=><option key={n} value={n}>{n}</option>)}</select></label>
      <label className="field"><span>Modelo de marca</span><select value={p.perfil_id} onChange={e=>setP({...p,perfil_id:e.target.value})}>
        <option value="">Automático (do canal ou o geral)</option>{(perfis.dados?.perfis||[]).map(x=><option key={x.id} value={x.id}>{x.nome}</option>)}</select></label>
    </div>
    <div className="row-gap left"><button className="primary" disabled={!ref||busy||(p.texto_modo==='exato'&&!p.texto.trim())} onClick={enviar}>{busy?<Loader2 size={14} className="spin"/>:<ImgIcon size={14}/>} Gerar capas</button></div>
  </section>;
}

function Galeria({id,voltar}:{id:string;voltar:()=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const r=useServidor(c=>id?lerJob(c,id):Promise.resolve(null),4,[id]);
  const [busy,setBusy]=useState(false); const [comparar,setComparar]=useState<string[]>([]); const [refTxt,setRefTxt]=useState<Record<number,string>>({});
  const j=r.dados;
  const ativas=useMemo(()=>j?j.variantes.filter(v=>v.estado!=='substituida'&&v.estado!=='rejeitada'):[],[j]);
  const historico=useMemo(()=>j?j.variantes.filter(v=>v.estado==='substituida'||v.estado==='rejeitada'):[],[j]);
  if(!id) return <section className="panel"><p className="muted">Escolha um pedido na <button className="link-btn" onClick={voltar}>Fila</button>.</p></section>;
  if(!j) return <section className="panel">{r.erro?<p className="hint bad">{r.erro}</p>:<p className="muted"><Loader2 size={14} className="spin"/> Carregando…</p>}</section>;
  async function fazer(f:()=>Promise<unknown>,msg:string){ setBusy(true); try{ await f(); toast(msg,'ok'); await r.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }
  async function escolher(v:Variante){
    if(v.estado!=='aprovada'){
      if(!window.confirm(`O diretor deu nota ${v.nota} para esta capa (abaixo do mínimo). Usar mesmo assim?`)) return;
      return fazer(()=>escolherCapa(cfg,j!.id,v,true),'Capa escolhida (com a sua confirmação).');
    }
    return fazer(()=>escolherCapa(cfg,j!.id,v),'Capa escolhida. O pacote vídeo + capa está pronto.');
  }
  const rodando=RODANDO.includes(j.estado);
  const vistos=comparar.length===2?ativas.filter(v=>comparar.includes(v.id)):[];
  return <>
    <section className="panel">
      <h3><ImgIcon size={16}/> {j.titulo} <Tag estado={j.estado}/></h3>
      <p className="muted">{j.origem==='corte'?'Corte do Agente 1':j.origem==='render'?'Vídeo do Agente 3':'Post'} · vídeo {j.video_sha.slice(0,10)} · {METODOS.find(m=>m[0]===j.metodo)?.[1]||j.metodo}
        {j.correcoes?` · ${j.correcoes} correção(ões) do diretor`:''}{j.custo?` · custo estimado R$ ${j.custo.toFixed(2)}`:''}</p>
      {j.erro&&<p className={'hint '+(j.estado==='falhou'||j.estado==='revisao_manual'?'bad':'warn')}><AlertTriangle size={13}/> {j.erro}</p>}
      {(j.config.avisos||[]).map((a,i)=><p key={i} className="hint warn">{a}</p>)}
      {j.progresso&&rodando&&<Progresso pct={j.progresso.pct} restante={j.progresso.restante_s} estimado={j.progresso.estimado} status={j.progresso.status}/>}
      {j.progresso&&<p className="muted thumb-tempos">Na fila: {quando(j.progresso.criado)} · começou: {quando(j.progresso.iniciado)||'ainda não'} · {j.progresso.terminado?`terminou: ${quando(j.progresso.terminado)} · trabalhando: ${seg(j.progresso.decorrido)}`:'rodando'}{j.progresso.tentativas?` · tentativas: ${j.progresso.tentativas}`:''}</p>}
      {j.selecao&&<p className="hint ok"><CheckCircle2 size={13}/> Capa escolhida ({j.selecao.escolha==='manual'?'por você, abaixo da nota':j.selecao.escolha==='automatica'?'pelo modo automático':'por você'}). Vai junto com o vídeo onde a rede aceitar. Se o vídeo ou a capa mudarem, a escolha cai sozinha.</p>}
      <div className="row-gap left">
        {rodando&&<button className="subtle" disabled={busy} onClick={()=>window.confirm('Cancelar este pedido?')&&fazer(()=>cancelarJob(cfg,j.id),'Pedido cancelado.')}><XCircle size={14}/> Cancelar</button>}
        <button className="subtle" onClick={()=>r.recarregar()}><RefreshCw size={14}/> Atualizar</button>
        {comparar.length>0&&<button className="subtle" onClick={()=>setComparar([])}>Limpar comparação</button>}
      </div>
    </section>
    {vistos.length===2&&<section className="panel"><h3>Comparar</h3><div className="thumb-comparar">{vistos.map(v=><figure key={v.id}><img src={urlServidor(cfg,v.url)} alt={`Capa ${v.numero}`}/>
      <figcaption>Capa {v.numero} · nota {v.nota} · {LAYOUT[v.layout]||v.layout}</figcaption></figure>)}</div></section>}
    <div className="thumb-galeria">{ativas.map(v=>{ const sel=j.selecao?.variante===v.id; const leg=v.relatorio.criterios?.legibilidade_medida;
      return <article key={v.id} className={'panel thumb-card'+(sel?' sel':'')}>
        <img src={urlServidor(cfg,v.url)} alt={`Capa ${v.numero}`} className={v.formato==='9:16'?'vert':''}/>
        <div className="thumb-mini" title="Como aparece pequena (120 px)"><img src={urlServidor(cfg,v.url)} alt="" width={120}/><small className="muted">120 px</small></div>
        <h4>Capa {String.fromCharCode(64+v.numero)} <small className="muted">v{v.versao}</small> {v.estado==='aprovada'?<span className="tag ok">diretor aprovou · {v.nota}</span>:<span className="tag bad">reprovada · {v.nota}</span>}{sel&&<span className="tag ok">escolhida</span>}</h4>
        <p className="muted">{LAYOUT[v.layout]||v.layout} · {v.formato} {v.largura}x{v.altura}{v.quadro_t!=null?` · quadro do segundo ${v.quadro_t.toFixed(1)}`:''} · hash {v.sha256.slice(0,10)}</p>
        {leg?.medido&&<p className="muted">Leitura a 120 px: contraste {leg.contraste}:1, letra {leg.altura_120} px</p>}
        {v.relatorio.bloqueios.map((b,i)=><p key={i} className="hint bad">{b}</p>)}
        {v.relatorio.notas.slice(0,3).map((b,i)=><p key={i} className="hint">{b}</p>)}
        <details><summary>Notas do diretor</summary><ul className="thumb-crit">{(['fidelidade','legibilidade','area_segura','tecnica','identidade','rede'] as const).map(k=><li key={k}>{({fidelidade:'Fiel ao vídeo (25)',legibilidade:'Leitura no celular (20)',area_segura:'Área segura (15)',tecnica:'Arquivo (15)',identidade:'Identidade (15)',rede:'Formato da rede (10)'})[k]}: <b>{v.relatorio.criterios[k]??'-'}</b></li>)}</ul>
          <small className="muted">{v.relatorio.metodo}</small></details>
        <div className="row-gap left">
          {j.rejeicao_habilitada&&!sel&&<button className="subtle sm" disabled={busy||rodando} onClick={()=>fazer(()=>rejeitarCapa(cfg,j.id,v),'Proposta recusada. A capa escolhida foi preservada.')}><XCircle size={13}/> Recusar</button>}
          {!sel&&<button className="primary sm" disabled={busy||rodando||!!v.relatorio.bloqueios.length} onClick={()=>escolher(v)}><CheckCircle2 size={13}/> Escolher</button>}
          <a className="subtle sm btn-link" href={urlServidor(cfg,v.baixar)} download><Download size={13}/> Baixar</a>
          <label className="check sm"><input type="checkbox" checked={comparar.includes(v.id)} onChange={e=>setComparar(e.target.checked?[...comparar.slice(-1),v.id]:comparar.filter(x=>x!==v.id))}/> comparar</label>
        </div>
        <details><summary>Refazer só esta capa</summary>
          <textarea maxLength={500} placeholder="Texto novo completo (deixe vazio para manter)" value={refTxt[v.numero]||''} onChange={e=>setRefTxt({...refTxt,[v.numero]:e.target.value})}/>
          <button className="subtle sm" disabled={busy||rodando} onClick={()=>fazer(()=>refazerCapa(cfg,j.id,v.numero,refTxt[v.numero]?.trim()||undefined),`Refazendo a capa ${v.numero}.`)}><RefreshCw size={13}/> Refazer</button>
          <small className="muted">Só esta capa muda. O vídeo não é refeito.</small></details>
      </article>; })}
      {!ativas.length&&!rodando&&<section className="panel"><p className="muted">Nenhuma capa neste pedido.</p></section>}</div>
    {historico.length>0&&<section className="panel"><details><summary>Histórico ({historico.length} versão(ões) substituída(s) ou recusada(s))</summary>
      <div className="thumb-hist">{historico.map(v=><figure key={v.id}><img src={urlServidor(cfg,v.url)} alt=""/><figcaption>Capa {v.numero} v{v.versao} · {v.estado==='rejeitada'?'recusada por você':`nota ${v.nota}`}<br/>{v.relatorio.bloqueios[0]||v.relatorio.notas[0]||''}</figcaption></figure>)}</div></details></section>}
  </>;
}

function Modelos(){
  const {toast}=useApp(); const cfg=useCfg();
  const r=useServidor(c=>lerPerfis(c));
  const vazio={nome:'',escopo:'geral',cor_texto:'#FFFFFF',cor_destaque:'#FFE14D',cor_faixa:'#111111',intensidade:70,maiusculas:true,nicho:'',exemplos:'',logo_asset:''};
  const [ed,setEd]=useState<typeof vazio&{id?:string}>(vazio); const [busy,setBusy]=useState(false);
  async function salvar(){ setBusy(true); try{ const {id,...d}=ed; if(id) await mudarPerfil(cfg,id,d); else await criarPerfil(cfg,d); toast('Modelo salvo.','ok'); setEd(vazio); await r.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }
  const editar=(p:Perfil)=>setEd({...vazio,...p.config,nome:p.nome,escopo:p.escopo,id:p.id});
  return <>
    <section className="panel"><h3><Palette size={16}/> Modelos de capa</h3>
      <p className="hint">Cores, força do escurecido e logo por canal, perfil de corte ou linha de conteúdo. O modelo "geral" vale quando o vídeo não tem um próprio. Mudar um modelo cria uma versão nova; capas já feitas não mudam.</p>
      {r.erro&&<p className="hint bad">{r.erro}</p>}
      <ul className="thumb-perfis">{(r.dados?.perfis||[]).map(p=><li key={p.id}><span className="thumb-paleta">{[p.config.cor_destaque,p.config.cor_faixa,p.config.cor_texto].map((c,i)=><i key={i} style={{background:c}}/>)}</span>
        <b>{p.nome}</b> <small className="muted">{p.escopo} · v{p.versao}</small> <button className="link-btn" onClick={()=>editar(p)}>editar</button></li>)}
        {r.dados&&!r.dados.perfis.length&&<li className="muted">Nenhum modelo ainda: as capas usam branco e amarelo.</li>}</ul>
    </section>
    <section className="panel"><h3>{ed.id?'Editar modelo':'Novo modelo'}</h3>
      <div className="thumb-grade">
        <label className="field"><span>Nome</span><input value={ed.nome} onChange={e=>setEd({...ed,nome:e.target.value})} placeholder="Ex.: Canal de GTA"/></label>
        <label className="field"><span>Vale para</span><input value={ed.escopo} disabled={!!ed.id} onChange={e=>setEd({...ed,escopo:e.target.value})}/><small className="muted">geral, perfil:ID, linha:ID ou canal:ID</small></label>
        <label className="field"><span>Cor do texto</span><input type="color" value={ed.cor_texto} onChange={e=>setEd({...ed,cor_texto:e.target.value.toUpperCase()})}/></label>
        <label className="field"><span>Cor de destaque</span><input type="color" value={ed.cor_destaque} onChange={e=>setEd({...ed,cor_destaque:e.target.value.toUpperCase()})}/></label>
        <label className="field"><span>Cor das faixas</span><input type="color" value={ed.cor_faixa} onChange={e=>setEd({...ed,cor_faixa:e.target.value.toUpperCase()})}/></label>
        <label className="field"><span>Força do escurecido ({ed.intensidade})</span><input type="range" min={0} max={100} value={ed.intensidade} onChange={e=>setEd({...ed,intensidade:Number(e.target.value)})}/></label>
        <label className="field"><span>Logo (id do arquivo na biblioteca)</span><input value={ed.logo_asset} onChange={e=>setEd({...ed,logo_asset:e.target.value.trim()})} placeholder="opcional"/></label>
        <label className="field"><span>Nicho</span><input value={ed.nicho} onChange={e=>setEd({...ed,nicho:e.target.value})} placeholder="Ex.: games"/></label>
      </div>
      <label className="check"><input type="checkbox" checked={ed.maiusculas} onChange={e=>setEd({...ed,maiusculas:e.target.checked})}/> Texto em maiúsculas</label>
      <div className="row-gap left"><button className="primary" disabled={busy||!ed.nome.trim()} onClick={salvar}>Salvar modelo</button>{ed.id&&<button className="subtle" onClick={()=>setEd(vazio)}>Novo</button>}</div>
    </section>
  </>;
}

function DesempenhoTela(){
  const r=useServidor(c=>lerDesempenho(c),30);
  const d=r.dados;
  return <section className="panel"><h3><BarChart3 size={16}/> Desempenho do Agente 6</h3>
    {r.erro&&<p className="hint bad">{r.erro}</p>}
    {!d?<p className="muted"><Loader2 size={14} className="spin"/> Carregando…</p>:<>
      <div className="es-agentes thumb-num">
        <div className="es-ag"><b>{d.pedidos}</b><span>pedidos</span></div>
        <div className="es-ag"><b>{seg(d.tempo_ativo_medio_s)}</b><span>trabalhando, em média</span></div>
        <div className="es-ag"><b>{seg(d.espera_fila_media_s)}</b><span>esperando na fila</span></div>
        <div className="es-ag"><b>{seg(d.previsao_por_pedido_s)}</b><span>previsão por pedido</span></div>
        <div className={'es-ag'+(d.falhas?' bad':'')}><b>{d.falhas}</b><span>falhas</span></div>
        <div className="es-ag"><b>{d.correcoes_criativas}</b><span>correções do diretor</span></div>
        <div className="es-ag"><b>{d.tentativas_fila}</b><span>tentativas técnicas</span></div>
        <div className="es-ag"><b>R$ {d.custo_estimado_reais.toFixed(2)}</b><span>custo estimado (IA)</span></div>
      </div>
      <p><b>Capas escolhidas:</b> {d.escolhas.total}{d.escolhas.manuais?` (${d.escolhas.manuais} abaixo da nota, com sua confirmação)`:''}</p>
      {Object.keys(d.escolhas.por_layout).length>0&&<ul>{Object.entries(d.escolhas.por_layout).sort((a,b)=>b[1]-a[1]).map(([k,n])=><li key={k}>{LAYOUT[k]||k}: {n}</li>)}</ul>}
      <p className="hint">{d.aviso}</p></>}
  </section>;
}

function Config(){
  const {toast}=useApp(); const cfg=useCfg();
  const r=useServidor(c=>lerCfgThumb(c)); const cap=useServidor(c=>lerCapacidades(c));
  const [c,setC]=useState<CfgThumb|null>(null); const [busy,setBusy]=useState(false);
  useEffect(()=>{ if(r.dados&&!c) setC(r.dados); },[r.dados,c]);
  if(!c) return <section className="panel">{r.erro?<p className="hint bad">{r.erro}</p>:<p className="muted"><Loader2 size={14} className="spin"/> Carregando…</p>}</section>;
  const m=(p:Partial<CfgThumb>)=>setC({...c,...p});
  async function salvar(){ setBusy(true); try{ setC(await salvarCfgThumb(cfg,c!)); toast('Configurações salvas.','ok'); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }
  return <>
    <section className="panel"><h3><Settings2 size={16}/> Como o Agente 6 trabalha</h3>
      <div className="seg big" role="radiogroup">{([['automatico','Automático','Escolhe sozinho a melhor capa aprovada pelo diretor.'],['supervisionado','Supervisionado','Faz as capas e espera você escolher.'],['manual','Manual','Só faz capa quando você pede.']] as const).map(([k,t,d])=>
        <button key={k} role="radio" aria-checked={c.modo===k} className={c.modo===k?'on':''} onClick={()=>m({modo:k})}><b>{t}</b><small>{d}</small></button>)}</div>
      {c.modo!=='manual'&&<label className="check"><input type="checkbox" checked={c.criar_sozinho} onChange={e=>m({criar_sozinho:e.target.checked})}/> Criar capas sozinho para os cortes e os vídeos do Agente 3 (até 2 por vez, primeiro os que saem mais cedo)</label>}
      <div className="thumb-grade">
        <label className="field"><span>Jeito padrão</span><select value={c.metodo_padrao} onChange={e=>m({metodo_padrao:e.target.value as Metodo})}>{METODOS.map(([k,t])=><option key={k} value={k}>{t}</option>)}</select></label>
        <label className="field"><span>Capas por pedido</span><select value={c.variantes_padrao} onChange={e=>m({variantes_padrao:Number(e.target.value)})}>{[1,2,3,4].map(n=><option key={n}>{n}</option>)}</select></label>
        <label className="field"><span>Correções do diretor (máx.)</span><input type="number" min={0} max={5} value={c.max_correcoes} onChange={e=>m({max_correcoes:Number(e.target.value)})}/></label>
        <label className="field"><span>Nota mínima</span><input type="number" min={50} max={95} value={c.nota_min} onChange={e=>m({nota_min:Number(e.target.value)})}/></label>
      </div>
      <h4>IA (opcional)</h4>
      <label className="check"><input type="checkbox" checked={c.ia} onChange={e=>m({ia:e.target.checked})}/> Usar o gerador de imagens do Gemini para o fundo</label>
      <div className="thumb-grade"><label className="field"><span>Imagens de IA por pedido</span><input type="number" min={0} max={4} value={c.ia_max_por_pedido} onChange={e=>m({ia_max_por_pedido:Number(e.target.value)})}/>
        <small className="muted">Cada imagem gasta da chave paga (estimativa de US$ 0,04). Conta no teto de gastos que já existe.</small></label></div>
      <label className="check"><input type="checkbox" checked={c.ia_fallback_local} onChange={e=>m({ia_fallback_local:e.target.checked})}/> Se a IA falhar, fazer com quadros do vídeo sem perguntar</label>
      {cap.dados&&!cap.dados.ia.disponivel&&<p className="hint warn">{cap.dados.ia.motivo}</p>}
      <h4>Redes</h4>
      <p className="hint">Capa obrigatória por rede, estratégia de cada rede e recuperação ficam na aba <b>Autonomia e Integração</b>.</p>
      <ul className="thumb-redes">{cap.dados&&Object.entries(cap.dados.redes).map(([k,x])=><li key={k}><b>{k[0].toUpperCase()+k.slice(1)}</b> <span className={'tag '+(x.testado?'ok':x.tipo==='manual_only'?'':'warn')}>{x.estado}</span>
        <label className="sm"> formato <select value={c.formato_por_rede[k]||'auto'} onChange={e=>m({formato_por_rede:{...c.formato_por_rede,[k]:e.target.value}})}><option value="auto">automático</option>{['16:9','9:16','4:5','1:1'].map(f=><option key={f}>{f}</option>)}</select></label>
        <br/><small className="muted">{x.detalhe}</small></li>)}</ul>
      <div className="row-gap left"><button className="primary" disabled={busy} onClick={salvar}>Salvar</button></div>
      {cap.dados&&<p className="hint">{cap.dados.aviso}</p>}
    </section>
  </>;
}
