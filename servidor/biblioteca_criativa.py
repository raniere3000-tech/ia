"""Biblioteca Criativa: modelos de roteiro, pacotes visuais e perfis de narração reutilizáveis pelas linhas de conteúdo.

- Cada mudança gera uma VERSÃO nova; as versões antigas ficam guardadas e nunca mudam.
- O episódio guarda a versão que usou: mudar o item depois não altera vídeo já feito.
- Campo com cadeado só muda se você tirar o cadeado no mesmo pedido.
- Personagens e cenários continuam na biblioteca das séries (series.py); aqui não há cópia deles.
"""
from __future__ import annotations

import json
import time
import uuid

import banco as db

TIPOS = {
    'modelo_roteiro': {'nome': 'Modelo de roteiro', 'campos': {'estrutura': 1500, 'gancho': 200, 'instrucoes': 1500, 'final': 300}},
    'pacote_visual': {'nome': 'Pacote visual', 'campos': {'estilo': 40, 'formato': 8, 'imagens': 10, 'observacoes': 800}},
    'perfil_narracao': {'nome': 'Perfil de narração', 'campos': {'voz': 40, 'ritmo': 10, 'emocao': 80, 'idioma': 12, 'observacoes': 400}},
}


class ErroBiblioteca(Exception):
    def __init__(self, msg: str, status: int = 400):
        super().__init__(msg)
        self.status = status


def _limpar(tipo: str, d: dict) -> dict:
    import estilos_codigo as ec
    import produtor
    campos = TIPOS[tipo]['campos']
    out = {k: str(d.get(k) or '').strip()[:n] for k, n in campos.items() if d.get(k) not in (None, '')}
    if tipo == 'pacote_visual':
        if out.get('estilo'):
            e = next((x for x in ec.catalogo() if x['id'] == out['estilo']), None)
            if not e:
                raise ErroBiblioteca('Estilo fora do catálogo.')
            if e['status'] == 'indisponivel':
                raise ErroBiblioteca(f'O estilo "{e["nome"]}" não roda neste servidor.')
        if out.get('formato') and out['formato'] not in ec.FORMATOS:
            raise ErroBiblioteca('Formato inválido.')
        if out.get('imagens') and out['imagens'] not in ('nenhuma', 'gemini', 'busca'):
            raise ErroBiblioteca('Imagens: nenhuma, gemini ou busca.')
    if tipo == 'perfil_narracao':
        if out.get('voz') and out['voz'] not in produtor.VOZES + ['nenhuma']:
            raise ErroBiblioteca('Voz fora da lista do servidor.')
        if out.get('ritmo') and out['ritmo'] not in produtor.RITMOS:
            raise ErroBiblioteca('Ritmo inválido.')
    return out


def _item(iid: str) -> dict:
    r = db.um('SELECT * FROM biblioteca_itens WHERE id=? AND apagado=0', iid)
    if not r:
        raise ErroBiblioteca('Item da biblioteca não encontrado.', 404)
    return {**r, 'dados': json.loads(r['dados']), 'travas': json.loads(r['travas'] or '[]'), 'nome_tipo': TIPOS[r['tipo']]['nome']}


def criar(tipo: str, nome: str, dados: dict, travas: list | None = None, quem: str = 'site') -> dict:
    if tipo not in TIPOS:
        raise ErroBiblioteca('Tipo inválido (modelo_roteiro, pacote_visual ou perfil_narracao).')
    nome = str(nome or '').strip()[:80]
    if len(nome) < 2:
        raise ErroBiblioteca('Dê um nome.')
    limpo = _limpar(tipo, dados or {})
    tr = [x for x in (travas or []) if x in TIPOS[tipo]['campos']]
    iid = 'bc_' + uuid.uuid4().hex[:10]
    agora = time.time()
    db.executar('INSERT INTO biblioteca_itens (id, tipo, nome, versao, dados, travas, criado, atualizado) VALUES (?,?,?,?,?,?,?,?)', iid, tipo, nome, 1,
                json.dumps(limpo, ensure_ascii=False), json.dumps(tr), agora, agora)
    db.executar('INSERT INTO biblioteca_versoes (item, versao, dados, motivo, por, criado) VALUES (?,?,?,?,?,?)', iid, 1, json.dumps(limpo, ensure_ascii=False),
                'criado', quem[:80], agora)
    return _item(iid)


def atualizar(iid: str, d: dict, versao: int | None, quem: str = 'site', automatico: bool = False) -> dict:
    """Nova versão. `automatico` (sugestão da IA): campo com cadeado é ignorado. Pedido seu: só muda campo travado se destravar junto."""
    it = _item(iid)
    if versao is None or int(versao) != it['versao']:
        raise ErroBiblioteca('Este item foi mudado em outro aparelho. Abra de novo.', 409)
    travas = [x for x in (d.get('travas', it['travas']) or []) if x in TIPOS[it['tipo']]['campos']]
    novos = dict(d.get('dados') or {})
    bloqueados = [k for k in novos if k in it['travas'] and k in travas and str(novos[k] or '') != str(it['dados'].get(k) or '')]
    if bloqueados and not automatico:
        raise ErroBiblioteca('Campo com cadeado: ' + ', '.join(bloqueados) + '. Tire o cadeado para mudar.', 423)
    for k in bloqueados:
        novos.pop(k)
    dados = _limpar(it['tipo'], {**it['dados'], **novos})
    nome = str(d.get('nome') or it['nome']).strip()[:80]
    if dados == it['dados'] and nome == it['nome'] and travas == it['travas']:
        return it
    nv = it['versao'] + 1
    agora = time.time()
    n = db.executar('UPDATE biblioteca_itens SET nome=?, versao=?, dados=?, travas=?, atualizado=? WHERE id=? AND versao=?', nome, nv,
                    json.dumps(dados, ensure_ascii=False), json.dumps(travas), agora, iid, it['versao'])
    if not n:
        raise ErroBiblioteca('Este item foi mudado em outro aparelho. Abra de novo.', 409)
    db.executar('INSERT INTO biblioteca_versoes (item, versao, dados, motivo, por, criado) VALUES (?,?,?,?,?,?)', iid, nv, json.dumps(dados, ensure_ascii=False),
                str(d.get('motivo') or '')[:200], quem[:80], agora)
    return _item(iid)


def listar(tipo: str = '') -> list:
    sql, a = 'SELECT id FROM biblioteca_itens WHERE apagado=0', []
    if tipo:
        sql += ' AND tipo=?'
        a.append(tipo)
    out = []
    for r in db.todos(sql + ' ORDER BY tipo, nome', *a):
        it = _item(r['id'])
        it['episodios'] = db.um("SELECT COUNT(*) n FROM conteudo_episodios WHERE dados LIKE ?", f'%"{r["id"]}"%')['n']
        out.append(it)
    return out


def versoes(iid: str) -> list:
    _item(iid)
    return [{**r, 'dados': json.loads(r['dados'])} for r in db.todos('SELECT * FROM biblioteca_versoes WHERE item=? ORDER BY versao DESC', iid)]


def versao(iid: str, v: int | None = None) -> dict | None:
    """Dados de uma versão exata (ou da atual). None se o item foi apagado/não existe."""
    r = db.um('SELECT * FROM biblioteca_itens WHERE id=?', iid)
    if not r:
        return None
    v = v or r['versao']
    x = db.um('SELECT * FROM biblioteca_versoes WHERE item=? AND versao=?', iid, v)
    return {'id': iid, 'tipo': r['tipo'], 'nome': r['nome'], 'versao': v, 'dados': json.loads(x['dados'])} if x else None


def apagar(iid: str) -> dict:
    _item(iid)
    db.executar('UPDATE biblioteca_itens SET apagado=1, atualizado=? WHERE id=?', time.time(), iid)
    return {'ok': True, 'aviso': 'Os vídeos já feitos guardam a versão que usaram.'}


def aplicar_no_briefing(b: dict, refs: dict) -> tuple[dict, dict]:
    """Aplica os itens da linha no briefing do episódio. Devolve (briefing, versões usadas) para o episódio guardar."""
    usados = {}
    b = dict(b)
    for tipo in ('modelo_roteiro', 'pacote_visual', 'perfil_narracao'):
        iid = (refs or {}).get(tipo)
        if not iid:
            continue
        it = versao(iid)
        if not it or it['tipo'] != tipo:
            continue
        d = it['dados']
        usados[tipo] = {'id': iid, 'versao': it['versao'], 'nome': it['nome']}
        if tipo == 'modelo_roteiro':
            extra = '\n'.join(x for x in (f'Estrutura: {d["estrutura"]}' if d.get('estrutura') else '', f'Gancho: {d["gancho"]}' if d.get('gancho') else '',
                                          d.get('instrucoes', ''), f'Final: {d["final"]}' if d.get('final') else '') if x)
            b['descricao'] = (b.get('descricao', '') + '\nModelo de roteiro "' + it['nome'] + '":\n' + extra)[:2500]
        elif tipo == 'pacote_visual':
            for k in ('estilo', 'formato', 'imagens'):
                if d.get(k):
                    b[k] = d[k]
        else:
            if d.get('voz'):
                b['voz'] = d['voz']
            if d.get('ritmo'):
                b['ritmo'] = d['ritmo']
            if d.get('emocao') or d.get('observacoes'):
                b['descricao'] = (b.get('descricao', '') + f'\nNarração: {d.get("emocao", "")} {d.get("observacoes", "")}'.rstrip())[:2500]
    return b, usados
