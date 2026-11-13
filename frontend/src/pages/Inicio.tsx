import InstalarApp from '../components/InstalarApp';
import { Search, Upload, Sparkles, Download, KeyRound, CheckCircle2, Circle, ArrowRight, ShieldCheck, Clock, Clapperboard, Mic, Film, PlayCircle } from 'lucide-react';
import { useApp } from '../state';
import { HelpButton } from '../components/Help';

export default function Inicio(){
  const {settings,go,projeto}=useApp();
  // Trabalhos guardados neste navegador, para continuar de onde parou.
  const ler=(k:string)=>{ try{ return JSON.parse(localStorage.getItem(k)||'null'); }catch{ return null; } };
  const continuar:{t:string;d:string;to:'cortes'|'manual'|'vozes'|'video'}[]=[];
  const nCortes=projeto.clips.filter(c=>!c.descartado).length; if(nCortes) continuar.push({t:'Cortes',d:`${nCortes} corte(s) prontos para editar`,to:'cortes'});
  const man=ler('studio_manual'); if(man?.texto?.trim()) continuar.push({t:'Montagem manual',d:man.sinc?.quadros?.length?`${man.sinc.quadros.length} quadros sincronizados`:'Roteiro de quadros salvo',to:'manual'});
  if(localStorage.getItem('studio_vozes_projeto')) continuar.push({t:'Estúdio de vozes',d:'Projeto de vozes aberto por último',to:'vozes'});
  const vc=ler('studio_video_codigo'); if(vc?.cenas?.length) continuar.push({t:'Vídeo animado',d:`${vc.titulo||'Roteiro'} • ${vc.cenas.length} cenas`,to:'video'});
  const entradas=[
    {icon:Clapperboard,t:'Criar cortes',d:'Envie um vídeo longo e receba os melhores trechos com nota, legenda e efeito.',onde:'Roda no seu navegador',to:'cortes' as const},
    {icon:Mic,t:'Montar episódio',d:'Roteiro, vozes dos personagens e montagem com imagens, trilha e efeitos.',onde:'Vozes pelo Gemini, montagem no navegador',to:'vozes' as const},
    {icon:Film,t:'Criar vídeo animado',d:'Digite um tema e o site monta um vídeo vertical com narração e batida.',onde:'Roteiro e voz por IA, vídeo no navegador',to:'video' as const},
  ];
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
   {continuar.length>0&&<section className="panel">
    <div className="section-head"><h2><PlayCircle size={18}/> Continuar projeto</h2></div>
    <div className="inicio-cont">{continuar.map(c=><button key={c.t} className="inicio-cont-item" onClick={()=>go(c.to)}><b>{c.t}</b><small>{c.d}</small><ArrowRight size={15}/></button>)}</div>
   </section>}
   <div className="inicio-entradas">{entradas.map(e=><button key={e.t} className="inicio-entrada" onClick={()=>go(e.to)}><span className="step-icon"><e.icon size={22}/></span><h3>{e.t}</h3><p>{e.d}</p><small>{e.onde}</small></button>)}</div>
   <InstalarApp/>
   <details className="inicio-ajuda"><summary>Ajuda: como configurar e usar, passo a passo</summary>
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
    <section className="panel"><div className="section-head"><h2><Clock size={18}/> Postar nas redes</h2><button className="subtle" onClick={()=>go('agendar')}>Abrir Agendar posts</button></div><ul className="plain muted">
     <li>O agendamento já funciona: com o servidor ligado, entre nas suas contas em <b>Agendar posts</b> (YouTube, Facebook, Instagram e TikTok). O Kwai é manual: você baixa o vídeo e posta no app.</li>
     <li>Cada rede pede um "app de desenvolvedor" seu, criado uma vez. O botão <b>Como criar?</b> de cada conta mostra o passo a passo.</li>
     <li>Enquanto a rede não aprova o seu app, há limites: no YouTube os vídeos sobem como privados, e no TikTok vão para os rascunhos (você toca em Postar).</li>
    </ul></section>
   </div>
   </details>
  </>;
}
