"""Avisos pelo WhatsApp (CallMeBot, grátis): o servidor manda uma mensagem de texto para o SEU número.

Como ativar (uma vez): pegue o número atual do robô em https://www.callmebot.com/blog/free-api-whatsapp-messages/,
salve nos contatos, mande para ele no WhatsApp "I allow callmebot to send me messages" e ele responde com a sua apikey. Cole número e apikey no site
(Agentes > Avisos e chaves > WhatsApp). A apikey fica cifrada só no servidor.

A mensagem só AVISA e traz o link: a aprovação final continua sendo um toque seu na tela de revisão do site
(nenhum link aprova nada sozinho). O CallMeBot é um serviço de terceiros: o texto do aviso passa por ele,
por isso a mensagem não leva senha, código de aprovação nem o vídeo.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.getenv('BASE_CALLMEBOT', 'https://api.callmebot.com')
LIMITE = 1400              # o CallMeBot corta mensagens muito longas
_TRAVA = threading.Lock()
_ULTIMO = [0.0]


class ErroWhatsApp(Exception):
    pass


def numero_limpo(n: str) -> str:
    d = re.sub(r'\D', '', n or '')
    return d if 10 <= len(d) <= 15 else ''


PONTE = os.getenv('PONTE_WHATSAPP', 'http://127.0.0.1:' + os.getenv('PORTA_PONTE', '8788'))


def ponte_ligada() -> bool:
    """A ponte do WhatsApp Web (whatsapp-ponte/ponte.mjs) foi pareada e está rodando neste celular?"""
    dados = Path(os.getenv('DADOS', str(Path.home() / '.estudioclip')))
    if not (dados / 'whatsapp-ligado').exists():
        return False
    try:
        with urllib.request.urlopen(PONTE + '/estado', timeout=3) as r:
            return bool(json.loads(r.read(2000) or b'{}').get('pronta'))
    except (OSError, ValueError):
        return False


def _pela_ponte(texto: str) -> None:
    req = urllib.request.Request(PONTE + '/enviar', data=json.dumps({'texto': texto}).encode(), method='POST',
                                 headers={'Content-Type': 'application/json', 'X-Token': os.getenv('TOKEN', '')})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read(2000)
    except urllib.error.HTTPError as e:
        raise ErroWhatsApp('A ponte do WhatsApp não mandou: ' + e.read(300).decode('utf-8', 'replace')) from None
    except OSError as e:
        raise ErroWhatsApp(f'A ponte do WhatsApp não respondeu: {getattr(e, "reason", e)}') from None


def enviar_aviso(numero: str, apikey: str, texto: str) -> str:
    """Pela ponte do WhatsApp Web (se pareada), senão pelo CallMeBot. Devolve por onde foi."""
    if ponte_ligada():
        _pela_ponte(texto)
        return 'ponte'
    enviar(numero, apikey, texto)
    return 'callmebot'


def enviar(numero: str, apikey: str, texto: str) -> None:
    num = numero_limpo(numero)
    if not num or not apikey:
        raise ErroWhatsApp('O WhatsApp não está ligado: rode no Termux  bash iniciar-termux.sh whatsapp SEU_NUMERO  '
                           '(ou preencha número e chave do CallMeBot).')
    texto = texto.strip()
    if len(texto) > LIMITE:
        texto = texto[:LIMITE - 1] + '…'
    q = urllib.parse.urlencode({'phone': '+' + num, 'text': texto, 'apikey': apikey})
    with _TRAVA:                          # o CallMeBot pede um intervalo entre mensagens
        espera = 4 - (time.time() - _ULTIMO[0])
        if espera > 0:
            time.sleep(espera)
        try:
            with urllib.request.urlopen(f'{BASE}/whatsapp.php?{q}', timeout=30) as r:
                corpo = r.read(4000).decode('utf-8', 'replace')
        except OSError as e:
            raise ErroWhatsApp(f'Não consegui falar com o CallMeBot: {getattr(e, "reason", e)}') from None
        finally:
            _ULTIMO[0] = time.time()
    baixo = corpo.lower()
    if 'apikey is invalid' in baixo or 'invalid apikey' in baixo:
        raise ErroWhatsApp('A chave do CallMeBot não confere com este número. Peça uma nova mandando a mensagem de ativação de novo.')
    if 'error' in baixo and 'queued' not in baixo and 'sent' not in baixo:
        raise ErroWhatsApp('O CallMeBot recusou a mensagem: ' + re.sub(r'<[^>]+>', ' ', corpo)[:200].strip())
