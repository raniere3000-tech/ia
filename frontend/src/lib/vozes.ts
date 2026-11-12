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
/** Vozes femininas do Gemini (as demais soam masculinas). */
export const VOZES_FEMININAS=['Kore','Aoede','Leda','Zephyr','Autonoe','Callirrhoe','Despina','Erinome','Laomedeia','Achernar','Pulcherrima','Vindemiatrix','Sulafat','Gacrux'];
export type Genero='masculina'|'feminina'|'qualquer';
export const generoDaVoz=(v:string):Genero=>VOZES_FEMININAS.includes(v)?'feminina':'masculina';
const sorteio=<T,>(l:T[])=>l[Math.floor(Math.random()*l.length)];
const faixa=(a:number,b:number)=>Math.round(a+Math.random()*(b-a));
/** Sorteia uma voz nova: voz-base do gênero pedido + gravidade, ritmo, energia, emoção e intensidade. */
export function vozAleatoria(g:Genero,evitar=''):Partial<Personagem>{
  const opcoes=VOZES_TTS.map(([v])=>v).filter(v=>v!==evitar&&(g==='qualquer'||generoDaVoz(v)===g));
  const voz=sorteio(opcoes); const fem=generoDaVoz(voz)==='feminina';
  return {voz,gravidade:fem?faixa(15,60):faixa(40,92),ritmo:faixa(30,75),energia:faixa(25,85),intensidade:faixa(30,80),
    emocao:sorteio(['neutra','alegre','irônica','séria','misteriosa','calorosa','empolgada','sarcástica','solene','sombria'])};
}
export const ehVoz = (v:string)=>VOZES_TTS.some(([n])=>n===v);
/** Se o nome do personagem for o nome de uma voz do Gemini (ex.: CHARON), devolve essa voz. */
export const vozDoNome = (nome:string)=>VOZES_TTS.find(([n])=>n.toLowerCase()===nome.trim().toLowerCase())?.[0]||'';

export type Projeto = {id:string;nome:string;criado:number};
export type Personagem = {id:string;projetoId:string;nome:string;voz:string;modelo:string;genero:string;gravidade:number;ritmo:number;energia:number;emocao:string;sotaque:string;descricao:string;aprovada:boolean;criado:number;testes?:string[];intensidade?:number;pct?:boolean};
export type Fala = {id:string;projetoId:string;ordem:number;cena:string;nomeRoteiro:string;personagemId:string;texto:string;direcao:string;pausa:number;tipo:'fala'|'acao'|'som';volume?:number;sobrepor?:boolean;fonteSom?:'auto'|'site'|'ia'|'arquivo'};
export type Take = {id:string;projetoId:string;falaId:string;personagemId:string;texto:string;direcao:string;pedido:string;voz:string;modelo:string;ajustes:string;data:number;duracao:number;wav:Blob;aprovado:boolean;nota:string};
export type Loja = 'projetos'|'personagens'|'falas'|'takes';

export const EMOCOES = ['neutra','alegre','irônica','séria','sombria','misteriosa','épica','triste','irritada','assustada','sarcástica','calorosa','solene','empolgada'];
const ESCALA:Record<string,string[]> = {
  gravidade:['muito aguda','aguda','média','grave','muito grave e encorpada'],
  ritmo:['muito lento, com pausas longas','lento e pausado','moderado','rápido','muito rápido'],
  energia:['contida, quase sussurrada','calma','natural','intensa','explosiva, gritando'],
};
/** Valores da ficha vão de 0 a 100%. O rótulo em palavras ajuda a IA a entender o tom. */
export const rotulo=(k:'gravidade'|'ritmo'|'energia',n:number)=>ESCALA[k][Math.max(0,Math.min(4,Math.floor(Math.min(99,Math.max(0,n))/20)))];
const INTENS=['bem leve','leve','moderada','forte','muito forte'];
export const rotuloIntensidade=(n:number)=>INTENS[Math.max(0,Math.min(4,Math.floor(Math.min(99,Math.max(0,n))/20)))];
/** Fichas antigas usavam 1 a 5: converte para porcentagem. */
export function normalizarPersonagem(p:Personagem):Personagem{
  if(p.pct) return p.intensidade===undefined?{...p,intensidade:50}:p;
  const c=(n:number)=>n<=5?Math.round((Math.max(1,n)-1)*25):n;
  return {...p,gravidade:c(p.gravidade),ritmo:c(p.ritmo),energia:c(p.energia),intensidade:p.intensidade??50,pct:true};
}

export function novoPersonagem(projetoId:string,nome:string):Personagem{
  return {id:uid(),projetoId,nome,voz:vozDoNome(nome)||'Charon',modelo:MODELOS_TTS[0][0],genero:'',gravidade:50,ritmo:50,energia:50,intensidade:50,pct:true,emocao:'neutra',sotaque:'brasileiro neutro',descricao:'',aprovada:false,criado:Date.now()};
}

/** Descrição de voz que vai para o Gemini, montada com os ajustes da ficha. */
export function descreverVoz(p:Personagem){
  return [
    `Personagem: ${p.nome}.`,
    p.genero.trim()?`Perfil: ${p.genero.trim()}.`:'',
    `Voz ${rotulo('gravidade',p.gravidade)} (gravidade ${p.gravidade}% de 100), ritmo ${rotulo('ritmo',p.ritmo)} (${p.ritmo}%), energia ${rotulo('energia',p.energia)} (${p.energia}%).`,
    p.emocao&&p.emocao!=='neutra'?`Emoção de base: ${p.emocao}, intensidade ${rotuloIntensidade(p.intensidade??50)} (${p.intensidade??50}%).`:'',
    p.sotaque.trim()?`Sotaque: ${p.sotaque.trim()}.`:'',
    p.descricao.trim(),
  ].filter(Boolean).join(' ');
}

// ---------------- Fichas coladas (texto livre → personagens) ----------------
export type FichaLida = {nome:string;voz?:string;modelo?:string;genero?:string;intensidade?:number;gravidade?:number;ritmo?:number;energia?:number;emocao?:string;sotaque?:string;descricao?:string;testes:string[]};
const semAcento=(t:string)=>t.normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase().trim();
/** 0–100% (ou 1–5, convertido) → porcentagem da ficha. */
function escala(v:string){
  const n=parseFloat(v.replace(',','.')); if(isNaN(n)) return undefined;
  if(/%/.test(v)||n>5) return Math.max(0,Math.min(100,Math.round(n)));
  return Math.round((Math.max(1,Math.min(5,n))-1)*25);
}
/** Lê fichas de voz escritas em texto: tabela (Personagem / Voz-base / Gravidade / Ritmo / Energia / Emoção)
 *  e blocos por personagem com "Perfil —", "Descrição e direção permanente" e "Teste — “frase”". */
export function lerFichas(txt:string):FichaLida[]{
  const linhas=txt.replace(/\r/g,'').split('\n');
  const fichas:FichaLida[]=[];
  const achar=(nome:string)=>fichas.find(f=>semAcento(f.nome)===semAcento(nome));
  const geral=semAcento(txt);
  const modelo=/\bpro\b/.test(geral.split('\n').slice(0,6).join(' '))?MODELOS_TTS[1][0]:undefined;
  const sotaque=(txt.match(/(brasileiro neutro|sotaque [^.,\n]+)/i)||[])[1];
  // 1) Tabela: linhas com colunas separadas por tab, | ou 2+ espaços, com uma voz do Gemini na 2ª coluna.
  let cab:string[]|null=null;
  for(const l of linhas){
    const cols=l.split(/\t|\s*\|\s*|\s{2,}/).map(c=>c.trim()).filter(Boolean);
    if(cols.length<3) continue;
    if(cols.some(c=>/voz/i.test(c))&&cols.some(c=>/gravidade|ritmo|energia/i.test(c))){ cab=cols.map(semAcento); continue; }
    const voz=cols.map(c=>vozDoNome(c.split(/[\s(]/)[0])).find(Boolean);
    if(!voz) continue;
    const f:FichaLida={nome:cols[0],voz,testes:[]};
    const col=(k:string)=>{ if(!cab) return undefined; const i=cab.findIndex(c=>c.includes(k)); return i>=0?cols[i]:undefined; };
    const pct=cols.filter(c=>/^\d+([.,]\d+)?\s*%?$/.test(c));
    f.gravidade=escala(col('gravidade')??pct[0]??''); f.ritmo=escala(col('ritmo')??pct[1]??''); f.energia=escala(col('energia')??pct[2]??'');
    const it=col('intens'); if(it) f.intensidade=escala(it);
    const em=col('emoc')??cols.filter(c=>!/^\d/.test(c)).slice(-1)[0]; if(em&&!/^\d/.test(em)&&!vozDoNome(em)) f.emocao=em.toLowerCase();
    if(!achar(f.nome)) fichas.push(f);
  }
  // 2) Blocos por personagem.
  let atual:FichaLida|null=null; let modo:''|'desc'='';
  const ehTitulo=(l:string)=>{
    if(l.length>60||/[“"”:]/.test(l)||/^(perfil|descri|teste)/i.test(l)) return null;
    const base=l.split(/\s+[·•\-–—]\s+/)[0].trim();
    const ja=fichas.find(f=>semAcento(base)===semAcento(f.nome)||semAcento(base).startsWith(semAcento(f.nome)+' '));
    if(ja) return ja;
    return null;
  };
  linhas.forEach((bruta,i)=>{
    const l=bruta.trim(); if(!l) return;
    const t=ehTitulo(l); if(t){ atual=t; modo=''; return; }
    const prox=linhas.slice(i+1).find(x=>x.trim())?.trim()||'';
    if(l.length<=60&&!/[“":]/.test(l)&&/^perfil\s*[—–:-]/i.test(prox)){ atual=null; modo=''; return; }   // personagem fora da tabela: lido abaixo
    // bloco novo sem tabela: "Nome" seguido de "Perfil —"
    if(!atual&&/^perfil\s*[—–:-]/i.test(l)) return;
    if(!atual) return;
    let m;
    if((m=l.match(/^perfil\s*[—–:-]\s*(.+)$/i))){ atual.genero=m[1].trim().replace(/\.$/,''); modo=''; return; }
    if(/^descri[cç][aã]o/i.test(l)){ const r=l.replace(/^descri[cç][aã]o[^—–:-]*[—–:-]?\s*/i,''); modo='desc'; if(r&&!/^e dire/i.test(r)) atual.descricao=((atual.descricao||'')+' '+r).trim(); return; }
    if(/^teste/i.test(l)){ const f=[...l.matchAll(/[“"]([^”"]+)[”"]/g)].map(x=>x[1].trim()); atual.testes.push(...f); modo=''; return; }
    if(modo==='desc'){ atual.descricao=((atual.descricao||'')+' '+l).trim(); }
  });
  // Blocos de personagens que não estavam na tabela: título seguido de "Perfil —".
  for(let i=0;i<linhas.length-1;i++){
    const l=linhas[i].trim(), prox=linhas.slice(i+1).find(x=>x.trim())?.trim()||'';
    if(l&&l.length<=60&&!/[“":]/.test(l)&&/^perfil\s*[—–:-]/i.test(prox)){
      const nome=l.split(/\s+[·•\-–—]\s+/)[0].trim();
      if(!achar(nome)&&!fichas.some(f=>semAcento(nome).startsWith(semAcento(f.nome)+' '))){
        const sub=lerFichas(`${nome}\tCharon\t50%\n`+linhas.slice(i).join('\n')).find(f=>semAcento(f.nome)===semAcento(nome));
        if(sub){ sub.voz=vozDoNome(nome)||undefined; fichas.push(sub); }
      }
    }
  }
  for(const f of fichas){ if(modelo) f.modelo=modelo; if(sotaque) f.sotaque=sotaque.replace(/^sotaque\s+/i,''); f.nome=f.nome.toUpperCase(); }
  return fichas;
}
/** Aplica uma ficha lida num personagem (novo ou existente). */
export function aplicarFicha(p:Personagem,f:FichaLida):Personagem{
  const n={...p};
  for(const k of ['voz','modelo','genero','gravidade','ritmo','energia','intensidade','emocao','sotaque','descricao'] as const){ const v=f[k]; if(v!==undefined&&v!=='') (n as any)[k]=v; }
  if(f.testes.length) n.testes=f.testes;
  return n;
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
export const listar=<T>(store:Loja)=>tx<T[]>(store,'readonly',s=>s.getAll()).then(l=>store==='personagens'?(l as unknown as Personagem[]).map(normalizarPersonagem) as unknown as T[]:l);
export const salvar=<T extends {id:string}>(store:Loja,v:T)=>tx<void>(store,'readwrite',s=>{ s.put(v); });
export const salvarVarios=<T extends {id:string}>(store:Loja,vs:T[])=>tx<void>(store,'readwrite',s=>{ vs.forEach(v=>s.put(v)); });
export const apagar=(store:Loja,id:string)=>tx<void>(store,'readwrite',s=>{ s.delete(id); });
export const limpar=(store:Loja)=>tx<void>(store,'readwrite',s=>{ s.clear(); });

// ---------------- Importação do roteiro ----------------
export type LinhaRoteiro = {cena:string;nome:string;texto:string;direcao:string;tipo:'fala'|'acao'|'som'};
/** Lê marcações de efeito sonoro: [SOM: ...], [SFX: ...], (SOM: ...), SOM: ... */
export function lerMarcaSom(l:string){
  const m=/^\**\s*[[(]?\s*(?:som|sfx|efeito(?: sonoro)?|ruido|ruído|barulho)\s*[:—–-]\s*(.+?)\s*[\])]?\s*\**$/i.exec(l.trim());
  return m?m[1].replace(/\*\*/g,'').trim():'';
}

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
    const som=lerMarcaSom(l); if(som){ out.push({cena,nome:'',texto:som,direcao:'',tipo:'som'}); continue; }
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
  const ordem=falas.filter(f=>f.tipo==='fala'||f.tipo==='som').sort((a,b)=>a.ordem-b.ordem);
  const partes:{f:Fala;t:Take;s:Float32Array;rate:number}[]=[];
  for(const f of ordem){ const t=takes.find(x=>x.falaId===f.id&&x.aprovado); if(!t) continue; const {samples,rate}=await lerWav(t.wav); partes.push({f,t,s:samples,rate}); }
  const rate=partes[0]?.rate||24000;
  // Takes com taxa diferente são reamostrados; pausa inválida vira 0,4 s.
  for(const p of partes){ if(p.rate!==rate&&p.rate>0){ const r=p.rate/rate, n=Math.floor(p.s.length/r), o=new Float32Array(n); for(let i=0;i<n;i++) o[i]=p.s[Math.min(p.s.length-1,Math.floor(i*r))]; p.s=o; p.rate=rate; } }
  const pausa=(f:Fala)=>Number.isFinite(f.pausa)&&f.pausa>=0?f.pausa:0.4;
  pausaInicial=Number.isFinite(pausaInicial)&&pausaInicial>=0?pausaInicial:0.3;
  // Som com "toca junto" não empurra a próxima fala: começa junto com ela.
  const avanco=(p:{f:Fala;s:Float32Array})=>(p.f.tipo==='som'&&p.f.sobrepor?0:p.s.length)+Math.round(pausa(p.f)*rate);
  let total=Math.round(pausaInicial*rate), fimMax=0; { let o=total; for(const p of partes){ fimMax=Math.max(fimMax,o+p.s.length); o+=avanco(p); } total=Math.max(o,fimMax); }
  const out=new Float32Array(total); let off=Math.round(pausaInicial*rate);
  const manifesto:{tipo:'fala'|'som';ordem:number;cena:string;personagem:string;texto:string;inicio:number;fim:number;duracao:number;take:string;voz:string;modelo:string;arquivo:string}[]=[];
  for(const p of partes){
    const vol=p.f.tipo==='som'?Math.max(0,Math.min(2,(p.f.volume??70)/100)):1;
    for(let i=0;i<p.s.length;i++) out[off+i]+=p.s[i]*vol;
    manifesto.push({tipo:p.f.tipo==='som'?'som':'fala',ordem:p.f.ordem,cena:p.f.cena,personagem:p.f.tipo==='som'?'SOM':nomes[p.f.personagemId]||p.f.nomeRoteiro,texto:p.f.texto,inicio:+(off/rate).toFixed(3),fim:+((off+p.s.length)/rate).toFixed(3),duracao:+(p.s.length/rate).toFixed(3),take:p.t.id,voz:p.t.voz,modelo:p.t.modelo,arquivo:nomeTake(p.f,p.t,nomes[p.f.personagemId]||p.f.nomeRoteiro)});
    off+=avanco(p);
  }
  let pico=0; for(const v of out) pico=Math.max(pico,Math.abs(v)); if(pico>1) for(let i=0;i<out.length;i++) out[i]/=pico;
  return {wav:wav(out,rate),manifesto,duracao:total/rate,faltando:ordem.filter(f=>!partes.some(p=>p.f.id===f.id))};
}

/** Legenda .srt do episódio montado (personagem: fala). */
export function srt(todos:{tipo?:string;personagem:string;texto:string;inicio:number;fim:number}[],comNome=true){
  const man=todos.filter(x=>x.tipo!=='som');
  const ts=(x:number)=>{ const ms=Math.round(x*1000); const h=Math.floor(ms/3600000), m=Math.floor(ms/60000)%60, s=Math.floor(ms/1000)%60; return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')},${String(ms%1000).padStart(3,'0')}`; };
  return man.map((x,i)=>`${i+1}\n${ts(x.inicio)} --> ${ts(x.fim)}\n${comNome?x.personagem+': ':''}${x.texto}\n`).join('\n');
}

export function nomeTake(f:Fala|null,t:Take,nome=''){
  const slug=(s:string)=>s.normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^a-zA-Z0-9]+/g,'-').replace(/^-|-$/g,'').toLowerCase().slice(0,30);
  return `${f?String(f.ordem+1).padStart(3,'0')+'-':''}${slug(nome||'teste')}-${slug(t.texto)}-${t.id.slice(0,5)}.wav`;
}
