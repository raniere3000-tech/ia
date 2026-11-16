"""Perfis e escolha das skills: cada tarefa existente usa poucas skills (padrão até 4), e só as regras de texto.

Especificidade: skills de desenvolvimento nunca entram em pedidos de produção; skills de direção não entram na postagem;
nenhuma skill autoriza publicar, aprovar ou mexer em conteúdo travado (elas só viram texto de apoio num pedido à IA).
"""
from __future__ import annotations

import json
import time
import uuid

import banco as db
from skills import catalogo as cat
from skills import seguranca as sg

# id: (agente, tarefa, rótulo, skills padrão, onde é usada de verdade hoje)
PERFIS = {
    'radar.temas': ('radar', 'sugerir temas', 'Radar: sugerir temas', ['social-evidence-research', 'short-drama-hook-engineering'], ''),
    'agente1.analisar': ('agente1', 'analisar vídeo', 'Agente 1: escolher os cortes', ['analyze-video-editing', 'editing-montage'], 'prompt de cortes do Agente 1'),
    'agente1.montar': ('agente1', 'montar clipe', 'Agente 1: montar o clipe', ['social-short-production', 'captions-media-accessibility', 'ffmpeg-media-finishing'], ''),
    'agente2.publicar': ('agente2', 'publicar', 'Agente 2: conferir antes de postar', ['media-provenance-rights', 'media-qc-delivery'], ''),
    'agente3.roteiro': ('agente3', 'roteiro', 'Agente 3: roteiro', ['cinematic-story-architecture', 'modular-film-prompt-bible'], 'prompt do roteiro do Agente 3'),
    'agente3.storyboard': ('agente3', 'storyboard', 'Agente 3: planos de cada cena', ['storyboard-shot-design', 'shot-size-and-angle-language', 'continuity-editing-axis-match'], 'prompt do roteiro (estilo documentário)'),
    'agente3.personagem': ('agente3', 'personagem', 'Agente 3: personagens', ['2d-character-rig-animation', 'character-design-continuity', 'world-asset-identity-lock'], ''),
    'agente3.dialogo': ('agente3', 'diálogo', 'Agente 3: falas e som', ['dialogue-performance-blocking', 'sound-design-foley', 'audio-mixing-mastering'], ''),
    'agente3.codigo2d': ('agente3', '2D/código', 'Agente 3: animação 2D', ['animation-basics', 'procedural-canvas-animation', 'gsap-animation-composition'], ''),
    'agente3.papel': ('agente3', 'papel recortado', 'Agente 3: papel recortado', ['papermotion', 'vfx-compositing'], ''),
    'agente3.motion': ('agente3', 'motion graphics', 'Agente 3: motion graphics', ['motion-canvas', 'title-kinetic-typography'], ''),
    'agente3.avaliacao': ('agente3', 'avaliação', 'Agente 3: avaliação', ['generated-media-qa', 'agentic-eval', 'qc-skill'], ''),
    'site.editor': ('editor', 'editor manual', 'Site: editor manual', ['video-editing', 'ffmpeg-media-finishing', 'captions-media-accessibility'], ''),
    'site.cenas': ('editor', 'editor de cenas', 'Site: editor de cenas', ['storyboard-shot-design', 'reference-media-analysis'], ''),
    'site.vozes': ('editor', 'vozes', 'Site: vozes', ['dialogue-editing-adr', 'layer-talking-characters'], ''),
    'dev.fable': ('desenvolvimento', 'desenvolvimento', 'Desenvolvimento do site', ['react-best-practices', 'test-driven-development', 'verification-before-completion', 'test-gap-audit'], 'só consulta'),
}
LIMITE_MAX = 6
_DIRECAO = ('Diretor', 'Roteiro', 'Animação', 'Séries', 'Motion', 'Papel', 'Pixel', 'Palitinho', 'Elenco', 'Mapas', '3D', 'FX')


def _permitida(perfil: str, sid: str) -> bool:
    ag = PERFIS[perfil][0]
    s = cat.manifesto()['por_id'].get(sid)
    if not s:
        return False
    if ag != 'desenvolvimento' and s['tipo'] == 'desenvolvimento':
        return False
    if ag == 'agente2' and s['categoria'] in _DIRECAO:
        return False
    return True


def perfis() -> list[dict]:
    salvos = {r['id']: r for r in db.todos('SELECT * FROM skills_perfis')}
    out = []
    for pid, (ag, tarefa, rotulo, padrao, uso) in PERFIS.items():
        r = salvos.get(pid)
        skills = json.loads(r['skills_json']) if r else padrao
        out.append({'id': pid, 'agente': ag, 'tarefa': tarefa, 'rotulo': rotulo, 'skills': skills, 'padrao': padrao,
                    'limite': r['limite'] if r else 4, 'ligado': bool(r['ligado']) if r else True, 'versao': r['versao'] if r else 0,
                    'usado_em': uso, 'prontas': [s for s in skills if cat.regras(s)]})
    return out


def salvar_perfil(pid: str, d: dict) -> dict:
    if pid not in PERFIS:
        raise cat.ErroSkill(404, 'Perfil não encontrado.')
    atual = next(p for p in perfis() if p['id'] == pid)
    skills = d.get('skills', atual['skills'])
    if not isinstance(skills, list) or not all(isinstance(s, str) for s in skills):
        raise cat.ErroSkill(400, 'Lista de skills inválida.')
    skills = list(dict.fromkeys(skills))
    bloqueadas = [s for s in skills if not _permitida(pid, s)]
    if bloqueadas:
        raise cat.ErroSkill(400, 'Estas skills não combinam com esta tarefa: ' + ', '.join(bloqueadas[:5]) + '.')
    limite = int(d.get('limite', atual['limite']))
    if not 1 <= limite <= LIMITE_MAX:
        raise cat.ErroSkill(400, f'O limite vai de 1 a {LIMITE_MAX} skills por tarefa.')
    if len(skills) > 12:
        raise cat.ErroSkill(400, 'Escolha no máximo 12 skills por perfil.')
    ligado = bool(d.get('ligado', atual['ligado']))
    db.executar('INSERT INTO skills_perfis (id, agente, tipo_tarefa, skills_json, limite, versao, ligado) VALUES (?,?,?,?,?,1,?) '
                'ON CONFLICT(id) DO UPDATE SET skills_json=excluded.skills_json, limite=excluded.limite, ligado=excluded.ligado, versao=versao+1',
                pid, PERFIS[pid][0], PERFIS[pid][1], json.dumps(skills), limite, 1 if ligado else 0)
    db.evento('skills', 'perfil_salvo', 'perfil:' + pid, {'skills': skills, 'limite': limite, 'ligado': ligado})
    return next(p for p in perfis() if p['id'] == pid)


def selecionar(pid: str, extras: list | None = None) -> dict:
    """Diz quais skills seriam usadas agora nesta tarefa e por quê as outras ficam de fora."""
    if pid not in PERFIS:
        raise cat.ErroSkill(404, 'Perfil não encontrado.')
    p = next(x for x in perfis() if x['id'] == pid)
    usar, fora = [], []
    if not p['ligado']:
        return {'perfil': pid, 'usar': [], 'fora': [{'id': s, 'motivo': 'perfil desligado'} for s in p['skills']]}
    for sid in list(dict.fromkeys([*(extras or []), *p['skills']])):
        if sid not in cat.manifesto()['por_id']:
            fora.append({'id': sid, 'motivo': 'não está no catálogo'})
        elif not _permitida(pid, sid):
            fora.append({'id': sid, 'motivo': 'não combina com esta tarefa'})
        elif not cat.regras(sid):
            r = db.um('SELECT estado, ativa FROM skills_catalogo WHERE id=?', sid)
            fora.append({'id': sid, 'motivo': 'desligada' if r and not r['ativa'] else cat.NOMES_ESTADO.get((r or {}).get('estado', 'nao_instalada'), 'indisponível').lower()})
        elif len(usar) >= p['limite']:
            fora.append({'id': sid, 'motivo': 'passou do limite do perfil'})
        else:
            usar.append(sid)
    return {'perfil': pid, 'usar': usar, 'fora': fora}


def orientacao(pid: str, *, job_id: str = '', projeto_id: str = '', origem: str = 'automatico', extras: list | None = None) -> tuple[str, list[str]]:
    """Texto de apoio para um pedido à IA, e a lista das skills usadas (fica no histórico). Nunca falha: sem skill, volta vazio."""
    try:
        sel = selecionar(pid, extras)
        blocos = []
        for sid in sel['usar']:
            desc, rg = cat.regras(sid) or ('', [])
            blocos.append((sid, desc, rg))
        texto = sg.compor(blocos)
        usadas = [b[0] for b in blocos if f'[{b[0]}]' in texto]
        for sid in usadas:
            registrar(sid, origem=f'{origem}:{pid}', job_id=job_id, projeto_id=projeto_id, resultado='orientacao_no_pedido')
        return texto, usadas
    except Exception as e:  # a biblioteca nunca pode derrubar um vídeo
        db.evento('skills', 'skill_erro', 'perfil:' + pid, {'erro': str(e)[:200]})
        return '', []


def registrar(sid: str, *, origem: str, job_id: str = '', projeto_id: str = '', resultado: str = '', custo: float | None = None):
    db.executar('INSERT INTO skills_ativacoes (id, skill_id, job_id, projeto_id, origem, resultado, custo, t) VALUES (?,?,?,?,?,?,?,?)',
                uuid.uuid4().hex[:12], sid, job_id or None, projeto_id or None, origem[:60], (resultado or '')[:200], custo, time.time())


def historico(job_id: str = '', projeto_id: str = '', limite: int = 100) -> list[dict]:
    if job_id:
        return db.todos('SELECT * FROM skills_ativacoes WHERE job_id=? ORDER BY t DESC LIMIT ?', job_id, limite)
    if projeto_id:
        return db.todos('SELECT * FROM skills_ativacoes WHERE projeto_id=? ORDER BY t DESC LIMIT ?', projeto_id, limite)
    return db.todos('SELECT * FROM skills_ativacoes ORDER BY t DESC LIMIT ?', limite)
