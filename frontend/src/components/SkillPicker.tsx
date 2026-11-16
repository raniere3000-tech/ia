import { useState } from 'react';
import { BookOpen } from 'lucide-react';
import { useServidor } from './Servidor2';
import { lerPerfis, listarSkills } from '../lib/skills';

/** "Usar nesta tarefa": escolhe skills extras (só regras de texto) para um pedido à IA. Nada roda sozinho. */
export default function SkillPicker({perfil,valor,onChange}:{perfil:string;valor:string[];onChange:(v:string[])=>void}){
  const [aberto,setAberto]=useState(false); const [busca,setBusca]=useState('');
  const p=useServidor(lerPerfis,0);
  const s=useServidor(c=>aberto?listarSkills(c,{estado:'usavel'}):Promise.resolve(null),0,[aberto]);
  const perf=p.dados?.perfis.find(x=>x.id===perfil);
  if(!perf) return null;
  const ag=perf.agente; const q=busca.trim().toLowerCase();
  const opc=(s.dados?.skills||[]).filter(x=>x.tipo==='producao'&&!perf.skills.includes(x.id)&&(valor.includes(x.id)||(q?(x.id+' '+x.gatilho+' '+x.descricao).toLowerCase().includes(q):x.agentes.includes(ag))));
  return <div className="skill-picker">
    <button className="link-btn" onClick={()=>setAberto(!aberto)}><BookOpen size={13}/> Boas práticas (skills): {perf.ligado?(perf.prontas.length?perf.prontas.join(', '):'nenhuma instalada'):'desligadas'}{valor.length>0&&` + ${valor.length} escolhida(s)`}</button>
    {aberto&&<div className="skill-picker-box">
      <p className="hint">As regras dessas skills entram no pedido à IA como material de apoio. Elas não aprovam nem publicam nada. Mude as automáticas em Ajustes &gt; Skills.</p>
      {s.erro&&<p className="hint bad">{s.erro}</p>}
      <input value={busca} onChange={e=>setBusca(e.target.value)} placeholder="Procurar (ex.: câmera, suspense, documentário)"/>
      {opc.length>0?<div className="chips mt">{opc.slice(0,12).map(x=>{ const on=valor.includes(x.id); return <button key={x.id} className={'chip '+(on?'on':'')} aria-pressed={on} title={x.descricao}
        onClick={()=>onChange(on?valor.filter(y=>y!==x.id):[...valor,x.id].slice(-3))}>{x.id}</button>; })}</div>
       :s.dados&&<p className="hint">Nenhuma outra skill pronta. Instale em Ajustes &gt; Skills.</p>}
    </div>}
  </div>;
}
