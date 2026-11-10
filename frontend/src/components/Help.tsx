import { useEffect, useState, type ReactNode } from 'react';
import { HelpCircle, X, ExternalLink } from 'lucide-react';

type Topic = {titulo:string; corpo:ReactNode};

const L = ({href,children}:{href:string;children:ReactNode})=><a className="help-link" href={href} target="_blank" rel="noreferrer">{children} <ExternalLink size={12}/></a>;

export const TOPICS:Record<string,Topic> = {
  youtube:{titulo:'Como conseguir a chave da YouTube Data API (grátis)',corpo:<>
    <p>A chave permite que o Radar pesquise vídeos e canais públicos do YouTube. É gratuita: o Google dá 10.000 unidades de cota por dia, o que dá para cerca de 90 pesquisas diárias.</p>
    <ol>
      <li>Entre no <L href="https://console.cloud.google.com/">Google Cloud Console</L> com sua conta Google.</li>
      <li>No topo, clique em <b>Selecionar projeto → Novo projeto</b>, dê um nome (ex.: “EstudioClip”) e clique em <b>Criar</b>.</li>
      <li>Abra a página da <L href="https://console.cloud.google.com/apis/library/youtube.googleapis.com">YouTube Data API v3</L> e clique em <b>Ativar</b>.</li>
      <li>Vá em <L href="https://console.cloud.google.com/apis/credentials">APIs e serviços → Credenciais</L>, clique em <b>Criar credenciais → Chave de API</b>.</li>
      <li>Copie a chave (começa com <code>AIza</code>) e cole no campo desta página.</li>
      <li><b>Recomendado:</b> clique em <b>Editar chave</b>, em “Restrições de aplicativo” escolha <b>Sites</b> e adicione <code>{location.origin}/*</code>. Em “Restrições de API”, escolha só a YouTube Data API v3.</li>
    </ol>
    <p className="help-note">A chave fica salva apenas neste navegador. Ninguém mais tem acesso a ela.</p>
  </>},
  claude:{titulo:'Como conseguir a chave da Claude (IA para notas e títulos)',corpo:<>
    <p>Com essa chave, a IA lê a transcrição (e, no modo Gameplay, quadros do vídeo) e dá notas de <b>gancho, fluxo, valor e tendência</b>, escreve títulos e aceita pedidos como “ache onde ele fala de preço”. É <b>opcional</b>: sem ela o site usa notas automáticas pelo áudio.</p>
    <ol>
      <li>Crie uma conta em <L href="https://console.anthropic.com/">console.anthropic.com</L>.</li>
      <li>Em <L href="https://console.anthropic.com/settings/billing">Billing</L>, adicione créditos (a API é paga por uso; avaliar um vídeo longo costuma custar alguns centavos de dólar).</li>
      <li>Em <L href="https://console.anthropic.com/settings/keys">API Keys</L>, clique em <b>Create Key</b>, dê um nome e copie a chave (começa com <code>sk-ant-</code>).</li>
      <li>Cole no campo desta página e clique em <b>Testar</b>.</li>
    </ol>
    <p className="help-note">A chave fica só neste navegador e é enviada direto para a Anthropic. Não use este site em computadores compartilhados com a chave salva; você pode apagá-la a qualquer momento. Defina um limite de gasto no console por segurança.</p>
  </>},
  whisper:{titulo:'Legendas automáticas (Whisper no navegador)',corpo:<>
    <p>O site transcreve a fala do vídeo usando o modelo Whisper rodando <b>no seu próprio computador</b>, sem enviar o vídeo para lugar nenhum e sem custo.</p>
    <ul>
      <li>Na primeira vez, o navegador baixa o modelo (40 a 250 MB, conforme a opção). Depois fica guardado.</li>
      <li>Funciona melhor no Chrome ou Edge atualizados. Com placa de vídeo compatível (WebGPU) fica bem mais rápido.</li>
      <li>Um vídeo de 10 minutos leva de 1 a 5 minutos para transcrever no modo “Rápido”.</li>
      <li>Se preferir, você pode enviar um arquivo de legenda pronto (.srt ou .vtt).</li>
    </ul>
  </>},
  srt:{titulo:'O que é um arquivo .srt ou .vtt?',corpo:<>
    <p>São arquivos de texto com as falas e os horários. Você pode baixar a legenda de um vídeo seu no <L href="https://studio.youtube.com/">YouTube Studio</L> (Legendas → ⋮ → Baixar → .srt) ou gerar em editores como CapCut.</p>
  </>},
  nota:{titulo:'Como a nota funciona',corpo:<>
    <p>Cada corte recebe uma nota interna de <b>0 a 99</b>, mostrada também de 0 a 10 (nota × 10 ÷ 99). Ela é a média ponderada de quatro critérios:</p>
    <ul><li><b>Gancho (35%)</b>: os 3 primeiros segundos prendem?</li><li><b>Fluxo (25%)</b>: começa e termina em frase completa?</li><li><b>Valor (25%)</b>: diverte, surpreende ou ensina?</li><li><b>Tendência (15%)</b>: tem a ver com o que está em alta?</li></ul>
    <p>Sem a chave da Claude, as notas vêm dos sinais de áudio e das frases da transcrição (tendência fica neutra, 50). Com a chave, a IA avalia o conteúdo. A nota é uma lista de prioridade, <b>não uma previsão de viralização</b>.</p>
  </>},
  velocidade:{titulo:'O que é “views por dia”',corpo:<>
    <p>É uma média: total de visualizações ÷ dias desde a publicação. Não é a velocidade de agora nem previsão de viralização, e os números públicos podem estar defasados.</p>
  </>},
  servidor:{titulo:'Como ligar os cortes direto pelo link',corpo:<>
    <p>Nenhum site consegue baixar vídeo do YouTube sozinho: o próprio YouTube bloqueia. Por isso o EstúdioClip tem um <b>servidor pequeno que roda no seu computador</b>. Ele baixa o vídeo do link e entrega para o site, que analisa e corta sozinho.</p>
    <ol>
     <li>Instale o <a href="https://www.python.org/downloads/" target="_blank" rel="noreferrer">Python</a> (no Windows, marque <b>Add Python to PATH</b> na instalação).</li>
     <li>Baixe o servidor: <a href="https://github.com/raniere3000-tech/ia/archive/refs/heads/main.zip" target="_blank" rel="noreferrer">clique aqui para baixar o ZIP do projeto</a> e descompacte.</li>
     <li>Abra a pasta <code>servidor</code> e dê dois cliques em <b>iniciar-windows.bat</b> (no Mac/Linux: <code>iniciar-mac-linux.sh</code>). Na primeira vez ele instala tudo sozinho em 1 a 3 minutos.</li>
     <li>Quando aparecer <code>rodando em http://localhost:8787</code>, deixe a janela aberta, cole <b>http://localhost:8787</b> aqui e clique em <b>Testar e salvar</b>.</li>
    </ol>
    <p>Pronto: em <b>Gerar cortes</b>, cole o link e clique em <b>Cortar automático</b>. Use só vídeos seus ou com autorização do dono.</p>
    <p><b>No celular Android (Termux):</b> rode <code>pkg install -y git && git clone https://github.com/raniere3000-tech/ia && cd ia/servidor && bash iniciar-termux.sh link</code>. O terminal mostra um link do site já ligado ao celular: abra esse link em qualquer aparelho, de qualquer lugar.</p>
    <p className="hint">Dá para hospedar o servidor na nuvem (tem Dockerfile na pasta), mas o YouTube costuma bloquear servidores de nuvem. No seu computador funciona melhor. Se hospedar, defina uma senha (variável <code>TOKEN</code>) e cole a mesma senha aqui.</p>
  </>},
  modelo:{titulo:'Falas ou Gameplay/ação?',corpo:<>
    <ul><li><b>Falas</b>: podcasts, entrevistas, aulas. Usa a transcrição para achar frases completas.</li><li><b>Gameplay/ação</b>: jogos, esportes, vídeos com pouca fala. Dá mais peso aos picos de áudio e, se a Claude estiver configurada, envia 2 quadros de cada trecho para a IA ver o que acontece (custa um pouco mais).</li></ul>
  </>},
  exportar:{titulo:'Como a exportação funciona',corpo:<>
    <p>O vídeo final é montado no seu navegador e gravado em tempo real: um corte de 60 s leva cerca de 60 s. Mantenha a aba aberta e visível até terminar.</p>
    <p>Chrome, Edge e Safari recentes geram <b>MP4</b>. Navegadores mais antigos geram <b>WEBM</b>, que também é aceito pelo YouTube e TikTok.</p>
  </>},
};

export function HelpButton({topic,label}:{topic:keyof typeof TOPICS;label?:string}){
  const [open,setOpen]=useState(false);
  return <>
    <button type="button" className={'help-btn'+(label?' with-label':'')} onClick={e=>{e.preventDefault();e.stopPropagation();setOpen(true)}} aria-label={'Ajuda: '+TOPICS[topic].titulo} title="Como funciona?"><HelpCircle size={15}/>{label&&<span>{label}</span>}</button>
    {open&&<Modal title={TOPICS[topic].titulo} onClose={()=>setOpen(false)}>{TOPICS[topic].corpo}</Modal>}
  </>;
}

export function Modal({title,children,onClose,wide}:{title:string;children:ReactNode;onClose:()=>void;wide?:boolean}){
  useEffect(()=>{ const k=(e:KeyboardEvent)=>{ if(e.key==='Escape') onClose(); }; addEventListener('keydown',k); return ()=>removeEventListener('keydown',k); },[onClose]);
  return <div className="modal-bg" onMouseDown={onClose}><div className={'modal'+(wide?' wide':'')} role="dialog" aria-modal="true" onMouseDown={e=>e.stopPropagation()}>
    <div className="modal-head"><h3>{title}</h3><button className="icon-btn" onClick={onClose} aria-label="Fechar"><X size={18}/></button></div>
    <div className="modal-body">{children}</div>
  </div></div>;
}
