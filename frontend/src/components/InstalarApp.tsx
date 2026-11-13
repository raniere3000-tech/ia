import { useEffect, useState } from 'react';
import { Smartphone, Download, CheckCircle2, Share } from 'lucide-react';
import { aoMudarInstalacao, ehIOS, instalado, instalar, podeInstalar } from '../lib/app';
import { useApp } from '../state';

/** Cartão "Instalar no telefone": botão direto no Android/Chrome e passo a passo no iPhone. */
export default function InstalarApp(){
  const {toast}=useApp();
  const [,setN]=useState(0);
  useEffect(()=>aoMudarInstalacao(()=>setN(n=>n+1)),[]);
  if(instalado()) return null;
  const ios=ehIOS();
  return <section className="panel instalar-app">
   <span className="step-icon"><Smartphone size={22}/></span>
   <div className="grow">
    <h3>Use como aplicativo no telefone</h3>
    {podeInstalar()?<p>Instale o EstúdioClip na tela inicial. Ele abre em tela cheia, sem a barra do navegador, e com todas as funções.</p>
    :ios?<p>No iPhone, abra este site no <b>Safari</b>, toque em <b>Compartilhar</b> <Share size={13}/> e depois em <b>Adicionar à Tela de Início</b>.</p>
    :<p>No Chrome do Android, toque nos <b>três pontinhos</b> e depois em <b>Instalar aplicativo</b> (ou <b>Adicionar à tela inicial</b>). No computador, use o ícone de instalar na barra de endereço.</p>}
   </div>
   {podeInstalar()&&<button className="primary" onClick={async()=>{ if(await instalar()) toast('Aplicativo instalado. Procure o ícone do EstúdioClip na tela inicial.','ok'); }}><Download size={16}/> Instalar aplicativo</button>}
   {!podeInstalar()&&!ios&&<small className="hint"><CheckCircle2 size={13}/> Se já instalou, abra pelo ícone na tela inicial.</small>}
  </section>;
}
