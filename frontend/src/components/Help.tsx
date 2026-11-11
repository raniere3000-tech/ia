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
  gemini:{titulo:'Como conseguir a chave do Gemini (IA do Google, tem cota grátis)',corpo:<>
    <p>O Gemini faz o mesmo que a Claude aqui: lê a transcrição (e, no modo Gameplay, quadros do vídeo), dá notas de <b>gancho, fluxo, valor e tendência</b>, escreve títulos e aceita pedidos. Tem uma <b>cota grátis por dia</b>.</p>
    <ol>
      <li>Entre em <L href="https://aistudio.google.com/apikey">aistudio.google.com/apikey</L> com sua conta Google.</li>
      <li>Clique em <b>Create API key</b> (ou <b>Criar chave de API</b>) e copie a chave (começa com <code>AIza</code>).</li>
      <li>Cole no campo desta página e clique em <b>Testar e salvar</b>.</li>
    </ol>
    <p>Já tem uma chave do Gemini em outro projeto? Pode usar a mesma.</p>
    <p className="help-note">A chave fica só neste navegador e vai direto para o Google. Na cota grátis, o Google pode usar o que é enviado para melhorar os modelos. Se a chave tiver restrição de site no Google Cloud, adicione <code>raniere3000-tech.github.io</code>.</p>
  </>},
  app_google:{titulo:'YouTube: criar o acesso para postar (no mesmo projeto da agendinha)',corpo:<>
    <ol>
      <li>Abra o <L href="https://console.cloud.google.com/">Google Cloud</L> e selecione o <b>projeto da agendinha</b> no topo.</li>
      <li>Em <b>APIs e serviços → Biblioteca</b>, procure <b>YouTube Data API v3</b> e clique em <b>Ativar</b>.</li>
      <li>Em <L href="https://console.cloud.google.com/auth/audience">Google Auth Platform → Público-alvo</L>: tipo <b>Externo</b>. Clique em <b>Publicar app</b> (Em produção). Se ficar em "Teste", o login vence a cada 7 dias.</li>
      <li>Em <L href="https://console.cloud.google.com/auth/clients">Clientes</L> → <b>Criar cliente</b> → tipo <b>Aplicativo da Web</b>. Em <b>URIs de redirecionamento autorizados</b>, cole o <b>endereço de retorno</b> que aparece na aba Agendar posts.</li>
      <li>Copie o <b>ID do cliente</b> e a <b>Chave secreta do cliente</b> e cole no card do YouTube. Clique em <b>Entrar com minha conta</b>. Como o app é seu e não verificado, o Google mostra um aviso: clique em <b>Avançado → Acessar</b>.</li>
    </ol>
    <p><b>Importante:</b> projetos não verificados pelo YouTube sobem os vídeos como <b>privados</b>. Para sair público sozinho, peça a auditoria gratuita no <L href="https://support.google.com/youtube/contact/yt_api_form">formulário da API do YouTube</L> (leva alguns dias). Até lá, o vídeo sobe privado e você o deixa público no YouTube Studio.</p>
    <p className="help-note">O ID e a chave secreta ficam guardados só no seu servidor (celular), não neste navegador.</p>
  </>},
  app_meta:{titulo:'Facebook + Instagram: criar o app da Meta',corpo:<>
    <p>Precisa de: Instagram <b>profissional</b> (Criador ou Empresa) <b>ligado a uma Página</b> do Facebook.</p>
    <ol>
      <li>Entre em <L href="https://developers.facebook.com/apps/">developers.facebook.com/apps</L> → <b>Criar app</b>. Escolha o caso de uso para <b>gerenciar Páginas</b> / tipo <b>Empresa</b>.</li>
      <li>Adicione o produto <b>Login do Facebook</b>. Em <b>Configurações</b> dele, cole o <b>endereço de retorno</b> (aba Agendar posts) em <b>URIs de redirecionamento do OAuth válidos</b> e salve.</li>
      <li>Em <b>Permissões / Casos de uso</b>, adicione: <code>pages_show_list</code>, <code>pages_read_engagement</code>, <code>pages_manage_posts</code>, <code>instagram_basic</code>, <code>instagram_content_publish</code>, <code>business_management</code>.</li>
      <li>Em <b>Configurações do app → Básico</b>, copie o <b>ID do app</b> e a <b>Chave secreta</b> e cole no card do Facebook + Instagram.</li>
      <li>Clique em <b>Entrar com minha conta</b> e, na tela da Meta, <b>marque sua Página e o Instagram</b>.</li>
    </ol>
    <p>Pode deixar o app em <b>modo de desenvolvimento</b>: para você (dono do app) tudo funciona, sem precisar de análise da Meta.</p>
  </>},
  app_tiktok:{titulo:'TikTok: criar o app de desenvolvedor',corpo:<>
    <ol>
      <li>Entre em <L href="https://developers.tiktok.com/apps/">developers.tiktok.com</L> com sua conta e clique em <b>Connect an app</b> / <b>Create app</b>.</li>
      <li>Adicione os produtos <b>Login Kit</b> e <b>Content Posting API</b>.</li>
      <li>No Login Kit, em <b>Redirect URI</b> (Web), cole o <b>endereço de retorno</b> (aba Agendar posts). Marque os escopos <code>user.info.basic</code>, <code>video.upload</code> e <code>video.publish</code>.</li>
      <li>Em <b>Sandbox</b>, adicione sua conta do TikTok em <b>Target users</b> (assim funciona sem análise).</li>
      <li>Copie o <b>Client key</b> e o <b>Client secret</b>, cole no card do TikTok e clique em <b>Entrar com minha conta</b>.</li>
    </ol>
    <p><b>Como o vídeo chega:</b> no modo <b>rascunhos</b>, ele aparece nas notificações/rascunhos do app do TikTok na hora marcada e você só toca em <b>Postar</b>. O modo <b>direto</b> publica sozinho, mas sem aprovação do TikTok o vídeo fica como "Só eu".</p>
  </>},
  cookies:{titulo:'YouTube pede login no servidor',corpo:<>
    <p>Às vezes o YouTube desconfia do servidor (principalmente na internet de celular) e pede para "confirmar que não é robô". Para resolver, você entrega ao servidor os cookies de uma conta do YouTube logada no navegador. Faça no computador:</p>
    <ol>
      <li>No Chrome do computador, instale a extensão <L href="https://chromewebstore.google.com/search/Get%20cookies.txt%20LOCALLY">Get cookies.txt LOCALLY</L>.</li>
      <li>Abra uma <b>janela anônima</b> (Ctrl+Shift+N), permita a extensão nela, entre no <L href="https://www.youtube.com">youtube.com</L> e faça login. De preferência use uma conta secundária, não a do seu canal.</li>
      <li>Com o YouTube aberto, clique na extensão e em <b>Export</b>. Ela baixa um arquivo <b>cookies.txt</b>.</li>
      <li>Feche a janela anônima (sem sair da conta, para os cookies continuarem valendo).</li>
      <li>Aqui em Chaves e ajustes, clique em <b>Enviar cookies.txt</b> e escolha o arquivo.</li>
    </ol>
    <p>O arquivo fica só no seu servidor, em uma pasta protegida. Ele dá acesso àquela conta do Google, por isso não mande para ninguém. Se depois de um tempo o erro voltar, os cookies venceram: repita os passos.</p>
    <p>Outra saída sem cookies: baixe o vídeo por outro app e use <b>Enviar arquivo</b>. Os trechos marcados no link continuam valendo.</p>
  </>},
  kwai:{titulo:'Kwai',corpo:<>
    <p>O Kwai não oferece API para postar de fora do app. Marque o Kwai ao agendar: na hora, o post aparece na agenda com <b>Baixar vídeo</b>. Baixe no celular, poste pelo app do Kwai e clique em <b>Já postei no Kwai</b> para ficar registrado.</p>
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
