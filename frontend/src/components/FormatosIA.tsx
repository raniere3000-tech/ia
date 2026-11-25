import { useState } from 'react';
import { Save } from 'lucide-react';
import { useApp } from '../state';
import { formatosIA, salvarFormatoIA, type FormatoIA, type ConfigFormato } from '../lib/criativo';
import type { Briefing } from '../lib/api';
import { useCfg, useServidor, erroTexto } from './Servidor2';

/** Configurações de formato na biblioteca existente; não produz nem troca o tema. */
export default function FormatosIA({b,set}:{b:Partial<Briefing>;set:(campos:Partial<Briefing>)=>void}){
  const cfg=useCfg(); const {toast}=useApp();
  const r=useServidor(formatosIA,0,[]);
  const [selecionado,selecionar]=useState<FormatoIA|null>(null);
  const [nome,setNome]=useState(''); const [busy,setBusy]=useState(false);
  if(!r.dados?.habilitado) return null;
  const escolher=(id:string)=>{
    const x=[...r.dados!.padroes,...r.dados!.salvos].find(x=>x.id===id)||null;
    selecionar(x);setNome(x?.nome||'');
    if(x) set(x.dados.briefing);
  };
  const salvar=async()=>{
    if(!selecionado||!nome.trim()) return;
    const campos:ConfigFormato={tipo:b.tipo||'curiosidades',estilo:b.estilo||'quadro_branco',
      duracao_alvo:b.duracao_alvo||45,cenas_qtd:b.cenas_qtd||6,ritmo:b.ritmo||'agil',formato:b.formato||'9:16'};
    setBusy(true);
    try{
      const x=await salvarFormatoIA(cfg,selecionado,nome.trim(),campos);
      selecionar(x);r.recarregar();toast(`Formato salvo (versão ${x.versao}).`,'ok');
    }catch(e){toast(erroTexto(e),'erro');r.recarregar();}
    finally{setBusy(false);}
  };
  return <details className="mt"><summary>Formatos de vídeo reutilizáveis</summary>
    <label>Escolher formato<select value={selecionado?.id||''} onChange={e=>escolher(e.target.value)}>
      <option value="">Configuração manual</option>
      <optgroup label="Pontos de partida">{r.dados.padroes.map(x=><option key={x.id} value={x.id}>{x.nome}</option>)}</optgroup>
      {!!r.dados.salvos.length&&<optgroup label="Meus formatos">{r.dados.salvos.map(x=><option key={x.id} value={x.id}>{x.nome} (v{x.versao})</option>)}</optgroup>}
    </select></label>
    {selecionado&&<>
      <small className="hint">{selecionado.descricao} Ajuste duração, cenas, ritmo, tipo e visual nos campos do vídeo e salve para reutilizar.</small>
      <label>Nome do formato<input maxLength={80} value={nome} onChange={e=>setNome(e.target.value)}/></label>
      <button type="button" className="subtle sm" disabled={busy||!nome.trim()} onClick={salvar}><Save size={13}/> {selecionado.versao?'Atualizar formato':'Salvar formato'}</button>
      <small className="hint">Escolher um formato preserva seu tema, voz e modo de aprovação. O vídeo segue sendo criado pelos botões habituais.</small>
    </>}
  </details>;
}
