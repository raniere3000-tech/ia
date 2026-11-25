"""Registro de capacidades dos agentes: o que existe NESTE servidor e o que cada agente usa.

Regras: nada é instalado sozinho; cada ferramenta externa é só DETECTADA (versão e saúde) e fica atrás de uma chave.
Skills em Markdown (SKILL.md) são orientação para a IA, nunca executáveis. O executor de vídeo é sempre o FFmpeg daqui,
com comandos montados pelo código a partir do plano de edição validado (contratos.py).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import time

import banco as db
from visual_presets import filtros_disponiveis

CACHE = 600
_memo: dict = {'t': 0.0, 'v': None}

EDITOR = {
    'montagem': ('Montagem A/V', ('trim', 'atrim', 'concat'), 'Usar o vídeo recebido ou sinalizar revisão.'),
    'zoom': ('Zoom por intervalo', ('crop', 'scale', 'overlay'), 'Manter o enquadramento de origem.'),
    'legenda': ('Legenda ASS', ('ass',), 'Preservar a mídia e oferecer revisão da legenda.'),
    'normalizacao': ('Normalização sonora', ('loudnorm',), 'Preservar o áudio e informar a limitação.'),
    'broll': ('Camadas de B-roll', ('scale', 'crop', 'overlay'), 'Manter a tomada principal.'),
    'cor': ('Tratamento de cor SDR', ('eq', 'exposure', 'colortemperature'), 'Preservar a cor do vídeo.'),
    'exportacao': ('Exportação configurada', ('fps', 'format'), 'Usar o perfil de exportação existente.'),
    'integridade': ('Verificação de integridade', ('blackdetect', 'freezedetect', 'silencedetect'), 'Marcar o teste técnico como indisponível.'),
}

CATALOGO = [
    {'id': 'ffmpeg', 'nome': 'FFmpeg (editor e medições)', 'agentes': ['agent5', 'agent4', 'agent1'], 'tipo': 'executor',
     'uso': 'Cortes, enquadramento, legenda, áudio e exportação; medições de tela preta, travada, silêncio e volume.', 'obrigatorio': True},
    {'id': 'libvmaf', 'nome': 'VMAF (qualidade de imagem)', 'agentes': ['agent4'], 'tipo': 'medidor', 'opcional': True,
     'uso': 'Compara a exportação com uma versão de referência do MESMO trecho. Não mede viralização e não serve para vídeo recortado.',
     'fonte': 'https://github.com/Netflix/vmaf'},
    {'id': 'auto-editor', 'nome': 'Auto-Editor (achar silêncios)', 'agentes': ['agent5'], 'tipo': 'sugestao', 'opcional': True,
     'uso': 'Só sugere pausas; quem corta é o editor daqui, respeitando trechos travados. Desligado para música e humor.',
     'fonte': 'https://github.com/WyattBlue/auto-editor'},
    {'id': 'youtube-api', 'nome': 'YouTube (referências públicas)', 'agentes': ['agent1', 'agent4'], 'tipo': 'dados', 'opcional': True,
     'uso': 'Vídeos públicos mais vistos do tema para comparar duração; respeita cota e não acessa retenção de outros canais.'},
    {'id': 'skills-texto', 'nome': 'Skills de texto (catálogo)', 'agentes': ['agent1', 'agent3', 'agent4', 'agent5'], 'tipo': 'orientacao',
     'uso': 'Critérios e roteiros em texto, com commit fixo. Não executam nada.'},
    {'id': 'mcp-video', 'nome': 'MCP Video', 'agentes': ['agent5'], 'tipo': 'nao_adotado',
     'uso': 'Não adotado: repete o que o FFmpeg daqui já faz e aumentaria a superfície de risco.', 'fonte': 'https://github.com/rhkiswani/mcp-video'},
    {'id': 'remotion', 'nome': 'Remotion', 'agentes': ['agent5'], 'tipo': 'nao_adotado',
     'uso': 'Não adotado no celular: precisa de Node e Chromium para renderizar e a licença comercial precisa de revisão.',
     'fonte': 'https://github.com/remotion-dev/remotion'},
]


def _rodar(cmd: list, tempo: float = 15) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=tempo, stdin=subprocess.DEVNULL)
        return (r.stdout or '') + (r.stderr or '')
    except (OSError, subprocess.TimeoutExpired):
        return ''


def _detectar(cid: str) -> dict:
    if cid == 'ffmpeg':
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            return {'estado': 'ausente', 'detalhe': 'Instale com: pkg install ffmpeg'}
        m = re.search(r'ffmpeg version (\S+)', _rodar(['ffmpeg', '-hide_banner', '-version']))
        return {'estado': 'ok', 'versao': m.group(1)[:40] if m else '?'}
    if cid == 'libvmaf':
        if not shutil.which('ffmpeg'):
            return {'estado': 'ausente'}
        return {'estado': 'ok'} if re.search(r'\blibvmaf\b', _rodar(['ffmpeg', '-hide_banner', '-filters'])) else \
            {'estado': 'ausente', 'detalhe': 'O FFmpeg deste aparelho não tem o filtro libvmaf. Não faz falta para os cortes.'}
    if cid == 'auto-editor':
        if not shutil.which('auto-editor'):
            return {'estado': 'ausente', 'detalhe': 'Opcional. O editor já acha pausas pela medição de silêncio do FFmpeg.'}
        v = _rodar(['auto-editor', '--version']).strip().splitlines()
        return {'estado': 'ok', 'versao': (v[0] if v else '?')[:40]}
    if cid == 'youtube-api':
        try:
            import agente as ag
            return {'estado': 'ok'} if ag.segredos().get('youtube') else {'estado': 'sem_chave', 'detalhe': 'Preencha a chave do YouTube na aba Agente.'}
        except Exception:  # noqa: BLE001
            return {'estado': 'sem_chave'}
    if cid == 'skills-texto':
        return {'estado': 'ok', 'detalhe': 'Catálogo na aba Skills.'}
    return {'estado': 'nao_adotado'}


def _editor() -> list[dict]:
    filtros = filtros_disponiveis()
    texto = _rodar(['ffmpeg', '-hide_banner', '-encoders']) if filtros else ''
    codificadores = frozenset(re.findall(r'^\s*[VAS][\w.]{5}\s+(\w+)\s', texto, re.M))
    ffprobe = shutil.which('ffprobe')
    resultado = []
    for id_, (nome, exigidos, fallback) in EDITOR.items():
        faltam = sorted(set(exigidos) - filtros)
        if id_ != 'integridade':
            faltam += sorted({'libx264', 'aac'} - codificadores)
        if not ffprobe:
            faltam.append('ffprobe')
        detalhe = 'Faltam: ' + ', '.join(faltam) if faltam else 'Pré-requisitos detectados; a execução é comprovada por recibo.'
        resultado.append({'id': 'editor-' + id_, 'nome': nome, 'agentes': ['agent5'], 'tipo': 'executor',
                          'uso': nome, 'versao': '1', 'estado': 'ausente' if faltam else 'ok',
                          'detalhe': detalhe, 'fallback': fallback, 'faltam': faltam})
    return resultado


def listar(forcar: bool = False) -> dict:
    if not forcar and _memo['v'] and time.time() - _memo['t'] < CACHE:
        return _memo['v']
    if forcar:
        filtros_disponiveis.cache_clear()
    itens = [{**c, **_detectar(c['id'])} for c in CATALOGO] + _editor()
    for item in itens:
        db.executar('INSERT OR REPLACE INTO capability_installs (id, versao, estado, detalhe, conferido) VALUES (?,?,?,?,?)',
                    item['id'], item.get('versao', ''), item['estado'], item.get('detalhe', ''), time.time())
    out = {'capacidades': itens, 'conferido': time.time(),
           'regra': 'Nada é instalado sozinho. Ferramentas externas são só detectadas; skills de texto não executam nada.'}
    _memo.update(t=time.time(), v=out)
    return out


def tem(cid: str) -> bool:
    return any(c['id'] == cid and c['estado'] == 'ok' for c in listar()['capacidades'])
