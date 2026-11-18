"""Alertas do site (o sino): todo aviso que o servidor manda por e-mail ou WhatsApp também fica guardado aqui,
para aparecer no site. Guarda os últimos 300. Lido/não lido é um número só (até onde você já viu)."""
from __future__ import annotations

import threading
import time

import postagem as pg

ARQ = pg.DADOS / 'alertas.json'
LOCK = threading.RLock()
MAX = 300
NIVEL = {'falha': 'erro', 'live': 'info', 'postado': 'ok', 'agendado': 'ok', 'corte': 'ok', 'canal': 'info', 'semana': 'info'}
DESTINO = {'falha': 'agendar', 'postado': 'agendar', 'agendado': 'agendar', 'corte': 'agente', 'canal': 'agente', 'live': 'live', 'semana': 'agente'}


def _ler() -> dict:
    d = pg._ler(ARQ, {})
    if not isinstance(d.get('itens'), list):
        d['itens'] = []
    d.setdefault('n', 0)
    d.setdefault('lido', 0)
    return d


def registrar(tipo: str, assunto: str, corpo: str = '', nivel: str = '', destino: str = '') -> dict:
    with LOCK:
        d = _ler()
        d['n'] += 1
        a = {'n': d['n'], 't': time.time(), 'tipo': tipo, 'nivel': nivel or NIVEL.get(tipo, 'info'), 'assunto': str(assunto)[:200],
             'corpo': str(corpo)[:1500], 'destino': destino or DESTINO.get(tipo, '')}
        d['itens'] = (d['itens'] + [a])[-MAX:]
        pg._gravar(ARQ, d)
        return a


def listar(desde: int = 0, limite: int = 50) -> dict:
    d = _ler()
    itens = [x for x in d['itens'] if x['n'] > desde][-max(1, min(limite, MAX)):]
    return {'alertas': list(reversed(itens)), 'nao_lidas': sum(1 for x in d['itens'] if x['n'] > d['lido']), 'ultimo': d['n'], 'lido': d['lido']}


def marcar_lidas(ate: int | None = None) -> dict:
    with LOCK:
        d = _ler()
        d['lido'] = max(d['lido'], min(d['n'], int(ate if ate is not None else d['n'])))
        pg._gravar(ARQ, d)
    return listar(0, 1)
