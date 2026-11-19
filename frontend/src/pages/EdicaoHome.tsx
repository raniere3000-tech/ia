import { Film, FolderOpen, Search, Clapperboard, LayoutTemplate, Captions, Mic, Radio, Plus, PlayCircle } from 'lucide-react';
import { useApp, type Tab } from '../state';
import Continuar, { trabalhosSalvos } from '../components/Continuar';

type Ent={Icon:typeof Film;t:string;d:string;to:Tab;onde?:string};
const FERRAMENTAS:Ent[]=[
  {Icon:Film,t:'Montagem manual',d:'Timeline com quadros, narração, trilha, cenas, transições, legendas e efeitos. Grava e exporta o vídeo.',to:'manual',onde:'No navegador'},
  {Icon:Search,t:'Radar de vídeos',d:'Pesquise temas e canais no YouTube e veja os vídeos em alta.',to:'radar',onde:'Precisa da chave do YouTube'},
  {Icon:Clapperboard,t:'Gerar cortes',d:'Envie um vídeo seu ou autorizado e escolha os melhores trechos com nota.',to:'cortes',onde:'No navegador'},
  {Icon:LayoutTemplate,t:'Templates',d:'Composição, tarjas, marca e exportação usados na edição e pelos agentes.',to:'templates'},
  {Icon:Captions,t:'Legendas e efeitos',d:'Visual padrão das legendas e efeito aplicado nos cortes.',to:'estilos'},
  {Icon:Mic,t:'Áudio e vozes',d:'Atalho para o Estúdio de vozes: teste, compare e baixe as narrações.',to:'vozes'},
  {Icon:Radio,t:'Live',d:'Grave uma live em blocos e transforme os melhores momentos em cortes.',to:'live',onde:'Precisa do servidor'},
  {Icon:FolderOpen,t:'Meus projetos',d:'Tudo o que está salvo no servidor, com versões e filtros.',to:'projetos',onde:'Precisa do servidor'},
];

/** Estúdio de Edição: entrada da criação e montagem manual. Cada botão abre a tela que já existia. */
export default function EdicaoHome(){
  const {go,projeto}=useApp();
  const temSalvo=trabalhosSalvos(projeto.clips.filter(c=>!c.descartado).length).some(x=>x.to!=='video');
  const ir=(t:Tab)=>go(t,'','edicao');
  return <div className="hub">
    <div className="hub-acoes">
      <button className="hub-acao primaria" onClick={()=>ir('manual')}><Plus size={20}/><b>Novo projeto</b><small>Começa uma montagem manual</small></button>
      <button className="hub-acao" onClick={()=>ir(temSalvo?'manual':'projetos')}><PlayCircle size={20}/><b>Continuar projeto</b><small>{temSalvo?'Volta ao que ficou salvo neste aparelho':'Abre Meus projetos'}</small></button>
      <button className="hub-acao" onClick={()=>ir('manual')}><Film size={20}/><b>Abrir editor</b><small>Montagem manual com timeline</small></button>
      <button className="hub-acao" onClick={()=>ir('radar')}><Search size={20}/><b>Radar e Cortes</b><small>Achar vídeos e gerar cortes</small></button>
    </div>
    <Continuar filtro={['cortes','manual','vozes']} area="edicao"/>
    <div className="inicio-entradas">{FERRAMENTAS.map(e=><button key={e.t} className="inicio-entrada" onClick={()=>ir(e.to)}><span className="step-icon"><e.Icon size={22}/></span><h3>{e.t}</h3><p>{e.d}</p>{e.onde&&<small>{e.onde}</small>}</button>)}</div>
  </div>;
}
