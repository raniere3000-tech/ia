"""Catálogo local das skills: instala só o texto SKILL.md de commits fixos, confere o hash, guarda versões e permite voltar.

Nada daqui executa código vindo de fora. Estado de cada skill (só o que foi conferido de verdade):
  nao_instalada        ainda não baixada
  definicao_instalada  arquivo guardado e conferido, mas sem regras aproveitáveis
  regras_disponiveis   arquivo conferido e regras de texto prontas para os agentes
  dep_externa_pendente depende de programa ou serviço externo que não está no servidor; só o texto pode ser lido
  incompativel         o arquivo não serve (não é texto, grande demais, manifesto inválido)
  falha_integridade    o arquivo mudou ou sumiu; a versão anterior continua guardada
  (executor_em_teste / executor_operacional ficam reservados: nenhuma skill roda programa neste servidor.)
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

import banco as db
import postagem as pg
from skills import seguranca as sg

MANIFESTO = Path(os.getenv('SKILLS_MANIFESTO') or Path(__file__).with_name('manifesto.json'))
PASTA = pg.DADOS / 'skills'
NOMES_ESTADO = {
    'nao_instalada': 'Não instalada', 'definicao_instalada': 'Texto instalado', 'regras_disponiveis': 'Regras prontas',
    'executor_em_teste': 'Executor em teste', 'executor_operacional': 'Executor funcionando', 'dep_externa_pendente': 'Depende de programa externo',
    'incompativel': 'Incompatível', 'desativada': 'Desligada', 'falha_integridade': 'Arquivo alterado ou sumiu',
}
USAVEIS = ('regras_disponiveis', 'dep_externa_pendente')
_cache: dict = {}


class ErroSkill(Exception):
    def __init__(self, status: int, msg: str):
        super().__init__(msg)
        self.status = status


def manifesto() -> dict:
    st = MANIFESTO.stat().st_mtime
    if _cache.get('t') != st:
        m = json.loads(MANIFESTO.read_text(encoding='utf-8'))
        m['por_id'] = {s['id']: s for s in m['skills']}
        _cache.update(t=st, m=m)
    return _cache['m']


def _item(sid: str) -> dict:
    s = manifesto()['por_id'].get(sid)
    if not s:
        raise ErroSkill(404, 'Skill não encontrada no manifesto.')
    return s


def _raw(s: dict, commit: str) -> str:
    return f'https://raw.githubusercontent.com/{s["repo"]}/{commit}/{s["caminho"]}'


def _arquivo(sid: str, sha: str) -> Path:
    return PASTA / sid / f'{sha}.md'


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _baixar(url: str) -> bytes:
    if not sg.url_permitida(url):
        raise ValueError('origem não permitida')
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'EstudioClip'}), timeout=40) as r:
            b = r.read(sg.MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise ValueError(f'a origem respondeu {e.code}')
    except (urllib.error.URLError, OSError) as e:
        raise ConnectionError(f'sem conexão com o GitHub ({getattr(e, "reason", e)})')
    if len(b) > sg.MAX_BYTES:
        raise ValueError('arquivo grande demais')
    return b


def _linha(sid: str) -> dict | None:
    return db.um('SELECT * FROM skills_catalogo WHERE id=?', sid)


def sincronizar():
    """Garante uma linha por skill do manifesto (sem apagar nada) e confere os arquivos já instalados."""
    for s in manifesto()['skills']:
        if sg.item_manifesto_valido(s) or _linha(s['id']):
            continue
        sem_lic = not s.get('licenca')
        db.executar('INSERT OR IGNORE INTO skills_catalogo (id, nome, origem_url, arquivo_origem, commit_sha, sha256, categoria, tipo, estado, licenca, '
                    'versao, deps_json, capacidades_json, atualizado, ativa, motivo) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    s['id'], s['id'], f'https://github.com/{s["repo"]}', s['caminho'], s['commit'], s['sha256'], s['categoria'], s['tipo'],
                    'nao_instalada', s.get('licenca') or '', s['commit'][:7], json.dumps([s['modalidade']] if s['modalidade'] != 'guia' else []),
                    json.dumps(['orientacao']), time.time(), 0 if sem_lic else 1,
                    'Licença não confirmada na origem: fica desligada até você conferir e ligar.' if sem_lic else '')
    verificar(registrar=False)


def _estado_para(s: dict, info: dict) -> tuple[str, str]:
    if s['modalidade'] == 'externo-condicional':
        return 'dep_externa_pendente', 'Depende de programa ou serviço externo que não está no servidor; só as regras de texto são usadas.'
    if len(info['regras']) < 2:
        return 'definicao_instalada', 'O texto foi instalado, mas não tem regras em lista que os agentes possam usar.'
    if s['modalidade'] == 'runtime-auditar':
        return 'regras_disponiveis', 'Só as regras de texto. O programa que acompanha esta skill não roda aqui (precisa de auditoria).'
    return 'regras_disponiveis', ''


def instalar_um(sid: str, commit: str = '', sha: str = '') -> dict:
    """Baixa, confere e instala uma versão. Troca atômica: a versão anterior continua guardada para voltar."""
    s = _item(sid)
    motivo = sg.item_manifesto_valido(s)
    if motivo:
        db.executar("UPDATE skills_catalogo SET estado='incompativel', motivo=?, ultimo_teste=? WHERE id=?", motivo, time.time(), sid)
        return {'id': sid, 'ok': False, 'motivo': motivo}
    commit, sha = commit or s['commit'], sha or s['sha256']
    atual = _linha(sid) or {}
    destino = _arquivo(sid, sha)
    if atual.get('sha256') == sha and atual.get('estado') in (*USAVEIS, 'definicao_instalada') and destino.is_file() \
            and _sha(destino.read_bytes()) == sha:
        return {'id': sid, 'ok': True, 'ja_estava': True}
    try:
        b = destino.read_bytes() if destino.is_file() and _sha(destino.read_bytes()) == sha else _baixar(_raw(s, commit))
        if _sha(b) != sha:
            raise ValueError('o arquivo na origem não confere com o hash fixado (mudou ou foi trocado)')
        info = sg.extrair(sg.validar_texto(b))
    except ConnectionError as e:
        return {'id': sid, 'ok': False, 'motivo': str(e), 'temporario': True}
    except ValueError as e:
        tem_ant = atual.get('estado') in (*USAVEIS, 'definicao_instalada')
        db.executar('UPDATE skills_catalogo SET estado=?, motivo=?, ultimo_teste=? WHERE id=?',
                    atual.get('estado') if tem_ant else ('falha_integridade' if 'hash' in str(e) else 'incompativel'),
                    f'Não instalei a versão nova: {e}.' + (' A anterior continua valendo.' if tem_ant else ''), time.time(), sid)
        return {'id': sid, 'ok': False, 'motivo': str(e)}
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix('.tmp')
    tmp.write_bytes(b)
    os.replace(tmp, destino)
    estado, motivo = _estado_para(s, info)
    anterior = atual.get('sha256') if atual.get('sha256') != sha and _arquivo(sid, atual.get('sha256') or '-').is_file() else atual.get('versao_anterior')
    db.executar('UPDATE skills_catalogo SET nome=?, commit_sha=?, sha256=?, versao=?, estado=?, motivo=?, ultimo_teste=?, atualizado=?, '
                'versao_anterior=?, regras_json=? WHERE id=?',
                info['nome'] or sid, commit, sha, commit[:7], estado, motivo if atual.get('ativa', 1) else (atual.get('motivo') or motivo),
                time.time(), time.time(), anterior, json.dumps(info, ensure_ascii=False), sid)
    db.evento('skills', 'skill_instalada', 'skill:' + sid, {'commit': commit[:12], 'estado': estado})
    return {'id': sid, 'ok': True, 'estado': estado}


def instalar(ids: list | None = None, ctx=None) -> dict:
    sincronizar()
    lista = [s['id'] for s in manifesto()['skills'] if not ids or s['id'] in ids]
    ordem = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}
    lista.sort(key=lambda i: ordem.get(manifesto()['por_id'][i]['prioridade'], 9))
    rel = {'instaladas': [], 'ja_estavam': [], 'falhas': []}
    for n, sid in enumerate(lista):
        if ctx:
            if ctx.cancelado():
                break
            ctx.progresso(int(100 * n / max(1, len(lista))), f'Instalando {sid} ({n + 1} de {len(lista)})')
        r = instalar_um(sid)
        (rel['ja_estavam'] if r.get('ja_estava') else rel['instaladas'] if r['ok'] else rel['falhas']).append(
            sid if r['ok'] else {'id': sid, 'motivo': r['motivo']})
    db.kv_gravar('skills_ultima_instalacao', {'t': time.time(), 'instaladas': len(rel['instaladas']), 'ja_estavam': len(rel['ja_estavam']),
                                               'falhas': rel['falhas'][:120]})
    return rel


def verificar(registrar: bool = True) -> dict:
    """Confere de novo cada arquivo instalado (hash e regras). Não baixa nada."""
    ok, problemas = 0, []
    for r in db.todos("SELECT * FROM skills_catalogo WHERE estado NOT IN ('nao_instalada','incompativel')"):
        arq = _arquivo(r['id'], r['sha256'])
        try:
            b = arq.read_bytes()
            if _sha(b) != r['sha256']:
                raise ValueError('o arquivo foi alterado no aparelho')
            info = sg.extrair(sg.validar_texto(b))
        except (OSError, ValueError) as e:
            m = 'o arquivo sumiu' if isinstance(e, OSError) else str(e)
            db.executar("UPDATE skills_catalogo SET estado='falha_integridade', motivo=?, ultimo_teste=? WHERE id=?",
                        f'{m.capitalize()}. Reinstale ou volte para a versão anterior.', time.time(), r['id'])
            problemas.append({'id': r['id'], 'motivo': m})
            continue
        ok += 1
        if registrar or r['estado'] == 'falha_integridade':
            s = manifesto()['por_id'].get(r['id'], {'modalidade': 'guia'})
            est, mot = _estado_para(s, info)
            db.executar('UPDATE skills_catalogo SET estado=?, motivo=?, ultimo_teste=?, regras_json=? WHERE id=?',
                        est, mot if r['ativa'] else r['motivo'], time.time(), json.dumps(info, ensure_ascii=False), r['id'])
    return {'conferidas': ok, 'problemas': problemas}


def ativar(sid: str, ligar: bool) -> dict:
    r = _linha(sid)
    if not r:
        raise ErroSkill(404, 'Skill não encontrada.')
    db.executar('UPDATE skills_catalogo SET ativa=?, motivo=? WHERE id=?', 1 if ligar else 0,
                '' if ligar else 'Desligada por você.', sid)
    db.evento('skills', 'skill_ligada' if ligar else 'skill_desligada', 'skill:' + sid)
    return obter(sid)


def rollback(sid: str) -> dict:
    r = _linha(sid)
    if not r or not r.get('versao_anterior'):
        raise ErroSkill(409, 'Não há versão anterior guardada desta skill.')
    ant = r['versao_anterior']
    arq = _arquivo(sid, ant)
    try:
        b = arq.read_bytes()
        if _sha(b) != ant:
            raise ValueError('a versão anterior também foi alterada')
        info = sg.extrair(sg.validar_texto(b))
    except (OSError, ValueError) as e:
        raise ErroSkill(409, f'Não deu para voltar: {e if isinstance(e, ValueError) else "o arquivo anterior sumiu"}.')
    s = _item(sid)
    est, mot = _estado_para(s, info)
    commit = (db.kv('skills_commits_por_sha') or {}).get(ant, '')
    _lembrar_commit(r['sha256'], r['commit_sha'])
    db.executar('UPDATE skills_catalogo SET sha256=?, versao_anterior=?, commit_sha=?, versao=?, estado=?, motivo=?, regras_json=?, ultimo_teste=?, atualizado=? WHERE id=?',
                ant, r['sha256'], commit or r['commit_sha'], (commit or r['commit_sha'])[:7], est, mot, json.dumps(info, ensure_ascii=False),
                time.time(), time.time(), sid)
    db.evento('skills', 'skill_rollback', 'skill:' + sid, {'para': ant[:12]})
    return obter(sid)


def _lembrar_commit(sha: str, commit: str):
    m = db.kv('skills_commits_por_sha') or {}
    m[sha] = commit
    db.kv_gravar('skills_commits_por_sha', m)


def atualizacoes(ctx=None) -> dict:
    """Procura versões novas (não instala). Usa a API pública do GitHub só para saber o commit mais recente."""
    m = manifesto()
    repos = sorted({s['repo'] for s in m['skills']})
    cand, erros = {}, []
    for n, repo in enumerate(repos):
        if ctx:
            ctx.progresso(int(100 * n / len(repos)), f'Olhando {repo}')
        try:
            st, _, j = pg.http('GET', f'https://api.github.com/repos/{repo}/commits/HEAD', cab={'Accept': 'application/vnd.github+json'}, tempo=30)
        except pg.ErroTemporario as e:
            erros.append({'repo': repo, 'motivo': str(e)})
            continue
        novo = (j or {}).get('sha', '') if st == 200 else ''
        if not sg._SHA.fullmatch(novo):
            erros.append({'repo': repo, 'motivo': f'o GitHub respondeu {st}'})
            continue
        for s in m['skills']:
            if s['repo'] != repo:
                continue
            r = _linha(s['id']) or {}
            if r.get('commit_sha') == novo:
                continue
            try:
                b = _baixar(_raw(s, novo))
                sg.validar_texto(b)
            except (ValueError, ConnectionError) as e:
                erros.append({'repo': repo, 'id': s['id'], 'motivo': str(e)})
                continue
            h = _sha(b)
            if h != r.get('sha256'):
                cand[s['id']] = {'commit': novo, 'sha256': h, 'visto': time.time()}
    db.kv_gravar('skills_candidatas', cand)
    return {'candidatas': cand, 'erros': erros[:50], 'conferido': time.time()}


def aplicar_atualizacao(sid: str) -> dict:
    c = (db.kv('skills_candidatas') or {}).get(sid)
    if not c:
        raise ErroSkill(409, 'Não há versão nova conferida desta skill. Procure atualizações primeiro.')
    r = _linha(sid) or {}
    if r.get('sha256') and r.get('commit_sha'):
        _lembrar_commit(r['sha256'], r['commit_sha'])
    res = instalar_um(sid, c['commit'], c['sha256'])
    if not res['ok']:
        raise ErroSkill(502, f'A versão nova não passou na conferência: {res["motivo"]}.')
    cand = db.kv('skills_candidatas') or {}
    cand.pop(sid, None)
    db.kv_gravar('skills_candidatas', cand)
    return obter(sid)


def _publico(r: dict, detalhe: bool = False) -> dict:
    s = manifesto()['por_id'].get(r['id'], {})
    info = json.loads(r.get('regras_json') or '{}')
    d = {'id': r['id'], 'nome': r['nome'], 'origem': r['origem_url'], 'arquivo': r['arquivo_origem'], 'versao': r['versao'], 'commit': r['commit_sha'],
         'sha256': r['sha256'], 'categoria': r['categoria'], 'tipo': r['tipo'], 'estado': r['estado'], 'estado_nome': NOMES_ESTADO.get(r['estado'], r['estado']),
         'licenca': r['licenca'] or '', 'ativa': bool(r['ativa']), 'motivo': r['motivo'] or '', 'ultimo_teste': r['ultimo_teste'],
         'tem_anterior': bool(r['versao_anterior']), 'uso': s.get('uso', ''), 'agentes': s.get('agentes', []), 'modalidade': s.get('modalidade', ''),
         'prioridade': s.get('prioridade', ''), 'gatilho': s.get('gatilho', ''), 'descricao': info.get('descricao', ''), 'n_regras': len(info.get('regras', [])),
         'usavel': bool(r['ativa']) and r['estado'] in USAVEIS and bool(info.get('regras')),
         'nova_versao': bool((db.kv('skills_candidatas') or {}).get(r['id']))}
    if detalhe:
        d['regras'] = [x['texto'] for x in info.get('regras', [])][:40]
        d['descartadas'] = info.get('descartadas', 0)
    return d


def listar(agente: str = '', estado: str = '', busca: str = '') -> list[dict]:
    out = []
    for r in db.todos('SELECT * FROM skills_catalogo ORDER BY id'):
        d = _publico(r)
        if agente and agente not in d['agentes']:
            continue
        if estado == 'usavel' and not d['usavel'] or estado and estado != 'usavel' and d['estado'] != estado:
            continue
        if busca and busca.lower() not in (d['id'] + ' ' + d['uso'] + ' ' + d['gatilho'] + ' ' + d['descricao']).lower():
            continue
        out.append(d)
    return out


def obter(sid: str) -> dict:
    r = _linha(sid)
    if not r:
        raise ErroSkill(404, 'Skill não encontrada.')
    return _publico(r, True)


def regras(sid: str) -> tuple[str, list[str]] | None:
    r = _linha(sid)
    if not r or not r['ativa'] or r['estado'] not in USAVEIS:
        return None
    info = json.loads(r.get('regras_json') or '{}')
    return (info.get('descricao', ''), [x['texto'] for x in info.get('regras', [])]) if info.get('regras') else None


def resumo() -> dict:
    est = {r['estado']: r['n'] for r in db.todos('SELECT estado, COUNT(*) n FROM skills_catalogo GROUP BY estado')}
    usaveis = sum(1 for d in listar() if d['usavel'])
    return {'total': len(manifesto()['skills']), 'estados': est, 'usaveis': usaveis, 'ultima_instalacao': db.kv('skills_ultima_instalacao'),
            'candidatas': len(db.kv('skills_candidatas') or {}), 'pasta': str(PASTA),
            'trabalho': db.um("SELECT id, status, etapa, progresso, erro, dados FROM jobs WHERE tipo='skills.instalar' ORDER BY criado DESC LIMIT 1")}
