"""Agente 3 — Fábrica de conteúdo original: linhas temáticas, pautas sem repetição, lotes de N episódios independentes.

- Uma LINHA guarda a identidade (tema, ideia geral, estilo do catálogo real, voz, personagens/cenários da biblioteca, agenda e estoque).
- PAUTAS: a IA propõe N (com gancho, classificação e fontes). Repetição é barrada por semelhança de palavras, não só pelo título.
  Afirmação de fato só vira "confirmada" quando o trecho que a sustenta é achado no texto baixado da fonte (checagem_fatos.py).
  Fato de risco alto (saúde, dinheiro, lei) sem tudo confirmado nunca é aceito sozinho.
- LOTE: cada pauta aceita vira um EPISÓDIO = um projeto do Agente 3 com o seu próprio roteiro, render, nota e versões.
  Se 5 de 6 passarem, os 5 seguem; o 6º fica na correção dele.
- Os episódios NÃO postam sozinhos ao ficar prontos: o vídeo aprovado (diretor + você, ou só o diretor na publicação automática)
  entra no estoque da linha e a programação diária do Agente 2 distribui nos horários.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
import uuid

import banco as db
import checagem_fatos as cf

MODOS_PAUTA = ('automatico', 'supervisionado', 'manual')
MODOS_EXEC = ('lote_unico', 'continuo')
MODOS_VISUAL = ('nenhum', 'fixo', 'variavel', 'misto')
CLASSES = ('fato', 'opiniao', 'hipotese', 'entretenimento')
ESTADOS_PAUTA = ('proposta', 'aceita', 'precisa_voce', 'bloqueada', 'usada', 'trocada', 'repetida')
SEMELHANCA_MAX = 0.5          # pauta com metade das palavras iguais a outra é repetição
CAMPOS_TRAVAVEIS = ('titulo', 'tema', 'estilo', 'voz', 'formato', 'duracao_seg', 'personagens', 'cenarios', 'ideia_roteiro', 'tipo', 'agenda', 'estoque',
                    'quantidade_lote', 'publicacao', 'modo_pautas', 'ritmo', 'imagens', 'tom', 'publico')


class ErroLinha(Exception):
    def __init__(self, msg: str, status: int = 400):
        super().__init__(msg)
        self.status = status


def _t(v, n: int) -> str:
    return re.sub(r'\s+', ' ', str(v or '')).strip()[:n]


def _lista(v, n: int, tam: int = 80) -> list:
    if isinstance(v, str):
        v = [x for x in re.split(r'[,;\n]', v)]
    return [_t(x, tam) for x in (v or []) if _t(x, tam)][:n]


def _int(v, lo: int, hi: int, nome: str) -> int:
    try:
        x = int(float(v))
    except (TypeError, ValueError):
        raise ErroLinha(f'{nome}: precisa ser um número.')
    if not lo <= x <= hi:
        raise ErroLinha(f'{nome}: de {lo} a {hi}.')
    return x


# ---------------------------------------------------------------- configuração
def validar(d: dict, atual: dict | None = None) -> dict:
    import estilos_codigo as ec
    import produtor
    if not isinstance(d, dict):
        raise ErroLinha('Configuração inválida.')
    base = dict(atual or {})
    travas = [x for x in (d.get('travas', base.get('travas')) or []) if x in CAMPOS_TRAVAVEIS]
    if atual and d.get('_sugestao'):           # sugestão automática nunca mexe em campo travado por você
        d = {k: v for k, v in d.items() if k not in travas}
    base.update({k: v for k, v in d.items() if not k.startswith('_')})
    titulo = _t(base.get('titulo'), 80)
    if len(titulo) < 3:
        raise ErroLinha('Dê um nome para a linha (ex.: Curiosidades Científicas).')
    tema = _t(base.get('tema'), 200)
    if len(tema) < 3:
        raise ErroLinha('Diga o tema principal da linha.')
    estilos = {e['id']: e for e in ec.catalogo()}
    est = str(base.get('estilo') or 'documentario')
    if est not in estilos:
        raise ErroLinha('Estilo fora do catálogo.')
    if estilos[est]['status'] == 'indisponivel':
        raise ErroLinha(f'O estilo "{estilos[est]["nome"]}" não roda neste servidor: {estilos[est]["descricao"][:160]}')
    if estilos[est]['status'] == 'beta' and not base.get('confirmar_beta'):
        raise ErroLinha(f'O estilo "{estilos[est]["nome"]}" está em teste (beta). Marque "aceito estilo em teste" para usar.')
    pers = base.get('personagens') if isinstance(base.get('personagens'), dict) else {}
    modo_vis = pers.get('modo') if pers.get('modo') in MODOS_VISUAL else 'nenhum'
    ids = [{'id': re.sub(r'[^a-z0-9_-]', '', str(x.get('id') or '').lower())[:40], 'versao': max(1, int(x.get('versao') or 1))}
           for x in (pers.get('ids') or []) if isinstance(x, dict) and x.get('id')][:4]
    if modo_vis != 'nenhum' and est not in ('animado2d', 'animado3d'):
        raise ErroLinha(f'O estilo "{estilos[est]["nome"]}" não tem personagem animado. Escolha "Sem personagem" ou um estilo animado (Desenho animado).')
    if modo_vis == 'fixo' and not ids and not _t(pers.get('descricao'), 10):
        raise ErroLinha('Personagem fixo: escolha um da biblioteca ou descreva como ele é.')
    ag_ = base.get('agenda') if isinstance(base.get('agenda'), dict) else {}
    redes = [r for r in (ag_.get('redes') or []) if r in ('youtube', 'instagram', 'facebook', 'tiktok', 'kwai')]
    horarios = []
    for h in (ag_.get('horarios') or [])[:12]:
        m = re.fullmatch(r'([01]?\d|2[0-3]):([0-5]\d)', str(h).strip())
        if not m:
            raise ErroLinha(f'Horário inválido: {str(h)[:8]} (use HH:MM).')
        horarios.append(f'{int(m.group(1)):02d}:{m.group(2)}')
    dias = sorted({int(x) for x in (ag_.get('dias') if ag_.get('dias') is not None else range(7)) if str(x).isdigit() and 0 <= int(x) <= 6})
    bib = base.get('biblioteca') if isinstance(base.get('biblioteca'), dict) else {}
    es = base.get('estoque') if isinstance(base.get('estoque'), dict) else {}
    minimo = _int(es.get('minimo', 3), 0, 60, 'Estoque mínimo')
    alvo = _int(es.get('alvo', 7), max(1, minimo), 90, 'Estoque alvo')
    cfg = {
        'titulo': titulo, 'tema': tema, 'subtemas': _lista(base.get('subtemas'), 12), 'excluir': _lista(base.get('excluir'), 12),
        'publico': _t(base.get('publico'), 200), 'idioma': _t(base.get('idioma') or 'pt-BR', 12), 'objetivo': _t(base.get('objetivo'), 200),
        'tom': _t(base.get('tom'), 120), 'ideia_geral': _t(base.get('ideia_geral'), 1500), 'referencias': _t(base.get('referencias'), 1500),
        'ideia_roteiro': _t(base.get('ideia_roteiro'), 1500), 'gancho_preferido': _t(base.get('gancho_preferido'), 200),
        'restricoes': _t(base.get('restricoes'), 800),
        'tipo': base.get('tipo') if base.get('tipo') in produtor.TIPOS else 'curiosidades',
        'quantidade_lote': _int(base.get('quantidade_lote', 6), 1, 30, 'Vídeos por lote'),
        'duracao_seg': _int(base.get('duracao_seg', 45), 15, 180, 'Duração'),
        'formato': base.get('formato') if base.get('formato') in ec.FORMATOS else '9:16',
        'estilo': est, 'confirmar_beta': bool(base.get('confirmar_beta')),
        'voz': base.get('voz') if base.get('voz') in produtor.VOZES + ['nenhuma'] else 'Charon',
        'ritmo': base.get('ritmo') if base.get('ritmo') in produtor.RITMOS else 'normal',
        'imagens': base.get('imagens') if base.get('imagens') in ('nenhuma', 'gemini', 'busca') else ('busca' if est == 'documentario' else 'nenhuma'),
        'personagens': {'modo': modo_vis, 'ids': ids, 'descricao': _t(pers.get('descricao'), 800)},
        'cenarios': {'ids': [re.sub(r'[^a-z0-9_-]', '', str(x).lower())[:40] for x in ((base.get('cenarios') or {}).get('ids') or []) if x][:4],
                     'descricao': _t((base.get('cenarios') or {}).get('descricao'), 800)},
        'modo_pautas': base.get('modo_pautas') if base.get('modo_pautas') in MODOS_PAUTA else 'supervisionado',
        'aprovar_roteiro': base.get('aprovar_roteiro') if base.get('aprovar_roteiro') in ('voce', 'automatico') else 'voce',
        'publicacao': base.get('publicacao') if base.get('publicacao') in ('voce', 'automatica') else 'voce',
        'agenda': {'redes': redes, 'horarios': sorted(set(horarios)), 'dias': dias},
        'prioridade': _int(base.get('prioridade', 3), 1, 5, 'Prioridade na agenda'),
        'orcamento_dia': max(0.0, min(float(base.get('orcamento_dia') or 0), 500.0)),
        'biblioteca': {k: str(bib.get(k) or '')[:40] for k in ('modelo_roteiro', 'pacote_visual', 'perfil_narracao')},
        'estoque': {'minimo': minimo, 'alvo': alvo},
        'modo_execucao': base.get('modo_execucao') if base.get('modo_execucao') in MODOS_EXEC else 'lote_unico',
        'limite_dia': _int(base.get('limite_dia', 3), 1, 12, 'Vídeos iniciados por dia'),
        'orcamento_video': max(0.0, min(float(base.get('orcamento_video') or 2.0), 20.0)),
        'travas': travas,
    }
    if cfg['publicacao'] == 'automatica' and not redes:
        raise ErroLinha('Publicação automática precisa de pelo menos uma rede na agenda da linha.')
    return cfg


def _linha(lid: str) -> dict:
    r = db.um('SELECT * FROM linhas_conteudo WHERE id=?', lid)
    if not r:
        raise ErroLinha('Linha não encontrada.', 404)
    return {'id': r['id'], 'titulo': r['titulo'], 'estado': r['estado'], 'versao': r['versao'], 'criado': r['criado'], 'atualizado': r['atualizado'],
            **json.loads(r['config'])}


def criar(d: dict, quem: str = 'site') -> dict:
    cfg = validar(d)
    lid = 'ln_' + uuid.uuid4().hex[:10]
    agora = time.time()
    db.executar('INSERT INTO linhas_conteudo (id, titulo, config, estado, versao, criado, atualizado) VALUES (?,?,?,?,?,?,?)', lid, cfg['titulo'],
                json.dumps(cfg, ensure_ascii=False), 'ativa', 1, agora, agora)
    db.evento(quem, 'linha_criada', 'linha:' + lid, {'titulo': cfg['titulo'], 'lote': cfg['quantidade_lote']})
    r = obter(lid)
    r['agenda_aplicada'] = aplicar_horarios(cfg, quem)
    return r


def aplicar_horarios(cfg: dict, quem: str = 'site') -> list:
    """Horários da linha viram horários na programação diária de cada rede (cria a programação ou SOMA os horários aos que já existem).
    Os horários são da rede, não exclusivos da linha: a prioridade da linha decide quem ocupa cada um."""
    import agenda_postagem as ag2
    hs, dias = cfg['agenda'].get('horarios') or [], cfg['agenda'].get('dias') or []
    out = []
    if not hs:
        return out
    for rede in cfg['agenda']['redes']:
        try:
            a = db.um('SELECT id FROM posting_schedules WHERE conta=? AND rede=? AND apagado=0', 'principal', rede)
            if not a:
                ag2.criar({'platform': rede, 'mode': 'fixed', 'weekdays': dias, 'fixed_times': hs}, quem)
                out.append({'rede': rede, 'ok': True, 'acao': 'programação criada'})
                continue
            atual = ag2._agenda(a['id'])
            if atual['mode'] == 'automatic':
                out.append({'rede': rede, 'ok': False, 'acao': 'A programação desta rede está no modo automático: mude para fixo ou misto para usar horários exatos.'})
                continue
            regras = {k: list(v) for k, v in atual['weekly_rules'].items()}
            mudou = False
            for d in dias:
                novo = sorted(set(regras.get(str(d), [])) | set(hs))
                mudou |= novo != sorted(regras.get(str(d), []))
                regras[str(d)] = novo
            if mudou:
                ag2.atualizar(a['id'], {'weekly_rules': regras}, atual['version'], quem)
            out.append({'rede': rede, 'ok': True, 'acao': 'horários somados à programação' if mudou else 'horários já estavam na programação'})
        except ag2.ErroAgenda as e:
            out.append({'rede': rede, 'ok': False, 'acao': str(e)})
    return out


def atualizar(lid: str, d: dict, quem: str = 'site') -> dict:
    atual = _linha(lid)
    if d.get('versao') is not None and int(d['versao']) != atual['versao']:
        raise ErroLinha('Esta linha foi mudada em outro aparelho. Abra de novo.', 409)
    cfg = validar(d, {k: v for k, v in atual.items() if k not in ('id', 'estado', 'versao', 'criado', 'atualizado')})
    estado = d.get('estado') if d.get('estado') in ('ativa', 'pausada') else atual['estado']
    db.executar('UPDATE linhas_conteudo SET titulo=?, config=?, estado=?, versao=versao+1, atualizado=? WHERE id=?', cfg['titulo'],
                json.dumps(cfg, ensure_ascii=False), estado, time.time(), lid)
    db.evento(quem, 'linha_mudou', 'linha:' + lid, {'estado': estado})
    r = obter(lid)
    if 'agenda' in d:
        r['agenda_aplicada'] = aplicar_horarios(cfg, quem)
    return r


PADRAO_NOVA = {'quantidade_lote': 6, 'duracao_seg': 45, 'estilo': 'documentario', 'modo_pautas': 'supervisionado', 'aprovar_roteiro': 'voce',
               'publicacao': 'voce', 'modo_execucao': 'lote_unico', 'limite_dia': 6, 'estoque': {'minimo': 3, 'alvo': 7}}
CAMPOS_SUGESTAO = ('titulo', 'tema', 'subtemas', 'excluir', 'publico', 'objetivo', 'tom', 'ideia_geral', 'ideia_roteiro', 'gancho_preferido', 'restricoes',
                   'tipo', 'quantidade_lote', 'duracao_seg', 'formato', 'estilo', 'voz', 'ritmo', 'imagens', 'personagens', 'agenda', 'modo_execucao', 'estoque')


def _prompt_config(texto: str, catalogo: list, vozes: list, tipos: list, formatos: list) -> str:
    est = '; '.join(f'{e["id"]} = {e["nome"]} ({e["status"]})' for e in catalogo)
    return ('Você transforma o pedido do dono em configuração de uma LINHA de vídeos curtos. Use só o que o pedido diz ou deixa claro; '
            'campo não citado fica de fora do JSON (não invente).\n'
            f'Estilos (id = nome (situação)): {est}\nVozes: {", ".join(vozes)}. Voz masculina grave: Charon; feminina: Kore.\n'
            f'Tipos: {", ".join(tipos)}. Formatos: {", ".join(formatos)}.\n'
            'Campos: titulo, tema, subtemas[], excluir[], publico, objetivo, tom, ideia_geral, ideia_roteiro, gancho_preferido, restricoes, tipo, '
            'quantidade_lote (1-30), duracao_seg (15-180), formato, estilo (id), voz, ritmo (calmo|normal|agil|rapido), imagens (nenhuma|gemini|busca: '
            '"imagens de apoio" = busca), personagens {modo: nenhum|fixo|variavel|misto, descricao}, '
            'agenda {redes: [youtube|instagram|facebook|tiktok|kwai], horarios: ["HH:MM"], dias: [0=segunda..6=domingo]}, '
            'modo_execucao (lote_unico|continuo: "quando o estoque ficar baixo" = continuo), estoque {minimo, alvo}.\n'
            f'PEDIDO: {texto[:3000]}\nResponda JSON: {{"config": {{...}}, "duvidas": ["o que ficou em aberto"]}}')


def sugerir_config(texto: str, lid: str | None = None, ia=None) -> dict:
    """A IA lê a descrição livre e PROPÕE a configuração. Nada é gravado: a tela mostra as mudanças e você aplica.
    Campo com cadeado nunca muda. Estilo fora do catálogo, indisponível ou beta não é escolhido sozinho."""
    import estilos_codigo as ec
    import produtor
    texto = str(texto or '').strip()
    if len(texto) < 15:
        raise ErroLinha('Descreva a linha com um pouco mais de detalhe (tema, quantos vídeos, duração, estilo, horários).')
    atual = _linha(lid) if lid else None
    base = {k: v for k, v in (atual or PADRAO_NOVA).items() if k not in ('id', 'estado', 'versao', 'criado', 'atualizado')}
    travas = (atual or {}).get('travas') or []
    cat = ec.catalogo()
    if ia is None:
        import agente as ag
        ia = lambda prompt: ag.gemini([{'text': prompt}], uso='roteiro')  # noqa: E731
    try:
        r = ia(_prompt_config(texto, cat, produtor.VOZES, produtor.TIPOS, list(ec.FORMATOS))) or {}
    except Exception as e:  # noqa: BLE001
        raise ErroLinha(f'A IA não conseguiu ler a descrição agora: {str(e)[:200]}', 502)
    sug = r.get('config') if isinstance(r.get('config'), dict) else {}
    avisos = [str(x)[:200] for x in (r.get('duvidas') or [])[:6]]
    estilos = {e['id']: e for e in cat}
    if 'estilo' in sug:
        e = estilos.get(str(sug['estilo']))
        if not e:
            avisos.append(f'A IA pediu um estilo que não existe ("{str(sug["estilo"])[:30]}"): mantive o atual.')
            sug.pop('estilo')
        elif e['status'] == 'indisponivel':
            avisos.append(f'O estilo "{e["nome"]}" não roda neste servidor: mantive o atual.')
            sug.pop('estilo')
        elif e['status'] == 'beta':
            avisos.append(f'O estilo "{e["nome"]}" está em teste: escolha você e marque "aceito estilo em teste".')
            sug.pop('estilo')
    novo = dict(base)
    mudancas = []
    for k in CAMPOS_SUGESTAO:
        if k not in sug or k in travas:
            continue
        v = sug[k]
        if k == 'agenda' and isinstance(v, dict):
            v = {**(base.get('agenda') or {}), **{a: b for a, b in v.items() if a in ('redes', 'horarios', 'dias')}}
        if k == 'personagens' and isinstance(v, dict):
            v = {**(base.get('personagens') or {'modo': 'nenhum', 'ids': [], 'descricao': ''}), **{a: b for a, b in v.items() if a in ('modo', 'descricao')}}
        if v != base.get(k):
            novo[k] = v
    try:
        cfg = validar(novo, None)
    except ErroLinha as e:          # o que a IA propôs não passa nas regras: mostra o motivo em vez de gravar algo errado
        raise ErroLinha(f'A proposta da IA não passou nas regras: {e}. Ajuste a descrição ou preencha o campo à mão.', 422)
    for k in CAMPOS_SUGESTAO:
        if cfg.get(k) != base.get(k):
            mudancas.append({'campo': k, 'de': base.get(k), 'para': cfg.get(k)})
    if travas:
        avisos.append('Campos com cadeado não foram mudados: ' + ', '.join(travas) + '.')
    return {'proposta': cfg, 'mudancas': mudancas, 'avisos': avisos, 'linha': lid or ''}


def listar() -> list:
    return [resumo(r['id']) for r in db.todos("SELECT id FROM linhas_conteudo WHERE estado<>'apagada' ORDER BY atualizado DESC")]


def obter(lid: str) -> dict:
    x = _linha(lid)
    x['resumo'] = resumo(lid)
    x['pautas'] = pautas(lid)
    x['episodios'] = episodios(lid)
    x['lotes'] = db.todos('SELECT * FROM conteudo_lotes WHERE linha=? ORDER BY iniciado DESC LIMIT 20', lid)
    return x


# ---------------------------------------------------------------- pautas
def _norm(t: str) -> set:
    t = unicodedata.normalize('NFKD', str(t).lower())
    t = ''.join(c for c in t if not unicodedata.combining(c))
    pal = re.findall(r'[a-z0-9]{3,}', t)
    para = {'que', 'com', 'para', 'por', 'uma', 'como', 'mais', 'dos', 'das', 'nos', 'nas', 'sobre', 'voce', 'isso', 'esse', 'essa', 'sao', 'nao', 'tem', 'seu', 'sua'}
    return {p for p in pal if p not in para}


def semelhanca(a: str, b: str) -> float:
    x, y = _norm(a), _norm(b)
    if not x or not y:
        return 0.0
    return len(x & y) / len(x | y)


def _ja_feitos(lid: str) -> list[str]:
    """Textos já usados (pautas da linha que não foram trocadas + títulos de vídeos do Agente 3) para barrar repetição."""
    out = []
    for r in db.todos("SELECT titulo, dados FROM conteudo_pautas WHERE linha=? AND status NOT IN ('trocada','repetida')", lid):
        out += [f'{r["titulo"]} {json.loads(r["dados"]).get("resumo", "")}', r['titulo']]      # título sozinho também: pega pauta curta escrita por você
    out += [r['titulo'] for r in db.todos("SELECT titulo FROM projetos WHERE tipo='agente3' ORDER BY criado DESC LIMIT 300")]
    return out


def repetida(texto: str, existentes: list[str], titulo: str = '') -> str | None:
    for e in existentes:
        if semelhanca(texto, e) >= SEMELHANCA_MAX or (titulo and semelhanca(titulo, e) >= SEMELHANCA_MAX):
            return e[:80]
    return None


def _prompt(cfg: dict, n: int, evitar: list[str]) -> str:
    return (f'Você planeja pautas de vídeos curtos ({cfg["duracao_seg"]} s, {cfg["formato"]}) da linha "{cfg["titulo"]}".\n'
            f'Tema: {cfg["tema"]}. Subtemas: {", ".join(cfg["subtemas"]) or "livre"}. NÃO tratar de: {", ".join(cfg["excluir"]) or "—"}.\n'
            f'Público: {cfg["publico"] or "geral"}. Objetivo: {cfg["objetivo"] or "informar e prender a atenção"}. Tom: {cfg["tom"] or "simples e direto"}.\n'
            f'Ideia geral do dono: {cfg["ideia_geral"] or "—"}\nIdeia de roteiro: {cfg["ideia_roteiro"] or "—"}\nGancho preferido: {cfg["gancho_preferido"] or "—"}\n'
            f'Restrições: {cfg["restricoes"] or "—"}\nJá feitos (não repita nem parafraseie): {" | ".join(x[:70] for x in evitar[-40:]) or "nenhum"}\n'
            f'Crie {n} pautas DIFERENTES entre si. Para cada uma: titulo, subtema, resumo (2 frases), gancho (primeira frase do vídeo), objetivo, '
            'classificacao (fato, opiniao, hipotese ou entretenimento), afirmacoes (até 4 frases que o vídeo vai afirmar como fato), '
            'fontes (até 3, cada uma {url, origem, fato}: só links reais de instituições, revistas científicas ou enciclopédias; se não souber um link real, deixe vazio). '
            'Responda JSON: {"pautas": [ ... ]}')


def _limpar_pauta(x: dict) -> dict | None:
    if not isinstance(x, dict) or len(_t(x.get('titulo'), 120)) < 4:
        return None
    fontes = []
    for f in (x.get('fontes') or [])[:3]:
        if isinstance(f, dict) and re.fullmatch(r'https://[\w.-]+\.[a-z]{2,}(/\S*)?', str(f.get('url') or '')[:300]):
            fontes.append({'url': str(f['url'])[:300], 'origem': _t(f.get('origem'), 80), 'fato': _t(f.get('fato'), 240)})
    cl = x.get('classificacao') if x.get('classificacao') in CLASSES else 'fato'
    return {'titulo': _t(x.get('titulo'), 120), 'subtema': _t(x.get('subtema'), 80), 'resumo': _t(x.get('resumo'), 400), 'gancho': _t(x.get('gancho'), 200),
            'objetivo': _t(x.get('objetivo'), 160), 'classificacao': cl, 'afirmacoes': [_t(a, 240) for a in (x.get('afirmacoes') or [])[:4] if _t(a, 240)],
            'fontes': fontes}


def _gravar_pauta(lid: str, p: dict, status: str) -> dict:
    pid = 'pa_' + uuid.uuid4().hex[:10]
    ass = hashlib.sha1(' '.join(sorted(_norm(p['titulo'] + ' ' + p.get('resumo', '')))).encode()).hexdigest()[:16]
    agora = time.time()
    db.executar('INSERT INTO conteudo_pautas (id, linha, lote, titulo, dados, status, assinatura, criado, atualizado) VALUES (?,?,?,?,?,?,?,?,?)', pid, lid, None,
                p['titulo'], json.dumps(p, ensure_ascii=False), status, ass, agora, agora)
    return {'id': pid, 'status': status, **p}


def planejar_pautas(lid: str, n: int | None = None, ia=None, buscar=None) -> dict:
    """A IA propõe N pautas. ia(prompt) -> dict (para testes); por padrão o Gemini do servidor."""
    cfg = _linha(lid)
    n = max(1, min(int(n or cfg['quantidade_lote']), 30))
    if cfg['modo_pautas'] == 'manual':
        raise ErroLinha('Esta linha está no modo "eu escrevo as pautas". Escreva as pautas ou mude o modo.')
    evitar = _ja_feitos(lid)
    if ia is None:
        import agente as ag
        ia = lambda prompt: ag.gemini([{'text': prompt}], uso='roteiro')  # noqa: E731
    try:
        bruto = ia(_prompt(cfg, n + 2, evitar))          # 2 de reserva, porque algumas caem na repetição
    except Exception as e:  # noqa: BLE001
        raise ErroLinha(f'A IA não conseguiu planejar as pautas agora: {str(e)[:200]}', 502)
    novas, repetidas = [], []
    for x in (bruto or {}).get('pautas') or []:
        p = _limpar_pauta(x)
        if not p:
            continue
        texto = f'{p["titulo"]} {p["resumo"]}'
        rep = repetida(texto, evitar, p['titulo'])
        if rep or any(t in texto.lower() for t in [e.lower() for e in cfg['excluir'] if e]):
            repetidas.append({'titulo': p['titulo'], 'parecida_com': rep or 'assunto que você excluiu'})
            continue
        if len(novas) >= n:
            break
        if p['classificacao'] == 'fato':
            p = cf.conferir(p, ia, buscar or cf.baixar)       # afirmação só é "confirmada" com o trecho achado no texto da fonte
        else:
            p['verificacao'] = 'não se aplica'
            p['risco'] = cf.risco(p)
        if cfg['modo_pautas'] == 'automatico':
            st = 'aceita' if cf.pode_aceitar_sozinha(p) else 'precisa_voce'
        else:
            st = 'proposta'
        novas.append(_gravar_pauta(lid, p, st))
        evitar += [texto, p['titulo']]
    db.evento('agente3', 'pautas_planejadas', 'linha:' + lid, {'novas': len(novas), 'repetidas': len(repetidas)})
    return {'pautas': novas, 'repetidas': repetidas,
            'aviso': '' if len(novas) >= n else f'A IA trouxe só {len(novas)} pauta(s) nova(s) de {n}: as outras repetiam assuntos já feitos.'}


def escrever_pautas(lid: str, titulos: list) -> dict:
    """Pautas escritas por você: entram como aceitas (só a repetição é conferida)."""
    _linha(lid)
    evitar = _ja_feitos(lid)
    novas, rep = [], []
    for t in [_t(x, 120) for x in titulos or [] if _t(x, 120)][:30]:
        r = repetida(t, evitar)
        if r:
            rep.append({'titulo': t, 'parecida_com': r})
            continue
        novas.append(_gravar_pauta(lid, {'titulo': t, 'subtema': '', 'resumo': '', 'gancho': '', 'objetivo': '', 'classificacao': 'entretenimento',
                                         'afirmacoes': [], 'fontes': [], 'verificacao': 'escrita por você'}, 'aceita'))
        evitar.append(t)
    return {'pautas': novas, 'repetidas': rep}


def mudar_pauta(pid: str, acao: str, dados: dict | None = None) -> dict:
    r = db.um('SELECT * FROM conteudo_pautas WHERE id=?', pid)
    if not r:
        raise ErroLinha('Pauta não encontrada.', 404)
    if r['status'] == 'usada':
        raise ErroLinha('Esta pauta já virou vídeo.', 409)
    d = json.loads(r['dados'])
    if acao == 'aceitar':
        st = 'aceita'
    elif acao == 'bloquear':
        st = 'bloqueada'
    elif acao == 'trocar':
        st = 'trocada'
    elif acao == 'editar':
        d.update({k: _t(v, 400) for k, v in (dados or {}).items() if k in ('titulo', 'resumo', 'gancho', 'subtema', 'objetivo')})
        d['editada'] = True
        st = 'aceita'
    else:
        raise ErroLinha('Ação inválida (aceitar, editar, trocar, bloquear).')
    db.executar('UPDATE conteudo_pautas SET titulo=?, dados=?, status=?, atualizado=? WHERE id=?', d['titulo'], json.dumps(d, ensure_ascii=False), st, time.time(), pid)
    return {'id': pid, 'status': st, **d}


def pautas(lid: str) -> list:
    return [{'id': r['id'], 'status': r['status'], 'lote': r['lote'], **json.loads(r['dados'])}
            for r in db.todos("SELECT * FROM conteudo_pautas WHERE linha=? AND status NOT IN ('trocada') ORDER BY criado DESC LIMIT 120", lid)]


# ---------------------------------------------------------------- lotes e episódios
def _briefing(cfg: dict, p: dict) -> dict:
    partes = [p.get('resumo', ''), f'Gancho: {p["gancho"]}' if p.get('gancho') else '', f'Ideia de roteiro: {cfg["ideia_roteiro"]}' if cfg['ideia_roteiro'] else '',
              f'Restrições: {cfg["restricoes"]}' if cfg['restricoes'] else '', f'Tom: {cfg["tom"]}' if cfg['tom'] else '',
              f'Personagem: {cfg["personagens"]["descricao"]}' if cfg['personagens']['descricao'] else '',
              f'Cenário: {cfg["cenarios"]["descricao"]}' if cfg['cenarios']['descricao'] else '']
    if p.get('afirmacoes'):
        partes.append('Afirmações que o vídeo pode fazer: ' + ' | '.join(p['afirmacoes']))
    nao_conf = [c['afirmacao'] for c in p.get('conferencia') or [] if not c.get('ok')]
    if p.get('verificacao') == 'não verificado' or nao_conf:
        partes.append('ATENÇÃO: estas afirmações NÃO foram confirmadas na fonte; não as apresente como fato: ' + (' | '.join(nao_conf) or 'todas'))
    fontes = '\n'.join(f'{f["origem"]}: {f["url"]}' for f in p.get('fontes') or [] if f.get('abre'))
    return {'tema': p['titulo'], 'nicho': cfg['tema'], 'publico': cfg['publico'], 'objetivo': p.get('objetivo') or cfg['objetivo'], 'idioma': cfg['idioma'],
            'tipo': cfg['tipo'], 'descricao': '\n'.join(x for x in partes if x)[:1500], 'origem': 'linha', 'referencias': fontes[:1500],
            'duracao_alvo': cfg['duracao_seg'], 'formato': cfg['formato'], 'cenas_qtd': max(3, min(9, cfg['duracao_seg'] // 7)), 'estilo': cfg['estilo'],
            'voz': cfg['voz'], 'ritmo': cfg['ritmo'], 'imagens': cfg['imagens'],
            'modo_aprovacao': 'assistido' if cfg['aprovar_roteiro'] == 'voce' else 'supervisionado',
            'orcamento_max': cfg['orcamento_video'], 'elenco_biblioteca': cfg['personagens']['ids'], 'cenarios_biblioteca': cfg['cenarios']['ids'],
            'destinos': {'redes': [], 'quando': 'proximo'}}       # quem distribui é a programação diária, não a aprovação


def iniciados_hoje(lid: str) -> int:
    ini = time.time() - 86400
    return db.um('SELECT COUNT(*) n FROM conteudo_episodios WHERE linha=? AND criado>?', lid, ini)['n']


def gasto_24h(lid: str) -> float:
    """Gasto estimado (o que o produtor registra a cada chamada de IA) dos vídeos desta linha nas últimas 24 h."""
    r = db.um('SELECT COALESCE(SUM(c.estimado),0) s FROM custos c JOIN jobs j ON j.id=c.job JOIN conteudo_episodios e ON e.projeto=j.projeto '
              'WHERE e.linha=? AND c.t>?', lid, time.time() - 86400)
    return round(float(r['s'] or 0), 2)


def iniciar_lote(lid: str, n: int | None = None, quem: str = 'site', motivo: str = 'pedido por você', produzir=None) -> dict:
    """Cria até N episódios (um projeto por pauta aceita ainda não usada) e manda produzir. Idempotente por pauta."""
    import produtor
    import projetos as pj
    cfg = _linha(lid)
    linha_estado = db.um('SELECT estado FROM linhas_conteudo WHERE id=?', lid)['estado']
    if linha_estado != 'ativa':
        raise ErroLinha('A linha está pausada.', 409)
    n = max(1, min(int(n or cfg['quantidade_lote']), 30))
    folga = cfg['limite_dia'] - iniciados_hoje(lid)
    if folga <= 0:
        raise ErroLinha(f'Esta linha já começou {cfg["limite_dia"]} vídeo(s) nas últimas 24 h (limite que você definiu).', 429)
    n = min(n, folga)
    if cfg.get('orcamento_dia'):
        gasto = gasto_24h(lid)
        cabe = int((cfg['orcamento_dia'] - gasto) // max(cfg['orcamento_video'], 0.01))
        if cabe <= 0:
            raise ErroLinha(f'Orçamento do dia da linha alcançado: R$ {gasto:.2f} de R$ {cfg["orcamento_dia"]:.2f} nas últimas 24 h '
                            f'(cada vídeo pode gastar até R$ {cfg["orcamento_video"]:.2f}).', 429)
        n = min(n, cabe)
    livres = db.todos("SELECT * FROM conteudo_pautas WHERE linha=? AND status='aceita' ORDER BY criado LIMIT ?", lid, n)
    if not livres:
        raise ErroLinha('Não há pauta aceita para produzir. Planeje pautas (ou aceite as propostas) primeiro.', 409)
    lote = 'lt_' + uuid.uuid4().hex[:10]
    db.executar('INSERT INTO conteudo_lotes (id, linha, meta, status, motivo, chave, iniciado) VALUES (?,?,?,?,?,?,?)', lote, lid, len(livres), 'produzindo',
                motivo[:200], None, time.time())
    produzir = produzir or (lambda pid_, chave: produtor.produzir(pid_, None, chave, '', quem))
    feitos = []
    for r in livres:
        p = json.loads(r['dados'])
        eid = 'ep_' + uuid.uuid4().hex[:10]
        n_ok = db.executar("UPDATE conteudo_pautas SET status='usada', lote=?, atualizado=? WHERE id=? AND status='aceita'", lote, time.time(), r['id'])
        if not n_ok:
            continue                   # outra chamada pegou esta pauta primeiro
        import biblioteca_criativa as bc
        brief, usados = bc.aplicar_no_briefing(_briefing(cfg, p), cfg.get('biblioteca') or {})     # versões da biblioteca ficam presas ao episódio
        proj = produtor.novo({'briefing': brief, 'modo': 'automatico', 'origem': 'linha'}, quem)
        pj.mudar_dados(proj['id'], lambda d, _p, eid=eid: d.update(linha={'id': lid, 'episodio': eid, 'pauta': r['id'], 'titulo': cfg['titulo'], 'biblioteca': usados}))
        db.executar('INSERT INTO conteudo_episodios (id, linha, lote, pauta, projeto, status, dados, criado, atualizado) VALUES (?,?,?,?,?,?,?,?,?)', eid, lid, lote,
                    r['id'], proj['id'], 'produzindo', json.dumps({'titulo': p['titulo'], 'biblioteca': usados}, ensure_ascii=False), time.time(), time.time())
        produzir(proj['id'], f'linha:{eid}')
        feitos.append({'episodio': eid, 'projeto': proj['id'], 'titulo': p['titulo']})
    db.evento(quem, 'lote_iniciado', 'linha:' + lid, {'lote': lote, 'episodios': len(feitos), 'motivo': motivo[:120]})
    return {'lote': lote, 'episodios': feitos}


ESTADO_EPISODIO = {'draft': 'Rascunho', 'researching': 'Pesquisando', 'waiting_brief_approval': 'Esperando você aprovar o roteiro',
                   'storyboard_ready': 'Roteiro pronto', 'queued': 'Na fila', 'generating_assets': 'Gerando imagens', 'narrating': 'Narrando',
                   'assembling': 'Montando', 'rendering': 'Renderizando', 'validating': 'Conferindo', 'ready_for_review': 'Aprovado pelo diretor: falta você',
                   'approved': 'No estoque (aprovado)', 'queued_to_publish': 'Na fila de postagem', 'posted': 'Publicado', 'failed': 'Precisa da sua revisão',
                   'cancelled': 'Cancelado', 'changes_requested': 'Correção pedida', 'rejected': 'Rejeitado', 'retry_wait': 'Esperando nova tentativa'}


def episodios(lid: str) -> list:
    import projetos as pj
    out = []
    for r in db.todos('SELECT * FROM conteudo_episodios WHERE linha=? ORDER BY criado DESC LIMIT 100', lid):
        try:
            p = pj.obter(r['projeto'])
        except Exception:  # noqa: BLE001
            out.append({'id': r['id'], 'projeto': r['projeto'], 'status': 'apagado', 'nome_status': 'Projeto apagado', 'titulo': json.loads(r['dados'] or '{}').get('titulo', '')})
            continue
        dr = p['dados'].get('diretor') or {}
        pubs = db.todos("SELECT rede, estado, quando_utc FROM posting_slots WHERE ref=? AND estado NOT IN ('cancelado','perdido','vazio')", 'p:' + r['projeto'])
        out.append({'id': r['id'], 'projeto': r['projeto'], 'lote': r['lote'], 'titulo': p['titulo'], 'status': p['status'],
                    'nome_status': ESTADO_EPISODIO.get(p['status'], p['status']), 'nota': dr.get('nota'), 'veredito': dr.get('veredito'),
                    'correcoes': dr.get('tentativas'), 'sha': ((p['dados'].get('render') or {}).get('sha') or '')[:12], 'publicacoes': pubs,
                    'erro': ((p['dados'].get('producao') or {}).get('erro') or '')[:300]})
    return out


def _render_sha(p: dict) -> str:
    return (p['dados'].get('render') or {}).get('sha') or ''


def estoque(lid: str) -> dict:
    """Vídeos da linha prontos para entrar na agenda (aprovados, com certificado do arquivo) e o que ainda está em produção."""
    import pipeline as pl
    import projetos as pj
    cfg = _linha(lid)
    livres, reservados, producao, revisao = [], 0, 0, 0
    for r in db.todos('SELECT projeto FROM conteudo_episodios WHERE linha=?', lid):
        try:
            p = pj.obter(r['projeto'])
        except Exception:  # noqa: BLE001
            continue
        st = p['status']
        if st in ('failed', 'cancelled', 'rejected', 'posted'):
            revisao += st == 'failed'
            continue
        if st in ('approved', 'ready_for_review', 'queued_to_publish'):
            sha = _render_sha(p)
            usadas = {x['rede'] for x in db.todos("SELECT rede FROM posting_slots WHERE ref=? AND estado NOT IN ('cancelado','perdido','vazio')", 'p:' + p['id'])}
            falta = [x for x in cfg['agenda']['redes'] if x not in usadas]
            if usadas and not falta:
                reservados += 1
            elif st == 'ready_for_review' and cfg['publicacao'] == 'voce':
                revisao += 1                     # pronto, esperando a sua aprovação
            elif sha and (not pl.ligado() or pl.certificado(sha)):
                livres.append(p['id'])
            continue
        producao += 1
    return {'linha': lid, 'livres': len(livres), 'ids_livres': livres, 'reservados': reservados, 'em_producao': producao, 'esperando_voce': revisao,
            'minimo': cfg['estoque']['minimo'], 'alvo': cfg['estoque']['alvo']}


def resumo(lid: str) -> dict:
    cfg = _linha(lid)
    e = estoque(lid)
    cont = {r['status']: r['n'] for r in db.todos('SELECT status, COUNT(*) n FROM conteudo_pautas WHERE linha=? GROUP BY status', lid)}
    return {'id': lid, 'titulo': cfg['titulo'], 'estado': cfg['estado'], 'gasto_24h': gasto_24h(lid), 'orcamento_dia': cfg.get('orcamento_dia', 0), 'versao': cfg['versao'], 'estilo': cfg['estilo'], 'modo_execucao': cfg['modo_execucao'],
            'publicacao': cfg['publicacao'], 'redes': cfg['agenda']['redes'], 'estoque': e, 'pautas': cont,
            'episodios': db.um('SELECT COUNT(*) n FROM conteudo_episodios WHERE linha=?', lid)['n']}


def aprovar_automaticos(quem: str = 'automação') -> int:
    """Linhas com publicação automática: vídeo com certificado do diretor é aprovado sem esperar você (registrado como 'automação')."""
    import aprovacoes as apv
    import pipeline as pl
    import projetos as pj
    n = 0
    for lr in db.todos("SELECT id FROM linhas_conteudo WHERE estado='ativa'"):
        cfg = _linha(lr['id'])
        if cfg['publicacao'] != 'automatica':
            continue
        for r in db.todos('SELECT projeto FROM conteudo_episodios WHERE linha=?', lr['id']):
            try:
                p = pj.obter(r['projeto'])
            except Exception:  # noqa: BLE001
                continue
            sha = _render_sha(p)
            if p['status'] != 'ready_for_review' or not sha or not pl.certificado(sha):
                continue
            try:
                apv.aprovar(p['id'], sha, {'redes': []}, 'automacao', f'{quem} (linha {cfg["titulo"][:40]})')
                n += 1
            except apv.ErroAprovacao as e:
                db.evento('automacao', 'aprovacao_automatica_falhou', 'projeto:' + p['id'], {'erro': str(e)[:200]})
    if n:
        import agenda_postagem as ag2
        ag2.acordar()          # os horários vazios recebem o vídeo já, sem esperar o relógio do Agente 2
    return n


def ativos_para(rede: str) -> list:
    """Vídeos das linhas que podem ocupar um horário desta rede: aprovados (por você ou pela publicação automática),
    certificado válido para o arquivo e ainda sem horário nesta rede."""
    import pipeline as pl
    import projetos as pj
    out = []
    for lr in db.todos("SELECT id FROM linhas_conteudo WHERE estado='ativa'"):
        cfg = _linha(lr['id'])
        if rede not in cfg['agenda']['redes']:
            continue
        for r in db.todos('SELECT projeto, criado FROM conteudo_episodios WHERE linha=?', lr['id']):
            try:
                p = pj.obter(r['projeto'])
            except Exception:  # noqa: BLE001
                continue
            sha = _render_sha(p)
            if p['status'] not in ('approved', 'queued_to_publish') or not sha:
                continue
            if not db.um("SELECT id FROM aprovacoes WHERE projeto=? AND render_sha=? AND decisao='aprovado'", p['id'], sha):
                continue
            if db.um("SELECT id FROM posting_slots WHERE ref=? AND rede=? AND estado NOT IN ('cancelado','perdido','vazio')", 'p:' + p['id'], rede):
                continue
            cert = pl.certificado(sha)
            if not cert:
                continue
            out.append({'tipo': 'agente3', 'projeto': p, 'ref': 'p:' + p['id'], 'sha': sha, 'nota': cert['nota'], 'criado': r['criado'], 'linha': cfg['titulo'],
                        'prioridade': cfg.get('prioridade', 3)})
    return out
