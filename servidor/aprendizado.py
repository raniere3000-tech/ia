"""Aprendizado dos agentes: o que as redes mostraram, guardado sem edição, e o que dá para tirar disso com honestidade.

Regras deste módulo (o documento de 17/11 e o seu pedido de sempre):
- Só entra número que veio de uma rede (lido pelo servidor) ou que VOCÊ importou (CSV/JSON). Nada é inventado.
- Cada medida vira um "retrato" (snapshot) com fonte, rede e período. Retrato não se edita; só se apaga, e apagar tira o efeito dele.
- Sem amostra mínima, a resposta é "dados insuficientes". Nunca há tendência com poucos vídeos.
- Mostra o que aconteceu junto, nunca o motivo ("correlação não é causa"). Nenhum texto daqui diz "causou".
- Teste A/B muda UMA variável por vez; as outras ficam fixas, e só um teste ativo por vez.
- Pesos aprendidos têm versão e botão de desfazer. Só valem onde já existe um sorteio (estilo visual); o resto é só leitura.
- Este módulo NUNCA mexe na frequência de postagem (limites e horários são seus), nem posta, nem aprova nada.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import time
import uuid
from datetime import datetime, timezone

import banco as db
import modelos as mo

VARIAVEIS = {'estilo': 'Estilo visual', 'modelo': 'Template', 'faixa': 'Dia e hora', 'duracao': 'Duração', 'gancho': 'Tipo de gancho', 'formato': 'Formato', 'perfil': 'Perfil',
             'arranjo': 'Tela dividida (comparação)'}
APLICAVEIS = ('estilo',)                 # onde já existe um sorteio que pode usar os pesos; o template tem os pesos próprios do Agente 1
REDES = ('youtube', 'instagram', 'facebook', 'kwai', 'tiktok')
MIN_AMOSTRAS = 5                         # vídeos medidos por valor antes de dizer qualquer coisa
DIFERENCA_CLARA = 0.2                    # o melhor precisa passar o segundo em 20% para se chamar tendência
FORCA = 0.5                              # até onde o peso anda em direção ao resultado (0 = ignora os dados, 1 = só o resultado)
MAX_LINHAS, MAX_BYTES = 2000, 1_000_000
AVISO_CAUSA = 'Isto mostra o que aconteceu junto, não o motivo. Pode ser outra coisa (assunto, horário, sorte). Use para testar, não como regra.'
FREQUENCIA = 'Nada aqui muda quantos posts saem por dia nem os horários: isso continua sendo só seu.'


class ErroAprendizado(Exception):
    def __init__(self, msg: str, codigo: int = 400):
        super().__init__(msg)
        self.codigo = codigo


# ---------------------------------------------------------------- normalizar variáveis e métricas
def _txt(v, n=60) -> str:
    return re.sub(r'\s+', ' ', str(v or '')).strip()[:n]


def faixa_duracao(seg) -> str:
    try:
        s = float(seg)
    except (TypeError, ValueError):
        return ''
    return 'até 30 s' if s <= 30 else '30 a 60 s' if s <= 60 else '60 a 90 s' if s <= 90 else 'mais de 90 s'


def tipo_gancho(texto: str) -> str:
    t = _txt(texto, 300)
    if not t:
        return ''
    if '?' in t:
        return 'pergunta'
    if re.search(r'\d', t):
        return 'número'
    if re.match(r'^[“"\']', t):
        return 'citação'
    if re.search(r'\b(nunca|ninguém|segredo|erro|verdade|cuidado)\b', t, re.I):
        return 'alerta ou segredo'
    return 'afirmação'


def _num(v):
    if v is None or str(v).strip() == '':
        return None
    try:
        x = float(str(v).strip().replace('.', '').replace(',', '.') if re.fullmatch(r'\d{1,3}(\.\d{3})+(,\d+)?', str(v).strip()) else str(v).strip().replace(',', '.'))
    except ValueError:
        raise ValueError(f'"{_txt(v, 20)}" não é número')
    if x < 0 or not math.isfinite(x):
        raise ValueError('número negativo ou inválido')
    return int(x)


def resultado(m: dict):
    """Número usado para comparar: visualizações; sem elas, curtidas mais comentários (o mesmo critério do Agente 1)."""
    if m.get('views') is not None:
        return m['views']
    if m.get('curtidas') is not None:
        return m['curtidas'] + (m.get('comentarios') or 0)
    return None


def _data(v):
    if v is None or str(v).strip() == '':
        return None
    s = str(v).strip()
    try:
        if re.fullmatch(r'\d{9,11}(\.\d+)?', s):
            return float(s)
        d = datetime.fromisoformat(s[:19].replace('/', '-')) if re.match(r'\d{4}[-/]\d', s) else datetime.strptime(s[:10], '%d/%m/%Y')
        return d.replace(tzinfo=d.tzinfo or timezone.utc).timestamp()
    except ValueError:
        raise ValueError(f'data "{_txt(s, 20)}" não entendida (use AAAA-MM-DD)')


def _hash(d: dict) -> str:
    return hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _gravar_retrato(fonte: str, rede: str, item: str, variaveis: dict, metricas: dict, ini, fim, imp: str = '', publicacao: dict | None = None) -> bool:
    variaveis = {k: _txt(v) for k, v in variaveis.items() if k in VARIAVEIS and _txt(v)}
    if publicacao:
        variaveis['_publicacao'] = json.loads(json.dumps(publicacao))
    metricas = metricas_validas(metricas)
    if not metricas:
        return False
    base = {'fonte': fonte, 'rede': rede, 'item': item, 'v': variaveis, 'm': metricas, 'ini': ini, 'fim': fim}
    h = _hash(base)
    if db.um('SELECT 1 FROM aprendizado_snapshots WHERE hash=?', h):
        return False                                  # o mesmo retrato não entra duas vezes
    db.executar('INSERT INTO aprendizado_snapshots (id, t, fonte, rede, periodo_ini, periodo_fim, item, variaveis, metricas, hash, importacao_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                uuid.uuid4().hex[:12], time.time(), fonte, rede, ini, fim, item[:80], json.dumps(variaveis, ensure_ascii=False), json.dumps(metricas), h, imp or None)
    return True


# ---------------------------------------------------------------- entrada 1: o que o servidor leu das redes
def metricas_validas(m: dict) -> dict:
    out = {}
    for k in ('views', 'curtidas', 'comentarios', 'compartilhamentos'):
        try:
            n = _num(m.get(k))
        except (ValueError, TypeError, OverflowError):
            n = None
        if n is not None:
            out[k] = n
    return out


def variaveis_do_corte(c: dict) -> dict:
    ini, fim = c.get('ini'), c.get('fim')
    return {'estilo': c.get('estilo_visual') or '', 'modelo': c.get('modelo_nome') or c.get('modelo') or '', 'faixa': c.get('faixa') or '',
            'duracao': faixa_duracao((fim - ini) if isinstance(ini, (int, float)) and isinstance(fim, (int, float)) else None),
            'gancho': tipo_gancho(c.get('gancho') or ''), 'formato': c.get('formato') or '', 'perfil': c.get('perfil_nome') or c.get('perfil') or '',
            'arranjo': {'empilhado': 'Um em cima do outro', 'lado': 'Lado a lado'}.get(c.get('arranjo') or '', '')}


def capturar(publicacoes: list | None = None) -> dict:
    """Guarda um retrato de cada corte já medido numa rede (idempotente). Só números que a rede entregou."""
    import agente as ag
    novos = 0
    representados = set()
    posts = {p['id']: p for p in publicacoes or []}
    for c in ag.estado()['cortes']:
        if not c.get('medido') or not c.get('metricas'):
            continue
        fim = c.get('postado') or c.get('criado') or 0
        for rede, m in c['metricas'].items():
            if rede in REDES and isinstance(m, dict) and resultado(metricas_validas(m)) is not None:
                destino = ((posts.get(c.get('post')) or {}).get('redes') or {}).get(rede) or {}
                novos += _gravar_retrato('rede', rede, c.get('id', ''), variaveis_do_corte(c), m, fim, c.get('metricas_em') or fim, publicacao=destino.get('publicacao'))
                if c.get('post'):
                    representados.add((c['post'], rede))
    if os.getenv('METRICAS_PUBLICACOES', '0') == '1':
        for p in publicacoes or []:
            if not p.get('medido') or not isinstance(p.get('metricas'), dict):
                continue
            for rede, m in p['metricas'].items():
                destino = (p.get('redes') or {}).get(rede) or {}
                if (rede not in REDES or destino.get('status') != 'postado' or not isinstance(m, dict)
                        or (p['id'], rede) in representados):
                    continue
                inicio = destino.get('feito') or p.get('quando')
                novos += _gravar_retrato('rede', rede, 'post:' + p['id'],
                                        {'modelo': p.get('modelo') or ''}, m, inicio, p.get('metricas_em'), publicacao=destino.get('publicacao'))
    if novos:
        db.evento('aprendizado', 'capturar', '', {'novos': novos})
    return {'novos': novos}


# ---------------------------------------------------------------- entrada 2: arquivo que você importa
_ALIAS = {'rede': 'rede', 'network': 'rede', 'plataforma': 'rede', 'id': 'item', 'item': 'item', 'video': 'item', 'titulo': 'item', 'data': 'data', 'date': 'data',
          'views': 'views', 'visualizacoes': 'views', 'visualizações': 'views', 'curtidas': 'curtidas', 'likes': 'curtidas', 'comentarios': 'comentarios',
          'comentários': 'comentarios', 'comments': 'comentarios', 'compartilhamentos': 'compartilhamentos', 'shares': 'compartilhamentos',
          'estilo': 'estilo', 'modelo': 'modelo', 'template': 'modelo', 'faixa': 'faixa', 'horario': 'faixa', 'horário': 'faixa', 'duracao': 'duracao',
          'duração': 'duracao', 'gancho': 'gancho', 'formato': 'formato', 'perfil': 'perfil', 'arranjo': 'arranjo', 'tela dividida': 'arranjo'}


def _linhas(formato: str, conteudo: str) -> list:
    if formato == 'json':
        try:
            j = json.loads(conteudo)
        except ValueError:
            raise ErroAprendizado('O JSON não pôde ser lido. Confira se é uma lista de objetos.')
        if isinstance(j, dict):
            j = j.get('itens') or j.get('linhas') or j.get('videos') or []
        if not isinstance(j, list) or not all(isinstance(x, dict) for x in j):
            raise ErroAprendizado('O JSON precisa ser uma lista de objetos (um por vídeo).')
        return j
    if formato == 'csv':
        amostra = conteudo[:2000]
        try:
            dial = csv.Sniffer().sniff(amostra, delimiters=',;\t')
        except csv.Error:
            dial = csv.excel
        return list(csv.DictReader(io.StringIO(conteudo), dialect=dial))
    raise ErroAprendizado('Formato precisa ser csv ou json.')


def importar(nome: str, formato: str, conteudo: str) -> dict:
    if not isinstance(conteudo, str) or not conteudo.strip():
        raise ErroAprendizado('O arquivo está vazio.')
    if len(conteudo.encode('utf-8')) > MAX_BYTES:
        raise ErroAprendizado('Arquivo grande demais (máximo 1 MB). Divida em partes.')
    linhas = _linhas(str(formato).lower(), conteudo)
    if not linhas:
        raise ErroAprendizado('Não achei nenhuma linha de dados.')
    if len(linhas) > MAX_LINHAS:
        raise ErroAprendizado(f'Linhas demais (máximo {MAX_LINHAS} por arquivo).')
    imp = uuid.uuid4().hex[:10]
    ok, recusadas, repetidas = 0, [], 0
    for n, cru in enumerate(linhas, start=2 if formato == 'csv' else 1):
        reg = {}
        for k, v in cru.items():
            a = _ALIAS.get(_txt(k, 30).lower())
            if a and v is not None:
                reg[a] = v
        try:
            rede = _txt(reg.get('rede'), 20).lower()
            if rede not in REDES:
                raise ValueError('rede não reconhecida (use ' + ', '.join(REDES) + ')')
            m = {k: _num(reg.get(k)) for k in ('views', 'curtidas', 'comentarios', 'compartilhamentos')}
            if resultado(m) is None:
                raise ValueError('sem visualizações nem curtidas')
            d = _data(reg.get('data'))
            if d is None:
                raise ValueError('sem data (o período é obrigatório)')
            dur = reg.get('duracao')
            var = {'estilo': reg.get('estilo'), 'modelo': reg.get('modelo'), 'faixa': reg.get('faixa'), 'formato': reg.get('formato'), 'perfil': reg.get('perfil'), 'arranjo': reg.get('arranjo'),
                   'duracao': faixa_duracao(dur) if re.fullmatch(r'\d+([.,]\d+)?', _txt(dur, 12).replace(',', '.') or 'x') else _txt(dur),
                   'gancho': tipo_gancho(reg.get('gancho')) if len(_txt(reg.get('gancho'), 300).split()) > 2 else _txt(reg.get('gancho'))}
            if _gravar_retrato('importado', rede, _txt(reg.get('item'), 80) or f'linha {n}', var, m, d, d, imp):
                ok += 1
            else:
                repetidas += 1
        except ValueError as e:
            recusadas.append({'linha': n, 'motivo': str(e)})
    if not ok and repetidas:
        return {'importacao': '', 'aceitas': 0, 'repetidas': repetidas, 'recusadas': recusadas[:20], 'total_recusadas': len(recusadas), 'aviso': 'Todas as linhas já estavam guardadas.'}
    if not ok:
        raise ErroAprendizado('Nenhuma linha foi aceita. Primeiros motivos: ' + '; '.join(f'linha {r["linha"]}: {r["motivo"]}' for r in recusadas[:3]))
    db.executar('INSERT INTO aprendizado_importacoes (id, nome, formato, sha256, linhas, recusadas, t) VALUES (?,?,?,?,?,?,?)',
                imp, _txt(nome, 100) or 'arquivo', formato, hashlib.sha256(conteudo.encode()).hexdigest(), ok, len(recusadas), time.time())
    db.evento('aprendizado', 'importar', 'importacao:' + imp, {'aceitas': ok, 'recusadas': len(recusadas), 'repetidas': repetidas})
    return {'importacao': imp, 'aceitas': ok, 'repetidas': repetidas, 'recusadas': recusadas[:20], 'total_recusadas': len(recusadas)}


# ---------------------------------------------------------------- leitura: o que dá para dizer
def _retratos(rede: str = '') -> list:
    out = []
    for r in db.todos('SELECT * FROM aprendizado_snapshots' + (' WHERE rede=?' if rede else '') + ' ORDER BY t', *([rede] if rede else [])):
        m = json.loads(r['metricas'])
        v = resultado(m)
        if v is not None:
            out.append({'id': r['id'], 'fonte': r['fonte'], 'rede': r['rede'], 'v': json.loads(r['variaveis']), 'r': v, 'importacao': r['importacao_id'], 'item': r['item']})
    return out


def _estat(valores: list) -> dict:
    n = len(valores)
    media = sum(valores) / n
    ordem = sorted(valores)
    med = ordem[n // 2] if n % 2 else (ordem[n // 2 - 1] + ordem[n // 2]) / 2
    dp = math.sqrt(sum((x - media) ** 2 for x in valores) / (n - 1)) if n > 1 else 0.0
    return {'n': n, 'media': round(media, 1), 'mediana': round(med, 1), 'dp': round(dp, 1)}


def analisar(variavel: str, rede: str = '', ret: list | None = None) -> dict:
    if variavel not in VARIAVEIS:
        raise ErroAprendizado('Variável desconhecida.', 404)
    ret = ret if ret is not None else _retratos(rede)
    grupos: dict = {}
    for x in ret:
        val = x['v'].get(variavel)
        if val:
            grupos.setdefault(val, []).append(x['r'])
    valores = [{'valor': k, **_estat(v)} for k, v in grupos.items()]
    suf = [x for x in valores if x['n'] >= MIN_AMOSTRAS]
    out = {'variavel': variavel, 'nome': VARIAVEIS[variavel], 'rede': rede or 'todas', 'minimo': MIN_AMOSTRAS, 'valores': sorted(valores, key=lambda x: -x['media']),
           'aplicavel': variavel in APLICAVEIS, 'aviso': AVISO_CAUSA}
    if len(suf) < 2:
        faltam = max(0, 2 - len(suf))
        out.update(estado='dados insuficientes', mensagem=(f'Preciso de pelo menos {MIN_AMOSTRAS} vídeos medidos em cada um de 2 valores para comparar. '
                                                           f'Hoje {len(suf)} valor(es) chegaram lá.' if valores else 'Ainda não há números medidos com esta informação.'),
                   faltam_valores=faltam)
        return out
    suf.sort(key=lambda x: -x['media'])
    a, b = suf[0], suf[1]
    folga = (a['media'] - b['media']) / a['media'] if a['media'] else 0
    if folga >= DIFERENCA_CLARA:
        out.update(estado='tendência', mensagem=f'"{a["valor"]}" ficou na frente de "{b["valor"]}" ({a["media"]:.0f} contra {b["media"]:.0f} por vídeo). {AVISO_CAUSA}',
                   melhor=a['valor'])
    else:
        out.update(estado='sem diferença clara', mensagem='Os valores com amostra suficiente ficaram parecidos: não dá para apontar um melhor.')
    out['comparaveis'] = [x['valor'] for x in suf]
    return out


def pesos_calculados(variavel: str, rede: str = '') -> dict:
    """Peso de cada valor, calculado do zero com os retratos que existem agora (apagar dados muda o resultado)."""
    an = analisar(variavel, rede)
    if an['estado'] == 'dados insuficientes':
        return {}
    suf = {x['valor']: x['media'] for x in an['valores'] if x['n'] >= MIN_AMOSTRAS}
    alvo = mo.normalizar(suf)
    igual = 1 / len(suf)
    cru = {k: igual + FORCA * (alvo[k] - igual) for k in suf}
    return {k: round(v, 4) for k, v in mo._com_piso(cru).items()}


# ---------------------------------------------------------------- pesos com versão (só onde já existe sorteio)
def _ativo(variavel: str) -> dict | None:
    return db.um('SELECT * FROM aprendizado_pesos WHERE variavel=? AND ativo=1 ORDER BY versao DESC LIMIT 1', variavel)


def pesos_ativos(variavel: str) -> dict:
    r = _ativo(variavel)
    return json.loads(r['pesos_json']) if r else {}


def aplicar(variavel: str, quem: str = 'site') -> dict:
    if variavel not in APLICAVEIS:
        raise ErroAprendizado('Esta variável só é lida: ainda não há sorteio que use pesos dela. Use um teste A/B para decidir.', 409)
    p = pesos_calculados(variavel)
    if not p:
        raise ErroAprendizado(f'Dados insuficientes: preciso de pelo menos {MIN_AMOSTRAS} vídeos medidos em cada um de 2 valores.', 409)
    ant = _ativo(variavel)
    if ant:
        db.executar('UPDATE aprendizado_pesos SET ativo=0 WHERE versao=?', ant['versao'])
    base = {'retratos': len(_retratos()), 'ids': [x['id'] for x in _retratos() if x['v'].get(variavel)][:200]}
    db.executar('INSERT INTO aprendizado_pesos (t, variavel, pesos_json, base_json, motivo, ativo, anterior) VALUES (?,?,?,?,?,1,?)',
                time.time(), variavel, json.dumps(p), json.dumps(base), f'aplicado por {quem}', ant['versao'] if ant else None)
    db.evento('aprendizado', 'pesos_aplicados', 'variavel:' + variavel, {'pesos': p})
    return painel()


def desfazer(variavel: str, quem: str = 'site') -> dict:
    atual = _ativo(variavel)
    if not atual:
        raise ErroAprendizado('Não há pesos aprendidos ligados para desfazer.', 409)
    db.executar('UPDATE aprendizado_pesos SET ativo=0 WHERE versao=?', atual['versao'])
    if atual['anterior']:
        db.executar('UPDATE aprendizado_pesos SET ativo=1 WHERE versao=?', atual['anterior'])
    db.evento('aprendizado', 'pesos_desfeitos', 'variavel:' + variavel, {'versao': atual['versao'], 'voltou_para': atual['anterior']})
    return painel()


def sortear_estilo(ok: list, rnd) -> str:
    """Usado pelo Agente 1: com pesos aprendidos e/ou teste A/B ativo no estilo; senão, sorteio igual (como sempre foi)."""
    ex = experimento_ativo()
    if ex and ex['variavel'] == 'estilo':
        par = [x for x in (ex['a'], ex['b']) if x in ok]
        if par:
            return rnd.choice(par)
    pesos = pesos_ativos('estilo')
    if pesos and len(ok) > 1:
        igual = 1 / len(ok)
        ch = mo._com_piso({i: float(pesos.get(i, igual)) for i in ok})
        return rnd.choices(list(ch), weights=list(ch.values()))[0]
    return rnd.choice(ok)


# ---------------------------------------------------------------- teste A/B (uma variável por vez)
def experimento_ativo() -> dict | None:
    r = db.um("SELECT * FROM aprendizado_experimentos WHERE status='ativo' ORDER BY criado DESC LIMIT 1")
    return _exp(r) if r else None


def _exp(r: dict) -> dict:
    return {'id': r['id'], 'nome': r['nome'], 'variavel': r['variavel'], 'a': r['a'], 'b': r['b'], 'fixos': json.loads(r['fixos_json']), 'min_amostras': r['min_amostras'],
            'status': r['status'], 'criado': r['criado'], 'encerrado': r['encerrado']}


def criar_experimento(d: dict) -> dict:
    var, a, b = str(d.get('variavel', '')), _txt(d.get('a')), _txt(d.get('b'))
    if var not in VARIAVEIS:
        raise ErroAprendizado('Escolha a variável que vai mudar.')
    if not a or not b or a == b:
        raise ErroAprendizado('Informe dois valores diferentes para comparar (A e B).')
    fixos = d.get('fixos') or {}
    if not isinstance(fixos, dict) or var in fixos or any(k not in VARIAVEIS for k in fixos):
        raise ErroAprendizado('Os valores fixos precisam ser de OUTRAS variáveis. Muda uma coisa por vez.')
    fixos = {k: _txt(v) for k, v in fixos.items() if _txt(v)}
    if experimento_ativo():
        raise ErroAprendizado('Já existe um teste ativo. Encerre-o antes: o painel só roda um teste por vez para não misturar causas.', 409)
    mn = max(MIN_AMOSTRAS, min(int(d.get('min_amostras') or MIN_AMOSTRAS), 100))
    eid = uuid.uuid4().hex[:10]
    db.executar('INSERT INTO aprendizado_experimentos (id, nome, variavel, a, b, fixos_json, min_amostras, status, criado) VALUES (?,?,?,?,?,?,?,?,?)',
                eid, _txt(d.get('nome'), 80) or f'{VARIAVEIS[var]}: {a} contra {b}', var, a, b, json.dumps(fixos, ensure_ascii=False), mn, 'ativo', time.time())
    db.evento('aprendizado', 'experimento_criado', 'experimento:' + eid, {'variavel': var, 'a': a, 'b': b, 'fixos': fixos})
    return ler_experimento(eid)


def ler_experimento(eid: str) -> dict:
    r = db.um('SELECT * FROM aprendizado_experimentos WHERE id=?', eid)
    if not r:
        raise ErroAprendizado('Teste não encontrado.', 404)
    ex = _exp(r)
    ret = [x for x in _retratos() if all(x['v'].get(k) == v for k, v in ex['fixos'].items())]
    br = {lado: [x['r'] for x in ret if x['v'].get(ex['variavel']) == ex[lado]] for lado in ('a', 'b')}
    ex['lados'] = {lado: ({'valor': ex[lado], **_estat(v)} if v else {'valor': ex[lado], 'n': 0}) for lado, v in br.items()}
    na, nb = len(br['a']), len(br['b'])
    if min(na, nb) < ex['min_amostras']:
        ex.update(resultado='dados insuficientes', mensagem=f'Faltam vídeos medidos: A tem {na}, B tem {nb}; preciso de {ex["min_amostras"]} em cada.')
    else:
        ea, eb = ex['lados']['a'], ex['lados']['b']
        erro = math.sqrt(ea['dp'] ** 2 / na + eb['dp'] ** 2 / nb) or 1e-9
        t = (ea['media'] - eb['media']) / erro
        if abs(t) < 2:
            ex.update(resultado='inconclusivo', mensagem='A diferença é pequena perto da variação entre os vídeos: não dá para dizer que um é melhor. ' + AVISO_CAUSA)
        else:
            win = 'a' if t > 0 else 'b'
            ex.update(resultado='sinal a favor de ' + win.upper(), mensagem=f'"{ex[win]}" ficou na frente. {AVISO_CAUSA}')
    ex['aviso_frequencia'] = FREQUENCIA
    return ex


def encerrar_experimento(eid: str) -> dict:
    ex = ler_experimento(eid)
    db.executar("UPDATE aprendizado_experimentos SET status='encerrado', encerrado=?, resultado_json=? WHERE id=?", time.time(),
                json.dumps({k: ex.get(k) for k in ('resultado', 'mensagem', 'lados')}, ensure_ascii=False), eid)
    db.evento('aprendizado', 'experimento_encerrado', 'experimento:' + eid, {'resultado': ex.get('resultado')})
    return ler_experimento(eid)


# ---------------------------------------------------------------- apagar dados: o efeito some junto
def apagar(d: dict) -> dict:
    """Apaga retratos (uma importação, os lidos das redes, ou tudo) e refaz os pesos: sem dados suficientes, o peso é desligado."""
    alvo = str(d.get('alvo', ''))
    if alvo == 'tudo':
        n = db.executar('DELETE FROM aprendizado_snapshots')
        db.executar('DELETE FROM aprendizado_importacoes')
    elif alvo == 'importacao':
        imp = str(d.get('id', ''))
        if not db.um('SELECT 1 FROM aprendizado_importacoes WHERE id=?', imp):
            raise ErroAprendizado('Importação não encontrada.', 404)
        n = db.executar('DELETE FROM aprendizado_snapshots WHERE importacao_id=?', imp)
        db.executar('DELETE FROM aprendizado_importacoes WHERE id=?', imp)
    elif alvo == 'rede':
        n = db.executar("DELETE FROM aprendizado_snapshots WHERE fonte='rede'")
    else:
        raise ErroAprendizado('Diga o que apagar: tudo, rede ou importacao.')
    refeitos = []
    for v in APLICAVEIS:
        at = _ativo(v)
        if not at:
            continue
        novo = pesos_calculados(v)
        db.executar('UPDATE aprendizado_pesos SET ativo=0 WHERE versao=?', at['versao'])
        if novo:
            db.executar('INSERT INTO aprendizado_pesos (t, variavel, pesos_json, base_json, motivo, ativo, anterior) VALUES (?,?,?,?,?,1,?)',
                        time.time(), v, json.dumps(novo), json.dumps({'retratos': len(_retratos())}), 'refeito: dados apagados', at['versao'])
            refeitos.append(v)
    ex = experimento_ativo()
    db.evento('aprendizado', 'apagar', alvo, {'retratos': n, 'pesos_refeitos': refeitos})
    return {'apagados': n, 'pesos_refeitos': refeitos, 'pesos_desligados': [v for v in APLICAVEIS if v not in refeitos], 'painel': painel(), 'teste_ativo': bool(ex)}


# ---------------------------------------------------------------- painel
def painel() -> dict:
    import agente as ag
    ret = _retratos()
    fontes: dict = {}
    for r in db.todos('SELECT fonte, rede, COUNT(*) AS n, MIN(periodo_ini) AS a, MAX(periodo_fim) AS b FROM aprendizado_snapshots GROUP BY fonte, rede'):
        fontes[f'{r["fonte"]}:{r["rede"]}'] = {'fonte': r['fonte'], 'rede': r['rede'], 'retratos': r['n'], 'de': r['a'], 'ate': r['b']}
    vars_ = []
    for v in VARIAVEIS:
        an = analisar(v, ret=ret)
        at = _ativo(v)
        an['peso_ativo'] = json.loads(at['pesos_json']) if at else {}
        an['versao_pesos'] = at['versao'] if at else None
        an['pode_desfazer'] = bool(at)
        an['pode_aplicar'] = v in APLICAVEIS and an['estado'] != 'dados insuficientes'
        an['pesos_calculados'] = pesos_calculados(v) if v in APLICAVEIS else {}
        vars_.append(an)
    exps = [ler_experimento(r['id']) for r in db.todos('SELECT id FROM aprendizado_experimentos ORDER BY criado DESC LIMIT 10')]
    apoio = []
    try:
        from skills import roteador
        apoio = roteador.lista_para_voce('agentes.aprendizado', f'painel:{len(ret)}', f'painel lido com {len(ret)} retratos', origem='aprendizado', quantas=6)
    except Exception:  # noqa: BLE001
        pass
    return {'retratos': len(ret), 'minimo': MIN_AMOSTRAS, 'fontes': list(fontes.values()), 'variaveis': vars_, 'experimentos': exps,
            'coleta': ag.inventario_metricas(),
            'importacoes': db.todos('SELECT id, nome, formato, linhas, recusadas, t FROM aprendizado_importacoes ORDER BY t DESC LIMIT 20'),
            'historico_pesos': db.todos('SELECT versao, t, variavel, motivo, ativo FROM aprendizado_pesos ORDER BY versao DESC LIMIT 20'),
            'aviso_causa': AVISO_CAUSA, 'aviso_frequencia': FREQUENCIA, 'boas_praticas': apoio,
            'como_voltar': 'Cada peso aprendido tem versão: "Desfazer" volta ao anterior (ou ao sorteio igual). "Apagar dados" tira o efeito dos números apagados.'}
