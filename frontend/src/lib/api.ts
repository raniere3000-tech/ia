// Cliente da API /api/v1 do servidor do celular (Termux): sessão do aparelho, projetos, fila, Agente 3 e aprovações.
// A sessão do aparelho vai só no cabeçalho X-Sessao. Nada de senha ou sessão em link.

export type CfgSrv = {servidor:string;servidorToken:string};

let SESSAO='';
/** Chamado pelo App quando a sessão do aparelho muda (entrar, parear, sair). */
export function definirSessao(s:string){ SESSAO=s||''; }
export function temSessao(){ return !!SESSAO; }

/** Cabeçalhos de autenticação: sessão do aparelho e, se ainda houver, a senha antiga (compatibilidade). */
export function cabAuth(token=''):Record<string,string>{
  const h:Record<string,string>={};
  if(SESSAO) h['X-Sessao']=SESSAO;
  if(token) h['X-Token']=token;
  return h;
}

export class ErroApi extends Error{
  status:number; dados:Record<string,unknown>;
  constructor(status:number,msg:string,dados:Record<string,unknown>={}){ super(msg); this.status=status; this.dados=dados; }
}

const base=(u:string)=>u.trim().replace(/\/+$/,'');

export async function api<T=Record<string,unknown>>(cfg:CfgSrv,metodo:string,caminho:string,corpo?:unknown,extra?:Record<string,string>):Promise<T>{
  if(!cfg.servidor) throw new ErroApi(0,'Ligue o servidor do celular em Ajustes primeiro.');
  let r:Response;
  const h:Record<string,string>={...cabAuth(cfg.servidorToken),...(extra||{})};
  let body:BodyInit|undefined;
  if(corpo instanceof Blob||corpo instanceof ArrayBuffer){ body=corpo as BodyInit; h['Content-Type']='application/octet-stream'; }
  else if(corpo!==undefined){ body=JSON.stringify(corpo); h['Content-Type']='application/json'; }
  try{ r=await fetch(base(cfg.servidor)+caminho,{method:metodo,headers:h,body}); }
  catch{ throw new ErroApi(0,'Sem conexão com o servidor do celular. Ele está ligado?'); }
  let dados:Record<string,unknown>={};
  try{ dados=await r.json(); }catch{ /* resposta sem json */ }
  if(!r.ok) throw new ErroApi(r.status,String(dados.detail||`O servidor respondeu com erro ${r.status}.`),dados);
  return dados as T;
}

/** Endereço completo de um link assinado devolvido pelo servidor (/api/v1/assets/...?exp=&sig=). */
export const urlServidor=(cfg:CfgSrv,caminho:string)=>caminho?base(cfg.servidor)+caminho:'';

// ---------------------------------------------------------------- aparelhos
export type Sessao={sessao:string;id:string;nome:string;anuncio:string;prova?:string};
export type Aparelho={id:string;nome:string;criado:number;visto:number;origem:string;atual:boolean};

export function nomeDoAparelho(){
  const ua=navigator.userAgent;
  const so=/Android/i.test(ua)?'Android':/iPhone|iPad/i.test(ua)?'iPhone':/Windows/i.test(ua)?'Windows':/Mac/i.test(ua)?'Mac':/Linux/i.test(ua)?'Linux':'Aparelho';
  const nav=/Edg\//.test(ua)?'Edge':/Chrome\//.test(ua)?'Chrome':/Firefox\//.test(ua)?'Firefox':/Safari\//.test(ua)?'Safari':'navegador';
  return `${so} • ${nav}`;
}

export const entrarComSenha=(cfg:CfgSrv,senha:string)=>api<Sessao>({...cfg,servidorToken:''},'POST','/api/v1/sessao/login',{senha,nome:nomeDoAparelho()});
export const gerarCodigo=(cfg:CfgSrv)=>api<{codigo:string;expira:number;minutos:number}>(cfg,'POST','/api/v1/pareamento/iniciar',{nome:'Aparelho novo'});
export const listarAparelhos=(cfg:CfgSrv)=>api<{aparelhos:Aparelho[]}>(cfg,'GET','/api/v1/aparelhos');
export const desconectar=(cfg:CfgSrv,id:string)=>api(cfg,'DELETE','/api/v1/aparelhos/'+id);

async function hmacHex(chave:string,msg:string){
  const k=await crypto.subtle.importKey('raw',new TextEncoder().encode(chave),{name:'HMAC',hash:'SHA-256'},false,['sign']);
  const s=new Uint8Array(await crypto.subtle.sign('HMAC',k,new TextEncoder().encode(msg)));
  return Array.from(s,b=>b.toString(16).padStart(2,'0')).join('');
}
const igual=(a:string,b:string)=>{ if(a.length!==b.length) return false; let d=0; for(let i=0;i<a.length;i++) d|=a.charCodeAt(i)^b.charCodeAt(i); return d===0; };

/** Conecta este aparelho com o código de uso único. Confere que o servidor conhece o código (um servidor falso não conhece). */
export async function parear(url:string,codigo:string):Promise<Sessao>{
  if(!crypto?.subtle) throw new Error('Abra o site pelo endereço https para conectar o aparelho.');
  const limpo=codigo.toUpperCase().replace(/[^A-Z0-9]/g,'');
  const nonce=Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');
  const s=await api<Sessao>({servidor:url,servidorToken:''},'POST','/api/v1/pareamento/completar',{codigo:limpo,nonce,nome:nomeDoAparelho()});
  const certo=await hmacHex(limpo,nonce);
  if(!s.prova||!igual(certo,s.prova)) throw new Error('Este servidor não confirmou o código. Não conectei (pode ser um endereço falso).');
  return s;
}

export async function assinaturaHex(chave:string,msg:string){ return hmacHex(chave,msg); }

// ---------------------------------------------------------------- projetos
export type ProjetoMeta={id:string;titulo:string;tipo:string;modo:string;status:string;revisao:number;criado:number;atualizado:number;dispositivo:string;origem:string};
export type ProjetoSrv=ProjetoMeta&{dados:Record<string,unknown>;links?:Record<string,string>};

export const listarProjetos=(cfg:CfgSrv,tipo='')=>api<{projetos:ProjetoMeta[];livre_mb:number}>(cfg,'GET','/api/v1/projetos'+(tipo?'?tipo='+tipo:''));
export const obterProjeto=(cfg:CfgSrv,id:string)=>api<ProjetoSrv>(cfg,'GET','/api/v1/projetos/'+id);
export const criarProjeto=(cfg:CfgSrv,d:{tipo:string;titulo:string;dados:unknown;origem_chave?:string;modo?:string})=>api<ProjetoSrv&{duplicado?:boolean}>(cfg,'POST','/api/v1/projetos',d);
export const salvarProjeto=(cfg:CfgSrv,id:string,revisao:number,d:{dados?:unknown;titulo?:string;status?:string})=>api<ProjetoMeta>(cfg,'PATCH','/api/v1/projetos/'+id,{...d,revisao});
export const apagarProjeto=(cfg:CfgSrv,id:string)=>api(cfg,'DELETE','/api/v1/projetos/'+id);
export const versoesProjeto=(cfg:CfgSrv,id:string)=>api<{versoes:{revisao:number;criado:number;dispositivo:string;origem:string;tamanho?:number}[]}>(cfg,'GET',`/api/v1/projetos/${id}/versoes`);
export const restaurarVersao=(cfg:CfgSrv,id:string,revisao:number)=>api<ProjetoMeta>(cfg,'POST',`/api/v1/projetos/${id}/restaurar`,{revisao});
export const duplicarProjeto=(cfg:CfgSrv,id:string)=>api<ProjetoMeta>(cfg,'POST',`/api/v1/projetos/${id}/duplicar`,{});
export async function baixarExportacao(cfg:CfgSrv,id:string,nome:string){
  const r=await fetch(base(cfg.servidor)+`/api/v1/projetos/${id}/exportar`,{headers:cabAuth(cfg.servidorToken)});
  if(!r.ok) throw new Error('Não consegui exportar o projeto.');
  const a=document.createElement('a'); a.href=URL.createObjectURL(await r.blob()); a.download=(nome||'projeto').replace(/[^\w\- ]+/g,'').slice(0,60)+'.zip'; a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href),4000);
}

// ---------------------------------------------------------------- arquivos (envio em pedaços, sem repetir o que o servidor já tem)
export type AssetInfo={id:string;nome:string;mime:string;tamanho:number;sha256:string};
export async function sha256Hex(b:Blob){
  const d=new Uint8Array(await crypto.subtle.digest('SHA-256',await b.arrayBuffer()));
  return Array.from(d,x=>x.toString(16).padStart(2,'0')).join('');
}
const PEDACO=4*1024*1024;
export async function enviarArquivo(cfg:CfgSrv,b:Blob,nome:string,projeto='',sha?:string,progresso?:(f:number)=>void):Promise<AssetInfo>{
  const s=sha||await sha256Hex(b);
  const mime=(b.type||'application/octet-stream').split(';')[0];
  let r=await api<{pronto:boolean;asset?:AssetInfo;upload?:string;recebido?:number}>(cfg,'POST','/api/v1/uploads',{sha256:s,tamanho:b.size,mime,nome,projeto});
  if(r.pronto&&r.asset) return r.asset;
  let off=r.recebido||0;
  while(off<b.size){
    const fim=Math.min(b.size,off+PEDACO);
    let tent=0;
    for(;;){
      try{ const x=await api<{recebido:number}>(cfg,'PUT',`/api/v1/uploads/${r.upload}?offset=${off}`,b.slice(off,fim)); off=x.recebido; break; }
      catch(e){ if(e instanceof ErroApi&&e.status===409&&typeof e.dados.recebido==='number'){ off=e.dados.recebido as number; break; }
        if(++tent>=4) throw e; await new Promise(z=>setTimeout(z,1500*tent)); }
    }
    progresso?.(off/b.size);
  }
  r=await api(cfg,'POST',`/api/v1/uploads/${r.upload}/fim`,{});
  return r.asset!;
}
export const assetsExistentes=(cfg:CfgSrv,shas:string[])=>api<Record<string,AssetInfo>>(cfg,'POST','/api/v1/assets/existentes',{sha256:shas});
export async function baixarAsset(cfg:CfgSrv,id:string):Promise<Blob>{
  const r=await fetch(base(cfg.servidor)+'/api/v1/assets/'+id,{headers:cabAuth(cfg.servidorToken)});
  if(!r.ok) throw new Error('Não consegui baixar um arquivo do servidor.');
  return r.blob();
}

// ---------------------------------------------------------------- fila e capacidade
export type Job={id:string;tipo:string;agente:string;titulo:string;status:string;etapa:string;progresso:number;projeto:string;run_at:number;criado:number;iniciado:number|null;terminado:number|null;
  decorrido:number;tentativas:number;max_tentativas:number;erro:string|null;pausado:number;recurso:string;prioridade:number;
  posicao?:number|null;inicio_previsto?:number|null;fim_previsto?:number|null;restante?:number|null;estimativa_medida?:boolean;decorrido_total?:number;dados?:Record<string,unknown>};
export type Fila={jobs:Job[];contagem:Record<string,number>;agora:number;limites:Record<string,number>};
export const lerFila=(cfg:CfgSrv,filtro='')=>api<Fila>(cfg,'GET','/api/v1/fila'+(filtro?'?filtro='+filtro:''));
export const acaoFila=(cfg:CfgSrv,id:string,acao:'pausar'|'retomar'|'cancelar'|'tentar'|'reagendar',corpo:unknown={})=>api<Job>(cfg,'POST',`/api/v1/fila/${id}/${acao}`,corpo);
export type Capacidade={limites:Record<string,number>;rodando:{id:string;tipo:string}[];cpus:number|null;disco_livre_mb:number|null;carga_cpu:number|null;memoria:{total_mb:number;livre_mb:number}|null;bateria:number|null;temperatura:number|null};
export const lerCapacidade=(cfg:CfgSrv)=>api<Capacidade>(cfg,'GET','/api/v1/capacidade');

// ---------------------------------------------------------------- Agente 3
export type EstiloInfo={id:string;nome:string;descricao:string;tecnica:string;status:'operacional'|'beta'|'indisponivel';prioridade:string;paleta:string[];precisa_imagem:boolean;servidor:boolean;formatos:string[];custo:string};
export type Plano={id:string;plano:'WS'|'MS'|'CU'|'ECU';camera?:string;foco_x?:number;foco_y?:number;peso?:number;busca?:string;intencao?:string};
export type Problema={tipo:string;severidade:'baixa'|'media'|'alta';descricao:string;correcao:string;cena_id:string;plano_id:string;timecode:string|null};
export type Qualidade={status:'falha_tecnica'|'alerta_visual'|'analise_indisponivel'|'apto_para_revisao_humana';problemas:Problema[];gerado:number;tecnico:{erros:string[];avisos:string[]}};
export type Cena={id:string;planos?:Plano[];busca?:string;titulo:string;texto:string;destaque?:string;numero?:number|null;unidade?:string;personagem?:string;prompt_visual?:string;duracao_alvo?:number;bloqueada?:boolean;elementos?:{rotulo:string;valor:number}[];audio?:{dur:number}|null;clipe?:{dur:number}|null};
export type Briefing={tema:string;nicho:string;publico:string;objetivo:string;idioma:string;tipo:string;descricao:string;origem:string;referencias:string;duracao_alvo:number;formato:string;cenas_qtd:number;
  estilo:string;paleta:string[];voz:string;ritmo?:string;trilha:string;imagens:string;modo_aprovacao:'assistido'|'supervisionado';prioridade:number;orcamento_max:number;max_tentativas:number;
  destinos:{redes:string[];quando:'proximo'|'agora'|'data';data?:number;titulo?:string;legenda?:string};temas:string[]};
export type Catalogo={estilos:EstiloInfo[];vozes:string[];tipos:string[];estados:Record<string,string>;briefing:Briefing;formatos:string[];ffmpeg:boolean;requisitos?:{ffmpeg:boolean;gemini:boolean;email:boolean;pexels:boolean;numpy:boolean};demos:Record<string,{asset:string;segundos:number}>};
export type Ideia={titulo:string;gancho:string;porque:string;tipo:string;fato:boolean;fontes:{titulo:string;url:string}[]};
export type Roteiro={titulo:string;alternativas:string[];gancho:string;publico:string;legenda:string;hashtags:string[];fontes:{titulo:string;url:string}[];cenas:Cena[];avisos?:string[];skills_usadas?:string[]};
export const catalogo=(cfg:CfgSrv)=>api<Catalogo>(cfg,'GET','/api/v1/agente3/catalogo');
export const ideias=(cfg:CfgSrv,b:Partial<Briefing>&{quantidade?:number})=>api<{ideias:Ideia[];radar:{titulo:string;canal:string}[]}>(cfg,'POST','/api/v1/agente3/ideias',b);
export const gerarRoteiro=(cfg:CfgSrv,briefing:Partial<Briefing>,roteiro_texto='',skills:string[]=[])=>api<Roteiro>(cfg,'POST','/api/v1/agente3/roteiro',{briefing,roteiro_texto,skills});
export type Quando={quando:'agora'|'daqui'|'data';minutos?:number;data?:number};
export const novoVideo=(cfg:CfgSrv,d:{briefing:Partial<Briefing>;roteiro?:Roteiro;produzir?:boolean;aprovar_roteiro?:boolean;modo?:string}&Partial<Quando>)=>api<ProjetoSrv>(cfg,'POST','/api/v1/agente3/projetos',d);
export const produzirLote=(cfg:CfgSrv,d:{briefing:Partial<Briefing>;quantidade:number;temas:string[];intervalo_min:number}&Partial<Quando>)=>api<{criados:{projeto:string;job:string;run_at:number}[]}>(cfg,'POST','/api/v1/agente3/lote',d);
export const produzir=(cfg:CfgSrv,id:string,q:Partial<Quando>={})=>api<{job:Job}>(cfg,'POST',`/api/v1/projetos/${id}/produzir`,q);
export const pedirDemo=(cfg:CfgSrv,estilo:string,formato='9:16')=>api<{pronto?:{asset:string;segundos:number};url?:string;job?:Job}>(cfg,'POST',`/api/v1/estilos/${estilo}/demo`,{formato});

export type Rotina={id:string;nome:string;dias:number[];hora:string;quantidade:number;ativo:number;proxima:number|null;briefing:Partial<Briefing>};
export const rotinas=(cfg:CfgSrv)=>api<{rotinas:Rotina[];fuso:string}>(cfg,'GET','/api/v1/rotinas');
export const criarRotina=(cfg:CfgSrv,d:Partial<Rotina>&{ativo?:boolean})=>api<Rotina>(cfg,'POST','/api/v1/rotinas',d);
export const mudarRotina=(cfg:CfgSrv,id:string,d:Partial<Rotina>|{ativo:boolean})=>api<Rotina>(cfg,'PATCH','/api/v1/rotinas/'+id,d);
export const apagarRotina=(cfg:CfgSrv,id:string)=>api(cfg,'DELETE','/api/v1/rotinas/'+id);

// ---------------------------------------------------------------- revisão e aprovação
export type Render={id:string;sha:string;versao:number;duracao:number;validado:boolean;avisos:string[];assets:Record<string,string>;tamanho:number;criado:number;codec:string;largura:number;altura:number};
export type Revisao={projeto:ProjetoSrv;ref:string;links:Record<string,string>;historico:{id:string;render_sha:string;decisao:string;origem:string;por:string;texto:string;criado:number}[];
  contas:{ok:string[];faltam:string[]};estados:Record<string,string>;job:Job|null};
export type Pendente={projeto:string;ref:string;titulo:string;status:string;atualizado:number;tipo:'video'|'roteiro';render:Partial<Render>|null;destinos:Briefing['destinos']};
export const pendentes=(cfg:CfgSrv)=>api<{pendentes:Pendente[]}>(cfg,'GET','/api/v1/aprovacoes');
export const lerRevisao=(cfg:CfgSrv,id:string)=>api<Revisao>(cfg,'GET',`/api/v1/projetos/${id}/revisao`);
export const aprovar=(cfg:CfgSrv,id:string,render_sha:string,destinos?:Partial<Briefing['destinos']>)=>
  api<{ok:boolean;quando?:number;posts:{id:string}[];repetido?:boolean}>(cfg,'POST',`/api/v1/projetos/${id}/aprovar`,{render_sha,destinos},{'Idempotency-Key':`site:${id}:${render_sha}`});
export const pedirCorrecao=(cfg:CfgSrv,id:string,render_sha:string,texto:string)=>api(cfg,'POST',`/api/v1/projetos/${id}/alterar`,{render_sha,texto});
export const rejeitar=(cfg:CfgSrv,id:string,render_sha:string,motivo:string)=>api(cfg,'POST',`/api/v1/projetos/${id}/rejeitar`,{render_sha,motivo});
export const aprovarRoteiro=(cfg:CfgSrv,id:string,revisao?:number)=>api(cfg,'POST',`/api/v1/projetos/${id}/aprovar-roteiro`,{revisao});
export const reenviarEmail=(cfg:CfgSrv,id:string)=>api<{ok:boolean}>(cfg,'POST',`/api/v1/projetos/${id}/reenviar-email`,{});

export type EstadoEmail={ativo:boolean;imap:string;porta:number;remetentes:string[];intervalo:number;remetentes_autorizados:string[];caixa:string;ultimo:number;erro:string;lidos:number;aplicados:number};
export const estadoEmail=(cfg:CfgSrv)=>api<EstadoEmail>(cfg,'GET','/api/v1/email/respostas');
export const salvarEmail=(cfg:CfgSrv,d:Partial<EstadoEmail>)=>api<EstadoEmail>(cfg,'POST','/api/v1/email/respostas',d);
export const lerRespostasAgora=(cfg:CfgSrv)=>api<{ok:boolean;lidos:number;aplicados:number;erro:string}>(cfg,'POST','/api/v1/email/respostas/ler',{});

// ---------------------------------------------------------------- servidor
export type Diagnostico={memoria_mb?:number|null;temperatura?:number|null;motores?:{estilo:string;seg_por_seg?:number;cenas?:number;correcoes_qualidade?:number;falhas_ffmpeg?:number}[];ffmpeg:boolean;livre_mb:number;minimo_mb:number;capacidade:Capacidade;jobs:Record<string,number>;falhas_recentes:{t:number;ator:string;acao:string;recurso:string}[];backups:{arquivo:string;tamanho:number;criado:number}[];banco:{arquivo:string;tamanho:number}};
export const diagnostico=(cfg:CfgSrv)=>api<Diagnostico>(cfg,'GET','/api/v1/diagnostico');
export const fazerBackup=(cfg:CfgSrv)=>api<{arquivo:string;tamanho:number}>(cfg,'POST','/api/v1/backups',{});
export type MidiasBackup={config:{ligado:boolean;categorias:string[];destino:string};destino:string;categorias:Record<string,{nome:string;arquivos:number;mb:number}>;escolhidos:number;ja_copiados:number;falta_mb:number;livre_mb:number;mesmo_aparelho:boolean;ultimos:{arquivo:string;criado:number}[]};
export const lerMidiasBackup=(cfg:CfgSrv)=>api<MidiasBackup>(cfg,'GET','/api/v1/midias-backup');
export const salvarMidiasBackup=(cfg:CfgSrv,d:Partial<MidiasBackup['config']>)=>api<MidiasBackup>(cfg,'PUT','/api/v1/midias-backup',d);
export const fazerMidiasBackup=(cfg:CfgSrv)=>api<{novos:number;ja_existiam:number;faltando:string[];destino:string}>(cfg,'POST','/api/v1/midias-backup/fazer',{});
export const testarMidiasBackup=(cfg:CfgSrv)=>api<{ok:boolean;conferidos:number;problemas:string[];referencias_sem_arquivo:string[]}>(cfg,'POST','/api/v1/midias-backup/testar',{});
export const testarBackup=(cfg:CfgSrv,arquivo:string)=>api<{ok:boolean;erros:string[];banco_ok:boolean;projetos:number}>(cfg,'POST',`/api/v1/backups/${encodeURIComponent(arquivo)}/testar`,{});

/** Texto curto de tempo: 45 s, 3 min, 1 h 20. */
export function duracaoTexto(s:number|null|undefined){
  if(s==null||!isFinite(s)) return '—';
  s=Math.max(0,Math.round(s));
  if(s<60) return `${s} s`;
  if(s<3600) return `${Math.round(s/60)} min`;
  const h=Math.floor(s/3600), m=Math.round(s%3600/60);
  return `${h} h${m?' '+String(m).padStart(2,'0'):''}`;
}
export const horaTexto=(t:number|null|undefined)=>t?new Date(t*1000).toLocaleString('pt-BR',{weekday:'short',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'—';
export const assinarAsset=(cfg:CfgSrv,id:string)=>api<{url:string}>(cfg,'POST',`/api/v1/assets/${id}/link`,{}).then(r=>r.url);
export const salvarStoryboard=(cfg:CfgSrv,id:string,revisao:number,d:{cenas:Cena[];briefing?:Partial<Briefing>;roteiro?:Partial<Roteiro>})=>api<ProjetoMeta>(cfg,'POST',`/api/v1/projetos/${id}/storyboard`,{...d,revisao});
