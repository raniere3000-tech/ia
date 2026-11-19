import { Sparkles, Users, CalendarRange, Palette, Mic, Film, FolderOpen } from 'lucide-react';
import { useApp, type Tab } from '../state';
import { useServidor } from '../components/Servidor2';
import { catalogo } from '../lib/api';
import { Prontidao } from '../components/Prontidao';
import Continuar from '../components/Continuar';

type Ent={Icon:typeof Film;t:string;d:string;to:Tab};
const PRINCIPAIS:Ent[]=[
  {Icon:Sparkles,t:'Criar com IA',d:'Ideia ou roteiro, estilo, duração, voz e personagem. O Agente 3 faz o vídeo e você revisa.',to:'ia'},
  {Icon:Users,t:'Séries e personagens',d:'Personagens, cenários, temporadas e episódios com o mesmo elenco.',to:'series'},
  {Icon:CalendarRange,t:'Produção em lote',d:'Vários vídeos de uma vez: agora, em data marcada ou todo dia.',to:'automatico'},
  {Icon:Palette,t:'Biblioteca criativa',d:'Estilos de animação reais (prontos, beta ou indisponíveis), personagens e cenários.',to:'galeria'},
];
const OUTRAS:Ent[]=[
  {Icon:Mic,t:'Vozes',d:'Estúdio de vozes do Gemini.',to:'vozes'},
  {Icon:Film,t:'Animado no navegador',d:'Vídeo animado montado no próprio navegador.',to:'video'},
  {Icon:FolderOpen,t:'Projetos IA',d:'Vídeos do Agente 3 salvos no servidor.',to:'projetos'},
];

function ProntidaoIA(){ const cat=useServidor(catalogo); return <Prontidao cat={cat.dados}/>; }

/** Estúdio IA: criação a partir de uma ideia. Cada botão abre a tela que já existia. */
export default function EstudioIAHome(){
  const {go,settings}=useApp();
  const ir=(t:Tab)=>go(t,'','estudio-ia');
  return <div className="hub">
    <div className="hub-acoes">{PRINCIPAIS.map((e,i)=><button key={e.t} className={'hub-acao'+(i===0?' primaria':'')} onClick={()=>ir(e.to)}><e.Icon size={20}/><b>{e.t}</b><small>{e.d}</small></button>)}</div>
    {settings.servidor&&<ProntidaoIA/>}
    <Continuar filtro={['video','vozes']} area="estudio-ia"/>
    <div className="inicio-entradas">{OUTRAS.map(e=><button key={e.t} className="inicio-entrada" onClick={()=>ir(e.to)}><span className="step-icon"><e.Icon size={22}/></span><h3>{e.t}</h3><p>{e.d}</p></button>)}</div>
  </div>;
}
