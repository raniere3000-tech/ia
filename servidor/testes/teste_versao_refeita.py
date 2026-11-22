"""Versão do vídeo depois de agendado: se o editor/diretor refaz o arquivo e a versão nova é aprovada, o post vale
(inclusive ao tocar em "Tentar de novo"). Arquivo trocado sem aprovação continua barrado.

Rodar:  python servidor/testes/teste_versao_refeita.py
Sem internet: o envio ao YouTube é simulado.
"""
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='versao-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import banco as db  # noqa: E402
import pipeline as pl  # noqa: E402
import postagem as pg  # noqa: E402

falhas = 0


def confere(c, nome):
    global falhas
    print(('ok    ' if c else 'FALHA ') + nome)
    falhas += 0 if c else 1


db.migrar()
pg.status_contas = lambda: {k: {'conectado': True, 'erro': '', 'paginas': [], 'pagina': ''} for k in set(pg.PROV.values())}
enviados = []
pg.PUBLICAR['youtube'] = lambda p, arq: (enviados.append(p['id']), 'https://youtu.be/teste')[1]

vid = 'v1teste'
arq = pg.VIDEOS / f'{vid}.mp4'
arq.write_bytes(b'versao-1 ' * 500)
p = {'id': 'p1', 'video': vid, 'criado': pg.agora(), 'quando': pg.agora() - 5, 'titulo': 't', 'legenda': 'l', 'opcoes': {},
     'redes': {'youtube': {'status': 'agendado', 'link': '', 'erro': ''}}, 'origem': 'manual', 'hash': pg.assinatura(vid)}
pg.salvar_posts([p])
antigo = p['hash']


def versao():
    post = next(x for x in pg.posts() if x['id'] == 'p1')
    return next(x for x in pg.conferencia(post, 'youtube') if x['item'] == 'versao')


confere(versao()['ok'], 'mesmo arquivo: versão ok')

# 1) arquivo trocado SEM aprovação: continua barrado
arq.write_bytes(b'versao-2 ' * 500)
v = versao()
confere(not v['ok'] and v['bloqueia'], 'arquivo trocado sem aprovação: barrado')
pg._publicar_um('p1', 'youtube')
r = next(x for x in pg.posts() if x['id'] == 'p1')['redes']['youtube']
confere(r['status'] == 'erro' and not enviados, 'não posta o arquivo trocado sem aprovação')

# 2) o diretor aprova a versão nova: "Tentar de novo" posta sem agendar de novo
pl.emitir_certificado('corte1', pl.sha_arquivo(arq), {'score': 100, 'blocking_findings': []})
v = versao()
confere(v['ok'] and 'aprovada pelo diretor' in v['detalhe'], 'versão nova aprovada pelo diretor: ok')
pg.postar_agora('p1', 'youtube')
pg._publicar_um('p1', 'youtube')
post = next(x for x in pg.posts() if x['id'] == 'p1')
confere(post['redes']['youtube']['status'] == 'postado' and enviados == ['p1'], 'Tentar de novo posta a versão aprovada')
confere(post['hash'] == pg.assinatura(vid) and post['hash'] != antigo, 'post passa a apontar para a versão nova')

# 3) troca feita por um agente atualiza os posts ainda não enviados
p2 = dict(p, id='p2', hash=antigo, redes={'youtube': {'status': 'agendado', 'link': '', 'erro': ''}}, quando=pg.agora() + 3600)
pg.salvar_posts(pg.posts() + [p2])
confere(pg.arquivo_trocado(vid, 'teste') == 1, 'arquivo_trocado atualiza só o post não enviado')
confere(next(x for x in pg.posts() if x['id'] == 'p2')['hash'] == pg.assinatura(vid), 'post agendado aponta para a versão nova')

print('\n' + ('TUDO OK' if not falhas else f'{falhas} FALHA(S)'))
sys.exit(1 if falhas else 0)
