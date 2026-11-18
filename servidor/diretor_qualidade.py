"""Agente 4 — Diretor de Qualidade: nota de 0 a 100, bloqueios e correções tipadas para o editor (Agente 5) ou o Agente 3.

final_release: confere o ARQUIVO EXPORTADO (não a prévia), lendo o vídeo inteiro: decodificação completa, buracos no tempo
dos quadros (o "começa certo e fica preto/lento no meio"), tela preta fora das bordas, imagem parada, silêncios, volume,
sincronia, formato, gancho, fim de frase e o plano de edição (legenda, template, formato).
creative_preedit: confere cenas e roteiro do Agente 3 antes da montagem final.

Tudo que entra na nota é MEDIDO (ou lido do plano de edição, e o relatório diz qual). Opinião de IA não entra na nota e
nunca bloqueia. Referências virais só viram observação: não são previsão de sucesso.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import contratos as ct

VERSAO = 'qc-1.0'


# ---------------------------------------------------------------- medidas do arquivo
def _ff(cmd: list, tempo: float = 900) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors='replace', stdin=subprocess.DEVNULL, timeout=tempo)
        return (r.stderr or '') + (r.stdout or '')
    except (OSError, subprocess.TimeoutExpired) as e:
        return f'ERRO_FF {e}'


def _sonda(arq: Path) -> dict:
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(arq)], capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, timeout=120)
        return json.loads(r.stdout or '{}')
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {}


def _intervalos(texto: str, ini: str, fim: str) -> list:
    a = [float(x) for x in re.findall(ini + r'\s*:?\s*([\d.]+)', texto)]
    b = [float(x) for x in re.findall(fim + r'\s*:?\s*([\d.]+)', texto)]
    return [(x, y) for x, y in zip(a, b)]


def _buracos(arq: Path, fps: float) -> list:
    """Instantes em que o vídeo 'trava': distância entre dois quadros muito maior que o normal."""
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'packet=pts_time', '-of', 'csv=p=0', str(arq)],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
    except (OSError, subprocess.TimeoutExpired):
        return []
    ts = sorted(float(x) for x in re.findall(r'^([\d.]+)', r.stdout, re.M))
    limite = max(0.5, 4.0 / fps) if fps else 0.5
    return [(a, b) for a, b in zip(ts, ts[1:]) if b - a > limite]


def _amostras(arq: Path, dur: float, extras: list) -> list:
    import qualidade as qd
    n = max(8, min(24, int(dur / 5) + 1))
    tempos = sorted({round(dur * (i + 0.5) / n, 2) for i in range(n)} | {round(t, 2) for t in extras if 0 < t < dur})
    out = []
    for t in tempos:
        px = qd._miniatura(arq, t)
        if px is not None:
            m, dp = qd._stats(px)
            out.append({'t': t, 'brilho': round(m, 1), 'detalhe': round(dp, 1)})
    return out


def medir(arq: Path, marcas: list | None = None) -> dict:
    """Uma leitura completa do arquivo. `marcas` = instantes de troca de cena (ganham amostras extras)."""
    info = _sonda(arq)
    v = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), None)
    a = next((s for s in info.get('streams', []) if s.get('codec_type') == 'audio'), None)
    dur = float((info.get('format') or {}).get('duration') or 0)
    try:
        num, den = ((v or {}).get('avg_frame_rate') or '0/1').split('/')
        fps = float(num) / float(den) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    filtros_v = 'scale=270:-2,blackdetect=d=0.3:pic_th=0.97,freezedetect=n=0.003:d=2'
    cmd = ['ffmpeg', '-nostdin', '-v', 'info', '-i', str(arq)]
    if v:
        cmd += ['-map', '0:v:0', '-vf', filtros_v]
    if a:
        cmd += ['-map', '0:a:0', '-af', 'silencedetect=n=-45dB:d=1.0,loudnorm=I=-16:TP=-1.5:print_format=json']
    cmd += ['-f', 'null', '-']
    log = _ff(cmd) if (v or a) else ''
    erros_dec = [ln.strip() for ln in log.splitlines() if re.search(r'error while decoding|corrupt|invalid nal|concealing|missing picture', ln, re.I)]
    loud = {}
    m = re.search(r'\{\s*"input_i"[^}]*\}', log, re.S)
    if m:
        try:
            j = json.loads(m.group(0))
            loud = {'lufs': float(j['input_i']), 'pico': float(j['input_tp'])}
        except (ValueError, KeyError):
            loud = {}
    silencios = _intervalos(log, 'silence_start', 'silence_end')
    # silêncio que vai até o fim do arquivo não tem silence_end
    if a and log.count('silence_start') > len(silencios):
        ult = re.findall(r'silence_start\s*:?\s*([\d.]+)', log)[-1]
        silencios.append((float(ult), dur))
    return {'duracao': round(dur, 3), 'largura': int((v or {}).get('width') or 0), 'altura': int((v or {}).get('height') or 0), 'fps': round(fps, 3),
            'codec_v': (v or {}).get('codec_name', ''), 'codec_a': (a or {}).get('codec_name', ''), 'tem_video': bool(v), 'tem_audio': bool(a),
            'dur_v': float((v or {}).get('duration') or dur), 'dur_a': float((a or {}).get('duration') or 0) if a else 0.0,
            'quadros': int((v or {}).get('nb_frames') or 0), 'erros_decodificacao': erros_dec[:5], 'n_erros_decodificacao': len(erros_dec),
            'pretos': [(round(x, 2), round(y, 2)) for x, y in _intervalos(log, 'black_start', 'black_end')],
            'congelados': [(round(x, 2), round(x + d, 2)) for x, d in zip([float(t) for t in re.findall(r'freeze_start\s*:?\s*([\d.]+)', log)],
                                                                           [float(t) for t in re.findall(r'freeze_duration\s*:?\s*([\d.]+)', log)])],
            'silencios': [(round(x, 2), round(y, 2)) for x, y in silencios], 'volume': loud,
            'travadas': [(round(x, 2), round(y, 2)) for x, y in _buracos(arq, fps)] if v else [],
            'amostras': _amostras(arq, dur, [t + d for t in (marcas or []) for d in (-0.2, 0.2)]) if v and dur > 0 else []}


def _ms(t) -> int | None:
    return None if t is None else int(round(float(t) * 1000))


# ---------------------------------------------------------------- nota final (final_release)
def avaliar_final(arq: Path, ctx: dict, medidas: dict | None = None) -> dict:
    """ctx: aspecto ('9:16'), palavras [(ini, fim, palavra)] relativas ao arquivo, legenda_esperada, legenda_aplicada,
    legenda_tamanho, legenda_altura, template_id, template_esperado, dur_min, dur_max, direitos_ok, sem_audio_ok,
    pretos_intencionais [(a, b)], marcas [instantes], referencias {resumo}."""
    md = medidas or medir(arq, ctx.get('marcas'))
    pesos = ct.PESOS['final_release']
    pontos = dict(pesos)
    achados, bloqueios, avisos = [], [], []
    dur = md['duracao'] or 0.0
    pal = [p for p in ctx.get('palavras') or [] if p[1] > 0 and p[0] < dur + 0.5]

    def tira(parte, n, f=None):
        pontos[parte] = max(0, pontos[parte] - n)
        if f:
            achados.append(f)

    def bloqueia(cat, evid, instr, **kw):
        f = ct.achado(cat, 'bloqueio', evid, instr, **kw)
        achados.append(f)
        bloqueios.append(f)

    # --- técnica
    if not md['tem_video']:
        bloqueia('arquivo_quebrado', 'O arquivo não tem imagem.', 'Exportar de novo.', alvo='agent5')
    if md['n_erros_decodificacao']:
        bloqueia('arquivo_quebrado', f'{md["n_erros_decodificacao"]} erro(s) ao decodificar o vídeo inteiro (ex.: {md["erros_decodificacao"][0][:90]}).',
                 'Exportar de novo a partir da fonte.', alvo='agent5')
    if md['tem_video'] and md['quadros'] and md['fps'] and md['dur_v'] and md['quadros'] < md['dur_v'] * md['fps'] * 0.9:
        bloqueia('arquivo_quebrado', f'Faltam quadros: {md["quadros"]} gravados para {md["dur_v"] * md["fps"]:.0f} esperados.', 'Exportar de novo.')
    for x, y in md['travadas'][:3]:
        bloqueia('travamento', f'O vídeo trava de {x:.2f}s a {y:.2f}s (nenhum quadro nesse intervalo).', 'Exportar de novo este trecho.',
                 ini_ms=_ms(x), fim_ms=_ms(y), acao={'acao': 'suavizar_cortes'})
    if not md['tem_audio'] and not ctx.get('sem_audio_ok'):
        bloqueia('audio', 'O arquivo não tem som.', 'Exportar de novo com o áudio.', alvo='agent5')
    if md['tem_audio'] and md['dur_a'] and md['dur_v']:
        dif = abs(md['dur_a'] - md['dur_v'])
        if dif > 1.5:
            bloqueia('sincronia', f'Som ({md["dur_a"]:.2f}s) e imagem ({md["dur_v"]:.2f}s) com {dif:.1f}s de diferença.', 'Exportar de novo.')
        elif dif > 0.5:
            tira('tecnica', 6, ct.achado('sincronia', 'media', f'Som e imagem com {dif:.2f}s de diferença de duração.', 'Conferir a junção dos trechos.',
                                          acao={'acao': 'suavizar_cortes'}))
    if md['codec_v'] and md['codec_v'] != 'h264':
        tira('tecnica', 4, ct.achado('formato', 'baixa', f'Vídeo em {md["codec_v"]} (as redes preferem H.264).', 'Exportar em H.264.'))
    if md['codec_a'] and md['codec_a'] != 'aac':
        tira('tecnica', 2, ct.achado('formato', 'baixa', f'Áudio em {md["codec_a"]} (as redes preferem AAC).', 'Exportar em AAC.'))
    vol = md.get('volume') or {}
    if vol.get('lufs') is not None and vol['lufs'] > -70 and not -24 <= vol['lufs'] <= -10:
        tira('tecnica', 4, ct.achado('volume', 'media', f'Volume médio {vol["lufs"]:.1f} LUFS (bom: entre -24 e -10).', 'Normalizar o volume.',
                                      acao={'acao': 'normalizar_audio'}))
    if vol.get('pico') is not None and vol['pico'] > -0.5:
        tira('tecnica', 2, ct.achado('volume', 'baixa', f'Pico de {vol["pico"]:.1f} dBTP (pode estourar).', 'Normalizar o volume.', acao={'acao': 'normalizar_audio'}))

    # --- imagem e formato
    alvo = ct.ASPECTOS.get(ctx.get('aspecto') or '9:16')
    if md['largura'] and md['altura'] and alvo:
        if abs(md['largura'] / md['altura'] - alvo[0] / alvo[1]) > 0.02:
            bloqueia('formato', f'Tela {md["largura"]}x{md["altura"]}, mas o pedido é {ctx.get("aspecto") or "9:16"}.', 'Reenquadrar para o formato pedido.',
                     acao={'acao': 'trocar_enquadramento', 'modo': 'desfocado'})
        if min(md['largura'], md['altura']) < 720:
            tira('imagem', 5, ct.achado('resolucao', 'media', f'Resolução baixa ({md["largura"]}x{md["altura"]}).', 'Exportar em 1080.'))
    intenc = ctx.get('pretos_intencionais') or []
    for x, y in md['pretos']:
        if any(a <= x and y <= b for a, b in intenc):
            continue
        if x > 0.3 and y < dur - 0.3 and y - x >= 0.5:
            bloqueia('preto_indevido', f'Tela preta no meio do vídeo, de {x:.2f}s a {y:.2f}s.', 'Refazer a junção deste trecho.', ini_ms=_ms(x), fim_ms=_ms(y),
                     acao={'acao': 'suavizar_cortes'})
        elif y - x > 1.0:
            borda = 'começo' if x <= 0.3 else 'fim'
            tira('imagem', 4, ct.achado('preto_borda', 'media', f'{y - x:.1f}s de tela preta no {borda}.', f'Cortar o preto do {borda}.', ini_ms=_ms(x), fim_ms=_ms(y),
                                         acao={'acao': 'ajustar_inicio', 'delta_ms': int((y - x) * 1000)} if borda == 'começo'
                                         else {'acao': 'ajustar_fim', 'delta_ms': -int((y - x) * 1000)}))
    escuros = [s for s in md['amostras'] if s['brilho'] < 18 and not any(x - 0.1 <= s['t'] <= y + 0.1 for x, y in md['pretos'])]
    lisos = [s for s in md['amostras'] if s['brilho'] >= 18 and s['detalhe'] < 7]
    for s in escuros[:3]:
        tira('imagem', 3, ct.achado('quadro_escuro', 'media', f'Quadro escuro aos {s["t"]:.1f}s (brilho {s["brilho"]:.0f}/255).', 'Clarear ou trocar a imagem.',
                                     ini_ms=_ms(s['t']), alvo='agent5'))
    for s in lisos[:3]:
        tira('imagem', 2, ct.achado('sem_detalhe', 'baixa', f'Imagem quase lisa aos {s["t"]:.1f}s.', 'Abrir o enquadramento ou trocar a imagem.', ini_ms=_ms(s['t'])))

    # --- ritmo
    tem_fala = bool(pal)
    dentro = [(x, y) for x, y in md['silencios'] if y - x >= 1.5 and x > 0.2 and y < dur - 0.2]
    for x, y in dentro[:3]:
        tira('ritmo', 4 if tem_fala else 2, ct.achado('ritmo', 'media' if tem_fala else 'baixa', f'Pausa de {y - x:.1f}s em silêncio ({x:.1f}s a {y:.1f}s).',
                                                       'Encurtar a pausa sem cortar fala.', ini_ms=_ms(x), fim_ms=_ms(y),
                                                       acao={'acao': 'encurtar_pausa', 'ini_ms': _ms(x), 'fim_ms': _ms(y)}))
    for x, y in md['congelados'][:2]:
        if y - x >= 3:
            tira('ritmo', 3, ct.achado('imagem_parada', 'baixa', f'Imagem parada por {y - x:.1f}s ({x:.1f}s a {y:.1f}s).', 'Dar movimento (zoom leve) ou cortar.',
                                        ini_ms=_ms(x), fim_ms=_ms(y)))
    dmin, dmax = ctx.get('dur_min'), ctx.get('dur_max')
    if dmin and dur < dmin * 0.9:
        tira('ritmo', 4, ct.achado('duracao', 'media', f'{dur:.0f}s: abaixo do mínimo de {dmin:.0f}s.', 'Estender até o fim da próxima frase.',
                                    acao={'acao': 'ajustar_fim', 'delta_ms': min(8000, int((dmin - dur) * 1000) + 300)}))
    if dmax and dur > dmax * 1.1:
        tira('ritmo', 4, ct.achado('duracao', 'media', f'{dur:.0f}s: acima do máximo de {dmax:.0f}s.', 'Encurtar o fim.',
                                    acao={'acao': 'ajustar_fim', 'delta_ms': -min(5000, int((dur - dmax) * 1000))}))

    # --- gancho (primeiros segundos)
    if pal:
        t0 = max(0.0, pal[0][0])
    elif md['tem_audio']:
        ini_sil = next((y for x, y in md['silencios'] if x <= 0.1), 0.0)
        t0 = ini_sil
        avisos.append('Sem transcrição: o começo foi medido pelo primeiro som, não pela primeira palavra.')
    else:
        t0 = None
    if t0 is None:
        pontos['gancho'] = 10
        avisos.append('Sem som e sem transcrição: o gancho não pôde ser medido (10 de 15, neutro).')
    else:
        pg = 15 if t0 <= 1.0 else 12 if t0 <= 2.0 else 8 if t0 <= 3.0 else 4 if t0 <= 5.0 else 0
        if pg < 15:
            tira('gancho', 15 - pg, ct.achado('gancho', 'alta' if pg <= 4 else 'media', f'A primeira fala chega aos {t0:.1f}s.', 'Começar logo antes da primeira fala.',
                                               ini_ms=0, fim_ms=_ms(t0), acao={'acao': 'ajustar_inicio', 'delta_ms': int(min(5000, max(0.0, t0 - 0.3) * 1000))}))

    # --- clareza: começa e termina inteiro
    if pal:
        if pal[0][0] < 0 < pal[0][1] - 0.05:
            bloqueia('truncado', f'O vídeo começa no meio da palavra "{pal[0][2]}".', 'Começar antes da palavra.', ini_ms=0, fim_ms=_ms(pal[0][1]),
                     acao={'acao': 'ajustar_inicio', 'delta_ms': -int(min(5000, (0 - pal[0][0]) * 1000 + 200))})
        ult = pal[-1]
        if ult[0] < dur - 0.05 < ult[1] - 0.05:
            bloqueia('truncado', f'O vídeo termina no meio da palavra "{ult[2]}".', 'Terminar depois da palavra.', ini_ms=_ms(ult[0]), fim_ms=_ms(dur),
                     acao={'acao': 'ajustar_fim', 'delta_ms': int(min(8000, (ult[1] - dur) * 1000 + 300))})
        elif ctx.get('fim_de_frase') is False:
            tira('clareza', 5, ct.achado('fim_de_frase', 'media', 'O vídeo termina no meio de uma frase.', 'Terminar no fim da frase.',
                                          ini_ms=_ms(ult[0]), acao={'acao': 'ajustar_fim', 'delta_ms': 2000}))
    else:
        avisos.append('Sem transcrição: começo e fim de frase não foram conferidos.')

    # --- legendas (conferidas pelo plano de edição: o que foi pedido e aplicado)
    if ctx.get('legenda_esperada') and tem_fala:
        if not ctx.get('legenda_aplicada'):
            tira('legendas', 10, ct.achado('legenda', 'alta', 'O vídeo tem fala, mas a legenda não foi aplicada.', 'Ligar a legenda.',
                                            acao={'acao': 'aumentar_legenda'}, natureza='plano'))
        else:
            tam, alt = ctx.get('legenda_tamanho'), ctx.get('legenda_altura')
            if tam is not None and tam < 0.06:
                tira('legendas', 5, ct.achado('legenda', 'media', f'Legenda pequena ({tam:.3f} da largura da tela).', 'Aumentar a legenda.',
                                               acao={'acao': 'aumentar_legenda'}, natureza='plano'))
            if alt is not None and not 0.15 <= alt <= 0.82:
                tira('legendas', 5, ct.achado('area_segura', 'media', f'Legenda em {alt:.2f} da altura: fora da área segura (botões da rede cobrem).',
                                               'Subir a legenda para a área segura.', acao={'acao': 'subir_legenda'}, natureza='plano'))
    elif ctx.get('legenda_esperada'):
        avisos.append('Sem fala detectada: a legenda não foi exigida.')

    # --- identidade
    if ctx.get('template_esperado') and not ctx.get('template_id'):
        tira('identidade', 5, ct.achado('template', 'media', 'O template configurado não foi aplicado.', 'Aplicar o template.', natureza='plano'))
    if not ctx.get('template_esperado'):
        avisos.append('Sem template configurado: identidade conferida só pelo formato.')

    # --- direitos (sempre bloqueio, nenhuma nota passa por cima)
    if ctx.get('direitos_ok') is False:
        bloqueia('direitos', ctx.get('direitos_motivo') or 'Direitos do material não confirmados.', 'Registrar de quem é o vídeo ou não postar.', alvo='pessoa')

    ref = ctx.get('referencias') or {}
    if ref.get('duracao_mediana') and dur:
        med = ref['duracao_mediana']
        if dur > med * 2 or dur < med / 2:
            avisos.append(f'As referências do tema têm mediana de {med:.0f}s e este vídeo tem {dur:.0f}s (só observação, não muda a nota).')
    nota = int(round(sum(pontos.values())))
    return {'schema_version': ct.SCHEMA, 'stage': 'final_release', 'render_sha256': ctx.get('sha', ''), 'score': nota, 'passed': ct.decidir(nota, bloqueios),
            'blocking_findings': bloqueios, 'findings': achados, 'partes': {k: {'pontos': pontos[k], 'maximo': pesos[k], 'nome': ct.NOMES_PARTES[k]} for k in pesos},
            'avisos': avisos, 'medidas': {k: md[k] for k in ('duracao', 'largura', 'altura', 'fps', 'codec_v', 'codec_a', 'pretos', 'congelados', 'silencios',
                                                              'volume', 'travadas', 'n_erros_decodificacao')} | {'amostras': len(md['amostras'])},
            'reference_set_id': ref.get('id'), 'referencias_resumo': ref or None, 'evaluator_version': VERSAO}


# ---------------------------------------------------------------- nota criativa (creative_preedit, Agente 3)
def avaliar_criativo(cenas: list, briefing: dict, roteiro: dict, extras: dict | None = None) -> dict:
    """Cenas e roteiro antes da montagem final. extras: {'alertas': [...] de qualidade.antes/diretor.checar/continuidade,
    'sem_licenca': [cena ids]}."""
    pesos = ct.PESOS['creative_preedit']
    pontos = dict(pesos)
    achados, bloqueios = [], []
    extras = extras or {}

    def tira(parte, n, f):
        pontos[parte] = max(0, pontos[parte] - n)
        achados.append(f)

    if not cenas:
        f = ct.achado('estrutura', 'bloqueio', 'O roteiro não tem cenas.', 'Gerar o roteiro de novo.', alvo='agent3')
        return {'stage': 'creative_preedit', 'score': 0, 'passed': False, 'blocking_findings': [f], 'findings': [f],
                'partes': {k: {'pontos': 0, 'maximo': v, 'nome': ct.NOMES_PARTES[k]} for k, v in pesos.items()}, 'avisos': [], 'evaluator_version': VERSAO}
    if not str((roteiro or {}).get('gancho') or '').strip() and len((cenas[0].get('texto') or '').split()) > 25:
        tira('estrutura', 8, ct.achado('gancho', 'media', 'Sem gancho e a primeira cena é longa.', 'Abrir com uma frase curta que prenda.', alvo='agent3',
                                        cena=cenas[0].get('id', ''), acao={'acao': 'refazer_cenas', 'cenas': [cenas[0].get('id', 'c1')]}))
    if not 2 <= len(cenas) <= 20:
        tira('estrutura', 5, ct.achado('estrutura', 'media', f'{len(cenas)} cena(s): fora do normal (2 a 20).', 'Reorganizar as cenas.', alvo='agent3'))
    for c in cenas:
        cid = c.get('id', '')
        pal = len((c.get('texto') or '').split())
        if pal == 0 and not c.get('falas'):
            tira('narracao', 5, ct.achado('narracao', 'media', f'A cena {cid} não tem narração nem fala.', 'Escrever o texto da cena.', alvo='agent3', cena=cid,
                                           acao={'acao': 'refazer_cenas', 'cenas': [cid]}))
        elif pal > 34:
            tira('roteiro', 4, ct.achado('ritmo', 'media', f'A cena {cid} tem {pal} palavras (fica longa).', 'Dividir ou encurtar.', alvo='agent3', cena=cid,
                                          acao={'acao': 'refazer_cenas', 'cenas': [cid]}))
    for x in extras.get('alertas') or []:
        sev = x.get('severidade', 'baixa')
        if x.get('natureza') == 'julgamento':
            continue
        tipo = x.get('tipo', '')
        parte = 'assets' if tipo in ('sem_imagem', 'quadro_escuro', 'sem_detalhe') else 'consistencia' if tipo in (
            'eixo', 'olhar', 'close_sem_dono', 'continuidade', 'sai_do_quadro', 'cabeca_cortada', 'sobreposicao') else 'roteiro'
        n = 5 if sev == 'alta' else 4 if sev == 'media' else 2
        cid = x.get('cena_id') or x.get('cena') or ''
        tira(parte, n, ct.achado(tipo or 'alerta', {'alta': 'alta', 'media': 'media'}.get(sev, 'baixa'), x.get('descricao', '')[:280],
                                 x.get('correcao') or x.get('proposta') or 'Revisar a cena.', alvo='agent3', cena=cid,
                                 acao={'acao': 'refazer_cenas', 'cenas': [cid]} if cid else None))
    for cid in extras.get('sem_licenca') or []:
        f = ct.achado('direitos', 'bloqueio', f'A imagem da cena {cid} não tem licença/crédito registrado.', 'Trocar por imagem com licença.', alvo='agent3',
                      cena=cid, acao={'acao': 'refazer_cenas', 'cenas': [cid]})
        achados.append(f)
        bloqueios.append(f)
    nota = int(round(sum(pontos.values())))
    return {'schema_version': ct.SCHEMA, 'stage': 'creative_preedit', 'score': nota, 'passed': ct.decidir(nota, bloqueios), 'blocking_findings': bloqueios,
            'findings': achados, 'partes': {k: {'pontos': pontos[k], 'maximo': pesos[k], 'nome': ct.NOMES_PARTES[k]} for k in pesos}, 'avisos': [],
            'evaluator_version': VERSAO}


def cenas_para_refazer(rel: dict) -> list:
    out = []
    for f in rel['findings']:
        a = f.get('action') or {}
        if f.get('target_agent') == 'agent3' and a.get('acao') == 'refazer_cenas':
            out += a.get('cenas') or []
    return sorted(set(x for x in out if x))
