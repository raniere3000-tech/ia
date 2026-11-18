"""Rotas da esteira dos 5 agentes, do diretor de qualidade, das capacidades, das referências virais e da programação diária do Agente 2."""
from __future__ import annotations

import re
import time

import agenda_postagem as ag2
import capacidades as cap
import contratos as ct
import inteligencia_viral as iv
import pipeline as pl

PREFIXOS = ('/api/v1/pipeline', '/api/v1/quality', '/api/v1/capabilities', '/api/v1/viral', '/api/v1/agent2')


class ErroRota(Exception):
    def __init__(self, status: int, msg: str):
        super().__init__(msg)
        self.status = status


def _q(q: dict, k: str, padrao: str = '') -> str:
    return (q.get(k) or [padrao])[0]


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def tratar(metodo: str, caminho: str, q: dict, corpo, quem: str, cabecalhos=None) -> dict:
    try:
        return _tratar(metodo, caminho, q, corpo, quem, cabecalhos or {})
    except pl.ErroPipeline as e:
        raise ErroRota(e.status, str(e))
    except ct.ErroContrato as e:
        raise ErroRota(400, str(e))
    except ag2.ErroAgenda as e:
        raise ErroRota(e.status, str(e))


def _tratar(metodo: str, caminho: str, q: dict, corpo, quem: str, cab) -> dict:
    rota = (metodo, caminho)
    # ---- esteira
    if rota == ('GET', '/api/v1/pipeline'):
        return pl.painel()
    if rota == ('PUT', '/api/v1/pipeline/chave'):
        return pl.ligar(bool(corpo().get('ligado')), quem)
    if rota == ('GET', '/api/v1/pipeline/jobs'):
        return {'execucoes': pl.lista(int(_f(_q(q, 'limite', '50')) or 50), _q(q, 'estado'))}
    m = re.fullmatch(r'/api/v1/pipeline/jobs/(\w{6,20})', caminho)
    if m and metodo == 'GET':
        return pl.obter(m.group(1))
    m = re.fullmatch(r'/api/v1/pipeline/jobs/(\w{6,20})/history', caminho)
    if m and metodo == 'GET':
        r = pl.obter(m.group(1))
        import banco as db
        return {'eventos': db.todos("SELECT * FROM eventos WHERE recurso=? ORDER BY n", 'run:' + m.group(1)), 'planos': r['planos'],
                'relatorios': [{k: x[k] for k in ('id', 'modalidade', 'score', 'passed', 'created_at', 'sha256')} for x in r['relatorios']]}
    m = re.fullmatch(r'/api/v1/pipeline/jobs/(\w{6,20})/manual-review', caminho)
    if m and metodo == 'POST':
        d = corpo()
        r = pl.decidir_manual(m.group(1), str(d.get('decisao', '')), str(d.get('motivo', '')), quem)
        if r['origem'] in ('corte', 'manual', 'importado'):
            import agente as ag
            ag.esteira_decidiu(r['ref'], r['estado'] == 'final_approved')
        return r
    # ---- diretor de qualidade
    m = re.fullmatch(r'/api/v1/quality/reports/(\w{6,20})', caminho)
    if m and metodo == 'GET':
        return pl.relatorio(m.group(1))
    if rota == ('GET', '/api/v1/quality/policy'):
        return {'nota_minima': ct.NOTA_MINIMA, 'max_correcoes': ct.MAX_CORRECOES, 'versao': ct.VERSAO_POLITICA, 'pesos': ct.PESOS, 'nomes': ct.NOMES_PARTES,
                'bloqueios_duros': ct.BLOQUEIOS_DUROS, 'acoes': list(ct.ACOES), 'efeitos': list(ct.EFEITOS)}
    # ---- capacidades e referências
    if rota == ('GET', '/api/v1/capabilities'):
        return cap.listar(_q(q, 'conferir') == '1')
    if rota == ('GET', '/api/v1/viral/references'):
        return iv.referencias(_q(q, 'topic')[:80], _q(q, 'platform', 'youtube'), _q(q, 'lang', 'pt'), _q(q, 'refresh') == '1')
    # ---- Agente 2: programação diária
    if rota == ('GET', '/api/v1/agent2/schedules'):
        return {'agendas': ag2.listar(), 'redes': ag2.NOMES_REDE, 'dias': ag2.DIAS, 'esteira': pl.ligado()}
    if rota == ('POST', '/api/v1/agent2/schedules'):
        return ag2.criar(corpo(), quem)
    if rota == ('POST', '/api/v1/agent2/preview'):
        return ag2.previa(corpo())
    m = re.fullmatch(r'/api/v1/agent2/schedules/(\w{6,20})(/preview)?', caminho)
    if m:
        aid = m.group(1)
        if m.group(2) and metodo == 'POST':
            atual = ag2._agenda(aid)
            base = {k: v for k, v in atual.items() if k not in ('id', 'version', 'atualizado')}
            base.update({k: v for k, v in corpo().items() if k not in ('platform', 'account_id')})
            return ag2.previa(base)
        if metodo == 'GET':
            return ag2._agenda(aid)
        if metodo in ('PATCH', 'PUT'):
            d = corpo()
            versao = d.get('version', cab.get('If-Match'))
            return ag2.atualizar(aid, d, int(_f(versao)) if _f(versao) is not None else None, quem)
        if metodo == 'DELETE':
            return ag2.desativar(aid, quem)
    if rota == ('GET', '/api/v1/agent2/slots'):
        return {'slots': ag2.slots(_f(_q(q, 'from')), _f(_q(q, 'to')), _q(q, 'platform'), _q(q, 'account_id')), 'agora': time.time()}
    m = re.fullmatch(r'/api/v1/agent2/slots/(\w{6,20})', caminho)
    if m and metodo == 'PATCH':
        return _mudar_slot(m.group(1), corpo(), quem)
    if rota == ('POST', '/api/v1/agent2/run'):
        return ag2.ciclo()
    if rota == ('GET', '/api/v1/agent2/metrics'):
        return ag2.metricas(_q(q, 'date'), _q(q, 'platform'), _q(q, 'account_id'))
    raise ErroRota(404, 'Rota não encontrada.')


def _mudar_slot(sid: str, d: dict, quem: str) -> dict:
    """Cancelar um horário: libera o vídeo de volta para a fila (nada é postado no lugar automaticamente)."""
    import banco as db
    s = db.um('SELECT * FROM posting_slots WHERE id=?', sid)
    if not s:
        raise ErroRota(404, 'Horário não encontrado.')
    if d.get('acao') != 'cancelar':
        raise ErroRota(400, 'Ação inválida (cancelar).')
    if s['estado'] in ('publicado', 'publicando'):
        raise ErroRota(409, 'Este horário já foi postado ou está sendo enviado.')
    if s.get('post'):
        import postagem as pg
        try:
            pg.cancelar_post(s['post'], manter_video=True)
        except pg.ErroRede:
            pass
        import agente as ag
        ag._mudar(lambda e: [x.update(status='pronto', post='', quando=None) for x in e['cortes'] if x['id'] == s['ref'] and x.get('post') == s['post']])
    db.executar("UPDATE posting_slots SET estado='cancelado', motivo=?, atualizado=? WHERE id=?", ('Cancelado por ' + quem)[:200], time.time(), sid)
    db.evento(quem, 'slot_cancelado', 'slot:' + sid)
    return db.um('SELECT * FROM posting_slots WHERE id=?', sid)
