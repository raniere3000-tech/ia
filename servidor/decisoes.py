"""O que espera a SUA decisão: uma lista só, para a faixa vermelha que aparece no topo de todas as telas do site.

Pedido do Raniere (22/11): "um alerta bem chamativo para as tarefas que dependem da minha decisão".

Regras:
- listar é só leitura; remover tira apenas o aviso, sem aprovar ou publicar;
- cada item diz o que é, de quem veio, desde quando espera e para onde o botão leva (aba/extra/área do site);
- "urgente" = algo está PARADO esperando você (vídeo, roteiro, plano, liberação, post barrado);
  "quando puder" = decisão que não trava nada agora (canais sugeridos, rascunho de pedido, Kwai para postar à mão);
- uma fonte com problema não derruba as outras (fica de fora e o resto aparece).
"""
from __future__ import annotations

import hashlib
import json
import time

import banco as db

DIAS_THUMB = 14          # capa parada há mais que isso não vira alarme (pedido velho esquecido)
DIAS_RASCUNHO = 3        # pedido incompleto ao Coordenador só aparece por 3 dias


def _seguro(f, padrao=None):
    try:
        return f()
    except Exception:  # noqa: BLE001 — uma fonte com problema não derruba a faixa
        return padrao


def _j(txt, padrao):
    try:
        return json.loads(txt) if txt else padrao
    except (TypeError, ValueError):
        return padrao


def _item(chave: str, tipo: str, titulo: str, detalhe: str, desde, ir: dict, botao: str, urgente: bool = True, quem: str = '') -> dict:
    item = {'chave': chave, 'tipo': tipo, 'titulo': titulo, 'detalhe': (detalhe or '').strip()[:220], 'desde': float(desde or 0) or None,
            'ir': ir, 'botao': botao, 'urgente': urgente, 'quem': quem}
    item['versao'] = hashlib.sha256(json.dumps(item, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return item


# ---------------------------------------------------------------- cada fonte
def _agente3(cobertos: set) -> list:
    """Vídeos prontos e roteiros do Agente 3 esperando você (mesma lista da tela Aprovações)."""
    import aprovacoes as apv
    out = []
    for p in apv.pendentes():
        if p['status'] == 'changes_requested':
            continue            # você já pediu correção: agora é a vez do agente
        cobertos.add(('projeto', p['projeto']))
        video = p['tipo'] == 'video'
        out.append(_item('a3:' + p['projeto'], 'video' if video else 'roteiro',
                         'Aprovar vídeo' if video else 'Aprovar roteiro', p.get('titulo') or p['ref'], p.get('atualizado'),
                         {'aba': 'revisar', 'extra': p['projeto'], 'area': 'agentes'}, 'Assistir e decidir' if video else 'Ler roteiro', quem='Agente 3'))
    return out


def _liberacoes(cobertos: set) -> list:
    """Pacotes finais que o Coordenador montou e só saem com a sua liberação."""
    out = []
    for a in db.todos("SELECT id, tarefa_id, ordem_id, referencia, relatorio, criado FROM coordenador_aprovacoes "
                      "WHERE decisao='pendente' AND revogado IS NULL ORDER BY criado DESC LIMIT 50"):
        rel = _j(a.get('relatorio'), {}) or {}
        if a.get('tarefa_id'):
            cobertos.add(('tarefa', a['tarefa_id']))
        titulo = rel.get('titulo') if isinstance(rel, dict) else ''
        out.append(_item('lib:' + a['id'], 'liberacao', 'Liberar pacote para postar', titulo or a.get('referencia') or 'Pacote do Coordenador',
                         a.get('criado'), {'aba': 'coordenador', 'extra': 'aprovacoes', 'area': 'agentes'}, 'Conferir e liberar', quem='Coordenador'))
    return out


def _planos() -> list:
    """Pedidos ao Coordenador: plano pronto esperando você confirmar (urgente) ou faltando informação (quando puder)."""
    out = []
    lim = time.time() - DIAS_RASCUNHO * 86400
    for o in db.todos("SELECT id, texto, status, atualizado FROM coordenador_ordens WHERE status IN ('aguardando_confirmacao','rascunho') "
                      'ORDER BY atualizado DESC LIMIT 30'):
        conf = o['status'] == 'aguardando_confirmacao'
        if not conf and float(o['atualizado'] or 0) < lim:
            continue
        out.append(_item('ord:' + o['id'], 'plano', 'Confirmar plano do Coordenador' if conf else 'Completar pedido ao Coordenador',
                         (o.get('texto') or '')[:160], o.get('atualizado'), {'aba': 'coordenador', 'extra': 'ordens:' + o['id'], 'area': 'agentes'},
                         'Ver plano' if conf else 'Completar', urgente=conf, quem='Coordenador'))
    return out


def _tarefas_paradas(cobertos: set) -> list:
    """Etapas de um pedido do Coordenador paradas em "esperando você" que não aparecem em outro item."""
    out = []
    for t in db.todos("SELECT id, ordem_id, agente, acao, resultado_json, erro, atualizado FROM coordenador_tarefas WHERE estado='aguardando_voce' "
                      'ORDER BY atualizado DESC LIMIT 50'):
        res = _j(t.get('resultado_json'), {}) or {}
        if ('tarefa', t['id']) in cobertos or ('projeto', res.get('projeto')) in cobertos or ('thumb', res.get('thumb')) in cobertos:
            continue
        out.append(_item('tar:' + t['id'], 'tarefa', 'Pedido do Coordenador parado esperando você', t.get('erro') or t['acao'], t.get('atualizado'),
                         {'aba': 'coordenador', 'extra': 'ordens:' + t['ordem_id'], 'area': 'agentes'}, 'Abrir pedido', quem='Coordenador'))
    return out


def _esteira() -> list:
    """Vídeos da esteira dos 7 agentes que o diretor mandou para a sua revisão manual."""
    out = []
    for r in db.todos("SELECT id, titulo, ref, atualizado FROM pipeline_runs WHERE estado='manual_review_required' ORDER BY atualizado DESC LIMIT 50"):
        out.append(_item('run:' + r['id'], 'esteira', 'Revisar vídeo na esteira', r.get('titulo') or r.get('ref') or '', r.get('atualizado'),
                         {'aba': 'agente', 'extra': 'esteira', 'area': 'agentes'}, 'Revisar', quem='Diretor (Agente 4)'))
    return out


def _cortes_barrados() -> list:
    """Cortes que voltaram ao editor o máximo de vezes e o diretor ainda não aprovou: só você destrava."""
    import agente as ag
    out = []
    for c in ag.sem_certificado():
        if not c.get('esperando_voce'):
            continue
        motivo = '; '.join(c.get('motivos') or [])
        out.append(_item('corte:' + c['id'], 'corte', 'Diretor não aprovou o corte', (c.get('titulo') or '') + (f' — {motivo}' if motivo else ''), None,
                         {'aba': 'central', 'extra': 'geral', 'area': 'agentes'}, 'Decidir', quem='Diretor (Agente 4)'))
    return out


def _capas(cobertos: set) -> list:
    """Capas do Agente 6 esperando você escolher (modo supervisionado) ou que nenhuma passou no diretor."""
    import thumbnails as th
    if th.config().get('modo') == 'automatico':
        pend = ('revisao_manual',)
    else:
        pend = ('aguardando_escolha', 'revisao_manual')
    lim = time.time() - DIAS_THUMB * 86400
    out = []
    ph = ','.join('?' * len(pend))
    for j in db.todos(f'SELECT id, titulo, estado, atualizado FROM thumbnail_jobs WHERE estado IN ({ph}) AND atualizado>=? ORDER BY atualizado DESC LIMIT 30', *pend, lim):
        if _seguro(lambda j=j: th.selecao_ativa(j['id'])):
            continue            # você já escolheu uma
        cobertos.add(('thumb', j['id']))
        escolher = j['estado'] == 'aguardando_escolha'
        out.append(_item('capa:' + j['id'], 'capa', 'Escolher a capa' if escolher else 'Nenhuma capa passou: decida',
                         j.get('titulo') or '', j.get('atualizado'), {'aba': 'thumbnails', 'extra': 'galeria:' + j['id'], 'area': 'agentes'},
                         'Escolher' if escolher else 'Ver capas', quem='Agente 6'))
    return out


def _posts() -> list:
    """Posts que não saem sem você: pedem liberação especial, deram erro, ou são do Kwai (postar à mão) e já passou a hora."""
    import postagem as pg
    agora = time.time()
    out = []
    for p in pg.posts():
        redes = p.get('redes') or {}
        lib = [r for r, x in redes.items() if x.get('status') == 'liberacao']
        err = [r for r, x in redes.items() if x.get('status') == 'erro']
        kw = [r for r, x in redes.items() if x.get('status') == 'manual'] if float(p.get('quando') or 0) <= agora else []
        tit = (p.get('titulo') or 'Post sem título')[:100]
        ir = {'aba': 'agendar', 'extra': '', 'area': 'publicacoes'}
        if lib:
            msg = next((redes[r].get('erro') for r in lib if redes[r].get('erro')), '')
            out.append(_item(f'plib:{p["id"]}', 'post', 'Post pede a sua liberação', f'{tit} ({", ".join(lib)})' + (f' — {msg}' if msg else ''),
                             p.get('quando'), ir, 'Ver e liberar', quem='Agente 2'))
        if err:
            msg = next((redes[r].get('erro') for r in err if redes[r].get('erro')), '')
            out.append(_item(f'perr:{p["id"]}', 'post', 'Post travado com erro', f'{tit} ({", ".join(err)})' + (f' — {msg}' if msg else ''),
                             p.get('quando'), ir, 'Ver e tentar de novo', quem='Agente 2'))
        if kw:
            out.append(_item(f'pkw:{p["id"]}', 'kwai', 'Postar no Kwai (à mão)', tit, p.get('quando'), ir, 'Abrir', urgente=False, quem='Agente 2'))
    return out


def _canais() -> list:
    import agente as ag
    sug = [c for c in ag.estado().get('canais', []) if c.get('status') == 'sugerido']
    if not sug:
        return []
    nomes = ', '.join(c.get('nome') or '?' for c in sug[:3]) + ('...' if len(sug) > 3 else '')
    return [_item('canais', 'canal', f'{len(sug)} canal(is) sugerido(s) para aprovar ou recusar', nomes, None,
                  {'aba': 'agente', 'extra': 'cortes', 'area': 'agentes'}, 'Ver canais', urgente=False, quem='Agente 1')]


# ---------------------------------------------------------------- lista final
def listar(incluir_removidos: bool = False) -> dict:
    cobertos: set = set()
    itens: list = []
    falhou: list = []
    # a ordem importa: quem "cobre" um item vem antes de _tarefas_paradas
    fontes = [('agente3', lambda: _agente3(cobertos)), ('liberacoes', lambda: _liberacoes(cobertos)), ('capas', lambda: _capas(cobertos)),
              ('planos', _planos), ('esteira', _esteira), ('cortes', _cortes_barrados), ('posts', _posts),
              ('tarefas', lambda: _tarefas_paradas(cobertos)), ('canais', _canais)]
    for nome, f in fontes:
        r = _seguro(f)
        if r is None:
            falhou.append(nome)
        else:
            itens.extend(r)
    if not incluir_removidos:
        removidos = {r['chave']: r['valor'] for r in db.todos("SELECT chave, valor FROM kv WHERE chave LIKE 'decisao_removida:%'")}
        itens = [x for x in itens if removidos.get('decisao_removida:' + x['chave']) != x['versao']]
    # urgentes primeiro; dentro de cada grupo, o que espera há mais tempo primeiro (sem data vai para o fim)
    itens.sort(key=lambda x: (not x['urgente'], x['desde'] or float('inf')))
    urg = sum(1 for x in itens if x['urgente'])
    return {'itens': itens, 'urgentes': urg, 'depois': len(itens) - urg, 'total': len(itens), 'fontes_com_erro': falhou, 'gerado_em': time.time()}


def contar_urgentes() -> int | None:
    return _seguro(lambda: listar()['urgentes'])


def remover(chave: str, versao: str, quem: str) -> dict:
    """Remove este aviso em todos os aparelhos. Uma nova decisão volta a aparecer."""
    from rotas_esteira import ErroRota
    item = next((x for x in listar(incluir_removidos=True)['itens'] if x['chave'] == chave), None)
    if item is None:
        raise ErroRota(404, 'Este item já não está aguardando decisão. Atualize a lista.')
    if not versao or item['versao'] != versao:
        raise ErroRota(409, 'O item mudou. Atualize a lista antes de removê-lo.')
    db.executar('INSERT INTO kv (chave, valor) VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',
                'decisao_removida:' + chave, versao)
    db.evento(quem, 'decisao_removida', chave, {'versao': versao})
    return listar()
