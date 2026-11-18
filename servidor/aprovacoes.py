"""Aprovação humana dos vídeos do Agente 3 — a ÚNICA porta entre o Agente 3 e a postagem (Agente 2).

Regra de ouro: só vira post se
  render conferido  +  aprovação APROVADA  +  hash aprovado == hash do vídeo atual
  +  conta da rede conectada  +  direitos OK (vídeo original do próprio canal).

- Aprovar pelo site é sempre POST com a sessão do aparelho (nunca um link GET).
- Aprovar por e-mail exige o código de desafio (uso único, 7 dias, preso ao projeto + hash do vídeo).
- Um novo render invalida os códigos antigos: aprovar a versão errada é impossível.
- A mesma aprovação nunca cria o mesmo post duas vezes (chave única por hash + rede).
"""
from __future__ import annotations

import descricao as ds
import hashlib
import hmac
import json
import os
import secrets
import shutil
import time
import uuid

import banco as db
import fila
import postagem as pg
import projetos as pj

ALFABETO = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
VALIDADE = 7 * 86400
MAX_ERROS = 5
SITE = os.getenv('SITE', 'https://raniere3000-tech.github.io/ia/').rstrip('/') + '/'
PROVEDOR = {'youtube': 'google', 'facebook': 'meta', 'instagram': 'meta', 'tiktok': 'tiktok', 'kwai': None}


class ErroAprovacao(Exception):
    def __init__(self, status: int, msg: str):
        super().__init__(msg)
        self.status = status


def ref(pid: str) -> str:
    """Referência curta que vai no assunto do e-mail: VID-XXXXXX."""
    return 'VID-' + pid[:6].upper()


def pid_da_ref(r: str) -> str | None:
    r = (r or '').strip().upper()
    if not r.startswith('VID-') or len(r) != 10:
        return None
    p = db.um("SELECT id FROM projetos WHERE tipo='agente3' AND apagado=0 AND UPPER(SUBSTR(id,1,6))=?", r[4:])
    return p['id'] if p else None


def _norm(codigo: str) -> str:
    return ''.join(ch for ch in (codigo or '').upper() if ch in ALFABETO)


def _hash_codigo(pid: str, sha: str, codigo: str) -> str:
    return hashlib.sha256(f'{pid}|{sha}|{_norm(codigo)}'.encode()).hexdigest()


# ---------------------------------------------------------------- desafio (código do e-mail)
def novo_desafio(pid: str, sha: str, message_id: str = '') -> str:
    """Cria o código de uso único para ESTA versão do vídeo e invalida os anteriores do projeto."""
    codigo = ''.join(secrets.choice(ALFABETO) for _ in range(8))
    agora = time.time()
    with db.tx() as c:
        c.execute('UPDATE desafios SET usado=? WHERE projeto=? AND usado IS NULL', (agora, pid))
        c.execute('INSERT INTO desafios (id, projeto, render_sha, codigo_hash, expira, usado, erros, message_id, criado) VALUES (?,?,?,?,?,NULL,0,?,?)',
                  (uuid.uuid4().hex[:16], pid, sha, _hash_codigo(pid, sha, codigo), agora + VALIDADE, message_id, agora))
    return codigo[:4] + '-' + codigo[4:]


def marcar_message_id(pid: str, sha: str, message_id: str):
    db.executar('UPDATE desafios SET message_id=? WHERE projeto=? AND render_sha=? AND usado IS NULL', message_id, pid, sha)


def desafio_ativo(pid: str) -> dict | None:
    return db.um('SELECT * FROM desafios WHERE projeto=? AND usado IS NULL AND expira>? ORDER BY criado DESC LIMIT 1', pid, time.time())


def validar_desafio(pid: str, codigo: str, *, consumir: bool = True) -> dict:
    """Confere o código. Erro demais bloqueia o desafio (precisa reenviar pelo site)."""
    d = desafio_ativo(pid)
    if not d:
        raise ErroAprovacao(410, 'Não há código válido para este vídeo (expirou, já foi usado ou saiu uma versão nova). Peça um novo pelo site.')
    if d['erros'] >= MAX_ERROS:
        raise ErroAprovacao(429, 'Código bloqueado por tentativas erradas. Peça um novo pelo site.')
    if not hmac.compare_digest(d['codigo_hash'], _hash_codigo(pid, d['render_sha'], codigo)):
        db.executar('UPDATE desafios SET erros=erros+1 WHERE id=?', d['id'])
        raise ErroAprovacao(403, 'Código errado.')
    if consumir:
        n = db.executar('UPDATE desafios SET usado=? WHERE id=? AND usado IS NULL', time.time(), d['id'])
        if not n:
            raise ErroAprovacao(409, 'Este código acabou de ser usado.')
    return d


# ---------------------------------------------------------------- consulta
def _render_atual(p: dict) -> dict | None:
    r = p['dados'].get('render') or None
    if not r or not r.get('validado'):
        return None
    linha = db.um('SELECT * FROM renders WHERE projeto=? AND sha256=? AND validado=1', p['id'], r.get('sha', ''))
    if not linha or not os.path.exists(linha['arquivo']):
        return None
    return dict(r, arquivo=linha['arquivo'])


def pendentes() -> list:
    """Vídeos esperando decisão (render pronto) e roteiros esperando aprovação."""
    out = []
    for p in db.todos("SELECT id, titulo, status, atualizado FROM projetos WHERE tipo='agente3' AND apagado=0 "
                      "AND status IN ('ready_for_review','waiting_brief_approval','changes_requested') ORDER BY atualizado DESC LIMIT 100"):
        full = pj.obter(p['id'])
        r = full['dados'].get('render') or {}
        out.append({'projeto': p['id'], 'ref': ref(p['id']), 'titulo': p['titulo'], 'status': p['status'], 'atualizado': p['atualizado'],
                    'tipo': 'video' if p['status'] == 'ready_for_review' else 'roteiro',
                    'render': {k: r.get(k) for k in ('sha', 'versao', 'duracao', 'avisos', 'assets', 'largura', 'altura')} if r else None,
                    'destinos': full['dados']['briefing'].get('destinos') or {}})
    return out


def historico(pid: str) -> list:
    return db.todos('SELECT id, render_sha, decisao, origem, por, texto, destinos, publicar_em, criado FROM aprovacoes WHERE projeto=? ORDER BY criado DESC', pid)


def contas_ok(redes: list) -> tuple[list, list]:
    """Separa as redes com conta conectada das que faltam conectar (Kwai é sempre manual)."""
    st = pg.status_contas()
    ok, faltam = [], []
    for r in redes:
        prov = PROVEDOR.get(r)
        if prov is None:
            ok.append(r)            # Kwai: o post fica como "manual" (você posta e marca)
        elif st.get(prov, {}).get('conectado'):
            ok.append(r)
        else:
            faltam.append(r)
    return ok, faltam


def _quando(dest: dict) -> float:
    q = dest.get('quando') or 'proximo'
    if q == 'agora':
        return time.time() + 60
    if q == 'data':
        try:
            t = float(dest.get('data') or 0)
        except (TypeError, ValueError):
            t = 0
        if t < time.time():
            raise ErroAprovacao(400, 'A data de publicação já passou. Escolha outra.')
        return t
    try:
        import agente as ag
        cfg = ag.config()
        v = ag.escolher_vaga(cfg['postagem'], 99)
        if v:
            return v['quando']
    except Exception:  # noqa: BLE001
        pass
    return time.time() + 3600


# ---------------------------------------------------------------- decisões
def descricao(p: dict, dest: dict | None = None) -> dict:
    """Descrição de publicação de um projeto do Agente 3 (a mesma usada na prévia do site e na aprovação).
    A editada à mão vale como está (só os créditos obrigatórios são garantidos); sem edição, o modelo padrão."""
    import produtor
    dest = dict(p['dados']['briefing'].get('destinos') or {}) if dest is None else dest
    creds = produtor.creditos(p['dados'])
    exigidos = [c for c in creds if 'Wikimedia' in c]
    dados_desc = dict(p['dados'], briefing=dict(p['dados']['briefing'], destinos=dest))
    padrao = ds.do_projeto(dados_desc, creds, p['titulo'])
    editada = str(dest.get('legenda') or '').strip()
    legenda = ds.com_creditos(editada or padrao, exigidos)
    redes = [x for x in dest.get('redes') or [] if x in pg.REDES]
    return {'legenda': legenda, 'padrao': padrao, 'editada': bool(editada), 'exigidos': exigidos,
            'link_original': ds.link_valido(dest.get('link_original')), 'avisos': ds.excede(legenda, redes)}


def diretor_ok(p: dict, sha: str) -> dict:
    """O diretor de qualidade aprovou ESTE arquivo? Vídeos feitos antes do diretor existir são julgados pelo laudo guardado."""
    import qualidade as qd
    import pipeline as pl
    if pl.ligado():          # esteira ligada: vale o certificado assinado do diretor para ESTE arquivo
        c = pl.certificado(sha)
        return {'aprovado': bool(c), 'motivos': [] if c else ['Este arquivo não tem o certificado do diretor de qualidade (nota 70 sem bloqueios).']}
    d = p['dados'].get('diretor') or {}
    if d.get('sha') == sha and d.get('veredito') in ('aprovado', 'reprovado'):
        return {'aprovado': d['veredito'] == 'aprovado', 'motivos': d.get('motivos') or []}
    return qd.veredito(p['dados'].get('qualidade'))


def aprovar(pid: str, render_sha: str, destinos: dict | None, origem: str, por: str, chave: str = '') -> dict:
    """Aprovação válida da versão final -> posts no Agente 2. Repetir a mesma chamada não duplica nada."""
    p = pj.obter(pid)
    if p['tipo'] != 'agente3':
        raise ErroAprovacao(400, 'Só vídeos do Agente 3 passam por esta aprovação.')
    r = _render_atual(p)
    if not r:
        raise ErroAprovacao(409, 'Este vídeo ainda não tem uma versão final conferida.')
    if not render_sha or render_sha != r['sha']:
        raise ErroAprovacao(409, 'O vídeo mudou depois que você abriu. Assista a versão nova antes de aprovar.')
    chave = chave or f'aprovar:{pid}:{render_sha}'
    ja = db.um('SELECT * FROM aprovacoes WHERE chave=?', chave)
    if ja:
        return {'ok': True, 'repetido': True, 'aprovacao': ja, 'posts': db.todos('SELECT * FROM publicacoes WHERE aprovacao=?', ja['id'])}
    if p['status'] not in ('ready_for_review', 'changes_requested'):
        raise ErroAprovacao(409, f'Este vídeo não está esperando aprovação (situação: {p["status"]}).')
    dr = diretor_ok(p, render_sha)
    if not dr['aprovado']:
        raise ErroAprovacao(409, 'O diretor de qualidade não aprovou esta versão: ' + ' '.join(dr['motivos'])[:400] + ' Refaça as cenas apontadas.')
    dest = dict(p['dados']['briefing'].get('destinos') or {})
    if isinstance(destinos, dict):
        dest.update({k: v for k, v in destinos.items() if k in ('redes', 'quando', 'data', 'titulo', 'legenda', 'link_original')})
    redes = [x for x in dest.get('redes') or [] if x in pg.REDES]
    ok, faltam = contas_ok(redes)
    if faltam:
        raise ErroAprovacao(412, 'Conecte a conta antes de aprovar: ' + ', '.join(x.capitalize() for x in faltam) + '. Ou tire essa rede da lista.')
    roteiro = p['dados'].get('roteiro') or {}
    titulo = ds.titulo_limpo(dest.get('titulo') or roteiro.get('titulo') or p['titulo'])[:100]
    dsc = descricao(p, dest)
    legenda, exigidos = dsc['legenda'], dsc['exigidos']
    excesso = ds.excede(legenda, redes)
    if excesso:
        raise ErroAprovacao(422, 'A descrição não cabe sem cortar: ' + ' '.join(excesso) + ' Encurte a descrição ou tire essa rede.')
    quando = _quando(dest) if redes else 0
    aid = uuid.uuid4().hex[:16]
    agora = time.time()
    try:
        db.executar('INSERT INTO aprovacoes (id, projeto, render_sha, decisao, origem, por, texto, destinos, publicar_em, criado, chave) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    aid, pid, render_sha, 'aprovado', origem[:20], por[:80], '', json.dumps(dest, ensure_ascii=False), quando, agora, chave)
    except Exception:  # noqa: BLE001  (corrida: outra chamada igual chegou primeiro)
        ja = db.um('SELECT * FROM aprovacoes WHERE chave=?', chave)
        return {'ok': True, 'repetido': True, 'aprovacao': ja, 'posts': db.todos('SELECT * FROM publicacoes WHERE aprovacao=?', ja['id'] if ja else '')}
    # invalida códigos de e-mail ainda abertos (a decisão já foi tomada)
    db.executar('UPDATE desafios SET usado=? WHERE projeto=? AND usado IS NULL', agora, pid)
    try:        # esteira: a execução deste arquivo passa para a fila de postagem do Agente 2
        import pipeline as pl
        for x in db.todos("SELECT id FROM pipeline_runs WHERE ref=? AND sha256=? AND estado='awaiting_human_publish_approval'", pid, render_sha):
            pl.mover(x['id'], 'publish_queued', agente='agent2', etapa=f'Aprovado por você ({origem})')
    except Exception as e:  # noqa: BLE001 - a aprovação vale mesmo se o painel da esteira não atualizar
        print('aprovacoes: esteira', e)
    posts = []
    if ok:
        vid = render_sha[:12]
        destino = pg.VIDEOS / f'{vid}.mp4'
        if not destino.exists():
            tmp = pg.VIDEOS / f'{vid}.copia.tmp'
            shutil.copy(r['arquivo'], tmp)
            tmp.replace(destino)
        novas = []
        for rede in ok:
            if db.um('SELECT id FROM publicacoes WHERE chave=?', f'{render_sha}:{rede}'):
                continue            # este vídeo já foi entregue a esta rede antes
            novas.append(rede)
        if novas:
            post = pg.criar_post({'video': vid, 'redes': novas, 'quando': quando, 'titulo': titulo, 'legenda': legenda,
                                  'origem': 'agente3', 'direitos': {'origem': 'meu', 'nota': 'Vídeo original do Agente 3, aprovado por ' + origem},
                                  'projeto': pid, 'render_sha': render_sha, 'creditos': exigidos})
            for rede in novas:
                db.executar('INSERT OR IGNORE INTO publicacoes (id, aprovacao, render_sha, post, rede, chave, criado) VALUES (?,?,?,?,?,?,?)',
                            uuid.uuid4().hex[:16], aid, render_sha, post['id'], rede, f'{render_sha}:{rede}', agora)
            posts.append(post)

    def f(d, _p):
        d.setdefault('revisao', {}).setdefault('historico', []).append({'t': agora, 'decisao': 'aprovado', 'origem': origem, 'sha': render_sha})
        d['revisao']['status'] = 'aprovado'
        d['publicacao'] = {'aprovacao': aid, 'quando': quando, 'redes': ok, 'posts': [x['id'] for x in posts]}
        return {'status': 'queued_to_publish' if posts else 'approved'}
    pj.mudar_dados(pid, f)
    db.evento(por or origem, 'video_aprovado', 'projeto:' + pid, {'sha': render_sha, 'origem': origem, 'redes': ok, 'quando': quando})
    if (p.get('dados') or {}).get('linha'):
        import agenda_postagem as ag2
        ag2.acordar()          # vídeo de linha aprovado: a programação diária confere já
    return {'ok': True, 'aprovacao': db.um('SELECT * FROM aprovacoes WHERE id=?', aid), 'posts': posts, 'quando': quando}


def pedir_alteracao(pid: str, render_sha: str, texto: str, origem: str, por: str) -> dict:
    texto = (texto or '').strip()[:2000]
    if len(texto) < 3:
        raise ErroAprovacao(400, 'Escreva o que precisa mudar.')
    p = pj.obter(pid)
    r = _render_atual(p)
    if r and render_sha and render_sha != r['sha']:
        raise ErroAprovacao(409, 'O vídeo mudou depois que você abriu. Assista a versão nova antes de pedir correção.')
    if p['status'] not in ('ready_for_review', 'waiting_brief_approval', 'storyboard_ready'):
        raise ErroAprovacao(409, f'Este vídeo não está em revisão (situação: {p["status"]}).')
    agora = time.time()
    db.executar('INSERT INTO aprovacoes (id, projeto, render_sha, decisao, origem, por, texto, destinos, publicar_em, criado, chave) VALUES (?,?,?,?,?,?,?,?,?,?,NULL)',
                uuid.uuid4().hex[:16], pid, render_sha or '', 'alterar', origem[:20], por[:80], texto, '', 0, agora)
    db.executar('UPDATE desafios SET usado=? WHERE projeto=? AND usado IS NULL', agora, pid)

    def f(d, _p):
        d.setdefault('revisao', {}).setdefault('historico', []).append({'t': agora, 'decisao': 'alterar', 'origem': origem, 'texto': texto, 'sha': render_sha})
        d['revisao']['status'] = 'alterar'
        return {'status': 'changes_requested'}
    pj.mudar_dados(pid, f)
    # se o trabalho estava esperando a aprovação do roteiro, ele é cancelado e recomeça já com a correção
    for j in db.todos("SELECT id FROM jobs WHERE projeto=? AND status='aguardando_aprovacao'", pid):
        fila.cancelar(j['id'])
    import produtor
    job = produtor.produzir(pid, etapa='revisar', extra={'correcao': texto}, dispositivo=por)
    db.evento(por or origem, 'correcao_pedida', 'projeto:' + pid, {'origem': origem, 'texto': texto[:300]})
    return {'ok': True, 'job': job}


def rejeitar(pid: str, render_sha: str, motivo: str, origem: str, por: str) -> dict:
    p = pj.obter(pid)
    if p['status'] in ('queued_to_publish', 'posted'):
        raise ErroAprovacao(409, 'Este vídeo já foi aprovado. Cancele os posts em Publicações.')
    agora = time.time()
    db.executar('INSERT INTO aprovacoes (id, projeto, render_sha, decisao, origem, por, texto, destinos, publicar_em, criado, chave) VALUES (?,?,?,?,?,?,?,?,?,?,NULL)',
                uuid.uuid4().hex[:16], pid, render_sha or '', 'rejeitado', origem[:20], por[:80], (motivo or '')[:1000], '', 0, agora)
    db.executar('UPDATE desafios SET usado=? WHERE projeto=? AND usado IS NULL', agora, pid)
    for j in db.todos("SELECT id FROM jobs WHERE projeto=? AND status NOT IN ('concluido','falhou','cancelado')", pid):
        fila.cancelar(j['id'])

    def f(d, _p):
        d.setdefault('revisao', {}).setdefault('historico', []).append({'t': agora, 'decisao': 'rejeitado', 'origem': origem, 'texto': motivo, 'sha': render_sha})
        d['revisao']['status'] = 'rejeitado'
        return {'status': 'rejected'}
    pj.mudar_dados(pid, f)
    db.evento(por or origem, 'video_rejeitado', 'projeto:' + pid, {'origem': origem})
    return {'ok': True}


def aprovar_roteiro(pid: str, por: str, revisao: int | None = None) -> dict:
    """Libera o trabalho que esperava a aprovação do roteiro (ou começa a produção, se ainda não havia trabalho)."""
    p = pj.obter(pid)
    if revisao is not None and int(revisao) != p['revisao']:
        raise ErroAprovacao(409, 'O roteiro mudou depois que você abriu. Confira de novo.')
    if not p['dados'].get('cenas'):
        raise ErroAprovacao(400, 'Ainda não há roteiro para aprovar.')

    def f(d, _p):
        d['aprovacao_roteiro'] = {'aprovado': True, 't': time.time(), 'por': por, 'revisao': p['revisao']}
        return {}
    pj.mudar_dados(pid, f)
    esperando = db.todos("SELECT id FROM jobs WHERE projeto=? AND status='aguardando_aprovacao'", pid)
    for j in esperando:
        fila.liberar(j['id'])
    db.evento(por, 'roteiro_aprovado', 'projeto:' + pid)
    if esperando:
        return {'ok': True, 'job': fila.obter(esperando[0]['id'])}
    ativo = db.um("SELECT id FROM jobs WHERE projeto=? AND status IN ('agendado','na_fila','rodando','aguardando_tentativa')", pid)
    if ativo:
        return {'ok': True, 'job': fila.obter(ativo['id'])}
    import produtor
    return {'ok': True, 'job': produtor.produzir(pid, etapa='roteiro', dispositivo=por)}
