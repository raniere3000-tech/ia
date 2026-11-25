"""Contratos da esteira dos 5 agentes: o que um agente pode entregar ao outro, conferido pelo código.

Nada aqui vira comando de shell ou filtro do FFmpeg. Texto de IA só entra como ESCOLHA dentro de listas fechadas,
com números presos em faixas seguras. O que não passa é recusado com o motivo (ErroContrato).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re

SCHEMA = 1
SCHEMA_TIMELINE = 2
NOTA_MINIMA = 70             # nota total para aprovar (0 a 100)
MAX_CORRECOES = 5            # correções por etapa; a 1ª avaliação não conta
VERSAO_POLITICA = 'p1-70-5'
VALIDADE_CERTIFICADO = 30 * 86400

MODALIDADES = ('creative_preedit', 'final_release')
# pesos das partes da nota (somam 100). A nota é medida; opinião de IA nunca muda a nota nem bloqueia.
PESOS = {
    'final_release': {'tecnica': 20, 'legendas': 15, 'imagem': 15, 'ritmo': 15, 'gancho': 15, 'clareza': 10, 'identidade': 10},
    'creative_preedit': {'estrutura': 20, 'roteiro': 20, 'consistencia': 20, 'narracao': 15, 'assets': 25},
}
NOMES_PARTES = {'tecnica': 'Técnica, som e sincronia', 'legendas': 'Legendas e áreas seguras', 'imagem': 'Imagem e enquadramento', 'ritmo': 'Ritmo',
                'gancho': 'Gancho (começo)', 'clareza': 'Começo e fim completos', 'identidade': 'Identidade e template',
                'estrutura': 'Estrutura', 'roteiro': 'Roteiro', 'consistencia': 'Continuidade', 'narracao': 'Narração e falas', 'assets': 'Imagens e direitos'}
SEVERIDADES = ('baixa', 'media', 'alta', 'bloqueio')
ALVOS = ('agent1', 'agent3', 'agent5', 'pessoa')     # agent1: o Agente 1 refaz começo/fim do trecho antes da edição
# bloqueios que NENHUMA nota e nenhuma revisão manual simples passam por cima
BLOQUEIOS_DUROS = ('direitos', 'arquivo_quebrado', 'seguranca')

ESTADOS = ('source_registered', 'cuts_selected', 'creative_qa_pending', 'creative_qa_failed', 'creative_correction_pending', 'creative_approved',
           'edit_queued', 'editing', 'rendering', 'final_qa_pending', 'final_qa_failed', 'edit_correction_pending', 'final_approved',
           'manual_review_required', 'awaiting_human_publish_approval', 'publish_queued', 'published', 'failed_technical', 'cancelled')
NOMES_ESTADO = {'source_registered': 'Recebido', 'cuts_selected': 'Trechos escolhidos', 'creative_qa_pending': 'Diretor conferindo as cenas',
                'creative_qa_failed': 'Cenas reprovadas', 'creative_correction_pending': 'Agente 3 corrigindo cenas', 'creative_approved': 'Cenas aprovadas',
                'edit_queued': 'Na fila do editor', 'editing': 'Editor trabalhando', 'rendering': 'Exportando', 'final_qa_pending': 'Diretor conferindo o vídeo',
                'final_qa_failed': 'Vídeo reprovado', 'edit_correction_pending': 'Editor corrigindo', 'final_approved': 'Aprovado pelo diretor',
                'manual_review_required': 'Precisa da sua revisão', 'awaiting_human_publish_approval': 'Esperando a sua aprovação',
                'publish_queued': 'Na fila de postagem', 'published': 'Publicado', 'failed_technical': 'Falha técnica', 'cancelled': 'Cancelado'}

# ---------------------------------------------------------------- plano de edição (Agente 5)
ASPECTOS = {'9:16': (1080, 1920), '16:9': (1920, 1080), '1:1': (1080, 1080), '4:5': (1080, 1350)}
REENQUADRAR = ('centro', 'desfocado', 'camera', 'manter')
EFEITOS = {          # tipo: {parâmetro: (mínimo, máximo)} ou tupla de escolhas
    'zoom': {'nivel': (1.0, 1.6), 'ini_ms': (0, 3_600_000), 'fim_ms': (0, 3_600_000)},
    'reframe': {'modo': REENQUADRAR},
    'fade': {'entrada_ms': (0, 1000), 'saida_ms': (0, 1500)},
    'caption': {'ligado': (0, 1), 'tamanho': (0.05, 0.09), 'altura': (0.15, 0.82)},
    'loudnorm': {'alvo_lufs': (-18.0, -12.0)},
}
PERFIS_SAIDA = ('final', 'previa')
# correções que o diretor pode pedir ao editor (cada uma vira mudança tipada no plano)
ACOES = {
    'ajustar_inicio': {'delta_ms': (-5000, 5000)},
    'ajustar_fim': {'delta_ms': (-5000, 8000)},
    'encurtar_pausa': {'ini_ms': (0, 3_600_000), 'fim_ms': (0, 3_600_000)},
    'aumentar_legenda': {},
    'subir_legenda': {},
    'mover_legenda': {'altura': (0.15, 0.82)},       # pedido pelo Coordenador (texto do vídeo por baixo da legenda)
    'reduzir_zoom': {},
    'normalizar_audio': {},
    'trocar_enquadramento': {'modo': REENQUADRAR},
    'suavizar_cortes': {},
    'refazer_cenas': {'cenas': 'lista'},          # vai para o Agente 3
    'revisao_humana': {},
}
LIMITE_CLIPES = 40


class ErroContrato(ValueError):
    pass


def _num(v, faixa, nome):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ErroContrato(f'{nome}: precisa ser número.')
    if not math.isfinite(x) or not faixa[0] <= x <= faixa[1]:
        raise ErroContrato(f'{nome}: fora da faixa permitida ({faixa[0]} a {faixa[1]}).')
    return x


def _params(spec: dict, d: dict, nome: str) -> dict:
    if not isinstance(d, dict):
        raise ErroContrato(f'{nome}: parâmetros inválidos.')
    extra = set(d) - set(spec) - {'tipo', 'acao'}
    if extra:
        raise ErroContrato(f'{nome}: parâmetro não permitido: {", ".join(sorted(extra))}.')
    out = {}
    for k, regra in spec.items():
        if k not in d:
            continue
        if regra == 'lista':
            v = d[k]
            if not isinstance(v, list) or len(v) > 50 or not all(isinstance(x, str) and 0 < len(x) <= 40 for x in v):
                raise ErroContrato(f'{nome}.{k}: lista inválida.')
            out[k] = v
        elif isinstance(regra, tuple) and regra and isinstance(regra[0], str):
            if d[k] not in regra:
                raise ErroContrato(f'{nome}.{k}: valor fora da lista ({", ".join(regra)}).')
            out[k] = d[k]
        else:
            out[k] = _num(d[k], regra, f'{nome}.{k}')
    return out


def efeitos_reais_ativos() -> bool:
    return os.getenv('A5_EFEITOS_REAIS','0').lower() in ('1','true','sim')


def validar_plano(p: dict, dur_fonte: float | None = None) -> dict:
    """EditPlan: confere tudo e devolve uma cópia limpa. Caminhos de arquivo nunca vêm do cliente: só ids de fontes conhecidas."""
    if not isinstance(p, dict):
        raise ErroContrato('Plano de edição inválido.')
    schema = p.get('schema_version', SCHEMA)
    if type(schema) is not int or schema not in (SCHEMA, SCHEMA_TIMELINE):
        raise ErroContrato('Versão do plano de edição não suportada.')
    versao = p.get('timeline_version', 1)
    if schema == SCHEMA_TIMELINE:
        if type(versao) is not int or not 1 <= versao <= 2_147_483_647:
            raise ErroContrato('Revisão da timeline inválida.')
        for campo, limite in (('source_assets', 1), ('effects', 24), ('manual_locks', 40)):
            valores = p.get(campo, [])
            if not isinstance(valores, list) or len(valores) > limite:
                raise ErroContrato(f'{campo}: lista inválida ou acima do limite.')
        if p.get('source_assets') not in (None, ['principal']):
            raise ErroContrato('A timeline atual aceita uma única fonte principal.')
    clipes = p.get('clips') or []
    if not isinstance(clipes, list) or not 1 <= len(clipes) <= LIMITE_CLIPES:
        raise ErroContrato(f'O plano precisa de 1 a {LIMITE_CLIPES} trechos.')
    limpos = []
    for i, c in enumerate(clipes):
        if not isinstance(c, dict):
            raise ErroContrato(f'Trecho {i + 1} inválido.')
        a = _num(c.get('in_ms'), (0, 36_000_000), f'trecho {i + 1} início')
        b = _num(c.get('out_ms'), (0, 36_000_000), f'trecho {i + 1} fim')
        if b - a < 300:
            raise ErroContrato(f'Trecho {i + 1}: fim precisa ser depois do início (mínimo 0,3 s).')
        if dur_fonte and b > dur_fonte * 1000 + 250:
            raise ErroContrato(f'Trecho {i + 1}: passa do fim do vídeo de origem.')
        src = str(c.get('source', 'principal'))
        if src not in [str(x) for x in (p.get('source_assets') or ['principal'])]:
            raise ErroContrato(f'Trecho {i + 1}: fonte desconhecida.')
        limpos.append({'source': src, 'in_ms': int(a), 'out_ms': int(b)})
    efeitos = []
    for i, e in enumerate(p.get('effects') or []):
        tipo = (e or {}).get('tipo') if isinstance(e, dict) else None
        if tipo == 'broll' and efeitos_reais_ativos():
            asset = str(e.get('asset') or '')
            if not re.fullmatch(r'[a-f0-9]{12,64}',asset) or e.get('direitos') not in ('meu','autorizado','regra'):
                raise ErroContrato('B-roll exige mídia registrada e origem de uso autorizada.')
            ini=int(_num(e.get('ini_ms'),(0,3_600_000),'b-roll início'))
            fim=int(_num(e.get('fim_ms'),(0,3_600_000),'b-roll fim'))
            if fim<=ini:
                raise ErroContrato('B-roll exige intervalo positivo.')
            efeitos.append({'tipo':'broll','asset':asset,'direitos':e['direitos'],'ini_ms':ini,'fim_ms':fim,
                            'credito':str(e.get('credito') or '')[:300]})
            continue
        if tipo not in EFEITOS:
            raise ErroContrato(f'Efeito {i + 1}: tipo não permitido ({tipo}). Permitidos: {", ".join(EFEITOS)}.')
        efeitos.append({'tipo': tipo, **_params(EFEITOS[tipo], e, f'efeito {tipo}')})
    asp = p.get('target_aspect_ratio', '9:16')
    if not isinstance(asp, str) or asp not in ASPECTOS:
        raise ErroContrato('Formato de tela não permitido.')
    perfil = p.get('output_profile', 'final')
    if perfil not in PERFIS_SAIDA:
        raise ErroContrato('Perfil de saída não permitido.')
    travas = []
    for t in p.get('manual_locks') or []:
        if not isinstance(t, (list, tuple)) or len(t) != 2:
            raise ErroContrato('Trecho travado inválido.')
        travas.append([int(_num(t[0], (0, 36_000_000), 'trava')), int(_num(t[1], (0, 36_000_000), 'trava'))])
    out = {'schema_version': schema, 'source_assets': [str(x)[:40] for x in (p.get('source_assets') or ['principal'])][:5],
            'timeline_version': int(versao or 1), 'clips': limpos, 'effects': efeitos,
            'template_id': str(p.get('template_id') or '')[:40], 'target_aspect_ratio': asp, 'output_profile': perfil,
            'manual_locks': travas, 'edit_reason': str(p.get('edit_reason') or '')[:300]}
    if schema == SCHEMA_TIMELINE:
        return _timeline_v2(p, out)
    return out


def _timeline_v2(bruto: dict, plano: dict) -> dict:
    clipes = plano['clips']
    if any(a['out_ms'] > b['in_ms'] for a, b in zip(clipes, clipes[1:])):
        raise ErroContrato('Os trechos da timeline precisam estar em ordem e sem sobreposição.')
    if any(fim <= ini for ini, fim in plano['manual_locks']):
        raise ErroContrato('Trava precisa ter duração positiva.')
    gancho = bruto.get('protected_hook')
    if gancho is not None:
        if not isinstance(gancho, dict) or set(gancho) != {'in_ms', 'out_ms'}:
            raise ErroContrato('Intervalo de gancho inválido.')
        ini, fim = gancho['in_ms'], gancho['out_ms']
        if (type(ini) is not int or type(fim) is not int
                or not clipes[0]['in_ms'] <= ini < fim <= clipes[0]['out_ms']):
            raise ErroContrato('O gancho protegido precisa estar inteiro no primeiro trecho.')
        plano['protected_hook'] = {'in_ms': ini, 'out_ms': fim}
    return plano


def hash_plano(p: dict) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in p.items() if k != 'edit_reason'}, sort_keys=True).encode()).hexdigest()


def validar_acao(a: dict) -> dict:
    if not isinstance(a, dict) or a.get('acao') not in ACOES:
        raise ErroContrato('Correção fora da lista permitida.')
    return {'acao': a['acao'], **_params(ACOES[a['acao']], a, 'correção ' + a['acao'])}


# ---------------------------------------------------------------- relatório do diretor (Agente 4)
def achado(categoria: str, severidade: str, evidencia: str, instrucao: str, *, alvo: str = 'agent5', ini_ms: int | None = None,
           fim_ms: int | None = None, acao: dict | None = None, cena: str = '', confianca: float = 1.0, natureza: str = 'medido') -> dict:
    if severidade not in SEVERIDADES:
        raise ErroContrato('severidade inválida')
    if alvo not in ALVOS:
        raise ErroContrato('alvo inválido')
    return {'category': categoria, 'severity': severidade, 'evidence': evidencia[:300], 'instruction': instrucao[:300], 'target_agent': alvo,
            'time_start_ms': ini_ms, 'time_end_ms': fim_ms, 'action': validar_acao(acao) if acao else None, 'scene': cena[:40],
            'confidence': round(max(0.0, min(1.0, confianca)), 2), 'nature': natureza}


def decidir(nota: int, bloqueios: list) -> bool:
    """Regra fixa: nota >= 70 E nenhum bloqueio. Nota alta nunca passa por cima de bloqueio."""
    return int(nota) >= NOTA_MINIMA and not bloqueios
