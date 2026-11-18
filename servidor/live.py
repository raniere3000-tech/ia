"""Parte Live: grava uma live do YouTube em blocos, o Agente 1 acha os melhores momentos de cada bloco,
o editor (Agente 5) e o diretor (Agente 4) conferem e, aprovado, o Agente 2 posta na hora.

Regras:
- Só com a esteira dos 5 agentes ligada (nada sai sem o certificado do diretor para o arquivo).
- Você diz de quem é a live (seu canal, autorizado pelo dono ou canal com regra pública de cortes) antes de gravar.
- Uma live por vez (é um celular). Limite de horas e de posts por live.
- Corte aprovado que passa do limite de posts vai para o estoque normal (a programação diária usa depois).
- A gravação é por cópia (sem recodificar): leve para o celular. O pesado (cortar, editar, conferir) é um bloco por vez, na fila.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

import postagem as pg

ARQ = pg.DADOS / 'live.json'
PASTA = pg.DADOS / 'live_blocos'
LOCK = threading.RLock()
PEGAR = None          # ligado pelo servidor: link -> {'url', 'titulo', 'id', 'canal', 'canal_nome', 'ao_vivo'}
PROC: dict = {}       # live -> processo do FFmpeg gravando
PADRAO = {'bloco_min': 5, 'cortes_por_bloco': 1, 'nota_min': 70, 'max_horas': 4, 'max_posts': 6, 'intervalo_min': 0,
          'redes': [], 'postar': True}
MOTIVOS = ('meu', 'autorizado', 'regra')
ESPERA_ERRO = 30      # segundos entre tentativas de reabrir a live


class ErroLive(Exception):
    def __init__(self, msg: str, status: int = 400):
        super().__init__(msg)
        self.status = status


# ---------------------------------------------------------------- estado
def _ler() -> dict:
    d = pg._ler(ARQ, {})
    if not isinstance(d.get('lives'), list):
        d['lives'] = []
    if not isinstance(d.get('config'), dict):
        d['config'] = {}
    return d


def _mudar(f):
    with LOCK:
        d = _ler()
        r = f(d)
        pg._gravar(ARQ, d)
        return r


def config() -> dict:
    return {**PADRAO, **_ler()['config']}


def _limpar_cfg(d: dict) -> dict:
    c = config()
    for k, (lo, hi) in {'bloco_min': (3, 20), 'cortes_por_bloco': (1, 3), 'nota_min': (40, 95), 'max_horas': (1, 12),
                        'max_posts': (1, 30), 'intervalo_min': (0, 240)}.items():
        if k in d:
            try:
                c[k] = max(lo, min(hi, int(d[k])))
            except (TypeError, ValueError):
                raise ErroLive(f'Valor inválido em {k}.')
    if 'redes' in d:
        c['redes'] = [r for r in (d['redes'] or []) if r in pg.REDES]
    if 'postar' in d:
        c['postar'] = bool(d['postar'])
    return c


def salvar_config(d: dict) -> dict:
    c = _limpar_cfg(d)
    _mudar(lambda x: x.update(config=c))
    return c


def obter(lid: str) -> dict:
    lv = next((x for x in _ler()['lives'] if x['id'] == lid), None)
    if not lv:
        raise ErroLive('Live não encontrada.', 404)
    return lv


def _mudar_live(lid: str, f):
    def g(d):
        for x in d['lives']:
            if x['id'] == lid:
                f(x)
                return x
    return _mudar(g)


def _anotar(lid: str, texto: str, tipo: str = 'info'):
    _mudar_live(lid, lambda x: (x.setdefault('log', []).append({'t': time.time(), 'tipo': tipo, 'texto': texto[:300]}),
                                x.update(log=x['log'][-60:])))
    print('live:', texto)


def ativa() -> dict | None:
    return next((x for x in _ler()['lives'] if x['estado'] in ('gravando', 'terminando')), None)


def ver() -> dict:
    d = _ler()
    lives = sorted(d['lives'], key=lambda x: -x.get('inicio', 0))[:10]
    try:
        import agente as ag
        cortes = {c['id']: c for c in ag.estado()['cortes'] if c.get('live')}
    except Exception:  # noqa: BLE001
        cortes = {}
    for lv in lives:
        lv['cortes'] = [{'id': c['id'], 'titulo': c.get('titulo', ''), 'status': c['status'], 'nota': (c.get('qa') or {}).get('nota'),
                         'post': c.get('post', ''), 'quando': c.get('quando'), 'links': c.get('links') or {}}
                        for c in cortes.values() if c['live'] == lv['id']]
    return {'config': config(), 'lives': lives, 'ativa': (ativa() or {}).get('id', ''), 'esteira': _esteira()}


def _esteira() -> bool:
    try:
        import pipeline as pl
        return pl.ligado()
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------- começar e parar
def comecar(d: dict, quem: str = 'site') -> dict:
    link = str(d.get('link') or '').strip()
    if not re.match(r'https?://', link):
        raise ErroLive('Cole o link da live.')
    if ativa():
        raise ErroLive('Já tem uma live sendo gravada. Pare a atual antes de começar outra.', 409)
    if not _esteira():
        raise ErroLive('Ligue a esteira dos 5 agentes (editor e diretor) antes: sem ela nada da live pode ser postado.', 409)
    if not (shutil.which('ffmpeg')):
        raise ErroLive('Falta o FFmpeg no servidor (Termux: pkg install ffmpeg).', 409)
    if PEGAR is None:
        raise ErroLive('Servidor sem a função de abrir lives.', 409)
    cfg = _limpar_cfg(d)
    origem = str((d.get('direitos') or {}).get('origem') or d.get('origem') or '')
    canal_aprovado = None
    try:
        info = PEGAR(link)
    except Exception as e:  # noqa: BLE001
        raise ErroLive(f'Não consegui abrir a live: {str(e)[:200]}')
    if not info.get('ao_vivo'):
        raise ErroLive('Este link não está ao vivo agora. Se a live já acabou, corte pelo link normal em Agente 1.')
    try:
        import agente as ag
        canal_aprovado = next((x for x in ag.estado()['canais'] if x['id'] == info.get('canal') and x['status'] == 'aprovado'
                               and x.get('motivo') in MOTIVOS), None)
    except Exception:  # noqa: BLE001
        pass
    if canal_aprovado and origem not in MOTIVOS:
        origem = canal_aprovado['motivo']
    if origem not in MOTIVOS:
        raise ErroLive('Diga de quem é a live: seu canal, autorizado pelo dono ou canal com regra pública de cortes.')
    if cfg['postar'] and not cfg['redes']:
        raise ErroLive('Escolha pelo menos uma rede para postar.')
    lid = uuid.uuid4().hex[:10]
    lv = {'id': lid, 'link': link, 'titulo': (info.get('titulo') or 'Live')[:150], 'video_id': info.get('id') or lid,
          'canal': canal_aprovado['id'] if canal_aprovado else '', 'canal_nome': info.get('canal_nome') or '',
          'direitos': {'origem': origem, 'nota': str((d.get('direitos') or {}).get('nota') or '')[:200] or 'Live gravada pela parte Live.'},
          'cfg': cfg, 'estado': 'gravando', 'inicio': time.time(), 'fim': None, 'blocos': [], 'postados': 0, 'ultimo_post': 0,
          'quem': str(quem)[:60], 'erro': '', 'log': []}
    _mudar(lambda x: (x['lives'].append(lv), x.update(lives=x['lives'][-30:])))
    _anotar(lid, f'Gravação começou: "{lv["titulo"][:80]}" em blocos de {cfg["bloco_min"]} min.', 'ok')
    threading.Thread(target=_gravar, args=(lid,), daemon=True).start()
    return obter(lid)


def parar(lid: str, quem: str = 'site') -> dict:
    lv = obter(lid)
    if lv['estado'] not in ('gravando', 'terminando'):
        return lv
    _mudar_live(lid, lambda x: x.update(estado='terminando', motivo_fim=f'Parada por {quem}.'))
    p = PROC.get(lid)
    if p and p.poll() is None:
        try:
            p.terminate()
        except OSError:
            pass
    _anotar(lid, 'Você parou a gravação. Os blocos já gravados ainda viram cortes.', 'aviso')
    return obter(lid)


# ---------------------------------------------------------------- gravação
def _blocos_no_disco(lid: str) -> list[Path]:
    return sorted((PASTA / lid).glob('b*.ts'))


def _num(arq: Path) -> int:
    return int(re.sub(r'\D', '', arq.stem) or 0)


def _registrar_bloco(lid: str, arq: Path):
    """Bloco fechado: entra na fila do Agente 1 (pesado, um por vez)."""
    n = _num(arq)
    lv = obter(lid)
    if any(b['n'] == n for b in lv['blocos']):
        return
    ini = (n - 1) * lv['cfg']['bloco_min'] * 60
    _mudar_live(lid, lambda x: x['blocos'].append({'n': n, 'arquivo': str(arq), 'estado': 'na_fila', 'ini': ini, 'cortes': [], 'msg': '', 't': time.time()}))
    try:
        import fila
        fila.enfileirar('live.bloco', agente='agente1', dados={'live': lid, 'n': n}, recurso='pesado', prioridade=5,
                        titulo=f'Live: bloco {n} de "{lv["titulo"][:40]}"', chave=f'live:{lid}:{n}', max_tentativas=1)
    except Exception as e:  # noqa: BLE001
        _mudar_live(lid, lambda x: [b.update(estado='erro', msg=str(e)[:200]) for b in x['blocos'] if b['n'] == n])
        _anotar(lid, f'Bloco {n}: não entrou na fila: {e}', 'erro')


def _gravar(lid: str):
    pasta = PASTA / lid
    pasta.mkdir(parents=True, exist_ok=True)
    erros = 0
    while True:
        lv = obter(lid)
        if lv['estado'] != 'gravando':
            break
        restante = lv['cfg']['max_horas'] * 3600 - (time.time() - lv['inicio'])
        if restante <= 5:
            _terminar(lid, f'Chegou ao limite de {lv["cfg"]["max_horas"]} hora(s) de gravação.')
            break
        try:
            info = PEGAR(lv['link'])
        except Exception as e:  # noqa: BLE001
            erros += 1
            _anotar(lid, f'Não consegui reabrir a live (tentativa {erros} de 3): {str(e)[:160]}', 'erro')
            if erros >= 3:
                _terminar(lid, 'Não consegui mais abrir a live.', erro=str(e)[:200])
                break
            time.sleep(ESPERA_ERRO)
            continue
        if not info.get('ao_vivo'):
            _terminar(lid, 'A live terminou.')
            break
        existentes = _blocos_no_disco(lid)
        prox = (max(_num(a) for a in existentes) + 1) if existentes else 1
        urls = info.get('urls') or [info['url']]
        entradas = [x for u in urls[:2] for x in ('-i', u)]
        mapas = ['-map', '0:v:0', '-map', '1:a:0'] if len(urls) > 1 else ['-map', '0:v:0?', '-map', '0:a:0?']
        cmd = ['ffmpeg', '-nostdin', '-v', 'error', '-y', *entradas, *mapas, '-c', 'copy',
               '-t', str(int(restante)), '-f', 'segment', '-segment_time', str(lv['cfg']['bloco_min'] * 60),
               '-segment_start_number', str(prox), '-reset_timestamps', '1', str(pasta / 'b%05d.ts')]
        t0 = time.time()
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        PROC[lid] = p
        while p.poll() is None:
            for a in _blocos_no_disco(lid)[:-1]:        # o último ainda está sendo gravado
                _registrar_bloco(lid, a)
            if obter(lid)['estado'] != 'gravando':
                p.terminate()
            time.sleep(3)
        err = (p.stderr.read() or b'').decode(errors='replace')[-300:] if p.stderr else ''
        PROC.pop(lid, None)
        for a in _blocos_no_disco(lid):                  # o FFmpeg parou: todos os blocos estão fechados
            _registrar_bloco(lid, a)
        if time.time() - t0 < 20:
            erros += 1
            if erros >= 3:
                _terminar(lid, 'A gravação parou várias vezes seguidas.', erro=err)
                break
            time.sleep(ESPERA_ERRO)
        else:
            erros = 0           # o link da live vence de tempos em tempos: reabre e continua no próximo bloco
    if obter(lid)['estado'] == 'terminando':
        _terminar(lid, obter(lid).get('motivo_fim') or 'Gravação parada.')


def _terminar(lid: str, motivo: str, erro: str = ''):
    lv = obter(lid)
    if lv['estado'] in ('terminada', 'erro'):
        return
    for a in _blocos_no_disco(lid):
        _registrar_bloco(lid, a)
    _mudar_live(lid, lambda x: x.update(estado='erro' if erro and not x['blocos'] else 'terminada', fim=time.time(), motivo_fim=motivo, erro=erro))
    _anotar(lid, motivo + (f' ({erro[:160]})' if erro else ''), 'erro' if erro else 'ok')
    try:
        import agente as ag
        lv = obter(lid)
        ag.avisar('live', 'Live: gravação encerrada', f'Live: {lv["titulo"]}\n{motivo}\nBlocos gravados: {len(lv["blocos"])}. '
                  f'Posts feitos até agora: {lv["postados"]}.\nOs blocos que faltam ainda viram cortes.\n',
                  zap=f'*EstúdioClip — Live*\n{motivo}\n"{lv["titulo"][:60]}": {len(lv["blocos"])} bloco(s), {lv["postados"]} post(s).', zap_tipo='a1_corte')
    except Exception as e:  # noqa: BLE001
        print('live: aviso', e)


# ---------------------------------------------------------------- cada bloco: melhores momentos -> editor/diretor -> posta
def job_bloco(ctx):
    import agente as ag
    lid, n = ctx.dados['live'], int(ctx.dados['n'])
    lv = obter(lid)
    b = next((x for x in lv['blocos'] if x['n'] == n), None)
    if not b:
        return {'etapa': 'Bloco não encontrado.'}
    arq = Path(b['arquivo'])

    def marcar(**k):
        _mudar_live(lid, lambda x: [y.update(**k) for y in x['blocos'] if y['n'] == n])
    if not arq.exists():
        marcar(estado='erro', msg='O arquivo do bloco sumiu.')
        return {'etapa': 'Arquivo sumiu.'}
    marcar(estado='cortando')
    ctx.progresso(5, f'Live: achando os melhores momentos do bloco {n}')
    cfg = lv['cfg']
    try:
        dur = ag.duracao(arq)
        if dur < 45:
            marcar(estado='feito', msg='Bloco curto demais para um corte.')
            return {'etapa': 'Bloco curto'}
        v = {'id': f'{lv["video_id"]}-live{n}', 'url': lv['link'], 'titulo': f'{lv["titulo"]} (live, bloco {n})', 'canal': lv['canal'],
             'canal_nome': lv['canal_nome']}
        criados = ag.processar_video(v, cfg['cortes_por_bloco'], baixado=(arq, {'title': lv['titulo'], 'duration': dur}, None),
                                     extra={'live': lid, 'live_bloco': n, 'live_fila': bool(cfg['postar']), 'direitos': lv['direitos'],
                                            'live_ini': b['ini']},
                                     ajustes={'nota_min': cfg['nota_min']})
    except ag.ErroAgente as e:
        marcar(estado='feito', msg=str(e)[:200])
        _anotar(lid, f'Bloco {n}: sem corte ({e}).')
        arq.unlink(missing_ok=True)
        return {'etapa': 'Sem corte neste bloco'}
    except Exception as e:  # noqa: BLE001
        marcar(estado='erro', msg=str(e)[:200])
        _anotar(lid, f'Bloco {n}: erro: {e}', 'erro')
        raise
    finally:
        ag.etapa('')
    ok = [c for c in criados if c['status'] == 'pronto']
    marcar(estado='feito', cortes=[c['id'] for c in criados], msg=f'{len(criados)} corte(s), {len(ok)} aprovado(s) pelo diretor.')
    arq.unlink(missing_ok=True)
    postados = postar_aprovados(lid)
    _anotar(lid, f'Bloco {n}: {len(criados)} corte(s), {len(ok)} aprovado(s), {postados} enviado(s) para postar.', 'ok' if ok else 'info')
    return {'etapa': f'{len(ok)} aprovado(s), {postados} postando', 'resultado': {'cortes': len(criados), 'aprovados': len(ok), 'postando': postados}}


def postar_aprovados(lid: str) -> int:
    """Cortes aprovados desta live: posta na hora (ou logo depois do post anterior, se tiver intervalo). Passou do limite: estoque normal."""
    import agente as ag
    import pipeline as pl
    import agenda_postagem as ag2
    lv = obter(lid)
    cfg = lv['cfg']
    feitos = 0
    for c in [x for x in ag.estado()['cortes'] if x.get('live') == lid and x.get('live_fila') and x['status'] == 'pronto']:
        lv = obter(lid)
        sha = ag2._sha(c)
        if not cfg['postar'] or lv['postados'] >= cfg['max_posts'] or not (sha and pl.certificado(sha)):
            ag._mudar(lambda e, cid=c['id']: [x.update(live_fila=False) for x in e['cortes'] if x['id'] == cid])   # vai para o estoque normal
            if lv['postados'] >= cfg['max_posts']:
                _anotar(lid, f'"{c["titulo"][:50]}" aprovado, mas a live já chegou a {cfg["max_posts"]} posts: foi para o estoque.')
            continue
        quando = max(time.time(), (lv.get('ultimo_post') or 0) + cfg['intervalo_min'] * 60)
        try:
            ag.agendar_corte(c['id'], quem='live', quando=quando, redes_live=cfg['redes'])
        except (ag.ErroAgente, pg.ErroRede) as e:
            ag._mudar(lambda e2, cid=c['id']: [x.update(live_fila=False) for x in e2['cortes'] if x['id'] == cid])
            _anotar(lid, f'Não postei "{c["titulo"][:50]}": {e}', 'erro')
            continue
        _mudar_live(lid, lambda x, q=quando: x.update(postados=x['postados'] + 1, ultimo_post=q))
        feitos += 1
    return feitos


def iniciar():
    """Servidor ligou: lives que estavam gravando quando ele caiu continuam (se ainda estiverem no ar)."""
    import fila
    fila.registrar('live.bloco', job_bloco, 'pesado')
    for lv in _ler()['lives']:
        if lv['estado'] == 'gravando':
            threading.Thread(target=_gravar, args=(lv['id'],), daemon=True).start()
        elif lv['estado'] == 'terminando':
            _terminar(lv['id'], lv.get('motivo_fim') or 'Gravação parada.')
