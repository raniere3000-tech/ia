"""Fila única dos agentes, guardada no banco (sobrevive a reinício).

Classes de recurso:
  pesado  -> FFmpeg / CPU: UM por vez (o celular não aguenta dois). Usa o mesmo cadeado do agente de cortes.
  leve    -> chamadas de IA, pesquisas, e-mails: poucos ao mesmo tempo.
A postagem (Agente 2) tem relógio próprio e nunca espera por esta fila.

Cada trabalho tem horário de liberação (run_at), prioridade, tentativas com espera crescente,
"aluguel" (lease) renovado enquanto roda e retomada depois de um reinício. Um trabalho pode ter
várias etapas: cada etapa devolve a próxima e a classe de recurso que ela precisa.
"""
from __future__ import annotations

import json
import os
import threading
import time
import traceback
import uuid

import banco as db

LIMITES = {'pesado': int(os.getenv('MAX_PESADOS', '1')), 'leve': int(os.getenv('MAX_LEVES', '2'))}
ALUGUEL = 180                      # segundos sem sinal de vida = trabalho travado
ESPERAS = [float(x) for x in os.getenv('ESPERAS_FILA', '60,300,1200').split(',')]
ATIVOS = ('agendado', 'na_fila', 'aguardando_tentativa', 'rodando')
FINAIS = ('concluido', 'falhou', 'cancelado')
HANDLERS: dict[str, tuple] = {}    # tipo -> (função, recurso padrão)
CADEADO_PESADO = None              # ligado pelo servidor ao cadeado OCUPADO do agente de cortes
ACORDAR = threading.Event()
_parar = threading.Event()
_rodando: dict[str, 'Contexto'] = {}
_LOCK = threading.Lock()


class Cancelado(Exception):
    pass


class Esperar(Exception):
    """A etapa precisa esperar algo (aprovação, API ocupada): volta para a fila sem contar tentativa."""
    def __init__(self, segundos: float, motivo: str, status: str = 'na_fila'):
        super().__init__(motivo)
        self.segundos = segundos
        self.motivo = motivo
        self.status = status


class Contexto:
    def __init__(self, job: dict):
        self.job = job
        self.id = job['id']
        self.dados = json.loads(job.get('dados') or '{}')
        self.inicio = time.time()
        self._ultimo = 0.0

    def progresso(self, pct: float | None = None, etapa: str | None = None):
        """Atualiza o progresso REAL (quem chama sabe quanto já fez) e renova o aluguel."""
        agora = time.time()
        if self.cancelado():
            raise Cancelado()
        if agora - self._ultimo < 1 and pct is not None and pct < 100:
            return
        self._ultimo = agora
        sets, args = ['heartbeat=?', 'lease=?'], [agora, agora + ALUGUEL]
        if pct is not None:
            sets.append('progresso=?')
            args.append(round(max(0, min(100, pct)), 1))
        if etapa is not None:
            sets.append('etapa=?')
            args.append(etapa[:200])
        db.executar(f'UPDATE jobs SET {", ".join(sets)} WHERE id=? AND cancelar=0 AND pausado=0', *args, self.id)

    def cancelado(self) -> bool:
        j = db.um('SELECT cancelar, pausado FROM jobs WHERE id=?', self.id)
        return bool(j and (j['cancelar'] or j['pausado']))

    def salvar(self):
        db.executar('UPDATE jobs SET dados=? WHERE id=?', json.dumps(self.dados, ensure_ascii=False), self.id)


def registrar(tipo: str, funcao, recurso: str = 'leve'):
    HANDLERS[tipo] = (funcao, recurso)


def enfileirar(tipo: str, *, agente: str, dados: dict | None = None, run_at: float | None = None, prioridade: int = 0,
               recurso: str | None = None, projeto: str = '', titulo: str = '', chave: str = '', max_tentativas: int = 3) -> dict:
    if tipo not in HANDLERS:
        raise ValueError('tipo de trabalho desconhecido: ' + tipo)
    if chave:
        ja = db.um('SELECT * FROM jobs WHERE chave=?', chave)
        if ja:                 # pedido repetido (duplo clique, reinício): não cria outro
            return ja
    agora = time.time()
    quando = float(run_at) if run_at else agora
    jid = uuid.uuid4().hex[:12]
    db.executar('INSERT INTO jobs (id, agente, tipo, projeto, titulo, status, run_at, prioridade, recurso, max_tentativas, criado, dados, chave, etapa) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', jid, agente, tipo, projeto, titulo[:160], 'agendado' if quando > agora + 1 else 'na_fila',
                quando, int(prioridade), recurso or HANDLERS[tipo][1], max_tentativas, agora, json.dumps(dados or {}, ensure_ascii=False), chave or None,
                'Esperando o horário' if quando > agora + 1 else 'Na fila')
    db.evento(agente, 'job_criado', 'job:' + jid, {'tipo': tipo, 'run_at': quando})
    ACORDAR.set()
    return db.um('SELECT * FROM jobs WHERE id=?', jid)


def obter(jid: str) -> dict | None:
    return db.um('SELECT * FROM jobs WHERE id=?', jid)


def _pronto_sql():
    return ("status IN ('agendado','na_fila','aguardando_tentativa') AND pausado=0 AND cancelar=0 AND run_at<=? AND proxima<=? AND recurso=?")


def _proximo(recurso: str) -> dict | None:
    """Prioridade + antiguidade (quem espera há mais tempo sobe aos poucos, ninguém fica esquecido)."""
    agora = time.time()
    with db.tx() as c:
        r = c.execute(f'SELECT * FROM jobs WHERE {_pronto_sql()} ORDER BY (prioridade + (?-run_at)/3600.0) DESC, run_at, criado LIMIT 1',
                      (agora, agora, recurso, agora)).fetchone()
        if not r:
            return None
        c.execute("UPDATE jobs SET status='rodando', lease=?, heartbeat=?, iniciado=COALESCE(iniciado, ?) WHERE id=?",
                  (agora + ALUGUEL, agora, agora, r['id']))
    return dict(r, status='rodando')


def _cancelar_entidades(job: dict):
    """Uma produção cancelada não continua aparecendo como aprovação pendente."""
    agora = time.time()
    if job.get('projeto'):
        db.executar("UPDATE projetos SET status='cancelled', atualizado=? WHERE id=? "
                    "AND status NOT IN ('queued_to_publish','posted','rejected')", agora, job['projeto'])
        db.executar('UPDATE desafios SET usado=? WHERE projeto=? AND usado IS NULL', agora, job['projeto'])
    db.executar("UPDATE thumbnail_jobs SET estado='cancelado', erro='Cancelado por você.', atualizado=? "
                "WHERE fila_job=? AND estado NOT IN ('pronto','cancelado')", agora, job['id'])


def _encerrar_interrompido(ctx: Contexto, dur: float):
    db.executar("""UPDATE jobs SET status=CASE WHEN cancelar=1 THEN 'cancelado' ELSE 'na_fila' END,
                etapa=CASE WHEN cancelar=1 THEN 'Cancelado por você' ELSE 'Pausado por você' END,
                terminado=CASE WHEN cancelar=1 THEN ? ELSE NULL END,
                erro=CASE WHEN cancelar=1 THEN NULL ELSE erro END,
                lease=0, dados=?, decorrido=decorrido+? WHERE id=? AND status='rodando'""",
                time.time(), json.dumps(ctx.dados, ensure_ascii=False), dur, ctx.id)
    job = obter(ctx.id)
    if job and job['cancelar']:
        _cancelar_entidades(job)


def _atualizar_execucao(ctx: Contexto, dur: float, sql: str, *args) -> bool:
    if db.executar(sql + " AND status='rodando' AND cancelar=0 AND pausado=0", *args, ctx.id):
        return True
    _encerrar_interrompido(ctx, dur)
    return False


def _executar(job: dict):
    ctx = Contexto(job)
    with _LOCK:
        _rodando[job['id']] = ctx
    funcao = HANDLERS.get(job['tipo'], (None,))[0]
    inicio = time.time()
    try:
        if not funcao:
            raise RuntimeError('Tipo de trabalho desconhecido (versão antiga do servidor?): ' + job['tipo'])
        if ctx.cancelado():
            raise Cancelado()
        r = funcao(ctx) or {}
        dur = time.time() - inicio
        db.executar('DELETE FROM kv WHERE chave=?', 'liberar:' + ctx.id)    # a etapa passou sem pedir aprovação: o aviso guardado não vale para a próxima
        if r.get('proxima'):           # etapa seguinte do mesmo trabalho
            _atualizar_execucao(ctx, dur, "UPDATE jobs SET status='na_fila', recurso=?, etapa=?, dados=?, decorrido=decorrido+?, lease=0, tentativas=0 WHERE id=?",
                        r.get('recurso', 'leve'), r.get('etapa', 'Na fila'), json.dumps(ctx.dados, ensure_ascii=False), dur)
        else:
            try:
                medir('job:' + job['tipo'], (job.get('decorrido') or 0) + dur)      # aprende quanto cada tipo de trabalho demora NESTE celular
            except Exception:  # noqa: BLE001
                pass
            if _atualizar_execucao(ctx, dur, "UPDATE jobs SET status='concluido', progresso=100, etapa=?, terminado=?, resultado=?, dados=?, decorrido=decorrido+?, lease=0 WHERE id=?",
                        r.get('etapa', 'Concluído'), time.time(), json.dumps(r.get('resultado'), ensure_ascii=False), json.dumps(ctx.dados, ensure_ascii=False), dur):
                db.evento('fila', 'job_concluido', 'job:' + job['id'])
    except Esperar as e:
        dur = time.time() - inicio
        status, motivo = e.status, e.motivo
        if status == 'aguardando_aprovacao' and db.kv('liberar:' + ctx.id):
            # a sua aprovação chegou enquanto a etapa ainda rodava: não fica parado esperando algo que já aconteceu
            status, motivo = 'na_fila', 'Na fila (aprovado)'
        if _atualizar_execucao(ctx, dur, 'UPDATE jobs SET status=?, proxima=?, etapa=?, dados=?, decorrido=decorrido+?, lease=0 WHERE id=?',
                               status, time.time() + (0 if status != e.status else e.segundos), motivo[:200],
                               json.dumps(ctx.dados, ensure_ascii=False), dur):
            db.executar('DELETE FROM kv WHERE chave=?', 'liberar:' + ctx.id)
    except Cancelado:
        _encerrar_interrompido(ctx, time.time() - inicio)
    except Exception as e:  # noqa: BLE001
        msg = str(e) or e.__class__.__name__
        print('fila:', job['tipo'], msg)
        if not isinstance(e, (ValueError, PermissionError)) and os.getenv('FILA_DEBUG'):
            traceback.print_exc()
        j = obter(job['id']) or job
        tent = (j['tentativas'] or 0) + 1
        definitivo = getattr(e, 'definitivo', False)
        dur = time.time() - inicio
        if tent >= j['max_tentativas'] or definitivo:
            if not _atualizar_execucao(ctx, dur, "UPDATE jobs SET status='falhou', tentativas=?, erro=?, etapa='Falhou', terminado=?, lease=0, dados=?, decorrido=decorrido+? WHERE id=?",
                        tent, msg[:1000], time.time(), json.dumps(ctx.dados, ensure_ascii=False), dur):
                return
            db.evento('fila', 'job_falhou', 'job:' + job['id'], {'erro': msg[:300]})
            for f in AO_FALHAR:
                try:
                    f(obter(job['id']), msg)
                except Exception as e2:  # noqa: BLE001
                    print('fila: aviso de falha:', e2)
        else:
            espera = ESPERAS[min(tent - 1, len(ESPERAS) - 1)]
            _atualizar_execucao(ctx, dur, "UPDATE jobs SET status='aguardando_tentativa', tentativas=?, erro=?, proxima=?, etapa=?, lease=0, dados=?, decorrido=decorrido+? WHERE id=?",
                        tent, msg[:1000], time.time() + espera, f'Erro, nova tentativa em {int(espera // 60) or 1} min', json.dumps(ctx.dados, ensure_ascii=False),
                        dur)
    finally:
        with _LOCK:
            _rodando.pop(job['id'], None)
        ACORDAR.set()


AO_FALHAR: list = []


def _trabalhador(recurso: str):
    while not _parar.is_set():
        job = None
        try:
            if recurso == 'pesado' and CADEADO_PESADO is not None:
                if not CADEADO_PESADO.acquire(timeout=5):     # o agente de cortes (caminho antigo) está usando
                    continue
                try:
                    job = _proximo(recurso)
                    if job:
                        _executar(job)
                finally:
                    CADEADO_PESADO.release()
            else:
                job = _proximo(recurso)
                if job:
                    _executar(job)
        except Exception as e:  # noqa: BLE001
            print('fila: trabalhador', recurso, e)
        if not job:
            ACORDAR.wait(float(os.getenv('FILA_INTERVALO', '5')))
            ACORDAR.clear()


def recuperar():
    """Depois de um reinício: o que estava 'rodando' volta para a fila (as etapas já feitas ficam salvas)."""
    agora = time.time()
    n = db.executar("UPDATE jobs SET status='na_fila', etapa='Retomando depois de reinício', lease=0 WHERE status='rodando' AND cancelar=0 AND (lease<? OR ?=1)",
                    agora, 1 if not _rodando else 0)
    db.executar("UPDATE jobs SET status='cancelado', etapa='Cancelado por você', terminado=?, lease=0 "
                "WHERE status='rodando' AND cancelar=1 AND (lease<? OR ?=1)", agora, agora, 1 if not _rodando else 0)
    if n:
        db.evento('fila', 'jobs_recuperados', '', {'quantos': n})
    return n


def vigiar():
    """Trabalho com aluguel vencido (travou sem avisar) volta para a fila."""
    while not _parar.is_set():
        time.sleep(30)
        try:
            with _LOCK:
                vivos = set(_rodando)
            for j in db.todos("SELECT id FROM jobs WHERE status='rodando' AND lease<?", time.time()):
                if j['id'] not in vivos:
                    db.executar("UPDATE jobs SET status=CASE WHEN cancelar=1 THEN 'cancelado' ELSE 'na_fila' END, "
                                "etapa=CASE WHEN cancelar=1 THEN 'Cancelado por você' ELSE 'Retomando (travou)' END, "
                                "terminado=CASE WHEN cancelar=1 THEN ? ELSE terminado END, lease=0 "
                                "WHERE id=? AND status='rodando'", time.time(), j['id'])
        except Exception as e:  # noqa: BLE001
            print('fila: vigia', e)


def iniciar():
    recuperar()
    for recurso, n in LIMITES.items():
        for i in range(max(1, n)):
            threading.Thread(target=_trabalhador, args=(recurso,), daemon=True, name=f'fila-{recurso}-{i}').start()
    threading.Thread(target=vigiar, daemon=True).start()


# ---------------------------------------------------------------- comandos
def pausar(jid: str) -> dict:
    db.executar("UPDATE jobs SET pausado=1, etapa=CASE WHEN status='rodando' THEN 'Pausando...' ELSE 'Pausado por você' END WHERE id=? AND cancelar=0 AND status NOT IN ('concluido','falhou','cancelado')", jid)
    return obter(jid)


def retomar(jid: str) -> dict:
    db.executar("UPDATE jobs SET pausado=0, etapa='Na fila' WHERE id=? AND cancelar=0 AND status NOT IN ('concluido','cancelado')", jid)
    ACORDAR.set()
    return obter(jid)


def cancelar(jid: str) -> dict:
    db.executar("""UPDATE jobs SET cancelar=1,
                status=CASE WHEN status='rodando' THEN status ELSE 'cancelado' END,
                etapa=CASE WHEN status='rodando' THEN 'Cancelando…' ELSE 'Cancelado por você' END,
                terminado=CASE WHEN status='rodando' THEN terminado ELSE ? END,
                pausado=0
                WHERE id=? AND status NOT IN ('concluido','falhou','cancelado')""", time.time(), jid)
    j = obter(jid)
    if not j:
        raise ValueError('Trabalho não encontrado.')
    if j['cancelar']:
        _cancelar_entidades(j)
    return j


def ignorar(jid: str) -> dict:
    db.executar("""UPDATE jobs SET status='cancelado', cancelar=1, pausado=0, etapa='Ignorado por você', terminado=?
                WHERE id=? AND status IN ('na_fila','agendado','aguardando_tentativa','aguardando_aprovacao')""",
                time.time(), jid)
    job = obter(jid)
    if job and job['status'] == 'cancelado':
        _cancelar_entidades(job)
    return job


def liberar(jid: str) -> dict:
    """Trabalho que esperava uma aprovação volta para a fila (continua da mesma etapa)."""
    if not db.executar("UPDATE jobs SET status='na_fila', proxima=0, etapa='Na fila (aprovado)' WHERE id=? AND status='aguardando_aprovacao'", jid):
        if (obter(jid) or {}).get('status') == 'rodando':
            db.kv_gravar('liberar:' + jid, time.time())      # chegou antes de a etapa terminar de pedir: vale quando ela pedir
    ACORDAR.set()
    return obter(jid)


def tentar_de_novo(jid: str) -> dict:
    db.executar("UPDATE jobs SET status='na_fila', tentativas=0, proxima=0, erro=NULL, cancelar=0, pausado=0, terminado=NULL, etapa='Na fila (nova tentativa)' "
                "WHERE id=? AND status IN ('falhou','cancelado','aguardando_tentativa')", jid)
    ACORDAR.set()
    return obter(jid)


def reagendar(jid: str, run_at: float) -> dict:
    db.executar("UPDATE jobs SET run_at=?, status=CASE WHEN ?>? THEN 'agendado' ELSE 'na_fila' END, etapa=CASE WHEN ?>? THEN 'Esperando o horário' ELSE 'Na fila' END "
                "WHERE id=? AND status IN ('agendado','na_fila','aguardando_tentativa')", run_at, run_at, time.time(), run_at, time.time(), jid)
    ACORDAR.set()
    return obter(jid)


# ---------------------------------------------------------------- medidas e previsão
PADRAO_ETAPA = {'roteiro': 40, 'narracao': 25, 'visual': 30, 'render_cena': 45, 'final': 90, 'validacao': 30, 'agente1': 900, 'leve': 30}


def medir(etapa: str, segundos: float, unidades: float = 1):
    db.executar('INSERT INTO medidas (etapa, segundos, unidades, t) VALUES (?,?,?,?)', etapa, segundos, unidades, time.time())


def media(etapa: str) -> tuple[float, bool]:
    """Segundos por unidade, medidos de verdade neste aparelho (últimas 20). Sem medida: chute inicial."""
    r = db.todos('SELECT segundos, unidades FROM medidas WHERE etapa=? ORDER BY id DESC LIMIT 20', etapa)
    if not r:
        return float(PADRAO_ETAPA.get(etapa, 60)), False
    tot = sum(x['segundos'] for x in r)
    un = sum(max(x['unidades'], 0.001) for x in r)
    return tot / un, True


def restante(job: dict) -> tuple[float, bool]:
    """Tempo de produção que ainda falta (estimativa)."""
    from_handler = ESTIMADORES.get(job['tipo'])
    if from_handler:
        return from_handler(job)
    p = float(job.get('progresso') or 0)
    if job.get('status') == 'rodando' and p >= 5 and job.get('iniciado'):
        gasto = time.time() - float(job['iniciado'])                 # pelo ritmo de agora: quanto já levou para chegar aqui
        return gasto * (100 - p) / p, True
    s, medido = media('job:' + job['tipo'])
    if not medido:
        s, medido = media('agente1' if job['agente'] == 'agente1' else 'leve')
    return s * (1 - p / 100), medido


ESTIMADORES: dict = {}


def lista(filtro: str = '') -> dict:
    agora = time.time()
    js = db.todos('SELECT * FROM jobs ORDER BY CASE status WHEN \'rodando\' THEN 0 WHEN \'na_fila\' THEN 1 WHEN \'aguardando_tentativa\' THEN 2 '
                  'WHEN \'agendado\' THEN 3 ELSE 4 END, run_at LIMIT 300')
    # previsão de início: soma do que está na frente na mesma classe de recurso
    frente = {'pesado': 0.0, 'leve': 0.0}
    for j in js:
        j['dados'] = json.loads(j.get('dados') or '{}')
        j['resultado'] = json.loads(j['resultado']) if j.get('resultado') else None
        if j['status'] in FINAIS:
            j['inicio_previsto'] = None
            j['restante'] = 0
            continue
        rest, medido = restante(j)
        j['restante'] = round(rest)
        j['estimativa_medida'] = medido
        base = max(agora, j['run_at'] or agora)
        if j['status'] == 'rodando':
            j['inicio_previsto'] = j['iniciado']
        else:
            j['inicio_previsto'] = max(base, agora + frente.get(j['recurso'], 0) / max(1, LIMITES.get(j['recurso'], 1)))
        j['fim_previsto'] = (j['inicio_previsto'] or agora) + rest if j['status'] != 'rodando' else agora + rest
        frente[j['recurso']] = frente.get(j['recurso'], 0) + rest
        j['decorrido_total'] = (j['decorrido'] or 0) + (agora - j['iniciado'] if j['status'] == 'rodando' and j['iniciado'] else 0)
        j['posicao'] = None
    pos = {}
    for j in js:
        if j['status'] in ('na_fila', 'aguardando_tentativa', 'agendado'):
            pos[j['recurso']] = pos.get(j['recurso'], 0) + 1
            j['posicao'] = pos[j['recurso']]
    grupos = {'todos': js}
    if filtro:
        grupos['todos'] = [j for j in js if _grupo(j) == filtro]
    return {'jobs': grupos['todos'], 'agora': agora, 'limites': LIMITES,
            'contagem': {g: sum(1 for j in js if _grupo(j) == g) for g in ('produzindo', 'agendados', 'prontos', 'pausados', 'erros', 'concluidos')}}


def _grupo(j: dict) -> str:
    if j['status'] == 'falhou':
        return 'erros'
    if j['pausado']:
        return 'pausados'
    if j['status'] == 'agendado':
        return 'agendados'
    if j['status'] in ('rodando', 'na_fila', 'aguardando_tentativa'):
        return 'prontos' if j.get('etapa') == 'Pronto para revisão' else 'produzindo'
    return 'concluidos'


def capacidade() -> dict:
    import shutil
    livre = -1
    try:
        livre = shutil.disk_usage(db.PASTA).free
    except OSError:
        pass
    carga = None
    try:
        carga = os.getloadavg()[0]
    except (OSError, AttributeError):
        pass
    mem = None
    try:
        with open('/proc/meminfo') as f:
            info = {ln.split(':')[0]: int(ln.split()[1]) for ln in f if ':' in ln and ln.split()[1].isdigit()}
        mem = {'total_mb': info.get('MemTotal', 0) // 1024, 'livre_mb': info.get('MemAvailable', 0) // 1024}
    except (OSError, ValueError, IndexError):
        pass
    bateria = None
    temp = None
    for base in ('/sys/class/power_supply/battery',):
        try:
            bateria = int(open(base + '/capacity').read().strip())
        except (OSError, ValueError):
            pass
        try:
            temp = int(open(base + '/temp').read().strip()) / 10
        except (OSError, ValueError):
            pass
    with _LOCK:
        rodando = [{'id': k, 'tipo': v.job['tipo'], 'recurso': v.job['recurso']} for k, v in _rodando.items()]
    return {'limites': LIMITES, 'rodando': rodando, 'cpus': os.cpu_count(), 'disco_livre_mb': livre // 1048576 if livre >= 0 else None,
            'carga_cpu': carga, 'memoria': mem, 'bateria': bateria, 'temperatura': temp,
            'nota': 'Métricas que o Android não mostra aparecem como "não disponível".'}
