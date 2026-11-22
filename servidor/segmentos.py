"""Render por plano (etapa T3 do lote 3): cada plano de uma cena vira um pedaço de vídeo próprio, guardado pelo
hash do que muda nele. Mudou só o plano 2 de 3? Só o pedaço 2 é refeito; os outros saem do cache e a cena é
montada de novo na ordem.

- Chave do pedaço = conteúdo da cena (texto, personagens, cenário, voz, imagem, efeitos, sem os planos) + este plano
  + a janela de tempo dele (+ os vizinhos no documentário, que tem passagem entre fotos) + pedidos de "refazer este plano".
- Cada pedaço é gravado em arquivo temporário e só vira definitivo no fim: cancelar ou reiniciar o celular no meio
  não estraga nada; na retomada, os pedaços prontos são reaproveitados.
- O som do pedaço sai sem compressão (PCM) e é comprimido uma vez só na junção (sem estalo entre os planos).
- Limite honesto: o FFmpeg ainda calcula os quadros ANTES do plano (as animações dependem do tempo da cena),
  mas não codifica nem grava. Refazer o último plano custa quase o mesmo que a cena; o primeiro custa bem menos.
- Projetos sem planos (ou com 1 plano) e o 3D continuam no caminho antigo (cena inteira de uma vez).
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import estilos_codigo as ec
import renderizador as rd

COM_VIZINHOS = ('documentario',)     # estilos com passagem entre planos: o pedaço depende dos vizinhos


def usa_segmentos(eid: str, cena: dict) -> bool:
    import os
    return os.getenv('RENDER_POR_PLANO', '1') != '0' and eid not in ('animado3d',) and len(cena.get('planos') or []) >= 2


def janelas(planos: list, dur: float) -> list[tuple[float, float]]:
    """Janelas alinhadas ao quadro (sem meio quadro perdido entre os pedaços)."""
    out = []
    for a, b in ec.tempos_planos([dict(p, peso=p.get('peso', 1.0)) for p in planos], dur):
        out.append((round(a * ec.FPS) / ec.FPS, round(b * ec.FPS) / ec.FPS))
    out[-1] = (out[-1][0], round(dur * ec.FPS) / ec.FPS)
    return out


def chaves(eid: str, chave_base: str, cena: dict, dur: float) -> list[str]:
    planos = cena['planos']
    refazer = cena.get('refazer_planos') or {}
    out = []
    for k, (p, jan) in enumerate(zip(planos, janelas(planos, dur))):
        viz = [planos[k - 1] if k else None, planos[k + 1] if k + 1 < len(planos) else None] if eid in COM_VIZINHOS else []
        pid = p.get('id') or f'p{k + 1}'
        base = json.dumps([chave_base, ec.VERSAO_MOTOR, eid, p, viz, jan, refazer.get(pid, 0)], sort_keys=True, ensure_ascii=False)
        out.append(hashlib.sha256(base.encode()).hexdigest()[:24])
    return out


def renderizar(eid: str, cena: dict, W: int, H: int, dur: float, pasta: Path, img, audio, paleta, imgs_pl, chave_base: str, saida: Path,
               cancelado=None, progresso=None) -> dict:
    """Faz (ou reaproveita) cada pedaço e monta a cena em `saida`. Devolve o que foi feito, para registrar e medir."""
    pasta_seg = pasta / 'planos'
    pasta_seg.mkdir(parents=True, exist_ok=True)
    jans = janelas(cena['planos'], dur)
    ks = chaves(eid, chave_base, cena, dur)
    info = []
    preparado = False
    for k, (chave, (t0, t1), p) in enumerate(zip(ks, jans, cena['planos'])):
        arq = pasta_seg / f'{chave}.mov'
        item = {'plano': p.get('id') or f'p{k + 1}', 'tipo': p.get('plano', ''), 'chave': chave, 'inicio': t0, 'fim': t1}
        if arq.exists() and arq.stat().st_size > 1000:
            info.append(dict(item, refeito=False, segundos=0.0))
            continue
        if progresso:
            progresso(k / len(ks), f'Plano {k + 1} de {len(ks)}')
        if not preparado:
            ec.preparar(eid, W, H, dur, paleta, cancelado, cena=cena)
            preparado = True
        trab = pasta_seg / f'trab-{chave}'
        trab.mkdir(exist_ok=True)
        tmp = pasta_seg / f'{chave}.tmp.mov'
        t_ini = time.time()
        try:
            rd.rodar(ec.montar(eid, cena, W, H, dur, trab, img, audio, tmp, paleta, imgs_pl, janela=(t0, t1)), cancelado,
                     tempo_max=max(600, dur * 120), etapa=f'plano {k + 1} de {len(ks)}')
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        tmp.replace(arq)
        import shutil
        shutil.rmtree(trab, ignore_errors=True)
        info.append(dict(item, refeito=True, segundos=round(time.time() - t_ini, 2)))
    juntar([pasta_seg / f'{k}.mov' for k in ks], saida, pasta_seg, cancelado)
    return {'planos': info, 'refeitos': sum(1 for x in info if x['refeito']), 'reaproveitados': sum(1 for x in info if not x['refeito'])}


def juntar(pedacos: list, saida: Path, pasta: Path, cancelado=None):
    lista = pasta / f'lista-{saida.stem}.txt'
    lista.write_text(''.join(f"file '{str(c).replace(chr(39), '')}'\n" for c in pedacos), encoding='utf-8')
    tmp = saida.with_name(saida.stem + '.junta.mp4')
    rd.rodar(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(lista), '-c:v', 'copy',
              '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-ac', '2', '-movflags', '+faststart', str(tmp)], cancelado, tempo_max=600)
    tmp.replace(saida)
    lista.unlink(missing_ok=True)


def limpar(pasta: Path, manter: set):
    """Apaga pedaços que nenhuma cena usa mais (chamado depois do vídeo final)."""
    for a in (pasta / 'planos').glob('*.mov') if (pasta / 'planos').exists() else []:
        if a.stem not in manter:
            a.unlink(missing_ok=True)
