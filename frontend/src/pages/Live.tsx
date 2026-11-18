import { useEffect, useState } from 'react';
import { CircleStop, Loader2, Radio, Scissors, Send } from 'lucide-react';
import { useApp } from '../state';
import { useCfg, useServidor, erroTexto } from '../components/Servidor2';
import { comecarLive, pararLive, salvarCfgLive, verLive, type CfgLive, type Live as TLive } from '../lib/live';

const REDES:[string,string][]=[['youtube','YouTube'],['tiktok','TikTok'],['instagram','Instagram'],['facebook','Facebook']];
const ORIGENS:[string,string][]=[['meu','É do meu canal'],['autorizado','O dono autorizou'],['regra','O canal tem regra pública que permite cortes']];
const ESTADO:Record<string,[string,string]>={gravando:['gravando','ok'],terminando:['terminando o último bloco','warn'],terminada:['terminada',''],erro:['parou com erro','bad']};
const BLOCO:Record<string,string>={na_fila:'na fila',cortando:'cortando agora',feito:'feito',erro:'erro'};
const hora=(t:number|null|undefined)=>t?new Date(t*1000).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'}):'';

export default function Live(){
  const {toast}=useApp(); const cfg=useCfg();
  const r=useServidor(c=>verLive(c),10);
  const [link,setLink]=useState(''); const [origem,setOrigem]=useState(''); const [c,setC]=useState<CfgLive|null>(null); const [busy,setBusy]=useState(false);
  useEffect(()=>{ if(r.dados&&!c) setC(r.dados.config); },[r.dados,c]);
  if(!cfg.servidor) return <section className="panel"><p className="hint">Conecte o servidor do celular em Ajustes para usar a parte Live.</p></section>;
  if(!r.dados||!c) return <section className="panel">{r.erro?<p className="hint bad">{/rota não encontrada/i.test(r.erro)?<>O servidor do celular ainda está na versão antiga, sem a parte Live. No Termux rode: <code>cd ~/ia &amp;&amp; git pull</code> e depois <code>cd servidor &amp;&amp; bash iniciar-termux.sh link</code>.</>:r.erro}</p>:<p className="muted"><Loader2 size={14} className="spin"/> Carregando…</p>}</section>;
  const d=r.dados; const ativa=d.lives.find(x=>x.id===d.ativa);
  const mudar=(p:Partial<CfgLive>)=>setC({...c,...p});
  async function fazer(f:()=>Promise<unknown>,msg:string){ setBusy(true); try{ await f(); toast(msg,'ok'); await r.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(false); } }
  const num=(k:keyof CfgLive,rot:string,min:number,max:number,dica:string)=><label className="field"><span>{rot}</span>
    <input type="number" min={min} max={max} value={c[k] as number} onChange={e=>mudar({[k]:Number(e.target.value)} as Partial<CfgLive>)}/><small className="muted">{dica}</small></label>;
  return <div className="live-pagina">
    {!d.esteira&&<section className="panel bloqueado"><p className="hint bad">Ligue a esteira dos 5 agentes (editor e diretor) na Central &gt; Qualidade e revisões. Sem ela nada da live é postado.</p></section>}
    {ativa?<LiveAtiva lv={ativa} busy={busy} ocupando={d.ocupando} parar={()=>{ if(window.confirm('Parar a gravação? Os blocos já gravados ainda viram cortes.')) fazer(()=>pararLive(cfg,ativa.id),'Gravação parada.'); }}/>
    :<section className="panel">
      <h3><Radio size={16}/> Gravar uma live</h3>
      <p className="hint">O celular grava a live em blocos. Quando um bloco fecha, o Agente 1 acha os melhores momentos, o editor e o diretor conferem, e o que for aprovado <b>posta na hora</b>, sem esperar a programação. Reprovado não sai.</p>
      <label className="field"><span>Link da live (YouTube)</span><input value={link} onChange={e=>setLink(e.target.value)} placeholder="https://www.youtube.com/live/..."/></label>
      <label className="field"><span>De quem é a live?</span><select value={origem} onChange={e=>setOrigem(e.target.value)}><option value="">Escolha…</option>{ORIGENS.map(([k,t])=><option key={k} value={k}>{t}</option>)}</select>
        <small className="muted">Se o canal já está aprovado em Agente 1, vale a aprovação dele.</small></label>
      <div className="field"><span>Postar em</span><div className="row-gap left">{REDES.map(([k,t])=><label key={k} className="check"><input type="checkbox" checked={c.redes.includes(k)} onChange={e=>mudar({redes:e.target.checked?[...c.redes,k]:c.redes.filter(x=>x!==k)})}/> {t}</label>)}</div></div>
      <label className="check"><input type="checkbox" checked={c.postar} onChange={e=>mudar({postar:e.target.checked})}/> Postar sozinho assim que o diretor aprovar</label>
      <details><summary>Mais opções</summary><div className="live-grid">
        {num('bloco_min','Tamanho do bloco (min)',3,20,'Menor = posta mais rápido. Maior = acha momentos melhores.')}
        {num('cortes_por_bloco','Cortes por bloco',1,3,'No máximo, por bloco.')}
        {num('nota_min','Nota mínima do momento',40,95,'Só os momentos com nota alta viram corte.')}
        {num('max_posts','Máximo de posts nesta live',1,30,'Os aprovados a mais vão para o estoque normal.')}
        {num('intervalo_min','Intervalo entre posts (min)',0,240,'0 = posta na hora.')}
        {num('max_horas','Gravar no máximo (horas)',1,12,'Para sozinho depois disso.')}
      </div></details>
      <div className="row-gap left" style={{marginTop:10}}>
        <button className="primary" disabled={busy||!link||!d.esteira} onClick={()=>fazer(async()=>{ await salvarCfgLive(cfg,c); await comecarLive(cfg,{...c,link,origem}); },'Gravando a live.')}><Radio size={14}/> Começar a gravar</button>
      </div>
      <p className="hint">Cada bloco leva alguns minutos para virar corte (ouvir a fala, editar e conferir). O corte sai alguns minutos depois do momento na live. A IA ouve cada bloco, então gasta a sua chave do Gemini.</p>
    </section>}
    {d.lives.filter(x=>x.id!==d.ativa).slice(0,5).map(x=><LiveAtiva key={x.id} lv={x} busy={busy}/>)}
  </div>;
}

function LiveAtiva({lv,busy,parar,ocupando}:{lv:TLive;busy:boolean;parar?:()=>void;ocupando?:string}){
  const [e,classe]=ESTADO[lv.estado]||[lv.estado,''];
  const aprovados=lv.cortes.filter(c=>['pronto','agendado','postado'].includes(c.status)).length;
  return <section className={'panel'+(lv.estado==='gravando'?' a1-agora':'')}>
    <h3>{lv.estado==='gravando'?<Loader2 size={16} className="spin"/>:<Radio size={16}/>} {lv.titulo} <span className={'tag '+classe}>{e}</span></h3>
    <p className="muted">Começou às {hora(lv.inicio)}{lv.fim?` · terminou às ${hora(lv.fim)}`:''}{lv.motivo_fim?` · ${lv.motivo_fim}`:''}</p>
    <div className="pd-metricas">
      <div className="es-ag"><b>{lv.blocos.length}</b><span>blocos gravados</span></div>
      <div className="es-ag"><b>{lv.cortes.length}</b><span>cortes feitos</span></div>
      <div className="es-ag"><b>{aprovados}</b><span>aprovados pelo diretor</span></div>
      <div className="es-ag"><b>{lv.postados}/{lv.cfg.max_posts}</b><span>enviados para postar</span></div>
    </div>
    {lv.blocos.some(b=>b.estado==='na_fila')&&!lv.blocos.some(b=>b.estado==='cortando')&&ocupando&&<p className="hint warn">Os blocos esperam a vez: o celular está terminando "{ocupando}". Assim que acabar, a Live vem primeiro (o Agente 1 automático espera).</p>}
    {lv.blocos.length>0&&<ul className="rq-lista">{lv.blocos.slice(-6).reverse().map(b=><li key={b.n}><span className={'tag '+(b.estado==='cortando'?'ok':b.estado==='erro'?'bad':'')}>{BLOCO[b.estado]||b.estado}</span> <Scissors size={12}/> Bloco {b.n}{b.msg?<> · <small className="muted">{b.msg}</small></>:null}</li>)}</ul>}
    {lv.cortes.length>0&&<ul className="rq-lista">{lv.cortes.slice(-8).reverse().map(c=><li key={c.id}><Send size={12}/> {c.titulo} <span className={'tag '+(c.status==='reprovado'?'bad':c.status==='postado'||c.status==='agendado'?'ok':'')}>{
      c.status==='agendado'?(c.quando&&c.quando>Date.now()/1000?`posta às ${hora(c.quando)}`:'postando'):c.status==='postado'?'postado':c.status==='reprovado'?'reprovado pelo diretor':c.status==='pronto'?'no estoque':c.status}</span>
      {c.nota!=null&&<small className="muted"> nota {c.nota}</small>}{Object.entries(c.links||{}).filter(([,u])=>u).map(([rd,u])=><a key={rd} className="help-link" href={u} target="_blank" rel="noreferrer"> {rd}</a>)}</li>)}</ul>}
    {lv.erro&&<p className="hint bad">{lv.erro}</p>}
    {parar&&<button className="sm" disabled={busy} onClick={parar}><CircleStop size={14}/> Parar a gravação</button>}
  </section>;
}
