"""Teste de ponta a ponta do servidor 2.0 (sem internet): Gemini, SMTP falsos; FFmpeg de verdade.

Rodar:  python servidor/testes/teste_agente3.py
Cobre: login e pareamento, projeto com conflito 409, fila, Agente 3 (roteiro -> aprovação do roteiro ->
narração -> render -> conferência), e-mail com código, resposta por e-mail (remetente, código, replay),
regra de ouro da publicação, link assinado com Range, backup e restauração de teste.
"""
import base64
import hashlib
import hmac
import json
import math
import os
import re
import socket
import socketserver
import struct
import sys
import tempfile
import threading
import time
import urllib.request
from email.message import EmailMessage
from email import message_from_bytes as _mfb, policy


def message_from_bytes(b):
    return _mfb(b, policy=policy.default)
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-teste-'))
os.environ.update(DADOS=str(TMP / 'dados'), BANCO_ARQ=str(TMP / 'dados' / 'studio.sqlite'), CHAVE_MESTRA_ARQ=str(TMP / 'chave'),
                  TOKEN='senha-de-teste-123', FILA_INTERVALO='0.3', ESPERA_INICIAL_AGENTE='99999', BACKUP_DIARIO='0',
                  EMAIL_SEM_TLS='1', INTERVALO_AGENDA='1')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ok_n = falhas = 0


def confere(cond, nome):
    global ok_n, falhas
    if cond:
        ok_n += 1
        print('  ok ', nome)
    else:
        falhas += 1
        print('  FALHOU', nome)


# ---------------------------------------------------------------- Gemini falso
ROTEIRO = {'titulo': 'Por que o céu é azul', 'legenda': 'A luz do sol explica.', 'hashtags': ['#ciencia'],
           'cenas': [{'titulo': 'A pergunta', 'texto': 'Por que o céu é azul?', 'destaque': 'Céu azul'},
                     {'titulo': 'A luz', 'texto': 'A luz do sol tem todas as cores.', 'destaque': 'Todas as cores', 'numero': 7, 'unidade': 'cores'},
                     {'titulo': 'O ar', 'texto': 'O ar espalha mais o azul.', 'destaque': 'Espalha o azul'}]}
PEDIDOS = []


class Gemini(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        corpo = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        PEDIDOS.append(self.path)
        if 'tts' in self.path:
            pcm = b''.join(struct.pack('<h', int(8000 * math.sin(2 * math.pi * 220 * i / 24000))) for i in range(int(24000 * 1.6)))
            r = {'candidates': [{'content': {'parts': [{'inlineData': {'mimeType': 'audio/pcm', 'data': base64.b64encode(pcm).decode()}}]}}]}
        else:
            r = {'candidates': [{'content': {'parts': [{'text': json.dumps(ROTEIRO, ensure_ascii=False)}]}}], 'usageMetadata': {}}
        b = json.dumps(r).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)


def livre():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


pg_port = livre()
threading.Thread(target=ThreadingHTTPServer(('127.0.0.1', pg_port), Gemini).serve_forever, daemon=True).start()
os.environ['BASE_GEMINI'] = f'http://127.0.0.1:{pg_port}'

# ---------------------------------------------------------------- SMTP falso
EMAILS = []


class Smtp(socketserver.StreamRequestHandler):
    def handle(self):
        w = lambda s: self.wfile.write((s + '\r\n').encode())
        w('220 teste')
        dados = None
        while True:
            ln = self.rfile.readline()
            if not ln:
                return
            cmd = ln.decode(errors='replace').strip()
            if dados is not None:
                if cmd == '.':
                    EMAILS.append(message_from_bytes(b''.join(dados)))
                    dados = None
                    w('250 ok')
                else:
                    dados.append(ln[1:] if ln.startswith(b'..') else ln)
                continue
            u = cmd.upper()
            if u.startswith('EHLO') or u.startswith('HELO'):
                w('250 teste')
            elif u == 'DATA':
                dados = []
                w('354 vai')
            elif u == 'QUIT':
                w('221 tchau')
                return
            else:
                w('250 ok')


smtp_port = livre()
socketserver.ThreadingTCPServer.allow_reuse_address = True
threading.Thread(target=socketserver.ThreadingTCPServer(('127.0.0.1', smtp_port), Smtp).serve_forever, daemon=True).start()

# ---------------------------------------------------------------- servidor de verdade
import servidor as S  # noqa: E402
import agente as ag  # noqa: E402
import postagem as pg  # noqa: E402
import emails  # noqa: E402
import banco as db  # noqa: E402

S.ligar_servicos()
porta = livre()
threading.Thread(target=ThreadingHTTPServer(('127.0.0.1', porta), S.Handler).serve_forever, daemon=True).start()
BASE = f'http://127.0.0.1:{porta}'


def api(metodo, caminho, corpo=None, cab=None, cru=False):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    h = {'Content-Type': 'application/json', **(cab or {})}
    req = urllib.request.Request(BASE + caminho, data=dados, method=metodo, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read()
            return r.status, (b if cru else json.loads(b or b'{}')), dict(r.headers)
    except urllib.error.HTTPError as e:
        b = e.read()
        try:
            return e.code, json.loads(b), dict(e.headers)
        except ValueError:
            return e.code, b, dict(e.headers)


print('Sessão e aparelhos')
st, r, _ = api('POST', '/api/v1/sessao/login', {'senha': 'errada', 'nome': 'X'})
confere(st == 401, 'senha errada recusada')
st, r, _ = api('POST', '/api/v1/sessao/login', {'senha': 'senha-de-teste-123', 'nome': 'Celular'})
confere(st == 200 and len(r['sessao']) > 30, 'login cria sessão do aparelho')
SES = {'X-Sessao': r['sessao']}
st, r, _ = api('GET', '/api/v1/projetos')
confere(st == 401, 'sem sessão não lista projetos')
st, r, _ = api('POST', '/api/v1/pareamento/iniciar', {'nome': 'Notebook'}, SES)
codigo = r['codigo']
st, r2, _ = api('POST', '/api/v1/pareamento/completar', {'codigo': codigo, 'nonce': 'abc123', 'nome': 'Notebook'})
limpo = codigo.replace('-', '')
confere(st == 200 and r2['prova'] == hmac.new(limpo.encode(), b'abc123', hashlib.sha256).hexdigest(), 'pareamento prova que conhece o código')
st, _, _ = api('POST', '/api/v1/pareamento/completar', {'codigo': codigo, 'nonce': 'x'})
confere(st == 401, 'código de pareamento é de uso único')
NB = {'X-Sessao': r2['sessao']}
st, r, _ = api('GET', '/api/v1/aparelhos', None, SES)
nb = next(a for a in r['aparelhos'] if a['nome'] == 'Notebook')
st, _, _ = api('DELETE', f'/api/v1/aparelhos/{nb["id"]}', None, SES)
st, _, _ = api('GET', '/api/v1/projetos', None, NB)
confere(st == 401, 'aparelho desconectado perde acesso')

print('Projetos e conflito')
st, p, _ = api('POST', '/api/v1/projetos', {'tipo': 'manual', 'titulo': 'Teste', 'dados': {'a': 1}}, SES)
st, p2, h = api('PATCH', f'/api/v1/projetos/{p["id"]}', {'revisao': p['revisao'], 'dados': {'a': 2}}, SES)
confere(st == 200 and p2['revisao'] == p['revisao'] + 1 and h.get('ETag'), 'salvar aumenta a revisão')
st, r, _ = api('PATCH', f'/api/v1/projetos/{p["id"]}', {'revisao': p['revisao'], 'dados': {'a': 3}}, SES)
confere(st == 409 and r.get('revisao') == p2['revisao'], 'revisão antiga dá conflito 409 com a revisão atual')

print('Configura chave e e-mail do agente')
st, _, _ = api('POST', '/agente/chaves', {'gemini': 'chave-falsa', 'email_senha': 'x'}, SES)
st, _, _ = api('POST', '/agente/config', {'email': {'para': 'dono@exemplo.com', 'de': 'robo@exemplo.com', 'smtp': '127.0.0.1', 'porta': smtp_port}}, SES)
confere(st == 200, 'configuração salva com sessão de aparelho (rotas antigas)')

print('Agente 3: produção')
briefing = {'tema': 'Por que o céu é azul', 'cenas_qtd': 3, 'duracao_alvo': 12, 'estilo': 'quadro_branco', 'voz': 'Puck',
            'modo_aprovacao': 'assistido', 'destinos': {'redes': ['kwai'], 'quando': 'agora'}}
st, proj, _ = api('POST', '/api/v1/agente3/projetos', {'briefing': briefing, 'produzir': True}, SES)
confere(st == 200 and proj['tipo'] == 'agente3', 'projeto do Agente 3 criado e na fila')
PID = proj['id']


def esperar(cond, seg=240):
    t = time.time()
    while time.time() - t < seg:
        st, r, _ = api('GET', f'/api/v1/projetos/{PID}/revisao', None, SES)
        if cond(r):
            return r
        time.sleep(0.5)
    return r


r = esperar(lambda r: r['projeto']['status'] == 'waiting_brief_approval')
confere(r['projeto']['status'] == 'waiting_brief_approval' and len(r['projeto']['dados']['cenas']) == 3, 'roteiro gerado e esperando aprovação')
confere(r['job']['status'] == 'aguardando_aprovacao', 'trabalho fica esperando (não renderiza sem aprovar)')
confere(any('Roteiro pronto' in (m['Subject'] or '') for m in EMAILS), 'e-mail de roteiro pronto enviado')
st, _, _ = api('POST', f'/api/v1/projetos/{PID}/aprovar-roteiro', {}, SES)
t0 = time.time()
r = esperar(lambda r: r['projeto']['status'] == 'failed' or (r['job'] or {}).get('status') in ('concluido', 'falhou'), 400)
print(f'     (produção levou {time.time() - t0:.0f}s)')
confere(r['projeto']['status'] == 'ready_for_review', 'vídeo produzido e pronto para revisão')
if r['projeto']['status'] != 'ready_for_review':
    print(json.dumps(r['job'], ensure_ascii=False)[:800])
    sys.exit(1)
render = r['projeto']['dados']['render']
arq = Path(db.um('SELECT arquivo FROM renders WHERE sha256=?', render['sha'])['arquivo'])
import renderizador as rd  # noqa: E402
info = rd.sonda(arq)
vs = [s for s in info['streams'] if s['codec_type'] == 'video'][0]
confere((vs['width'], vs['height'], vs['codec_name']) == (1080, 1920, 'h264'), 'ffprobe: 1080x1920 H.264')
confere(any(s['codec_type'] == 'audio' and s['codec_name'] == 'aac' for s in info['streams']), 'ffprobe: áudio AAC')
confere(rd.sha256(arq) == render['sha'], 'hash do arquivo confere com o registrado')
confere(pg.posts() == [], 'nada foi publicado ao terminar o render')
pronto = [m for m in EMAILS if 'aprovação' in (m['Subject'] or '')]
confere(len(pronto) == 1, 'e-mail de vídeo pronto enviado')
corpo = pronto[0].get_body(('plain',)).get_content()
cod = re.search(r'APROVAR (VID-\w{6}) (\w{4}-\w{4})', corpo)
confere(bool(cod) and 'senha-de-teste' not in corpo and 'X-Sessao' not in corpo, 'e-mail tem código e não tem senha nem sessão')
confere(any(p.get_filename() for p in pronto[0].iter_attachments()), 'prévia anexada')
ref, code = cod.group(1), cod.group(2)
MID = pronto[0]['Message-ID']

print('Links e Range')
url = r['links']['video']
st, b, h = api('GET', url, None, {'Range': 'bytes=0-99'}, cru=True)
confere(st == 206 and len(b) == 100 and h.get('Content-Range', '').startswith('bytes 0-99/'), 'link assinado responde com Range (206)')
st, _, _ = api('GET', url.replace('sig=', 'sig=00'), None, None, cru=True)
confere(st == 403, 'link adulterado recusado')

print('Aprovação')
st, r2, _ = api('POST', f'/api/v1/projetos/{PID}/aprovar', {'render_sha': 'outro'}, SES)
confere(st == 409, 'aprovar hash diferente é recusado')


def resposta(texto, de='dono@exemplo.com', em_resposta=MID, mid=None):
    m = EmailMessage()
    m['From'] = de
    m['To'] = 'robo@exemplo.com'
    m['Subject'] = f'Re: Vídeo pronto [{ref}]'
    m['Message-ID'] = mid or f'<{time.time()}@exemplo.com>'
    if em_resposta:
        m['In-Reply-To'] = em_resposta
    m.set_content(texto + '\n\n> APROVAR ' + ref + ' ' + code + '\n')
    return message_from_bytes(bytes(m))


x = emails.processar(resposta(f'APROVAR {ref} {code}', de='intruso@exemplo.com'))
confere(not x['ok'] and 'autorizado' in x['motivo'], 'remetente estranho ignorado')
x = emails.processar(resposta(f'APROVAR {ref} {code}', em_resposta='<outro@x>'))
confere(not x['ok'], 'resposta fora da conversa ignorada')
x = emails.processar(resposta(f'APROVAR {ref} ZZZZ-ZZZZ'))
confere(not x['ok'] and 'errado' in x['motivo'], 'código errado recusado')
x = emails.processar(resposta('ok obrigado'))
confere(not x['ok'], 'texto citado não conta como comando')
msg = resposta(f'APROVAR {ref} {code}', mid='<aprovar-1@exemplo.com>')
x = emails.processar(msg)
confere(x['ok'], 'aprovado por e-mail com código válido')
posts = pg.posts()
confere(len(posts) == 1 and posts[0]['origem'] == 'agente3' and posts[0]['redes']['kwai']['status'] == 'manual', 'post criado no Agente 2 (Kwai manual)')
x = emails.processar(msg)
confere(not x['ok'] and x.get('repetido'), 'o mesmo e-mail não é aplicado duas vezes')
x = emails.processar(resposta(f'APROVAR {ref} {code}', mid='<aprovar-2@exemplo.com>'))
confere(not x['ok'], 'código já usado não aprova de novo')
st, r2, _ = api('POST', f'/api/v1/projetos/{PID}/aprovar', {'render_sha': render['sha']}, SES)
confere(len(pg.posts()) == 1, 'aprovar de novo pelo site não duplica o post')
p = api('GET', f'/api/v1/projetos/{PID}', None, SES)[1]
confere(p['status'] == 'queued_to_publish', 'situação: na fila de postagem')

print('Storyboard editado no site')
st, rasc, _ = api('POST', '/api/v1/agente3/projetos', {'briefing': dict(briefing, tema='Rascunho'), 'cenas': [{'titulo': 'A', 'texto': 'Primeira cena.'}, {'titulo': 'B', 'texto': 'Segunda cena.'}]}, SES)
confere(st == 200 and rasc['status'] != 'queued', 'rascunho criado sem produzir')
st, sb, _ = api('POST', f'/api/v1/projetos/{rasc["id"]}/storyboard', {'revisao': rasc['revisao'], 'cenas': [{'titulo': 'B', 'texto': 'Segunda cena, agora primeiro.', 'bloqueada': True}, {'titulo': 'C', 'texto': 'Nova.'}]}, SES)
confere(st == 200 and sb['revisao'] == rasc['revisao'] + 1, 'storyboard salvo numa revisão nova')
st, sb2, _ = api('POST', f'/api/v1/projetos/{rasc["id"]}/storyboard', {'revisao': rasc['revisao'], 'cenas': [{'texto': 'x'}]}, SES)
confere(st == 409, 'storyboard de revisão antiga dá conflito 409')
pd = api('GET', f'/api/v1/projetos/{rasc["id"]}', None, SES)[1]['dados']
confere([c['texto'] for c in pd['cenas']] == ['Segunda cena, agora primeiro.', 'Nova.'] and pd['cenas'][0].get('bloqueada'), 'ordem, texto e cena travada guardados')
st, _, _ = api('POST', f'/api/v1/projetos/{rasc["id"]}/storyboard', {'revisao': sb['revisao'], 'cenas': [{'texto': ''}]}, SES)
confere(st == 400, 'storyboard vazio recusado')

print('Fila, capacidade, backup')
st, f, _ = api('GET', '/api/v1/fila', None, SES)
confere(st == 200 and f['contagem']['concluidos'] >= 1, 'fila lista os concluídos')
st, c, _ = api('GET', '/api/v1/capacidade', None, SES)
confere(st == 200 and 'cpus' in c, 'capacidade do aparelho')
st, b, _ = api('POST', '/api/v1/backups', {}, SES)
st, t, _ = api('POST', f'/api/v1/backups/{b["arquivo"]}/testar', {}, SES)
confere(t['ok'] and t['projetos'] >= 2, 'backup e restauração de teste conferem')
st, a, _ = api('POST', '/agente/rodar', {'oque': 'buscar'}, SES)
confere(st == 200 and a.get('fila'), 'pedido manual do agente de cortes entra na fila')

print(f'\n{ok_n} ok, {falhas} falhas   (pasta {TMP})')
if os.getenv('MANTER_SERVIDOR'):
    # Para testar o site no navegador contra este servidor de teste.
    Path(os.environ['MANTER_SERVIDOR']).write_text(json.dumps({'base': BASE, 'sessao': SES['X-Sessao'], 'pid': PID}))
    print('servidor de teste no ar:', BASE, flush=True)
    while True:
        time.sleep(3600)
sys.exit(1 if falhas else 0)
