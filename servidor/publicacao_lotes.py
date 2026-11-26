"""Prévia e agendamento em lote. Muda somente os destinos escolhidos de posts existentes."""
from __future__ import annotations
import hashlib
import json
import math
import re
import time
import banco as db
import postagem as pg
import agenda_postagem as agenda


def _parametros(d):
    ids, redes = d.get('posts'), d.get('redes')
    if not isinstance(ids, list) or not ids or len(ids) > 200 or any(not isinstance(x, str) for x in ids):
        raise pg.ErroRede('Selecione de 1 a 200 vídeos.')
    if not isinstance(redes, list) or not redes or any(r not in pg.REDES for r in redes):
        raise pg.ErroRede('Escolha pelo menos uma rede válida.')
    try:
        inicio = float(d.get('inicio'))
        intervalo = float(d.get('intervalo_min', 30)) * 60
        intervalo_api = float(d.get('intervalo_api_s', 30))
    except (TypeError, ValueError):
        raise pg.ErroRede('Confira o horário e os intervalos.') from None
    if not all(math.isfinite(n) for n in (inicio, intervalo, intervalo_api)) or inicio < time.time() - 60:
        raise pg.ErroRede('Escolha um horário inicial no futuro.')
    if not 60 <= intervalo <= 30 * 86400 or not 1 <= intervalo_api <= 3600:
        raise pg.ErroRede('Intervalo de publicação: 1 minuto a 30 dias. Pausa entre envios: 1 a 3600 segundos.')
    modo = d.get('modo', 'intervalo')
    if modo not in ('intervalo', 'programacao'):
        raise pg.ErroRede('Modo de agendamento inválido.')
    return dict(posts=list(dict.fromkeys(ids)), redes=list(dict.fromkeys(redes)), inicio=inicio,
                intervalo_s=intervalo, intervalo_api_s=intervalo_api, modo=modo,
                reagendar=d.get('reagendar') is True)


def _identidade(p):
    return p.get('hash') or p['video']


def horario(p, r):
    return float(r.get('quando', p['quando']))


def _planejar(cfg, ps):
    por_id = {p['id']: p for p in ps}
    proximos = {r: cfg['inicio'] for r in cfg['redes']}
    ocupados = {r: [horario(p, s) for p in ps for rd, s in p['redes'].items() if rd == r
                   and s['status'] in ('agendado', 'postando', 'manual')] for r in cfg['redes']}
    slots = db.todos("SELECT s.* FROM posting_slots s JOIN posting_schedules a ON a.id=s.agenda "
                     "WHERE a.apagado=0 AND a.ligado=1 AND s.quando_utc>=? AND s.estado NOT IN ('cancelado','perdido') ORDER BY s.quando_utc", cfg['inicio'])
    livres = {r: [s for s in slots if s['rede'] == r and s['estado'] in ('vazio', 'manual') and not s.get('post')]
              for r in cfg['redes']}
    saida = {'agendados': [], 'ignorados': [], 'ajustes': []}
    vistos = set()
    for pid in cfg['posts']:
        p = por_id.get(pid)
        for rede in cfg['redes']:
            item = {'post': pid, 'rede': rede, 'titulo': p.get('titulo') or 'Sem título' if p else pid}
            if not p:
                saida['ajustes'].append(dict(item, motivo='Post não encontrado.'))
                continue
            chave = (_identidade(p), rede)
            if chave in vistos:
                saida['ignorados'].append(dict(item, motivo='Vídeo repetido na seleção.'))
                continue
            vistos.add(chave)
            iguais = [x for x in ps if _identidade(x) == chave[0] or x['video'] == p['video']]
            estados = [(x, x['redes'][rede]) for x in iguais if rede in x['redes']]
            if any(s['status'] in ('postado', 'postando') for _, s in estados):
                saida['ignorados'].append(dict(item, motivo='Já publicado ou em envio nesta rede.'))
                continue
            dono, atual = next(((x, s) for x, s in estados if s['status'] in ('agendado', 'manual')), estados[0] if estados else (p, None))
            item['post'] = dono['id']
            if atual and atual['status'] in ('agendado', 'manual') and not cfg['reagendar']:
                saida['ignorados'].append(dict(item, motivo='Já agendado nesta rede.'))
                continue
            if atual and atual['status'] == 'liberacao':
                saida['ajustes'].append(dict(item, motivo='Falta sua liberação; confira o post primeiro.'))
                continue
            try:
                if not pg.video_pronto(dono['video']):
                    raise pg.ErroRede('Vídeo ainda sendo preparado.')
                pg.video_path(dono['video'])
            except pg.ErroRede as e:
                saida['ajustes'].append(dict(item, motivo=str(e)))
                continue
            antigo = horario(dono, atual) if atual else None
            # Ao reagendar, libera somente o horário antigo deste destino na prévia.
            if antigo is not None and antigo in ocupados[rede]:
                ocupados[rede].remove(antigo)
            if cfg['modo'] == 'programacao':
                livres[rede] = [s for s in livres[rede] if not any(abs(s['quando_utc'] - t) < 60 for t in ocupados[rede])]
                if not livres[rede]:
                    saida['ajustes'].append(dict(item, motivo='Sem horário livre na programação ativa dos próximos dias.'))
                    continue
                s = livres[rede].pop(0)
                q, slot = s['quando_utc'], s['id']
            else:
                q, slot = proximos[rede], None
                bloqueados = ocupados[rede] + [s['quando_utc'] for s in slots if s['rede'] == rede and (antigo is None or abs(s['quando_utc'] - antigo) >= 1)]
                while any(abs(q - t) < 60 for t in bloqueados):
                    q += cfg['intervalo_s']
                proximos[rede] = q + cfg['intervalo_s']
            ocupados[rede].append(q)
            saida['agendados'].append(dict(item, quando=q, slot=slot))
    return saida


def previa(d):
    cfg = _parametros(d)
    with agenda._LOCK, pg.LOCK:
        plano = _planejar(cfg, pg.posts())
    # O cliente devolve este hash: se os horários ou os itens mudarem, pede uma prévia nova.
    plano['versao'] = hashlib.sha256(json.dumps(plano, sort_keys=True).encode()).hexdigest()
    return plano


def criar(d, quem='site'):
    lid = str(d.get('chave') or '')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{12,80}', lid):
        raise pg.ErroRede('Identificador do lote inválido. Abra o agendamento novamente.')
    assinatura = hashlib.sha256(json.dumps({k: v for k, v in d.items() if k != 'versao'}, sort_keys=True).encode()).hexdigest()
    with agenda._LOCK, pg.LOCK:
        guardado = db.kv('publicacao_lote:' + lid)
        if guardado:
            if guardado['assinatura'] != assinatura:
                raise pg.ErroRede('Este identificador já pertence a outro lote.')
            return dict(guardado['resultado'], repetido=True)
        ps = pg.posts()
        existentes = [(p, r, s) for p in ps for r, s in p['redes'].items() if s.get('lote') == lid]
        if existentes:  # recuperação se o processo caiu entre salvar os posts e registrar o recibo
            if any(s.get('lote_assinatura') != assinatura for _, _, s in existentes):
                raise pg.ErroRede('Este identificador já pertence a outro lote.')
            return {'lote': lid, 'agendados': [{'post': p['id'], 'rede': r, 'quando': s['quando'], 'titulo': p['titulo']} for p, r, s in existentes],
                    'ignorados': [], 'ajustes': [], 'repetido': True}
        cfg = _parametros(d)
        plano = _planejar(cfg, ps)
        versao = hashlib.sha256(json.dumps(plano, sort_keys=True).encode()).hexdigest()
        if d.get('versao') != versao:
            raise pg.ErroRede('A lista ou os horários mudaram. Gere uma nova prévia antes de agendar.')
        por_id = {p['id']: p for p in ps}
        for x in plano['agendados']:
            p = por_id[x['post']]
            s = p['redes'].setdefault(x['rede'], {'link': '', 'erro': ''})
            s.update(status='manual' if x['rede'] == 'kwai' else 'agendado', quando=x['quando'], proxima=0,
                     erro='', tentativas=0, outra_rede=True, lote=lid, lote_assinatura=assinatura,
                     lote_inicio=cfg['inicio'], lote_intervalo=cfg['intervalo_s'], intervalo_api_s=cfg['intervalo_api_s'],
                     lote_pausado=False, lote_slot=x['slot'])
            pg._anotar(p, x['rede'], 'lote_agendado', 'Agendado em lote por ' + quem)
        if plano['agendados']:
            pg.salvar_posts(ps)  # uma gravação atômica, sem disparar chamadas para as redes
            for x in plano['agendados']:
                if x['slot']:
                    db.executar("UPDATE posting_slots SET estado='agendado', post=?, motivo='Agendado em lote', atualizado=? WHERE id=?",
                                x['post'], time.time(), x['slot'])
        res = dict(plano, lote=lid)
        db.kv_gravar('publicacao_lote:' + lid, {'assinatura': assinatura, 'resultado': res})
    pg.acordar()
    return res


def listar():
    grupos = {}
    for p in pg.posts():
        for rede, s in p['redes'].items():
            if not s.get('lote'):
                continue
            l = grupos.setdefault(s['lote'], {'id': s['lote'], 'inicio': s.get('lote_inicio'), 'total': 0, 'publicados': 0, 'pendentes': 0, 'cancelados': 0, 'pausado': False, 'redes': []})
            l['total'] += 1
            if rede not in l['redes']:
                l['redes'].append(rede)
            if s['status'] == 'postado':
                l['publicados'] += 1
            elif s['status'] == 'cancelado':
                l['cancelados'] += 1
            else:
                l['pendentes'] += 1
                l['pausado'] = l['pausado'] or bool(s.get('lote_pausado'))
    return {'lotes': list(grupos.values())[::-1]}


def acao(lid, operacao):
    if operacao not in ('pausar', 'retomar', 'cancelar'):
        raise pg.ErroRede('Ação do lote inválida.')
    with agenda._LOCK, pg.LOCK:
        ps, encontrado = pg.posts(), False
        for p in ps:
            for rede, s in p['redes'].items():
                if s.get('lote') != lid:
                    continue
                encontrado = True
                if s['status'] in ('postado', 'postando', 'cancelado'):
                    continue
                if operacao == 'cancelar':
                    s.update(status='cancelado', lote_pausado=False, erro='Cancelado por você.')
                    if s.get('lote_slot'):
                        db.executar("UPDATE posting_slots SET estado='cancelado', motivo='Lote cancelado por você', atualizado=? WHERE id=?", time.time(), s['lote_slot'])
                else:
                    s['lote_pausado'] = operacao == 'pausar'
                pg._anotar(p, rede, 'lote_' + operacao, 'Ação aplicada somente aos envios restantes do lote.')
        if not encontrado:
            raise pg.ErroRede('Lote não encontrado.')
        pg.salvar_posts(ps)
    pg.acordar()
    return listar()
