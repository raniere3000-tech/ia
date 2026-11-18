"""Referências virais do diretor (Agente 4) e do Agente 1: só números medidos, com origem e data.

Duas fontes:
- seus próprios vídeos medidos (painel Aprendizado), sempre disponíveis e sem cota;
- busca pública do YouTube (shorts do tema, mais vistos nos últimos 30 dias), só com a chave do YouTube e dentro da cota.
Sem dados, o conjunto diz "dados insuficientes": nunca inventa número nem tendência.
As referências viram observação no relatório do diretor; NUNCA mudam a nota nem bloqueiam (é só contexto).
Vídeos de referência não são usados como material de edição.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timedelta, timezone

import banco as db

VALIDADE = 24 * 3600         # um conjunto por tema/rede por dia: economiza a cota do YouTube
MIN_ITENS = 5
_ULTIMO_ERRO = {'t': 0.0}


def _mediana(v: list) -> float | None:
    if not v:
        return None
    o = sorted(v)
    n = len(o)
    return o[n // 2] if n % 2 else (o[n // 2 - 1] + o[n // 2]) / 2


def _por_dia(views: int, publicado: str, agora: datetime) -> float | None:
    try:
        p = datetime.strptime(publicado[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    dias = max(1.0, (agora - p).total_seconds() / 86400)
    return round(views / dias, 1)


def _resumo(itens: list, origem: str) -> dict:
    durs = [i['dur'] for i in itens if i.get('dur')]
    vpd = [i['views_dia'] for i in itens if i.get('views_dia') is not None]
    r = {'n': len(itens), 'origem': origem}
    if len(itens) < MIN_ITENS:
        r.update(estado='dados insuficientes', mensagem=f'Só {len(itens)} vídeo(s) com números; preciso de {MIN_ITENS} para comparar.')
        return r
    r.update(estado='ok', duracao_mediana=_mediana(durs), views_dia_mediana=_mediana(vpd),
             duracao_faixa=[min(durs), max(durs)] if durs else None)
    return r


def _proprios(plataforma: str) -> list:
    try:
        import aprendizado as ap
        ret = ap._retratos(plataforma if plataforma in ('youtube', 'instagram', 'tiktok', 'facebook', 'kwai') else '')
    except Exception:  # noqa: BLE001 - sem tabela ou sem dados
        return []
    itens = []
    for x in ret:
        itens.append({'titulo': x.get('item') or '', 'views': x['r'], 'dur': None, 'faixa_duracao': x['v'].get('duracao') or '', 'views_dia': None,
                      'fonte': 'seus vídeos', 'licenca': 'seu'})
    return itens


def _sua_duracao(plataforma: str) -> dict:
    """Faixa de duração que mais rendeu nos SEUS vídeos (painel Aprendizado), com o mesmo critério de amostra mínima."""
    try:
        import aprendizado as ap
        a = ap.analisar('duracao', plataforma if plataforma in ap.REDES else '')
    except Exception:  # noqa: BLE001
        return {'estado': 'dados insuficientes'}
    return {'estado': a.get('estado'), 'mensagem': a.get('mensagem', ''), 'melhor': a.get('melhor')}


def _youtube(tema: str, idioma: str) -> list:
    import agente as ag
    if not ag.segredos().get('youtube'):
        return []
    if time.time() - _ULTIMO_ERRO['t'] < 3600:          # o YouTube recusou há pouco (cota): espera uma hora antes de tentar de novo
        return []
    desde = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    try:
        j = ag.yt('search', part='snippet', q=tema, type='video', order='viewCount', publishedAfter=desde, maxResults=25, videoDuration='short',
                  relevanceLanguage=idioma or 'pt')
        ids = [it['id']['videoId'] for it in j.get('items', []) if it.get('id', {}).get('videoId')]
        det = ag._detalhes(ids) if ids else {}
    except Exception:  # noqa: BLE001 - cota, rede, chave
        _ULTIMO_ERRO['t'] = time.time()
        return []
    agora = datetime.now(timezone.utc)
    return [{'titulo': v['titulo'][:120], 'url': f'https://www.youtube.com/watch?v={v["id"]}', 'views': v['views'], 'dur': v['dur'] or None,
             'views_dia': _por_dia(v['views'], v['publicado'], agora), 'publicado': v['publicado'][:10], 'fonte': 'YouTube (público)',
             'licenca': 'só referência, não usar como material'} for v in det.values()]


def referencias(tema: str = '', plataforma: str = 'youtube', idioma: str = 'pt', forcar: bool = False) -> dict:
    tema = (tema or '').strip()[:80]
    ja = db.um('SELECT * FROM reference_sets WHERE tema=? AND plataforma=? AND idioma=? ORDER BY criado DESC LIMIT 1', tema, plataforma, idioma)
    if ja and not forcar and time.time() - ja['criado'] < VALIDADE:
        return _saida(ja)
    itens, origem = [], []
    if tema and plataforma == 'youtube':
        yt = _youtube(tema, idioma)
        if yt:
            itens += yt
            origem.append('YouTube público')
    prop = _proprios(plataforma)
    if prop:
        itens += prop
        origem.append('seus vídeos medidos')
    resumo = _resumo(itens, ' + '.join(origem) or 'nenhuma')
    resumo['seus_videos_duracao'] = _sua_duracao(plataforma)
    rid = 'ref_' + uuid.uuid4().hex[:10]
    db.executar('INSERT INTO reference_sets (id, tema, plataforma, idioma, itens, origem, resumo, criado) VALUES (?,?,?,?,?,?,?,?)', rid, tema, plataforma, idioma,
                json.dumps(itens[:60], ensure_ascii=False), resumo['origem'], json.dumps(resumo, ensure_ascii=False), time.time())
    return _saida(db.um('SELECT * FROM reference_sets WHERE id=?', rid))


def _saida(r: dict) -> dict:
    resumo = json.loads(r['resumo'] or '{}')
    return {'id': r['id'], 'tema': r['tema'], 'plataforma': r['plataforma'], 'idioma': r['idioma'], 'capturado': r['criado'], 'origem': r['origem'],
            'resumo': resumo, 'itens': json.loads(r['itens'] or '[]')[:30],
            'aviso': 'Referência para decidir a edição; não é previsão de viralização e não muda a nota do diretor.'}


def para_diretor(tema: str, plataforma: str = 'youtube') -> dict:
    """Resumo curto que vai no contexto do diretor (só observação). Nunca levanta erro."""
    try:
        r = referencias(tema, plataforma)
    except Exception:  # noqa: BLE001
        return {}
    s = r['resumo']
    if s.get('estado') != 'ok':
        return {'id': r['id'], 'estado': s.get('estado')}
    return {'id': r['id'], 'estado': 'ok', 'duracao_mediana': s.get('duracao_mediana'), 'origem': r['origem']}
