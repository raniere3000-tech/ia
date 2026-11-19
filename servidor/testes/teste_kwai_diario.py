"""Pacote diário do Kwai: o Coordenador junta os vídeos do dia (nome, descrição, hashtags, link original e vídeo)
e manda no fim do dia (WhatsApp com o link da página + e-mail com o .txt).

Rodar: cd servidor && python3 testes/teste_kwai_diario.py
"""
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

TMP = Path(tempfile.mkdtemp(prefix='ec-kwai-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
os.environ['CENTRAL_SEM_ACORDAR'] = '1'
os.environ['COORDENADOR_SEM_VIGIA'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agente as ag  # noqa: E402
import autenticacao as au  # noqa: E402
import banco as db  # noqa: E402
import coordenador as co  # noqa: E402
import kwai_diario as kd  # noqa: E402
import postagem as pg  # noqa: E402

db.migrar()
ok = falhas = 0


def check(c, m):
    global ok, falhas
    if c:
        ok += 1
    else:
        falhas += 1
        print('FALHA:', m)


YT = 'https://www.youtube.com/watch?v=abcdefghijk'
hoje = time.strftime('%Y-%m-%d')
meio_dia = time.mktime(time.strptime(hoje + ' 12:00', '%Y-%m-%d %H:%M'))
for v in ('v1', 'v2', 'v3'):
    (pg.VIDEOS / (v + '.mp4')).write_bytes(b'\x00' * 2048)
POSTS = [
    {'id': 'p1', 'video': 'v1', 'origem': 'agente', 'titulo': 'Fuga insana no GTA', 'legenda': 'Fuga insana no GTA\n\n#gta #gameplay',
     'quando': meio_dia, 'redes': {'youtube': {'status': 'postado', 'link': 'https://youtu.be/xyz'}, 'kwai': {'status': 'manual'}}},
    {'id': 'p2', 'video': 'v2', 'origem': 'agente3', 'titulo': 'História do café', 'legenda': 'História do café #cafe',
     'quando': meio_dia + 3600, 'redes': {'tiktok': {'status': 'agendado'}}},
    {'id': 'p3', 'video': 'v3', 'origem': 'agente', 'titulo': 'Ontem', 'legenda': 'Ontem', 'quando': meio_dia - 86400, 'redes': {'youtube': {'status': 'postado'}}},
    {'id': 'p4', 'video': 'sumiu', 'origem': 'agente', 'titulo': 'Sem arquivo', 'legenda': 'Sem arquivo #x', 'quando': meio_dia + 60,
     'redes': {'youtube': {'status': 'postado'}}},
]
pg.posts = lambda: [dict(p) for p in POSTS]
ag.estado = lambda: {'cortes': [{'id': 'c1', 'post': 'p1', 'video': 'v1', 'titulo': 'Fuga insana no GTA', 'hashtags': ['#gta'], 'origem': 'abcdefghijk', 'origem_url': YT},
                                {'id': 'c4', 'post': 'p4', 'video': 'sumiu', 'titulo': 'Sem arquivo', 'origem': ''}]}
ag._endereco = lambda: 'https://tunel.exemplo.com'

its = kd.itens(hoje)
check([i['post'] for i in its] == ['p1', 'p4', 'p2'], f'só os vídeos de hoje, em ordem de horário: {[i["post"] for i in its]}')
i1 = its[0]
check(i1['titulo'] == 'Fuga insana no GTA' and i1['link_original'] == YT, 'nome e link original do corte')
check(i1['descricao'].startswith('Fuga insana no GTA') and i1['descricao'].endswith('[' + YT + ']'), 'descrição pronta já com o link original: ' + repr(i1['descricao']))
check(i1['hashtags'] == ['#gta', '#gameplay'], f'hashtags tiradas da descrição: {i1["hashtags"]}')
check(i1['tem_video'] and i1['kwai_marcado'] and not i1['kwai_feito'], 'vídeo existe e Kwai está marcado como manual')
check(its[2]['proprio'] and its[2]['link_original'] == '', 'vídeo próprio (Agente 3): sem link original, não inventa')
check(not its[1]['tem_video'], 'post cujo arquivo sumiu: avisado, sem link de vídeo')

r = kd.montar(hoje)
txt = Path(r['arquivos']['texto']).read_text()
pag = Path(r['arquivos']['pagina']).read_text()
check('Fuga insana no GTA' in txt and YT in txt and '#gta #gameplay' in txt, 'o .txt tem nome, link original e hashtags')
check('https://tunel.exemplo.com/api/v1/kwai/video/p1?exp=' in txt, 'o .txt tem o link completo para baixar o vídeo')
check('vídeo próprio' in txt and 'não está mais no servidor' in txt, 'o .txt explica vídeo próprio e arquivo sumido')
check('Copiar descrição' in pag and '/api/v1/kwai/video/p1?exp=' in pag and 'download' in pag, 'a página tem copiar e baixar')
check('<script>alert' not in kd.pagina(hoje, [dict(i1, titulo='<script>alert(1)</script>')], r['links']), 'página escapa o texto (sem HTML injetado)')

# links assinados abrem sem senha e só o caminho certo
u = urlparse(r['links']['videos']['p1'])
q = parse_qs(u.query)
check(au.url_assinada_ok(u.path, q['exp'][0], q['sig'][0]), 'link do vídeo assinado vale')
check(not au.url_assinada_ok('/api/v1/kwai/video/p2', q['exp'][0], q['sig'][0]), 'assinatura de um vídeo não abre outro')
arq, nome = kd.video('p1')
check(arq.name == 'v1.mp4' and nome == 'Fuga insana no GTA.mp4', f'baixar com o nome do vídeo: {nome}')
check(kd.arquivo(hoje, 'pagina').suffix == '.html' and kd.arquivo(hoje, 'texto').suffix == '.txt', 'arquivos do dia')
# ZIP: cada vídeo com o texto dele do lado + um texto com todos
import zipfile  # noqa: E402
zp = kd.arquivo(hoje, 'zip')
with zipfile.ZipFile(zp) as z:
    nomes = sorted(z.namelist())
    check(nomes == ['00 - LEIA PRIMEIRO.txt', '01 - Fuga insana no GTA.mp4', '01 - Fuga insana no GTA.txt', '02 - Sem arquivo.txt', '03 - Historia do cafe.mp4', '03 - Historia do cafe.txt'],
          f'ZIP com vídeo e texto de mesmo nome: {nomes}')
    t1 = z.read('01 - Fuga insana no GTA.txt').decode('utf-8')
    check('\r\n' in t1 and YT in t1 and '#gta #gameplay' in t1 and t1.count('Link original do vídeo [') == 1, 'texto do vídeo pronto para o bloco de notas: ' + repr(t1))
    check(z.getinfo('01 - Fuga insana no GTA.mp4').compress_type == zipfile.ZIP_STORED, 'vídeo entra sem recompressão')
    check('Historia do cafe' in z.read('00 - LEIA PRIMEIRO.txt').decode() or 'História do café' in z.read('00 - LEIA PRIMEIRO.txt').decode(), 'LEIA PRIMEIRO tem todos')
mt = zp.stat().st_mtime_ns
check(kd.arquivo(hoje, 'zip').stat().st_mtime_ns == mt, 'nada mudou: não refaz o ZIP')
check('/api/v1/kwai/' + hoje + '/zip?exp=' in r['links']['zip'] and 'Baixar tudo' in Path(kd.arquivo(hoje, 'pagina')).read_text(), 'link do ZIP na página')
for ruim in ('2026-13-45', '../etc', 'ontem'):
    try:
        kd.data_valida(ruim)
        check(False, 'data inválida aceita: ' + ruim)
    except kd.ErroKwai:
        check(True, '')

# o Coordenador manda sozinho no fim do dia, uma vez só
AVISOS = []
ag.avisar = lambda *a, **k: AVISOS.append((a, k)) or True
check(co.config()['kwai_diario'] and co.config()['kwai_hora'] == '21:00', 'ligado por padrão, às 21:00')
check(co.pacote_kwai_do_dia(meio_dia) is None and not AVISOS, 'antes do horário não manda')
noite = time.mktime(time.strptime(hoje + ' 21:05', '%Y-%m-%d %H:%M'))
res = co.pacote_kwai_do_dia(noite)
check(res and res['videos'] == 3 and len(AVISOS) == 1, f'às 21h manda o pacote: {res}')
a, k = AVISOS[0]
check(a[0] == 'kwai' and Path(a[3]).suffix == '.txt' and a[4] == f'kwai-{hoje}.txt', 'e-mail leva o .txt anexado')
check(k['zap_tipo'] == 'a7_kwai' and 'https://tunel.exemplo.com/api/v1/kwai/' in k['zap'] and '#coordenador/kwai' in k['zap'], 'WhatsApp leva o link da página e do site')
check('/zip?exp=' in k['zap'] and 'ZIP' in k['zap'], 'WhatsApp leva o link do ZIP')
check(co.pacote_kwai_do_dia(noite + 600) is None and len(AVISOS) == 1, 'não repete no mesmo dia')
check(any(e['categoria'] == 'kwai' for e in co.eventos()), 'fica no histórico do Coordenador')
check(ag.PADRAO['whatsapp']['avisos']['a7_kwai'] is True, 'aviso do Kwai no WhatsApp ligado por padrão')

# dia sem vídeo: não manda nada
amanha = noite + 86400
check(co.pacote_kwai_do_dia(amanha) == {'data': time.strftime('%Y-%m-%d', time.localtime(amanha)), 'videos': 0} and len(AVISOS) == 1, 'dia sem vídeo: não manda')

# desligado / horário
co.salvar_config({'kwai_diario': False, 'kwai_hora': '22:30'})
check(co.pacote_kwai_do_dia(amanha + 86400) is None, 'desligado: não manda')
try:
    co.salvar_config({'kwai_hora': '25:00'})
    check(False, 'horário inválido aceito')
except co.ErroCoord:
    check(True, '')
check(co.config()['kwai_hora'] == '22:30', 'horário salvo')
co.salvar_config({'kwai_diario': True})

# pedir pelo chat
for frase in ('manda o pacote do kwai', 'quero o arquivo do Kawai de hoje', 'cadê o kwai'):
    check(co.entender(frase)['intencao'] == 'kwai', 'chat entende: ' + frase)
check(co.entender('como está?')['intencao'] == 'status', 'não atrapalha as outras frases')
out = co.interpretar('manda o pacote do kwai')
check(out['tipo'] == 'resposta' and '3 vídeo' in out['resposta'] and len(AVISOS) == 2, 'pelo chat manda na hora: ' + out['resposta'])

print(f'{ok} ok, {falhas} falha(s)')
sys.exit(1 if falhas else 0)
