"""Teste de aceite do pacote v2 (sem internet; Gemini falso, FFmpeg e servidor HTTP de verdade).

O que precisa acontecer, do jeito que a pessoa faz pelo site:
  1. descreve a linha em texto livre -> a IA propõe a configuração (nada é gravado) -> a pessoa salva;
  2. os horários da linha viram programação diária de verdade (2 redes);
  3. planeja e aceita 6 pautas diferentes -> produz o lote -> a fila RENDERIZA 6 vídeos (arquivos MP4 reais);
  4. o diretor dá nota e certificado para o arquivo exato de cada vídeo (com correções, se houver);
  5. publicação automática da linha aprova só vídeo certificado;
  6. o Agente 2 coloca os 6 vídeos nos horários, um por horário, sem repetir vídeo na mesma rede;
  7. nada é publicado: os posts ficam agendados e cada um leva o SHA certificado.

Rodar: cd servidor && python3 testes/teste_aceite_linha6.py   (deixa o servidor no ar com AINDA_NO_AR=1 para tirar fotos da tela)
"""
import base64
import json
import math
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import re
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-aceite-'))
os.environ.update(DADOS=str(TMP / 'dados'), BANCO_ARQ=str(TMP / 'dados' / 'studio.sqlite'), CHAVE_MESTRA_ARQ=str(TMP / 'chave'),
                  TOKEN='senha-de-teste-123', FILA_INTERVALO='0.3', ESPERA_INICIAL_AGENTE='99999', BACKUP_DIARIO='0',
                  INTERVALO_AGENDA='2', INTERVALO_AGENDA2='600', CENTRAL_SEM_ACORDAR='1', INTERVALO_CENTRAL_INICIO='1', INTERVALO_CENTRAL='2', PIPELINE_V2='1')
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


PAUTAS = ['Por que o mar é salgado', 'Como o polvo muda de cor', 'Por que a Lua tem fases', 'Como as abelhas fazem mel',
          'Por que o gelo boia na água', 'Como o raio se forma']
CONFIG_IA = {'config': {'titulo': 'Curiosidades da Natureza', 'tema': 'curiosidades da natureza', 'tom': 'leve e curioso', 'publico': 'geral',
                        'quantidade_lote': 6, 'duracao_seg': 15, 'estilo': 'quadro_branco', 'voz': 'Puck',
                        'agenda': {'redes': ['tiktok', 'youtube'], 'horarios': ['08:00', '12:00', '19:00'], 'dias': [0, 1, 2, 3, 4, 5, 6]}},
             'duvidas': ['Você não disse a voz; deixei Puck.']}
PEDIDOS = []


def roteiro_para(txt: str) -> dict:
    tema = next((p for p in PAUTAS if p in txt), 'Curiosidade')
    return {'titulo': tema, 'legenda': f'{tema}: a resposta curta.', 'hashtags': ['#natureza'],
            'cenas': [{'titulo': 'A pergunta', 'texto': f'{tema}?', 'destaque': tema[:30]},
                      {'titulo': 'A explicação', 'texto': f'A resposta de {tema.lower()} está na natureza.', 'destaque': 'A resposta'},
                      {'titulo': 'O fim', 'texto': 'Agora você sabe.', 'destaque': 'Agora você sabe'}]}


class Gemini(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, tipo='application/json'):
        b = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(200)
        self.send_header('Content-Type', tipo)
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith('/w/api.php'):
            return self._json({})
        if self.path.startswith('/v1/search'):
            return self._json({'photos': [{'id': 900 + i, 'photographer': f'Fulano {i}', 'url': f'https://www.pexels.com/photo/{900 + i}/',
                                           'src': {'large2x': f'http://127.0.0.1:{pg_port}/foto{i}.jpg'}} for i in range(1, 7)]})
        return self._json(FOTO.read_bytes(), 'image/jpeg')

    def do_POST(self):
        corpo = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        PEDIDOS.append(self.path)
        txt = json.dumps(corpo, ensure_ascii=False)
        if 'image' in self.path:
            return self._json({'candidates': [{'content': {'parts': [{'inlineData': {'mimeType': 'image/jpeg', 'data': base64.b64encode(FOTO.read_bytes()).decode()}}]}}]})
        if 'tts' in self.path:
            pcm = b''.join(struct.pack('<h', int(8000 * math.sin(2 * math.pi * (200 + len(txt) % 80) * i / 24000))) for i in range(int(24000 * 2.2)))
            return self._json({'candidates': [{'content': {'parts': [{'inlineData': {'mimeType': 'audio/pcm', 'data': base64.b64encode(pcm).decode()}}]}}]})
        if 'configuração de uma LINHA' in txt:
            r = CONFIG_IA
        elif 'Você planeja pautas' in txt:
            r = {'pautas': [{'titulo': t, 'subtema': 'natureza', 'resumo': f'Explica {t.lower()}. Em linguagem simples.', 'gancho': f'{t}?',
                             'classificacao': 'entretenimento', 'afirmacoes': [], 'fontes': []} for t in PAUTAS]}
        elif 'AVALIADOR VISUAL' in txt or 'REVISOR DE ROTEIRO' in txt or 'VERIFICADOR DE CONTINUIDADE' in txt:
            r = {'pontos': [], 'contradicoes': []}
        else:
            r = roteiro_para(txt)
        return self._json({'candidates': [{'content': {'parts': [{'text': json.dumps(r, ensure_ascii=False)}]}}], 'usageMetadata': {}})


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
os.environ.update(BASE_GEMINI=f'http://127.0.0.1:{pg_port}', BASE_PEXELS=f'http://127.0.0.1:{pg_port}', BASE_WIKI=f'http://127.0.0.1:{pg_port}',
                  PERMITIR_QUALQUER_URL='1')

import servidor as S  # noqa: E402
import banco as db  # noqa: E402
import pipeline as pl  # noqa: E402
import postagem as pg  # noqa: E402

S.ligar_servicos()
porta = int(os.getenv('PORTA_TESTE') or livre())
threading.Thread(target=ThreadingHTTPServer(('127.0.0.1', porta), S.Handler).serve_forever, daemon=True).start()
BASE = f'http://127.0.0.1:{porta}'
SES = {}


def api(metodo, caminho, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(BASE + caminho, data=dados, method=metodo, headers={'Content-Type': 'application/json', **SES})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        b = e.read()
        try:
            return e.code, json.loads(b)
        except ValueError:
            return e.code, b


st, r = api('POST', '/api/v1/sessao/login', {'senha': 'senha-de-teste-123', 'nome': 'Celular'})
SES['X-Sessao'] = r['sessao']
api('POST', '/agente/chaves', {'gemini': 'chave-falsa'})
confere(pl.ligado(), 'esteira dos 5 agentes ligada (diretor obrigatório)')

print('1. Linha a partir de uma descrição')
desc = ('Quero 6 vídeos curtos de curiosidades da natureza, tom leve, estilo quadro branco, para TikTok e YouTube às 8h, 12h e 19h, '
        'todos os dias. Pode publicar sozinho quando o diretor aprovar.')
n_linhas = db.um('SELECT COUNT(*) n FROM linhas_conteudo')['n']
st, sug = api('POST', '/api/v1/linhas-conteudo/sugerir', {'descricao': desc})
confere(st == 200 and sug['proposta']['quantidade_lote'] == 6 and sug['proposta']['agenda']['horarios'] == ['08:00', '12:00', '19:00'],
        f'IA propôs a configuração (6 vídeos, 3 horários): {st}')
confere(db.um('SELECT COUNT(*) n FROM linhas_conteudo')['n'] == n_linhas, 'proposta não grava nada')
confere(any(m['campo'] == 'agenda' for m in sug['mudancas']) and sug['avisos'], 'tela mostra o que mudou e as dúvidas da IA')
proposta = {**sug['proposta'], 'publicacao': 'automatica', 'aprovar_roteiro': 'automatico'}       # a pessoa confere e escolhe na tela
st, linha = api('POST', '/api/v1/linhas-conteudo', proposta)
confere(st == 200, f'linha salva ({st} {str(linha)[:200] if st != 200 else ""})')
LID = linha['id']
confere({a['rede'] for a in linha['agenda_aplicada'] if a['ok']} == {'tiktok', 'youtube'}, 'horários viraram programação diária nas 2 redes')
st, ags = api('GET', '/api/v1/agent2/schedules')
ags = ags['agendas']
confere(len(ags) == 2 and all(set(h for hs in a['weekly_rules'].values() for h in hs) == {'08:00', '12:00', '19:00'} and len(a['weekly_rules']) == 7 for a in ags),
        f'programação fixa 08:00, 12:00 e 19:00 nos 7 dias ({[a.get("weekly_rules") for a in ags][:1]})')

print('2. Pautas e lote de 6')
st, pl_ = api('POST', f'/api/v1/linhas-conteudo/{LID}/planejar-pautas', {'quantidade': 6})
confere(st == 200 and len(pl_['pautas']) == 6, f'6 pautas propostas ({st})')
for p in pl_['pautas']:
    if p['status'] != 'aceita':
        api('PATCH', f'/api/v1/linhas-conteudo/pautas/{p["id"]}', {'acao': 'aceitar'})
st, pl2 = api('POST', f'/api/v1/linhas-conteudo/{LID}/planejar-pautas', {'quantidade': 6})
confere(st == 200 and not pl2['pautas'] and len(pl2['repetidas']) == 6, 'planejar de novo: as 6 são barradas como repetidas')
st, lote = api('POST', f'/api/v1/linhas-conteudo/{LID}/iniciar-lote', {'quantidade': 6})
confere(st == 200 and len(lote['episodios']) == 6, f'lote começou com 6 episódios ({st})')
st, lote2 = api('POST', f'/api/v1/linhas-conteudo/{LID}/iniciar-lote', {'quantidade': 6})
confere(st in (409, 429) and db.um('SELECT COUNT(*) n FROM conteudo_episodios WHERE linha=?', LID)['n'] == 6,
        f'pedir o lote de novo é recusado e não duplica ({st}: {str(lote2)[:90]})')
PIDS = [e['projeto'] for e in lote['episodios']]

print('3. Produção, diretor e correções (aguarde: 6 renders de verdade)')
t0 = time.time()
FINAIS = ('approved', 'queued_to_publish', 'posted', 'failed', 'ready_for_review')
while time.time() - t0 < 1500:
    sts = [db.um('SELECT status FROM projetos WHERE id=?', p)['status'] for p in PIDS]
    if all(s in ('approved', 'queued_to_publish', 'failed') for s in sts):
        break
    time.sleep(2)
print(f'     (levou {time.time() - t0:.0f}s) estados: {sts}')
confere(all(s in ('approved', 'queued_to_publish') for s in sts), 'os 6 vídeos terminaram aprovados (certificado + publicação automática)')
shas = {}
for p in PIDS:
    rd = db.um('SELECT * FROM renders WHERE projeto=? ORDER BY versao DESC LIMIT 1', p)
    arq = Path(rd['arquivo']) if rd else None
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(arq)], capture_output=True,
                               text=True).stdout.strip() or 0) if arq and arq.exists() else 0
    shas[p] = rd['sha256'] if rd else ''
    confere(arq and arq.exists() and dur > 3 and pl.sha_arquivo(arq) == rd['sha256'], f'{p}: MP4 real de {dur:.1f}s, SHA confere com o arquivo')
    confere(bool(pl.certificado(rd['sha256'])), f'{p}: certificado do diretor para este arquivo')
    ap = db.um("SELECT * FROM aprovacoes WHERE projeto=? AND render_sha=? AND decisao='aprovado'", p, rd['sha256'])
    confere(ap is not None, f'{p}: aprovação registrada para o mesmo SHA')
confere(len(set(shas.values())) == 6, '6 arquivos diferentes (nenhum vídeo repetido)')
st, ln = api('GET', f'/api/v1/linhas-conteudo/{LID}')
confere(st == 200 and all(e['nota'] is not None for e in ln['episodios']), f'tela da linha mostra a nota de cada episódio: {[e["nota"] for e in ln["episodios"]]}')

print('4. Calendário')
t0 = time.time()
while time.time() - t0 < 60:
    sl = db.todos("SELECT * FROM posting_slots WHERE ref LIKE 'p:%' AND estado IN ('agendado','reservado')")
    if len(sl) >= 12:
        break
    time.sleep(1)
por_rede = {}
for s in sl:
    por_rede.setdefault(s['rede'], []).append(s)
confere(len(sl) == 12 and set(por_rede) == {'tiktok', 'youtube'}, f'6 vídeos x 2 redes = 12 horários ocupados ({len(sl)})')
for rede, ss in por_rede.items():
    confere(len({s['ref'] for s in ss}) == len(ss) == 6, f'{rede}: cada vídeo uma vez só')
    confere(all(s['hora_local'] in ('08:00', '12:00', '19:00') for s in ss), f'{rede}: só nos horários configurados')
    confere(all(s['sha256'] == shas[s['ref'][2:]] for s in ss), f'{rede}: cada horário guarda o SHA certificado do vídeo')
st, rs = api('GET', '/api/v1/agent2/slots')
confere(sum(1 for s in rs['slots'] if s.get('titulo') in PAUTAS) == 12, 'a API do calendário mostra o nome do vídeo em cada horário')
posts = [p for p in pg.posts() if p.get('origem') == 'agente3']
confere(len(posts) == 12 and all(p.get('render_sha') and pl.certificado(p['render_sha']) for p in posts), '12 posts, todos com certificado')
confere(not any(p.get('status') in ('postado', 'publicado') for p in pg.posts()), 'nada foi publicado (só agendado para o horário)')
dup = db.um("SELECT COUNT(*) n FROM (SELECT render_sha, rede, COUNT(*) c FROM publicacoes GROUP BY render_sha, rede HAVING c>1)")['n']
confere(dup == 0, 'nenhuma publicação duplicada (mesmo vídeo, mesma rede)')
time.sleep(5)
confere(len(db.todos("SELECT id FROM posting_slots WHERE ref LIKE 'p:%' AND estado IN ('agendado','reservado')")) == 12, 'ciclos seguintes não repetem')

print(f'\n{ok_n} ok, {falhas} falha(s)')
if os.getenv('AINDA_NO_AR'):
    Path(os.getenv('AINDA_NO_AR')).write_text(json.dumps({'base': BASE, 'sessao': SES['X-Sessao'], 'linha': LID}))
    print('servidor no ar em', BASE, flush=True)
    time.sleep(float(os.getenv('SEGUNDOS_NO_AR', '600')))
sys.exit(1 if falhas else 0)
