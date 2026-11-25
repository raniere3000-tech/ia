"""Download em lote de Publicações: nomes, TXT, MP4 individual, ZIP simples e completo, falhas, cancelamento, segurança e "não mexe em nada".

Servidor HTTP de verdade (sem internet, nenhuma publicação). Rodar: cd servidor && PYTHONPATH=. python3 testes/teste_download_lote.py
"""
import hashlib
import io
import json
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path

os.environ.setdefault('ESTEIRA_COMPLETA', '0')
TMP = Path(tempfile.mkdtemp(prefix='ec-dl-'))
os.environ.update(DADOS=str(TMP / 'dados'), BANCO_ARQ=str(TMP / 'dados' / 'studio.sqlite'), CHAVE_MESTRA_ARQ=str(TMP / 'chave'), TOKEN='senha-de-teste-123',
                  FILA_INTERVALO='0.3', ESPERA_INICIAL_AGENTE='99999', BACKUP_DIARIO='0', INTERVALO_AGENDA='600', INTERVALO_AGENDA2='600',
                  CENTRAL_SEM_ACORDAR='1', AGENTE6_SEM_VIGIA='1', COORDENADOR_SEM_VIGIA='1')
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


import servidor as S  # noqa: E402
import banco as db  # noqa: E402
import postagem as pg  # noqa: E402
import pipeline as pl  # noqa: E402
import download_lote as dl  # noqa: E402
from PIL import Image  # noqa: E402

S.ligar_servicos()
porta = livre()
threading.Thread(target=ThreadingHTTPServer(('127.0.0.1', porta), S.Handler).serve_forever, daemon=True).start()
BASE = f'http://127.0.0.1:{porta}'
SES = {}


def req(metodo, caminho, corpo=None, cab=None, ses=True):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    r = urllib.request.Request(BASE + caminho, data=dados, method=metodo, headers={'Content-Type': 'application/json', **(SES if ses else {}), **(cab or {})})
    try:
        with urllib.request.urlopen(r, timeout=120) as x:
            return x.status, x.read(), dict(x.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def api(metodo, caminho, corpo=None, ses=True):
    st, b, h = req(metodo, caminho, corpo, ses=ses)
    try:
        return st, json.loads(b or b'{}')
    except ValueError:
        return st, {}


st, r = api('POST', '/api/v1/sessao/login', {'senha': 'senha-de-teste-123', 'nome': 'Celular'})
SES['X-Sessao'] = r['sessao']

pg.VIDEOS.mkdir(parents=True, exist_ok=True)
PNG = None


def png_bytes(cor):
    b = io.BytesIO()
    Image.new('RGB', (64, 112), cor).save(b, 'PNG')
    return b.getvalue()


def post(pid, titulo, legenda='', redes=None, conteudo=None, extra=None):
    """Post de teste com vídeo falso (bytes diferentes por vídeo)."""
    (pg.VIDEOS / f'v{pid}.mp4').write_bytes(conteudo if conteudo is not None else (f'video-{pid}-'.encode() * 300))
    p = {'id': pid, 'video': f'v{pid}', 'titulo': titulo, 'legenda': legenda, 'quando': time.time() + 3600, 'criado': time.time(),
         'opcoes': {}, 'redes': redes or {'youtube': {'status': 'agendado', 'link': '', 'erro': ''}}, 'hash': f'h{pid}', **(extra or {})}
    pg.salvar_posts(pg.posts() + [p])
    return p


def capa(pid, cor, nome_arquivo='capa.jpg'):
    """Capa aprovada e escolhida para o hash do vídeo atual. O arquivo é PNG de verdade mesmo com nome .jpg."""
    arq = pg.VIDEOS / f'v{pid}.mp4'
    sha = pl.sha_arquivo(arq)
    f = TMP / f'{pid}-{nome_arquivo}'
    f.write_bytes(png_bytes(cor))
    csha = hashlib.sha256(f.read_bytes()).hexdigest()
    agora = time.time()
    db.executar("INSERT INTO thumbnail_jobs (id, origem, referencia, video_sha, config, estado, criado, atualizado, chave, titulo) VALUES (?,?,?,?,?,?,?,?,?,?)",
                f'j{pid}', 'render', f'proj{pid}', sha, '{}', 'pronto', agora, agora, f'j{pid}', 't')
    db.executar("INSERT INTO thumbnail_variantes (id, job, numero, versao, arquivo, sha256, formato, nota, estado, criado) VALUES (?,?,?,?,?,?,?,?,?,?)",
                f'var{pid}', f'j{pid}', 1, 1, str(f), csha, '9:16', 90, 'aprovada', agora)
    db.executar("INSERT INTO thumbnail_selecoes (id, job, variante, video_sha, thumb_sha, escolha, aprovado, criado) VALUES (?,?,?,?,?,?,?,?)",
                f'sel{pid}', f'j{pid}', f'var{pid}', sha, csha, 'automatica', 1, agora)
    return f


def esperar(jid, estados=('pronto', 'parcial', 'falhou', 'cancelado'), limite=60):
    fim = time.time() + limite
    while time.time() < fim:
        st, j = api('GET', f'/api/v1/downloads/{jid}')
        if j.get('estado') in estados:
            return j
        time.sleep(0.2)
    return api('GET', f'/api/v1/downloads/{jid}')[1]


def baixar(caminho, cab=None):
    return req('GET', caminho, cab=cab, ses=False)


# ---------------------------------------------------------------- nomes
print('DL.03 Nomes seguros')
usados = set()
a = dl.nome_base(1, 'Role noturno de jet ski GTA 6', 'a1b2c3d4e5', usados)
b = dl.nome_base(2, 'Role noturno de jet ski GTA 6', 'f6a7b8c9d0', usados)
confere(a == '001 - Role noturno de jet ski GTA 6 - a1b2c3' and a != b and b.startswith('002 - '), 'títulos iguais viram nomes diferentes (número + ID)')
perigosos = ['../../etc/passwd', 'a/b\\c:d*e?f"g<h>i|j', 'CON', '....', '   ', 'x' * 500, 'Vídeo 🔥🚀 incrível ✨ — ação!', '\x00\x01evil.mp4', 'a‮b']
for t in perigosos:
    n = dl.nome_base(7, t, 'zz99aa11bb', set())
    ok = all(c not in n for c in '/\\:*?"<>|\x00') and '..' not in n and len(n) <= 120 and not n.endswith(('.', ' ')) and n.startswith('007 - ')
    confere(ok, f'nome seguro para {t[:24]!r} -> {n[:50]!r}')
confere(dl.nome_base(1, '', 'abc123def4', set()) == '001 - Video - abc123def4 - abc123', 'sem título: "Video - ID"')
confere('Vídeo' in dl.nome_base(1, 'Vídeo 🔥 incrível', 'abc123def4', set()) and '🔥' not in dl.nome_base(1, 'Vídeo 🔥 incrível', 'abc123def4', set()),
        'acentos ficam; emoji sai só do nome do arquivo')

# ---------------------------------------------------------------- texto de publicação
print('DL.03 TXT de publicação')
p1 = post('aaa1111111', 'Rolê noturno de jet ski explorando o mapa do GTA 6', 'Rolê noturno de jet ski explorando o mapa do GTA 6\nExplorando o mapa durante a noite! 🌙🔥\n\n#GTA6 #Gameplay #Games\n\nLink original do vídeo [https://youtu.be/ORIGINAL1]',
          {'youtube': {'status': 'postado', 'link': 'https://youtube.com/shorts/ABCdef12345', 'erro': ''}, 'tiktok': {'status': 'agendado', 'link': '', 'erro': ''},
           'instagram': {'status': 'agendado', 'link': '', 'erro': ''}})
p1['tiktok_meta'] = {'titulo': 'Rolê noturno de jet ski no GTA 6!', 'descricao': 'Explorando o mapa durante a noite! 🌙', 'hashtags': ['#GTA6', '#Gaming', '#Gameplay'],
                     'links': [{'rotulo': 'Vídeo original', 'url': 'https://youtu.be/ORIGINAL1'}]}
pg.salvar_posts([p1])
t = dl.texto_publicacao(p1)
confere(t.startswith('VÍDEO: Rolê noturno de jet ski explorando o mapa do GTA 6\nID: aaa1111111\n'), 'cabeçalho com título real e ID')
confere(all(f'========== {r} ==========' in t for r in ('YOUTUBE', 'TIKTOK', 'INSTAGRAM')) and 'FACEBOOK' not in t, 'um bloco por rede do post')
confere('🌙🔥' in t and 'ê' in t and '\n\n#GTA6' in t, 'emoji, acento e quebra de linha preservados')
yt = t.split('========== TIKTOK')[0]
confere('Publicado: https://youtube.com/shorts/ABCdef12345' in yt and 'LINKS: Vídeo original: https://youtu.be/ORIGINAL1' in yt, 'links reais do YouTube (o publicado e o original)')
confere('HASHTAGS: #GTA6 #Gameplay #Games' in yt, 'hashtags do YouTube vêm da legenda salva')
desc_yt = yt.split('DESCRIÇÃO: ')[1].split('\nHASHTAGS')[0]
confere('#GTA6' not in desc_yt and 'Link original' not in desc_yt and not desc_yt.startswith('Rolê noturno'), 'campo descrição não repete título, hashtags nem link do texto pronto')
confere('TEXTO PRONTO PARA COPIAR:\nRolê noturno de jet ski explorando o mapa do GTA 6\nExplorando' in yt, 'YouTube também tem o texto pronto para copiar')
tk = t.split('========== TIKTOK ==========')[1].split('==========')[0]
confere('TÍTULO: Rolê noturno de jet ski no GTA 6!' in tk and 'HASHTAGS: #GTA6 #Gaming #Gameplay' in tk, 'TikTok usa os metadados próprios dele')
confere('TEXTO PRONTO PARA COPIAR:\nRolê noturno de jet ski no GTA 6!' in tk, 'TikTok: texto pronto é o do TikTok')
ig = t.split('========== INSTAGRAM ==========')[1]
confere('LINKS: Vídeo original: https://youtu.be/ORIGINAL1' in ig and 'Publicado' not in ig, 'Instagram sem link próprio: só o original (nada inventado)')
p2 = {'id': 'bbb2222222', 'video': 'vbbb', 'titulo': '', 'legenda': '', 'redes': {'kwai': {'status': 'manual', 'link': '', 'erro': ''}}}
t2 = dl.texto_publicacao(p2)
confere('VÍDEO: Video - bbb2222222' in t2 and t2.count(dl.NAO_CONFIG) == 4 and 'TEXTO PRONTO' not in t2, 'campos ausentes: "[não configurado]" e nenhum bloco de cópia vazio')

# ---------------------------------------------------------------- API e segurança
print('DL.03/04 API, segurança e MP4 individual')
st, _ = api('POST', '/api/v1/downloads', {'posts': ['aaa1111111'], 'formato': 'pacote'}, ses=False)
confere(st in (401, 403), f'sem login: recusado ({st})')
st, _ = api('GET', '/api/v1/downloads/0123456789ab', ses=False)
confere(st in (401, 403), f'consulta sem login: recusada ({st})')
st, r = api('POST', '/api/v1/downloads', {'posts': [], 'formato': 'zip'})
confere(st == 400, 'sem vídeo escolhido: 400')
st, r = api('POST', '/api/v1/downloads', {'posts': ['x'] * 3, 'formato': 'exe'})
confere(st == 400, 'formato inválido: 400')
st, r = api('POST', '/api/v1/downloads', {'posts': [f'p{i}' for i in range(dl.MAX_ITENS + 1)], 'formato': 'zip'})
confere(st == 400, 'passou do limite por vez: 400')

# vários posts, com títulos iguais e um arquivo que não existe
pa = post('ccc3333333', 'Mesmo título', 'Mesmo título\n#a', conteudo=b'AAAA' * 5000)
pb = post('ddd4444444', 'Mesmo título', 'Mesmo título\n#b', conteudo=b'BBBB' * 7000)
pc = post('eee5555555', 'Sem arquivo', 'x')
(pg.VIDEOS / 'veee5555555.mp4').unlink()
f_capa_c = capa('ccc3333333', (200, 30, 30))
antes_posts = json.dumps(pg.posts(), sort_keys=True)
antes_sel = db.um('SELECT COUNT(*) n, SUM(revogado IS NOT NULL) r FROM thumbnail_selecoes')
antes_fila = db.um('SELECT COUNT(*) n FROM jobs')['n']

ordem = ['ccc3333333', 'ddd4444444', 'eee5555555', '../../etc/passwd', 'aaa1111111', 'ccc3333333']
st, j = api('POST', '/api/v1/downloads', {'posts': ordem, 'formato': 'pacote'})
confere(st == 200 and j['total'] == 5 and j['disponiveis'] == 3, f'pedido aceito: duplicado some, inexistente e sem arquivo ficam indisponíveis ({j.get("total")}/{j.get("disponiveis")})')
confere([i['n'] for i in j['itens']] == [1, 2, 3, 4, 5] and j['itens'][0]['post'] == 'ccc3333333', 'numeração na ordem apresentada')
confere(j['itens'][3]['disponivel'] is False and 'não encontrado' in j['itens'][3]['motivo'] and '/' not in j['itens'][3]['nome'], 'caminho malicioso do cliente é só um ID inexistente')
j = esperar(j['id'])
confere(j['estado'] == 'parcial' and j['preparados'] == 3 and len(j['falhas']) == 2, f'resultado parcial declarado ({j["estado"]}, {j["preparados"]} preparados)')
confere(j['arquivo'] and j['arquivo']['nome'].startswith('EstudioClip_') and j['arquivo']['nome'].endswith('.zip') and '_videos' not in j['arquivo']['nome'], 'nome do ZIP do pacote completo')
st, corpo, cab = baixar(j['arquivo']['url'])
confere(st == 200 and cab.get('Content-Type') == 'application/zip' and 'attachment' in cab.get('Content-Disposition', '') and "filename*=UTF-8''EstudioClip_" in cab['Content-Disposition'], 'ZIP entregue como download (com nome em UTF-8)')
zf = zipfile.ZipFile(io.BytesIO(corpo))
nomes = zf.namelist()
c1 = j['itens'][0]['nome']
c2 = j['itens'][1]['nome']
confere(zf.testzip() is None, 'ZIP íntegro')
confere(f'{c1}/{c1}.mp4' in nomes and f'{c1}/{c1}_PUBLICACAO.txt' in nomes and f'{c2}/{c2}.mp4' in nomes, 'estrutura: pasta por vídeo com MP4 e TXT com o mesmo nome base')
confere(f'{c1}/{c1}_CAPA.png' in nomes and not any(n.endswith('_CAPA.jpg') for n in nomes), 'capa com a extensão VERDADEIRA (PNG, mesmo salva como .jpg)')
confere(zf.read(f'{c1}/{c1}_CAPA.png')[:8] == b'\x89PNG\r\n\x1a\n' and zf.read(f'{c1}/{c1}_CAPA.png') == f_capa_c.read_bytes(), 'a capa do ZIP é a aprovada, byte a byte')
confere(zf.read(f'{c1}/{c1}.mp4') == b'AAAA' * 5000 and zf.read(f'{c2}/{c2}.mp4') == b'BBBB' * 7000, 'cada MP4 corresponde ao vídeo certo (títulos iguais não se misturam)')
confere(not any(n.startswith(f'{c2}/') and 'CAPA' in n for n in nomes) and j['sem_capa'] >= 1, 'vídeo sem capa aprovada: sem capa no ZIP, MP4 e TXT seguem')
confere('RELATORIO.txt' in nomes and 'Sem arquivo' in zf.read('RELATORIO.txt').decode() and 'Post não encontrado' in zf.read('RELATORIO.txt').decode()
        and c2 in zf.read('RELATORIO.txt').decode(), 'relatório lista ausentes e vídeos sem capa')
confere(zf.read(f'{c1}/{c1}_PUBLICACAO.txt').decode('utf-8').startswith('VÍDEO: Mesmo título\nID: ccc3333333'), 'TXT em UTF-8 dentro do ZIP')
confere(all(not n.startswith('/') and '..' not in n and '\\' not in n for n in nomes), 'nenhum caminho absoluto ou relativo dentro do ZIP')

# Range (retomada de transferência interrompida)
tam = len(corpo)
st1, parte1, _ = baixar(j['arquivo']['url'], {'Range': f'bytes=0-{tam // 2 - 1}'})
st2, parte2, cab2 = baixar(j['arquivo']['url'], {'Range': f'bytes={tam // 2}-'})
confere(st1 == 206 and st2 == 206 and parte1 + parte2 == corpo and cab2.get('Content-Range', '').startswith(f'bytes {tam // 2}-'), 'transferência interrompida retoma por Range e fecha igual')

# links assinados
url = j['arquivo']['url']
st, _, _ = baixar(url.split('?')[0])
confere(st in (401, 403), 'sem assinatura nem login: recusado')
st, _, _ = baixar(url[:-3] + ('abc' if not url.endswith('abc') else 'xyz'))
confere(st == 403, 'assinatura adulterada: 403')
st, _, _ = baixar(url.replace('/arquivo', '/item/1'))
confere(st in (403, 404), 'assinatura de um arquivo não vale para outro endereço')

# ZIP só de vídeos
st, jz = api('POST', '/api/v1/downloads', {'posts': ['ccc3333333', 'ddd4444444'], 'formato': 'zip'})
jz = esperar(jz['id'])
zz = zipfile.ZipFile(io.BytesIO(baixar(jz['arquivo']['url'])[1]))
confere(jz['estado'] == 'pronto' and sorted(zz.namelist()) == sorted([f'{jz["itens"][0]["nome"]}.mp4', f'{jz["itens"][1]["nome"]}.mp4']) and '_videos' in jz['arquivo']['nome'],
        'ZIP só com vídeos: sem pastas, sem capa, sem TXT, mesmos nomes base; completo = "pronto"')

# MP4 individual
st, jm = api('POST', '/api/v1/downloads', {'posts': ['ccc3333333', 'ddd4444444', 'eee5555555'], 'formato': 'mp4'})
confere(jm['estado'] == 'parcial' and jm['itens'][0].get('url') and not jm['itens'][2].get('url'), 'MP4 individual: link só para quem tem arquivo; o ausente é declarado')
st, corpo1, cab1 = baixar(jm['itens'][1]['url'])
confere(st == 200 and corpo1 == b'BBBB' * 7000 and cab1.get('Content-Type') == 'video/mp4' and f"filename*=UTF-8''{urllib.parse.quote(jm['itens'][1]['nome'] + '.mp4', safe='')}" in cab1.get('Content-Disposition', ''),
        'MP4 individual: bytes do arquivo final e nome base no cabeçalho')
st, _, _ = baixar(jm['itens'][2]['url'] if jm['itens'][2].get('url') else f'/api/v1/downloads/{jm["id"]}/item/3')
confere(st in (401, 403, 404), 'item indisponível não é entregue')

# nada mudou
depois_sel = db.um('SELECT COUNT(*) n, SUM(revogado IS NOT NULL) r FROM thumbnail_selecoes')
confere(json.dumps(pg.posts(), sort_keys=True) == antes_posts, 'posts (status, horários, redes, links) exatamente iguais')
confere(depois_sel == antes_sel and db.um('SELECT COUNT(*) n FROM jobs')['n'] == antes_fila, 'nenhuma capa revogada, nenhum job de agente criado')
confere((pg.VIDEOS / 'vccc3333333.mp4').read_bytes() == b'AAAA' * 5000, 'vídeos originais intactos')

# ---------------------------------------------------------------- capa desatualizada
print('DL.04 Capa desatualizada, falta de espaço, cancelar, repetir')
(pg.VIDEOS / 'vccc3333333.mp4').write_bytes(b'NOVO' * 6000)        # versão final mudou depois da capa aprovada
st, jd = api('POST', '/api/v1/downloads', {'posts': ['ccc3333333'], 'formato': 'pacote'})
jd = esperar(jd['id'])
zd = zipfile.ZipFile(io.BytesIO(baixar(jd['arquivo']['url'])[1]))
nm = jd['itens'][0]['nome']
confere(jd['itens'][0]['capa'] in ('desatualizada', 'ausente') and f'{nm}/{nm}_CAPA.png' not in zd.namelist() and zd.read(f'{nm}/{nm}.mp4') == b'NOVO' * 6000
        and 'RELATORIO.txt' in zd.namelist(), f'capa de versão antiga não vai; o MP4 novo sim; relatório avisa ({jd["itens"][0]["capa"]})')

orig = dl._espaco_livre
dl._espaco_livre = lambda pasta: 1024
st, jf = api('POST', '/api/v1/downloads', {'posts': ['ddd4444444'], 'formato': 'zip'})
jf = esperar(jf['id'])
dl._espaco_livre = orig
confere(jf['estado'] == 'falhou' and 'espaço' in jf['erro'] and not list(dl.DIR.glob(jf['id'] + '*')), 'falta de espaço: falha clara, sem arquivo pela metade')

dl._PREPARO.acquire()                                              # segura a fila de preparo: o job fica "preparando"
st, jc = api('POST', '/api/v1/downloads', {'posts': ['ccc3333333', 'ddd4444444'], 'formato': 'pacote'})
confere(jc['estado'] == 'preparando', 'enquanto espera a vez, o estado é "preparando"')
st, jc2 = api('POST', f'/api/v1/downloads/{jc["id"]}/cancelar', {})
dl._PREPARO.release()
jc = esperar(jc['id'])
time.sleep(0.5)
confere(jc['estado'] == 'cancelado' and not list(dl.DIR.glob(jc['id'] + '*')), 'cancelado: estado certo e temporários apagados')
confere((pg.VIDEOS / 'vddd4444444.mp4').exists(), 'cancelar nunca apaga o vídeo original')
st, r = api('POST', f'/api/v1/downloads/{jc["id"]}/cancelar', {})
confere(st == 409, 'cancelar de novo: 409')
st, jr = api('POST', f'/api/v1/downloads/{jc["id"]}/tentar-novamente', {})
jr = esperar(jr['id'])
confere(st == 200 and jr['id'] != jc['id'] and jr['estado'] == 'pronto' and jr['preparados'] == 2, 'tentar novamente: novo preparo com os mesmos vídeos, completo')
st, _ = api('GET', f'/api/v1/downloads/{jc["id"]}')
confere(st == 404, 'o pedido cancelado antigo foi limpo')

# servidor reiniciou no meio
j0 = db.kv('download.job.' + jr['id'])
j0.update(id='0123456789ab', estado='preparando')
db.kv_gravar('download.job.0123456789ab', j0)
st, r = api('GET', '/api/v1/downloads/0123456789ab')
confere(r.get('estado') == 'falhou' and 'reiniciou' in r.get('erro', ''), 'preparo interrompido por reinício vira falha com saída (tentar novamente)')

# limpeza de prontos velhos
j1 = db.kv('download.job.' + jr['id'])
j1['criado'] = time.time() - 3 * 24 * 3600
db.kv_gravar('download.job.' + jr['id'], j1)
dl.limpar()
confere(not list(dl.DIR.glob(jr['id'] + '*')) and (pg.VIDEOS / 'vccc3333333.mp4').exists(), 'arquivos prontos velhos são apagados; vídeos originais não')

# o agendamento e as redes não foram tocados em momento nenhum
confere(all(p['redes'][r]['status'] in ('agendado', 'postado', 'manual') for p in pg.posts() for r in p['redes']), 'status dos posts continuam os de antes')

print(f'\n{ok_n} ok, {falhas} falha(s)   (pasta {TMP})')
sys.exit(1 if falhas else 0)
