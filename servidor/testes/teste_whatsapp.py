"""Avisos pelo WhatsApp (CallMeBot simulado): avisos, vídeo pronto só depois do diretor, chave nunca volta para o site.

Rodar:  python servidor/testes/teste_whatsapp.py
Sem internet: o CallMeBot é simulado aqui.
"""
import json
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import sys
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='whatsapp-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
recebidas = []
resposta = ['Message queued. You will receive it in a few seconds.']


class Falso(BaseHTTPRequestHandler):
    def do_GET(self):
        recebidas.append(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(resposta[0].encode())

    def log_message(self, *a):
        pass


srv = HTTPServer(('127.0.0.1', 0), Falso)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ['BASE_CALLMEBOT'] = f'http://127.0.0.1:{srv.server_port}'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import banco as db  # noqa: E402
import api_v1  # noqa: E402
import agente as ag  # noqa: E402
import emails  # noqa: E402
import produtor  # noqa: E402
import projetos as pj  # noqa: E402
import whatsapp  # noqa: E402

whatsapp._ULTIMO[0] = 0
falhas = 0


def confere(c, nome):
    global falhas
    print(('ok    ' if c else 'FALHA ') + nome)
    falhas += 0 if c else 1


db.migrar()
api_v1.iniciar()
ag.enviar_email = lambda *a, **k: 'mid'

confere(not ag.avisar_whatsapp('a1_falha', 'x'), 'desligado: não manda nada')
try:
    ag.avisar_whatsapp('teste', 'x', erro=True)
    confere(False, 'teste sem número avisa o que falta')
except ag.ErroAgente as e:
    confere('número' in str(e), 'teste sem número avisa o que falta')

ag.salvar_config({'whatsapp': {'ligado': True, 'numero': '+55 (11) 91234-5678'}})
ag.salvar_segredos({'callmebot': 'CHAVE-SECRETA'})
confere(ag.config()['whatsapp']['numero'] == '5511912345678', 'número fica só com os dígitos')
v = ag.ver()
confere(v['chaves']['callmebot'] is True and 'CHAVE-SECRETA' not in json.dumps(v), 'a chave fica só no servidor')

ag.avisar('falha', 'Um vídeo não pôde ser cortado', 'Vídeo: X\nMotivo: Y\nVeja: https://site/#fila', zap_tipo='a1_falha')
m = recebidas[-1]
confere(m['phone'] == ['+5511912345678'] and m['apikey'] == ['CHAVE-SECRETA'] and 'Motivo: Y' in m['text'][0] and 'https://site/#fila' in m['text'][0],
        'falha chega no WhatsApp com o motivo e o link')
n = len(recebidas)
ag.avisar('agendado', 'Post agendado', 'x', zap_tipo='a2_agendado')
confere(len(recebidas) == n, 'aviso desmarcado não vai para o WhatsApp')

# vídeo pronto: só depois que o diretor aprovou
p = produtor.novo({'briefing': {'tema': 'T', 'estilo': 'animado2d', 'destinos': {'redes': ['youtube']}},
                   'roteiro': {'titulo': 'Meu vídeo', 'legenda': 'x', 'hashtags': [], 'cenas': [{'titulo': 'A', 'texto': 'b'}]}})
pid = p['id']
sha = 'a' * 64
pj.mudar_dados(pid, lambda d, _p: (d.update(render={'id': 'r1', 'versao': 1, 'sha': sha, 'duracao': 42.0},
                                            qualidade={'status': 'alerta_visual', 'problemas': [{'tipo': 'cabeca_cortada', 'severidade': 'alta', 'descricao': 'x', 'cena_id': 'c1', 'natureza': 'objetivo'}]}), {'status': 'ready_for_review'})[1])
n = len(recebidas)
confere(not emails.zap_pronto(pid, sha) and len(recebidas) == n, 'vídeo reprovado pelo diretor não chega no WhatsApp')
pj.mudar_dados(pid, lambda d, _p: d.update(qualidade={'status': 'apto_para_revisao_humana', 'problemas': []},
                                           diretor={'veredito': 'aprovado', 'sha': sha, 'motivos': [], 'tentativas': 2}))
emails.enviar_pronto(pid, sha)
t = recebidas[-1]['text'][0]
confere(len(recebidas) == n + 1 and 'Meu vídeo' in t and 'diretor de qualidade' in t and 'refeito 2' in t and f'#revisar/{pid}' in t,
        'vídeo aprovado pelo diretor chega com o link para a sua aprovação final')
confere('CHAVE' not in t and 'APROVAR' not in t, 'a mensagem não leva código de aprovação nem chave')

resposta[0] = 'APIKey is invalid. Please activate again.'
try:
    ag.avisar_whatsapp('teste', 'x', erro=True)
    confere(False, 'chave errada: explica o que fazer')
except ag.ErroAgente as e:
    confere('não confere' in str(e), 'chave errada: explica o que fazer')
confere(not ag.avisar_whatsapp('a1_falha', 'x') and any('WhatsApp não enviado' in l['texto'] for l in ag.estado()['log'][:3]),
        'erro no envio fica no histórico e não trava o resto')

resposta[0] = 'Message queued.'
ag.salvar_config({'whatsapp': {'avisos': {'a2_postado': False}}})
n = len(recebidas)
ag.avisar('postado', 'Post enviado', 'x', zap_tipo='a2_postado')
ag.avisar('falha', 'Falha na produção', 'y', zap_tipo='a3_falha')
confere(len(recebidas) == n + 1 and 'Falha na produção' in recebidas[-1]['text'][0], 'cada agente tem a sua escolha: Agente 2 desligado não cala o Agente 3')
print('\nTUDO OK' if not falhas else f'\n{falhas} FALHA(S)')
sys.exit(1 if falhas else 0)
