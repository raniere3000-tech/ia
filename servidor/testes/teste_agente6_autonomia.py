"""Agente 6 autônomo (24/11/2026): configuração aprovada, seleção automática, recuperação, portão do Agente 2 e envio da capa.

FFmpeg e Pillow de verdade; YouTube falso (sem internet, nenhuma publicação real).

Rodar: cd servidor && PYTHONPATH=. python3 testes/teste_agente6_autonomia.py
"""
import hashlib
import json
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-a6auto-'))
os.environ.update(DADOS=str(TMP / 'dados'), BANCO_ARQ=str(TMP / 'dados' / 'studio.sqlite'), CHAVE_MESTRA_ARQ=str(TMP / 'chave'),
                  TOKEN='senha-de-teste-123', FILA_INTERVALO='0.3', ESPERA_INICIAL_AGENTE='99999', BACKUP_DIARIO='0',
                  INTERVALO_AGENDA='600', INTERVALO_AGENDA2='600', CENTRAL_SEM_ACORDAR='1', AGENTE6_SEM_VIGIA='1', COORDENADOR_SEM_VIGIA='1')
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


CAPAS_YT = []
YT_STATUS = [200]


class YT(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        corpo = self.rfile.read(n)
        if '/thumbnails/set' in self.path:
            CAPAS_YT.append((self.path, hashlib.sha256(corpo).hexdigest()))
            st = YT_STATUS[0]
            out = {'items': [{}]} if st < 300 else {'error': {'message': 'Backend Error'}}
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
import postagem as pg  # noqa: E402
import agente as ag  # noqa: E402
import thumbnails as th  # noqa: E402

S.ligar_servicos()


def esperar(tid, estados=('aguardando_escolha', 'pronto', 'revisao_manual', 'falhou', 'cancelado'), limite=240):
    fim = time.time() + limite
    while time.time() < fim:
        j = th.obter(tid)
        if j['estado'] in estados:
            return j
        time.sleep(0.4)
    return th.obter(tid)


def esperar_fila(limite=240):
    fim = time.time() + limite
    while time.time() < fim:
        if not db.um("SELECT 1 FROM jobs WHERE tipo='agente6.thumbnail' AND status IN ('na_fila','rodando','agendado','aguardando_tentativa')"):
            return True
        time.sleep(0.4)
    return False


def video(nome, w=720, h=1280, dur=6, cor='testsrc2'):
    pg.VIDEOS.mkdir(parents=True, exist_ok=True)
    arq = pg.VIDEOS / f'{nome}.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'{cor}=s={w}x{h}:r=25:d={dur}', '-f', 'lavfi', '-i', f'sine=d={dur}',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(arq)], check=True)
    return arq


def corte(cid, nome, titulo, status='pronto'):
    ag._mudar(lambda e: e['cortes'].append({'id': cid, 'video': nome, 'titulo': titulo, 'gancho': titulo + ' e ninguém esperava o final!',
                                             'hashtags': ['#teste'], 'status': status, 'criado': time.time()}))


# ---------------------------------------------------------------- TH.02
print('TH.02 Configuração aprovada e seleção automática')
c = th.config()
confere(c['modo'] == 'automatico', 'modo padrão: automático')
confere(c['variantes_padrao'] == 3 and c['nota_min'] == 70 and c['max_correcoes'] == 5, '3 capas, nota mínima 70, até 5 correções')
confere(c['exigir_capa'] and c['recuperacao_automatica'] and c['criar_sozinho'], 'capa obrigatória, recuperação e criação sozinha ligadas')
# servidor antigo com "supervisionado" salvo antes da mudança: a migração única passa para automático uma vez só
db.executar("DELETE FROM kv WHERE chave='agente6.autonomia_v1'")
db.kv_gravar('agente6.config', {**th.CONFIG_PADRAO, 'modo': 'supervisionado', 'exigir_capa': False})
confere(th.config()['modo'] == 'automatico' and th.config()['exigir_capa'], 'migração única: configuração antiga vira a aprovada')
th.salvar_config({'modo': 'supervisionado'})
confere(th.config()['modo'] == 'supervisionado', 'depois da migração, a sua escolha na tela vale (não volta sozinho)')
th.salvar_config({'modo': 'automatico'})

video('v1')
corte('k1', 'v1', 'Virada incrível no fim')
j = th.criar({'origem': 'corte', 'referencia': 'k1', 'variantes': 3}, 'teste')
j = esperar(j['id'])
aprov = [v for v in j['variantes'] if v['estado'] == 'aprovada']
confere(j['estado'] == 'pronto' and j['selecao'] and j['selecao']['escolha'] == 'automatica', f'automático: escolheu sozinho ({j["estado"]})')
if aprov:
    melhor = max(aprov, key=lambda v: (v['nota'], -v['numero']))
    confere(j['selecao']['variante'] == melhor['id'], 'escolheu a aprovada de maior nota')
# refazer: sem escolha ativa, o automático escolhe de novo
s0 = th.selecao_ativa(j['id'])
th._revogar(s0['id'], 'teste: escolha caiu')
th._estado(j['id'], 'aguardando_escolha', '')
r = th.refazer(j['id'], {'numero': 1}, 'teste')
j = esperar(r['id'], ('pronto', 'revisao_manual', 'falhou'))
confere(j['estado'] == 'pronto' and th.selecao_ativa(j['id']) is not None, 'depois de refazer, o automático escolhe sozinho')
# escolha sua não é trocada pelo automático
outra = next((v for v in j['variantes'] if v['estado'] == 'aprovada' and v['id'] != j['selecao']['variante']), None)
if outra:
    th.selecionar(j['id'], {'variante_id': outra['id']}, 'voce')
    confere(th.selecionar_melhor(j['id']) is None and th.selecao_ativa(j['id'])['variante'] == outra['id'], 'a escolha feita por você não é trocada')

# ---------------------------------------------------------------- TH.03
print('TH.03 Correção e recuperação')
# vídeo mudou: a escolha cai e a varredura pede capa da versão nova sozinha
sha_antigo = j['video_sha']
video('v1', cor='smptebars')
d = th.diagnosticar({'origem': 'corte', 'referencia': 'k1'})
confere(d['acao'] == 'criar' and d.get('recuperacao'), f'vídeo mudou: diagnóstico pede capa nova ({d["acao"]})')
r = th.recuperar()
confere(any(x['referencia'] == 'k1' for x in r['criados']), 'recuperação criou o pedido da versão nova')
esperar_fila()
jn = th._ultimo_job('corte', 'k1')
confere(jn['video_sha'] != sha_antigo and jn['estado'] == 'pronto', f'versão nova com capa escolhida sozinha ({jn["estado"]})')
confere(th.capa_para_video(pg.VIDEOS / 'v1.mp4') is not None, 'o Agente 2 acha a capa da versão nova')
confere(th.recuperar()['criados'] == [], 'passada seguinte não cria nada de novo (idempotente)')

# pedido falhou: refaz com outro método, até o limite; depois vira exceção para você
video('v2')
corte('k2', 'v2', 'Outro corte')
jf = th.criar({'origem': 'corte', 'referencia': 'k2', 'variantes': 3}, 'teste')
esperar(jf['id'])
th._estado(jf['id'], 'falhou', 'teste: falha simulada')
db.executar('UPDATE thumbnail_selecoes SET revogado=? WHERE job=?', time.time(), jf['id'])
d = th.diagnosticar({'origem': 'corte', 'referencia': 'k2'})
confere(d['acao'] == 'refazer_pedido', f'pedido falho: refaz ({d["acao"]})')
th.salvar_config({'max_recuperacoes': 1})
r = th.recuperar()
confere(any(x['referencia'] == 'k2' for x in r['criados']), 'recuperação refez o pedido que falhou')
esperar_fila()
j2 = th._ultimo_job('corte', 'k2')
confere(j2['por'] == 'agente6-recuperacao' and j2['estado'] == 'pronto', f'pedido de recuperação terminou com capa ({j2["estado"]})')
th._estado(j2['id'], 'falhou', 'teste: falhou de novo')
db.executar('UPDATE thumbnail_selecoes SET revogado=? WHERE job=?', time.time(), j2['id'])
d = th.diagnosticar({'origem': 'corte', 'referencia': 'k2'})
confere(d['acao'] == 'excecao', f'passou do limite de recuperações: exceção para você, sem laço ({d["acao"]})')
th.salvar_config({'max_recuperacoes': 3})
# cancelado por você: respeita
th._estado(j2['id'], 'cancelado', 'Cancelado por você.')
confere(th.diagnosticar({'origem': 'corte', 'referencia': 'k2'})['acao'] == 'nada', 'pedido cancelado por você não é refeito sozinho')
# supervisionado: capa aprovada sem escolha vira exceção (não escolhe sozinho)
video('v3')
corte('k3', 'v3', 'Terceiro corte')
th.salvar_config({'modo': 'supervisionado'})
j3 = esperar(th.criar({'origem': 'corte', 'referencia': 'k3', 'variantes': 3}, 'teste')['id'])
confere(j3['estado'] == 'aguardando_escolha', 'supervisionado: espera a sua escolha')
d = th.diagnosticar({'origem': 'corte', 'referencia': 'k3'})
confere(d['acao'] == 'excecao', 'supervisionado: aparece como pendência sua')
th.salvar_config({'modo': 'automatico'})
r = th.recuperar()
confere(any(x['referencia'] == 'k3' for x in r['selecionados']) and th.selecao_ativa(j3['id']), 'voltando ao automático, a recuperação escolhe a aprovada')

# ---------------------------------------------------------------- TH.04
print('TH.04 Coordenador, esteira e capa embutida')
import coordenador as co  # noqa: E402
jn = th._ultimo_job('corte', 'k1')
r = th.criar({'origem': 'corte', 'referencia': 'k1', 'variantes': 2, 'chave_idempotencia': 'coord:outra:0', 'reaproveitar': True}, 'agente7')
confere(r['id'] == jn['id'] and r.get('reaproveitado'), 'Coordenador e esteira reaproveitam o pedido vivo do mesmo vídeo (sem duplicar)')
n_antes = db.um('SELECT COUNT(*) n FROM thumbnail_jobs')['n']
th.criar({'origem': 'corte', 'referencia': 'k1', 'variantes': 3, 'chave_idempotencia': 'esteira:x:y', 'reaproveitar': True}, 'agente7-esteira')
confere(db.um('SELECT COUNT(*) n FROM thumbnail_jobs')['n'] == n_antes, 'nenhum pedido novo para o mesmo vídeo')

# Coordenador no automático: só conclui com capa escolhida e válida
video('v4')
corte('k4', 'v4', 'Quarto corte')
th.salvar_config({'modo': 'supervisionado'})
j4 = esperar(th.criar({'origem': 'corte', 'referencia': 'k4', 'variantes': 3}, 'teste')['id'])
th.salvar_config({'modo': 'automatico'})
tid4 = co._nova_tarefa('ordem-teste', 'capas_k4', 'agente6', 'a6.capas', {}, [])
co._set_tarefa(tid4, estado='executando', resultado={'thumb': j4['id']})
aprovadas4 = [v for v in j4['variantes'] if v['estado'] == 'aprovada']
co._acompanhar({'id': 'ordem-teste'}, co._tarefa(tid4))
t4 = co._tarefa(tid4)
if aprovadas4:
    confere(t4['estado'] == 'concluida' and t4['resultado'].get('variante') and th.selecao_ativa(j4['id']),
            f'Coordenador (automático): escolheu e só então concluiu ({t4["estado"]})')
else:
    confere(t4['estado'] == 'aguardando_voce', 'sem aprovada: fica com você, não conclui')
# sem nenhuma aprovada: não conclui
db.executar("UPDATE thumbnail_variantes SET estado='reprovada' WHERE job=?", j4['id'])
db.executar('UPDATE thumbnail_selecoes SET revogado=? WHERE job=?', time.time(), j4['id'])
th._estado(j4['id'], 'revisao_manual', 'teste: nenhuma passou')
co._set_tarefa(tid4, estado='executando')
co._acompanhar({'id': 'ordem-teste'}, co._tarefa(tid4))
confere(co._tarefa(tid4)['estado'] == 'aguardando_voce', 'Coordenador: sem capa aprovada não conclui (fica como pendência sua)')

# capa embutida para TikTok/Instagram, presa à mesma escolha e sem novo ciclo
arq1 = pg.VIDEOS / 'v1.mp4'
cap1 = th.capa_para_video(arq1)
e = th.video_com_capa(arq1)
confere(e and e['arquivo'].exists() and e['arquivo'] != arq1, 'versão de publicação com a capa embutida criada')
if e:
    dur = lambda a: float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(a)],
                                         capture_output=True, text=True).stdout.strip() or 0)
    d0, d1 = dur(arq1), dur(e['arquivo'])
    confere(0.3 <= d1 - d0 <= 0.8 and d0 * 1000 < e['tempo_ms'] < d1 * 1000, f'quadro final curto ({d1 - d0:.2f}s) e tempo da capa dentro dele ({e["tempo_ms"]} ms)')
    # o quadro no tempo indicado é a arte da capa (não um quadro qualquer)
    from PIL import Image, ImageChops, ImageStat  # noqa: E402
    q = TMP / 'quadro.png'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{e["tempo_ms"] / 1000:.3f}', '-i', str(e['arquivo']), '-frames:v', '1', str(q)], check=True)
    a = Image.open(q).convert('RGB').resize((90, 160))
    b = Image.open(cap1['arquivo']).convert('RGB').resize((90, 160))
    dif = sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3
    confere(dif < 25, f'o quadro no tempo da capa é a arte escolhida (diferença média {dif:.1f})')
    c2 = th.capa_para_video(e['arquivo'])
    confere(c2 and c2['embutida'] and c2['selecao'] == cap1['selecao'] and c2['tempo_ms'] == e['tempo_ms'], 'o Agente 2 reconhece a versão embutida pela MESMA escolha')
    confere(th.video_com_capa(arq1)['reaproveitado'], 'pedir de novo reaproveita o arquivo (não refaz)')
    rr = th.recuperar()
    confere(not any(x['referencia'] == 'k1' for x in rr['criados']) and
            not db.um('SELECT 1 FROM thumbnail_jobs WHERE video_sha=?', e['sha']), 'a versão embutida não gera pedido de capa novo (sem ciclo)')
    esperar_fila()
    th._revogar(cap1['selecao'], 'teste')
    confere(th.capa_para_video(e['arquivo']) is None, 'escolha revogada: a versão embutida também perde a capa')
    th.recuperar()
    esperar_fila()

# ---------------------------------------------------------------- TH.05
print('TH.05 Agente 2: capa obrigatória por rede e estado da capa separado do post')
video('v5', cor='rgbtestsrc')
corte('k5', 'v5', 'Quinto corte sem capa')
p5 = pg.criar_post({'video': 'v5', 'redes': ['youtube', 'tiktok', 'instagram', 'facebook'], 'quando': pg.agora() + 3600, 'titulo': 't', 'legenda': 'x'})
p5 = next(x for x in pg.posts() if x['id'] == p5['id'])
for rede in ('youtube', 'tiktok', 'instagram', 'facebook'):
    conf = pg.conferencia(p5, rede)
    confere(any(x['item'] == 'capa' and x['bloqueia'] for x in conf), f'{rede} {[x["item"] for x in conf]}: sem capa aprovada para o arquivo, não sai')
th.salvar_config({'exigir_capa': False, 'exigir_capa_youtube': False})
confere(not any(x['item'] == 'capa' for x in pg.conferencia(p5, 'tiktok')), 'com "exigir capa" desligado, a capa não barra')
th.salvar_config({'exigir_capa': True, 'exigir_capa_youtube': True})
pg.cancelar_post(p5['id']) if hasattr(pg, 'cancelar_post') else None

# capa da versão antiga não vale
arq1 = pg.VIDEOS / 'v1.mp4'
jk1 = th._ultimo_job('corte', 'k1')
if not th.capa_para_video(arq1):
    th.selecionar_melhor(jk1['id'])
confere(th.capa_para_video(arq1) is not None, 'v1 tem capa válida para o arquivo atual')

pg.status_contas = lambda: {k: {'conectado': True, 'erro': '', 'paginas': [], 'pagina': ''} for k in set(pg.PROV.values())}
pg._token_google = lambda: 'tok'
pg._token_tiktok = lambda: {'access': 'tok'}
os.environ['TIKTOK_DIRECT_POST_APROVADO'] = '1'
ENVIOS = []
TT = {}
http_real = pg.http


def http_falso(metodo, url, **kw):
    if 'uploadType=resumable' in url:
        return 200, {'Location': 'http://falso/up'}, {}
    if url == 'http://falso/up':
        ENVIOS.append(('youtube', len(kw.get('dados') or b'')))
        return 200, {}, {'id': 'vidYTabc123', 'status': {'privacyStatus': 'public'}}
    if '/creator_info/' in url:
        return 200, {}, {'data': {'privacy_level_options': ['PUBLIC_TO_EVERYONE']}, 'error': {'code': 'ok'}}
    if '/video/init/' in url:
        TT['init'] = kw.get('js')
        return 200, {}, {'data': {'publish_id': 'pub1', 'upload_url': 'http://falso/tt'}, 'error': {'code': 'ok'}}
    if url == 'http://falso/tt':
        TT.setdefault('bytes', b'')
        TT['bytes'] += kw.get('dados') or b''
        return 201, {}, {}
    if '/status/fetch/' in url:
        return 200, {}, {'data': {'status': 'PUBLISH_COMPLETE'}, 'error': {'code': 'ok'}}
    return http_real(metodo, url, **kw)


pg.http = http_falso
# YouTube: a capa falha (erro do servidor do YouTube) -> o vídeo fica postado e SÓ a capa é tentada de novo depois
YT_STATUS[0] = 500
n_capas = len(CAPAS_YT)
py = pg.criar_post({'video': 'v1', 'redes': ['youtube'], 'quando': pg.agora() - 5, 'titulo': 'Virada', 'legenda': 'x', 'repetir': True})
pg._publicar_um(py['id'], 'youtube')
q = next(x for x in pg.posts() if x['id'] == py['id'])
cy = q['redes']['youtube'].get('capa') or {}
confere(q['redes']['youtube']['status'] == 'postado' and cy.get('estado') == 'falhou' and cy.get('ref_rede') == 'vidYTabc123',
        f'YouTube: vídeo postado, capa "falhou" guardada à parte com o ID do vídeo ({cy.get("estado")})')
confere(len(CAPAS_YT) == n_capas + 1 and len(ENVIOS) == 1, 'uma tentativa de capa e um envio de vídeo')
confere(db.um("SELECT estado FROM thumbnail_aplicacoes WHERE post=? AND rede='youtube'", py['id'])['estado'] == 'falhou', 'estado da capa registrado por post e rede')
confere(pg.reenviar_capas_pendentes() == [], 'antes da hora marcada, não reenvia')
YT_STATUS[0] = 200
pg._mudar(py['id'], lambda q: q['redes']['youtube']['capa'].update(proxima=pg.agora() - 1))
feitos = pg.reenviar_capas_pendentes()
q = next(x for x in pg.posts() if x['id'] == py['id'])
cy = q['redes']['youtube']['capa']
confere(feitos == [(py['id'], 'aplicada')] and cy['estado'] == 'aplicada' and cy['tentativas'] == 2, f'nova tentativa só da capa: aplicada ({feitos})')
confere(len(ENVIOS) == 1 and 'videoId=vidYTabc123' in CAPAS_YT[-1][0] and CAPAS_YT[-1][1] == th.capa_para_video(arq1)['sha'],
        'o vídeo NÃO foi enviado de novo; a capa foi para o mesmo ID, com o hash da capa escolhida')
confere(pg.reenviar_capas_pendentes() == [], 'capa aplicada não é reenviada')
YT_STATUS[0] = 403
r403 = pg.reenviar_capa(py['id'], 'youtube', 'voce', forcar=True)
confere(r403['estado'] == 'bloqueada' and not r403.get('proxima'), 'conta sem permissão (403): fica bloqueada, sem repetir sozinho')
YT_STATUS[0] = 200

# TikTok direto (app aprovado): sobe a versão com a arte no quadro final e manda o tempo dela
pt = pg.criar_post({'video': 'v1', 'redes': ['tiktok'], 'quando': pg.agora() - 5, 'titulo': 'Virada', 'legenda': 'x', 'tiktok_modo': 'direto'})
pg._publicar_um(pt['id'], 'tiktok')
q = next(x for x in pg.posts() if x['id'] == pt['id'])
ct = q['redes']['tiktok'].get('capa') or {}
emb = db.um('SELECT * FROM thumbnail_embutidos WHERE original_sha=? ORDER BY criado DESC LIMIT 1', th.capa_para_video(arq1)['original_sha'])
confere(q['redes']['tiktok']['status'] == 'postado' and ct.get('estado') == 'indicada', f'TikTok direto: postado e capa indicada ({ct.get("estado")})')
confere(TT.get('init') and TT['init']['post_info'].get('video_cover_timestamp_ms') == emb['tempo_ms'], 'TikTok recebeu o tempo do quadro com a arte')
confere(hashlib.sha256(TT.get('bytes', b'')).hexdigest() == emb['video_sha'], 'o arquivo enviado é a versão com a capa embutida (hash registrado)')
# TikTok assistido (rascunho): você escolhe a capa no app, com a instrução do quadro
os.environ['TIKTOK_DIRECT_POST_APROVADO'] = '0'
TT.clear()
pa = pg.criar_post({'video': 'v1', 'redes': ['tiktok'], 'quando': pg.agora() - 5, 'titulo': 'Virada 2', 'legenda': 'x', 'repetir': True})
pg._publicar_um(pa['id'], 'tiktok')
q = next(x for x in pg.posts() if x['id'] == pa['id'])
ca = q['redes']['tiktok'].get('capa') or {}
confere(ca.get('estado') == 'manual' and 'ÚLTIMO quadro' in ca.get('detalhe', ''), 'TikTok assistido: capa fica manual, com a instrução do quadro (sem fingir aplicada)')
pg.http = http_real

print(f'\n{ok_n} ok, {falhas} falha(s)   (pasta {TMP})')
sys.exit(1 if falhas else 0)
