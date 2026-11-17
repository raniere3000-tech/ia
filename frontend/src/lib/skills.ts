import { api, type CfgSrv } from './api';

export type Skill={id:string;nome:string;origem:string;arquivo:string;versao:string;commit:string;sha256:string;categoria:string;tipo:'producao'|'desenvolvimento';
  estado:string;estado_nome:string;licenca:string;ativa:boolean;motivo:string;ultimo_teste:number|null;tem_anterior:boolean;uso:string;agentes:string[];
  modalidade:string;prioridade:string;gatilho:string;descricao:string;n_regras:number;usavel:boolean;nova_versao:boolean;regras?:string[];descartadas?:number;
  estado_lote?:string;executor?:string;servico_externo?:boolean;versao_testada?:boolean;
  teste?:{ok:boolean;motivo?:string;regras?:number;novas?:string[];removidas?:string[]}};
export type ResumoSkills={total:number;estados:Record<string,number>;usaveis:number;candidatas:number;pasta:string;
  ultima_instalacao:{t:number;instaladas:number;ja_estavam:number;falhas:{id:string;motivo:string}[]}|null;
  trabalho:{id:string;status:string;etapa:string;progresso:number;erro:string|null;dados:string}|null};
export type PerfilSkills={id:string;agente:string;tarefa:string;rotulo:string;skills:string[];padrao:string[];limite:number;ligado:boolean;versao:number;usado_em:string;prontas:string[];
  gatilhos?:string[];estilos?:string[];custo_max?:number;fallback?:string;personalizado?:boolean;pode_desfazer?:boolean};
export type Ativacao={id:string;skill_id:string;job_id:string|null;projeto_id:string|null;origem:string;resultado:string;t:number;
  perfil?:string|null;etapa?:string|null;versao?:string|null;artefato?:string|null;decisao?:string|null};
export type Consumidor={id:string;nome:string;ultimo:number|null;artefato:string;saida:string;skills:{id:string;versao:string;decisao:string}[];fallback:{t:number;motivo:string}|null};

export const listarSkills=(cfg:CfgSrv,f:{agente?:string;estado?:string;busca?:string}={})=>api<{skills:Skill[];resumo:ResumoSkills}>(cfg,'GET','/api/v1/skills?'+new URLSearchParams(f as Record<string,string>).toString());
export const obterSkill=(cfg:CfgSrv,id:string)=>api<Skill>(cfg,'GET','/api/v1/skills/'+encodeURIComponent(id));
export const instalarSkills=(cfg:CfgSrv,ids:string[]=[])=>api<{job:string}>(cfg,'POST','/api/v1/skills/instalar',{ids});
export const conferirSkills=(cfg:CfgSrv)=>api<{conferidas:number;problemas:{id:string;motivo:string}[]}>(cfg,'POST','/api/v1/skills/validar',{});
export const procurarAtualizacoes=(cfg:CfgSrv)=>api<{job:string}>(cfg,'POST','/api/v1/skills/atualizacoes',{});
export const acaoSkill=(cfg:CfgSrv,id:string,acao:'ativar'|'desativar'|'rollback'|'atualizar'|'testar-atualizacao')=>api<Skill>(cfg,'POST',`/api/v1/skills/${encodeURIComponent(id)}/${acao}`,{});
export const lerPerfis=(cfg:CfgSrv)=>api<{perfis:PerfilSkills[];limite_max:number}>(cfg,'GET','/api/v1/skills/perfis');
export const salvarPerfil=(cfg:CfgSrv,id:string,d:Partial<Pick<PerfilSkills,'skills'|'limite'|'ligado'>>)=>api<PerfilSkills>(cfg,'PUT','/api/v1/skills/perfis/'+id,d);
export const selecionarSkills=(cfg:CfgSrv,perfil:string,skills:string[]=[])=>api<{perfil:string;usar:string[];fora:{id:string;motivo:string}[]}>(cfg,'POST','/api/v1/skills/selecionar',{perfil,skills});
export const usarSkills=(cfg:CfgSrv,perfil:string,skills:string[]=[],projeto='')=>api<{texto:string;usadas:string[]}>(cfg,'POST','/api/v1/skills/usar',{perfil,skills,projeto});
export const historicoSkills=(cfg:CfgSrv,f:{job_id?:string;projeto_id?:string;etapa?:string;perfil?:string}={})=>api<{historico:Ativacao[]}>(cfg,'GET','/api/v1/skills/historico?'+new URLSearchParams(f as Record<string,string>).toString());

export const desfazerPerfil=(cfg:CfgSrv,id:string)=>api<PerfilSkills>(cfg,'POST',`/api/v1/skills/perfis/${id}/desfazer`,{});
export const pontaAPonta=(cfg:CfgSrv)=>api<{consumidores:Consumidor[]}>(cfg,'GET','/api/v1/skills/ponta-a-ponta');
export const desfazerLote=(cfg:CfgSrv)=>api<{voltaram:string[];ficaram:{id:string;motivo:string}[]}>(cfg,'POST','/api/v1/skills/desfazer-lote',{});

export const NOME_AGENTE:Record<string,string>={agente1:'Agente 1',agente2:'Agente 2',agente3:'Agente 3',radar:'Radar',editor:'Editor do site',qualidade:'Qualidade',canal:'Perfil de canal',aprendizado:'Aprendizado',criativo:'Modelagem com IA',desenvolvimento:'Desenvolvimento',infra:'Servidor'};
