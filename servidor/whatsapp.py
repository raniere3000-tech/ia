"""Avisos pelo WhatsApp (CallMeBot, grátis): o servidor manda uma mensagem de texto para o SEU número.

Como ativar (uma vez): pegue o número atual do robô em https://www.callmebot.com/blog/free-api-whatsapp-messages/,
salve nos contatos, mande para ele no WhatsApp "I allow callmebot to send me messages" e ele responde com a sua apikey. Cole número e apikey no site
(Agentes > Avisos e chaves > WhatsApp). A apikey fica cifrada só no servidor.

A mensagem só AVISA e traz o link: a aprovação final continua sendo um toque seu na tela de revisão do site
(nenhum link aprova nada sozinho). O CallMeBot é um serviço de terceiros: o texto do aviso passa por ele,
por isso a mensagem não leva senha, código de aprovação nem o vídeo.
"""
from __future__ import annotations

import os
import re
import threading
import time
import urllib.parse
import urllib.request

BASE = os.getenv('BASE_CALLMEBOT', 'https://api.callmebot.com')
LIMITE = 1400              # o CallMeBot corta mensagens muito longas
_TRAVA = threading.Lock()
_ULTIMO = [0.0]


class ErroWhatsApp(Exception):
    pass


def numero_limpo(n: str) -> str:
    d = re.sub(r'\D', '', n or '')
    return d if 10 <= len(d) <= 15 else ''


def enviar(numero: str, apikey: str, texto: str) -> None:
    num = numero_limpo(numero)
    if not num or not apikey:
        raise ErroWhatsApp('Falta o número (com DDI e DDD, ex.: 55 11 91234-5678) ou a chave do CallMeBot.')
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
