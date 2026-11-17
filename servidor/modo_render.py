"""Modo Rápido e modo Caprichado dos cortes feitos no servidor.

Rápido:     preset veloz do x264, sem as peças pesadas dos estilos (brilho e desfoque de foco), sem o zoom que muda a cada quadro e
            sem mixagem de áudio extra. Continua passando pelo QA técnico e pela sua aprovação.
Caprichado: preset mais lento (melhor compressão), qualidade um pouco maior, mixagem de áudio com normalização de volume
            e conferência extra do volume final medido. Os tempos mostrados vêm de cortes que ESTE aparelho já fez; sem dados, aparece "não medido".
Nenhum dos modos promete mais visualizações: só mudam o que o aparelho faz e o tempo que leva.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import postagem as pg

MODOS = {
    'rapido': {'nome': 'Rápido', 'preset': 'veryfast', 'crf_delta': 2, 'loudnorm': False, 'sem_pesadas': True, 'sem_zoom_vivo': True, 'qa_volume': False,
               'desc': 'Menos trabalho: pula brilho, desfoque de foco e zoom lento; áudio como veio.'},
    'caprichado': {'nome': 'Caprichado', 'preset': 'medium', 'crf_delta': -2, 'loudnorm': True, 'sem_pesadas': False, 'sem_zoom_vivo': False, 'qa_volume': True,
                   'desc': 'Mais trabalho: compressão melhor, volume normalizado e conferência do volume final.'},
}
PESADAS = ('brilho', 'foco')
ARQ = pg.DADOS / 'modo_medidas.json'


def valido(m: str) -> str:
    return m if m in MODOS else ''


def aplicar(tpl: dict, modo: str) -> list:
    """Ajusta o template do corte para o modo e devolve a lista das operações que foram mesmo mudadas (para mostrar na tela)."""
    modo = valido(modo)
    if not modo:
        return []
    cfg, ops = MODOS[modo], []
    tpl['modo'] = modo
    tpl['x264_preset'] = cfg['preset']
    ops.append(f'preset do x264: {cfg["preset"]}')
    tpl['crf'] = max(16, min(30, int(tpl.get('crf', 23)) + cfg['crf_delta']))
    ops.append(f'qualidade (CRF {tpl["crf"]})')
    if cfg['sem_pesadas'] and tpl.get('estilo_visual'):
        off = list(tpl.get('estilo_off') or [])
        novos = [c for c in PESADAS if c not in off]
        if novos:
            tpl['estilo_off'] = off + novos
            ops.append('estilo sem as peças pesadas (' + ', '.join(novos) + ')')
    if cfg['sem_zoom_vivo'] and tpl.get('efeito') == 'zoom-acao':
        tpl['efeito'] = 'nenhum'
        ops.append('sem zoom lento')
    if cfg['loudnorm']:
        tpl['loudnorm'] = True
        ops.append('áudio normalizado (loudnorm)')
    if cfg['qa_volume']:
        ops.append('conferência do volume final')
    return ops


def volume_final(arq: Path) -> dict | None:
    """Mede o volume do arquivo pronto (EBU R128, em LUFS). None se o arquivo não tem áudio."""
    r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'info', '-i', str(arq), '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True, timeout=600)
    m = re.findall(r'I:\s+(-?[\d.]+) LUFS', r.stderr)
    if not m:
        return None
    pk = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', r.stderr)
    return {'lufs': float(m[-1]), 'pico_dbfs': float(pk[-1]) if pk else None}


def registrar_tempo(modo: str, segundos: float, duracao: float):
    if not valido(modo) or duracao < 2 or segundos <= 0:
        return
    with pg.LOCK:
        d = pg._ler(ARQ, {})
        x = d.setdefault(modo, {'n': 0, 'seg': 0.0, 'dur': 0.0})
        x['n'] += 1
        x['seg'] += segundos
        x['dur'] += duracao
        pg._gravar(ARQ, d)


def estimar(modo: str, duracao: float) -> dict:
    """Tempo ESTIMADO de montagem, só com base em cortes já feitos neste aparelho (precisa de pelo menos 3). Sem isso: não medido."""
    x = pg._ler(ARQ, {}).get(valido(modo) or '_', None)
    if not x or x['n'] < 3 or x['dur'] <= 0:
        return {'segundos': None, 'motivo': 'não medido: faltam cortes feitos neste modo (precisa de pelo menos 3)', 'amostras': (x or {}).get('n', 0)}
    return {'segundos': round(x['seg'] / x['dur'] * duracao, 1), 'amostras': x['n'], 'motivo': f'média de {x["n"]} corte(s) feitos neste celular'}


def resumo(duracao: float = 30.0) -> dict:
    return {k: {'nome': v['nome'], 'desc': v['desc'], 'estimativa': estimar(k, duracao)} for k, v in MODOS.items()}
