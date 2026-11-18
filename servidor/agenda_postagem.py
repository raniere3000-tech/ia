"""Agente 2: programação diária de postagens por conta e rede (modo fixo, automático e misto).

- Horários locais da conta (fuso IANA, padrão America/Sao_Paulo); no banco tudo em UTC.
- Cada horário vira um "slot" com chave fixa conta:rede:data_local:hora#ocorrência (nunca duplica, nem depois de reiniciar).
- Um slot só recebe vídeo com certificado do diretor (Agente 4) válido para o arquivo atual e sem bloqueio de direitos.
  Sem vídeo aprovado o slot fica vazio: nada é inventado nem repetido para tapar buraco.
- Na hora de postar, a conferência do Agente 2 confere tudo de novo (postagem.conferencia + portão da esteira).
- Horário perdido (servidor desligado): "next_slot" não posta atrasado; "publish_when_online" posta até o atraso máximo;
  "manual_review" espera você.
Esta agenda é separada da agenda de criação do Agente 3 (agendador.py) e não mexe em posts manuais já criados.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone

import banco as db

MODOS = ('fixed', 'automatic', 'mixed')
POLITICAS_PERDIDO = ('next_slot', 'publish_when_online', 'manual_review')
SELECAO = ('oldest_approved', 'best_score')
REDES = ('youtube', 'instagram', 'facebook', 'tiktok', 'kwai')
NOMES_REDE = {'youtube': 'YouTube Shorts', 'instagram': 'Instagram Reels', 'facebook': 'Facebook Reels', 'tiktok': 'TikTok', 'kwai': 'Kwai (manual)'}
DIAS = ('segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado', 'domingo')
HORIZONTE = 7
TOLERANCIA_MIN = 15          # atraso tolerado antes de considerar o horário perdido
MAX_POR_DIA = 24
_LOCK = threading.Lock()


class ErroAgenda(Exception):
    def __init__(self, msg: str, status: int = 400):
        super().__init__(msg)
        self.status = status


# ---------------------------------------------------------------- fuso
def fuso(nome: str):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(nome)
    except Exception:  # noqa: BLE001 - aparelho sem base de fusos
        if nome == 'America/Sao_Paulo':
            return timezone(timedelta(hours=-3), 'America/Sao_Paulo')     # sem horário de verão desde 2019
        raise ErroAgenda(f'Fuso horário desconhecido neste aparelho: {nome}.')


def _hm(s) -> int:
    m = re.fullmatch(r'([01]\d|2[0-3]):([0-5]\d)', str(s or '').strip())
    if not m:
        raise ErroAgenda(f'Horário inválido: "{str(s)[:10]}". Use HH:MM, por exemplo 09:00.')
    return int(m.group(1)) * 60 + int(m.group(2))


def _txt_hm(minutos: int) -> str:
    return f'{minutos // 60:02d}:{minutos % 60:02d}'


def local_para_utc(dia: date, hm: str, tz) -> tuple[float, str]:
    """Horário local -> instante UTC. Horário que não existe (início do horário de verão) anda para frente; horário repetido usa a 1ª vez."""
    h, m = map(int, hm.split(':'))
    ingenuo = datetime(dia.year, dia.month, dia.day, h, m)
    dt = ingenuo.replace(tzinfo=tz, fold=0)
    volta = dt.astimezone(timezone.utc).astimezone(tz)
    if (volta.hour, volta.minute) != (h, m):         # buraco do horário de verão
        dt = (ingenuo + timedelta(hours=1)).replace(tzinfo=tz)
    off = dt.utcoffset() or timedelta(0)
    return dt.astimezone(timezone.utc).timestamp(), f'{"+" if off >= timedelta(0) else "-"}{abs(off) // timedelta(hours=1):02d}:{(abs(off) % timedelta(hours=1)) // timedelta(minutes=1):02d}'


# ---------------------------------------------------------------- configuração tipada
def validar(d: dict) -> dict:
    """Só campos conhecidos. weekly_rules: {"0": ["09:00", ...], ...} (0 = segunda). fixed_times + weekdays também valem (forma curta)."""
    if not isinstance(d, dict):
        raise ErroAgenda('Configuração inválida.')
    rede = str(d.get('platform', '')).lower()
    if rede not in REDES:
        raise ErroAgenda('Rede inválida.')
    conta = str(d.get('account_id') or 'principal')
    if not re.fullmatch(r'[\w.-]{1,40}', conta):
        raise ErroAgenda('Conta inválida.')
    nome_fuso = str(d.get('timezone') or 'America/Sao_Paulo')[:60]
    fuso(nome_fuso)
    modo = d.get('mode', 'fixed')
    if modo not in MODOS:
        raise ErroAgenda('Modo inválido (fixed, automatic ou mixed).')
    regras: dict = {}
    if isinstance(d.get('weekly_rules'), dict):
        for k, v in d['weekly_rules'].items():
            if str(k) not in [str(i) for i in range(7)] or not isinstance(v, list):
                raise ErroAgenda('Dia da semana inválido nos horários.')
            regras[str(k)] = v
    else:
        dias = d.get('weekdays', list(range(7)))
        if not isinstance(dias, list) or not all(isinstance(x, int) and 0 <= x <= 6 for x in dias):
            raise ErroAgenda('Dias da semana inválidos.')
        for x in dias:
            regras[str(x)] = list(d.get('fixed_times') or [])
    limpas = {}
    for k, v in regras.items():
        mins = [_hm(x) for x in v]
        if len(set(mins)) != len(mins):
            raise ErroAgenda(f'Horário repetido na {DIAS[int(k)]}.')
        limpas[k] = [_txt_hm(x) for x in sorted(mins)]
    flex = int(d.get('flex_slots_per_day') or 0)
    if not 0 <= flex <= MAX_POR_DIA:
        raise ErroAgenda('Quantidade de horários flexíveis inválida (0 a 24).')
    jan = d.get('automatic_window') or {'start': '09:00', 'end': '22:00'}
    j0, j1 = _hm(jan.get('start')), _hm(jan.get('end'))
    if j1 <= j0:
        raise ErroAgenda('A janela automática precisa terminar depois de começar.')
    gap = int(d.get('minimum_gap_minutes') or 60)
    if not 5 <= gap <= 720:
        raise ErroAgenda('Intervalo mínimo entre posts: de 5 a 720 minutos.')
    perdido = d.get('missed_slot_policy', 'next_slot')
    if perdido not in POLITICAS_PERDIDO:
        raise ErroAgenda('Política de horário perdido inválida.')
    atraso = int(d.get('max_delay_minutes') or 60)
    if not 15 <= atraso <= 360:
        raise ErroAgenda('Atraso máximo: de 15 a 360 minutos.')
    sel = d.get('selection_policy', 'oldest_approved')
    if sel not in SELECAO:
        raise ErroAgenda('Seleção de vídeo inválida.')
    if modo == 'fixed':
        flex = 0
    if modo == 'automatic':
        limpas = {k: [] for k in limpas} or {str(i): [] for i in range(7)}
    excecoes = {}
    for k, v in (d.get('exceptions') or {}).items():
        try:
            date.fromisoformat(str(k))
        except ValueError:
            raise ErroAgenda(f'Data de exceção inválida: {str(k)[:12]}.')
        if v == 'pausado' or v == []:
            excecoes[str(k)] = 'pausado'
        elif isinstance(v, list):
            mins = [_hm(x) for x in v]
            if len(set(mins)) != len(mins):
                raise ErroAgenda(f'Horário repetido em {k}.')
            excecoes[str(k)] = [_txt_hm(x) for x in sorted(mins)]
        else:
            raise ErroAgenda('Exceção inválida (use "pausado" ou uma lista de horários).')
    cfg = {'account_id': conta, 'platform': rede, 'timezone': nome_fuso, 'mode': modo, 'enabled': bool(d.get('enabled', True)),
           'weekly_rules': limpas, 'flex_slots_per_day': flex, 'automatic_window': {'start': _txt_hm(j0), 'end': _txt_hm(j1)},
           'minimum_gap_minutes': gap, 'missed_slot_policy': perdido, 'max_delay_minutes': atraso, 'selection_policy': sel, 'exceptions': excecoes}
    for k in limpas:                       # confere já: modo automático/misto que não cabe na janela vira erro no formulário
        horarios_do_dia(cfg, int(k), None)
    return cfg


def _espalhar(n: int, ini: int, fim: int, gap: int, fixos: list) -> list:
    """n horários flexíveis dentro da janela, longe pelo menos `gap` minutos de tudo (fixos incluídos). Erro se não couber."""
    if n <= 0:
        return []
    ocupados = sorted(fixos)
    livres = []
    for m in range(ini, fim + 1, 5):
        if all(abs(m - o) >= gap for o in ocupados):
            livres.append(m)
    escolhidos: list = []
    # distribui pelo meio de cada pedaço da janela; guloso, mas determinístico
    alvo = [ini + (fim - ini) * (i + 0.5) / n for i in range(n)]
    for a in alvo:
        cand = [m for m in livres if all(abs(m - x) >= gap for x in escolhidos)]
        if not cand:
            break
        escolhidos.append(min(cand, key=lambda m: (abs(m - a), m)))
    if len(escolhidos) < n:
        raise ErroAgenda(f'Não cabem {n} post(s) entre {_txt_hm(ini)} e {_txt_hm(fim)} com {gap} min de intervalo'
                         + (' além dos horários fixos' if fixos else '') + '. Diminua a quantidade, o intervalo ou aumente a janela.')
    return sorted(escolhidos)


def horarios_do_dia(cfg: dict, dia_semana: int, data_local: str | None) -> list:
    """Lista [(HH:MM, tipo)] daquele dia (tipo fixo/flexivel). Exceção da data manda."""
    exc = cfg['exceptions'].get(data_local) if data_local else None
    if exc == 'pausado':
        return []
    fixos = exc if isinstance(exc, list) else cfg['weekly_rules'].get(str(dia_semana))
    if fixos is None:
        return []
    mins = [_hm(x) for x in fixos]
    for a, b in zip(mins, mins[1:]):
        if b - a < cfg['minimum_gap_minutes']:
            raise ErroAgenda(f'{_txt_hm(a)} e {_txt_hm(b)} ficam a menos de {cfg["minimum_gap_minutes"]} min um do outro.')
    flex = []
    if cfg['mode'] in ('automatic', 'mixed') and not isinstance(exc, list):
        j = cfg['automatic_window']
        flex = _espalhar(cfg['flex_slots_per_day'], _hm(j['start']), _hm(j['end']), cfg['minimum_gap_minutes'], mins)
    out = [(_txt_hm(m), 'fixo') for m in mins] + [(_txt_hm(m), 'flexivel') for m in flex]
    if len(out) > MAX_POR_DIA:
        raise ErroAgenda(f'No máximo {MAX_POR_DIA} posts por dia.')
    return sorted(out)


def meta_do_dia(cfg: dict, dia_semana: int, data_local: str | None = None) -> int:
    return len(horarios_do_dia(cfg, dia_semana, data_local))


# ---------------------------------------------------------------- persistência
def _agenda(aid: str) -> dict:
    r = db.um('SELECT * FROM posting_schedules WHERE id=? AND apagado=0', aid)
    if not r:
        raise ErroAgenda('Programação não encontrada.', 404)
    cfg = json.loads(r['regras'])
    cfg.update(id=r['id'], version=r['versao'], enabled=bool(r['ligado']), atualizado=r['atualizado'])
    return cfg


def listar() -> list:
    out = []
    for r in db.todos('SELECT id FROM posting_schedules WHERE apagado=0 ORDER BY rede, conta'):
        c = _agenda(r['id'])
        c['meta_semana'] = sum(meta_do_dia(c, i) for i in range(7))
        c['nome_rede'] = NOMES_REDE[c['platform']]
        out.append(c)
    return out


def criar(d: dict, quem: str = 'site') -> dict:
    cfg = validar(d)
    if db.um('SELECT id FROM posting_schedules WHERE conta=? AND rede=? AND apagado=0', cfg['account_id'], cfg['platform']):
        raise ErroAgenda('Já existe programação para esta conta nesta rede. Edite a que existe.', 409)
    aid = uuid.uuid4().hex[:12]
    agora = time.time()
    db.executar('INSERT INTO posting_schedules (id, conta, rede, fuso, modo, ligado, regras, versao, criado, atualizado, apagado) VALUES (?,?,?,?,?,?,?,?,?,?,0)',
                aid, cfg['account_id'], cfg['platform'], cfg['timezone'], cfg['mode'], 1 if cfg['enabled'] else 0, json.dumps(cfg, ensure_ascii=False), 1, agora, agora)
    db.evento(quem, 'agenda_criada', 'agenda:' + aid, {'rede': cfg['platform'], 'modo': cfg['mode']})
    reconciliar(aid)
    return _agenda(aid)


def atualizar(aid: str, d: dict, versao: int | None, quem: str = 'site') -> dict:
    atual = _agenda(aid)
    if versao is None or int(versao) != atual['version']:
        raise ErroAgenda('Esta programação foi mudada em outro aparelho. Abra de novo para ver a versão atual.', 409)
    base = {k: v for k, v in atual.items() if k not in ('id', 'version', 'atualizado')}
    base.update({k: v for k, v in d.items() if k not in ('platform', 'account_id', 'id', 'version')})
    if 'weekly_rules' not in d and ('fixed_times' in d or 'weekdays' in d):     # forma curta: troca a regra de todos os dias
        antigas = base.pop('weekly_rules', {}) or {}
        base.setdefault('weekdays', sorted(int(k) for k in antigas))
        base.setdefault('fixed_times', next((v for v in antigas.values() if v), []))
    cfg = validar(base)
    db.executar('UPDATE posting_schedules SET fuso=?, modo=?, ligado=?, regras=?, versao=versao+1, atualizado=? WHERE id=? AND versao=?', cfg['timezone'],
                cfg['mode'], 1 if cfg['enabled'] else 0, json.dumps(cfg, ensure_ascii=False), time.time(), aid, atual['version'])
    db.evento(quem, 'agenda_mudou', 'agenda:' + aid, {'versao': atual['version'] + 1})
    reconciliar(aid)
    return _agenda(aid)


def desativar(aid: str, quem: str = 'site') -> dict:
    _agenda(aid)
    db.executar('UPDATE posting_schedules SET ligado=0, apagado=1, atualizado=? WHERE id=?', time.time(), aid)
    db.executar("UPDATE posting_slots SET estado='cancelado', motivo='Programação apagada', atualizado=? WHERE agenda=? AND estado='vazio'", time.time(), aid)
    db.evento(quem, 'agenda_apagada', 'agenda:' + aid)
    return {'ok': True}


# ---------------------------------------------------------------- prévia e slots
def _dias(cfg: dict, inicio: date | None, n: int):
    tz = fuso(cfg['timezone'])
    hoje = inicio or datetime.now(tz).date()
    for i in range(n):
        yield hoje + timedelta(days=i), tz


def previa(d: dict, dias: int = HORIZONTE, inicio: date | None = None) -> dict:
    """Próximos dias com datas e horários reais, sem criar nada. Avisa falta de vídeo aprovado e conta desconectada."""
    cfg = validar(d)
    agora = time.time()
    lista, total = [], 0
    for dia, tz in _dias(cfg, inicio, dias):
        ds = dia.isoformat()
        hs = horarios_do_dia(cfg, dia.weekday(), ds)
        itens = []
        for hm, tipo in hs:
            utc, off = local_para_utc(dia, hm, tz)
            if utc < agora:
                continue
            itens.append({'hora': hm, 'tipo': tipo, 'utc': utc, 'offset': off})
        total += len(itens)
        exc = cfg['exceptions'].get(ds)
        lista.append({'data': ds, 'dia': DIAS[dia.weekday()], 'horarios': itens, 'excecao': exc == 'pausado' and 'pausado' or ('especial' if exc else '')})
    avisos = []
    aprov = len(elegiveis(cfg['platform']))
    if aprov < total:
        avisos.append(f'Há {aprov} vídeo(s) aprovado(s) pelo diretor para {total} horário(s): os que sobrarem ficam vazios (nada é repetido).')
    try:
        import postagem as pg
        prov = pg.PROV.get(cfg['platform'])
        if prov and not pg.status_contas()[prov]['conectado']:
            avisos.append(f'A conta do {NOMES_REDE[cfg["platform"]]} não está conectada: nada vai sair até conectar.')
    except Exception:  # noqa: BLE001
        pass
    if cfg['platform'] == 'kwai':
        avisos.append('Kwai não tem postagem automática oficial: os horários ficam como lembrete para postar à mão.')
    try:
        import pipeline as pl
        if not pl.ligado():
            avisos.append('A esteira dos 5 agentes está desligada: sem o certificado do diretor nenhum horário recebe vídeo.')
    except Exception:  # noqa: BLE001
        pass
    return {'config': cfg, 'dias': lista, 'total': total, 'por_rede': {cfg['platform']: total}, 'avisos': avisos}


def _sid(cfg: dict, ds: str, hm: str, n: int) -> str:
    chave = f'{cfg["account_id"]}:{cfg["platform"]}:{ds}:{hm}#{n}'
    return hashlib.sha1(chave.encode()).hexdigest()[:16]


def reconciliar(aid: str) -> dict:
    """Cria os slots dos próximos dias e cancela os vazios que saíram da programação. Não mexe em slot com vídeo nem em publicado."""
    cfg = _agenda(aid)
    agora = time.time()
    validos, novos = set(), 0
    if cfg['enabled']:
        for dia, tz in _dias(cfg, None, HORIZONTE):
            ds = dia.isoformat()
            for hm, tipo in horarios_do_dia(cfg, dia.weekday(), ds):
                utc, off = local_para_utc(dia, hm, tz)
                if utc < agora - 60:
                    continue
                sid = _sid(cfg, ds, hm, 0)
                validos.add(sid)
                n = db.executar('INSERT OR IGNORE INTO posting_slots (id, agenda, conta, rede, data_local, hora_local, ocorrencia, quando_utc, tipo, estado, motivo, criado, atualizado) '
                                'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', sid, aid, cfg['account_id'], cfg['platform'], ds, hm, 0, utc, tipo,
                                'manual' if cfg['platform'] == 'kwai' else 'vazio', 'fuso ' + off, agora, agora)
                novos += n or 0
                db.executar("UPDATE posting_slots SET estado=CASE WHEN rede='kwai' THEN 'manual' ELSE 'vazio' END, motivo='voltou para a programação', atualizado=? "
                            "WHERE id=? AND estado='cancelado' AND motivo='saiu da programação'", agora, sid)
    canc = 0
    for s in db.todos("SELECT id FROM posting_slots WHERE agenda=? AND estado IN ('vazio','manual') AND quando_utc>? AND tipo<>'movido'", aid, agora):
        if s['id'] not in validos:
            db.executar("UPDATE posting_slots SET estado='cancelado', motivo='saiu da programação', atualizado=? WHERE id=?", agora, s['id'])
            canc += 1
    return {'novos': novos, 'cancelados': canc}


def mover_slot(sid: str, data_local: str, hora_local: str, quem: str = 'site') -> dict:
    """Muda UM horário de lugar (só este dia). Se já tem vídeo, o post vai junto para o novo horário. O resto da programação não muda."""
    s = db.um('SELECT * FROM posting_slots WHERE id=?', sid)
    if not s:
        raise ErroAgenda('Horário não encontrado.', 404)
    if s['estado'] not in ('vazio', 'agendado', 'reservado', 'aguardando_aprovacao'):
        raise ErroAgenda('Este horário não pode mais ser mudado (já foi postado, perdido ou cancelado).', 409)
    cfg = _agenda(s['agenda'])
    try:
        dia = date.fromisoformat(str(data_local))
    except ValueError:
        raise ErroAgenda('Data inválida (use AAAA-MM-DD).') from None
    hm = _txt_hm(_hm(hora_local))
    utc, off = local_para_utc(dia, hm, fuso(cfg['timezone']))
    if utc < time.time() + 120:
        raise ErroAgenda('Escolha um horário no futuro (pelo menos 2 minutos à frente).')
    gap = cfg['minimum_gap_minutes'] * 60
    perto = db.um("SELECT hora_local, data_local FROM posting_slots WHERE rede=? AND conta=? AND id<>? AND estado NOT IN ('cancelado','perdido') "
                  "AND ABS(quando_utc-?)<?", s['rede'], s['conta'], sid, utc, gap)
    if perto:
        raise ErroAgenda(f'Fica a menos de {cfg["minimum_gap_minutes"]} min do horário de {perto["data_local"]} {perto["hora_local"]} nesta rede.')
    if s.get('post'):
        import postagem as pg
        lim = utc + (cfg['max_delay_minutes'] if cfg['missed_slot_policy'] == 'publish_when_online' else TOLERANCIA_MIN) * 60
        pg._mudar(s['post'], lambda q: q.update(quando=utc, agenda=dict(q.get('agenda') or {}, ate=lim)))
    db.executar("UPDATE posting_slots SET data_local=?, hora_local=?, quando_utc=?, tipo='movido', motivo=?, atualizado=? WHERE id=?",
                dia.isoformat(), hm, utc, f'movido por {quem} (fuso {off})'[:200], time.time(), sid)
    db.evento(quem, 'slot_movido', 'slot:' + sid, {'de': f'{s["data_local"]} {s["hora_local"]}', 'para': f'{dia.isoformat()} {hm}'})
    return db.um('SELECT * FROM posting_slots WHERE id=?', sid)


def rotulo_ref(ref: str | None, cache: dict | None = None) -> str:
    """Nome do vídeo que ocupa o horário (para a tela). Vazio se não achar."""
    if not ref:
        return ''
    try:
        if ref.startswith('p:'):
            r = db.um('SELECT titulo FROM projetos WHERE id=?', ref[2:])
            return (r or {}).get('titulo') or ''
        if cache is None:
            cache = {}
        if 'cortes' not in cache:
            import agente as ag
            cache['cortes'] = {c['id']: c for c in ag.estado()['cortes']}
        c = cache['cortes'].get(ref) or {}
        return str(c.get('titulo') or c.get('nome') or '')[:120]
    except Exception:  # noqa: BLE001
        return ''


def slots(de: float | None = None, ate: float | None = None, rede: str = '', conta: str = '') -> list:
    de = de if de is not None else time.time() - 86400
    ate = ate if ate is not None else time.time() + HORIZONTE * 86400
    sql = 'SELECT * FROM posting_slots WHERE quando_utc BETWEEN ? AND ?'
    args: list = [de, ate]
    if rede:
        sql += ' AND rede=?'
        args.append(rede)
    if conta:
        sql += ' AND conta=?'
        args.append(conta)
    return db.todos(sql + " AND estado<>'cancelado' ORDER BY quando_utc", *args)


# ---------------------------------------------------------------- vídeos elegíveis e reserva
def _sha(c: dict) -> str:
    import pipeline as pl
    import postagem as pg
    try:
        return pl.sha_arquivo(pg.video_path(c['video']))
    except Exception:  # noqa: BLE001
        return ''


def _esteira() -> bool:
    try:
        import pipeline as pl
        return pl.ligado()
    except Exception:  # noqa: BLE001
        return False


def rede_programada(rede: str) -> bool:
    """A programação desta rede está ligada E a esteira também (sem esteira a programação não recebe vídeo; aí vale o caminho antigo)."""
    return _esteira() and bool(db.um('SELECT id FROM posting_schedules WHERE apagado=0 AND ligado=1 AND rede=?', rede))


def tem_programacao() -> bool:
    """Há programação diária ligada em alguma rede."""
    return _esteira() and bool(db.um('SELECT id FROM posting_schedules WHERE apagado=0 AND ligado=1'))


def elegiveis(rede: str) -> list:
    """Cortes prontos com certificado do diretor válido PARA O ARQUIVO ATUAL, sem bloqueio de direitos, ainda não reservados nesta rede."""
    try:
        import agente as ag
        import pipeline as pl
    except Exception:  # noqa: BLE001
        return []
    if not pl.ligado():
        return []
    usados = {r['ref'] for r in db.todos("SELECT ref FROM posting_slots WHERE rede=? AND ref IS NOT NULL AND estado NOT IN ('cancelado','perdido','vazio')", rede)}
    out = []
    for c in ag.estado()['cortes']:
        if c['id'] in usados or c['status'] not in ('pronto', 'agendado') or (c['status'] == 'agendado' and not c.get('via_agenda')):
            continue
        if c.get('redes') and rede not in c['redes']:
            continue
        if not ag.liberado_para_postar(c):
            continue            # mesma regra da postagem antiga: espera o seu ok (se a exigência estiver ligada)
        sha = _sha(c)
        cert = pl.certificado(sha) if sha else None
        if not cert:
            continue
        conf = ag.conferir(c)
        if conf['bloqueios']:
            continue
        out.append({'tipo': 'corte', 'corte': c, 'ref': c['id'], 'sha': sha, 'nota': cert['nota'], 'criado': c.get('criado', 0)})
    try:        # vídeos das linhas de conteúdo do Agente 3 (aprovados por você ou pela publicação automática da linha)
        import linhas_conteudo as lc
        out += lc.ativos_para(rede)
    except Exception as e:  # noqa: BLE001
        print('agenda: linhas de conteúdo', e)
    return out


def ordenar(cand: list, politica: str) -> list:
    """Prioridade da linha (1 a 5; cortes = 3) vem primeiro; depois a regra da programação (mais antigo ou maior nota)."""
    if politica == 'oldest_approved':
        return sorted(cand, key=lambda x: (-x.get('prioridade', 3), x['criado']))
    return sorted(cand, key=lambda x: (-x.get('prioridade', 3), -x['nota'], x['criado']))


def _reservar(s: dict, cfg: dict) -> str:
    import agente as ag
    import postagem as pg
    cand = elegiveis(s['rede'])
    if not cand:
        db.executar("UPDATE posting_slots SET motivo='Sem vídeo aprovado pelo diretor', atualizado=? WHERE id=? AND estado='vazio'", time.time(), s['id'])
        return 'vazio'
    esc = ordenar(cand, cfg['selection_policy'])[0]
    # trava o slot ANTES de criar o post: só um trabalhador ganha
    n = db.executar("UPDATE posting_slots SET estado='reservado', ref=?, sha256=?, atualizado=? WHERE id=? AND estado='vazio'", esc['ref'], esc['sha'], time.time(), s['id'])
    if not n:
        return 'ocupado'
    if esc.get('tipo') == 'agente3':
        return _reservar_agente3(s, cfg, esc)
    c = esc['corte']
    try:
        legenda = c.get('legenda_post') or (c['titulo'] + '\n\n' + ' '.join(c.get('hashtags') or [])).strip()
        po = ag.config()['postagem']
        p = pg.criar_post({'video': c['video'], 'redes': [s['rede']], 'quando': s['quando_utc'], 'titulo': c['titulo'], 'legenda': legenda,
                           'youtube_privacidade': po.get('youtube_privacidade', 'public'), 'tiktok_modo': po.get('tiktok_modo', 'rascunho'),
                           'modelo': c.get('modelo', ''), 'origem': 'agenda', 'direitos': c.get('direitos') or ag._direitos_do_canal(c)})
        limite = s['quando_utc'] + (cfg['max_delay_minutes'] if cfg['missed_slot_policy'] == 'publish_when_online' else TOLERANCIA_MIN) * 60
        pg._mudar(p['id'], lambda q: q.update(agenda={'slot': s['id'], 'politica': cfg['missed_slot_policy'], 'ate': limite}))
    except Exception as e:  # noqa: BLE001
        db.executar("UPDATE posting_slots SET estado='vazio', ref=NULL, sha256=NULL, motivo=?, atualizado=? WHERE id=?", str(e)[:200], time.time(), s['id'])
        return 'erro'
    db.executar("UPDATE posting_slots SET estado='agendado', post=?, motivo='', atualizado=? WHERE id=?", p['id'], time.time(), s['id'])

    def f(e):
        for x in e['cortes']:
            if x['id'] == c['id']:
                x.update(status='agendado', via_agenda=True, post=x.get('post') or p['id'], quando=min(x.get('quando') or s['quando_utc'], s['quando_utc']))
    ag._mudar(f)
    db.evento('agente2', 'slot_reservado', 'slot:' + s['id'], {'corte': c['id'], 'rede': s['rede'], 'sha': esc['sha'][:16]})
    return 'agendado'


def _reservar_agente3(s: dict, cfg: dict, esc: dict) -> str:
    """Vídeo de uma linha do Agente 3: mesmo arquivo aprovado, um post por rede. A chave sha:rede impede postar duas vezes na mesma rede."""
    import shutil
    import uuid
    import aprovacoes as apv
    import descricao as ds
    import postagem as pg
    p, sha = esc['projeto'], esc['sha']
    try:
        if db.um('SELECT id FROM publicacoes WHERE chave=?', f'{sha}:{s["rede"]}'):
            raise ValueError('Este vídeo já foi entregue a esta rede.')
        r = apv._render_atual(p)
        if not r or r['sha'] != sha:
            raise ValueError('O arquivo aprovado mudou ou sumiu.')
        apr = db.um("SELECT id FROM aprovacoes WHERE projeto=? AND render_sha=? AND decisao='aprovado' ORDER BY criado DESC", p['id'], sha)
        if not apr:
            raise ValueError('Vídeo sem aprovação.')
        vid = sha[:12]
        destino = pg.VIDEOS / f'{vid}.mp4'
        if not destino.exists():
            tmp = pg.VIDEOS / f'{vid}.copia.tmp'
            shutil.copy(r['arquivo'], tmp)
            tmp.replace(destino)
        dest = dict(p['dados']['briefing'].get('destinos') or {})
        dsc = apv.descricao(p, dest)
        titulo = ds.titulo_limpo(((p['dados'].get('roteiro') or {}).get('titulo')) or p['titulo'])[:100]
        post = pg.criar_post({'video': vid, 'redes': [s['rede']], 'quando': s['quando_utc'], 'titulo': titulo, 'legenda': dsc['legenda'],
                              'origem': 'agente3', 'direitos': {'origem': 'meu', 'nota': 'Vídeo original do Agente 3 (linha de conteúdo)'},
                              'projeto': p['id'], 'render_sha': sha, 'creditos': dsc['exigidos']})
        limite = s['quando_utc'] + (cfg['max_delay_minutes'] if cfg['missed_slot_policy'] == 'publish_when_online' else TOLERANCIA_MIN) * 60
        pg._mudar(post['id'], lambda q: q.update(agenda={'slot': s['id'], 'politica': cfg['missed_slot_policy'], 'ate': limite}))
        db.executar('INSERT OR IGNORE INTO publicacoes (id, aprovacao, render_sha, post, rede, chave, criado) VALUES (?,?,?,?,?,?,?)',
                    uuid.uuid4().hex[:16], apr['id'], sha, post['id'], s['rede'], f'{sha}:{s["rede"]}', time.time())
    except Exception as e:  # noqa: BLE001
        db.executar("UPDATE posting_slots SET estado='vazio', ref=NULL, sha256=NULL, motivo=?, atualizado=? WHERE id=?", str(e)[:200], time.time(), s['id'])
        return 'erro'
    db.executar("UPDATE posting_slots SET estado='agendado', post=?, motivo='', atualizado=? WHERE id=?", post['id'], time.time(), s['id'])
    db.evento('agente2', 'slot_reservado', 'slot:' + s['id'], {'projeto': p['id'], 'rede': s['rede'], 'sha': sha[:16], 'linha': esc.get('linha', '')})
    return 'agendado'


def _liberar_ref(s: dict, post_id: str):
    """O horário não usou o vídeo: ele volta para o estoque (corte vira 'pronto'; vídeo do Agente 3 pode ir de novo para esta rede)."""
    if str(s.get('ref') or '').startswith('p:'):
        db.executar('DELETE FROM publicacoes WHERE post=? AND rede=?', post_id, s['rede'])
        return
    import agente as ag
    ag._mudar(lambda e: [x.update(status='pronto', post='', quando=None) for x in e['cortes'] if x['id'] == s['ref'] and x.get('post') == post_id])


def _acompanhar(s: dict, cfg: dict | None):
    """Atualiza o estado do slot pelo post e trata horário perdido."""
    import postagem as pg
    agora = time.time()
    p = next((x for x in pg.posts() if x['id'] == s.get('post')), None)
    if not p:
        if s['estado'] in ('agendado', 'publicando'):
            db.executar("UPDATE posting_slots SET estado='erro', motivo='O post foi cancelado fora da agenda', atualizado=? WHERE id=?", agora, s['id'])
            if str(s.get('ref') or '').startswith('p:'):
                _liberar_ref(s, s['post'])
        return
    st = p['redes'].get(s['rede'], {}).get('status', '')
    mapa = {'postado': 'publicado', 'postando': 'publicando', 'erro': 'erro', 'liberacao': 'aguardando_aprovacao', 'manual': 'manual'}
    if st in mapa and mapa[st] != s['estado']:
        db.executar('UPDATE posting_slots SET estado=?, motivo=?, atualizado=? WHERE id=?', mapa[st], (p['redes'][s['rede']].get('erro') or '')[:200], agora, s['id'])
        return
    lim = (p.get('agenda') or {}).get('ate') or s['quando_utc'] + TOLERANCIA_MIN * 60
    if st == 'agendado' and agora > lim and not p['redes'][s['rede']].get('tentativas'):
        pol = (cfg or {}).get('missed_slot_policy', 'next_slot')
        try:
            pg.cancelar_post(p['id'], manter_video=True)
        except pg.ErroRede:
            return
        novo = 'aguardando_aprovacao' if pol == 'manual_review' else 'perdido'
        db.executar('UPDATE posting_slots SET estado=?, motivo=?, atualizado=? WHERE id=?', novo,
                    'Servidor estava desligado na hora: não postei atrasado.' if novo == 'perdido' else 'Horário passou: espera você decidir.', agora, s['id'])
        _liberar_ref(s, p['id'])


def ciclo() -> dict:
    """Roda a cada poucos minutos: cria slots, preenche os vazios com vídeo aprovado e acompanha os agendados."""
    if not _LOCK.acquire(blocking=False):
        return {'ocupado': True}
    try:
        res = {'agendados': 0}
        cfgs = {}
        for a in db.todos('SELECT id FROM posting_schedules WHERE apagado=0'):
            try:
                cfgs[a['id']] = _agenda(a['id'])
                reconciliar(a['id'])
            except ErroAgenda as e:
                db.evento('agente2', 'agenda_erro', 'agenda:' + a['id'], {'erro': str(e)[:200]})
        agora = time.time()
        for s in db.todos("SELECT * FROM posting_slots WHERE estado IN ('agendado','publicando','reservado','aguardando_aprovacao') AND post IS NOT NULL"):
            _acompanhar(s, cfgs.get(s['agenda']))
        db.executar("UPDATE posting_slots SET estado='perdido', motivo='Sem vídeo aprovado na hora', atualizado=? WHERE estado='vazio' AND quando_utc<?",
                    agora, agora - TOLERANCIA_MIN * 60)
        for s in db.todos("SELECT * FROM posting_slots WHERE estado='vazio' AND quando_utc>? ORDER BY quando_utc", agora + 60):
            cfg = cfgs.get(s['agenda'])
            if cfg and cfg['enabled'] and _reservar(s, cfg) == 'agendado':
                res['agendados'] += 1
        return res
    finally:
        _LOCK.release()


def metricas(data_local: str = '', rede: str = '', conta: str = '') -> dict:
    sql = 'SELECT estado, rede, COUNT(*) n FROM posting_slots WHERE estado<>\'cancelado\''
    args: list = []
    if data_local:
        sql += ' AND data_local=?'
        args.append(data_local)
    if rede:
        sql += ' AND rede=?'
        args.append(rede)
    if conta:
        sql += ' AND conta=?'
        args.append(conta)
    por: dict = {}
    for r in db.todos(sql + ' GROUP BY estado, rede', *args):
        por.setdefault(r['rede'], {})[r['estado']] = r['n']
    tot = {r: {'meta': sum(v.values()), 'publicados': v.get('publicado', 0), 'agendados': v.get('agendado', 0) + v.get('reservado', 0),
               'livres': v.get('vazio', 0), 'falhas': v.get('erro', 0), 'perdidos': v.get('perdido', 0), 'estados': v} for r, v in por.items()}
    return {'data': data_local, 'por_rede': tot, 'disponiveis': {r: len(elegiveis(r)) for r in (tot or {})}}


_relogio = {'on': False}
_acordar = threading.Event()


def acordar():
    """Chegou vídeo aprovado: roda o ciclo agora em vez de esperar o relógio (não fura nenhuma regra, só adianta a conferência)."""
    _acordar.set()


def iniciar():
    if _relogio['on']:
        return
    _relogio['on'] = True

    def laco():
        while True:
            try:
                ciclo()
            except Exception as e:  # noqa: BLE001
                print('agenda do Agente 2:', e)
            _acordar.wait(float(os.getenv('INTERVALO_AGENDA2', '180')))
            _acordar.clear()
    threading.Thread(target=laco, daemon=True, name='agenda-agente2').start()
