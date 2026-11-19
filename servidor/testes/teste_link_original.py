"""Link do vídeo original na descrição de cada corte (crédito ao criador).

Rodar: cd servidor && python3 testes/teste_link_original.py
"""
import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-link-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
os.environ['CENTRAL_SEM_ACORDAR'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agente as ag  # noqa: E402
import descricao as ds  # noqa: E402
import publish_package as pub  # noqa: E402

ok = falhas = 0


def check(c, m):
    global ok, falhas
    if c:
        ok += 1
    else:
        falhas += 1
        print('FALHA:', m)


YT = 'https://www.youtube.com/watch?v=abcdefghijk'
# de onde vem o link
check(ag._link_do_video({'id': 'abcdefghijk', 'url': 'http://teste.local/v.mp4'}) == YT, 'id do YouTube vira link público (não o de teste)')
check(ag._link_do_video({'id': 'abcdefghijk-live3', 'url': 'https://www.youtube.com/live/abcdefghijk'}) == YT, 'bloco da live aponta para a live')
check(ag._link_do_video({'id': 'x1234567890', 'url': 'https://www.twitch.tv/videos/123'}) == 'https://www.twitch.tv/videos/123', 'link enviado que não é YouTube')
check(ag._link_do_video({'id': 'x1234567890', 'url': ''}) == '', 'sem link: vazio, nunca inventa')

# descrição do corte
c = {'titulo': 'Jogada absurda', 'hashtags': ['#gta', '#gameplay'], 'origem': 'abcdefghijk', 'origem_url': YT}
t = ag.legenda_do_corte(c)
check(t.startswith('Jogada absurda\n\n#gta #gameplay'), 'título e hashtags primeiro: ' + repr(t))
check(t.endswith('.\n.\n.\nLink original do vídeo [' + YT + ']'), 'termina com o link original: ' + repr(t))
check(ag.legenda_do_corte({'titulo': 'A', 'hashtags': [], 'origem': 'abcdefghijk'}).endswith('[' + YT + ']'), 'corte antigo (sem origem_url) acha pelo id')

# legenda editada à mão: mantém o texto, só acrescenta o link
e = ag.legenda_do_corte(dict(c, legenda_post='Meu texto #gta'))
check(e.startswith('Meu texto #gta') and e.endswith('[' + YT + ']'), 'editada ganha o link no fim: ' + repr(e))
check(ag.legenda_do_corte(dict(c, legenda_post='Olha ' + YT)) == 'Olha ' + YT, 'link já presente: não repete')
vazio = ds.compor('T', ['#a'], '')
check(ds.com_link(vazio, YT).endswith('[' + YT + ']') and ds.com_link(vazio, YT).count('Link original') == 1, 'colchete vazio é preenchido')
check(ds.com_link('texto', 'nao-e-link') == 'texto', 'link inválido: não mexe')

# pacote de publicação usa o mesmo link
check(pub._link_original({'origem': 'x1234567890', 'origem_url': 'https://www.twitch.tv/videos/123'}) == 'https://www.twitch.tv/videos/123', 'pacote usa origem_url')

# post já agendado antes desta mudança: ganha o link
mud = {}
_orig = ag.pg._mudar
ag.pg._mudar = lambda pid, f: (f(mud.setdefault(pid, {})), mud[pid])[1]
ag._completar_link(c, {'id': 'p1', 'legenda': 'Jogada absurda\n\n#gta'})
check(mud.get('p1', {}).get('legenda', '').endswith('[' + YT + ']'), 'post agendado antigo recebe o link')
mud.clear()
ag._completar_link(c, {'id': 'p2', 'legenda': t})
check('p2' not in mud, 'post que já tem o link não é mexido')
ag.pg._mudar = _orig

# última conferência antes de enviar: post de corte sem o link (agendado antes, editado à mão ou feito pela tela) ganha o link
pg = ag.pg
pg.posts = lambda: list(POSTS.values())
POSTS = {'q1': {'id': 'q1', 'video': 'v1', 'origem': 'agente', 'titulo': 'Fuga insana', 'legenda': 'Fuga insana\n\n#gta6 #gameplay', 'redes': {}},
         'q2': {'id': 'q2', 'video': 'v2', 'origem': 'manual', 'titulo': 'Outro', 'legenda': 'Outro #gta', 'redes': {}},
         'q3': {'id': 'q3', 'video': 'v3', 'origem': 'agente', 'titulo': 'Sem fonte', 'legenda': 'Sem fonte', 'redes': {}},
         'q4': {'id': 'q4', 'video': 'v4', 'origem': 'agente3', 'titulo': 'Próprio', 'legenda': 'Próprio', 'redes': {}}}
pg._mudar = lambda pid, f: (f(POSTS[pid]), POSTS[pid])[1]
CORTES = [dict(c, id='c1', post='q1', video='v1'), dict(c, id='c2', post='', video='v2'), {'id': 'c3', 'post': 'q3', 'video': 'v3', 'titulo': 'Sem fonte', 'origem': ''},
          dict(c, id='c4', post='q4', video='v4')]
ag.estado = lambda: {'cortes': CORTES}
for q in POSTS:
    pg._garantir_link(q)
check(POSTS['q1']['legenda'].startswith('Fuga insana\n\n#gta6') and POSTS['q1']['legenda'].endswith('[' + YT + ']'), 'post do agente sem link ganha o link antes de enviar: ' + repr(POSTS['q1']['legenda']))
check(POSTS['q2']['legenda'].endswith('[' + YT + ']'), 'post feito pela tela com o vídeo de um corte também ganha o link')
check(POSTS['q3']['legenda'] == 'Sem fonte' and any(x['evento'] == 'sem_link' for x in POSTS['q3']['relatorio']), 'sem fonte conhecida: não inventa, fica anotado')
check(POSTS['q4']['legenda'] == 'Próprio', 'vídeo próprio (Agente 3) não é mexido')
antes = POSTS['q1']['legenda']
pg._garantir_link('q1')
check(POSTS['q1']['legenda'] == antes, 'conferir de novo não repete o link')

print(f'{ok} ok, {falhas} falha(s)')
sys.exit(1 if falhas else 0)
