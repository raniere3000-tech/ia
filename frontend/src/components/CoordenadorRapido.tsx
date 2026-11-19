import { Suspense, lazy, useEffect, useRef } from 'react';
import { ArrowRight, MessagesSquare, X } from 'lucide-react';
import { useApp } from '../state';

// Mesmo componente de chat da tela do Coordenador (não é um segundo chat: as mensagens vêm do servidor e o rascunho é o mesmo).
const Conversar=lazy(()=>import('../pages/Coordenador').then(m=>({default:m.Conversar})));

/** Atalho global do Coordenador: abre por cima da tela atual, sem perder o que estava aberto. Fecha com X, Esc, toque fora ou Voltar. */
export default function CoordenadorRapido({aberto,fechar}:{aberto:boolean;fechar:()=>void}){
  const {go,settings}=useApp();
  const caixa=useRef<HTMLDivElement>(null);
  const antes=useRef<Element|null>(null);
  const comHistorico=useRef(false);
  useEffect(()=>{
    if(!aberto) return;
    antes.current=document.activeElement;
    // Voltar do celular fecha o atalho em vez de sair da tela
    history.pushState({coordRapido:1},'',location.href); comHistorico.current=true;
    const voltar=()=>{ comHistorico.current=false; fechar(); };
    const tecla=(e:KeyboardEvent)=>{ if(e.key==='Escape') sair(); };
    addEventListener('popstate',voltar); addEventListener('keydown',tecla);
    const foco=setTimeout(()=>caixa.current?.querySelector<HTMLElement>('[data-coord-texto]')?.focus()||caixa.current?.querySelector<HTMLElement>('button')?.focus(),300);
    document.body.classList.add('sem-rolar');
    return ()=>{ removeEventListener('popstate',voltar); removeEventListener('keydown',tecla); clearTimeout(foco); document.body.classList.remove('sem-rolar');
      (antes.current as HTMLElement|null)?.focus?.(); };
  },[aberto]);   // eslint-disable-line react-hooks/exhaustive-deps
  const sair=()=>{ if(comHistorico.current&&history.state?.coordRapido){ comHistorico.current=false; history.back(); } fechar(); };
  const irPara=(extra:string)=>{ const tinha=comHistorico.current&&history.state?.coordRapido; comHistorico.current=false; fechar();
    // tira o passo extra do Voltar antes de navegar
    if(tinha){ const f=()=>{ removeEventListener('popstate',f); go('coordenador',extra,'agentes'); }; addEventListener('popstate',f); history.back(); } else go('coordenador',extra,'agentes'); };
  if(!aberto) return null;
  return <div className="coord-drawer-fundo" onClick={e=>{ if(e.target===e.currentTarget) sair(); }}>
    <div className="coord-drawer" role="dialog" aria-modal="true" aria-labelledby="coord-drawer-titulo" ref={caixa}>
      <header className="coord-drawer-topo">
        <MessagesSquare size={18}/><h2 id="coord-drawer-titulo" className="grow">Coordenador</h2>
        <button className="link-btn" onClick={()=>irPara('conversar')}>Tela completa <ArrowRight size={13}/></button>
        <button className="icon-btn" onClick={sair} aria-label="Fechar"><X size={18}/></button>
      </header>
      {settings.servidor?<Suspense fallback={<p className="hint" role="status">Abrindo...</p>}><Conversar compacto abrirOrdem={id=>irPara('ordens:'+id)}/></Suspense>
        :<p className="hint">Conecte o servidor do celular em Ajustes para falar com o Coordenador.</p>}
    </div>
  </div>;
}
