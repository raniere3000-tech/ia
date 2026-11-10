// Preferências salvas apenas neste navegador (chaves, pesquisas, template).
export const store = {
  get(k:string){ try{ return localStorage.getItem(k); }catch{ return null; } },
  set(k:string,v:string){ try{ localStorage.setItem(k,v); }catch{ /* armazenamento indisponível */ } },
  del(k:string){ try{ localStorage.removeItem(k); }catch{ /* ignore */ } },
  json<T>(k:string,fallback:T):T{ try{ const v = localStorage.getItem(k); return v ? JSON.parse(v) as T : fallback; }catch{ return fallback; } },
  setJson(k:string,v:unknown){ try{ localStorage.setItem(k,JSON.stringify(v)); }catch{ /* ignore */ } },
};

export const fmt = (n:number)=>Intl.NumberFormat('pt-BR').format(n);
export const tm = (s:number)=>{ s=Math.max(0,s); const h=Math.floor(s/3600), m=Math.floor(s%3600/60), x=Math.floor(s%60); return (h?`${h}:${String(m).padStart(2,'0')}`:`${m}`)+':'+String(x).padStart(2,'0'); };
export const parseTime = (t:string)=>{ const p=t.trim().split(':').map(Number); if(p.some(isNaN)) return NaN; return p.reduce((a,b)=>a*60+b,0); };
export const uid = ()=>Math.random().toString(36).slice(2,9);
