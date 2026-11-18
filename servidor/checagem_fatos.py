"""Checagem de fatos das pautas: uma afirmação só vira "confirmada" quando um TRECHO LITERAL que a sustenta está no texto da fonte.

Como funciona:
1. Baixa o texto das fontes da pauta (até 3; só https; até 1,5 MB; sem rodar nada da página).
2. A IA aponta, para cada afirmação, a frase da fonte que a sustenta, copiada como está.
3. O SERVIDOR confere se essa frase existe mesmo no texto baixado (comparação com espaços, maiúsculas e acentos normalizados).
   Se a IA "inventar" um trecho, ele não é achado e a afirmação fica NÃO confirmada.

Limites honestos: achar o trecho prova que a fonte DIZ aquilo, não que a fonte está certa. Página que precisa de JavaScript,
login ou bloqueia robôs fica "não deu para ler". Isto não substitui revisão humana em assunto de saúde, dinheiro ou lei.
"""
from __future__ import annotations

import html
import re
import unicodedata
import urllib.error
import urllib.request

MAX_BYTES = 1_500_000
MAX_TEXTO_IA = 6000
RISCO_ALTO = ('saude', 'saúde', 'remedio', 'remédio', 'doenca', 'doença', 'cura', 'vacina', 'dieta', 'dinheiro', 'investimento', 'lei', 'crime',
              'medicamento', 'tratamento', 'cancer', 'câncer', 'gravidez', 'imposto', 'eleicao', 'eleição')


def _norm(t: str) -> str:
    t = unicodedata.normalize('NFKD', str(t).lower())
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r'[“”"«»‘’\']', '', t)
    return re.sub(r'\s+', ' ', re.sub(r'[^\w%.,;:()-]+', ' ', t)).strip()


def texto_da_pagina(bruto: bytes, tipo: str = '') -> str:
    s = bruto.decode('utf-8', errors='replace')
    if 'html' in tipo or '<html' in s[:2000].lower() or '<p' in s[:5000].lower():
        s = re.sub(r'(?is)<(script|style|noscript|svg|nav|footer|header)\b.*?</\1>', ' ', s)
        s = re.sub(r'(?s)<!--.*?-->', ' ', s)
        s = re.sub(r'(?i)<br\s*/?>|</p>|</li>|</h\d>', '\n', s)
        s = re.sub(r'(?s)<[^>]+>', ' ', s)
        s = html.unescape(s)
    return re.sub(r'[ \t\r\f\v]+', ' ', s).strip()


def baixar(url: str, tempo: float = 10) -> dict:
    """{'ok': bool, 'texto': str, 'motivo': str}. Nunca levanta exceção."""
    if not re.fullmatch(r'https://[\w.-]+\.[a-z]{2,}(/\S*)?', url or ''):
        return {'ok': False, 'texto': '', 'motivo': 'link inválido'}
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; conferencia-de-fontes)', 'Accept': 'text/html,text/plain'})
    try:
        with urllib.request.urlopen(req, timeout=tempo) as r:
            tipo = r.headers.get('Content-Type', '')
            if not any(x in tipo for x in ('html', 'text', 'xml')):
                return {'ok': False, 'texto': '', 'motivo': f'não é página de texto ({tipo[:40]})'}
            bruto = r.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        return {'ok': False, 'texto': '', 'motivo': f'a página respondeu {e.code}'}
    except Exception as e:  # noqa: BLE001
        return {'ok': False, 'texto': '', 'motivo': 'não abriu: ' + str(e)[:80]}
    txt = texto_da_pagina(bruto[:MAX_BYTES], tipo)
    if len(txt) < 200:
        return {'ok': False, 'texto': txt, 'motivo': 'quase sem texto (página pode precisar de JavaScript ou login)'}
    return {'ok': True, 'texto': txt, 'motivo': ''}


def risco(p: dict) -> str:
    t = _norm(' '.join([p.get('titulo', ''), p.get('resumo', ''), p.get('subtema', '')] + list(p.get('afirmacoes') or [])))
    return 'alto' if any(_norm(x) in t for x in RISCO_ALTO) else 'normal'


def _prompt(afirmacoes: list, textos: list) -> str:
    fontes = '\n\n'.join(f'[FONTE {i + 1}] {t[:MAX_TEXTO_IA]}' for i, t in enumerate(textos))
    lista = '\n'.join(f'{i + 1}. {a}' for i, a in enumerate(afirmacoes))
    return ('Você confere afirmações contra textos de fontes. Para cada afirmação, copie EXATAMENTE (letra por letra, sem resumir) '
            'a frase de uma das fontes que a sustenta. Se nenhuma fonte sustenta, use trecho vazio. Não use conhecimento próprio.\n\n'
            f'AFIRMAÇÕES:\n{lista}\n\nTEXTOS DAS FONTES:\n{fontes}\n\n'
            'Responda JSON: {"itens": [{"n": 1, "fonte": 1, "trecho": "frase copiada da fonte"}]}')


def conferir(p: dict, ia, buscar=baixar) -> dict:
    """Devolve a pauta com 'conferencia' (por afirmação), 'verificacao' e 'risco'. ia(prompt) -> dict; buscar(url) -> {'ok','texto','motivo'}."""
    p = dict(p)
    p['risco'] = risco(p)
    afirm = [a for a in (p.get('afirmacoes') or []) if a][:4]
    lidas = []
    for f in p.get('fontes') or []:
        b = buscar(f['url'])
        f['abre'] = bool(b['ok'])
        f['leitura'] = 'texto lido' if b['ok'] else b['motivo']
        if b['ok']:
            lidas.append((f, b['texto']))
    if not afirm:
        p['conferencia'] = []
        p['verificacao'] = 'sem afirmações para conferir' if lidas else 'não verificado'
        return p
    if not lidas:
        p['conferencia'] = [{'afirmacao': a, 'ok': False, 'trecho': '', 'fonte': '', 'motivo': 'nenhuma fonte pôde ser lida'} for a in afirm]
        p['verificacao'] = 'não verificado'
        return p
    try:
        r = ia(_prompt(afirm, [t for _, t in lidas])) or {}
    except Exception as e:  # noqa: BLE001
        p['conferencia'] = [{'afirmacao': a, 'ok': False, 'trecho': '', 'fonte': '', 'motivo': 'a IA não respondeu: ' + str(e)[:60]} for a in afirm]
        p['verificacao'] = 'não verificado'
        return p
    por_n = {int(x.get('n') or 0): x for x in (r.get('itens') or []) if isinstance(x, dict) and str(x.get('n') or '').isdigit()}
    conf = []
    for i, a in enumerate(afirm, 1):
        x = por_n.get(i) or {}
        trecho = str(x.get('trecho') or '').strip()[:400]
        try:
            k = int(x.get('fonte') or 0) - 1
        except (TypeError, ValueError):
            k = -1
        ok = False
        url = ''
        if len(_norm(trecho)) >= 20:
            alvo = [lidas[k]] if 0 <= k < len(lidas) else lidas
            for f, t in alvo:                       # o servidor procura o trecho no texto real: a palavra da IA não basta
                if _norm(trecho) in _norm(t):
                    ok, url = True, f['url']
                    break
        conf.append({'afirmacao': a, 'ok': ok, 'trecho': trecho if ok else '', 'fonte': url,
                     'motivo': '' if ok else ('o trecho citado não está na fonte' if trecho else 'nenhuma fonte sustenta')})
    p['conferencia'] = conf
    n_ok = sum(c['ok'] for c in conf)
    p['verificacao'] = 'conferida (trecho achado na fonte)' if n_ok == len(conf) else ('parcial' if n_ok else 'não verificado')
    return p


def pode_aceitar_sozinha(p: dict) -> bool:
    """Modo automático: fato de risco alto só com tudo conferido; fato comum precisa de pelo menos parte conferida."""
    if p.get('classificacao') != 'fato':
        return True
    if p.get('risco') == 'alto':
        return p.get('verificacao', '').startswith('conferida')
    return p.get('verificacao', '') not in ('não verificado', '')
