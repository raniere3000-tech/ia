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

# id: (agente, tarefa, rótulo, skills padrão em ordem, onde é usada de verdade hoje)
# Padrões do lote 2 (K3). Um perfil salvo pelo site (override manual) vale no lugar do padrão.
PERFIS = {
    'radar.temas': ('radar', 'sugerir temas', 'Radar: sugerir temas',
                    ['social-evidence-research', 'reference-media-analysis', 'social-short-production', 'short-drama-hook-engineering'],
                    'prompt de ideias do Radar → ficha de oportunidade'),
    'agente1.analisar': ('agente1', 'analisar vídeo', 'Agente 1: escolher os cortes',
                         ['analyze-video-editing', 'video-editing', 'editing-montage', 'captions-media-accessibility'], 'prompt de cortes do Agente 1 → trechos com tempo'),
    'agente1.montar': ('agente1', 'montar clipe', 'Agente 1: montar o clipe', ['social-short-production', 'captions-media-accessibility', 'ffmpeg-media-finishing'], ''),
    'agente2.publicar': ('agente2', 'publicar', 'Agente 2: conferir antes de postar', ['media-provenance-rights', 'media-qc-delivery', 'social-short-production'],
                         'lista de conferência antes de postar (você vê as regras)'),
    'agente3.roteiro': ('agente3', 'roteiro', 'Agente 3: roteiro', ['cinematic-story-architecture', 'screenplay-fountain-format', 'modular-film-prompt-bible'],
                        'prompt do roteiro do Agente 3'),
    'agente3.storyboard': ('agente3', 'direção', 'Agente 3: direção (planos, câmera e posições)',
                           ['storyboard-shot-design', 'shot-size-and-angle-language', 'scene-blocking-and-staging', 'continuity-editing-axis-match'],
                           'prompt do roteiro → planos, câmera e posições conferidos pelo código'),
    'agente3.personagem': ('agente3', 'animar 2D', 'Agente 3: animação 2D (bonecos)', ['2d-character-rig-animation', 'animation-basics', 'performance-direction',
                           'character-design-continuity'], 'prompt do roteiro (animados) → poses, ações e objetos conferidos pelo código'),
    'agente3.dialogo': ('agente3', 'áudio', 'Agente 3: falas, efeitos e mixagem', ['sound-design-foley', 'audio-mixing-mastering', 'dialogue-performance-blocking'],
                        'prompt do roteiro (animados) → falas e efeitos sonoros'),
    'agente3.codigo2d': ('agente3', '2D/código', 'Agente 3: outros estilos desenhados', ['animation-basics', 'procedural-canvas-animation', 'gsap-animation-composition'], 'prompt do roteiro (estilos desenhados)'),
    'agente3.papel': ('agente3', 'papel recortado', 'Agente 3: papel recortado', ['papermotion', 'vfx-compositing'], 'prompt do roteiro (papel recortado)'),
    'agente3.motion': ('agente3', 'motion graphics', 'Agente 3: motion graphics', ['motion-canvas', 'title-kinetic-typography'], 'prompt do roteiro (motion graphics)'),
    'agente3.avaliacao': ('agente3', 'avaliação', 'Agente 3: leitura crítica do roteiro', ['generated-media-qa', 'agentic-eval', 'qc-skill'], 'leitura crítica do roteiro no relatório de qualidade'),
    'qc.validar': ('qualidade', 'validar', 'Diretor de Qualidade: conferir o vídeo', ['generated-media-qa', 'media-qc-delivery', 'agentic-eval'],
                   'avaliação visual pela IA (quando ligada) → defeitos com evidência'),
    'site.editor': ('editor', 'editor manual', 'Site: editor manual', ['video-editing', 'ffmpeg-media-finishing', 'captions-media-accessibility'], ''),
    'site.cenas': ('editor', 'editor de cenas', 'Site: editor de cenas', ['storyboard-shot-design', 'reference-media-analysis'], ''),
    'site.vozes': ('editor', 'vozes', 'Site: vozes', ['dialogue-editing-adr', 'layer-talking-characters'], ''),
    'dev.fable': ('desenvolvimento', 'desenvolvimento', 'Desenvolvimento do site (React)', ['react-best-practices', 'web-design-guidelines',
                  'test-driven-development', 'verification-before-completion'], 'só consulta'),
}
# configuração de cada perfil: gatilhos (palavras da tarefa), estilos em que entra, orçamento em caracteres e o que acontece sem skill
_CFG_PADRAO = {'gatilhos': [], 'estilos': [], 'custo_max': 3000, 'fallback': 'Segue sem material de apoio (regras próprias do servidor).'}
CONFIG = {
    'radar.temas': {'gatilhos': ['radar', 'tema', 'pauta', 'ideia', 'tendencia', 'pesquisa'], 'fallback': 'Pautas sem material de apoio; a ficha de oportunidade é feita igual.'},
    'agente1.analisar': {'gatilhos': ['corte', 'cortes', 'trecho', 'analisar'], 'fallback': 'Escolhe trechos só com as regras de duração e viralidade do Agente 1.'},
    'agente1.montar': {'gatilhos': ['montar', 'clipe', 'legenda']},
    'agente2.publicar': {'gatilhos': ['postar', 'publicar', 'postagem', 'conferencia'], 'custo_max': 1500,
                         'fallback': 'A conferência antes de postar roda igual (arquivo, versão, conta, formato, direitos, qualidade).'},
    'agente3.roteiro': {'gatilhos': ['roteiro', 'historia', 'texto'], 'fallback': 'Roteiro só com as regras de retenção do servidor.'},
    'agente3.storyboard': {'gatilhos': ['planos', 'plano', 'direcao', 'camera', 'storyboard', 'posicao'], 'estilos': ['documentario', 'animado2d', 'animado3d']},
    'agente3.personagem': {'gatilhos': ['animar', 'pose', 'boneco', 'personagem', 'rig'], 'estilos': ['animado2d', 'animado3d']},
    'agente3.dialogo': {'gatilhos': ['dialogo', 'fala', 'audio', 'som', 'voz', 'efeito sonoro'], 'estilos': ['animado2d', 'animado3d']},
    'agente3.codigo2d': {'gatilhos': ['desenho'], 'estilos': ['*desenhado']},
    'agente3.papel': {'gatilhos': ['papel'], 'estilos': ['papel_recortado']},
    'agente3.motion': {'gatilhos': ['motion', 'titulo animado'], 'estilos': ['motion_graphics']},
    'agente3.avaliacao': {'gatilhos': ['revisar roteiro', 'leitura critica']},
    'qc.validar': {'gatilhos': ['qualidade', 'validar', 'conferir video', 'qc'], 'fallback': 'Só a conferência técnica e de geometria do código (sem IA).'},
    'site.editor': {'gatilhos': ['editor', 'montagem manual']},
    'site.cenas': {'gatilhos': ['editor de cenas']},
    'site.vozes': {'gatilhos': ['vozes']},
    'dev.fable': {'gatilhos': ['react', 'site', 'frontend'], 'custo_max': 3000},
}
# em que decisão cada skill entra (produto esperado do K3): aparece no registro de uso
DECISOES = {
    'social-evidence-research': 'evidência e fontes da pauta', 'reference-media-analysis': 'leitura das referências', 'social-short-production': 'formato curto vertical',
    'short-drama-hook-engineering': 'gancho', 'analyze-video-editing': 'escolha dos trechos', 'video-editing': 'início e fim do corte',
    'editing-montage': 'ritmo e duração', 'captions-media-accessibility': 'legenda e leitura', 'media-provenance-rights': 'origem e direitos',
    'media-qc-delivery': 'formato, conferência e hash', 'cinematic-story-architecture': 'estrutura da história', 'screenplay-fountain-format': 'cenas e falas estruturadas',
    'modular-film-prompt-bible': 'contexto de cada cena', 'storyboard-shot-design': 'quantos planos e qual', 'shot-size-and-angle-language': 'enquadramento e ângulo',
    'scene-blocking-and-staging': 'posição dos personagens', 'continuity-editing-axis-match': 'eixo e continuidade', '2d-character-rig-animation': 'poses e juntas',
    'animation-basics': 'movimento', 'performance-direction': 'atuação e expressões', 'character-design-continuity': 'identidade do personagem',
    'sound-design-foley': 'efeitos sonoros', 'audio-mixing-mastering': 'volume e mixagem', 'dialogue-performance-blocking': 'falas',
    'generated-media-qa': 'defeitos do vídeo gerado', 'agentic-eval': 'critério de avaliação', 'qc-skill': 'checagem técnica',
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


def cfg(pid: str) -> dict:
    return {**_CFG_PADRAO, **CONFIG.get(pid, {})}


def perfis() -> list[dict]:
    salvos = {r['id']: r for r in db.todos('SELECT * FROM skills_perfis')}
    out = []
    for pid, (ag, tarefa, rotulo, padrao, uso) in PERFIS.items():
        r = salvos.get(pid)
        skills = json.loads(r['skills_json']) if r else padrao
        c = {**cfg(pid), **(json.loads(r.get('config_json') or '{}') if r else {})}
        out.append({'id': pid, 'agente': ag, 'tarefa': tarefa, 'rotulo': rotulo, 'skills': skills, 'padrao': padrao,
                    'limite': r['limite'] if r else 4, 'ligado': bool(r['ligado']) if r else True, 'versao': r['versao'] if r else 0,
                    'usado_em': uso, 'prontas': [s for s in skills if cat.regras(s)], 'gatilhos': c['gatilhos'], 'estilos': c['estilos'],
                    'custo_max': c['custo_max'], 'fallback': c['fallback'], 'personalizado': bool(r),
                    'pode_desfazer': bool(db.kv('skills_perfil_hist:' + pid))})
    return out


def _perfil(pid: str) -> dict:
    if pid not in PERFIS:
        raise cat.ErroSkill(404, 'Perfil não encontrado.')
    return next(p for p in perfis() if p['id'] == pid)


def salvar_perfil(pid: str, d: dict, quem: str = '') -> dict:
    atual = _perfil(pid)
    skills = d.get('skills', atual['skills'])
    if not isinstance(skills, list) or not all(isinstance(s, str) for s in skills):
        raise cat.ErroSkill(400, 'Lista de skills inválida.')
    skills = list(dict.fromkeys(skills))
    fora_cat = [s for s in skills if s not in cat.manifesto()['por_id'] and s not in atual['skills']]
    if fora_cat:
        raise cat.ErroSkill(400, 'Estas skills não estão no catálogo autorizado: ' + ', '.join(fora_cat[:5]) + '.')
    bloqueadas = [s for s in skills if s in cat.manifesto()['por_id'] and not _permitida(pid, s)]
    if bloqueadas:
        raise cat.ErroSkill(400, 'Estas skills não combinam com esta tarefa: ' + ', '.join(bloqueadas[:5]) + '.')
    limite = int(d.get('limite', atual['limite']))
    if not 1 <= limite <= LIMITE_MAX:
        raise cat.ErroSkill(400, f'O limite vai de 1 a {LIMITE_MAX} skills por tarefa.')
    if len(skills) > 12:
        raise cat.ErroSkill(400, 'Escolha no máximo 12 skills por perfil.')
    custo = int(d.get('custo_max', atual['custo_max']))
    if not 300 <= custo <= 6000:
        raise cat.ErroSkill(400, 'O orçamento vai de 300 a 6000 caracteres de regras por pedido.')
    gat = d.get('gatilhos', atual['gatilhos'])
    if not isinstance(gat, list) or len(gat) > 20 or not all(isinstance(g, str) and 1 <= len(g) <= 40 for g in gat):
        raise cat.ErroSkill(400, 'Gatilhos inválidos (até 20 palavras curtas).')
    ligado = bool(d.get('ligado', atual['ligado']))
    # guarda como estava, para o botão "Desfazer"
    hist = db.kv('skills_perfil_hist:' + pid) or []
    hist.append({k: atual[k] for k in ('skills', 'limite', 'ligado', 'custo_max', 'gatilhos', 'personalizado')})
    db.kv_gravar('skills_perfil_hist:' + pid, hist[-10:])
    conf = {'custo_max': custo, 'gatilhos': [g.strip().lower() for g in gat]}
    db.executar('INSERT INTO skills_perfis (id, agente, tipo_tarefa, skills_json, limite, versao, ligado, config_json) VALUES (?,?,?,?,?,1,?,?) '
                'ON CONFLICT(id) DO UPDATE SET skills_json=excluded.skills_json, limite=excluded.limite, ligado=excluded.ligado, '
                'config_json=excluded.config_json, versao=versao+1',
                pid, PERFIS[pid][0], PERFIS[pid][1], json.dumps(skills), limite, 1 if ligado else 0, json.dumps(conf))
    db.evento(quem or 'skills', 'perfil_salvo', 'perfil:' + pid, {'skills': skills, 'limite': limite, 'ligado': ligado, 'custo_max': custo})
    return _perfil(pid)


def desfazer_perfil(pid: str, quem: str = '') -> dict:
    """Volta o perfil para como estava antes da última alteração feita pelo site."""
    _perfil(pid)
    hist = db.kv('skills_perfil_hist:' + pid) or []
    if not hist:
        raise cat.ErroSkill(409, 'Não há alteração para desfazer neste perfil.')
    ant = hist.pop()
    db.kv_gravar('skills_perfil_hist:' + pid, hist)
    if not ant.get('personalizado'):
        db.executar('DELETE FROM skills_perfis WHERE id=?', pid)
    else:
        db.executar('UPDATE skills_perfis SET skills_json=?, limite=?, ligado=?, config_json=?, versao=versao+1 WHERE id=?',
                    json.dumps(ant['skills']), ant['limite'], 1 if ant['ligado'] else 0,
                    json.dumps({'custo_max': ant['custo_max'], 'gatilhos': ant['gatilhos']}), pid)
    db.evento(quem or 'skills', 'perfil_desfeito', 'perfil:' + pid)
    return _perfil(pid)


def _custo(sid: str) -> int:
    desc, rg = cat.regras(sid) or ('', [])
    t = sg.compor([(sid, desc, rg)]) if rg else ''
    return len(t) - (t.index('\n') + 1) if t else 0     # só o bloco da skill (o cabeçalho do material de apoio entra uma vez)


def selecionar(pid: str, extras: list | None = None, *, custo_max: int | None = None, evitar: list | None = None,
               assets: list | None = None, permitir_externo: bool = True) -> dict:
    """Diz quais skills seriam usadas agora nesta tarefa e por que as outras ficam de fora (ordem, limite, orçamento)."""
    p = _perfil(pid)
    usar, fora, gasto = [], [], 0
    orc = min(int(custo_max or p['custo_max']), p['custo_max'])
    if not p['ligado']:
        return {'perfil': pid, 'usar': [], 'fora': [{'id': s, 'motivo': 'perfil desligado'} for s in p['skills']], 'custo': 0, 'orcamento': orc,
                'fallback': p['fallback']}
    evitar = set(evitar or [])
    for sid in list(dict.fromkeys([*(extras or []), *p['skills']])):
        if sid not in cat.manifesto()['por_id']:
            fora.append({'id': sid, 'motivo': 'não está no catálogo'})
            continue
        s = cat.manifesto()['por_id'][sid]
        if sid in evitar:
            fora.append({'id': sid, 'motivo': 'você pediu para não usar'})
        elif not _permitida(pid, sid):
            fora.append({'id': sid, 'motivo': 'não combina com esta tarefa'})
        elif not cat.regras(sid):
            r = db.um('SELECT estado, ativa FROM skills_catalogo WHERE id=?', sid)
            fora.append({'id': sid, 'motivo': 'desligada' if r and not r['ativa'] else cat.NOMES_ESTADO.get((r or {}).get('estado', 'nao_instalada'), 'indisponível').lower()})
        elif s.get('modalidade') == 'externo-condicional' and not permitir_externo:
            fora.append({'id': sid, 'motivo': 'depende de serviço externo não conectado'})
        elif assets is not None and REQUER.get(sid) and not set(REQUER[sid]) & set(assets):
            fora.append({'id': sid, 'motivo': 'precisa de ' + ' ou '.join(REQUER[sid]) + ' de referência'})
        elif len(usar) >= p['limite']:
            fora.append({'id': sid, 'motivo': 'passou do limite do perfil'})
        else:
            c = _custo(sid)
            if gasto + c > orc:
                fora.append({'id': sid, 'motivo': f'passou do orçamento ({gasto + c} de {orc} caracteres)'})
                continue
            gasto += c
            usar.append(sid)
    return {'perfil': pid, 'usar': usar, 'fora': fora, 'custo': gasto, 'orcamento': orc, 'fallback': '' if usar else p['fallback']}


REQUER = {'reference-media-analysis': ('video', 'imagem'), 'analyze-video-editing': ('video',), 'find-broll': ('video',),
          'video-to-audio-foley': ('video',)}


def _norm(t: str) -> str:
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', (t or '').lower()) if unicodedata.category(c) != 'Mn')


def escolher(pedido: dict) -> dict:
    """Roteador (K2): de uma tarefa (agente, tarefa, estilo, preferências, assets, permissão, custo máximo) escolhe os perfis
    pelos gatilhos e as skills de cada um. Devolve uma seleção estruturada já validada; nada é executado aqui."""
    if not isinstance(pedido, dict):
        raise cat.ErroSkill(400, 'Pedido inválido.')
    agente = str(pedido.get('agente') or '')[:30]
    tarefa = _norm(str(pedido.get('tarefa') or ''))[:200]
    estilo = str(pedido.get('estilo') or '')[:40]
    pref = [str(x) for x in (pedido.get('preferir') or []) if isinstance(x, str)][:6]
    evitar = [str(x) for x in (pedido.get('evitar') or []) if isinstance(x, str)][:20]
    assets = [str(x) for x in pedido['assets'] if isinstance(x, str)][:10] if isinstance(pedido.get('assets'), list) else None
    custo_max = max(300, min(int(pedido.get('custo_max') or 6000), 6000))
    externo = bool(pedido.get('permitir_externo', False))
    perfis_ok = [str(x) for x in pedido['perfis'] if x in PERFIS] if isinstance(pedido.get('perfis'), list) else []
    if not perfis_ok:
        for pid, (ag, *_r) in PERFIS.items():
            c = cfg(pid)
            if agente and ag != agente or ag == 'desenvolvimento' and agente != 'desenvolvimento':
                continue
            if c['estilos'] and estilo and estilo not in c['estilos'] and not ('*desenhado' in c['estilos'] and estilo not in _NAO_DESENHADOS):
                continue
            if any(_norm(g) in tarefa for g in c['gatilhos']) or pid == pedido.get('tarefa'):
                perfis_ok.append(pid)
    if not perfis_ok:
        return {'pedido': {'agente': agente, 'tarefa': tarefa, 'estilo': estilo}, 'perfis': [], 'usar': [], 'fora': [], 'custo': 0,
                'orcamento': custo_max, 'fallback': 'Nenhum perfil combina com esta tarefa: segue sem skills.', 'valido': True}
    usar, fora, gasto = [], [], 0
    for pid in perfis_ok:
        sel = selecionar(pid, [x for x in pref if _permitida(pid, x)], custo_max=max(0, custo_max - gasto) or 1, evitar=evitar, assets=assets,
                         permitir_externo=externo)
        for sid in sel['usar']:
            if sid in (u['id'] for u in usar):
                continue
            usar.append({'id': sid, 'perfil': pid, 'decisao': DECISOES.get(sid, PERFIS[pid][1]), 'versao': _versao(sid), 'chars': _custo(sid)})
        gasto = sum(u['chars'] for u in usar)
        fora += [dict(f, perfil=pid) for f in sel['fora']]
    out = {'pedido': {'agente': agente, 'tarefa': tarefa, 'estilo': estilo}, 'perfis': perfis_ok, 'usar': usar, 'fora': fora, 'custo': gasto,
           'custo_tokens': gasto // 4, 'orcamento': custo_max, 'fallback': '' if usar else 'Sem skill disponível: segue com as regras próprias do servidor.'}
    out['valido'] = not validar_selecao(out)
    return out


_NAO_DESENHADOS = ('documentario', 'animado2d', 'animado3d', 'motion_graphics', 'papel_recortado')


def validar_selecao(sel: dict) -> list[str]:
    """Confere a seleção pelo código antes de usar: skill existe, está pronta, combina com o perfil, cabe no limite e no orçamento."""
    erros = []
    por_perfil: dict = {}
    for u in sel.get('usar', []):
        sid, pid = u.get('id'), u.get('perfil')
        if pid not in PERFIS or sid not in cat.manifesto()['por_id']:
            erros.append(f'{sid}: fora do catálogo ou do perfil')
        elif not _permitida(pid, sid):
            erros.append(f'{sid}: não combina com {pid}')
        elif not cat.regras(sid):
            erros.append(f'{sid}: não está pronta')
        por_perfil[pid] = por_perfil.get(pid, 0) + 1
    for pid, n in por_perfil.items():
        if pid in PERFIS and n > _perfil(pid)['limite']:
            erros.append(f'{pid}: passou do limite')
    if sel.get('custo', 0) > sel.get('orcamento', 0):
        erros.append('passou do orçamento')
    if len(sel.get('usar', [])) > LIMITE_MAX * 2:
        erros.append('skills demais num pedido')
    return erros


def _versao(sid: str) -> str:
    r = db.um('SELECT commit_sha FROM skills_catalogo WHERE id=?', sid)
    return (r or {}).get('commit_sha', '')[:12]


def orientacao(pid: str, *, job_id: str = '', projeto_id: str = '', origem: str = 'automatico', extras: list | None = None,
               registrar_carga: bool = True) -> tuple[str, list[str]]:
    """Texto de apoio para um pedido à IA e a lista das skills carregadas. Nunca falha: sem skill, volta vazio e registra o fallback.
    O registro aqui é "carregada" (entrou no pedido). "Utilizada" só depois que o agente produz algo de verdade (concluir)."""
    try:
        sel = selecionar(pid, extras)
        blocos = []
        for sid in sel['usar']:
            desc, rg = cat.regras(sid) or ('', [])
            blocos.append((sid, desc, rg))
        texto = sg.compor(blocos, limite_total=max(sel['orcamento'], 300))
        usadas = [b[0] for b in blocos if f'[{b[0]}]' in texto]
        if registrar_carga:
            for sid in usadas:
                registrar(sid, origem=f'{origem}:{pid}', job_id=job_id, projeto_id=projeto_id, resultado='texto no pedido à IA', perfil=pid,
                          etapa='carregada', chars=_custo(sid))
            if not usadas:
                _fallback(pid, origem, job_id, projeto_id, sel)
        return texto, usadas
    except Exception as e:  # a biblioteca nunca pode derrubar um vídeo
        db.evento('skills', 'skill_erro', 'perfil:' + pid, {'erro': str(e)[:200]})
        return '', []


def _fallback(pid: str, origem: str, job_id: str, projeto_id: str, sel: dict):
    ult = db.um("SELECT t FROM skills_ativacoes WHERE perfil=? AND etapa='fallback' AND COALESCE(projeto_id,'')=? ORDER BY t DESC LIMIT 1", pid, projeto_id or '')
    if ult and time.time() - ult['t'] < 600:
        return
    motivo = '; '.join(f'{f["id"]}: {f["motivo"]}' for f in sel.get('fora', [])[:4])
    registrar('-', origem=f'{origem}:{pid}', job_id=job_id, projeto_id=projeto_id, resultado=(sel.get('fallback') or 'sem skill') + (f' ({motivo})' if motivo else ''),
              perfil=pid, etapa='fallback')


def concluir(usadas: list, pid: str, *, artefato: str, saida: str, projeto_id: str = '', job_id: str = '', origem: str = '') -> int:
    """Registra "skill utilizada" SÓ depois que o agente produziu algo real (ficha, cortes, roteiro, conferência, laudo),
    com a versão da skill, a decisão em que entrou e o artefato ligado. Repetir a mesma coisa não duplica o registro."""
    n = 0
    for sid in usadas or []:
        v = _versao(sid)
        if db.um("SELECT 1 FROM skills_ativacoes WHERE skill_id=? AND perfil=? AND artefato=? AND versao=? AND etapa='utilizada'", sid, pid, artefato, v):
            continue
        registrar(sid, origem=origem or pid.split('.')[0], job_id=job_id, projeto_id=projeto_id, resultado=saida, perfil=pid, etapa='utilizada',
                  artefato=artefato, decisao=DECISOES.get(sid, PERFIS.get(pid, ('', ''))[1]))
        n += 1
    return n


def registrar(sid: str, *, origem: str, job_id: str = '', projeto_id: str = '', resultado: str = '', custo: float | None = None,
              perfil: str = '', etapa: str = 'carregada', artefato: str = '', decisao: str = '', chars: int | None = None):
    db.executar('INSERT INTO skills_ativacoes (id, skill_id, job_id, projeto_id, origem, resultado, custo, t, perfil, etapa, versao, artefato, decisao, chars) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                uuid.uuid4().hex[:12], sid, job_id or None, projeto_id or None, origem[:60], (resultado or '')[:200], custo, time.time(),
                perfil or None, etapa, _versao(sid) if sid != '-' else '', (artefato or '')[:120] or None, (decisao or '')[:80] or None, chars)


def historico(job_id: str = '', projeto_id: str = '', limite: int = 100, etapa: str = '', perfil: str = '') -> list[dict]:
    cond, args = [], []
    for col, val in (('job_id', job_id), ('projeto_id', projeto_id), ('etapa', etapa), ('perfil', perfil)):
        if val:
            cond.append(f'{col}=?')
            args.append(val)
    sql = 'SELECT * FROM skills_ativacoes' + (' WHERE ' + ' AND '.join(cond) if cond else '') + ' ORDER BY t DESC LIMIT ?'
    return db.todos(sql, *args, max(1, min(int(limite), 500)))


CONSUMIDORES = (('radar', 'Radar', ('radar.temas',)), ('agente1', 'Agente 1', ('agente1.analisar', 'agente1.montar')),
                ('agente2', 'Agente 2', ('agente2.publicar',)),
                ('agente3', 'Agente 3', ('agente3.roteiro', 'agente3.storyboard', 'agente3.personagem', 'agente3.dialogo', 'agente3.codigo2d',
                                         'agente3.papel', 'agente3.motion')),
                ('qualidade', 'Diretor de Qualidade', ('qc.validar', 'agente3.avaliacao')))


def ponta_a_ponta() -> list[dict]:
    """Último uso real (com artefato) de cada consumidor, e o último fallback: a prova de que a skill virou alguma coisa."""
    out = []
    for cid, nome, pids in CONSUMIDORES:
        marca = ','.join('?' * len(pids))
        uso = db.todos(f"SELECT * FROM skills_ativacoes WHERE etapa='utilizada' AND perfil IN ({marca}) ORDER BY t DESC LIMIT 6", *pids)
        fb = db.um(f"SELECT * FROM skills_ativacoes WHERE etapa='fallback' AND perfil IN ({marca}) ORDER BY t DESC LIMIT 1", *pids)
        out.append({'id': cid, 'nome': nome, 'ultimo': uso[0]['t'] if uso else None, 'artefato': uso[0]['artefato'] if uso else '',
                    'saida': uso[0]['resultado'] if uso else '', 'skills': [{'id': u['skill_id'], 'versao': u['versao'], 'decisao': u['decisao']} for u in uso
                                                                             if u['artefato'] == uso[0]['artefato']],
                    'fallback': {'t': fb['t'], 'motivo': fb['resultado']} if fb else None})
    return out
