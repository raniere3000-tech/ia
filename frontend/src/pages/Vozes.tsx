import { useEffect, useMemo, useRef, useState } from 'react';
import { CheckCircle2, Dices, Volume2, Download, FileAudio, FileText, FlaskConical, KeyRound, Loader2, Mic, Package, Plus, RotateCcw, Star, Trash2, Upload, Users, Wand2 } from 'lucide-react';
import JSZip from 'jszip';
import { FICHAS_PRONTAS, GUIA_FICHA } from '../lib/fichasPadrao';
import { gerarSom, receitaDe, type FonteSom } from '../lib/sons';
/** Sons de fundo (ambiente) já começam tocando junto com a fala seguinte, mais baixos. */
const AMBIENTE=/murm|multid|taverna|chuva|fogo|fogueira|vento|tens|ambiente|fundo|clima/i;
import { useApp } from '../state';
import { baixar } from '../lib/exporter';
import { uid, store } from '../lib/store';
import {
  EMOCOES, MODELOS_TTS, aplicarFicha, rotuloIntensidade, vozAleatoria, generoDaVoz, type Genero, lerFichas, vozDoNome, VOZES_TTS, descreverVoz, gerarVoz, lerRoteiro, listar, montarEpisodio, previaTempo, nomeTake, novoPersonagem, pedidoTTS, rotulo, salvar, salvarVarios, apagar, srt,
  type FichaLida, type Fala, type LinhaRoteiro, type Personagem, type Projeto, type Take,
} from '../lib/vozes';

type Aba = 'elenco'|'lab'|'roteiro'|'final';
const fmt=(s:number)=>`${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}.${Math.floor((s%1)*10)}`;
const AJ=['voz','modelo','genero','gravidade','ritmo','energia','intensidade','emocao','sotaque','descricao'] as const;
const ajustesDe=(p:Personagem)=>JSON.stringify(Object.fromEntries(AJ.map(k=>[k,p[k]])));

/** Player de um take guardado (cria e libera o endereço do áudio). */
function Audio({blob}:{blob:Blob}){
  const url=useMemo(()=>URL.createObjectURL(blob),[blob]);
  useEffect(()=>()=>URL.revokeObjectURL(url),[url]);
  return <audio src={url} controls preload="none" className="take-audio"/>;
}

export default function Vozes(){
  const {settings,toast,go}=useApp();
  const [projetos,setProjetos]=useState<Projeto[]>([]);
  const [pid,setPid]=useState(()=>store.get('studio_vozes_projeto')||'');
  const [pers,setPers]=useState<Personagem[]>([]);
  const [falas,setFalas]=useState<Fala[]>([]);
  const [takes,setTakes]=useState<Take[]>([]);
  const [aba,setAba]=useState<Aba>('elenco'); const [labPid,setLabPid]=useState('');
  const [carregado,setCarregado]=useState(false);
  const [ocupado,setOcupado]=useState<{txt:string;pct:number}|null>(null); const parar=useRef(false);
  const [gerando,setGerando]=useState<string>('');   // id da fala ou 'lab'

  // ---------- carregar ----------
  async function recarregar(){
    try{
      const [pr,pe,fa,ta]=await Promise.all([listar<Projeto>('projetos'),listar<Personagem>('personagens'),listar<Fala>('falas'),listar<Take>('takes')]);
      let lista=pr.sort((a,b)=>a.criado-b.criado);
      // Fichas prontas que vêm no site: cria o projeto uma vez (se apagar, não volta sozinho).
      let selecionar='';
      for(const m of FICHAS_PRONTAS){
        if(store.get('studio_vozes_pronto_'+m.id)) continue;
        if(!lista.some(p=>p.nome===m.nome)){
          const proj={id:uid(),nome:m.nome,criado:Date.now()}; await salvar('projetos',proj); lista=[...lista,proj];
          const t0=Date.now(); const novos=lerFichas(m.texto).map((f,i)=>({...aplicarFicha(novoPersonagem(proj.id,f.nome),f),criado:t0+i}));
          await salvarVarios('personagens',novos); pe.push(...novos); selecionar=proj.id;
        }
        store.set('studio_vozes_pronto_'+m.id,'1');
      }
      if(!lista.length){ const p={id:uid(),nome:'Meu primeiro projeto',criado:Date.now()}; await salvar('projetos',p); lista=[p]; }
      setProjetos(lista); setPers(pe); setFalas(fa); setTakes(ta.sort((a,b)=>b.data-a.data));
      setPid(x=>selecionar||(lista.some(p=>p.id===x)?x:lista[0].id));
    }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }
    finally{ setCarregado(true); }
  }
  useEffect(()=>{ recarregar(); },[]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(()=>{ if(pid) store.set('studio_vozes_projeto',pid); },[pid]);

  const projeto=projetos.find(p=>p.id===pid);
  const elenco=pers.filter(p=>p.projetoId===pid).sort((a,b)=>a.criado-b.criado);
  const roteiro=falas.filter(f=>f.projetoId===pid).sort((a,b)=>a.ordem-b.ordem);
  const meusTakes=takes.filter(t=>t.projetoId===pid);
  const nomes=Object.fromEntries(elenco.map(p=>[p.id,p.nome]));

  // ---------- projetos ----------
  async function novoProjeto(){ const nome=`Projeto ${projetos.length+1}`; const p={id:uid(),nome,criado:Date.now()}; await salvar('projetos',p); setProjetos(x=>[...x,p]); setPid(p.id); setAba('elenco'); toast('Projeto criado. Dê um nome e cadastre os personagens.','ok'); }
  async function renomear(nome:string){ if(!projeto) return; const p={...projeto,nome}; setProjetos(x=>x.map(y=>y.id===p.id?p:y)); await salvar('projetos',p); }
  async function apagarProjeto(){
    if(!projeto||projetos.length<2){ toast('Crie outro projeto antes de apagar este.','info'); return; }
    if(!confirmar.current){ confirmar.current=true; toast('Toque de novo em Apagar projeto para confirmar. Apaga personagens, roteiro e takes dele.','info'); setTimeout(()=>{ confirmar.current=false; },5000); return; }
    confirmar.current=false;
    for(const x of elenco) await apagar('personagens',x.id); for(const x of roteiro) await apagar('falas',x.id); for(const x of meusTakes) await apagar('takes',x.id);
    await apagar('projetos',projeto.id); await recarregar(); toast('Projeto apagado.','ok');
  }
  const confirmar=useRef(false);

  // ---------- elenco ----------
  async function addPersonagem(nome='NOVO PERSONAGEM'){ const p=novoPersonagem(pid,nome); await salvar('personagens',p); setPers(x=>[...x,p]); return p; }
  function mudarPersonagem(id:string,pt:Partial<Personagem>){
    setPers(x=>x.map(p=>{ if(p.id!==id) return p; const n={...p,...pt}; salvar('personagens',n); return n; }));
  }
  async function importarFichas(fs:FichaLida[]){
    const novos:Personagem[]=[]; let atualizados=0;
    const lista=[...pers];
    for(const f of fs){
      const ja=elenco.find(p=>p.nome.trim().toUpperCase()===f.nome.toUpperCase());
      const n=aplicarFicha(ja||novoPersonagem(pid,f.nome),f);
      await salvar('personagens',n);
      if(ja){ atualizados++; const i=lista.findIndex(x=>x.id===n.id); lista[i]=n; } else { novos.push(n); lista.push(n); }
    }
    setPers(lista);
    toast(`${novos.length} personagens criados${atualizados?` e ${atualizados} atualizados`:''}. Teste no Laboratório: as frases de teste das fichas já estão lá.`,'ok');
  }
  /** Texto livre sem formato conhecido: pede ao Gemini para montar as fichas. */
  async function fichasComIA(txt:string):Promise<FichaLida[]>{
    if(!settings.geminiKey) throw new Error('Não reconheci fichas nesse texto. Use uma tabela (Personagem, Voz-base, Gravidade, Ritmo, Energia, Emoção) ou coloque a chave do Gemini para a IA entender texto livre.');
    const {chamar,GEMINI_MODEL}=await import('../lib/gemini');
    const vozes=VOZES_TTS.map(([v,d])=>`${v} (${d})`).join(', ');
    const pedido=`Leia o texto abaixo e monte fichas de voz para cada personagem que fala. Use só estas vozes-base do Gemini: ${vozes}. Escolha a que combina com o personagem se o texto não disser. gravidade, ritmo, energia e intensidade (da emoção) vão de 0 a 100 (0 = aguda/lenta/contida/leve, 100 = muito grave/muito rápida/explosiva/muito forte). emocao é uma palavra em português. testes são frases de teste citadas no texto (vazio se não houver). Não invente personagens.\n\nTEXTO:\n${txt.slice(0,20000)}`;
    const SCH={type:'OBJECT',properties:{fichas:{type:'ARRAY',items:{type:'OBJECT',properties:{nome:{type:'STRING'},voz:{type:'STRING'},genero:{type:'STRING'},gravidade:{type:'INTEGER'},ritmo:{type:'INTEGER'},energia:{type:'INTEGER'},intensidade:{type:'INTEGER'},emocao:{type:'STRING'},sotaque:{type:'STRING'},descricao:{type:'STRING'},testes:{type:'ARRAY',items:{type:'STRING'}}},required:['nome','voz','gravidade','ritmo','energia','emocao','descricao','testes']}}},required:['fichas']};
    const r=await chamar(settings.geminiKey,GEMINI_MODEL+':generateContent',{contents:[{role:'user',parts:[{text:pedido}]}],generationConfig:{responseMimeType:'application/json',responseSchema:SCH,temperature:0.3}});
    const t=r?.candidates?.[0]?.content?.parts?.map((x:any)=>x.text||'').join('')||'{}';
    const lim=(n:number)=>Math.max(0,Math.min(100,Math.round(n??50)));
    return (JSON.parse(t).fichas||[]).map((f:any)=>({...f,nome:String(f.nome||'').toUpperCase(),voz:vozDoNome(f.voz)||undefined,gravidade:lim(f.gravidade),ritmo:lim(f.ritmo),energia:lim(f.energia),intensidade:lim(f.intensidade),emocao:String(f.emocao||'').toLowerCase(),testes:f.testes||[]})).filter((f:FichaLida)=>f.nome);
  }
  async function apagarPersonagem(p:Personagem){
    if(roteiro.some(f=>f.personagemId===p.id)){ toast('Este personagem tem falas no roteiro. Troque quem fala essas falas antes de apagar.','erro'); return; }
    await apagar('personagens',p.id); setPers(x=>x.filter(y=>y.id!==p.id));
  }

  // ---------- geração ----------
  async function gerarTake(p:Personagem,texto:string,direcao:string,falaId='',vozOutra=''){
    if(!settings.geminiKey) throw new Error('Coloque a chave do Gemini em Chaves e ajustes.');
    const voz=vozOutra||p.voz; const pedido=pedidoTTS(p,texto,direcao);
    const {wav,duracao}=await gerarVoz(settings.geminiKey,p.modelo,voz,pedido,(seg)=>setOcupado(o=>o?{...o,txt:`O Gemini pediu uma pausa (limite de pedidos por minuto do plano grátis). Continuo sozinho em ${seg} s`}:o));
    // Aprova sozinho o primeiro take da fala, ou o primeiro depois de o texto da fala ser editado.
    const jaTem=falaId&&takes.some(t=>t.falaId===falaId&&t.aprovado&&t.texto===texto);
    const t:Take={id:uid(),projetoId:pid,falaId,personagemId:p.id,texto,direcao,pedido,voz,modelo:p.modelo,ajustes:ajustesDe({...p,voz}),data:Date.now(),duracao,wav,aprovado:!!falaId&&!jaTem,nota:''};
    const velhos=t.aprovado?takes.filter(x=>x.falaId===falaId&&x.aprovado).map(x=>({...x,aprovado:false})):[];
    if(velhos.length) await salvarVarios('takes',velhos);
    await salvar('takes',t); setTakes(x=>[t,...x.map(y=>velhos.find(v=>v.id===y.id)||y)]);
    return t;
  }
  async function gerarSomTake(f:Fala,arquivo?:File){
    const fonte=(f.fonteSom||'auto') as FonteSom;
    const {wav,duracao,origem}=await gerarSom(f.texto,fonte,{arquivo});
    const jaTem=takes.some(t=>t.falaId===f.id&&t.aprovado&&t.texto===f.texto);
    const t:Take={id:uid(),projetoId:pid,falaId:f.id,personagemId:'',texto:f.texto,direcao:'',pedido:f.texto,voz:origem,modelo:'som',ajustes:'{}',data:Date.now(),duracao,wav,aprovado:!jaTem,nota:''};
    const velhos=t.aprovado?takes.filter(x=>x.falaId===f.id&&x.aprovado).map(x=>({...x,aprovado:false})):[];
    if(velhos.length) await salvarVarios('takes',velhos);
    await salvar('takes',t); setTakes(x=>[t,...x.map(y=>velhos.find(v=>v.id===y.id)||y)]);
  }
  async function aprovarTake(t:Take){
    const mud=takes.filter(x=>x.falaId===t.falaId&&t.falaId&&x.id!==t.id&&x.aprovado).map(x=>({...x,aprovado:false}));
    const n={...t,aprovado:t.falaId?true:!t.aprovado};
    await salvarVarios('takes',[...mud,n]); setTakes(x=>x.map(y=>y.id===n.id?n:mud.find(m=>m.id===y.id)||y));
  }
  async function notaTake(t:Take,nota:string){ const n={...t,nota}; setTakes(x=>x.map(y=>y.id===n.id?n:y)); await salvar('takes',n); }
  async function apagarTake(t:Take){ await apagar('takes',t.id); setTakes(x=>x.filter(y=>y.id!==t.id)); }

  if(!carregado) return <section className="panel empty-state"><Loader2 className="spin" size={28}/><h2>Abrindo o estúdio...</h2></section>;

  const semChave=!settings.geminiKey&&<div className="note-bar"><KeyRound size={16}/><span>Para gerar vozes, coloque a chave do Gemini (grátis) em Chaves e ajustes. Ela fica só neste navegador.</span><button className="primary sm" onClick={()=>go('config')}>Colocar chave</button></div>;

  return <>
   <section className="panel vozes-topo">
    <div className="row-gap left">
     <label className="grow">Projeto<select value={pid} onChange={e=>setPid(e.target.value)}>{projetos.map(p=><option key={p.id} value={p.id}>{p.nome}</option>)}</select></label>
     <label className="grow">Nome do projeto<input value={projeto?.nome||''} maxLength={80} onChange={e=>renomear(e.target.value)}/></label>
    </div>
    <div className="row-gap left mt"><button className="subtle sm" onClick={novoProjeto}><Plus size={14}/> Novo projeto</button><button className="subtle sm" onClick={apagarProjeto}><Trash2 size={14}/> Apagar projeto</button>
     <span className="hint">{elenco.length} personagem(ns) • {roteiro.filter(f=>f.tipo==='fala').length} fala(s) • {meusTakes.length} take(s) guardados neste navegador</span></div>
    <div className="tabs mt">{([['elenco','Elenco',Users],['lab','Laboratório',FlaskConical],['roteiro','Roteiro',FileText],['final','Arquivo final',FileAudio]] as [Aba,string,typeof Users][]).map(([k,n,I])=><button key={k} className={aba===k?'on':''} onClick={()=>setAba(k)}><I size={15}/> {n}</button>)}</div>
   </section>
   {semChave}
   {ocupado&&<div className="dl-box"><div className="row"><Loader2 size={16} className="spin"/><span><b>{ocupado.txt}</b> {ocupado.pct}%</span><button className="subtle sm" onClick={()=>{ parar.current=true; }}>Parar</button></div><div className="dl-bar"><i style={{width:Math.max(3,ocupado.pct)+'%'}}/></div></div>}
   {aba==='elenco'&&<Elenco elenco={elenco} aleatoria={async(g:Genero)=>{ const n=elenco.length+1; const p=await addPersonagem(g==='feminina'?`PERSONAGEM ${n} (F)`:g==='masculina'?`PERSONAGEM ${n} (M)`:`PERSONAGEM ${n}`); mudarPersonagem(p.id,{...vozAleatoria(g),genero:g==='feminina'?'mulher':g==='masculina'?'homem':''}); toast('Voz sorteada. Dê um nome e teste no Laboratório; não gostou, toque em Sortear outra.','ok'); }} importar={importarFichas} comIA={fichasComIA} add={addPersonagem} mudar={mudarPersonagem} apagar={apagarPersonagem} testar={id=>{ setLabPid(id); setAba('lab'); }}/>}
   {aba==='lab'&&<Lab pid={labPid} setPid={setLabPid} elenco={elenco} takes={meusTakes.filter(t=>!t.falaId)} gerando={gerando==='lab'} gerar={async(p,txt,dir,vozB)=>{
      setGerando('lab');
      try{ await gerarTake(p,txt,dir); if(vozB&&vozB!==p.voz) await gerarTake(p,txt,dir,'',vozB); toast(vozB?'Dois takes prontos para comparar.':'Take pronto. Ouça abaixo.','ok'); }
      catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); } finally{ setGerando(''); }
    }} aprovar={aprovarTake} nota={notaTake} apagarTake={apagarTake} usarAjustes={(t)=>{ try{ const a=JSON.parse(t.ajustes); if(!('intensidade' in a)) for(const k of ['gravidade','ritmo','energia']) if(typeof a[k]==='number'&&a[k]<=5) a[k]=Math.round((Math.max(1,a[k])-1)*25); mudarPersonagem(t.personagemId,a); toast('Ajustes deste take copiados para a ficha do personagem.','ok'); }catch{ /* ajustes antigos */ } }} add={()=>{ setAba('elenco'); addPersonagem(); }}/>}
   {aba==='roteiro'&&<Roteiro pid={pid} elenco={elenco} roteiro={roteiro} takes={meusTakes} gerando={gerando} ocupado={!!ocupado}
     aplicar={async(linhas,mapa)=>{
       const criados:Record<string,string>={};
       for(const [nome,dest] of Object.entries(mapa)) criados[nome]=dest==='__novo'?(await addPersonagem(nome)).id:dest;
       for(const f of roteiro) await apagar('falas',f.id);
       const novas:Fala[]=linhas.map((l,i)=>({id:uid(),projetoId:pid,ordem:i,cena:l.cena,nomeRoteiro:l.nome,personagemId:l.tipo==='fala'?criados[l.nome]||'':'',texto:l.texto,direcao:l.direcao,pausa:l.tipo==='fala'?0.4:0,tipo:l.tipo,...(l.tipo==='som'?{volume:AMBIENTE.test(l.texto)?40:70,sobrepor:AMBIENTE.test(l.texto),fonteSom:'auto' as const}:{})}));
       await salvarVarios('falas',novas); setFalas(x=>[...x.filter(f=>f.projetoId!==pid),...novas]);
       toast(`Roteiro aplicado: ${novas.filter(f=>f.tipo==='fala').length} falas${novas.some(f=>f.tipo==='som')?` e ${novas.filter(f=>f.tipo==='som').length} efeitos sonoros`:''}. Agora gere as vozes${novas.some(f=>f.tipo==='som')?' e os sons':''}.`,'ok');
     }}
     mudarFala={async(f)=>{ setFalas(x=>x.map(y=>y.id===f.id?f:y)); await salvar('falas',f); }}
     gerar={async(f)=>{ const p=elenco.find(x=>x.id===f.personagemId); if(!p){ toast('Escolha quem fala esta fala.','erro'); return; } setGerando(f.id); try{ await gerarTake(p,f.texto,f.direcao,f.id); }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); } finally{ setGerando(''); } }}
     lote={async(lista)=>{
       if(!settings.geminiKey){ toast('Coloque a chave do Gemini em Chaves e ajustes.','erro'); return; }
       parar.current=false; let ok=0; const erros:string[]=[];
       for(let i=0;i<lista.length;i++){
         if(parar.current) break;
         const f=lista[i]; const p=elenco.find(x=>x.id===f.personagemId); if(!p){ erros.push(`Fala ${f.ordem+1}: sem personagem`); continue; }
         setOcupado({txt:`Gerando fala ${i+1} de ${lista.length} (${p.nome})`,pct:Math.round(i/lista.length*100)}); setGerando(f.id);
         try{ await gerarTake(p,f.texto,f.direcao,f.id); ok++; }catch(e){ erros.push(`Fala ${f.ordem+1}: ${e instanceof Error?e.message:String(e)}`); if(/chave|inválida|limite|cota/i.test(String(e))) break; }
       }
       setOcupado(null); setGerando('');
       toast(`${ok} fala(s) geradas.${erros.length?` ${erros.length} com problema: ${erros.slice(0,2).join(' | ')}`:''}${parar.current?' Parado por você.':''}`,erros.length?'info':'ok');
     }}
     gerarSom={async(f,arq)=>{ setGerando(f.id); try{ await gerarSomTake(f,arq); }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); } finally{ setGerando(''); } }}
     loteSons={async(lista)=>{ parar.current=false; let ok=0; const erros:string[]=[];
       for(let i=0;i<lista.length;i++){ if(parar.current) break; const f=lista[i]; if(f.fonteSom==='arquivo') continue; setOcupado({txt:`Gerando som ${i+1} de ${lista.length}: ${f.texto}`,pct:Math.round(i/lista.length*100)}); setGerando(f.id);
         try{ await gerarSomTake(f); ok++; }catch(e){ erros.push(`${f.texto}: ${e instanceof Error?e.message:String(e)}`); } }
       setOcupado(null); setGerando(''); toast(`${ok} som(ns) gerados.${erros.length?` ${erros.length} com problema: ${erros.slice(0,2).join(' | ')}`:''}`,erros.length?'info':'ok'); }}
     aprovar={aprovarTake} apagarTake={apagarTake}/>}
   {aba==='final'&&<Final projeto={projeto?.nome||'projeto'} elenco={elenco} roteiro={roteiro} takes={meusTakes} nomes={nomes} irRoteiro={()=>setAba('roteiro')}/>}
  </>;
}

// ================= Elenco =================
function Elenco({elenco,add,mudar,apagar,testar,importar,comIA,aleatoria}:{aleatoria:(g:Genero)=>Promise<void>;elenco:Personagem[];add:()=>void;mudar:(id:string,p:Partial<Personagem>)=>void;apagar:(p:Personagem)=>void;testar:(id:string)=>void;importar:(f:FichaLida[])=>Promise<void>;comIA:(t:string)=>Promise<FichaLida[]>}){
  const {toast}=useApp();
  const [abrir,setAbrir]=useState(false); const [txt,setTxt]=useState(''); const [lidas,setLidas]=useState<FichaLida[]|null>(null); const [lendo,setLendo]=useState(false);
  async function ler(){
    setLendo(true);
    try{ let f=lerFichas(txt); if(!f.length) f=await comIA(txt); if(!f.length) throw new Error('Não achei personagens nesse texto.'); setLidas(f); }
    catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }
    finally{ setLendo(false); }
  }
  const [gen,setGen]=useState<Genero>('masculina');
  const existe=(n:string)=>elenco.some(p=>p.nome.trim().toUpperCase()===n.toUpperCase());
  return <section className="panel">
   <div className="section-head"><h2><Users size={18}/> Elenco</h2><span className="row-gap"><span className="aleatoria"><select value={gen} onChange={e=>setGen(e.target.value as Genero)} aria-label="Gênero da voz aleatória"><option value="masculina">Masculina</option><option value="feminina">Feminina</option><option value="qualquer">Qualquer</option></select><button className="subtle sm" onClick={()=>aleatoria(gen)}><Dices size={14}/> Voz aleatória</button></span><button className="subtle sm" onClick={()=>setAbrir(!abrir)}><Wand2 size={14}/> Colar fichas</button><button className="primary sm" onClick={()=>add()}><Plus size={14}/> Novo personagem</button></span></div>
   {(abrir||!elenco.length)&&<div className="colar-fichas">
    <details className="guia-ficha"><summary>Como escrever uma ficha (o que é necessário)</summary>
     <ul>
      <li><b>Nome</b> (obrigatório): igual ao do roteiro, assim cada fala acha a voz certa. Ex.: <code>NARRADOR</code>, <code>THORGAR</code>.</li>
      <li><b>Voz-base</b>: uma das 30 vozes do Gemini (Charon, Algenib, Puck, Leda...). Se faltar, usa Charon.</li>
      <li><b>Gravidade, Ritmo e Energia</b> em %: 0% = aguda / lenta / contida; 100% = muito grave / muito rápida / explosiva.</li>
      <li><b>Emoção de base</b> (ex.: neutra, cansada, autoritária) e, se quiser, a <b>Intensidade</b> em %.</li>
      <li><b>Perfil —</b> quem é o personagem (gênero, idade, jeito).</li>
      <li><b>Descrição e direção permanente</b>: como a voz soa e como interpretar em todas as falas.</li>
      <li><b>Teste — “frase”</b>: frases curtas que viram botões no Laboratório.</li>
      <li>Escreva <b>Pro</b> e <b>brasileiro neutro</b> no começo do texto para usar o modelo mais expressivo e esse sotaque em todos.</li>
     </ul>
     <p className="hint">A tabela pode ter as colunas separadas por tabulação (copiada de planilha ou do Docs) ou por <code>|</code>. Só a linha de cada personagem é obrigatória; os blocos de perfil, direção e teste são opcionais.</p>
     <div className="row-gap left"><button className="subtle sm" onClick={()=>{ setTxt(GUIA_FICHA); setLidas(null); }}>Usar o modelo em branco</button><button className="subtle sm" onClick={()=>navigator.clipboard?.writeText(GUIA_FICHA).then(()=>toast('Modelo copiado.','ok'),()=>{})}>Copiar o modelo</button></div>
    </details>
    <label className="mt">Fichas prontas<span className="row-gap left">{FICHAS_PRONTAS.map(m=><button key={m.id} className="subtle sm" onClick={()=>{ setTxt(m.texto); setLidas(null); }}>{m.nome}</button>)}</span></label>
    <p className="hint">Cole o texto com as fichas (pode ser a tabela <b>Personagem / Voz-base / Gravidade / Ritmo / Energia / Emoção</b> e os blocos com <b>Perfil —</b>, <b>Descrição e direção permanente</b> e <b>Teste — “frase”</b>). O site cria ou atualiza cada personagem e já deixa as frases de teste no Laboratório. Se o texto for livre, a IA (Gemini) monta as fichas.</p>
    <textarea rows={6} value={txt} onChange={e=>{ setTxt(e.target.value); setLidas(null); }} placeholder={'Personagem\tVoz-base\tGravidade\tRitmo\tEnergia\tEmoção\nNarrador\tCharon\t72%\t42%\t45%\tNeutra\n\nNarrador\nPerfil — Homem maduro, contador de histórias...\nDescrição e direção permanente\nVoz encorpada, dicção clara...\nTeste — “Era uma noite tranquila na taverna.”'} aria-label="Texto das fichas"/>
    <button className="primary mt" disabled={!txt.trim()||lendo} onClick={ler}>{lendo?<Loader2 size={15} className="spin"/>:<Wand2 size={15}/>} Ler fichas</button>
    {lidas&&<div className="fichas-lidas mt">
     <h3>{lidas.length} personagens encontrados</h3>
     <ul>{lidas.map(f=><li key={f.nome}><b>{f.nome}</b> <span className={'tag '+(existe(f.nome)?'warn':'ok')}>{existe(f.nome)?'atualiza':'novo'}</span> <small>{[f.voz&&`voz ${f.voz}`,f.modelo?.includes('pro')&&'Pro',f.gravidade!==undefined&&`gravidade ${f.gravidade}%`,f.ritmo!==undefined&&`ritmo ${f.ritmo}%`,f.energia!==undefined&&`energia ${f.energia}%`,f.intensidade!==undefined&&`intensidade ${f.intensidade}%`,f.emocao,f.testes.length&&`${f.testes.length} frase(s) de teste`].filter(Boolean).join(' • ')}</small></li>)}</ul>
     <button className="primary" onClick={async()=>{ await importar(lidas); setLidas(null); setTxt(''); setAbrir(false); }}><CheckCircle2 size={15}/> Criar e configurar {lidas.length} personagens</button>
    </div>}
   </div>}
   <p className="hint">Cada personagem tem uma ficha de voz. Os ajustes viram uma descrição que vai junto para o Gemini em toda fala dele, então a voz fica parecida entre as falas. Teste no Laboratório e marque <b>Voz aprovada</b> quando gostar.</p>
   {!elenco.length&&<div className="empty"><Users size={30}/><strong>Nenhum personagem ainda</strong><p>Crie aqui ou cole o roteiro na aba Roteiro: os personagens são criados a partir dele.</p></div>}
   <div className="fichas">{elenco.map(p=><article key={p.id} className={'ficha '+(p.aprovada?'ok':'')}>
    <div className="ficha-top"><input className="ficha-nome" value={p.nome} maxLength={40} onChange={e=>mudar(p.id,{nome:e.target.value})} aria-label="Nome do personagem"/>
     <label className="check"><input type="checkbox" checked={p.aprovada} onChange={e=>mudar(p.id,{aprovada:e.target.checked})}/> Voz aprovada</label></div>
    <div className="small-grid">
     <label>Voz-base do Gemini<select value={p.voz} onChange={e=>mudar(p.id,{voz:e.target.value})}>{VOZES_TTS.map(([v,d])=><option key={v} value={v}>{v} ({d})</option>)}</select></label>
     <label>Modelo<select value={p.modelo} onChange={e=>mudar(p.id,{modelo:e.target.value})}>{MODELOS_TTS.map(([v,d])=><option key={v} value={v}>{d}</option>)}</select></label>
    </div>
    <label className="mt">Perfil (gênero, idade, jeito)<input value={p.genero} placeholder="Ex.: homem maduro, narrador de RPG experiente" onChange={e=>mudar(p.id,{genero:e.target.value})}/></label>
    {(['gravidade','ritmo','energia'] as const).map(k=><label key={k} className="mt slider"><span className="label-row">{k==='gravidade'?'Gravidade (aguda ↔ grave)':k==='ritmo'?'Ritmo (lento ↔ rápido)':'Energia (contida ↔ explosiva)'}: <b>{p[k]}%</b> <small>({rotulo(k,p[k])})</small></span>
     <span className="pct-row"><input type="range" min={0} max={100} step={1} value={p[k]} onChange={e=>mudar(p.id,{[k]:+e.target.value} as Partial<Personagem>)}/><input type="number" min={0} max={100} value={p[k]} onChange={e=>mudar(p.id,{[k]:Math.max(0,Math.min(100,+e.target.value||0))} as Partial<Personagem>)} aria-label={k+' em %'}/></span></label>)}
    <div className="small-grid mt">
     <label>Emoção de base<select value={p.emocao} onChange={e=>mudar(p.id,{emocao:e.target.value})}>{(EMOCOES.includes(p.emocao)?EMOCOES:[p.emocao,...EMOCOES]).map(x=><option key={x} value={x}>{x}</option>)}</select></label>
     <label>Sotaque<input value={p.sotaque} onChange={e=>mudar(p.id,{sotaque:e.target.value})}/></label>
    </div>
    <label className="mt slider"><span className="label-row">Intensidade da emoção ({p.emocao}): <b>{p.intensidade??50}%</b> <small>({rotuloIntensidade(p.intensidade??50)})</small></span>
     <span className="pct-row"><input type="range" min={0} max={100} step={1} value={p.intensidade??50} onChange={e=>mudar(p.id,{intensidade:+e.target.value})}/><input type="number" min={0} max={100} value={p.intensidade??50} onChange={e=>mudar(p.id,{intensidade:Math.max(0,Math.min(100,+e.target.value||0))})} aria-label="intensidade em %"/></span></label>
    <label className="mt">Descrição e direção permanente<textarea rows={3} value={p.descricao} placeholder="Ex.: voz encorpada e cinematográfica, ironia seca e discreta; sem tom publicitário." onChange={e=>mudar(p.id,{descricao:e.target.value})}/></label>
    <details className="mt"><summary>Ver o que vai para o Gemini</summary><p className="hint">{descreverVoz(p)}</p></details>
    <div className="row-gap left mt"><button className="subtle sm" onClick={()=>testar(p.id)}><FlaskConical size={14}/> Testar no Laboratório</button><button className="subtle sm" onClick={()=>mudar(p.id,vozAleatoria(generoDaVoz(p.voz),p.voz))} title="Sorteia outra voz do mesmo gênero e novos ajustes"><Dices size={14}/> Sortear outra</button><button className="subtle sm" onClick={()=>apagar(p)}><Trash2 size={14}/> Apagar</button></div>
   </article>)}</div>
  </section>;
}

// ================= Laboratório =================
const FRASE_TESTE='Olá! Esta é a minha voz. Escute com atenção... porque o que vem agora vai mudar tudo.';
function Lab({pid,setPid,elenco,takes,gerando,gerar,aprovar,nota,apagarTake,usarAjustes,add}:{pid:string;setPid:(id:string)=>void;elenco:Personagem[];takes:Take[];gerando:boolean;gerar:(p:Personagem,txt:string,dir:string,vozB:string)=>void;aprovar:(t:Take)=>void;nota:(t:Take,n:string)=>void;apagarTake:(t:Take)=>void;usarAjustes:(t:Take)=>void;add:()=>void}){
  const p=elenco.find(x=>x.id===pid)||elenco[0];
  const [txt,setTxt]=useState(FRASE_TESTE);
  useEffect(()=>{ if(p?.testes?.length) setTxt(p.testes[0]); },[p?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const [dir,setDir]=useState(''); const [vozB,setVozB]=useState('');
  const [so,setSo]=useState(false);
  if(!p) return <section className="panel empty-state"><FlaskConical size={30}/><h2>Crie um personagem para testar a voz</h2><button className="primary" onClick={add}><Plus size={15}/> Novo personagem</button></section>;
  const lista=takes.filter(t=>t.personagemId===p.id&&(!so||t.aprovado));
  return <section className="panel">
   <div className="section-head"><h2><FlaskConical size={18}/> Laboratório de voz</h2></div>
   <p className="hint">Escreva uma frase, ajuste a direção e gere. Cada geração vira um take guardado com os ajustes usados, para você comparar lado a lado e voltar ao que gostou. Mudanças na ficha (aba Elenco) valem para os próximos takes.</p>
   <div className="small-grid">
    <label>Personagem<select value={p.id} onChange={e=>setPid(e.target.value)}>{elenco.map(x=><option key={x.id} value={x.id}>{x.nome}</option>)}</select></label>
    <label>Comparar com outra voz-base (opcional)<select value={vozB} onChange={e=>setVozB(e.target.value)}><option value="">Não, só a voz da ficha ({p.voz})</option>{VOZES_TTS.filter(v=>v[0]!==p.voz).map(([v,d])=><option key={v} value={v}>{v} ({d})</option>)}</select></label>
   </div>
   {!!p.testes?.length&&<div className="chips mt">{p.testes.map(t=><button key={t} className={'chip'+(txt===t?' on':'')} onClick={()=>setTxt(t)} title="Usar esta frase de teste da ficha">“{t.length>50?t.slice(0,48)+'…':t}”</button>)}</div>}
   <label className="mt">Frase de teste<textarea rows={3} value={txt} onChange={e=>setTxt(e.target.value)}/></label>
   <label className="mt">Direção só deste teste (não é falada)<input value={dir} placeholder="Ex.: mais grave, pausa dramática antes de 'porque', tom de suspense" onChange={e=>setDir(e.target.value)}/></label>
   <p className="hint">Ficha atual: {descreverVoz(p)}</p>
   <button className="primary mt" disabled={gerando||!txt.trim()} onClick={()=>gerar(p,txt.trim(),dir,vozB)}>{gerando?<Loader2 size={15} className="spin"/>:<Mic size={15}/>} {vozB?`Gerar e comparar ${p.voz} × ${vozB}`:'Gerar take'}</button>
   <div className="section-head mt"><h3>Takes de {p.nome} ({lista.length})</h3><label className="check"><input type="checkbox" checked={so} onChange={e=>setSo(e.target.checked)}/> Só favoritos</label></div>
   {!lista.length&&<p className="hint">Nenhum take ainda.</p>}
   <div className="takes-grid">{lista.map((t,i)=><article key={t.id} className={'take '+(t.aprovado?'ok':'')}>
    <div className="take-top"><b>{String.fromCharCode(65+(i%26))}</b><span>{t.voz} • {fmt(t.duracao)} • {new Date(t.data).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}</span></div>
    <small className="take-txt">“{t.texto}”{t.direcao&&<em> — {t.direcao}</em>}</small>
    <Audio blob={t.wav}/>
    <input className="take-nota" value={t.nota} placeholder="Anotação (ex.: grave demais)" onChange={e=>nota(t,e.target.value)}/>
    <div className="row-gap left"><button className={t.aprovado?'primary sm':'subtle sm'} onClick={()=>aprovar(t)}><Star size={13}/> {t.aprovado?'Favorito':'Favoritar'}</button>
     <button className="subtle sm" onClick={()=>usarAjustes(t)} title="Copia voz e ajustes deste take para a ficha"><RotateCcw size={13}/> Usar estes ajustes</button>
     <button className="icon-btn" onClick={()=>baixar(t.wav,nomeTake(null,t,p.nome))} aria-label="Baixar WAV"><Download size={14}/></button>
     <button className="icon-btn" onClick={()=>apagarTake(t)} aria-label="Apagar take"><Trash2 size={14}/></button></div>
   </article>)}</div>
  </section>;
}

// ================= Roteiro =================
function Roteiro({pid,elenco,roteiro,takes,gerando,ocupado,aplicar,mudarFala,gerar,lote,aprovar,apagarTake,gerarSom:gerarSomF,loteSons}:{gerarSom:(f:Fala,arq?:File)=>void;loteSons:(l:Fala[])=>void;pid:string;elenco:Personagem[];roteiro:Fala[];takes:Take[];gerando:string;ocupado:boolean;
  aplicar:(l:LinhaRoteiro[],mapa:Record<string,string>)=>Promise<void>;mudarFala:(f:Fala)=>void;gerar:(f:Fala)=>void;lote:(l:Fala[])=>void;aprovar:(t:Take)=>void;apagarTake:(t:Take)=>void}){
  const [texto,setTexto]=useState(''); const [prev,setPrev]=useState<LinhaRoteiro[]|null>(null); const [mapa,setMapa]=useState<Record<string,string>>({});
  const [filtro,setFiltro]=useState(''); const [aberta,setAberta]=useState('');
  const arq=useRef<HTMLInputElement>(null);
  useEffect(()=>{ setPrev(null); setTexto(''); },[pid]);
  function ler(t=texto){
    const l=lerRoteiro(t); if(!l.some(x=>x.tipo==='fala')){ toastMsg('Não achei falas. Use uma linha por fala no formato NOME: texto.'); return; }
    setPrev(l);
    const m:Record<string,string>={}; for(const n of new Set(l.filter(x=>x.tipo==='fala').map(x=>x.nome))) m[n]=elenco.find(p=>p.nome.toUpperCase()===n)?.id||'__novo';
    setMapa(m);
  }
  const [aviso,toastMsg]=useState('');
  const falasR=roteiro.filter(f=>f.tipo==='fala');
  const aprovadoDe=(f:Fala)=>takes.find(t=>t.falaId===f.id&&t.aprovado);
  const visiveis=roteiro.filter(f=>!filtro||f.personagemId===filtro||(f.tipo==='acao'&&!filtro));
  const semTake=falasR.filter(f=>(!filtro||f.personagemId===filtro)&&!takes.some(t=>t.falaId===f.id&&t.texto===f.texto));
  const sonsR=roteiro.filter(f=>f.tipo==='som'); const sonsSem=sonsR.filter(f=>!takes.some(t=>t.falaId===f.id&&t.texto===f.texto)&&f.fonteSom!=='arquivo');
  let cenaAnt='';
  return <>
   <section className="panel">
    <div className="section-head"><h2><FileText size={18}/> {roteiro.length?'Trocar o roteiro':'Colocar o roteiro'}</h2><button className="subtle sm" onClick={()=>arq.current?.click()}><Upload size={14}/> Abrir arquivo .md ou .txt</button></div>
    <input ref={arq} type="file" accept=".md,.txt,text/plain,text/markdown" hidden onChange={async e=>{ const f=e.target.files?.[0]; if(!f) return; const t=await f.text(); setTexto(t); ler(t); e.target.value=''; }}/>
    <p className="hint">Uma fala por linha: <code>NOME: texto</code> (também serve <code>**NOME:** “texto”</code> e <code>NOME (sussurrando): texto</code>). Títulos como <code>## Cena 1</code> separam as cenas. Linhas sem nome viram ações e não são faladas. Efeitos sonoros: uma linha <code>[SOM: porta batendo]</code> (ou <code>[SFX: ...]</code>) no ponto onde o som deve tocar; escreva <i>forte</i> ou <i>fraco</i> para mudar a força. O texto das falas é usado exatamente como está.</p>
    <textarea rows={6} value={texto} onChange={e=>setTexto(e.target.value)} placeholder={'## Cena 1 — A taverna\n[SOM: murmúrio de taverna]\nNARRADOR: Era uma noite tranquila...\n[SOM: porta batendo, forte]\nHERÓI (gritando): Quem derrubou minha cerveja?!'} aria-label="Texto do roteiro"/>
    {aviso&&<p className="hint erro">{aviso}</p>}
    <button className="primary mt" disabled={!texto.trim()} onClick={()=>{ toastMsg(''); ler(); }}><Wand2 size={15}/> Ler roteiro</button>
    {prev&&<div className="prev-roteiro mt">
     <h3>Prévia: {prev.filter(x=>x.tipo==='fala').length} falas, {prev.filter(x=>x.tipo==='acao').length} ações{prev.some(x=>x.tipo==='som')?`, ${prev.filter(x=>x.tipo==='som').length} sons`:''}</h3>
     <p className="hint">Confira quem fala. Nome igual a um personagem do elenco usa a voz dele. Nome igual a uma voz do Gemini (ex.: CHARON) cria o personagem com essa voz. Os outros viram personagens novos.</p>
     <div className="mapa">{Object.keys(mapa).map(n=><label key={n}><b>{n}</b> ({prev.filter(x=>x.nome===n).length} falas)<select value={mapa[n]} onChange={e=>setMapa(m=>({...m,[n]:e.target.value}))}><option value="__novo">Criar personagem novo “{n}”{vozDoNome(n)?` com a voz ${vozDoNome(n)}`:''}</option>{elenco.map(p=><option key={p.id} value={p.id}>{p.nome}</option>)}</select></label>)}</div>
     <div className="prev-lista">{prev.map((l,i)=><div key={i} className={'prev-linha '+l.tipo}><small>{l.cena}</small>{l.tipo==='fala'?<span><b>{l.nome}{l.direcao&&` (${l.direcao})`}:</b> {l.texto}</span>:l.tipo==='som'?<span className="som-prev">🔊 {l.texto}</span>:<span className="acao">{l.texto}</span>}
      <button className="link-btn" onClick={()=>setPrev(p=>p!.map((x,j)=>j!==i?x:x.tipo==='fala'?{...x,tipo:'acao'}:{...x,tipo:'fala',nome:x.nome||'NARRADOR'}))}>{l.tipo==='fala'?'é ação':'é fala'}</button></div>)}</div>
     <div className="row-gap left mt"><button className="primary" onClick={async()=>{ await aplicar(prev,mapa); setPrev(null); setTexto(''); }}><CheckCircle2 size={15}/> {roteiro.length?'Substituir o roteiro atual':'Usar este roteiro'}</button><button className="subtle" onClick={()=>setPrev(null)}>Cancelar</button></div>
     {roteiro.length>0&&<p className="hint">Os takes já gerados continuam guardados, mas ficam fora do roteiro novo.</p>}
    </div>}
   </section>

   {roteiro.length>0&&<section className="panel">
    <div className="section-head"><h2><Mic size={18}/> Falas ({falasR.length})</h2><span>{falasR.filter(aprovadoDe).length} com take aprovado</span></div>
    <div className="row-gap left">
     <label>Mostrar<select value={filtro} onChange={e=>setFiltro(e.target.value)}><option value="">Todos os personagens</option>{elenco.map(p=><option key={p.id} value={p.id}>{p.nome}</option>)}</select></label>
     <button className="primary" disabled={!semTake.length||ocupado} onClick={()=>lote(semTake)}><Mic size={15}/> Gerar as {semTake.length} falas sem voz</button>
     {sonsR.length>0&&<button className="subtle" disabled={!sonsSem.length||ocupado} onClick={()=>loteSons(sonsSem)}><Volume2 size={15}/> Gerar os {sonsSem.length} sons</button>}
    </div>
    <p className="hint">Gere uma por uma ou em lote. Cada fala pode ter vários takes; o aprovado (estrela) é o que entra no arquivo final. A direção muda só a interpretação, nunca o texto.</p>
    <div className="falas">{visiveis.map(f=>{ const cab=f.cena!==cenaAnt; cenaAnt=f.cena; const ts=takes.filter(t=>t.falaId===f.id); const ap=aprovadoDe(f);
     return <div key={f.id}>{cab&&<h3 className="cena-tit">{f.cena}</h3>}
      {f.tipo==='acao'?<p className="acao">{f.texto}</p>:f.tipo==='som'?<div className={'fala som '+(aprovadoDe(f)?'ok':'')+(gerando===f.id?' on':'')}>
       <div className="fala-top"><span className="fala-n">{f.ordem+1}</span><Volume2 size={16}/>
        <input className="grow" value={f.texto} onChange={e=>mudarFala({...f,texto:e.target.value})} aria-label="Descrição do som"/></div>
       <div className="fala-ctl">
        <select value={f.fonteSom==='arquivo'?'arquivo':'site'} onChange={e=>mudarFala({...f,fonteSom:e.target.value as FonteSom})} aria-label="Fonte do som"><option value="site">Feito pelo site (grátis){receitaDe(f.texto)?`: ${receitaDe(f.texto)!.nome}`:': impacto genérico'}</option><option value="arquivo">Meu arquivo</option></select>
        <label className="pausa">Volume<input type="number" min={0} max={200} step={5} value={f.volume??70} onChange={e=>mudarFala({...f,volume:Math.max(0,Math.min(200,+e.target.value||0))})} aria-label="Volume do som"/>%</label>
        <label className="pausa"><input type="checkbox" checked={!!f.sobrepor} onChange={e=>mudarFala({...f,sobrepor:e.target.checked})}/> toca junto com a próxima fala</label>
        {f.fonteSom==='arquivo'?<label className="subtle sm vc-upload"><Upload size={13}/> Enviar som<input type="file" accept="audio/*" hidden onChange={e=>{ const a=e.target.files?.[0]; if(a) gerarSomF(f,a); e.target.value=''; }}/></label>
         :<button className="subtle sm" disabled={!!gerando||ocupado} onClick={()=>gerarSomF(f)}>{gerando===f.id?<Loader2 size={13} className="spin"/>:<Volume2 size={13}/>} {takes.some(t=>t.falaId===f.id)?'Novo take':'Gerar som'}</button>}
        {takes.some(t=>t.falaId===f.id)&&<button className="link-btn" onClick={()=>setAberta(a=>a===f.id?'':f.id)}>{aberta===f.id?'Fechar':'Ver'} {takes.filter(t=>t.falaId===f.id).length} take(s)</button>}
       </div>
       {aprovadoDe(f)&&aberta!==f.id&&<><small className="hint">{aprovadoDe(f)!.voz}</small><Audio blob={aprovadoDe(f)!.wav}/></>}
       {aberta===f.id&&<div className="takes-grid">{takes.filter(t=>t.falaId===f.id).map((t,i)=><article key={t.id} className={'take '+(t.aprovado?'ok':'')}>
         <div className="take-top"><b>{String.fromCharCode(65+(i%26))}</b><span>{t.voz} • {fmt(t.duracao)}</span></div>
         <Audio blob={t.wav}/>
         <div className="row-gap left"><button className={t.aprovado?'primary sm':'subtle sm'} onClick={()=>aprovar(t)}><Star size={13}/> {t.aprovado?'Aprovado':'Aprovar'}</button>
          <button className="icon-btn" onClick={()=>apagarTake(t)} aria-label="Apagar take"><Trash2 size={14}/></button></div>
       </article>)}</div>}
      </div>:<div className={'fala '+(ap?'ok':'')+(gerando===f.id?' on':'')}>
       <div className="fala-top"><span className="fala-n">{f.ordem+1}</span>
        <select value={f.personagemId} onChange={e=>mudarFala({...f,personagemId:e.target.value})} aria-label="Quem fala"><option value="">Quem fala?</option>{elenco.map(p=><option key={p.id} value={p.id}>{p.nome}</option>)}</select>
        <textarea className="grow fala-txt" rows={Math.min(5,Math.max(1,Math.ceil(f.texto.length/70)))} value={f.texto} onChange={e=>mudarFala({...f,texto:e.target.value})} aria-label="Texto da fala"/></div>
       {ap&&ap.texto!==f.texto&&<p className="hint erro">O texto mudou depois desta voz. Toque em Novo take para gravar o texto novo (o take antigo continua no arquivo final até você aprovar outro).</p>}
       <div className="fala-ctl">
        <input value={f.direcao} placeholder="Direção (ex.: sussurrando, com raiva)" onChange={e=>mudarFala({...f,direcao:e.target.value})} aria-label="Direção da fala"/>
        <label className="pausa">Pausa depois<input type="number" min={0} max={10} step={0.1} value={f.pausa} onChange={e=>mudarFala({...f,pausa:Math.max(0,+e.target.value)})}/>s</label>
        <button className="subtle sm" disabled={!!gerando||ocupado} onClick={()=>gerar(f)}>{gerando===f.id?<Loader2 size={13} className="spin"/>:<Mic size={13}/>} {ts.length?'Novo take':'Gerar voz'}</button>
        {ts.length>0&&<button className="link-btn" onClick={()=>setAberta(a=>a===f.id?'':f.id)}>{aberta===f.id?'Fechar':'Ver'} {ts.length} take(s)</button>}
       </div>
       {ap&&aberta!==f.id&&<Audio blob={ap.wav}/>}
       {aberta===f.id&&<div className="takes-grid">{ts.map((t,i)=><article key={t.id} className={'take '+(t.aprovado?'ok':'')}>
         <div className="take-top"><b>{String.fromCharCode(65+(i%26))}</b><span>{t.voz} • {fmt(t.duracao)}{t.direcao&&` • ${t.direcao}`}</span></div>
         <Audio blob={t.wav}/>
         <div className="row-gap left"><button className={t.aprovado?'primary sm':'subtle sm'} onClick={()=>aprovar(t)}><Star size={13}/> {t.aprovado?'Aprovado':'Aprovar'}</button>
          <button className="icon-btn" onClick={()=>baixar(t.wav,nomeTake(f,t,elenco.find(p=>p.id===f.personagemId)?.nome))} aria-label="Baixar WAV"><Download size={14}/></button>
          <button className="icon-btn" onClick={()=>apagarTake(t)} aria-label="Apagar take"><Trash2 size={14}/></button></div>
       </article>)}</div>}
      </div>}
     </div>; })}</div>
   </section>}
  </>;
}

// ================= Arquivo final =================
/** Lê "10", "9:30" ou "9,5" como segundos. */
function lerTempo(t:string){ const v=t.trim().replace(',','.'); if(!v) return 0; const m=v.match(/^(\d+):(\d{1,2})$/); if(m) return +m[1]*60+ +m[2]; const n=parseFloat(v); return Number.isFinite(n)&&n>0?n*60:0; }
function Final({projeto,elenco,roteiro,takes,nomes,irRoteiro}:{projeto:string;elenco:Personagem[];roteiro:Fala[];takes:Take[];nomes:Record<string,string>;irRoteiro:()=>void}){
  const {toast}=useApp();
  const [pausaIni,setPausaIni]=useState(0.3); const [comNome,setComNome]=useState(true);
  const [res,setRes]=useState<Awaited<ReturnType<typeof montarEpisodio>>|null>(null); const [montando,setMontando]=useState(false);
  const falasR=roteiro.filter(f=>f.tipo==='fala');
  const semAprov=falasR.filter(f=>!takes.some(t=>t.falaId===f.id&&t.aprovado));
  const semQuem=falasR.filter(f=>!f.personagemId);
  const usados=new Set(falasR.map(f=>f.personagemId).filter(Boolean));
  const vozNaoAprov=elenco.filter(p=>usados.has(p.id)&&!p.aprovada);
  const slug=projeto.normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^a-zA-Z0-9]+/g,'-').replace(/^-|-$/g,'').toLowerCase()||'projeto';
  const assinatura=roteiro.map(f=>f.id+f.pausa+f.personagemId).join()+'|'+takes.filter(t=>t.aprovado).map(t=>t.id).join();
  useEffect(()=>{ setRes(null); },[assinatura]);
  const chaveMeta='studio_vozes_meta_'+slug;
  const [metaTxt,setMetaTxt]=useState(()=>{ try{ return localStorage.getItem(chaveMeta)||''; }catch{ return ''; } });
  const [maxVel,setMaxVel]=useState(1.25);
  useEffect(()=>{ try{ localStorage.setItem(chaveMeta,metaTxt); }catch{ /* sem armazenamento */ } },[metaTxt,chaveMeta]);
  const alvo=lerTempo(metaTxt);
  useEffect(()=>{ setRes(null); },[metaTxt,maxVel]);
  const prev=previaTempo(roteiro,takes,pausaIni);
  const pausasTot=roteiro.filter(f=>f.tipo==='fala'||f.tipo==='som').reduce((a,f)=>a+(Number.isFinite(f.pausa)?f.pausa:0.4),0);
  const minimo=prev.total-prev.fala+prev.fala/maxVel-pausasTot*0.65;
  async function montar(){ setMontando(true); try{ setRes(await montarEpisodio(roteiro,takes,nomes,pausaIni,alvo?{alvo,maxVel}:undefined)); }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); } finally{ setMontando(false); } }
  async function zip(){
    if(!res) return; const z=new JSZip();
    z.file(`${slug}-completo.wav`,res.wav); z.file(`${slug}.srt`,srt(res.manifesto,comNome)); z.file(`${slug}-manifesto.json`,JSON.stringify({projeto,duracao:+res.duracao.toFixed(3),falas:res.manifesto},null,2));
    const pasta=z.folder('falas')!; for(const m of res.manifesto){ const t=takes.find(x=>x.id===m.take); if(t) pasta.file(m.arquivo,t.wav); }
    baixar(await z.generateAsync({type:'blob'}),`${slug}-audio.zip`);
  }
  if(!falasR.length) return <section className="panel empty-state"><FileAudio size={30}/><h2>Coloque um roteiro primeiro</h2><button className="primary" onClick={irRoteiro}>Ir para Roteiro</button></section>;
  return <section className="panel">
   <div className="section-head"><h2><FileAudio size={18}/> Arquivo final</h2></div>
   <p className="hint">Junta o take aprovado de cada fala, na ordem do roteiro, com a pausa que você definiu. Sai o áudio completo para colocar no vídeo, a legenda .srt com os tempos certos e o manifesto (quem fala, quando começa e termina) para animação.</p>
   <div className="conferencia">
    <div className={semAprov.length?'tag':'tag ok'}>{semAprov.length?`${semAprov.length} fala(s) sem take aprovado`:'Todas as falas com take aprovado'}</div>
    {semQuem.length>0&&<div className="tag">{semQuem.length} fala(s) sem personagem</div>}
    {vozNaoAprov.length>0&&<div className="tag">Voz ainda não aprovada: {vozNaoAprov.map(p=>p.nome).join(', ')}</div>}
   </div>
   {semAprov.length>0&&<p className="hint">Faltando: {semAprov.slice(0,8).map(f=>`#${f.ordem+1}`).join(', ')}{semAprov.length>8?'...':''}. Elas ficam de fora da montagem. <button className="link-btn inline" onClick={irRoteiro}>Gerar no Roteiro</button></p>}
   <div className="small-grid mt">
    <label>Silêncio no começo (s)<input type="number" min={0} max={10} step={0.1} value={pausaIni} onChange={e=>setPausaIni(Math.max(0,+e.target.value))}/></label>
    <label className="check"><input type="checkbox" checked={comNome} onChange={e=>setComNome(e.target.checked)}/> Legenda com o nome de quem fala</label>
   </div>
   <div className="tempo-meta mt">
    <h3>Tempo do vídeo</h3>
    <p className="previa-tempo"><b>Prévia:</b> cerca de <b>{fmt(prev.total)}</b> de áudio ({fmt(prev.fala)} só de falas{prev.faltam?`, ${prev.faltam} sem take ainda`:''}).</p>
    <div className="small-grid">
     <label>Quanto o vídeo precisa ter (minutos)<input value={metaTxt} placeholder="ex.: 10 ou 9:30 (vazio = sem limite)" onChange={e=>setMetaTxt(e.target.value)} aria-label="Tempo do vídeo"/></label>
     <label>Acelerar a fala no máximo<select value={maxVel} onChange={e=>setMaxVel(+e.target.value)}><option value={1.1}>1,10x (quase não se nota)</option><option value={1.2}>1,20x</option><option value={1.25}>1,25x (recomendado)</option><option value={1.35}>1,35x</option><option value={1.5}>1,50x (bem rápido)</option></select></label>
    </div>
    {alvo>0&&(prev.total<=alvo?<p className="hint ok-txt">Cabe no tempo: sobra {fmt(alvo-prev.total)}. Nada será cortado.</p>
     :<p className="hint">Passa {fmt(prev.total-alvo)} do tempo. Ao montar, o site corta o silêncio das pontas das falas, encurta as pausas e, se ainda precisar, acelera a fala (sem mudar o tom) até {String(maxVel).replace('.',',')}x.{minimo>alvo?` Atenção: mesmo no máximo deve ficar perto de ${fmt(minimo)}. Aumente a aceleração ou tire algumas falas.`:''}</p>)}
   </div>
   <button className="primary lg mt" disabled={montando||semAprov.length===falasR.length} onClick={montar}>{montando?<Loader2 size={17} className="spin"/>:<Package size={17}/>} Montar o áudio do episódio</button>
   {res&&<div className="final-ok mt">
    <p><b>Pronto:</b> {res.manifesto.filter(m=>m.tipo!=='som').length} falas{res.manifesto.some(m=>m.tipo==='som')?` e ${res.manifesto.filter(m=>m.tipo==='som').length} sons`:''} • {fmt(res.duracao)} de áudio{res.faltando.length?` • ${res.faltando.length} faltando`:''}</p>
    {res.ajuste&&res.ajuste.passos.length>0&&<div className={'ajuste-tempo '+(res.ajuste.bateu?'ok':'')}><b>{res.ajuste.bateu?'Ajustado para caber no tempo':'Ainda passou do tempo'}:</b> {fmt(res.ajuste.original)} → {fmt(res.ajuste.final)} (meta {fmt(res.ajuste.alvo)})<ul>{res.ajuste.passos.map(x=><li key={x}>{x}</li>)}</ul>{!res.ajuste.bateu&&<small>Aumente a aceleração máxima ou tire algumas falas do roteiro.</small>}</div>}
    <Audio blob={res.wav}/>
    <div className="row-gap left mt">
     <button className="primary" onClick={()=>baixar(res.wav,`${slug}-completo.wav`)}><Download size={15}/> Áudio completo (WAV)</button>
     <button className="subtle" onClick={()=>baixar(new Blob([srt(res.manifesto,comNome)],{type:'text/plain'}),`${slug}.srt`)}><FileText size={15}/> Legenda (.srt)</button>
     <button className="subtle" onClick={()=>baixar(new Blob([JSON.stringify({projeto,duracao:+res.duracao.toFixed(3),falas:res.manifesto},null,2)],{type:'application/json'}),`${slug}-manifesto.json`)}><FileText size={15}/> Manifesto (.json)</button>
     <button className="subtle" onClick={zip}><Package size={15}/> Tudo em ZIP (com cada fala separada)</button>
    </div>
    <details className="mt"><summary>Linha do tempo</summary><div className="linha-tempo">{res.manifesto.map(m=><div key={m.take}><small>{fmt(m.inicio)} – {fmt(m.fim)}</small> <b>{m.personagem}:</b> {m.texto}</div>)}</div></details>
   </div>}
  </section>;
}
