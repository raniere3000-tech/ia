"""Projetos guardados no servidor: o mesmo projeto abre em qualquer aparelho autorizado.

Cada projeto tem uma revisão que só cresce. Quem salva diz em qual revisão estava; se outro aparelho
salvou antes, a resposta é CONFLITO (nada é sobrescrito sem a pessoa decidir). As últimas versões
ficam guardadas para restaurar. Arquivos (imagens, áudios, vídeos) sobem em pedaços, conferidos por
SHA-256, e o mesmo arquivo nunca é guardado duas vezes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import uuid
import zipfile
from pathlib import Path

import banco as db

TIPOS = ('video', 'manual', 'vozes', 'agente3', 'outro')
MAX_DADOS = int(os.getenv('MAX_PROJETO_MB', '8')) * 1024 * 1024
MAX_ARQUIVO = int(os.getenv('MAX_ARQUIVO_MB', '1500')) * 1024 * 1024
MANTER_VERSOES = 40
MIMES = re.compile(r'^(image|audio|video)/[\w.+-]{1,40}$|^application/(json|octet-stream)$')
SCHEMA = 1


class ErroProjeto(Exception):
    def __init__(self, status: int, msg: str, extra: dict | None = None):
        super().__init__(msg)
        self.status = status
        self.msg = msg
        self.extra = extra or {}


def pasta(pid: str) -> Path:
    if not re.fullmatch(r'[a-f0-9]{8,32}', pid or ''):
        raise ErroProjeto(400, 'Projeto inválido.')
    return db.PROJETOS / pid


def _meta(p: dict) -> dict:
    return {k: p[k] for k in ('id', 'titulo', 'tipo', 'modo', 'status', 'revisao', 'criado', 'atualizado', 'dispositivo', 'origem')}


def listar(tipo: str = '') -> list:
    sql = 'SELECT id, titulo, tipo, modo, status, revisao, criado, atualizado, dispositivo, origem FROM projetos WHERE apagado=0'
    if tipo:
        return db.todos(sql + ' AND tipo=? ORDER BY atualizado DESC', tipo)
    return db.todos(sql + ' ORDER BY atualizado DESC')


def obter(pid: str) -> dict:
    p = db.um('SELECT * FROM projetos WHERE id=? AND apagado=0', pid)
    if not p:
        raise ErroProjeto(404, 'Projeto não encontrado no servidor.')
    p['dados'] = json.loads(p['dados'] or '{}')
    return p


def _texto(dados) -> str:
    t = json.dumps(dados, ensure_ascii=False, separators=(',', ':'))
    if len(t.encode()) > MAX_DADOS:
        raise ErroProjeto(413, 'Projeto grande demais para salvar de uma vez. Os arquivos (imagens, áudio, vídeo) precisam subir separados.')
    return t


def criar(d: dict, dispositivo: str = '', origem: str = 'site') -> dict:
    tipo = d.get('tipo') if d.get('tipo') in TIPOS else 'outro'
    chave = str(d.get('origem_chave') or '')[:80]
    if chave:
        ja = db.um('SELECT id FROM projetos WHERE origem_chave=? AND apagado=0', chave)
        if ja:            # o mesmo projeto deste navegador já foi importado: não duplica
            return dict(obter(ja['id']), duplicado=True)
    pid = uuid.uuid4().hex[:16]
    agora = time.time()
    dados = d.get('dados') if isinstance(d.get('dados'), dict) else {}
    texto = _texto(dados)
    titulo = str(d.get('titulo') or 'Projeto sem nome').strip()[:120]
    with db.tx() as c:
        c.execute('INSERT INTO projetos (id, titulo, tipo, modo, status, revisao, schema, dados, criado, atualizado, dispositivo, origem, origem_chave) '
                  'VALUES (?,?,?,?,?,1,?,?,?,?,?,?,?)', (pid, titulo, tipo, str(d.get('modo') or '')[:20], str(d.get('status') or 'rascunho')[:30],
                                                        SCHEMA, texto, agora, agora, dispositivo, origem, chave or None))
        c.execute('INSERT INTO versoes (projeto, revisao, dados, criado, dispositivo, origem) VALUES (?,?,?,?,?,?)',
                  (pid, 1, texto, agora, dispositivo, origem))
    pasta(pid).mkdir(parents=True, exist_ok=True)
    _snapshot(pid)
    db.evento(dispositivo, 'projeto_criado', 'projeto:' + pid, {'tipo': tipo, 'origem': origem})
    return obter(pid)


def atualizar(pid: str, d: dict, dispositivo: str = '', origem: str = 'site') -> dict:
    base = d.get('revisao')
    agora = time.time()
    with db.tx() as c:
        p = c.execute('SELECT revisao, dados, titulo, status, modo FROM projetos WHERE id=? AND apagado=0', (pid,)).fetchone()
        if not p:
            raise ErroProjeto(404, 'Projeto não encontrado no servidor.')
        if base is None or int(base) != p['revisao']:
            raise ErroProjeto(409, 'Este projeto mudou em outro aparelho depois que você abriu.', {'revisao': p['revisao']})
        dados = d['dados'] if isinstance(d.get('dados'), dict) else json.loads(p['dados'] or '{}')
        texto = _texto(dados)
        nova = p['revisao'] + 1
        c.execute('UPDATE projetos SET dados=?, revisao=?, atualizado=?, dispositivo=?, titulo=?, status=?, modo=? WHERE id=?',
                  (texto, nova, agora, dispositivo, str(d.get('titulo') or p['titulo'])[:120], str(d.get('status') or p['status'])[:30],
                   str(d.get('modo') if d.get('modo') is not None else p['modo'])[:20], pid))
        c.execute('INSERT OR REPLACE INTO versoes (projeto, revisao, dados, criado, dispositivo, origem) VALUES (?,?,?,?,?,?)',
                  (pid, nova, texto, agora, dispositivo, origem))
        c.execute('DELETE FROM versoes WHERE projeto=? AND revisao<=?', (pid, nova - MANTER_VERSOES))
    _snapshot(pid)
    return _meta(obter(pid))


def hash_roteiro(dados: dict) -> str:
    """Identifica o conteúdo conferido, sem depender das revisões de status/parecer."""
    gerados = {'audio', 'imagem', 'clipe', 'fotos_planos', 'refazer', 'variante_imagem',
               'variante_voz', 'fotos_recusadas', 'duracao_real'}
    cenas = [{k: v for k, v in c.items() if k not in gerados} for c in dados.get('cenas') or []]
    conteudo = {'briefing': dados.get('briefing'), 'roteiro': dados.get('roteiro'), 'cenas': cenas}
    return hashlib.sha256(json.dumps(conteudo, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def roteiro_aprovado(dados: dict) -> bool:
    ap = dados.get('aprovacao_roteiro') or {}
    return bool(ap.get('aprovado') and ap.get('hash') == hash_roteiro(dados))


def mudar_dados(pid: str, f, origem: str = 'servidor') -> dict:
    """Mudança feita pelo próprio servidor (Agente 3): lê, altera e grava numa revisão nova, sem conflito."""
    for _ in range(5):
        p = obter(pid)
        dados = p['dados']
        r = f(dados, p)
        try:
            atualizar(pid, {'revisao': p['revisao'], 'dados': dados, **(r or {})}, 'servidor', origem)
            return dados
        except ErroProjeto as e:
            if e.status != 409:
                raise
    raise ErroProjeto(409, 'Não consegui salvar o projeto (muitas mudanças ao mesmo tempo).')


def _snapshot(pid: str):
    """Cópia legível do projeto na pasta dele (ajuda backup e recuperação manual)."""
    try:
        p = obter(pid)
        arq = pasta(pid) / 'project.json'
        tmp = arq.with_suffix('.tmp')
        tmp.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding='utf-8')
        tmp.replace(arq)
    except (OSError, ErroProjeto):
        pass


def apagar(pid: str, dispositivo: str = '') -> dict:
    """Vai para a lixeira (não apaga arquivos): dá para restaurar."""
    if not db.executar('UPDATE projetos SET apagado=1, atualizado=? WHERE id=?', time.time(), pid):
        raise ErroProjeto(404, 'Projeto não encontrado.')
    db.evento(dispositivo, 'projeto_lixeira', 'projeto:' + pid)
    return {'ok': True}


def versoes(pid: str) -> list:
    obter(pid)
    return db.todos('SELECT revisao, criado, dispositivo, origem, length(dados) AS tamanho FROM versoes WHERE projeto=? ORDER BY revisao DESC', pid)


def restaurar(pid: str, rev: int, dispositivo: str = '') -> dict:
    v = db.um('SELECT dados FROM versoes WHERE projeto=? AND revisao=?', pid, rev)
    if not v:
        raise ErroProjeto(404, 'Versão não encontrada.')
    p = obter(pid)
    return atualizar(pid, {'revisao': p['revisao'], 'dados': json.loads(v['dados'])}, dispositivo, f'restaurado:{rev}')


def duplicar(pid: str, dispositivo: str = '') -> dict:
    p = obter(pid)
    return criar({'tipo': p['tipo'], 'modo': p['modo'], 'titulo': p['titulo'] + ' (cópia)', 'dados': p['dados']}, dispositivo, 'copia')


# ---------------------------------------------------------------- arquivos
def _pasta_assets() -> Path:
    p = db.PROJETOS.parent / 'assets'
    p.mkdir(parents=True, exist_ok=True)
    return p


def _ext(nome: str, mime: str) -> str:
    m = re.search(r'\.([a-z0-9]{1,5})$', (nome or '').lower())
    if m:
        return '.' + m.group(1)
    return '.' + (mime.split('/')[-1].split(';')[0][:5] if '/' in mime else 'bin')


def asset_info(a: dict) -> dict:
    return {k: a[k] for k in ('id', 'nome', 'mime', 'tamanho', 'sha256', 'projeto', 'criado')}


def upload_inicio(d: dict) -> dict:
    sha = str(d.get('sha256') or '').lower()
    tamanho = int(d.get('tamanho') or 0)
    mime = str(d.get('mime') or 'application/octet-stream')[:60]
    if not re.fullmatch(r'[0-9a-f]{64}', sha):
        raise ErroProjeto(400, 'Falta a impressão digital (SHA-256) do arquivo.')
    if not MIMES.match(mime):
        raise ErroProjeto(415, 'Tipo de arquivo não aceito (só imagem, áudio, vídeo e JSON).')
    if tamanho <= 0 or tamanho > MAX_ARQUIVO:
        raise ErroProjeto(413, f'Arquivo vazio ou maior que {MAX_ARQUIVO // 1048576} MB.')
    ja = db.um('SELECT * FROM assets WHERE sha256=? AND tamanho=?', sha, tamanho)
    if ja and Path(ja['caminho']).exists():
        return {'pronto': True, 'asset': asset_info(ja)}
    up = db.um('SELECT * FROM uploads WHERE sha256=? AND tamanho=?', sha, tamanho)
    if up:                    # envio interrompido: continua de onde parou
        parte = _pasta_assets() / (up['id'] + '.parte')
        rec = parte.stat().st_size if parte.exists() else 0
        return {'pronto': False, 'upload': up['id'], 'recebido': rec}
    uid = uuid.uuid4().hex
    db.executar('INSERT INTO uploads (id, projeto, nome, mime, tamanho, sha256, recebido, criado) VALUES (?,?,?,?,?,?,0,?)',
                uid, str(d.get('projeto') or '')[:32], str(d.get('nome') or 'arquivo')[:120], mime, tamanho, sha, time.time())
    (_pasta_assets() / (uid + '.parte')).write_bytes(b'')
    return {'pronto': False, 'upload': uid, 'recebido': 0}


def upload_pedaco(uid: str, offset: int, dados: bytes) -> dict:
    up = db.um('SELECT * FROM uploads WHERE id=?', uid)
    if not up or not re.fullmatch(r'[0-9a-f]{32}', uid):
        raise ErroProjeto(404, 'Envio não encontrado. Comece de novo.')
    parte = _pasta_assets() / (uid + '.parte')
    atual = parte.stat().st_size if parte.exists() else 0
    if offset + len(dados) <= atual:          # pedaço repetido (retry): ignora sem duplicar
        return {'recebido': atual}
    if offset != atual:
        raise ErroProjeto(409, 'Pedaço fora de ordem.', {'recebido': atual})
    if atual + len(dados) > up['tamanho']:
        raise ErroProjeto(413, 'Recebi mais bytes que o tamanho combinado.')
    with open(parte, 'ab') as f:
        f.write(dados)
    return {'recebido': atual + len(dados)}


def upload_fim(uid: str, origem: str = 'site') -> dict:
    up = db.um('SELECT * FROM uploads WHERE id=?', uid)
    if not up:
        raise ErroProjeto(404, 'Envio não encontrado.')
    parte = _pasta_assets() / (uid + '.parte')
    h = hashlib.sha256()
    with open(parte, 'rb') as f:
        for bloco in iter(lambda: f.read(1 << 20), b''):
            h.update(bloco)
    if parte.stat().st_size != up['tamanho'] or h.hexdigest() != up['sha256']:
        parte.unlink(missing_ok=True)
        db.executar('DELETE FROM uploads WHERE id=?', uid)
        raise ErroProjeto(422, 'O arquivo chegou diferente do original (conexão falhou no meio). Envie de novo.')
    final = _pasta_assets() / (up['sha256'] + _ext(up['nome'], up['mime']))
    parte.replace(final)        # troca atômica: ou o arquivo inteiro, ou nada
    return registrar_asset(final, up['nome'], up['mime'], up['projeto'], origem, up['sha256'], uid)


def registrar_asset(arq: Path, nome: str, mime: str, projeto: str = '', origem: str = 'servidor', sha: str = '', uid: str = '') -> dict:
    if not sha:
        h = hashlib.sha256()
        with open(arq, 'rb') as f:
            for bloco in iter(lambda: f.read(1 << 20), b''):
                h.update(bloco)
        sha = h.hexdigest()
    ja = db.um('SELECT * FROM assets WHERE sha256=?', sha)
    if ja and Path(ja['caminho']).exists():
        if uid:
            db.executar('DELETE FROM uploads WHERE id=?', uid)
        return {'pronto': True, 'asset': asset_info(ja)}
    aid = uuid.uuid4().hex[:16]
    with db.tx() as c:
        c.execute('INSERT INTO assets (id, projeto, nome, mime, tamanho, sha256, caminho, criado, origem) VALUES (?,?,?,?,?,?,?,?,?)',
                  (aid, projeto or '', nome[:120], mime, arq.stat().st_size, sha, str(arq), time.time(), origem))
        if uid:
            c.execute('DELETE FROM uploads WHERE id=?', (uid,))
    return {'pronto': True, 'asset': asset_info(db.um('SELECT * FROM assets WHERE id=?', aid))}


def asset(aid: str) -> dict:
    a = db.um('SELECT * FROM assets WHERE id=?', aid)
    if not a or not Path(a['caminho']).exists():
        raise ErroProjeto(404, 'Arquivo não encontrado no servidor.')
    return a


def assets_por_sha(shas: list) -> dict:
    """Quais destes arquivos o servidor já tem (para não reenviar)."""
    r = {}
    for s in shas[:2000]:
        a = db.um('SELECT * FROM assets WHERE sha256=?', str(s))
        if a and Path(a['caminho']).exists():
            r[s] = asset_info(a)
    return r


def _refs(obj, achados: set):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ('asset', 'asset_id') and isinstance(v, str):
                achados.add(v)
            _refs(v, achados)
    elif isinstance(obj, list):
        for v in obj:
            _refs(v, achados)


def exportar(pid: str) -> Path:
    """Pacote .zip com o projeto e todos os arquivos que ele usa (backup ou levar para outro lugar)."""
    p = obter(pid)
    refs: set = set()
    _refs(p['dados'], refs)
    tmp = Path(tempfile.mkdtemp()) / f'projeto-{pid}.zip'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('project.json', json.dumps(p, ensure_ascii=False, indent=1))
        lista = []
        for aid in sorted(refs):
            try:
                a = asset(aid)
            except ErroProjeto:
                continue
            nome = f'assets/{a["sha256"]}{Path(a["caminho"]).suffix}'
            z.write(a['caminho'], nome, compress_type=zipfile.ZIP_STORED)
            lista.append(dict(asset_info(a), arquivo=nome))
        z.writestr('assets.json', json.dumps(lista, ensure_ascii=False, indent=1))
    return tmp


def limpar_uploads_velhos():
    for up in db.todos('SELECT id FROM uploads WHERE criado < ?', time.time() - 3 * 86400):
        (_pasta_assets() / (up['id'] + '.parte')).unlink(missing_ok=True)
        db.executar('DELETE FROM uploads WHERE id=?', up['id'])


def espaco_livre() -> int:
    try:
        return shutil.disk_usage(db.PROJETOS).free
    except OSError:
        return -1
