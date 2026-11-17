"""Diretor de cena: mapa de palco (visto de cima, com o eixo de 180°), animatic leve e prévia A/B de enquadramento.

Tudo usa o MESMO desenho do vídeo final (estilos_codigo.montar), só que pequeno (1/3 do tamanho) e com poucos quadros por
segundo: o que aparece na prévia é o que o vídeo vai mostrar, e custa uma fração do tempo. Nada aqui muda o projeto;
as escolhas da pessoa são salvas pelo editor de cenas de sempre (com conferência de revisão).
"""
from __future__ import annotations

import base64
import hashlib
import json
import shutil
import threading
import time
from pathlib import Path

import estilos_codigo as ec
import fila
import projetos as pj
import renderizador as rd
import rig2d

FPS_ANIMATIC = 8
ESCALA = 3                 # 1/3 da largura e da altura (1/9 dos pontos)
_TRAVA_FPS = threading.Lock()


class ErroDiretor(pj.ErroProjeto):
    pass


def _baixa(W: int, H: int) -> tuple[int, int]:
    return W // ESCALA // 2 * 2, H // ESCALA // 2 * 2


class _fps:
    """Troca o número de quadros por segundo do desenho só durante este render (um trabalho pesado por vez)."""
    def __init__(self, n):
        self.n = n

    def __enter__(self):
        _TRAVA_FPS.acquire()
        self.antes = ec.FPS
        ec.FPS = self.n

    def __exit__(self, *a):
        ec.FPS = self.antes
        _TRAVA_FPS.release()


# ---------------------------------------------------------------- mapa de palco e eixo
def _x_final(el: dict) -> float:
    x = rig2d.POSICOES[el['posicao']]
    for a in el.get('acoes') or []:
        if a['tipo'] in ('andar', 'correr'):
            x = rig2d.POSICOES.get(a.get('alvo') or 'direita', 0.73)
    return x


def _lado(alvo: str, x: float, outro: float) -> bool | None:
    """O personagem em x olha/aponta para o lado do outro? None = alvo neutro (cima, baixo, centro)."""
    if alvo not in ('esquerda', 'direita'):
        return None
    return (alvo == 'direita') == (outro > x)


def checar(cenas: list) -> list:
    """Regras de direção que dá para conferir sem render: eixo de 180° (troca de lado sem motivo),
    olhar para o lado errado numa conversa, close sem dono e planos iguais em sequência."""
    out = []
    antes: dict = {}          # cenário -> posições finais da cena anterior no mesmo lugar
    for c in cenas:
        cid, nome = c.get('id', ''), c.get('titulo') or (c.get('texto') or '')[:30]
        elenco = c.get('elenco') or []
        planos = c.get('planos') or []
        if elenco:
            xs = {e['personagem_id']: rig2d.POSICOES[e['posicao']] for e in elenco}
            andou = {e['personagem_id'] for e in elenco if any(a['tipo'] in ('andar', 'correr') for a in e.get('acoes') or [])}
            ant = antes.get(c.get('cenario_id') or '')
            if ant:
                comuns = [k for k in xs if k in ant]
                for a_ in comuns:
                    for b_ in comuns:
                        if a_ < b_ and (xs[a_] - xs[b_]) * (ant[a_] - ant[b_]) < 0 and not (andou & {a_, b_}):
                            out.append({'tipo': 'eixo', 'severidade': 'media', 'cena': cid,
                                        'descricao': f'Na cena "{nome}", {a_} e {b_} trocaram de lado em relação à cena anterior no mesmo lugar (quebra o eixo de 180°).',
                                        'correcao': 'Mantenha cada um do mesmo lado ou mostre alguém andando para o outro lado.'})
            if len(xs) == 2:
                (p1, x1), (p2, x2) = xs.items()
                for e in elenco:
                    x, outro = (x1, x2) if e['personagem_id'] == p1 else (x2, x1)
                    for a in e.get('acoes') or []:
                        if a['tipo'] in ('olhar', 'apontar', 'entregar', 'acenar') and _lado(a.get('alvo') or '', x, outro) is False:
                            out.append({'tipo': 'direcao_olhar', 'severidade': 'baixa', 'cena': cid,
                                        'descricao': f'Na cena "{nome}", {e["personagem_id"]} faz "{a["tipo"]}" para o lado de fora, longe de quem está na cena.',
                                        'correcao': f'Troque o lado para "{"direita" if outro > x else "esquerda"}" se for para o outro personagem.'})
            if len(xs) > 1:
                for p in planos:
                    if p.get('plano') in ('CU', 'ECU') and not p.get('personagem'):
                        out.append({'tipo': 'close_sem_foco', 'severidade': 'baixa', 'cena': cid, 'plano': p.get('id', ''),
                                    'descricao': f'Na cena "{nome}" há um close sem dizer em quem: a câmera escolhe quem fala.',
                                    'correcao': 'Escolha o personagem do close.'})
            antes[c.get('cenario_id') or ''] = {e['personagem_id']: _x_final(e) for e in elenco}
    return out


def mapa(pid: str) -> dict:
    """Dados do mapa de palco de cada cena: onde cada um está (e para onde anda), a câmera de cada plano e o eixo."""
    p = pj.obter(pid)
    d = p['dados']
    b = d.get('briefing') or {}
    serie = d.get('serie') or {}
    nomes = {k: rig2d.validar_personagem(v)['nome'] for k, v in (serie.get('personagens') or {}).items()}
    cenas = []
    for c in d.get('cenas') or []:
        el = c.get('elenco') or []
        atores = [{'id': e['personagem_id'], 'nome': nomes.get(e['personagem_id'], e['personagem_id']), 'x': rig2d.POSICOES[e['posicao']],
                   'x_fim': _x_final(e), 'cor': rig2d.validar_personagem((serie.get('personagens') or {}).get(e['personagem_id']) or {})['roupa'],
                   'fala': (c.get('personagem') or '') == e['personagem_id']} for e in el]
        eixo = [atores[0]['x'], atores[1]['x']] if len(atores) >= 2 else None
        cenas.append({'id': c.get('id'), 'titulo': c.get('titulo') or (c.get('texto') or '')[:40], 'cenario': c.get('cenario_id') or '',
                      'atores': atores, 'eixo': eixo, 'planos': [{k: x.get(k) for k in ('id', 'plano', 'personagem', 'peso')} for x in c.get('planos') or []]})
    an = d.get('animatic') or {}
    return {'estilo': b.get('estilo'), 'formato': b.get('formato', '9:16'), 'cenas': cenas, 'avisos': checar(d.get('cenas') or []),
            'animatic': an if an.get('versao') == _versao(d) else ({**an, 'desatualizado': True} if an else None)}


# ---------------------------------------------------------------- render pequeno (o mesmo desenho do vídeo final)
def _versao(d: dict) -> str:
    cs = [{k: c.get(k) for k in ('texto', 'titulo', 'destaque', 'numero', 'elementos', 'camera', 'planos', 'elenco', 'cenario_id', 'personagem',
                                 'duracao_alvo', 'estilo', 'clima', 'luz')} | {'a': (c.get('audio') or {}).get('h', '')} for c in d.get('cenas') or []]
    return hashlib.sha256(json.dumps([cs, (d.get('briefing') or {}).get('estilo'), (d.get('briefing') or {}).get('formato'),
                                      d.get('serie')], sort_keys=True, default=str).encode()).hexdigest()[:16]


def _render_pequeno(pid: str, d: dict, i: int, c: dict, pasta: Path, cancelado, fps: int, planos: list | None = None) -> tuple[Path, float]:
    import produtor   # import tardio: produtor importa muita coisa
    b = produtor.limpar_briefing(d.get('briefing') or {})
    W, H = _baixa(*ec.FORMATOS[b['formato']])
    cenas = d.get('cenas') or []
    if planos is not None:
        c = dict(c, planos=ec.validar_planos(planos))
    dur = produtor._dur_cena(c)
    eid, c2, img, audio, imgs_pl, extra = produtor.preparar_cena(pid, i, c, cenas, b, d)
    chave = ec.chave_cena(eid, {k: c2.get(k) for k in ('texto', 'titulo', 'destaque', 'numero', 'unidade', 'elementos', 'camera', 'planos', 'elenco',
                                                         'cenario_id', 'personagem', 'clima', 'luz')},
                          W, H, dur, (c.get('audio') or {}).get('h', ''), (str(img) if img else '') + extra + f'fps{fps}', b['paleta'])
    saida = pasta / f'{chave}.mp4'
    if saida.exists() and saida.stat().st_size > 500:
        return saida, dur
    trab = pasta / f'trab-{chave}'
    shutil.rmtree(trab, ignore_errors=True)
    trab.mkdir(parents=True)
    tmp = pasta / f'{chave}.tmp.mp4'
    with _fps(fps):
        ec.preparar(eid, W, H, dur, b['paleta'] or None, cancelado, cena=c2)
        cmd = ec.montar(eid, c2, W, H, dur, trab, img, audio, tmp, b['paleta'] or None, imgs_pl)
    # o comando já está pronto (as contas de tempo usam o FPS de quando foi montado); roda fora da trava
    rd.rodar(cmd, cancelado, tempo_max=max(300, dur * 60))
    tmp.replace(saida)
    shutil.rmtree(trab, ignore_errors=True)
    return saida, dur


def job_animatic(ctx):
    pid = ctx.dados['projeto']
    p = pj.obter(pid)
    d = p['dados']
    cenas = d.get('cenas') or []
    if not cenas:
        raise RuntimeError('O projeto ainda não tem cenas.')
    pasta = pj.pasta(pid) / 'animatic'
    pasta.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    partes = []
    for i, c in enumerate(cenas):
        ctx.progresso(5 + 80 * i / len(cenas), f'Desenhando a cena {i + 1} de {len(cenas)} (pequena e rápida)')
        try:
            arq, dur = _render_pequeno(pid, d, i, c, pasta, ctx.cancelado, FPS_ANIMATIC)
        except InterruptedError:
            raise fila.Cancelado()
        partes.append(arq)
    ctx.progresso(88, 'Juntando as cenas')
    lista = pasta / 'lista.txt'
    lista.write_text(''.join(f"file '{x.name}'\n" for x in partes))
    v = _versao(d)
    saida = pasta / f'animatic-{v}.mp4'
    try:
        rd.rodar(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(lista), '-c:v', 'libx264', '-preset', 'veryfast',
                  '-crf', '26', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', str(saida)], ctx.cancelado, tempo_max=600)
    except InterruptedError:
        raise fila.Cancelado()
    a = pj.registrar_asset(saida, f'animatic-{v}.mp4', 'video/mp4', pid, 'animatic')['asset']
    info = {'asset': a['id'], 'versao': v, 'duracao': round(rd.duracao(saida), 2), 'segundos_para_fazer': round(time.time() - t0, 1),
            'fps': FPS_ANIMATIC, 'criado': time.time()}
    pj.mudar_dados(pid, lambda dd, _p: dd.update(animatic=info))
    fila.medir('animatic', time.time() - t0, info['duracao'])
    return {'resultado': info, 'etapa': 'Animatic pronto'}


def _quadros(video: Path, tempos: list, pasta: Path, nome: str) -> list:
    out = []
    for k, t in enumerate(tempos):
        arq = pasta / f'{nome}-{k}.jpg'
        rd.rodar(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-ss', f'{t:.3f}', '-i', str(video), '-frames:v', '1', '-q:v', '4', str(arq)], tempo_max=60)
        out.append('data:image/jpeg;base64,' + base64.b64encode(arq.read_bytes()).decode())
    return out


def job_previa_ab(ctx):
    """Mesma cena com dois jeitos de filmar (A e B): devolve quadros de verdade no meio de cada plano."""
    pid, i = ctx.dados['projeto'], int(ctx.dados['cena'])
    d = pj.obter(pid)['dados']
    cenas = d.get('cenas') or []
    if not 0 <= i < len(cenas):
        raise RuntimeError('Cena não encontrada.')
    pasta = pj.pasta(pid) / 'previas'
    pasta.mkdir(parents=True, exist_ok=True)
    res = {}
    for k, nome in enumerate(('a', 'b')):
        ctx.progresso(10 + 40 * k, f'Desenhando a versão {nome.upper()}')
        planos = ec.validar_planos(ctx.dados[nome]) or None
        try:
            arq, dur = _render_pequeno(pid, d, i, cenas[i], pasta, ctx.cancelado, 10, planos if planos else [])
        except InterruptedError:
            raise fila.Cancelado()
        pl = planos or [{'id': 'p1', 'plano': 'WS', 'peso': 1.0}]
        tempos = [(a + b_) / 2 for a, b_ in ec.tempos_planos(pl, dur)]
        res[nome] = [{'plano': x['plano'], 'personagem': x.get('personagem', ''), 't': round(t, 2), 'img': img}
                     for x, t, img in zip(pl, tempos, _quadros(arq, tempos, pasta, f'{arq.stem}-{nome}'))]
    return {'resultado': res, 'etapa': 'Prévia pronta'}


def pedir_animatic(pid: str) -> dict:
    d = pj.obter(pid)['dados']
    if not d.get('cenas'):
        raise ErroDiretor(400, 'O projeto ainda não tem cenas.')
    j = fila.enfileirar('diretor.animatic', agente='agente3', projeto=pid, dados={'projeto': pid}, titulo='Animatic (prévia leve)',
                        chave=f'animatic-{pid}-{_versao(d)}', prioridade=5)
    if j['status'] in ('falhou', 'cancelado'):
        j = fila.tentar_de_novo(j['id'])
    return {'job': j['id'], 'status': j['status']}


def pedir_ab(pid: str, i: int, a: list, b: list) -> dict:
    d = pj.obter(pid)['dados']
    if not 0 <= i < len(d.get('cenas') or []):
        raise ErroDiretor(404, 'Cena não encontrada.')
    if not isinstance(a, list) or not isinstance(b, list) or len(a) > 6 or len(b) > 6:
        raise ErroDiretor(400, 'Planos inválidos.')
    a, b = ec.validar_planos(a), ec.validar_planos(b)
    h = hashlib.sha256(json.dumps([_versao(d), i, a, b], sort_keys=True).encode()).hexdigest()[:16]
    j = fila.enfileirar('diretor.previa_ab', agente='agente3', projeto=pid, dados={'projeto': pid, 'cena': i, 'a': a, 'b': b},
                        titulo=f'Prévia A/B da cena {i + 1}', chave=f'ab-{pid}-{h}', prioridade=6)
    if j['status'] in ('falhou', 'cancelado'):
        j = fila.tentar_de_novo(j['id'])
    return {'job': j['id'], 'status': j['status']}


def estado(jid: str) -> dict:
    j = fila.obter(jid)
    if not j or j['tipo'] not in ('diretor.animatic', 'diretor.previa_ab', 'storyboard.quadros', 'gameplay.analisar', 'gameplay.cortar', 'gameplay.comparar'):
        raise ErroDiretor(404, 'Trabalho não encontrado.')
    return {'id': j['id'], 'status': j['status'], 'etapa': j['etapa'], 'progresso': j['progresso'], 'erro': j['erro'],
            'resultado': json.loads(j['resultado']) if j.get('resultado') else None}


def iniciar():
    fila.registrar('diretor.animatic', job_animatic, 'pesado')
    fila.registrar('diretor.previa_ab', job_previa_ab, 'pesado')
