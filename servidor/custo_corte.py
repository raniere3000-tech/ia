"""Custo de cada corte e o banco de trechos.

O que gasta dinheiro (ou cota) no Agente 1 são as chamadas ao Gemini:
  - ouvir o áudio (só quando o vídeo não tem legenda do YouTube) — a parte mais cara, áudio custa ~3x o texto;
  - escolher os trechos (texto da transcrição) — uma chamada a cada 25 min de vídeo;
  - olhar uma imagem (câmera do streamer, momentos sem fala).
Baixar o vídeo e editar com o FFmpeg não custa nada.

Aqui ficam:
  - o registro de CADA chamada ao Gemini (tokens que o Google devolveu × tabela de preço), ligada à análise que a fez;
  - a análise de cada vídeo-fonte (quantos trechos a IA achou, quantos viraram corte, quantos ficaram guardados);
  - o banco de trechos: os bons trechos que sobram de uma análise ficam guardados (com a transcrição) e viram cortes
    nas próximas rodadas SEM pagar a IA de novo para ouvir e escolher;
  - o resumo para a aba Custos do Coordenador, as sugestões e o aviso semanal.

Os valores em R$ são ESTIMADOS: tokens reais devolvidos pelo Google × preço de tabela (Agentes > Avisos e chaves > orçamento).
A cobrança de verdade é a do Google (ai.studio/spend). Chave grátis = R$ 0 de verdade, mas gasta cota.
"""
from __future__ import annotations

import gzip
import json
import threading
import time
import uuid
from pathlib import Path

import banco as db
import postagem as pg

PASTA_RESERVA = pg.DADOS / 'reserva_trechos'
DIAS_RESERVA = 21                 # trecho guardado vale 3 semanas (depois o assunto esfria)
_LOCAL = threading.local()
_PRONTO = False
_LOCK = threading.Lock()

# preço por milhão de tokens (US$) dos modelos que não seguem a tabela do orçamento (texto/áudio/saída)
PRECO_ESPECIAL = {'image': (0.30, 30.0), 'tts': (0.50, 10.0)}

ETAPAS = {'ouvir': 'Ouvir o áudio (vídeo sem legenda)', 'escolher': 'Escolher os trechos', 'camera': 'Achar a câmera do streamer',
          'momento': 'Olhar momentos sem fala', 'outro': 'Outros'}
USOS_A1 = ('cortes', 'camera')


def _tabelas():
    global _PRONTO
    if _PRONTO:
        return
    with _LOCK:
        if _PRONTO:
            return
        with db._LOCK_ESCRITA:
            db.con().executescript('''
            CREATE TABLE IF NOT EXISTS ia_uso (id INTEGER PRIMARY KEY AUTOINCREMENT, t REAL NOT NULL, uso TEXT, etapa TEXT, modelo TEXT, chave TEXT,
                ent INTEGER, sai INTEGER, audio INTEGER, dolar REAL, reais REAL, cobrado INTEGER, ref TEXT);
            CREATE INDEX IF NOT EXISTS ia_uso_t ON ia_uso (t);
            CREATE INDEX IF NOT EXISTS ia_uso_ref ON ia_uso (ref);
            CREATE TABLE IF NOT EXISTS ia_analises (id TEXT PRIMARY KEY, t REAL NOT NULL, video TEXT, titulo TEXT, url TEXT, fonte TEXT, dur REAL,
                achados INTEGER, usados INTEGER, guardados INTEGER);
            CREATE INDEX IF NOT EXISTS ia_analises_t ON ia_analises (t);
            CREATE TABLE IF NOT EXISTS cortes_reserva (id INTEGER PRIMARY KEY AUTOINCREMENT, analise TEXT, video TEXT, url TEXT, titulo TEXT,
                canal TEXT, canal_nome TEXT, nota INTEGER, ini REAL, fim REAL, dados TEXT, criado REAL NOT NULL, usado REAL);
            CREATE INDEX IF NOT EXISTS cortes_reserva_livre ON cortes_reserva (usado, criado);
            ''')
        _PRONTO = True


# ---------------------------------------------------------------- de qual análise é a chamada
def definir_ref(ref: str):
    _LOCAL.ref = ref or ''


def ref_atual() -> str:
    return getattr(_LOCAL, 'ref', '') or ''


def nova_ref() -> str:
    return 'an' + uuid.uuid4().hex[:10]


# ---------------------------------------------------------------- registro de cada chamada
def _tipo_partes(corpo: dict) -> tuple[bool, bool]:
    """(tem áudio, tem imagem) no pedido."""
    audio = imagem = False
    try:
        for c in corpo.get('contents') or []:
            for p in c.get('parts') or []:
                d = p.get('inline_data') or p.get('inlineData') or {}
                mime = str(d.get('mime_type') or d.get('mimeType') or '')
                audio |= mime.startswith('audio/')
                imagem |= mime.startswith('image/')
    except (AttributeError, TypeError):
        pass
    return audio, imagem


def _etapa(uso: str, audio: bool, imagem: bool) -> str:
    if uso == 'camera':
        return 'camera'
    if uso == 'cortes':
        return 'ouvir' if audio else 'momento' if imagem else 'escolher'
    return 'outro'


def preco(modelo: str, ent: int, sai: int, audio: bool) -> float:
    """US$ estimados pela tabela."""
    import agente as ag
    o = ag.config()['orcamento']
    for k, (pe, ps) in PRECO_ESPECIAL.items():
        if k in modelo:
            return ent / 1e6 * pe + sai / 1e6 * ps
    return ent / 1e6 * (o['preco_audio'] if audio else o['preco_texto']) + sai / 1e6 * o['preco_saida']


def registrar(uso: str, modelo: str, chave: str, corpo: dict, uso_tokens: dict | None, cobrado: bool):
    """Chamado pelo agente.http_gemini depois de cada resposta boa do Google. Nunca derruba o trabalho."""
    try:
        _tabelas()
        import agente as ag
        u = uso_tokens or {}
        ent = int(u.get('promptTokenCount') or 0)
        sai = int(u.get('candidatesTokenCount') or 0) + int(u.get('thoughtsTokenCount') or 0)
        audio, imagem = _tipo_partes(corpo)
        dol = preco(modelo, ent, sai, audio)
        reais = dol * float(ag.config()['orcamento']['dolar'])
        db.executar('INSERT INTO ia_uso (t, uso, etapa, modelo, chave, ent, sai, audio, dolar, reais, cobrado, ref) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                    time.time(), uso, _etapa(uso, audio, imagem), modelo[:60], chave, ent, sai, int(audio), round(dol, 6), round(reais, 6),
                    int(bool(cobrado)), ref_atual())
    except Exception as e:  # noqa: BLE001
        print('custo_corte: registro', e)


def registrar_analise(ref: str, v: dict, fonte: str, dur: float, achados: int, usados: int, guardados: int):
    try:
        _tabelas()
        db.executar('INSERT OR REPLACE INTO ia_analises (id, t, video, titulo, url, fonte, dur, achados, usados, guardados) VALUES (?,?,?,?,?,?,?,?,?,?)',
                    ref, time.time(), str(v.get('id') or '')[:40], str(v.get('titulo') or '')[:150], str(v.get('url') or '')[:300], fonte, float(dur or 0),
                    int(achados), int(usados), int(guardados))
    except Exception as e:  # noqa: BLE001
        print('custo_corte: análise', e)


# ---------------------------------------------------------------- banco de trechos
def _arq(ref: str) -> Path:
    return PASTA_RESERVA / f'{ref}.json.gz'


def guardar(ref: str, v: dict, sobras: list, palavras: list, cam=None, tem_cam: bool = False) -> int:
    """Guarda os trechos bons que sobraram da análise (com a transcrição) para virarem cortes depois, sem IA."""
    if not sobras or not v.get('url'):
        return 0
    _tabelas()
    PASTA_RESERVA.mkdir(parents=True, exist_ok=True)
    with gzip.open(_arq(ref), 'wt', encoding='utf-8') as f:
        json.dump({'palavras': palavras, 'cam': cam, 'tem_cam': tem_cam}, f, ensure_ascii=False)
    agora = time.time()
    for c in sobras:
        db.executar('INSERT INTO cortes_reserva (analise, video, url, titulo, canal, canal_nome, nota, ini, fim, dados, criado) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    ref, str(v.get('id') or '')[:40], v['url'][:300], str(v.get('titulo') or '')[:150], str(v.get('canal') or '')[:60],
                    str(v.get('canal_nome') or '')[:80], int(c.get('nota') or 0), float(c['ini']), float(c['fim']),
                    json.dumps(c, ensure_ascii=False), agora)
    return len(sobras)


def limpar():
    """Tira da reserva o que venceu e apaga a transcrição que ninguém mais vai usar."""
    _tabelas()
    limite = time.time() - DIAS_RESERVA * 86400
    db.executar('UPDATE cortes_reserva SET usado=-1 WHERE usado IS NULL AND criado < ?', limite)
    vivos = {r['analise'] for r in db.todos('SELECT DISTINCT analise FROM cortes_reserva WHERE usado IS NULL')}
    if PASTA_RESERVA.exists():
        for a in PASTA_RESERVA.glob('*.json.gz'):
            if a.name[:-8] not in vivos:
                a.unlink(missing_ok=True)


def disponiveis() -> list:
    _tabelas()
    limite = time.time() - DIAS_RESERVA * 86400
    return db.todos('SELECT id, analise, video, url, titulo, canal_nome, nota, ini, fim, criado FROM cortes_reserva '
                    'WHERE usado IS NULL AND criado >= ? ORDER BY nota DESC, criado', limite)


def tomar(quantos: int, tema: str = '') -> dict | None:
    """Pega da reserva até `quantos` trechos de UM vídeo (um download só): o vídeo com o melhor trecho guardado.
    Marca como usados na hora (outra rodada não pega os mesmos). Devolve None se não há nada guardado."""
    import agente as ag
    limpar()
    with _LOCK:
        livres = disponiveis()
        if tema:
            livres = [r for r in livres if ag._casa_tema(r['titulo'], [tema])]
        for r in livres:
            arq = _arq(r['analise'])
            if not arq.exists():
                db.executar('UPDATE cortes_reserva SET usado=-1 WHERE analise=? AND usado IS NULL', r['analise'])
                continue
            try:
                with gzip.open(arq, 'rt', encoding='utf-8') as f:
                    extra = json.load(f)
            except (OSError, ValueError):
                db.executar('UPDATE cortes_reserva SET usado=-1 WHERE analise=? AND usado IS NULL', r['analise'])
                continue
            grupo = [x for x in livres if x['analise'] == r['analise']][:max(1, quantos)]
            agora = time.time()
            itens = []
            for x in grupo:
                db.executar('UPDATE cortes_reserva SET usado=? WHERE id=?', agora, x['id'])
                d = db.um('SELECT dados FROM cortes_reserva WHERE id=?', x['id'])
                itens.append(json.loads(d['dados']))
            itens.sort(key=lambda c: c['ini'])
            v = {'id': r['video'], 'url': r['url'], 'titulo': r['titulo'], 'canal': '', 'canal_nome': r['canal_nome'] or ''}
            return {'ref': r['analise'], 'video': v, 'itens': itens, 'ids': [x['id'] for x in grupo],
                    'palavras': [tuple(p) for p in extra.get('palavras') or []], 'cam': extra.get('cam'), 'tem_cam': bool(extra.get('tem_cam'))}
    return None


def devolver(reserva: dict, descartar: bool = False):
    """Não deu para cortar (ex.: o download falhou). descartar=True: o vídeo saiu do ar, não tenta mais."""
    for i in reserva.get('ids') or []:
        db.executar('UPDATE cortes_reserva SET usado=? WHERE id=?', -1 if descartar else None, i)


# ---------------------------------------------------------------- resumo para a aba Custos
def _reais(x: float | None) -> float | None:
    return None if x is None else round(x, 4)


def _cortes_periodo(desde: float) -> list:
    import agente as ag
    return [c for c in ag.estado()['cortes'] if c.get('criado', 0) >= desde and c.get('tipo', 'agente') == 'agente' and c.get('video')]


def historico(dias: int = 30) -> dict:
    """O que já estava guardado ANTES do registro por chamada: os cortes feitos (de qual vídeo saíram e se a IA
    precisou ouvir o áudio), o contador de gasto do mês (só a chave paga), os vídeos que deram erro, as vezes em que a
    chave grátis acabou e a paga entrou, e o gasto estimado do Agente 3. Tudo dado real; nada inventado."""
    import agente as ag
    agora = time.time()
    desde = agora - dias * 86400
    e = ag.estado()
    grupos: dict = {}
    for c in e['cortes']:
        if c.get('criado', 0) < desde or c.get('tipo', 'agente') != 'agente' or not c.get('origem'):
            continue
        g = grupos.setdefault(c.get('analise') or c['origem'], {'video': c['origem'], 'titulo': c.get('origem_titulo') or c.get('titulo') or '',
                                                                 'fala': c.get('fala') or '', 't': c['criado'], 'cortes': 0, 'reprovados': 0, 'live': bool(c.get('live'))})
        g['t'] = min(g['t'], c['criado'])
        g['reprovados' if c.get('status') in ('reprovado', 'descartado') else 'cortes'] += 1
    lista = sorted(grupos.values(), key=lambda g: -g['t'])
    ouvidos = [g for g in lista if g['fala'] == 'IA']
    feitos = sum(g['cortes'] for g in lista)
    erros = [v for v in e['vistos'].values() if v.get('t', 0) >= desde and str(v.get('r', '')).startswith('erro')]
    trocas = [x for x in e['log'] if x.get('t', 0) >= desde and 'sem cota; usei a outra' in str(x.get('texto', ''))]
    meses = {}
    for m, g in sorted(e['gasto'].items()):
        if m >= time.strftime('%Y-%m', time.localtime(desde)):
            meses[m] = {'reais_pago': round(g.get('reais', 0), 2), 'chamadas_pagas': g.get('chamadas', 0)}
    a3 = db.um('SELECT COALESCE(SUM(estimado),0) AS s, COUNT(DISTINCT job) AS n FROM custos WHERE t >= ?', desde) or {'s': 0, 'n': 0}
    pago = sum(m['reais_pago'] for m in meses.values())
    return {
        'dias': dias, 'analises': len(lista), 'cortes': feitos, 'reprovados': sum(g['reprovados'] for g in lista),
        'cortes_por_analise': round(feitos / len(lista), 1) if lista else None,
        'ouvidos_pela_ia': len(ouvidos), 'parte_ouvidos': round(len(ouvidos) / len(lista), 2) if lista else 0,
        'videos_com_erro': len(erros), 'trocas_para_paga': len(trocas), 'meses': meses, 'reais_pago_meses': round(pago, 2),
        'por_corte_contador': round(pago / feitos, 3) if feitos and pago > 0 else None,
        'agente3': {'reais_estimado': round(a3['s'] or 0, 2), 'videos': a3['n'] or 0},
        'lista': lista[:15],
    }


def resumo(dias: int = 30) -> dict:
    import agente as ag
    _tabelas()
    dias = max(1, min(365, int(dias)))
    agora = time.time()
    desde = agora - dias * 86400
    usos = db.todos('SELECT uso, etapa, chave, ent, sai, audio, reais, cobrado, ref, t FROM ia_uso WHERE t >= ?', desde)
    a1 = [u for u in usos if u['uso'] in USOS_A1]
    pago_a1 = sum(u['reais'] for u in a1 if u['cobrado'])
    tabela_a1 = sum(u['reais'] for u in a1)
    por_etapa = {}
    for u in a1:
        e = por_etapa.setdefault(u['etapa'], {'etapa': u['etapa'], 'nome': ETAPAS.get(u['etapa'], u['etapa']), 'chamadas': 0, 'reais_tabela': 0.0, 'reais_pago': 0.0})
        e['chamadas'] += 1
        e['reais_tabela'] += u['reais']
        e['reais_pago'] += u['reais'] if u['cobrado'] else 0
    etapas = sorted(por_etapa.values(), key=lambda e: -e['reais_tabela'])
    for e in etapas:
        e['parte'] = round(e['reais_tabela'] / tabela_a1, 3) if tabela_a1 > 0 else 0
        e['reais_tabela'], e['reais_pago'] = _reais(e['reais_tabela']), _reais(e['reais_pago'])
    outros = {}
    for u in usos:
        if u['uso'] not in USOS_A1:
            o = outros.setdefault(u['uso'], {'uso': u['uso'], 'nome': ag.USOS.get(u['uso'], u['uso']), 'chamadas': 0, 'reais_tabela': 0.0, 'reais_pago': 0.0})
            o['chamadas'] += 1
            o['reais_tabela'] += u['reais']
            o['reais_pago'] += u['reais'] if u['cobrado'] else 0
    for o in outros.values():
        o['reais_tabela'], o['reais_pago'] = _reais(o['reais_tabela']), _reais(o['reais_pago'])

    cortes = _cortes_periodo(desde)
    bons = [c for c in cortes if c.get('status') not in ('reprovado', 'descartado')]
    reprov = [c for c in cortes if c.get('status') == 'reprovado']
    medidos = [c for c in bons if c.get('analise')]          # cortes feitos depois que o registro começou

    analises = db.todos('SELECT * FROM ia_analises WHERE t >= ? ORDER BY t DESC', desde)
    custo_ref: dict = {}
    for u in usos:
        if u['ref']:
            custo_ref.setdefault(u['ref'], [0.0, 0.0])
            custo_ref[u['ref']][0] += u['reais']
            custo_ref[u['ref']][1] += u['reais'] if u['cobrado'] else 0
    todos_cortes = ag.estado()['cortes']
    por_ref: dict = {}
    for c in todos_cortes:
        if c.get('analise'):
            por_ref.setdefault(c['analise'], [0, 0])
            por_ref[c['analise']][0 if c.get('status') not in ('reprovado', 'descartado') else 1] += 1
    reserva = disponiveis()
    na_reserva: dict = {}
    for r in reserva:
        na_reserva[r['analise']] = na_reserva.get(r['analise'], 0) + 1
    lista = []
    for a in analises[:15]:
        tab, pago = custo_ref.get(a['id'], [0.0, 0.0])
        feitos, rep = por_ref.get(a['id'], [0, 0])
        lista.append({'id': a['id'], 't': a['t'], 'titulo': a['titulo'], 'url': a['url'], 'fonte': a['fonte'], 'minutos': round((a['dur'] or 0) / 60, 1),
                      'achados': a['achados'], 'cortes': feitos, 'reprovados': rep, 'guardados': na_reserva.get(a['id'], 0),
                      'reais_tabela': _reais(tab), 'reais_pago': _reais(pago), 'por_corte': _reais(tab / feitos) if feitos else None})
    cortes_por_analise = round(len([c for c in medidos if c['analise'] in {a['id'] for a in analises}]) / len(analises), 1) if analises else None

    # contador antigo (desde sempre): só a chave paga, todos os agentes, por mês
    mes = ag.gasto_mes()
    o = ag.config()['orcamento']
    ini_mes = time.mktime(time.strptime(time.strftime('%Y-%m') + '-01', '%Y-%m-%d'))
    cortes_mes = [c for c in _cortes_periodo(ini_mes) if c.get('status') not in ('reprovado', 'descartado')]
    r = {
        'dias': dias, 'desde': desde, 'gerado': agora,
        'medindo_desde': (db.um('SELECT MIN(t) AS t FROM ia_uso') or {}).get('t'),
        'a1': {'chamadas': len(a1), 'reais_pago': _reais(pago_a1), 'reais_tabela': _reais(tabela_a1), 'etapas': etapas,
               'chave_gratis': sum(1 for u in a1 if not u['cobrado'])},
        'cortes': {'feitos': len(bons), 'reprovados': len(reprov), 'medidos': len(medidos)},
        'por_corte': {'pago': _reais(pago_a1 / len(medidos)) if medidos else None, 'tabela': _reais(tabela_a1 / len(medidos)) if medidos else None},
        'analises': {'total': len(analises), 'cortes_por_analise': cortes_por_analise, 'lista': lista,
                     'achados_media': round(sum(a['achados'] or 0 for a in analises) / len(analises), 1) if analises else None},
        'reserva': {'trechos': len(reserva), 'videos': len(na_reserva), 'dias_validade': DIAS_RESERVA},
        'outros': sorted(outros.values(), key=lambda x: -x['reais_tabela']),
        'mes': {'reais_pago': round(mes['reais'], 2), 'chamadas_pagas': mes['chamadas'], 'teto': o['teto'], 'cortes': len(cortes_mes),
                'por_corte_antigo': round(mes['reais'] / len(cortes_mes), 4) if cortes_mes and mes['reais'] > 0 else None},
        'config': {'por_analise': ag.config()['cortes'].get('por_analise', 0), 'por_video': ag.config()['cortes']['por_video'],
                   'por_semana': ag.config()['cortes']['por_semana'], 'chave_cortes': ag.config()['chaves_uso'].get('cortes', 'gratis'),
                   'dolar': o['dolar'], 'preco_texto': o['preco_texto'], 'preco_audio': o['preco_audio'], 'preco_saida': o['preco_saida']},
    }
    r['historico'] = historico(dias)
    r['sugestoes'] = sugestoes(r)
    return r


def _brl(x) -> str:
    if x is None:
        return '—'
    if 0 < x < 0.01:
        return 'menos de R$ 0,01'
    return 'R$ ' + f'{x:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def sugestoes(r: dict) -> list:
    """Sugestões concretas para tirar mais cortes gastando menos, lidas do histórico dos últimos dias e do registro por chamada.
    Cada uma diz de onde veio o número. `feito`: a configuração já está como a sugestão pede (aparece para você saber)."""
    import agente as ag
    out = []
    cfg = r['config']
    cu = ag.config()['chaves_uso']
    co = ag.config()['cortes']
    s = ag.segredos()
    an, h = r['analises'], r['historico']
    medido = an['total'] >= 2
    cpa = an['cortes_por_analise'] if medido else h['cortes_por_analise']
    n_an = an['total'] if medido else h['analises']
    base = 'registro por chamada' if medido else f'histórico dos últimos {h["dias"]} dias'
    etapas = {e['etapa']: e for e in r['a1']['etapas']}

    if cpa is not None and n_an >= 1 and cpa < 6:
        alvo = 12 if cpa < 3 else 16
        feito = cfg['por_analise'] >= alvo
        out.append({'id': 'mais_por_analise', 'prioridade': 1, 'feito': feito, 'fonte': base,
                    'titulo': f'Cada vídeo analisado rendeu só {str(cpa).replace(".", ",")} corte(s) ({n_an} vídeo(s))',
                    'texto': f'O que custa é a análise do vídeo, não o corte. Pedindo {alvo} trechos na mesma análise, a análise custa quase o mesmo '
                             '(só a resposta da IA fica um pouco maior) e os trechos que não saem na hora ficam guardados para virar corte depois, '
                             f'sem pagar a IA de novo. Com {alvo} por análise, o custo de cada corte cai para cerca de 1/{max(2, round(alvo / max(cpa, 1)))} '
                             'do que era.' + (' Já está ligado.' if feito else ''),
                    'acao': {'rotulo': f'Pedir {alvo} trechos por análise', 'cortes': {'por_analise': alvo}}})
    elif cfg['por_analise'] <= 0:
        out.append({'id': 'mais_por_analise', 'prioridade': 1, 'feito': False, 'fonte': 'configuração',
                    'titulo': 'Banco de trechos desligado',
                    'texto': f'Hoje cada vídeo analisado rende no máximo {cfg["por_video"]} corte(s) e o resto que a IA achou é jogado fora. '
                             f'Ligando, os trechos que sobram ficam guardados {DIAS_RESERVA} dias e viram corte sem pagar a IA de novo.',
                    'acao': {'rotulo': 'Pedir 12 trechos por análise', 'cortes': {'por_analise': 12}}})

    ouvir = etapas.get('ouvir')
    parte = ouvir['parte'] if ouvir and medido else h['parte_ouvidos']
    if parte >= 0.3 and (ouvir or h['ouvidos_pela_ia']):
        txt = (f'Ouvir o áudio foi {round(parte * 100)}% do custo dos cortes' if ouvir and medido
               else f'{h["ouvidos_pela_ia"]} de {h["analises"]} vídeo(s) não tinham legenda e a IA teve que ouvir o áudio inteiro')
        out.append({'id': 'so_com_legenda', 'prioridade': 2, 'feito': bool(co.get('so_com_legenda')), 'fonte': base, 'titulo': txt,
                    'texto': 'Ouvir é a parte mais cara: áudio custa cerca de 3 vezes o texto e a IA ouve o vídeo todo, em pedaços de 8 minutos. '
                             'Vídeo com legenda do YouTube sai quase de graça para ouvir. Ligando "Só vídeos com legenda", o Agente 1 pula o vídeo sem '
                             'legenda e pega o próximo (gameplay sem fala continua funcionando, pelo som e pela imagem).',
                    'acao': {'rotulo': 'Só cortar vídeos com legenda', 'cortes': {'so_com_legenda': True}}})

    if h['trocas_para_paga']:
        out.append({'id': 'sem_reserva_paga', 'prioridade': 1, 'feito': not cu.get('reserva', True), 'fonte': f'histórico dos últimos {h["dias"]} dias',
                    'titulo': f'A chave grátis acabou {h["trocas_para_paga"]} vez(es) e a paga entrou no lugar',
                    'texto': 'É aí que o dinheiro sai: quando a cota grátis do dia acaba, a reserva passa o trabalho para a chave com saldo. '
                             'Desligando a reserva, o trabalho espera a cota grátis voltar no dia seguinte em vez de gastar.',
                    'acao': {'rotulo': 'Não usar a chave paga quando a grátis acabar', 'chaves_uso': {'reserva': False}}})

    if cfg['chave_cortes'] == 'paga' and s.get('gemini'):
        out.append({'id': 'chave_gratis', 'prioridade': 1, 'feito': False, 'fonte': 'configuração',
                    'titulo': 'Os cortes estão usando a chave com saldo',
                    'texto': 'Você tem a chave grátis guardada. Usando a grátis para ouvir e escolher os trechos, o gasto em dinheiro dos cortes vai a zero.',
                    'acao': {'rotulo': 'Usar a chave grátis nos cortes', 'chaves_uso': {'cortes': 'gratis', 'camera': 'gratis'}}})

    tot = r['cortes']['feitos'] + r['cortes']['reprovados']
    rep, tot = (r['cortes']['reprovados'], tot) if tot >= 5 else (h['reprovados'], h['cortes'] + h['reprovados'])
    if tot >= 5 and rep / tot >= 0.25:
        out.append({'id': 'reprovados', 'prioridade': 3, 'feito': False, 'fonte': base, 'titulo': f'{round(rep / tot * 100)}% dos cortes foram reprovados pelo diretor',
                    'texto': 'Corte reprovado é análise paga que não vira vídeo. Veja os motivos em Agente 1 e ajuste a duração ou a nota mínima.'})
    if h['videos_com_erro'] >= 3:
        out.append({'id': 'erros', 'prioridade': 3, 'feito': False, 'fonte': f'histórico dos últimos {h["dias"]} dias',
                    'titulo': f'{h["videos_com_erro"]} vídeo(s) deram erro no Agente 1',
                    'texto': 'Quando o erro vem depois de a IA ouvir ou escolher, a análise foi paga e não virou corte. Os motivos estão em Agente 1 > Agora.'})

    res = r['reserva']['trechos']
    if res >= 10:
        out.append({'id': 'reserva_cheia', 'prioridade': 3, 'feito': False, 'fonte': 'banco de trechos', 'titulo': f'{res} trechos guardados esperando para virar corte',
                    'texto': f'Eles saem sem gastar IA para escolher. Com {cfg["por_semana"]} cortes por semana, alguns vão vencer '
                             f'({DIAS_RESERVA} dias). Se quiser postar mais, suba os cortes por semana.',
                    'acao': {'rotulo': f'Subir para {min(ag.LIM_POR_SEMANA, cfg["por_semana"] + 4)} por semana', 'cortes': {'por_semana': min(ag.LIM_POR_SEMANA, cfg['por_semana'] + 4)}}})

    m = r['mes']
    if m['teto'] > 0 and m['reais_pago'] >= 0.8 * m['teto']:
        out.append({'id': 'teto', 'prioridade': 0, 'feito': False, 'fonte': 'contador do mês', 'titulo': f'Já foram {_brl(m["reais_pago"])} dos {_brl(m["teto"])} do teto do mês',
                    'texto': 'Quando chegar no teto a IA para até o mês virar. As sugestões abaixo reduzem o gasto por corte.'})

    if not out and not r['a1']['chamadas'] and not h['analises']:
        out.append({'id': 'sem_dados', 'prioridade': 9, 'feito': False, 'fonte': '', 'titulo': 'Ainda não há cortes nem chamadas neste período',
                    'texto': 'Assim que o Agente 1 cortar um vídeo, os números aparecem aqui.'})
    out.sort(key=lambda x: (x['feito'], x['prioridade']))
    return out


def aplicar(sid: str) -> dict:
    """Aplica a sugestão (só mudanças de configuração previstas acima). sid='todas': aplica todas as que ainda faltam."""
    import agente as ag
    sugs = resumo(30)['sugestoes']
    alvo = [x for x in sugs if x.get('acao') and not x.get('feito')] if sid == 'todas' else [x for x in sugs if x['id'] == sid and x.get('acao')]
    if not alvo:
        raise ValueError('Não há nada para aplicar agora.' if sid == 'todas' else 'Esta sugestão não tem nada para aplicar agora.')
    novo: dict = {'cortes': {}, 'chaves_uso': {}}
    for sug in alvo:
        a = sug['acao']
        novo['cortes'].update({k: v for k, v in (a.get('cortes') or {}).items() if k in ('por_analise', 'por_semana', 'so_com_legenda')})
        novo['chaves_uso'].update({k: v for k, v in (a.get('chaves_uso') or {}).items()
                                   if (k in ('cortes', 'camera') and v in ('gratis', 'paga')) or (k == 'reserva' and isinstance(v, bool))})
    ag.salvar_config({k: v for k, v in novo.items() if v})
    try:
        import coordenador as co
        co.evento(None, None, 'agente7', 'custos', {'acao': 'aplicou', 'sugestoes': [x['id'] for x in alvo]})
    except Exception as e:  # noqa: BLE001
        print('custo_corte: evento', e)
    return {'ok': True, 'aplicadas': [x['titulo'] for x in alvo], 'acao': '; '.join(x['acao']['rotulo'] for x in alvo)}


# ---------------------------------------------------------------- aviso (WhatsApp/e-mail)
def texto_aviso(r: dict) -> str:
    pc = r['por_corte']
    linhas = [f'Últimos {r["dias"]} dias: {max(r["cortes"]["feitos"], r["historico"]["cortes"])} corte(s) feitos, '
              f'{max(r["analises"]["total"], r["historico"]["analises"])} vídeo(s) analisado(s).']
    if pc['tabela'] is not None:
        linhas.append(f'Custo médio da IA por corte: {_brl(pc["pago"])} pago de verdade (chave paga) — {_brl(pc["tabela"])} pelo preço de tabela.')
    if r['analises']['cortes_por_analise'] is not None:
        linhas.append(f'Cada análise rendeu em média {str(r["analises"]["cortes_por_analise"]).replace(".", ",")} corte(s).')
    if r['reserva']['trechos']:
        linhas.append(f'Guardados para os próximos cortes (sem gastar IA): {r["reserva"]["trechos"]} trecho(s).')
    h = r['historico']
    if pc['tabela'] is None and h['analises']:
        linhas.append(f'Histórico: {h["analises"]} vídeo(s) viraram {h["cortes"]} corte(s) ({str(h["cortes_por_analise"]).replace(".", ",")} por vídeo); '
                      f'{h["ouvidos_pela_ia"]} precisaram da IA para ouvir o áudio.')
        if h['por_corte_contador'] is not None:
            linhas.append(f'Pelo contador da chave paga: {_brl(h["reais_pago_meses"])} → cerca de {_brl(h["por_corte_contador"])} por corte.')
    sug = [s for s in r['sugestoes'] if s['id'] != 'sem_dados' and not s.get('feito')][:3]
    if sug:
        linhas.append('')
        linhas += [f'Sugestão: {s["titulo"]}.' for s in sug]
    linhas.append('\nValores estimados (tokens reais × preço de tabela). Detalhes em Coordenador > Custos.')
    return '\n'.join(linhas)


def enviar_aviso(dias: int = 7) -> dict:
    import agente as ag
    r = resumo(dias)
    corpo = texto_aviso(r)
    import os
    link = os.getenv('SITE', 'https://raniere3000-tech.github.io/ia/').rstrip('/') + '/#coordenador/custos'
    ag.avisar('custos', 'Custo por corte da semana', corpo + (f'\n\n{link}' if link else ''),
              zap='*EstúdioClip — Custo por corte*\n\n' + corpo + (f'\n\n{link}' if link else ''), zap_tipo='a7_custos')
    return {'ok': True, 'texto': corpo}
