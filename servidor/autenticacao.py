"""Aparelhos autorizados: entrar com a senha do servidor, parear um aparelho novo com código de uso único,
listar e desconectar aparelhos.

Cada aparelho recebe uma sessão própria (um segredo longo guardado só nele). No servidor fica apenas o
resumo (hash) da sessão, então nem uma cópia do banco revela as sessões. Nada disso vai em link ou e-mail.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
import uuid
from pathlib import Path

import banco as db

DURACAO = float(os.getenv('SESSAO_DIAS', '120')) * 86400      # renovada a cada uso
CODIGO_MIN = 10                                               # validade do código de pareamento
ALFABETO = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'                  # sem 0/O, 1/I/L
ARQ_ANUNCIO = Path(__file__).parent / '.anuncio'
ARQ_LINKS = Path(__file__).parent / '.links'
ERROS: dict[str, list] = {}


class ErroAuth(Exception):
    def __init__(self, status: int, msg: str):
        super().__init__(msg)
        self.status = status
        self.msg = msg


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _segredo(arq: Path) -> str:
    try:
        v = arq.read_text().strip()
        if len(v) >= 20:
            return v
    except OSError:
        pass
    v = secrets.token_hex(24)
    fd = os.open(arq, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(v)
    return v


def chave_anuncio() -> str:
    """Segredo usado para assinar o aviso do endereço novo (dado só aos aparelhos pareados)."""
    return _segredo(ARQ_ANUNCIO)


def _chave_links() -> bytes:
    """Segredo SÓ do servidor para os links temporários de arquivo (nenhum aparelho conhece)."""
    return _segredo(ARQ_LINKS).encode()


def _limitar(quem: str):
    agora = time.time()
    lista = [t for t in ERROS.get(quem, []) if agora - t < 600]
    ERROS[quem] = lista
    if len(ERROS) > 5000:
        ERROS.clear()
    if len(lista) >= 8:
        raise ErroAuth(429, 'Muitas tentativas erradas. Espere 10 minutos.')


def _errou(quem: str):
    ERROS.setdefault(quem, []).append(time.time())
    time.sleep(0.3)


def criar_sessao(nome: str, origem: str) -> dict:
    token = secrets.token_urlsafe(32)
    sid = uuid.uuid4().hex[:12]
    agora = time.time()
    nome = (nome or 'Aparelho').strip()[:60]
    db.executar('INSERT INTO sessoes (id, nome, token_hash, criado, visto, expira, revogado, origem) VALUES (?,?,?,?,?,?,0,?)',
                sid, nome, _h(token), agora, agora, agora + DURACAO, origem)
    db.evento(nome, 'sessao_criada', 'sessao:' + sid, {'origem': origem})
    return {'sessao': token, 'id': sid, 'nome': nome, 'anuncio': chave_anuncio()}


def validar(token: str) -> dict | None:
    if not token or len(token) > 200:
        return None
    s = db.um('SELECT * FROM sessoes WHERE token_hash=?', _h(token))
    agora = time.time()
    if not s or s['revogado'] or s['expira'] < agora:
        return None
    if agora - (s['visto'] or 0) > 300:
        db.executar('UPDATE sessoes SET visto=?, expira=? WHERE id=?', agora, agora + DURACAO, s['id'])
    return s


def login(senha: str, senha_dono: str, nome: str, quem: str) -> dict:
    _limitar(quem)
    if not senha_dono:
        raise ErroAuth(400, 'Este servidor está sem senha (só aceita o próprio aparelho). Ligue com: bash iniciar-termux.sh link')
    if not hmac.compare_digest(senha.encode(), senha_dono.encode()):
        _errou(quem)
        raise ErroAuth(401, 'Senha do servidor errada.')
    return criar_sessao(nome, 'senha')


def iniciar_pareamento(nome: str = '') -> dict:
    codigo = ''.join(secrets.choice(ALFABETO) for _ in range(8))
    agora = time.time()
    db.executar('DELETE FROM pareamentos WHERE expira < ?', agora - 86400)
    db.executar('INSERT INTO pareamentos (codigo_hash, nome, criado, expira, usado) VALUES (?,?,?,?,NULL)',
                _h(codigo), (nome or '')[:60], agora, agora + CODIGO_MIN * 60)
    return {'codigo': codigo[:4] + '-' + codigo[4:], 'expira': agora + CODIGO_MIN * 60, 'minutos': CODIGO_MIN}


def completar_pareamento(codigo: str, nonce: str, nome: str, quem: str) -> dict:
    """O aparelho novo manda o código e um desafio (nonce). A resposta prova que este é mesmo o servidor
    que gerou o código (um servidor falso não sabe o código), e entrega a sessão do aparelho."""
    _limitar(quem)
    limpo = ''.join(ch for ch in (codigo or '').upper() if ch in ALFABETO)
    p = db.um('SELECT * FROM pareamentos WHERE codigo_hash=?', _h(limpo)) if len(limpo) == 8 else None
    if not p or p['usado'] or p['expira'] < time.time():
        _errou(quem)
        raise ErroAuth(401, 'Código inválido ou vencido. Gere outro no aparelho que já está conectado.')
    with db.tx() as c:
        n = c.execute('UPDATE pareamentos SET usado=? WHERE codigo_hash=? AND usado IS NULL', (time.time(), p['codigo_hash'])).rowcount
    if n != 1:
        raise ErroAuth(401, 'Este código já foi usado.')
    s = criar_sessao(nome or p['nome'] or 'Aparelho novo', 'pareamento')
    s['prova'] = hmac.new(limpo.encode(), (nonce or '').encode(), hashlib.sha256).hexdigest()
    return s


def listar(atual: str = '') -> list:
    return [{'id': s['id'], 'nome': s['nome'], 'criado': s['criado'], 'visto': s['visto'], 'origem': s['origem'],
             'atual': s['id'] == atual} for s in db.todos('SELECT * FROM sessoes WHERE revogado=0 AND expira>? ORDER BY visto DESC', time.time())]


def revogar(sid: str, ator: str = '') -> dict:
    n = db.executar('UPDATE sessoes SET revogado=1 WHERE id=?', sid)
    if not n:
        raise ErroAuth(404, 'Aparelho não encontrado.')
    db.evento(ator, 'sessao_revogada', 'sessao:' + sid)
    return {'ok': True}


def assinar_url(caminho: str, segundos: int = 3600) -> str:
    """Link temporário para um arquivo (o player de vídeo do navegador não manda cabeçalhos)."""
    exp = int(time.time()) + segundos
    sig = hmac.new(_chave_links(), f'{caminho}|{exp}'.encode(), hashlib.sha256).hexdigest()[:40]
    return f'{caminho}?exp={exp}&sig={sig}'


def url_assinada_ok(caminho: str, exp: str, sig: str) -> bool:
    try:
        if int(exp) < time.time():
            return False
    except ValueError:
        return False
    certo = hmac.new(_chave_links(), f'{caminho}|{exp}'.encode(), hashlib.sha256).hexdigest()[:40]
    return hmac.compare_digest(certo, sig or '')
