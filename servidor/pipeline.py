"""Esteira dos 5 agentes: estados, contadores, política 70/5 e certificado do diretor preso ao arquivo exportado.

  Agente 1 (cortes) / corte manual / vídeo importado -> Agente 5 (editor) -> Agente 4 (diretor, final_release) -> Agente 2
  Agente 3 (criação) -> Agente 4 (creative_preedit) -> Agente 5 -> Agente 4 (final_release) -> Agente 2

Regras fixas (VERSAO_POLITICA):
- aprova com nota >= 70 e nenhum bloqueio; nota alta nunca passa por cima de bloqueio;
- a 1ª avaliação não conta; cada reenvio corrigido conta 1; depois da 5ª correção reprovada -> manual_review_required;
- contadores separados por etapa (creative_preedit e final_release) e separados das tentativas técnicas da fila;
- correção que não muda nada (mesmo plano e mesmo arquivo) não se repete: vai para revisão manual;
- revisão manual não passa por cima de direitos, arquivo quebrado nem segurança;
- certificado assinado pelo servidor vale só para o SHA-256 daquele arquivo; arquivo novo = certificado inválido.
- A esteira só manda na postagem quando está LIGADA (Agentes > Esteira, ou PIPELINE_V2=1). Desligada, tudo segue como antes.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from pathlib import Path

import banco as db
import contratos as ct


class ErroPipeline(Exception):
    def __init__(self, msg: str, status: int = 400):
        super().__init__(msg)
        self.status = status


# ---------------------------------------------------------------- liga/desliga (rollback sem perder dados)
def ligado() -> bool:
    try:
        import esteira as es
        completa = es.completa()       # esteira obrigatória dos 7 agentes: editor e diretor sempre ligados
    except Exception:  # noqa: BLE001
        completa = False
    if completa:
        return True
    v = db.kv('pipeline_v2')
    if isinstance(v, dict) and 'ligado' in v:
        return bool(v['ligado'])
    return os.getenv('PIPELINE_V2', '0') in ('1', 'true', 'sim')


def ligar(on: bool, quem: str = 'site') -> dict:
    db.kv_gravar('pipeline_v2', {'ligado': bool(on), 't': time.time(), 'por': quem})
    db.evento(quem, 'pipeline_ligado' if on else 'pipeline_desligado', 'pipeline')
    return {'ligado': ligado()}


# ---------------------------------------------------------------- execuções e etapas
def _run(rid: str) -> dict:
    r = db.um('SELECT * FROM pipeline_runs WHERE id=?', rid)
    if not r:
        raise ErroPipeline('Execução da esteira não encontrada.', 404)
    r['dados'] = json.loads(r['dados'] or '{}')
    return r


def obter(rid: str) -> dict:
    r = _run(rid)
    r['etapas'] = {s['modalidade']: s for s in db.todos('SELECT * FROM pipeline_stages WHERE run=?', rid)}
    for s in r['etapas'].values():
        s['ultimo_relatorio'] = json.loads(s['ultimo_relatorio']) if s.get('ultimo_relatorio') else None
    r['nome_estado'] = ct.NOMES_ESTADO.get(r['estado'], r['estado'])
    r['relatorios'] = [relatorio(x['id']) for x in db.todos('SELECT id FROM quality_reports WHERE run=? ORDER BY criado', rid)]
    r['planos'] = db.todos('SELECT versao, hash, motivo, arquivo_sha, criado FROM edit_plans WHERE run=? ORDER BY versao', rid)
    return r


def criar(origem: str, ref: str, titulo: str = '', chave: str = '', estado: str = 'source_registered', dados: dict | None = None) -> dict:
    if origem not in ('corte', 'manual', 'importado', 'agente3', 'post'):
        raise ErroPipeline('Origem desconhecida.')
    chave = chave or f'{origem}:{ref}'
    ja = db.um('SELECT id FROM pipeline_runs WHERE chave=?', chave)
    if ja:
        return obter(ja['id'])
    rid = uuid.uuid4().hex[:12]
    agora = time.time()
    db.executar('INSERT INTO pipeline_runs (id, origem, ref, titulo, estado, etapa, agente, dados, criado, atualizado, chave) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                rid, origem, ref, titulo[:160], estado, '', 'agent1' if origem == 'corte' else 'agent3' if origem == 'agente3' else 'agent5',
                json.dumps(dados or {}, ensure_ascii=False), agora, agora, chave)
    db.evento('pipeline', 'run_criado', 'run:' + rid, {'origem': origem, 'ref': ref})
    return obter(rid)


def mover(rid: str, estado: str, *, agente: str = '', etapa: str = '', arquivo: str | None = None, sha: str | None = None, dados: dict | None = None):
    if estado not in ct.ESTADOS:
        raise ErroPipeline('Estado desconhecido: ' + estado)
    r = _run(rid)
    novos = dict(r['dados'], **(dados or {}))
    db.executar('UPDATE pipeline_runs SET estado=?, agente=COALESCE(NULLIF(?, \'\'), agente), etapa=?, arquivo=COALESCE(?, arquivo), sha256=COALESCE(?, sha256), '
                'dados=?, atualizado=? WHERE id=?', estado, agente, etapa[:200], arquivo, sha, json.dumps(novos, ensure_ascii=False), time.time(), rid)
    db.evento('pipeline', 'estado', 'run:' + rid, {'estado': estado, 'agente': agente, 'etapa': etapa[:120]})


def etapa(rid: str, modalidade: str) -> dict:
    if modalidade not in ct.MODALIDADES:
        raise ErroPipeline('Modalidade desconhecida.')
    s = db.um('SELECT * FROM pipeline_stages WHERE run=? AND modalidade=?', rid, modalidade)
    if not s:
        db.executar('INSERT OR IGNORE INTO pipeline_stages (id, run, modalidade, avaliacoes, correcoes, limite, estado, atualizado) VALUES (?,?,?,?,?,?,?,?)',
                    uuid.uuid4().hex[:12], rid, modalidade, 0, 0, ct.MAX_CORRECOES, 'pendente', time.time())
        s = db.um('SELECT * FROM pipeline_stages WHERE run=? AND modalidade=?', rid, modalidade)
    return s


def registrar_avaliacao(rid: str, modalidade: str, rel: dict, *, mudou: bool = True, continuo: bool = False) -> dict:
    """Aplica a política a um relatório do diretor e devolve a decisão:
    {'decisao': 'aprovado'|'corrigir'|'revisao_manual', 'tentativa', 'restam', 'motivo'}.
    `mudou` = o reenvio trouxe plano/arquivo diferente do anterior (se não, não adianta repetir)."""
    s = etapa(rid, modalidade)
    if s['estado'] in ('aprovado', 'revisao_manual'):
        raise ErroPipeline(f'Esta etapa já terminou ({s["estado"]}).', 409)
    avaliacoes = s['avaliacoes'] + 1
    correcoes = max(0, avaliacoes - 1)            # a 1ª avaliação não consome correção
    aprovado = ct.decidir(rel['score'], rel['blocking_findings'])
    if aprovado:
        dec, est = 'aprovado', 'aprovado'
        motivo = f'Nota {rel["score"]} sem bloqueios.'
    elif not continuo and avaliacoes > 1 and not mudou:
        dec, est = 'revisao_manual', 'revisao_manual'
        motivo = 'A correção não mudou nada no vídeo (mesmo plano e mesmo arquivo): não adianta repetir.'
    elif not continuo and correcoes >= s['limite']:
        dec, est = 'revisao_manual', 'revisao_manual'
        motivo = f'Reprovado depois de {correcoes} correções (limite {s["limite"]}).'
    else:
        dec, est = 'corrigir', 'corrigindo'
        motivo = f'Nota {rel["score"]}' + (f' e {len(rel["blocking_findings"])} bloqueio(s)' if rel['blocking_findings'] else '') + '.'
    db.executar('UPDATE pipeline_stages SET avaliacoes=?, correcoes=?, estado=?, ultimo_relatorio=?, atualizado=? WHERE id=?',
                avaliacoes, correcoes, est, json.dumps({'id': rel.get('id'), 'score': rel['score'], 'passed': aprovado}), time.time(), s['id'])
    return {'decisao': dec, 'avaliacao': avaliacoes, 'correcoes_usadas': correcoes, 'restam': max(0, s['limite'] - correcoes), 'motivo': motivo}


# ---------------------------------------------------------------- relatórios do diretor
def guardar_relatorio(rid: str | None, modalidade: str, ref: str, sha: str, rel: dict) -> dict:
    qid = uuid.uuid4().hex[:12]
    db.executar('INSERT INTO quality_reports (id, run, modalidade, ref, sha256, nota, aprovado, bloqueios, partes, tentativa, limite, referencias, versao_avaliador, '
                'versao_politica, dados, criado) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', qid, rid, modalidade, ref, sha, int(rel['score']),
                1 if rel['passed'] else 0, json.dumps(rel['blocking_findings'], ensure_ascii=False), json.dumps(rel['partes'], ensure_ascii=False),
                rel.get('attempts_used'), rel.get('attempts_limit'), rel.get('reference_set_id'), rel.get('evaluator_version'), ct.VERSAO_POLITICA,
                json.dumps({k: rel.get(k) for k in ('medidas', 'avisos', 'opinioes', 'referencias_resumo')}, ensure_ascii=False), time.time())
    for f in rel['findings']:
        db.executar('INSERT INTO quality_findings (id, relatorio, categoria, severidade, ini_ms, fim_ms, evidencia, instrucao, alvo, acao, cena, confianca, natureza) '
                    'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', uuid.uuid4().hex[:12], qid, f['category'], f['severity'], f.get('time_start_ms'), f.get('time_end_ms'),
                    f['evidence'], f['instruction'], f['target_agent'], json.dumps(f.get('action')) if f.get('action') else None, f.get('scene'),
                    f.get('confidence'), f.get('nature'))
    rel['id'] = qid
    return rel


def relatorio(qid: str) -> dict:
    r = db.um('SELECT * FROM quality_reports WHERE id=?', qid)
    if not r:
        raise ErroPipeline('Relatório não encontrado.', 404)
    fs = db.todos('SELECT * FROM quality_findings WHERE relatorio=? ORDER BY COALESCE(ini_ms, 0)', qid)
    for f in fs:
        f['acao'] = json.loads(f['acao']) if f.get('acao') else None
    extra = json.loads(r.get('dados') or '{}')
    return {'id': r['id'], 'run': r['run'], 'modalidade': r['modalidade'], 'ref': r['ref'], 'sha256': r['sha256'], 'score': r['nota'], 'passed': bool(r['aprovado']),
            'blocking_findings': json.loads(r['bloqueios']), 'partes': json.loads(r['partes']), 'attempts_used': r['tentativa'], 'attempts_limit': r['limite'],
            'reference_set_id': r['referencias'], 'evaluator_version': r['versao_avaliador'], 'policy_version': r['versao_politica'], 'created_at': r['criado'],
            'findings': fs, **extra}


# ---------------------------------------------------------------- certificado (assinado pelo servidor)
def _chave() -> bytes:
    import cofre
    return cofre._sub(b'certificado-diretor')


def _assinar(c: dict) -> str:
    base = '|'.join(str(c.get(k, '')) for k in ('id', 'ref', 'modalidade', 'sha256', 'nota', 'bloqueios', 'versao_politica', 'revisao', 'manual', 'criado', 'expira'))
    return hmac.new(_chave(), base.encode(), hashlib.sha256).hexdigest()


def emitir_certificado(ref: str, sha: str, rel: dict, *, run: str = '', revisao: int = 0, manual: bool = False, por: str = '', motivo: str = '',
                       modalidade: str = 'final_release') -> dict:
    if not sha or len(sha) != 64:
        raise ErroPipeline('Certificado precisa do SHA-256 do arquivo exportado.')
    bloq = rel.get('blocking_findings') or []
    if manual:
        duros = [b for b in bloq if b.get('category') in ct.BLOQUEIOS_DUROS]
        if duros:
            raise ErroPipeline('Revisão manual não libera direitos, arquivo quebrado ou segurança: ' + '; '.join(b['evidence'] for b in duros)[:300], 409)
        if bloq:
            raise ErroPipeline('Ainda há bloqueio técnico neste arquivo: ' + '; '.join(b['evidence'] for b in bloq)[:300] + ' Corrija antes de aprovar.', 409)
    elif not ct.decidir(rel['score'], bloq):
        raise ErroPipeline('O diretor não aprovou este arquivo.', 409)
    # um certificado novo revoga os anteriores da mesma ref nesta modalidade
    agora = time.time()
    db.executar('UPDATE approval_certificates SET revogado=? WHERE ref=? AND modalidade=? AND revogado IS NULL AND sha256<>?', agora, ref, modalidade, sha)
    c = {'id': uuid.uuid4().hex[:16], 'ref': ref, 'modalidade': modalidade, 'sha256': sha, 'nota': int(rel['score']), 'bloqueios': len(bloq),
         'versao_politica': ct.VERSAO_POLITICA, 'revisao': int(revisao), 'manual': 1 if manual else 0, 'criado': round(agora, 3),
         'expira': round(agora + ct.VALIDADE_CERTIFICADO, 3)}
    c['assinatura'] = _assinar(c)
    db.executar('INSERT INTO approval_certificates (id, ref, run, modalidade, sha256, nota, bloqueios, versao_politica, revisao, manual, por, motivo, assinatura, criado, expira) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', c['id'], ref, run or None, modalidade, sha, c['nota'], json.dumps(bloq, ensure_ascii=False),
                c['versao_politica'], c['revisao'], c['manual'], por[:80], motivo[:300], c['assinatura'], c['criado'], c['expira'])
    db.evento(por or 'diretor', 'certificado_emitido', 'ref:' + ref, {'sha': sha[:16], 'nota': c['nota'], 'manual': bool(manual)})
    return c


def certificado(sha: str, modalidade: str = 'final_release') -> dict | None:
    """Certificado válido para ESTE arquivo (assinatura confere, não revogado, não vencido). None = não pode postar."""
    if not sha:
        return None
    for r in db.todos('SELECT * FROM approval_certificates WHERE sha256=? AND modalidade=? AND revogado IS NULL ORDER BY criado DESC', sha, modalidade):
        try:
            c = {**r, 'bloqueios': len(json.loads(r['bloqueios'] or '[]'))}
        except ValueError:
            continue
        c['criado'], c['expira'] = round(float(r['criado']), 3), round(float(r['expira']), 3)
        if not hmac.compare_digest(_assinar(c), r['assinatura']):
            db.evento('pipeline', 'certificado_adulterado', 'cert:' + r['id'])
            continue
        if r['expira'] < time.time():
            continue
        return r
    return None


def revogar(ref: str, motivo: str):
    n = db.executar('UPDATE approval_certificates SET revogado=? WHERE ref=? AND revogado IS NULL', time.time(), ref)
    if n:
        db.evento('pipeline', 'certificado_revogado', 'ref:' + ref, {'motivo': motivo[:200]})


_SHA_CACHE: dict = {}


def sha_arquivo(arq: Path) -> str:
    """SHA-256 com cache por (tamanho, data): o mesmo arquivo não é lido de novo a cada conferência."""
    try:
        st = arq.stat()
    except OSError:
        return ''
    k = (str(arq), st.st_size, st.st_mtime_ns)
    if k not in _SHA_CACHE:
        h = hashlib.sha256()
        with open(arq, 'rb') as f:
            for bloco in iter(lambda: f.read(1 << 20), b''):
                h.update(bloco)
        _SHA_CACHE.clear() if len(_SHA_CACHE) > 200 else None
        _SHA_CACHE[k] = h.hexdigest()
    return _SHA_CACHE[k]


def portao_postagem(arq: Path) -> dict:
    """Usado pelo Agente 2 em TODA postagem (criar, agendar e enviar): com a esteira ligada, só passa arquivo com certificado."""
    if not ligado():
        return {'ok': True, 'ativo': False, 'detalhe': 'Esteira dos 5 agentes desligada: vale a conferência de antes.'}
    sha = sha_arquivo(arq)
    c = certificado(sha)
    if not c:
        return {'ok': False, 'ativo': True, 'sha': sha, 'detalhe': 'Este arquivo não tem a aprovação do diretor de qualidade (Agente 4) para esta versão. '
                'Mande para o editor e o diretor antes de postar.'}
    return {'ok': True, 'ativo': True, 'sha': sha, 'certificado': c['id'], 'nota': c['nota'], 'manual': bool(c['manual']),
            'detalhe': f'Aprovado pelo diretor (nota {c["nota"]}{", revisão manual" if c["manual"] else ""}) para este arquivo.'}


# ---------------------------------------------------------------- revisão manual
def decidir_manual(rid: str, decisao: str, motivo: str, por: str) -> dict:
    """Você decide quando a esteira desistiu (5 correções). Nunca passa por cima de bloqueio."""
    r = obter(rid)
    if r['estado'] != 'manual_review_required':
        raise ErroPipeline('Esta execução não está esperando revisão manual.', 409)
    motivo = (motivo or '').strip()
    if len(motivo) < 5:
        raise ErroPipeline('Escreva o motivo da decisão (fica registrado).')
    if decisao == 'cancelar':
        mover(rid, 'cancelled', etapa='Cancelado por você: ' + motivo[:120])
        return obter(rid)
    if decisao != 'aprovar':
        raise ErroPipeline('Decisão inválida (aprovar ou cancelar).')
    if not r['relatorios']:
        raise ErroPipeline('Não há relatório do diretor para revisar.', 409)
    ult = r['relatorios'][-1]
    if ult['modalidade'] != 'final_release':
        raise ErroPipeline('A revisão manual da etapa criativa libera só a próxima etapa; o vídeo final ainda passa pelo diretor.', 409)
    arq = Path(r['arquivo'] or '')
    if not arq.is_file() or sha_arquivo(arq) != ult['sha256']:
        raise ErroPipeline('O arquivo mudou depois do último relatório: o diretor precisa conferir de novo.', 409)
    c = emitir_certificado(r['ref'], ult['sha256'], ult, run=rid, manual=True, por=por, motivo=motivo)
    mover(rid, 'final_approved', agente='agent2', etapa='Aprovado na revisão manual: ' + motivo[:120], dados={'certificado': c['id']})
    return obter(rid)


def lista(limite: int = 50, estado: str = '') -> list:
    sql = 'SELECT id FROM pipeline_runs' + (' WHERE estado=?' if estado else '') + ' ORDER BY atualizado DESC LIMIT ?'
    out = []
    for x in db.todos(sql, *([estado] if estado else []), max(1, min(limite, 200))):
        r = _run(x['id'])
        ult = db.um('SELECT nota, aprovado, modalidade FROM quality_reports WHERE run=? ORDER BY criado DESC LIMIT 1', x['id'])
        cont = {s['modalidade']: {'avaliacoes': s['avaliacoes'], 'correcoes': s['correcoes'], 'limite': s['limite'], 'estado': s['estado']}
                for s in db.todos('SELECT * FROM pipeline_stages WHERE run=?', x['id'])}
        out.append({'id': r['id'], 'origem': r['origem'], 'ref': r['ref'], 'titulo': r['titulo'], 'estado': r['estado'],
                    'nome_estado': ct.NOMES_ESTADO.get(r['estado'], r['estado']), 'agente': r['agente'], 'etapa': r['etapa'], 'atualizado': r['atualizado'],
                    'nota': ult['nota'] if ult else None, 'aprovado': bool(ult['aprovado']) if ult else None, 'contadores': cont,
                    'tentativas_tecnicas': r['dados'].get('tentativas_tecnicas', 0)})
    return out


def painel() -> dict:
    cont = {e: 0 for e in ct.ESTADOS}
    for r in db.todos('SELECT estado, COUNT(*) n FROM pipeline_runs GROUP BY estado'):
        cont[r['estado']] = r['n']
    return {'ligado': ligado(), 'politica': {'nota_minima': ct.NOTA_MINIMA, 'max_correcoes': ct.MAX_CORRECOES, 'versao': ct.VERSAO_POLITICA,
                                             'pesos': ct.PESOS, 'nomes': ct.NOMES_PARTES},
            'contagem': cont, 'nomes_estado': ct.NOMES_ESTADO, 'execucoes': lista(30)}


def encerrar_etapa(rid: str, modalidade: str, estado: str, motivo: str):
    """Fecha a etapa sem nova avaliação (ex.: a correção pedida não mudaria nada). Não consome correção."""
    s = etapa(rid, modalidade)
    db.executar('UPDATE pipeline_stages SET estado=?, atualizado=? WHERE id=?', estado, time.time(), s['id'])
    db.evento('pipeline', 'etapa_encerrada', 'run:' + rid, {'modalidade': modalidade, 'estado': estado, 'motivo': motivo[:200]})


def guardar_plano(rid: str, plano: dict, motivo: str = '', arquivo_sha: str = '') -> int:
    h = ct.hash_plano(plano)
    ult = db.um('SELECT versao, hash FROM edit_plans WHERE run=? ORDER BY versao DESC LIMIT 1', rid)
    if ult and ult['hash'] == h:
        if arquivo_sha:
            db.executar('UPDATE edit_plans SET arquivo_sha=? WHERE run=? AND versao=?', arquivo_sha, rid, ult['versao'])
        return ult['versao']
    v = (ult['versao'] if ult else 0) + 1
    db.executar('INSERT INTO edit_plans (id, run, versao, plano, hash, motivo, arquivo_sha, criado) VALUES (?,?,?,?,?,?,?,?)', uuid.uuid4().hex[:12], rid, v,
                json.dumps(plano, ensure_ascii=False), h, motivo[:300], arquivo_sha or None, time.time())
    return v


def ultimo_plano(rid: str) -> dict | None:
    r = db.um('SELECT plano FROM edit_plans WHERE run=? ORDER BY versao DESC LIMIT 1', rid)
    return json.loads(r['plano']) if r else None
