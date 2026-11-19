"""Liberação especial do Agente 2: falta de origem registrada não barra de vez; pede a sua liberação e, liberado, posta.

Rodar:  python servidor/testes/teste_liberacao.py
Sem internet: o envio ao YouTube é simulado.
"""
import json
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='liberacao-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import banco as db  # noqa: E402
import api_v1  # noqa: E402
import aprovacoes as apv  # noqa: E402
import postagem as pg  # noqa: E402
import produtor  # noqa: E402
import projetos as pj  # noqa: E402

falhas = 0


def confere(c, nome):
    global falhas
    print(('ok    ' if c else 'FALHA ') + nome)
    falhas += 0 if c else 1


db.migrar()
api_v1.iniciar()
pg.status_contas = lambda: {k: {'conectado': True, 'erro': '', 'paginas': [], 'pagina': ''} for k in set(pg.PROV.values())}
enviados = []
pg.PUBLICAR['youtube'] = lambda p, arq: (enviados.append(p['id']), 'https://youtu.be/teste')[1]


def novo_post(versao=1):
    p = produtor.novo({'briefing': {'tema': 'GTA', 'estilo': 'animado2d', 'destinos': {'redes': ['youtube']}},
                       'roteiro': {'titulo': 'Mídia física', 'legenda': 'x', 'hashtags': ['#a'], 'cenas': [{'titulo': 'A', 'texto': 'b'}]}})
    pid = p['id']
    arq = TMP / f'{pid}.mp4'
    arq.write_bytes(pid.encode() * 100)
    sha = (pid * 8)[:64]
    db.executar('INSERT INTO renders (id, projeto, versao, arquivo, sha256, duracao, codec, largura, altura, validado, alertas, criado) VALUES (?,?,?,?,?,?,?,?,?,1,?,?)',
                'r' + pid, pid, versao, str(arq), sha, 3.0, 'h264', 360, 640, '[]', 0)
    pj.mudar_dados(pid, lambda d, _p: (d.update(render={'id': 'r' + pid, 'versao': 1, 'sha': sha, 'validado': True}, qualidade={'status': 'apto_para_revisao_humana', 'problemas': []}), {'status': 'ready_for_review'})[1])
    apv.aprovar(pid, sha, {'redes': ['youtube'], 'quando': 'data', 'data': 4102444800}, 'site', 'teste')
    post = next(x for x in pg.posts() if x.get('projeto') == pid)
    # simula um corte do Agente 1 sem a origem registrada (o caso do aviso)
    pg._mudar(post['id'], lambda q: q.update(origem='agente', direitos=None, quando=pg.agora() - 5))
    return post['id']


pid = novo_post()
pg._publicar_um(pid, 'youtube')
r = next(x for x in pg.posts() if x['id'] == pid)['redes']['youtube']
confere(r['status'] == 'liberacao' and 'liberação especial' in r['erro'] and not enviados, 'sem origem registrada: espera liberação (não é erro e nada é enviado)')
conf = {x['item']: x for x in pg.conferencia(next(x for x in pg.posts() if x['id'] == pid), 'youtube')}
confere(conf['direitos'].get('liberavel') and conf['direitos']['bloqueia'], 'conferência mostra o item como liberável')
pg.ciclo()
confere(not enviados, 'o relógio não posta sozinho sem a liberação')

pg.liberar(pid, 'teste')
p = next(x for x in pg.posts() if x['id'] == pid)
confere(p['redes']['youtube']['status'] == 'agendado' and p['liberacao']['itens'] == ['direitos'], 'liberação registrada só para o item liberável')
confere(any(e['evento'] == 'liberado' for e in p['relatorio']), 'liberação fica no relatório do post')
pg.ciclo()
p = next(x for x in pg.posts() if x['id'] == pid)
confere(p['redes']['youtube']['status'] == 'postado' and enviados == [pid], 'liberado: posta')
cf = {x['item']: x for x in pg.conferencia(p, 'youtube')}
confere(not cf['direitos']['bloqueia'] and cf['direitos'].get('liberado') and not cf['direitos']['ok'], 'conferência diz que foi liberado por você (não finge que a origem foi registrada)')

# arquivo trocado depois da liberação: precisa liberar de novo
pid2 = novo_post()
pg._publicar_um(pid2, 'youtube')
pg.liberar(pid2, 'teste')
pg._mudar(pid2, lambda q: q.update(hash='outro-arquivo'))
c2 = {x['item']: x for x in pg.conferencia(next(x for x in pg.posts() if x['id'] == pid2), 'youtube')}
confere(c2['direitos']['bloqueia'] and c2['direitos'].get('liberavel'), 'vídeo trocado: a liberação antiga não vale')

# bloqueio técnico continua barrando, mesmo com liberação
pid3 = novo_post()
pg._mudar(pid3, lambda q: q.update(liberacao={'itens': ['direitos'], 't': pg.agora(), 'quem': 'x', 'hash': q.get('hash') or ''}))
pg.status_contas = lambda: {k: {'conectado': False, 'erro': '', 'paginas': [], 'pagina': ''} for k in set(pg.PROV.values())}
pg._publicar_um(pid3, 'youtube')
r3 = next(x for x in pg.posts() if x['id'] == pid3)['redes']['youtube']
confere(r3['status'] == 'erro' and 'não está conectada' in r3['erro'], 'conta desconectada continua sendo erro (liberação não passa por cima)')
try:
    pg.liberar(next(x for x in pg.posts() if x['id'] == pid)['id'])
    confere(False, 'post sem nada a liberar recusa')
except pg.ErroRede:
    confere(True, 'post sem nada a liberar recusa')

print('\n' + ('TUDO OK' if not falhas else f'{falhas} FALHA(S)'))
sys.exit(1 if falhas else 0)
