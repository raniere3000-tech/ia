"""Ferramentas externas (seção 7 do pacote v2): ficha de cada uma, teste de funcionamento e chave liga/desliga.

Regras:
- Nada é baixado nem instalado por aqui. O servidor só DETECTA o que você instalou.
- Uma ferramenta só pode ser LIGADA quando: (1) você marcou a licença como conferida (lendo o arquivo LICENSE e o das dependências)
  e (2) o teste de funcionamento passou neste aparelho. Desligada, o fluxo usa o que já existe (FFmpeg) e a tela diz isso.
- "licenca_declarada" é o que o pacote v2 informa ou None. Não é auditoria.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import banco as db

# status: em_uso | adaptador_opcional | so_referencia | nao_adotado | nao_auditado
FICHAS = [
    {'id': 'ffmpeg', 'capacidade': 'Editar, medir e exportar vídeo', 'repo': 'https://ffmpeg.org', 'agentes': [1, 4, 5], 'tipo': 'executavel',
     'status': 'em_uso', 'so': 'Termux/Linux', 'custo': 'grátis', 'fallback': '—', 'licenca_declarada': 'LGPL/GPL (pacote do sistema)'},
    {'id': 'auto-editor', 'capacidade': 'Achar pausas (silêncios)', 'repo': 'https://github.com/WyattBlue/auto-editor', 'agentes': [5], 'tipo': 'executavel',
     'status': 'adaptador_opcional', 'so': 'Linux; Termux não conferido', 'custo': 'grátis', 'fallback': 'Medição de silêncio do FFmpeg (silencedetect)',
     'licenca_declarada': None, 'limite': 'Adaptador escrito, mas NÃO testado com o programa real (não foi instalado aqui). Só liga depois que o teste passar no seu aparelho.'},
    {'id': 'libvmaf', 'capacidade': 'Qualidade de imagem (VMAF)', 'repo': 'https://github.com/Netflix/vmaf', 'agentes': [4], 'tipo': 'executavel',
     'status': 'adaptador_opcional', 'so': 'FFmpeg com libvmaf', 'custo': 'grátis', 'fallback': 'Sem VMAF: a nota usa as medições do FFmpeg',
     'licenca_declarada': None, 'limite': 'Só compara duas versões do MESMO trecho. Não mede viralização e não entra na nota.'},
    {'id': 'remotion', 'capacidade': 'Composição e títulos complexos', 'repo': 'https://github.com/remotion-dev/remotion', 'agentes': [5], 'tipo': 'executavel',
     'status': 'nao_adotado', 'so': 'Precisa de Node e Chromium', 'custo': 'licença comercial a revisar', 'fallback': 'Renderizador FFmpeg daqui',
     'licenca_declarada': None, 'limite': 'Pesado para o celular; licença comercial precisa de revisão.'},
    {'id': 'mcp-video', 'capacidade': 'Abstração de edição', 'repo': 'https://github.com/rhkiswani/mcp-video', 'agentes': [5], 'tipo': 'executavel',
     'status': 'nao_adotado', 'so': '—', 'custo': '—', 'fallback': 'Plano de edição tipado + FFmpeg', 'licenca_declarada': None,
     'limite': 'Repete o que o editor daqui já faz.'},
    {'id': 'cuesync', 'capacidade': 'Acertar o tempo das legendas', 'repo': 'https://github.com/nicochunger/cuesync', 'agentes': [4, 5], 'tipo': 'executavel',
     'status': 'nao_auditado', 'so': 'não conferido', 'custo': '—', 'fallback': 'Legenda pelos tempos da transcrição', 'licenca_declarada': None},
    {'id': 'yt-factcheck', 'capacidade': 'Checagem de fatos', 'repo': 'https://github.com/mickpletcher/yt-factcheck', 'agentes': [3, 4], 'tipo': 'referencia',
     'status': 'nao_auditado', 'so': '—', 'custo': '—', 'fallback': 'checagem_fatos.py (trecho literal achado no texto da fonte)', 'licenca_declarada': None},
    {'id': 'moneyprinterturbo', 'capacidade': 'Fábrica tema→vídeo', 'repo': 'https://github.com/harry0703/MoneyPrinterTurbo', 'agentes': [3], 'tipo': 'referencia',
     'status': 'nao_auditado', 'so': '—', 'custo': '—', 'fallback': 'produtor.py (Agente 3)', 'licenca_declarada': None},
    {'id': 'openreels', 'capacidade': 'Vídeos verticais', 'repo': 'https://github.com/tsensei/OpenReels', 'agentes': [3, 5], 'tipo': 'referencia',
     'status': 'nao_auditado', 'so': '—', 'custo': '—', 'fallback': 'produtor.py + renderizador.py', 'licenca_declarada': None},
    {'id': 'tubelab-research', 'capacidade': 'Pesquisa de nichos', 'repo': 'https://github.com/TubeLabHQ/youtube-research-skills', 'agentes': [1, 3], 'tipo': 'skill',
     'status': 'nao_auditado', 'so': '—', 'custo': 'pode exigir conta', 'fallback': 'Radar + YouTube Data API', 'licenca_declarada': None},
    {'id': 'youtube-data-skills', 'capacidade': 'Sinais do YouTube', 'repo': 'https://github.com/nikhilbhansali/youtube-data-skills', 'agentes': [1, 3], 'tipo': 'skill',
     'status': 'nao_auditado', 'so': '—', 'custo': 'cota da API', 'fallback': 'inteligencia_viral.py', 'licenca_declarada': None},
    {'id': 'auto-video-editor', 'capacidade': 'Seleção de cortes', 'repo': 'https://github.com/kiy0ni/auto-video-editor', 'agentes': [1, 5], 'tipo': 'referencia',
     'status': 'nao_auditado', 'so': '—', 'custo': '—', 'fallback': 'agente.py (escolha de trechos)', 'licenca_declarada': None},
    {'id': 'ai-shorts-generator', 'capacidade': 'Shorts a partir de longos', 'repo': 'https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator', 'agentes': [1],
     'tipo': 'referencia', 'status': 'nao_auditado', 'so': '—', 'custo': '—', 'fallback': 'agente.py', 'licenca_declarada': None},
    {'id': 'visual-storytelling', 'capacidade': 'Storyboard e entidades', 'repo': 'https://github.com/leynos/visual-storytelling-skills', 'agentes': [3, 4], 'tipo': 'skill',
     'status': 'nao_auditado', 'so': '—', 'custo': '—', 'fallback': 'storyboard.py', 'licenca_declarada': None},
    {'id': 'character-continuity', 'capacidade': 'Identidade de personagem', 'repo': 'https://github.com/Nagacash/character-continuity-skill', 'agentes': [3, 4],
     'tipo': 'skill', 'status': 'nao_auditado', 'so': '—', 'custo': '—', 'fallback': 'series.py (fichas e versões)', 'licenca_declarada': None},
    {'id': 'scenario-skills', 'capacidade': 'Referências e assets', 'repo': 'https://github.com/scenario-labs/skills', 'agentes': [3, 4], 'tipo': 'skill',
     'status': 'nao_auditado', 'so': '—', 'custo': 'pode ser pago', 'fallback': 'biblioteca das séries', 'licenca_declarada': None},
    {'id': 'video-production-skills', 'capacidade': 'Direção e roteiro', 'repo': 'https://github.com/sb-dev/video-production-skills', 'agentes': [3, 4], 'tipo': 'skill',
     'status': 'nao_auditado', 'so': '—', 'custo': '—', 'fallback': 'catálogo de skills', 'licenca_declarada': None},
    {'id': 'video-studio-skills', 'capacidade': 'Direção e roteiro', 'repo': 'https://github.com/g0dam/video-studio-skills', 'agentes': [3, 4], 'tipo': 'skill',
     'status': 'nao_auditado', 'so': '—', 'custo': '—', 'fallback': 'catálogo de skills', 'licenca_declarada': None},
    {'id': 'kalaris-research', 'capacidade': 'Pesquisa verificável', 'repo': 'https://github.com/KalarisLabs/research-agent-skills', 'agentes': [3, 4], 'tipo': 'skill',
     'status': 'nao_auditado', 'so': '—', 'custo': '—', 'fallback': 'checagem_fatos.py', 'licenca_declarada': None},
    {'id': 'qc-video', 'capacidade': 'Controle técnico', 'repo': 'https://github.com/ddfzhh/qc-video', 'agentes': [4], 'tipo': 'referencia',
     'status': 'nao_auditado', 'so': '—', 'custo': '—', 'fallback': 'diretor_qualidade.py (medições FFmpeg)', 'licenca_declarada': None},
    {'id': 'ai-video-qc', 'capacidade': 'Controle técnico', 'repo': 'https://github.com/jackships/ai-video-qc', 'agentes': [4], 'tipo': 'referencia',
     'status': 'nao_auditado', 'so': '—', 'custo': '—', 'fallback': 'diretor_qualidade.py', 'licenca_declarada': None},
    {'id': 'ffmpeg-skill', 'capacidade': 'FFmpeg por comandos seguros', 'repo': 'https://github.com/kajisho5/ffmpeg-skill', 'agentes': [5], 'tipo': 'skill',
     'status': 'nao_auditado', 'so': '—', 'custo': '—', 'fallback': 'contratos.py (operações tipadas)', 'licenca_declarada': None},
    {'id': 'postiz', 'capacidade': 'Calendário de redes', 'repo': 'https://github.com/gitroomhq/postiz-app', 'agentes': [2], 'tipo': 'referencia',
     'status': 'so_referencia', 'so': '—', 'custo': '—', 'fallback': 'agenda_postagem.py', 'licenca_declarada': 'AGPL-3.0 (segundo o pacote v2)',
     'limite': 'Só como referência de tela: AGPL exige analisar obrigações antes de usar código.'},
    {'id': 'openmontage', 'capacidade': 'Pipeline alternativo', 'repo': 'https://github.com/m-fyi/openmontage', 'agentes': [3, 5], 'tipo': 'referencia',
     'status': 'so_referencia', 'so': '—', 'custo': '—', 'fallback': 'esteira atual', 'licenca_declarada': 'AGPL-3.0 (segundo o pacote v2)'},
    {'id': 'film-production-skills', 'capacidade': 'Planejamento audiovisual', 'repo': 'https://github.com/zhangzhangco/film-production-skills', 'agentes': [3],
     'tipo': 'skill', 'status': 'nao_auditado', 'so': '—', 'custo': '—', 'fallback': 'storyboard.py', 'licenca_declarada': None},
]
NOMES_STATUS = {'em_uso': 'Em uso', 'adaptador_opcional': 'Adaptador opcional', 'so_referencia': 'Só referência', 'nao_adotado': 'Não adotado',
                'nao_auditado': 'Licença não conferida'}
TESTAVEIS = ('ffmpeg', 'auto-editor', 'libvmaf')


class ErroIntegracao(Exception):
    def __init__(self, msg: str, status: int = 400):
        super().__init__(msg)
        self.status = status


def _reg() -> dict:
    v = db.kv('integracoes')
    return v if isinstance(v, dict) else {}


def _ficha(iid: str) -> dict:
    f = next((x for x in FICHAS if x['id'] == iid), None)
    if not f:
        raise ErroIntegracao('Ferramenta desconhecida.', 404)
    return f


def listar() -> dict:
    reg = _reg()
    out = []
    for f in FICHAS:
        r = reg.get(f['id']) or {}
        out.append({**f, 'nome_status': NOMES_STATUS[f['status']], 'ref_commit': r.get('ref_commit'), 'licenca_auditada': bool(r.get('licenca_auditada')),
                    'nota_licenca': r.get('nota_licenca', ''), 'habilitada': f['status'] == 'em_uso' or bool(r.get('habilitada')),
                    'teste_smoke': r.get('teste'), 'testavel': f['id'] in TESTAVEIS})
    return {'ferramentas': out, 'regra': 'Nada é instalado por aqui. Ligar exige licença conferida por você e teste de funcionamento aprovado neste aparelho.'}


def habilitada(iid: str) -> bool:
    return bool((_reg().get(iid) or {}).get('habilitada'))


def _video_teste(pasta: Path) -> Path:
    arq = pasta / 't.mp4'
    subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=gray:s=320x568:d=4:r=15', '-f', 'lavfi', '-i',
                    'sine=f=440:d=1.5', '-af', 'apad=whole_dur=4', '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', '-t', '4', str(arq)],
                   check=True, timeout=60, capture_output=True)
    return arq


def testar(iid: str) -> dict:
    """Teste de funcionamento NESTE aparelho, com um vídeo de 4 s gerado aqui. Grava o resultado (não liga nada)."""
    _ficha(iid)
    if iid not in TESTAVEIS:
        res = {'ok': False, 'detalhe': 'Sem teste: esta ferramenta não foi integrada (só ficha). Ver a coluna "alternativa".'}
    else:
        try:
            with tempfile.TemporaryDirectory() as td:
                res = _testar(iid, Path(td))
        except Exception as e:  # noqa: BLE001
            res = {'ok': False, 'detalhe': 'Falhou: ' + str(e)[:200]}
    res['t'] = time.time()
    reg = _reg()
    reg.setdefault(iid, {})['teste'] = res
    if not res['ok']:
        reg[iid]['habilitada'] = False           # teste falhou: volta para a alternativa
    db.kv_gravar('integracoes', reg)
    return res


def _testar(iid: str, pasta: Path) -> dict:
    if not shutil.which('ffmpeg'):
        return {'ok': False, 'detalhe': 'FFmpeg não encontrado (pkg install ffmpeg).'}
    if iid == 'ffmpeg':
        v = _video_teste(pasta)
        return {'ok': v.stat().st_size > 0, 'detalhe': 'Gerou e leu um vídeo de 4 s.'}
    if iid == 'libvmaf':
        v = _video_teste(pasta)
        r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(v), '-i', str(v), '-lavfi', 'libvmaf', '-f', 'null', '-'], capture_output=True,
                           text=True, timeout=120)
        return {'ok': r.returncode == 0, 'detalhe': 'VMAF rodou.' if r.returncode == 0 else 'O FFmpeg daqui não tem libvmaf: ' + r.stderr[-160:]}
    if iid == 'auto-editor':
        if not shutil.which('auto-editor'):
            return {'ok': False, 'detalhe': 'Auto-Editor não está instalado. A medição de silêncio do FFmpeg continua sendo usada.'}
        v = _video_teste(pasta)
        silencios = pausas_auto_editor(v, pasta)
        ok = any(a >= 1.0 for a, _ in silencios)          # o vídeo de teste tem som até 1,5 s e silêncio depois
        return {'ok': ok, 'detalhe': f'Achou {len(silencios)} pausa(s) no vídeo de teste.' if ok else 'Rodou, mas não achou a pausa esperada no vídeo de teste.'}
    return {'ok': False, 'detalhe': 'Sem teste.'}


def pausas_ffmpeg(arq: Path, limiar_db: int = -40, minimo: float = 0.6) -> list:
    r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'info', '-i', str(arq), '-map', '0:a:0', '-af', f'silencedetect=n={limiar_db}dB:d={minimo}', '-f', 'null', '-'],
                       capture_output=True, text=True, timeout=600)
    ini, out = None, []
    for ln in r.stderr.splitlines():
        if 'silence_start:' in ln:
            ini = float(ln.split('silence_start:')[1].split()[0])
        elif 'silence_end:' in ln and ini is not None:
            out.append((round(ini, 2), round(float(ln.split('silence_end:')[1].split()[0]), 2)))
            ini = None
    return out


def pausas_auto_editor(arq: Path, pasta: Path) -> list:
    """Adaptador do Auto-Editor: pede a linha do tempo em JSON e devolve os trechos que ele cortaria (silêncios). Argumentos fixos, sem shell."""
    saida = pasta / 'ae.json'
    for exp in (['--export', 'v3'], ['--export', 'timeline:api=1']):
        r = subprocess.run(['auto-editor', str(arq), *exp, '-o', str(saida), '--no-open'], capture_output=True, text=True, timeout=300)
        if r.returncode == 0 and saida.exists():
            break
    else:
        raise RuntimeError('o Auto-Editor não exportou a linha do tempo nesta versão')
    d = json.loads(saida.read_text())
    fps = float(d.get('timebase', '30/1').split('/')[0]) / float(d.get('timebase', '30/1').split('/')[1]) if isinstance(d.get('timebase'), str) else 30.0
    mantidos = []
    for trilha in d.get('v') or []:
        for c in trilha:
            mantidos.append((c['start'] / fps, (c['start'] + c['dur']) / fps))
    if not mantidos and d.get('chunks'):
        mantidos = [(a / fps, b / fps) for a, b, vel in d['chunks'] if vel not in (0, 99999)]
    mantidos.sort()
    out, fim = [], 0.0
    for a, b in mantidos:
        if a - fim >= 0.3:
            out.append((round(fim, 2), round(a, 2)))
        fim = max(fim, b)
    return out


def pausas(arq: Path) -> dict:
    """Pausas do vídeo. Usa o Auto-Editor só se estiver LIGADO (licença + teste); senão, ou se ele falhar, usa o FFmpeg e diz."""
    if habilitada('auto-editor') and shutil.which('auto-editor'):
        try:
            with tempfile.TemporaryDirectory() as td:
                return {'fonte': 'auto-editor', 'pausas': pausas_auto_editor(arq, Path(td)), 'aviso': ''}
        except Exception as e:  # noqa: BLE001
            return {'fonte': 'ffmpeg', 'pausas': pausas_ffmpeg(arq), 'aviso': f'Auto-Editor falhou ({str(e)[:80]}); usei o FFmpeg.'}
    return {'fonte': 'ffmpeg', 'pausas': pausas_ffmpeg(arq), 'aviso': ''}


def ligar(iid: str, on: bool, quem: str = 'site', licenca_ok: bool | None = None, nota: str = '', ref_commit: str = '') -> dict:
    f = _ficha(iid)
    reg = _reg()
    r = reg.setdefault(iid, {})
    if licenca_ok is not None:
        r.update(licenca_auditada=bool(licenca_ok), nota_licenca=nota[:300], ref_commit=ref_commit[:40] or r.get('ref_commit'), auditada_por=quem[:80])
    if on:
        if f['status'] not in ('adaptador_opcional',):
            raise ErroIntegracao('Esta ferramenta não tem adaptador neste servidor (só ficha). Não dá para ligar.', 409)
        if not r.get('licenca_auditada'):
            raise ErroIntegracao('Marque a licença como conferida (você leu o LICENSE e o das dependências) antes de ligar.', 412)
        if not (r.get('teste') or {}).get('ok'):
            raise ErroIntegracao('Rode o teste de funcionamento neste aparelho. Só liga se passar.', 412)
    r['habilitada'] = bool(on)
    db.kv_gravar('integracoes', reg)
    db.evento(quem, 'integracao_' + ('ligada' if on else 'desligada'), 'integracao:' + iid)
    return next(x for x in listar()['ferramentas'] if x['id'] == iid)
