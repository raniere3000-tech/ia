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
import time
from pathlib import Path


class ErroRender(Exception):
    pass


def rodar(cmd: list, cancelado=None, tempo_max: float = 3600, progresso=None, dur: float = 0) -> str:
    """Roda o FFmpeg; se `cancelado()` ficar verdadeiro, encerra com calma (sem deixar arquivo pela metade)."""
    if progresso and dur > 0 and cmd and cmd[0] == 'ffmpeg':
        cmd = cmd[:1] + ['-progress', 'pipe:1', '-nostats'] + cmd[1:]
    p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE if progresso else subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    inicio = time.time()
    erro = ''
    try:
        if progresso and p.stdout:
            for linha in p.stdout:
                m = re.match(r'out_time_ms=(\d+)', linha)
                if m and dur > 0:
                    progresso(min(1.0, int(m.group(1)) / 1e6 / dur))
                if cancelado and cancelado():
                    p.terminate()
                    break
                if time.time() - inicio > tempo_max:
                    p.kill()
                    raise ErroRender('O FFmpeg passou do tempo máximo.')
        while p.poll() is None:
            if cancelado and cancelado():
                p.terminate()
            if time.time() - inicio > tempo_max:
                p.kill()
                raise ErroRender('O FFmpeg passou do tempo máximo.')
            time.sleep(0.3)
        erro = p.stderr.read() if p.stderr else ''
    finally:
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
    if p.returncode != 0:
        if cancelado and cancelado():
            raise InterruptedError('cancelado')
        raise ErroRender('FFmpeg falhou: ' + (erro.strip().splitlines() or ['sem detalhe'])[-1][:400])
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
    rodar(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(lista), '-c', 'copy', '-movflags', '+faststart', str(saida)], cancelado)


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
    rodar(cmd, cancelado)


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
    try:
        analise = rodar(['ffmpeg', '-nostdin', '-v', 'info', '-i', str(video), '-vf', 'scale=270:-2,blackdetect=d=1.0:pic_th=0.97,freezedetect=n=0.002:d=4',
                         '-af', 'silencedetect=n=-50dB:d=3', '-f', 'null', '-'], cancelado, tempo_max=1800)
    except ErroRender as e:
        avisos.append('Não deu para analisar tela preta/congelada: ' + str(e)[:120])
    pretos = re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', analise)
    congel = re.findall(r'freeze_duration: ([\d.]+)', analise)
    silencio = re.findall(r'silence_duration: ([\d.]+)', analise)
    if pretos:
        avisos.append('Trecho preto: ' + ', '.join(f'{float(a):.1f}s–{float(b):.1f}s' for a, b in pretos[:4]))
    if congel:
        avisos.append(f'Imagem parada por {max(float(x) for x in congel):.1f}s (normal em cenas sem movimento).')
    if silencio:
        avisos.append(f'Silêncio de {max(float(x) for x in silencio):.1f}s.')
    fotos = quadros(video, pasta, dur)
    if len(fotos) < 3:
        erros.append('Não consegui ler quadros do começo, meio e fim.')
    return {'ok': not erros, 'erros': erros, 'avisos': avisos, 'duracao': dur, 'largura': int(v.get('width', 0)) if v else 0,
            'altura': int(v.get('height', 0)) if v else 0, 'codec': v.get('codec_name') if v else '', 'audio': a.get('codec_name') if a else '',
            'tamanho': video.stat().st_size, 'quadros': [str(f) for f in fotos]}


def preview_leve(video: Path, saida: Path, cancelado=None):
    """Cópia menor (para o e-mail e para assistir no celular com pouca internet)."""
    rodar(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(video), '-vf', "scale='if(gt(iw,ih),-2,540)':'if(gt(iw,ih),540,-2)'", '-c:v', 'libx264',
           '-preset', 'veryfast', '-crf', '30', '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', str(saida)], cancelado)


def tem_ffmpeg() -> bool:
    return bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))


def livre_mb(pasta: Path) -> int:
    try:
        return shutil.disk_usage(pasta).free // 1048576
    except OSError:
        return -1


MIN_LIVRE_MB = int(os.getenv('MIN_LIVRE_MB', '500'))
