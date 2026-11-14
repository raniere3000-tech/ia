"""Cofre do servidor: guarda chaves, senhas e logins das redes criptografados no disco.

A chave-mestra fica em um arquivo separado da pasta de dados (~/.estudioclip-chave), então uma cópia,
backup ou vazamento só da pasta de dados não revela nada. Quem tiver acesso total ao aparelho consegue
ler os dois: isso não tem como evitar, porque o servidor precisa usar as chaves sozinho.

Só biblioteca padrão: fluxo de cifra por HMAC-SHA256 em modo contador e conferência de integridade
(cifra e depois autentica), com chaves separadas para cada uso.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

MARCA = b'EC1:'
ARQ_CHAVE = Path(os.getenv('CHAVE_MESTRA_ARQ', str(Path.home() / '.estudioclip-chave')))
_chave: bytes | None = None


class ErroCofre(Exception):
    pass


def _privado(arq: Path):
    try:
        os.chmod(arq, 0o600)
    except OSError:
        pass


def chave_mestra() -> bytes:
    global _chave
    if _chave is None:
        try:
            bruto = base64.b64decode(ARQ_CHAVE.read_text().strip())
            if len(bruto) != 32:
                raise ValueError
        except (OSError, ValueError):
            if ARQ_CHAVE.exists():
                raise ErroCofre(f'O arquivo da chave-mestra ({ARQ_CHAVE}) está estragado.')
            bruto = secrets.token_bytes(32)
            ARQ_CHAVE.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(ARQ_CHAVE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(base64.b64encode(bruto).decode())
            _privado(ARQ_CHAVE)
        _chave = bruto
    return _chave


def _sub(uso: bytes) -> bytes:
    return hmac.new(chave_mestra(), b'estudioclip/' + uso, hashlib.sha256).digest()


def _fluxo(chave: bytes, nonce: bytes, n: int) -> bytes:
    out = bytearray()
    i = 0
    while len(out) < n:
        out += hmac.new(chave, nonce + i.to_bytes(8, 'big'), hashlib.sha256).digest()
        i += 1
    return bytes(out[:n])


def cifrar(dados: bytes) -> bytes:
    nonce = secrets.token_bytes(16)
    ct = bytes(a ^ b for a, b in zip(dados, _fluxo(_sub(b'cifra'), nonce, len(dados))))
    selo = hmac.new(_sub(b'selo'), MARCA + nonce + ct, hashlib.sha256).digest()
    return MARCA + base64.b64encode(nonce + ct + selo)


def decifrar(pacote: bytes) -> bytes:
    if not pacote.startswith(MARCA):
        raise ErroCofre('Arquivo não está no formato do cofre.')
    try:
        bruto = base64.b64decode(pacote[len(MARCA):], validate=True)
    except ValueError:
        raise ErroCofre('Arquivo do cofre estragado.')
    if len(bruto) < 48:
        raise ErroCofre('Arquivo do cofre estragado.')
    nonce, ct, selo = bruto[:16], bruto[16:-32], bruto[-32:]
    if not hmac.compare_digest(selo, hmac.new(_sub(b'selo'), MARCA + nonce + ct, hashlib.sha256).digest()):
        raise ErroCofre('O arquivo foi alterado ou a chave-mestra é outra.')
    return bytes(a ^ b for a, b in zip(ct, _fluxo(_sub(b'cifra'), nonce, len(ct))))


def ler_json(arq: Path, padrao):
    """Lê um JSON protegido. Arquivo antigo, em texto puro, é lido e já regravado criptografado."""
    try:
        bruto = arq.read_bytes()
    except OSError:
        return padrao
    if bruto.startswith(MARCA):
        try:
            return json.loads(decifrar(bruto.strip()).decode('utf-8'))
        except (ErroCofre, ValueError) as e:
            print(f'cofre: não consegui abrir {arq.name}: {e} (as chaves e logins guardados nele precisam ser refeitos)')
            return padrao
    try:
        dados = json.loads(bruto.decode('utf-8'))
    except ValueError:
        return padrao
    try:
        gravar_json(arq, dados)
    except (OSError, ErroCofre):
        pass
    return dados


def gravar_json(arq: Path, dados):
    tmp = arq.with_suffix('.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(cifrar(json.dumps(dados, ensure_ascii=False).encode('utf-8')))
    tmp.replace(arq)
    _privado(arq)
