import { createContext, useContext } from 'react';
import type { Clip } from './lib/analyze';
import type { Cue, Preset } from './lib/captions';
import type { Template } from './lib/render';
import presets from '../../config/presets.json';

export type Marca = {id:string;inicio:number;fim:number;titulo:string};
export type Settings = {ytKey:string; claudeKey:string; whisperModel:string; idioma:string; api:string; legendaPadrao:string; efeitoPadrao:string; servidor:string; servidorToken:string; servidorCanal:string; geminiKey:string; ia:''|'gemini'|'claude'};
export type Tab = 'inicio'|'radar'|'cortes'|'video'|'vozes'|'agendar'|'estilos'|'templates'|'config';

export type Projeto = {
  file:File|null; url:string; nome:string; duracao:number;
  cues:Cue[]; cuesFonte:''|'whisper'|'gemini'|'arquivo';
  candidatos:number; clips:Clip[]; tema:string; prompt:string;
  job:Job;
};
export type Job = {status:'idle'|'rodando'|'pronto'|'erro'; etapa:string; pct:number; erro?:string; etapas:string[]};
export const PROJETO_VAZIO:Projeto = {file:null,url:'',nome:'',duracao:0,cues:[],cuesFonte:'',candidatos:0,clips:[],tema:'',prompt:'',job:{status:'idle',etapa:'',pct:0,etapas:[]}};

export const allPresets = presets.presets as unknown as Preset[];
export const captionPresets = allPresets.filter(p=>p.tipo==='legenda');
export const effectPresets = allPresets.filter(p=>p.tipo==='efeito');

export type Ctx = {
  settings:Settings; setSettings:(s:Partial<Settings>)=>void;
  tab:Tab; go:(t:Tab)=>void;
  toast:(msg:string,kind?:'ok'|'erro'|'info')=>void;
  projeto:Projeto; setProjeto:(f:(p:Projeto)=>Projeto)=>void;
  template:Template; setTemplate:(t:Template)=>void;
  linkRef:string; setLinkRef:(s:string)=>void;
  marcas:Marca[]; setMarcas:(f:(m:Marca[])=>Marca[])=>void;
};
export const AppCtx = createContext<Ctx>(null as unknown as Ctx);
export const useApp = ()=>useContext(AppCtx);
