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
import subprocess
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
PROMPTS = []
VISAO = []
SEM_FOTOS = False
ROTEIRO_SERIE = {'titulo': 'O barulho', 'legenda': 'O que foi aquilo?', 'hashtags': ['#serie'],
                 'mudancas': [{'alvo': 'ana', 'texto': 'Ana agora guarda a chave do sótão.'}],
                 'cenas': [{'texto': 'Beto, você ouviu isso?', 'personagem': 'ana', 'cenario_id': 'sala', 'duracao_alvo': 3,
                            'elenco': [{'personagem_id': 'ana', 'posicao': 'esquerda', 'expressao': 'preocupado', 'acoes': [{'t': 0.3, 'tipo': 'apontar', 'alvo': 'direita'}]},
                                       {'personagem_id': 'beto', 'posicao': 'direita', 'acoes': [{'t': 0.5, 'tipo': 'olhar', 'alvo': 'esquerda'}, {'t': 1, 'tipo': 'voar'}]},
                                       {'personagem_id': 'intruso', 'posicao': 'centro'}],
                            'planos': [{'plano': 'WS'}, {'plano': 'CU', 'personagem': 'ana'}]},
                           {'texto': 'Deve ser só o vento.', 'personagem': 'Beto', 'cenario_id': 'inexistente', 'duracao_alvo': 3,
                            'elenco': [{'personagem_id': 'beto', 'posicao': 'centro', 'expressao': 'feliz', 'acoes': [{'t': 0.2, 'tipo': 'rir'}]}]}]}


class Gemini(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        # Pexels falso: busca devolve fotos do próprio servidor de teste; /fotoN.jpg serve uma imagem de verdade
        if self.path.startswith('/w/api.php') or (self.path.startswith('/v1/search') and SEM_FOTOS):
            b, tipo = b'{}', 'application/json'
        elif self.path.startswith('/v1/search'):
            PEDIDOS.append('pexels:' + (self.headers.get('Authorization') or ''))
            r = {'photos': [{'id': 900 + i, 'photographer': f'Fulano {i}', 'url': f'https://www.pexels.com/photo/{900 + i}/',
                             'src': {'large2x': f'http://127.0.0.1:{pg_port}/foto{i}.jpg'}} for i in range(1, 7)]}
            b = json.dumps(r).encode()
            tipo = 'application/json'
        else:
            b = FOTO.read_bytes()
            tipo = 'image/jpeg'
        self.send_response(200)
        self.send_header('Content-Type', tipo)
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        corpo = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        PEDIDOS.append(self.path)
        if 'image' in self.path:
            r = {'candidates': [{'content': {'parts': [{'inlineData': {'mimeType': 'image/jpeg', 'data': base64.b64encode(FOTO.read_bytes()).decode()}}]}}]}
        elif 'tts' in self.path:
            pcm = b''.join(struct.pack('<h', int(8000 * math.sin(2 * math.pi * 220 * i / 24000))) for i in range(int(24000 * 1.6)))
            r = {'candidates': [{'content': {'parts': [{'inlineData': {'mimeType': 'audio/pcm', 'data': base64.b64encode(pcm).decode()}}]}}]}
        else:
            txt = json.dumps(corpo)
            PROMPTS.append(txt)
            if 'pauteiro de v' in txt:
                rot = {'ideias': [{'titulo': 'Por que o mar é salgado', 'gancho': 'g', 'porque': 'p', 'tipo': 'curiosidade', 'fato': True, 'risco': 'baixo', 'fontes': []},
                                  {'titulo': 'Remédio caseiro cura gripe?', 'gancho': 'g', 'porque': 'p', 'tipo': 'saúde', 'fato': True, 'risco': 'alto',
                                   'motivo_risco': 'saúde', 'fontes': [{'titulo': 'OMS', 'url': 'https://www.who.int'}]}]}
                r = {'candidates': [{'content': {'parts': [{'text': json.dumps(rot, ensure_ascii=False)}]}}], 'usageMetadata': {}}
                b = json.dumps(r).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(b)))
                self.end_headers()
                self.wfile.write(b)
                return
            if 'AVALIADOR VISUAL' in txt:
                m = re.search(r'\[([\w-]+)/([\w-]+)\]', txt)
                rot = {'pontos': [{'cena': m.group(1) if m else '', 'plano': m.group(2) if m else '', 'problema': 'Rosto cortado na borda', 'sugestao': 'Abrir o plano', 'confianca': 0.8},
                                  {'cena': '', 'plano': '', 'problema': 'Talvez a cor esteja fria', 'sugestao': '', 'confianca': 0.3}]}
                VISAO.append(txt.count('inline_data'))
                r = {'candidates': [{'content': {'parts': [{'text': json.dumps(rot, ensure_ascii=False)}]}}], 'usageMetadata': {}}
                b = json.dumps(r).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(b)))
                self.end_headers()
                self.wfile.write(b)
                return
            if 'REVISOR DE ROTEIRO' in txt or 'VERIFICADOR DE CONTINUIDADE' in txt:
                m = re.search(r'\\n\[([^\]]+)\]', txt)
                rot = ({'pontos': [{'cena': m.group(1) if m else '', 'gravidade': 'baixa', 'problema': 'Gancho fraco no começo', 'sugestao': 'Comece pela pergunta.'}]}
                       if 'REVISOR' in txt else
                       {'contradicoes': [{'cena': m.group(1) if m else '', 'fato': 'Ana perdeu o medo do escuro.', 'problema': 'Ana diz que tem medo do escuro'}]})
                r = {'candidates': [{'content': {'parts': [{'text': json.dumps(rot, ensure_ascii=False)}]}}], 'usageMetadata': {}}
                b = json.dumps(r).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(b)))
                self.end_headers()
                self.wfile.write(b)
                return
            rot = ROTEIRO_SERIE if 'ANIMA\\u00c7\\u00c3O COM PERSONAGENS' in txt or 'ANIMAÇÃO COM PERSONAGENS' in txt else ROTEIRO
            r = {'candidates': [{'content': {'parts': [{'text': json.dumps(rot, ensure_ascii=False)}]}}], 'usageMetadata': {}}
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


FOTO = TMP / 'foto.jpg'
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=900x1200', '-frames:v', '1', str(FOTO)], check=True)
pg_port = livre()
threading.Thread(target=ThreadingHTTPServer(('127.0.0.1', pg_port), Gemini).serve_forever, daemon=True).start()
os.environ['BASE_GEMINI'] = f'http://127.0.0.1:{pg_port}'
os.environ['BASE_PEXELS'] = f'http://127.0.0.1:{pg_port}'
os.environ['BASE_WIKI'] = f'http://127.0.0.1:{pg_port}'
os.environ['PERMITIR_QUALQUER_URL'] = '1'

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
import fila  # noqa: E402
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

print('Agente 2: portões antes de postar')
post = pg.posts()[0]
confere(post['projeto'] == PID and post['render_sha'] == render['sha'], 'post do Agente 3 sabe de qual versão aprovada veio')
cf = {x['item']: x for x in pg.conferencia(post, 'youtube')}
confere(cf['aprovacao']['ok'] and cf['direitos']['ok'] and cf['qualidade']['ok'] and cf['versao']['ok'], 'versão aprovada, direitos, qualidade e arquivo conferidos')
confere(cf['conta']['bloqueia'], 'conta não conectada bloqueia a rede')
confere({x['item']: x for x in pg.conferencia(dict(post, render_sha='ab' * 32), 'youtube')}['aprovacao']['bloqueia'], 'versão não aprovada é barrada')
confere({x['item']: x for x in pg.conferencia(dict(post, creditos=['Ana, Wikimedia Commons (CC BY 4.0)']), 'youtube')}['creditos']['bloqueia'], 'crédito exigido fora da legenda é barrado')
confere({x['item']: x for x in pg.conferencia(dict(post, origem='agente', direitos=None), 'youtube')}['direitos']['bloqueia'], 'corte sem dono registrado é barrado')
confere(not {x['item']: x for x in pg.conferencia(dict(post, origem='manual', direitos=None), 'youtube')}['direitos']['bloqueia'], 'post enviado à mão só recebe aviso')
st, cfr, _ = api('GET', f'/api/v1/posts/{post["id"]}/conferencia', None, SES)
confere(st == 200 and 'kwai' not in cfr['redes'] and all(isinstance(v, list) for v in cfr['redes'].values()), 'site consegue ver a conferência antes de postar')

print('Radar: ficha de oportunidade')
st, idz, _ = api('POST', '/api/v1/agente3/ideias', {'nicho': 'Ciência', 'tema': 'mar', 'usar_radar': False}, SES)
f0, f1 = idz['ideias'][0]['ficha'], idz['ideias'][1]['ficha']
confere(st == 200 and f0['coletado_em'] and f0['filtros']['nicho'] == 'Ciência' and f0['estimado']['interesse'] == 'desconhecido', 'ficha diz quando, com quais filtros e que o interesse é desconhecido sem dados')
confere(any('sem fonte' in r for r in f0['riscos']) and f1['risco'] == 'alto' and any(x['tipo'] == 'conferir' for x in f1['fontes']), 'ficha mostra fontes e riscos (saúde = alto)')

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

print('Fotos por cena remodeladas no estilo')
st, _, _ = api('POST', '/agente/chaves', {'pexels': 'chave-pexels'}, SES)
b2 = dict(briefing, tema='Fotos', imagens='busca', estilo='quadrinhos', modo_aprovacao='supervisionado', cenas_qtd=3, duracao_alvo=9)
st, pf, _ = api('POST', '/api/v1/agente3/projetos', {'briefing': b2, 'produzir': True}, SES)
t = time.time()
while time.time() - t < 400:
    rf = api('GET', f'/api/v1/projetos/{pf["id"]}/revisao', None, SES)[1]
    if rf['projeto']['status'] in ('ready_for_review', 'failed'):
        break
    time.sleep(0.5)
confere(rf['projeto']['status'] == 'ready_for_review', 'vídeo com fotos produzido e pronto para revisão')
cf = rf['projeto']['dados']['cenas']
confere(all((c.get('imagem') or {}).get('credito', '').startswith('Foto de Fulano') for c in cf), 'cada cena guardou a foto e o crédito')
confere(len({c['imagem']['id'] for c in cf}) == len(cf), 'cenas não repetem a mesma foto')
confere('pexels:chave-pexels' in PEDIDOS, 'a busca usou a chave do Pexels')
confere(any('Fotos usadas' in (m.get_body(('plain',)).get_content() if m.get_body(('plain',)) else '') for m in EMAILS), 'e-mail lista os créditos das fotos')

print('Modo misto: IA desenha a cena sem foto')
SEM_FOTOS = True
b3 = dict(briefing, tema='Misto', imagens='busca', estilo='documentario', modo_aprovacao='supervisionado', cenas_qtd=3, duracao_alvo=9)
st, pm, _ = api('POST', '/api/v1/agente3/projetos', {'briefing': b3, 'produzir': True}, SES)
t = time.time()
while time.time() - t < 400:
    rm = api('GET', f'/api/v1/projetos/{pm["id"]}/revisao', None, SES)[1]
    if rm['projeto']['status'] in ('ready_for_review', 'failed'):
        break
    time.sleep(0.5)
confere(rm['projeto']['status'] == 'ready_for_review', 'vídeo documentário sem fotos achadas ficou pronto')
confere(all((c.get('imagem') or {}).get('fonte') == 'ia' for c in rm['projeto']['dados']['cenas']), 'cada cena sem foto ganhou imagem da IA')
SEM_FOTOS = False

print('Planos por cena (documentário)')
ROTEIRO['cenas'][0]['planos'] = [{'plano': 'WS', 'busca': 'blue sky'}, {'plano': 'CU', 'busca': 'sun close'}]
ROTEIRO['cenas'][2]['planos'] = [{'plano': 'MS', 'busca': 'air molecules'}, {'plano': 'XX', 'busca': 'clouds', 'foco_x': 9}]
b4 = dict(briefing, tema='Planos', imagens='busca', estilo='documentario', modo_aprovacao='supervisionado', cenas_qtd=3, duracao_alvo=9, qa_visao=True)
st, pp, _ = api('POST', '/api/v1/agente3/projetos', {'briefing': b4, 'produzir': True}, SES)
t = time.time()
while time.time() - t < 400:
    rp = api('GET', f'/api/v1/projetos/{pp["id"]}/revisao', None, SES)[1]
    if rp['projeto']['status'] in ('ready_for_review', 'failed'):
        break
    time.sleep(0.5)
confere(rp['projeto']['status'] == 'ready_for_review', 'vídeo com planos ficou pronto')
cp = rp['projeto']['dados']['cenas']
confere([p['plano'] for p in cp[2]['planos']] == ['MS', 'WS'] and cp[2]['planos'][1]['foco_x'] == 1.0, 'plano inválido vira aberto e números ficam na faixa')
confere(len(cp[0].get('fotos_planos') or {}) == 2, 'cada plano com busca ganhou a sua foto')
ids = [f['id'] for c in cp for f in (c.get('fotos_planos') or {}).values()] + [c['imagem']['id'] for c in cp if c.get('imagem')]
confere(len(ids) == len(set(ids)), 'planos e cenas não repetem foto')
qp = rp['projeto']['dados'].get('qualidade') or {}
confere(qp.get('status') in ('apto_para_revisao_humana', 'alerta_visual') and 'tecnico' in qp, 'diretor de qualidade deixou o relatório no projeto')
confere(all(set(x) >= {'tipo', 'severidade', 'cena_id', 'timecode', 'descricao'} for x in qp.get('problemas', [])), 'cada alerta tem cena, instante e descrição')
nar = [x for x in qp.get('problemas', []) if x['tipo'] == 'narrativa']
confere(len(nar) == 1 and nar[0]['cena_id'] == cp[0]['id'] and 'Gancho' in nar[0]['descricao'], 'leitura crítica do roteiro vira alerta na cena certa')
confere(rp['projeto']['dados'].get('revisao_narrativa', {}).get('h'), 'leitura crítica guardada para não pagar de novo')
vis = [x for x in qp.get('problemas', []) if x['tipo'] == 'visual_ia']
confere(len(VISAO) == 1 and 0 < VISAO[0] <= 6, f'olhar da IA: uma chamada, no máximo 6 quadros ({VISAO})')
confere(len(vis) == 1 and vis[0]['natureza'] == 'julgamento' and 'confiança 0.80' in vis[0]['evidencia'], 'só o apontamento com confiança alta entra, marcado como opinião')
confere(qp.get('status') != 'falha_tecnica' and qp.get('contagem', {}).get('julgamento') == 1, 'opinião da IA não reprova o vídeo')
cl0 = cp[0].get('clipe') or {}
confere(len(cl0.get('planos') or []) == 2 and all(x['refeito'] for x in cl0['planos']), 'cena com 2 planos foi feita por pedaços (render por plano)')
for c in ROTEIRO['cenas']:
    c.pop('planos', None)
st, _, _ = api('POST', '/agente/chaves', {'pexels': ''}, SES)

print('Estilos 3D')
import estilos_codigo as ec3  # noqa: E402
import motor3d  # noqa: E402
if motor3d.disponivel():
    cat3 = {e['id']: e for e in ec3.catalogo()}
    confere(all(cat3[i]['status'] == 'beta' and cat3[i]['servidor'] for i in motor3d.ESTILOS_3D), '3D aparece como beta quando há numpy')
    ec3.preparar('retro3d_2000', 1080, 1920, 5.0, None)
    confere(motor3d.caminho('retro3d_2000', 1080, 1920, ec3.estilo('retro3d_2000')['paleta']).exists(), 'fundo 3D em loop gerado e guardado')
    st, e3, _ = api('POST', '/api/v1/estilos/retro3d_2000/demo', {'formato': '9:16'}, SES)
    confere(st == 200, 'demonstração 3D entra na fila')
else:
    print('  (sem numpy: 3D continua indisponível)')

print('Backup das mídias')
st, em, _ = api('GET', '/api/v1/midias-backup', None, SES)
confere(st == 200 and em['categorias']['finais']['arquivos'] >= 1 and em['mesmo_aparelho'], 'mostra o que existe e avisa que o destino é o mesmo celular')
st, _, _ = api('PUT', '/api/v1/midias-backup', {'destino': '/etc'}, SES)
confere(st == 400, 'destino fora do Termux/armazenamento é recusado')
st, em, _ = api('PUT', '/api/v1/midias-backup', {'categorias': ['finais', 'audios', 'imagens']}, SES)
st, m1, _ = api('POST', '/api/v1/midias-backup/fazer', {}, SES)
st2, m2, _ = api('POST', '/api/v1/midias-backup/fazer', {}, SES)
confere(st == 200 and m1['novos'] > 0 and m2['novos'] == 0 and m2['ja_existiam'] == m1['novos'] + m1['ja_existiam'], 'backup incremental: a segunda vez não copia de novo')
st, tm, _ = api('POST', '/api/v1/midias-backup/testar', {}, SES)
confere(st == 200 and tm['ok'] and tm['conferidos'] == m1['novos'] + m1['ja_existiam'], 'restauração de teste confere todos os sha256')
import backups as bk  # noqa: E402
obj = next((bk._destino(bk.config_midias()) / 'objetos').rglob('*'))
while obj.is_dir():
    obj = next(obj.iterdir())
obj.write_bytes(b'estragado')
st, tm2, _ = api('POST', '/api/v1/midias-backup/testar', {}, SES)
confere(not tm2['ok'] and any('corrompido' in x for x in tm2['problemas']), 'arquivo estragado no backup aparece como problema')

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

print('Séries animadas (personagens articulados)')
st, se, _ = api('POST', '/api/v1/series', {'titulo': 'Casa Assombrada', 'genero': 'mistério', 'tom': 'leve', 'formato': '9:16', 'cenas_qtd': 2, 'duracao_alvo': 8}, SES)
SID = se['id']
st, e0, _ = api('POST', f'/api/v1/series/{SID}/episodios', {'resumo': 'sem elenco'}, SES)
confere(st == 400, 'episódio sem personagem é recusado')
st, ana, _ = api('POST', '/api/v1/personagens', {'serie_id': SID, 'nome': 'Ana', 'cabelo_tipo': 'longo', 'roupa': '#e63946', 'voz': 'Kore'}, SES)
st, beto, _ = api('POST', '/api/v1/personagens', {'serie_id': SID, 'nome': 'Beto', 'cabelo_tipo': 'cacheado', 'corpo': 'forte', 'voz': 'Puck', 'pele': 'roxo'}, SES)
confere(ana['id'] == 'ana' and beto['id'] == 'beto' and beto['dados']['pele'] == '#e8b98f', 'personagens criados com id legível e cor inválida trocada')
st, fl, _ = api('GET', '/api/v1/personagens/ana/folha', None, SES)
confere(st == 200 and fl['png'].startswith('data:image/png;base64,') and len(fl['png']) > 2000, 'folha de modelo do personagem gerada')
st, sala, _ = api('POST', '/api/v1/cenarios', {'serie_id': SID, 'nome': 'Sala', 'tipo': 'casa', 'horario': 'noite'}, SES)
st, bb, _ = api('PUT', f'/api/v1/series/{SID}/biblia', {'entradas': [{'tipo': 'fato', 'alvo': 'ana', 'texto': 'Ana tem medo do escuro.', 'estado': 'aprovada'},
                                                                   {'tipo': 'fato', 'texto': 'A casa tem um segredo no sótão.', 'estado': 'proposta'}]}, SES)
fato = next(x for x in bb['biblia'] if 'escuro' in x['texto'])
st, bb, _ = api('PUT', f'/api/v1/series/{SID}/biblia', {'entradas': [{'id': fato['id'], 'tipo': 'fato', 'alvo': 'ana', 'texto': 'Ana perdeu o medo do escuro.', 'estado': 'aprovada'}]}, SES)
confere(any('perdeu' in x['texto'] and x['substitui'] == fato['id'] for x in bb['biblia']) and not any(x['id'] == fato['id'] for x in bb['biblia']),
        'fato aprovado não muda em silêncio (vira mudança e o antigo fica guardado)')
st, ep, _ = api('POST', f'/api/v1/series/{SID}/episodios', {'titulo': 'O barulho', 'resumo': 'Um barulho estranho na sala.', 'produzir': True,
                                                           'modo_aprovacao': 'supervisionado'}, SES)
confere(st == 200 and ep['ordem'] == 1 and ep['projeto_id'], 'episódio criado como projeto do Agente 3')
api('PUT', '/api/v1/personagens/ana/rig', {'dados': {'roupa': '#00ff00'}}, SES)
t = time.time()
while time.time() - t < 500:
    re_ = api('GET', f'/api/v1/projetos/{ep["projeto_id"]}/revisao', None, SES)[1]
    if re_['projeto']['status'] in ('ready_for_review', 'failed'):
        break
    time.sleep(0.5)
confere(re_['projeto']['status'] == 'ready_for_review', 'episódio animado produzido e pronto para revisão')
if re_['projeto']['status'] != 'ready_for_review':
    print(json.dumps(re_['job'], ensure_ascii=False)[:1500])
dp = re_['projeto']['dados']
pr = next(x for x in PROMPTS if 'ANIMA' in x)
confere('perdeu o medo' in pr and 'segredo no s' not in pr and 'beto: Beto' in pr, 'roteiro do episódio vê só fatos aprovados e o elenco da série')
c0, c1 = dp['cenas'][0], dp['cenas'][1]
confere([e['personagem_id'] for e in c0['elenco']] == ['ana', 'beto'] and [a['tipo'] for a in c0['elenco'][1]['acoes']] == ['olhar'],
        'só personagens da série e só ações do catálogo')
confere(c0['voz'] == 'Kore' and c1['personagem'] == 'beto' and c1['voz'] == 'Puck' and c1['cenario_id'] == 'sala', 'cada fala com a voz do seu personagem')
confere(dp['serie']['personagens']['ana']['roupa'] == '#e63946', 'mudar o personagem depois não altera o episódio já criado')
confere(api('GET', '/api/v1/personagens/ana', None, SES)[1]['versao'] == 2, 'mudança de aparência vira versão nova do personagem')
st, bb, _ = api('POST', f'/api/v1/series/episodios/{ep["id"]}/propostas', {}, SES)
confere(any(x['texto'] == 'Ana agora guarda a chave do sótão.' and x['estado'] == 'proposta' for x in bb['biblia']), 'mudanças do episódio entram na bíblia como proposta')
st, so, _ = api('GET', f'/api/v1/series/{SID}', None, SES)
confere(so['episodios'][0]['status'] == 'ready_for_review' and len(so['personagens']) == 2, 'série mostra episódios com a situação do vídeo')

print('Continuidade com a bíblia e voz gravada no Estúdio')
qs = dp.get('qualidade', {}).get('problemas', [])
confere(any(x['tipo'] == 'continuidade' and x['descricao'].startswith('Bíblia:') and x['cena_id'] == c0['id'] for x in qs), 'contradição com a bíblia vira alerta na cena')
confere(any(x['tipo'] == 'continuidade' and 'mudou de aparência' in x['descricao'] for x in qs), 'avisa que o personagem mudou depois do episódio criado')
confere(any('VERIFICADOR DE CONTINUIDADE' in x and 'perdeu o medo' in x and 'segredo no s' not in x for x in PROMPTS), 'conferência usa só os fatos aprovados')


def enviar(dados: bytes, nome: str, mime: str, projeto: str) -> str:
    st_, r_, _ = api('POST', '/api/v1/uploads', {'sha256': hashlib.sha256(dados).hexdigest(), 'tamanho': len(dados), 'mime': mime, 'nome': nome, 'projeto': projeto}, SES)
    if r_.get('pronto'):
        return r_['asset']['id']
    req = urllib.request.Request(BASE + f'/api/v1/uploads/{r_["upload"]}?offset=0', data=dados, method='PUT', headers={'Content-Type': 'application/octet-stream', **SES})
    urllib.request.urlopen(req, timeout=60).read()
    return api('POST', f'/api/v1/uploads/{r_["upload"]}/fim', {}, SES)[1]['asset']['id']


wav = TMP / 'take.wav'
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=f=300:d=1.4', '-ar', '44100', '-ac', '2', str(wav)], check=True)
aid = enviar(wav.read_bytes(), 'take-ana.wav', 'audio/wav', ep['projeto_id'])
cs = [dict(c, audio_manual={'asset': aid, 'nome': 'take-ana.wav'}) if k == 0 else c for k, c in enumerate(dp['cenas'])]
st, sb, _ = api('POST', f'/api/v1/projetos/{ep["projeto_id"]}/storyboard', {'revisao': re_['projeto']['revisao'], 'cenas': cs}, SES)
confere(st == 200, f'storyboard com voz gravada salvo ({sb if st != 200 else ""})')
n_tts = sum('tts' in x for x in PEDIDOS)
st, jb, _ = api('POST', f'/api/v1/projetos/{ep["projeto_id"]}/produzir', {'etapa': 'narracao'}, SES)
t = time.time()
while time.time() - t < 300:
    rv = api('GET', f'/api/v1/projetos/{ep["projeto_id"]}/revisao', None, SES)[1]
    if (rv.get('job') or {}).get('id') == jb['job']['id'] and rv['job']['status'] in ('concluido', 'falhou'):
        break
    time.sleep(0.5)
a0 = rv['projeto']['dados']['cenas'][0].get('audio') or {}
confere(rv['projeto']['status'] == 'ready_for_review' and a0.get('manual') and abs(a0.get('dur', 0) - 1.4) < 0.1, f'cena usa a voz gravada no lugar da IA ({rv["job"].get("erro")})')
confere(sum('tts' in x for x in PEDIDOS) == n_tts, 'não pagou voz da IA para a cena com voz gravada')
import rig2d as rg  # noqa: E402
nv = rg.niveis_fala(Path(a0['arquivo']), 1.4)
confere(sum(v > 0 for v in nv) > len(nv) * 0.6, 'boca do personagem segue a voz gravada')

print('Diretor: mapa de palco, eixo, animatic e prévia A/B')
EPID = ep['projeto_id']
st, mp, _ = api('GET', f'/api/v1/projetos/{EPID}/diretor', None, SES)
confere(st == 200 and [a['id'] for a in mp['cenas'][0]['atores']] == ['ana', 'beto'] and mp['cenas'][0]['eixo'] == [0.27, 0.73], 'mapa de palco com atores e eixo')
import diretor  # noqa: E402
cx = [{'id': 'a', 'cenario_id': 'sala', 'elenco': [{'personagem_id': 'ana', 'posicao': 'esquerda', 'acoes': []}, {'personagem_id': 'beto', 'posicao': 'direita', 'acoes': []}]},
      {'id': 'b', 'cenario_id': 'sala', 'planos': [{'id': 'p1', 'plano': 'CU', 'personagem': ''}],
       'elenco': [{'personagem_id': 'ana', 'posicao': 'direita', 'acoes': [{'tipo': 'olhar', 'alvo': 'direita'}]}, {'personagem_id': 'beto', 'posicao': 'esquerda', 'acoes': []}]},
      {'id': 'c', 'cenario_id': 'sala', 'elenco': [{'personagem_id': 'ana', 'posicao': 'esquerda', 'acoes': [{'tipo': 'andar', 'alvo': 'esquerda'}]},
                                                   {'personagem_id': 'beto', 'posicao': 'direita', 'acoes': []}]}]
tipos = [(x['cena'], x['tipo']) for x in diretor.checar(cx)]
confere(('b', 'eixo') in tipos and ('b', 'direcao_olhar') in tipos and ('b', 'close_sem_foco') in tipos and ('c', 'eixo') not in tipos,
        'eixo de 180°: troca de lado sem motivo avisa; andando para o outro lado não avisa')
st, an, _ = api('POST', f'/api/v1/projetos/{EPID}/animatic', {}, SES)
t = time.time()
while time.time() - t < 300:
    ea = api('GET', f'/api/v1/diretor/{an["job"]}', None, SES)[1]
    if ea['status'] in ('concluido', 'falhou'):
        break
    time.sleep(0.5)
confere(ea['status'] == 'concluido', f'animatic feito ({ea.get("erro")})')
if ea['status'] == 'concluido':
    r = ea['resultado']
    arq = Path(db.um('SELECT caminho FROM assets WHERE id=?', r['asset'])['caminho'])
    vs = [s for s in rd.sonda(arq)['streams'] if s['codec_type'] == 'video'][0]
    print(f'     (animatic de {r["duracao"]}s levou {r["segundos_para_fazer"]}s)')
    confere((vs['width'], vs['height']) == (360, 640) and vs['avg_frame_rate'] in ('8/1', '8/1.0') and abs(r['duracao'] - sum(c['duracao_real'] for c in dp['cenas'])) < 1,
            'animatic pequeno (360x640, 8 quadros/s) com a duração do vídeo')
    confere(api('GET', f'/api/v1/projetos/{EPID}/diretor', None, SES)[1]['animatic']['asset'] == r['asset'], 'mapa mostra o animatic atual')
st, ab, _ = api('POST', f'/api/v1/projetos/{EPID}/cenas/0/previa-ab', {'a': [{'plano': 'WS'}], 'b': [{'plano': 'WS'}, {'plano': 'CU', 'personagem': 'beto'}]}, SES)
t = time.time()
while time.time() - t < 300:
    eb = api('GET', f'/api/v1/diretor/{ab["job"]}', None, SES)[1]
    if eb['status'] in ('concluido', 'falhou'):
        break
    time.sleep(0.5)
confere(eb['status'] == 'concluido' and len(eb['resultado']['a']) == 1 and [x['plano'] for x in eb['resultado']['b']] == ['WS', 'CU']
        and all(x['img'].startswith('data:image/jpeg;base64,') for x in eb['resultado']['b']), f'prévia A/B com quadros desenhados de verdade ({eb.get("erro")})')
if eb['status'] == 'concluido':
    for k, x in enumerate(eb['resultado']['a'] + eb['resultado']['b']):
        (TMP / f'ab-{k}.jpg').write_bytes(base64.b64decode(x['img'].split(',', 1)[1]))
st, ab2, _ = api('POST', f'/api/v1/projetos/{EPID}/cenas/9/previa-ab', {'a': [], 'b': []}, SES)
confere(st == 404, 'cena que não existe é recusada')

print('Clima e luz por cena')
import estilos_codigo as ec2  # noqa: E402
cv = ec2.validar_cena({'texto': 'x', 'clima': 'chuva', 'luz': 'noite'})
confere(cv['clima'] == 'chuva' and cv['luz'] == 'noite' and ec2.validar_cena({'clima': 'fogo', 'luz': 'x'})['clima'] == 'nenhum', 'clima e luz só da lista')
pt = TMP / 'clima'
pt.mkdir()
cmd = ec2.montar('vetor_chapado', cv, 540, 960, 2, pt, None, None, pt / 'o.mp4')
g = cmd[cmd.index('-filter_complex') + 1]
confere('colorbalance' in g and any('clima-chuva' in x for x in cmd), 'cena com chuva à noite ganha partículas e camada de cor')
cmd2 = ec2.montar('vetor_chapado', ec2.validar_cena({'texto': 'x'}), 540, 960, 2, pt, None, None, pt / 'o2.mp4')
confere('colorbalance' not in cmd2[cmd2.index('-filter_complex') + 1] and not any('clima-' in x for x in cmd2), 'cena comum fica sem efeito extra')
rd.rodar(cmd)
confere(abs(rd.duracao(pt / 'o.mp4') - 2) < 0.2, 'render com clima funciona')

print('Diretor completo: ângulo, luz por plano, movimento livre e refazer uma cena')
pv = ec2.validar_planos([{'plano': 'MS'}, {'plano': 'CU', 'angulo': 'inclinado', 'luz': 'noite', 'chaves': [{'t': 1, 'zoom': 9, 'x': 2}, {'t': 0, 'zoom': 1}]},
                         {'angulo': 'voando', 'luz': 'roxa', 'chaves': [{'t': 0}]}])
confere('angulo' not in pv[0] and 'chaves' not in pv[0] and 'luz' not in pv[0], 'plano antigo continua igual (mesma chave de cache)')
confere(pv[1]['angulo'] == 'inclinado' and pv[1]['luz'] == 'noite' and pv[1]['chaves'][0]['t'] == 0 and pv[1]['chaves'][1]['zoom'] == 3 and pv[1]['chaves'][1]['x'] == 1,
        'ângulo, luz e quadros-chave validados e ordenados')
confere('angulo' not in pv[2] and 'luz' not in pv[2] and 'chaves' not in pv[2], 'valores fora da lista são descartados')
cd = ec2.validar_cena({'texto': 'x', 'planos': [{'plano': 'MS', 'angulo': 'baixo'}, {'plano': 'WS', 'angulo': 'inclinado', 'luz': 'noite'},
                                                 {'plano': 'CU', 'chaves': [{'t': 0, 'zoom': 1, 'x': 0.2}, {'t': 1, 'zoom': 2, 'x': 0.8}]}]})
pt2 = TMP / 'dir2'
pt2.mkdir()
for eid in ('documentario', 'animado2d'):
    cmd = ec2.montar(eid, cd, 540, 960, 3, pt2, FOTO if eid == 'documentario' else None, None, pt2 / f'{eid}.mp4')
    g = cmd[cmd.index('-filter_complex') + 1]
    confere('perspective=' in g and 'rotate=' in g and "enable='between(t" in g, f'{eid}: ângulos e luz do plano entram no desenho')
    rd.rodar(cmd)
    confere(abs(rd.duracao(pt2 / f'{eid}.mp4') - 3) < 0.2, f'{eid}: render com ângulos e movimento livre funciona')
RPID = pp['id']
antes = {c['id']: (c.get('clipe') or {}).get('chave') for c in api('GET', f'/api/v1/projetos/{RPID}/revisao', None, SES)[1]['projeto']['dados']['cenas']}
v0 = api('GET', f'/api/v1/projetos/{RPID}/revisao', None, SES)[1]['projeto']['dados']['render']['versao']
n_tts = sum('tts' in x for x in PEDIDOS)
st, rf, _ = api('POST', f'/api/v1/projetos/{RPID}/cenas/1/refazer', {'voz': True}, SES)
confere(st == 200 and rf['job']['id'], 'pedido de refazer só a cena 2 aceito')
st, _, _ = api('POST', f'/api/v1/projetos/{RPID}/cenas/1/refazer', {}, SES)
confere(st == 400, 'não deixa pedir de novo enquanto está na fila')
t = time.time()
while time.time() - t < 300:
    rr = api('GET', f'/api/v1/projetos/{RPID}/revisao', None, SES)[1]
    if (rr.get('job') or {}).get('id') == rf['job']['id'] and rr['job']['status'] in ('concluido', 'falhou') and rr['projeto']['status'] in ('ready_for_review', 'failed'):
        break
    time.sleep(0.5)
depois = {c['id']: (c.get('clipe') or {}).get('chave') for c in rr['projeto']['dados']['cenas']}
ids = list(antes)
confere(rr['projeto']['status'] == 'ready_for_review' and rr['projeto']['dados']['render']['versao'] > v0, f"vídeo refeito voltou para a revisão com versão nova ({rr['projeto']['status']}, {rr['projeto']['dados'].get('producao')})")
confere(depois[ids[1]] != antes[ids[1]] and all(depois[k] == antes[k] for k in ids if k != ids[1]), 'só a cena pedida foi desenhada de novo')
confere(sum('tts' in x for x in PEDIDOS) == n_tts + 1, 'narração gravada de novo só nessa cena')
st, _, _ = api('POST', f'/api/v1/projetos/{RPID}/cenas/40/refazer', {}, SES)
confere(st == 404, 'cena que não existe é recusada')

print('Galeria: prévias reais do desenho animado e dos efeitos')
st, dm, _ = api('POST', '/api/v1/estilos/animado2d/demo', {'formato': '9:16', 'variante': 'chuva_noite'}, SES)
confere(st == 200 and dm.get('job'), 'demonstração do efeito entra na fila')
t = time.time()
while time.time() - t < 400:
    j = fila.obter(dm['job']['id'])
    if j['status'] in ('concluido', 'falhou'):
        break
    time.sleep(0.5)
confere(j['status'] == 'concluido', f'demonstração com chuva à noite renderizada ({j.get("erro")})')
cat = api('GET', '/api/v1/agente3/catalogo', None, SES)[1]
ef = {x['id']: x for x in cat['efeitos']}
confere(set(ef) == {'chuva_noite', 'neve_fria', 'poeira_quente', 'neblina_dramatica', 'angulos', 'fumaca_susto'} and ef['chuva_noite']['demos'].get('9:16'), 'catálogo mostra os efeitos e a prévia pronta')
st, dm2, _ = api('POST', '/api/v1/estilos/animado2d/demo', {'formato': '9:16', 'variante': 'chuva_noite'}, SES)
confere(st == 200 and dm2.get('url'), 'segunda vez já vem pronta (guardada)')
st, dm3, _ = api('POST', '/api/v1/estilos/vetor_chapado/demo', {'formato': '9:16', 'variante': 'xx'}, SES)
confere(st == 200 and (dm3.get('job') or {}).get('dados', '{}') and 'chuva' not in json.dumps(dm3), 'variante desconhecida é ignorada')

print('Personagens em 3D (beta)')
import personagens3d as p3d  # noqa: E402
if p3d.disponivel():
    cat3d = {e['id']: e for e in api('GET', '/api/v1/agente3/catalogo', None, SES)[1]['estilos']}
    confere(cat3d['animado3d']['status'] == 'beta' and cat3d['animado3d']['servidor'], '3D com personagens aparece como beta')
    st, s3, _ = api('POST', '/api/v1/series', {'titulo': 'Blocos', 'formato': '9:16', 'cenas_qtd': 2, 'duracao_alvo': 8, 'estilo': 'animado3d'}, SES)
    confere(s3['estilo'] == 'animado3d', 'série guarda o visual 3D')
    api('POST', '/api/v1/personagens', {'serie_id': s3['id'], 'nome': 'Ana', 'cabelo_tipo': 'longo', 'roupa': '#e63946', 'voz': 'Kore'}, SES)
    api('POST', '/api/v1/personagens', {'serie_id': s3['id'], 'nome': 'Beto', 'voz': 'Puck'}, SES)
    st, e3, _ = api('POST', f'/api/v1/series/{s3["id"]}/episodios', {'titulo': 'Cubo', 'resumo': 'Um cubo aparece no parque.', 'produzir': True,
                                                                  'modo_aprovacao': 'supervisionado'}, SES)
    t = time.time()
    while time.time() - t < 600:
        r3 = api('GET', f'/api/v1/projetos/{e3["projeto_id"]}/revisao', None, SES)[1]
        if r3['projeto']['status'] in ('ready_for_review', 'failed'):
            break
        time.sleep(0.5)
    print(f'     (episódio 3D levou {time.time() - t:.0f}s)')
    confere(r3['projeto']['status'] == 'ready_for_review', f'episódio 3D produzido ({(r3.get("job") or {}).get("erro")})')
    confere(all((c.get('clipe') or {}).get('estilo') == 'animado3d' for c in r3['projeto']['dados']['cenas']), 'todas as cenas saíram no 3D (sem trocar de estilo escondido)')
    cv3 = ec2.validar_cena({'texto': 'x', 'personagem': 'ana', 'elenco': [{'personagem_id': 'ana', 'posicao': 'centro'}],
                            'planos': [{'plano': 'MS', 'personagem': 'ana', 'angulo': 'baixo'}]})
    cv3['_personagens'] = {'ana': {'nome': 'Ana'}}
    k1 = p3d.chave(cv3, 270, 480, 1)
    cv3['planos'][0]['angulo'] = 'alto'
    confere(k1 != p3d.chave(cv3, 270, 480, 1), 'ângulo do plano muda a câmera 3D (e a chave do cache)')

print('Backup seletivo e métricas (T6)')
obj.unlink()       # o teste anterior estragou um arquivo de propósito; o backup seguinte copia de novo
st, em6, _ = api('PUT', '/api/v1/midias-backup', {'categorias': ['finais', 'audios', 'imagens', 'originais', 'rigs'], 'projetos': [pp['id']]}, SES)
confere(st == 200 and em6['config']['projetos'] == [pp['id']] and 'rigs' in em6['categorias'] and em6['aviso'], 'backup seletivo: só um projeto + rigs; avisa que no mesmo celular não protege contra perda')
st, f6, _ = api('POST', '/api/v1/midias-backup/fazer', {}, SES)
confere(st == 200 and f6['novos'] + f6['ja_existiam'] > 0, f'backup das mídias do projeto feito ({f6})')
st, r6, _ = api('POST', f'/api/v1/midias-backup/restaurar/{pp["id"]}', {}, SES)
confere(st == 200 and r6['ok'] and r6['projeto_encontrado'] and r6['arquivos'] > 0 and Path(r6['pasta']).exists(), f'projeto restaurado em pasta de teste ({r6.get("arquivos")} arquivos)')
import hashlib as _hl  # noqa: E402
conf6 = json.loads((Path(r6['pasta']) / 'conferencia.json').read_text(encoding='utf-8'))
reconf = all(_hl.sha256(p_.read_bytes()).hexdigest()[:16] in {c['sha256'] for c in conf6['conferidos']}
             for p_ in Path(r6['pasta']).rglob('*') if p_.is_file() and p_.name not in ('conferencia.json', 'projeto.json'))
confere(reconf and (Path(r6['pasta']) / 'projeto.json').exists(), 'hash de cada arquivo restaurado conferido de novo, fora do servidor')
st, r6b, _ = api('POST', '/api/v1/midias-backup/restaurar/naoexiste', {}, SES)
confere(st == 200 and not r6b['ok'] and r6b['arquivos'] == 0, 'projeto que não existe: restauração diz que não deu')
api('PUT', '/api/v1/midias-backup', {'projetos': []}, SES)
st, mt, _ = api('GET', '/api/v1/metricas', None, SES)
confere(st == 200 and any(p_['estilo'] == 'documentario' for p_ in mt['planos']), 'métricas: tempo por plano medido de verdade nos jobs')
confere(mt['cache_planos']['refeitos'] > 0 and mt['memoria']['aparelho'] and mt['espaco']['por_pasta_mb'], 'métricas: cache dos planos, memória e espaço por pasta')
confere(mt['estado'] == 'aguardando teste no Android' and 'tentativas' in mt and 'fila' in mt, 'métricas: estado honesto (fora do celular) e tentativas/fila')
confere(not any(k in json.dumps(mt).lower() for k in ('gemini_pago', 'token', 'senha', 'chave_')), 'métricas sem segredo')

print('Diagnóstico do aparelho (T1)')
st, ap, _ = api('GET', '/api/v1/aparelho', None, SES)
confere(st == 200 and ap['ficha']['ffmpeg']['instalado'] and ap['ficha']['processador']['arquitetura'], 'ficha do aparelho lida sem instalar nada')
confere(ap['ficha']['ambiente'] != 'android' and ap['laudo'] is None, 'aqui não é Android: a ficha diz isso e ainda não há laudo')
confere(all(i['pacote'] in ('python', 'ffmpeg', 'git', 'nodejs', 'python-numpy', 'python-pillow', 'librsvg', 'imagemagick') for i in ap['ficha']['pacotes']['itens']),
        'só pacotes aprovados aparecem')
confere(not ap['ficha']['pacotes']['comando'] or ap['ficha']['pacotes']['comando'].startswith('pkg install -y '), 'comando pronto só com o que falta')
st, tj, _ = api('POST', '/api/v1/aparelho/testar', {}, SES)
st2, tj2, _ = api('POST', '/api/v1/aparelho/testar', {}, SES)
confere(st == 200 and tj2['job'] == tj['job'], 'pedir o teste duas vezes não cria dois trabalhos pesados')
t = time.time()
while time.time() - t < 300 and (api('GET', '/api/v1/aparelho', None, SES)[1].get('job') or {}).get('status') not in ('concluido', 'falhou'):
    time.sleep(0.5)
ap = api('GET', '/api/v1/aparelho', None, SES)[1]
lau = ap['laudo'] or {}
confere(ap['job']['status'] == 'concluido' and len(lau.get('testes', [])) == 2, f'teste do aparelho rodou ({ap["job"].get("erro")})')
confere(all(t['ok'] and t['reproducao']['toca'] and t['segundos'] > 0 and t['tamanho_kb'] > 0 for t in lau.get('testes', [])),
        'render de 5 s e prévia leve: conferidos e tocam do começo ao fim')
confere(all('aac' in (t.get('audio') or '') and 'h264' in (t.get('video') or '') for t in lau.get('testes', [])), 'codecs registrados (h264 + aac)')
confere(lau.get('testes') and lau['testes'][1]['resolucao'] == '360x640' and lau['testes'][1]['fps'] == 8, 'prévia leve em 360x640 a 8 quadros/s')
confere(lau.get('testes') and lau['testes'][1]['segundos'] < lau['testes'][0]['segundos'], 'prévia leve custa menos que o render final')
confere(lau.get('estado') == 'aguardando teste no Android' and not lau.get('medido_no_celular'), 'fora do celular o laudo NÃO diz que foi medido no celular')
confere(not any('arquivo' in t for t in lau.get('testes', [])) and lau.get('log'), 'laudo sem caminhos internos e com registro')
import hardware as hw  # noqa: E402
confere(hw.Medidor().resultado()['aparelho_livre_inicio_mb'] is not None, 'memória livre do aparelho é lida de verdade (/proc/meminfo)')

print(f'\n{ok_n} ok, {falhas} falhas   (pasta {TMP})')
if os.getenv('MANTER_SERVIDOR'):
    # Para testar o site no navegador contra este servidor de teste.
    Path(os.environ['MANTER_SERVIDOR']).write_text(json.dumps({'base': BASE, 'sessao': SES['X-Sessao'], 'pid': PID}))
    print('servidor de teste no ar:', BASE, flush=True)
    while True:
        time.sleep(3600)
sys.exit(1 if falhas else 0)
