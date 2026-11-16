"""Diretor de Qualidade do Agente 3: confere o storyboard antes do render e cada plano depois do render.

Complementa a conferência técnica de `renderizador.conferir` (codec, duração, tela preta, congelado, silêncio), que continua
sendo a única que REPROVA o vídeo. Aqui tudo vira alerta com evidência (cena, plano, instante e quadro), para a pessoa decidir.
A única correção automática é localizada e segura: um plano cuja foto própria saiu escura ou sem detalhe volta a usar a foto
da cena e só aquela cena é refeita (no máximo uma vez por cena).

Leve para o celular: cada plano vira um quadro de 16x16 em tons de cinza (256 bytes) e as contas são feitas em Python puro.
"""
from __future__ import annotations

import math
import subprocess
import time
from pathlib import Path

import estilos_codigo as ec

ESCURO = 18          # média de brilho (0-255) abaixo disso: quadro escuro demais
SEM_DETALHE = 7      # desvio padrão abaixo disso: imagem lisa, sem nada para ver
PARECIDO = 6         # diferença média entre dois planos seguidos abaixo disso: parece o mesmo plano


def _problema(tipo, sev, descricao, correcao, cena='', plano='', t=None, evidencia='') -> dict:
    return {'tipo': tipo, 'severidade': sev, 'descricao': descricao, 'correcao': correcao, 'cena_id': cena, 'plano_id': plano,
            'timecode': None if t is None else f'{int(t // 60):02d}:{t % 60:06.3f}', 'evidencia': evidencia}


def antes(cenas: list, estilo: str) -> list:
    """Confere o storyboard (sem render): ritmo, planos repetidos e cenas sem imagem."""
    out = []
    for c in cenas:
        cid = c.get('id', '')
        nome = c.get('titulo') or (c.get('texto') or '')[:30]
        pal = len((c.get('texto') or '').split())
        if pal > 34:
            out.append(_problema('ritmo', 'media', f'A cena "{nome}" tem {pal} palavras: fica longa na tela.', 'Divida em duas cenas.', cid))
        planos = c.get('planos') or []
        for a, b in zip(planos, planos[1:]):
            if a['plano'] == b['plano'] and not (c.get('fotos_planos') or {}).get(b['id']):
                out.append(_problema('plano_repetido', 'baixa', f'Na cena "{nome}" dois planos seguidos são {ec.NOME_PLANO[a["plano"]]} com a mesma foto.',
                                     'Troque um deles para aberto, médio ou close.', cid, b['id']))
        if estilo == 'documentario' and not (c.get('imagem') or {}).get('arquivo'):
            out.append(_problema('sem_imagem', 'media', f'A cena "{nome}" ficou sem foto própria e usa a de outra cena.',
                                 'Troque a busca da cena ou cole uma chave de fotos (Pixabay ou Pexels).', cid))
    import diretor   # regras de direção (eixo de 180°, olhar, close sem dono) para cenas com personagens
    for x in diretor.checar(cenas):
        out.append(_problema(x['tipo'], x['severidade'], x['descricao'], x['correcao'], x['cena'], x.get('plano', '')))
    return out


def _miniatura(video: Path, t: float) -> list[int] | None:
    try:
        r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-ss', f'{max(0, t):.3f}', '-i', str(video), '-frames:v', '1',
                            '-vf', 'scale=16:16:flags=area,format=gray', '-f', 'rawvideo', '-'],
                           capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return list(r.stdout[:256]) if len(r.stdout) >= 256 else None


def _stats(px: list[int]) -> tuple[float, float]:
    m = sum(px) / len(px)
    return m, math.sqrt(sum((x - m) ** 2 for x in px) / len(px))


def cena(clipe: Path, c: dict, dur: float, inicio: float, pasta: Path) -> tuple[list, list]:
    """Confere os planos de uma cena já renderizada. Devolve (problemas, ids de planos a corrigir)."""
    out, corrigir = [], []
    planos = c.get('planos') or ec.planos_auto(c, dur)
    tempos = ec.tempos_planos([dict(p, peso=p.get('peso', 1.0)) for p in planos], dur)
    anterior = None
    nome = c.get('titulo') or (c.get('texto') or '')[:30]
    for p, (t0, t1) in zip(planos, tempos):
        meio = (t0 + t1) / 2
        px = _miniatura(clipe, meio)
        if px is None:
            out.append(_problema('analise_indisponivel', 'baixa', f'Não consegui ler um quadro do plano {p["id"]} da cena "{nome}".', '', c.get('id', ''), p['id'], inicio + meio))
            continue
        m, dp = _stats(px)
        propria = bool((c.get('fotos_planos') or {}).get(p['id']))
        if m < ESCURO:
            out.append(_problema('quadro_escuro', 'media', f'O plano {ec.NOME_PLANO.get(p["plano"], "")} da cena "{nome}" ficou escuro demais.',
                                 'Usar a foto da cena neste plano.' if propria else 'Trocar a foto da cena.', c.get('id', ''), p['id'], inicio + meio))
            if propria:
                corrigir.append(p['id'])
        elif dp < SEM_DETALHE:
            out.append(_problema('sem_detalhe', 'baixa', f'O plano {ec.NOME_PLANO.get(p["plano"], "")} da cena "{nome}" quase não mostra nada (imagem lisa).',
                                 'Usar a foto da cena neste plano.' if propria else 'Abrir mais o plano ou trocar a foto.', c.get('id', ''), p['id'], inicio + meio))
            if propria:
                corrigir.append(p['id'])
        if anterior is not None and sum(abs(a - b) for a, b in zip(px, anterior)) / 256 < PARECIDO:
            out.append(_problema('plano_repetido', 'baixa', f'Dois planos seguidos da cena "{nome}" ficaram quase iguais.',
                                 'Mude o enquadramento ou a busca de um deles.', c.get('id', ''), p['id'], inicio + t0))
        anterior = px
    return out, corrigir


def resumo(problemas: list, tecnico: dict | None) -> dict:
    """Situação final: só a conferência técnica reprova; o resto é alerta para a revisão humana."""
    if tecnico and not tecnico.get('ok', True):
        st = 'falha_tecnica'
    elif any(p['tipo'] == 'analise_indisponivel' for p in problemas) and len(problemas) == sum(p['tipo'] == 'analise_indisponivel' for p in problemas):
        st = 'analise_indisponivel'
    elif problemas:
        st = 'alerta_visual'
    else:
        st = 'apto_para_revisao_humana'
    return {'status': st, 'problemas': problemas[:40], 'gerado': time.time(),
            'tecnico': {'erros': (tecnico or {}).get('erros', []), 'avisos': (tecnico or {}).get('avisos', [])}}
