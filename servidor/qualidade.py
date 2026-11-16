"""Diretor de Qualidade do Agente 3: confere o storyboard antes do render e cada plano depois do render.

Complementa a conferência técnica de `renderizador.conferir` (codec, duração, tela preta, congelado, silêncio), que continua
sendo a única que REPROVA o vídeo. Aqui tudo vira alerta com evidência (cena, plano, instante e quadro), para a pessoa decidir.
Correções automáticas são localizadas, seguras e limitadas (QA_MAX_CORRECOES, padrão 2 por defeito):
- documentário: plano com foto própria escura ou lisa volta a usar a foto da cena;
- desenho animado: close em quem anda e sai do quadro vira plano aberto; personagens empilhados no mesmo lugar
  (sem caminhada) são afastados para um lado livre.
Cada correção só é aplicada se muda algo; se o defeito continuar depois do limite, vai para revisão humana (sem laço infinito).
Laudo: cada achado tem status, cena_id, plano_id, timecode, evidencia, tipo, severidade, proposta, tentativas e natureza
("objetivo" = medido; "julgamento" = opinião estética, por exemplo da IA de visão, que nunca bloqueia).

Leve para o celular: cada plano vira um quadro de 16x16 em tons de cinza (256 bytes) e as contas são feitas em Python puro.
"""
from __future__ import annotations

import math
import os
import subprocess
import time
from pathlib import Path

import estilos_codigo as ec

ESCURO = 18          # média de brilho (0-255) abaixo disso: quadro escuro demais
SEM_DETALHE = 7      # desvio padrão abaixo disso: imagem lisa, sem nada para ver
PARECIDO = 6         # diferença média entre dois planos seguidos abaixo disso: parece o mesmo plano
MAX_CORRECOES = int(os.getenv('QA_MAX_CORRECOES', '2'))


def _problema(tipo, sev, descricao, correcao, cena='', plano='', t=None, evidencia='', natureza='objetivo') -> dict:
    return {'tipo': tipo, 'severidade': sev, 'descricao': descricao, 'correcao': correcao, 'proposta': correcao, 'cena_id': cena, 'plano_id': plano,
            'timecode': None if t is None else f'{int(t // 60):02d}:{t % 60:06.3f}', 'evidencia': evidencia, 'status': 'aberto',
            'tentativas': 0, 'natureza': natureza}


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


def cena(clipe: Path, c: dict, dur: float, inicio: float, pasta: Path, eid: str = 'documentario', W: int = 1080, H: int = 1920) -> tuple[list, list]:
    """Confere os planos de uma cena já renderizada (quadros do começo, meio e fim de cada plano) e, no desenho animado,
    a geometria dos personagens em cada plano. Devolve (problemas, ids de planos a corrigir no documentário)."""
    out, corrigir = [], []
    if eid == 'animado2d':
        out += geometria(c, dur, W, H, inicio)
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
        for nome_t, tt in (('começo', t0 + min(0.15, (t1 - t0) / 4)), ('fim', t1 - min(0.15, (t1 - t0) / 4))):
            q = _miniatura(clipe, tt)
            if q is not None and _stats(q)[0] < ESCURO * 0.6 and m >= ESCURO:
                out.append(_problema('quadro_escuro', 'baixa', f'O {nome_t} do plano {ec.NOME_PLANO.get(p["plano"], "")} da cena "{nome}" ficou quase preto.',
                                     'Conferir a passagem entre os planos.', c.get('id', ''), p['id'], inicio + tt, f'brilho médio {_stats(q)[0]:.0f}/255'))
        if anterior is not None and sum(abs(a - b) for a, b in zip(px, anterior)) / 256 < PARECIDO:
            out.append(_problema('plano_repetido', 'baixa', f'Dois planos seguidos da cena "{nome}" ficaram quase iguais.',
                                 'Mude o enquadramento ou a busca de um deles.', c.get('id', ''), p['id'], inicio + t0))
        anterior = px
    return out, corrigir


# ---------------------------------------------------------------- desenho animado: geometria por plano (sem olhar o vídeo)
def _pos_x(el: dict, t: float, W: float) -> float:
    """Onde o personagem está no instante t (caminhada do catálogo, mesma curva suave do rig)."""
    import rig2d
    x = rig2d.POSICOES.get(el.get('posicao'), 0.5) * W
    for a in el.get('acoes') or []:
        if a['tipo'] in ('andar', 'correr') and a['t'] <= t:
            d = a.get('dur') or rig2d.ACOES[a['tipo']][1]
            prog = max(0.0, min(1.0, (t - a['t']) / max(0.2, d)))
            alvo = rig2d.POSICOES.get(a.get('alvo') or 'direita', 0.73) * W
            x = x + (alvo - x) * prog * prog * (3 - 2 * prog)
    return x


def geometria(c: dict, dur: float, W: int, H: int, inicio: float = 0.0) -> list:
    """Para cada plano: quem está em foco continua no quadro? Cabeça cortada no close? Dois personagens no mesmo lugar?
    Usa a mesma conta da câmera do estilo animado (zoom do plano centrado em quem está em foco)."""
    out = []
    elenco = c.get('elenco') or []
    if not elenco:
        return out
    planos = c.get('planos') or [{'id': 'p1', 'plano': 'WS', 'peso': 1.0}]
    tempos = ec.tempos_planos([dict(p, peso=p.get('peso', 1.0)) for p in planos], dur)
    v = H > W
    chao = H * (0.80 if v else 0.86)
    altura = H * (0.40 if v else 0.62) / (1.25 if len(elenco) > 2 else 1)
    u = altura / 100
    falante = (c.get('personagem') or '').strip().lower()
    nome = c.get('titulo') or (c.get('texto') or '')[:30]
    cid = c.get('id', '')
    for p, (t0, t1) in zip(planos, tempos):
        z = ec.ZOOM_2D.get(p.get('plano'), 1.0)
        if z <= 1:
            continue
        foco_id = p.get('personagem') or falante or elenco[0]['personagem_id']
        foco = next((e for e in elenco if e['personagem_id'] == foco_id), elenco[0])
        cx = _pos_x(foco, t0, W)               # a câmera mira onde o personagem estava no começo
        larg = W / z
        xs = [_pos_x(foco, t0 + (t1 - t0) * k / 4, W) for k in range(5)]
        fora = max(abs(x - cx) for x in xs)
        if fora > larg * 0.42:
            k = max(range(5), key=lambda k: abs(xs[k] - cx))
            out.append(_problema('sai_do_quadro', 'media', f'No plano {ec.NOME_PLANO.get(p["plano"], "")} da cena "{nome}", {foco_id} anda e sai do quadro.',
                                 'Trocar este plano por um aberto (WS).', cid, p.get('id', ''), inicio + t0 + (t1 - t0) * k / 4,
                                 f'deslocamento {fora:.0f}px; meia largura do quadro {larg / 2:.0f}px'))
        if p.get('plano') in ('CU', 'ECU'):
            cab = chao - (48.5 + 31 + 11) * u
            topo_quadro = cab + 0.06 * H - H / z / 2
            if cab - 11 * u < topo_quadro:
                out.append(_problema('cabeca_cortada', 'baixa', f'No close da cena "{nome}" o topo da cabeça de {foco_id} fica fora do quadro.',
                                     'Usar plano médio (MS).', cid, p.get('id', ''), inicio + t0, f'topo da cabeça {cab - 11 * u:.0f}px; topo do quadro {topo_quadro:.0f}px'))
    # personagens empilhados no mesmo lugar (um esconde o outro)
    for k, (p, (t0, t1)) in enumerate(zip(planos, tempos)):
        meio = (t0 + t1) / 2
        xs = [(e['personagem_id'], _pos_x(e, meio, W)) for e in elenco]
        for a in range(len(xs)):
            for b in range(a + 1, len(xs)):
                if abs(xs[a][1] - xs[b][1]) < 14 * u:
                    out.append(_problema('sobreposicao', 'media', f'Na cena "{nome}", {xs[a][0]} e {xs[b][0]} ficam no mesmo lugar e um esconde o outro.',
                                         'Afastar um deles para um lado livre.', cid, p.get('id', ''), inicio + meio,
                                         f'distância {abs(xs[a][1] - xs[b][1]):.0f}px; mínimo {14 * u:.0f}px'))
                    break
            else:
                continue
            break
    if falante and not c.get('_audio') and not (c.get('audio') or {}).get('arquivo') and c.get('texto'):
        out.append(_problema('boca_parada', 'baixa', f'A cena "{nome}" tem fala mas ainda não tem voz: a boca de {falante} fica parada.',
                             'Gerar ou gravar a voz da cena.', cid))
    return out


def correcao(c: dict, achados: list, eid: str) -> dict | None:
    """Mudança mínima na cena que resolve um achado objetivo do desenho animado. None = nada seguro a fazer
    (ou a mudança já foi feita: assim não entra em laço)."""
    if eid != 'animado2d':
        return None
    planos = [dict(p) for p in (c.get('planos') or [])]
    elenco = [dict(e) for e in (c.get('elenco') or [])]
    mudou = False
    for a in achados:
        if a['tipo'] in ('sai_do_quadro', 'cabeca_cortada'):
            for p in planos:
                if p.get('id') == a['plano_id']:
                    novo = 'WS' if a['tipo'] == 'sai_do_quadro' else 'MS'
                    if p.get('plano') != novo:
                        p['plano'] = novo
                        mudou = True
        elif a['tipo'] == 'sobreposicao':
            usados = {e.get('posicao') for e in elenco}
            livres = [x for x in ('esquerda', 'direita', 'centro') if x not in usados]
            falante = (c.get('personagem') or '').lower()
            for e in reversed(elenco):
                if e['personagem_id'] != falante and livres and not any(x['tipo'] in ('andar', 'correr') for x in e.get('acoes') or []):
                    e['posicao'] = livres[0]
                    mudou = True
                    break
    return {'planos': planos, 'elenco': elenco} if mudou else None


def resumo(problemas: list, tecnico: dict | None) -> dict:
    """Situação final: só a conferência técnica reprova; o resto é alerta para a revisão humana."""
    for p in problemas:          # laudos antigos: completa os campos novos sem mudar o que já estava
        p.setdefault('proposta', p.get('correcao', ''))
        p.setdefault('status', 'aberto')
        p.setdefault('tentativas', 0)
        p.setdefault('natureza', 'objetivo')
    if tecnico and not tecnico.get('ok', True):
        st = 'falha_tecnica'
    elif any(p['tipo'] == 'analise_indisponivel' for p in problemas) and len(problemas) == sum(p['tipo'] == 'analise_indisponivel' for p in problemas):
        st = 'analise_indisponivel'
    elif problemas:
        st = 'alerta_visual'
    else:
        st = 'apto_para_revisao_humana'
    return {'status': st, 'problemas': problemas[:40], 'gerado': time.time(),
            'revisao_humana': sum(1 for p in problemas if p.get('status') == 'revisao_humana'),
            'contagem': {'objetivo': sum(1 for p in problemas if p.get('natureza') != 'julgamento'),
                         'julgamento': sum(1 for p in problemas if p.get('natureza') == 'julgamento')},
            'tecnico': {'erros': (tecnico or {}).get('erros', []), 'avisos': (tecnico or {}).get('avisos', [])}}
