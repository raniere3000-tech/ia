"""Perfis de canal: a identidade de conteúdo de cada página (nome, nicho, tom, voz, cores, templates, estilos, redes, regras).

Herança por camadas, da mais fraca para a mais forte:  padrão do site  <  perfil do canal  <  projeto  <  corte individual.
Cada valor sabe de qual camada veio (para a tela mostrar). Um corte usa UM perfil: nunca se misturam voz, logo, cores ou redes de
perfis diferentes. Cada alteração guarda uma versão (dá para voltar). Só biblioteca padrão do Python.
Limite real do servidor hoje: existe UMA conta por rede (um token do Google, um do Meta, um do TikTok). O perfil escolhe QUAIS redes
usar e, no Meta, qual página; não cria contas novas.
"""
from __future__ import annotations

import re
import time
import uuid

import postagem as pg
import visual_presets as vp

ARQ = pg.DADOS / 'perfis.json'
MAX_PERFIS = 20
MAX_VERSOES = 20
CAMPOS_LISTA = ('elenco', 'series', 'templates', 'estilos_permitidos', 'hashtags_base', 'redes', 'temas_frequentes')
MODOS_QUALIDADE = ('', 'rapido', 'caprichado')
FONTES = ('meu', 'autorizado', 'regra')


class ErroPerfil(Exception):
    pass


def _s(v, n) -> str:
    return str(v or '').strip()[:n]


def _lista(v, n, item=60) -> list:
    return [_s(x, item) for x in (v if isinstance(v, list) else []) if _s(x, item)][:n]


def _cor(v, padrao='') -> str:
    return v if isinstance(v, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', v) else padrao


def limpar(d: dict) -> dict:
    if not isinstance(d, dict):
        raise ErroPerfil('Perfil inválido.')
    nome = _s(d.get('nome'), 40)
    if not nome:
        raise ErroPerfil('Dê um nome ao perfil (o nome do canal).')
    cores = d.get('cores') if isinstance(d.get('cores'), dict) else {}
    pf = d.get('politica_fonte') if isinstance(d.get('politica_fonte'), dict) else {}
    contas = d.get('contas') if isinstance(d.get('contas'), dict) else {}
    logo = d.get('logo') if isinstance(d.get('logo'), str) else ''
    if logo and (not logo.startswith('data:image/') or len(logo) > 600000):
        logo = ''
    try:
        orc = round(max(0.0, min(50.0, float(d.get('orcamento') or 0))), 2)
    except (TypeError, ValueError):
        orc = 0.0
    return {'nome': nome, 'nicho': _s(d.get('nicho'), 60), 'publico': _s(d.get('publico'), 120), 'tom': _s(d.get('tom'), 120),
            'voz': _s(d.get('voz'), 30), 'elenco': _lista(d.get('elenco'), 20, 40), 'series': _lista(d.get('series'), 20, 40),
            'cores': {'primaria': _cor(cores.get('primaria')), 'secundaria': _cor(cores.get('secundaria'))}, 'logo': logo,
            'templates': _lista(d.get('templates'), 3, 40), 'estilos_permitidos': [x for x in _lista(d.get('estilos_permitidos'), 12, 40) if x in vp.PRESETS],
            'hashtags_base': _lista(d.get('hashtags_base'), 10, 40),
            'politica_fonte': {'origens': [x for x in _lista(pf.get('origens'), 3, 20) if x in FONTES], 'nota': _s(pf.get('nota'), 300)},
            'redes': [x for x in _lista(d.get('redes'), 5, 20) if x in pg.REDES],
            'contas': {'meta_pagina': _s(contas.get('meta_pagina'), 60)},
            'modo_qualidade': d.get('modo_qualidade') if d.get('modo_qualidade') in MODOS_QUALIDADE else '', 'orcamento': orc,
            'temas_frequentes': _lista(d.get('temas_frequentes'), 20, 80), 'regras_de_marca': _s(d.get('regras_de_marca'), 1200)}


def _dados() -> dict:
    return pg._ler(ARQ, {'perfis': {}})


def listar() -> list:
    return [{'id': k, **{c: v[c] for c in ('nome', 'nicho', 'redes', 'modo_qualidade')}, 'versao': v['versao'], 'atualizado': v['atualizado'], 'tem_logo': bool(v.get('logo'))}
            for k, v in _dados()['perfis'].items()]


def obter(pid: str) -> dict:
    p = _dados()['perfis'].get(pid)
    if not p:
        raise ErroPerfil('Perfil não encontrado.')
    return {'id': pid, **p}


def salvar(d: dict, pid: str = '') -> dict:
    campos = limpar(d)
    agora = time.time()
    with pg.LOCK:
        todos = _dados()
        if not pid:
            if len(todos['perfis']) >= MAX_PERFIS:
                raise ErroPerfil(f'No máximo {MAX_PERFIS} perfis.')
            pid = uuid.uuid4().hex[:8]
            todos['perfis'][pid] = {**campos, 'versao': 1, 'atualizado': agora, 'historico': [{'versao': 1, 't': agora, 'campos': campos, 'o_que': 'criado'}]}
        else:
            atual = todos['perfis'].get(pid)
            if not atual:
                raise ErroPerfil('Perfil não encontrado.')
            ant = {k: atual[k] for k in campos}
            mudou = [k for k in campos if ant[k] != campos[k]]
            if mudou:
                v = atual['versao'] + 1
                atual.update(campos)
                atual['versao'], atual['atualizado'] = v, agora
                atual['historico'] = (atual['historico'] + [{'versao': v, 't': agora, 'campos': campos, 'o_que': 'mudou: ' + ', '.join(mudou)}])[-MAX_VERSOES:]
        pg._gravar(ARQ, todos)
    return obter(pid)


def duplicar(pid: str) -> dict:
    p = obter(pid)
    return salvar({**{k: p[k] for k in limpar({'nome': 'x'})}, 'nome': (p['nome'] + ' (cópia)')[:40]})


def restaurar(pid: str, versao: int) -> dict:
    p = obter(pid)
    v = next((h for h in p['historico'] if h['versao'] == int(versao)), None)
    if not v:
        raise ErroPerfil('Versão não encontrada.')
    return salvar(dict(v['campos']), pid)


def apagar(pid: str):
    with pg.LOCK:
        todos = _dados()
        if pid not in todos['perfis']:
            raise ErroPerfil('Perfil não encontrado.')
        del todos['perfis'][pid]
        pg._gravar(ARQ, todos)


# ---------------------------------------------------------------- herança por camadas
def padrao_do_site(cfg_cortes: dict, cfg_post: dict) -> dict:
    return {'voz': 'Puck', 'templates': list(cfg_cortes.get('modelos') or []), 'estilos_permitidos': list(cfg_cortes.get('estilos') or []),
            'redes': list(cfg_post.get('redes') or []), 'modo_qualidade': cfg_cortes.get('modo', ''), 'orcamento': 0.0, 'hashtags_base': [], 'nicho': '', 'tom': '', 'publico': ''}


def resolver(pid: str, site: dict, projeto: dict | None = None, corte: dict | None = None) -> dict:
    """Valores finais e a camada de onde cada um veio. Só entra o que a camada realmente definiu (vazio não apaga o valor de baixo)."""
    camadas = [('site', site)]
    if pid:
        p = obter(pid)
        camadas.append(('perfil', {k: v for k, v in p.items() if k not in ('id', 'historico', 'versao', 'atualizado')}))
    camadas += [('projeto', projeto or {}), ('corte', corte or {})]
    valores, origem = {}, {}
    for nome, c in camadas:
        for k, v in c.items():
            if v in (None, '', [], {}) or (k == 'cores' and not any(v.values())) or (k == 'orcamento' and not v and nome != 'corte'):
                continue
            valores[k], origem[k] = v, nome
    return {'perfil': pid, 'valores': valores, 'origem': origem}


# ---------------------------------------------------------------- conferência com o que existe de verdade
def validar(pid: str, modelos_ids: list, vozes: list) -> list:
    """Problemas reais do perfil agora: rede não conectada, página do Meta que não existe, template apagado, voz fora da lista."""
    p = obter(pid)
    erros = []
    contas = pg.status_contas()
    prov = {'youtube': 'google', 'instagram': 'meta', 'facebook': 'meta', 'tiktok': 'tiktok'}
    for r in p['redes']:
        if r == 'kwai':
            continue                         # Kwai é manual: não precisa de conta conectada
        pv = prov.get(r)
        if not pv or not contas.get(pv, {}).get('conectado'):
            erros.append(f'A rede {r.capitalize()} está no perfil, mas a conta não está conectada/autorizada em Postagem.')
    pagina = p['contas'].get('meta_pagina')
    if pagina and any(r in ('instagram', 'facebook') for r in p['redes']):
        if not any(x['id'] == pagina for x in contas.get('meta', {}).get('paginas', [])):
            erros.append('A página do Meta escolhida no perfil não está entre as páginas conectadas.')
    for t in p['templates']:
        if t not in modelos_ids:
            erros.append(f'O template "{t}" do perfil não existe mais.')
    if p['voz'] and vozes and p['voz'] not in vozes:
        erros.append(f'A voz "{p["voz"]}" não está na lista de vozes.')
    return erros


def aplicar_ao_tpl(tpl: dict, perfil: dict, rnd) -> list:
    """Põe a identidade do perfil no template de UM corte. Devolve o que foi aplicado (para o histórico do corte)."""
    notas = []
    cor = perfil['cores'].get('primaria')
    if cor:
        tpl['cor_marca'] = cor
        notas.append(f'cor da marca {cor}')
    if perfil.get('logo') and not tpl.get('logo'):
        tpl['logo'] = perfil['logo']
        notas.append('logo do canal')
    if not tpl.get('estilo_visual') and perfil['estilos_permitidos']:
        ok = [e['id'] for e in vp.listar() if e['id'] in perfil['estilos_permitidos'] and e['status'] != 'unavailable']
        if ok:
            pid = rnd.choice(ok)
            tpl['estilo_visual'], tpl['estilo_forca'], tpl['estilo_off'], tpl['estilo_texto'] = pid, 1.0, [], ''
            notas.append(f'estilo {vp.PRESETS[pid]["nome"]}')
    return notas
