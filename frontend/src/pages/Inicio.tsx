import { Search, Upload, Sparkles, Download, KeyRound, CheckCircle2, Circle, ArrowRight, ShieldCheck, Clock, Ban } from 'lucide-react';
import { useApp } from '../state';
import { HelpButton } from '../components/Help';

export default function Inicio(){
  const {settings,go}=useApp();
  const passos=[
    {icon:KeyRound,t:'1. Cole suas chaves',d:'A chave gratuita do YouTube ativa o Radar. A chave de IA (Gemini grátis ou Claude) é opcional e deixa as notas mais inteligentes.',btn:'Abrir Chaves e ajustes',to:'config' as const},
    {icon:Search,t:'2. Ache vídeos em alta',d:'No Radar, escolha um nicho e veja vídeos e canais com mais views por dia. Use para se inspirar ou achar parceiros.',btn:'Abrir o Radar',to:'radar' as const},
    {icon:Upload,t:'3. Envie seu vídeo',d:'Em Gerar cortes, arraste um vídeo seu ou autorizado. O site transcreve a fala e encontra os melhores trechos.',btn:'Gerar cortes',to:'cortes' as const},
    {icon:Download,t:'4. Edite e exporte',d:'Ajuste início e fim, corrija a legenda, escolha estilo e efeito, e baixe em MP4 vertical, quadrado ou horizontal.',btn:'Ver estilos',to:'estilos' as const},
  ];
  const checks=[
    {ok:!!settings.ytKey,t:'Chave da YouTube Data API',d:'Necessária só para o Radar. Grátis.',help:'youtube' as const,need:'Obrigatória para o Radar'},
    {ok:!!(settings.geminiKey||settings.claudeKey),t:'Chave de IA: Gemini (grátis) ou Claude',d:'Opcional. Notas de gancho, fluxo, valor e tendência, títulos e busca por pedido.',help:'gemini' as const,need:'Opcional'},
    {ok:true,t:'Legendas automáticas (Whisper)',d:'Já funciona, sem chave. O modelo é baixado na primeira vez.',help:'whisper' as const,need:'Sem chave'},
  ];
  return <>
   <section className="hero panel">
    <div className="hero-text">
     <span className="pill"><Sparkles size={13}/> Funciona direto no navegador</span>
     <h2 className="hero-title">Do vídeo longo ao corte viral em 4 passos</h2>
     <p>Seu vídeo não é enviado para nenhum servidor: a análise, a transcrição e a exportação acontecem no seu computador.</p>
     <div className="actions"><button className="primary lg" onClick={()=>go('cortes')}><Upload size={17}/> Começar com um vídeo</button><button className="subtle lg" onClick={()=>go(settings.ytKey?'radar':'config')}><Search size={17}/> {settings.ytKey?'Pesquisar no Radar':'Configurar o Radar'}</button></div>
    </div>
   </section>

   <div className="steps">{passos.map(p=><article key={p.t} className="step-card"><span className="step-icon"><p.icon size={20}/></span><h3>{p.t}</h3><p>{p.d}</p><button className="link-btn" onClick={()=>go(p.to)}>{p.btn} <ArrowRight size={14}/></button></article>)}</div>

   <section className="panel">
    <div className="section-head"><h2><KeyRound size={18}/> O que precisa estar configurado</h2><button className="subtle" onClick={()=>go('config')}>Configurar agora</button></div>
    <div className="check-list">{checks.map(c=><div key={c.t} className={'check-item '+(c.ok?'ok':'')}>{c.ok?<CheckCircle2 size={20}/>:<Circle size={20}/>}<div><strong>{c.t} <HelpButton topic={c.help}/></strong><p>{c.d}</p></div><span className={'tag '+(c.ok?'ok':c.need==='Opcional'?'':'warn')}>{c.ok?'Pronto':c.need}</span></div>)}</div>
   </section>

   <div className="two-cols even">
    <section className="panel"><div className="section-head"><h2><ShieldCheck size={18}/> Boas práticas</h2></div><ul className="plain">
     <li>Use apenas vídeos seus ou com autorização do dono. Dar crédito não substitui a autorização.</li>
     <li>A nota é uma lista de prioridade, não uma garantia de viralização. Assista antes de publicar.</li>
     <li>As chaves ficam salvas só neste navegador. Apague-as em Chaves e ajustes se usar um computador compartilhado.</li>
    </ul></section>
    <section className="panel"><div className="section-head"><h2><Clock size={18}/> Ainda não disponível no site</h2></div><ul className="plain muted">
     <li><Ban size={13}/> Agendar e postar automaticamente no TikTok, Instagram e YouTube: exige servidor e apps aprovados pelas redes.</li>
     <li><Ban size={13}/> Reenquadramento que segue o rosto: os cortes usam fundo desfocado ou corte central.</li>
    </ul></section>
   </div>
  </>;
}
