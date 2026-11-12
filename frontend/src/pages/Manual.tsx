import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, FileText, ImagePlus, Loader2, Mic, Music, Play, Sparkles, Trash2, Volume2, Wand2, SlidersHorizontal, RotateCcw, ListChecks, Settings2 } from 'lucide-react';
import { useApp } from '../state';
import { transcrever, transcreverGemini } from '../lib/transcribe';
import type { Cue } from '../lib/captions';
import EditorVideo from '../components/EditorVideo';
import { deSinc, type Proj } from '../lib/editor';
import {
  MODELO_ROTEIRO, OPCOES_PADRAO, apagarArquivo, audioDe, batidas, conferirImagensIA, guardarArquivo, lerQuadros,
  listarArquivos, midias, mono16k, narracoesDe, prepararMidia, sincronizar,
  type Arquivo, type Formato, type Opcoes, type Sinc, type TipoArq,
} from '../lib/montagem';

const CHAVE='studio_manual';
type Salvo={texto:string;o:Opcoes;sinc:Sinc|null;cues:Cue[]|null;cuesDe:string};
function ler():Salvo{ try{ const j=JSON.parse(localStorage.getItem(CHAVE)||'null'); if(j) return {texto:j.texto||'',o:{...OPCOES_PADRAO,...j.o},sinc:j.sinc||null,cues:j.cues||null,cuesDe:j.cuesDe||''}; }catch{ /* vazio */ } return {texto:'',o:OPCOES_PADRAO,sinc:null,cues:null,cuesDe:''}; }
const fmt=(s:number)=>{ s=Math.max(0,s); const m=Math.floor(s/60); const x=s-m*60; return `${m}:${x<10?'0':''}${x.toFixed(1)}`; };

const AREAS:[TipoArq,string,string,string,typeof ImagePlus][]=[
  ['quadro','Imagens e vídeos dos quadros','image/*,video/*','Dê nomes com o número do quadro (quadro-01.png, 2.jpg...). Sem número, entram na ordem.',ImagePlus],
  ['narracao','Narração / vozes','audio/*,video/*','Um arquivo só (o site transcreve e acha onde cada quadro começa), um por fala (quadro-01.mp3, quadro-02-a.mp3...) ou os takes enviados pelo Estúdio de vozes.',Mic],
  ['trilha','Trilha sonora','audio/*','Toca do começo ao fim e abaixa sozinha quando alguém fala. Com [TRILHA: nome] no roteiro, troca de música naquele quadro.',Music],
  ['efeito','Efeitos sonoros','audio/*','O nome do arquivo é comparado com as marcações [SOM: ...] (ex.: porta-batendo.mp3). O que faltar, o site cria.',Volume2],
];

export default function Manual(){
  const {settings,toast}=useApp();
  const ini=useMemo(ler,[]);
  const [texto,setTexto]=useState(ini.texto); const [o,setO]=useState<Opcoes>(ini.o);
  const [sinc,setSinc]=useState<Sinc|null>(ini.sinc); const [cues,setCues]=useState<{de:string;lista:Cue[]}|null>(ini.cues?{de:ini.cuesDe,lista:ini.cues}:null);
  const [arqs,setArqs]=useState<Arquivo[]>([]); const [carregado,setCarregado]=useState(false);
  const [usarIA,setUsarIA]=useState(false); const [ocupado,setOcupado]=useState('');
  const [proj,setProj]=useState<Proj|null>(()=>{ try{ return JSON.parse(localStorage.getItem(CHAVE+'_editor')||'null'); }catch{ return null; } });
  const [versao,setVersao]=useState(0);
  const salvarProj=(n:Proj|null)=>{ try{ if(n) localStorage.setItem(CHAVE+'_editor',JSON.stringify(n)); else localStorage.removeItem(CHAVE+'_editor'); }catch{ /* cheio */ } };
  // "editado" = a pessoa já mexeu no editor à mão; daí uma sincronização nova não troca o projeto sozinha.
  const [editado,setEditadoS]=useState(()=>{ try{ const v=localStorage.getItem(CHAVE+'_editado'); return v==null?!!localStorage.getItem(CHAVE+'_editor'):v==='1'; }catch{ return false; } });
  const setEditado=(v:boolean)=>{ setEditadoS(v); try{ localStorage.setItem(CHAVE+'_editado',v?'1':'0'); }catch{ /* cheio */ } };
  const [pendente,setPendente]=useState(false);
  const [aba,setAba]=useState<''|'roteiro'|'arquivos'|'conferencia'|'opcoes'>(ini.sinc||proj?'':'roteiro');
  function abrirEditor(s:Sinc|null=sinc,lista:Arquivo[]=arqs){ if(!s) return; const n=deSinc(s,lista,o); setProj(n); salvarProj(n); setEditado(false); setPendente(false); setVersao(v=>v+1); setTimeout(()=>document.querySelector('.ed')?.scrollIntoView({behavior:'smooth',block:'start'}),100); }
  const quadros=useMemo(()=>lerQuadros(texto),[texto]);
  // Associações escolhidas à mão na conferência (por número do quadro). "-" = sem imagem.
  const [manual,setManual]=useState<Record<number,string>>(()=>{ try{ return JSON.parse(localStorage.getItem(CHAVE+'_manual')||'{}')||{}; }catch{ return {}; } });
  useEffect(()=>{ try{ localStorage.setItem(CHAVE+'_manual',JSON.stringify(manual)); }catch{ /* cheio */ } },[manual]);
  const [soAvisos,setSoAvisos]=useState(false);
  const narUnica=arqs.filter(a=>a.tipo==='narracao'); const cuesOk=narUnica.length===1&&cues?.de===narUnica[0].id?cues.lista:null;
  // Conferência: a mesma conta da sincronização, feita na hora, sem ouvir a narração.
  const rascunho=useMemo(()=>carregado&&quadros.length?sincronizar({quadros,arquivos:arqs,cues:cuesOk,batidas:null,opcoes:o,manual:{midia:manual}}):null,[carregado,quadros,arqs,cuesOk,o,manual]);
  const assinatura=JSON.stringify([texto,arqs.map(a=>a.id),manual,o.durPadrao]);
  const [assinaturaSinc,setAssinaturaSinc]=useState(()=>{ try{ return localStorage.getItem(CHAVE+'_ass')||''; }catch{ return ''; } });
  const tocarArq=(id:string)=>{ const a=arqs.find(x=>x.id===id); if(!a) return; ouvindo.current?.pause(); const el=new Audio(URL.createObjectURL(a.blob)); ouvindo.current=el; el.play().catch(()=>{}); };
  const ouvindo=useRef<HTMLAudioElement|null>(null);

  useEffect(()=>{ (async()=>{ try{ const l=await listarArquivos(); for(const a of l) if(a.tipo==='quadro'){ try{ await prepararMidia(a); }catch{ /* arquivo estragado */ } } setArqs(l);
    if(ini.sinc&&!proj){ const n=deSinc(ini.sinc,l,ini.o); setProj(n); salvarProj(n); setEditado(false); } }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); } setCarregado(true); })(); },[]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(()=>{ try{ localStorage.setItem(CHAVE,JSON.stringify({texto,o,sinc,cues:cues?.lista||null,cuesDe:cues?.de||''})); }catch{ /* cheio */ } },[texto,o,sinc,cues]);
  async function enviar(tipo:TipoArq,fs:FileList|null,doEditor=false):Promise<Arquivo[]>{
    if(!fs?.length) return []; const novos:Arquivo[]=[]; const erros:string[]=[];
    for(const f of Array.from(fs)){ setOcupado(`Guardando ${f.name}`); try{ novos.push(await guardarArquivo(f,tipo)); }catch(e){ erros.push(e instanceof Error?e.message:String(e)); } }
    setOcupado(''); setArqs(x=>[...x,...novos]);
    if(erros.length) toast(erros.slice(0,2).join(' | '),'erro'); else if(!doEditor) toast(`${novos.length} arquivo(s) guardados. Quando terminar de enviar, toque em Analisar e sincronizar.`,'ok');
    return novos;
  }
  async function remover(a:Arquivo){ await apagarArquivo(a.id); setArqs(x=>x.filter(y=>y.id!==a.id)); }
  async function limpar(tipo:TipoArq){ for(const a of arqs.filter(x=>x.tipo===tipo)) await apagarArquivo(a.id); setArqs(x=>x.filter(y=>y.tipo!==tipo)); }

  async function analisar(){
    if(!quadros.length){ toast('Cole o roteiro de quadros primeiro.','erro'); return; }
    try{
      const nars=arqs.filter(a=>a.tipo==='narracao'); let lista:Cue[]|null=null;
      if(nars.length===1&&quadros.some(q=>q.falas.length)){
        if(cues&&cues.de===nars[0].id) lista=cues.lista;
        else{
          setOcupado('Preparando a narração para ouvir'); const sm=await mono16k(await audioDe(nars[0]));
          try{ lista=await transcrever(sm,settings.whisperModel,settings.idioma||'portuguese',(s,p)=>setOcupado(`Ouvindo a narração: ${s}${p?` ${p}%`:''}`)); }
          catch(e){ if(!settings.geminiKey) throw e; lista=await transcreverGemini(sm,settings.geminiKey,settings.idioma||'portuguese',(s,p)=>setOcupado(`${s} ${p}%`)); }
          setCues({de:nars[0].id,lista});
        }
      }
      const trs=arqs.filter(a=>a.tipo==='trilha'); let bt:number[]|null=null;
      if(trs.length&&o.naBatida&&!nars.length){ setOcupado('Procurando a batida da música'); bt=batidas(await audioDe(trs[0])); }
      let ia:Map<number,string>|undefined;
      if(usarIA){ if(!settings.geminiKey) toast('Para a IA conferir as imagens, coloque a chave do Gemini em Chaves e ajustes.','info');
        else{ setOcupado('A IA está olhando as imagens'); try{ ia=await conferirImagensIA(settings.geminiKey,quadros,arqs.filter(a=>a.tipo==='quadro')); }catch(e){ toast('A IA não conseguiu conferir as imagens: '+(e instanceof Error?e.message:String(e)),'info'); } } }
      const s=sincronizar({quadros,arquivos:arqs,cues:lista,batidas:bt,opcoes:o,imagensIA:ia,manual:{midia:manual}});
      if(ia?.size) s.notas.unshift(`A IA escolheu a imagem de ${ia.size} quadro(s) pelo que aparece nelas.`);
      setSinc(s); setAssinaturaSinc(assinatura); try{ localStorage.setItem(CHAVE+'_ass',assinatura); }catch{ /* cheio */ }
      if(proj&&editado&&proj.clips.length){ setPendente(true); toast(`Sincronizei ${s.quadros.length} quadros em ${fmt(s.total)}. Como você já editou o vídeo, o editor ficou como estava. Toque em "Usar a nova sincronização" se quiser trocar.`,'info'); }
      else{ abrirEditor(s); setAba(''); toast(`Pronto: ${s.quadros.length} quadros em ${fmt(s.total)}. Já está no editor aqui embaixo: toque em ▶ para ver.`,'ok'); }
    }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }
    finally{ setOcupado(''); }
  }
  const imgs=arqs.filter(a=>a.tipo==='quadro');
  const nome=(id:string)=>arqs.find(a=>a.id===id)?.nome||'';
  const resumo=`${quadros.length} quadros • ${quadros.reduce((a,q)=>a+q.falas.length,0)} falas • ${quadros.reduce((a,q)=>a+q.sons.length,0)} efeitos • ${quadros.filter(q=>q.trilha).length} marcações de trilha`;

  const nAvisos=rascunho?rascunho.quadros.filter(q=>q.avisos?.length).length:0;
  const ABAS:[typeof aba,string,typeof FileText,string][]=[['roteiro','Roteiro',FileText,quadros.length?`${quadros.length} quadros`:'colar'],['arquivos','Arquivos',ImagePlus,arqs.length?`${arqs.length}`:'enviar'],['conferencia','Conferência',ListChecks,rascunho?(nAvisos?`${nAvisos} aviso(s)`:'tudo certo'):'—'],['opcoes','Opções',Settings2,o.formato]];
  const vazio:Proj={clips:[],formato:o.formato,abaixarTrilha:true};

  return <div className="manual">
   <section className="panel prep">
    <div className="prep-topo">
     <div className="prep-abas" role="tablist" aria-label="Preparar">{ABAS.map(([k,n,I,r])=><button key={k} role="tab" aria-selected={aba===k} className={aba===k?'on':''} onClick={()=>setAba(a=>a===k?'':k)} data-aba={k}><I size={15}/> {n}<small>{r}</small></button>)}</div>
     <button className="primary" disabled={!!ocupado||!quadros.length} onClick={analisar} title={quadros.length?'':'Cole o roteiro de quadros primeiro'}>{ocupado?<Loader2 size={16} className="spin"/>:<Wand2 size={16}/>} Analisar e sincronizar</button>
     {aba&&<button className="icon-btn" onClick={()=>setAba('')} aria-label="Recolher" title="Recolher"><ChevronDown size={16}/></button>}
    </div>
    {!aba&&<p className="hint prep-dica">{sinc?`Sincronizado: ${sinc.quadros.length} quadros em ${fmt(sinc.total)}. Toque em uma parte acima para mudar o roteiro, os arquivos ou as opções.`:quadros.length?'Roteiro lido. Envie os arquivos e toque em Analisar e sincronizar. O resultado abre no editor aqui embaixo.':'Cole o roteiro e envie os arquivos para o site montar tudo, ou vá direto ao editor abaixo e abra um vídeo pronto.'}</p>}
    {ocupado&&<p className="hint mt"><Loader2 size={14} className="spin"/> {ocupado}</p>}
    {pendente&&<p className="conf-aviso mt">A sincronização nova está pronta, mas o editor ainda mostra a sua edição. <button className="link-btn" onClick={()=>abrirEditor()}>Usar a nova sincronização</button> (a edição feita à mão é trocada).</p>}
    {sinc&&!editado&&assinaturaSinc&&assinaturaSinc!==assinatura&&<p className="conf-aviso mt">⚠ O roteiro, os arquivos ou as escolhas mudaram depois da última sincronização. Toque em Analisar e sincronizar de novo para o editor usar o que está na conferência.</p>}
    {sinc&&sinc.notas.length>0&&aba!==''&&<ul className="manual-notas">{sinc.notas.map(n=><li key={n}>{n}</li>)}</ul>}

    <div className="prep-corpo" hidden={aba!=='roteiro'}>
     <div className="row-gap left"><button className="subtle sm" onClick={()=>setTexto(t=>t.trim()?t:MODELO_ROTEIRO)} disabled={!!texto.trim()}>Usar modelo</button></div>
    <p className="hint">Um bloco por quadro, começando com <b>QUADRO 1</b>. Dentro: <b>VISUAL:</b> o que aparece, falas <b>NOME: texto</b>, <b>[SOM: porta batendo]</b> (com <b>@1.5</b> para tocar 1,5 s depois do início do quadro), <b>[TRILHA: tensa]</b>, <b>MOVIMENTO: aproximar</b> e, se quiser, o tempo no título: <b>QUADRO 2 (0:04–0:09)</b> ou <b>(4 s)</b>. Sem tempo, o site calcula pela narração, pelos vídeos ou pela duração padrão.</p>
    <textarea className="roteiro-quadros" rows={12} value={texto} onChange={e=>setTexto(e.target.value)} placeholder={MODELO_ROTEIRO} aria-label="Roteiro de quadros"/>
    {quadros.length>0&&<p className="hint">Li: <b>{resumo}</b></p>}
    </div>
    <div className="prep-corpo" hidden={aba!=='arquivos'}>
    {!carregado&&<p className="hint"><Loader2 size={14} className="spin"/> Abrindo os arquivos guardados...</p>}
    <div className="manual-areas">{AREAS.map(([tipo,tit,acc,dica,I])=>{ const l=arqs.filter(a=>a.tipo===tipo); return <div key={tipo} className="manual-area">
     <div className="manual-area-top"><b><I size={15}/> {tit}</b>{l.length>0&&<button className="link-btn" onClick={()=>limpar(tipo)}>Tirar todos</button>}</div>
     <small className="hint">{dica}</small>
     <label className="subtle sm vc-upload mt">Enviar<input type="file" accept={acc} multiple hidden data-area={tipo} onChange={e=>{ enviar(tipo,e.target.files); e.target.value=''; }}/></label>
     {l.length>0&&<ul className="manual-lista">{l.map(a=><li key={a.id}>{a.tipo==='quadro'&&midias.get(a.id)?.tipo==='imagem'?<img src={(midias.get(a.id)!.el as HTMLImageElement).src} alt=""/>:null}<span title={a.nome}>{a.nome}</span><small>{a.duracao?fmt(a.duracao):''}</small><button className="icon-btn" onClick={()=>remover(a)} aria-label={'Tirar '+a.nome}><Trash2 size={13}/></button></li>)}</ul>}
    </div>; })}</div>
    </div>
    <div className="prep-corpo" hidden={aba!=='conferencia'}>
     {!rascunho&&<p className="hint">Cole o roteiro para ver aqui o que vai em cada quadro.</p>}
     {rascunho&&<>
     <div className="section-head"><span className="hint">{rascunho.quadros.length} quadros • {nAvisos} com aviso</span></div>
    <p className="hint">Veja o que vai em cada quadro antes de sincronizar. Para trocar a imagem, escolha outra na lista: não precisa renomear nem enviar de novo. A prévia e o vídeo final usam exatamente estas escolhas.</p>
    <div className="row-gap left"><label className="check"><input type="checkbox" checked={soAvisos} onChange={e=>setSoAvisos(e.target.checked)}/> Mostrar só os quadros com aviso</label>
     {Object.keys(manual).length>0&&<button className="link-btn" onClick={()=>setManual({})}>Voltar tudo para o automático</button>}</div>
    {rascunho.narracao==='unica'&&!cuesOk&&<p className="hint">Com uma narração só, o tempo de cada quadro com fala é calculado ao sincronizar (o site ouve a narração). Aqui aparece a duração provisória.</p>}
    <div className="conf-lista">{rascunho.quadros.filter(q=>!soAvisos||q.avisos?.length).map(q=>{ const rot=quadros.find(x=>x.n===q.n); const m=q.midia?midias.get(q.midia):undefined; const nars=narracoesDe(q);
     return <article key={q.n} className={'conf-q'+(q.avisos?.length?' aviso':'')} data-quadro={q.n}>
      <div className="conf-thumb">{m?.tipo==='imagem'?<img src={(m.el as HTMLImageElement).src} alt=""/>:m?<span>vídeo</span>:<span>sem imagem</span>}</div>
      <div className="conf-info">
       <b>Quadro {q.n}{q.titulo?` — ${q.titulo}`:''}</b>
       <div className="conf-linha"><span className="conf-rot">Imagem</span>
        <select value={manual[q.n]??''} onChange={e=>setManual(x=>{ const n={...x}; if(e.target.value) n[q.n]=e.target.value; else delete n[q.n]; return n; })} aria-label={`Arquivo do quadro ${q.n}`}>
         <option value="">Automático{q.midia&&manual[q.n]==null?`: ${nome(q.midia)}`:''}</option>{imgs.map(a=><option key={a.id} value={a.id}>{a.nome}</option>)}<option value="-">Sem imagem</option></select>
        {q.origemMidia&&<small className="conf-origem">{q.origemMidia}</small>}</div>
       {(rot?.falas.length||0)>0&&<div className="conf-linha"><span className="conf-rot">Fala</span><span className="conf-falas">{rot!.falas.map((f,k)=><span key={k} className={nars[k]||rascunho.narracao!=='separada'?'':'falta'}><b>{f.nome}:</b> {f.texto}{nars[k]&&<button className="icon-btn" onClick={()=>tocarArq(nars[k].arquivo)} aria-label={`Ouvir fala ${k+1} do quadro ${q.n}`} title={nome(nars[k].arquivo)}><Play size={11}/></button>}</span>)}</span></div>}
       <div className="conf-linha"><span className="conf-rot">Duração</span><span>{q.dur.toFixed(1)} s <small className="conf-origem">{rascunho.narracao==='unica'&&!cuesOk&&q.fonteDur!=='roteiro'?'provisória':`veio do ${q.fonteDur==='narração'?'tempo da narração':q.fonteDur==='áudio'?'áudio das falas':q.fonteDur||'padrão'}`}</small></span></div>
       {q.sons.length>0&&<div className="conf-linha"><span className="conf-rot">Efeitos</span><span>{q.sons.map(s=>`${s.desc} (${s.arquivo?nome(s.arquivo):'feito pelo site'})`).join(' • ')}</span></div>}
       {q.avisos?.map(a=><p key={a} className="conf-aviso">⚠ {a}</p>)}
      </div>
     </article>; })}</div>
     </>}
    </div>
    <div className="prep-corpo" hidden={aba!=='opcoes'}>
     <p className="hint">Valem para a próxima sincronização. Depois, cada bloco pode ser ajustado no editor.</p>
    <div className="small-grid">
     <label>Formato<select value={o.formato} onChange={e=>setO({...o,formato:e.target.value as Formato})}><option value="9:16">Vertical 9:16 (Reels, TikTok, Shorts)</option><option value="16:9">Horizontal 16:9 (YouTube)</option><option value="1:1">Quadrado 1:1</option></select></label>
     <label>Duração padrão do quadro (s)<input type="number" min={0.5} max={60} step={0.5} value={o.durPadrao} onChange={e=>setO({...o,durPadrao:Math.max(0.5,+e.target.value||3)})}/></label>
     <label>Transição<select value={o.transicao} onChange={e=>setO({...o,transicao:e.target.value as Opcoes['transicao']})}><option value="fade">Suave (0,4 s)</option><option value="corte">Corte seco</option></select></label>
     <label>Volume da trilha (%)<input type="number" min={0} max={100} step={5} value={o.volTrilha} onChange={e=>setO({...o,volTrilha:Math.max(0,Math.min(100,+e.target.value||0))})}/></label>
     <label>Volume dos efeitos (%)<input type="number" min={0} max={200} step={5} value={o.volEfeitos} onChange={e=>setO({...o,volEfeitos:Math.max(0,Math.min(200,+e.target.value||0))})}/></label>
    </div>
    <div className="row-gap left mt">
     <label className="check"><input type="checkbox" checked={o.legendas} onChange={e=>setO({...o,legendas:e.target.checked})}/> Legenda com as falas</label>
     <label className="check"><input type="checkbox" checked={o.naBatida} onChange={e=>setO({...o,naBatida:e.target.checked})}/> Cortar na batida da música (quando não há narração)</label>
     <label className="check"><input type="checkbox" checked={usarIA} onChange={e=>setUsarIA(e.target.checked)}/> <Sparkles size={13}/> IA confere qual imagem é de cada quadro (Gemini)</label>
    </div>
    </div>
   </section>

   <section className="panel">
    <div className="section-head"><h2><SlidersHorizontal size={18}/> Editor</h2>
     <span className="hint">Roda tudo no seu navegador. Nada é enviado para fora.</span>
     {sinc&&proj&&proj.clips.length>0&&<button className="subtle sm" onClick={()=>abrirEditor()} title="Joga fora a edição e começa de novo pela sincronização"><RotateCcw size={14}/> Recomeçar pela sincronização</button>}</div>
    {!carregado?<p className="hint"><Loader2 size={14} className="spin"/> Abrindo os arquivos guardados...</p>
     :<EditorVideo key={versao} inicial={proj||vazio} arquivos={arqs} onEnviar={(t,fs)=>enviar(t,fs,true)} onChange={(n,manual)=>{ setProj(n); salvarProj(n); if(manual&&!editado) setEditado(true); }}/>}
   </section>
  </div>;
}
