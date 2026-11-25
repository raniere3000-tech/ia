"""Rotas /api/v1 (projetos no servidor, aparelhos, fila, rotinas, Agente 3, aprovações, backups).

Autenticação: cabeçalho X-Sessao (sessão do aparelho) ou X-Token (senha do servidor, compatibilidade).
Arquivos para o <video> do navegador usam link temporário assinado (?exp=&sig=), nunca a senha na URL.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import agendador
import aprovacoes as apv
import autenticacao as au
import backups
import coordenador as co
import criativo as cri
import banco as db
import emails
import descricao as descricao_mod
import diretor
import storyboard
import estilos_codigo as ec
import exportacao
import fila
import hardware
import postagem as pg
import produtor
import projetos as pj
import renderizador as rd
import rotas_esteira
import thumbnails as th
import download_lote as dl
import series as srs
from skills import catalogo as skcat
from skills import roteador as skrot

ABERTAS = {('POST', '/api/v1/sessao/login'), ('POST', '/api/v1/pareamento/completar'), ('GET', '/api/v1/saude')}
LIMITE_PEDACO = 8 * 1024 * 1024


class Resposta(Exception):
    """Resposta que não é JSON (arquivo)."""
    def __init__(self, arquivo: Path, mime: str, nome: str = '', baixar: bool = False):
        super().__init__('arquivo')
        self.arquivo, self.mime, self.nome, self.baixar = arquivo, mime, nome, baixar


def limite_corpo(metodo: str, rota: str) -> int:
    if metodo == 'PUT' and rota.startswith('/api/v1/uploads/'):
        return LIMITE_PEDACO
    if rota.startswith('/api/v1/projetos') or rota.startswith('/api/v1/agente3'):
        return 6 * 1024 * 1024          # dados de projeto (storyboard, legendas) — os arquivos vão por upload
    return 200000


def _int(v, padrao=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return padrao


def _f(v, padrao=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return padrao


def _arquivo_assinado(caminho: str, q: dict) -> bool:
    return bool(q.get('sig')) and au.url_assinada_ok(caminho, q.get('exp', [''])[0], q.get('sig', [''])[0])


def links_render(r: dict | None) -> dict:
    """Links temporários (6 h) para assistir o vídeo e a prévia no site."""
    if not r:
        return {}
    out = {}
    for nome, aid in (r.get('assets') or {}).items():
        out[nome] = au.assinar_url(f'/api/v1/assets/{aid}', 6 * 3600)
    return out


def _quando(d: dict) -> float | None:
    """quando: 'agora' | 'daqui' (minutos) | 'data' (timestamp)."""
    q = d.get('quando') or 'agora'
    if q == 'daqui':
        return time.time() + max(1, _int(d.get('minutos'), 60)) * 60
    if q == 'data':
        t = _f(d.get('data'))
        if not t or t < time.time() - 60:
            raise pj.ErroProjeto(400, 'Escolha uma data no futuro.')
        return t
    return None


# ---------------------------------------------------------------- render de demonstração dos estilos
def job_demo(ctx):
    eid, fmt, var = ctx.dados['estilo'], ctx.dados.get('formato', '9:16'), ctx.dados.get('variante', '')
    chave = f'demo:{eid}:{fmt}:{ec.VERSAO_MOTOR}' + (f':{var}' if var else '')
    if db.kv(chave) and not ctx.dados.get('refazer'):      # refazer: a demonstração antiga só é trocada quando a nova passar
        return {'resultado': db.kv(chave), 'etapa': 'Pronto'}
    if not ec.utilizavel(eid, False):
        raise produtor.ErroProdutor('Este estilo não roda neste servidor ainda.', True)
    W, H = ec.FORMATOS[fmt]
    pasta = pg.DADOS / 'demos' / (f'{eid}-{fmt.replace(":", "x")}' + (f'-{var}' if var else '') + (f'-r{int(time.time())}' if ctx.dados.get('refazer') else ''))
    shutil.rmtree(pasta, ignore_errors=True)        # (refazer usa outra pasta: o arquivo da demonstração antiga continua valendo até a nova passar)
    pasta.mkdir(parents=True)
    saida = pasta / 'demo.mp4'
    ctx.progresso(10, 'Desenhando as peças' if eid not in ec.motor3d.ESTILOS_3D else 'Desenhando o fundo 3D (só na primeira vez, uns 30 s)')
    t0 = time.time()
    cena = ec.demo_cena(eid, var)
    if eid in ec.ANIMADOS:
        # fala de mentira (sílabas em volume e timbre variados), só para a boca mexer na demonstração; o vídeo sai sem som
        fala = pasta / 'fala.wav'
        rd.rodar(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                  "aevalsrc='0.6*sin(2*PI*(220+180*sin(2*PI*0.7*t))*t)*max(0,sin(2*PI*3.3*t))*lt(mod(t,1.6),1.2)':s=24000:d=5",
                  '-ac', '1', '-c:a', 'pcm_s16le', str(fala)], tempo_max=60)
        cena['_audio'] = str(fala)
    ec.preparar(eid, W, H, 5.0, None, ctx.cancelado, (lambda x: ctx.progresso(10 + 60 * x, 'Desenhando em 3D')) if eid == 'animado3d' else None, cena=cena)
    cmd = ec.montar(eid, cena, W, H, 5.0, pasta, None, None, saida)
    ctx.progresso(30, 'Renderizando 5 segundos')
    rd.rodar(cmd, ctx.cancelado, tempo_max=900)
    fila.medir('render_cena', (time.time() - t0) / 5.0)
    conf = rd.conferir(saida, pasta, {'largura': W, 'altura': H, 'duracao': 5.0}, ctx.cancelado)
    if not conf['ok']:
        raise produtor.ErroProdutor('A demonstração não passou na conferência: ' + '; '.join(conf['erros']))
    a = pj.registrar_asset(saida, f'demo-{eid}-{fmt.replace(":", "x")}{"-" + var if var else ""}.mp4', 'video/mp4', '', 'demo')['asset']
    tec, lim = ec.TECNOLOGIA.get(eid, ('', ''))
    r = {'asset': a['id'], 'segundos': round(time.time() - t0, 1), 'avisos': conf['avisos'], 'formato': fmt, 'motor': ec.VERSAO_MOTOR,
         'tecnologia': tec, 'limites': lim, 'onde': 'celular' if hardware.e_android() else 'fora do celular (tempo não vale para o Android)',
         'seg_por_seg': round((time.time() - t0) / 5.0, 2)}
    db.kv_gravar(chave, r)
    return {'resultado': r, 'etapa': 'Pronto'}


_FICHA: dict = {}


def _estilos_com_3d() -> list:
    """Catálogo com o estado HONESTO do 3D de personagens: se o teste do 3D rodou no celular, o número medido entra
    no texto; 'beta_lento' avisa que serve só para cenas curtas; sem medida no Android, diz que não foi medido."""
    est = ec.catalogo()
    l3 = db.kv('diagnostico_3d') or {}
    for e in est:
        if e['id'] != 'animado3d' or e['status'] == 'indisponivel':
            continue
        t3 = next((t for t in l3.get('testes', []) if t.get('estilo') == 'animado3d'), None)
        if l3.get('ambiente') == 'android' and t3:
            if l3.get('estado') == 'indisponivel':
                e.update(status='indisponivel', servidor=False, formatos=[])
            e['descricao'] += f' Medido neste celular: {t3.get("seg_por_seg", "?")} s por segundo de vídeo. {l3.get("conclusao", "")}'
        e['estado_3d'] = l3.get('estado') or 'não medido no celular'
    return est


def _aparelho() -> dict:
    """Ficha do aparelho (guardada 10 min: lê FFmpeg e o sistema), último laudo do teste e o teste em andamento."""
    if not _FICHA or time.time() - _FICHA.get('t', 0) > 600:
        _FICHA.update(t=time.time(), ficha=hardware.ficha())
    j = db.um("SELECT id, status, etapa, progresso, erro FROM jobs WHERE tipo='aparelho.testar' ORDER BY criado DESC LIMIT 1")
    return {'ficha': _FICHA['ficha'], 'laudo': hardware.ultimo_laudo(), 'job': j}


def _chave_pose(dados: dict, d: dict) -> str:
    import rig2d
    p = rig2d.validar_personagem(dados)
    return f'pose:{rig2d.assinatura(p)}:{d.get("pose", "")}:{d.get("objeto", "")}:{d.get("expressao", "")}:{ec.VERSAO_MOTOR}'


def job_pose(ctx):
    """Prévia real de uma pose (S3): o motor 2D renderiza 2 s do personagem com a pose/objeto e o quadro do meio vira imagem."""
    import base64
    import rig2d
    d = ctx.dados
    p = srs.obter_personagem(d['personagem'])
    chave = _chave_pose(p['dados'], d)
    if db.kv(chave):
        return {'resultado': {'png': db.kv(chave)}, 'etapa': 'Pronto'}
    acoes = []
    if d.get('pose') in rig2d.POSES:
        acoes.append({'t': 0.1, 'tipo': 'pose', 'pose': d['pose']})
    if d.get('objeto') in rig2d.OBJETOS:
        acoes.append({'t': 0.1, 'tipo': 'segurar', 'objeto': d['objeto']})
    cena = ec.validar_cena({'titulo': '', 'texto': '', 'personagem': 'x', 'cenario_id': 'previa',
                            'elenco': [{'personagem_id': 'x', 'posicao': 'centro', 'expressao': d.get('expressao') or 'neutro', 'acoes': acoes}],
                            'planos': [{'plano': 'WS'}]})
    cena['_personagens'] = {'x': p['dados']}
    cena['_cenario'] = {'tipo': 'vazio'}
    pasta = pg.DADOS / 'rig2d' / 'poses' / hashlib.sha256(chave.encode()).hexdigest()[:16]
    shutil.rmtree(pasta, ignore_errors=True)
    pasta.mkdir(parents=True)
    W, H = 360, 640
    ctx.progresso(20, 'Desenhando a pose com o motor 2D')
    ec.preparar('animado2d', W, H, 2.0, None, ctx.cancelado, cena=cena)
    rd.rodar(ec.montar('animado2d', cena, W, H, 2.0, pasta, None, None, pasta / 'pose.mp4'), ctx.cancelado, tempo_max=600)
    rd.rodar(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', '1.6', '-i', str(pasta / 'pose.mp4'), '-frames:v', '1', str(pasta / 'pose.png')],
             ctx.cancelado, tempo_max=60)
    png = 'data:image/png;base64,' + base64.b64encode((pasta / 'pose.png').read_bytes()).decode()
    db.kv_gravar(chave, png)
    shutil.rmtree(pasta, ignore_errors=True)
    return {'resultado': {'png': png}, 'etapa': 'Pronto'}


def pedir_pose(pid: str, d: dict) -> dict:
    import rig2d
    p = srs.obter_personagem(pid)
    d = {'personagem': pid, 'pose': d.get('pose') if d.get('pose') in rig2d.POSES else '',
         'objeto': d.get('objeto') if d.get('objeto') in rig2d.OBJETOS else '',
         'expressao': d.get('expressao') if d.get('expressao') in rig2d.EXPRESSOES else 'neutro'}
    chave = _chave_pose(p['dados'], d)
    if db.kv(chave):
        return {'png': db.kv(chave)}
    j = db.um('SELECT * FROM jobs WHERE chave LIKE ? ORDER BY criado DESC LIMIT 1', chave + '%')
    if not j or j['status'] in ('falhou', 'cancelado'):
        j = fila.enfileirar('personagem.pose', agente='series', dados=d, titulo='Prévia de pose do personagem',
                            chave=chave + ('' if not j else ':' + str(int(time.time()))), max_tentativas=1)
    return {'job': j['id'], 'status': j['status'], 'etapa': j.get('etapa') or '', 'erro': j.get('erro') or ''}


def visemas_audio(d: dict) -> dict:
    """Prévia da boca (S3): os níveis que o motor usaria para uma fala gravada, quadro a quadro (12 por segundo)."""
    import rig2d
    import tempfile
    a = pj.asset(str(d.get('asset') or ''))
    with tempfile.TemporaryDirectory() as t:
        wav = Path(t) / 'fala.wav'
        rd.rodar(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', a['caminho'], '-ac', '1', '-ar', '24000', '-t', '60', str(wav)], tempo_max=120)
        dur = rd.duracao(wav)
        niveis, modo = rig2d.visemas(wav, dur, str(d.get('texto') or '')[:600])
    return {'dur': round(dur, 2), 'passo': round(1 / 12, 4), 'niveis': niveis, 'modo': modo,
            'formas': ['fechada', 'pouco aberta', 'aberta (a)', 'redonda (o, u)', 'larga (e, i)'],
            'limites': 'Aproximação pelo volume e pelas vogais do texto; não é leitura de fonemas.'}


def quadros_render(pid: str, d: dict) -> dict:
    """S4: o quadro de verdade de cada versão do vídeo num instante (para ver a falha e comparar antes/depois).
    Só versões deste projeto; o arquivo é o render guardado. Quadro pequeno (360 px), guardado em cache no disco."""
    import base64
    pj.obter(pid)
    try:
        t = max(0.0, min(3600.0, float(d.get('t') or 0)))
    except (TypeError, ValueError):
        raise pj.ErroProjeto(400, 'Instante inválido.')
    ids = [re.sub(r'[^\w]', '', str(x))[:20] for x in (d.get('renders') or [])][:3]
    out = {}
    for rid in ids:
        r = db.um('SELECT id, versao, arquivo, duracao FROM renders WHERE id=? AND projeto=?', rid, pid)
        if not r or not Path(r['arquivo']).exists():
            out[rid] = {'erro': 'Essa versão do vídeo não está mais guardada no celular.'}
            continue
        tt = min(t, max(0.0, (r['duracao'] or 0) - 0.05))
        cache = Path(r['arquivo']).with_name(f'{rid}.q{int(tt * 10)}.jpg')
        if not cache.exists():
            try:
                rd.rodar(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{tt:.2f}', '-i', r['arquivo'], '-frames:v', '1', '-vf', 'scale=360:-2',
                          '-q:v', '5', str(cache)], tempo_max=40)
            except rd.ErroRender:
                out[rid] = {'erro': 'Não consegui tirar o quadro desse instante.'}
                continue
        out[rid] = {'versao': r['versao'], 't': round(tt, 2), 'jpg': 'data:image/jpeg;base64,' + base64.b64encode(cache.read_bytes()).decode()}
    return {'quadros': out}


def job_skills(ctx):
    if ctx.dados.get('oque') == 'atualizacoes':
        r = skcat.atualizacoes(ctx)
        return {'resultado': {'candidatas': len(r['candidatas']), 'erros': r['erros'][:10]}, 'etapa': 'Pronto'}
    r = skcat.instalar(ctx.dados.get('ids') or None, ctx)
    return {'resultado': {'instaladas': len(r['instaladas']), 'ja_estavam': len(r['ja_estavam']), 'falhas': r['falhas'][:20]},
            'etapa': f'{len(r["instaladas"]) + len(r["ja_estavam"])} prontas, {len(r["falhas"])} com problema'}


def _skills(metodo: str, caminho: str, q: dict, corpo, quem: str = '') -> dict:
    rota = (metodo, caminho)
    if rota == ('GET', '/api/v1/skills'):
        p = lambda k: q.get(k, [''])[0]
        return {'skills': skcat.listar(p('agente'), p('estado'), p('busca')), 'resumo': skcat.resumo()}
    if rota == ('POST', '/api/v1/skills/instalar'):
        ids = [str(x) for x in (corpo().get('ids') or []) if isinstance(x, str)][:200]
        estranhas = [i for i in ids if i not in skcat.manifesto()['por_id']]
        if estranhas:   # só o que está no manifesto fixado (commit + hash) pode ser instalado
            db.evento(quem or 'skills', 'skill_recusada', 'catalogo', {'ids': estranhas[:10]})
            raise skcat.ErroSkill(400, 'Skill fora do catálogo autorizado: ' + ', '.join(estranhas[:5]) + '.')
        j = fila.enfileirar('skills.instalar', agente='skills', dados={'ids': ids}, titulo='Instalar skills (só texto)',
                            chave='skills-instalar-' + str(int(time.time() // 30)), max_tentativas=2)
        return {'job': j['id']}
    if rota == ('POST', '/api/v1/skills/validar'):
        return skcat.verificar()
    if rota == ('POST', '/api/v1/skills/atualizacoes'):
        j = fila.enfileirar('skills.instalar', agente='skills', dados={'oque': 'atualizacoes'}, titulo='Procurar versões novas das skills',
                            chave='skills-atualizacoes-' + str(int(time.time() // 30)), max_tentativas=1)
        return {'job': j['id']}
    if rota == ('GET', '/api/v1/skills/relatorio'):
        return skcat.relatorio(gravar=False)
    if rota == ('POST', '/api/v1/skills/conferir-catalogo'):
        return skcat.conferir_catalogo(json.loads(skcat.CATALOGO_118.read_text(encoding='utf-8')))
    if rota == ('POST', '/api/v1/skills/desfazer-lote'):
        return skcat.desfazer_lote()
    if rota == ('GET', '/api/v1/skills/ponta-a-ponta'):
        return {'consumidores': skrot.ponta_a_ponta()}
    if rota == ('GET', '/api/v1/skills/perfis'):
        return {'perfis': skrot.perfis(), 'limite_max': skrot.LIMITE_MAX}
    m = re.fullmatch(r'/api/v1/skills/perfis/([\w.]+)', caminho)
    if m and metodo == 'PUT':
        return skrot.salvar_perfil(m.group(1), corpo(), quem)
    m = re.fullmatch(r'/api/v1/skills/perfis/([\w.]+)/desfazer', caminho)
    if m and metodo == 'POST':
        return skrot.desfazer_perfil(m.group(1), quem)
    if rota == ('POST', '/api/v1/skills/selecionar'):
        d = corpo()
        if not d.get('perfil'):    # roteador: agente, tarefa, estilo, preferências, assets, permissão e custo máximo
            return skrot.escolher(d)
        return skrot.selecionar(str(d.get('perfil') or ''), [str(x) for x in (d.get('skills') or []) if isinstance(x, str)][:6])
    if rota == ('POST', '/api/v1/skills/usar'):
        # prévia do texto de apoio que entraria no pedido à IA; não roda nada e não muda conteúdo.
        # Só perfis de tarefas que existem no servidor (lista fechada); quem pediu fica no registro de eventos.
        d = corpo()
        perfil = str(d.get('perfil') or '')
        if perfil not in skrot.PERFIS:
            raise skcat.ErroSkill(403, 'Ação manual não permitida para este perfil.')
        extras = [str(x) for x in (d.get('skills') or []) if isinstance(x, str)][:6]
        estranhas = [x for x in extras if x not in skcat.manifesto()['por_id']]
        if estranhas:
            raise skcat.ErroSkill(400, 'Skill fora do catálogo autorizado: ' + ', '.join(estranhas[:5]) + '.')
        texto, usadas = skrot.orientacao(perfil, projeto_id=str(d.get('projeto') or '')[:40], origem='manual', extras=extras, registrar_carga=False)
        db.evento(quem or 'skills', 'skill_previa_manual', 'perfil:' + perfil, {'skills': usadas})
        return {'texto': texto, 'usadas': usadas, 'executa': False}
    if rota == ('GET', '/api/v1/skills/historico'):
        p = lambda k: q.get(k, [''])[0]
        return {'historico': skrot.historico(p('job_id'), p('projeto_id'), _int(p('limite') or '100', 100), p('etapa'), p('perfil'))}
    m = re.fullmatch(r'/api/v1/skills/([a-z0-9._-]+)(?:/(ativar|desativar|rollback|atualizar|testar-atualizacao))?', caminho)
    if m:
        sid, acao = m.groups()
        if metodo == 'GET' and not acao:
            return skcat.obter(sid)
        if metodo == 'POST' and acao in ('ativar', 'desativar'):
            return skcat.ativar(sid, acao == 'ativar')
        if metodo == 'POST' and acao == 'rollback':
            return skcat.rollback(sid)
        if metodo == 'POST' and acao == 'testar-atualizacao':
            return skcat.testar_atualizacao(sid)
        if metodo == 'POST' and acao == 'atualizar':
            return skcat.aplicar_atualizacao(sid)
    raise pj.ErroProjeto(404, 'Rota não encontrada.')


_PEDIDOS_IA: dict = {}


def _limite_ia(sid: str, por_hora: int = 30):
    """Freio simples de gasto: no máximo `por_hora` pedidos de proposta por aparelho em uma hora."""
    agora = time.time()
    lista = [t for t in _PEDIDOS_IA.get(sid or '-', []) if agora - t < 3600]
    if len(lista) >= por_hora:
        raise pj.ErroProjeto(429, 'Muitos pedidos de proposta na última hora. Espere um pouco para não gastar a cota da IA.')
    _PEDIDOS_IA[sid or '-'] = lista + [agora]


def _criativo(metodo: str, caminho: str, q: dict, corpo, quem: str, sid: str) -> dict:
    """Núcleo criativo: biblioteca compartilhada, Modelagem com IA e tendências. Nada aqui produz, cobra vídeo ou posta."""
    rota = (metodo, caminho)
    p = lambda k, padrao='': q.get(k, [padrao])[0]  # noqa: E731
    if rota == ('GET', '/api/v1/criativo/capacidades'):
        return cri.capacidades()
    if rota == ('GET', '/api/v1/criativo/formatos'):
        return cri.formatos_ia()
    if rota == ('GET', '/api/v1/criativo/biblioteca'):
        return cri.biblioteca(p('tipo'), p('q')[:80], _int(p('pagina', '1'), 1))
    if rota == ('POST', '/api/v1/criativo/biblioteca'):
        return cri.criar_asset(corpo(), quem)
    if rota == ('POST', '/api/v1/criativo/tendencias/pesquisar'):
        d = corpo()
        return cri.pesquisar_tendencias(d.get('filtros'), d.get('evidencias_radar'), bool(d.get('atualizar')))
    if rota == ('POST', '/api/v1/criativo/modelagem/propor'):
        _limite_ia(sid)
        return cri.propor(corpo(), quem)
    if rota == ('GET', '/api/v1/criativo/propostas'):
        return {'propostas': cri.listar_propostas(p('favoritas') == '1')}
    if rota == ('POST', '/api/v1/criativo/usar-no-projeto'):
        d = corpo()
        return cri.usar_no_projeto(str(d.get('projeto_id') or ''), d, quem)
    if rota == ('POST', '/api/v1/criativo/serie-completa'):
        _limite_ia(sid)
        return cri.pedir_serie_completa(corpo(), quem)
    if rota == ('POST', '/api/v1/criativo/transformar-em-serie'):
        return cri.transformar_em_serie(str(corpo().get('projeto_id') or ''), quem)
    m = re.fullmatch(r'/api/v1/criativo/propostas/(\w+)(?:/(salvar-modelo|aplicar|previa|duplicar))?', caminho)
    if m:
        prid, acao = m.groups()
        if not acao and metodo == 'GET':
            return cri.obter_proposta(prid)
        if not acao and metodo == 'PATCH':
            return cri.editar_proposta(prid, corpo())
        if acao == 'salvar-modelo' and metodo == 'POST':
            return cri.aplicar(prid, dict(corpo(), destino='biblioteca'), quem, quem)
        if acao == 'aplicar' and metodo == 'POST':
            return cri.aplicar(prid, corpo(), quem, quem)
        if acao == 'previa' and metodo == 'POST':
            return cri.previa(prid, corpo())
        if acao == 'duplicar' and metodo == 'POST':
            return cri.duplicar_proposta(prid, quem)
    m = re.fullmatch(r'/api/v1/criativo/assets/([\w-]+)(?:/(duplicar|versoes|previa))?', caminho)
    if m:
        aid, acao = m.groups()
        if aid.startswith('ca'):
            if not acao and metodo == 'GET':
                return cri.obter_asset(aid)
            if not acao and metodo == 'PATCH':
                return cri.atualizar_asset(aid, corpo(), quem)
            if acao == 'duplicar' and metodo == 'POST':
                return cri.duplicar_asset(aid, quem)
            if acao == 'versoes' and metodo == 'GET':
                return {'versoes': cri.versoes_asset(aid)}
            if acao == 'previa' and metodo == 'POST':
                return {'status': 'indisponivel', 'motivo': 'Este tipo de modelo é uma ficha em texto; não há desenho dele.'}
        else:   # personagem ou cenário das Séries (mesma biblioteca, sem copiar)
            if not acao and metodo == 'GET':
                try:
                    return srs.obter_personagem(aid)
                except srs.ErroSerie:
                    c = next((x for x in srs.listar_cenarios() if x['id'] == aid), None)
                    if not c:
                        raise pj.ErroProjeto(404, 'Modelo não encontrado.')
                    return c
            if acao == 'versoes' and metodo == 'GET':
                return {'versoes': srs.obter_personagem(aid)['versoes']}
            if acao == 'previa' and metodo == 'POST':
                c = next((x for x in srs.listar_cenarios() if x['id'] == aid), None)
                return srs.previa_cenario(c['dados']) if c else srs.folha(aid)
    raise pj.ErroProjeto(404, 'Rota não encontrada.')


def _series(metodo: str, caminho: str, q: dict, corpo, quem: str) -> dict:
    rota = (metodo, caminho)
    if rota == ('GET', '/api/v1/series'):
        return {'series': srs.listar(), 'acoes': {k: v[0] for k, v in srs.rig2d.ACOES.items()}, 'expressoes': list(srs.rig2d.EXPRESSOES)}
    if rota == ('POST', '/api/v1/series'):
        return srs.criar(corpo())
    m = re.fullmatch(r'/api/v1/series/(\w+)(?:/(temporadas|episodios|biblia))?', caminho)
    if m:
        sid, sub = m.groups()
        if not sub:
            if metodo == 'GET':
                return srs.obter(sid)
            if metodo in ('PATCH', 'PUT'):
                return srs.atualizar(sid, corpo())
        if sub == 'temporadas':
            if metodo == 'GET':
                return {'temporadas': srs.obter(sid)['temporadas']}
            if metodo == 'POST':
                return srs.criar_temporada(sid, corpo())
        if sub == 'episodios':
            if metodo == 'GET':
                return {'episodios': srs.listar_episodios(sid)}
            if metodo == 'POST':
                return srs.criar_episodio(sid, corpo(), quem)
        if sub == 'biblia':
            if metodo == 'GET':
                return {'biblia': srs.biblia(sid)}
            if metodo == 'PUT':
                return {'biblia': srs.salvar_biblia(sid, corpo().get('entradas'))}
    m = re.fullmatch(r'/api/v1/series/episodios/(\w+)/propostas', caminho)
    if m and metodo == 'POST':
        return {'biblia': srs.propostas_do_episodio(m.group(1))}
    if rota == ('GET', '/api/v1/personagens'):
        return {'personagens': srs.listar_personagens(q.get('serie', [''])[0])}
    if rota == ('POST', '/api/v1/personagens'):
        return srs.criar_personagem(corpo())
    if rota == ('POST', '/api/v1/personagens/previa'):
        return srs.folha('', corpo().get('dados') or {})
    if rota == ('POST', '/api/v1/personagens/visemas'):
        return visemas_audio(corpo())
    m = re.fullmatch(r'/api/v1/personagens/([a-z0-9-]+)/pose', caminho)
    if m and metodo == 'POST':
        return pedir_pose(m.group(1), corpo())
    m = re.fullmatch(r'/api/v1/personagens/([a-z0-9-]+)(?:/(rig|folha))?', caminho)
    if m:
        pid, sub = m.groups()
        if metodo == 'GET' and not sub:
            return srs.obter_personagem(pid)
        if sub == 'rig' and metodo == 'GET':
            p = srs.obter_personagem(pid)
            import rig2d
            bib = rig2d.biblioteca(p['dados'], pg.DADOS / 'rig2d')
            return {'rig_id': p['rig_id'], 'versao': p['versao'], 'dados': p['dados'], 'aprovado': p['aprovado'], 'biblioteca': bib}
        if sub == 'rig' and metodo == 'PUT':
            return srs.salvar_rig(pid, corpo())
        if sub == 'folha' and metodo == 'GET':
            return srs.folha(pid)
    if rota == ('GET', '/api/v1/cenarios'):
        return {'cenarios': srs.listar_cenarios(q.get('serie', [''])[0])}
    if rota == ('POST', '/api/v1/cenarios'):
        return srs.criar_cenario(corpo())
    if rota == ('POST', '/api/v1/cenarios/previa'):
        d = corpo()
        return srs.previa_cenario(d.get('dados') or {}, str(d.get('formato') or '9:16'))
    m = re.fullmatch(r'/api/v1/cenarios/([a-z0-9-]+)', caminho)
    if m and metodo in ('PATCH', 'PUT'):
        return srs.atualizar_cenario(m.group(1), corpo())
    raise pj.ErroProjeto(404, 'Rota não encontrada.')


def _downloads(metodo: str, caminho: str, corpo, quem: str):
    base = '/api/v1/downloads'
    try:
        if (metodo, caminho) == ('POST', base):
            d = corpo()
            return dl.criar(d.get('posts'), str(d.get('formato') or 'pacote'), quem)
        m = re.fullmatch(base + r'/([0-9a-f]{12})(?:/(cancelar|tentar-novamente|arquivo|item/(\d{1,3})))?', caminho)
        if m:
            jid, acao = m.group(1), m.group(2)
            if metodo == 'GET' and not acao:
                return dl.obter(jid)
            if metodo == 'POST' and acao == 'cancelar':
                return dl.cancelar(jid, quem)
            if metodo == 'POST' and acao == 'tentar-novamente':
                return dl.tentar_de_novo(jid, quem)
            if metodo == 'GET' and acao == 'arquivo':
                arq, nome = dl.arquivo_zip(jid)
                raise Resposta(arq, 'application/zip', nome, True)
            if metodo == 'GET' and m.group(3):
                arq, nome = dl.arquivo_item(jid, int(m.group(3)))
                raise Resposta(arq, 'video/mp4' if arq.suffix.lower() == '.mp4' else 'application/octet-stream', nome, True)
    except dl.ErroDownload as e:
        raise pj.ErroProjeto(e.status, e.msg)
    raise pj.ErroProjeto(404, 'Rota não encontrada.')


def _thumbs(metodo: str, caminho: str, q: dict, corpo, quem: str):
    rota = (metodo, caminho)
    base = '/api/v1/thumbnails'
    if rota == ('GET', base + '/capacidades'):
        return th.capacidades()
    if rota == ('GET', base + '/config'):
        return th.config()
    if rota in (('POST', base + '/config'), ('PATCH', base + '/config')):
        return th.salvar_config(corpo(), quem)
    if rota == ('GET', base + '/fontes'):
        return {'fontes': th.fontes(q.get('origem', [''])[0], q.get('termo', [''])[0], _int(q.get('limite', ['80'])[0], 80))}
    if rota == ('GET', base + '/jobs'):
        return th.listar(q.get('estado', [''])[0], _int(q.get('limite', ['50'])[0], 50))
    if rota == ('POST', base + '/jobs'):
        return th.criar(corpo(), quem)
    if rota == ('GET', base + '/desempenho'):
        return th.desempenho()
    if rota == ('GET', base + '/perfis'):
        return {'perfis': th.perfis()}
    if rota == ('POST', base + '/perfis'):
        return th.criar_perfil(corpo(), quem)
    m = re.fullmatch(base + r'/perfis/(\w+)', caminho)
    if m and metodo in ('PATCH', 'POST'):
        return th.mudar_perfil(m.group(1), corpo(), quem)
    m = re.fullmatch(base + r'/midia/(\w+)', caminho)
    if m and metodo == 'GET':
        arq, nome = th.midia(m.group(1))
        raise Resposta(arq, 'image/jpeg', nome, 'baixar' in q)
    m = re.fullmatch(base + r'/jobs/(\w+)(?:/(cancelar|refazer|variantes|selecionar|rejeitar|validar|pacote))?', caminho)
    if m:
        tid, acao = m.group(1), m.group(2)
        if metodo == 'GET' and not acao:
            return th.obter(tid)
        if metodo == 'GET' and acao == 'variantes':
            return {'variantes': th.obter(tid)['variantes']}
        if metodo == 'GET' and acao == 'pacote':
            return th.pacote(tid)
        if metodo == 'POST' and acao == 'cancelar':
            return th.cancelar(tid, quem)
        if metodo == 'POST' and acao == 'refazer':
            return th.refazer(tid, corpo(), quem)
        if metodo == 'POST' and acao == 'rejeitar':
            return th.rejeitar(tid, corpo(), quem)
        if metodo == 'POST' and acao == 'selecionar':
            return th.selecionar(tid, corpo(), quem)
        if metodo == 'POST' and acao == 'validar':        # o diretor confere de novo a escolha (vídeo e capa ainda iguais?)
            return th.pacote(tid)
    raise pj.ErroProjeto(404, 'Rota não encontrada.')


def _coord(metodo: str, caminho: str, q: dict, corpo, quem: str):
    """Agente 7 (Coordenador-Geral): conversa, ordens, agentes, liberação final, memória e aprendizado."""
    rota = (metodo, caminho)
    base = '/api/v1/coordenador'
    v = lambda k, p='': q.get(k, [p])[0]  # noqa: E731
    if rota == ('POST', base + '/interpretar'):
        d = corpo()
        _limite_ia('coord:' + quem, 60)
        return co.interpretar(str(d.get('texto') or ''), quem, str(d.get('chave') or ''))
    if rota == ('GET', base + '/conversa'):
        return {'mensagens': co.conversa(_int(v('limite', '60'), 60))}
    if rota == ('GET', base + '/catalogo'):
        return {'acoes': co.CATALOGO, 'ia': co.ia_disponivel()}
    if rota == ('GET', base + '/config'):
        return co.config()
    if rota in (('POST', base + '/config'), ('PATCH', base + '/config')):
        return co.salvar_config(corpo(), quem)
    if rota == ('GET', base + '/ordens'):
        return co.ordens(v('status'), _int(v('limite', '50'), 50))
    if rota == ('POST', base + '/ordens'):
        d = corpo()
        return co.criar_ordem(str(d.get('intencao') or ''), d.get('parametros') or {}, str(d.get('texto') or ''), quem, str(d.get('chave') or ''))
    m = re.fullmatch(base + r'/ordens/(\w+)(?:/(confirmar|pausar|retomar|cancelar|parametros))?', caminho)
    if m:
        oid, acao = m.group(1), m.group(2)
        if metodo == 'GET' and not acao:
            co.avancar(oid)
            return co.obter_ordem(oid)
        if metodo == 'POST' and acao == 'confirmar':
            return co.confirmar(oid, corpo(), quem)
        if metodo in ('POST', 'PATCH') and acao == 'parametros':
            return co.atualizar_parametros(oid, corpo(), quem)
        if metodo == 'POST' and acao == 'pausar':
            return co.pausar_ordem(oid, quem)
        if metodo == 'POST' and acao == 'retomar':
            return co.retomar_ordem(oid, quem)
        if metodo == 'POST' and acao == 'cancelar':
            return co.cancelar_ordem(oid, quem)
    if rota == ('GET', base + '/agentes'):
        return co.agentes()
    if rota == ('GET', base + '/eventos'):
        return {'eventos': co.eventos(v('ordem'), v('categoria'), _int(v('limite', '100'), 100))}
    if rota == ('GET', base + '/historico/conferir'):
        return co.conferir_historico()
    if rota == ('POST', base + '/links/conferir'):
        return co.conferir_links()
    if rota in (('GET', base + '/kwai'), ('POST', base + '/kwai/enviar')):
        import kwai_diario as kd
        try:
            if metodo == 'GET':
                r = kd.montar(v('data'))
                r.pop('arquivos', None)
                r['enviados'] = db.kv('agente7.kwai_enviados', []) or []
                return r
            d = corpo()
            return kd.enviar(str(d.get('data') or ''), quem)
        except kd.ErroKwai as e:
            raise pj.ErroProjeto(400, str(e))
    if rota == ('GET', base + '/custos'):
        import custo_corte as cc
        return cc.resumo(_int(v('dias', '30'), 30))
    if rota == ('POST', base + '/custos/aviso'):
        import custo_corte as cc
        return cc.enviar_aviso(_int(str(corpo().get('dias') or 7), 7))
    m = re.fullmatch(base + r'/custos/sugestoes/(\w+)/aplicar', caminho)
    if m and metodo == 'POST':
        import custo_corte as cc
        try:
            return cc.aplicar(m.group(1))
        except ValueError as e:
            raise pj.ErroProjeto(400, str(e))
    if rota == ('GET', base + '/aprovacoes'):
        return co.aprovacoes(v('estado'))
    m = re.fullmatch(base + r'/aprovacoes/(\w+)/(decidir|capa)', caminho)
    if m and metodo == 'POST':
        return co.decidir(m.group(1), corpo(), quem) if m.group(2) == 'decidir' else co.escolher_capa(m.group(1), corpo(), quem)
    if rota == ('GET', base + '/memorias'):
        return {'memorias': co.memorias(v('status'), v('escopo'))}
    if rota == ('POST', base + '/memorias'):
        return co.criar_memoria(corpo(), quem, 'voce')
    m = re.fullmatch(base + r'/memorias/(\w+)(?:/(confirmar|desativar|reverter))?', caminho)
    if m:
        mid, acao = m.group(1), m.group(2)
        if metodo == 'GET' and not acao:
            return co.memoria(mid)
        if metodo == 'PATCH' and not acao:
            return co.editar_memoria(mid, corpo(), quem)
        if metodo == 'POST' and acao == 'confirmar':
            return co.confirmar_memoria(mid, quem, corpo().get('versao'))
        if metodo == 'POST' and acao == 'desativar':
            return co.desativar_memoria(mid, quem, corpo().get('versao'))
        if metodo == 'POST' and acao == 'reverter':
            return co.reverter_memoria(mid, _int(corpo().get('versao'), 0), quem)
    m = re.fullmatch(base + r'/memorias/([\w-]+)/testar', caminho)
    if m and metodo == 'POST':
        return co.testar_hipotese(m.group(1), quem, corpo().get('versao'))
    if rota == ('POST', base + '/feedback'):
        return co.feedback(corpo(), quem)
    if rota == ('GET', base + '/aprendizado/sugestoes'):
        return co.sugestoes()
    m = re.fullmatch(base + r'/aprendizado/sugestoes/([\w.-]+)/(propor|dispensar)', caminho)
    if m and metodo == 'POST':
        return co.propor_sugestao(m.group(1), quem) if m.group(2) == 'propor' else co.dispensar_sugestao(m.group(1), quem)
    raise pj.ErroProjeto(404, 'Rota não encontrada.')


def iniciar():
    fila.registrar('estilo.demo', job_demo, 'pesado')
    fila.registrar('skills.instalar', job_skills, 'leve')
    fila.registrar('personagem.pose', job_pose, 'pesado')
    fila.registrar('criativo.serie_completa', cri.job_serie_completa, 'leve')
    import agente as _ag
    fila.registrar('esteira.recebido', _ag.job_esteira_recebido, 'pesado')
    fila.registrar('editor.legenda', _ag.job_mover_legenda, 'pesado')
    import texto_tela
    texto_tela.iniciar()
    rotas_esteira.ag2.iniciar()
    rotas_esteira.oq.iniciar()
    th.iniciar()
    co.iniciar()
    exportacao.iniciar()
    diretor.iniciar()
    storyboard.iniciar()
    hardware.iniciar()
    try:
        skcat.sincronizar()
    except Exception as e:  # catálogo com problema não impede o servidor de subir
        db.evento('skills', 'skill_erro', 'catalogo', {'erro': str(e)[:200]})


# ---------------------------------------------------------------- roteamento
def tratar(h, metodo: str, caminho: str, sessao: dict | None):
    """h = Handler do servidor (para corpo e cabeçalhos). Devolve um dict (JSON) ou levanta Resposta (arquivo)."""
    q = parse_qs(urlparse(h.path).query)
    quem = (sessao or {}).get('nome') or 'senha'
    sid = (sessao or {}).get('id', '')

    def corpo() -> dict:
        try:
            d = json.loads(h.corpo or b'{}')
            return d if isinstance(d, dict) else {}
        except ValueError:
            raise pj.ErroProjeto(400, 'Pedido inválido.')

    rota = (metodo, caminho)

    # ---- sessão e aparelhos
    if rota == ('GET', '/api/v1/saude'):
        return {'ok': True, 'api': 1, 'ffmpeg': rd.tem_ffmpeg()}
    if rota == ('POST', '/api/v1/sessao/login'):
        d = corpo()
        return au.login(str(d.get('senha', '')), h.TOKEN, str(d.get('nome', '')), h.quem())
    if rota == ('POST', '/api/v1/pareamento/completar'):
        d = corpo()
        return au.completar_pareamento(str(d.get('codigo', '')), str(d.get('nonce', '')), str(d.get('nome', '')), h.quem())
    if rota == ('GET', '/api/v1/sessao'):
        return {'aparelho': {'id': sid, 'nome': quem} if sessao else None, 'por_senha': not sessao, 'anuncio': au.chave_anuncio()}
    if rota == ('POST', '/api/v1/pareamento/iniciar'):
        return au.iniciar_pareamento(str(corpo().get('nome', '')))
    if rota == ('GET', '/api/v1/aparelhos'):
        return {'aparelhos': au.listar(sid)}
    m = re.fullmatch(r'/api/v1/aparelhos/(\w+)', caminho)
    if m and metodo == 'DELETE':
        return au.revogar(m.group(1), quem)
    if rota == ('POST', '/api/v1/sessao/sair'):
        return au.revogar(sid, quem) if sid else {'ok': True}

    # ---- projetos
    if rota == ('GET', '/api/v1/projetos'):
        return {'projetos': pj.listar(q.get('tipo', [''])[0]), 'livre_mb': rd.livre_mb(pg.DADOS)}
    if rota == ('POST', '/api/v1/projetos'):
        return pj.criar(corpo(), quem, 'site')
    # ---- diretor de cena: mapa de palco, animatic e prévia A/B (render pequeno de verdade)
    m = re.fullmatch(r'/api/v1/projetos/(\w+)/diretor', caminho)
    if m and metodo == 'GET':
        return diretor.mapa(m.group(1))
    m = re.fullmatch(r'/api/v1/projetos/(\w+)/animatic', caminho)
    if m and metodo == 'POST':
        return diretor.pedir_animatic(m.group(1))
    m = re.fullmatch(r'/api/v1/projetos/(\w+)/cenas/(\d{1,3})/refazer', caminho)
    if m and metodo == 'POST':
        d = corpo()
        return {'job': produtor.refazer_cena(m.group(1), int(m.group(2)), bool(d.get('imagem')), bool(d.get('voz')), quem,
                                             re.sub(r'[^\w-]', '', str(d.get('plano') or ''))[:20], d.get('problema') if isinstance(d.get('problema'), dict) else None)}
    m = re.fullmatch(r'/api/v1/projetos/(\w+)/quadros', caminho)
    if m and metodo == 'POST':
        return quadros_render(m.group(1), corpo())
    m = re.fullmatch(r'/api/v1/projetos/(\w+)/cenas/(\d{1,3})/previa-ab', caminho)
    if m and metodo == 'POST':
        d = corpo()
        return diretor.pedir_ab(m.group(1), int(m.group(2)), d.get('a') or [], d.get('b') or [])
    m = re.fullmatch(r'/api/v1/projetos/(\w+)/storyboard-visual', caminho)
    if m and metodo == 'GET':
        return storyboard.estado(m.group(1))
    m = re.fullmatch(r'/api/v1/projetos/(\w+)/storyboard-visual/(quadros|aprovar|corrigir)', caminho)
    if m and metodo == 'POST':
        d = corpo()
        if m.group(2) == 'quadros':
            return storyboard.pedir(m.group(1), d.get('cenas'))
        if m.group(2) == 'aprovar':
            return storyboard.aprovar(m.group(1), d.get('cenas'), quem)
        return storyboard.corrigir(m.group(1), str(d.get('cena', '')), d.get('mudancas') or {}, quem)
    m = re.fullmatch(r'/api/v1/diretor/(\w{6,40})', caminho)
    if m and metodo == 'GET':
        return diretor.estado(m.group(1))
    m = re.fullmatch(r'/api/v1/projetos/(\w+)', caminho)
    if m:
        pid = m.group(1)
        if metodo == 'GET':
            p = pj.obter(pid)
            if p['tipo'] == 'agente3':
                p['links'] = links_render(p['dados'].get('render'))
            return p
        if metodo in ('PATCH', 'PUT'):
            d = corpo()
            if 'revisao' not in d and h.headers.get('If-Match'):
                d['revisao'] = _int(h.headers.get('If-Match').strip('"W/'))
            return pj.atualizar(pid, d, quem, 'site')
        if metodo == 'DELETE':
            return pj.apagar(pid, quem)
    m = re.fullmatch(r'/api/v1/projetos/(\w+)/(versoes|restaurar|duplicar|exportar|revisao|aprovar|alterar|rejeitar|aprovar-roteiro|produzir|reenviar-email|storyboard|descricao)', caminho)
    if m:
        pid, acao = m.groups()
        if acao == 'versoes' and metodo == 'GET':
            return {'versoes': pj.versoes(pid)}
        if acao == 'restaurar' and metodo == 'POST':
            return pj.restaurar(pid, _int(corpo().get('revisao')), quem)
        if acao == 'duplicar' and metodo == 'POST':
            return pj.duplicar(pid, quem)
        if acao == 'exportar' and metodo == 'GET':
            arq = pj.exportar(pid)
            raise Resposta(arq, 'application/zip', arq.name, True)
        if acao == 'revisao' and metodo == 'GET':
            p = pj.obter(pid)
            r = p['dados'].get('render')
            redes = (p['dados']['briefing'].get('destinos') or {}).get('redes') or [] if p['tipo'] == 'agente3' else []
            ok, faltam = apv.contas_ok(redes)
            return {'projeto': p, 'ref': apv.ref(pid), 'links': links_render(r),
                    'parecer': apv.diretor_ok(p, r.get('sha')) if r else None,
                    'bloqueios_manuais': apv.bloqueios_manuais(p, r['sha']) if r and r.get('sha') else [], 'historico': apv.historico(pid),
                    'contas': {'ok': ok, 'faltam': faltam}, 'estados': produtor.ESTADOS,
                    'job': db.um("SELECT * FROM jobs WHERE projeto=? ORDER BY criado DESC LIMIT 1", pid)}
        if acao == 'descricao':
            # prévia da descrição de publicação (a mesma que a aprovação manda ao Agente 2); POST guarda a edição ou volta ao padrão
            p = pj.obter(pid)
            if p['tipo'] != 'agente3':
                raise pj.ErroProjeto(400, 'Só vídeos do Agente 3 têm esta descrição.')
            if metodo == 'POST':
                d = corpo()

                def _salvar(dd, _p):
                    de = dd['briefing'].setdefault('destinos', {})
                    if 'link_original' in d:
                        de['link_original'] = descricao_mod.link_valido(d.get('link_original'))
                    if d.get('restaurar'):
                        de['legenda'] = ''
                    elif 'legenda' in d:
                        txt = str(d.get('legenda') or '').strip()[:5000]
                        # igual ao modelo padrão = não editada (assim o padrão continua acompanhando título, hashtags e link)
                        de['legenda'] = '' if txt == apv.descricao(dict(_p, dados=dd), dict(de, legenda=''))['padrao'] else txt
                pj.mudar_dados(pid, _salvar, 'site')
                p = pj.obter(pid)
            elif metodo != 'GET':
                raise pj.ErroProjeto(405, 'Método não permitido.')
            dest = dict(p['dados']['briefing'].get('destinos') or {})
            if 'redes' in q:
                dest['redes'] = [x for x in q['redes'][0].split(',') if x]
            out = apv.descricao(p, dest)
            out.pop('exigidos', None)
            return out
        if metodo != 'POST':
            raise pj.ErroProjeto(405, 'Método não permitido.')
        d = corpo()
        if acao == 'aprovar':
            chave = (h.headers.get('Idempotency-Key') or d.get('chave') or '')[:80]
            return apv.aprovar(pid, str(d.get('render_sha', '')), d.get('destinos'), 'site', quem, chave, manual=d.get('manual') is True)
        if acao == 'alterar':
            return apv.pedir_alteracao(pid, str(d.get('render_sha', '')), str(d.get('texto', '')), 'site', quem)
        if acao == 'rejeitar':
            return apv.rejeitar(pid, str(d.get('render_sha', '')), str(d.get('motivo', '')), 'site', quem)
        if acao == 'aprovar-roteiro':
            return apv.aprovar_roteiro(pid, quem, d.get('revisao'))
        if acao == 'produzir':
            return {'job': produtor.produzir(pid, _quando(d), '', str(d.get('etapa', '')), quem)}
        if acao == 'storyboard':
            return produtor.salvar_storyboard(pid, _int(d.get('revisao'), -1), d, quem)
        if acao == 'reenviar-email':
            p = pj.obter(pid)
            return {'ok': emails.enviar_pronto(pid, (p['dados'].get('render') or {}).get('sha', ''))}

    # ---- uploads e arquivos
    if rota == ('POST', '/api/v1/uploads'):
        return pj.upload_inicio(corpo())
    m = re.fullmatch(r'/api/v1/uploads/(\w+)', caminho)
    if m and metodo == 'PUT':
        return pj.upload_pedaco(m.group(1), _int(q.get('offset', ['0'])[0]), h.corpo or b'')
    m = re.fullmatch(r'/api/v1/uploads/(\w+)/fim', caminho)
    if m and metodo == 'POST':
        return pj.upload_fim(m.group(1), 'site')
    if rota == ('POST', '/api/v1/assets/existentes'):
        return pj.assets_por_sha(corpo().get('sha256') or [])
    m = re.fullmatch(r'/api/v1/assets/(\w+)', caminho)
    if m and metodo == 'GET':
        a = pj.asset(m.group(1))
        raise Resposta(Path(a['caminho']), a['mime'] or 'application/octet-stream', a['nome'], 'baixar' in q)
    m = re.fullmatch(r'/api/v1/assets/(\w+)/link', caminho)
    if m and metodo == 'POST':
        pj.asset(m.group(1))
        return {'url': au.assinar_url(f'/api/v1/assets/{m.group(1)}', 6 * 3600)}

    # ---- fila
    if rota == ('GET', '/api/v1/fila'):
        return fila.lista(q.get('filtro', [''])[0])
    m = re.fullmatch(r'/api/v1/fila/(\w+)', caminho)
    if m and metodo == 'GET':
        j = fila.obter(m.group(1))
        if not j:
            raise pj.ErroProjeto(404, 'Trabalho não encontrado.')
        j = fila.estado_publico(j)
        j['dados'] = json.loads(j.get('dados') or '{}')
        j['resultado'] = json.loads(j['resultado']) if j.get('resultado') else None
        if j['status'] not in fila.FINAIS:
            j['restante'] = None if j['heartbeat_atrasado'] or j['estado_comum'] in ('PAUSED','WAITING_USER','CANCEL_REQUESTED') else round(fila.restante(j)[0])
        return j
    m = re.fullmatch(r'/api/v1/fila/(\w+)/(pausar|retomar|cancelar|ignorar|tentar|reagendar)', caminho)
    if m and metodo == 'POST':
        jid, acao = m.groups()
        if not fila.obter(jid):
            raise pj.ErroProjeto(404, 'Trabalho não encontrado.')
        db.evento(quem, 'fila_' + acao, 'job:' + jid)
        if acao == 'reagendar':
            t = _quando(corpo()) or time.time()
            return fila.reagendar(jid, t)
        return {'pausar': fila.pausar, 'retomar': fila.retomar, 'cancelar': fila.cancelar, 'ignorar': fila.ignorar, 'tentar': fila.tentar_de_novo}[acao](jid)
    if rota == ('GET', '/api/v1/capacidade'):
        return fila.capacidade()

    # ---- rotinas (agenda de PRODUÇÃO)
    if rota == ('GET', '/api/v1/rotinas'):
        return {'rotinas': agendador.listar(), 'fuso': str(agendador.FUSO)}
    if rota == ('POST', '/api/v1/rotinas'):
        try:
            d = corpo()
            if isinstance(d.get('briefing'), dict):
                d['briefing'] = produtor.limpar_briefing(d['briefing'])
            return agendador.criar(d)
        except ValueError as e:
            raise pj.ErroProjeto(400, str(e))
    m = re.fullmatch(r'/api/v1/rotinas/(\w+)', caminho)
    if m:
        try:
            if metodo in ('PATCH', 'PUT'):
                d = corpo()
                if isinstance(d.get('briefing'), dict):
                    d['briefing'] = produtor.limpar_briefing(d['briefing'])
                return agendador.mudar(m.group(1), d)
            if metodo == 'DELETE':
                return agendador.apagar(m.group(1))
        except ValueError as e:
            raise pj.ErroProjeto(400, str(e))

    # ---- Agente 3
    if rota == ('GET', '/api/v1/agente3/catalogo'):
        return {'estilos': _estilos_com_3d(), 'vozes': produtor.VOZES, 'tipos': produtor.TIPOS, 'estados': produtor.ESTADOS,
                'briefing': produtor.BRIEFING_PADRAO, 'formatos': list(ec.FORMATOS), 'ffmpeg': rd.tem_ffmpeg(), 'requisitos': produtor.requisitos(),
                'demos': {f'{e["id"]}:{f}': db.kv(f'demo:{e["id"]}:{f}:{ec.VERSAO_MOTOR}') for e in ec.catalogo() for f in ec.FORMATOS
                          if db.kv(f'demo:{e["id"]}:{f}:{ec.VERSAO_MOTOR}')},
                'efeitos': [{'id': k, 'nome': v[0], 'demos': {f: db.kv(f'demo:animado2d:{f}:{ec.VERSAO_MOTOR}:{k}') for f in ec.FORMATOS
                                                               if db.kv(f'demo:animado2d:{f}:{ec.VERSAO_MOTOR}:{k}')}} for k, v in ec.VARIANTES_DEMO.items()]}
    if rota == ('POST', '/api/v1/agente3/ideias'):
        return produtor.ideias(corpo())
    if rota == ('POST', '/api/v1/agente3/roteiro'):
        d = corpo()
        b = produtor.limpar_briefing(d.get('briefing') or d)
        if str(d.get('roteiro_texto') or '').strip():
            return produtor.ler_roteiro_colado(str(d['roteiro_texto'])[:20000], b)
        extras = [str(x) for x in (d.get('skills') or [])[:6] if isinstance(x, str)]
        serie = None
        if d.get('projeto_id'):   # vídeo com personagens da biblioteca (ou episódio): a IA escreve com esse elenco, na versão fixada
            serie = pj.obter(str(d['projeto_id'])[:40])['dados'].get('serie') or None
        return produtor.gerar_roteiro(b, str(d.get('ideia') or b['tema']), extras=extras, serie=serie)
    if rota == ('POST', '/api/v1/agente3/projetos'):
        d = corpo()
        p = produtor.novo(d, quem)
        if d.get('produzir'):
            if d.get('aprovar_roteiro') and p['dados'].get('cenas'):
                # quem montou o storyboard no site já o revisou: fica aprovado (vale também para produção agendada)
                pj.mudar_dados(p['id'], lambda dd, _p: dd.update(aprovacao_roteiro={'aprovado': True, 't': time.time(), 'por': quem}))
            produtor.produzir(p['id'], _quando(d), '', '', quem)
        return pj.obter(p['id'])
    if rota == ('POST', '/api/v1/agente3/lote'):
        d = corpo()
        n = max(1, min(_int(d.get('quantidade'), 1), 12))
        inicio = _quando(d) or time.time()
        intervalo = max(0, _int(d.get('intervalo_min'), 0)) * 60
        temas = [str(t).strip()[:200] for t in (d.get('temas') or []) if str(t).strip()]
        criados = []
        for i in range(n):
            b = dict(d.get('briefing') or {})
            if temas:
                b['tema'] = temas[i % len(temas)]
            p = produtor.novo({'briefing': b, 'modo': 'automatico', 'origem': 'lote'}, quem)
            j = produtor.produzir(p['id'], inicio + i * intervalo if (i or d.get('quando') not in (None, 'agora')) else None, '', '', quem)
            criados.append({'projeto': p['id'], 'job': j['id'], 'run_at': j['run_at']})
        return {'criados': criados}
    m = re.fullmatch(r'/api/v1/estilos/(\w+)/demo', caminho)
    if m and metodo == 'POST':
        d = corpo()
        fmt = d.get('formato') if d.get('formato') in ec.FORMATOS else '9:16'
        var = d.get('variante') if d.get('variante') in ec.VARIANTES_DEMO and m.group(1) == 'animado2d' else ''
        suf = f':{var}' if var else ''
        pronto = db.kv(f'demo:{m.group(1)}:{fmt}:{ec.VERSAO_MOTOR}{suf}')
        refazer = bool(d.get('refazer'))
        if pronto and not refazer:
            return {'pronto': pronto, 'url': au.assinar_url(f'/api/v1/assets/{pronto["asset"]}', 6 * 3600)}
        if not ec.utilizavel(m.group(1), False):
            raise pj.ErroProjeto(400, 'Este estilo ainda não roda no servidor.')
        j = fila.enfileirar('estilo.demo', agente='galeria', dados={'estilo': m.group(1), 'formato': fmt, 'variante': var, 'refazer': refazer}, recurso='pesado',
                            titulo=f'Demonstração: {ec.estilo(m.group(1))["nome"]}' + (f' ({ec.VARIANTES_DEMO[var][0]})' if var else ''),
                            chave=f'demo:{m.group(1)}:{fmt}:{ec.VERSAO_MOTOR}{suf}:' + (f'r{int(time.time() // 60)}' if refazer else str(int(time.time() // 600))))
        return {'job': j}

    # ---- aprovações e e-mail
    if rota == ('GET', '/api/v1/aprovacoes'):
        return {'pendentes': apv.pendentes()}
    if rota == ('GET', '/api/v1/email/respostas'):
        return emails.estado()
    if rota == ('POST', '/api/v1/email/respostas'):
        return emails.salvar_respostas(corpo())
    if rota == ('POST', '/api/v1/email/respostas/ler'):
        return emails.ler_respostas()

    # ---- backups, diagnóstico e registro
    if rota == ('GET', '/api/v1/diagnostico'):
        return backups.diagnostico()
    if rota == ('GET', '/api/v1/3d'):
        j = db.um("SELECT id, status, etapa, progresso, erro FROM jobs WHERE tipo='aparelho.testar3d' ORDER BY criado DESC LIMIT 1")
        return {'videos': hardware.registrar_videos_3d(), 'laudo': db.kv('diagnostico_3d'), 'job': j}
    if rota == ('POST', '/api/v1/3d/testar'):
        return hardware.pedir_teste_3d()
    if rota == ('GET', '/api/v1/metricas'):
        return backups.metricas()
    m = re.fullmatch(r'/api/v1/midias-backup/restaurar/([\w-]{1,40})', caminho)
    if m and metodo == 'POST':
        try:
            return backups.restaurar_projeto(m.group(1), corpo().get('categorias') or None, str(corpo().get('manifesto') or ''))
        except FileNotFoundError as e:
            raise pj.ErroProjeto(404, str(e))
    if rota == ('GET', '/api/v1/aparelho'):
        return _aparelho()
    if rota == ('POST', '/api/v1/aparelho/testar'):
        return hardware.pedir_teste()
    if rota == ('GET', '/api/v1/backups'):
        return {'backups': backups.listar()}
    if rota == ('POST', '/api/v1/backups'):
        return backups.fazer('manual')
    m = re.fullmatch(r'/api/v1/backups/([\w.-]+)/testar', caminho)
    if m and metodo == 'POST':
        return backups.testar_restauracao(m.group(1))
    if rota == ('GET', '/api/v1/midias-backup'):
        return backups.estado_midias()
    if rota == ('PUT', '/api/v1/midias-backup'):
        try:
            return backups.salvar_config_midias(corpo())
        except ValueError as e:
            raise pj.ErroProjeto(400, str(e))
    if rota == ('POST', '/api/v1/midias-backup/fazer'):
        try:
            return backups.fazer_midias('manual')
        except OSError as e:
            raise pj.ErroProjeto(400, str(e))
    if rota == ('POST', '/api/v1/midias-backup/testar'):
        try:
            return backups.testar_midias(str(corpo().get('manifesto') or ''))
        except FileNotFoundError as e:
            raise pj.ErroProjeto(404, str(e))
    # ---- exportação da Montagem manual feita no servidor
    m = re.fullmatch(r'/api/v1/posts/(\w+)/(editor|permitir)', caminho)
    if m and metodo == 'POST':          # alerta "mande para o editor": o botão faz isso pelo corte deste post
        post = next((x for x in pg.posts() if x['id'] == m.group(1)), None)
        if not post:
            raise pj.ErroProjeto(404, 'Post não encontrado.')
        import agente as _ag
        c = next((x for x in _ag.estado()['cortes'] if x.get('post') == post['id']), None) or \
            next((x for x in _ag.estado()['cortes'] if x.get('video') == post.get('video') and x['status'] not in ('descartado', 'postado')), None)
        if not c:
            raise pj.ErroProjeto(409, 'Este post não veio de um corte do Agente 1. Vídeo do Agente 3: abra em Fila e aprovações e peça correção; '
                                      'vídeo enviado à mão: mande pela tela Cortes para passar pelo editor.')
        try:
            if m.group(2) == 'permitir':        # o diretor não aprovou e você decidiu postar mesmo assim
                return _ag.permitir_postar(c['id'], quem)
            return _ag.mandar_para_editor(c['id'], quem)
        except _ag.ErroAgente as e:
            raise pj.ErroProjeto(409, str(e))
    m = re.fullmatch(r'/api/v1/posts/(\w+)/conferencia', caminho)
    if m and metodo == 'GET':
        post = next((x for x in pg.posts() if x['id'] == m.group(1)), None)
        if not post:
            raise pj.ErroProjeto(404, 'Post não encontrado.')
        return {'redes': {r: pg.conferencia(post, r) for r in post['redes'] if r != 'kwai'},
                'estados': {r: {'status': x.get('status', ''), 'erro': (x.get('erro') or '')[:300], 'link': x.get('link') or ''} for r, x in post['redes'].items()},
                'hash': (post.get('hash') or '')[:16]}
    if rota == ('POST', '/api/v1/exportar'):
        return exportacao.pedir(corpo(), quem)
    m = re.fullmatch(r'/api/v1/exportar/(\w{6,40})', caminho)
    if m and metodo == 'GET':
        return exportacao.estado(m.group(1))
    # ---- séries animadas, personagens e cenários
    if caminho.startswith(('/api/v1/series', '/api/v1/personagens', '/api/v1/cenarios')):
        return _series(metodo, caminho, q, corpo, quem)
    # ---- núcleo criativo (Modelagem com IA, biblioteca compartilhada e tendências)
    if caminho.startswith('/api/v1/criativo/'):
        return _criativo(metodo, caminho, q, corpo, quem, sid)
    # ---- Agente 6: capas (thumbnails)
    if caminho.startswith('/api/v1/downloads'):          # download em lote de Publicações (somente leitura)
        return _downloads(metodo, caminho, corpo, quem)
    if caminho.startswith('/api/v1/thumbnails'):
        try:
            return _thumbs(metodo, caminho, q, corpo, quem)
        except th.ErroThumb as e:
            raise pj.ErroProjeto(e.status, str(e))
    # ---- pacote diário do Kwai (arquivos; abre também por link assinado, sem senha, para o link do WhatsApp)
    m = re.fullmatch(r'/api/v1/kwai/(\d{4}-\d{2}-\d{2})/(pagina|texto|zip)', caminho)
    if m and metodo == 'GET':
        import kwai_diario as kd
        try:
            arq = kd.arquivo(m.group(1), m.group(2))
        except kd.ErroKwai as e:
            raise pj.ErroProjeto(400, str(e))
        if m.group(2) == 'pagina':
            raise Resposta(arq, 'text/html; charset=utf-8')
        if m.group(2) == 'zip':
            raise Resposta(arq, 'application/zip', arq.name, True)
        raise Resposta(arq, 'text/plain; charset=utf-8', arq.name, True)
    m = re.fullmatch(r'/api/v1/kwai/video/(\w+)', caminho)
    if m and metodo == 'GET':
        import kwai_diario as kd
        try:
            arq, nome = kd.video(m.group(1))
        except (kd.ErroKwai, pg.ErroRede) as e:
            raise pj.ErroProjeto(404, str(e))
        raise Resposta(arq, 'video/mp4' if arq.suffix == '.mp4' else 'video/' + arq.suffix[1:], nome, True)
    # ---- Agente 7: Coordenador-Geral
    if caminho.startswith('/api/v1/coordenador'):
        try:
            return _coord(metodo, caminho, q, corpo, quem)
        except co.ErroCoord as e:
            raise pj.ErroProjeto(e.status, str(e))
        except th.ErroThumb as e:
            raise pj.ErroProjeto(e.status, str(e))
    # ---- esteira dos 5 agentes, diretor de qualidade, capacidades, referências virais e programação diária do Agente 2
    if caminho.startswith(rotas_esteira.PREFIXOS):
        try:
            return rotas_esteira.tratar(metodo, caminho, q, corpo, quem, {'If-Match': h.headers.get('If-Match') if getattr(h, 'headers', None) else None})
        except rotas_esteira.ErroRota as e:
            raise pj.ErroProjeto(e.status, str(e))
    # ---- biblioteca de skills (só texto de orientação; nada é executado)
    if caminho.startswith('/api/v1/skills'):
        try:
            return _skills(metodo, caminho, q, corpo, quem)
        except skcat.ErroSkill as e:
            raise pj.ErroProjeto(e.status, str(e))
    # ---- painel do Início e da Central de Agentes (só leitura)
    if rota == ('GET', '/api/v1/dashboard/resumo'):
        import painel
        return painel.resumo(q.get('periodo', ['7d'])[0])
    if rota == ('GET', '/api/v1/eventos'):
        n = max(1, min(_int(q.get('limite', ['50'])[0], 50), 300))
        return {'eventos': db.todos('SELECT * FROM eventos ORDER BY n DESC LIMIT ?', n)}
    raise pj.ErroProjeto(404, 'Rota não encontrada.')
