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
PADRAO = {'v': 2, 'bloco_min': 5, 'cortes_por_bloco': 3, 'nota_min': 60, 'max_horas': 4, 'max_posts': 6, 'intervalo_min': 0,
          'redes': [], 'postar': True}
MOTIVOS = ('meu', 'autorizado', 'regra')
ESPERA_ERRO = 30      # segundos entre tentativas de reabrir a live
LIVRE_MIN = 1500 * 2**20   # abaixo disso a gravação espera (um bloco de 10 min em 1080p passa de 300 MB)
ESPERA_ESPACO = 60
SEM_DADOS = 90        # segundos sem o arquivo crescer = a live parou de mandar vídeo


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
    salvo = _ler()['config']
    c = {**PADRAO, **salvo}
    if salvo and int(salvo.get('v') or 0) < 2:          # 18/11: 1 corte por bloco e nota 70 davam corte de menos
        c.update(v=2, cortes_por_bloco=max(3, int(c.get('cortes_por_bloco') or 1)), nota_min=min(60, int(c.get('nota_min') or 60)))
    return c


def _limpar_cfg(d: dict) -> dict:
    c = config()
    for k, (lo, hi) in {'bloco_min': (3, 20), 'cortes_por_bloco': (1, 5), 'nota_min': (40, 95), 'max_horas': (1, 12),
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


def pendente() -> bool:
    """A Live tem bloco esperando ou sendo cortado: o Agente 1 automático (Central) espera, a Live vem primeiro."""
    try:          # vale o que está de fato na fila (um bloco cancelado à mão não segura o Agente 1 para sempre)
        import banco as db
        return bool(db.um("SELECT id FROM jobs WHERE tipo='live.bloco' AND status IN ('agendado','na_fila','rodando','aguardando_tentativa') "
                          "AND pausado=0 AND cancelar=0 LIMIT 1"))
    except Exception:  # noqa: BLE001
        return False


def _ocupando() -> str:
    """O que está usando a vez do trabalho pesado agora (para a tela explicar a espera)."""
    try:
        import agente as ag
        import banco as db
        j = db.um("SELECT titulo FROM jobs WHERE status='rodando' AND recurso='pesado' LIMIT 1")
        if j:
            return j['titulo'] or 'outro trabalho'
        if ag.OCUPADO.locked():
            return 'Agente 1: ' + (ag.ATUAL.get('etapa') or 'cortes')
    except Exception:  # noqa: BLE001
        pass
    return ''


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
    return {'config': config(), 'lives': lives, 'ativa': (ativa() or {}).get('id', ''), 'esteira': _esteira(), 'ocupando': _ocupando()}


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
        fila.enfileirar('live.bloco', agente='agente1', dados={'live': lid, 'n': n}, recurso='pesado', prioridade=100,
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
        limpar_disco()
        if _livre() < LIVRE_MIN:
            if not obter(lid).get('sem_espaco'):
                _anotar(lid, f'Pouco espaço no celular ({_livre() // 2**20} MB livres): pausei a gravação até os blocos na fila virarem corte '
                             'e liberarem espaço. Apague vídeos antigos para liberar mais.', 'erro')
                _mudar_live(lid, lambda x: x.update(sem_espaco=True))
            time.sleep(ESPERA_ESPACO)
            continue
        if obter(lid).get('sem_espaco'):
            _mudar_live(lid, lambda x: x.update(sem_espaco=False))
            _anotar(lid, 'Espaço liberado: voltei a gravar.', 'ok')
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
        arq = pasta / f'b{prox:05d}.ts'
        dur = int(min(lv['cfg']['bloco_min'] * 60, restante))
        urls = info.get('urls') or [info['url']]
        entradas = [x for u in urls[:2] for x in ('-i', u)]
        mapas = ['-map', '0:v:0', '-map', '1:a:0'] if len(urls) > 1 else ['-map', '0:v:0?', '-map', '0:a:0?']
        # Um FFmpeg por bloco, com duração fixa: o arquivo fecha sozinho no fim do bloco (cortar uma live em pedaços
        # dentro de um FFmpeg só não fechava nunca com a live do YouTube) e o link da live é renovado a cada bloco.
        cmd = ['ffmpeg', '-nostdin', '-v', 'error', '-y', *entradas, *mapas, '-c', 'copy', '-t', str(dur), '-f', 'mpegts', str(arq)]
        log = pasta / 'ffmpeg.log'
        t0 = time.time()
        with open(log, 'wb') as fe:          # nunca em PIPE: com muito aviso o cano enche e o FFmpeg trava
            p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=fe)
        PROC[lid] = p
        alt = int(info.get('altura') or 0)
        if alt and alt != obter(lid).get('altura'):
            _anotar(lid, f'Gravando em {alt}p.' + (' O YouTube não liberou qualidade melhor para o servidor: o corte pode sair com pouca nitidez.' if alt < 720 else ''),
                    'erro' if alt < 720 else 'info')
        _mudar_live(lid, lambda x: x.update(gravando_bloco=prox, gravando_desde=t0, altura=alt or x.get('altura')))
        tam, mudou, motivo = 0, time.time(), ''
        while p.poll() is None:
            time.sleep(3)
            if obter(lid)['estado'] != 'gravando':
                p.terminate()
                break
            t = arq.stat().st_size if arq.exists() else 0
            if t != tam:
                tam, mudou = t, time.time()
            if time.time() - mudou > SEM_DADOS:
                motivo = f'A live parou de mandar vídeo por {SEM_DADOS} s.'
                p.kill()
                break
            if time.time() - t0 > dur + 180:
                p.terminate()                 # passou muito do tempo do bloco: fecha o arquivo assim mesmo
                break
        try:
            p.wait(timeout=15)
        except subprocess.TimeoutExpired:
            p.kill()
        PROC.pop(lid, None)
        err = log.read_text(errors='replace')[-300:].strip() if log.exists() else ''
        if arq.exists() and arq.stat().st_size > 200_000:
            _registrar_bloco(lid, arq)
            erros = 0
            continue
        arq.unlink(missing_ok=True)
        erros += 1
        _anotar(lid, f'O bloco {prox} não gravou (tentativa {erros} de 3). ' + (motivo or err[-160:] or 'O FFmpeg não recebeu vídeo.'), 'erro')
        if erros >= 3:
            _terminar(lid, 'A gravação falhou 3 vezes seguidas.', erro=(motivo or err or 'sem vídeo')[-200:])
            break
        time.sleep(ESPERA_ERRO)
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


def _remux(ts: Path) -> Path:
    """O pedaço gravado da live vem com os horários da transmissão (às vezes horas lá na frente): copiado para MP4 com o relógio
    zerado, a duração lida fica certa e os cortes caem no lugar. Sem recodificar (leve). Se falhar, segue com o original."""
    mp4 = ts.with_suffix('.mp4')
    r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-fflags', '+genpts', '-i', str(ts), '-map', '0:v:0?', '-map', '0:a:0?', '-c', 'copy',
                        '-avoid_negative_ts', 'make_zero', '-movflags', '+faststart', str(mp4)], capture_output=True)
    if r.returncode == 0 and mp4.exists() and mp4.stat().st_size > 100_000:
        return mp4
    mp4.unlink(missing_ok=True)
    return ts


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
    bruto = arq
    try:
        arq = _remux(bruto)
        dur = ag.duracao(arq)
        if dur < 45:
            marcar(estado='feito', msg=f'Bloco curto demais para um corte ({int(dur)} s).')
            for x in {bruto, arq}:
                x.unlink(missing_ok=True)
            return {'etapa': 'Bloco curto'}
        v = {'id': f'{lv["video_id"]}-live{n}', 'url': lv['link'], 'titulo': f'{lv["titulo"]} (live, bloco {n})', 'canal': lv['canal'],
             'canal_nome': lv['canal_nome']}
        criados = ag.processar_video(v, cfg['cortes_por_bloco'], baixado=(arq, {'title': lv['titulo'], 'duration': dur}, None),
                                     extra={'live': lid, 'live_bloco': n, 'live_fila': bool(cfg['postar']), 'direitos': lv['direitos'],
                                            'live_ini': b['ini']},
                                     ajustes={'nota_min': cfg['nota_min'], 'sem_fala': True})
    except ag.ErroAgente as e:
        marcar(estado='feito', msg=str(e)[:200])
        _anotar(lid, f'Bloco {n}: sem corte ({e}).')
        for x in {bruto, arq}:
            x.unlink(missing_ok=True)
        return {'etapa': 'Sem corte neste bloco'}
    except Exception as e:  # noqa: BLE001
        marcar(estado='erro', msg=str(e)[:200])
        _anotar(lid, f'Bloco {n}: erro: {e}', 'erro')
        raise
    finally:
        ag.etapa('')
    ok = [c for c in criados if c['status'] == 'pronto']
    marcar(estado='feito', cortes=[c['id'] for c in criados], msg=f'{len(criados)} corte(s), {len(ok)} aprovado(s) pelo diretor.')
    for x in {bruto, arq}:
        x.unlink(missing_ok=True)
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


def _livre() -> int:
    try:
        PASTA.mkdir(parents=True, exist_ok=True)
        return shutil.disk_usage(PASTA).free
    except OSError:
        return 1 << 40


def limpar_disco() -> int:
    """Apaga da memória do celular os arquivos de bloco que não vão mais virar corte: blocos já feitos ou com erro,
    sobras de lives encerradas e o MP4 de apoio. Bloco na fila ou sendo cortado fica. Devolve quantos bytes liberou."""
    liberado = 0
    try:
        lives = {x['id']: x for x in _ler()['lives']}
    except Exception:  # noqa: BLE001
        return 0
    if not PASTA.exists():
        return 0
    for pasta in PASTA.iterdir():
        if not pasta.is_dir():
            continue
        lv = lives.get(pasta.name)
        vivos = {Path(b['arquivo']).stem for b in (lv or {}).get('blocos', []) if b['estado'] in ('na_fila', 'cortando')}
        gravando = lv and lv['estado'] in ('gravando', 'terminando')
        atual = f'b{int(lv.get("gravando_bloco") or 0):05d}' if gravando else ''
        for a in pasta.iterdir():
            if a.suffix not in ('.ts', '.mp4') or a.stem in vivos or a.stem == atual:
                continue
            if gravando and a.stem not in {Path(b['arquivo']).stem for b in lv.get('blocos', [])}:
                continue                    # ainda não registrado (acabou de fechar)
            try:
                liberado += a.stat().st_size
                a.unlink()
            except OSError:
                pass
        if not gravando and not vivos and not any(pasta.glob('*.ts')):
            shutil.rmtree(pasta, ignore_errors=True)
    return liberado


def iniciar():
    """Servidor ligou: lives que estavam gravando quando ele caiu continuam (se ainda estiverem no ar)."""
    import fila
    fila.registrar('live.bloco', job_bloco, 'pesado')
    try:
        mb = limpar_disco() // 2**20
        if mb:
            print(f'live: limpeza liberou {mb} MB de blocos antigos')
    except Exception as e:  # noqa: BLE001
        print('live: limpeza', e)
    for lv in _ler()['lives']:
        if lv['estado'] == 'gravando':
            threading.Thread(target=_gravar, args=(lv['id'],), daemon=True).start()
        elif lv['estado'] == 'terminando':
            _terminar(lv['id'], lv.get('motivo_fim') or 'Gravação parada.')
