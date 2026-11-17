"""Terceira porta de aprovação: o STORYBOARD VISUAL (Pauta -> Roteiro -> Storyboard visual -> Vídeo final).

Cada cena ganha miniaturas tiradas de uma prévia REAL (o mesmo desenho pequeno do diretor de cena). A aprovação é por cena e
guarda o hash da versão aprovada: mudar uma cena invalida só a aprovação dela (e só ela é redesenhada); as outras seguem
aprovadas e vêm do cache. Esta porta NÃO substitui a aprovação do vídeo final, que continua sendo sua.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import banco as db
import estilos_codigo as ec
import fila
import projetos as pj
import renderizador as rd

FPS_QUADROS = 8
CAMPOS = ('texto', 'titulo', 'destaque', 'numero', 'unidade', 'elementos', 'camera', 'planos', 'elenco', 'cenario_id', 'personagem',
          'duracao_alvo', 'estilo', 'clima', 'luz')
EDITAVEIS = ('camera', 'duracao_alvo', 'planos', 'personagem', 'texto', 'titulo', 'estilo', 'elenco')


class ErroStoryboard(pj.ErroProjeto):
    pass


def _cid(c: dict, i: int) -> str:
    return str(c.get('id') or f'c{i + 1}')


def hash_cena(c: dict, d: dict) -> str:
    """Versão material da cena: texto, câmera, planos, elenco, estilo, duração e o áudio já gerado. Mudou algo daqui, a aprovação cai."""
    b = d.get('briefing') or {}
    base = {k: c.get(k) for k in CAMPOS}
    base['audio'] = (c.get('audio') or {}).get('h', '')
    base['imagem'] = (c.get('imagem') or {}).get('h', '')
    return hashlib.sha256(json.dumps([base, b.get('estilo'), b.get('formato'), (d.get('serie') or {}).get('personagens')], sort_keys=True, default=str).encode()).hexdigest()[:16]


def hash_geral(d: dict) -> str:
    return hashlib.sha256(json.dumps([hash_cena(c, d) for c in d.get('cenas') or []]).encode()).hexdigest()[:16]


def porta_ativa(d: dict) -> bool:
    b = d.get('briefing') or {}
    return bool(b.get('porta_storyboard')) and b.get('modo_aprovacao') == 'assistido'


def estado(pid: str) -> dict:
    d = pj.obter(pid)['dados']
    sb = d.get('storyboard') or {}
    quadros, aprov = sb.get('quadros') or {}, sb.get('aprovados') or {}
    cenas = []
    for i, c in enumerate(d.get('cenas') or []):
        cid, h = _cid(c, i), hash_cena(c, d)
        q = quadros.get(cid)
        fresco = bool(q and q.get('hash') == h)
        a = aprov.get(cid)
        ok = bool(a and a.get('hash') == h)
        cenas.append({'id': cid, 'n': i + 1, 'titulo': c.get('titulo') or (c.get('texto') or '')[:50], 'hash': h,
                      'quadros': q['frames'] if fresco else [], 'quadros_desatualizados': bool(q and not fresco),
                      'status': 'aprovada' if ok else ('pronta_para_conferir' if fresco else ('mudou_depois_de_aprovar' if a else 'sem_miniatura')),
                      'ja_aprovada_antes': bool(a and not ok),
                      'camera': c.get('camera') or '', 'duracao': c.get('duracao_alvo'), 'personagem': c.get('personagem') or '',
                      'estilo': c.get('estilo') or (d.get('briefing') or {}).get('estilo', ''), 'aprovada_por': a.get('por') if ok else ''})
    ok = bool(cenas) and all(x['status'] == 'aprovada' for x in cenas)
    return {'ativa': porta_ativa(d), 'cenas': cenas, 'todas_aprovadas': ok, 'versao': hash_geral(d),
            'faltam': [x['n'] for x in cenas if x['status'] != 'aprovada'], 'boas_praticas': sb.get('boas_praticas') or [], 'aviso_final': 'Aprovar o storyboard não publica nada: o vídeo final ainda precisa da sua aprovação.'}


def pendentes(pid: str) -> list:
    return estado(pid)['faltam']


def _frames(video: Path, tempos: list, pasta: Path, nome: str) -> list:
    out = []
    for k, t in enumerate(tempos):
        arq = pasta / f'{nome}-{k}.jpg'
        rd.rodar(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-ss', f'{t:.3f}', '-i', str(video), '-frames:v', '1', '-vf', 'scale=320:-2', '-q:v', '5', str(arq)], tempo_max=60)
        out.append(arq)
    return out


def job_quadros(ctx):
    import diretor
    pid = ctx.dados['projeto']
    alvo = set(ctx.dados.get('cenas') or [])
    p = pj.obter(pid)
    d = p['dados']
    cenas = d.get('cenas') or []
    pasta = pj.pasta(pid) / 'storyboard'
    pasta.mkdir(parents=True, exist_ok=True)
    feitos, reaproveitados = 0, 0
    sb0 = d.get('storyboard') or {}
    for i, c in enumerate(cenas):
        cid, h = _cid(c, i), hash_cena(c, d)
        if alvo and cid not in alvo:
            continue
        q = (sb0.get('quadros') or {}).get(cid)
        if q and q.get('hash') == h:
            reaproveitados += 1
            continue                                   # cena sem mudança: não redesenha
        ctx.progresso(5 + 90 * i / max(1, len(cenas)), f'Desenhando o quadro da cena {i + 1} de {len(cenas)}')
        try:
            arq, dur = diretor._render_pequeno(pid, d, i, c, pasta, ctx.cancelado, FPS_QUADROS)
        except InterruptedError:
            raise fila.Cancelado()
        pl = ec.validar_planos(c.get('planos') or []) or [{'id': 'p1', 'plano': 'WS', 'peso': 1.0}]
        tempos = [(a + b_) / 2 for a, b_ in ec.tempos_planos(pl, dur)]
        imgs = _frames(arq, tempos, pasta, f'{cid}-{h}')
        frames = []
        for x, t, im in zip(pl, tempos, imgs):
            a = pj.registrar_asset(im, im.name, 'image/jpeg', pid, 'storyboard')['asset']
            frames.append({'asset': a['id'], 't': round(t, 2), 'plano': x.get('plano', ''), 'personagem': x.get('personagem', ''), 'angulo': x.get('angulo', '')})
        novo = {'hash': h, 'frames': frames, 'criado': time.time(), 'duracao': round(dur, 2)}
        pj.mudar_dados(pid, lambda dd, _p, cid=cid, novo=novo: dd.setdefault('storyboard', {}).setdefault('quadros', {}).__setitem__(cid, novo))
        feitos += 1
    try:      # boas práticas para VOCÊ conferir ao aprovar os quadros (nada é decidido por elas)
        from skills import roteador
        dica = roteador.lista_para_voce('diretor.storyboard_visual', f'quadros:{pid}:{hash_geral(pj.obter(pid)["dados"])}',
                                        f'{feitos + reaproveitados} cenas com miniaturas', projeto_id=pid, origem='diretor')
        pj.mudar_dados(pid, lambda dd, _p: dd.setdefault('storyboard', {}).__setitem__('boas_praticas', dica))
    except Exception:  # noqa: BLE001
        pass
    return {'resultado': {'desenhadas': feitos, 'reaproveitadas': reaproveitados}, 'etapa': 'Quadros prontos'}


def pedir(pid: str, cenas: list | None = None) -> dict:
    d = pj.obter(pid)['dados']
    if not d.get('cenas'):
        raise ErroStoryboard(400, 'O projeto ainda não tem cenas.')
    ids = sorted(str(x) for x in (cenas or []))
    j = fila.enfileirar('storyboard.quadros', agente='agente3', projeto=pid, dados={'projeto': pid, 'cenas': ids}, titulo='Quadros do storyboard',
                        chave=f'storyboard-{pid}-{hash_geral(d)}-{",".join(ids)}', prioridade=5)
    if j['status'] in ('falhou', 'cancelado'):
        j = fila.tentar_de_novo(j['id'])
    return {'job': j['id'], 'status': j['status']}


def aprovar(pid: str, cenas: list | None, por: str) -> dict:
    """Aprova as cenas (ou todas) NA VERSÃO ATUAL, que precisa ter miniatura de prévia real. Libera o trabalho que esperava esta porta."""
    est = estado(pid)
    alvo = [x for x in est['cenas'] if not cenas or x['id'] in set(map(str, cenas))]
    if not alvo:
        raise ErroStoryboard(404, 'Cena não encontrada.')
    sem = [x['n'] for x in alvo if x['status'] in ('sem_miniatura', 'mudou_depois_de_aprovar') and not x['quadros']]
    if sem:
        raise ErroStoryboard(409, f'As cenas {", ".join(map(str, sem))} ainda não têm quadro atualizado para conferir. Gere os quadros primeiro.')
    agora = time.time()

    def f(d, _p):
        ap = d.setdefault('storyboard', {}).setdefault('aprovados', {})
        atuais = {_cid(c, i): hash_cena(c, d) for i, c in enumerate(d.get('cenas') or [])}
        for x in alvo:
            if atuais.get(x['id']) != x['hash']:
                raise ErroStoryboard(409, 'A cena mudou enquanto você conferia. Confira de novo.')
            ap[x['id']] = {'hash': x['hash'], 't': agora, 'por': por}
        return {}
    pj.mudar_dados(pid, f)
    db.evento(por, 'storyboard_aprovado', 'projeto:' + pid, {'cenas': [x['id'] for x in alvo]})
    novo = estado(pid)
    if novo['todas_aprovadas']:
        for j in db.todos("SELECT id FROM jobs WHERE projeto=? AND status='aguardando_aprovacao'", pid):
            fila.liberar(j['id'])
    return novo


def corrigir(pid: str, cena: str, mudancas: dict, por: str) -> dict:
    """Corrige UMA cena (câmera, duração, planos, personagem, texto...). Só a aprovação dela cai; só ela é redesenhada."""
    if not isinstance(mudancas, dict) or not (set(mudancas) & set(EDITAVEIS)):
        raise ErroStoryboard(400, 'Nada para corrigir.')

    def f(d, _p):
        for i, c in enumerate(d.get('cenas') or []):
            if _cid(c, i) == str(cena):
                for k in EDITAVEIS:
                    if k not in mudancas:
                        continue
                    v = mudancas[k]
                    if k == 'planos':
                        v = ec.validar_planos(v)
                    elif k == 'camera':
                        if v not in ec.CAMERAS:
                            raise ErroStoryboard(400, 'Câmera inválida.')
                    elif k == 'duracao_alvo':
                        try:
                            v = round(max(1.0, min(60.0, float(v))), 1)
                        except (TypeError, ValueError):
                            raise ErroStoryboard(400, 'Duração inválida.')
                    elif k in ('texto', 'titulo'):
                        v = str(v)[:600]
                    c[k] = v
                return {}
        raise ErroStoryboard(404, 'Cena não encontrada.')
    pj.mudar_dados(pid, f)
    db.evento(por, 'storyboard_cena_corrigida', 'projeto:' + pid, {'cena': str(cena), 'campos': sorted(set(mudancas) & set(EDITAVEIS))})
    return {**estado(pid), **pedir(pid, [str(cena)])}


def iniciar():
    fila.registrar('storyboard.quadros', job_quadros, 'pesado')
