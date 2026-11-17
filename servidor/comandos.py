"""Comandos por mensagem (WhatsApp ou outro canal): você escreve do seu jeito, o servidor entende e age.

Exemplos:  "o que tem para aprovar?" · "aprova o VID-AB12CD" · "corrige o VID-AB12CD: narração mais curta na cena 3"
           "agenda o corte 2" · "descarta o corte 1" · "corta este vídeo https://youtu.be/..." · "como está a fila?"

Primeiro tenta entender por regras fixas (rápido, sem gastar IA); se não der, pergunta ao Gemini, que só pode devolver
uma das ações da lista. Tudo que publica (aprovar vídeo, agendar corte) pede um "SIM" de confirmação, que vale 10 minutos
e só para aquele pedido. A ação passa pelas MESMAS regras do site: o diretor de qualidade tem de ter aprovado.
"""
from __future__ import annotations

import json
import re
import time

import agente as ag
import aprovacoes as apv
import postagem as pg
import projetos as pj

ARQ = pg.DADOS / 'comandos.json'
VALIDADE = 600
ACOES = {'pendentes', 'aprovar', 'corrigir', 'rejeitar', 'agendar_corte', 'descartar_corte', 'cortar_link', 'cortar_tema', 'liberar_corte', 'status', 'ajuda'}
PUBLICAM = {'aprovar', 'agendar_corte', 'liberar_corte'}

AJUDA = ('*Comandos do EstúdioClip* (escreva do seu jeito):\n'
         '• *pendentes*: o que espera a sua aprovação\n'
         '• *aprovar VID-XXXXXX*: aprovação final do vídeo (vai para o agente de postagem)\n'
         '• *corrigir VID-XXXXXX o que mudar*: pede correção, o vídeo é refeito\n'
         '• *rejeitar VID-XXXXXX*\n'
         '• *agendar corte 2* / *descartar corte 2* (o número vem da lista de pendentes)\n'
         '• *liberar corte 2*: agenda mesmo com restrições de direitos (você assume)\n'
         '• *cortar <link do YouTube>*: o Agente 1 corta esse vídeo\n'
         '• *cortar sobre <tema>*: o Agente 1 procura um vídeo novo sobre o tema e corta\n'
         '• *status*: como está a fila\n'
         'O que publica pede um SIM para confirmar.')


# ---------------------------------------------------------------- o que espera você
def _videos_pendentes() -> list:
    out = []
    for x in pj.listar('agente3'):
        if x['status'] != 'ready_for_review':
            continue
        p = pj.obter(x['id'])
        r = p['dados'].get('render') or {}
        if r.get('sha') and apv.diretor_ok(p, r['sha'])['aprovado']:
            out.append({'pid': p['id'], 'ref': apv.ref(p['id']), 'titulo': p['titulo'], 'sha': r['sha'], 'dur': r.get('duracao') or 0})
    return out


def _cortes_pendentes() -> list:
    cs = [c for c in ag.estado()['cortes'] if c['status'] == 'pronto']
    return sorted(cs, key=lambda c: c.get('criado', 0))


def _corte_n(n) -> dict:
    cs = _cortes_pendentes()
    try:
        return cs[int(n) - 1]
    except (TypeError, ValueError, IndexError):
        raise ag.ErroAgente(f'Não achei o corte {n}. Mande *pendentes* para ver a lista.') from None


def _video(ref: str) -> dict:
    ref = (ref or '').strip().upper()
    if ref and not ref.startswith('VID-'):
        ref = 'VID-' + ref
    pid = apv.pid_da_ref(ref)
    if not pid:
        vs = _videos_pendentes()
        if not ref and len(vs) == 1:          # "aprova" sem dizer qual, e só há um esperando
            return vs[0]
        raise ag.ErroAgente(f'Não achei o vídeo {ref or "(sem código)"}. Mande *pendentes* para ver os códigos.')
    v = next((x for x in _videos_pendentes() if x['pid'] == pid), None)
    if not v:
        raise ag.ErroAgente(f'O {ref} não está esperando a sua aprovação (ainda em produção, já decidido ou sem aprovação do diretor).')
    return v


def pendentes() -> str:
    vs, cs = _videos_pendentes(), _cortes_pendentes()
    if not vs and not cs:
        return 'Nada esperando a sua aprovação agora.'
    site = apv.SITE
    linhas = []
    if vs:
        linhas.append('*Vídeos (Agente 3), já aprovados pelo diretor:*')
        linhas += [f'• {v["ref"]}: {v["titulo"][:70]} ({v["dur"]:.0f} s)\n  {site}#revisar/{v["pid"]}' for v in vs[:8]]
    if cs:
        linhas.append('*Cortes do Radar, já aprovados pelo diretor:*')
        linhas += [f'• corte {i + 1}: {c["titulo"][:70]} ({c["fim"] - c["ini"]:.0f} s, nota {c["nota"]})' for i, c in enumerate(cs[:10])]
        linhas.append(f'Assista em {site}#agente/fila')
    return '\n'.join(linhas)


def status() -> str:
    e = ag.estado()
    cs = e['cortes']
    n = {s: sum(1 for c in cs if c['status'] == s) for s in ('pronto', 'agendado', 'postado', 'reprovado')}
    em_prod = sum(1 for x in pj.listar('agente3') if x['status'] not in ('ready_for_review', 'approved', 'posted', 'queued_to_publish', 'failed', 'cancelled', 'rejected', 'draft'))
    ultimo = (e.get('log') or [{}])[0].get('texto', '')
    return (f'*Status*\nCortes esperando você: {n["pronto"]} · agendados: {n["agendado"]} · postados: {n["postado"]} · reprovados pelo diretor: {n["reprovado"]}\n'
            f'Vídeos do Agente 3 em produção: {em_prod} · esperando você: {len(_videos_pendentes())}\n'
            + (f'Último registro: {ultimo[:200]}' if ultimo else ''))


# ---------------------------------------------------------------- entender a mensagem
def _regras(t: str) -> dict | None:
    s = t.strip()
    b = s.lower()
    if re.fullmatch(r'(ajuda|help|menu|comandos|\?)', b):
        return {'acao': 'ajuda'}
    if re.fullmatch(r'(pendentes?|lista|o que (tem|falta)[^?]*\??)', b):
        return {'acao': 'pendentes'}
    if re.fullmatch(r'(status|fila|como (est[aá]|t[aá])[^?]*\??)', b):
        return {'acao': 'status'}
    m = re.search(r'https?://\S+', s)
    if m and re.search(r'\b(cort|corta|cortar|clip)', b):
        return {'acao': 'cortar_link', 'link': m.group(0)}
    m = re.match(r'(?:cort\w*|busc\w*|procur\w*|ach\w*)\s+(?:um\s+|o\s+)?(?:v[ií]deos?\s+)?(?:sobre|de|do|da|com)\s+(.{3,80}?)(?:\s+(?:pra|para)\s+mim)?[.!]?$', b)
    if m:
        return {'acao': 'cortar_tema', 'tema': s[m.start(1):m.end(1)].strip()}
    ref = re.search(r'VID-([A-Z0-9]{6})\b', s.upper())
    rf = ('VID-' + ref.group(1)) if ref else ''
    resto = re.split(r'VID-[A-Z0-9]{6}[\s:,.-]*', s, maxsplit=1, flags=re.I)
    resto = resto[1].strip() if len(resto) > 1 else ''
    if re.match(r'(aprov|aprova|aprovar|aprovo|pode postar|manda postar)', b) and rf:
        return {'acao': 'aprovar', 'ref': rf}
    if re.match(r'(corrig|alter|muda|refaz)', b) and rf:
        return {'acao': 'corrigir', 'ref': rf, 'texto': resto}
    if re.match(r'(rejeit|recus|reprov)', b) and rf:
        return {'acao': 'rejeitar', 'ref': rf, 'texto': resto}
    m = re.match(r'(?:libera\w*|for[cç]a\w*)(?:\s+e\s+(?:agend|post)\w*)?\s+(?:o\s+)?corte\s*(\d+)', b)
    if m:
        return {'acao': 'liberar_corte', 'n': int(m.group(1))}
    m = re.match(r'(agend|aprov|post)\w*\s+(?:o\s+)?corte\s*(\d+)', b)
    if m:
        return {'acao': 'agendar_corte', 'n': int(m.group(2))}
    m = re.match(r'(descart|apag|remov|joga fora)\w*\s+(?:o\s+)?corte\s*(\d+)', b)
    if m:
        return {'acao': 'descartar_corte', 'n': int(m.group(2))}
    return None


def _ia(t: str) -> dict:
    vs = [{'ref': v['ref'], 'titulo': v['titulo'][:80]} for v in _videos_pendentes()][:8]
    cs = [{'n': i + 1, 'titulo': c['titulo'][:80]} for i, c in enumerate(_cortes_pendentes()[:10])]
    pedido = ('Você traduz a mensagem do dono de um estúdio de vídeos em UMA ação. Ações possíveis: '
              'pendentes, status, ajuda, aprovar (campo ref), corrigir (ref e texto com o que mudar), rejeitar (ref e texto), '
              'agendar_corte (n), liberar_corte (n; agendar mesmo com restrições), descartar_corte (n), cortar_link (link), cortar_tema (tema). Se a mensagem não pedir nenhuma delas, use "nada" e '
              'explique em "resposta" (curta, português simples). Nunca invente ref, n ou link que não estejam na mensagem ou nas listas.\n'
              f'Vídeos esperando aprovação: {json.dumps(vs, ensure_ascii=False)}\nCortes esperando aprovação: {json.dumps(cs, ensure_ascii=False)}\n'
              f'Mensagem: {t[:800]}\nResponda só JSON: {{"acao": "...", "ref": "", "n": 0, "texto": "", "link": "", "resposta": ""}}')
    r = ag.gemini([{'text': pedido}], uso='roteiro', tempo=60)
    return r if isinstance(r, dict) else {}


def entender(t: str) -> dict:
    r = _regras(t)
    if r:
        return r
    try:
        r = _ia(t)
    except ag.ErroAgente as e:
        return {'acao': 'nada', 'resposta': f'Não entendi e a IA não respondeu agora ({e}). Mande *ajuda* para ver os comandos.'}
    if r.get('acao') not in ACOES:
        return {'acao': 'nada', 'resposta': str(r.get('resposta') or 'Não entendi. Mande *ajuda* para ver os comandos.')[:500]}
    return r


# ---------------------------------------------------------------- confirmação e execução
def _pendente(por: str) -> dict | None:
    d = pg._ler(ARQ, {}).get(por)
    return d if d and time.time() - d.get('t', 0) < VALIDADE else None


def _guardar(por: str, pedido: dict | None):
    def _f():
        d = pg._ler(ARQ, {})
        if pedido is None:
            d.pop(por, None)
        else:
            d[por] = dict(pedido, t=time.time())
        pg._gravar(ARQ, d)
    with ag.LOCK:
        _f()


def _descrever(p: dict) -> str:
    if p['acao'] == 'aprovar':
        return f'dar a aprovação final ao {p["ref"]} "{p["titulo"][:60]}" e mandar para o agente de postagem'
    if p['acao'] == 'liberar_corte':
        return f'LIBERAR e agendar o corte {p["n"]} "{p["titulo"][:60]}" mesmo com estas restrições: ' + ' '.join(p.get('restricoes') or [])[:400]
    return f'aprovar e agendar o corte {p["n"]} "{p["titulo"][:60]}" nas redes'


def executar(p: dict, por: str, confirmado: bool = False) -> str:
    a = p.get('acao')
    if a == 'ajuda':
        return AJUDA
    if a == 'pendentes':
        return pendentes()
    if a == 'status':
        return status()
    if a == 'nada':
        return p.get('resposta') or 'Não entendi. Mande *ajuda*.'
    if a == 'cortar_link':
        link = str(p.get('link') or '')
        ag.rodar_agora('link', link)
        return 'Certo! Mandei o Agente 1 cortar esse vídeo. Aviso quando os cortes passarem pelo diretor de qualidade.'
    if a == 'cortar_tema':
        tema = str(p.get('tema') or '').strip()
        ag.rodar_agora('tema', tema)
        return f'Certo! O Agente 1 vai procurar um vídeo novo sobre "{tema[:60]}", cortar e passar pelo diretor de qualidade. Aviso quando estiver pronto.'
    if a in ('aprovar', 'corrigir', 'rejeitar'):
        v = _video(str(p.get('ref') or ''))
        if a == 'corrigir':
            texto = str(p.get('texto') or '').strip()
            if len(texto) < 3:
                return f'O que é para mudar no {v["ref"]}? Mande assim: corrigir {v["ref"]} deixe a narração mais curta na cena 3'
            apv.pedir_alteracao(v['pid'], v['sha'], texto[:2000], 'whatsapp', por)
            return f'Pedido de correção registrado no {v["ref"]}: "{texto[:200]}". O vídeo volta para produção e passa de novo pelo diretor.'
        if a == 'rejeitar':
            apv.rejeitar(v['pid'], v['sha'], str(p.get('texto') or '')[:500], 'whatsapp', por)
            return f'{v["ref"]} rejeitado. Nada será publicado.'
        p = {'acao': 'aprovar', 'ref': v['ref'], 'pid': v['pid'], 'sha': v['sha'], 'titulo': v['titulo']}
        if not confirmado:
            _guardar(por, p)
            return f'Confirma {_descrever(p)}? Responda *SIM* em até 10 minutos.'
        r = apv.aprovar(v['pid'], v['sha'], None, 'whatsapp', por, chave=f'zap:{v["pid"]}:{v["sha"][:16]}')
        quando = r.get('quando')
        return (f'✅ {v["ref"]} aprovado por você e enviado ao agente de postagem'
                + (f' ({len(r.get("posts") or [])} post(s) na fila).' if r.get('posts') else '.') + (f' Quando: {quando}.' if quando else ''))
    if a == 'liberar_corte':
        c = _corte_n(p.get('n'))
        conf = ag.conferir(c)
        if not conf['bloqueios']:
            return f'O corte {p["n"]} não tem restrição. Use: agendar corte {p["n"]}.'
        if not conf['liberavel']:
            return 'Esse corte tem problema técnico ou já saiu igual, e isso não dá para liberar: ' + ' '.join(conf['bloqueios'])[:300]
        _guardar(por, {'acao': 'liberar_corte', 'n': p.get('n'), 'id': c['id'], 'titulo': c['titulo'], 'restricoes': conf['liberaveis']})
        return f'Confirma {_descrever({"acao": "liberar_corte", "n": p.get("n"), "titulo": c["titulo"], "restricoes": conf["liberaveis"]})}? A responsabilidade é sua. Responda *SIM* em até 10 minutos.'
    if a in ('agendar_corte', 'descartar_corte'):
        c = _corte_n(p.get('n'))
        if a == 'descartar_corte':
            ag.acao_corte(c['id'], 'descartar')
            return f'Corte "{c["titulo"][:60]}" descartado.'
        p = {'acao': 'agendar_corte', 'n': p.get('n'), 'id': c['id'], 'titulo': c['titulo']}
        if not confirmado:
            _guardar(por, p)
            return f'Confirma {_descrever(p)}? Responda *SIM* em até 10 minutos.'
        if c['id'] != p['id']:
            return 'A lista mudou desde o seu pedido. Mande *pendentes* e peça de novo.'
        ag.acao_corte(c['id'], 'agendar')
        c2 = next((x for x in ag.estado()['cortes'] if x['id'] == c['id']), c)
        return f'✅ Corte "{c["titulo"][:60]}" aprovado por você e agendado' + (f' para {time.strftime("%d/%m %H:%M", time.localtime(c2["quando"]))}.' if c2.get('quando') else '.')
    return 'Não entendi. Mande *ajuda*.'


def responder(texto: str, por: str) -> str:
    """Uma mensagem sua -> a resposta que volta para você. Nunca levanta erro: devolve o motivo em texto simples."""
    t = (texto or '').strip()
    if not t:
        return ''
    try:
        if re.fullmatch(r'(sim|s|confirmo|confirma|pode|ok)[.!]*', t.lower()):
            p = _pendente(por)
            if not p:
                return 'Não há nada esperando confirmação (o pedido vale 10 minutos). Mande o comando de novo.'
            _guardar(por, None)
            if p['acao'] == 'liberar_corte':
                c = next((x for x in ag.estado()['cortes'] if x['id'] == p['id'] and x['status'] == 'pronto'), None)
                if not c:
                    return 'Esse corte não está mais esperando aprovação.'
                ag.acao_corte(c['id'], 'liberar')
                return f'✅ Corte "{c["titulo"][:60]}" liberado por você (com as restrições registradas) e agendado.'
            if p['acao'] == 'agendar_corte':
                c = next((x for x in ag.estado()['cortes'] if x['id'] == p['id'] and x['status'] == 'pronto'), None)
                if not c:
                    return 'Esse corte não está mais esperando aprovação.'
                ag.acao_corte(c['id'], 'agendar')
                c2 = next((x for x in ag.estado()['cortes'] if x['id'] == c['id']), c)
                return f'✅ Corte "{c["titulo"][:60]}" aprovado por você e agendado' + (f' para {time.strftime("%d/%m %H:%M", time.localtime(c2["quando"]))}.' if c2.get('quando') else '.')
            return executar(p, por, confirmado=True)
        if re.fullmatch(r'(n[aã]o|cancela|cancelar)[.!]*', t.lower()) and _pendente(por):
            _guardar(por, None)
            return 'Cancelado. Nada foi feito.'
        return executar(entender(t), por)
    except (ag.ErroAgente, apv.ErroAprovacao, pj.ErroProjeto) as e:
        return 'Não deu: ' + str(e)[:400]
    except Exception as e:  # noqa: BLE001
        ag.anotar(f'Comando por mensagem falhou: {e}', 'erro')
        return 'Deu um erro inesperado aqui. Tente pelo site e me avise.'
