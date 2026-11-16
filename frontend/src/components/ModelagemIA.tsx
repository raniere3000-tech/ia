import { useEffect, useState } from 'react';
import { Wand2, Shuffle, Loader2, Star, ExternalLink, Eye, Pencil, Save, RotateCcw, AlertTriangle, Search, CheckCircle2 } from 'lucide-react';
import { useApp } from '../state';
import { useCfg, erroTexto } from './Servidor2';
import { biblioteca, usarNoProjeto, previaAsset, capacidades, propor, editarProposta, aplicarProposta, previaProposta, lerDoRadar, NOME_TIPO, NOME_DESTINO,
  type TipoModelo, type Destino, type Proposta, type Resultado, type PedidoModelagem, type Filtros, type Capacidades, type Campos, type Aplicado, type Tendencias, type ItemBiblioteca } from '../lib/criativo';

const FILTROS0:Filtros={plataforma:'youtube',nicho:'',idioma:'pt',regiao:'BR',periodo_dias:30,views_min:0,duracao:'curto',ordem:'views'};
const num=(n:number|null|undefined)=>n===null||n===undefined?'não informado':n.toLocaleString('pt-BR');
const data=(s?:string|null)=>s?new Date(s).toLocaleDateString('pt-BR'):'—';

/** Lista de referências pesquisadas: só o que a API devolveu, com fonte, data e limites. */
export function Referencias({t}:{t:Tendencias}){
  if(!t.disponivel) return <p className="hint warn"><AlertTriangle size={13}/> Tendências indisponíveis: {t.motivo}</p>;
  return <details className="mod-refs" open>
    <summary>Referências em alta ({t.referencias.length} de {t.amostra} vídeos coletados){t.cache?' • da última pesquisa':''}</summary>
    <p className="hint">Fonte: {t.fonte} • coletado em {data(t.coletado_em)} • critério: {t.criterio}. {t.limites}</p>
    <ul className="mod-ref-lista">{t.referencias.map(r=><li key={r.video_id}>
      <a href={r.url} target="_blank" rel="noreferrer"><b>{r.titulo}</b> <ExternalLink size={11}/></a>
      <small>{r.canal_nome} • publicado {data(r.publicado_em)} • {num(r.views)} views{r.views_dia_desde_publicacao!=null?` • ${num(r.views_dia_desde_publicacao)}/dia desde a publicação`:''} • {r.confianca==='medido'?'medido':'views não informadas'}</small>
      {r.caracteristicas_abstratas.length>0&&<small className="muted">Padrão: {r.caracteristicas_abstratas.join(', ')}</small>}
    </li>)}</ul>
    <p className="hint">Só para pesquisa de padrões: nada desses vídeos (personagens, falas, roteiro, imagens ou estilo do canal) é copiado.</p>
  </details>;
}

function Lista({titulo,itens}:{titulo:string;itens:string[]}){
  return itens.length?<div><div className="field-label">{titulo}</div><ul className="mod-mini">{itens.map((x,i)=><li key={i}>{x}</li>)}</ul></div>:null;
}

function CartaoProposta({p,destinos,serieId,projetoId,onMudou,onAplicado,outra}:{p:Proposta;destinos:Destino[];serieId?:string;projetoId?:string;
  onMudou:(p:Proposta)=>void;onAplicado?:(r:Aplicado,p:Proposta)=>void;outra:()=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const [edit,setEdit]=useState(false); const [c,setC]=useState<Campos>(p.campos); const [busy,setBusy]=useState('');
  const [previas,setPrevias]=useState<Record<string,string>>({});
  useEffect(()=>setC(p.campos),[p.campos]);
  const fazer=async(n:string,f:()=>Promise<void>)=>{ setBusy(n); try{ await f(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } };
  const salvar=()=>fazer('salvar',async()=>{ onMudou(await editarProposta(cfg,p.id,{revisao:p.revisao,campos:c})); setEdit(false); toast('Proposta salva.','ok'); });
  const aplicar=(d:Destino)=>fazer(d,async()=>{
    if(!window.confirm(`${NOME_DESTINO[d]} com a proposta "${p.campos.titulo}"? Nada é produzido nem postado; fica como rascunho para você conferir.`)) return;
    const r=await aplicarProposta(cfg,p.id,{destino:d,serie_id:serieId,projeto_id:projetoId,chave:`${d}:${p.id}:${p.revisao}:${serieId||''}:${projetoId||''}`});
    toast(r.repetido?'Isso já tinha sido feito com esta proposta.':'Pronto. '+(r.criados?.length?`${r.criados.length} item(ns) na biblioteca.`:'Rascunho criado.'),'ok');
    onAplicado?.(r,p);
  });
  const ver=(o:'personagem'|'cenario',i:number)=>fazer('pv'+o+i,async()=>{ const r=await previaProposta(cfg,p.id,{o_que:o,indice:i}); if(r.png) setPrevias(x=>({...x,[o+i]:r.png!})); else toast(r.motivo||'Sem desenho.','info'); });
  const campo=(k:keyof Campos,rot:string,area=false)=><label className={area?'larga':''}>{rot}{area?<textarea rows={2} value={String(c[k]??'')} onChange={e=>setC({...c,[k]:e.target.value})}/>
    :<input value={String(c[k]??'')} onChange={e=>setC({...c,[k]:k==='duracao_seg'?+e.target.value:e.target.value})}/>}</label>;
  return <div className={'mod-prop'+(p.status==='aplicada'?' ok':'')}>
    <div className="mod-prop-topo"><b>{c.titulo}</b>
      <span className={'tag '+(p.origem==='ia'?'':'warn')}>{p.rotulo}</span>
      <span className={'tag '+(p.tendencia==='medida'?'ok':'')}>{p.tendencia==='medida'?'baseada em tendência medida':p.tendencia==='indisponivel'?'tendência indisponível (ideia sem alegar popularidade)':'sem pesquisa de tendência'}</span>
      {p.status==='aplicada'&&<span className="tag ok"><CheckCircle2 size={11}/> usada</span>}
      <button className="icon-btn" aria-label={p.favorita?'Tirar dos favoritos':'Favoritar'} onClick={()=>fazer('fav',async()=>onMudou(await editarProposta(cfg,p.id,{revisao:p.revisao,favorita:!p.favorita})))}><Star size={15} fill={p.favorita?'currentColor':'none'}/></button>
    </div>
    {!edit?<>
      {c.sinopse&&<p>{c.sinopse}</p>}
      <p className="hint">{[c.genero,c.tom&&`tom ${c.tom}`,c.publico&&`para ${c.publico}`,`${c.duracao_seg} s`,c.formato,`visual: ${c.estilo}`].filter(Boolean).join(' • ')}</p>
      {c.gancho&&<p><b>Gancho:</b> {c.gancho}</p>}
      {c.premissa&&<p className="muted">{c.premissa}</p>}
      {c.personagens.length>0&&<div><div className="field-label">Personagens</div><div className="mod-pers">{c.personagens.map((x,i)=><div key={i} className="mod-per">
        {previas['personagem'+i]?<img src={previas['personagem'+i]} alt={`Desenho de ${x.nome}`}/>:<div className="mod-sem-img">imagem ainda não gerada</div>}
        <b>{x.nome}</b><small>{x.descricao}{x.personalidade?` • ${x.personalidade}`:''} • voz {x.voz}</small>
        <button className="link-btn" disabled={!!busy} onClick={()=>ver('personagem',i)}>{busy==='pvpersonagem'+i?<Loader2 size={12} className="spin"/>:<Eye size={12}/>} Ver o boneco 2D</button></div>)}</div></div>}
      {c.cenarios.length>0&&<div><div className="field-label">Cenários</div><div className="mod-pers">{c.cenarios.map((x,i)=><div key={i} className="mod-per">
        {previas['cenario'+i]?<img src={previas['cenario'+i]} alt={`Cenário ${x.nome}`}/>:<div className="mod-sem-img">imagem ainda não gerada</div>}
        <b>{x.nome}</b><small>{x.tipo} • {x.horario}{x.clima?` • ${x.clima}`:''}</small>
        <button className="link-btn" disabled={!!busy} onClick={()=>ver('cenario',i)}><Eye size={12}/> Ver o cenário</button></div>)}</div></div>}
      <Lista titulo="Objetos" itens={c.objetos.map(o=>`${o.nome}${o.animavel?'':' (só ficha)'}`)}/>
      <Lista titulo="Movimentos" itens={c.movimentos.map(m=>`${m.nome}${m.animavel?'':' (só orientação)'}`)}/>
      <Lista titulo="Cenas" itens={c.cenas.map(x=>`${x.titulo}: ${x.texto}`)}/>
      <Lista titulo="Regras do mundo" itens={c.regras_mundo}/>
      {c.porque&&<p className="hint"><b>Por que foi sugerida:</b> {c.porque}</p>}
    </>:<div className="small-grid">
      {campo('titulo','Título')}{campo('genero','Gênero')}{campo('tom','Tom')}{campo('publico','Público')}{campo('duracao_seg','Duração (s)')}
      {campo('sinopse','Sinopse',true)}{campo('gancho','Gancho',true)}{campo('premissa','Premissa',true)}
      {c.personagens.map((x,i)=><label key={'p'+i}>Personagem {i+1}<input value={x.nome} onChange={e=>setC({...c,personagens:c.personagens.map((y,k)=>k===i?{...y,nome:e.target.value}:y)})}/>
        <input value={x.descricao} onChange={e=>setC({...c,personagens:c.personagens.map((y,k)=>k===i?{...y,descricao:e.target.value}:y)})} placeholder="Como é"/></label>)}
      {c.cenas.map((x,i)=><label key={'c'+i} className="larga">Cena {i+1}<textarea rows={2} value={x.texto} onChange={e=>setC({...c,cenas:c.cenas.map((y,k)=>k===i?{...y,texto:e.target.value}:y)})}/></label>)}
    </div>}
    {p.compatibilidade.avisos.length>0&&<ul className="avisos">{p.compatibilidade.avisos.map(a=><li key={a}><AlertTriangle size={12}/> {a}</li>)}</ul>}
    {p.fontes_pesquisadas.length>0&&<p className="hint">Inspirada em padrões de {p.fontes_pesquisadas.length} vídeo(s) medidos: {p.fontes_pesquisadas.slice(0,3).map(r=><a key={r.video_id} className="help-link" href={r.url} target="_blank" rel="noreferrer">{r.canal_nome} <ExternalLink size={10}/></a>)}</p>}
    {p.skills_usadas.length>0&&<p className="hint">Boas práticas consultadas (orientação, não motor): {[...new Set(p.skills_usadas.map(s=>s.skill))].join(', ')}.</p>}
    <div className="row-gap left mt">
      {edit?<><button className="primary sm" disabled={!!busy} onClick={salvar}><Save size={14}/> Salvar a edição</button><button className="link-btn" onClick={()=>{ setC(p.campos); setEdit(false); }}>Cancelar</button></>
        :<button className="subtle sm" onClick={()=>setEdit(true)}><Pencil size={14}/> Editar proposta</button>}
      <button className="subtle sm" disabled={!!busy} onClick={outra}><RotateCcw size={14}/> Gerar outra versão</button>
      {destinos.map(d=><button key={d} className={d==='biblioteca'?'subtle sm':'primary sm'} disabled={!!busy||edit||(d!=='biblioteca'&&!p.pronto_para_aplicar)||(d==='episodio'&&!serieId)||(d==='projeto'&&!projetoId)} onClick={()=>aplicar(d)}>
        {busy===d?<Loader2 size={14} className="spin"/>:null} {NOME_DESTINO[d]}</button>)}
    </div>
  </div>;
}

/** "Modelagem com IA": Descrever para a IA ou Surpreenda-me. Igual em todas as telas; muda só o que dá para criar e onde aplicar. */
export default function ModelagemIA({contexto,tipos,destinos,serieId,projetoId,compacto,titulo,rotuloUsar,assets,onAplicado,onUsarCampos}:{contexto:string;tipos:TipoModelo[];destinos:Destino[];
  serieId?:string;projetoId?:string;compacto?:boolean;titulo?:string;rotuloUsar?:string;assets?:{id:string;tipo:string;nome:string;descricao?:string}[];
  onAplicado?:(r:Aplicado,p:Proposta)=>void;onUsarCampos?:(c:Campos,p:Proposta)=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const [aberto,setAberto]=useState(!compacto); const [modo,setModo]=useState<'descricao'|'surpresa'>('descricao');
  const [tipo,setTipo]=useState<TipoModelo>(tipos[0]); const [desc,setDesc]=useState(''); const [f,setF]=useState<Filtros>(FILTROS0);
  const [ousada,setOusada]=useState(false); const [verificadas,setVerificadas]=useState(false); const [estilo,setEstilo]=useState(''); const [formato,setFormato]=useState('9:16');
  const [radar,setRadar]=useState<ReturnType<typeof lerDoRadar>>(null);
  const [res,setRes]=useState<Resultado|null>(null); const [busy,setBusy]=useState(''); const [cap,setCap]=useState<Capacidades|null>(null); const [ultimo,setUltimo]=useState<PedidoModelagem|null>(null);
  useEffect(()=>{ const r=lerDoRadar(); if(r?.length){ setRadar(r); setModo('surpresa'); setAberto(true); } },[]);
  useEffect(()=>{ if(aberto&&!cap) capacidades(cfg).then(setCap).catch(()=>{}); },[aberto,cap,cfg]);
  const pedir=(d:PedidoModelagem)=>{ setBusy(d.modo); setUltimo(d);
    propor(cfg,d).then(r=>{ setRes(r); if(!r.propostas.length&&!r.precisa_confirmar) toast('A IA não trouxe propostas. Tente de novo.','info'); })
      .catch(e=>toast(erroTexto(e),'erro')).finally(()=>setBusy('')); };
  const base=():PedidoModelagem=>({contexto,modo,tipo_modelo:tipo,descricao:desc,surpresa:ousada?'ousada':'equilibrada',serie_id:serieId,projeto_id:projetoId,assets_selecionados:assets,regras:{formato,estilo}});
  const surpreender=(extra:Partial<PedidoModelagem>={})=>pedir({...base(),modo:'surpresa',filtros_tendencias:f,somente_verificadas:verificadas,evidencias_radar:radar||undefined,...extra});
  const mudar=(p:Proposta)=>setRes(r=>r&&{...r,propostas:r.propostas.map(x=>x.id===p.id?p:x)});
  if(!aberto) return <button className="subtle sm mod-abrir" onClick={()=>setAberto(true)}><Wand2 size={14}/> {titulo||'Criar com a IA'}: descrever ou surpreenda-me</button>;
  return <div className={'mod'+(compacto?' compacto':'')}>
    <div className="mod-abas" role="tablist">
      <button role="tab" aria-selected={modo==='descricao'} className={modo==='descricao'?'on':''} onClick={()=>setModo('descricao')}><Wand2 size={15}/> Descrever para a IA</button>
      <button role="tab" aria-selected={modo==='surpresa'} className={modo==='surpresa'?'on':''} onClick={()=>setModo('surpresa')}><Shuffle size={15}/> Surpreenda-me</button>
    </div>
    {tipos.length>1&&<label>O que criar?<select value={tipo} onChange={e=>setTipo(e.target.value as TipoModelo)}>{tipos.map(t=><option key={t} value={t}>{NOME_TIPO[t]}</option>)}</select></label>}
    {cap&&!cap.ia.disponivel&&<p className="hint warn">{cap.ia.motivo}</p>}
    {modo==='descricao'?<>
      <label className="mt">Descreva em poucas palavras<textarea rows={2} value={desc} onChange={e=>setDesc(e.target.value)} placeholder="Ex.: Uma aventura de dois amigos robôs numa cidade futurista chuvosa"/></label>
      <div className="row-gap left mt"><button className="primary" disabled={!!busy||desc.trim().length<4} onClick={()=>pedir({...base(),modo:'descricao'})}>
        {busy==='descricao'?<Loader2 size={15} className="spin"/>:<Wand2 size={15}/>} Gerar proposta</button></div>
      <p className="hint">Sai uma proposta para você ler e editar. Nada é produzido nem postado.</p>
    </>:<>
      {radar&&<p className="hint ok">Usando {radar.length} vídeo(s) que você pesquisou no Radar. <button className="link-btn" onClick={()=>setRadar(null)}>Pesquisar de novo aqui</button></p>}
      <label className="mt">Direção (opcional; a IA respeita)<input value={desc} onChange={e=>setDesc(e.target.value)} placeholder="Ex.: para crianças, sem violência, com um gato"/></label>
      {!radar&&<details className="mt"><summary><Search size={13}/> Filtros da pesquisa ({f.plataforma}, {f.periodo_dias} dias{f.nicho?`, ${f.nicho}`:''})</summary><div className="small-grid">
        <label>Plataforma<select value={f.plataforma} onChange={e=>setF({...f,plataforma:e.target.value})}>{['youtube','tiktok','instagram','facebook','kwai'].map(r=><option key={r} value={r}>{r}{cap&&!cap.tendencias[r]?.disponivel?' (indisponível)':''}</option>)}</select></label>
        <label>Nicho<input value={f.nicho} onChange={e=>setF({...f,nicho:e.target.value})} placeholder="Padrão: histórias e animações feitas com IA"/></label>
        <label>Período<select value={f.periodo_dias} onChange={e=>setF({...f,periodo_dias:+e.target.value})}><option value={7}>7 dias</option><option value={30}>30 dias</option><option value={90}>90 dias</option></select></label>
        <label>Views mínimas<input type="number" min={0} value={f.views_min} onChange={e=>setF({...f,views_min:+e.target.value})}/></label>
        <label>Duração<select value={f.duracao} onChange={e=>setF({...f,duracao:e.target.value})}><option value="curto">Curto (até 4 min)</option><option value="medio">Médio (4 a 20 min)</option><option value="longo">Longo</option></select></label>
        <label>Ordenar por<select value={f.ordem} onChange={e=>setF({...f,ordem:e.target.value})}><option value="views">Views totais</option><option value="views_dia">Views por dia desde a publicação</option><option value="engajamento">Engajamento</option><option value="diversidade">Variedade de temas</option></select></label>
        <label>Idioma<input value={f.idioma} maxLength={2} onChange={e=>setF({...f,idioma:e.target.value})}/></label>
        <label>Região<input value={f.regiao} maxLength={2} onChange={e=>setF({...f,regiao:e.target.value.toUpperCase()})}/></label>
        <label>Formato<select value={formato} onChange={e=>setFormato(e.target.value)}><option value="9:16">Em pé</option><option value="16:9">Deitado</option><option value="1:1">Quadrado</option></select></label>
        <label>Estilo<select value={estilo} onChange={e=>setEstilo(e.target.value)}><option value="">A IA escolhe</option><option value="animado2d">Desenho 2D com personagens</option><option value="documentario">Documentário</option><option value="quadrinhos">Quadrinhos</option><option value="papel_recortado">Papel recortado</option><option value="pixel_art">Pixel art</option></select></label>
        <label className="check"><input type="checkbox" checked={ousada} onChange={e=>setOusada(e.target.checked)}/> Surpresa ousada</label>
        <label className="check"><input type="checkbox" checked={verificadas} onChange={e=>setVerificadas(e.target.checked)}/> Somente tendências verificadas</label>
      </div></details>}
      <div className="row-gap left mt">
        <button className="primary" disabled={!!busy} onClick={()=>surpreender()}>{busy==='surpresa'?<Loader2 size={15} className="spin"/>:<Shuffle size={15}/>} Buscar tendências e criar proposta original</button>
        <button className="subtle sm" disabled={!!busy} onClick={()=>pedir({...base(),modo:'sorteio'})}>{busy==='sorteio'?<Loader2 size={14} className="spin"/>:null} Sortear sem IA</button>
      </div>
      <p className="hint">A pesquisa usa só dados oficiais (YouTube). Sem acesso, o site avisa e não inventa ranking. A proposta é original: nada é copiado.</p>
    </>}
    {res?.precisa_confirmar&&<div className="mod-confirma"><p className="hint warn"><AlertTriangle size={13}/> {res.mensagem}</p>
      {res.tendencias&&<p className="hint">{res.tendencias.motivo}</p>}
      <button className="subtle sm" onClick={()=>surpreender({sem_tendencias:true,somente_verificadas:false})}>Sim, criar ideia fictícia</button></div>}
    {res?.tendencias&&!res.precisa_confirmar&&<Referencias t={res.tendencias}/>}
    {res&&res.propostas.length>0&&<div className="mod-props">{res.propostas.map(p=><CartaoProposta key={p.id} p={p} destinos={destinos} serieId={serieId} projetoId={projetoId}
      onMudou={mudar} outra={()=>ultimo&&pedir(ultimo)} onAplicado={onAplicado}/>)}
      {onUsarCampos&&<div className="row-gap left">{res.propostas.map((p,i)=><button key={p.id} className="subtle sm" onClick={()=>onUsarCampos(p.campos,p)}>{rotuloUsar||'Usar neste vídeo'}: proposta {i+1}</button>)}</div>}
    </div>}
  </div>;
}

/** Personagens da biblioteca (os mesmos das Séries) num vídeo único, fixados na versão de agora. */
export function EscolherDaBiblioteca({projetoId,garantirProjeto,onUsado}:{projetoId:string;garantirProjeto:()=>Promise<string>;onUsado:(nomes:Record<string,string>)=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const [itens,setItens]=useState<ItemBiblioteca[]|null>(null); const [sel,setSel]=useState<string[]>([]); const [busy,setBusy]=useState(false);
  const [img,setImg]=useState<Record<string,string>>({});
  const abrir=()=>biblioteca(cfg,'character').then(r=>setItens(r.itens)).catch(e=>toast(erroTexto(e),'erro'));
  if(!itens) return <button className="subtle sm" onClick={abrir}>Usar personagens da biblioteca</button>;
  return <div className="mod compacto">
    <div className="field-label">Personagens da biblioteca (os mesmos das Séries)</div>
    {!itens.length&&<p className="hint">Ainda não há personagens. Crie em Séries ou com "Criar com a IA" (Personagem).</p>}
    <div className="mod-pers">{itens.map(p=><label key={p.id} className="mod-per">
      {img[p.id]?<img src={img[p.id]} alt={p.nome}/>:<button className="link-btn" onClick={e=>{ e.preventDefault(); previaAsset(cfg,p.id).then(r=>r.png&&setImg(x=>({...x,[p.id]:r.png!}))).catch(()=>{}); }}><Eye size={12}/> ver</button>}
      <span className="check"><input type="checkbox" checked={sel.includes(p.id)} onChange={e=>setSel(e.target.checked?[...sel,p.id].slice(0,4):sel.filter(x=>x!==p.id))}/> <b>{p.nome}</b></span>
      <small className="muted">versão {p.versao}{p.status==='aprovado'?' • aprovado':''}</small></label>)}</div>
    <p className="hint">O vídeo guarda a versão de hoje: se o personagem mudar depois, este vídeo não muda (a não ser que você escolha de novo).</p>
    <div className="row-gap left"><button className="primary sm" disabled={busy||!sel.length} onClick={async()=>{ setBusy(true);
      try{ const pid=projetoId||await garantirProjeto(); const r=await usarNoProjeto(cfg,pid,sel); onUsado(Object.fromEntries(Object.entries(r.serie.personagens).map(([k,v])=>[k,v.nome||k])));
        toast('Personagens no vídeo. Gere o roteiro de novo para a IA escrever com eles, ou escolha quem aparece em cada cena.','ok'); setItens(null); }
      catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }}>{busy?<Loader2 size={14} className="spin"/>:null} Usar no vídeo</button>
      <button className="link-btn" onClick={()=>setItens(null)}>Fechar</button></div>
  </div>;
}

/** Personagens da biblioteca para vídeos em lote ou rotina: ficam fixados na versão escolhida (mudar o personagem depois não muda a rotina). */
export function ElencoFixado({valor,mudar}:{valor:{id:string;versao:number}[];mudar:(v:{id:string;versao:number}[])=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const [itens,setItens]=useState<ItemBiblioteca[]|null>(null);
  useEffect(()=>{ if(valor.length&&!itens) biblioteca(cfg,'character').then(r=>setItens(r.itens)).catch(()=>{}); },[valor.length,itens,cfg]);
  const abrir=()=>biblioteca(cfg,'character').then(r=>setItens(r.itens)).catch(e=>toast(erroTexto(e),'erro'));
  const nome=(id:string)=>itens?.find(x=>x.id===id)?.nome||id;
  return <div className="mt">
    <div className="field-label">Personagens da biblioteca nestes vídeos (opcional)</div>
    {valor.length>0&&<ul className="mod-mini">{valor.map(v=>{ const atual=itens?.find(x=>x.id===v.id)?.versao;
      return <li key={v.id}>{nome(v.id)} (versão {v.versao}){atual&&atual>v.versao&&<> • tem versão {atual} <button className="link-btn" onClick={()=>mudar(valor.map(x=>x.id===v.id?{...x,versao:atual}:x))}>usar a nova</button></>}
        {' '}<button className="link-btn" onClick={()=>mudar(valor.filter(x=>x.id!==v.id))}>tirar</button></li>; })}</ul>}
    {!itens?<button className="subtle sm" onClick={abrir}>Escolher personagens da biblioteca</button>
      :<div className="bib-lista">{itens.filter(x=>!valor.some(v=>v.id===x.id)).map(x=><button key={x.id} className="chip" disabled={valor.length>=4} onClick={()=>mudar([...valor,{id:x.id,versao:x.versao}])}>+ {x.nome} (v{x.versao})</button>)}
        {!itens.length&&<span className="hint">Nenhum personagem ainda. Crie em Séries ou com "Criar com a IA".</span>}</div>}
    {valor.length>0&&<p className="hint">Com personagens, o visual passa a ser desenho 2D. Cada vídeo usa a versão marcada aqui, mesmo que o personagem mude depois.</p>}
  </div>;
}

/** Modelos guardados na biblioteca (histórias e pacotes) para virar assunto. Só preenche: não produz nada. */
export function ModelosBiblioteca({onUsar}:{onUsar:(titulo:string,item:ItemBiblioteca)=>void}){
  const {toast}=useApp(); const cfg=useCfg();
  const [itens,setItens]=useState<ItemBiblioteca[]|null>(null);
  if(!itens) return <button className="subtle sm" onClick={()=>Promise.all(['story','scene_package','series_bible'].map(t=>biblioteca(cfg,t))).then(rs=>setItens(rs.flatMap(r=>r.itens))).catch(e=>toast(erroTexto(e),'erro'))}>Usar um modelo da biblioteca</button>;
  return <div className="mod compacto">
    <div className="field-label">Modelos guardados</div>
    {!itens.length&&<p className="hint">Nenhum modelo ainda. Em "Criar com a IA", use "Salvar como modelo".</p>}
    <ul className="mod-ref-lista">{itens.map(x=><li key={x.id}><b>{x.nome}</b><small className="muted">{x.descricao} • versão {x.versao} • {x.origem==='ia'?'gerado com IA':x.origem==='codigo'?'sorteio do código':x.origem}</small>
      <button className="link-btn" onClick={()=>onUsar(x.nome,x)}>Usar como assunto</button></li>)}</ul>
    <button className="link-btn" onClick={()=>setItens(null)}>Fechar</button>
  </div>;
}
