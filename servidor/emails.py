"""E-mails do Agente 3: vídeo pronto (com código de aprovação), roteiro pronto, falha — e leitura das RESPOSTAS.

Responder o e-mail funciona assim (IMAP, mesma senha de aplicativo do envio):
  APROVAR VID-AB12CD K7QM-2XPA
  CORRIGIR VID-AB12CD K7QM-2XPA deixe a narração mais curta na cena 3
  REJEITAR VID-AB12CD K7QM-2XPA

Proteções: só aceita remetentes autorizados, só respostas ao e-mail que o servidor mandou (In-Reply-To /
References), código de uso único preso ao projeto + hash do vídeo, cada e-mail é lido uma vez só
(anti-replay), texto citado é ignorado, e um limite de códigos errados bloqueia o desafio.
Nenhum link do e-mail aprova nada sozinho: o link só abre a tela de revisão no site.
"""
from __future__ import annotations

import email
import imaplib
import os
import re
import ssl
import threading
import time
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.utils import getaddresses, parseaddr
from pathlib import Path

import agente as ag
import aprovacoes as apv
import banco as db
import projetos as pj

LIMITE_ANEXO = int(os.getenv('LIMITE_ANEXO_MB', '12')) * 1048576
PADRAO_RESP = {'ativo': False, 'imap': '', 'porta': 993, 'remetentes': [], 'intervalo': 120}
CMD = re.compile(r'\b(APROVAR|APROVO|CORRIGIR|ALTERAR|REJEITAR)\b[\s:]+(VID-[A-Z0-9]{6})[\s:]+([A-Z0-9]{4}-?[A-Z0-9]{4})\b(.*)', re.I | re.S)


# ---------------------------------------------------------------- configuração das respostas
def config_respostas() -> dict:
    c = dict(PADRAO_RESP)
    c.update({k: v for k, v in (db.kv('respostas_email', {}) or {}).items() if k in PADRAO_RESP})
    return c


def salvar_respostas(d: dict) -> dict:
    c = config_respostas()
    if 'ativo' in d:
        c['ativo'] = bool(d['ativo'])
    if 'imap' in d:
        c['imap'] = re.sub(r'[^a-zA-Z0-9.-]', '', str(d['imap']))[:120]
    if 'porta' in d:
        try:
            c['porta'] = max(1, min(65535, int(d['porta'] or 993)))
        except (TypeError, ValueError):
            pass
    if 'remetentes' in d and isinstance(d['remetentes'], list):
        c['remetentes'] = [str(x).strip().lower()[:120] for x in d['remetentes'] if '@' in str(x)][:5]
    if 'intervalo' in d:
        try:
            c['intervalo'] = max(60, min(3600, int(d['intervalo'])))
        except (TypeError, ValueError):
            pass
    db.kv_gravar('respostas_email', c)
    return estado()


def _imap_host(cfg_email: dict, c: dict) -> tuple[str, int]:
    if c['imap']:
        return c['imap'], c['porta'] or 993
    dom = cfg_email['de'].rsplit('@', 1)[-1].lower()
    if dom in ('gmail.com', 'googlemail.com'):
        return 'imap.gmail.com', 993
    if dom in ('outlook.com', 'hotmail.com', 'live.com', 'outlook.com.br', 'msn.com'):
        return 'outlook.office365.com', 993
    if dom.startswith('yahoo.'):
        return 'imap.mail.yahoo.com', 993
    if dom in ('icloud.com', 'me.com'):
        return 'imap.mail.me.com', 993
    raise ag.ErroAgente(f'Não sei o servidor IMAP de "{dom}". Preencha o campo Servidor IMAP.')


def remetentes_autorizados() -> list:
    c = config_respostas()
    base = [ag.config()['email']['para'].strip().lower()]
    return [x for x in dict.fromkeys(base + c['remetentes']) if x]


def estado() -> dict:
    c = config_respostas()
    e = db.kv('imap_estado', {}) or {}
    cfg = ag.config()['email']
    return {**c, 'remetentes_autorizados': remetentes_autorizados(), 'caixa': cfg['de'], 'ultimo': e.get('ultimo', 0),
            'erro': e.get('erro', ''), 'lidos': e.get('lidos', 0), 'aplicados': e.get('aplicados', 0),
            'gmail_api': 'não implementado (use IMAP com a senha de aplicativo)'}


# ---------------------------------------------------------------- envio
def _projeto(pid: str) -> dict:
    return pj.obter(pid)


def _link(pid: str) -> str:
    return f'{apv.SITE}#revisar/{pid}'


def enviar_pronto(pid: str, sha: str) -> bool:
    """E-mail do vídeo pronto: resumo, link para revisar no site, código de aprovação e a prévia leve anexada."""
    cfg = ag.config()['email']
    if not cfg['para']:
        return False
    p = _projeto(pid)
    r = p['dados'].get('render') or {}
    if not sha or r.get('sha') != sha:
        return False
    codigo = apv.novo_desafio(pid, sha)
    referencia = apv.ref(pid)
    b = p['dados']['briefing']
    dest = b.get('destinos') or {}
    redes = ', '.join(x.capitalize() for x in dest.get('redes') or []) or 'nenhuma rede escolhida (só fica salvo)'
    avisos = '\n'.join('  - ' + a for a in r.get('avisos') or []) or '  - nenhum'
    roteiro = p['dados'].get('roteiro') or {}
    corpo = (f'O vídeo "{p["titulo"]}" ficou pronto e passou na conferência automática.\n\n'
             f'Duração: {r.get("duracao", 0):.0f} s   Formato: {r.get("largura")}x{r.get("altura")}   Versão: {r.get("versao")}\n'
             f'Estilo: {b.get("estilo")}   Redes: {redes}\n'
             f'Avisos da conferência:\n{avisos}\n\n'
             f'Legenda sugerida:\n{(roteiro.get("legenda") or "")[:600]}\n\n'
             f'ASSISTA E DECIDA NO SITE: {_link(pid)}\n'
             f'(o link só abre a revisão; nada é aprovado sem você confirmar lá)\n\n'
             f'Ou responda ESTE e-mail com UMA linha:\n'
             f'  APROVAR {referencia} {codigo}\n'
             f'  CORRIGIR {referencia} {codigo} <o que mudar>\n'
             f'  REJEITAR {referencia} {codigo}\n\n'
             f'O código vale 7 dias, uma vez só, e só para esta versão do vídeo.\n'
             f'Nada é publicado sem a sua aprovação.')
    prev = None
    try:
        aid = (r.get('assets') or {}).get('preview')
        if aid and cfg.get('anexar', True):
            a = pj.asset(aid)
            if a['tamanho'] <= LIMITE_ANEXO:
                prev = Path(a['caminho'])
    except pj.ErroProjeto:
        prev = None
    mid = ag.enviar_email(f'Vídeo pronto para aprovação [{referencia}]', corpo, prev, f'previa-{referencia}.mp4',
                          cabecalhos={'X-EstudioClip': f'{referencia};v{r.get("versao")}'}, prefixo='EstúdioClip — ')
    apv.marcar_message_id(pid, sha, mid)
    db.evento('agente3', 'email_aprovacao', 'projeto:' + pid, {'sha': sha, 'anexo': bool(prev)})
    return True


def avisar_roteiro(pid: str) -> bool:
    p = _projeto(pid)
    cenas = p['dados'].get('cenas') or []
    resumo = '\n'.join(f'{i + 1}. {c.get("titulo", "")}: {c.get("texto", "")[:140]}' for i, c in enumerate(cenas[:12]))
    return ag.avisar('corte', f'Roteiro pronto para conferir [{apv.ref(pid)}]',
                     f'O roteiro e o storyboard de "{p["titulo"]}" estão prontos.\n\n{resumo}\n\n'
                     f'Confira, edite se quiser e aprove no site para o vídeo ser produzido: {_link(pid)}')


def avisar_falha(pid: str, msg: str) -> bool:
    try:
        p = _projeto(pid)
        titulo = p['titulo']
    except pj.ErroProjeto:
        titulo = pid
    return ag.avisar('falha', f'Falha na produção [{apv.ref(pid)}]',
                     f'A produção de "{titulo}" parou depois das tentativas automáticas.\n\nMotivo: {msg[:600]}\n\n'
                     f'Veja em Fila e aprovações e toque em "Tentar de novo": {apv.SITE}#fila')


# ---------------------------------------------------------------- leitura das respostas
def _decod(v: str) -> str:
    try:
        return str(make_header(decode_header(v or '')))
    except Exception:  # noqa: BLE001
        return v or ''


def _texto_sem_citacao(msg) -> str:
    corpo = ''
    if msg.is_multipart():
        for parte in msg.walk():
            if parte.get_content_type() == 'text/plain' and not parte.get_filename():
                corpo = parte.get_payload(decode=True).decode(parte.get_content_charset() or 'utf-8', 'replace')
                break
        if not corpo:
            for parte in msg.walk():
                if parte.get_content_type() == 'text/html':
                    html = parte.get_payload(decode=True).decode(parte.get_content_charset() or 'utf-8', 'replace')
                    html = re.sub(r'(?is)<blockquote.*?</blockquote>|<div class="gmail_quote.*', '', html)
                    corpo = re.sub(r'<[^>]+>', '\n', html)
                    break
    else:
        corpo = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', 'replace') if msg.get_payload() else ''
    linhas = []
    for ln in corpo.splitlines():
        s = ln.strip()
        if s.startswith('>'):
            continue
        if re.match(r'^(Em .{3,120}escreveu:|On .{3,120}wrote:|-----Original Message-----|De: |From: )', s):
            break
        linhas.append(ln)
    return '\n'.join(linhas)[:5000]


def _autenticado(msg, remetente: str) -> bool:
    """Se o provedor marcou o e-mail (Authentication-Results), exige DKIM ou SPF aprovado para o domínio do remetente."""
    ar = ' '.join(msg.get_all('Authentication-Results') or [])
    if not ar:
        return True
    dom = remetente.rsplit('@', 1)[-1].lower()
    return bool(re.search(r'dkim=pass[^;]*header\.(?:i|d)=@?[\w.-]*' + re.escape(dom), ar, re.I) or
                re.search(r'spf=pass[^;]*smtp\.mailfrom=[^;\s]*' + re.escape(dom), ar, re.I) or
                re.search(r'dmarc=pass[^;]*header\.from=' + re.escape(dom), ar, re.I))


def _ids_da_conversa(msg) -> set:
    ids = set()
    for h in ('In-Reply-To', 'References'):
        ids |= set(re.findall(r'<[^<>\s]+>', msg.get(h, '') or ''))
    return ids


def processar(msg) -> dict:
    """Aplica UMA resposta. Devolve o que aconteceu (vai para emails_lidos e para a confirmação)."""
    mid = (msg.get('Message-ID') or '').strip()[:300]
    if not mid:
        return {'ok': False, 'motivo': 'e-mail sem Message-ID'}
    if db.um('SELECT 1 AS x FROM emails_lidos WHERE message_id=?', mid):
        return {'ok': False, 'motivo': 'já lido', 'repetido': True}
    rem = parseaddr(msg.get('From', ''))[1].strip().lower()
    out = {'ok': False, 'remetente': rem}
    try:
        if rem not in remetentes_autorizados():
            out['motivo'] = 'remetente não autorizado'
            return out
        if len(getaddresses(msg.get_all('From', []))) != 1 or not _autenticado(msg, rem):
            out['motivo'] = 'remetente não confirmado pelo provedor de e-mail'
            return out
        m = CMD.search(_texto_sem_citacao(msg))
        if not m:
            out['motivo'] = 'nenhum comando APROVAR/CORRIGIR/REJEITAR com código encontrado'
            return out
        acao, referencia, codigo, resto = m.group(1).upper(), m.group(2).upper(), m.group(3), m.group(4).strip()
        pid = apv.pid_da_ref(referencia)
        if not pid:
            out['motivo'] = f'vídeo {referencia} não encontrado'
            return out
        conversa = _ids_da_conversa(msg)
        d_ativo = apv.desafio_ativo(pid)
        if not d_ativo or not d_ativo['message_id'] or d_ativo['message_id'] not in conversa:
            out['motivo'] = 'esta resposta não é do e-mail mais recente deste vídeo'
            return out
        d = apv.validar_desafio(pid, codigo)
        out.update(projeto=pid, ref=referencia, acao=acao)
        if acao in ('APROVAR', 'APROVO'):
            r = apv.aprovar(pid, d['render_sha'], None, 'email', rem, chave='email:' + mid)
            out.update(ok=True, quando=r.get('quando'), posts=[p['id'] for p in r.get('posts', [])])
        elif acao in ('CORRIGIR', 'ALTERAR'):
            texto = resto.split('\n\n')[0].strip()[:2000]
            apv.pedir_alteracao(pid, d['render_sha'], texto, 'email', rem)
            out.update(ok=True, texto=texto)
        else:
            apv.rejeitar(pid, d['render_sha'], resto[:500], 'email', rem)
            out.update(ok=True)
        return out
    except apv.ErroAprovacao as e:
        out['motivo'] = str(e)
        return out
    except Exception as e:  # noqa: BLE001
        out['motivo'] = 'erro: ' + str(e)[:200]
        return out
    finally:
        import json
        db.executar('INSERT OR IGNORE INTO emails_lidos (message_id, t, resultado) VALUES (?,?,?)', mid, time.time(),
                    json.dumps({k: v for k, v in out.items() if k != 'repetido'}, ensure_ascii=False)[:2000])
        if out.get('remetente') and not out.get('repetido'):
            db.evento('email:' + out.get('remetente', ''), 'resposta_email', 'projeto:' + out.get('projeto', ''), out)


def _confirmar(msg, r: dict):
    """Responde na mesma conversa dizendo o que foi feito (só para remetente autorizado)."""
    if r.get('repetido') or r.get('remetente') not in remetentes_autorizados():
        return
    mid = msg.get('Message-ID', '')
    if r.get('ok'):
        if r.get('acao') in ('APROVAR', 'APROVO'):
            quando = datetime.fromtimestamp(r['quando']).strftime('%d/%m %H:%M') if r.get('quando') else '—'
            texto = f'Aprovado. {"Agendado para " + quando + "." if r.get("posts") else "Nenhuma rede escolhida: o vídeo ficou salvo como aprovado."}'
        elif r.get('acao') in ('CORRIGIR', 'ALTERAR'):
            texto = f'Correção recebida: "{r.get("texto", "")[:200]}". O vídeo vai ser refeito e você recebe um novo e-mail.'
        else:
            texto = 'Vídeo rejeitado. Nada será publicado.'
    else:
        texto = 'Não fiz nada: ' + r.get('motivo', '')
    try:
        ag.enviar_email(f'Re: {r.get("ref", "")} {texto[:60]}', texto, cabecalhos={'In-Reply-To': mid, 'References': mid}, prefixo='EstúdioClip — ')
    except ag.ErroAgente as e:
        print('emails: confirmação', e)


def ler_respostas() -> dict:
    """Uma passada na caixa de entrada: só não lidos dos últimos 8 dias com VID- no assunto."""
    c = config_respostas()
    cfg = ag.config()['email']
    senha = ag.segredos()['email_senha']
    e = db.kv('imap_estado', {}) or {}
    if not (c['ativo'] and cfg['de'] and senha):
        return {'ok': False, 'motivo': 'leitura de respostas desligada ou e-mail não configurado'}
    host, porta = _imap_host(cfg, c)
    lidos = aplicados = 0
    try:
        if os.getenv('IMAP_SEM_TLS') == '1':          # só para testes locais
            im = imaplib.IMAP4(host, porta)
        else:
            im = imaplib.IMAP4_SSL(host, porta, ssl_context=ssl.create_default_context(), timeout=60)
        with im:
            im.login(cfg['de'], senha)
            im.select('INBOX')
            desde = (datetime.now() - timedelta(days=8)).strftime('%d-%b-%Y')
            st, dados = im.search(None, 'UNSEEN', 'SINCE', desde, 'SUBJECT', 'VID-')
            for num in (dados[0].split() if st == 'OK' and dados and dados[0] else [])[:30]:
                st, partes = im.fetch(num, '(BODY.PEEK[])')
                if st != 'OK' or not partes or not isinstance(partes[0], tuple):
                    continue
                msg = email.message_from_bytes(partes[0][1])
                r = processar(msg)
                lidos += 1
                if r.get('ok'):
                    aplicados += 1
                _confirmar(msg, r)
                im.store(num, '+FLAGS', '\\Seen')
        e.update(ultimo=time.time(), erro='', lidos=e.get('lidos', 0) + lidos, aplicados=e.get('aplicados', 0) + aplicados)
    except imaplib.IMAP4.error as x:
        e.update(ultimo=time.time(), erro='A caixa recusou o login IMAP (use senha de aplicativo e ative o IMAP): ' + str(x)[:160])
    except (OSError, ssl.SSLError, ag.ErroAgente) as x:
        e.update(ultimo=time.time(), erro=str(x)[:200])
    db.kv_gravar('imap_estado', e)
    return {'ok': not e.get('erro'), 'lidos': lidos, 'aplicados': aplicados, 'erro': e.get('erro', '')}


def iniciar():
    def laco():
        while True:
            c = config_respostas()
            try:
                if c['ativo']:
                    ler_respostas()
            except Exception as x:  # noqa: BLE001
                print('emails:', x)
            time.sleep(max(60, c['intervalo']))
    threading.Thread(target=laco, daemon=True, name='emails').start()


def _assunto(msg) -> str:
    return _decod(msg.get('Subject', ''))
