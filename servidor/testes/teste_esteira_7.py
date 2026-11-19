"""Esteira obrigatória dos 7 agentes, de ponta a ponta, com FFmpeg de verdade (sem internet).

  Corte:         A1 corta -> A4 avaliação inicial -> A5 edita/exporta -> A4 arquivo final -> A6 capa -> A7 libera -> A2 agenda -> A2 publica
  Vídeo próprio: A3 cria  -> A4 avaliação inicial -> A5 (montagem do A3) -> A4 arquivo final -> A6 capa -> A7 libera -> A2 agenda -> A2 publica

O que é simulado (e só isso): a IA (Gemini) e o envio às redes (não há internet nem contas aqui). Todo o resto é o código de verdade:
FFmpeg corta/edita/exporta, o diretor mede o arquivo, o Agente 6 desenha as capas com Pillow, o Coordenador confere o pacote,
o Agente 2 passa pela conferência real antes de "enviar".

Rodar: cd servidor && python3 testes/teste_esteira_7.py
"""
import base64
import json
import math
import os
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-e7-'))
os.environ.update(DADOS=str(TMP / 'dados'), BANCO_ARQ=str(TMP / 'dados' / 'database' / 'studio.sqlite'), CHAVE_MESTRA_ARQ=str(TMP / 'chave'),
                  COORDENADOR_SEM_VIGIA='1', PERMITIR_QUALQUER_URL='1')
os.environ.pop('PIPELINE_V2', None)
os.environ.pop('ESTEIRA_COMPLETA', None)          # política padrão: esteira completa LIGADA
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ok_n = falhas = 0
RELATORIO = []


def confere(c, nome):
    global ok_n, falhas
    if c:
        ok_n += 1
        print('  ok ', nome)
    else:
        falhas += 1
        print('  FALHOU', nome)


# ---------------------------------------------------------------- IA falsa (Gemini/Pexels) para o Agente 3
ROTEIRO = {'titulo': 'Por que o céu é azul', 'legenda': 'A luz do sol explica.', 'hashtags': ['#ciencia'],
           'cenas': [{'titulo': 'A pergunta', 'texto': 'Por que o céu é azul?', 'destaque': 'Céu azul'},
                     {'titulo': 'A luz', 'texto': 'A luz do sol tem todas as cores.', 'destaque': 'Todas as cores'},
                     {'titulo': 'O ar', 'texto': 'O ar espalha mais o azul.', 'destaque': 'Espalha o azul'}]}


class IAFalsa(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, r):
        b = json.dumps(r).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith('/v1/search') or self.path.startswith('/w/api.php'):
            return self._json({})
        b = FOTO.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if 'image' in self.path:
            return self._json({'candidates': [{'content': {'parts': [{'inlineData': {'mimeType': 'image/jpeg', 'data': base64.b64encode(FOTO.read_bytes()).decode()}}]}}]})
        if 'tts' in self.path:
            pcm = b''.join(struct.pack('<h', int(8000 * math.sin(2 * math.pi * 220 * i / 24000))) for i in range(int(24000 * 1.6)))
            return self._json({'candidates': [{'content': {'parts': [{'inlineData': {'mimeType': 'audio/pcm', 'data': base64.b64encode(pcm).decode()}}]}}]})
        return self._json({'candidates': [{'content': {'parts': [{'text': json.dumps(ROTEIRO, ensure_ascii=False)}]}}], 'usageMetadata': {}})


def livre():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


TMP.mkdir(parents=True, exist_ok=True)
FOTO = TMP / 'foto.jpg'
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=900x1200', '-frames:v', '1', str(FOTO)], check=True)
porta = livre()
threading.Thread(target=ThreadingHTTPServer(('127.0.0.1', porta), IAFalsa).serve_forever, daemon=True).start()
for k in ('BASE_GEMINI', 'BASE_PEXELS', 'BASE_WIKI'):
    os.environ[k] = f'http://127.0.0.1:{porta}'

import agente as ag
import aprovacoes as apv
import banco as db
import coordenador as co
import esteira as es
import fila
import painel
import pipeline as pl
import postagem as pg
import produtor
import projetos as pj
import rotas_esteira
import texto_tela as tt
import thumbnails as th

db.migrar()
fila.registrar('agente6.thumbnail', th.job_thumbnail, 'pesado')
fila.registrar('esteira.recebido', ag.job_esteira_recebido, 'pesado')
fila.registrar('agente3.produzir', produtor.job_produzir, 'leve')
fila.registrar('editor.legenda', ag.job_mover_legenda, 'pesado')
tt.iniciar()

# IA de imagem simulada para o Coordenador: o vídeo original tem uma legenda embutida FIXA, na faixa onde a nossa legenda foi parar
# no primeiro corte. Ela continua lá nas versões novas (é do vídeo); só a nossa legenda pode mudar de lugar.
TEXTO_ORIGINAL = {}
VISTAS_IA = []


def ia_quadros(quadros, info):
    VISTAS_IA.append({'posicao': info['posicao'], 'quadros': len(quadros), 'bytes': sum(q.stat().st_size for q in quadros)})
    if not TEXTO_ORIGINAL.get('ligado'):
        return {'quadros': [{'n': i + 1, 'textos': []} for i in range(len(quadros))], 'sobreposta': False, 'explicacao': 'sem texto'}
    a, b = TEXTO_ORIGINAL.setdefault('faixa', tt.FAIXAS[info['posicao']])
    t = [{'y0': a + 0.02, 'y1': b - 0.02, 'tipo': 'legenda', 'texto': 'LEGENDA QUE JÁ VEIO NO VÍDEO'}]
    return {'quadros': [{'n': i + 1, 'textos': t} for i in range(len(quadros))], 'sobreposta': tt._cruza((a, b), tt.FAIXAS[info['posicao']]),
            'explicacao': 'o vídeo já tem legenda embutida'}


tt.IA = ia_quadros
ag.avisar = lambda *a, **k: True
pg.status_contas = lambda: {k: {'conectado': True, 'erro': '', 'paginas': [], 'pagina': ''} for k in set(pg.PROV.values())}
ENVIADOS = []
def envio_falso(r):
    def enviar(p, arq):
        ENVIADOS.append((r, p['id'], pl.sha_arquivo(arq)))
        return f'https://{r}.exemplo/{p["id"]}'
    return enviar


for rede in ('youtube', 'instagram', 'tiktok', 'facebook'):
    pg.PUBLICAR[rede] = envio_falso(rede)
th.salvar_config({'modo': 'automatico', 'variantes_padrao': 2}, 'teste')       # o Agente 6 escolhe a melhor capa aprovada


def rodar_fila(limite=80):
    """Roda de verdade os trabalhos que estiverem na fila (como os trabalhadores do servidor), um por vez."""
    n = 0
    for _ in range(limite):
        j = fila._proximo('leve') or fila._proximo('pesado')
        if not j:
            break
        fila._executar(j)
        n += 1
    return n


def registro(vid, titulo):
    """Mostra a linha do tempo de um vídeo na esteira (o que fica guardado no banco)."""
    v = es.timeline(vid)
    print(f'\n  --- Registro da esteira: {titulo} ({vid}) — estado final: {v["estado"]}, {v["progresso"]}% das etapas')
    linhas = []
    for e in v['etapas']:
        rec = {k: x for k, x in (e['recibo'] or {}).items() if k in ('nota', 'certificado', 'relatorio', 'plano_versao', 'render', 'job', 'variante', 'capa_sha',
                                                                    'aprovacao', 'posts', 'links', 'correcao', 'ini', 'fim', 'cenas', 'decisao', 'adotado', 'escolha')}
        dur = f'{e["segundos_ativos"]:.1f}s' if e['segundos_ativos'] else '—'
        txt = f'  {e["agente"]:<8} {e["nome"]:<32} {e["estado"]:<19} tempo {dur:<8} correções {e["correcoes"]}  prova {json.dumps(rec, ensure_ascii=False)[:150]}'
        print(txt)
        linhas.append({'etapa': e['nome'], 'agente': e['agente'], 'estado': e['estado'], 'segundos': e['segundos_ativos'], 'correcoes': e['correcoes'],
                       'prova': rec, 'motivo': e['motivo'], 'executor': e['executor']})
    RELATORIO.append({'video': vid, 'titulo': titulo, 'estado': v['estado'], 'etapas': linhas, 'historico': len(v['historico'])})
    return v


def etapa(vid, nome):
    return es._etapa(vid, nome)


# ---------------------------------------------------------------- 0. política padrão
print('0. Política padrão')
confere(es.completa() and es.politica()['capa_obrigatoria'] and es.politica()['liberacao_automatica'], 'esteira completa ligada por padrão, capa obrigatória')
confere(pl.ligado(), 'com a esteira completa, editor e diretor ficam sempre ligados')
confere(co.exigir_liberacao_efetiva(), 'o Agente 2 passa a exigir a liberação do Coordenador')

# ---------------------------------------------------------------- 1. corte de ponta a ponta
print('\n1. Corte de ponta a ponta (Agente 1 -> 4 -> 5 -> 4 -> 6 -> 7 -> 2)')
FONTE = TMP / 'fonte.mp4'
subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=1280x720:d=40:r=30', '-f', 'lavfi', '-i', 'sine=f=300:d=40',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(FONTE)], check=True)
FRASES = ['Hoje eu vou contar como tudo começou de verdade.', 'Ninguém acreditava que aquele plano daria certo.', 'Mas a gente insistiu todos os dias sem parar.',
          'E no fim o resultado surpreendeu todo mundo aqui.', 'Esse foi o momento que mudou a nossa história.', 'Depois disso nada mais foi igual para nós.']
eventos, t = [], 5.0
for f in FRASES:
    ps = f.split()
    eventos.append({'tStartMs': int(t * 1000), 'dDurationMs': int(len(ps) * 450), 'segs': [{'utf8': ' '.join(ps)}]})
    t += len(ps) * 0.45 + 0.9
LEG = TMP / 'fonte.json3'
LEG.write_text(json.dumps({'events': eventos}), encoding='utf-8')
_escolher = ag.escolher
_gemini = ag.gemini


def escolher_ruim(frs, titulo, n, co_):
    """IA simulada escolhe o trecho; para provar a correção A4 -> A1, o começo vem 3,5 s antes da primeira fala (gancho perdido)."""
    ag.gemini = lambda partes, **k: [{'inicio': frs[0]['ini'], 'fim': frs[min(3, len(frs) - 1)]['fim'], 'nota': 88, 'titulo': 'O plano que ninguém acreditava',
                                      'gancho': 'Ninguém acreditava', 'hashtags': ['#historia', '#superacao', '#motivacao', '#cortes'], 'motivo': 'história completa'}]
    r = _escolher(frs, titulo, n, co_)
    for c in r:
        c['ini'] = max(0.0, c['ini'] - 3.5)
    return r


ag.escolher = escolher_ruim
ag._mudar(lambda e: e['canais'].append({'id': 'canal1', 'nome': 'Canal Teste', 'url': 'https://youtube.com/@teste', 'motivo': 'autorizado', 'status': 'aprovado'}))
_cfg = ag.config()
ag.salvar_config({'postagem': dict(_cfg['postagem'], redes=['youtube', 'tiktok'])})
v = {'id': 'ytVIDEO01', 'titulo': 'Como tudo começou', 'url': 'https://www.youtube.com/watch?v=ytVIDEO01', 'canal': 'canal1', 'canal_nome': 'Canal Teste'}
ag.JOB_ATUAL = 'job-de-teste'
t0 = time.time()
try:
    criados = ag.processar_video(v, 1, baixado=(FONTE, {'duration': 40.0, 'title': v['titulo']}, LEG), ajustes={'dur_min': 8, 'dur_max': 30})
except Exception:  # noqa: BLE001
    import traceback
    traceback.print_exc()
    criados = []
ag.JOB_ATUAL = ''
ag.escolher = _escolher
ag.gemini = _gemini
print(f'     (Agente 1 + diretor + editor levaram {time.time() - t0:.0f}s)')
confere(len(criados) == 1, 'o Agente 1 criou 1 corte')
if not criados:
    print('Sem corte: não dá para seguir.')
    sys.exit(1)
c = criados[0]
VC = es.vid_de('corte', c['id'])
confere(c.get('job_a1') == 'job-de-teste', 'o corte guarda de qual trabalho do Agente 1 saiu (o Coordenador acompanha por ele)')
p0 = etapa(VC, 'producao')
confere(p0['estado'] == 'concluida' and p0['recibo'].get('corte') == c['id'] and p0['segundos_ativos'] > 0, 'A1: produção concluída com recibo (id do corte) e tempo medido')
pre = etapa(VC, 'a4_previo')
confere(pre['estado'] == 'concluida' and pre['correcoes'] >= 1, f'A4 avaliação inicial: reprovou o começo, o A1 corrigiu e passou ({pre["correcoes"]} correção)')
hist = [h for h in es.timeline(VC)['historico'] if h['etapa'] == 'a4_previo']
confere(any(h['estado'] == 'reprovada' for h in hist) and hist[-1]['estado'] == 'concluida', 'histórico guarda a reprovação e a aprovação da avaliação inicial')
rel_previo = db.todos("SELECT nota, aprovado FROM quality_reports WHERE ref=? AND modalidade='creative_preedit' ORDER BY criado", c['id'])
confere(len(rel_previo) >= 2 and not rel_previo[0]['aprovado'] and rel_previo[-1]['aprovado'], f'laudos da avaliação inicial guardados: {[r["nota"] for r in rel_previo]}')
ed5 = etapa(VC, 'a5_edicao')
confere(ed5['estado'] == 'concluida' and ed5['saida_sha'] and ed5['recibo'].get('plano_versao'), 'A5: edição concluída com SHA do arquivo exportado e versão do plano')
a4f = etapa(VC, 'a4_final')
cert = pl.certificado(pl.sha_arquivo(pg.video_path(c['video'])))
confere(a4f['estado'] == 'concluida' and cert and a4f['recibo'].get('certificado') == cert['id'], f'A4 arquivo final: aprovado com certificado preso ao arquivo (nota {cert and cert["nota"]})')
confere(etapa(VC, 'a6_capa')['estado'] == 'pendente', 'A6 liberado automaticamente (pendente) só depois do certificado')

# gate: sem A6/A7 o Publicador não agenda
try:
    pg.criar_post({'video': c['video'], 'redes': ['youtube'], 'titulo': 'x', 'legenda': 'y'})
    barrou = False
except pg.ErroRede as e:
    barrou = 'Falta na esteira' in str(e)
    print('     Publicador recusou:', str(e)[:120])
confere(barrou, 'sem capa e sem liberação, o Publicador NÃO cria o post (diz o que falta)')
confere(not ag.a7_liberou(c), 'o agendador automático também não pega o corte ainda')

# A6 -> A7 pelo condutor
es.avancar(VC)
confere(etapa(VC, 'a6_capa')['estado'] == 'na_fila', 'A6: pedido de capa criado e na fila (sem trabalho falso)')
rodar_fila()
es.avancar(VC)

# A7 confere se o vídeo já tinha legenda/texto por baixo da nossa (pedido de 19/11): aqui o vídeo original TEM legenda embutida
print('\n1b. Coordenador acha legenda do vídeo por baixo da nossa e manda de volta para o editor')
c_atual = next(x for x in ag.estado()['cortes'] if x['id'] == c['id'])
confere(c_atual.get('legendado') and ag.pode_mover_legenda(c['id']), 'corte com legenda nossa e trecho original guardado (sem a nossa legenda) para o editor')
pos0 = tt.posicao_da_altura(tt._altura(pl.ultimo_plano(c_atual['esteira'])))
sha0 = pl.sha_arquivo(pg.video_path(c['video']))
TEXTO_ORIGINAL['ligado'] = True
e7a = etapa(VC, 'a7_liberacao')
confere(e7a['estado'] != 'concluida' and 'conferindo' in (e7a['motivo'] or '').lower(), f'A7 não libera enquanto confere o texto na tela: "{(e7a["motivo"] or "")[:90]}"')
rodar_fila()                       # trabalho "coordenador.texto_tela" (quadros reais do arquivo, IA simulada)
es.avancar(VC)
chk = tt.resultado(sha0)
confere(chk and chk['estado'] == 'pronto' and chk['resultado']['sobreposta'] and VISTAS_IA and VISTAS_IA[0]['quadros'] == 5,
        f'Coordenador olhou 5 quadros reais do vídeo e achou a legenda embutida em cima da nossa (nossa: {pos0})')
nova = chk['resultado']['nova_posicao'] if chk else None
confere(nova and nova != pos0, f'escolheu um lugar livre para a nossa legenda: {nova}')
e7b, e5b = etapa(VC, 'a7_liberacao'), etapa(VC, 'a5_edicao')
confere(e7b['estado'] == 'reprovada' and e5b['estado'] == 'corrigindo', 'A7 reprovou pela legenda e o A5 ficou "corrigindo" (registro na esteira)')
jl = db.um("SELECT * FROM jobs WHERE tipo='editor.legenda' ORDER BY criado DESC LIMIT 1")
confere(jl and json.loads(jl['dados'])['posicao'] == nova, 'trabalho do editor na fila com a posição nova')
confere(not db.um("SELECT id FROM coordenador_aprovacoes WHERE referencia=? AND decisao='aprovado' AND revogado IS NULL", c['id']), 'nada liberado para postar com a legenda sobreposta')
rodar_fila()                       # editor monta de novo a partir do trecho guardado; diretor confere
sha1 = pl.sha_arquivo(pg.video_path(c['video']))
c_atual = next(x for x in ag.estado()['cortes'] if x['id'] == c['id'])
confere(sha1 != sha0 and pl.certificado(sha1), 'arquivo novo no lugar do antigo, já com o certificado do diretor')
confere((c_atual.get('legenda_movida') or {}).get('posicao') == nova, f'o corte registra que a legenda foi para {nova}')
confere(tt.posicao_da_altura(tt._altura(pl.ultimo_plano(c_atual['esteira']))) == nova, 'o plano do editor tem a legenda na posição nova')
for _ in range(8):                 # capa nova para o arquivo novo, conferência de novo, liberação
    es.avancar(VC)
    if etapa(VC, 'a7_liberacao')['estado'] == 'concluida':
        break
    rodar_fila()
chk1 = tt.resultado(sha1)
confere(chk1 and chk1['estado'] == 'pronto' and not chk1['resultado']['sobreposta'] and chk1['resultado']['tem_texto'],
        'segunda conferência: o texto do vídeo continua lá, mas a nossa legenda não fica mais em cima dele')
confere(etapa(VC, 'a6_capa')['saida_sha'] and etapa(VC, 'a6_capa')['entrada_sha'] == sha1, 'A6 refez a capa para o arquivo novo')
confere(not ag.pode_mover_legenda(c['id']), 'trecho guardado apagado depois da conferência aprovada')
e6 = etapa(VC, 'a6_capa')
confere(e6['estado'] == 'concluida' and e6['recibo'].get('capa_sha') and e6['saida_sha'], f'A6: capa feita pelo Agente 6, escolhida ({e6["recibo"].get("escolha")}) e presa ao vídeo')
e7 = etapa(VC, 'a7_liberacao')
a7 = db.um('SELECT * FROM coordenador_aprovacoes WHERE id=?', (e7['recibo'] or {}).get('aprovacao') or '')
rel7 = json.loads(a7['relatorio']) if a7 else {}
confere(e7['estado'] == 'concluida' and a7 and a7['decisao'] == 'aprovado', 'A7: pacote conferido item por item e liberado')
confere({i['item'] for i in rel7.get('itens', [])} >= {'diretor', 'avaliacao_inicial', 'capa', 'direitos', 'link_original', 'titulo', 'legenda_sobreposta'}, 'A7 conferiu diretor, avaliação inicial, capa, direitos, link original, título e legenda sobreposta')
confere(a7 and a7['thumbnail_sha256'] == e6['recibo'].get('capa_sha'), 'liberação presa ao hash do vídeo E da capa')
confere(ag.a7_liberou(next(x for x in ag.estado()['cortes'] if x['id'] == c['id'])), 'agora o agendador do Agente 2 pode pegar o corte')

# A2: agenda (pelo caminho de sempre) e publica (conferência real; só o envio à rede é simulado)
pg_cfg = ag.config()['postagem']
ag._mudar(lambda e: None)
try:
    post = ag.agendar_corte(c['id'], quem='teste')
except ag.ErroAgente as e:
    print('     agendar:', e)
    post = None
confere(post is not None, 'A2: corte agendado pelo Publicador')
es.avancar(VC)
confere(etapa(VC, 'a2_agendamento')['estado'] == 'concluida', 'A2 agendamento concluído com o id do post como prova')
pg._mudar(post['id'], lambda q: q.update(quando=pg.agora() - 1))
pg.ciclo()
for _ in range(40):
    if all(r['status'] in ('postado', 'erro', 'manual') for r in next(x for x in pg.posts() if x['id'] == post['id'])['redes'].values()):
        break
    time.sleep(0.25)
es.avancar(VC)
pub = etapa(VC, 'a2_publicacao')
if pub['estado'] != 'concluida':
    print('     envio:', json.dumps(next(x for x in pg.posts() if x['id'] == post['id'])['redes'], ensure_ascii=False)[:400])
confere(pub['estado'] == 'concluida' and pub['recibo'].get('links'), f'A2 publicação concluída com o link de cada rede: {list((pub["recibo"] or {}).get("links", {}))}')
confere(all(s == pl.sha_arquivo(pg.video_path(c['video'])) for _, _, s in ENVIADOS), 'o arquivo enviado é exatamente o aprovado pelo diretor (mesmo SHA)')
vc = registro(VC, 'Corte do Agente 1')
confere(vc['estado'] == 'publicado' and vc['progresso'] == 100, 'corte: as 8 etapas concluídas')
desc = next(x for x in pg.posts() if x['id'] == post['id'])['legenda']
confere(v['url'] in desc, 'descrição publicada com o link do vídeo original')

# ---------------------------------------------------------------- 2. vídeo próprio de ponta a ponta
print('\n2. Vídeo original do Agente 3 de ponta a ponta (A3 -> 4 -> 5 -> 4 -> 6 -> 7 -> 2)')
ag.salvar_segredos({'gemini': 'chave-falsa'})
proj = produtor.novo({'briefing': {'tema': 'Por que o céu é azul', 'cenas_qtd': 3, 'duracao_alvo': 12, 'estilo': 'quadro_branco', 'voz': 'Puck',
                                   'modo_aprovacao': 'supervisionado', 'destinos': {'redes': ['youtube'], 'quando': 'agora'}}}, 'teste')
PID = proj['id']
job = produtor.produzir(PID, dispositivo='teste')
t0 = time.time()
for _ in range(12):
    rodar_fila()
    if pj.obter(PID)['status'] in ('ready_for_review', 'failed', 'cancelled'):
        break
print(f'     (produção do Agente 3 levou {time.time() - t0:.0f}s; situação: {pj.obter(PID)["status"]})')
if pj.obter(PID)['status'] != 'ready_for_review':
    print('     job:', json.dumps(fila.obter(job['id']), ensure_ascii=False, default=str)[:600])
VR = es.vid_de('render', PID)
confere(pj.obter(PID)['status'] == 'ready_for_review', 'vídeo do Agente 3 pronto para revisão')
p3 = etapa(VR, 'producao')
confere(p3 and p3['estado'] == 'concluida' and p3['recibo'].get('cenas') == 3 and p3['recibo'].get('hash_cenas'), 'A3: produção com recibo (3 cenas e hash das cenas)')
pre3 = etapa(VR, 'a4_previo')
confere(pre3['estado'] == 'concluida' and pre3['recibo'].get('relatorio'), 'A4 avaliação inicial (cenas e roteiro) ANTES da montagem')
t_pre = max(h['t'] for h in es.timeline(VR)['historico'] if h['etapa'] == 'a4_previo' and h['estado'] == 'concluida')
t_a5 = min(h['t'] for h in es.timeline(VR)['historico'] if h['etapa'] == 'a5_edicao' and h['estado'] == 'executando')
confere(t_pre <= t_a5, 'a montagem só começou depois da avaliação inicial aprovada')
m5 = etapa(VR, 'a5_edicao')
confere(m5['estado'] == 'concluida' and m5['recibo'].get('render') and 'Agente 3' in (m5['executor'] or ''), 'A5 nos vídeos próprios: montagem registrada com o render e quem fez (o Agente 3)')
f3 = etapa(VR, 'a4_final')
confere(f3['estado'] == 'concluida' and f3['recibo'].get('certificado'), 'A4 arquivo final com certificado')
es.avancar(VR)
rodar_fila()
es.avancar(VR)
confere(etapa(VR, 'a6_capa')['estado'] == 'concluida', 'A6: capa do vídeo próprio feita e escolhida')
confere(etapa(VR, 'a7_liberacao')['estado'] == 'concluida', 'A7: pacote do vídeo próprio liberado')
r = apv._render_atual(pj.obter(PID))
res = apv.aprovar(PID, r['sha'], {'redes': ['youtube'], 'quando': 'agora'}, 'site', 'Raniere')
confere(res['ok'] and res['posts'], 'sua aprovação em Revisar cria o post (pacote já liberado pelo A7)')
for p in pg.posts():
    if p.get('projeto') == PID:
        pg._mudar(p['id'], lambda q: q.update(quando=pg.agora() - 1))
pg.ciclo()
for _ in range(40):
    ps = [p for p in pg.posts() if p.get('projeto') == PID]
    if ps and all(r['status'] in ('postado', 'erro') for p in ps for r in p['redes'].values()):
        break
    time.sleep(0.25)
es.avancar(VR)
vr = registro(VR, 'Vídeo original do Agente 3')
confere(vr['estado'] == 'publicado', 'vídeo próprio: as 8 etapas concluídas')

# ---------------------------------------------------------------- 3. arquivo mudou depois da liberação: só o necessário cai
print('\n3. Arquivo mudou depois da liberação')
c2 = dict(c)
arq = pg.video_path(c['video'])
with open(arq, 'ab') as f:
    f.write(b'\0' * 32)
db.executar("UPDATE esteira_videos SET estado='em_andamento' WHERE id=?", VC)
db.executar("UPDATE esteira_etapas SET estado='na_fila' WHERE video=? AND etapa='a2_publicacao'", VC)
es.avancar(VC)
confere(etapa(VC, 'a4_final')['estado'] != 'concluida', 'o arquivo mudou: a aprovação do diretor não vale para a versão nova')
confere(etapa(VC, 'a6_capa')['estado'] == 'aguardando_dependencia' and etapa(VC, 'a7_liberacao')['estado'] == 'aguardando_dependencia',
        'capa e liberação voltam a esperar (o histórico fica)')
confere(not co.liberado(arq)['ok'], 'a liberação antiga não serve para o arquivo novo')

# ---------------------------------------------------------------- 4. sem Pillow: A6 fica "falta um recurso", não finge
print('\n4. A6 sem Pillow')
proj2 = pj.criar({'tipo': 'agente3', 'modo': 'automatico', 'titulo': 'Sem Pillow', 'status': 'ready_for_review', 'dados': {}}, 'teste', 'site')
VX = es.garantir('render', proj2['id'], 'Sem Pillow')
for et in ('producao', 'a4_previo', 'a5_edicao'):
    es.marcar(VX, et, 'concluida', recibo={'teste': True})
es.marcar(VX, 'a4_final', 'concluida', recibo={'teste': True}, saida_sha='x')
_arq = es.arquivo_atual
es.arquivo_atual = lambda v: (FONTE, pl.sha_arquivo(FONTE), {'projeto': {'dados': {}}})
pil = th.PIL_OK
th.PIL_OK = False
db.executar("UPDATE esteira_etapas SET saida_sha=? WHERE video=? AND etapa='a4_final'", pl.sha_arquivo(FONTE), VX)
pl.emitir_certificado(proj2['id'], pl.sha_arquivo(FONTE), {'score': 80, 'blocking_findings': [], 'findings': [], 'partes': {}, 'passed': True})
es.avancar(VX)
x6 = etapa(VX, 'a6_capa')
confere(x6['estado'] == 'aguardando_recurso' and 'Pillow' in (x6['motivo'] or ''), f'sem Pillow: "{es.NOMES_ESTADO[x6["estado"]]}" com o motivo, sem concluir')
confere(etapa(VX, 'a7_liberacao')['estado'] == 'aguardando_dependencia', 'A7 não começa sem a capa')
th.PIL_OK = pil
es.arquivo_atual = _arq

# ---------------------------------------------------------------- 5. produção antiga incompleta: diagnóstico e recuperação com confirmação
print('\n5. Recuperação de produção antiga')
ANTIGO = TMP / 'antigo.mp4'
subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=720x1280:d=12:r=30', '-f', 'lavfi', '-i', 'sine=f=440:d=12',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(ANTIGO)], check=True)
import shutil

shutil.copy(ANTIGO, pg.VIDEOS / 'antigo1.mp4')
ag._mudar(lambda e: e['cortes'].append({'id': 'corteantigo', 'video': 'antigo1', 'titulo': 'Corte de antes da esteira', 'status': 'pronto', 'tipo': 'agente',
                                        'canal': 'canal1', 'origem': 'ytVIDEO01', 'origem_url': v['url'], 'criado': time.time() - 86400, 'ini': 0, 'fim': 12}))
antes = db.um('SELECT COUNT(*) n FROM esteira_videos')['n']
sim = es.simular_conciliacao()
item = next((i for i in sim['itens'] if i['ref'] == 'corteantigo'), None)
confere(item and item['falta'] == 'a4_final' and item['acao'] == 'editor_diretor', f'simulação mostra o que falta: {item and item["motivo"]}')
confere(db.um('SELECT COUNT(*) n FROM esteira_videos')['n'] == antes, 'simular não muda nada')
confere(not any(i['ref'] == c['id'] for i in sim['itens']), 'vídeo já publicado fica de fora da recuperação')
try:
    rotas_esteira.tratar('POST', '/api/v1/esteira/conciliar', {}, lambda: {'videos': ['corte:corteantigo']}, 'teste')
    recusou = False
except rotas_esteira.ErroRota:
    recusou = True
confere(recusou, 'recuperar sem confirmar é recusado')
feito = rotas_esteira.tratar('POST', '/api/v1/esteira/conciliar', {}, lambda: {'confirmar': True, 'videos': ['corte:corteantigo']}, 'teste')
confere(feito['total'] == 1 and 'editor' in feito['feitos'][0]['feito'], 'com a sua confirmação: só a etapa que falta (editor e diretor) é pedida')
rodar_fila()
es.avancar('corte:corteantigo')
ea = es.obter('corte:corteantigo')
print('     corte antigo agora:', ea['estado'], '/', ea['etapa_atual'], '/', ea['motivo'][:80])
confere(etapa('corte:corteantigo', 'a4_previo')['estado'] == 'pulada_justificada', 'avaliação inicial marcada "não se aplica" com o motivo (vídeo já editado)')
confere(etapa('corte:corteantigo', 'a4_final')['estado'] in ('concluida', 'revisao_manual', 'reprovada', 'aguardando_usuario'), 'o diretor avaliou o arquivo de verdade')

# ---------------------------------------------------------------- 6. post antigo agendado sem liberação: espera, não vira erro
print('\n6. Post antigo agendado antes da esteira completa')
shutil.copy(ANTIGO, pg.VIDEOS / 'antigo2.mp4')
os.environ['ESTEIRA_COMPLETA'] = '0'
pl.emitir_certificado('antigo2', pl.sha_arquivo(pg.video_path('antigo2')), {'score': 80, 'blocking_findings': [], 'findings': [], 'partes': {}, 'passed': True})
pa = pg.criar_post({'video': 'antigo2', 'redes': ['youtube'], 'quando': pg.agora() - 5, 'titulo': 'Antigo', 'legenda': 'x'})
os.environ.pop('ESTEIRA_COMPLETA')
n_env = len(ENVIADOS)
pg.ciclo()
time.sleep(1)
ra = next(x for x in pg.posts() if x['id'] == pa['id'])['redes']['youtube']
confere(ra['status'] == 'agendado' and 'esteira' in ra['erro'].lower() and len(ENVIADOS) == n_env, f'não foi enviado e espera a esteira (sem virar erro): {ra["erro"][:90]}')

# ---------------------------------------------------------------- 7. Coordenador: a1.rodar não conclui sem prova
print('\n7. Coordenador não conclui tarefa só porque pediu')
o = co.criar_ordem('fazer_cortes', {'modo': 'cortar'}, 'corta', 'teste')
co.confirmar(o['id'], {'versao_plano': o['versao_plano']}, 'teste')
ENF = ag.ENFILEIRAR
ag.ENFILEIRAR = None
ag.OCUPADO.acquire()
co.avancar(o['id'])
ag.OCUPADO.release()
ag.ENFILEIRAR = ENF
t1 = next(t for t in co.obter_ordem(o['id'])['tarefas'] if t['acao'] == 'a1.rodar')
confere(t1['estado'] != 'concluida', f'sem trabalho na fila para acompanhar, a tarefa não é dada como concluída ({t1["estado"]})')

# ---------------------------------------------------------------- 8. Início com os estados reais
print('\n8. Painel Início')
r = painel.resumo('hoje')
estados = {a['id']: a.get('estado_real') for a in r['agentes']}
confere(len(estados) == 7 and all(x for x in estados.values()), f'os 7 agentes com estado real: {estados}')
a4 = next(a for a in r['agentes'] if a['id'] == 'agente4')
confere((a4['esteira_periodo'] or {}).get('concluidas', 0) >= 2, f'Diretor (A4) com etapas concluídas COM PROVA no período: {a4["esteira_periodo"]}')
confere(r['esteira7'] and r['esteira7']['por_estado'].get('publicado', 0) >= 1, f'resumo da esteira no Início: {r["esteira7"]["por_estado"]}')
d = rotas_esteira.tratar('GET', '/api/v1/esteira/diagnostico', {}, dict, 'teste')
confere(d['politica']['completa'] and d['coordenador']['liberacao_efetiva'], 'diagnóstico mostra a política e que a liberação é exigida')
tl = rotas_esteira.tratar('GET', f'/api/v1/esteira/execucoes/corte-{c["id"]}/timeline', {}, dict, 'teste')
confere(len(tl['etapas']) == 8 and tl['historico'], 'API da linha do tempo do vídeo responde com as 8 etapas e o histórico')

(TMP.parent / 'esteira7-relatorio.json').write_text(json.dumps(RELATORIO, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
print(f'\n{ok_n} ok, {falhas} falhas   (registros salvos em {TMP.parent / "esteira7-relatorio.json"})')
sys.exit(1 if falhas else 0)
