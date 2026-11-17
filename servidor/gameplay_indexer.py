"""Gameplay Narrativa: acha os destaques de um vídeo de jogo a partir do que dá para OBSERVAR e propõe ganchos honestos.

Sinais usados (todos medidos no próprio vídeo): mudança de cena (FFmpeg), picos de som (FFmpeg astats), falas (transcrição) e,
se houver chave da IA, uma descrição dos quadros nos momentos mais fortes. Sem a descrição dos quadros a análise sai marcada como
"parcial". Os ganchos só podem citar eventos que existem na lista observada: nada é inventado.
Direitos: só analisa vídeo com origem declarada (seu, autorizado ou com regra pública de cortes). Nada aqui publica nada.
"""
from __future__ import annotations

import base64
import json
import math
import re
import statistics
import subprocess
import time
import uuid
from pathlib import Path

import agente as ag
import modo_render as mr
import perfis as pf
import postagem as pg

PASTA = pg.DADOS / 'gameplay'
HISTORIAS = {
    'engracada': 'Engraçada', 'suspense': 'Suspense', 'desafio': 'Desafio', 'reviravolta': 'Reviravolta',
    'tutorial': 'Tutorial', 'documentario': 'Documentário de gameplay',
}
MAX_DESTAQUES = 8


class ErroGameplay(Exception):
    pass


def mmss(t: float) -> str:
    return f'{int(t) // 60}:{int(t) % 60:02d}'


def _fmt_pct(x: float) -> str:
    return f'{round(x * 100)}%'


# ---------------------------------------------------------------- sinais medidos
def mudancas_de_cena(video: Path, limite: float = 0.35) -> list:
    r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'info', '-i', str(video), '-an', '-vf', f"select='gt(scene,{limite})',showinfo", '-f', 'null', '-'],
                       capture_output=True, text=True, timeout=1800)
    out = []
    for m in re.finditer(r'pts_time:([\d.]+)', r.stderr):
        t = float(m.group(1))
        if not out or t - out[-1] > 0.8:
            out.append(round(t, 2))
    return out


def picos_de_audio(video: Path, janela: float = 0.5) -> list:
    """[(tempo, nivel_dB)] de todas as janelas e a lista dos picos (bem acima do normal do próprio vídeo)."""
    r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'info', '-i', str(video), '-vn', '-af',
                        f'aresample=16000,astats=metadata=1:reset=1:length={janela},ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-',
                        '-f', 'null', '-'], capture_output=True, text=True, timeout=1800)
    brutos, t = [], None
    for ln in r.stdout.splitlines():
        m = re.search(r'pts_time:([\d.]+)', ln)
        if m:
            t = float(m.group(1))
        m = re.search(r'RMS_level=(-?[\d.]+|-inf)', ln)
        if m and t is not None:
            brutos.append((t, -90.0 if m.group(1) == '-inf' else float(m.group(1))))
    baldes: dict = {}
    for t, n in brutos:                      # o FFmpeg anota a cada pedacinho de áudio: junta em janelas (média da potência)
        baldes.setdefault(int(t / janela), []).append(10 ** (n / 10))
    return [(round(k * janela, 2), round(10 * math.log10(max(1e-9, sum(v) / len(v))), 1)) for k, v in sorted(baldes.items())]


def _picos(niveis: list, margem_db: float = 8.0) -> list:
    if len(niveis) < 6:
        return []
    vals = [n for _, n in niveis if n > -80]
    if len(vals) < 6:
        return []
    med = statistics.median(vals)
    out = []
    for t, n in niveis:
        if n >= med + margem_db and n > -35:
            if out and t - out[-1]['t'] <= 1.5:
                out[-1]['fim'] = t
                out[-1]['db'] = max(out[-1]['db'], n)
            else:
                out.append({'t': t, 'fim': t, 'db': n, 'acima_da_media_db': round(n - med, 1)})
    for p in out:
        p['acima_da_media_db'] = round(p['db'] - med, 1)
    return out


def _falas(palavras: list) -> list:
    out = []
    for f in ag.frases(palavras):
        txt = f['texto'].strip()
        dur = max(0.5, f['fim'] - f['ini'])
        ritmo = len(txt.split()) / dur
        forte = txt.count('!') + (1 if txt.isupper() else 0) + (1 if ritmo > 3.6 else 0)
        out.append({'t': round(f['ini'], 2), 'fim': round(f['fim'], 2), 'texto': txt[:160], 'forca': forte, 'ritmo': round(ritmo, 2)})
    return out


# ---------------------------------------------------------------- linha do tempo e destaques
def linha_do_tempo(video: Path, palavras: list, dur: float) -> dict:
    cenas = mudancas_de_cena(video)
    niveis = picos_de_audio(video)
    picos = _picos(niveis)
    falas = _falas(palavras)
    ev = []
    for t in cenas:
        ev.append({'tipo': 'mudanca_de_cena', 't': t, 'fim': t, 'descricao': f'A imagem muda de cena aos {mmss(t)}.', 'confianca': 0.7})
    for p in picos:
        ev.append({'tipo': 'pico_de_audio', 't': round(p['t'], 2), 'fim': round(p['fim'], 2),
                   'descricao': f'O som sobe {p["acima_da_media_db"]} dB acima do normal aos {mmss(p["t"])}.', 'confianca': round(min(0.95, 0.5 + p['acima_da_media_db'] / 40), 2)})
    for f in falas:
        if f['forca'] >= 1:
            ev.append({'tipo': 'fala_forte', 't': f['t'], 'fim': f['fim'], 'descricao': f'Fala marcante aos {mmss(f["t"])}: "{f["texto"][:90]}"', 'texto': f['texto'],
                       'confianca': round(min(0.9, 0.5 + 0.12 * f['forca']), 2)})
    ev.sort(key=lambda e: (e['t'], e['tipo']))
    for i, e in enumerate(ev):
        e['id'] = f'e{i + 1}'
        e['observado'] = True
    return {'eventos': ev, 'n_cenas': len(cenas), 'n_picos': len(picos), 'n_falas': len(falas), 'audio': bool(niveis), 'falas': falas}


def destaques(eventos: list, dur: float, min_s: float = 10, max_s: float = 45, antes: float = 4, depois: float = 8) -> list:
    """Agrupa eventos próximos (até 6 s) e dá a cada grupo uma janela de corte. Quanto mais sinais juntos, maior a nota."""
    grupos, atual = [], []
    for e in eventos:
        if atual and e['t'] - atual[-1]['fim'] > 6:
            grupos.append(atual)
            atual = []
        atual.append(e)
    if atual:
        grupos.append(atual)
    peso = {'pico_de_audio': 2.0, 'fala_forte': 1.5, 'mudanca_de_cena': 1.0}
    out = []
    for g in grupos:
        tipos = {e['tipo'] for e in g}
        score = sum(peso[e['tipo']] * e['confianca'] for e in g) + 1.5 * (len(tipos) - 1)
        ini = max(0.0, g[0]['t'] - antes)
        fim = min(dur, g[-1]['fim'] + depois)
        if fim - ini < min_s:
            fim = min(dur, ini + min_s)
        if fim - ini > max_s:
            fim = ini + max_s
        if fim - ini < 3:
            continue
        nomes = {'pico_de_audio': 'pico de som', 'fala_forte': 'fala marcante', 'mudanca_de_cena': 'mudança de cena'}
        out.append({'ini': round(ini, 2), 'fim': round(fim, 2), 'eventos': [e['id'] for e in g], 'score': round(score, 2),
                    'confianca': round(min(0.95, 0.35 + score / 10), 2),
                    'porque': f'Juntou {len(g)} sinal(is) observado(s) ({", ".join(sorted(nomes[t] for t in tipos))}) entre {mmss(g[0]["t"])} e {mmss(g[-1]["fim"])}.'})
    out.sort(key=lambda d: -d['score'])
    out = out[:MAX_DESTAQUES]
    out.sort(key=lambda d: d['ini'])
    for i, d in enumerate(out):
        d['id'] = f'd{i + 1}'
    return out


# ---------------------------------------------------------------- descrição dos quadros (opcional, precisa da chave da IA)
def descrever_quadros(video: Path, eventos: list, pasta: Path, maximo: int = 5) -> tuple[int, str]:
    """Pede à IA uma descrição curta do que aparece NOS QUADROS dos momentos mais fortes. Devolve (quantos descreveu, motivo se falhou)."""
    fortes = sorted([e for e in eventos if e['tipo'] in ('pico_de_audio', 'fala_forte')], key=lambda e: -e['confianca'])[:maximo]
    if not fortes:
        return 0, 'sem momentos fortes para olhar'
    feitos = 0
    for e in fortes:
        q = pasta / f'quadro-{e["id"]}.jpg'
        subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-ss', f'{e["t"]:.2f}', '-i', str(video), '-frames:v', '1', '-vf', 'scale=640:-2', '-q:v', '5', str(q)],
                       stdin=subprocess.DEVNULL, capture_output=True)
        if not q.exists() or q.stat().st_size < 800:
            continue
        try:
            r = ag.gemini([{'text': 'Descreva em UMA frase curta, em português, só o que aparece nesta imagem de um jogo (personagem, veículo, ação, cenário). '
                                   'Se não der para ter certeza, diga "não dá para ter certeza". Não invente o que aconteceu antes ou depois. '
                                   'Responda JSON: {"descricao": "..."}'},
                          {'inlineData': {'mimeType': 'image/jpeg', 'data': base64.b64encode(q.read_bytes()).decode()}}], tempo=90, uso='gameplay')
        except (ag.ErroAgente, pg.ErroRede) as err:
            return feitos, str(err)[:160]
        finally:
            q.unlink(missing_ok=True)
        if isinstance(r, list):
            r = r[0] if r else {}
        txt = str((r or {}).get('descricao', '')).strip()[:200] if isinstance(r, dict) else ''
        if txt and 'não dá para ter certeza' not in txt.lower():
            e['visual'] = txt
            feitos += 1
    return feitos, '' if feitos else 'a IA não conseguiu descrever os quadros'


# ---------------------------------------------------------------- ganchos (3 ou mais), sempre ligados a eventos que existem
TOM = {
    'engracada': ('Isso aqui não era pra acontecer…', 'ESPERA O FINAL 😂'),
    'suspense': ('Fica até o fim: ', 'O QUE VEM AGORA?'),
    'desafio': ('Será que dá? Olha só aos {t}.', 'DÁ OU NÃO DÁ?'),
    'reviravolta': ('Parecia normal, até que…', 'REVIRAVOLTA'),
    'tutorial': ('Presta atenção neste momento.', 'VEJA ESTE LANCE'),
    'documentario': ('Este é o momento mais intenso desta gravação.', 'O MOMENTO'),
}


def ganchos_por_regras(dest: dict, eventos: dict, historia: str) -> list:
    """Sem IA: ganchos montados só com o que foi medido (horário, tipo do sinal, fala real). Nunca diz o que aconteceu no jogo."""
    evs = [eventos[i] for i in dest['eventos'] if i in eventos]
    fala = next((e for e in sorted(evs, key=lambda e: -e['confianca']) if e['tipo'] == 'fala_forte'), None)
    pico = next((e for e in sorted(evs, key=lambda e: -e['confianca']) if e['tipo'] == 'pico_de_audio'), None)
    ref = pico or fala or evs[0]
    abertura, tela = TOM.get(historia, TOM['documentario'])
    out = []
    if fala:
        out.append({'tipo': 'fala_real', 'abertura_falada': f'“{fala["texto"][:90]}”', 'texto_na_tela': tela, 'primeiro_quadro_t': max(dest['ini'], fala['t'] - 0.5),
                    'eventos': [fala['id']], 'justificativa': 'Usa uma fala que está mesmo na gravação.'})
    if pico:
        out.append({'tipo': 'pico_de_som', 'abertura_falada': abertura.replace('{t}', mmss(pico['t'])) if '{t}' in abertura else f'{abertura}'.strip(),
                    'texto_na_tela': f'ESPERA ATÉ {mmss(pico["t"] - dest["ini"])}', 'primeiro_quadro_t': dest['ini'], 'eventos': [pico['id']],
                    'justificativa': f'O som sobe forte aos {mmss(pico["t"])}; o gancho só promete esse momento, não diz o que é.'})
    out.append({'tipo': 'pergunta', 'abertura_falada': f'Olha o que acontece aos {mmss(ref["t"] - dest["ini"])} deste trecho.', 'texto_na_tela': tela,
                'primeiro_quadro_t': max(dest['ini'], ref['t'] - 1.0), 'eventos': [ref['id']], 'justificativa': 'Convida a olhar um momento medido, sem inventar a ação.'})
    out.append({'tipo': 'contagem', 'abertura_falada': f'{round(dest["fim"] - dest["ini"])} segundos que valem a pena.', 'texto_na_tela': f'{round(dest["fim"] - dest["ini"])} SEGUNDOS',
                'primeiro_quadro_t': dest['ini'], 'eventos': [ref['id']], 'justificativa': 'Só usa a duração real do trecho.'})
    return out


def ganchos_por_ia(dest: dict, eventos: dict, historia: str) -> list:
    evs = [eventos[i] for i in dest['eventos'] if i in eventos]
    resumo = [{k: e.get(k) for k in ('id', 'tipo', 't', 'descricao', 'texto', 'visual') if e.get(k) is not None} for e in evs]
    prompt = (f'Você escreve ganchos para um corte de gameplay. História escolhida: {HISTORIAS.get(historia, historia)}. '
              f'Janela do corte: {dest["ini"]:.1f}s a {dest["fim"]:.1f}s. Eventos REALMENTE observados no vídeo (JSON): {json.dumps(resumo, ensure_ascii=False)}. '
              'Escreva 3 ganchos diferentes. REGRAS: cada gancho só pode se apoiar em eventos desta lista (cite os ids em "eventos"); '
              'NÃO invente o que aconteceu no jogo, nomes, placares ou resultados; "primeiro_quadro_t" é um tempo em segundos dentro da janela. '
              'Responda JSON: {"ganchos":[{"abertura_falada":"...","texto_na_tela":"até 6 palavras","primeiro_quadro_t":0,"eventos":["e1"],"justificativa":"..."}]}')
    try:
        from skills import roteador
        apoio, _u = roteador.orientacao('agente1.gameplay', origem='gameplay', registrar_carga=False)
        if apoio:
            prompt += '\n' + apoio
    except Exception:  # noqa: BLE001  (sem skill, o pedido segue igual)
        pass
    r = ag.gemini([{'text': prompt}], tempo=120, uso='gameplay')
    if isinstance(r, list):
        r = {'ganchos': r}
    return [g for g in (r.get('ganchos') if isinstance(r, dict) else None) or [] if isinstance(g, dict)]


def validar_ganchos(gs: list, dest: dict, eventos: dict) -> list:
    """Só passa gancho que cita evento real do destaque, com tempo dentro da janela e texto curto. O resto é descartado."""
    out = []
    for g in gs:
        ids = [i for i in (g.get('eventos') or []) if i in eventos and i in dest['eventos']]
        txt, tela = str(g.get('abertura_falada', '')).strip(), str(g.get('texto_na_tela', '')).strip()
        try:
            t = float(g.get('primeiro_quadro_t'))
        except (TypeError, ValueError):
            continue
        if not ids or not txt or not tela or not (dest['ini'] - 0.01 <= t <= dest['fim']) or len(tela.split()) > 8 or len(txt) > 200:
            continue
        out.append({'tipo': str(g.get('tipo', 'ia'))[:20], 'abertura_falada': txt[:200], 'texto_na_tela': tela[:60], 'primeiro_quadro_t': round(t, 2),
                    'eventos': ids, 'justificativa': str(g.get('justificativa', ''))[:200]})
    return out


def propor_ganchos(dest: dict, eventos: list, historia: str, usar_ia: bool = True) -> dict:
    ev = {e['id']: e for e in eventos}
    ia, aviso = [], ''
    if usar_ia:
        try:
            ia = validar_ganchos(ganchos_por_ia(dest, ev, historia), dest, ev)
        except (ag.ErroAgente, pg.ErroRede) as e:
            aviso = f'A IA não respondeu ({str(e)[:100]}): usei ganchos montados só com o que foi medido.'
    regras = validar_ganchos(ganchos_por_regras(dest, ev, historia), dest, ev)
    gs = ia[:3]
    for g in regras:
        if len(gs) >= 3:
            break
        if all(g['abertura_falada'] != x['abertura_falada'] for x in gs):
            gs.append(g)
    return {'ganchos': gs, 'origem': 'ia' if ia else 'regras', 'aviso': aviso}


# ---------------------------------------------------------------- análise completa e relatório
def analisar_arquivo(video: Path, palavras: list, *, fonte: str, direitos: dict, titulo: str = '', historia: str = 'documentario', usar_ia: bool = True,
                     gid: str = '') -> dict:
    if direitos.get('origem') not in ag.MOTIVOS:
        raise ErroGameplay('Diga de quem é o vídeo antes de analisar: seu, autorizado pelo dono ou de canal com regra pública de cortes.')
    if historia not in HISTORIAS:
        historia = 'documentario'
    dur = ag.duracao(video)
    if dur < 5:
        raise ErroGameplay('Não consegui ler a duração do vídeo.')
    gid = gid or uuid.uuid4().hex[:10]
    pasta = PASTA / gid
    pasta.mkdir(parents=True, exist_ok=True)
    lt = linha_do_tempo(video, palavras, dur)
    if not lt['eventos']:
        raise ErroGameplay('Não achei nenhum momento marcante neste vídeo (sem mudança de cena, pico de som ou fala forte).')
    parcial, motivo = True, 'não foi pedida a descrição dos quadros'
    if usar_ia:
        n, motivo = descrever_quadros(video, lt['eventos'], pasta)
        parcial = n == 0
        if n and n < min(5, len([e for e in lt['eventos'] if e['tipo'] != 'mudanca_de_cena'])):
            motivo = f'a IA descreveu {n} quadro(s); os outros ficaram só com os sinais medidos'
    ds = destaques(lt['eventos'], dur)
    for d in ds:
        pr = propor_ganchos(d, lt['eventos'], historia, usar_ia)
        d['ganchos'], d['ganchos_origem'], d['ganchos_aviso'] = pr['ganchos'], pr['origem'], pr['aviso']
    if any(d.get('ganchos_origem') == 'ia' for d in ds):          # só conta como usada se a IA recebeu o texto e voltou com ganchos válidos
        try:
            from skills import roteador
            roteador.concluir(roteador.selecionar('agente1.gameplay')['usar'], 'agente1.gameplay', artefato='gameplay:' + gid, origem='gameplay',
                              saida=f'{len(ds)} destaques com ganchos ligados a eventos medidos')
        except Exception:  # noqa: BLE001
            pass
    rel = {'id': gid, 'criado': time.time(), 'titulo': titulo[:150], 'historia': historia, 'historias': HISTORIAS,
           'fonte': fonte[:300], 'direitos': {'origem': direitos['origem'], 'nota': str(direitos.get('nota', ''))[:300]},
           'duracao': round(dur, 2), 'arquivo': str(video), 'analise': 'parcial' if parcial else 'completa',
           'analise_motivo': motivo if parcial or motivo else '',
           'sinais': {k: lt[k] for k in ('n_cenas', 'n_picos', 'n_falas', 'audio')}, 'eventos': lt['eventos'], 'destaques': ds,
           'palavras': [list(p) for p in palavras], 'aviso': 'Nada foi publicado. Cada corte ainda passa pelo diretor de qualidade e pela sua aprovação.'}
    (pasta / 'relatorio.json').write_text(json.dumps(rel, ensure_ascii=False), encoding='utf-8')
    return rel


def ler(gid: str) -> dict:
    arq = PASTA / re.sub(r'\W', '', gid) / 'relatorio.json'
    if not arq.exists():
        raise ErroGameplay('Análise não encontrada.')
    return json.loads(arq.read_text(encoding='utf-8'))


def relatorio(gid: str) -> dict:
    """Versão enxuta para o site: sem a transcrição inteira nem o caminho do arquivo."""
    r = ler(gid)
    return {k: v for k, v in r.items() if k not in ('palavras', 'arquivo')} | {'tem_video': Path(r['arquivo']).exists()}


def listar() -> list:
    out = []
    for p in sorted(PASTA.glob('*/relatorio.json'), key=lambda x: -x.stat().st_mtime)[:30] if PASTA.exists() else []:
        try:
            r = json.loads(p.read_text(encoding='utf-8'))
            out.append({'id': r['id'], 'titulo': r.get('titulo', ''), 'criado': r['criado'], 'analise': r['analise'], 'destaques': len(r['destaques']), 'fonte': r['fonte']})
        except (ValueError, KeyError):
            continue
    return out


def propor_de_novo(gid: str, historia: str, usar_ia: bool = True) -> dict:
    r = ler(gid)
    if historia not in HISTORIAS:
        raise ErroGameplay('História desconhecida.')
    for d in r['destaques']:
        pr = propor_ganchos(d, r['eventos'], historia, usar_ia)
        d['ganchos'], d['ganchos_origem'], d['ganchos_aviso'] = pr['ganchos'], pr['origem'], pr['aviso']
    r['historia'] = historia
    (PASTA / gid / 'relatorio.json').write_text(json.dumps(r, ensure_ascii=False), encoding='utf-8')
    return relatorio(gid)


# ---------------------------------------------------------------- jobs (entram na fila; um trabalho pesado por vez)
def _baixar(link: str, gid: str, idioma: str, progresso) -> tuple[Path, list]:
    pasta = PASTA / gid
    pasta.mkdir(parents=True, exist_ok=True)
    if not ag.BAIXAR:
        raise ErroGameplay('Este servidor não tem a função de download.')
    arq, info, legenda = ag.BAIXAR(link, pasta, idioma, progresso)
    dur = float(info.get('duration') or 0) or ag.duracao(arq)
    palavras = ag.palavras_json3(legenda.read_text(encoding='utf-8', errors='replace')) if legenda else []
    if len(palavras) < 20:
        try:
            palavras = ag.transcrever_ia(arq, dur, pasta, idioma)
        except (ag.ErroAgente, pg.ErroRede):
            palavras = []                    # sem fala: a análise segue só com cena e som
    return arq, palavras


def job_analisar(ctx):
    d = ctx.dados
    gid = uuid.uuid4().hex[:10]
    direitos = {'origem': d.get('origem', ''), 'nota': d.get('nota', '')}
    if direitos['origem'] not in ag.MOTIVOS:
        raise ErroGameplay('Diga de quem é o vídeo antes de analisar.')
    ctx.progresso(5, 'Baixando o vídeo')
    try:
        if d.get('video'):                   # vídeo já guardado no servidor (enviado pelo site)
            arq = pg.video_path(str(d['video']))
            palavras = []
        else:
            arq, palavras = _baixar(str(d.get('link', '')), gid, d.get('idioma', 'pt'), lambda p: ctx.progresso(5 + p * 30, 'Baixando o vídeo'))
        ctx.progresso(40, 'Medindo cenas, sons e falas')
        r = analisar_arquivo(arq, palavras, fonte=str(d.get('link') or 'arquivo enviado por você'), direitos=direitos, titulo=str(d.get('titulo', '')),
                             historia=str(d.get('historia', 'documentario')), usar_ia=bool(d.get('usar_ia', True)), gid=gid)
    except (ag.ErroAgente, pg.ErroRede) as e:
        raise ErroGameplay(str(e))
    return {'resultado': {'id': r['id'], 'destaques': len(r['destaques']), 'analise': r['analise']}, 'etapa': 'Análise pronta'}


def gid_seed(rel: dict) -> str:
    return rel['id']


def job_cortar(ctx):
    """Faz UM corte do destaque escolhido (com o gancho e o estilo escolhidos). O corte passa pelo diretor de qualidade e fica esperando a sua aprovação."""
    d = ctx.dados
    rel = ler(str(d['gid']))
    dest = next((x for x in rel['destaques'] if x['id'] == d.get('destaque')), None)
    if not dest:
        raise ErroGameplay('Destaque não encontrado.')
    video = Path(rel['arquivo'])
    if not video.exists():
        raise ErroGameplay('O vídeo desta análise não está mais no servidor. Analise de novo.')
    ini = max(0.0, float(d.get('ini', dest['ini'])))
    fim = min(rel['duracao'], float(d.get('fim', dest['fim'])))
    if not 3 <= fim - ini <= 120:
        raise ErroGameplay('O corte precisa ter entre 3 e 120 segundos.')
    g = d.get('gancho') or (dest['ganchos'][0] if dest.get('ganchos') else {})
    palavras = [tuple(p) for p in rel['palavras']]
    perfil = None
    if d.get('perfil'):
        try:
            perfil = pf.obter(str(d['perfil']))
        except pf.ErroPerfil as e:
            raise ErroGameplay(str(e))
    modelo = ag.mo.por_id(str(d.get('modelo', ''))) or (ag.mo.por_id(perfil['templates'][0]) if perfil and perfil['templates'] else None) or ag.mo.ativos(ag.config()['cortes']['modelos'])[0]
    tpl = ag.mo.tpl(modelo)
    notas_perfil = pf.aplicar_ao_tpl(tpl, perfil, ag.random.Random(gid_seed(rel))) if perfil else []
    if d.get('estilo') in ag.vp.PRESETS:
        tpl['estilo_visual'], tpl['estilo_forca'], tpl['estilo_off'], tpl['estilo_texto'] = d['estilo'], float(d.get('estilo_forca', 1.0)), list(d.get('estilo_off') or []), ''
    modo = mr.valido(str(d.get('modo', ''))) or (mr.valido(perfil['modo_qualidade']) if perfil else '')
    ops = mr.aplicar(tpl, modo) if modo else []
    c = {'ini': round(ini, 2), 'fim': round(fim, 2), 'gancho': str(g.get('texto_na_tela', ''))[:80], 'titulo': (rel['titulo'] or 'Gameplay')[:70] + ' — ' + str(g.get('texto_na_tela', 'destaque'))[:30],
         'nota': 0, 'motivo': dest['porque'], 'hashtags': [], 'legenda_post': ''}
    vid = uuid.uuid4().hex[:12]
    pasta = PASTA / rel['id'] / 'trab'
    pasta.mkdir(parents=True, exist_ok=True)
    ctx.progresso(20, 'Montando o corte')
    ag.editar(video, c, palavras, tpl, pg.VIDEOS / (vid + '.mp4'), pasta)
    qa = ag.inspecionar_corte(pg.VIDEOS / (vid + '.mp4'), c, palavras, pasta)
    refeito = 0
    while not ag.veredito_corte(qa)['aprovado'] and refeito < ag.MAX_REFAZER_CORTE and not d.get('ini') and not d.get('fim'):
        refeito += 1
        ctx.progresso(60, f'Diretor de qualidade mandou refazer (tentativa {refeito})')
        ajuste = ag.ajustar_corte(c, palavras, qa, ag.config()['cortes'], rel['duracao'])
        if not ajuste:
            break
        c.update(ajuste)
        ag.editar(video, c, palavras, tpl, pg.VIDEOS / (vid + '.mp4'), pasta)
        qa = ag.inspecionar_corte(pg.VIDEOS / (vid + '.mp4'), c, palavras, pasta)
    vd = ag.veredito_corte(qa)
    if modo and mr.MODOS[modo]['qa_volume']:
        qa['volume'] = mr.volume_final(pg.VIDEOS / (vid + '.mp4'))
    qa['diretor'] = {'veredito': 'aprovado' if vd['aprovado'] else 'reprovado', 'motivos': vd['motivos'], 'tentativas': refeito, 't': time.time()}
    evs = {e['id']: e for e in rel['eventos']}
    arq = pg.VIDEOS / (vid + '.mp4')
    c.update(id=uuid.uuid4().hex[:10], chave=ag.secrets.token_urlsafe(18), video=vid, criado=time.time(), status='pronto' if vd['aprovado'] else 'reprovado', post='',
             origem='gameplay-' + rel['id'], origem_titulo=rel['titulo'][:150], canal='', canal_nome='', variacoes=[f'História: {HISTORIAS.get(rel["historia"], "")}'] + ([f'Perfil {perfil["nome"]}: ' + ('; '.join(notas_perfil) or 'sem mudanças de identidade')] if perfil else []) + ([f'Modo {mr.MODOS[modo]["nome"]}: ' + '; '.join(ops)] if modo else []),
             fala='transcrição' if palavras else 'sem fala', tamanho=arq.stat().st_size, email=False, tipo='gameplay', modelo=modelo['id'], modelo_nome=modelo['nome'],
             hash=ag._hash(arq), legendado=tpl['legenda'] != 'nenhuma', qa=qa, direitos=rel['direitos'], dur=round(fim - ini, 1),
             gameplay={'analise': rel['id'], 'destaque': dest['id'], 'fonte': rel['fonte'], 'gancho': g,
                       'eventos': [{k: evs[i].get(k) for k in ('id', 'tipo', 't', 'descricao', 'confianca', 'visual')} for i in dest['eventos'] if i in evs]})
    if perfil:
        c.update(perfil=perfil['id'], perfil_nome=perfil['nome'], perfil_versao=perfil['versao'], redes=list(perfil['redes']), hashtags=list(perfil['hashtags_base']))
    ag._mudar(lambda e: e['cortes'].append(c))
    return {'resultado': {'corte': c['id'], 'status': c['status']}, 'etapa': 'Corte pronto' if vd['aprovado'] else 'Diretor reprovou'}


def pedir_analise(d: dict) -> dict:
    import fila
    if d.get('origem') not in ag.MOTIVOS:
        raise ErroGameplay('Diga de quem é o vídeo: seu, autorizado pelo dono ou de canal com regra pública de cortes.')
    if not d.get('video') and not re.match(r'https?://', str(d.get('link', ''))):
        raise ErroGameplay('Cole o link do vídeo ou envie o arquivo.')
    dados = {k: d.get(k) for k in ('link', 'video', 'origem', 'nota', 'titulo', 'historia', 'usar_ia', 'idioma')}
    j = fila.enfileirar('gameplay.analisar', agente='agente1', dados=dados, recurso='pesado', titulo='Analisar gameplay', max_tentativas=1)
    return {'ok': True, 'job': j['id']}


def pedir_corte(d: dict) -> dict:
    import fila
    ler(str(d.get('gid', '')))
    chaves = ('gid', 'destaque', 'gancho', 'ini', 'fim', 'modelo', 'estilo', 'estilo_forca', 'estilo_off', 'modo', 'perfil')
    j = fila.enfileirar('gameplay.cortar', agente='agente1', dados={k: d[k] for k in chaves if k in d}, recurso='pesado', titulo='Cortar destaque de gameplay', max_tentativas=1)
    return {'ok': True, 'job': j['id']}


def job_comparar(ctx):
    d = ctx.dados
    ctx.progresso(10, 'Montando o corte nos dois modos')
    return {'resultado': comparar_modos(str(d['gid']), str(d['destaque']), str(d.get('estilo', ''))), 'etapa': 'Comparação pronta'}


def pedir_comparacao(d: dict) -> dict:
    import fila
    ler(str(d.get('gid', '')))
    j = fila.enfileirar('gameplay.comparar', agente='agente1', dados={k: d.get(k) for k in ('gid', 'destaque', 'estilo')}, recurso='pesado',
                        titulo='Comparar modo Rápido e Caprichado', max_tentativas=1)
    return {'ok': True, 'job': j['id']}


def iniciar():
    import fila
    fila.registrar('gameplay.comparar', job_comparar, 'pesado')
    fila.registrar('gameplay.analisar', job_analisar, 'pesado')
    fila.registrar('gameplay.cortar', job_cortar, 'pesado')


def comparar_modos(gid: str, destaque: str, estilo: str = '') -> dict:
    """O MESMO corte nos dois modos, lado a lado em números reais: tempo, tamanho, volume, operações. Os vídeos ficam guardados para comparar no site."""
    rel = ler(gid)
    dest = next((x for x in rel['destaques'] if x['id'] == destaque), None)
    video = Path(rel['arquivo'])
    if not dest or not video.exists():
        raise ErroGameplay('Destaque ou vídeo não encontrado.')
    palavras = [tuple(p) for p in rel['palavras']]
    modelo = ag.mo.ativos(ag.config()['cortes']['modelos'])[0]
    pasta = PASTA / gid / 'comparar'
    pasta.mkdir(parents=True, exist_ok=True)
    out = {}
    for modo in mr.MODOS:
        tpl = ag.mo.tpl(modelo)
        if estilo in ag.vp.PRESETS:
            tpl['estilo_visual'], tpl['estilo_forca'], tpl['estilo_off'], tpl['estilo_texto'] = estilo, 1.0, [], ''
        ops = mr.aplicar(tpl, modo)
        dest_arq = pasta / f'{modo}.mp4'
        t0 = time.time()
        ag.editar(video, {'ini': dest['ini'], 'fim': dest['fim'], 'gancho': ''}, palavras, tpl, dest_arq, pasta)
        seg = time.time() - t0
        out[modo] = {'nome': mr.MODOS[modo]['nome'], 'segundos_de_render': round(seg, 2), 'tamanho_bytes': dest_arq.stat().st_size, 'operacoes': ops,
                     'volume': mr.volume_final(dest_arq), 'duracao': round(ag.duracao(dest_arq), 2)}
    (pasta / 'resultado.json').write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    return out
