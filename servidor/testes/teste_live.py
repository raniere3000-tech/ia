"""Parte Live: grava em blocos, cada bloco vira cortes (Agente 1 -> editor/diretor) e o aprovado é postado na hora.

A live de verdade (YouTube) não é usada aqui: a "live" é um arquivo local que o FFmpeg grava em blocos do mesmo jeito.
O corte do bloco (Gemini, editor e diretor) é simulado; a postagem usa o caminho real (criar_post com o portão do certificado).

Rodar: cd servidor && python3 testes/teste_live.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-live-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
os.environ['CENTRAL_SEM_ACORDAR'] = '1'
os.environ.pop('PIPELINE_V2', None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import banco as db  # noqa: E402
import agente as ag  # noqa: E402
import postagem as pg  # noqa: E402
import pipeline as pl  # noqa: E402
import agenda_postagem as a2  # noqa: E402
import live as lv  # noqa: E402
import rotas_esteira as rt  # noqa: E402

db.migrar()
pg.acordar = lambda: None
avisos = []
ag.avisar = lambda tipo, assunto, corpo, *a, **k: avisos.append(assunto) or True
lv.ESPERA_ERRO = 0
ok = falhas = 0


def check(c, m):
    global ok, falhas
    if c:
        ok += 1
        print('  ok  ', m)
    else:
        falhas += 1
        print('  FALHOU:', m)


def erro(f, *a, **k):
    try:
        f(*a, **k)
    except (lv.ErroLive, rt.ErroRota) as e:
        return e
    return None


def rota(metodo, caminho, corpo=None):
    return rt.tratar(metodo, caminho, {}, lambda: corpo or {}, 'teste')


# "live": arquivo de 6 min e 40 s (blocos de 3 min -> 3 blocos: 3 min, 3 min e 40 s)
FONTE = TMP / 'live.mp4'
subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=160x284:d=400:r=5', '-f', 'lavfi', '-i', 'sine=f=300:d=400',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-g', '10', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(FONTE)], check=True)
estado_live = {'ao_vivo': True, 'chamadas': 0}


def pegar(link):
    estado_live['chamadas'] += 1
    no_ar = estado_live['ao_vivo'] and estado_live['chamadas'] <= 2      # comecar + 1ª gravação; a abertura seguinte: a live acabou
    return {'url': str(FONTE), 'titulo': 'Live de teste', 'id': 'LIVE1234567', 'canal': 'UCx', 'canal_nome': 'Canal X', 'ao_vivo': no_ar}


lv.PEGAR = pegar
lv.iniciar()

print('1. Antes de gravar')
check('esteira' in str(erro(lv.comecar, {'link': 'https://youtube.com/live/abc', 'origem': 'meu', 'redes': ['youtube']})), 'sem a esteira ligada não grava')
pl.ligar(True, 'teste')
check('link' in str(erro(lv.comecar, {'link': 'nada'})), 'sem link não grava')
check('de quem é a live' in str(erro(lv.comecar, {'link': 'https://youtube.com/live/abc', 'redes': ['youtube']})), 'sem dizer de quem é a live não grava')
estado_live['chamadas'] = 0
check('rede' in str(erro(lv.comecar, {'link': 'https://youtube.com/live/abc', 'origem': 'meu', 'redes': []})), 'sem rede para postar não grava')
estado_live.update(ao_vivo=False, chamadas=0)
check('não está ao vivo' in str(erro(lv.comecar, {'link': 'https://youtube.com/live/abc', 'origem': 'meu', 'redes': ['youtube']})), 'link que não está ao vivo é recusado')
check(erro(lv.salvar_config, {'bloco_min': 'x'}) is not None and lv.salvar_config({'bloco_min': 99})['bloco_min'] == 20, 'configuração com limites')

print('2. Gravando em blocos')
estado_live.update(ao_vivo=True, chamadas=0)
L = rota('POST', '/api/v1/live/comecar', {'link': 'https://youtube.com/live/abc', 'origem': 'meu', 'redes': ['youtube', 'tiktok'], 'bloco_min': 3,
                                           'max_posts': 2, 'cortes_por_bloco': 2})
lid = L['id']
check(L['estado'] == 'gravando' and L['direitos']['origem'] == 'meu', 'começou a gravar, com a origem registrada')
check('Já tem uma live' in str(erro(lv.comecar, {'link': 'https://youtube.com/live/abc', 'origem': 'meu', 'redes': ['youtube']})), 'uma live por vez')
for _ in range(120):
    if lv.obter(lid)['estado'] == 'terminada':
        break
    time.sleep(0.5)
L = lv.obter(lid)
check(L['estado'] == 'terminada' and 'terminou' in L['motivo_fim'], 'quando a live acaba, a gravação termina sozinha')
check([b['n'] for b in L['blocos']] == [1, 2, 3], 'gravou 3 blocos (3 min + 3 min + o resto)')
check(abs(ag.duracao(Path(L['blocos'][0]['arquivo'])) - 180) < 8, 'cada bloco tem o tamanho escolhido (3 min)')
jobs = db.todos("SELECT * FROM jobs WHERE tipo='live.bloco' ORDER BY criado")
check(len(jobs) == 3 and all(j['agente'] == 'agente1' for j in jobs), 'cada bloco entrou na fila do Agente 1 (um por vez)')
check(any('gravação encerrada' in a for a in avisos), 'aviso no fim da gravação')

print('3. Cada bloco: melhores momentos -> editor e diretor -> posta na hora')
chamadas = []


def processar_falso(v, quantos, baixado=None, extra=None, ajustes=None):
    """No lugar do Agente 1 + esteira: 1 corte aprovado (com certificado) e 1 reprovado por bloco."""
    chamadas.append({'v': v, 'quantos': quantos, 'arq': baixado[0], 'ajustes': ajustes})
    criados = []
    for aprovado in (True, False):
        vid = uuid.uuid4().hex[:12]
        arq = pg.VIDEOS / f'{vid}.mp4'
        subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', f'color=c={"green" if aprovado else "red"}:s=160x284:d=2:r=10',
                        '-f', 'lavfi', '-i', f'sine=f={300 + len(chamadas)}:d=2', '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac', '-shortest', str(arq)], check=True)
        cid = uuid.uuid4().hex[:10]
        c = dict(id=cid, titulo=f'Momento {len(chamadas)}{"" if aprovado else " (ruim)"}', chave='k' + cid, video=vid, criado=time.time(),
                 status='pronto' if aprovado else 'reprovado', post='', origem=v['id'], origem_titulo=v['titulo'], canal=v['canal'], canal_nome='',
                 ini=0, fim=60, dur=60, hashtags=['#live'], gancho='', motivo='m', nota=80, variacoes=[], fala='IA', tamanho=arq.stat().st_size,
                 email=False, tipo='agente', hash=ag._hash(arq), legendado=True, qa={'nota': 82 if aprovado else 40, 'erros': [], 'avisos': []})
        c.update(extra or {})
        if aprovado:
            sha = pl.sha_arquivo(arq)
            pl.emitir_certificado(cid, sha, {'score': 82, 'blocking_findings': []})
        ag._mudar(lambda e, c=c: e['cortes'].append(c))
        criados.append(c)
    return criados


ag.processar_video = processar_falso


class Ctx:
    def __init__(self, d):
        self.dados = d

    def progresso(self, *a):
        pass


r1 = lv.job_bloco(Ctx({'live': lid, 'n': 1}))
check(chamadas[0]['quantos'] == 2 and chamadas[0]['ajustes'] == {'nota_min': 70} and chamadas[0]['v']['id'] == 'LIVE1234567-live1',
      'o Agente 1 corta o bloco já gravado, com a nota mínima da live (70)')
cs = [c for c in ag.estado()['cortes'] if c.get('live') == lid]
apr = next(c for c in cs if c['status'] == 'agendado')
p = next(x for x in pg.posts() if x['id'] == apr['post'])
check(r1['resultado'] == {'cortes': 2, 'aprovados': 1, 'postando': 1}, 'bloco 1: 2 cortes, 1 aprovado, 1 indo para as redes')
check(abs(p['quando'] - time.time()) < 30 and set(p['redes']) == {'youtube', 'tiktok'}, 'aprovado: post NA HORA, nas redes escolhidas para a live')
check(not any(c['status'] == 'agendado' for c in cs if c['status'] == 'reprovado') and next(c for c in cs if c['status'] == 'reprovado')['post'] == '',
      'reprovado pelo diretor não é postado')
check(not Path(lv.obter(lid)['blocos'][0]['arquivo']).exists(), 'o arquivo do bloco é apagado depois (economiza espaço no celular)')
check(not any('agendado para' in a.lower() for a in avisos), 'sem aviso de "agendado" (o aviso vem quando o post sair)')
r2 = lv.job_bloco(Ctx({'live': lid, 'n': 2}))
check(r2['resultado']['postando'] == 1 and lv.obter(lid)['postados'] == 2, 'bloco 2: mais um post (2 de 2)')
lv.salvar_config({})
r3 = lv.job_bloco(Ctx({'live': lid, 'n': 3}))
check(r3['etapa'] == 'Bloco curto' or r3['resultado']['postando'] == 0, 'bloco 3 (40 s): curto demais, sem corte')

print('4. Limite de posts e a programação diária')
lv._mudar_live(lid, lambda x: x['blocos'].append({'n': 4, 'arquivo': str(lv.PASTA / lid / 'b00004.ts'), 'estado': 'na_fila', 'ini': 540, 'cortes': [], 'msg': ''}))
subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(FONTE), '-t', '70', '-c', 'copy', str(lv.PASTA / lid / 'b00004.ts')], check=True)
r4 = lv.job_bloco(Ctx({'live': lid, 'n': 4}))
c4 = next(c for c in ag.estado()['cortes'] if c.get('live_bloco') == 4 and c['status'] == 'pronto')
check(r4['resultado']['postando'] == 0 and not c4.get('live_fila'), 'passou de 2 posts: o aprovado vai para o estoque normal')
check(any(x['ref'] == c4['id'] for x in a2.elegiveis('youtube')), 'e a programação diária pode usar depois')
ag._mudar(lambda e: [x.update(live_fila=True) for x in e['cortes'] if x['id'] == c4['id']])
check(not any(x['ref'] == c4['id'] for x in a2.elegiveis('youtube')), 'enquanto a live vai postar, a programação não pega o corte')

print('5. Tela e parar')
v = rota('GET', '/api/v1/live')
vl = next(x for x in v['lives'] if x['id'] == lid)
check(v['esteira'] and len(vl['cortes']) == 6 and len(vl['blocos']) == 4, 'a tela mostra blocos e cortes da live')
estado_live.update(ao_vivo=True, chamadas=0)
lv._mudar(lambda d: d['lives'].append(dict(vl, id='parar1', estado='gravando', blocos=[], cortes=None, inicio=time.time())))
check(rota('POST', '/api/v1/live/parar1/parar')['estado'] == 'terminando', 'parar: termina o bloco atual')
lv._gravar('parar1')
check(lv.obter('parar1')['estado'] == 'terminada', 'e encerra a gravação')
check(rota('POST', '/api/v1/live/parar1/parar')['estado'] == 'terminada', 'parar de novo não faz nada')

print(f'\n{ok} ok, {falhas} falha(s)')
sys.exit(1 if falhas else 0)
