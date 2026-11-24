"""Render e conferência dos vídeos no servidor (FFmpeg/FFprobe), sem depender do navegador.

- Cada comando roda como subprocesso que pode ser interrompido (cancelar não corrompe o arquivo final).
- O arquivo é gravado com nome temporário e só ganha o nome final depois de conferido (troca atômica).
- A conferência olha codec, resolução, duração, áudio e quadros do começo, meio e fim; tela preta,
  imagem congelada e silêncio viram AVISOS (uma cena escura de propósito não reprova o vídeo).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path


class ErroRender(Exception):
    pass


# Quanto tempo o FFmpeg pode ficar SEM AVANÇAR (nenhum quadro novo, nada gravado) antes de ser considerado travado.
FFMPEG_PARADO_S = float(os.environ.get('FFMPEG_PARADO_S') or 600)
# Enquanto o FFmpeg está avançando, o limite de tempo de cada comando é multiplicado por este fator
# (celular lento demora mais, mas não está travado; antes ele era morto no meio e o trabalho falhava 3 vezes).
FFMPEG_FATOR_TEMPO = float(os.environ.get('FFMPEG_FATOR_TEMPO') or 4)


def _min(seg: float) -> str:
    return f'{seg / 60:.0f} min' if seg >= 90 else f'{seg:.0f} s'


def rodar(cmd: list, cancelado=None, tempo_max: float = 3600, progresso=None, dur: float = 0, etapa: str = '') -> str:
    """Roda o FFmpeg; se `cancelado()` ficar verdadeiro, encerra com calma (sem deixar arquivo pela metade).

    Tempo: o FFmpeg informa o avanço (-progress). Enquanto ele avança, pode passar de `tempo_max` até
    `tempo_max × FFMPEG_FATOR_TEMPO`; se ficar FFMPEG_PARADO_S sem avançar, é tratado como travado.
    Sem informação de avanço (outro programa), vale `tempo_max` como antes. `etapa` entra na mensagem de erro."""
    eh_ffmpeg = bool(cmd) and Path(str(cmd[0])).name in ('ffmpeg', 'ffmpeg.exe')
    acompanha = eh_ffmpeg and '-progress' not in cmd
    if acompanha:
        cmd = cmd[:1] + ['-progress', 'pipe:1', '-nostats'] + cmd[1:]
    p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE if acompanha else subprocess.DEVNULL, stderr=subprocess.PIPE,
                         text=True, errors='replace')
    inicio = time.time()

    def _matar():
        p.kill()
    # o stderr é lido numa linha separada: se ficar cheio (FFmpeg repetindo o mesmo erro), o FFmpeg travaria parado
    cauda: list = []
    av = {'ultimo': inicio, 'fracao': None, 'teve': False}

    def _ler_erros():
        for ln in p.stderr:
            cauda.append(ln)
            if len(cauda) > 200:
                del cauda[:100]

    def _ler_avanco():
        vistos: dict = {}
        for ln in p.stdout:
            k, _, v = ln.strip().partition('=')
            if k in ('out_time_ms', 'out_time_us', 'frame', 'total_size') and v.isdigit():
                n = int(v)
                if n > vistos.get(k, -1):
                    if k in vistos or n > 0:
                        av['ultimo'] = time.time()
                        av['teve'] = True
                    vistos[k] = n
                if k in ('out_time_ms', 'out_time_us') and dur > 0:
                    av['fracao'] = min(1.0, n / 1e6 / dur)
    leitores = [threading.Thread(target=_ler_erros, daemon=True)]
    if acompanha:
        leitores.append(threading.Thread(target=_ler_avanco, daemon=True))
    for t in leitores:
        t.start()
    onde = f' ({etapa})' if etapa else ''
    parado_max = min(FFMPEG_PARADO_S, max(30.0, tempo_max))
    limite = tempo_max * (max(1.0, FFMPEG_FATOR_TEMPO) if acompanha else 1.0)
    ultima_fracao = None
    try:
        while p.poll() is None:
            if cancelado and cancelado():
                p.terminate()
                break
            agora = time.time()
            if progresso and av['fracao'] is not None and av['fracao'] != ultima_fracao:
                ultima_fracao = av['fracao']
                progresso(ultima_fracao)
            feito = f', parou em {av["fracao"] * 100:.0f}%' if av['fracao'] else ''
            if acompanha and agora - av['ultimo'] > parado_max:
                _matar()
                raise ErroRender(f'O FFmpeg travou{onde}: ficou {_min(agora - av["ultimo"])} sem produzir nada{feito}.')
            if agora - inicio > limite:
                _matar()
                raise ErroRender(f'O FFmpeg passou do tempo máximo{onde}: {_min(agora - inicio)} rodando{feito}. '
                                 'O aparelho está lento demais para este trecho; tente uma qualidade menor ou um vídeo mais curto.')
            time.sleep(0.3)
    finally:
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _matar()
            p.wait(timeout=10)
        for t in leitores:
            t.join(timeout=5)
        if p.stdout is not None:
            p.stdout.close()
        if p.stderr is not None:
            p.stderr.close()
    if progresso and dur > 0 and p.returncode == 0:
        progresso(1.0)
    erro = ''.join(cauda)
    if p.returncode != 0:
        if cancelado and cancelado():
            raise InterruptedError('cancelado')
        raise ErroRender('FFmpeg falhou' + onde + ': ' + (erro.strip().splitlines() or ['sem detalhe'])[-1][:400])
    return erro


def sonda(arq: Path) -> dict:
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(arq)],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
    if r.returncode != 0:
        raise ErroRender('O arquivo não abre (FFprobe): ' + r.stderr.strip()[-200:])
    return json.loads(r.stdout or '{}')


def duracao(arq: Path) -> float:
    try:
        return float(sonda(arq).get('format', {}).get('duration') or 0)
    except (ErroRender, ValueError, subprocess.TimeoutExpired):
        return 0.0


def sha256(arq: Path) -> str:
    h = hashlib.sha256()
    with open(arq, 'rb') as f:
        for bloco in iter(lambda: f.read(1 << 20), b''):
            h.update(bloco)
    return h.hexdigest()


def concatenar(clipes: list[Path], saida: Path, pasta: Path, cancelado=None):
    lista = pasta / 'lista.txt'
    lista.write_text(''.join(f"file '{str(c).replace(chr(39), '')}'\n" for c in clipes), encoding='utf-8')
    rodar(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(lista), '-c', 'copy', '-movflags', '+faststart', str(saida)], cancelado, etapa='juntando as cenas')


def mixar_trilha(video: Path, trilha: Path | None, saida: Path, cancelado=None, volume: float = 0.18):
    """Trilha de fundo que abaixa sozinha quando tem voz (ducking) e volume final normalizado."""
    if trilha:
        filtro = (f'[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={volume}[m];'
                  f'[0:a]asplit[v1][v2];[m][v2]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[md];'
                  f'[v1][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]')
        cmd = ['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(video), '-stream_loop', '-1', '-i', str(trilha), '-filter_complex', filtro,
               '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-shortest', '-movflags', '+faststart', str(saida)]
    else:
        cmd = ['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(video), '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-c:v', 'copy',
               '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-movflags', '+faststart', str(saida)]
    rodar(cmd, cancelado, etapa='misturando a trilha')


def quadros(video: Path, pasta: Path, dur: float) -> list[Path]:
    """Quadros do começo, meio e fim (para conferir e para a miniatura)."""
    out = []
    for nome, t in (('inicio', min(0.5, dur * 0.1)), ('meio', dur / 2), ('fim', max(0, dur - 0.5))):
        arq = pasta / f'quadro-{nome}.jpg'
        subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-ss', f'{t:.2f}', '-i', str(video), '-frames:v', '1', '-vf', 'scale=360:-2', '-q:v', '4', str(arq)],
                       capture_output=True, stdin=subprocess.DEVNULL, timeout=120)
        if arq.exists() and arq.stat().st_size > 500:
            out.append(arq)
    return out


def capa(video: Path, arq: Path, t: float) -> bool:
    """Um quadro do vídeo para servir de capa (miniatura)."""
    subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-ss', f'{max(0, t):.2f}', '-i', str(video), '-frames:v', '1', '-vf', "scale='min(720,iw)':-2", '-q:v', '3', str(arq)],
                   capture_output=True, stdin=subprocess.DEVNULL, timeout=120)
    return arq.exists() and arq.stat().st_size > 500


def conferir(video: Path, pasta: Path, esperado: dict, cancelado=None) -> dict:
    """Confere o vídeo final. Erros reprovam; avisos só informam."""
    info = sonda(video)
    v = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), None)
    a = next((s for s in info.get('streams', []) if s.get('codec_type') == 'audio'), None)
    dur = float(info.get('format', {}).get('duration') or 0)
    erros, avisos = [], []
    if not v:
        erros.append('O arquivo não tem imagem.')
    if not a:
        erros.append('O arquivo não tem som.')
    if v and (int(v.get('width', 0)), int(v.get('height', 0))) != (esperado.get('largura'), esperado.get('altura')):
        erros.append(f'Tamanho {v.get("width")}x{v.get("height")} diferente do pedido {esperado.get("largura")}x{esperado.get("altura")}.')
    alvo = esperado.get('duracao') or 0
    if alvo and abs(dur - alvo) > max(1.0, alvo * 0.05):
        erros.append(f'Duração {dur:.1f}s diferente do esperado ({alvo:.1f}s).')
    if v and v.get('codec_name') != 'h264':
        avisos.append(f'Codec de vídeo {v.get("codec_name")} (o esperado é H.264).')
    if a and a.get('codec_name') != 'aac':
        avisos.append(f'Codec de áudio {a.get("codec_name")} (o esperado é AAC).')
    # tela preta, imagem congelada e silêncio (análise em tamanho pequeno para ser leve no celular)
    analise = ''
    analise_ok = True
    try:
        analise = rodar(['ffmpeg', '-nostdin', '-v', 'info', '-i', str(video), '-vf', 'scale=270:-2,blackdetect=d=1.0:pic_th=0.97,freezedetect=n=0.002:d=4',
                         '-af', 'silencedetect=n=-50dB:d=3,volumedetect', '-f', 'null', '-'], cancelado, tempo_max=1800, etapa='conferindo tela preta e silêncio')
    except ErroRender as e:
        analise_ok = False
        avisos.append('Não deu para analisar tela preta/congelada: ' + str(e)[:120])
    # falha de decodificação (o player travaria): o decodificador reclama durante a mesma leitura da análise
    ruins = [ln.strip() for ln in analise.splitlines()
             if re.search(r'error while decoding|corrupt|invalid nal|concealing|missing picture', ln, re.I)]
    if ruins:
        erros.append(f'O vídeo tem {len(ruins)} erro(s) de decodificação (ex.: {ruins[0][:120]}).')
    dts = [ln for ln in analise.splitlines() if re.search(r'non[- ]monoton', ln, re.I)]
    if dts:      # carimbo de tempo repetido na junção das cenas: os players toleram, mas fica registrado
        avisos.append(f'{len(dts)} carimbo(s) de tempo repetido(s) na junção das cenas.')
    # carimbos de tempo: som e imagem com durações bem diferentes = dessincronia ou trecho faltando
    dv, da = float((v or {}).get('duration') or 0), float((a or {}).get('duration') or 0)
    if dv and da and abs(dv - da) > 0.5:
        avisos.append(f'Som ({da:.2f}s) e imagem ({dv:.2f}s) com durações diferentes.')
    if v and float(v.get('start_time') or 0) > 0.2:
        avisos.append(f'A imagem começa atrasada ({float(v["start_time"]):.2f}s).')
    # exportação completa: quadros gravados x esperados pela duração
    try:
        nq = int(v.get('nb_frames') or 0) if v else 0
        num, den = (v.get('avg_frame_rate') or '0/1').split('/') if v else ('0', '1')
        fps = float(num) / float(den or 1) if float(den or 1) else 0
    except (ValueError, ZeroDivisionError):
        nq, fps = 0, 0
    if nq and fps and dv and nq < dv * fps * 0.9:
        erros.append(f'Faltam quadros: {nq} gravados para {dv * fps:.0f} esperados.')
    if esperado.get('srt'):
        erros += conferir_srt(Path(esperado['srt']), dur)
    pretos = re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', analise)
    congel = re.findall(r'freeze_duration: ([\d.]+)', analise)
    silencio = re.findall(r'silence_duration: ([\d.]+)', analise)
    if pretos:
        avisos.append('Trecho preto: ' + ', '.join(f'{float(a):.1f}s–{float(b):.1f}s' for a, b in pretos[:4]))
    if congel:
        avisos.append(f'Imagem parada por {max(float(x) for x in congel):.1f}s (normal em cenas sem movimento).')
    if silencio:
        avisos.append(f'Silêncio de {max(float(x) for x in silencio):.1f}s.')
    # O detector não emite freeze_end quando a imagem fica parada até o EOF.
    congelamentos, inicio = [], None
    for evento, valor in re.findall(r'freeze_(start|end): ([\d.]+)', analise):
        if evento == 'start':
            inicio = float(valor)
        elif inicio is not None:
            congelamentos.append([inicio, float(valor)])
            inicio = None
    if inicio is not None:
        congelamentos.append([inicio, dur])
    pretos = [[float(x), float(y)] for x, y in pretos]

    def previsto(intervalo, permitidos):
        # Só permite o trecho explicitamente previsto no manifesto, não o vídeo inteiro.
        cursor, fim = intervalo
        for ini, ate in sorted(permitidos):
            if ini > cursor + .2:
                break
            if ate >= cursor:
                cursor = ate
            if cursor >= fim - .2:
                return True
        return False

    def volume(nome):
        m = re.search(rf'{nome}_volume: (-?[\d.]+|-inf) dB', analise)
        return float(m[1]) if m and m[1] != '-inf' else None

    integridade = {'schema': 1, 'analise_ok': analise_ok, 'pretos': pretos,
                   'congelamentos': congelamentos, 'silencios_s': [float(x) for x in silencio],
                   'volume_medio_db': volume('mean'), 'pico_db': volume('max'),
                   'diferenca_audio_video_s': round(abs(dv - da), 3) if dv and da else None,
                   'diferenca_inicio_audio_video_s': round(abs(float((v or {}).get('start_time') or 0) -
                                                              float((a or {}).get('start_time') or 0)), 3) if v and a else None}
    if os.getenv('RENDER_INTEGRIDADE', '0') == '1':
        if not analise_ok:
            erros.append('A análise de integridade não foi concluída.')
        if (v and v.get('codec_name') != 'h264') or (a and a.get('codec_name') != 'aac'):
            erros.append('Codecs incompatíveis com a saída H.264/AAC.')
        if (dv and da and abs(dv - da) > .5) or (integridade['diferenca_inicio_audio_video_s'] or 0) > .2:
            erros.append('Áudio e vídeo dessincronizados: diferença de duração acima de 0,5s.')
        if any(not previsto(x, esperado.get('pretos_previstos', [])) for x in pretos):
            erros.append('Há trecho preto não previsto no plano.')
        if any(not previsto(x, esperado.get('parados_previstos', [])) for x in congelamentos):
            erros.append('Há imagem congelada não prevista no plano.')
        if silencio and not esperado.get('silencio_previsto'):
            erros.append('Há silêncio prolongado não previsto no plano.')
        if integridade['pico_db'] is not None and integridade['pico_db'] > -.1:
            erros.append('Áudio sem margem de pico (acima de -0,1 dB).')
    if cancelado and cancelado():
        raise InterruptedError('cancelado')
    fotos = quadros(video, pasta, dur)
    if len(fotos) < 3:
        erros.append('Não consegui ler quadros do começo, meio e fim.')
    return {'ok': not erros, 'erros': erros, 'avisos': avisos, 'duracao': dur, 'largura': int(v.get('width', 0)) if v else 0,
            'altura': int(v.get('height', 0)) if v else 0, 'codec': v.get('codec_name') if v else '', 'audio': a.get('codec_name') if a else '',
            'tamanho': video.stat().st_size, 'quadros': [str(f) for f in fotos], 'integridade': integridade}


def conferir_srt(arq: Path, dur: float) -> list:
    """Legenda: arquivo legível, tempos em ordem, cada fala com começo antes do fim e dentro do vídeo."""
    if not arq.exists():
        return ['A legenda (SRT) não foi gerada.']
    def seg(x):
        h, m, r = x.replace(',', '.').split(':')
        return int(h) * 3600 + int(m) * 60 + float(r)
    ant, erros = -1.0, []
    for k, (a, b) in enumerate(re.findall(r'(\d\d:\d\d:\d\d,\d{3}) --> (\d\d:\d\d:\d\d,\d{3})', arq.read_text(encoding='utf-8', errors='replace'))):
        ta, tb = seg(a), seg(b)
        if tb <= ta or ta < ant - 0.01 or tb > dur + 0.5:
            erros.append(f'Legenda {k + 1} com tempo errado ({a} --> {b}).')
            break
        ant = ta
    return erros


def preview_leve(video: Path, saida: Path, cancelado=None):
    """Cópia menor (para o e-mail e para assistir no celular com pouca internet)."""
    rodar(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(video), '-vf', "scale='if(gt(iw,ih),-2,540)':'if(gt(iw,ih),540,-2)'", '-c:v', 'libx264',
           '-preset', 'veryfast', '-crf', '30', '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', str(saida)], cancelado, etapa='prévia leve')


def tem_ffmpeg() -> bool:
    return bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))


def livre_mb(pasta: Path) -> int:
    try:
        return shutil.disk_usage(pasta).free // 1048576
    except OSError:
        return -1


MIN_LIVRE_MB = int(os.getenv('MIN_LIVRE_MB', '500'))
