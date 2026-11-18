"""Central de Automação: o estoque decide quando os agentes trabalham.

Agente 1 não procura nem corta vídeo enquanto o estoque de cortes aprovados der conta. Quando o estoque cai abaixo do
MÍNIMO ele volta a trabalhar e só para quando chega no ALVO (histerese: não fica liga-desliga a cada corte).
As linhas de conteúdo do Agente 3 em modo contínuo seguem a mesma regra, cada uma com o seu mínimo e alvo.

Desligada (padrão), tudo funciona como antes (meta de cortes por semana). Nada aqui posta: quem posta é o Agente 2,
e só vídeo com certificado do diretor para o arquivo atual.
As "sugestões" desta tela são regras simples sobre os seus números, não opinião de IA.
"""
import json
import math
import threading
import time

import banco as db

ESTADOS = ('desligada', 'ativa', 'pausada')
PRESETS = {
    'economico':   {'minimo': 5,  'alvo': 10, 'busca_horas': 48, 'cooldown_min': 180, 'linha_cooldown_min': 360},
    'equilibrado': {'minimo': 9,  'alvo': 21, 'busca_horas': 24, 'cooldown_min': 60,  'linha_cooldown_min': 120},
    'intensivo':   {'minimo': 14, 'alvo': 35, 'busca_horas': 12, 'cooldown_min': 30,  'linha_cooldown_min': 60},
}
NOMES_MODO = {'economico': 'Econômico', 'equilibrado': 'Equilibrado', 'intensivo': 'Intensivo', 'personalizado': 'Personalizado'}
TAXA_PADRAO = 0.6           # sem histórico: de cada 10 cortes, 6 passam no diretor (só para prever; ajustado pelos seus números)
_LOCK = threading.Lock()


class ErroAutomacao(Exception):
    def __init__(self, msg: str, status: int = 400):
        super().__init__(msg)
        self.status = status


def _padrao() -> dict:
    p = PRESETS['equilibrado']
    return {'estado': 'desligada', 'modo': 'equilibrado', 'versao': 0, 'atualizado': 0, 'por': '',
            'cortes': {'controle_estoque': True, 'minimo': p['minimo'], 'alvo': p['alvo'], 'busca_horas': p['busca_horas'],
                       'cooldown_min': p['cooldown_min']},
            'linhas': {'cooldown_min': p['linha_cooldown_min']}}


def config() -> dict:
    cfg = _padrao()
    v = db.kv('automacao')
    if isinstance(v, dict):
        for k in ('estado', 'modo', 'versao', 'atualizado', 'por'):
            if k in v:
                cfg[k] = v[k]
        for k in ('cortes', 'linhas'):
            if isinstance(v.get(k), dict):
                cfg[k].update({a: b for a, b in v[k].items() if a in cfg[k]})
    return cfg


def _int(v, lo, hi, nome):
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise ErroAutomacao(f'{nome}: use um número.') from None
    if not lo <= n <= hi:
        raise ErroAutomacao(f'{nome}: use um número de {lo} a {hi}.')
    return n


def validar(d: dict, atual: dict) -> dict:
    novo = json.loads(json.dumps(atual))
    if 'modo' in d:
        if d['modo'] not in (*PRESETS, 'personalizado'):
            raise ErroAutomacao('Modo inválido.')
        novo['modo'] = d['modo']
        if d['modo'] in PRESETS:               # o modo é só um atalho: os números ficam visíveis e editáveis
            p = PRESETS[d['modo']]
            novo['cortes'].update(minimo=p['minimo'], alvo=p['alvo'], busca_horas=p['busca_horas'], cooldown_min=p['cooldown_min'])
            novo['linhas']['cooldown_min'] = p['linha_cooldown_min']
    c = d.get('cortes')
    if isinstance(c, dict):
        mexeu = False
        if 'controle_estoque' in c:
            novo['cortes']['controle_estoque'] = bool(c['controle_estoque'])
        for k, lo, hi, nome in (('minimo', 0, 200, 'Mínimo de cortes'), ('alvo', 1, 300, 'Alvo de cortes'),
                                ('busca_horas', 1, 168, 'Busca de canais'), ('cooldown_min', 10, 1440, 'Intervalo entre rodadas')):
            if k in c:
                val = _int(c[k], lo, hi, nome)
                mexeu |= val != novo['cortes'][k]
                novo['cortes'][k] = val
        if mexeu and 'modo' not in d:
            novo['modo'] = 'personalizado'
    li = d.get('linhas')
    if isinstance(li, dict) and 'cooldown_min' in li:
        novo['linhas']['cooldown_min'] = _int(li['cooldown_min'], 10, 1440, 'Intervalo entre lotes')
    if novo['cortes']['alvo'] <= novo['cortes']['minimo']:
        raise ErroAutomacao('O alvo precisa ser maior que o mínimo (senão o agente fica liga-desliga a cada corte).')
    if 'estado' in d:
        if d['estado'] not in ESTADOS:
            raise ErroAutomacao('Situação inválida.')
        novo['estado'] = d['estado']
    return novo


def salvar(d: dict, versao=None, quem: str = 'site') -> dict:
    with _LOCK:
        atual = config()
        if versao is not None and int(versao) != int(atual['versao']):
            raise ErroAutomacao('Outra tela mudou a automação. Recarregue e tente de novo.', 409)
        novo = validar(d, atual)
        novo.update(versao=int(atual['versao']) + 1, atualizado=time.time(), por=str(quem)[:80])
        db.kv_gravar('automacao', novo)
    if novo['estado'] != atual['estado']:
        evento('central', 'estado', novo['estado'], f'De "{atual["estado"]}" para "{novo["estado"]}" por {quem}.')
    db.evento(quem, 'automacao_config', 'automacao', {k: novo[k] for k in ('estado', 'modo', 'cortes', 'linhas')})
    return novo


def ativa() -> bool:
    return config()['estado'] == 'ativa'


def pausar(quem: str = 'site') -> dict:
    return salvar({'estado': 'pausada'}, None, quem)


def retomar(quem: str = 'site') -> dict:
    return salvar({'estado': 'ativa'}, None, quem)


# ---------------------------------------------------------------- memória curta (histerese, último lote, última decisão)
def _mem() -> dict:
    v = db.kv('automacao_mem')
    v = v if isinstance(v, dict) else {}
    v.setdefault('repondo', {})
    v.setdefault('ultimo', {})
    v.setdefault('decisao', {})
    return v


def _mem_gravar(m: dict):
    db.kv_gravar('automacao_mem', m)


def evento(agente: str, tipo: str, decisao: str, motivo: str, dados: dict | None = None):
    db.executar('INSERT INTO automacao_eventos (t, agente, tipo, decisao, motivo, dados) VALUES (?,?,?,?,?,?)', time.time(), agente[:20], tipo[:40],
                decisao[:40], motivo[:400], json.dumps(dados or {}, ensure_ascii=False)[:2000])


def eventos(limite: int = 100, agente: str = '') -> list:
    sql, a = 'SELECT * FROM automacao_eventos', []
    if agente:
        sql += ' WHERE agente=?'
        a.append(agente)
    return db.todos(sql + ' ORDER BY n DESC LIMIT ?', *a, max(1, min(int(limite), 500)))


# ---------------------------------------------------------------- estoque de cortes (Agente 1)
def taxa_aprovacao(cortes: list) -> tuple[float, int]:
    """Dos cortes dos últimos 60 dias que o diretor já julgou, quantos passaram. Poucos dados: usa 0,6 e diz que é estimativa."""
    ini = time.time() - 60 * 86400
    julgados = [c for c in cortes if c.get('criado', 0) >= ini and c['status'] in ('pronto', 'agendado', 'postado', 'reprovado')]
    if len(julgados) < 5:
        return TAXA_PADRAO, len(julgados)
    ok = sum(1 for c in julgados if c['status'] != 'reprovado')
    return max(0.1, ok / len(julgados)), len(julgados)


def demanda_por_dia() -> tuple[float, str]:
    """Quantos vídeos DIFERENTES a programação pede por dia (o mesmo vídeo pode ir para várias redes): a rede que mais pede manda."""
    try:
        import agenda_postagem as ag2
        from datetime import date, timedelta
        por_rede: dict = {}
        hoje = date.today()
        for a in ag2.listar():
            if not a.get('enabled'):
                continue
            tot = 0
            for i in range(7):
                dia = hoje + timedelta(days=i)
                try:
                    tot += ag2.meta_do_dia(a, dia.weekday(), dia.isoformat())
                except Exception:  # noqa: BLE001
                    pass
            for rede in a.get('platforms') or [a.get('platform')]:
                if rede:
                    por_rede[rede] = por_rede.get(rede, 0) + tot
        if por_rede:
            return max(por_rede.values()) / 7, 'programação diária'
    except Exception:  # noqa: BLE001
        pass
    try:
        import agente as ag
        return ag.config()['cortes']['por_semana'] / 7, 'meta por semana do Agente 1'
    except Exception:  # noqa: BLE001
        return 1.0, 'padrão'


def _cert_ok(c: dict) -> bool:
    import pipeline as pl
    if not pl.ligado():
        d = ((c.get('qa') or {}).get('diretor') or {})
        return d.get('aprovado', True) is not False
    import agenda_postagem as ag2
    sha = ag2._sha(c)
    return bool(sha and pl.certificado(sha))


def estoque_cortes(cortes: list | None = None, ocupado: bool | None = None) -> dict:
    import agente as ag
    cortes = ag.estado()['cortes'] if cortes is None else cortes
    co = ag.config()['cortes']
    disponiveis = [c for c in cortes if c['status'] == 'pronto' and _cert_ok(c)]
    reservados = sum(1 for c in cortes if c['status'] == 'agendado')
    taxa, amostra = taxa_aprovacao(cortes)
    ocupado = ag.OCUPADO.locked() if ocupado is None else ocupado
    previsto = round(co['por_video'] * taxa, 1) if ocupado else 0
    dem, fonte = demanda_por_dia()
    return {'disponiveis': len(disponiveis), 'reservados': reservados, 'em_producao_previsto': previsto, 'taxa_aprovacao': round(taxa, 2),
            'taxa_amostra': amostra, 'taxa_estimada': amostra < 5, 'efetivo': round(len(disponiveis) + previsto, 1),
            'demanda_dia': round(dem, 2), 'demanda_fonte': fonte, 'cobertura_dias': round(len(disponiveis) / dem, 1) if dem > 0 else None}


def decidir_cortes(cfg: dict, est: dict, repondo: bool, agora: float, ultima_rodada: float, ultima_busca: float) -> dict:
    """Função pura: o que o Agente 1 deve fazer agora e por quê."""
    c = cfg['cortes']
    efetivo = est['efetivo']
    if efetivo < c['minimo']:
        repondo = True
    elif efetivo >= c['alvo']:
        repondo = False
    if not repondo:
        return {'acao': 'nada', 'repondo': False, 'quantos': 0,
                'motivo': f'Estoque de {est["disponiveis"]} corte(s) aprovado(s) dá conta (mínimo {c["minimo"]}, alvo {c["alvo"]}). Não procuro nem corto agora.'}
    deficit = max(1, int(round(c['alvo'] - efetivo)))
    falta_cortar = max(1, math.ceil(deficit / max(est['taxa_aprovacao'], 0.1)))     # para sobrar 'deficit' aprovados, corta um pouco mais
    espera = c['cooldown_min'] * 60 - (agora - ultima_rodada)
    if espera > 0:
        return {'acao': 'esperar', 'repondo': True, 'quantos': falta_cortar,
                'motivo': f'Faltam {deficit} para o alvo, mas a última rodada foi há pouco. Próxima em {int(espera // 60) + 1} min.'}
    if agora - ultima_busca > c['busca_horas'] * 3600:
        return {'acao': 'buscar_canais', 'repondo': True, 'quantos': falta_cortar,
                'motivo': f'Estoque baixo ({est["disponiveis"]}): primeiro procuro canais novos (última busca há mais de {c["busca_horas"]} h).'}
    return {'acao': 'cortar', 'repondo': True, 'quantos': falta_cortar,
            'motivo': f'Estoque de {est["disponiveis"]} abaixo do alvo {c["alvo"]}: corto até {falta_cortar} (taxa de aprovação {int(est["taxa_aprovacao"] * 100)}%).'}


def decisao_cortes() -> dict | None:
    """Chamado pelo relógio do Agente 1. None = central desligada ou sem controle por estoque (regra antiga da meta semanal)."""
    cfg = config()
    if cfg['estado'] == 'desligada' or not cfg['cortes']['controle_estoque']:
        return None
    if cfg['estado'] == 'pausada':
        return {'acao': 'nada', 'repondo': False, 'quantos': 0, 'motivo': 'Automação pausada por você.'}
    import agente as ag
    marcas = ag.estado()['marcas']
    m = _mem()
    est = estoque_cortes()
    d = decidir_cortes(cfg, est, bool(m['repondo'].get('cortes')), time.time(), marcas.get('tentativa', 0), marcas.get('busca', 0))
    _lembrar(m, 'cortes', d, est)
    return d


def _lembrar(m: dict, chave: str, d: dict, est: dict | None = None):
    """Grava a histerese e registra no histórico só quando a decisão MUDA (não enche o histórico a cada 2 minutos)."""
    antes = m['decisao'].get(chave)
    m['repondo'][chave] = d['repondo']
    if antes != d['acao']:
        m['decisao'][chave] = d['acao']
        agente = 'agente1' if chave == 'cortes' else 'agente3'
        evento(agente, 'decisao', d['acao'], d['motivo'], {'chave': chave, 'estoque': est})
    _mem_gravar(m)


# ---------------------------------------------------------------- linhas de conteúdo (Agente 3)
def decidir_linha(lcfg: dict, est: dict, repondo: bool, agora: float, ultimo_lote: float, cooldown_min: int, aceitas: int, hoje: int) -> dict:
    """Função pura: uma linha em modo contínuo começa um lote novo? Conta o que já está em produção e esperando você, para não produzir demais."""
    if lcfg['estado'] != 'ativa':
        return {'acao': 'nada', 'repondo': False, 'n': 0, 'motivo': 'Linha pausada.'}
    if lcfg['modo_execucao'] != 'continuo':
        return {'acao': 'nada', 'repondo': False, 'n': 0, 'motivo': 'Lote único: só começa quando você pede.'}
    mn, alvo = lcfg['estoque']['minimo'], lcfg['estoque']['alvo']
    efetivo = est['livres'] + est['em_producao'] + est['esperando_voce']
    if efetivo < mn:
        repondo = True
    elif efetivo >= alvo:
        repondo = False
    if not repondo:
        return {'acao': 'nada', 'repondo': False, 'n': 0, 'motivo': f'{est["livres"]} pronto(s) + {est["em_producao"]} em produção: estoque dá conta (mínimo {mn}, alvo {alvo}).'}
    if est['esperando_voce'] >= max(alvo, 1):
        return {'acao': 'nada', 'repondo': True, 'n': 0, 'motivo': f'{est["esperando_voce"]} vídeo(s) esperando você. Não começo mais até você olhar.'}
    folga = lcfg['limite_dia'] - hoje
    if folga <= 0:
        return {'acao': 'nada', 'repondo': True, 'n': 0, 'motivo': f'Já começou {lcfg["limite_dia"]} vídeo(s) em 24 h (o seu limite).'}
    espera = cooldown_min * 60 - (agora - ultimo_lote)
    n = max(1, min(alvo - efetivo, lcfg['quantidade_lote'], folga))
    if espera > 0:
        return {'acao': 'esperar', 'repondo': True, 'n': n, 'motivo': f'Faltam {alvo - efetivo} para o alvo. Próximo lote em {int(espera // 60) + 1} min.'}
    if aceitas < n:
        if lcfg['modo_pautas'] == 'automatico':
            return {'acao': 'planejar', 'repondo': True, 'n': n, 'motivo': f'Só {aceitas} pauta(s) aceita(s): planejo pautas novas e começo {n} vídeo(s).'}
        if aceitas == 0:
            return {'acao': 'nada', 'repondo': True, 'n': 0, 'motivo': 'Sem pauta aceita. Aceite pautas na linha (modo supervisionado/manual).'}
        n = aceitas
    return {'acao': 'lote', 'repondo': True, 'n': n, 'motivo': f'Estoque {efetivo} abaixo do alvo {alvo}: começo {n} vídeo(s).'}


def _dados_linha(lid: str, cfg: dict, m: dict) -> tuple:
    import linhas_conteudo as lc
    lcfg = lc._linha(lid)
    est = lc.estoque(lid)
    aceitas = db.um("SELECT COUNT(*) n FROM conteudo_pautas WHERE linha=? AND status='aceita'", lid)['n']
    return lcfg, est, aceitas, lc.iniciados_hoje(lid)


def _decisoes_linhas(cfg: dict, m: dict, agora: float) -> list:
    out = []
    for r in db.todos('SELECT id FROM linhas_conteudo ORDER BY criado'):
        lcfg, est, aceitas, hoje = _dados_linha(r['id'], cfg, m)
        d = decidir_linha(lcfg, est, bool(m['repondo'].get('linha:' + r['id'])), agora, m['ultimo'].get('linha:' + r['id'], 0),
                          cfg['linhas']['cooldown_min'], aceitas, hoje)
        out.append({'linha': r['id'], 'titulo': lcfg['titulo'], 'estoque': est, 'decisao': d})
    return out


def _produzir_linha(lid: str, d: dict, ia=None, produzir=None):
    import linhas_conteudo as lc
    try:
        if d['acao'] == 'planejar':
            lc.planejar_pautas(lid, d['n'], ia=ia)
        r = lc.iniciar_lote(lid, d['n'], 'automação', 'estoque abaixo do alvo', produzir=produzir)
        evento('agente3', 'lote', 'iniciado', f'{len(r["episodios"])} vídeo(s) começado(s) na linha.', {'linha': lid, 'lote': r['lote']})
    except Exception as e:  # noqa: BLE001
        evento('agente3', 'lote', 'falhou', str(e)[:300], {'linha': lid})


def ciclo(ia=None, produzir=None, em_fundo: bool = True) -> dict:
    """Roda no relógio (a cada poucos minutos). Pausada ou desligada: não faz nada."""
    cfg = config()
    if cfg['estado'] != 'ativa':
        return {'ativa': False}
    if not _LOCK.acquire(blocking=False):
        return {'ocupado': True}
    try:
        import linhas_conteudo as lc
        res = {'ativa': True, 'aprovados_auto': lc.aprovar_automaticos(), 'lotes': []}
        agora = time.time()
        m = _mem()
        for x in _decisoes_linhas(cfg, m, agora):
            d = x['decisao']
            _lembrar(m, 'linha:' + x['linha'], d, x['estoque'])
            if d['acao'] in ('planejar', 'lote'):
                m['ultimo']['linha:' + x['linha']] = agora      # marca antes: um erro não vira tentativa a cada ciclo
                _mem_gravar(m)
                res['lotes'].append(x['linha'])
                if em_fundo:
                    threading.Thread(target=_produzir_linha, args=(x['linha'], d, ia, produzir), daemon=True).start()
                else:
                    _produzir_linha(x['linha'], d, ia, produzir)
        return res
    finally:
        _LOCK.release()


def simular() -> dict:
    """O que a automação faria AGORA, com os números reais, sem gravar nada e sem chamar nenhum agente."""
    cfg = config()
    m = _mem()
    agora = time.time()
    out = {'estado': cfg['estado'], 'cortes': None, 'linhas': [], 'aviso': ''}
    if cfg['estado'] != 'ativa':
        out['aviso'] = 'A automação está ' + ('desligada' if cfg['estado'] == 'desligada' else 'pausada') + '. Abaixo, o que ela faria se estivesse ligada.'
    try:
        import agente as ag
        marcas = ag.estado()['marcas']
        est = estoque_cortes()
        if cfg['cortes']['controle_estoque']:
            d = decidir_cortes(cfg, est, bool(m['repondo'].get('cortes')), agora, marcas.get('tentativa', 0), marcas.get('busca', 0))
        else:
            d = {'acao': 'meta_semanal', 'motivo': 'Controle por estoque desligado: o Agente 1 segue a meta de cortes por semana.'}
        ligado = ag.config()['cortes']['ligado']
        if not ligado:
            d = dict(d, motivo=d['motivo'] + ' (O Agente 1 está desligado na aba dele: nada roda até você ligar.)')
        out['cortes'] = {'estoque': est, 'decisao': d, 'agente_ligado': ligado}
    except Exception as e:  # noqa: BLE001
        out['cortes'] = {'erro': str(e)[:200]}
    out['linhas'] = _decisoes_linhas(cfg, m, agora)
    return out


# ---------------------------------------------------------------- painel
def resumo() -> dict:
    import pipeline as pl
    cfg = config()
    agora = time.time()
    proximas = db.todos("SELECT id, rede, conta, data_local, hora_local, quando_utc, estado, ref FROM posting_slots WHERE quando_utc>? "
                        "AND estado IN ('agendado','reservado','vazio','aguardando_aprovacao') ORDER BY quando_utc LIMIT 8", agora - 60)
    try:
        ec = estoque_cortes()
    except Exception as e:  # noqa: BLE001
        ec = {'erro': str(e)[:200], 'disponiveis': 0}
    linhas = []
    try:
        import linhas_conteudo as lc
        linhas = [lc.resumo(r['id']) for r in db.todos('SELECT id FROM linhas_conteudo ORDER BY criado')]
    except Exception as e:  # noqa: BLE001
        print('automacao: linhas', e)
    rodando = db.um("SELECT COUNT(*) n FROM jobs WHERE status='rodando'")['n']
    na_fila = db.um("SELECT COUNT(*) n FROM jobs WHERE status IN ('na_fila','agendado','aguardando_tentativa')")['n']
    falhas = db.um("SELECT COUNT(*) n FROM jobs WHERE status='falhou' AND terminado>?", agora - 86400)['n']
    falhas += db.um("SELECT COUNT(*) n FROM posting_slots WHERE estado='erro' AND atualizado>?", agora - 86400)['n']
    revisao = db.um("SELECT COUNT(*) n FROM pipeline_runs WHERE estado='manual_review_required'")['n']
    try:
        import aprovacoes as apv
        espera_voce = len(apv.pendentes())
    except Exception:  # noqa: BLE001
        espera_voce = 0
    return {
        'config': cfg, 'nomes_modo': NOMES_MODO, 'presets': PRESETS, 'esteira_ligada': pl.ligado(),
        'indicadores': {'estoque_cortes': ec.get('disponiveis', 0), 'estoque_linhas': sum(x['estoque']['livres'] for x in linhas),
                        'rodando': rodando, 'na_fila': na_fila, 'revisao_manual': revisao, 'esperando_voce': espera_voce, 'falhas_24h': falhas},
        'proximas': proximas, 'estoque_cortes': ec, 'linhas': linhas, 'eventos': eventos(15),
    }


def sugestoes() -> list:
    """Regras simples sobre os SEUS números (não é IA). Cada sugestão diz de onde veio e pode ser aplicada ou ignorada."""
    cfg = config()
    out = []
    try:
        ec = estoque_cortes()
    except Exception:  # noqa: BLE001
        return out
    dem = ec['demanda_dia']
    c = cfg['cortes']
    if dem > 0:
        ideal_min = max(1, int(round(dem * 3)))           # 3 dias de folga
        ideal_alvo = max(ideal_min + 1, int(round(dem * 7)))  # uma semana
        if abs(c['minimo'] - ideal_min) >= 2 or abs(c['alvo'] - ideal_alvo) >= 3:
            out.append({'id': 'estoque_pela_agenda', 'titulo': f'Mínimo {ideal_min} e alvo {ideal_alvo} cortes',
                        'porque': f'A sua programação pede cerca de {dem:.1f} vídeo(s) por dia ({ec["demanda_fonte"]}). Mínimo = 3 dias, alvo = 7 dias.',
                        'mudanca': {'cortes': {'minimo': ideal_min, 'alvo': ideal_alvo}}})
    if not ec['taxa_estimada'] and ec['taxa_aprovacao'] < 0.4:
        out.append({'id': 'taxa_baixa', 'titulo': 'Muitos cortes reprovados pelo diretor',
                    'porque': f'Só {int(ec["taxa_aprovacao"] * 100)}% dos últimos {ec["taxa_amostra"]} cortes passaram. Vale revisar os canais ou a duração dos cortes antes de cortar mais.',
                    'mudanca': None})
    if ec['disponiveis'] > c['alvo'] * 2:
        out.append({'id': 'estoque_alto', 'titulo': 'Estoque muito acima do alvo',
                    'porque': f'{ec["disponiveis"]} cortes prontos para um alvo de {c["alvo"]}. Cortes antigos podem perder o assunto: aumente os horários na programação ou baixe o alvo.',
                    'mudanca': None})
    return out


def aplicar_sugestoes(ids: list, quem: str = 'site') -> dict:
    mud: dict = {}
    for s in sugestoes():
        if s['id'] in ids and s['mudanca']:
            for k, v in s['mudanca'].items():
                mud.setdefault(k, {}).update(v)
    if not mud:
        raise ErroAutomacao('Nenhuma sugestão aplicável foi escolhida.')
    return salvar(mud, None, quem)


# ---------------------------------------------------------------- relógio
_relogio = {'on': False}


def iniciar():
    if _relogio['on']:
        return
    _relogio['on'] = True

    def laco():
        time.sleep(30)
        while True:
            try:
                ciclo()
            except Exception as e:  # noqa: BLE001
                print('central de automação:', e)
            time.sleep(300)
    threading.Thread(target=laco, daemon=True).start()
