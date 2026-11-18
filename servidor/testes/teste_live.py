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
    no_ar = estado_live['ao_vivo'] and estado_live['chamadas'] <= 4      # comecar + 1ª gravação; a abertura seguinte: a live acabou
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
check(chamadas[0]['quantos'] == 2 and chamadas[0]['ajustes'] == {'nota_min': 60, 'sem_fala': True} and chamadas[0]['v']['id'] == 'LIVE1234567-live1',
      'o Agente 1 corta o bloco já gravado, com a nota da live (60) e aceitando momento sem fala')
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
check(v['esteira'] and len(vl['cortes']) == 8 and len(vl['blocos']) == 4, 'a tela mostra blocos e cortes da live')
estado_live.update(ao_vivo=True, chamadas=0)
lv._mudar(lambda d: d['lives'].append(dict(vl, id='parar1', estado='gravando', blocos=[], cortes=None, inicio=time.time())))
check(rota('POST', '/api/v1/live/parar1/parar')['estado'] == 'terminando', 'parar: termina o bloco atual')
lv._gravar('parar1')
check(lv.obter('parar1')['estado'] == 'terminada', 'e encerra a gravação')
check(rota('POST', '/api/v1/live/parar1/parar')['estado'] == 'terminada', 'parar de novo não faz nada')

print('6. A Live vem primeiro')
db.executar("UPDATE jobs SET status='concluido' WHERE tipo='live.bloco'")
check(not lv.pendente(), 'sem bloco na fila: o Agente 1 segue normal')
lv._registrar_bloco(lid, lv.PASTA / lid / 'b00009.ts')
check(lv.pendente(), 'bloco na fila: a Live tem trabalho esperando')
chamou = []
ag._em_fundo = lambda nome, f, *a: chamou.append(nome)
ag.salvar_config({'cortes': {'ligado': True}})
ag.passo()
check(not chamou, 'com bloco da Live esperando, o Agente 1 automático não começa outra rodada')
rodou = []
ag.trabalhar_cortes = lambda **k: rodou.append(1) or ''
ag.rodada_estoque(3, 3)
check(not rodou, 'rodada de estoque em andamento para antes do próximo vídeo')
check(db.um("SELECT prioridade FROM jobs WHERE tipo='live.bloco' LIMIT 1")['prioridade'] == 100, 'bloco da Live entra na fila com prioridade alta')
check('ocupando' in lv.ver(), 'a tela diz o que está ocupando o celular')

print('7. Live que para de mandar vídeo')
import socket  # noqa: E402
import threading  # noqa: E402
srv = socket.socket(); srv.bind(('127.0.0.1', 0)); srv.listen(5)
presos = []
threading.Thread(target=lambda: [presos.append(srv.accept()) for _ in range(5)], daemon=True).start()     # aceita e nunca responde
lv.SEM_DADOS = 4
lv.PEGAR = lambda link: {'url': f'http://127.0.0.1:{srv.getsockname()[1]}/v.ts', 'titulo': 'Muda', 'id': 'MUDA', 'canal': '', 'canal_nome': '', 'ao_vivo': True}
db.executar("UPDATE jobs SET status='concluido' WHERE tipo='live.bloco'")
lv._mudar(lambda d: [x.update(estado='terminada') for x in d['lives']])
m = lv.comecar({'link': 'https://youtube.com/live/muda', 'origem': 'meu', 'redes': ['youtube']})
t0 = time.time()
while lv.obter(m['id'])['estado'] == 'gravando' and time.time() - t0 < 90:
    time.sleep(1)
mm = lv.obter(m['id'])
check(mm['estado'] in ('erro', 'terminada') and 'falhou 3 vezes' in (mm.get('motivo_fim') or ''), 'sem vídeo chegando: tenta 3 vezes e avisa, em vez de ficar "gravando" para sempre')
check(any('parou de mandar vídeo' in x['texto'] for x in mm['log']), 'o motivo aparece no histórico da live')

print('8. Gameplay sem fala e bloco com o relógio da transmissão')
G = TMP / 'gameplay.mp4'
# 3 min: fundo baixo, 3 explosões de som (40 s, 95 s, 150 s) e troca de cena aos 95 s
som = "aevalsrc='0.02*sin(2*PI*220*t)+if(between(mod(t\\,1000)\\,40\\,41.5)+between(t\\,95\\,97)+between(t\\,150\\,151)\\,0.9*sin(2*PI*90*t)\\,0)':s=16000:d=180"
subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:d=95:r=10', '-f', 'lavfi', '-i', 'color=c=yellow:s=320x180:d=85:r=10',
                '-f', 'lavfi', '-i', som, '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]', '-map', '[v]', '-map', '2:a', '-c:v', 'libx264', '-preset', 'ultrafast',
                '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(G)], check=True)
ag.gemini = lambda partes, **k: {'titulo': 'Explosão no meio da missão', 'gancho': 'OLHA ISSO', 'hashtags': ['#gta6', 'gameplay'], 'descricao': 'Um carro pegando fogo.'}
co = dict(ag.config()['cortes'], nota_min=60)
pasta8 = TMP / 'p8'
pasta8.mkdir()
esc = ag.escolher_sem_fala(G, 180.0, [], 3, co, 'GTA 6 LIVE', pasta8)
check(len(esc) >= 2, f'sem fala: achou {len(esc)} momento(s) pelos picos de som e troca de cena')
check(all(co['dur_min'] - 1 <= c['fim'] - c['ini'] <= co['dur_max'] + 0.5 for c in esc), 'cada momento vira um corte de 60 a 65 s')
check(any(c['ini'] < 95 < c['fim'] for c in esc), 'o momento com explosão e troca de cena (95 s) está entre os escolhidos')
check(all(c['sem_legenda'] and c['titulo'] == 'Explosão no meio da missão' and c['hashtags'] == ['#gta6', '#gameplay'] for c in esc),
      'título, gancho e hashtags da IA olhando o quadro; sem legenda (não há fala)')
check(all(min(a['fim'], b['fim']) - max(a['ini'], b['ini']) <= 0.3 * 60 for i, a in enumerate(esc) for b in esc[i + 1:]), 'os cortes não se repetem')
TS = TMP / 'relogio.ts'
subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(G), '-t', '70', '-c', 'copy', '-output_ts_offset', '36000', '-f', 'mpegts', str(TS)], check=True)
mp4 = lv._remux(TS)
check(mp4.suffix == '.mp4' and abs(ag.duracao(mp4) - 70) < 3, f'bloco com o relógio da transmissão vira MP4 com a duração certa ({ag.duracao(mp4):.0f} s)')
check(lv.config()['cortes_por_bloco'] == 3 and lv.config()['nota_min'] == 60, 'padrão novo: até 3 cortes por bloco, nota 60')
lv._mudar(lambda d: d.update(config={'cortes_por_bloco': 1, 'nota_min': 70}))
check(lv.config()['cortes_por_bloco'] == 3 and lv.config()['nota_min'] == 60, 'configuração antiga (1 corte, nota 70) é atualizada')

print('9. Memória do celular')
velha = lv.PASTA / 'velha1'
velha.mkdir(parents=True, exist_ok=True)
(velha / 'b00001.ts').write_bytes(b'x' * 5000)
lv._mudar(lambda d: d['lives'].append({'id': 'velha1', 'estado': 'terminada', 'blocos': [{'n': 1, 'arquivo': str(velha / 'b00001.ts'), 'estado': 'feito'}],
                                       'inicio': 0, 'cfg': lv.config(), 'log': []}))
fila1 = lv.PASTA / 'fila1'
fila1.mkdir(parents=True, exist_ok=True)
(fila1 / 'b00002.ts').write_bytes(b'x' * 5000)
lv._mudar(lambda d: d['lives'].append({'id': 'fila1', 'estado': 'terminada', 'blocos': [{'n': 2, 'arquivo': str(fila1 / 'b00002.ts'), 'estado': 'na_fila'}],
                                       'inicio': 0, 'cfg': lv.config(), 'log': []}))
liberou = lv.limpar_disco()
check(liberou >= 5000 and not velha.exists(), 'bloco já feito de live encerrada é apagado (libera memória)')
check((fila1 / 'b00002.ts').exists(), 'bloco ainda na fila NÃO é apagado')
lv._livre = lambda: 100 * 2**20
lv.ESPERA_ESPACO = 0.2
estado_live.update(ao_vivo=True, chamadas=0)
lv.PEGAR = pegar
lv._mudar(lambda d: [x.update(estado='terminada') for x in d['lives']])
cheio = lv.comecar({'link': 'https://youtube.com/live/cheio', 'origem': 'meu', 'redes': ['youtube']})
time.sleep(1.5)
ch = lv.obter(cheio['id'])
check(ch.get('sem_espaco') and not ch['blocos'] and any('Pouco espaço' in x['texto'] for x in ch['log']), 'pouco espaço: a gravação espera e avisa, sem encher o celular')
lv.parar(cheio['id'])

print(f'\n{ok} ok, {falhas} falha(s)')
sys.exit(1 if falhas else 0)
