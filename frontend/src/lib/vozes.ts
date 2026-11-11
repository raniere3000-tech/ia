// Estúdio de vozes: elenco de personagens, roteiro (falas), takes gerados pelo Gemini TTS
// e montagem do episódio. Tudo fica guardado no próprio navegador (IndexedDB), inclusive os WAVs.
import { chamar, ErroGemini } from './gemini';
import { pcmParaFloat } from './dublagem';
import { uid } from './store';

export const MODELOS_TTS:[string,string][] = [['gemini-2.5-flash-preview-tts','Flash (rápido e mais barato)'],['gemini-2.5-pro-preview-tts','Pro (mais expressivo)']];
/** Vozes prontas do Gemini TTS e o estilo descrito pelo Google. */
export const VOZES_TTS:[string,string][] = [
  ['Charon','informativa'],['Orus','firme'],['Fenrir','empolgada'],['Puck','animada'],['Enceladus','sussurrada'],['Iapetus','clara'],['Algenib','rouca'],['Gacrux','madura'],
  ['Alnilam','firme'],['Rasalgethi','informativa'],['Sadaltager','conhecedora'],['Schedar','equilibrada'],['Umbriel','tranquila'],['Algieba','suave'],['Achird','amigável'],['Zubenelgenubi','casual'],
  ['Sadachbia','viva'],['Kore','firme'],['Aoede','leve'],['Leda','jovem'],['Zephyr','brilhante'],['Autonoe','brilhante'],['Callirrhoe','tranquila'],['Despina','suave'],
  ['Erinome','clara'],['Laomedeia','animada'],['Achernar','macia'],['Pulcherrima','direta'],['Vindemiatrix','gentil'],['Sulafat','calorosa'],
];
export const ehVoz = (v:string)=>VOZES_TTS.some(([n])=>n===v);

export type Projeto = {id:string;nome:string;criado:number};
export type Personagem = {id:string;projetoId:string;nome:string;voz:string;modelo:string;genero:string;gravidade:number;ritmo:number;energia:number;emocao:string;sotaque:string;descricao:string;aprovada:boolean;criado:number};
export type Fala = {id:string;projetoId:string;ordem:number;cena:string;nomeRoteiro:string;personagemId:string;texto:string;direcao:string;pausa:number;tipo:'fala'|'acao'};
export type Take = {id:string;projetoId:string;falaId:string;personagemId:string;texto:string;direcao:string;pedido:string;voz:string;modelo:string;ajustes:string;data:number;duracao:number;wav:Blob;aprovado:boolean;nota:string};
export type Loja = 'projetos'|'personagens'|'falas'|'takes';

export const EMOCOES = ['neutra','alegre','irônica','séria','sombria','misteriosa','épica','triste','irritada','assustada','sarcástica','calorosa','solene','empolgada'];
const ESCALA:Record<string,string[]> = {
  gravidade:['muito aguda','aguda','média','grave','muito grave e encorpada'],
  ritmo:['muito lento, com pausas longas','lento e pausado','moderado','rápido','muito rápido'],
  energia:['contida, quase sussurrada','calma','natural','intensa','explosiva, gritando'],
};
export const rotulo=(k:'gravidade'|'ritmo'|'energia',n:number)=>ESCALA[k][Math.max(1,Math.min(5,n))-1];

export function novoPersonagem(projetoId:string,nome:string):Personagem{
  return {id:uid(),projetoId,nome,voz:'Charon',modelo:MODELOS_TTS[0][0],genero:'',gravidade:3,ritmo:3,energia:3,emocao:'neutra',sotaque:'brasileiro neutro',descricao:'',aprovada:false,criado:Date.now()};
}

/** Descrição de voz que vai para o Gemini, montada com os ajustes da ficha. */
export function descreverVoz(p:Personagem){
  return [
    `Personagem: ${p.nome}.`,
    p.genero.trim()?`Perfil: ${p.genero.trim()}.`:'',
    `Voz ${rotulo('gravidade',p.gravidade)}, ritmo ${rotulo('ritmo',p.ritmo)}, energia ${rotulo('energia',p.energia)}.`,
    p.emocao&&p.emocao!=='neutra'?`Emoção de base: ${p.emocao}.`:'',
    p.sotaque.trim()?`Sotaque: ${p.sotaque.trim()}.`:'',
    p.descricao.trim(),
  ].filter(Boolean).join(' ');
}

// ---------------- Armazenamento (IndexedDB) ----------------
const DB='estudio_vozes', V=1;
const LOJAS:Loja[]=['projetos','personagens','falas','takes'];
let dbp:Promise<IDBDatabase>|null=null;
function db(){
  if(!dbp) dbp=new Promise((res,rej)=>{
    const r=indexedDB.open(DB,V);
    r.onupgradeneeded=()=>{ const d=r.result; for(const s of LOJAS) if(!d.objectStoreNames.contains(s)) d.createObjectStore(s,{keyPath:'id'}); };
    r.onsuccess=()=>res(r.result); r.onerror=()=>rej(new Error('O navegador não deixou guardar os dados do estúdio (modo anônimo?).'));
  });
  return dbp;
}
async function tx<T>(store:string,modo:IDBTransactionMode,f:(s:IDBObjectStore)=>IDBRequest|void):Promise<T>{
  const d=await db();
  return new Promise((res,rej)=>{ const t=d.transaction(store,modo); const r=f(t.objectStore(store)); t.oncomplete=()=>res((r as IDBRequest)?.result); t.onerror=()=>rej(t.error); });
}
export const listar=<T>(store:Loja)=>tx<T[]>(store,'readonly',s=>s.getAll());
export const salvar=<T extends {id:string}>(store:Loja,v:T)=>tx<void>(store,'readwrite',s=>{ s.put(v); });
export const salvarVarios=<T extends {id:string}>(store:Loja,vs:T[])=>tx<void>(store,'readwrite',s=>{ vs.forEach(v=>s.put(v)); });
export const apagar=(store:Loja,id:string)=>tx<void>(store,'readwrite',s=>{ s.delete(id); });
export const limpar=(store:Loja)=>tx<void>(store,'readwrite',s=>{ s.clear(); });

// ---------------- Importação do roteiro ----------------
export type LinhaRoteiro = {cena:string;nome:string;texto:string;direcao:string;tipo:'fala'|'acao'};

/**
 * Lê um roteiro colado ou um arquivo .md/.txt. Aceita falas como:
 *   NOME: texto      **NOME:** “texto”      Nome (sussurrando): "texto"      - NOME: texto
 * Títulos (# ..., CENA 1, Cena 2 — ...) viram cenas. As outras linhas viram ações (não faladas).
 * O texto da fala é mantido como está; só tiramos as aspas de fora.
 */
export function lerRoteiro(txt:string):LinhaRoteiro[]{
  const linhas=txt.replace(/\r/g,'').split('\n');
  const temCena=linhas.some(l=>ehCena(l.trim()));
  const out:LinhaRoteiro[]=[]; let cena=temCena?'':'Roteiro'; let dentro=!temCena;
  for(const l0 of linhas){
    const l=l0.trim(); if(!l||/^(---|___|\*\*\*)$/.test(l)) continue;
    if(ehCena(l)){ cena=l.replace(/^#+\s*/,'').replace(/\*\*/g,'').trim(); dentro=true; continue; }
    if(/^#{1,6}\s/.test(l)){ dentro=false; continue; }
    if(!dentro) continue;
    const m=/^(?:[-*•]\s+)?\**\s*([^:*\n]{1,40}?)\s*(?:\(([^)]{1,60})\))?\s*\**\s*:\s*\**\s*(.+)$/.exec(l);
    if(m){
      const nome=m[1].trim(); let texto=m[3].trim().replace(/^\*\*\s*/,'');
      const aspas=/^[“"«](.*)[”"»]\s*$/.exec(texto);
      const maiusc=nome===nome.toUpperCase()&&/[A-ZÀ-Ú]/.test(nome);
      if(aspas||maiusc){ out.push({cena,nome:nome.toUpperCase(),texto:aspas?aspas[1]:texto,direcao:m[2]?.trim()||'',tipo:'fala'}); continue; }
    }
    out.push({cena,nome:'',texto:l.replace(/\*\*/g,''),direcao:'',tipo:'acao'});
  }
  return out;
}
function ehCena(l:string){ return /^#{1,4}\s*(cena|scene|parte|ato)\b/i.test(l)||/^\**\s*(CENA|Cena|SCENE)\s*\d+/.test(l); }

// ---------------- Geração de voz ----------------
/** Monta o pedido separando a direção (não falada) do texto que deve ser dito exatamente. */
export function pedidoTTS(p:Personagem|null,texto:string,direcao:string){
  const instr=[p?descreverVoz(p):'',direcao.trim()?`Direção desta fala: ${direcao.trim()}.`:''].filter(Boolean).join('\n');
  return `${instr?'Instruções de interpretação (não leia em voz alta):\n'+instr+'\n\n':''}Fale somente o texto entre <fala> e </fala>, exatamente como está escrito, sem ler as instruções e sem acrescentar nada.\n<fala>${texto}</fala>`;
}

export async function gerarVoz(key:string,modelo:string,voz:string,pedido:string,onEspera?:()=>void){
  const corpo={contents:[{role:'user',parts:[{text:pedido}]}],generationConfig:{responseModalities:['AUDIO'],speechConfig:{voiceConfig:{prebuiltVoiceConfig:{voiceName:voz}}}}};
  let res:any;
  for(let t=0;;t++){
    try{ res=await chamar(key,modelo+':generateContent',corpo); break; }
    catch(e){ if(e instanceof ErroGemini&&(e.status===429||e.status>=500)&&t<3){ onEspera?.(); await new Promise(r=>setTimeout(r,25000*(t+1))); continue; } throw e; }
  }
  const p=(res?.candidates?.[0]?.content?.parts||[]).find((x:any)=>x.inlineData?.data||x.inline_data?.data);
  const d=p?.inlineData||p?.inline_data;
  if(!d) throw new Error(res?.candidates?.[0]?.finishReason==='SAFETY'?'O Gemini recusou gerar esta fala.':'O Gemini não devolveu áudio. Tente de novo.');
  const m=/rate=(\d+)/.exec(d.mimeType||d.mime_type||''); const rate=m?+m[1]:24000;
  const samples=pcmParaFloat(d.data);
  return {wav:wav(samples,rate),duracao:samples.length/rate};
}

export function wav(s:Float32Array,rate:number){
  const buf=new ArrayBuffer(44+s.length*2); const v=new DataView(buf);
  const str=(o:number,t:string)=>{ for(let i=0;i<t.length;i++) v.setUint8(o+i,t.charCodeAt(i)); };
  str(0,'RIFF'); v.setUint32(4,36+s.length*2,true); str(8,'WAVE'); str(12,'fmt '); v.setUint32(16,16,true); v.setUint16(20,1,true); v.setUint16(22,1,true);
  v.setUint32(24,rate,true); v.setUint32(28,rate*2,true); v.setUint16(32,2,true); v.setUint16(34,16,true); str(36,'data'); v.setUint32(40,s.length*2,true);
  for(let i=0;i<s.length;i++){ const x=Math.max(-1,Math.min(1,s[i])); v.setInt16(44+i*2,x<0?x*0x8000:x*0x7fff,true); }
  return new Blob([buf],{type:'audio/wav'});
}
/** Lê um WAV 16 bits mono gerado aqui. */
export async function lerWav(b:Blob){
  const ab=await b.arrayBuffer(); const v=new DataView(ab); const rate=v.getUint32(24,true); const n=(ab.byteLength-44)>>1;
  const s=new Float32Array(n); for(let i=0;i<n;i++) s[i]=v.getInt16(44+i*2,true)/0x8000;
  return {samples:s,rate};
}

/** Junta os takes aprovados na ordem do roteiro, com a pausa de cada fala. Devolve o WAV e o manifesto. */
export async function montarEpisodio(falas:Fala[],takes:Take[],nomes:Record<string,string>,pausaInicial=0.3){
  const ordem=falas.filter(f=>f.tipo==='fala').sort((a,b)=>a.ordem-b.ordem);
  const partes:{f:Fala;t:Take;s:Float32Array;rate:number}[]=[];
  for(const f of ordem){ const t=takes.find(x=>x.falaId===f.id&&x.aprovado); if(!t) continue; const {samples,rate}=await lerWav(t.wav); partes.push({f,t,s:samples,rate}); }
  const rate=partes[0]?.rate||24000;
  let total=Math.round(pausaInicial*rate); for(const p of partes) total+=p.s.length+Math.round(p.f.pausa*rate);
  const out=new Float32Array(total); let off=Math.round(pausaInicial*rate);
  const manifesto:{ordem:number;cena:string;personagem:string;texto:string;inicio:number;fim:number;duracao:number;take:string;voz:string;modelo:string;arquivo:string}[]=[];
  for(const p of partes){
    out.set(p.s,off);
    manifesto.push({ordem:p.f.ordem,cena:p.f.cena,personagem:nomes[p.f.personagemId]||p.f.nomeRoteiro,texto:p.f.texto,inicio:+(off/rate).toFixed(3),fim:+((off+p.s.length)/rate).toFixed(3),duracao:+(p.s.length/rate).toFixed(3),take:p.t.id,voz:p.t.voz,modelo:p.t.modelo,arquivo:nomeTake(p.f,p.t,nomes[p.f.personagemId]||p.f.nomeRoteiro)});
    off+=p.s.length+Math.round(p.f.pausa*rate);
  }
  return {wav:wav(out,rate),manifesto,duracao:total/rate,faltando:ordem.filter(f=>!partes.some(p=>p.f.id===f.id))};
}

/** Legenda .srt do episódio montado (personagem: fala). */
export function srt(man:{personagem:string;texto:string;inicio:number;fim:number}[],comNome=true){
  const ts=(x:number)=>{ const ms=Math.round(x*1000); const h=Math.floor(ms/3600000), m=Math.floor(ms/60000)%60, s=Math.floor(ms/1000)%60; return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')},${String(ms%1000).padStart(3,'0')}`; };
  return man.map((x,i)=>`${i+1}\n${ts(x.inicio)} --> ${ts(x.fim)}\n${comNome?x.personagem+': ':''}${x.texto}\n`).join('\n');
}

export function nomeTake(f:Fala|null,t:Take,nome=''){
  const slug=(s:string)=>s.normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^a-zA-Z0-9]+/g,'-').replace(/^-|-$/g,'').toLowerCase().slice(0,30);
  return `${f?String(f.ordem+1).padStart(3,'0')+'-':''}${slug(nome||'teste')}-${slug(t.texto)}-${t.id.slice(0,5)}.wav`;
}
