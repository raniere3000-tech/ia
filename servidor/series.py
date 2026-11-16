"""Séries animadas: série, temporadas, episódios, bíblia (o que já é verdade na história), personagens e cenários.

Cada episódio é um projeto normal do Agente 3 (estilo "animado2d"), com uma FOTO da série no momento em que foi criado:
personagens na versão aprovada, cenários e só os fatos APROVADOS da bíblia. Mudar um personagem depois cria uma versão
nova e não altera episódios já feitos. Mudanças propostas pela IA entram na bíblia como "proposta" até a pessoa aprovar.
"""
from __future__ import annotations

import base64
import json
import re
import time
import uuid

import banco as db
import postagem as pg
import produtor
import projetos as pj
import rig2d

PASTA_RIG = pg.DADOS / 'rig2d'
TIPOS_BIBLIA = ('fato', 'relacao', 'objeto', 'mudanca', 'regra', 'evento')


class ErroSerie(pj.ErroProjeto):
    pass


def _id(prefixo: str) -> str:
    return prefixo + uuid.uuid4().hex[:10]


def _txt(v, n: int) -> str:
    return re.sub(r'[\x00-\x1f\x7f]', ' ', str(v or '')).strip()[:n]


def _serie_dados(d: dict) -> dict:
    return {'genero': _txt(d.get('genero'), 60), 'formato': d.get('formato') if d.get('formato') in ('9:16', '16:9', '1:1') else '9:16',
            'publico': _txt(d.get('publico'), 120), 'tom': _txt(d.get('tom'), 120), 'regras': _txt(d.get('regras'), 1500),
            'duracao_alvo': max(15, min(180, int(d.get('duracao_alvo') or 45))), 'cenas_qtd': max(3, min(20, int(d.get('cenas_qtd') or 6)))}


def _linha_serie(r: dict) -> dict:
    return {'id': r['id'], 'titulo': r['titulo'], 'versao': r['versao'], 'criado': r['criado'], 'atualizado': r['atualizado'], **json.loads(r['dados'])}


# ---------------------------------------------------------------- série
def listar() -> list[dict]:
    out = []
    for r in db.todos('SELECT * FROM series ORDER BY atualizado DESC'):
        s = _linha_serie(r)
        s['episodios'] = db.um('SELECT COUNT(*) n FROM episodios WHERE serie_id=?', r['id'])['n']
        s['personagens'] = db.um('SELECT COUNT(*) n FROM personagens WHERE serie_id=?', r['id'])['n']
        out.append(s)
    return out


def criar(d: dict) -> dict:
    titulo = _txt(d.get('titulo'), 80)
    if not titulo:
        raise ErroSerie(400, 'Dê um nome para a série.')
    sid = _id('s')
    agora = time.time()
    db.executar('INSERT INTO series (id, titulo, dados, versao, criado, atualizado) VALUES (?,?,?,1,?,?)', sid, titulo,
                json.dumps(_serie_dados(d), ensure_ascii=False), agora, agora)
    db.executar('INSERT INTO temporadas (id, serie_id, ordem, titulo, arco, metas, criado) VALUES (?,?,1,?,?,?,?)',
                _id('t'), sid, 'Temporada 1', '', '', agora)
    db.evento('series', 'serie_criada', 'serie:' + sid)
    return obter(sid)


def _serie(sid: str) -> dict:
    r = db.um('SELECT * FROM series WHERE id=?', sid)
    if not r:
        raise ErroSerie(404, 'Série não encontrada.')
    return r


def obter(sid: str) -> dict:
    s = _linha_serie(_serie(sid))
    s['temporadas'] = db.todos('SELECT * FROM temporadas WHERE serie_id=? ORDER BY ordem', sid)
    s['episodios'] = listar_episodios(sid)
    s['personagens'] = listar_personagens(sid)
    s['cenarios'] = listar_cenarios(sid)
    s['biblia'] = biblia(sid)
    return s


def atualizar(sid: str, d: dict) -> dict:
    r = _serie(sid)
    if d.get('versao') is not None and int(d['versao']) != r['versao']:
        raise ErroSerie(409, 'Esta série foi mudada em outro aparelho. Abra de novo para ver a versão atual.')
    dados = {**json.loads(r['dados']), **{k: v for k, v in _serie_dados({**json.loads(r['dados']), **d}).items()}}
    titulo = _txt(d.get('titulo'), 80) or r['titulo']
    db.executar('UPDATE series SET titulo=?, dados=?, versao=versao+1, atualizado=? WHERE id=?', titulo, json.dumps(dados, ensure_ascii=False), time.time(), sid)
    return obter(sid)


def criar_temporada(sid: str, d: dict) -> dict:
    _serie(sid)
    n = db.um('SELECT COALESCE(MAX(ordem),0)+1 n FROM temporadas WHERE serie_id=?', sid)['n']
    tid = _id('t')
    db.executar('INSERT INTO temporadas (id, serie_id, ordem, titulo, arco, metas, criado) VALUES (?,?,?,?,?,?,?)', tid, sid, n,
                _txt(d.get('titulo'), 80) or f'Temporada {n}', _txt(d.get('arco'), 600), _txt(d.get('metas'), 600), time.time())
    return db.um('SELECT * FROM temporadas WHERE id=?', tid)


# ---------------------------------------------------------------- personagens
def _pub_personagem(r: dict) -> dict:
    return {'id': r['id'], 'serie_id': r['serie_id'], 'nome': r['nome'], 'versao': r['versao'], 'aprovado': bool(r['aprovado']),
            'rig_id': rig2d.RIG_ID, 'dados': json.loads(r['dados']), 'atualizado': r['atualizado']}


def listar_personagens(sid: str = '') -> list[dict]:
    rows = db.todos('SELECT * FROM personagens WHERE serie_id=? ORDER BY criado', sid) if sid else db.todos('SELECT * FROM personagens ORDER BY criado')
    return [_pub_personagem(r) for r in rows]


def _slug(nome: str) -> str:
    s = re.sub(r'[^a-z0-9]+', '-', nome.lower().translate(str.maketrans('áàâãéêíóôõúçü', 'aaaaeeioooucu'))).strip('-')
    return s[:20] or 'personagem'


def criar_personagem(d: dict) -> dict:
    sid = str(d.get('serie_id') or '')
    if sid:
        _serie(sid)
    p = rig2d.validar_personagem(d.get('dados') or d)
    base = _slug(p['nome'])
    pid, k = base, 2
    while db.um('SELECT id FROM personagens WHERE id=?', pid):
        pid, k = f'{base}-{k}', k + 1
    agora = time.time()
    db.executar('INSERT INTO personagens (id, serie_id, nome, dados, versao, aprovado, criado, atualizado) VALUES (?,?,?,?,1,0,?,?)',
                pid, sid, p['nome'], json.dumps(p, ensure_ascii=False), agora, agora)
    db.executar('INSERT INTO personagens_versoes (personagem_id, versao, dados, t) VALUES (?,1,?,?)', pid, json.dumps(p, ensure_ascii=False), agora)
    return obter_personagem(pid)


def obter_personagem(pid: str) -> dict:
    r = db.um('SELECT * FROM personagens WHERE id=?', pid)
    if not r:
        raise ErroSerie(404, 'Personagem não encontrado.')
    out = _pub_personagem(r)
    out['versoes'] = [v['versao'] for v in db.todos('SELECT versao FROM personagens_versoes WHERE personagem_id=? ORDER BY versao', pid)]
    return out


def salvar_rig(pid: str, d: dict) -> dict:
    """Muda a aparência (cria versão nova; episódios já feitos continuam com a antiga) e/ou aprova a folha de modelo."""
    r = db.um('SELECT * FROM personagens WHERE id=?', pid)
    if not r:
        raise ErroSerie(404, 'Personagem não encontrado.')
    if d.get('versao') is not None and int(d['versao']) != r['versao']:
        raise ErroSerie(409, 'Este personagem foi mudado em outro aparelho. Abra de novo.')
    atual = json.loads(r['dados'])
    novo = rig2d.validar_personagem({**atual, **(d.get('dados') or {})}) if d.get('dados') else atual
    agora = time.time()
    if novo != atual:
        v = r['versao'] + 1
        db.executar('UPDATE personagens SET nome=?, dados=?, versao=?, aprovado=0, atualizado=? WHERE id=?', novo['nome'], json.dumps(novo, ensure_ascii=False), v, agora, pid)
        db.executar('INSERT OR REPLACE INTO personagens_versoes (personagem_id, versao, dados, t) VALUES (?,?,?,?)', pid, v, json.dumps(novo, ensure_ascii=False), agora)
    if 'aprovado' in d:
        db.executar('UPDATE personagens SET aprovado=?, atualizado=? WHERE id=?', 1 if d['aprovado'] else 0, agora, pid)
    return obter_personagem(pid)


def _png64(arq) -> str:
    return 'data:image/png;base64,' + base64.b64encode(arq.read_bytes()).decode()


def folha(pid: str = '', dados: dict | None = None) -> dict:
    """Folha de modelo (corpo, 6 expressões). Com `dados`, é só uma prévia sem salvar."""
    p = rig2d.validar_personagem(dados if dados is not None else obter_personagem(pid)['dados'])
    arq = PASTA_RIG / 'folhas' / f'{rig2d.assinatura(p)}.png'
    if not arq.exists():
        arq.parent.mkdir(parents=True, exist_ok=True)
        rig2d.folha_modelo(p, PASTA_RIG, arq)
    return {'png': _png64(arq), 'limites': 'Só vista de frente (sem ¾ e perfil). Boca pelo volume da voz (aproximada).'}


# ---------------------------------------------------------------- cenários
def listar_cenarios(sid: str = '') -> list[dict]:
    rows = db.todos('SELECT * FROM cenarios WHERE serie_id=? ORDER BY criado', sid) if sid else db.todos('SELECT * FROM cenarios ORDER BY criado')
    return [{'id': r['id'], 'serie_id': r['serie_id'], 'nome': r['nome'], 'versao': r['versao'], 'dados': json.loads(r['dados'])} for r in rows]


def criar_cenario(d: dict) -> dict:
    sid = str(d.get('serie_id') or '')
    if sid:
        _serie(sid)
    c = rig2d.validar_cenario(d.get('dados') or d)
    cid = _slug(c['nome'])
    k = 2
    while db.um('SELECT id FROM cenarios WHERE id=?', cid):
        cid, k = f'{_slug(c["nome"])}-{k}', k + 1
    agora = time.time()
    db.executar('INSERT INTO cenarios (id, serie_id, nome, dados, versao, criado, atualizado) VALUES (?,?,?,?,1,?,?)', cid, sid, c['nome'],
                json.dumps(c, ensure_ascii=False), agora, agora)
    return next(x for x in listar_cenarios(sid) if x['id'] == cid)


def atualizar_cenario(cid: str, d: dict) -> dict:
    r = db.um('SELECT * FROM cenarios WHERE id=?', cid)
    if not r:
        raise ErroSerie(404, 'Cenário não encontrado.')
    c = rig2d.validar_cenario({**json.loads(r['dados']), **(d.get('dados') or d)})
    db.executar('UPDATE cenarios SET nome=?, dados=?, versao=versao+1, atualizado=? WHERE id=?', c['nome'], json.dumps(c, ensure_ascii=False), time.time(), cid)
    return next(x for x in listar_cenarios(r['serie_id']) if x['id'] == cid)


def previa_cenario(d: dict, formato: str = '9:16') -> dict:
    import estilos_codigo as ec
    c = rig2d.validar_cenario(d)
    W, H = ec.FORMATOS.get(formato, ec.FORMATOS['9:16'])
    arq = PASTA_RIG / 'cenarios' / (re.sub(r'[^a-z0-9]', '', json.dumps(c, sort_keys=True).lower())[:40] + f'-{W}x{H}.png')
    arq.parent.mkdir(parents=True, exist_ok=True)
    ec._fundo_cenario(c, W // 4, H // 4, 0.80 if H > W else 0.86, arq)
    return {'png': _png64(arq)}


# ---------------------------------------------------------------- bíblia
def biblia(sid: str, estado: str = '') -> list[dict]:
    if estado:
        return db.todos('SELECT * FROM biblia WHERE serie_id=? AND estado=? ORDER BY criado', sid, estado)
    return db.todos("SELECT * FROM biblia WHERE serie_id=? AND estado!='substituida' ORDER BY criado", sid)


def salvar_biblia(sid: str, entradas: list) -> list[dict]:
    """Grava a bíblia. Um fato aprovado não muda em silêncio: mudar o texto cria uma entrada nova e a antiga fica guardada como substituída."""
    _serie(sid)
    if not isinstance(entradas, list):
        raise ErroSerie(400, 'Lista inválida.')
    agora = time.time()
    vistos = set()
    for e in entradas[:300]:
        if not isinstance(e, dict):
            continue
        texto = _txt(e.get('texto'), 500)
        tipo = e.get('tipo') if e.get('tipo') in TIPOS_BIBLIA else 'fato'
        estado = e.get('estado') if e.get('estado') in ('proposta', 'aprovada', 'rejeitada') else 'proposta'
        alvo = re.sub(r'[^a-z0-9_-]', '', str(e.get('alvo') or '').lower())[:40]
        atual = db.um('SELECT * FROM biblia WHERE id=? AND serie_id=?', str(e.get('id') or ''), sid) if e.get('id') else None
        if atual and e.get('apagar'):
            if atual['estado'] == 'aprovada':
                db.executar("UPDATE biblia SET estado='substituida' WHERE id=?", atual['id'])
            else:
                db.executar('DELETE FROM biblia WHERE id=?', atual['id'])
            continue
        if not texto:
            continue
        if atual and atual['estado'] == 'aprovada' and (atual['texto'] != texto or atual['alvo'] != alvo):
            db.executar("UPDATE biblia SET estado='substituida' WHERE id=?", atual['id'])
            novo = _id('b')
            db.executar('INSERT INTO biblia (id, serie_id, tipo, alvo, texto, episodio_id, estado, substitui, criado) VALUES (?,?,?,?,?,?,?,?,?)',
                        novo, sid, 'mudanca' if tipo == 'fato' else tipo, alvo, texto, atual['episodio_id'], estado, atual['id'], agora)
            vistos.add(novo)
        elif atual:
            db.executar('UPDATE biblia SET tipo=?, alvo=?, texto=?, estado=? WHERE id=?', tipo, alvo, texto, estado, atual['id'])
            vistos.add(atual['id'])
        else:
            novo = _id('b')
            db.executar('INSERT INTO biblia (id, serie_id, tipo, alvo, texto, episodio_id, estado, substitui, criado) VALUES (?,?,?,?,?,?,?,?,?)',
                        novo, sid, tipo, alvo, texto, str(e.get('episodio_id') or '')[:40], estado, None, agora)
    db.evento('series', 'biblia_salva', 'serie:' + sid)
    return biblia(sid)


# ---------------------------------------------------------------- episódios
def listar_episodios(sid: str) -> list[dict]:
    out = []
    for e in db.todos('SELECT * FROM episodios WHERE serie_id=? ORDER BY ordem', sid):
        p = db.um('SELECT status, titulo FROM projetos WHERE id=?', e['projeto_id'] or '')
        e['status'] = (p or {}).get('status', '')
        e['status_nome'] = produtor.ESTADOS.get(e['status'], e['status'])
        out.append(e)
    return out


def foto_da_serie(sid: str, ate_ordem: int | None = None) -> dict:
    """O que o Agente 3 pode usar ao escrever um episódio: só personagens, cenários e fatos APROVADOS."""
    s = _linha_serie(_serie(sid))
    pers = {p['id']: p['dados'] for p in listar_personagens(sid)}
    cens = {c['id']: c['dados'] for c in listar_cenarios(sid)}
    fatos = [(f'[{b["alvo"]}] ' if b['alvo'] else '') + b['texto'] for b in biblia(sid, 'aprovada')]
    ant = [{'ordem': e['ordem'], 'titulo': e['titulo'], 'resumo': e['resumo']} for e in listar_episodios(sid) if ate_ordem is None or e['ordem'] < ate_ordem]
    return {'serie_id': sid, 'titulo': s['titulo'], 'genero': s['genero'], 'tom': s['tom'], 'publico': s['publico'], 'regras': s['regras'],
            'personagens': pers, 'versoes': {p['id']: p['versao'] for p in listar_personagens(sid)}, 'cenarios': cens, 'biblia': fatos, 'anteriores': ant}


def criar_episodio(sid: str, d: dict, dispositivo: str = '') -> dict:
    s = _linha_serie(_serie(sid))
    if not listar_personagens(sid):
        raise ErroSerie(400, 'Crie pelo menos um personagem antes do primeiro episódio.')
    if not listar_cenarios(sid):
        criar_cenario({'serie_id': sid, 'nome': 'Parque', 'tipo': 'parque'})
    temporadas = db.todos('SELECT * FROM temporadas WHERE serie_id=? ORDER BY ordem', sid)
    tid = str(d.get('temporada_id') or (temporadas[-1]['id'] if temporadas else ''))
    ordem = db.um('SELECT COALESCE(MAX(ordem),0)+1 n FROM episodios WHERE serie_id=?', sid)['n']
    titulo = _txt(d.get('titulo'), 100) or f'Episódio {ordem}'
    resumo = _txt(d.get('resumo') or d.get('tema'), 800)
    if not resumo:
        raise ErroSerie(400, 'Escreva do que trata o episódio.')
    foto = foto_da_serie(sid, ordem)
    foto['episodio'] = {'ordem': ordem, 'titulo': titulo}
    briefing = {'tema': f'{titulo}: {resumo}', 'nicho': s['genero'] or 'Animação', 'tipo': 'animação com personagens', 'estilo': 'animado2d',
                'formato': s['formato'], 'duracao_alvo': s['duracao_alvo'], 'cenas_qtd': s['cenas_qtd'], 'publico': s['publico'],
                'descricao': f'Episódio {ordem} da série "{s["titulo"]}". {resumo}', 'imagens': 'nenhuma',
                'modo_aprovacao': d.get('modo_aprovacao') if d.get('modo_aprovacao') in ('assistido', 'supervisionado') else 'assistido',
                'destinos': d.get('destinos') or {'redes': [], 'quando': 'proximo'}}
    proj = produtor.novo({'briefing': briefing, 'modo': 'assistido'}, dispositivo)
    pj.mudar_dados(proj['id'], lambda dd, _p: dd.update(serie=foto))
    eid = _id('e')
    agora = time.time()
    db.executar('INSERT INTO episodios (id, serie_id, temporada_id, ordem, titulo, resumo, projeto_id, criado, atualizado) VALUES (?,?,?,?,?,?,?,?,?)',
                eid, sid, tid, ordem, titulo, resumo, proj['id'], agora, agora)
    db.executar('UPDATE series SET atualizado=? WHERE id=?', agora, sid)
    db.evento('series', 'episodio_criado', 'serie:' + sid, {'episodio': eid, 'projeto': proj['id']})
    if d.get('produzir'):
        produtor.produzir(proj['id'], dispositivo=dispositivo)
    return next(e for e in listar_episodios(sid) if e['id'] == eid)


def propostas_do_episodio(eid: str) -> list[dict]:
    """Leva as mudanças que a IA percebeu no roteiro do episódio para a bíblia, como proposta (a pessoa aprova ou não)."""
    e = db.um('SELECT * FROM episodios WHERE id=?', eid)
    if not e:
        raise ErroSerie(404, 'Episódio não encontrado.')
    p = pj.obter(e['projeto_id'])
    novas = [{'tipo': 'mudanca', 'alvo': m.get('alvo', ''), 'texto': m.get('texto', ''), 'estado': 'proposta', 'episodio_id': eid}
             for m in p['dados'].get('mudancas_propostas') or []]
    ja = {b['texto'] for b in biblia(e['serie_id'])}
    salvar_biblia(e['serie_id'], [n for n in novas if n['texto'] not in ja])
    return biblia(e['serie_id'])
