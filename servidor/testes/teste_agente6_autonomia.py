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

print(f'\n{ok_n} ok, {falhas} falha(s)   (pasta {TMP})')
sys.exit(1 if falhas else 0)
