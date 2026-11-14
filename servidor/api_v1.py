"""Rotas /api/v1 (projetos no servidor, aparelhos, fila, rotinas, Agente 3, aprovações, backups).

Autenticação: cabeçalho X-Sessao (sessão do aparelho) ou X-Token (senha do servidor, compatibilidade).
Arquivos para o <video> do navegador usam link temporário assinado (?exp=&sig=), nunca a senha na URL.
"""
from __future__ import annotations

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
import banco as db
import emails
import estilos_codigo as ec
import fila
import postagem as pg
import produtor
import projetos as pj
import renderizador as rd

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
    eid, fmt = ctx.dados['estilo'], ctx.dados.get('formato', '9:16')
    chave = f'demo:{eid}:{fmt}:{ec.VERSAO_MOTOR}'
    if db.kv(chave):
        return {'resultado': db.kv(chave), 'etapa': 'Pronto'}
    if not ec.utilizavel(eid, False):
        raise produtor.ErroProdutor('Este estilo não roda neste servidor ainda.', True)
    W, H = ec.FORMATOS[fmt]
    pasta = pg.DADOS / 'demos' / f'{eid}-{fmt.replace(":", "x")}'
    shutil.rmtree(pasta, ignore_errors=True)
    pasta.mkdir(parents=True)
    saida = pasta / 'demo.mp4'
    ctx.progresso(10, 'Desenhando as peças')
    t0 = time.time()
    cmd = ec.montar(eid, ec.demo_cena(eid), W, H, 5.0, pasta, None, None, saida)
    ctx.progresso(30, 'Renderizando 5 segundos')
    rd.rodar(cmd, ctx.cancelado, tempo_max=900)
    fila.medir('render_cena', (time.time() - t0) / 5.0)
    conf = rd.conferir(saida, pasta, {'largura': W, 'altura': H, 'duracao': 5.0}, ctx.cancelado)
    if not conf['ok']:
        raise produtor.ErroProdutor('A demonstração não passou na conferência: ' + '; '.join(conf['erros']))
    a = pj.registrar_asset(saida, f'demo-{eid}-{fmt.replace(":", "x")}.mp4', 'video/mp4', '', 'demo')['asset']
    r = {'asset': a['id'], 'segundos': round(time.time() - t0, 1), 'avisos': conf['avisos'], 'formato': fmt}
    db.kv_gravar(chave, r)
    return {'resultado': r, 'etapa': 'Pronto'}


def iniciar():
    fila.registrar('estilo.demo', job_demo, 'pesado')


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
    m = re.fullmatch(r'/api/v1/projetos/(\w+)/(versoes|restaurar|duplicar|exportar|revisao|aprovar|alterar|rejeitar|aprovar-roteiro|produzir|reenviar-email)', caminho)
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
            return {'projeto': p, 'ref': apv.ref(pid), 'links': links_render(r), 'historico': apv.historico(pid),
                    'contas': {'ok': ok, 'faltam': faltam}, 'estados': produtor.ESTADOS,
                    'job': db.um("SELECT * FROM jobs WHERE projeto=? ORDER BY criado DESC LIMIT 1", pid)}
        if metodo != 'POST':
            raise pj.ErroProjeto(405, 'Método não permitido.')
        d = corpo()
        if acao == 'aprovar':
            chave = (h.headers.get('Idempotency-Key') or d.get('chave') or '')[:80]
            return apv.aprovar(pid, str(d.get('render_sha', '')), d.get('destinos'), 'site', quem, chave)
        if acao == 'alterar':
            return apv.pedir_alteracao(pid, str(d.get('render_sha', '')), str(d.get('texto', '')), 'site', quem)
        if acao == 'rejeitar':
            return apv.rejeitar(pid, str(d.get('render_sha', '')), str(d.get('motivo', '')), 'site', quem)
        if acao == 'aprovar-roteiro':
            return apv.aprovar_roteiro(pid, quem, d.get('revisao'))
        if acao == 'produzir':
            return {'job': produtor.produzir(pid, _quando(d), '', str(d.get('etapa', '')), quem)}
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
    m = re.fullmatch(r'/api/v1/fila/(\w+)/(pausar|retomar|cancelar|tentar|reagendar)', caminho)
    if m and metodo == 'POST':
        jid, acao = m.groups()
        if not fila.obter(jid):
            raise pj.ErroProjeto(404, 'Trabalho não encontrado.')
        db.evento(quem, 'fila_' + acao, 'job:' + jid)
        if acao == 'reagendar':
            t = _quando(corpo()) or time.time()
            return fila.reagendar(jid, t)
        return {'pausar': fila.pausar, 'retomar': fila.retomar, 'cancelar': fila.cancelar, 'tentar': fila.tentar_de_novo}[acao](jid)
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
        return {'estilos': ec.catalogo(), 'vozes': produtor.VOZES, 'tipos': produtor.TIPOS, 'estados': produtor.ESTADOS,
                'briefing': produtor.BRIEFING_PADRAO, 'formatos': list(ec.FORMATOS), 'ffmpeg': rd.tem_ffmpeg(),
                'demos': {f'{e["id"]}:{f}': db.kv(f'demo:{e["id"]}:{f}:{ec.VERSAO_MOTOR}') for e in ec.catalogo() for f in ec.FORMATOS
                          if db.kv(f'demo:{e["id"]}:{f}:{ec.VERSAO_MOTOR}')}}
    if rota == ('POST', '/api/v1/agente3/ideias'):
        return produtor.ideias(corpo())
    if rota == ('POST', '/api/v1/agente3/roteiro'):
        d = corpo()
        b = produtor.limpar_briefing(d.get('briefing') or d)
        if str(d.get('roteiro_texto') or '').strip():
            return produtor.ler_roteiro_colado(str(d['roteiro_texto'])[:20000], b)
        return produtor.gerar_roteiro(b, str(d.get('ideia') or b['tema']))
    if rota == ('POST', '/api/v1/agente3/projetos'):
        d = corpo()
        p = produtor.novo(d, quem)
        if d.get('produzir'):
            if d.get('aprovar_roteiro') and p['dados'].get('cenas'):
                apv.aprovar_roteiro(p['id'], quem)
            else:
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
        pronto = db.kv(f'demo:{m.group(1)}:{fmt}:{ec.VERSAO_MOTOR}')
        if pronto:
            return {'pronto': pronto, 'url': au.assinar_url(f'/api/v1/assets/{pronto["asset"]}', 6 * 3600)}
        if not ec.utilizavel(m.group(1), False):
            raise pj.ErroProjeto(400, 'Este estilo ainda não roda no servidor.')
        j = fila.enfileirar('estilo.demo', agente='galeria', dados={'estilo': m.group(1), 'formato': fmt}, recurso='pesado',
                            titulo=f'Demonstração: {ec.estilo(m.group(1))["nome"]}', chave=f'demo:{m.group(1)}:{fmt}:{ec.VERSAO_MOTOR}:{int(time.time() // 600)}')
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
    if rota == ('GET', '/api/v1/backups'):
        return {'backups': backups.listar()}
    if rota == ('POST', '/api/v1/backups'):
        return backups.fazer('manual')
    m = re.fullmatch(r'/api/v1/backups/([\w.-]+)/testar', caminho)
    if m and metodo == 'POST':
        return backups.testar_restauracao(m.group(1))
    if rota == ('GET', '/api/v1/eventos'):
        n = max(1, min(_int(q.get('limite', ['50'])[0], 50), 300))
        return {'eventos': db.todos('SELECT * FROM eventos ORDER BY n DESC LIMIT ?', n)}
    raise pj.ErroProjeto(404, 'Rota não encontrada.')
