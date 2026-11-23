"""Painel do Início e da Central de Agentes: SÓ LEITURA, só números que o servidor tem de verdade.

Regras (pedido do Raniere, 19/11):
- nada é inventado: o que o servidor não sabe vai como None ("Não disponível" no site), nunca 0;
- vídeos, tarefas e tentativas são unidades diferentes e não se somam;
- "aprovado" = certificado final válido do diretor (esteira), não só "trabalho concluído";
- agendado ≠ publicado; tempo ativo = tempo medido rodando (coluna `decorrido` da fila), sem a espera;
- este módulo nunca grava nada, não posta, não aprova e não mexe em certificado.
"""
from __future__ import annotations

import time

import banco as db

PERIODOS = ('hoje', '7d', '30d')
# mesmos nomes da fila que o Coordenador usa (coordenador.AGENTES_JOBS)
AGENTES_JOBS = {'agente1': ('agente1',), 'agente2': ('agent2',), 'agente3': ('agente3', 'agent3'), 'agente4': ('agent4',),
                'agente5': ('agent5', 'editor'), 'agente6': ('agente6',)}


def inicio_periodo(periodo: str, agora: float | None = None) -> float:
    """Hoje = desde a meia-noite no fuso do servidor; 7d e 30d = janelas corridas."""
    agora = time.time() if agora is None else agora
    if periodo == 'hoje':
        t = time.localtime(agora)
        return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))
    return agora - (7 if periodo == '7d' else 30) * 86400


def _n(sql: str, *a) -> int:
    r = db.um(sql, *a)
    return int((r or {}).get('n') or 0)


def _seguro(f, padrao=None):
    try:
        return f()
    except Exception:  # noqa: BLE001 — uma fonte com problema não derruba o painel; ela só fica "não disponível"
        return padrao


def _posts() -> list | None:
    import postagem as pg
    return pg.posts()


def _esteira_ligada() -> bool | None:
    import pipeline as pl
    return bool(pl.ligado())


ESTADOS_REAIS = {'ativo': 'Trabalhando', 'na_fila': 'Na fila', 'aguardando_voce': 'Esperando você', 'bloqueado': 'Bloqueado',
                 'aguardando_etapa': 'Esperando a etapa anterior', 'sem_demanda': 'Sem trabalho agora'}


def _estado_real(ag_id: str, a: dict, ini: float) -> dict:
    """Estado de verdade do agente: junta a fila (trabalho rodando) com o registro da esteira dos 7 agentes
    (o diretor e o editor trabalham DENTRO do trabalho do Agente 1, então a fila sozinha diria "parado")."""
    est = (a or {}).get('esteira') or {}
    e_est = est.get('estado')
    fila = (a or {}).get('estado')
    if fila in ('trabalhando', 'coordenando') or e_est == 'ativo':
        real = 'ativo'
    elif e_est in ('aguardando_voce', 'bloqueado'):
        real = e_est
    elif fila == 'na_fila' or e_est == 'na_fila':
        real = 'na_fila'
    elif e_est == 'aguardando_etapa':
        real = 'aguardando_etapa'
    else:
        real = 'sem_demanda' if e_est is not None or fila else None
    def met():
        import esteira as es
        return es.metricas_agente(ag_id, ini)
    return {'estado_real': real, 'estado_real_nome': ESTADOS_REAIS.get(real) if real else None, 'motivo': est.get('motivo') or '',
            'esteira_agora': est.get('agora') or [], 'esteira_contagem': est.get('contagem') or {}, 'esteira_periodo': _seguro(met)}


def _esteira7() -> dict:
    import esteira as es
    r = es.resumo()
    r['politica'] = es.politica()
    return r


def resumo(periodo: str = '7d') -> dict:
    if periodo not in PERIODOS:
        periodo = '7d'
    agora = time.time()
    ini = inicio_periodo(periodo, agora)
    posts = _seguro(_posts)
    esteira = _seguro(_esteira_ligada)

    # ---- vídeos produzidos (unidade = vídeo distinto)
    def a1():
        import agente as ag
        return sum(1 for c in ag.estado()['cortes'] if (c.get('criado') or 0) >= ini and c.get('status') not in ('descartado', 'reprovado'))
    def a3():
        return _n('SELECT COUNT(DISTINCT sha256) AS n FROM renders WHERE criado>=? AND sha256 IS NOT NULL AND sha256<>\'\'', ini)
    v1, v3 = _seguro(a1), _seguro(a3)
    videos = None if v1 is None and v3 is None else (v1 or 0) + (v3 or 0)

    # ---- aprovados (certificado final válido do diretor), ainda sem post
    def aprovados():
        if not esteira:
            return None
        return _n("SELECT COUNT(DISTINCT r.id) AS n FROM pipeline_runs r JOIN approval_certificates c ON c.run=r.id "
                  "WHERE r.estado IN ('final_approved','awaiting_human_publish_approval') AND c.modalidade='final_release' "
                  "AND c.revogado IS NULL AND (c.expira IS NULL OR c.expira>?)", agora)
    aprov = _seguro(aprovados)

    # ---- posts (unidade = post numa rede)
    agendados = publicados = posts_erro = None
    proxima = None
    if posts is not None:
        agendados = publicados = posts_erro = 0
        for p in posts:
            for rede, r in (p.get('redes') or {}).items():
                st = r.get('status')
                if st == 'agendado':
                    agendados += 1
                    q = float(p.get('quando') or 0)
                    if q and (proxima is None or q < proxima['quando']):
                        proxima = {'post': p.get('id'), 'titulo': (p.get('titulo') or '')[:100], 'quando': q, 'redes': [], 'status': 'agendado'}
                elif st == 'postado' and float(r.get('feito') or 0) >= ini:
                    publicados += 1
                elif st == 'erro':
                    posts_erro += 1
        if proxima:
            pp = next(p for p in posts if p.get('id') == proxima['post'])
            proxima['redes'] = [rd for rd, r in pp['redes'].items() if r.get('status') == 'agendado']

    # ---- tarefas (unidade = trabalho da fila)
    em_producao = _seguro(lambda: _n("SELECT COUNT(*) AS n FROM jobs WHERE status IN ('rodando','na_fila','aguardando_tentativa')"))
    falhas = _seguro(lambda: _n("SELECT COUNT(*) AS n FROM jobs WHERE status='falhou' AND terminado>=?", ini))

    # ---- decisões que dependem de você (unidade = item para decidir)
    def decisao():
        import decisoes      # mesma conta da faixa vermelha do topo do site (só os itens que travam algo)
        n = decisoes.contar_urgentes()
        if n is not None:
            return n
        import aprovacoes as apv
        n = len(apv.pendentes())
        n += _seguro(lambda: _n("SELECT COUNT(*) AS n FROM coordenador_aprovacoes WHERE decisao='pendente' AND revogado IS NULL"), 0)
        n += _seguro(lambda: _n("SELECT COUNT(*) AS n FROM pipeline_runs WHERE estado='manual_review_required'"), 0)
        return n
    esperando = _seguro(decisao)

    # ---- por agente (estado atual vem do Coordenador; contagens do período vêm da fila)
    atual = _seguro(lambda: {a['id']: a for a in __import__('coordenador').agentes()['agentes']}, {})
    # O relógio do Agente 1 também trabalha fora da fila. Conta a execução uma
    # única vez, sem somar os seis cortes previstos nem duplicar um job existente.
    if em_producao is not None:
        for j in (atual.get('agente1') or {}).get('atual', []):
            if j.get('execucao_direta'):
                registrado = _seguro(lambda: _n("SELECT COUNT(*) AS n FROM jobs WHERE id=? AND status IN ('rodando','na_fila','aguardando_tentativa')", j['job']))
                em_producao = None if registrado is None else em_producao + (0 if registrado else 1)
                if em_producao is None:
                    break
    agentes = []
    for ag_id, nomes in AGENTES_JOBS.items():
        ph = ','.join('?' * len(nomes))
        def conta(ag_id=ag_id, ph=ph, nomes=nomes):
            r = db.um(f"SELECT SUM(status='concluido') AS ok, SUM(status='falhou') AS erro, SUM(COALESCE(decorrido,0)) AS seg, COUNT(*) AS n "
                      f"FROM jobs WHERE agente IN ({ph}) AND status IN ('concluido','falhou') AND terminado>=?", *nomes, ini) or {}
            return {'concluidas': int(r.get('ok') or 0), 'falhas': int(r.get('erro') or 0),
                    'tempo_ativo_s': round(r['seg']) if r.get('n') and r.get('seg') else None}
        c = _seguro(conta, {'concluidas': None, 'falhas': None, 'tempo_ativo_s': None})
        a = atual.get(ag_id) or {}
        item = {'id': ag_id, 'estado': a.get('estado'), 'atual': a.get('atual') or [], 'na_fila': a.get('na_fila'),
                'concluidas_periodo': c['concluidas'], 'falhas_periodo': c['falhas'], 'tempo_ativo_s': c['tempo_ativo_s'],
                'tempos_medios': a.get('tempos_medios') or {}}
        item.update(_estado_real(ag_id, a, ini))
        if ag_id == 'agente2':        # o Agente 2 posta pelo próprio relógio (não usa a fila): conta pelos posts
            item['concluidas_periodo'] = publicados
            item['falhas_periodo'] = posts_erro
            item['unidade'] = 'posts por rede'
        agentes.append(item)
    def a7():
        ok = _n("SELECT COUNT(*) AS n FROM coordenador_ordens WHERE status IN ('concluida','parcial') AND atualizado>=?", ini)
        er = _n("SELECT COUNT(*) AS n FROM coordenador_ordens WHERE status='falhou' AND atualizado>=?", ini)
        return ok, er
    ok7, er7 = _seguro(a7, (None, None))
    x7 = atual.get('agente7') or {}
    agentes.append({'id': 'agente7', 'estado': x7.get('estado'), 'atual': [], 'na_fila': None, 'ordens_ativas': x7.get('ordens_ativas'),
                    'esperando_voce': x7.get('esperando_voce'), 'modo': x7.get('modo'), 'concluidas_periodo': ok7, 'falhas_periodo': er7,
                    'tempo_ativo_s': None, 'unidade': 'pedidos', 'tempos_medios': {}, **_estado_real('agente7', x7, ini)})

    # ---- atenção (só o que dá para conferir)
    alertas = []
    if posts_erro:
        alertas.append({'tipo': 'post_erro', 'texto': f'{posts_erro} envio(s) para redes com erro', 'onde': 'agendar'})
    if esperando:
        alertas.append({'tipo': 'decisao', 'texto': f'{esperando} item(ns) esperando a sua decisão', 'onde': 'fila'})
    f24 = _seguro(lambda: _n("SELECT COUNT(*) AS n FROM jobs WHERE status='falhou' AND terminado>=?", agora - 86400))
    if f24:
        alertas.append({'tipo': 'falha', 'texto': f'{f24} trabalho(s) falharam nas últimas 24 h', 'onde': 'fila'})
    revog = _seguro(lambda: _n('SELECT COUNT(*) AS n FROM approval_certificates WHERE revogado>=?', agora - 7 * 86400))
    if revog:
        alertas.append({'tipo': 'certificado', 'texto': f'{revog} certificado(s) do diretor revogado(s) nos últimos 7 dias', 'onde': 'agente:esteira'})

    return {
        'gerado_em': agora, 'periodo': periodo, 'inicio': ini, 'backend_disponivel': True, 'esteira_ligada': esteira,
        'esteira7': _seguro(_esteira7),
        'totais': {'videos_criados': videos, 'videos_por_origem': {'agente1': v1, 'agente3': v3}, 'aprovados_disponiveis': aprov,
                   'agendados': agendados, 'publicados': publicados, 'em_producao': em_producao, 'esperando_decisao': esperando,
                   'falhas': falhas, 'posts_com_erro': posts_erro},
        'definicoes': {
            'videos_criados': 'Cortes do Agente 1 criados no período + vídeos do Agente 3 (arquivos distintos por SHA-256).',
            'aprovados_disponiveis': 'Vídeos com certificado final válido do diretor que ainda não foram para a fila de postagem (só com a esteira ligada).',
            'agendados': 'Envios marcados para uma rede e ainda não feitos (cada rede conta 1). Agora, não no período.',
            'publicados': 'Envios feitos com sucesso no período (cada rede conta 1).',
            'em_producao': 'Trabalhos rodando ou na fila agora, incluindo a rotina automática do Agente 1 (tarefas, não vídeos).',
            'esperando_decisao': 'Itens parados esperando você (os mesmos da faixa vermelha do topo): vídeos e roteiros, planos e pacotes do Coordenador, revisões da esteira, capas para escolher e posts barrados.',
            'falhas': 'Trabalhos da fila que falharam no período (tarefas).',
        },
        'agentes': agentes, 'proxima_publicacao': proxima, 'alertas': alertas,
    }
