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
b4 = dict(briefing, tema='Planos', imagens='busca', estilo='documentario', modo_aprovacao='supervisionado', cenas_qtd=3, duracao_alvo=9)
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

print(f'\n{ok_n} ok, {falhas} falhas   (pasta {TMP})')
if os.getenv('MANTER_SERVIDOR'):
    # Para testar o site no navegador contra este servidor de teste.
    Path(os.environ['MANTER_SERVIDOR']).write_text(json.dumps({'base': BASE, 'sessao': SES['X-Sessao'], 'pid': PID}))
    print('servidor de teste no ar:', BASE, flush=True)
    while True:
        time.sleep(3600)
sys.exit(1 if falhas else 0)
