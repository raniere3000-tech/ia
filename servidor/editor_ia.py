"""Agente 5, editor de IA: transforma o pedido de corte num plano de edição (EditPlan) e aplica as correções do diretor.

Segurança: o plano só tem campos de listas fechadas e números presos em faixas (contratos.validar_plano). O filtro do FFmpeg
é montado aqui com números já validados; nenhum texto vindo de IA entra no comando.

Ciclo (pipeline.py manda nas regras):
  plano -> render -> SHA-256 -> diretor (avaliar_final) -> política 70/5 -> aprovado (certificado) | corrigir | revisão manual.
Falha técnica do render (FFmpeg, falta de espaço...) sobe como exceção: a fila tenta de novo e isso NÃO conta como correção.
"""
from __future__ import annotations

import copy
import json
import os
import time
import subprocess
from pathlib import Path

import banco as db
import contratos as ct
import esteira as es
import pipeline as pl

TAMANHOS = {'pequeno': 62 / 1080, 'medio': 78 / 1080, 'grande': 96 / 1080}
ORDEM_TAMANHO = ['pequeno', 'medio', 'grande']
ALTURA = {'baixo': 0.78, 'meio': 0.5, 'topo': 0.2}
QUADRO_PARA_MODO = {'desfoque': 'desfocado', 'cortar': 'centro', 'gameplay-streamer': 'manter'}
MODO_PARA_QUADRO = {'desfocado': 'desfoque', 'centro': 'cortar'}
FOLGA_PAUSA_MS = 250


def _efeito(plano: dict, tipo: str) -> dict | None:
    return next((e for e in plano['effects'] if e['tipo'] == tipo), None)


def _tamanho_nome(frac: float) -> str:
    return min(TAMANHOS, key=lambda k: abs(TAMANHOS[k] - frac))


# ---------------------------------------------------------------- pedido -> plano
def plano_do_corte(c: dict, tpl: dict, dur_fonte: float | None = None, motivo: str = 'Plano inicial do corte.') -> dict:
    """Plano inicial a partir do corte escolhido (ini/fim em segundos) e do modelo sorteado."""
    efeitos = [{'tipo': 'zoom', 'nivel': max(1.0, min(1.6, float(tpl.get('zoom') or 1.0))), 'ini_ms': 0,
                'fim_ms': int((c['fim'] - c['ini']) * 1000)},
               {'tipo': 'reframe', 'modo': QUADRO_PARA_MODO.get(tpl.get('enquadramento'), 'manter')}]
    if tpl.get('legenda', 'nenhuma') != 'nenhuma':
        efeitos.append({'tipo': 'caption', 'ligado': 1, 'tamanho': round(TAMANHOS.get(tpl.get('tamanho'), TAMANHOS['medio']), 4),
                        'altura': ALTURA.get(tpl.get('legenda_pos'), 0.78)})
    if tpl.get('loudnorm'):
        efeitos.append({'tipo': 'loudnorm', 'alvo_lufs': -16.0})
    bruto = {'clips': [{'source': 'principal', 'in_ms': int(round(c['ini'] * 1000)), 'out_ms': int(round(c['fim'] * 1000))}],
             'effects': efeitos, 'template_id': str(tpl.get('modelo') or c.get('modelo') or ''), 'output_profile': 'final',
             'target_aspect_ratio': tpl.get('formato') if tpl.get('formato') in ct.ASPECTOS else '9:16', 'edit_reason': motivo}
    if ct.editor_pro_ativo():
        bruto['schema_version'] = ct.SCHEMA_TIMELINE
        efeitos[0].pop('fim_ms')  # o zoom global acompanha a duração após cortes
        if tpl.get('gancho') and c.get('gancho'):
            trecho = bruto['clips'][0]
            primeiro = trecho['in_ms']
            bruto['protected_hook'] = {'in_ms': primeiro, 'out_ms': min(trecho['out_ms'], primeiro + 3500)}
    return ct.validar_plano(bruto, dur_fonte)


def tpl_do_plano(tpl: dict, plano: dict) -> dict:
    """Modelo do Agente 1 ajustado pelo plano (só os campos que o plano controla)."""
    t = copy.deepcopy(tpl)
    z = _efeito(plano, 'zoom')
    if z:
        t['zoom'] = round(z['nivel'], 3)
    cap = _efeito(plano, 'caption')
    if cap and cap.get('ligado', 1):
        t['tamanho'] = _tamanho_nome(cap.get('tamanho', TAMANHOS['medio']))
        alt = cap.get('altura', 0.78)
        t['legenda_pos'] = 'topo' if alt < 0.35 else 'meio' if alt < 0.65 else 'baixo'
        if t.get('legenda', 'nenhuma') == 'nenhuma':
            t['legenda'] = 'destaque'
    rf = _efeito(plano, 'reframe')
    if rf and rf['modo'] in MODO_PARA_QUADRO and t.get('enquadramento') not in ('gameplay-streamer', 'comparacao'):
        t['enquadramento'] = MODO_PARA_QUADRO[rf['modo']]
        if rf['modo'] == 'centro':
            t['pos_x'], t['pos_y'] = 0.5, 0.5
    if _efeito(plano, 'loudnorm'):
        t['loudnorm'] = True
    return t


# ---------------------------------------------------------------- correções tipadas
def _duracao_clipe_ms(clipe: dict) -> float:
    return (clipe['out_ms'] - clipe['in_ms']) / clipe.get('speed', 1)


def _saida_para_fonte(clipes: list, ms: int) -> tuple[int, int] | None:
    """Instante no vídeo final -> (índice do trecho, instante na fonte)."""
    acc = 0
    for i, c in enumerate(clipes):
        d = _duracao_clipe_ms(c)
        if ms < acc + d:
            return i, round(c['in_ms'] + (ms - acc) * c.get('speed', 1))
        acc += d
    return None


def _travado(plano: dict, a: int, b: int) -> bool:
    travas = list(plano.get('manual_locks') or [])
    gancho = plano.get('protected_hook')
    if gancho:
        travas.append((gancho['in_ms'], gancho['out_ms']))
    return any(b > ini and a < fim for ini, fim in travas)


def corrigir(plano: dict, acoes: list, dur_fonte: float | None = None) -> tuple[dict, list]:
    """Aplica as correções do diretor (já tipadas) e devolve (plano novo validado, lista do que mudou em português)."""
    p = copy.deepcopy(plano)
    feitas, vistas = [], set()
    lim = int(dur_fonte * 1000) if dur_fonte else None
    for bruto in acoes:
        try:
            a = ct.validar_acao(bruto)
        except ct.ErroContrato:
            continue
        chave = a['acao'] if a['acao'] not in ('encurtar_pausa',) else (a['acao'], a.get('ini_ms'), a.get('fim_ms'))
        if chave in vistas:
            continue
        vistas.add(chave)
        cl = p['clips']
        if a['acao'] == 'ajustar_inicio':
            d = int(a.get('delta_ms', 0))
            novo = max(0, cl[0]['in_ms'] + d)
            if novo != cl[0]['in_ms'] and cl[0]['out_ms'] - novo >= 300 and not _travado(p, min(novo, cl[0]['in_ms']), max(novo, cl[0]['in_ms'])):
                feitas.append(f'Começo {"adiantado" if d < 0 else "atrasado"} {abs(novo - cl[0]["in_ms"]) / 1000:.1f} s.')
                cl[0]['in_ms'] = novo
        elif a['acao'] == 'ajustar_fim':
            d = int(a.get('delta_ms', 0))
            novo = cl[-1]['out_ms'] + d
            if lim is not None:
                novo = min(novo, lim)
            if novo != cl[-1]['out_ms'] and novo - cl[-1]['in_ms'] >= 300 and not _travado(p, min(novo, cl[-1]['out_ms']), max(novo, cl[-1]['out_ms'])):
                feitas.append(f'Fim {"estendido" if novo > cl[-1]["out_ms"] else "encurtado"} {abs(novo - cl[-1]["out_ms"]) / 1000:.1f} s.')
                cl[-1]['out_ms'] = novo
        elif a['acao'] == 'encurtar_pausa':
            ini, fim = int(a.get('ini_ms', 0)), int(a.get('fim_ms', 0))
            ini, fim = ini + FOLGA_PAUSA_MS, fim - FOLGA_PAUSA_MS
            x, y = _saida_para_fonte(cl, ini), _saida_para_fonte(cl, fim)
            if fim - ini >= 300 and x and y and x[0] == y[0] and len(cl) < ct.LIMITE_CLIPES:
                i, a_src, b_src = x[0], x[1], y[1]
                c = cl[i]
                if a_src - c['in_ms'] >= 300 and c['out_ms'] - b_src >= 300 and not _travado(p, a_src, b_src):
                    cl[i:i + 1] = [dict(c, out_ms=a_src), dict(c, in_ms=b_src)]
                    feitas.append(f'Pausa de {(b_src - a_src) / 1000:.1f} s tirada.')
        elif a['acao'] == 'aumentar_legenda':
            cap = _efeito(p, 'caption')
            if not cap:
                p['effects'].append({'tipo': 'caption', 'ligado': 1, 'tamanho': round(TAMANHOS['medio'], 4), 'altura': 0.78})
                feitas.append('Legenda ligada.')
            else:
                atual = ORDEM_TAMANHO.index(_tamanho_nome(cap.get('tamanho', TAMANHOS['medio'])))
                if not cap.get('ligado', 1):
                    cap['ligado'] = 1
                    feitas.append('Legenda ligada.')
                elif atual < len(ORDEM_TAMANHO) - 1:
                    cap['tamanho'] = round(TAMANHOS[ORDEM_TAMANHO[atual + 1]], 4)
                    feitas.append(f'Legenda aumentada para {ORDEM_TAMANHO[atual + 1]}.')
        elif a['acao'] == 'subir_legenda':
            cap = _efeito(p, 'caption')
            if cap and cap.get('altura', 0.78) > 0.6:
                cap['altura'] = 0.5
                feitas.append('Legenda subiu para o meio da tela.')
        elif a['acao'] == 'mover_legenda':
            # o Coordenador viu texto do vídeo original por baixo da legenda: ela vai para a faixa livre que ele indicou
            cap = _efeito(p, 'caption')
            alvo = round(float(a.get('altura', 0.5)), 3)
            nome = 'topo' if alvo < 0.35 else 'meio' if alvo < 0.65 else 'baixo'
            if cap and abs(cap.get('altura', 0.78) - alvo) > 0.05:
                cap['altura'] = alvo
                cap['ligado'] = 1
                feitas.append(f'Legenda mudou de lugar ({nome} da tela) para não ficar em cima do texto do vídeo.')
        elif a['acao'] == 'reduzir_zoom':
            z = _efeito(p, 'zoom')
            if z and z['nivel'] > 1.0:
                z['nivel'] = round(max(1.0, z['nivel'] - 0.08), 3)
                feitas.append(f'Zoom reduzido para {z["nivel"]:.2f}.')
        elif a['acao'] == 'normalizar_audio':
            if not _efeito(p, 'loudnorm'):
                p['effects'].append({'tipo': 'loudnorm', 'alvo_lufs': -16.0})
                feitas.append('Volume normalizado.')
        elif a['acao'] == 'trocar_enquadramento':
            rf = _efeito(p, 'reframe')
            modo = a.get('modo', 'desfocado')
            if rf and rf['modo'] != modo:
                rf['modo'] = modo
                feitas.append(f'Enquadramento trocado para {modo}.')
            elif not rf:
                p['effects'].append({'tipo': 'reframe', 'modo': modo})
                feitas.append(f'Enquadramento trocado para {modo}.')
        elif a['acao'] == 'suavizar_cortes':
            if not _efeito(p, 'fade'):
                p['effects'].append({'tipo': 'fade', 'entrada_ms': 120, 'saida_ms': 250})
                feitas.append('Entrada e saída suavizadas, vídeo regravado com quadros regulares.')
        # refazer_cenas e revisao_humana não são do editor: quem chama trata
    if feitas:
        p['timeline_version'] = int(p.get('timeline_version') or 1) + 1
        p['edit_reason'] = ' '.join(feitas)[:300]
    return ct.validar_plano(p, dur_fonte), feitas


# ---------------------------------------------------------------- execução (FFmpeg com números validados)
def _grafo_montagem(plano: dict, audio: bool, offset_ms: int = 0) -> list[str]:
    fc = []
    clipes = plano['clips']
    for i, c in enumerate(clipes):
        a, b = ((c[k] - offset_ms) / 1000 for k in ('in_ms', 'out_ms'))
        speed = c.get('speed')
        tempo_video = f'settb=AVTB,setpts=(PTS-STARTPTS)/{speed:.4f}' if speed else 'setpts=PTS-STARTPTS'
        fc.append(f'[0:v]trim=start={a:.3f}:end={b:.3f},{tempo_video}[v{i}]')
        if audio:
            tempo_audio = ''
            if speed:
                dur = _duracao_clipe_ms(c) / 1000
                tempo_audio = f',atempo={speed:.4f},apad,atrim=duration={dur:.6f}'
            fc.append(f'[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS{tempo_audio}[a{i}]')
    entradas = ''.join(f'[v{i}]' + (f'[a{i}]' if audio else '') for i in range(len(clipes)))
    fc.append(entradas + f'concat=n={len(clipes)}:v=1:a={int(audio)}[vc]' + ('[ac]' if audio else ''))
    return fc


def _passo_final(base: Path, plano: dict, destino: Path, base_ini_ms: int):
    """Monta os trechos e aplica fade com quadros regulares."""
    import renderizador as rd
    audio = tem_audio(base)
    fade = _efeito(plano, 'fade')
    total = duracao_saida(plano)
    fc = _grafo_montagem(plano, audio, base_ini_ms)
    vf, af = ['fps=30'], []
    if fade:
        e, s = fade.get('entrada_ms', 0) / 1000, fade.get('saida_ms', 0) / 1000
        if e > 0:
            vf.append(f'fade=t=in:st=0:d={e:.3f}')
            af.append(f'afade=t=in:st=0:d={e:.3f}')
        if s > 0:
            vf.append(f'fade=t=out:st={max(0.0, total - s):.3f}:d={s:.3f}')
            af.append(f'afade=t=out:st={max(0.0, total - s):.3f}:d={s:.3f}')
    fc.append('[vc]' + ','.join(vf) + '[v]')
    if audio:
        fc.append('[ac]' + (','.join(af) if af else 'anull') + '[a]')
    cmd = ['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(base), '-filter_complex', ';'.join(fc), '-map', '[v]',
           *(['-map', '[a]'] if audio else []),
           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p', '-r', '30', '-c:a', 'aac', '-b:a', '128k', '-ar', '44100',
           '-movflags', '+faststart', str(destino)]
    try:
        rd.rodar(cmd, cancelado=_cancelamento_editor(), dur=total, etapa='montagem')
        if not destino.exists() or destino.stat().st_size < 2000:
            raise rd.ErroRender('O editor não conseguiu montar o vídeo final: arquivo incompleto.')
    except BaseException:
        destino.unlink(missing_ok=True)
        raise


def tem_audio(arq: Path) -> bool:
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', str(arq)],
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


def executar_corte(plano: dict, video: Path, c: dict, palavras: list, tpl: dict, destino: Path, pasta: Path) -> Path:
    """Render do plano de um corte do Agente 1: o montador do modelo (agente.editar) faz a base; o passo final tira pausas e suaviza."""
    import agente as ag
    if ct.efeitos_reais_ativos() or plano.get('schema_version') == ct.SCHEMA_TIMELINE:
        return _executar_corte_efeitos(plano,video,c,palavras,tpl,destino,pasta)
    cl = plano['clips']
    ini, fim = cl[0]['in_ms'], cl[-1]['out_ms']
    t = tpl_do_plano(tpl, plano)
    corte = dict(c, ini=ini / 1000, fim=fim / 1000)
    precisa_final = len(cl) > 1 or _efeito(plano, 'fade')
    if not precisa_final:
        ag.editar(video, corte, palavras, t, destino, pasta)
        return destino
    base = pasta / f'{destino.stem}-base.mp4'
    ag.editar(video, corte, palavras, t, base, pasta)
    try:
        if not tem_audio(base):
            raise RuntimeError('O corte não tem áudio; não dá para tirar pausas.')
        _passo_final(base, plano, destino, ini)
    finally:
        base.unlink(missing_ok=True)
    return destino


def duracao_saida(plano: dict) -> float:
    return sum(_duracao_clipe_ms(c) for c in plano['clips']) / 1000


def palavras_saida(plano: dict, palavras: list) -> list:
    """Palavras da fonte (início, fim, texto) levadas para o tempo do vídeo final (só as que caem dentro dos trechos)."""
    out, acc = [], 0.0
    for c in plano['clips']:
        a, b = c['in_ms'] / 1000, c['out_ms'] / 1000
        speed = c.get('speed', 1)
        for p in palavras:
            if a <= p[0] < b:
                out.append(((p[0] - a) / speed + acc, (min(p[1], b) - a) / speed + acc, p[2]))
        acc += (b - a) / speed
    return out


# ---------------------------------------------------------------- ciclo editor <-> diretor
MODOS_EDITOR = ('automatico', 'supervisionado', 'manual')


def modo_editor() -> str:
    """automatico: corrige e libera sozinho (com o diretor). supervisionado: corrige sozinho, mas você libera.
    manual: não corrige sozinho; reprovou, vai para você. Vale para os cortes (Agente 1, corte manual, vídeo importado)."""
    v = (db.kv('automacao') or {}).get('editor') or {}
    return v.get('modo') if v.get('modo') in MODOS_EDITOR else 'automatico'


def rodar(rid: str, ref: str, plano: dict, render, contexto, *, dur_fonte: float | None = None, avisar=None) -> dict:
    """Loop do Agente 5 com o Agente 4 (final_release).
    render(plano) -> Path do arquivo exportado; contexto(plano) -> dict para diretor_qualidade.avaliar_final.
    Devolve {'resultado': 'aprovado'|'revisao_manual'|'agente3', 'arquivo', 'sha', 'relatorio', 'certificado', 'plano', 'pedidos_agente3'}."""
    import diretor_qualidade as dq
    avisar = avisar or (lambda _t: None)
    st = pl.etapa(rid, 'final_release')
    if st['estado'] in ('aprovado', 'revisao_manual'):       # retomada depois de queda: a etapa já terminou
        r = pl.obter(rid)
        return {'resultado': 'aprovado' if st['estado'] == 'aprovado' else 'revisao_manual', 'arquivo': r['arquivo'], 'sha': r['sha256'],
                'relatorio': r['relatorios'][-1] if r['relatorios'] else None, 'certificado': r['dados'].get('certificado'), 'plano': pl.ultimo_plano(rid),
                'pedidos_agente3': []}
    plano = pl.ultimo_plano(rid) or plano
    anterior = None
    corrigindo = 0
    # registro da esteira dos 7 agentes: A5 (edição e exportação) e A4 (arquivo final), com o tempo de cada trecho e a prova
    es.marcar_run(rid, 'a5_edicao', 'executando', executor='editor_ia.rodar')

    def a4(estado, rel, dec, motivo='', cert=None):
        es.marcar_run(rid, 'a4_final', estado, recibo={'relatorio': rel['id'], 'nota': rel['score'], 'bloqueios': len(rel['blocking_findings']),
                                                       'decisao': dec['decisao'], 'certificado': cert, 'sha': sha},
                      saida_sha=sha if cert else None, entrada_sha=sha, motivo=motivo or dec.get('motivo') or '', correcoes=dec['correcoes_usadas'])
    while True:
        versao = pl.guardar_plano(rid, plano, plano.get('edit_reason', ''))
        pl.mover(rid, 'rendering', agente='agent5', etapa=f'Editor exportando a versão {versao} do plano')
        arq = Path(render(plano))
        sha = pl.sha_arquivo(arq)
        if ct.efeitos_reais_ativos() or plano.get('schema_version') == ct.SCHEMA_TIMELINE:
            recibo = json.loads(arq.with_suffix('.efeitos.json').read_text())
            if recibo.get('status') != 'concluido' or recibo.get('arquivo_sha') != sha or recibo.get('plano_hash') != ct.hash_plano(plano):
                raise RuntimeError('Falta comprovar os efeitos aplicados neste render.')
            pl.mover(rid, 'rendering', dados={'execucao_efeitos': recibo})
        pl.guardar_plano(rid, plano, arquivo_sha=sha)
        es.marcar_run(rid, 'a5_edicao', 'concluida', executor='editor_ia.rodar', saida_sha=sha, correcoes=corrigindo,
                      recibo={'plano_versao': versao, 'sha': sha, 'arquivo': arq.name, 'tamanho': arq.stat().st_size,
                              'efeitos': [e.get('tipo') for e in plano.get('effects') or []], 'trechos': len(plano.get('clips') or [])})
        es.marcar_run(rid, 'a4_final', 'executando', entrada_sha=sha, executor='diretor_qualidade.avaliar_final')
        pl.mover(rid, 'final_qa_pending', agente='agent4', etapa='Diretor conferindo o vídeo', arquivo=str(arq), sha=sha)
        avisar('Diretor conferindo o vídeo')
        rel = dq.avaliar_final(arq, dict(contexto(plano), sha=sha))
        atual = (ct.hash_plano(plano), sha)
        dec = pl.registrar_avaliacao(rid, 'final_release', rel, mudou=atual != anterior)
        anterior = atual
        rel['attempts_used'], rel['attempts_limit'] = dec['correcoes_usadas'], ct.MAX_CORRECOES
        rel = pl.guardar_relatorio(rid, 'final_release', ref, sha, rel)
        base = {'arquivo': str(arq), 'sha': sha, 'relatorio': rel, 'plano': plano, 'pedidos_agente3': [], 'decisao': dec}
        if dec['decisao'] == 'aprovado' and modo_editor() == 'supervisionado':
            # supervisionado: o diretor aprovou, mas o certificado só sai quando VOCÊ liberar (fica registrado como liberado por você)
            motivo = f'Editor supervisionado: o diretor aprovou com nota {rel["score"]}. Confira a edição e libere.'
            pl.mover(rid, 'manual_review_required', agente='pessoa', etapa=motivo)
            a4('aguardando_usuario', rel, dec, motivo)
            return dict(base, resultado='revisao_manual', certificado=None, decisao=dict(dec, motivo=motivo))
        if dec['decisao'] == 'aprovado':
            cert = pl.emitir_certificado(ref, sha, rel, run=rid, revisao=versao)
            pl.mover(rid, 'final_approved', agente='agent2', etapa=f'Aprovado pelo diretor com nota {rel["score"]}', dados={'certificado': cert['id']})
            a4('concluida', rel, dec, cert=cert['id'])
            return dict(base, resultado='aprovado', certificado=cert['id'])
        if dec['decisao'] == 'revisao_manual':
            pl.mover(rid, 'manual_review_required', agente='pessoa', etapa=dec['motivo'])
            a4('revisao_manual', rel, dec)
            return dict(base, resultado='revisao_manual', certificado=None)
        todos = rel['blocking_findings'] + rel['findings']
        acoes = [f['action'] for f in todos if f.get('action') and f.get('target_agent') == 'agent5']
        pedidos3 = [f for f in todos if f.get('target_agent') == 'agent3']
        so_pessoa = [f for f in rel['blocking_findings'] if f.get('target_agent') == 'pessoa']
        if so_pessoa:          # direitos, por exemplo: o editor não resolve
            pl.encerrar_etapa(rid, 'final_release', 'revisao_manual', so_pessoa[0]['evidence'])
            pl.mover(rid, 'manual_review_required', agente='pessoa', etapa='Precisa de você: ' + so_pessoa[0]['evidence'][:150])
            a4('revisao_manual', rel, dec, 'Precisa de você: ' + so_pessoa[0]['evidence'])
            return dict(base, resultado='revisao_manual', certificado=None)
        if modo_editor() == 'manual':          # manual: o editor não corrige sozinho; o vídeo vai para você com os pontos do diretor
            motivo = 'Editor no modo manual: corrija você os pontos apontados pelo diretor.'
            pl.encerrar_etapa(rid, 'final_release', 'revisao_manual', motivo)
            pl.mover(rid, 'manual_review_required', agente='pessoa', etapa=motivo)
            a4('revisao_manual', rel, dec, motivo)
            return dict(base, resultado='revisao_manual', certificado=None, decisao=dict(dec, motivo=motivo))
        novo, feitas = corrigir(plano, acoes, dur_fonte)
        if ct.hash_plano(novo) == ct.hash_plano(plano):
            if pedidos3:
                pl.mover(rid, 'creative_correction_pending', agente='agent3', etapa='O diretor pediu para refazer cenas')
                a4('reprovada', rel, dec, 'O diretor pediu para o Agente 3 refazer cenas.')
                return dict(base, resultado='agente3', certificado=None, pedidos_agente3=pedidos3)
            motivo = 'O editor não tem correção que mude o vídeo para os problemas apontados.'
            pl.encerrar_etapa(rid, 'final_release', 'revisao_manual', motivo)
            pl.mover(rid, 'manual_review_required', agente='pessoa', etapa=motivo)
            a4('revisao_manual', rel, dec, motivo)
            return dict(base, resultado='revisao_manual', certificado=None)
        pl.mover(rid, 'edit_correction_pending', agente='agent5',
                 etapa=f'Correção {dec["correcoes_usadas"] + 1} de {ct.MAX_CORRECOES}: ' + ' '.join(feitas)[:150])
        avisar(f'Editor corrigindo ({dec["correcoes_usadas"] + 1} de {ct.MAX_CORRECOES})')
        a4('reprovada', rel, dec, f'Nota {rel["score"]}: ' + '; '.join(f['evidence'] for f in rel['blocking_findings'][:2]))
        corrigindo = dec['correcoes_usadas'] + 1
        es.marcar_run(rid, 'a5_edicao', 'corrigindo', motivo=f'Correção {corrigindo} de {ct.MAX_CORRECOES}: ' + ' '.join(feitas)[:200],
                      correcoes=corrigindo, recibo={'acoes': acoes[:8]})
        plano = novo


# ---------------------------------------------------------------- vídeo que já chega editado (corte manual do site ou vídeo importado)
def plano_importado(dur: float, aspecto: str = '9:16', template_id: str = '') -> dict:
    """Plano "não mexer": o vídeo inteiro, sem efeito. O editor só age se o diretor pedir."""
    return ct.validar_plano({'clips': [{'source': 'principal', 'in_ms': 0, 'out_ms': int(dur * 1000)}], 'effects': [{'tipo': 'reframe', 'modo': 'manter'}],
                             'target_aspect_ratio': aspecto if aspecto in ct.ASPECTOS else '9:16', 'template_id': template_id,
                             'edit_reason': 'Vídeo recebido pronto: conferir antes de mexer.'}, dur)


def _executar_importado_base(plano: dict, fonte: Path, destino: Path, inicial_hash: str = '', *, cancelado=None) -> Path:
    """Plano igual ao inicial: o arquivo segue como veio (mesmo SHA). Senão: trechos, enquadramento, fade e volume, sempre 30 fps."""
    import shutil
    if inicial_hash and ct.hash_plano(plano) == inicial_hash:
        if fonte.resolve() != destino.resolve():
            shutil.copyfile(fonte, destino)
        return destino
    L, A = ct.ASPECTOS[plano['target_aspect_ratio']]
    rf = (_efeito(plano, 'reframe') or {}).get('modo', 'manter')
    if rf == 'centro':
        quadro = f'scale={L}:{A}:force_original_aspect_ratio=increase,crop={L}:{A},setsar=1'
    elif rf == 'desfocado':
        quadro = (f'split=2[fa][fb];[fa]scale={L // 4}:{A // 4}:force_original_aspect_ratio=increase,crop={L // 4}:{A // 4},boxblur=6:2,scale={L}:{A},setsar=1[fu];'
                  f'[fb]scale={L}:{A}:force_original_aspect_ratio=decrease,setsar=1[ff];[fu][ff]overlay=(W-w)/2:(H-h)/2')
    else:
        quadro = f'scale={L}:{A}:force_original_aspect_ratio=decrease,pad={L}:{A}:(ow-iw)/2:(oh-ih)/2,setsar=1'
    total = duracao_saida(plano)
    audio = tem_audio(fonte)
    fc = _grafo_montagem(plano, audio)
    vf = [quadro, 'fps=30']
    af = []
    fade = _efeito(plano, 'fade')
    if fade:
        e, s = fade.get('entrada_ms', 0) / 1000, fade.get('saida_ms', 0) / 1000
        if e > 0:
            vf.append(f'fade=t=in:st=0:d={e:.3f}')
            af.append(f'afade=t=in:st=0:d={e:.3f}')
        if s > 0:
            vf.append(f'fade=t=out:st={max(0.0, total - s):.3f}:d={s:.3f}')
            af.append(f'afade=t=out:st={max(0.0, total - s):.3f}:d={s:.3f}')
    ln = _efeito(plano, 'loudnorm')
    if ln:
        af.append(f'loudnorm=I={ln["alvo_lufs"]:.1f}:TP=-1.5:LRA=11')
    fc.append('[vc]' + ','.join(vf) + '[v]')
    if audio:
        fc.append('[ac]' + (','.join(af) if af else 'anull') + '[a]')
    tmp = destino.with_name(destino.stem + '-novo.mp4')
    cmd = ['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(fonte), '-filter_complex', ';'.join(fc), '-map', '[v]', *(['-map', '[a]'] if audio else []),
           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p', '-r', '30',
           *(['-c:a', 'aac', '-b:a', '128k', '-ar', '44100'] if audio else []), '-movflags', '+faststart', str(tmp)]
    import renderizador as rd
    try:
        rd.rodar(cmd, cancelado=cancelado or _cancelamento_editor(), dur=total)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    if not tmp.exists() or tmp.stat().st_size < 2000:
        tmp.unlink(missing_ok=True)
        raise RuntimeError('O editor não conseguiu montar o vídeo: arquivo incompleto.')
    tmp.replace(destino)
    return destino


# F2.02: execução verificável compartilhada, desativada por padrão.
def _cancelamento_editor():
    import agente as ag
    return getattr(ag.CONTROLE_TRABALHO,'cancelado',None)


def _registrar_efeitos(destino: Path, recibo: dict):
    p=destino.with_suffix('.efeitos.json')
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(recibo,ensure_ascii=False,indent=2))
    tmp.replace(p)


def _finalizar_efeitos(plano: dict, base: Path, destino: Path, *, ass: Path | None = None, base_aplicados=(), cancelado=None) -> Path:
    import projetos as pj
    import renderizador as rd
    plano=ct.validar_plano(plano)
    total=duracao_saida(plano)
    efeitos=plano['effects']
    recibo={'schema':1,'plano_hash':ct.hash_plano(plano),'planejados':len(efeitos),'aplicados':0,'falhas':0,
            'efeitos':[],'criado':time.time(),'status':'executando'}
    tmp=destino.with_name(destino.stem+'-efeitos.tmp.mp4')
    cancelar=cancelado or _cancelamento_editor()
    try:
        meta=rd.sonda(base)
        v=next(x for x in meta['streams'] if x['codec_type']=='video');w,h=int(v['width']),int(v['height'])
        cmd=['ffmpeg','-nostdin','-y','-v','error','-i',str(base)]
        filtros=[];atual='[0:v]';entrada=1;parados=[]
        for k,e in enumerate(efeitos):
            tipo=e['tipo'];status='aplicado';motivo=''
            a=float(e.get('ini_ms',0))/1000;b=float(e.get('fim_ms',total*1000))/1000
            if tipo=='zoom' and not e.get('fim_ms'):
                b=total  # planos antigos omitem o fim do zoom global
            if tipo in ('zoom','broll') and not (0<=a<b<=total+0.05):
                raise ct.ErroContrato('Intervalo do efeito passa da duração renderizada.')
            if tipo=='zoom' and e['nivel']>1:
                cw=max(2,int(w/e['nivel'])//2*2);ch=max(2,int(h/e['nivel'])//2*2)
                filtros += [f'{atual}split[z{k}a][z{k}b]',f'[z{k}b]crop={cw}:{ch},scale={w}:{h}[z{k}c]',
                            f"[z{k}a][z{k}c]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[e{k}]"]
                atual=f'[e{k}]'
            elif tipo=='broll':
                midia=pj.asset(e['asset']);mime=midia['mime']
                if not mime.startswith(('image/','video/')):
                    raise ct.ErroContrato('B-roll precisa de uma imagem ou vídeo.')
                if mime.startswith('image/'):
                    parados.append([a,b])
                    cmd += ['-loop','1','-t',str(total),'-i',midia['caminho']]
                else:
                    cmd += ['-stream_loop','-1','-i',midia['caminho']]
                filtros += [f'[{entrada}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,format=yuv420p[br{k}]',
                            f"{atual}[br{k}]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})':shortest=1[e{k}]"]
                atual=f'[e{k}]';entrada+=1
            elif tipo=='caption':
                if e.get('ligado',1) and (ass is None or ',Leg,' not in ass.read_text()):
                    raise ct.ErroContrato('Legenda dinâmica exige transcrição da fala para aplicação.')
                if not e.get('ligado',1):status='sem_alteracao'
            elif tipo=='zoom':
                status='sem_alteracao';motivo='Nível de zoom igual a 1.'
            elif tipo=='reframe' and e.get('modo')=='manter':
                status='sem_alteracao';motivo='Enquadramento mantido.'
            elif tipo not in base_aplicados:
                raise ct.ErroContrato('O render base não comprovou aplicação de '+tipo)
            recibo['efeitos'].append({'tipo':tipo,'status':status,'parametros':e,'motivo':motivo})
        if ass:
            esc=lambda p:str(p).replace('\\','/').replace(':','\\:').replace("'","\\'")
            filtros.append(f"{atual}ass='{esc(ass)}'[leg]");atual='[leg]'
        filtros.append(f'{atual}format=yuv420p[v]')
        cmd += ['-filter_complex',';'.join(filtros),'-map','[v]','-map','0:a?','-t',str(total),
                '-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-c:a','aac']
        ln=_efeito(plano,'loudnorm')
        if ln:
            cmd += ['-af',f"loudnorm=I={ln['alvo_lufs']:.1f}:TP=-1.5:LRA=11"]
        cmd += ['-movflags','+faststart',str(tmp)]
        rd.rodar(cmd,cancelado=cancelar,dur=total)
        dur=rd.duracao(tmp)
        if abs(dur-total)>0.25:
            raise rd.ErroRender('Duração do efeito divergente do plano.')
        if os.getenv('RENDER_INTEGRIDADE','0')=='1':
            qa=destino.parent/(destino.stem+'-integridade');qa.mkdir(exist_ok=True)
            conferencia=rd.conferir(tmp,qa,{'largura':w,'altura':h,'duracao':total,
                                         'parados_previstos':parados},cancelar)
            recibo['integridade']=conferencia['integridade']
            if not conferencia['ok']:
                raise rd.ErroRender('Integridade do render: '+'; '.join(conferencia['erros']))
        if cancelar and cancelar():
            raise InterruptedError('cancelado')
        recibo.update(status='concluido',arquivo_sha=rd.sha256(tmp),duracao=dur,
                      aplicados=sum(x['status']=='aplicado' for x in recibo['efeitos']),
                      sem_alteracao=sum(x['status']=='sem_alteracao' for x in recibo['efeitos']))
        if plano['schema_version'] == ct.SCHEMA_TIMELINE:
            recibo['montagem'] = {'versao': plano['timeline_version'], 'trechos': plano['clips'],
                                  'gancho_protegido': plano.get('protected_hook')}
        _registrar_efeitos(destino,recibo)
        tmp.replace(destino)
        return destino
    except BaseException as erro:
        tmp.unlink(missing_ok=True)
        recibo.update(status='falhou',falhas=1,erro=str(erro)[:500],aplicados=0)
        _registrar_efeitos(destino,recibo)
        raise


def _executar_corte_efeitos(plano: dict, video: Path, c: dict, palavras: list, tpl: dict, destino: Path, pasta: Path) -> Path:
    import agente as ag
    import renderizador as rd
    plano=ct.validar_plano(plano)
    pasta.mkdir(parents=True,exist_ok=True)
    cl=plano['clips'];ini,fim=cl[0]['in_ms']/1000,cl[-1]['out_ms']/1000
    t=tpl_do_plano(tpl,plano);t['zoom']=1.0
    base=pasta/(destino.stem+'-base-efeitos.mp4');montado=pasta/(destino.stem+'-montado-efeitos.mp4')
    sem_texto=dict(t,legenda='nenhuma',gancho=False,credito='',tarja_topo='',tarja_base='')
    ag.editar(video,dict(c,ini=ini,fim=fim),palavras,sem_texto,base,pasta)
    try:
        temporal=base
        if len(cl)>1 or 'speed' in cl[0] or _efeito(plano,'fade'):
            _passo_final(base,plano,montado,int(ini*1000));temporal=montado
        vs=next(x for x in rd.sonda(temporal)['streams'] if x['codec_type']=='video')
        ass=pasta/(destino.stem+'-efeitos.ass')
        cap=_efeito(plano,'caption')
        if not cap or not cap.get('ligado',1):t['legenda']='nenhuma'
        ass.write_text(ag.montar_ass(palavras_saida(plano,palavras),0,duracao_saida(plano),t,c.get('gancho',''),int(vs['width']),int(vs['height'])))
        return _finalizar_efeitos(plano,temporal,destino,ass=ass,base_aplicados=('reframe','fade','loudnorm'))
    finally:
        base.unlink(missing_ok=True);montado.unlink(missing_ok=True)


def executar_importado(plano: dict, fonte: Path, destino: Path, inicial_hash: str = '', *, comprovar=False, cancelado=None) -> Path:
    if not comprovar and not ct.efeitos_reais_ativos() and plano.get('schema_version') != ct.SCHEMA_TIMELINE:
        return _executar_importado_base(plano,fonte,destino,inicial_hash,cancelado=cancelado)
    p=copy.deepcopy(ct.validar_plano(plano));base=destino.with_name(destino.stem+'-base-efeitos.mp4')
    p['effects']=[e for e in p['effects'] if e['tipo'] not in ('zoom','broll','caption')]
    try:
        _executar_importado_base(p,fonte,base,cancelado=cancelado)
        return _finalizar_efeitos(plano,base,destino,base_aplicados=('reframe','fade','loudnorm'),cancelado=cancelado)
    finally:
        base.unlink(missing_ok=True)
