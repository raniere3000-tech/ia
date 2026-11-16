import { useState } from 'react';
import { Smartphone, KeyRound, Loader2, Trash2, Link2, Copy, HardDrive, Stethoscope, Archive, CheckCircle2, AlertTriangle } from 'lucide-react';
import { useApp } from '../state';
import { HelpButton } from './Help';
import { useCfg, useServidor, erroTexto } from './Servidor2';
import { entrarComSenha, gerarCodigo, listarAparelhos, desconectar, diagnostico, fazerBackup, testarBackup, lerMidiasBackup, salvarMidiasBackup, fazerMidiasBackup, testarMidiasBackup, horaTexto, duracaoTexto } from '../lib/api';

export function AparelhosCard(){
  const {settings,setSettings,toast}=useApp(); const cfg=useCfg();
  const [senha,setSenha]=useState(settings.servidorToken||'');
  const [busy,setBusy]=useState('');
  const [codigo,setCodigo]=useState<{codigo:string;expira:number}|null>(null);
  const lista=useServidor(c=>settings.servidorSessao||settings.servidorToken?listarAparelhos(c):Promise.resolve({aparelhos:[]}),0,[settings.servidorSessao]);
  if(!settings.servidor) return null;
  const link=codigo?`${location.origin}${location.pathname}?servidor=${encodeURIComponent(settings.servidor)}${settings.servidorCanal?'&canal='+settings.servidorCanal:''}#par=${codigo.codigo}`:'';
  return <section className="panel config-card">
    <div className="config-icon srv"><Smartphone size={22}/></div>
    <div className="config-body">
     <div className="section-head"><h2>Aparelhos conectados <HelpButton topic="aparelhos"/></h2>{settings.servidorSessao?<span className="tag ok">este aparelho conectado</span>:<span className="tag warn">usando a senha antiga</span>}</div>
     {!settings.servidorSessao&&<>
      <p className="subtitle">Conecte este aparelho com a senha do servidor uma vez. Depois ele usa uma entrada própria e a senha deixa de ficar guardada aqui.</p>
      <div className="key-row"><div className="input-wrap"><KeyRound size={16}/><input type="password" value={senha} onChange={e=>setSenha(e.target.value)} placeholder="Senha do servidor (aparece no Termux)" autoComplete="off"/></div>
       <button className="primary" disabled={!senha||!!busy} onClick={async()=>{ setBusy('entrar'); try{ const s=await entrarComSenha(cfg,senha); setSettings({servidorSessao:s.sessao,servidorAnuncio:s.anuncio,servidorToken:''}); toast(`Aparelho conectado como "${s.nome}".`,'ok'); lista.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } }}>{busy==='entrar'?<Loader2 size={15} className="spin"/>:<CheckCircle2 size={15}/>} Conectar este aparelho</button></div>
     </>}
     {(settings.servidorSessao||settings.servidorToken)&&<>
      <ul className="aparelhos">{(lista.dados?.aparelhos||[]).map(a=><li key={a.id}><Smartphone size={15}/><b>{a.nome}</b>{a.atual&&<span className="tag ok">este</span>}<small className="muted">visto {horaTexto(a.visto)} • entrou por {a.origem==='pareamento'?'código':'senha'}</small>
        {!a.atual&&<button className="subtle sm" onClick={async()=>{ if(!window.confirm(`Desconectar "${a.nome}"? Ele precisará de um código novo para voltar.`)) return; try{ await desconectar(cfg,a.id); lista.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); } }}><Trash2 size={14}/> Desconectar</button>}</li>)}</ul>
      <div className="row-gap left">
       <button className="subtle" disabled={!!busy} onClick={async()=>{ setBusy('cod'); try{ setCodigo(await gerarCodigo(cfg)); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } }}><Link2 size={15}/> Conectar outro aparelho</button>
       {settings.servidorSessao&&<button className="link-btn" onClick={()=>{ if(window.confirm('Desconectar ESTE aparelho do servidor?')){ desconectar(cfg,lista.dados?.aparelhos.find(a=>a.atual)?.id||'').catch(()=>{}); setSettings({servidorSessao:'',servidorAnuncio:''}); } }}>Desconectar este aparelho</button>}
      </div>
      {codigo&&<div className="codigo-par">
       <p>Código: <b className="mono grande">{codigo.codigo}</b> • vale até {new Date(codigo.expira*1000).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}, uma vez só.</p>
       <p className="hint">Abra este link no aparelho novo (mande para você mesmo; não compartilhe):</p>
       <div className="key-row"><input readOnly value={link} onFocus={e=>e.target.select()}/><button className="subtle" onClick={()=>{ navigator.clipboard?.writeText(link).then(()=>toast('Link copiado.','ok'),()=>{}); }}><Copy size={15}/> Copiar</button></div>
       <p className="hint">O endereço do servidor no link muda quando o Termux reinicia; o código vence em 10 minutos de qualquer jeito.</p>
      </div>}
     </>}
    </div>
  </section>;
}

/** Backup opcional das mídias (vídeos finais, narrações, fotos): incremental, cada arquivo guardado uma vez pelo sha256. */
function BackupMidias(){
  const {toast}=useApp(); const cfg=useCfg();
  const m=useServidor(lerMidiasBackup,0);
  const [busy,setBusy]=useState(''); const [dest,setDest]=useState<string|null>(null);
  const x=m.dados; if(!x) return m.erro?<p className="hint bad">{m.erro}</p>:null;
  const run=async(k:string,f:()=>Promise<unknown>,ok:(r:any)=>[string,'ok'|'erro'])=>{ setBusy(k); try{ const r=await f(); const [t,tp]=ok(r); toast(t,tp); m.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } };
  const cats=x.config.categorias;
  return <div className="midias-bk mt">
    <div className="field-label">Backup das mídias (opcional)</div>
    <label className="check"><input type="checkbox" checked={x.config.ligado} onChange={e=>run('cfg',()=>salvarMidiasBackup(cfg,{ligado:e.target.checked}),()=>[e.target.checked?'Backup diário das mídias ligado.':'Backup das mídias desligado.','ok'])}/> Fazer todo dia, junto com o backup do banco</label>
    <div className="chips">{Object.entries(x.categorias).map(([k,c])=>{ const on=cats.includes(k); return <button key={k} className={'chip '+(on?'on':'')} aria-pressed={on} onClick={()=>run('cfg',()=>salvarMidiasBackup(cfg,{categorias:on?cats.filter(y=>y!==k):[...cats,k]}),()=>['Salvo.','ok'])}>{c.nome} · {c.arquivos} ({c.mb.toFixed(0)} MB)</button>; })}</div>
    <p className="hint">{x.ja_copiados} de {x.escolhidos} arquivos já estão no backup. Falta copiar {x.falta_mb.toFixed(0)} MB; o destino tem {(x.livre_mb/1024).toFixed(1)} GB livres.</p>
    {x.mesmo_aparelho&&<p className="hint warn">O backup está no mesmo celular. Ele protege contra arquivo apagado ou estragado, mas não contra perder o aparelho. Para mais segurança, use uma pasta do cartão ou do armazenamento (ex.: /sdcard/EstudioClip), depois de rodar termux-setup-storage.</p>}
    <div className="ag-add"><input value={dest??x.config.destino} onChange={e=>setDest(e.target.value)} placeholder={x.destino}/><button className="subtle sm" disabled={!!busy||dest===null} onClick={()=>run('cfg',()=>salvarMidiasBackup(cfg,{destino:dest||''}),()=>{ setDest(null); return ['Pasta do backup salva.','ok']; })}>Usar esta pasta</button></div>
    <div className="row-gap left mt">
     <button className="subtle sm" disabled={!!busy||!cats.length} onClick={()=>run('fz',()=>fazerMidiasBackup(cfg),(r)=>[`Backup das mídias: ${r.novos} novo(s), ${r.ja_existiam} já estavam lá${r.faltando.length?`, ${r.faltando.length} sem arquivo`:''}.`,r.faltando.length?'erro':'ok'])}>{busy==='fz'?<Loader2 size={14} className="spin"/>:<Archive size={14}/>} Fazer agora</button>
     <button className="subtle sm" disabled={!!busy||!x.ultimos.length} onClick={()=>run('ts',()=>testarMidiasBackup(cfg),(r)=>[r.ok?`Restauração de teste: ${r.conferidos} arquivo(s) conferidos, tudo certo.`:`Problemas: ${r.problemas.slice(0,3).join('; ')}`,r.ok?'ok':'erro'])}>Testar restauração</button>
    </div>
  </div>;
}

export function DiagnosticoCard(){
  const {settings,toast}=useApp(); const cfg=useCfg();
  const d=useServidor(diagnostico,0,[settings.servidorSessao]);
  const [busy,setBusy]=useState('');
  if(!settings.servidor) return null;
  const x=d.dados;
  return <section className="panel config-card">
    <div className="config-icon srv"><Stethoscope size={22}/></div>
    <div className="config-body">
     <div className="section-head"><h2>Servidor do celular: diagnóstico e backups</h2></div>
     {d.erro&&<p className="hint bad">{d.erro}</p>}
     {x&&<>
      <ul className="diag">
       <li>{x.ffmpeg?<CheckCircle2 size={14} className="ok"/>:<AlertTriangle size={14} className="bad"/>} FFmpeg {x.ffmpeg?'instalado':'faltando (pkg install ffmpeg)'}</li>
       <li><HardDrive size={14}/> {(x.livre_mb/1024).toFixed(1)} GB livres (mínimo para render: {x.minimo_mb} MB) • banco {(x.banco.tamanho/1048576).toFixed(1)} MB</li>
       <li>Trabalhos: {Object.entries(x.jobs).map(([k,v])=>`${k} ${v}`).join(' • ')||'nenhum'}</li>
       {x.falhas_recentes.length>0&&<li>Últimas falhas: {x.falhas_recentes.slice(0,3).map(f=>`${f.acao} (${horaTexto(f.t)})`).join(' • ')}</li>}
      </ul>
      <div className="field-label">Backups (banco e configurações; os vídeos não entram)</div>
      <ul className="aparelhos">{x.backups.map(b=><li key={b.arquivo}><Archive size={14}/> {b.arquivo} • {(b.tamanho/1024).toFixed(0)} KB • há {duracaoTexto(Date.now()/1000-b.criado)}
       <button className="subtle sm" disabled={!!busy} onClick={async()=>{ setBusy(b.arquivo); try{ const r=await testarBackup(cfg,b.arquivo); toast(r.ok?`Backup conferido: banco íntegro, ${r.projetos} projeto(s).`:'Backup com problema: '+r.erros.join(', '),r.ok?'ok':'erro'); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } }}>Testar restauração</button></li>)}</ul>
      <button className="subtle" disabled={!!busy} onClick={async()=>{ setBusy('bk'); try{ const r=await fazerBackup(cfg); toast(`Backup feito: ${r.arquivo}.`,'ok'); d.recarregar(); }catch(e){ toast(erroTexto(e),'erro'); }finally{ setBusy(''); } }}>{busy==='bk'?<Loader2 size={15} className="spin"/>:<Archive size={15}/>} Fazer backup agora</button>
      <p className="hint">Backup diário automático, os 7 últimos ficam em ~/.estudioclip/backups no celular. "Testar restauração" abre a cópia numa pasta de teste e confere; não mexe nos dados reais.</p>
     </>}
     <BackupMidias/>
    </div>
  </section>;
}
