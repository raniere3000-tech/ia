"""Agenda de PRODUÇÃO (quando o Agente 3 começa a fazer um vídeo). Não confundir com a agenda de
PUBLICAÇÃO (Agente 2).

Rotinas recorrentes: dias da semana + hora (horário de Brasília por padrão) + quantos vídeos.
Cada ocorrência vira trabalho(s) na fila com uma chave única, então reiniciar o servidor nunca
cria a mesma produção duas vezes.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import banco as db

try:
    from zoneinfo import ZoneInfo
    FUSO = ZoneInfo(os.getenv('FUSO', 'America/Sao_Paulo'))
except Exception:  # noqa: BLE001  (Android sem base de fusos: Brasília não tem horário de verão desde 2019)
    FUSO = timezone(timedelta(hours=-3))

CRIAR = None          # função (agenda, ocorrencia_ts, indice) -> cria o projeto e o trabalho; ligada pelo produtor


def proxima(dias: list[int], hora: str, depois: float | None = None) -> float | None:
    """Próximo horário (timestamp) que cai num dos dias (0=segunda) às HH:MM no fuso de Brasília."""
    try:
        h, m = (int(x) for x in hora.split(':')[:2])
    except ValueError:
        return None
    if not dias:
        return None
    base = datetime.fromtimestamp(depois or time.time(), FUSO)
    for d in range(0, 8):
        dia = (base + timedelta(days=d)).replace(hour=h, minute=m, second=0, microsecond=0)
        if dia.weekday() in dias and dia.timestamp() > (depois or time.time()) + 1:
            return dia.timestamp()
    return None


def _limpar(d: dict) -> dict:
    dias = sorted({int(x) for x in d.get('dias', []) if str(x).isdigit() and 0 <= int(x) <= 6})
    hora = str(d.get('hora') or '21:00')[:5]
    qtd = max(1, min(int(d.get('quantidade') or 1), 6))
    return {'nome': str(d.get('nome') or 'Rotina')[:80], 'dias': dias, 'hora': hora, 'quantidade': qtd,
            'ativo': 1 if d.get('ativo', True) else 0, 'briefing': d.get('briefing') if isinstance(d.get('briefing'), dict) else {}}


def listar() -> list:
    r = db.todos('SELECT * FROM agendas ORDER BY criado')
    for a in r:
        a['dias'] = json.loads(a['dias'] or '[]')
        a['briefing'] = json.loads(a['briefing'] or '{}')
    return r


def criar(d: dict) -> dict:
    a = _limpar(d)
    if not a['dias']:
        raise ValueError('Escolha pelo menos um dia da semana.')
    aid = uuid.uuid4().hex[:10]
    nx = proxima(a['dias'], a['hora'])
    if nx is None:
        raise ValueError('Hora inválida. Use HH:MM.')
    db.executar('INSERT INTO agendas (id, nome, dias, hora, quantidade, ativo, proxima, briefing, criado) VALUES (?,?,?,?,?,?,?,?,?)',
                aid, a['nome'], json.dumps(a['dias']), a['hora'], a['quantidade'], a['ativo'], nx, json.dumps(a['briefing'], ensure_ascii=False), time.time())
    return next(x for x in listar() if x['id'] == aid)


def mudar(aid: str, d: dict) -> dict:
    atual = next((x for x in listar() if x['id'] == aid), None)
    if not atual:
        raise ValueError('Rotina não encontrada.')
    a = _limpar({**atual, **d})
    nx = proxima(a['dias'], a['hora'])
    db.executar('UPDATE agendas SET nome=?, dias=?, hora=?, quantidade=?, ativo=?, proxima=?, briefing=? WHERE id=?',
                a['nome'], json.dumps(a['dias']), a['hora'], a['quantidade'], a['ativo'], nx, json.dumps(a['briefing'], ensure_ascii=False), aid)
    return next(x for x in listar() if x['id'] == aid)


def apagar(aid: str) -> dict:
    db.executar('DELETE FROM agendas WHERE id=?', aid)
    return {'ok': True}


def passo():
    agora = time.time()
    for a in listar():
        if not a['ativo'] or not a['proxima'] or a['proxima'] > agora:
            continue
        ocorr = a['proxima']
        for i in range(a['quantidade']):
            try:
                if CRIAR:
                    CRIAR(a, ocorr, i)
            except Exception as e:  # noqa: BLE001
                db.evento('agendador', 'rotina_erro', 'agenda:' + a['id'], {'erro': str(e)[:300]})
        db.executar('UPDATE agendas SET proxima=? WHERE id=? AND proxima=?', proxima(a['dias'], a['hora'], ocorr), a['id'], ocorr)


def iniciar():
    def laco():
        while True:
            try:
                passo()
            except Exception as e:  # noqa: BLE001
                print('agendador:', e)
            time.sleep(float(os.getenv('INTERVALO_AGENDA', '30')))
    threading.Thread(target=laco, daemon=True).start()
