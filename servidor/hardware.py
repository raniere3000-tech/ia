"""Diagnóstico do aparelho (etapa T1 do lote 3): o que este celular tem e quanto ele aguenta de verdade.

- `ficha()`: leitura rápida e sem instalar nada: Android, Termux, processador (ARM), núcleos, memória, espaço,
  FFmpeg (versão, codificadores e filtros que o EstúdioClip usa), Python, Node, numpy, Pillow, librsvg, ImageMagick.
- `faltando()`: só os pacotes aprovados que faltam, com o comando `pkg install` pronto. Nunca instala sozinho.
- `testar()`: trabalho pesado (um por vez, pela fila): renderiza 5 s do estilo padrão e uma prévia leve (animatic
  360x640 a 8 quadros/s) e mede o tempo, a memória do aparelho no pico, o tamanho, os codecs e se o vídeo toca
  do começo ao fim (decodificação completa). O laudo fica gravado; nada aqui é chute.
- Também roda sem o servidor: `python diagnostico_aparelho.py` (ou `bash iniciar-termux.sh diagnostico`).

Medidas feitas fora do celular (computador, sandbox) NÃO valem como medida do Android: o laudo grava onde rodou
(`ambiente`) e o site só mostra "medido no celular" quando o laudo veio de um Android/Termux.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

VERSAO = 1

# pacotes do Termux que o lote 3 aprova; nada fora desta lista é sugerido
PACOTES = [
    # (pacote, como conferir, importância, para que serve)
    ('python', ('bin', 'python3'), 'necessario', 'roda o servidor'),
    ('ffmpeg', ('bin', 'ffmpeg'), 'necessario', 'faz todos os vídeos'),
    ('git', ('bin', 'git'), 'recomendado', 'baixa as atualizações do EstúdioClip'),
    ('nodejs', ('bin', 'node'), 'recomendado', 'ajuda o yt-dlp a baixar vídeos do YouTube'),
    ('python-numpy', ('py', 'numpy'), 'opcional', 'personagens em 3D (beta)'),
    ('python-pillow', ('py', 'PIL'), 'opcional', 'desenho de bonecos em SVG/recorte (próxima etapa, T2)'),
    ('librsvg', ('bin', 'rsvg-convert'), 'opcional', 'transformar desenhos SVG em quadros (próxima etapa, T2)'),
    ('imagemagick', ('bin', 'magick|convert'), 'opcional', 'ajustes de imagem fora do FFmpeg'),
]
# só com motivo e teste (o lote pede): não entram no comando pronto
SO_COM_MOTIVO = {'libcairo': 'só se o SVG precisar de cairo', 'sox': 'só se faltar algum efeito de áudio no FFmpeg',
                 'chromium / x11': 'não usado: o render não depende de navegador'}

# o que o motor de vídeo usa de verdade (estilos_codigo, renderizador, exportacao, diretor)
CODIFICADORES = ['libx264', 'aac', 'pcm_s16le', 'png', 'mjpeg']
FILTROS = ['scale', 'crop', 'format', 'fade', 'drawbox', 'gblur', 'eq', 'overlay', 'zoompan', 'vignette', 'rotate', 'noise', 'split',
           'colorchannelmixer', 'subtitles', 'ass', 'perspective', 'loudnorm', 'drawtext', 'boxblur', 'amix', 'afade', 'xfade',
           'silencedetect', 'sidechaincompress', 'palettegen', 'paletteuse', 'hue', 'freezedetect', 'concat', 'blackdetect', 'aevalsrc']


def _cmd(args: list, tempo: float = 10) -> str:
    try:
        r = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True, text=True, errors='replace', timeout=tempo)
        return (r.stdout or '') + (r.stderr or '')
    except (OSError, subprocess.SubprocessError):
        return ''


def _getprop(nome: str) -> str:
    return _cmd(['getprop', nome], 3).strip() if shutil.which('getprop') else ''


def e_android() -> bool:
    return bool(os.getenv('TERMUX_VERSION') or os.getenv('PREFIX', '').startswith('/data/data/com.termux') or _getprop('ro.build.version.release'))


def _ler(arq: str) -> str:
    try:
        return Path(arq).read_text(encoding='utf-8', errors='replace').strip()
    except OSError:
        return ''


def memoria() -> dict | None:
    t = _ler('/proc/meminfo')
    if not t:
        return None
    info = {}
    for ln in t.splitlines():
        p = ln.split()
        if len(p) >= 2 and p[1].isdigit():
            info[p[0].rstrip(':')] = int(p[1]) // 1024
    return {'total_mb': info.get('MemTotal', 0), 'livre_mb': info.get('MemAvailable', info.get('MemFree', 0)),
            'troca_mb': info.get('SwapTotal', 0)}


def processador() -> dict:
    cpu = _ler('/proc/cpuinfo')
    modelo = ''
    for chave in ('Hardware', 'model name', 'Processor'):
        m = re.search(rf'^{chave}\s*:\s*(.+)$', cpu, re.M)
        if m:
            modelo = m.group(1).strip()
            break
    freqs = []
    for f in sorted(Path('/sys/devices/system/cpu').glob('cpu[0-9]*/cpufreq/cpuinfo_max_freq')):
        try:
            freqs.append(int(f.read_text().strip()) // 1000)
        except (OSError, ValueError):
            pass
    try:
        uso = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        uso = None
    carga = None
    try:
        carga = round(os.getloadavg()[0], 2)
    except (OSError, AttributeError):
        pass
    return {'arquitetura': platform.machine(), 'modelo': modelo or _getprop('ro.soc.model') or _getprop('ro.board.platform'),
            'nucleos': os.cpu_count(), 'nucleos_liberados': uso, 'mhz_max': max(freqs) if freqs else None,
            'mhz_por_nucleo': freqs or None, 'carga_1min': carga}


def ffmpeg_info() -> dict:
    if not shutil.which('ffmpeg'):
        return {'instalado': False}
    v = _cmd(['ffmpeg', '-hide_banner', '-version'])
    linha = v.splitlines()[0] if v else ''
    enc = _cmd(['ffmpeg', '-hide_banner', '-encoders'])
    fil = _cmd(['ffmpeg', '-hide_banner', '-filters'])
    tem_enc = {c: bool(re.search(rf'^\s*\S+\s+{re.escape(c)}\s', enc, re.M)) for c in CODIFICADORES}
    tem_fil = {f: bool(re.search(rf'^\s*\S+\s+{re.escape(f)}\s', fil, re.M)) for f in FILTROS}
    return {'instalado': True, 'versao': linha.replace('ffmpeg version', '').split(' Copyright')[0].strip()[:80],
            'faltam_codificadores': [c for c, ok in tem_enc.items() if not ok],
            'faltam_filtros': [f for f, ok in tem_fil.items() if not ok],
            'ffprobe': bool(shutil.which('ffprobe'))}


def _tem(como: tuple) -> str | None:
    tipo, nome = como
    if tipo == 'bin':
        for n in nome.split('|'):
            if shutil.which(n):
                return n
        return None
    try:
        mod = __import__(nome)
        return getattr(mod, '__version__', 'sim')
    except Exception:  # noqa: BLE001
        return None


def faltando() -> dict:
    itens = []
    for pac, como, imp, para in PACOTES:
        achou = _tem(como)
        itens.append({'pacote': pac, 'tem': bool(achou), 'versao': achou if isinstance(achou, str) and como[0] == 'py' else None,
                      'importancia': imp, 'para': para})
    falta_nec = [i['pacote'] for i in itens if not i['tem'] and i['importancia'] in ('necessario', 'recomendado')]
    falta_opc = [i['pacote'] for i in itens if not i['tem'] and i['importancia'] == 'opcional']
    return {'itens': itens,
            'comando': ('pkg install -y ' + ' '.join(falta_nec)) if falta_nec else '',
            'comando_opcional': ('pkg install -y ' + ' '.join(falta_opc)) if falta_opc else '',
            'so_com_motivo': SO_COM_MOTIVO}


def _versao(args: list) -> str | None:
    if not shutil.which(args[0]):
        return None
    s = _cmd(args).strip().splitlines()
    return s[0][:60] if s else None


def ficha() -> dict:
    """Leitura rápida (uns 2 s), sem instalar nem renderizar nada."""
    from pathlib import Path as _P
    dados = _P(os.getenv('DADOS', str(_P.home() / '.estudioclip')))
    livre = total = None
    try:
        u = shutil.disk_usage(dados if dados.exists() else _P.home())
        livre, total = u.free // 1048576, u.total // 1048576
    except OSError:
        pass
    limites = {}
    try:
        import resource
        for nome, k in (('arquivos_abertos', 'RLIMIT_NOFILE'), ('processos', 'RLIMIT_NPROC')):
            if hasattr(resource, k):
                s, _h = resource.getrlimit(getattr(resource, k))
                limites[nome] = None if s == resource.RLIM_INFINITY else s
    except ImportError:
        pass
    android = e_android()
    return {
        'versao_diagnostico': VERSAO, 'quando': time.time(),
        'ambiente': 'android' if android else 'outro (computador ou servidor: não vale como medida do celular)',
        'android': {'versao': _getprop('ro.build.version.release') or None, 'sdk': _getprop('ro.build.version.sdk') or None,
                    'aparelho': ' '.join(x for x in (_getprop('ro.product.manufacturer'), _getprop('ro.product.model')) if x) or None,
                    'termux': os.getenv('TERMUX_VERSION') or None} if android else None,
        'sistema': f'{platform.system()} {platform.release()}',
        'processador': processador(),
        'memoria': memoria(),
        'espaco': {'livre_mb': livre, 'total_mb': total, 'pasta': str(dados)},
        'limites': limites,
        'ffmpeg': ffmpeg_info(),
        'python': sys.version.split()[0],
        'node': _versao(['node', '--version']),
        'git': _versao(['git', '--version']),
        'pacotes': faltando(),
    }


# ---------------------------------------------------------------- medida de memória durante o teste
class Medidor:
    """Lê, a cada 0,25 s, a memória livre do aparelho e a memória dos processos filhos (FFmpeg) deste programa."""

    def __init__(self):
        self.parar = threading.Event()
        m = memoria()
        self.livre_inicio = m['livre_mb'] if m else None
        self.livre_min = self.livre_inicio
        self.filhos_max = 0.0
        self.proprio_max = 0.0
        self.t = threading.Thread(target=self._laco, daemon=True)

    def _rss_filhos(self) -> float:
        meu = os.getpid()
        tot = 0
        filhos = {meu}
        try:
            procs = [p for p in os.listdir('/proc') if p.isdigit()]
        except OSError:
            return 0.0
        pais = {}
        for p in procs:
            st = _ler(f'/proc/{p}/stat')
            if st:
                try:
                    pais[int(p)] = int(st.rsplit(')', 1)[1].split()[1])
                except (IndexError, ValueError):
                    pass
        mudou = True
        while mudou:   # netos também (FFmpeg chamado por um shell)
            mudou = False
            for pid, pai in pais.items():
                if pai in filhos and pid not in filhos:
                    filhos.add(pid)
                    mudou = True
        for pid in filhos - {meu}:
            m = re.search(r'VmRSS:\s+(\d+)', _ler(f'/proc/{pid}/status'))
            if m:
                tot += int(m.group(1))
        return tot / 1024

    def _laco(self):
        while not self.parar.is_set():
            m = memoria()
            if m and self.livre_min is not None:
                self.livre_min = min(self.livre_min, m['livre_mb'])
            self.filhos_max = max(self.filhos_max, self._rss_filhos())
            r = re.search(r'VmRSS:\s+(\d+)', _ler('/proc/self/status'))
            if r:
                self.proprio_max = max(self.proprio_max, int(r.group(1)) / 1024)
            self.parar.wait(0.25)

    def __enter__(self):
        self.t.start()
        return self

    def __exit__(self, *a):
        self.parar.set()
        self.t.join(2)

    def resultado(self) -> dict:
        return {'ffmpeg_pico_mb': round(self.filhos_max, 1) if self.filhos_max else None,
                'programa_pico_mb': round(self.proprio_max, 1) if self.proprio_max else None,
                'aparelho_livre_inicio_mb': self.livre_inicio, 'aparelho_livre_minimo_mb': self.livre_min}


# ---------------------------------------------------------------- os testes de render
def _toca(arq: Path, cancelado=None) -> dict:
    """Decodifica o vídeo inteiro (como um player faria). Erro de decodificação = não toca."""
    import renderizador as rd
    t0 = time.time()
    try:
        saida = rd.rodar(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(arq), '-f', 'null', '-'], cancelado, tempo_max=300)
        erros = [ln for ln in (saida or '').splitlines() if ln.strip()][:5]
        return {'toca': not erros, 'erros': erros, 'segundos': round(time.time() - t0, 2)}
    except Exception as e:  # noqa: BLE001
        return {'toca': False, 'erros': [str(e)[:300]], 'segundos': round(time.time() - t0, 2)}


def _sobre(arq: Path) -> dict:
    import renderizador as rd
    info = rd.sonda(arq)
    v = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), {})
    a = next((s for s in info.get('streams', []) if s.get('codec_type') == 'audio'), {})
    return {'tamanho_kb': round(arq.stat().st_size / 1024, 1), 'duracao': round(float(info.get('format', {}).get('duration') or 0), 2),
            'video': f"{v.get('codec_name', '?')} {v.get('width', '?')}x{v.get('height', '?')} {v.get('pix_fmt', '')}".strip() if v else None,
            'audio': f"{a.get('codec_name', '?')} {a.get('sample_rate', '')} Hz".strip() if a else None}


ESTILO_TESTE = 'documentario'


def _um_teste(nome: str, titulo: str, pasta: Path, W: int, H: int, fps: int, cancelado, log) -> dict:
    import estilos_codigo as ec
    import renderizador as rd
    pasta.mkdir(parents=True, exist_ok=True)
    saida = pasta / f'{nome}.mp4'
    saida.unlink(missing_ok=True)
    eid = ESTILO_TESTE if ec.utilizavel(ESTILO_TESTE, False) else 'vetor_chapado'
    cena = ec.demo_cena(eid, '')
    # voz de mentira (tom variando) só para o teste ter áudio e o vídeo final ser conferido com som
    fala = pasta / f'{nome}-som.wav'
    rd.rodar(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i',
              "aevalsrc='0.4*sin(2*PI*(220+120*sin(2*PI*0.5*t))*t)':s=24000:d=5", '-ac', '1', '-c:a', 'pcm_s16le', str(fala)], tempo_max=60)
    log(f'{titulo}: estilo {eid}, {W}x{H}, {fps} quadros/s')
    trava = getattr(sys.modules.get('diretor'), '_TRAVA_FPS', None) or threading.Lock()
    trava.acquire()    # o número de quadros por segundo é global no motor: ninguém renderiza no meio da troca
    antes = ec.FPS
    ec.FPS = fps
    t0 = time.time()
    try:
        with Medidor() as med:
            ec.preparar(eid, W, H, 5.0, None, cancelado, cena=cena)
            cmd = ec.montar(eid, cena, W, H, 5.0, pasta, None, fala, saida)
            rd.rodar(cmd, cancelado, tempo_max=900)
        seg = time.time() - t0
    except Exception as e:  # noqa: BLE001
        log(f'{titulo}: FALHOU depois de {time.time() - t0:.1f} s: {e}')
        return {'nome': nome, 'titulo': titulo, 'ok': False, 'erro': str(e)[:500], 'segundos': round(time.time() - t0, 1)}
    finally:
        ec.FPS = antes
        trava.release()
    r = {'nome': nome, 'titulo': titulo, 'estilo': eid, 'resolucao': f'{W}x{H}', 'fps': fps, 'segundos': round(seg, 2),
         'seg_por_seg': round(seg / 5.0, 2), 'memoria': med.resultado(), **_sobre(saida)}
    conf = rd.conferir(saida, pasta, {'largura': W, 'altura': H, 'duracao': 5.0}, cancelado)
    r['conferencia'] = {'ok': conf['ok'], 'erros': conf['erros'], 'avisos': conf['avisos']}
    r['reproducao'] = _toca(saida, cancelado)
    r['ok'] = bool(conf['ok'] and r['reproducao']['toca'])
    r['arquivo'] = str(saida)
    log(f"{titulo}: {'ok' if r['ok'] else 'COM PROBLEMA'} em {seg:.1f} s ({r['seg_por_seg']} s por segundo de vídeo), "
        f"{r['tamanho_kb']} KB, FFmpeg no pico {r['memoria']['ffmpeg_pico_mb']} MB")
    return r


def testar(pasta: Path, cancelado=None, progresso=None, log=None) -> dict:
    """Renderiza 5 s no tamanho final (1080x1920) e uma prévia leve (360x640, 8 quadros/s). Uma coisa por vez."""
    import estilos_codigo as ec
    linhas: list = []

    def _log(msg):
        linha = time.strftime('%H:%M:%S ') + msg
        linhas.append(linha)
        if log:
            log(linha)
    ficha_ = ficha()
    _log(f"Aparelho: {ficha_['ambiente']}; {ficha_['processador']['arquitetura']}, {ficha_['processador']['nucleos']} núcleos")
    W, H = ec.FORMATOS['9:16']
    testes = []
    for k, (nome, titulo, w, h, fps) in enumerate((('render5s', 'Render de 5 segundos (tamanho final)', W, H, ec.FPS),
                                                    ('animatic', 'Prévia leve (animatic)', 360, 640, 8))):
        if cancelado and cancelado():
            break
        if progresso:
            progresso(10 + 45 * k, titulo)
        testes.append(_um_teste(nome, titulo, pasta, w, h, fps, cancelado, _log))
    ok = bool(testes) and all(t.get('ok') for t in testes)
    laudo = {'versao': VERSAO, 'quando': time.time(), 'ficha': ficha_, 'testes': testes, 'ok': ok,
             'medido_no_celular': ficha_['ambiente'] == 'android',
             'estado': ('medido no celular' if ficha_['ambiente'] == 'android' else 'aguardando teste no Android'),
             'log': linhas}
    try:
        (pasta / 'laudo.json').write_text(json.dumps(laudo, ensure_ascii=False, indent=1), encoding='utf-8')
        (pasta / 'laudo.log').write_text('\n'.join(linhas) + '\n', encoding='utf-8')
    except OSError:
        pass
    return laudo


# ---------------------------------------------------------------- ligação com o servidor (fila + banco)
def ultimo_laudo() -> dict | None:
    import banco as db
    return db.kv('diagnostico_aparelho') or None


def job_testar(ctx):
    import banco as db
    import fila
    import postagem as pg
    pasta = pg.DADOS / 'diagnostico'
    laudo = testar(pasta, ctx.cancelado, ctx.progresso)
    if ctx.cancelado():
        raise fila.Cancelado()
    for t in laudo['testes']:
        if t.get('ok'):
            fila.medir('diagnostico_' + t['nome'], t['segundos'], 5.0)
        t.pop('arquivo', None)   # caminho interno não vai para o site
    db.kv_gravar('diagnostico_aparelho', laudo)
    return {'resultado': {'ok': laudo['ok'], 'estado': laudo['estado']}, 'etapa': 'Teste do aparelho pronto'}


def pedir_teste() -> dict:
    import banco as db
    import fila
    ja = db.um("SELECT id, status FROM jobs WHERE tipo='aparelho.testar' AND status IN ('na_fila','agendado','rodando') LIMIT 1")
    if ja:      # já tem um teste andando: não começa outro
        return {'job': ja['id'], 'status': ja['status']}
    j = fila.enfileirar('aparelho.testar', agente='sistema', titulo='Teste do aparelho (5 s + prévia leve)',
                        chave=f'aparelho-{int(time.time() // 60)}', prioridade=3, max_tentativas=1)
    return {'job': j['id'], 'status': j['status']}


def iniciar():
    import fila
    fila.registrar('aparelho.testar', job_testar, 'pesado')
    fila.registrar('aparelho.testar3d', job_testar_3d, 'pesado')


# ---------------------------------------------------------------- T7: 3D só depois do 2D, com medida real
def videos_3d() -> list:
    """Acha os vídeos 3D que já foram feitos neste aparelho (cache das cenas 3D, fundos 3D, demonstração, teste do
    comando de medida) para revisar. Não apaga nem move nada: só lista e registra para tocar no site."""
    import postagem as pg
    base = pg.DADOS
    achados = []
    fontes = [('personagens 3D (cena)', base / 'cache3d' / 'cenas', '*.mp4'), ('fundo 3D em loop', base / 'cache3d', '*.mp4'),
              ('demonstração 3D', base / 'demos', 'animado3d*/demo.mp4'), ('teste de medida', Path.home(), 'estudioclip-3d-teste*.mp4')]
    for tipo, pasta, padrao in fontes:
        if not pasta.exists():
            continue
        for a in pasta.glob(padrao):
            try:
                st = a.stat()
            except OSError:
                continue
            if st.st_size > 1000:
                achados.append({'tipo': tipo, 'arquivo': a, 'tamanho_kb': round(st.st_size / 1024), 'criado': st.st_mtime})
    achados.sort(key=lambda x: x['criado'])
    return achados


def registrar_videos_3d() -> list:
    """Registra os vídeos 3D achados como mídia do servidor (o site pode tocar), o mais antigo primeiro."""
    import projetos as pj
    import renderizador as rd
    out = []
    for k, v in enumerate(videos_3d()[:30]):
        a = pj.registrar_asset(v['arquivo'], f'3d-{k + 1}-{v["arquivo"].stem[:24]}.mp4', 'video/mp4', '', 'revisao3d')['asset']
        try:
            dur = round(rd.duracao(v['arquivo']), 2)
        except Exception:  # noqa: BLE001
            dur = None
        out.append({'asset': a['id'], 'tipo': v['tipo'], 'tamanho_kb': v['tamanho_kb'], 'criado': v['criado'], 'duracao': dur, 'primeiro': k == 0})
    return out


def testar_3d(pasta: Path, cancelado=None, progresso=None) -> dict:
    """Mede o 3D de personagens contra o loop 3D atual (fundo) e o 2D articulado, na MESMA cena de 5 s:
    tempo, memória no pico, tamanho e conferência. Só vale como medida do Android se rodar no celular."""
    import estilos_codigo as ec
    import personagens3d as p3
    import renderizador as rd
    pasta.mkdir(parents=True, exist_ok=True)
    W, H = ec.FORMATOS['9:16']
    res = {'ambiente': 'android' if e_android() else 'outro', 'quando': time.time(), 'testes': []}
    if not p3.disponivel():
        res['erro'] = 'Falta o numpy (pkg install -y python-numpy).'
        res['estado'] = 'indisponivel'
        return res
    fala = pasta / 'fala.wav'
    rd.rodar(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i',
              "aevalsrc='0.6*sin(2*PI*(220+180*sin(2*PI*0.7*t))*t)*max(0,sin(2*PI*3.3*t))*lt(mod(t,1.6),1.2)':s=24000:d=5",
              '-ac', '1', '-c:a', 'pcm_s16le', str(fala)], tempo_max=60)
    for k, (eid, nome) in enumerate((('animado2d', '2D articulado (referência)'), ('animado3d', 'Personagens 3D'), ('cinema3d', 'Loop 3D atual (fundo)'))):
        if cancelado and cancelado():
            break
        if not ec.utilizavel(eid, False):
            res['testes'].append({'estilo': eid, 'nome': nome, 'ok': False, 'erro': 'não disponível neste aparelho'})
            continue
        if progresso:
            progresso(5 + 30 * k, nome)
        cena = ec.demo_cena(eid)
        cena['_audio'] = str(fala)
        saida = pasta / f'{eid}.mp4'
        t0 = time.time()
        try:
            with Medidor() as med:
                ec.preparar(eid, W, H, 5.0, None, cancelado, cena=cena)
                rd.rodar(ec.montar(eid, cena, W, H, 5.0, pasta, None, fala, saida), cancelado, tempo_max=3600)
            seg = time.time() - t0
            conf = rd.conferir(saida, pasta, {'largura': W, 'altura': H, 'duracao': 5.0}, cancelado)
            res['testes'].append({'estilo': eid, 'nome': nome, 'ok': conf['ok'], 'segundos': round(seg, 1), 'seg_por_seg': round(seg / 5, 2),
                                  'memoria': med.resultado(), 'tamanho_kb': round(saida.stat().st_size / 1024), 'erros': conf['erros'], 'avisos': conf['avisos'],
                                  'arquivo': str(saida)})
        except Exception as e:  # noqa: BLE001
            res['testes'].append({'estilo': eid, 'nome': nome, 'ok': False, 'erro': str(e)[:300], 'segundos': round(time.time() - t0, 1)})
    t3 = next((t for t in res['testes'] if t['estilo'] == 'animado3d'), {})
    t2 = next((t for t in res['testes'] if t['estilo'] == 'animado2d'), {})
    if not t3.get('ok'):
        res['estado'] = 'indisponivel'
        res['conclusao'] = 'O 3D com personagens não terminou neste aparelho: fica indisponível.'
    elif res['ambiente'] != 'android':
        res['estado'] = 'beta'
        res['conclusao'] = 'Medido fora do celular: não serve para decidir. Rode no Termux.'
    else:
        lento = t3['seg_por_seg']
        res['estado'] = 'beta' if lento <= LIMITE_3D_VIAVEL else 'beta_lento'
        res['conclusao'] = (f'No celular o 3D levou {lento} s por segundo de vídeo'
                            + (f' ({lento / max(0.01, t2.get("seg_por_seg") or 0.01):.1f}x o 2D)' if t2.get('ok') else '')
                            + ('. Dá para usar em vídeos curtos.' if lento <= LIMITE_3D_VIAVEL else
                               f'. Acima de {LIMITE_3D_VIAVEL} s por segundo: um vídeo de 45 s levaria mais de '
                               f'{LIMITE_3D_VIAVEL * 45 / 60:.0f} min. Fica em beta, só para cenas curtas.'))
    (pasta / 'laudo-3d.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    return res


LIMITE_3D_VIAVEL = float(os.getenv('LIMITE_3D_VIAVEL', '20'))   # s de render por s de vídeo acima disso: lento demais para o dia a dia


def job_testar_3d(ctx):
    import banco as db
    import fila
    import postagem as pg
    r = testar_3d(pg.DADOS / 'diagnostico' / '3d', ctx.cancelado, ctx.progresso)
    if ctx.cancelado():
        raise fila.Cancelado()
    import projetos as pj
    for t in r['testes']:
        arq = t.pop('arquivo', None)
        if arq and t.get('ok'):
            t['asset'] = pj.registrar_asset(Path(arq), f'teste3d-{t["estilo"]}.mp4', 'video/mp4', '', 'revisao3d')['asset']['id']
    db.kv_gravar('diagnostico_3d', r)
    return {'resultado': {'estado': r['estado']}, 'etapa': 'Teste do 3D pronto'}


def pedir_teste_3d() -> dict:
    import banco as db
    import fila
    ja = db.um("SELECT id, status FROM jobs WHERE tipo='aparelho.testar3d' AND status IN ('na_fila','agendado','rodando') LIMIT 1")
    if ja:
        return {'job': ja['id'], 'status': ja['status']}
    j = fila.enfileirar('aparelho.testar3d', agente='sistema', titulo='Teste do 3D (2D x 3D x loop 3D)', chave=f'a3d-{int(time.time() // 60)}',
                        prioridade=2, max_tentativas=1)
    return {'job': j['id'], 'status': j['status']}
