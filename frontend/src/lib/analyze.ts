// Motor de cortes no navegador: monta candidatos a partir dos picos de áudio e das frases
// da transcrição, dá notas heurísticas (gancho, fluxo, valor, tendência) e remove sobreposições.
import type { Cue } from './captions';

export type Notas = {gancho:number;fluxo:number;valor:number;tendencia:number};
export type Formato = '9:16'|'1:1'|'16:9';
export type Clip = {
  id:string; titulo:string; inicio:number; fim:number;
  nota_final:number; nota_10:number; notas:Notas; motivo:string; fonte:'heuristica'|'ia';
  legenda:string; efeito:string; formato:Formato; gancho_texto:string;
  versao_de?:string; descartado?:boolean; thumb?:string; marca?:string; legendaOk?:boolean; dublado?:boolean; semTemplate?:boolean;
  /** Vídeo próprio do corte (ex.: vários Shorts do Radar no mesmo lote). Sem isso, usa o vídeo do projeto. */
  video?:Fonte;
};
export type Fonte = {url:string;file:File;cues:Cue[];duracao:number;link?:string};
/** Legenda e vídeo que valem para este corte. */
export const cuesDe=(c:Clip,cues:Cue[])=>c.video?.cues??cues;
export const urlDe=(c:Clip,url:string)=>c.video?.url||url;
export type AnalyzeOpts = {min:number;max:number;limite:number;inicio:number;fim:number};

/** Converte a nota interna 0–99 para a exibição 0–10 (arredondada em 1 casa). */
export const nota10 = (n:number)=>Math.round(n*10/99*10)/10;
export const notaFinal = (n:Notas)=>Math.round(0.35*n.gancho+0.25*n.fluxo+0.25*n.valor+0.15*n.tendencia);

function mean(a:Float32Array,i:number,j:number){ let s=0; const b=Math.max(i,0), e=Math.min(j,a.length); for(let k=b;k<e;k++) s+=a[k]; return e>b? s/(e-b):0; }
function maxOf(a:Float32Array,i:number,j:number){ let m=0; for(let k=Math.max(i,0);k<Math.min(j,a.length);k++) m=Math.max(m,a[k]); return m; }

export type Candidate = {inicio:number;fim:number;notas:Notas;motivo:string};

const FRACAS = /^(e|mas|então|entao|aí|ai|daí|dai|porque|pq|tipo|né|ne|sim|não|nao|isso|é|eh|ah|hum|uhum|tá|ta|ok|beleza|exato|claro|só que|so que|and|but|so|yeah|yes|right|um|uh|like)\b[\s,.!?]/i;
/** Primeira fala começa com palavra que só faz sentido com o que veio antes? */
export function aberturaFraca(t:string){ const s=t.trim().toLowerCase(); return FRACAS.test(s+' ')||/^[^\s]+[.!?]?$/.test(s); }

export function gerarCandidatos(energy:Float32Array|null,step:number,duration:number,cues:Cue[],o:AnalyzeOpts):Candidate[]{
  const a = Math.max(0,Math.min(o.inicio,duration)), b = Math.min(duration,o.fim>0?o.fim:duration);
  const span = b-a;
  if(span < Math.min(o.min,5)) return [];
  const min = Math.min(o.min,span), max = Math.min(o.max,span);
  const lens = Array.from(new Set([min,Math.round((min+max)/2),max])).filter(l=>l>0);
  const stride = Math.max(2,Math.round(min/4));
  const ref = energy ? (()=>{ const s=Array.from(energy.slice(Math.floor(a/step),Math.ceil(b/step))).sort((x,y)=>x-y); return {p50:s[Math.floor(s.length*0.5)]||0, p95:s[Math.floor(s.length*0.95)]||1}; })() : {p50:0,p95:1};
  const norm = (v:number)=>Math.max(0,Math.min(1,(v-ref.p50)/Math.max(1e-6,ref.p95-ref.p50)));
  const snapStart = (t:number)=>{ const c=cues.find(c=>c.start>=t-0.01&&c.start<=t+3); return c? c.start : t; };
  const snapEnd = (t:number)=>{ const c=[...cues].reverse().find(c=>c.end<=t+0.01&&c.end>=t-3); return c? c.end : t; };
  const out:Candidate[] = [];
  for(const L of lens){
    for(let s=a; s+L<=b+0.01; s+=stride){
      let ini=s, fim=Math.min(b,s+L);
      let snapped=0;
      if(cues.length){ const ns=snapStart(ini); if(ns!==ini){ini=ns;snapped++;} const ne=snapEnd(fim); if(ne!==fim&&ne-ini>=min*0.8){fim=ne;snapped++;} }
      if(fim-ini < min*0.8) continue;
      const fala = cues.filter(c=>c.end>ini&&c.start<fim).reduce((n,c)=>n+Math.min(fim,c.end)-Math.max(ini,c.start),0)/(fim-ini);
      let gancho=40, valor=40, fluxo=cues.length? 45+snapped*25 : 55, motivo='';
      if(energy){
        const i0=Math.floor(ini/step), i3=Math.floor((ini+3)/step), i1=Math.floor(fim/step);
        const hook = Math.max(norm(mean(energy,i0,i3)), norm(maxOf(energy,i0,i3))*0.8);
        const body = norm(mean(energy,i0,i1)); const peak = norm(maxOf(energy,i0,i1));
        gancho = 20+75*hook; valor = 20+45*body+30*peak;
        motivo = hook>0.6 ? 'Começa com áudio forte, bom gancho nos primeiros segundos.' : peak>0.8 ? 'Tem pico de áudio marcante (reação, grito, risada ou ação).' : 'Trecho com energia sonora estável.';
      }
      if(cues.length){ valor += 10*fala; motivo += fala>0.6 ? ' Fala contínua.' : ''; if(snapped===2) motivo+=' Começa e termina em frase completa.'; }
      // Abrir com conjunção, muleta ou resposta solta depende do que veio antes: gancho fraco.
      const primeira = cues.find(c=>c.end>ini&&c.start<fim);
      if(primeira&&aberturaFraca(primeira.text)){ gancho -= 15; motivo += ' Começa com palavra que depende do contexto anterior.'; }
      const notas = {gancho:Math.round(Math.min(95,gancho)),fluxo:Math.round(Math.min(95,fluxo)),valor:Math.round(Math.min(95,valor)),tendencia:50};
      out.push({inicio:+ini.toFixed(2),fim:+fim.toFixed(2),notas,motivo:motivo.trim()||'Sem áudio legível: trecho sugerido em sequência.'});
    }
  }
  // Ordena por nota e remove candidatos que se sobrepõem mais de 50%.
  out.sort((x,y)=>notaFinal(y.notas)-notaFinal(x.notas) || y.notas.gancho-x.notas.gancho || x.inicio-y.inicio);
  const sel:Candidate[] = [];
  for(const c of out){
    const ok = sel.every(s=>{ const ov=Math.max(0,Math.min(s.fim,c.fim)-Math.max(s.inicio,c.inicio)); return ov/Math.min(s.fim-s.inicio,c.fim-c.inicio) <= 0.5; });
    if(ok) sel.push(c);
    if(sel.length>=60) break;
  }
  return sel;
}

/** Dá notas aos trechos que o próprio usuário marcou (sem procurar outros). */
export function avaliarJanelas(energy:Float32Array|null,step:number,cues:Cue[],janelas:{inicio:number;fim:number;titulo?:string}[]):(Candidate&{titulo?:string})[]{
  const ref = energy ? (()=>{ const s=Array.from(energy).sort((x,y)=>x-y); return {p50:s[Math.floor(s.length*0.5)]||0, p95:s[Math.floor(s.length*0.95)]||1}; })() : {p50:0,p95:1};
  const norm = (v:number)=>Math.max(0,Math.min(1,(v-ref.p50)/Math.max(1e-6,ref.p95-ref.p50)));
  return janelas.filter(j=>j.fim-j.inicio>=1).map(j=>{
    const ini=j.inicio, fim=j.fim;
    const fala = cues.length ? cues.filter(c=>c.end>ini&&c.start<fim).reduce((n,c)=>n+Math.min(fim,c.end)-Math.max(ini,c.start),0)/(fim-ini) : 0;
    let gancho=50, valor=50;
    if(energy){
      const i0=Math.floor(ini/step), i3=Math.floor((ini+3)/step), i1=Math.floor(fim/step);
      gancho = 20+75*Math.max(norm(mean(energy,i0,i3)), norm(maxOf(energy,i0,i3))*0.8);
      valor = 20+45*norm(mean(energy,i0,i1))+30*norm(maxOf(energy,i0,i1))+10*fala;
    }
    const notas = {gancho:Math.round(Math.min(95,gancho)),fluxo:60,valor:Math.round(Math.min(95,valor)),tendencia:50};
    return {inicio:+ini.toFixed(2),fim:+fim.toFixed(2),notas,motivo:'Trecho marcado por você no link.',titulo:j.titulo};
  });
}
