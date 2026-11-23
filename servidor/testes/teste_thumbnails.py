"""Agente 6 (capas/thumbnails) com servidor HTTP de verdade, FFmpeg e Pillow (sem internet).

Confere: API com sessão (e recusa sem ela), IDs inválidos e caminho fora da pasta, vídeo inexistente/corrompido, capas de um
corte do Agente 1 e de um vídeo do Agente 3, 3 capas diferentes com hash, texto com acento/emoji/quebra sem estourar, 16:9 e
9:16 dentro da área segura, pedido repetido não duplica, reinício não refaz, cancelamento, escolha presa ao hash (cai se o
vídeo ou a capa mudarem), IA desligada com e sem permissão do jeito local, esteira ligada esperando o certificado do vídeo,
envio da capa ao YouTube (falso) e nenhum "postado" falso quando o YouTube recusa a capa.

Rodar: cd servidor && python3 testes/teste_thumbnails.py
"""
import hashlib
import json
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-thumb-'))
os.environ.update(DADOS=str(TMP / 'dados'), BANCO_ARQ=str(TMP / 'dados' / 'studio.sqlite'), CHAVE_MESTRA_ARQ=str(TMP / 'chave'),
                  TOKEN='senha-de-teste-123', FILA_INTERVALO='0.3', ESPERA_INICIAL_AGENTE='99999', BACKUP_DIARIO='0',
                  INTERVALO_AGENDA='600', INTERVALO_AGENDA2='600', CENTRAL_SEM_ACORDAR='1', AGENTE6_SEM_VIGIA='1')
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


def livre():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


# YouTube falso: recebe a capa
CAPAS_YT = []
YT_STATUS = [200]


class YT(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        corpo = self.rfile.read(n)
        if '/thumbnails/set' in self.path:
            CAPAS_YT.append((self.path, hashlib.sha256(corpo).hexdigest(), self.headers.get('Content-Type')))
            st = YT_STATUS[0]
            out = {'items': [{}]} if st < 300 else {'error': {'message': 'The authenticated user doesnt have permissions to upload and set custom video thumbnails.'}}
        else:
            st, out = 404, {}
        b = json.dumps(out).encode()
        self.send_response(st)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)


yt_port = livre()
threading.Thread(target=ThreadingHTTPServer(('127.0.0.1', yt_port), YT).serve_forever, daemon=True).start()
os.environ['BASE_GOOGLE_API'] = f'http://127.0.0.1:{yt_port}'

import servidor as S  # noqa: E402
import banco as db  # noqa: E402
import fila  # noqa: E402
import pipeline as pl  # noqa: E402
import postagem as pg  # noqa: E402
import agente as ag  # noqa: E402
import projetos as pj  # noqa: E402
import thumbnails as th  # noqa: E402
from PIL import Image  # noqa: E402

S.ligar_servicos()
porta = livre()
threading.Thread(target=ThreadingHTTPServer(('127.0.0.1', porta), S.Handler).serve_forever, daemon=True).start()
BASE = f'http://127.0.0.1:{porta}'
SES = {}


def api(metodo, caminho, corpo=None, cab=None, cru=False):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(BASE + caminho, data=dados, method=metodo, headers={'Content-Type': 'application/json', **SES, **(cab or {})})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            b = r.read()
            return r.status, (b if cru else json.loads(b or b'{}')), dict(r.headers)
    except urllib.error.HTTPError as e:
        b = e.read()
        try:
            return e.code, json.loads(b), {}
        except ValueError:
            return e.code, b, {}


def esperar(tid, estados=('aguardando_escolha', 'pronto', 'revisao_manual', 'falhou', 'cancelado', 'aguardando_video'), limite=180):
    fim = time.time() + limite
    while time.time() < fim:
        st, j, _ = api('GET', f'/api/v1/thumbnails/jobs/{tid}')
        if st == 200 and j['estado'] in estados:
            return j
        time.sleep(0.5)
    return api('GET', f'/api/v1/thumbnails/jobs/{tid}')[1]


def video(nome, w, h, dur=8, cor='testsrc2'):
    pg.VIDEOS.mkdir(parents=True, exist_ok=True)
    arq = pg.VIDEOS / f'{nome}.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'{cor}=s={w}x{h}:r=25:d={dur}', '-f', 'lavfi', '-i', f'sine=d={dur}',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(arq)], check=True)
    return arq


# ---------------------------------------------------------------- preparo
print('0. Preparo')
st, r, _ = api('POST', '/api/v1/sessao/login', {'senha': 'senha-de-teste-123', 'nome': 'Celular'})
SES['X-Sessao'] = r['sessao']
confere(not pl.ligado(), 'esteira desligada no começo')
v1 = video('corteum', 720, 1280)
ag._mudar(lambda e: e['cortes'].append({'id': 'c1', 'video': 'corteum', 'titulo': 'Jogada absurda no GTA', 'gancho': 'Ninguém esperava essa jogada no último segundo, quando tudo parecia perdido!',
                                         'hashtags': ['#gta'], 'status': 'pronto', 'criado': time.time()}))
# vídeo do Agente 3 (render final validado), horizontal
p = pj.criar({'titulo': 'Por que o mar é salgado', 'tipo': 'agente3', 'dados': {'roteiro': {'titulo': 'Por que o mar é salgado'}}})
rpasta = db.PROJETOS / p['id']
rpasta.mkdir(parents=True, exist_ok=True)
rarq = rpasta / 'final.mp4'
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=s=1280x720:r=25:d=6', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(rarq)], check=True)
rsha = pl.sha_arquivo(rarq)
db.executar('INSERT INTO renders (id, projeto, versao, arquivo, sha256, duracao, codec, largura, altura, validado, alertas, criado) VALUES (?,?,?,?,?,?,?,?,?,1,?,?)',
            'r1', p['id'], 1, str(rarq), rsha, 6.0, 'h264', 1280, 720, '[]', time.time())
pj.mudar_dados(p['id'], lambda d, _p: (d.update(render={'id': 'r1', 'versao': 1, 'sha': rsha, 'validado': True}), {'status': 'ready_for_review'})[1])

# ---------------------------------------------------------------- segurança
print('1. Segurança da API')
st, _, _ = api('GET', '/api/v1/thumbnails/jobs', cab={'X-Sessao': 'errada'})
confere(st in (401, 403), f'sem sessão válida: recusado ({st})')
st, r, _ = api('POST', '/api/v1/thumbnails/jobs', {'origem': 'corte', 'referencia': '../../etc/passwd'})
confere(st == 400, f'referência com caminho: 400 ({st})')
st, r, _ = api('POST', '/api/v1/thumbnails/jobs', {'origem': 'arquivo', 'referencia': 'x'})
confere(st == 400, f'origem desconhecida: 400 ({st})')
st, r, _ = api('POST', '/api/v1/thumbnails/jobs', {'origem': 'corte', 'referencia': 'naoexiste'})
confere(st == 404, f'corte inexistente: 404 ({st})')
st, r, _ = api('POST', '/api/v1/thumbnails/jobs', {'origem': 'corte', 'referencia': 'c1', 'variantes': 9})
confere(st == 400, f'variantes demais: 400 ({st})')
fora = TMP / 'fora.mp4'
fora.write_bytes(v1.read_bytes())
try:
    th._dentro_dos_dados(fora)
    confere(False, 'arquivo fora da pasta de dados recusado')
except th.ErroThumb as e:
    confere(e.status == 403, 'arquivo fora da pasta de dados recusado (403)')
ruim = pg.VIDEOS / 'quebrado.mp4'
ruim.write_bytes(b'nao sou um video' * 100)
ag._mudar(lambda e: e['cortes'].append({'id': 'cq', 'video': 'quebrado', 'titulo': 'Quebrado', 'status': 'pronto'}))
st, rq, _ = api('POST', '/api/v1/thumbnails/jobs', {'origem': 'corte', 'referencia': 'cq', 'metodo': 'frame'})
jq = esperar(rq['id'])
confere(jq['estado'] == 'falhou' and not jq['variantes'] and 'corrompido' in (jq['erro'] or ''), f'vídeo corrompido: nenhuma capa, falhou com motivo ({jq["estado"]}: {jq["erro"]})')
st, r, _ = api('GET', '/api/v1/thumbnails/capacidades')
confere(st == 200 and r['ffmpeg'] and r['redes']['youtube']['tipo'] == 'custom_image_upload' and not r['redes']['youtube']['testado']
        and r['redes']['tiktok']['tipo'] == 'frame_timestamp_only', 'capacidades por rede, nada "testado" antes de envio real')

# ---------------------------------------------------------------- IA desligada
print('2. IA desligada')
st, r, _ = api('POST', '/api/v1/thumbnails/jobs', {'origem': 'corte', 'referencia': 'c1', 'metodo': 'ia'})
confere(st == 503 and 'Quadro do vídeo' in json.dumps(r, ensure_ascii=False), f'IA sem configuração: 503 com orientação ({st})')

# ---------------------------------------------------------------- corte do Agente 1 (vertical)
print('3. Capas de um corte do Agente 1 (9:16)')
pedido = {'origem': 'corte', 'referencia': 'c1', 'metodo': 'inteligente', 'variantes': 3, 'formato': 'auto', 'texto_modo': 'auto'}
st, j1, _ = api('POST', '/api/v1/thumbnails/jobs', pedido)
confere(st == 200 and j1['estado'] in ('na_fila', 'analisando', 'criando') and not j1['variantes'], f'pedido vira trabalho na fila, sem imagem na resposta ({st})')
st, j1b, _ = api('POST', '/api/v1/thumbnails/jobs', pedido)
confere(j1b['id'] == j1['id'] and j1b.get('repetido'), 'pedido repetido (duplo clique) devolve o mesmo')
confere(fila.obter(db.um('SELECT fila_job FROM thumbnail_jobs WHERE id=?', j1['id'])['fila_job'])['recurso'] == 'pesado', 'trabalho na classe pesada')
j1 = esperar(j1['id'])
vs = [v for v in j1['variantes'] if v['estado'] in ('aprovada', 'reprovada')]
confere(j1['estado'] == 'aguardando_escolha', f'modo supervisionado: espera sua escolha ({j1["estado"]} {j1.get("erro")})')
confere(len(vs) == 3 and len({v['sha256'] for v in vs}) == 3, '3 capas com hashes diferentes')
confere(len({v['layout'] for v in vs}) == 3, 'três composições diferentes: ' + ', '.join(v['layout'] for v in vs))
confere(len({v['quadro_t'] for v in vs}) >= 2, 'quadros de momentos diferentes do vídeo')
confere(all(v['formato'] == '9:16' and (v['largura'], v['altura']) == (1080, 1920) for v in vs), 'vídeo vertical: capas 9:16 (1080x1920)')
confere(all(v['relatorio'].get('metodo', '').startswith('conferência automática') for v in vs), 'laudo diz o método usado')
confere(all(v['relatorio']['criterios'].get('legibilidade_medida', {}).get('medido') for v in vs), 'legibilidade medida a 120 px')
confere(all(not v['relatorio']['bloqueios'] for v in vs if v['estado'] == 'aprovada'), 'aprovadas não têm bloqueio')
for v in vs:
    arq = Path(db.um('SELECT arquivo FROM thumbnail_variantes WHERE id=?', v['id'])['arquivo'])
    confere(arq.exists() and hashlib.sha256(arq.read_bytes()).hexdigest() == v['sha256'] and arq.stat().st_size <= th.MAX_BYTES,
            f'capa {v["numero"]} gravada com o hash certo e até 2 MB')
    with Image.open(arq) as im:
        im.verify()
st, b, h = api('GET', vs[0]['url'], cab={'X-Sessao': ''}, cru=True)
confere(st == 200 and h.get('Content-Type') == 'image/jpeg' and b[:2] == b'\xff\xd8', f'link assinado abre a imagem sem sessão ({st})')
st, _, _ = api('GET', vs[0]['url'].split('?')[0], cab={'X-Sessao': ''})
confere(st in (401, 403), f'sem assinatura e sem sessão: recusado ({st})')
st, _, _ = api('GET', vs[0]['url'].replace('sig=', 'sig=0'), cab={'X-Sessao': ''})
confere(st == 403, f'assinatura adulterada: recusado ({st})')

# texto automático
confere(vs[0]['relatorio']['texto'] == 'Ninguém esperava essa jogada no último segundo, quando tudo parecia perdido!', 'texto automático: gancho completo do corte, com pontuação e mais de 4 palavras')

# ---------------------------------------------------------------- escolha presa ao hash
print('4. Escolha e pacote')
apr = [v for v in vs if v['estado'] == 'aprovada']
confere(bool(apr), 'pelo menos uma capa aprovada pelo diretor')
st, r, _ = api('POST', f'/api/v1/thumbnails/jobs/{j1["id"]}/selecionar', {'variante_id': apr[0]['id'], 'versao': apr[0]['versao'] + 1})
confere(st == 409, f'versão errada: 409 ({st})')
st, r, _ = api('POST', f'/api/v1/thumbnails/jobs/{j1["id"]}/selecionar', {'variante_id': apr[0]['id'], 'versao': apr[0]['versao']})
confere(st == 200 and r['estado'] == 'pronto' and r['selecao'], f'escolha feita: pacote pronto ({st})')
st, pac, _ = api('GET', f'/api/v1/thumbnails/jobs/{j1["id"]}/pacote')
confere(pac['valido'] and pac['video_sha'] == pl.sha_arquivo(v1) and pac['thumb_sha'] == apr[0]['sha256'], 'pacote liga o vídeo e a capa pelos hashes')
confere(db.um("SELECT COUNT(*) n FROM eventos WHERE acao='thumbnail.pacote_pronto'")['n'] == 1, 'evento thumbnail.pacote_pronto registrado (para o Agente 7)')
cap = th.capa_para_video(v1)
confere(cap and cap['sha'] == apr[0]['sha256'], 'Agente 2 acha a capa aprovada para este arquivo')
corte = next(x for x in ag.estado()['cortes'] if x['id'] == 'c1')
confere((corte.get('capa') or {}).get('job') == j1['id'], 'o corte mostra a capa escolhida')

# capa adulterada: cai a aprovação
arq0 = Path(db.um('SELECT arquivo FROM thumbnail_variantes WHERE id=?', apr[0]['id'])['arquivo'])
original = arq0.read_bytes()
arq0.write_bytes(original + b'x')
confere(th.capa_para_video(v1) is None, 'capa mudou depois da aprovação: não vai junto')
st, pac, _ = api('GET', f'/api/v1/thumbnails/jobs/{j1["id"]}/pacote')
confere(not pac['valido'], 'pacote inválido depois que a capa mudou')
arq0.write_bytes(original)
st, r, _ = api('POST', f'/api/v1/thumbnails/jobs/{j1["id"]}/selecionar', {'variante_id': apr[0]['id']})
confere(st == 200 and r['estado'] == 'pronto', 'escolher de novo depois de restaurar')

# ---------------------------------------------------------------- refazer só uma variante
print('5. Refazer só uma capa')
antes = {v['id'] for v in r['variantes']}
st, r, _ = api('POST', f'/api/v1/thumbnails/jobs/{j1["id"]}/refazer', {'numero': 2, 'texto': 'POR QUÊ? 😱'})
confere(st == 200, f'pedido de refazer aceito ({st})')
r = esperar(j1['id'], ('aguardando_escolha', 'pronto', 'revisao_manual', 'falhou'))
novas = [v for v in r['variantes'] if v['id'] not in antes]
confere(novas and all(v['numero'] == 2 for v in novas) and novas[0]['versao'] >= 2, 'só a capa 2 ganhou versão nova')
confere(novas and novas[0]['relatorio']['texto'] == 'POR QUÊ?', 'emoji removido e acento mantido no texto exato da refação')
confere(any('Emoji' in a for a in (r['config'].get('avisos') or [])), 'aviso de emoji removido')
confere(r['selecao'] and r['selecao']['variante'] == apr[0]['id'], 'refazer outra capa não derruba a escolha')

# ---------------------------------------------------------------- texto longo e quebras
print('6. Texto exato longo, quebras, 16:9 e área segura')
fundo = Image.new('RGB', (1280, 720), (30, 120, 200))
cabe = []
for formato in ('16:9', '9:16', '4:5', '1:1'):
    for layout in ('cheia', 'faixa', 'dividido', 'moldura', 'cheia_topo', 'caixa'):
        img, laudo = th.desenhar(fundo, formato, layout, 'Ação incrível\nno último segundo da partida', {})
        sx, sy, sw, sh = th.area_segura(formato)
        cx = laudo['caixa_texto']
        dentro = cx[0] >= sx - 12 and cx[1] >= sy - 12 and cx[2] <= sx + sw + 12 and cx[3] <= sy + sh + 12
        confere(img.size == th.FORMATOS[formato] and (dentro or laudo['overflow']), f'{formato} {layout}: texto dentro da área segura (ou estouro detectado)')
        cabe.append(not laudo['overflow'])
confere(sum(cabe) >= 20, f'texto de 2 linhas cabe na maioria das composições ({sum(cabe)} de 24)')
img, laudo = th.desenhar(fundo, '9:16', 'cheia', 'PALAVRA' * 40, {})
confere(laudo['overflow'], 'texto que não cabe é detectado (overflow), não cortado em silêncio')

# ---------------------------------------------------------------- vídeo do Agente 3 (16:9)
print('7. Capas de um vídeo do Agente 3 (16:9)')
st, j3, _ = api('POST', '/api/v1/thumbnails/jobs', {'origem': 'render', 'referencia': p['id'], 'metodo': 'editorial', 'variantes': 3,
                                                     'texto_modo': 'exato', 'texto': 'Mar salgado?'})
confere(st == 200, f'pedido do Agente 3 aceito ({st})')
j3 = esperar(j3['id'])
v3 = [v for v in j3['variantes'] if v['estado'] in ('aprovada', 'reprovada')]
confere(len(v3) == 3 and all(v['formato'] == '16:9' and v['largura'] == 1280 for v in v3), 'vídeo horizontal: capas 16:9 (1280x720)')
confere(all(v['relatorio']['texto'] == 'Mar salgado?' for v in v3), 'texto exato mantido')
st, fts, _ = api('GET', '/api/v1/thumbnails/fontes')
confere(any(f['origem'] == 'render' and f['referencia'] == p['id'] and f['job'] for f in fts['fontes']) and any(f['referencia'] == 'c1' for f in fts['fontes']),
        'lista de fontes mostra corte e vídeo do Agente 3 com o pedido')

# vídeo mudou: escolha cai
apr3 = next(v for v in v3 if v['estado'] == 'aprovada')
api('POST', f'/api/v1/thumbnails/jobs/{j3["id"]}/selecionar', {'variante_id': apr3['id']})
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=s=1280x720:r=25:d=5', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(rarq)], check=True)
nsha = pl.sha_arquivo(rarq)
db.executar('UPDATE renders SET sha256=? WHERE id=?', nsha, 'r1')
pj.mudar_dados(p['id'], lambda d, _p: d.update(render={'id': 'r1', 'versao': 2, 'sha': nsha, 'validado': True}))
st, j3b, _ = api('GET', f'/api/v1/thumbnails/jobs/{j3["id"]}')
confere(j3b['estado'] == 'aguardando_escolha' and not j3b['selecao'], 'vídeo mudou: a escolha da capa caiu sozinha')
st, r, _ = api('POST', f'/api/v1/thumbnails/jobs/{j3["id"]}/selecionar', {'variante_id': apr3['id']})
confere(st == 409, f'não deixa escolher capa feita para a versão antiga ({st})')

# ---------------------------------------------------------------- reprovada pede confirmação
print('8. Capa reprovada e perfil de marca')
st, pf, _ = api('POST', '/api/v1/thumbnails/perfis', {'nome': 'Canal GTA', 'escopo': 'geral', 'cor_destaque': '#FF3366', 'cor_texto': '#FFFFFF'})
confere(st == 200 and pf['config']['cor_destaque'] == '#FF3366', f'perfil de marca criado ({st})')
st, r, _ = api('POST', '/api/v1/thumbnails/perfis', {'nome': 'X', 'cor_texto': 'vermelho'})
confere(st == 400, 'cor inválida recusada')
st, pf2, _ = api('PATCH', f'/api/v1/thumbnails/perfis/{pf["id"]}', {'intensidade': 90})
confere(pf2['versao'] == 2 and pf2['config']['cor_destaque'] == '#FF3366', 'mudar perfil cria versão nova sem perder o resto')
st, jp, _ = api('POST', '/api/v1/thumbnails/jobs', {'origem': 'corte', 'referencia': 'c1', 'metodo': 'frame', 'variantes': 1, 'texto_modo': 'sem'})
jp = esperar(jp['id'])
vp = jp['variantes'][0]
confere(vp['relatorio']['criterios']['identidade'] == 15, 'perfil "geral" aplicado sozinho (identidade 15)')
rep = db.um("SELECT id FROM thumbnail_variantes WHERE job=? LIMIT 1", jp['id'])
db.executar("UPDATE thumbnail_variantes SET estado='reprovada', nota=55 WHERE id=?", rep['id'])
st, r, _ = api('POST', f'/api/v1/thumbnails/jobs/{jp["id"]}/selecionar', {'variante_id': rep['id']})
confere(st == 409 and 'confirme' in json.dumps(r, ensure_ascii=False), f'capa reprovada pede confirmação ({st})')
st, r, _ = api('POST', f'/api/v1/thumbnails/jobs/{jp["id"]}/selecionar', {'variante_id': rep['id'], 'confirmacao': True})
confere(st == 200 and r['selecao']['escolha'] == 'manual', 'com confirmação: escolha manual registrada')
confere(not db.todos('SELECT id FROM thumbnail_selecoes WHERE job=? AND revogado IS NULL', j1['id']), 'nova escolha para o mesmo vídeo derruba a anterior (uma capa por vídeo)')
relb = json.loads(db.um('SELECT relatorio FROM thumbnail_variantes WHERE id=?', rep['id'])['relatorio'])
relb['bloqueios'] = ['Texto fora da área segura.']
db.executar('UPDATE thumbnail_variantes SET relatorio=? WHERE id=?', json.dumps(relb), rep['id'])
st, r, _ = api('POST', f'/api/v1/thumbnails/jobs/{jp["id"]}/selecionar', {'variante_id': rep['id'], 'confirmacao': True})
confere(st == 409, f'bloqueio crítico: nem com confirmação ({st})')

# ---------------------------------------------------------------- cancelamento e reinício
print('9. Cancelar e reiniciar')
v2 = video('cortedois', 1280, 720, 6, 'smptebars')
ag._mudar(lambda e: e['cortes'].append({'id': 'c2', 'video': 'cortedois', 'titulo': 'Outro corte', 'status': 'pronto'}))
with fila.CADEADO_PESADO if fila.CADEADO_PESADO else threading.Lock():      # segura a fila pesada: o pedido fica esperando
    st, jc, _ = api('POST', '/api/v1/thumbnails/jobs', {'origem': 'corte', 'referencia': 'c2', 'metodo': 'frame', 'variantes': 2})
    st, r, _ = api('POST', f'/api/v1/thumbnails/jobs/{jc["id"]}/cancelar')
confere(st == 200 and r['estado'] == 'cancelado', f'cancelado na fila ({st})')
time.sleep(2)
confere(not db.todos('SELECT id FROM thumbnail_variantes WHERE job=?', jc['id']), 'cancelado: nenhuma capa feita')
st, jr, _ = api('POST', '/api/v1/thumbnails/jobs', {'origem': 'corte', 'referencia': 'c2', 'metodo': 'frame', 'variantes': 2, 'texto_modo': 'sem'})
jr = esperar(jr['id'])
n_antes = db.um('SELECT COUNT(*) n FROM thumbnail_variantes WHERE job=?', jr['id'])['n']


class Ctx:
    def __init__(self, d):
        self.dados, self.id = d, 'x'

    def progresso(self, *a):
        pass

    def salvar(self):
        pass


db.executar("UPDATE thumbnail_jobs SET estado='criando' WHERE id=?", jr['id'])
th.job_thumbnail(Ctx({'job': jr['id']}))          # como se o servidor reiniciasse no meio e a fila rodasse de novo
confere(db.um('SELECT COUNT(*) n FROM thumbnail_variantes WHERE job=?', jr['id'])['n'] == n_antes, 'reinício: não cria capas em dobro')

# ---------------------------------------------------------------- esteira ligada: espera o certificado do vídeo
print('10. Esteira ligada')
pl.ligar(True, 'teste')
v3a = video('cortetres', 720, 1280, 5, 'rgbtestsrc')
ag._mudar(lambda e: e['cortes'].append({'id': 'c3', 'video': 'cortetres', 'titulo': 'Terceiro', 'status': 'pronto'}))
st, je, _ = api('POST', '/api/v1/thumbnails/jobs', {'origem': 'corte', 'referencia': 'c3', 'metodo': 'frame', 'variantes': 1})
je = esperar(je['id'], ('aguardando_video', 'aguardando_escolha', 'pronto', 'falhou'))
confere(je['estado'] == 'aguardando_video' and not je['variantes'], f'sem certificado do vídeo: espera o diretor, sem capa ({je["estado"]})')
pl.ligar(False, 'teste')

# ---------------------------------------------------------------- envio ao YouTube
print('11. Agente 2 envia a capa ao YouTube (falso)')
pg.status_contas = lambda: {k: {'conectado': True, 'erro': '', 'paginas': [], 'pagina': ''} for k in set(pg.PROV.values())}
pg._token_google = lambda: 'tok'
UP = {}


def http_falso(metodo, url, **kw):
    if 'uploadType=resumable' in url:
        return 200, {'Location': BASE_UP + '/up'}, {}
    if url.endswith('/up'):
        return 200, {}, {'id': 'vidYT12345a', 'status': {'privacyStatus': 'public'}}
    return http_real(metodo, url, **kw)


http_real = pg.http
BASE_UP = 'http://falso'
pg.http = http_falso
post = pg.criar_post({'video': 'corteum', 'redes': ['youtube'], 'quando': pg.agora() - 5, 'titulo': 'Jogada', 'legenda': 'x', 'repetir': True})
pg._publicar_um(post['id'], 'youtube')
q = next(x for x in pg.posts() if x['id'] == post['id'])
confere(q['redes']['youtube']['status'] == 'postado', 'vídeo postado')
ativa = db.um('SELECT thumb_sha FROM thumbnail_selecoes WHERE video_sha=? AND revogado IS NULL', pl.sha_arquivo(v1))
confere(CAPAS_YT and 'videoId=vidYT12345a' in CAPAS_YT[-1][0] and CAPAS_YT[-1][1] == ativa['thumb_sha'] and CAPAS_YT[-1][2] == 'image/jpeg',
        'capa aprovada enviada para o vídeo certo, com o mesmo hash')
confere(th.capacidades()['redes']['youtube']['testado'], 'YouTube vira "funcionou num envio real" só depois do envio')
YT_STATUS[0] = 403
post2 = pg.criar_post({'video': 'corteum', 'redes': ['youtube'], 'quando': pg.agora() - 5, 'titulo': 'Jogada 2', 'legenda': 'x', 'repetir': True})
pg._publicar_um(post2['id'], 'youtube')
q2 = next(x for x in pg.posts() if x['id'] == post2['id'])
hist = json.dumps(q2, ensure_ascii=False)
confere(q2['redes']['youtube']['status'] == 'postado' and 'não aceitou a capa' in hist and 'verificada' in hist,
        'YouTube recusou a capa: o vídeo segue postado e fica a nota (sem fingir que a capa foi)')
pg.http = http_real

# exigir capa
th.salvar_config({'exigir_capa_youtube': True})
post3 = pg.criar_post({'video': 'cortedois', 'redes': ['youtube'], 'quando': pg.agora() - 5, 'titulo': 'Sem capa', 'legenda': 'x', 'repetir': True})
conf = pg.conferencia(next(x for x in pg.posts() if x['id'] == post3['id']), 'youtube')
confere(any(x['item'] == 'capa' and x['bloqueia'] for x in conf), '"exigir capa" ligado: sem capa aprovada, o YouTube não sai')
th.salvar_config({'exigir_capa_youtube': False})

# ---------------------------------------------------------------- automático e desempenho
print('12. Modo automático e desempenho')
th.salvar_config({'modo': 'automatico', 'criar_sozinho': True})
v4 = video('cortequatro', 720, 1280, 5)
ag._mudar(lambda e: e['cortes'].append({'id': 'c4', 'video': 'cortequatro', 'titulo': 'Quarto corte', 'status': 'pronto', 'gancho': 'Olha isso'}))
n = th.varrer()
confere(n >= 1, f'criou capas sozinho para corte novo ({n})')
ja = th._ultimo_job('corte', 'c4')
ja = esperar(ja['id'])
confere(ja['estado'] == 'pronto' and ja['selecao'] and ja['selecao']['escolha'] == 'automatica', f'automático: escolheu a melhor aprovada ({ja["estado"]})')
st, dz, _ = api('GET', '/api/v1/thumbnails/desempenho')
confere(st == 200 and dz['pedidos'] >= 5 and dz['tempo_ativo_medio_s'] is not None and 'CTR' in dz['aviso'], 'desempenho com tempos medidos e sem CTR')
st, cf, _ = api('POST', '/api/v1/thumbnails/config', {'modo': 'qualquer'})
confere(st == 400, 'modo inválido recusado')

print('13. Criar sozinho também no supervisionado, com cortes já agendados')
import time as _t  # noqa: E402
th.salvar_config({'modo': 'supervisionado'})
video('corte5', 720, 1280, 5)
video('corte6', 720, 1280, 5)
video('corte7', 720, 1280, 5)
ag._mudar(lambda e: e['cortes'].extend([
    {'id': 'c5', 'video': 'corte5', 'titulo': 'Sai depois', 'status': 'agendado', 'quando': _t.time() + 9000, 'gancho': 'a'},
    {'id': 'c6', 'video': 'corte6', 'titulo': 'Sai antes', 'status': 'agendado', 'quando': _t.time() + 600, 'gancho': 'b'},
    {'id': 'c7', 'video': 'corte7', 'titulo': 'Já foi', 'status': 'postado', 'quando': _t.time() - 600, 'gancho': 'c'}]))
th.salvar_config({'modo': 'manual'})
confere(th.varrer() == 0, 'modo manual: não cria nada sozinho')
th.salvar_config({'modo': 'supervisionado'})
confere(th.config()['criar_sozinho'], '"criar sozinho" vem ligado')
n = th.varrer()
confere(n >= 1 and th._ultimo_job('corte', 'c6') is not None, f'supervisionado: cria capa para corte já agendado, primeiro o que sai antes ({n})')
confere(th._ultimo_job('corte', 'c7') is None, 'corte já postado não ganha capa')
j6 = esperar(th._ultimo_job('corte', 'c6')['id'])
confere(j6['estado'] == 'aguardando_escolha' and not j6.get('selecao'), f'supervisionado: as capas esperam a sua escolha ({j6["estado"]})')

print(f'\n{ok_n} ok, {falhas} falha(s)   (pasta {TMP})')
sys.exit(1 if falhas else 0)
