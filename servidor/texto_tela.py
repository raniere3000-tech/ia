"""Coordenador (Agente 7): o vídeo já tinha texto ou legenda na tela?

Pedido do Raniere (19/11/2026): na revisão final, o Coordenador confere se o vídeo original já mostra algum texto
(legenda embutida, letreiro, nome, placar, marca d'água). Se esse texto fica por baixo ou encostado na legenda que nós
colocamos, o vídeo volta para o editor (Agente 5), que muda a legenda de lugar e passa de novo pelo diretor.

Como confere: 5 quadros do arquivo final vão para a IA de imagem (Gemini), que diz onde fica cada texto original.
A conta de "está em cima da nossa legenda?" é feita aqui, com as faixas que a nossa legenda ocupa em cada posição.
O resultado fica guardado pelo SHA-256 do arquivo (uma conferência por versão do vídeo).
"""
from __future__ import annotations

import base64
import json
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import banco as db

# faixa vertical (fração da altura, 0 = topo) que a NOSSA legenda ocupa em cada posição (agente.montar_ass)
FAIXAS = {'baixo': (0.66, 0.82), 'meio': (0.42, 0.58), 'topo': (0.07, 0.20)}
ALTURAS = {'baixo': 0.78, 'meio': 0.5, 'topo': 0.2}       # o que vai no efeito "caption" do plano do editor
PREFERENCIA = ('baixo', 'meio', 'topo')
FOLGA = 0.02
QUADROS = (0.1, 0.3, 0.5, 0.7, 0.9)
MAX_TENTATIVAS = 3
IA = None              # gancho para testes: IA(quadros: list[Path], info: dict) -> dict no formato pedido à IA


def posicao_da_altura(altura: float | None) -> str:
    a = 0.78 if altura is None else float(altura)
    return 'topo' if a < 0.35 else 'meio' if a < 0.65 else 'baixo'


def _cruza(f: tuple, g: tuple) -> bool:
    return f[0] < g[1] + FOLGA and g[0] < f[1] + FOLGA


def faixas_originais(resposta: dict) -> list[dict]:
    """Textos que já eram do vídeo, com a faixa vertical validada (0..1)."""
    out = []
    for q in (resposta or {}).get('quadros') or []:
        for t in (q or {}).get('textos') or []:
            try:
                y0, y1 = sorted((float(t.get('y0')), float(t.get('y1'))))
            except (TypeError, ValueError):
                continue
            y0, y1 = max(0.0, min(1.0, y0)), max(0.0, min(1.0, y1))
            if y1 - y0 < 0.005:
                continue
            out.append({'y0': round(y0, 3), 'y1': round(y1, 3), 'tipo': str(t.get('tipo') or 'outro')[:20],
                        'texto': str(t.get('texto') or '')[:80], 'quadro': int(q.get('n') or 0)})
    return out


def decidir(resposta: dict, pos: str) -> dict:
    """Junta o que a IA viu com a faixa da nossa legenda. Devolve sobreposta, os textos que batem e a posição livre."""
    textos = faixas_originais(resposta)
    nossa = FAIXAS.get(pos, FAIXAS['baixo'])
    batem = [t for t in textos if _cruza((t['y0'], t['y1']), nossa)]
    sobreposta = bool(batem) or bool((resposta or {}).get('sobreposta') and textos)
    livre = None
    if sobreposta:
        for p in PREFERENCIA:
            if p != pos and not any(_cruza((t['y0'], t['y1']), FAIXAS[p]) for t in textos):
                livre = p
                break
    return {'tem_texto': bool(textos), 'sobreposta': sobreposta, 'textos': textos[:20], 'batem': batem[:10], 'posicao': pos,
            'nova_posicao': livre, 'explicacao': str((resposta or {}).get('explicacao') or '')[:300]}


# ---------------------------------------------------------------- quadros e IA
def _quadros(arq: Path, pasta: Path) -> list[Path]:
    import agente as ag
    dur = ag.duracao(arq)
    if dur <= 0:
        raise RuntimeError('Não consegui ler a duração do vídeo.')
    out = []
    for i, f in enumerate(QUADROS, 1):
        q = pasta / f'q{i}.jpg'
        subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-ss', f'{dur * f:.2f}', '-i', str(arq), '-frames:v', '1', '-vf', 'scale=-2:640',
                        '-q:v', '5', str(q)], capture_output=True, timeout=120, check=False)
        if q.exists() and q.stat().st_size > 500:
            out.append(q)
    if len(out) < 2:
        raise RuntimeError('Não consegui tirar quadros do vídeo.')
    return out


def _pergunta(info: dict) -> str:
    pos = info.get('posicao', 'baixo')
    a, b = FAIXAS.get(pos, FAIXAS['baixo'])
    cor = f' na cor {info["cor"]}' if info.get('cor') else ''
    return (
        'Você é o revisor final de vídeos curtos verticais. As imagens são quadros do MESMO vídeo, em ordem (quadro 1, 2, 3...).\n'
        f'NÓS colocamos uma legenda neste vídeo: 1 a 3 palavras por vez, letras grandes{cor} com contorno, centralizadas, '
        f'na faixa vertical de {a:.2f} a {b:.2f} da altura (0 = topo da imagem, 1 = base). Essa legenda NÃO conta.\n'
        'Procure QUALQUER OUTRO texto que já fazia parte do vídeo original: legenda embutida, letreiro, nome de quem fala, título, '
        'placar, texto de jogo, marca d\'água, logotipo com letras. Para cada texto diga a faixa vertical que ele ocupa (y0 e y1, de 0 a 1).\n'
        'Diga também se algum texto original fica por baixo, por cima ou encostado na nossa legenda.\n'
        'Responda só JSON: {"quadros":[{"n":1,"textos":[{"y0":0.0,"y1":0.0,"tipo":"legenda|letreiro|marca|outro","texto":""}]}],'
        '"sobreposta":false,"explicacao":"uma frase em português simples"}')


def _gemini(quadros: list[Path], info: dict) -> dict:
    import agente as ag
    partes = [{'text': _pergunta(info)}]
    for i, q in enumerate(quadros, 1):
        partes += [{'text': f'quadro {i}'}, {'inline_data': {'mime_type': 'image/jpeg', 'data': base64.b64encode(q.read_bytes()).decode()}}]
    return ag.gemini(partes, tempo=120, uso='cortes')


def analisar(arq: Path, info: dict) -> dict:
    pasta = Path(info.get('pasta') or (Path(arq).parent / f'.texto-{uuid.uuid4().hex[:8]}'))
    pasta.mkdir(parents=True, exist_ok=True)
    try:
        qs = _quadros(Path(arq), pasta)
        resp = (IA or _gemini)(qs, info)
        if not isinstance(resp, dict):
            raise TypeError('A IA respondeu fora do formato combinado.')
        return dict(decidir(resp, info.get('posicao', 'baixo')), quadros=len(qs))
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# ---------------------------------------------------------------- guardado por versão do arquivo
def resultado(sha: str) -> dict | None:
    r = db.um('SELECT * FROM texto_tela WHERE video_sha=?', sha)
    if r:
        r['resultado'] = json.loads(r['resultado'] or '{}')
    return r


def _gravar(sha: str, ref: str, estado: str, res: dict, tentativas: int):
    agora = time.time()
    db.executar('INSERT INTO texto_tela (video_sha, ref, estado, resultado, tentativas, criado, atualizado) VALUES (?,?,?,?,?,?,?) '
                'ON CONFLICT(video_sha) DO UPDATE SET estado=excluded.estado, resultado=excluded.resultado, tentativas=excluded.tentativas, '
                'atualizado=excluded.atualizado', sha, ref, estado, json.dumps(res, ensure_ascii=False), tentativas, agora, agora)


def pedir(ref: str, sha: str, posicao: str, cor: str = '') -> None:
    """Põe a conferência na fila (uma por versão do arquivo; tenta de novo até 3 vezes se a IA falhar)."""
    import fila
    r = resultado(sha)
    n = int(r['tentativas']) if r else 0
    if r and (r['estado'] in ('pronto', 'conferindo') or n >= MAX_TENTATIVAS):
        return
    if r and r['estado'] == 'erro' and time.time() - float(r['atualizado'] or 0) < 300:
        return                                              # espera 5 min antes de tentar de novo
    _gravar(sha, ref, 'conferindo', (r or {}).get('resultado') or {}, n)
    fila.enfileirar('coordenador.texto_tela', agente='agent7', dados={'corte': ref, 'sha': sha, 'posicao': posicao, 'cor': cor},
                    recurso='leve', titulo='Coordenador: texto na tela do vídeo', chave=f'texto_tela:{sha[:24]}:{n + 1}')


def job(ctx):
    """Trabalho da fila: confere o arquivo atual do corte (se ainda for o mesmo SHA)."""
    import agente as ag
    import pipeline as pl
    import postagem as pg
    d = ctx.dados
    sha, ref = d['sha'], d['corte']
    n = int((resultado(sha) or {}).get('tentativas') or 0) + 1
    c = next((x for x in ag.estado()['cortes'] if x['id'] == ref), None)
    try:
        arq = pg.video_path(c['video']) if c else None
    except pg.ErroRede:
        arq = None
    if not arq or pl.sha_arquivo(arq) != sha:
        _gravar(sha, ref, 'erro', {'erro': 'O vídeo mudou ou foi apagado antes da conferência.'}, MAX_TENTATIVAS)
        return {'etapa': 'O vídeo mudou: nada a conferir nesta versão.'}
    ctx.progresso(20, 'Coordenador olhando os quadros do vídeo')
    try:
        res = analisar(arq, {'posicao': d.get('posicao') or 'baixo', 'cor': d.get('cor') or '', 'pasta': ag.TRABALHO / f'texto-{sha[:12]}'})
    except Exception as e:  # noqa: BLE001 - IA fora do ar, sem chave, FFmpeg: registra e tenta de novo depois
        _gravar(sha, ref, 'erro', {'erro': str(e)[:300]}, n)
        return {'etapa': f'Não deu para conferir (tentativa {n} de {MAX_TENTATIVAS}): {str(e)[:120]}'}
    _gravar(sha, ref, 'pronto', res, n)
    return {'etapa': 'Legenda sobreposta a texto do vídeo' if res['sobreposta'] else 'Sem texto por baixo da legenda',
            'resultado': {'sobreposta': res['sobreposta'], 'nova_posicao': res['nova_posicao']}}


def item_do_pacote(c: dict, sha: str, plano: dict | None) -> dict:
    """Item "legenda" da conferência do Coordenador. ok=None quando ainda está conferindo."""
    if not c.get('legendado', True) or (plano is not None and not _legenda_ligada(plano)):
        return {'ok': True, 'detalhe': 'O corte não leva legenda nossa: nada para sobrepor.', 'estado': 'nao_se_aplica'}
    pos = posicao_da_altura(_altura(plano))
    r = resultado(sha)
    if not r or r['estado'] == 'conferindo' or (r['estado'] == 'erro' and int(r['tentativas']) < MAX_TENTATIVAS):
        try:
            pedir(c['id'], sha, pos, str((c.get('qa') or {}).get('cor') or ''))
        except Exception as e:  # noqa: BLE001
            print('texto_tela:', e)
        return {'ok': False, 'detalhe': 'Coordenador conferindo se o vídeo já tem texto ou legenda por baixo da nossa.', 'estado': 'conferindo'}
    res = r['resultado'] or {}
    if r['estado'] == 'erro':
        return {'ok': True, 'estado': 'nao_conferido',
                'detalhe': f'Não deu para conferir texto na tela depois de {r["tentativas"]} tentativas ({(res.get("erro") or "")[:120]}). Seguiu sem essa conferência.'}
    if not res.get('sobreposta'):
        return {'ok': True, 'estado': 'ok', 'resultado': res,
                'detalhe': 'Vídeo sem texto por baixo da legenda.' if not res.get('tem_texto') else 'O vídeo tem texto, mas longe da nossa legenda.'}
    onde = ', '.join(dict.fromkeys(f'{t["y0"]:.0%}–{t["y1"]:.0%} da altura' for t in res.get('batem') or [])) or 'na mesma faixa'
    return {'ok': False, 'estado': 'sobreposta', 'resultado': res, 'nova_posicao': res.get('nova_posicao'),
            'detalhe': f'A legenda fica em cima de um texto que já estava no vídeo ({onde}). ' +
                       (f'Vai para o editor mudar a legenda para {res["nova_posicao"]}.' if res.get('nova_posicao') else
                        'Não há lugar livre na tela: precisa da sua decisão.')}


def _legenda_ligada(plano: dict) -> bool:
    cap = next((e for e in plano.get('effects') or [] if e.get('tipo') == 'caption'), None)
    return bool(cap and cap.get('ligado', 1))


def _altura(plano: dict | None) -> float | None:
    cap = next((e for e in (plano or {}).get('effects') or [] if e.get('tipo') == 'caption'), None)
    return cap.get('altura') if cap else None


def iniciar():
    import fila
    fila.registrar('coordenador.texto_tela', job, 'leve')
