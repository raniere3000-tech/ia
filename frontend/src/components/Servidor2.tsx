import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Server } from 'lucide-react';
import { useApp } from '../state';
import type { CfgSrv } from '../lib/api';

/** Endereço e senha (compatibilidade) do servidor do celular, prontos para a API. */
export function useCfg():CfgSrv{
  const {settings}=useApp();
  return useMemo(()=>({servidor:settings.servidor,servidorToken:settings.servidorToken}),[settings.servidor,settings.servidorToken]);
}

/** Lê algo do servidor e repete a cada `seg` segundos enquanto a tela está visível. */
export function useServidor<T>(f:(cfg:CfgSrv)=>Promise<T>,seg=0,deps:unknown[]=[]){
  const cfg=useCfg();
  const [dados,setDados]=useState<T|null>(null);
  const [erro,setErro]=useState('');
  const [carregando,setCarregando]=useState(false);
  const fRef=useRef(f); fRef.current=f;
  const recarregar=useCallback(async()=>{
    if(!cfg.servidor) return;
    setCarregando(true);
    try{ setDados(await fRef.current(cfg)); setErro(''); }
    catch(e){ setErro(e instanceof Error?e.message:String(e)); }
    finally{ setCarregando(false); }
  },[cfg]);
  useEffect(()=>{
    recarregar();
    if(!seg) return;
    const iv=setInterval(()=>{ if(document.visibilityState==='visible') recarregar(); },seg*1000);
    return ()=>clearInterval(iv);
  },[recarregar,seg,...deps]);   // eslint-disable-line react-hooks/exhaustive-deps
  return {dados,erro,carregando,recarregar,setDados};
}

/** Aviso quando a tela precisa do servidor do celular e ele não está ligado neste aparelho. */
export function PrecisaServidor({oque}:{oque:string}){
  const {go}=useApp();
  return <section className="panel empty-state">
    <Server size={30}/>
    <h2>Ligue o servidor do celular</h2>
    <p className="subtitle">{oque} roda no servidor do seu Android (Termux), com o navegador fechado. Conecte este aparelho em Ajustes &gt; Servidor do celular, ou abra o link de conexão gerado pelo servidor.</p>
    <button className="primary" onClick={()=>go('config')}>Abrir Ajustes</button>
  </section>;
}

export const erroTexto=(e:unknown)=>e instanceof Error?e.message:String(e);
