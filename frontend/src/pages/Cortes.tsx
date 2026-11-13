import { useEffect, useMemo, useRef, useState } from 'react';
import { Upload, Film, Sparkles, Loader2, CheckCircle2, Circle, AlertTriangle, Pencil, Download, Copy, Trash2, Undo2, FileText, Wand2, Package, Play, CalendarClock, ArrowRight, Clock, GitCompare, RotateCcw, X, ChevronDown } from 'lucide-react';
import { useApp, captionPresets, PROJETO_VAZIO, type Job } from '../state';
import { HelpButton } from '../components/Help';
import Editor from '../components/Editor';
import LinkStudio from '../components/LinkStudio';
import AgendarPost from '../components/AgendarPost';
import EdicaoLote from '../components/EdicaoLote';
import { dublarCorte } from '../lib/dublagem';
import { legendaAutomatica } from '../lib/legendasPost';
import PostarLote from '../components/PostarLote';
import { iaAtiva, nomeIA, avaliar, erroIA, escolherNaTranscricao } from '../lib/ia';
import { ErroGemini, erroGemini } from '../lib/gemini';
import { videoInfo, decodeAudio, energyProfile, captureFrames, type AudioData } from '../lib/media';
import { gerarCandidatos, avaliarJanelas, notaFinal, nota10, cuesDe, urlDe, fatorEscala, faixaNota, sobrepoe, completar, type Clip, type Candidate, type Escolhido } from '../lib/analyze';
import { parseLegendas, type Cue } from '../lib/captions';
import { transcrever, transcreverGemini, IDIOMAS } from '../lib/transcribe';
import { formatoSuportado } from '../lib/render';
import { AJUSTE_MAX } from '../lib/promptCortes';
import { renderClip, baixar, zipar, nomeArquivo, srtDoCorte } from '../lib/exporter';
import { tm, parseTime, uid, store } from '../lib/store';

// Cache do áudio decodificado, para refazer a análise sem ler o arquivo de novo.
/** Erro de leitura do arquivo (comum no Android) em português. */
const CELULAR=typeof navigator!=='undefined'&&/Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
export function erroArquivo(e:unknown){
  const m=e instanceof Error?e.message:String(e);
  if(/could not be read|NotReadable|permission/i.test(m)||(e as any)?.name==='NotReadableError') return CELULAR
    ?'O celular não deixou o site ler esse vídeo. Escolha o arquivo de novo, de preferência pelo app Arquivos ou pela pasta Downloads (não pela Galeria ou Google Fotos). Se o vídeo estiver na nuvem, baixe para o celular antes.'
    :'O computador não deixou o site ler esse vídeo. Isso acontece quando o arquivo ainda está baixando, está aberto em outro programa (editor de vídeo) ou está só na nuvem (OneDrive/Google Drive, ícone de nuvem). Espere terminar, feche o outro programa ou copie o vídeo para a pasta Downloads e escolha de novo.';
  if(/memory|allocation|too large|Array buffer/i.test(m)) return 'O vídeo é grande demais para a memória deste aparelho. Tente um vídeo menor ou use o computador.';
  return m;
}
let cache:{file:File|null;audio:AudioData|null;energy:Float32Array|null} = {file:null,audio:null,energy:null};
const STEP=0.5;
const DURACOES:[string,number,number][] = [['Até 30 s',15,30],['30–60 s',30,60],['61–90 s',61,90],['90–180 s',90,180]];
type Etapa='cortes'|'edicao'|'postar';
// Guarda a etapa e a seleção ao trocar de aba (o vídeo continua carregado).
let mem:{etapa:Etapa;sel:Set<string>;url:string;tempos:string;inteiro:boolean}={etapa:'cortes',sel:new Set(),url:'',tempos:'',inteiro:false};
/** Chamado pelo Radar: o próximo vídeo aberto é usado inteiro (sem cortar) e vai direto para a edição. */
export function usarVideoInteiro(v:boolean){ mem={...mem,inteiro:v}; }
/** Chamado pelo Radar depois de baixar vários vídeos: abre direto a edição com todos marcados. */
export function abrirLote(ids:string[],url:string){ mem={etapa:'edicao',sel:new Set(ids),url,tempos:'',inteiro:false}; }

/** Lê os tempos colados, um corte por linha: "0:30-1:10", "1:02:05 a 1:03:00 Título", "90-120". */
export function lerTempos(txt:string){
  const janelas:{inicio:number;fim:number;titulo?:string}[]=[]; const erros:string[]=[];
  const T='(\\d{1,3}(?::\\d{1,2}){0,2}(?:[.,]\\d+)?)';
  const re=new RegExp('^'+T+'\\s*(?:-|–|—|a|até|ate|to|>|\\s)\\s*'+T+'(?:\\s+|\\s*[-–:|]\\s*|$)(.*)$','i');
  for(const linha of txt.split(/\n|;|,(?=\s*\d{1,2}:)/)){
    const l=linha.trim().replace(/^[\d]+[.)]\s+(?=\d)/,''); if(!l) continue;
    const m=re.exec(l); if(!m){ erros.push(l); continue; }
    const a=parseTime(m[1].replace(',','.')), b=parseTime(m[2].replace(',','.'));
    if(isNaN(a)||isNaN(b)||b<=a){ erros.push(l); continue; }
    janelas.push({inicio:a,fim:b,titulo:m[3].trim()||undefined});
  }
  return {janelas,erros};
}

export default function Cortes(){
  const {settings,toast,projeto,setProjeto,template,marcas,go}=useApp();
  const [usarMarcas,setUsarMarcas]=useState(true);
  const [direitos,setD]=useState(()=>store.get('studio_direitos')==='1');
  const setDireitos=(v:boolean)=>{ setD(v); store.set('studio_direitos',v?'1':''); };
  const [modelo,setModelo]=useState<'falas'|'acao'>('falas');
  const [faixa,setFaixa]=useState<[number,number]>([30,60]);
  const [custom,setCustom]=useState(false);
  const [trechoIni,setTrechoIni]=useState(''); const [trechoFim,setTrechoFim]=useState('');
  const [limite,setLimite]=useState(15); const [minimo,setMinimo]=useState(30);
  const [legSrc,setLegSrc]=useState<'depois'|'auto'|'gemini'|'arquivo'|'nenhuma'>('depois'); const [idioma,setIdioma]=useState(settings.idioma);
  const [prompt,setPrompt]=useState(''); const [tema,setTema]=useState('');
  const [srtFile,setSrtFile]=useState<File|null>(null);
  const [mostrarTodos,setMostrarTodos]=useState(false); const [ordem,setOrdem]=useState<'nota'|'tempo'>('nota');
  const mesmo=mem.url===projeto.url&&!!projeto.url;
  const [sel,setSel]=useState<Set<string>>(()=>mesmo?mem.sel:new Set());
  const [aberto,setAberto]=useState<'opcoes'|'video'|'cortes'>(()=>projeto.clips.length&&projeto.job.status==='pronto'?'cortes':projeto.file?'video':'opcoes');
  const [etapa,setE]=useState<Etapa>(()=>mesmo?mem.etapa:'cortes');
  const [tempos,setTempos]=useState(mem.tempos);
  const [inteiro,setInteiro]=useState(mem.inteiro);
  const [legErro,setLegErro]=useState('');
  useEffect(()=>{ mem={etapa,sel,url:projeto.url,tempos,inteiro}; },[etapa,sel,projeto.url,tempos,inteiro]);
  const setEtapa=(e:Etapa)=>{ setE(e); window.scrollTo({top:0}); };
  const lidos=useMemo(()=>lerTempos(tempos),[tempos]);
  const [editando,setEditando]=useState<Clip|null>(null);
  const [postarIds,setPostarIds]=useState<string[]|null>(null);
  const [agendando,setAgendando]=useState<Clip|null>(null);
  const [exp,setExp]=useState<{id:string;pct:number;fila?:string}|null>(null);
  const [previa,setPrevia]=useState(''); const [comparar,setComparar]=useState<[string,string]|null>(null);
  // Exportação em lote: um status por corte, para repetir só os que falharam.
  type ItemLote={id:string;titulo:string;status:'fila'|'gravando'|'ok'|'erro';pct:number;erro?:string};
  const [lote,setLote]=useState<{itens:ItemLote[];rodando:boolean}|null>(null);
  const prontos=useRef(new Map<string,{nome:string;blob:Blob;srt:string}>());
  const [drag,setDrag]=useState(false);
  const [novoPrompt,setNovoPrompt]=useState('');
  const fileInput=useRef<HTMLInputElement>(null);
  const job=projeto.job; const rodando=job.status==='rodando';
  const qualIA=iaAtiva(settings); const temIA=!!qualIA; const rotuloIA=`Avaliando com IA (${nomeIA(qualIA)})`;
  const recSupport=formatoSuportado();

  /** iniciar=true quando veio do botão "Baixar e começar" (link): já gera os cortes com as opções escolhidas. */
  async function escolherArquivo(orig:File|null,iniciar=false){
    if(!orig) return;
    if(!orig.type.startsWith('video/') && !/\.(mp4|mov|mkv|webm|m4v)$/i.test(orig.name)){ toast('Escolha um arquivo de vídeo (MP4, MOV, WEBM).','erro'); return; }
    // No celular, a permissão de ler o arquivo escolhido pode acabar antes de tocar em Gerar cortes.
    // Por isso guardamos uma cópia do vídeo na memória logo ao escolher.
    let f=orig;
    if(!iniciar){   // arquivo do servidor já está na memória
      setLendo(true);
      try{
        if(CELULAR) f=new File([await orig.arrayBuffer()],orig.name,{type:orig.type||'video/mp4'});
        else await orig.slice(0,1024*1024).arrayBuffer();   // no computador só confere se dá para ler (vídeos grandes não cabem na memória)
      }catch(e){
        // Se a cópia falhou mas o arquivo ainda abre, segue com o original.
        let ok=false; if(CELULAR){ try{ await orig.slice(0,1024*1024).arrayBuffer(); ok=true; }catch{ /* não dá mesmo */ } }
        if(!ok){ setLendo(false); toast(erroArquivo(e),'erro'); return; }
      }
      setLendo(false);
    }
    if(projeto.url) URL.revokeObjectURL(projeto.url);
    cache={file:null,audio:null,energy:null};
    const url=URL.createObjectURL(f);
    setProjeto(()=>({...PROJETO_VAZIO,file:f,url,nome:f.name}));
    setSel(new Set()); setE('cortes'); setLegErro(''); setAberto('video');
    if(iniciar&&direitos){ gerar({file:f,url}); return; }
    videoInfo(url).then(i=>setProjeto(p=>p.url===url?{...p,duracao:i.duration}:p)).catch(e=>toast(e.message,'erro'));
    toast('Vídeo carregado. Confira as opções e toque em Gerar cortes.','ok');
    setTimeout(()=>document.getElementById('btn-gerar')?.scrollIntoView({behavior:'smooth',block:'center'}),400);
  }
  const [lendo,setLendo]=useState(false);
  const setJob=(j:Partial<Job>)=>setProjeto(p=>({...p,job:{...p.job,...j}}));

  async function avaliarIA(cands:(Candidate&{id:string})[],cues:Cue[],promptTxt:string,temaTxt:string,url=projeto.url){
    const top=cands.slice(0,Math.min(30,Math.max(10,limite*2)));
    if(!top.length) return new Map<string,any>();
    let frames:Record<string,string[]>|undefined;
    // Sem transcrição a IA não tem o que ler: manda quadros do vídeo para ela julgar pela imagem.
    if(modelo==='acao'||!cues.length){
      frames={};
      for(const c of top.slice(0,20)){ frames[c.id]=await captureFrames(url,[c.inicio+(c.fim-c.inicio)*0.25,c.inicio+(c.fim-c.inicio)*0.65],512); }
    }
    const res=await avaliar(settings,top,cues,{prompt:promptTxt,tema:temaTxt,frames,semFala:!cues.length});
    const k=fatorEscala(res.flatMap(r=>[r.gancho,r.fluxo,r.valor,r.tendencia]));   // resposta em escala de 0 a 10 vira 0 a 99
    return new Map(res.map(r=>[r.id,k===1?r:{...r,gancho:r.gancho*k,fluxo:r.fluxo*k,valor:r.valor*k,tendencia:r.tendencia*k}]));
  }

  function montarClips(cands:(Candidate&{id:string;titulo?:string;tituloIA?:string;gancho?:string;daIA?:boolean})[],ia:Map<string,any>|null,dur:number):Clip[]{
    const out=cands.map(c=>{
      const r=ia?.get(c.id);
      const notas=r?{gancho:clamp(r.gancho),fluxo:clamp(r.fluxo),valor:clamp(r.valor),tendencia:clamp(r.tendencia)}:c.notas;
      let ini=r&&Math.abs(r.inicio-c.inicio)<=AJUSTE_MAX?Math.max(0,r.inicio):c.inicio; let fim=r&&Math.abs(r.fim-c.fim)<=AJUSTE_MAX?Math.min(dur,r.fim):c.fim;
      if(fim-ini<Math.min(5,c.fim-c.inicio)){ ini=c.inicio; fim=c.fim; }   // ajuste da IA deixou curto demais: mantém o original
      const nf=notaFinal(notas);
      return {id:c.id,titulo:c.titulo||c.tituloIA||r?.titulo||'',marca:c.titulo,inicio:+ini.toFixed(2),fim:+fim.toFixed(2),notas,nota_final:nf,nota_10:nota10(nf),motivo:r?.motivo||c.motivo,fonte:r||c.daIA?'ia':'heuristica',legenda:legSrc==='nenhuma'?'':settings.legendaPadrao,efeito:settings.efeitoPadrao,formato:'9:16',gancho_texto:String(r?.gancho_texto||c.gancho||'').replace(/[#"“”]/g,'').trim().slice(0,60)} as Clip;
    });
    // Os avaliados pela IA vêm antes dos que só têm a nota automática do áudio.
    const daIA=(c:Clip)=>c.fonte==='ia'?1:0;
    out.sort((a,b)=>daIA(b)-daIA(a)||b.nota_final-a.nota_final||b.notas.gancho-a.notas.gancho||a.inicio-b.inicio);
    out.forEach((c,i)=>{ if(!c.titulo) c.titulo=`Destaque ${i+1}`; });
    return out;
  }

  /** Vídeo curto: usa o arquivo inteiro como um corte só e vai direto para a edição. */
  async function usarInteiro(file:File,url:string){
    const etapas=['Lendo o vídeo','Gerando miniatura'];
    setProjeto(p=>({...p,clips:[],candidatos:0,job:{status:'rodando',etapa:etapas[0],pct:0,etapas}}));
    setSel(new Set()); setLegErro('');
    try{
      const info=await videoInfo(url);
      setJob({etapa:'Gerando miniatura'});
      const [thumb]=await captureFrames(url,[Math.min(Math.max(0,info.duration-0.1),1.5)],320).catch(()=>[] as string[]);
      const id=uid();
      const clip:Clip={id,titulo:file.name.replace(/\.\w+$/,'').slice(0,90),inicio:0,fim:+info.duration.toFixed(2),notas:{gancho:0,fluxo:0,valor:0,tendencia:0},nota_final:0,nota_10:0,motivo:'Vídeo inteiro, sem cortes.',fonte:'heuristica',legenda:legSrc==='nenhuma'?'':settings.legendaPadrao,efeito:settings.efeitoPadrao,formato:'9:16',gancho_texto:'',thumb};
      setProjeto(p=>({...p,duracao:info.duration,clips:[clip],candidatos:1,job:{...p.job,status:'pronto',etapa:'',pct:100,erro:undefined}}));
      setMostrarTodos(true); setSel(new Set([id])); setE('edicao'); window.scrollTo({top:0});
      toast('Vídeo pronto para editar: coloque o template e a legenda.','ok');
    }catch(e){ const msg=erroArquivo(e); setJob({status:'erro',erro:msg}); toast(msg,'erro'); }
  }

  /** Faz a legenda só dos cortes escolhidos (bem mais rápido que o vídeo todo). */
  /** Dubla os cortes em português (Gemini): troca a legenda pela traduzida e guarda a voz para a exportação. */
  async function dublar(ids:string[],voz:string,volumeOriginal:number,onStatus:(s:string,pct:number)=>void){
    if(!settings.geminiKey) throw new Error('Coloque a chave do Gemini em Chaves e ajustes.');
    const lista=projeto.clips.filter(c=>ids.includes(c.id)); let cues=projeto.cues;
    for(let i=0;i<lista.length;i++){
      const c=lista[i];
      if(c.video){
        const novas=await dublarCorte(settings.geminiKey,c,c.video.cues,voz,volumeOriginal,(t,p)=>onStatus(lista.length>1?`Corte ${i+1} de ${lista.length}: ${t}`:t,Math.round((i+p/100)/lista.length*100)));
        setProjeto(p=>({...p,clips:p.clips.map(x=>x.id===c.id&&x.video?{...x,video:{...x.video,cues:novas},dublado:true,legendaOk:true,legenda:x.legenda||settings.legendaPadrao}:x)}));
        continue;
      }
      const novas=await dublarCorte(settings.geminiKey,c,cues,voz,volumeOriginal,(t,p)=>onStatus(lista.length>1?`Corte ${i+1} de ${lista.length}: ${t}`:t,Math.round((i+p/100)/lista.length*100)));
      cues=[...cues.filter(q=>!(q.end>c.inicio&&q.start<c.fim)),...novas].sort((a,b)=>a.start-b.start);
      const fixas=cues;
      setProjeto(p=>({...p,cues:fixas,clips:p.clips.map(x=>x.id===c.id?{...x,dublado:true,legendaOk:true,legenda:x.legenda||settings.legendaPadrao}:x)}));
    }
    return lista.length;
  }

  async function gerarLegendas(idsTodos:string[],via:'auto'|'gemini',onStatus:(s:string,pct:number)=>void){
    // Cortes com vídeo próprio (lote do Radar): transcreve cada vídeo inteiro, que já é curto.
    const proprios=projeto.clips.filter(c=>idsTodos.includes(c.id)&&c.video);
    let n=0;
    for(let i=0;i<proprios.length;i++){
      const c=proprios[i], f=c.video!;
      const st=(t:string,p:number)=>onStatus(proprios.length>1?`Vídeo ${i+1} de ${proprios.length}: ${t}`:t,Math.round((i+p/100)/proprios.length*100));
      st('Lendo o áudio do vídeo',0);
      const audio=await decodeAudio(f.file);
      if(!audio) throw new Error('O navegador não conseguiu ler o áudio de um dos vídeos. Tente pelo computador.');
      const cues=via==='gemini'?await transcreverGemini(audio.samples,settings.geminiKey,settings.idioma,st):await transcrever(audio.samples,settings.whisperModel,settings.idioma,st);
      n+=cues.length;
      setProjeto(p=>({...p,clips:p.clips.map(x=>x.id===c.id&&x.video?{...x,video:{...x.video,cues},legendaOk:true,legenda:x.legenda||settings.legendaPadrao}:x)}));
    }
    const ids=idsTodos.filter(id=>!proprios.some(c=>c.id===id));
    if(!ids.length) return n;
    const file=projeto.file; if(!file) throw new Error('Envie o vídeo de novo.');
    if(cache.file!==file||!cache.audio){ onStatus('Lendo o áudio do vídeo',0); const audio=await decodeAudio(file,p=>onStatus('Lendo o áudio do vídeo',p)); cache={file,audio,energy:audio?energyProfile(audio,STEP):null}; }
    const audio=cache.audio;
    if(!audio) throw new Error('O navegador não conseguiu ler o áudio deste vídeo. Tente pelo computador ou envie um .srt.');
    const R=16000;
    // Junta os trechos (sem repetir partes iguais) com 1 s de silêncio entre eles e transcreve tudo de uma vez.
    const faixas=projeto.clips.filter(c=>ids.includes(c.id)).map(c=>[Math.max(0,Math.floor(c.inicio*R)),Math.min(audio.samples.length,Math.ceil(c.fim*R))] as [number,number]).sort((a,b)=>a[0]-b[0]);
    const unidas:[number,number][]=[]; for(const f of faixas){ const u=unidas[unidas.length-1]; if(u&&f[0]<=u[1]) u[1]=Math.max(u[1],f[1]); else unidas.push([...f]); }
    const total=unidas.reduce((t,[a,b])=>t+(b-a)+R,0); const junto=new Float32Array(total);
    const mapa:{ini:number;fim:number;base:number}[]=[]; let off=0;
    for(const [a,b] of unidas){ junto.set(audio.samples.subarray(a,b),off); mapa.push({ini:off/R,fim:(off+b-a)/R,base:a/R}); off+=b-a+R; }
    const cues=via==='gemini'?await transcreverGemini(junto,settings.geminiKey,settings.idioma,onStatus):await transcrever(junto,settings.whisperModel,settings.idioma,onStatus);
    const novas:Cue[]=[];
    for(const q of cues){ const m=mapa.find(x=>q.start>=x.ini-0.3&&q.start<x.fim); if(!m) continue; const d=m.base-m.ini; novas.push({start:+Math.max(m.base,q.start+d).toFixed(2),end:+Math.min(m.base+(m.fim-m.ini),Math.max(q.start,q.end)+d).toFixed(2),text:q.text}); }
    setProjeto(p=>{ const fora=p.cues.filter(q=>!unidas.some(([a,b])=>q.start<b/R&&q.end>a/R)); return {...p,cues:[...fora,...novas].sort((a,b)=>a.start-b.start),cuesFonte:via==='gemini'?'gemini':'whisper',clips:p.clips.map(c=>ids.includes(c.id)?{...c,legendaOk:true,legenda:c.legenda||settings.legendaPadrao}:c)}; });
    return novas.length;
  }

  async function gerar(src?:{file:File;url:string}){
    const file=src?.file??projeto.file, url=src?.url??projeto.url;
    if(!file||!direitos) return;
    if(inteiro){ await usarInteiro(file,url); return; }
    // Com IA, o site ouve as falas antes: é lendo a transcrição que a IA acha os melhores momentos.
    const ouvir=legSrc==='depois'&&temIA&&!!settings.geminiKey&&!lerTempos(tempos).janelas.length&&!(usarMarcas&&marcas.length>0);
    const etapaLeg=ouvir?'Ouvindo as falas para escolher os cortes':'Preparando a legenda';
    const etapas=['Lendo o vídeo','Analisando o áudio',...(ouvir||legSrc!=='nenhuma'&&legSrc!=='depois'?[etapaLeg]:[]),'Montando candidatos',...(temIA?[rotuloIA]:[]),'Gerando miniaturas'];
    setProjeto(p=>({...p,clips:[],candidatos:0,prompt,tema,job:{status:'rodando',etapa:etapas[0],pct:0,etapas}}));
    setSel(new Set()); setE('cortes'); setLegErro('');
    try{
      const info=await videoInfo(url);
      setJob({etapa:'Analisando o áudio',pct:0});
      if(cache.file!==file){ const audio=await decodeAudio(file,p=>setJob({etapa:'Analisando o áudio',pct:p})); cache={file,audio,energy:audio?energyProfile(audio,STEP):null}; }
      if(!cache.audio) toast('O navegador não conseguiu ler o áudio deste vídeo. Os cortes serão sugeridos em sequência e sem legenda automática.','erro');
      let cues:Cue[]=src?[]:projeto.cues; let fonte=src?'':projeto.cuesFonte;
      if(legSrc==='arquivo'){
        if(!srtFile) throw new Error('Escolha o arquivo de legenda (.srt ou .vtt) ou mude a opção de legenda.');
        setJob({etapa:'Preparando a legenda'}); cues=parseLegendas(await srtFile.text()); fonte='arquivo';
        if(!cues.length) toast('Não encontramos falas no arquivo de legenda.','erro');
      }else if((legSrc==='auto'||legSrc==='gemini'||ouvir) && cache.audio && fonte!=='whisper' && fonte!=='gemini'){
        setJob({etapa:etapaLeg,pct:0});
        const audio=cache.audio;
        const status=(st:string,pct:number)=>setJob({etapa:etapaLeg,pct,erro:st});
        const viaGemini=async()=>{ cues=await transcreverGemini(audio.samples,settings.geminiKey,idioma,status); fonte='gemini'; };
        try{
          if(legSrc==='gemini'||ouvir) await viaGemini();
          else{
            try{ cues=await transcrever(audio.samples,settings.whisperModel,idioma,status); fonte='whisper'; }
            catch(e){
              if(!settings.geminiKey) throw e;
              console.warn(e); toast('A legenda no aparelho falhou. Tentando pelo Gemini...','info'); await viaGemini();
            }
          }
          if(!cues.length) toast('Não encontramos fala neste vídeo para a legenda.','info');
        }catch(e){
          cues=[]; fonte='';
          const msg=e instanceof ErroGemini?erroGemini(e):e instanceof Error?e.message:String(e);
          if(ouvir) toast('Não deu para ouvir as falas agora ('+msg+'). Os cortes serão escolhidos pelo áudio e pela imagem.','info');
          else{ setLegErro(msg); toast(msg+' Os cortes serão gerados sem legenda.','erro'); }
        }
      }else if(legSrc==='nenhuma'){ cues=[]; fonte=''; }
      if((legSrc==='auto'||legSrc==='gemini')&&!cache.audio) setLegErro('O navegador não conseguiu ler o áudio deste arquivo, então não deu para fazer a legenda. Isso costuma acontecer com vídeos muito grandes no celular: tente pelo computador, um vídeo menor, ou envie um .srt.');
      setProjeto(p=>({...p,cues,cuesFonte:fonte,duracao:info.duration}));
      setJob({etapa:'Montando candidatos',pct:0,erro:undefined});
      const ini=trechoIni?parseTime(trechoIni):0, fimT=trechoFim?parseTime(trechoFim):0;
      const manuais=lerTempos(tempos).janelas;
      const porMarca=manuais.length>0||(usarMarcas&&marcas.length>0);
      const janelas=manuais.length?manuais:marcas;
      // Trecho marcado/colado maior que a duração máxima escolhida = área de busca: vira vários cortes dentro dele.
      const validas=janelas.filter(m=>m.inicio<info.duration).map(m=>({...m,fim:Math.min(m.fim,info.duration)}));
      const curtas=validas.filter(m=>m.fim-m.inicio<=faixa[1]+3), longas=validas.filter(m=>m.fim-m.inicio>faixa[1]+3);
      const dasLongas=longas.flatMap(m=>gerarCandidatos(cache.energy,STEP,info.duration,modelo==='falas'?cues:cues.length?cues:[],{min:faixa[0],max:faixa[1],limite,inicio:m.inicio,fim:m.fim,sobreposicao:0.05}));
      // Trechos que a IA achou assistindo o link já vêm com nota, motivo e frase de gancho: aproveita.
      const comLink=(l:(Candidate&{titulo?:string})[])=>manuais.length?l:l.map(c=>{ const m=marcas.find(x=>x.ia&&x.nota!=null&&Math.abs(x.inicio-c.inicio)<0.06&&Math.abs(x.fim-c.fim)<0.06); if(!m) return c; const n=m.nota!;
        return {...c,notas:{gancho:cache.energy?Math.round((n*2+c.notas.gancho)/3):n,fluxo:n,valor:cache.energy?Math.round((n*2+c.notas.valor)/3):n,tendencia:n},motivo:m.motivo||c.motivo,gancho:m.gancho||'',daIA:true}; });
      const a0=isNaN(ini)?0:ini, b0=isNaN(fimT)?0:fimT;
      const auto=()=>gerarCandidatos(cache.energy,STEP,info.duration,cues,{min:faixa[0],max:faixa[1],limite,inicio:porMarca?0:a0,fim:porMarca?0:b0});
      type Cand=Candidate&{id:string;titulo?:string;tituloIA?:string;gancho?:string;daIA?:boolean};
      let cands:Cand[]; let completou=false; let jaAvaliados=0;
      if(porMarca){
        let l:(Candidate&{titulo?:string})[]=[...comLink(avaliarJanelas(cache.energy,STEP,cues,curtas)),...dasLongas];
        // A IA do link devolveu menos trechos do que o pedido: completa com os melhores momentos do resto do vídeo.
        if(!manuais.length&&l.length>0&&l.length<limite&&marcas.every(m=>m.ia)){ const n=l.length; l=completar(l,auto(),limite); completou=l.length>n; }
        cands=l.map(c=>({...c,id:uid()}));
      }else{
        const heur=auto();
        let lidos2:Escolhido[]=[];
        if(temIA&&cues.length>=6){
          setJob({etapa:rotuloIA,pct:0});
          try{ lidos2=await escolherNaTranscricao(settings,cues,{limite,min:faixa[0],max:faixa[1],tema,prompt,ini:a0,fim:b0,duracao:info.duration},p=>setJob({etapa:rotuloIA,pct:p})); }
          catch(e){ toast('A IA não conseguiu ler a transcrição agora. '+await erroIA(settings,e),'erro'); }
        }
        const base:Cand[]=lidos2.map(c=>({...c,titulo:undefined,tituloIA:c.titulo,daIA:true,id:uid()}));
        jaAvaliados=base.length;
        cands=[...base,...heur.filter(h=>base.every(s=>sobrepoe(s,h)<=0.3)).map(c=>({...c,id:uid()}))];
      }
      if(!cands.length&&porMarca) throw new Error(`Os tempos ${manuais.length?'colados':'marcados'} ficam depois do fim deste vídeo (${tm(info.duration)}). Confira os tempos ou o arquivo.`);
      if(!cands.length) throw new Error('O vídeo (ou o trecho escolhido) é mais curto que a duração mínima dos cortes. Escolha uma duração menor.');
      let ia:Map<string,any>|null=null;
      if(temIA){
        setJob({etapa:rotuloIA});
        // Só avalia o que a IA ainda não escolheu, e só se faltar corte para a quantidade pedida.
        try{ if(jaAvaliados<limite) ia=await avaliarIA(cands.slice(jaAvaliados),cues,prompt,tema,url); }
        catch(e){ toast('A avaliação com IA falhou, usando notas automáticas. '+await erroIA(settings,e),'erro'); }
      }
      let clips=montarClips(cands,ia,info.duration);
      setProjeto(p=>({...p,clips,candidatos:cands.length}));
      setJob({etapa:'Gerando miniaturas'});
      const top=clips.slice(0,30);
      const thumbs=await captureFrames(url,top.map(c=>Math.min(c.fim-0.1,c.inicio+1.5)),320).catch(()=>[] as string[]);
      clips=clips.map(c=>{ const i=top.indexOf(c); return i>=0&&thumbs[i]?{...c,thumb:thumbs[i]}:c; });
      setProjeto(p=>({...p,clips,job:{...p.job,status:'pronto',etapa:'',pct:100,erro:undefined}}));
      // Já deixa marcados os cortes que aparecem (dá para desmarcar).
      if(porMarca&&!longas.length&&!completou){ setMostrarTodos(true); setSel(new Set(clips.map(c=>c.id))); }
      else{ const topo=clips.slice(0,limite), bons=topo.filter(c=>c.nota_final>minimo); setSel(new Set((bons.length?bons:topo).map(c=>c.id))); }
      toast(porMarca&&longas.length?`${cands.length} cortes encontrados dentro do trecho que você separou, cada um com ${faixa[0]} a ${faixa[1]} s.`:porMarca?`${cands.length} cortes prontos nos tempos que você escolheu.`:`${cands.length} trechos avaliados. Confira os melhores abaixo.`,'ok');
    }catch(e){
      const msg=erroArquivo(e);
      setJob({status:'erro',erro:msg}); toast(msg,'erro');
    }
  }

  async function refazer(){
    if(!temIA||!novoPrompt.trim()) return;
    const cands=projeto.clips.filter(c=>!c.versao_de).map(c=>({id:c.id,inicio:c.inicio,fim:c.fim,notas:c.notas,motivo:c.motivo,titulo:c.marca}));
    const prev=new Map(projeto.clips.map(c=>[c.id,c]));
    setJob({status:'rodando',etapa:rotuloIA,etapas:[rotuloIA],pct:0});
    try{
      const ia=await avaliarIA(cands,projeto.cues,novoPrompt,projeto.tema);
      const clips=montarClips(cands,ia,projeto.duracao).map(c=>({...c,thumb:prev.get(c.id)?.thumb,legenda:prev.get(c.id)?.legenda??c.legenda,efeito:prev.get(c.id)?.efeito??c.efeito,formato:prev.get(c.id)?.formato??c.formato}));
      setProjeto(p=>({...p,clips,prompt:novoPrompt,job:{...p.job,status:'pronto',etapa:''}}));
      toast('Cortes reavaliados com o novo pedido.','ok');
    }catch(e){ setJob({status:'pronto'}); toast(await erroIA(settings,e),'erro'); }
  }

  const atualizar=(c:Clip)=>setProjeto(p=>({...p,clips:p.clips.map(x=>x.id===c.id?c:x)}));
  const duplicar=(c:Clip)=>{ const raiz=c.versao_de||c.id; const k=projeto.clips.filter(x=>x.versao_de===raiz).length+2; const n:Clip={...c,id:uid(),versao_de:raiz,titulo:c.titulo.replace(/ \((versão|variação) \d+\)$/,'')+` (variação ${k})`}; setProjeto(p=>{ const i=p.clips.findIndex(x=>x.id===c.id); const cl=[...p.clips]; cl.splice(i+1,0,n); return {...p,clips:cl}; }); toast('Variação criada logo abaixo do original. Mude o gancho, o enquadramento ou a legenda só nela: o original fica como está.','ok'); return n; };

  async function exportar(c:Clip){
    if(exp) return;
    setExp({id:c.id,pct:0});
    try{
      const {blob,ext}=await renderClip(projeto.url,c,projeto.cues,captionPresets,template,pct=>setExp({id:c.id,pct}));
      baixar(blob,nomeArquivo(c,visiveis.indexOf(c),ext));
      toast(`Corte exportado em ${ext.toUpperCase()}.`,'ok');
    }catch(e){ toast(e instanceof Error?e.message:String(e),'erro'); }
    finally{ setExp(null); }
  }
  async function exportarZip(soFalhas=false){
    if(exp||lote?.rodando) return;
    const base=soFalhas&&lote?lote.itens.filter(i=>i.status==='erro').map(i=>projeto.clips.find(c=>c.id===i.id)).filter((c):c is Clip=>!!c):escolhidos;
    if(!base.length) return;
    if(!soFalhas) prontos.current.clear();
    let itens:ItemLote[]=soFalhas&&lote?lote.itens.map(i=>i.status==='erro'?{...i,status:'fila' as const,pct:0,erro:undefined}:i):base.map(c=>({id:c.id,titulo:c.titulo,status:'fila' as const,pct:0}));
    const muda=(id:string,m:Partial<ItemLote>)=>{ itens=itens.map(i=>i.id===id?{...i,...m}:i); setLote({itens,rodando:true}); };
    setLote({itens,rodando:true});
    for(const c of base){
      muda(c.id,{status:'gravando',pct:0});
      try{
        const {blob,ext}=await renderClip(urlDe(c,projeto.url),c,cuesDe(c,projeto.cues),captionPresets,template,pct=>muda(c.id,{pct}));
        prontos.current.set(c.id,{nome:nomeArquivo(c,itens.findIndex(i=>i.id===c.id),ext),blob,srt:srtDoCorte(c,cuesDe(c,projeto.cues))||''});
        muda(c.id,{status:'ok',pct:100});
      }catch(e){ muda(c.id,{status:'erro',erro:e instanceof Error?e.message:String(e)}); }
    }
    setLote({itens,rodando:false});
    const falhas=itens.filter(i=>i.status==='erro').length;
    toast(falhas?`${itens.length-falhas} corte(s) prontos e ${falhas} com falha. Você pode repetir só os que falharam.`:`${itens.length} corte(s) prontos. Baixe o ZIP.`,falhas?'info':'ok');
  }
  async function baixarLote(){
    if(!lote) return; const lista=lote.itens.filter(i=>i.status==='ok').map(i=>({c:projeto.clips.find(c=>c.id===i.id),p:prontos.current.get(i.id)})).filter((x):x is {c:Clip;p:{nome:string;blob:Blob;srt:string}}=>!!x.c&&!!x.p);
    if(!lista.length) return; const extras:Record<string,string>={};
    for(const {p} of lista) if(p.srt) extras[p.nome.replace(/\.\w+$/,'.srt')]=p.srt;
    extras['cortes.csv']='arquivo;titulo;inicio;fim;nota_0_99;nota_0_10;gancho;fluxo;valor;tendencia;motivo\n'+lista.map(({c,p})=>[p.nome,c.titulo,tm(c.inicio),tm(c.fim),c.nota_final,c.nota_10,c.notas.gancho,c.notas.fluxo,c.notas.valor,c.notas.tendencia,c.motivo].map(x=>`"${String(x).replace(/"/g,'""')}"`).join(';')).join('\n');
    baixar(await zipar(lista.map(x=>({nome:x.p.nome,blob:x.p.blob})),extras),`cortes-${projeto.nome.replace(/\.\w+$/,'')||'video'}.zip`);
  }
  /** Trecho da fala dentro do corte. */
  const trecho=(c:Clip)=>{ const t=cuesDe(c,projeto.cues).filter(q=>q.end>c.inicio&&q.start<c.fim).map(q=>q.text.trim()).join(' ').replace(/\s+/g,' ').trim(); return t.length>170?t.slice(0,170).replace(/\s\S*$/,'')+'…':t; };
  /** Cortes que pegam o mesmo pedaço do vídeo (30% ou mais do menor). */
  const sobrepostos=(c:Clip)=>ativos.filter(x=>x.id!==c.id&&urlDe(x,projeto.url)===urlDe(c,projeto.url)&&x.versao_de!==c.id&&c.versao_de!==x.id&&(Math.min(x.fim,c.fim)-Math.max(x.inicio,c.inicio))>=0.3*Math.min(x.fim-x.inicio,c.fim-c.inicio));

  const ativos=projeto.clips.filter(c=>!c.descartado);
  // Sempre mostra a quantidade pedida; a pontuação mínima só avisa quais ficaram fracos.
  const topo=ativos.slice(0,limite);
  const aprovados=topo.filter(c=>c.nota_final>minimo);
  const visiveis=useMemo(()=>{ let l=mostrarTodos?ativos:topo; if(!mostrarTodos){ const ids=new Set(l.map(c=>c.id)); l=[...l,...ativos.filter(c=>c.versao_de&&ids.has(c.versao_de)&&!ids.has(c.id))]; } return ordem==='tempo'?[...l].sort((a,b)=>a.inicio-b.inicio):l; },[ativos,mostrarTodos,limite,ordem]);
  const descartados=projeto.clips.filter(c=>c.descartado);
  const escolhidos=[...visiveis.filter(c=>sel.has(c.id)),...ativos.filter(c=>sel.has(c.id)&&!visiveis.includes(c))];
  const mudar=(ids:string[],pt:Partial<Clip>)=>{ const s=new Set(ids); setProjeto(p=>({...p,clips:p.clips.map(c=>s.has(c.id)?{...c,...pt}:c)})); };
  const renderizar=async(c:Clip,onPct:(p:number)=>void)=>{ const {blob,ext}=await renderClip(projeto.url,c,projeto.cues,captionPresets,template,onPct); return {blob,nome:nomeArquivo(c,escolhidos.indexOf(c),ext)}; };
  const temResultado=job.status==='pronto'&&projeto.clips.length>0;
  // Quando os cortes ficam prontos, o passo 3 abre sozinho; ao escolher um vídeo novo o passo 2 abre.
  useEffect(()=>{ if(temResultado) setAberto('cortes'); },[temResultado]);
  useEffect(()=>{ if(!projeto.file) setAberto(a=>a==='cortes'?'opcoes':a); },[projeto.file]);
  const passo=!temResultado?1:etapa==='edicao'?3:etapa==='postar'?4:2;
  const irPasso=temResultado?(n:number)=>{ if(n===2) setEtapa('cortes'); else if(escolhidos.length){ setEtapa(n===3?'edicao':'postar'); } else toast('Escolha pelo menos um corte primeiro.','erro'); }:undefined;

  // Opções: aparecem antes de enviar o vídeo, para os cortes já saírem do jeito certo.
  const opcoes=<>
    <div className="field"><span className="field-label">O que fazer com o vídeo</span><div className="seg big">
     <button className={!inteiro?'on':''} onClick={()=>setInteiro(false)}><strong>Fazer cortes</strong><small>Vídeo longo: o site acha os melhores trechos</small></button>
     <button className={inteiro?'on':''} onClick={()=>setInteiro(true)}><strong>Usar o vídeo inteiro</strong><small>Já é curto (Shorts): só template e legenda</small></button></div></div>
    {!inteiro&&<>
    {marcas.length>0&&!lidos.janelas.length&&<label className="check big marks-check"><input type="checkbox" checked={usarMarcas} onChange={e=>setUsarMarcas(e.target.checked)}/> Usar os {marcas.length} trechos que marquei no link ({marcas.map(m=>`${tm(m.inicio)}–${tm(m.fim)}`).join(', ')}). Desmarque para o site procurar os melhores trechos sozinho.</label>}
    <div className="field tempos-field"><span className="field-label"><Clock size={15}/> Tempos exatos dos cortes (opcional)</span>
     <textarea rows={4} value={tempos} onChange={e=>setTempos(e.target.value)} placeholder={'Cole um corte por linha, assim:\n0:30 - 1:10\n12:05 a 12:50 Melhor jogada\n1:02:00 - 1:03:15'} aria-label="Tempos dos cortes"/>
     {tempos.trim()?<small className={lidos.erros.length?'bad':'ok-txt'}>{lidos.janelas.length?`${lidos.janelas.length} corte(s) entendido(s): ${lidos.janelas.slice(0,6).map(j=>`${tm(j.inicio)}–${tm(j.fim)} (${Math.round(j.fim-j.inicio)} s)`).join(', ')}${lidos.janelas.length>6?'...':''}. O site corta exatamente nesses tempos.`:'Nenhum tempo entendido ainda.'}{lidos.erros.length>0&&` Não entendi: "${lidos.erros.slice(0,3).join('", "')}". Use o formato 0:30 - 1:10.`}</small>
     :<small>Deixe vazio para o site achar os melhores momentos sozinho, com a duração escolhida abaixo.</small>}
    </div>
    <div className="form-grid">
     <div className="field"><span className="field-label">Tipo de vídeo <HelpButton topic="modelo"/></span><div className="seg big">
      <button className={modelo==='falas'?'on':''} onClick={()=>setModelo('falas')}><strong>Falas</strong><small>Podcast, entrevista, aula</small></button>
      <button className={modelo==='acao'?'on':''} onClick={()=>setModelo('acao')}><strong>Gameplay / ação</strong><small>Jogos, esportes, pouca fala</small></button></div></div>
     <div className={'field '+(lidos.janelas.length?'off':'')}><span className="field-label">Duração de cada corte {lidos.janelas.length>0&&<span className="tag">usando os tempos colados</span>}</span><div className="seg">{DURACOES.map(([l,a,b])=><button key={l} className={!custom&&faixa[0]===a&&faixa[1]===b?'on':''} onClick={()=>{setCustom(false);setFaixa([a,b])}}>{l}</button>)}<button className={custom?'on':''} onClick={()=>setCustom(true)}>Personalizada</button></div>
      {custom&&<div className="small-grid mt"><label>Mínimo (s)<input type="number" min={5} max={600} value={faixa[0]} onChange={e=>{const v=Math.max(5,+e.target.value);setFaixa([v,Math.max(v,faixa[1])])}}/></label><label>Máximo (s)<input type="number" min={5} max={600} value={faixa[1]} onChange={e=>setFaixa([faixa[0],Math.max(faixa[0],+e.target.value)])}/></label></div>}</div>
     <div className="field"><span className="field-label">Legenda <HelpButton topic="whisper"/></span><div className="seg">
      <button className={legSrc==='depois'?'on':''} onClick={()=>setLegSrc('depois')}>Depois, só nos escolhidos</button><button className={legSrc==='auto'?'on':''} onClick={()=>setLegSrc('auto')}>Agora, no vídeo todo</button>{settings.geminiKey&&<button className={legSrc==='gemini'?'on':''} onClick={()=>setLegSrc('gemini')}>Pelo Gemini</button>}<button className={legSrc==='arquivo'?'on':''} onClick={()=>setLegSrc('arquivo')}>Tenho um .srt/.vtt</button><button className={legSrc==='nenhuma'?'on':''} onClick={()=>setLegSrc('nenhuma')}>Sem legenda</button></div>
      {(legSrc==='auto'||legSrc==='gemini')&&<label className="mt">Idioma da fala<select value={idioma} onChange={e=>setIdioma(e.target.value)}>{IDIOMAS.map(i=><option key={i.id} value={i.id}>{i.nome}</option>)}</select></label>}
      {legSrc==='depois'&&<small className="hint">Mais rápido: os cortes saem sem esperar a legenda. Você gera a legenda na etapa de Edição, só dos cortes que escolher.</small>}
      {legSrc==='auto'&&<small className="hint">Roda no seu aparelho e pode demorar em vídeos longos.{settings.geminiKey?' Se falhar, o site tenta pelo Gemini sozinho.':' Se der erro no celular, configure a chave do Gemini para ter outra opção.'}</small>}
      {legSrc==='gemini'&&<small className="hint">Usa sua chave do Google. Mais rápido no celular; o áudio é enviado ao Gemini.</small>}
      {legSrc==='arquivo'&&<label className="mt"><span className="label-row">Arquivo de legenda <HelpButton topic="srt"/></span><input type="file" accept=".srt,.vtt" onChange={e=>setSrtFile(e.target.files?.[0]||null)}/></label>}
     </div>
     <div className={'field '+(lidos.janelas.length?'off':'')}><span className="field-label">Quantidade e qualidade <HelpButton topic="nota"/></span><div className="small-grid">
      <label>Quantidade de cortes<select value={limite} onChange={e=>setLimite(+e.target.value)}>{[3,5,10,15,20,30].map(n=><option key={n} value={n}>{n}</option>)}</select></label>
      <label>Pontuação mínima (0–99)<input type="number" min={0} max={99} step={5} value={minimo} onChange={e=>setMinimo(Math.min(99,Math.max(0,+e.target.value)))}/></label></div></div>
     <details className="field more"><summary>Mais opções: trecho do vídeo, gênero e momentos específicos</summary>
      <div className="small-grid mt"><label>Começar em (min:seg)<input placeholder="0:00" value={trechoIni} onChange={e=>setTrechoIni(e.target.value)}/></label><label>Terminar em (min:seg)<input placeholder={projeto.duracao?tm(projeto.duracao):'fim'} value={trechoFim} onChange={e=>setTrechoFim(e.target.value)}/></label></div>
      <label className="mt">Gênero ou tema do vídeo<input placeholder="Ex.: GTA RP, podcast de finanças" value={tema} onChange={e=>setTema(e.target.value)}/></label>
      <label className="mt"><span className="label-row">Incluir momentos específicos {!temIA&&<span className="tag">precisa de uma chave de IA</span>}</span><input disabled={!temIA} placeholder={temIA?'Ex.: ache onde ele fala de preço; perseguições policiais':'Configure uma chave de IA para usar'} value={prompt} onChange={e=>setPrompt(e.target.value)}/></label>
     </details>
    </div>
    </>}
  </>;

  // ---------- Acordeão: 1 opções → 2 vídeo → 3 cortes (edição e postagem abrem em tela própria) ----------
  const resumoOpcoes=inteiro?'Usar o vídeo inteiro (já é curto)':[lidos.janelas.length?`${lidos.janelas.length} tempo(s) colado(s)`:`${faixa[0]} a ${faixa[1]} s por corte`,modelo==='falas'?'Falas':'Gameplay/ação',lidos.janelas.length?'':`até ${limite} cortes`].filter(Boolean).join(' • ');
  const tocar=(k:'opcoes'|'video'|'cortes')=>setAberto(a=>a===k?a:k);
  return <>
   <Stepper atual={passo} onIr={irPasso}/>
   {etapa==='edicao'&&temResultado?<>
   <EdicaoLote clips={escolhidos} mudar={mudar} gerarLegendas={gerarLegendas} dublar={dublar} onEditar={setEditando} onVoltar={()=>setEtapa('cortes')} onProximo={ids=>{ setPostarIds(ids); setEtapa('postar'); }} onZip={exportarZip} exportando={!!exp}/>
   </>:etapa==='postar'&&temResultado?<>
   <PostarLote clips={postarIds?escolhidos.filter(c=>postarIds.includes(c.id)):escolhidos} tema={projeto.tema} gerar={renderizar} onVoltar={()=>setEtapa('edicao')}/>
   </>:<div className="acordeao">
    <Passo n={1} id="opcoes" titulo="Como você quer os cortes?" resumo={resumoOpcoes} aberto={aberto==='opcoes'} feito={!!projeto.file||temResultado} manter onToggle={()=>tocar('opcoes')}>
     {opcoes}
     <label className="check big auto-check"><input type="checkbox" checked={direitos} onChange={e=>setDireitos(e.target.checked)}/> <span>Declaro que tenho direito de usar e publicar os vídeos que envio (meus ou com autorização).</span></label>
     <div className="passo-acao"><button className="primary lg" disabled={!direitos} onClick={()=>setAberto('video')}>Continuar: enviar o vídeo <ArrowRight size={17}/></button>{!direitos&&<small className="hint">Marque a declaração acima para continuar.</small>}</div>
    </Passo>

    <Passo n={2} id="video" titulo={projeto.file?'Vídeo':'Envie o vídeo'} resumo={projeto.file?`${projeto.nome}${projeto.duracao?' • '+tm(projeto.duracao):''}`:'Link do YouTube ou arquivo'} aberto={aberto==='video'} feito={!!projeto.file&&job.status!=='rodando'} manter onToggle={()=>tocar('video')}>
     {!projeto.file?<>
      <LinkStudio onUpload={()=>fileInput.current?.click()} onArquivo={f=>escolherArquivo(f,true)} direitos={direitos} opcoes={{min:faixa[0],max:faixa[1],limite,tema,pedido:prompt,acao:modelo==='acao'}}/>
   <section className={'panel dropzone '+(drag?'drag':'')} onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);escolherArquivo(e.dataTransfer.files?.[0]||null)}} onClick={()=>fileInput.current?.click()} role="button" tabIndex={0}>
    <span className="drop-icon"><Upload size={30}/></span>
    <h2>{lendo?<><Loader2 size={18} className="spin"/> Preparando o vídeo...</>:marcas.length?`Envie o arquivo deste vídeo para cortar os ${marcas.length} trechos marcados`:'Arraste o vídeo aqui ou clique para escolher'}</h2>
    <p>MP4, MOV ou WEBM. O site analisa o áudio e as falas, dá nota a cada trecho e entrega os melhores cortes com legenda. O arquivo não sai do seu computador.</p>
    <input ref={fileInput} type="file" accept="video/*,.mkv,.mov" hidden onChange={e=>escolherArquivo(e.target.files?.[0]||null)}/>
   </section>
   <p className="hint center">Ainda sem vídeo? Ache inspiração no <button className="link-btn inline" onClick={()=>go('radar')}>Radar</button>.</p>     </>:<>
   <section className="panel file-bar"><Film size={20}/><div className="grow"><strong>{projeto.nome}</strong><small>{projeto.duracao?`${tm(projeto.duracao)} de vídeo`:'Lendo...'}{projeto.cuesFonte&&` • ${projeto.cues.length} falas na legenda`}</small></div><button className="subtle" disabled={rodando||!!exp} onClick={()=>{ if(projeto.url) URL.revokeObjectURL(projeto.url); cache={file:null,audio:null,energy:null}; setProjeto(()=>PROJETO_VAZIO); setE('cortes'); setSel(new Set()); setAberto('video'); }}>Trocar vídeo</button></section>
   {legErro&&temResultado&&<div className="note-bar"><AlertTriangle size={16}/><span><b>Legenda:</b> {legErro}</span><button className="subtle sm" onClick={()=>setLegErro('')}>Ok</button></div>}
      {!temResultado?<>
       <button id="btn-gerar" className="primary lg full" disabled={!direitos||rodando||!projeto.duracao} onClick={()=>gerar()}>{rodando?<Loader2 size={18} className="spin"/>:<Sparkles size={18}/>} {rodando?(inteiro?'Preparando...':'Gerando cortes...'):(inteiro?'Usar o vídeo inteiro':'Gerar cortes')}</button>
       {!direitos&&<p className="hint center">Falta marcar a declaração de direitos no passo 1. <button className="link-btn inline" onClick={()=>setAberto('opcoes')}>Abrir o passo 1</button></p>}
       {!temIA&&<p className="hint center">Notas automáticas pelo áudio e pelas frases. Para notas e títulos feitos por IA, <button className="link-btn inline" onClick={()=>go('config')}>configure a chave do Gemini (grátis) ou da Claude</button>.</p>}
       {job.status!=='idle'&&<JobView job={job}/>}
      </>:<p className="hint">Os cortes já foram gerados e estão no passo 3. Para gerar de novo com outras opções, use "Alterar opções e refazer" lá.</p>}
     </>}
    </Passo>

    <Passo n={3} id="cortes" titulo="Cortes" resumo={temResultado?`${topo.length} cortes de ${projeto.candidatos} trechos analisados`:'Aparecem aqui depois de gerar'} aberto={aberto==='cortes'&&temResultado} desabilitado={!temResultado} feito={temResultado} onToggle={()=>tocar('cortes')}>
    <section className="panel results-bar">
     <div className="result-summary"><strong>{topo.length} cortes</strong> de {projeto.candidatos} trechos analisados • {aprovados.length} acima da pontuação mínima ({minimo}/99) {projeto.clips.some(c=>c.fonte==='ia')?<span className="tag ai"><Sparkles size={12}/> pontuação da IA</span>:<span className="tag">pontuação automática</span>}</div>
     <div className="result-controls">
      <label className="inline">Pontuação mínima<input type="number" min={0} max={99} step={5} value={minimo} onChange={e=>setMinimo(Math.min(99,Math.max(0,+e.target.value)))}/></label>
      <label className="inline">Máximo<select value={limite} onChange={e=>setLimite(+e.target.value)}>{[3,5,10,15,20,30].map(n=><option key={n}>{n}</option>)}</select></label>
      <label className="inline">Ordenar<select value={ordem} onChange={e=>setOrdem(e.target.value as 'nota'|'tempo')}><option value="nota">Maior pontuação</option><option value="tempo">Ordem no vídeo</option></select></label>
      <button className="subtle" onClick={()=>setMostrarTodos(!mostrarTodos)}>{mostrarTodos?`Só os ${limite} melhores`:'Mostrar todos'}</button>
      <button className="subtle" onClick={()=>{ setProjeto(p=>({...p,clips:[],job:{status:'idle',etapa:'',pct:0,etapas:[]}})); setAberto('opcoes'); }}>Alterar opções e refazer</button>
     </div>
     {temIA&&<div className="redo"><Wand2 size={16}/><input placeholder="Refazer com outro pedido, ex.: momentos engraçados" value={novoPrompt} onChange={e=>setNovoPrompt(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')refazer()}}/><button className="subtle" disabled={!novoPrompt.trim()||rodando} onClick={refazer}>{rodando?<Loader2 size={15} className="spin"/>:null} Refazer com IA</button></div>}
     {rodando&&<JobView job={job}/>}
    </section>

    <div className="bulk-bar">
     <label className="check"><input type="checkbox" checked={visiveis.length>0&&visiveis.every(c=>sel.has(c.id))} onChange={e=>setSel(e.target.checked?new Set(visiveis.map(c=>c.id)):new Set())}/> Selecionar todos</label>
     <span>{sel.size} selecionado(s)</span>
     <button className="subtle" disabled={!sel.size||!!exp||!!lote?.rodando||!recSupport} onClick={()=>exportarZip()} title={!recSupport?'Este navegador não grava vídeo':!sel.size?'Marque pelo menos um corte':'Grava cada corte no seu navegador e junta num ZIP'}><Package size={16}/> Exportar selecionados (ZIP)</button>
     <HelpButton topic="exportar"/>
     <button className="primary next-btn" disabled={!sel.size} onClick={()=>setEtapa('edicao')}>Próximo: editar {sel.size||''} corte(s) <ArrowRight size={16}/></button>
    </div>
    {lote&&<section className="panel lote-exp">
     <div className="section-head"><h2><Package size={17}/> Exportação em lote</h2><span className="hint">roda no seu navegador, deixe esta aba aberta{lote.rodando?'':` • ${lote.itens.filter(i=>i.status==='ok').length} de ${lote.itens.length} prontos`}</span>{!lote.rodando&&<button className="icon-btn" onClick={()=>setLote(null)} aria-label="Fechar exportação"><X size={15}/></button>}</div>
     <ul className="lote-lista">{lote.itens.map(i=><li key={i.id} className={i.status}><span className="lote-tit">{i.titulo}</span><div className="progress"><div style={{width:(i.status==='ok'?100:i.pct)+'%'}}/></div><small>{i.status==='fila'?'na fila':i.status==='gravando'?`gravando ${i.pct}%`:i.status==='ok'?'pronto':`falhou: ${i.erro}`}</small></li>)}</ul>
     {!lote.rodando&&<div className="row-gap left mt">
      <button className="primary" disabled={!lote.itens.some(i=>i.status==='ok')} onClick={baixarLote}><Download size={15}/> Baixar ZIP com os {lote.itens.filter(i=>i.status==='ok').length} prontos</button>
      {lote.itens.some(i=>i.status==='erro')&&<button className="subtle" onClick={()=>exportarZip(true)}><RotateCcw size={15}/> Repetir só os {lote.itens.filter(i=>i.status==='erro').length} que falharam</button>}
     </div>}
    </section>}
    {comparar&&(()=>{ const par=comparar.map(id=>ativos.find(c=>c.id===id)).filter((c):c is Clip=>!!c); if(par.length<2) return null;
     return <section className="panel comparar">
      <div className="section-head"><h2><GitCompare size={17}/> Comparar trechos sobrepostos</h2><button className="icon-btn" onClick={()=>setComparar(null)} aria-label="Fechar comparação"><X size={15}/></button></div>
      <div className="comparar-grid">{par.map((c,i)=><div key={c.id} className="comparar-lado">
       <video src={`${urlDe(c,projeto.url)}#t=${c.inicio.toFixed(2)},${c.fim.toFixed(2)}`} controls preload="metadata" playsInline/>
       <b>{c.titulo}</b><small>{tm(c.inicio)}–{tm(c.fim)} • {Math.round(c.fim-c.inicio)} s • pontuação {c.nota_final}/99</small>
       <small>gancho {c.notas.gancho} • fluxo {c.notas.fluxo} • valor {c.notas.valor} • tendência {c.notas.tendencia}</small>
       {trecho(c)&&<p className="trecho">“{trecho(c)}”</p>}
       <button className="primary sm" onClick={()=>{ const outro=par[1-i]; const s2=new Set(sel); s2.add(c.id); s2.delete(outro.id); setSel(s2); setComparar(null); toast(`Ficou "${c.titulo}". O outro continua na lista, só saiu da seleção.`,'ok'); }}>Ficar com este</button>
      </div>)}</div>
     </section>; })()}
    {!sel.size&&visiveis.length>0&&<p className="hint">Marque os cortes que você quer usar (ou clique em Selecionar todos) e depois em <b>Próximo</b>.</p>}
    {exp&&<div className="export-bar"><Loader2 size={16} className="spin"/><span>{exp.fila?`Exportando ${exp.fila}`:'Exportando corte'} • {exp.pct}% — mantenha esta aba aberta e visível</span><div className="progress"><div style={{width:exp.pct+'%'}}/></div></div>}

    {visiveis.length===0?<div className="empty"><Sparkles size={30}/><strong>Nenhum corte para mostrar</strong><p>Clique em “Mostrar todos” ou em “Alterar opções e refazer”.</p></div>
    :<div className="clip-grid">{visiveis.map(c=><article key={c.id} className={'clip-card '+(sel.has(c.id)?'selected':'')+(c.nota_final<=minimo?' below':'')}>
      <div className="clip-thumb" onClick={()=>setPrevia(previa===c.id?'':c.id)} title="Prévia rápida do trecho">{previa===c.id?<video className="previa-rapida" src={`${urlDe(c,projeto.url)}#t=${c.inicio.toFixed(2)},${c.fim.toFixed(2)}`} autoPlay playsInline onTimeUpdate={e=>{ const v=e.currentTarget; if(v.currentTime>=c.fim){ v.pause(); setPrevia(''); } }} onClick={e=>{ e.stopPropagation(); setPrevia(''); }}/>:c.thumb?<img src={c.thumb} alt=""/>:<Film size={28}/>}{previa!==c.id&&<span className="play"><Play size={18}/></span>}<span className="dur">{tm(c.inicio)}–{tm(c.fim)} • {Math.round(c.fim-c.inicio)} s</span>
       <label className="sel" onClick={e=>e.stopPropagation()}><input type="checkbox" checked={sel.has(c.id)} onChange={e=>{const s=new Set(sel); e.target.checked?s.add(c.id):s.delete(c.id); setSel(s);}}/></label></div>
      <div className="clip-body">
       <div className="score-row"><div className={'score big '+faixaNota(c.nota_final).id} title="Pontuação de viralidade, de 0 a 99"><strong>{c.nota_final}</strong><small>/99</small><em>{faixaNota(c.nota_final).nome}</em></div><div className="sub-scores">{(['gancho','fluxo','valor','tendencia'] as const).map(k=><span key={k} title={`${k}: ${c.notas[k]}/99`}><i style={{width:c.notas[k]+'%'}}/>{k==='tendencia'?'tendência':k} {c.notas[k]}</span>)}</div></div>
       <input className="title-input" value={c.titulo} onChange={e=>atualizar({...c,titulo:e.target.value})} aria-label="Título"/>
       <p className="motivo">{c.motivo} <small>Nota {c.nota_final}/99{c.versao_de?' • variação de outro corte':''}</small></p>
       {trecho(c)&&<p className="trecho">“{trecho(c)}”</p>}
       <details className="porque"><summary>Por que esta pontuação</summary>
        <table><tbody>{([['gancho','Gancho (a abertura prende)',35],['fluxo','Fluxo (anda bem e fecha a ideia)',25],['valor','Valor (ensina, diverte ou emociona)',25],['tendencia','Tendência (assunto em alta)',15]] as const).map(([k,n,p])=><tr key={k}><td>{n}</td><td>{c.notas[k]}</td><td>× {p}%</td><td>= {(c.notas[k]*p/100).toFixed(1)}</td></tr>)}
         <tr className="tot"><td>Pontuação de viralidade</td><td colSpan={3}>{c.nota_final}/99 ({faixaNota(c.nota_final).nome.toLowerCase()})</td></tr></tbody></table>
        <small>{c.fonte==='ia'?`Notas dadas pela IA (${nomeIA(iaAtiva(settings))||'IA'}), lendo a transcrição.`:'Notas automáticas, calculadas no seu navegador pelo volume da fala e pelas frases da legenda. Com uma chave de IA elas ficam mais precisas.'}</small>
       </details>
       {sobrepostos(c).length>0&&<p className="sobrepoe">Pega o mesmo trecho que {sobrepostos(c).slice(0,2).map(x=><button key={x.id} className="link-btn inline" onClick={()=>{ setComparar([c.id,x.id]); setTimeout(()=>document.querySelector('.comparar')?.scrollIntoView({behavior:'smooth',block:'center'}),80); }}>{x.titulo} ({tm(x.inicio)}–{tm(x.fim)})</button>)} <small>toque para comparar</small></p>}
       {exp?.id===c.id&&<div className="progress"><div style={{width:exp.pct+'%'}}/></div>}
       <div className="clip-actions">
        <button className="primary sm" onClick={()=>setEditando(c)}><Pencil size={14}/> Editar e ver</button>
        <button className="subtle sm" disabled={!!exp||!recSupport} onClick={()=>exportar(c)}>{exp?.id===c.id?<><Loader2 size={14} className="spin"/> {exp.pct}%</>:<><Download size={14}/> Baixar</>}</button>
        <button className="subtle sm" disabled={!!exp||!recSupport} title="Agendar nas redes" onClick={()=>setAgendando(c)}><CalendarClock size={14}/> Agendar</button>
        <button className="icon-btn" title="Duplicar como variação (para testar outro gancho, enquadramento ou legenda)" aria-label="Duplicar como variação" onClick={()=>duplicar(c)}><Copy size={15}/></button>
        <button className="icon-btn" title="Descartar" onClick={()=>atualizar({...c,descartado:true})}><Trash2 size={15}/></button>
       </div>
      </div>
     </article>)}</div>}
    {descartados.length>0&&<details className="discarded"><summary>{descartados.length} descartado(s)</summary>{descartados.map(c=><div key={c.id} className="discard-row"><span>{c.titulo} ({tm(c.inicio)}–{tm(c.fim)})</span><button className="link-btn" onClick={()=>atualizar({...c,descartado:false})}><Undo2 size={13}/> Restaurar</button></div>)}</details>}
    {!recSupport&&<p className="hint center"><AlertTriangle size={13}/> Este navegador não grava vídeo. Use Chrome, Edge ou Safari atualizados para exportar.</p>}

    </Passo>
   </div>}
   {exp&&etapa==='edicao'&&temResultado&&<div className="export-bar"><Loader2 size={16} className="spin"/><span>{exp.fila?`Exportando ${exp.fila}`:'Exportando corte'} • {exp.pct}% — mantenha esta aba aberta e visível</span><div className="progress"><div style={{width:exp.pct+'%'}}/></div></div>}
   {agendando&&<AgendarPost titulo={agendando.titulo} legenda={legendaAutomatica(agendando,projeto.cues,projeto.tema)} gerar={async onPct=>{ const {blob,ext}=await renderClip(projeto.url,agendando,projeto.cues,captionPresets,template,onPct); return {blob,nome:nomeArquivo(agendando,visiveis.indexOf(agendando),ext)}; }} onClose={()=>setAgendando(null)}/>}
   {editando&&<Editor clip={editando} onClose={()=>setEditando(null)}
     onSave={(c,cues)=>{ if(c.video) atualizar({...c,video:{...c.video,cues}}); else { atualizar(c); setProjeto(p=>({...p,cues})); } setEditando(null); toast('Alterações salvas.','ok'); }}
     onDuplicate={c=>{ const n=duplicar(c); setEditando(n); }}
     onExport={c=>{ setEditando(null); exportar(c); }}/>}
  </>;
}

/** Um passo do acordeão: só um fica aberto. "manter" deixa o conteúdo montado (com download ou player em andamento) mesmo fechado. */
function Passo({n,id,titulo,resumo,aberto,feito,desabilitado,manter,onToggle,children}:{n:number;id:string;titulo:string;resumo:string;aberto:boolean;feito?:boolean;desabilitado?:boolean;manter?:boolean;onToggle:()=>void;children:React.ReactNode}){
  return <section className={'passo'+(aberto?' aberto':'')+(feito?' feito':'')+(desabilitado?' off':'')} data-passo={id}>
   <button className="passo-cab" onClick={onToggle} aria-expanded={aberto} disabled={desabilitado}>
    <span className="passo-num">{feito&&!aberto?<CheckCircle2 size={16}/>:n}</span>
    <span className="passo-tit"><b>{titulo}</b>{!aberto&&resumo&&<small>{resumo}</small>}</span>
    <ChevronDown size={18} className="passo-seta"/>
   </button>
   {(aberto||manter)&&<div className="passo-corpo" hidden={!aberto}>{children}</div>}
  </section>;
}

function clamp(n:number){ return Math.max(0,Math.min(99,Math.round(n||0))); }

function Stepper({atual,onIr}:{atual:number;onIr?:(n:number)=>void}){
  const s=['Configurar e enviar','Escolher cortes','Edição','Postar'];
  return <ol className="stepper">{s.map((t,i)=><li key={t} className={(i+1<atual?'done':i+1===atual?'on':'')+(onIr&&i>0?' clicavel':'')} onClick={onIr&&i>0?()=>onIr(i+1):undefined}><span>{i+1<atual?<CheckCircle2 size={16}/>:i+1}</span>{t}</li>)}</ol>;
}

function JobView({job}:{job:Job}){
  // Marca quando a etapa atual começou, para estimar o tempo que falta.
  const ini=useRef<{etapa:string;t:number;txt:string}>({etapa:'',t:0,txt:''});
  const [,tick]=useState(0);
  useEffect(()=>{ const t=setInterval(()=>tick(x=>x+1),1000); return ()=>clearInterval(t); },[]);
  if(job.status==='erro') return <div className="job-status err"><AlertTriangle size={17}/><span>{job.erro}</span></div>;
  const idx=Math.max(0,job.etapas.indexOf(job.etapa));
  const pct=Math.max(0,Math.min(100,job.pct||0));
  const chave=job.etapa+'|'+(job.erro||'');
  if(ini.current.etapa!==chave){ ini.current={etapa:chave,t:Date.now(),txt:job.erro||''}; }
  const passou=(Date.now()-ini.current.t)/1000;
  const falta=pct>=3&&pct<100&&passou>5?passou*(100-pct)/pct:0;
  const geral=job.status==='pronto'?100:Math.round((idx+pct/100)/Math.max(1,job.etapas.length)*100);
  const fmtS=(x:number)=>x>=60?`${Math.floor(x/60)} min ${Math.round(x%60)} s`:`${Math.round(x)} s`;
  return <div className="job-status">
   {job.status==='rodando'&&<div className="geral"><div className="geral-row"><b>Progresso geral</b><b>{geral}%</b></div><div className="progress"><div style={{width:geral+'%'}}/></div></div>}
   <ul className="stages">{job.etapas.map((e,i)=><li key={e} className={job.status==='pronto'||i<idx?'done':i===idx?'on':''}>{job.status==='pronto'||i<idx?<CheckCircle2 size={15}/>:i===idx?<Loader2 size={15} className="spin"/>:<Circle size={15}/>}<span>{e}{i===idx&&job.status==='rodando'&&<small> — {job.erro?job.erro+' ':''}<b className="pct">{pct}%</b>{falta>0&&` • faltam uns ${fmtS(falta)}`}</small>}</span></li>)}</ul>
   {job.status==='rodando'&&pct>0&&<div className="progress etapa"><div style={{width:pct+'%'}}/></div>}
   {job.etapa==='Preparando a legenda'&&<p className="hint"><FileText size={13}/> A transcrição roda no seu aparelho (ou no Gemini). Pode levar alguns minutos em vídeos longos.</p>}</div>;
}

