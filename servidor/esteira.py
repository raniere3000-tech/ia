"""Esteira obrigatória dos 7 agentes: cada vídeo (corte ou vídeo próprio) tem um registro com uma linha por etapa.

  Corte:         A1 corta -> A4 prévio -> A5 edita -> A4 final -> A6 capa -> A7 libera o pacote -> A2 agenda -> A2 publica
  Vídeo próprio: A3 cria  -> A4 prévio -> A5 edita -> A4 final -> A6 capa -> A7 libera o pacote -> A2 agenda -> A2 publica

Regras:
- Uma etapa só fica "concluida" com prova: id do corte, laudo do diretor, SHA do arquivo exportado, certificado, capa escolhida
  presa ao SHA, liberação do pacote, id do post, link da rede. Pedir para fazer NÃO é concluir.
- As etapas são marcadas por quem trabalha (agente.py, editor_ia.py, produtor.py) na hora em que o trabalho acontece, com o tempo
  medido. Este módulo não refaz trabalho para "aparecer": ele só segue (A6, A7 e A2) a partir do que já foi provado.
- Arquivo mudou: as aprovações dali para a frente caem (capa, liberação), e só o necessário é refeito.
- Política (esteira.politica): "completa" ligada = nenhum vídeo sai sem certificado do diretor E liberação do Coordenador,
  em qualquer caminho (corte automático, corte manual, vídeo próprio, agenda diária, postar agora, nova tentativa).
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

import banco as db

ETAPAS = (('producao', ''), ('a4_previo', 'agente4'), ('a5_edicao', 'agente5'), ('a4_final', 'agente4'), ('a6_capa', 'agente6'),
          ('a7_liberacao', 'agente7'), ('a2_agendamento', 'agente2'), ('a2_publicacao', 'agente2'))
ORDEM = [e for e, _ in ETAPAS]
NOMES = {'producao': 'Produção', 'a4_previo': 'Diretor: avaliação inicial', 'a5_edicao': 'Editor: edição e exportação',
         'a4_final': 'Diretor: arquivo final', 'a6_capa': 'Capa (thumbnail)', 'a7_liberacao': 'Coordenador: liberação final',
         'a2_agendamento': 'Publicador: agendamento', 'a2_publicacao': 'Publicador: envio às redes'}
ESTADOS = ('pendente', 'aguardando_dependencia', 'na_fila', 'executando', 'aguardando_usuario', 'aguardando_recurso', 'corrigindo', 'concluida',
           'reprovada', 'revisao_manual', 'falhou', 'cancelada', 'pulada_justificada')
NOMES_ESTADO = {'pendente': 'Pendente', 'aguardando_dependencia': 'Esperando a etapa anterior', 'na_fila': 'Na fila', 'executando': 'Trabalhando',
                'aguardando_usuario': 'Esperando você', 'aguardando_recurso': 'Falta um recurso', 'corrigindo': 'Corrigindo', 'concluida': 'Concluída',
                'reprovada': 'Reprovada', 'revisao_manual': 'Revisão manual', 'falhou': 'Falhou', 'cancelada': 'Cancelada',
                'pulada_justificada': 'Não se aplica'}
OK = ('concluida', 'pulada_justificada')
ATIVOS = ('executando', 'corrigindo')
PARADOS = ('aguardando_usuario', 'revisao_manual', 'aguardando_recurso')
RUINS = ('falhou', 'reprovada')
MAX_CORRECOES = 5
POLITICA_PADRAO = {'completa': True, 'capa_obrigatoria': True, 'liberacao_automatica': True, 'versao': 1}
_LOCK = threading.RLock()


class ErroEsteira(Exception):
    def __init__(self, msg: str, status: int = 400):
        super().__init__(msg)
        self.status = status


def _agora() -> float:
    return time.time()


def _j(x) -> str:
    return json.dumps(x, ensure_ascii=False, default=str)


def _l(s, padrao=None):
    try:
        return json.loads(s) if s else padrao
    except (TypeError, ValueError):
        return padrao


# ---------------------------------------------------------------- política
def politica() -> dict:
    p = {**POLITICA_PADRAO, **(db.kv('esteira.politica', {}) or {})}
    if os.getenv('ESTEIRA_COMPLETA') in ('0', '1'):          # testes antigos (fluxo de antes) desligam por variável
        p['completa'] = os.getenv('ESTEIRA_COMPLETA') == '1'
    return p


def completa() -> bool:
    try:
        return bool(politica()['completa'])
    except Exception:  # noqa: BLE001  (banco sem a migração: fluxo antigo)
        return False


def salvar_politica(d: dict, quem: str = 'site') -> dict:
    atual = {**POLITICA_PADRAO, **(db.kv('esteira.politica', {}) or {})}
    if 'versao' in d and int(d['versao']) != int(atual['versao']):
        raise ErroEsteira('A política mudou em outro aparelho. Atualize a tela.', 409)
    for k in ('completa', 'capa_obrigatoria', 'liberacao_automatica'):
        if k in d:
            atual[k] = bool(d[k])
    atual['versao'] = int(atual['versao']) + 1
    db.kv_gravar('esteira.politica', atual)
    db.evento(quem, 'esteira_politica', 'esteira', {k: atual[k] for k in ('completa', 'capa_obrigatoria', 'liberacao_automatica', 'versao')})
    return politica()


# ---------------------------------------------------------------- registro
def vid_de(origem: str, ref: str) -> str:
    return f'{"render" if origem in ("render", "agente3") else "corte"}:{ref}'


def garantir(origem: str, ref: str, titulo: str = '', *, ordem_id: str | None = None, run: str | None = None) -> str:
    """Cria (uma vez) o registro do vídeo com as 8 etapas. Idempotente."""
    vid = vid_de(origem, ref)
    agora = _agora()
    with _LOCK:
        if not db.um('SELECT id FROM esteira_videos WHERE id=?', vid):
            db.executar('INSERT OR IGNORE INTO esteira_videos (id, origem, ref, titulo, ordem_id, run, estado, etapa_atual, motivo, politica, criado, atualizado) '
                        'VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', vid, 'render' if vid.startswith('render:') else 'corte', ref, (titulo or '')[:160], ordem_id, run,
                        'em_andamento', 'producao', '', _j(politica()), agora, agora)
            produtor = 'agente3' if vid.startswith('render:') else 'agente1'
            for i, (e, ag) in enumerate(ETAPAS):
                db.executar('INSERT OR IGNORE INTO esteira_etapas (id, video, etapa, agente, estado, ordem, atualizado) VALUES (?,?,?,?,?,?,?)',
                            hashlib.sha1(f'{vid}|{e}'.encode()).hexdigest()[:16], vid, e, ag or produtor, 'pendente' if i == 0 else 'aguardando_dependencia', i, agora)
        else:
            sets, a = [], []
            for k, v in (('titulo', (titulo or '')[:160]), ('ordem_id', ordem_id), ('run', run)):
                if v:
                    sets.append(f'{k}=COALESCE(NULLIF({k}, \'\'), ?)')
                    a.append(v)
            if sets:
                db.executar(f'UPDATE esteira_videos SET {", ".join(sets)} WHERE id=?', *a, vid)
    return vid


def _etapa(vid: str, etapa: str) -> dict | None:
    r = db.um('SELECT * FROM esteira_etapas WHERE video=? AND etapa=?', vid, etapa)
    if r:
        r['recibo'] = _l(r['recibo'], {}) or {}
    return r


def marcar(vid: str, etapa: str, estado: str, *, recibo: dict | None = None, entrada_sha: str | None = None, saida_sha: str | None = None,
           erro: str | None = None, motivo: str | None = None, executor: str | None = None, inicio: float | None = None, fim: float | None = None,
           correcoes: int | None = None, segundos_fila: float | None = None, nova_tentativa: bool = False) -> dict:
    """Muda o estado de uma etapa com a prova. O tempo ativo soma cada trecho "trabalhando/corrigindo" até a etapa parar."""
    if etapa not in ORDEM or estado not in ESTADOS:
        raise ErroEsteira(f'Etapa ou estado inválido: {etapa}/{estado}')
    agora = _agora()
    with _LOCK:
        e = _etapa(vid, etapa)
        if not e:
            raise ErroEsteira('Vídeo sem registro na esteira.', 404)
        if estado == 'concluida' and not (recibo or e['recibo']):
            raise ErroEsteira('Etapa só conclui com prova (recibo).')
        ativo = float(e['segundos_ativos'] or 0)
        if e['estado'] in ATIVOS and estado not in ATIVOS:       # fecha o trecho trabalhado
            ult = db.um("SELECT t FROM esteira_historico WHERE video=? AND etapa=? AND estado IN ('executando','corrigindo') ORDER BY n DESC LIMIT 1", vid, etapa)
            base = inicio if inicio is not None else (ult['t'] if ult else agora)
            ativo += max(0.0, (fim or agora) - base)
        elif estado not in ATIVOS and inicio is not None and fim is not None and e['estado'] not in ATIVOS:
            ativo += max(0.0, fim - inicio)                       # trabalho feito de uma vez (ex.: medido por quem fez)
        ini = e['inicio'] or (inicio if inicio is not None else (agora if estado in ATIVOS or estado in OK else None))
        fim_v = (fim or agora) if estado in OK + RUINS + ('revisao_manual', 'cancelada') else None
        rec = {**(e['recibo'] or {}), **(recibo or {})} if recibo is not None else e['recibo']
        db.executar('UPDATE esteira_etapas SET estado=?, recibo=?, entrada_sha=COALESCE(?, entrada_sha), saida_sha=COALESCE(?, saida_sha), inicio=?, fim=?, '
                    'segundos_ativos=?, segundos_fila=COALESCE(?, segundos_fila), tentativas=tentativas+?, correcoes=COALESCE(?, correcoes), erro=?, motivo=?, '
                    'executor=COALESCE(?, executor), atualizado=? WHERE id=?',
                    estado, _j(rec) if rec else None, entrada_sha, saida_sha, ini, fim_v, round(ativo, 3), segundos_fila,
                    1 if (nova_tentativa or (estado in ATIVOS and e['estado'] not in ATIVOS)) else 0, correcoes,
                    (erro or '')[:500] or None, (motivo or '')[:500] or None, executor, agora, e['id'])
        if estado != e['estado'] or recibo:
            db.executar('INSERT INTO esteira_historico (video, etapa, estado, detalhe, t) VALUES (?,?,?,?,?)', vid, etapa, estado,
                        _j({'motivo': motivo or erro or '', 'recibo': recibo or {}, 'saida_sha': (saida_sha or '')[:16]})[:4000], agora)
        if estado in OK:          # libera a próxima etapa (só a que esperava esta)
            i = ORDEM.index(etapa)
            if i + 1 < len(ORDEM):
                db.executar("UPDATE esteira_etapas SET estado='pendente', atualizado=? WHERE video=? AND etapa=? AND estado='aguardando_dependencia'",
                            agora, vid, ORDEM[i + 1])
        _resumo(vid)
    return _etapa(vid, etapa)


def invalidar_depois(vid: str, etapa: str, motivo: str):
    """O arquivo (ou a capa) mudou: as etapas depois de `etapa` voltam a esperar. O histórico fica."""
    i = ORDEM.index(etapa)
    with _LOCK:
        for e in ORDEM[i + 1:]:
            x = _etapa(vid, e)
            if not x or x['estado'] in ('aguardando_dependencia',) or (e.startswith('a2_') and x['estado'] in OK):
                continue
            db.executar("UPDATE esteira_etapas SET estado='aguardando_dependencia', motivo=?, fim=NULL, atualizado=? WHERE id=?", motivo[:300], _agora(), x['id'])
            db.executar('INSERT INTO esteira_historico (video, etapa, estado, detalhe, t) VALUES (?,?,?,?,?)', vid, e, 'aguardando_dependencia',
                        _j({'motivo': motivo, 'invalidado': True}), _agora())
        _resumo(vid)


def _resumo(vid: str):
    ets = {e['etapa']: e for e in db.todos('SELECT etapa, estado, motivo, erro FROM esteira_etapas WHERE video=?', vid)}
    if not ets:
        return
    atual = next((e for e in ORDEM if ets[e]['estado'] not in OK), None)
    if atual is None:
        est, mot = 'publicado', ''
    else:
        x = ets[atual]
        est = {'aguardando_usuario': 'aguardando_voce', 'revisao_manual': 'aguardando_voce', 'aguardando_recurso': 'bloqueado', 'falhou': 'bloqueado',
               'reprovada': 'corrigindo', 'cancelada': 'cancelado', 'corrigindo': 'corrigindo'}.get(x['estado'], 'em_andamento')
        mot = x['motivo'] or x['erro'] or ''
        if x['estado'] == 'cancelada':
            est = 'cancelado'
        if x['estado'] == 'revisao_manual' and atual in ('a4_previo',) and 'descartado' in (mot or ''):
            est = 'descartado'
    db.executar('UPDATE esteira_videos SET estado=?, etapa_atual=?, motivo=?, atualizado=? WHERE id=?', est, atual or 'a2_publicacao', (mot or '')[:300], _agora(), vid)


MOTIVO_SUMIU = 'O vídeo foi apagado ou descartado.'


def reabrir_cancelados_por_engano() -> int:
    """Conserto de 22/11: cortes recém-aprovados eram cancelados porque o Agente 1 ainda não tinha salvo o corte na lista.
    Se o corte existe agora, com arquivo e sem ter sido descartado ou postado, o registro volta a andar (A6 -> A7 -> A2)."""
    import agente as ag
    import postagem as pg
    cortes = {c['id']: c for c in ag.estado()['cortes']}
    n = 0
    for v in db.todos("SELECT * FROM esteira_videos WHERE estado='cancelado' AND origem='corte' AND motivo=?", MOTIVO_SUMIU):
        c = cortes.get(v['ref'])
        if not c or not c.get('video') or c.get('status') in ('descartado', 'postado'):
            continue
        try:
            if not pg.video_path(c['video']).exists():
                continue
        except pg.ErroRede:
            continue
        with _LOCK:
            for e in ORDEM:
                x = _etapa(vid := v['id'], e)
                if x and x['estado'] == 'cancelada':
                    db.executar("UPDATE esteira_etapas SET estado='aguardando_dependencia', motivo=?, fim=NULL, atualizado=? WHERE id=?",
                                'Reaberto: o corte não tinha sumido (só ainda não estava salvo).', _agora(), x['id'])
            db.executar('INSERT INTO esteira_historico (video, etapa, estado, detalhe, t) VALUES (?,?,?,?,?)', vid, 'a6_capa', 'aguardando_dependencia',
                        _j({'motivo': 'Reaberto: cancelado por engano enquanto o Agente 1 salvava o corte.'}), _agora())
            _resumo(vid)
        n += 1
    return n


def cancelar(vid: str, motivo: str):
    with _LOCK:
        for e in ORDEM:
            x = _etapa(vid, e)
            if x and x['estado'] not in OK:
                db.executar("UPDATE esteira_etapas SET estado='cancelada', motivo=?, atualizado=? WHERE id=?", motivo[:300], _agora(), x['id'])
        db.executar('INSERT INTO esteira_historico (video, etapa, estado, detalhe, t) VALUES (?,?,?,?,?)', vid, 'producao', 'cancelada', _j({'motivo': motivo}), _agora())
        _resumo(vid)


# ---------------------------------------------------------------- ligações com quem trabalha
def vid_do_run(rid: str) -> str | None:
    """A execução da esteira antiga (pipeline_runs) diz de qual vídeo é."""
    try:
        r = db.um('SELECT origem, ref, titulo FROM pipeline_runs WHERE id=?', rid)
    except Exception:  # noqa: BLE001
        return None
    if not r:
        return None
    vid = garantir('render' if r['origem'] == 'agente3' else 'corte', r['ref'], r['titulo'] or '', run=rid)
    return vid


def marcar_run(rid: str, etapa: str, estado: str, **kw):
    """Atalho para quem só conhece a execução (editor_ia, produtor). Nunca derruba o trabalho de quem chamou."""
    try:
        vid = vid_do_run(rid)
        if vid:
            return marcar(vid, etapa, estado, **kw)
    except Exception as e:  # noqa: BLE001
        print('esteira:', etapa, estado, e)
    return None


def marcar_seguro(vid: str, etapa: str, estado: str, **kw):
    try:
        return marcar(vid, etapa, estado, **kw)
    except Exception as e:  # noqa: BLE001
        print('esteira:', etapa, estado, e)
        return None


# ---------------------------------------------------------------- arquivo atual do vídeo
def arquivo_atual(v: dict) -> tuple[Path | None, str, dict]:
    """(arquivo, sha, extra) da versão atual do vídeo. extra traz título/legenda/estado para a conferência do pacote."""
    import pipeline as pl
    if v['origem'] == 'corte':
        import agente as ag
        import postagem as pg
        c = next((x for x in ag.estado()['cortes'] if x['id'] == v['ref']), None)
        if not c or not c.get('video'):
            # o Agente 1 só grava o corte na lista DEPOIS do diretor aprovar o arquivo (e de guardar o trecho para o editor):
            # nesse intervalo o corte ainda não existe, mas não sumiu
            return None, '', {'sumiu': True, 'nao_salvo': True}
        if c.get('status') == 'descartado':
            return None, '', {'sumiu': True, 'corte': c, 'descartado': True}
        try:
            arq = pg.video_path(c['video'])
        except pg.ErroRede:
            return None, '', {'sumiu': True, 'corte': c}
        return arq, pl.sha_arquivo(arq), {'corte': c}
    import aprovacoes as apv
    import projetos as pj
    try:
        p = pj.obter(v['ref'])
    except pj.ErroProjeto:
        return None, '', {'sumiu': True}
    r = apv._render_atual(p)
    if not r:
        return None, '', {'projeto': p}
    return Path(r['arquivo']), r['sha'], {'projeto': p, 'render': r}


def ordem_do_projeto(pid: str) -> str | None:
    """Vídeo do Agente 3 pedido por uma ordem do Coordenador: qual ordem."""
    try:
        r = db.um("SELECT ordem_id FROM coordenador_tarefas WHERE acao='a3.produzir' AND resultado_json LIKE ? LIMIT 1", f'%"projeto":"{pid}"%')
    except Exception:  # noqa: BLE001
        return None
    return r['ordem_id'] if r else None


def _ordem_cuida(v: dict, acao: str) -> bool:
    """O vídeo é de uma ordem do Coordenador que já tem a tarefa (ex.: capas pedidas na ordem): o Coordenador pede, a esteira só acompanha."""
    if not v.get('ordem_id'):
        return False
    return bool(db.um('SELECT id FROM coordenador_tarefas WHERE ordem_id=? AND acao=? AND estado NOT IN (\'cancelada\')', v['ordem_id'], acao))


def _ordem_ja_liberou(v: dict) -> bool:
    """A tarefa de liberar da ordem já terminou (e não vai rodar de novo): se a liberação caiu, quem refaz é a esteira."""
    t = db.um("SELECT estado FROM coordenador_tarefas WHERE ordem_id=? AND acao='a7.liberar' AND estado NOT IN ('cancelada') ORDER BY rowid DESC LIMIT 1",
              v['ordem_id'])
    return bool(t and t['estado'] == 'concluida')


# ---------------------------------------------------------------- condutor: A6 -> A7 -> A2 a partir do que já foi provado
def avancar(vid: str, posts: list | None = None) -> dict | None:
    v = db.um('SELECT * FROM esteira_videos WHERE id=?', vid)
    if not v or v['estado'] in ('cancelado', 'publicado', 'descartado'):
        return v
    ets = {e: _etapa(vid, e) for e in ORDEM}
    arq, sha, extra = arquivo_atual(v)
    if extra.get('sumiu'):
        # só cancela o que já estava pronto (ou parado há muito tempo): durante a produção o corte ainda não está salvo
        # corte ainda não salvo pelo Agente 1 (acabou de ser aprovado): espera; só cancela se continuar sem existir por 6 h
        parado = _agora() - float(v['atualizado'] or 0) > 6 * 3600
        if ets['a2_publicacao']['estado'] not in OK and (parado or (not extra.get('nao_salvo') and ets['a4_final']['estado'] in OK)):
            cancelar(vid, MOTIVO_SUMIU)
        return v
    import pipeline as pl
    cert = pl.certificado(sha) if sha else None
    if cert and ets['a4_final']['estado'] not in OK and ets['a4_final']['estado'] not in ATIVOS:
        # aprovado fora do laço automático (você liberou a revisão manual / editor supervisionado): adota o certificado deste arquivo
        for et in ('producao', 'a4_previo', 'a5_edicao', 'a4_final'):
            x = ets[et]
            if x['estado'] in OK:
                continue
            if et in ('producao', 'a4_previo'):
                marcar(vid, et, 'pulada_justificada', motivo='Etapa resolvida antes: o arquivo final já tem o certificado do diretor.')
            else:
                marcar(vid, et, 'concluida', recibo={'certificado': cert['id'], 'nota': cert['nota'], 'sha': sha, 'manual': bool(cert.get('manual')),
                                                     'por': cert.get('por') or '', 'adotado': 'certificado do arquivo atual'}, saida_sha=sha,
                       executor='revisão manual' if cert.get('manual') else 'certificado existente')
        ets = {e: _etapa(vid, e) for e in ORDEM}
    # arquivo mudou depois da aprovação do diretor: o que vem depois cai (o editor/diretor marcam a versão nova quando trabalharem)
    f = ets['a4_final']
    if f['estado'] == 'concluida' and sha and f['saida_sha'] and f['saida_sha'] != sha:
        if pl.certificado(sha):
            marcar(vid, 'a4_final', 'concluida', recibo={'certificado': pl.certificado(sha)['id'], 'sha': sha, 'nota': pl.certificado(sha)['nota'],
                                                          'adotado': 'certificado da versão atual'}, saida_sha=sha)
        else:
            marcar(vid, 'a4_final', 'aguardando_dependencia', motivo='O arquivo mudou depois da aprovação: o diretor precisa conferir a versão nova.')
        invalidar_depois(vid, 'a4_final', 'O vídeo mudou: capa e liberação valem só para a versão aprovada.')
        ets = {e: _etapa(vid, e) for e in ORDEM}
    if ets['a4_final']['estado'] != 'concluida' or not sha:
        return v
    c6 = ets['a6_capa']
    if c6['estado'] == 'concluida' and c6['entrada_sha'] and c6['entrada_sha'] != sha:
        # o editor trocou o arquivo (ex.: legenda mudou de lugar) e o diretor já aprovou a versão nova: capa e liberação são refeitas
        invalidar_depois(vid, 'a4_final', 'O vídeo mudou: capa e liberação valem só para a versão aprovada.')
        ets = {e: _etapa(vid, e) for e in ORDEM}
    if ets['a6_capa']['estado'] not in OK:
        _a6(v, ets['a6_capa'], sha)
        ets['a6_capa'] = _etapa(vid, 'a6_capa')
    if ets['a6_capa']['estado'] not in OK:
        return v
    reaberta = False
    if ets['a7_liberacao']['estado'] == 'concluida' and not _liberacao_vale(sha):
        # a liberação caiu depois (capa trocada/apagada ou pacote revogado): sem isto o post ficava esperando para sempre
        import thumbnails as th
        sem_capa = politica()['capa_obrigatoria'] and th.capa_para_video(arq) is None
        invalidar_depois(vid, 'a4_final' if sem_capa else 'a6_capa',
                         'A liberação do Coordenador caiu (capa ou pacote mudou): ' + ('a capa é refeita e o pacote é conferido de novo.' if sem_capa
                                                                                       else 'o pacote é conferido e liberado de novo.'))
        ets = {e: _etapa(vid, e) for e in ORDEM}
        reaberta = True
        if ets['a6_capa']['estado'] not in OK:
            _a6(v, ets['a6_capa'], sha)
            ets['a6_capa'] = _etapa(vid, 'a6_capa')
            if ets['a6_capa']['estado'] not in OK:
                return v
    if ets['a7_liberacao']['estado'] != 'concluida':
        _a7(v, ets, arq, sha, extra, sem_ordem=reaberta)
        ets['a7_liberacao'] = _etapa(vid, 'a7_liberacao')
    if ets['a7_liberacao']['estado'] != 'concluida':
        return v
    _a2(v, ets, sha, extra, posts)
    return db.um('SELECT * FROM esteira_videos WHERE id=?', vid)


def _a6(v: dict, e: dict, sha: str):
    import thumbnails as th
    pol = politica()
    origem = 'render' if v['origem'] == 'render' else 'corte'
    j = db.um('SELECT * FROM thumbnail_jobs WHERE origem=? AND referencia=? AND video_sha=? ORDER BY criado DESC LIMIT 1', origem, v['ref'], sha)
    if not j:
        if not pol['capa_obrigatoria']:
            marcar(v['id'], 'a6_capa', 'pulada_justificada', motivo='Política sem capa obrigatória.', recibo={'politica': pol['versao']})
            return
        if _ordem_cuida(v, 'a6.capas'):
            if e['estado'] != 'aguardando_dependencia':
                marcar(v['id'], 'a6_capa', 'pendente', motivo='O Coordenador pede as capas pela ordem.')
            return
        if not th.PIL_OK:
            marcar(v['id'], 'a6_capa', 'aguardando_recurso', motivo=th.SEM_PIL)
            return
        cfg = th.config()
        try:
            j0 = th.criar({'origem': origem, 'referencia': v['ref'], 'metodo': 'inteligente', 'variantes': cfg['variantes_padrao'], 'formato': 'auto',
                           'texto_modo': 'auto', 'chave_idempotencia': f'esteira:{v["id"]}:{sha[:16]}', 'reaproveitar': True}, 'agente7-esteira')
        except th.ErroThumb as err:
            marcar(v['id'], 'a6_capa', 'falhou', erro=str(err))
            return
        marcar(v['id'], 'a6_capa', 'na_fila', recibo={'job': j0['id']}, entrada_sha=sha, executor='thumbnails.job_thumbnail')
        return
    est = j['estado']
    rec = {'job': j['id']}
    if est in ('analisando', 'criando', 'validando'):
        if e['estado'] not in ATIVOS:
            marcar(v['id'], 'a6_capa', 'executando', recibo=rec, entrada_sha=sha, executor='thumbnails.job_thumbnail')
        return
    if est in ('na_fila', 'aguardando_video'):
        if e['estado'] != 'na_fila':
            marcar(v['id'], 'a6_capa', 'na_fila', recibo=rec, entrada_sha=sha, motivo=j.get('erro') or '')
        return
    s = th.revalidar(j['id']) if est in ('pronto', 'aguardando_escolha') else None
    if not s and est in ('pronto', 'aguardando_escolha', 'revisao_manual') and th.config()['modo'] == 'automatico':
        s = th.selecionar_melhor(j['id'], 'agente6-automatico') and th.revalidar(j['id'])   # automático: escolhe a aprovada de maior nota
    if s and s.get('aprovado') in (1, True, None):
        n_var = db.um("SELECT COUNT(*) n FROM thumbnail_variantes WHERE job=? AND estado<>'substituida'", j['id'])['n']
        ini, fim = j.get('criado'), j.get('atualizado')
        marcar(v['id'], 'a6_capa', 'concluida', recibo={**rec, 'variante': s['variante'], 'capa_sha': s['thumb_sha'], 'escolha': s['escolha'], 'variantes': n_var},
               saida_sha=s['thumb_sha'], entrada_sha=sha, executor='thumbnails.job_thumbnail',
               inicio=ini if e['estado'] not in ATIVOS else None, fim=fim if e['estado'] not in ATIVOS else None)
        return
    if est in ('pronto', 'aguardando_escolha'):
        if e['estado'] != 'aguardando_usuario':
            marcar(v['id'], 'a6_capa', 'aguardando_usuario', recibo=rec, motivo='Capas prontas: escolha uma (Capas ou Coordenador > Aprovações).')
        return
    if est == 'revisao_manual':
        if e['estado'] != 'revisao_manual':
            marcar(v['id'], 'a6_capa', 'revisao_manual', recibo=rec, motivo=j.get('erro') or 'Nenhuma capa passou depois das correções.')
        return
    if est in ('falhou', 'cancelado') and e['estado'] != 'falhou':
        marcar(v['id'], 'a6_capa', 'falhou', recibo=rec, erro=j.get('erro') or est)


def revisar_pacote(v: dict, arq: Path, sha: str, extra: dict) -> dict:
    """Agente 7: confere o pacote real de ponta a ponta (certificado do diretor para ESTE arquivo, capa presa a ele, direitos,
    título e descrição com o link original nos cortes). Devolve os itens e o hash do pacote (vídeo + capa + metadados)."""
    import pipeline as pl
    import thumbnails as th
    itens = []

    def item(nome, ok, detalhe):
        itens.append({'item': nome, 'ok': bool(ok), 'detalhe': detalhe})
    cert = pl.certificado(sha)
    item('diretor', cert is not None, ('Arquivo aceito em revisão manual.' if cert['manual'] else f'Diretor aprovou este arquivo (nota {cert["nota"]}).') if cert else 'Falta o certificado do diretor para este arquivo.')
    pre = _etapa(v['id'], 'a4_previo')
    item('avaliacao_inicial', pre and pre['estado'] in OK, 'Avaliação inicial do diretor feita.' if pre and pre['estado'] == 'concluida' else
         (pre['motivo'] or 'Não se aplica.') if pre and pre['estado'] == 'pulada_justificada' else 'Falta a avaliação inicial do diretor.')
    capa = th.capa_para_video(arq)
    if politica()['capa_obrigatoria']:
        item('capa', capa is not None, 'Capa aprovada e presa a este vídeo.' if capa else 'Falta a capa escolhida para este vídeo.')
    titulo, legenda = '', ''
    if v['origem'] == 'corte':
        import agente as ag
        c = extra.get('corte') or {}
        titulo = c.get('titulo') or ''
        legenda = ag.legenda_do_corte(c)
        conf = ag.conferir(c)
        item('direitos', not conf['bloqueios'], 'Origem do vídeo registrada.' if not conf['bloqueios'] else ' '.join(conf['bloqueios'])[:300])
        link = ag.link_original(c)
        item('link_original', bool(link) and link in legenda, 'Descrição com o link do vídeo original.' if link else
             'Não sei de qual vídeo este corte saiu: a descrição iria sem o link original.')
        # pedido do Raniere (19/11): o vídeo já tinha texto/legenda? a nossa legenda não pode ficar em cima dele
        import texto_tela as tt
        plano = pl.ultimo_plano(c['esteira']) if c.get('esteira') else None
        lg = tt.item_do_pacote(c, sha, plano)
        itens.append({'item': 'legenda_sobreposta', 'ok': bool(lg['ok']), 'detalhe': lg['detalhe'], 'estado': lg['estado'],
                      **({'nova_posicao': lg['nova_posicao']} if lg.get('nova_posicao') else {}),
                      **({'textos': (lg.get('resultado') or {}).get('textos', [])[:6]} if lg.get('resultado') else {})})
    else:
        p = extra.get('projeto') or {}
        rot = (p.get('dados') or {}).get('roteiro') or {}
        titulo = rot.get('titulo') or p.get('titulo') or ''
        try:
            import aprovacoes as apv
            legenda = apv.descricao(p, {}) if hasattr(apv, 'descricao') else ''
        except Exception:  # noqa: BLE001
            legenda = ''
        item('direitos', not _sem_licenca(p), 'Imagens com licença registrada.' if not _sem_licenca(p) else 'Há imagem sem licença registrada.')
    item('titulo', bool(titulo.strip()), 'Título preenchido.' if titulo.strip() else 'Falta o título.')
    meta = hashlib.sha256(_j([titulo, legenda]).encode()).hexdigest()
    h = hashlib.sha256(_j([sha, capa['sha'] if capa else '', meta]).encode()).hexdigest()
    return {'ok': all(i['ok'] for i in itens), 'itens': itens, 'pacote_hash': h, 'video_sha': sha, 'thumb_sha': capa['sha'] if capa else '',
            'thumb_job': capa['job'] if capa else '', 'variante': capa['variante'] if capa else '', 'metadados_sha': meta, 'titulo': titulo}


def _sem_licenca(p: dict) -> list:
    try:
        import produtor
        return produtor._sem_licenca((p.get('dados') or {}).get('cenas') or [])
    except Exception:  # noqa: BLE001
        return []


def _liberacao_vale(sha: str) -> bool:
    try:
        import coordenador as co
        return bool(co.liberado_sha(sha)['ok'])
    except Exception as e:  # noqa: BLE001  (sem conseguir conferir, não reabre nada)
        print('esteira: conferir liberação', e)
        return True


def _a7(v: dict, ets: dict, arq: Path, sha: str, extra: dict, sem_ordem: bool = False):
    """sem_ordem: a liberação caiu depois que a ordem do Coordenador já tinha terminado: a esteira refaz o pacote sozinha."""
    import coordenador as co
    e = ets['a7_liberacao']
    a = db.um('SELECT * FROM coordenador_aprovacoes WHERE referencia=? AND video_sha256=? AND revogado IS NULL ORDER BY criado DESC LIMIT 1', v['ref'], sha)
    if not a:
        if not sem_ordem and _ordem_cuida(v, 'a7.liberar') and not _ordem_ja_liberou(v):
            if e['estado'] != 'pendente':
                marcar(v['id'], 'a7_liberacao', 'pendente', motivo='O Coordenador libera pela ordem.')
            return
        a = co.criar_pacote(v, arq, sha, revisar_pacote(v, arq, sha, extra))
        marcar(v['id'], 'a7_liberacao', 'executando', recibo={'aprovacao': a['id']}, entrada_sha=sha, executor='coordenador.revisar_pacote')
    else:
        if not a['ordem_id']:
            co.atualizar_pacote(a['id'], revisar_pacote(v, arq, sha, extra))
            a = db.um('SELECT * FROM coordenador_aprovacoes WHERE id=?', a['id'])
    rel = _l(a['relatorio'], {}) or {}
    if a['decisao'] == 'aprovado':
        if co._revalidar(a['id']):
            marcar(v['id'], 'a7_liberacao', 'concluida', recibo={'aprovacao': a['id'], 'pacote_hash': a['pacote_hash'], 'por': a['por'],
                                                                 'thumb_sha': a['thumbnail_sha256']}, saida_sha=a['pacote_hash'], entrada_sha=sha,
                   executor='coordenador')
        return
    if a['decisao'] == 'reprovado':
        if e['estado'] != 'reprovada':
            marcar(v['id'], 'a7_liberacao', 'reprovada', recibo={'aprovacao': a['id']}, motivo=a['motivo'] or 'Reprovado no Coordenador.')
        return
    if _legenda_de_volta(v, a, rel):
        return
    falta = [i['detalhe'] for i in rel.get('itens') or [] if not i['ok']]
    if falta:
        if e['motivo'] != ' '.join(falta)[:500] or e['estado'] != 'aguardando_dependencia':
            marcar(v['id'], 'a7_liberacao', 'aguardando_dependencia' if 'capa' not in ' '.join(falta).lower() else 'aguardando_usuario',
                   recibo={'aprovacao': a['id']}, motivo=' '.join(falta))
        return
    if politica().get('liberacao_automatica') or co.config()['modo'] == 'automatico':
        db.executar("UPDATE coordenador_aprovacoes SET decisao='aprovado', por=?, decidido=? WHERE id=? AND decisao='pendente'",
                    'agente7 (liberação automática: pacote conferido item por item)', _agora(), a['id'])
        co.evento(a['ordem_id'], a['tarefa_id'], 'agente7', 'liberacao', {'aprovacao': a['id'], 'decisao': 'aprovado', 'automatico': True, 'video': v['id']})
        return _a7(v, {**ets, 'a7_liberacao': _etapa(v['id'], 'a7_liberacao')}, arq, sha, extra)
    if e['estado'] != 'aguardando_usuario':
        marcar(v['id'], 'a7_liberacao', 'aguardando_usuario', recibo={'aprovacao': a['id']},
               motivo='Pacote conferido: falta você liberar em Coordenador > Aprovações (ou ligue o modo automático).')
        co.avisar_pacote(a)


def _legenda_de_volta(v: dict, a: dict, rel: dict) -> bool:
    """Coordenador viu a nossa legenda em cima de texto do vídeo original: manda o corte de volta para o editor (Agente 5)
    mudar a legenda de lugar. O diretor confere de novo; capa e liberação são refeitas para o arquivo novo. Até 5 voltas."""
    if v['origem'] != 'corte':
        return False
    lg = next((i for i in rel.get('itens') or [] if i.get('item') == 'legenda_sobreposta'), None)
    if not lg or lg['ok']:
        if lg and lg.get('estado') in ('ok', 'nao_se_aplica'):
            try:
                import agente as ag
                ag.apagar_bruto(v['ref'])          # conferido: o trecho guardado não é mais preciso
            except Exception as e:  # noqa: BLE001
                print('esteira: trecho guardado não apagado:', e)
        return False
    if lg.get('estado') != 'sobreposta' or not lg.get('nova_posicao'):
        return False                               # ainda conferindo, ou sem lugar livre: fica para você (aguardando_usuario)
    import agente as ag
    import coordenador as co
    c = next((x for x in ag.estado()['cortes'] if x['id'] == v['ref']), None) or {}
    limite = co.config()['correcoes_por_etapa']
    if ag.legenda_na_fila(v['ref']):
        return True
    if int(c.get('voltas_legenda') or 0) >= limite:
        lg['detalhe'] += f' Já foram {limite} voltas ao editor por causa da legenda: precisa da sua decisão.'
        return False
    if not ag.pode_mover_legenda(v['ref']):
        lg['detalhe'] += ' O trecho original não está mais guardado: o editor não consegue montar de novo sozinho.'
        return False
    try:
        r = ag.mover_legenda(v['ref'], lg['nova_posicao'], lg['detalhe'][:200])
    except ag.ErroAgente as e:
        lg['detalhe'] += ' ' + str(e)
        return False
    db.executar('UPDATE coordenador_aprovacoes SET revogado=?, motivo=? WHERE id=? AND revogado IS NULL', _agora(),
                'Legenda em cima de texto do vídeo: voltou para o editor.', a['id'])
    co.evento(a['ordem_id'], a['tarefa_id'], 'agente7', 'correcao', {'aprovacao': a['id'], 'alvo': 'legenda', 'para': lg['nova_posicao'],
                                                                     'job': r.get('job'), 'video': v['id']})
    marcar(v['id'], 'a7_liberacao', 'reprovada', recibo={'aprovacao': a['id'], 'item': 'legenda_sobreposta', 'textos': lg.get('textos', [])},
           motivo=lg['detalhe'][:400])
    marcar(v['id'], 'a5_edicao', 'corrigindo', motivo=f'Coordenador pediu: legenda para {lg["nova_posicao"]} (volta {r.get("volta", 1)} de {limite}).',
           recibo={'job': r.get('job'), 'posicao': lg['nova_posicao']})
    return True


def _a2(v: dict, ets: dict, sha: str, extra: dict, posts: list | None):
    import postagem as pg
    posts = posts if posts is not None else pg.posts()
    if v['origem'] == 'corte':
        c = extra.get('corte') or {}
        meus = [p for p in posts if p['video'] == c.get('video')]
    else:
        meus = [p for p in posts if p.get('projeto') == v['ref'] and (not p.get('render_sha') or p.get('render_sha') == sha)]
    meus = [p for p in meus if any(r['status'] != 'cancelado' for r in p['redes'].values())]
    ag_e, pub_e = ets['a2_agendamento'], ets['a2_publicacao']
    if not meus:
        if ag_e['estado'] not in ('na_fila',) or ag_e['motivo'] is None:
            marcar(v['id'], 'a2_agendamento', 'na_fila', motivo='Liberado: esperando o próximo horário livre do Publicador.')
        return
    if ag_e['estado'] != 'concluida' or set((ag_e['recibo'] or {}).get('posts') or []) != {p['id'] for p in meus}:
        cri = min(p['criado'] for p in meus)
        lib = _etapa(v['id'], 'a7_liberacao')['fim'] or cri
        marcar(v['id'], 'a2_agendamento', 'concluida', recibo={'posts': [p['id'] for p in meus], 'quando': min(p['quando'] for p in meus),
                                                              'redes': sorted({r for p in meus for r in p['redes']})},
               inicio=min(lib, cri), fim=cri, executor='agente2', segundos_fila=max(0.0, cri - lib))
    redes = {(p['id'], r): x for p in meus for r, x in p['redes'].items()}
    feitos = {k: x for k, x in redes.items() if x['status'] == 'postado'}
    erros = {k: x for k, x in redes.items() if x['status'] in ('erro', 'liberacao')}
    abertos = {k: x for k, x in redes.items() if x['status'] in ('agendado', 'postando')}
    rec = {'links': {f'{k[1]}': x.get('link') for k, x in feitos.items()}, 'erros': {k[1]: (x.get('erro') or '')[:200] for k, x in erros.items()},
           'manual': [k[1] for k, x in redes.items() if x['status'] == 'manual']}
    if feitos and not abertos and not erros:
        if pub_e['estado'] != 'concluida':
            t = [x.get('feito') or 0 for x in feitos.values()]
            ini = [x.get('inicio') for x in feitos.values() if x.get('inicio')]
            marcar(v['id'], 'a2_publicacao', 'concluida', recibo=rec, executor='agente2', inicio=min(ini) if ini else None, fim=max(t) if t else None)
    elif erros and not abertos:
        if pub_e['estado'] != 'falhou' or (pub_e['recibo'] or {}) != rec:
            marcar(v['id'], 'a2_publicacao', 'falhou', recibo=rec, erro='; '.join(f'{r}: {m}' for r, m in rec['erros'].items())[:400])
    elif any(x['status'] == 'postando' for x in abertos.values()):
        if pub_e['estado'] != 'executando':
            marcar(v['id'], 'a2_publicacao', 'executando', recibo=rec)
    elif pub_e['estado'] not in ('na_fila',):
        marcar(v['id'], 'a2_publicacao', 'na_fila', recibo=rec, motivo='Agendado para ' + time.strftime('%d/%m %H:%M', time.localtime(min(p['quando'] for p in meus))))


def video_do_arquivo(sha: str = '', video: str = '', projeto: str = '') -> dict | None:
    """Registro da esteira de um arquivo (corte pelo id do vídeo no servidor, vídeo próprio pelo projeto)."""
    if video:
        import agente as ag
        c = next((x for x in ag.estado()['cortes'] if x.get('video') == video), None)
        if c:
            return db.um('SELECT * FROM esteira_videos WHERE id=?', vid_de('corte', c['id']))
    if projeto:
        return db.um('SELECT * FROM esteira_videos WHERE id=?', vid_de('render', projeto))
    return None


def falta_para_postar(sha: str, video: str = '', projeto: str = '') -> str:
    """Frase simples do que falta na esteira para este arquivo poder ser postado ('' = nada falta)."""
    import coordenador as co
    if co.liberado_sha(sha)['ok']:
        return ''
    v = video_do_arquivo(sha, video, projeto)
    if not v:
        return ('Este vídeo não passou pela esteira dos 7 agentes (diretor, editor, capa e liberação do Coordenador). '
                'Veja Agentes > Coordenador > Esteira > Recuperar produções.')
    return f'Falta na esteira: {NOMES.get(v["etapa_atual"], v["etapa_atual"])}' + (f' ({v["motivo"]})' if v.get('motivo') else '') + '.'


def liberar_por_pessoa(origem: str, ref: str, quem: str) -> dict:
    """Você aprovou o vídeo (Revisar): vale como liberação final do Agente 7 SE o pacote estiver conferido item por item."""
    import coordenador as co
    vid = vid_de(origem, ref)
    if not db.um('SELECT id FROM esteira_videos WHERE id=?', vid):
        return {'ok': False, 'falta': ['Este vídeo não tem registro na esteira dos 7 agentes.']}
    avancar(vid)
    if _etapa(vid, 'a7_liberacao')['estado'] == 'concluida':
        return {'ok': True}
    v = db.um('SELECT * FROM esteira_videos WHERE id=?', vid)
    arq, sha, extra = arquivo_atual(v)
    if not arq:
        return {'ok': False, 'falta': ['Vídeo sem arquivo final.']}
    if _etapa(vid, 'a4_final')['estado'] != 'concluida':
        return {'ok': False, 'falta': ['O diretor ainda não aprovou este arquivo.']}
    if _etapa(vid, 'a6_capa')['estado'] not in OK:
        e6 = _etapa(vid, 'a6_capa')
        return {'ok': False, 'falta': [e6['motivo'] or 'Falta a capa deste vídeo (Agente 6).']}
    rev = revisar_pacote(v, arq, sha, extra)
    if not rev['ok']:
        return {'ok': False, 'falta': [i['detalhe'] for i in rev['itens'] if not i['ok']]}
    a = co.criar_pacote(v, arq, sha, rev)
    co.atualizar_pacote(a['id'], rev)
    db.executar("UPDATE coordenador_aprovacoes SET decisao='aprovado', por=?, decidido=? WHERE id=? AND decisao='pendente'", f'{quem} (aprovou o vídeo)'[:60], _agora(), a['id'])
    co.evento(None, None, quem, 'liberacao', {'aprovacao': a['id'], 'decisao': 'aprovado', 'video': vid, 'por_aprovacao_do_video': True})
    avancar(vid)
    return {'ok': _etapa(vid, 'a7_liberacao')['estado'] == 'concluida', 'aprovacao': a['id']}


def varrer() -> int:
    """Passa por todos os vídeos que ainda não terminaram (a cada poucos segundos, em segundo plano)."""
    import postagem as pg
    posts = pg.posts()       # mesmo com a política desligada o registro segue (só a postagem deixa de exigir)
    try:
        reabrir_cancelados_por_engano()
    except Exception as e:  # noqa: BLE001
        print('esteira: reabrir cancelados', e)
    n = 0
    for r in db.todos("SELECT id FROM esteira_videos WHERE estado NOT IN ('publicado','cancelado','descartado') ORDER BY atualizado LIMIT 200"):
        try:
            avancar(r['id'], posts)
            n += 1
        except Exception as e:  # noqa: BLE001  (um vídeo com problema não trava os outros)
            print('esteira:', r['id'], e)
    return n


# ---------------------------------------------------------------- leitura
def _etapa_publica(e: dict) -> dict:
    return {'etapa': e['etapa'], 'nome': NOMES[e['etapa']], 'agente': e['agente'], 'estado': e['estado'], 'nome_estado': NOMES_ESTADO.get(e['estado'], e['estado']),
            'inicio': e['inicio'], 'fim': e['fim'], 'segundos_ativos': e['segundos_ativos'], 'segundos_fila': e['segundos_fila'], 'tentativas': e['tentativas'],
            'correcoes': e['correcoes'], 'recibo': e['recibo'], 'entrada_sha': e['entrada_sha'], 'saida_sha': e['saida_sha'], 'erro': e['erro'],
            'motivo': e['motivo'], 'executor': e['executor'], 'atualizado': e['atualizado']}


def obter(vid: str) -> dict:
    v = db.um('SELECT * FROM esteira_videos WHERE id=?', vid)
    if not v:
        raise ErroEsteira('Vídeo não encontrado na esteira.', 404)
    ets = [_etapa(vid, e) for e in ORDEM]
    v['etapas'] = [_etapa_publica(e) for e in ets if e]
    feitas = sum(1 for e in ets if e and e['estado'] in OK)
    v['progresso'] = round(100 * feitas / len(ORDEM))
    v['segundos_total'] = round(sum(e['segundos_ativos'] or 0 for e in ets if e), 1)
    v['politica'] = _l(v['politica'], {})
    return v


def timeline(vid: str) -> dict:
    v = obter(vid)
    v['historico'] = [{**h, 'detalhe': _l(h['detalhe'], {})} for h in db.todos('SELECT * FROM esteira_historico WHERE video=? ORDER BY n', vid)]
    return v


def lista(estado: str = '', limite: int = 50, ordem_id: str = '') -> list:
    sql, a = 'SELECT id FROM esteira_videos WHERE 1=1', []
    if estado:
        sql += ' AND estado=?'
        a.append(estado)
    if ordem_id:
        sql += ' AND ordem_id=?'
        a.append(ordem_id)
    return [obter(r['id']) for r in db.todos(sql + ' ORDER BY atualizado DESC LIMIT ?', *a, max(1, min(200, limite)))]


def resumo() -> dict:
    """Quantos vídeos há em cada etapa (para o Início)."""
    por_estado = {r['estado']: r['n'] for r in db.todos('SELECT estado, COUNT(*) n FROM esteira_videos GROUP BY estado')}
    por_etapa = {r['etapa_atual']: r['n'] for r in db.todos("SELECT etapa_atual, COUNT(*) n FROM esteira_videos WHERE estado NOT IN ('publicado','cancelado','descartado') "
                                                           'GROUP BY etapa_atual')}
    return {'por_estado': por_estado, 'por_etapa': por_etapa, 'nomes_etapa': NOMES}


def metricas_agente(agente: str, desde: float) -> dict:
    """Conta só o que o registro prova (etapa concluída com recibo), com o tempo medido."""
    rs = db.todos('SELECT etapa, estado, segundos_ativos, fim FROM esteira_etapas WHERE agente=? AND fim>=?', agente, desde)
    feitas = [r for r in rs if r['estado'] == 'concluida']
    tempos = [r['segundos_ativos'] for r in feitas if r['segundos_ativos']]
    por_etapa = {}
    for r in feitas:
        por_etapa[r['etapa']] = por_etapa.get(r['etapa'], 0) + 1
    return {'concluidas': len(feitas), 'falhas': sum(1 for r in rs if r['estado'] in RUINS), 'por_etapa': por_etapa,
            'tempo_medio_s': round(sum(tempos) / len(tempos), 1) if tempos else None, 'amostras': len(tempos)}


def situacao_agente(agente: str) -> dict:
    """Estado real de um agente pela esteira: trabalhando, na fila, esperando você, bloqueado, esperando etapa anterior ou sem demanda."""
    rs = db.todos("SELECT e.etapa, e.estado, e.motivo, e.erro, e.video, e.inicio, v.titulo FROM esteira_etapas e JOIN esteira_videos v ON v.id=e.video "
                  "WHERE e.agente=? AND v.estado NOT IN ('publicado','cancelado','descartado')", agente)
    cont = {}
    for r in rs:
        cont[r['estado']] = cont.get(r['estado'], 0) + 1
    ativo = [r for r in rs if r['estado'] in ATIVOS]
    if ativo:
        est = 'ativo'
    elif cont.get('na_fila'):
        est = 'na_fila'
    elif cont.get('aguardando_usuario') or cont.get('revisao_manual'):
        est = 'aguardando_voce'
    elif cont.get('aguardando_recurso') or cont.get('falhou'):
        est = 'bloqueado'
    elif cont.get('pendente') or cont.get('aguardando_dependencia'):
        est = 'aguardando_etapa'
    else:
        est = 'sem_demanda'
    exemplo = (ativo or [r for r in rs if r['estado'] in ('aguardando_usuario', 'revisao_manual', 'aguardando_recurso', 'falhou')] or [None])[0]
    return {'estado': est, 'contagem': cont, 'agora': [{'video': r['video'], 'titulo': r['titulo'], 'etapa': NOMES[r['etapa']], 'desde': r['inicio']} for r in ativo][:3],
            'motivo': (exemplo['motivo'] or exemplo['erro'] or '') if exemplo else ''}


# ---------------------------------------------------------------- diagnóstico e recuperação
def diagnostico() -> dict:
    import pipeline as pl
    out = {'politica': politica(), 'esteira_ligada': pl.ligado(), 'capacidades': {}, 'producoes': []}
    try:
        import coordenador as co
        out['coordenador'] = {k: co.config()[k] for k in ('modo', 'exigir_liberacao')}
        out['coordenador']['liberacao_efetiva'] = co.exigir_liberacao_efetiva()
    except Exception as e:  # noqa: BLE001
        out['coordenador'] = {'erro': str(e)[:120]}
    try:
        import orquestrador as oq
        out['central'] = oq.config()['estado']
    except Exception:  # noqa: BLE001
        out['central'] = None
    try:
        import thumbnails as th
        out['capacidades'] = th.capacidades()
        out['agente6'] = {k: th.config()[k] for k in ('modo', 'criar_sozinho')}
    except Exception as e:  # noqa: BLE001
        out['capacidades'] = {'erro': str(e)[:120]}
    out['resumo'] = resumo()
    out['incompletos'] = simular_conciliacao()['itens']
    return out


def _candidatos() -> list:
    """Vídeos ainda não publicados, com arquivo de verdade: cortes prontos/agendados e vídeos do Agente 3 com versão final."""
    import agente as ag
    import postagem as pg
    out = []
    for c in ag.estado()['cortes']:
        if c.get('status') not in ('pronto', 'agendado') or not c.get('video'):
            continue
        try:
            pg.video_path(c['video'])
        except pg.ErroRede:
            continue
        out.append(('corte', c['id'], c.get('titulo') or 'Corte'))
    for p in db.todos("SELECT id, titulo FROM projetos WHERE tipo='agente3' AND apagado=0 AND status IN ('ready_for_review','approved','scheduled')"):
        out.append(('render', p['id'], p['titulo'] or 'Vídeo'))
    return out


def _primeira_falta(origem: str, ref: str) -> dict:
    """Primeira etapa que falta para este vídeo e o que a recuperação faria (sem mexer em nada)."""
    import pipeline as pl
    import postagem as pg
    vid = vid_de(origem, ref)
    v = db.um('SELECT * FROM esteira_videos WHERE id=?', vid) or {'id': vid, 'origem': 'render' if origem == 'render' else 'corte', 'ref': ref}
    arq, sha, extra = arquivo_atual(v)
    if not arq or not sha:
        return {'falta': 'producao', 'acao': None, 'motivo': 'Sem arquivo final: não dá para recuperar com segurança.'}
    postado = False
    if origem == 'corte':
        c = extra.get('corte') or {}
        p = next((x for x in pg.posts() if x['id'] == c.get('post')), None)
        postado = bool(p and any(r['status'] == 'postado' for r in p['redes'].values()))
    if postado:
        return {'falta': None, 'acao': None, 'motivo': 'Já foi postado: não mexo.'}
    if not pl.certificado(sha):
        if origem == 'corte':
            return {'falta': 'a4_final', 'acao': 'editor_diretor', 'motivo': 'Sem certificado do diretor para o arquivo atual: vai para o editor e o diretor.'}
        return {'falta': 'a4_final', 'acao': None, 'motivo': 'Vídeo do Agente 3 sem certificado: mande produzir de novo pela tela do vídeo.'}
    import thumbnails as th
    if politica()['capa_obrigatoria'] and not th.capa_para_video(arq):
        return {'falta': 'a6_capa', 'acao': 'registrar', 'motivo': 'Falta a capa: o Agente 6 faz e a esteira segue.'}
    import coordenador as co
    if not co.liberado(arq)['ok']:
        return {'falta': 'a7_liberacao', 'acao': 'registrar', 'motivo': 'Falta a liberação final do Coordenador.'}
    return {'falta': 'a2_agendamento', 'acao': 'registrar', 'motivo': 'Pacote completo: só falta o Publicador agendar.'}


def simular_conciliacao() -> dict:
    itens = []
    for origem, ref, titulo in _candidatos():
        vid = vid_de(origem, ref)
        v = db.um('SELECT estado, etapa_atual FROM esteira_videos WHERE id=?', vid)
        f = _primeira_falta(origem, ref)
        if f['falta'] is None:
            continue
        itens.append({'video': vid, 'origem': origem, 'ref': ref, 'titulo': titulo, 'registrado': bool(v), 'estado': (v or {}).get('estado') or 'incompleto',
                      **f})
    return {'itens': itens, 'total': len(itens), 'nota': 'Simulação: nada foi mudado. Vídeos já postados e cancelados ficam de fora.'}


def conciliar(videos: list | None = None, quem: str = 'site') -> dict:
    """Recuperação com a sua confirmação: põe na esteira os vídeos incompletos e pede SÓ a etapa que falta. Idempotente."""
    import agente as ag
    import pipeline as pl
    feitos = []
    alvo = set(videos or [])
    for it in simular_conciliacao()['itens']:
        if alvo and it['video'] not in alvo:
            continue
        if not it['acao']:
            feitos.append({**it, 'feito': 'nada (precisa de você)'})
            continue
        vid = garantir(it['origem'], it['ref'], it['titulo'])
        e = _etapa(vid, 'producao')
        if e['estado'] not in OK:
            marcar(vid, 'producao', 'concluida', recibo={'recuperado': True, 'ref': it['ref'], 'origem': it['origem']}, motivo='Produção anterior à esteira completa.',
                   executor='recuperação')
        pre = _etapa(vid, 'a4_previo')
        if pre['estado'] not in OK:
            marcar(vid, 'a4_previo', 'pulada_justificada', motivo='Vídeo feito antes da avaliação inicial existir: o diretor confere o arquivo final.')
        _arq, sha, _x = arquivo_atual(db.um('SELECT * FROM esteira_videos WHERE id=?', vid))
        if it['acao'] == 'editor_diretor':
            try:
                r = ag.mandar_para_editor(it['ref'], 'recuperação')
                marcar(vid, 'a5_edicao', 'na_fila', recibo={'job': r.get('job')}, motivo='Recuperação: editor e diretor vão conferir o arquivo.')
                feitos.append({**it, 'feito': 'mandado ao editor e ao diretor', 'job': r.get('job')})
            except ag.ErroAgente as e:
                feitos.append({**it, 'feito': 'não deu: ' + str(e)[:200]})
            continue
        c = pl.certificado(sha)
        if c:
            for et in ('a5_edicao', 'a4_final'):
                x = _etapa(vid, et)
                if x['estado'] not in OK:
                    marcar(vid, et, 'concluida', recibo={'certificado': c['id'], 'sha': sha, 'nota': c['nota'], 'recuperado': True}, saida_sha=sha,
                           executor='certificado existente')
        avancar(vid)
        feitos.append({**it, 'feito': 'registrado; a esteira segue a partir de ' + NOMES.get(it['falta'], it['falta'])})
    db.evento(quem, 'esteira_conciliacao', 'esteira', {'n': len(feitos)})
    return {'feitos': feitos, 'total': len(feitos)}
