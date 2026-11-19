"""Histórico de cortes: aprovar e agendar mesmo com restrições de direitos (liberação especial); o técnico continua barrando.

Rodar:  python servidor/testes/teste_liberar_corte.py
"""
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='liberar-corte-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import banco as db  # noqa: E402
import api_v1  # noqa: E402
import agente as ag  # noqa: E402
import comandos as cm  # noqa: E402
import postagem as pg  # noqa: E402

falhas = 0


def confere(c, nome, extra=''):
    global falhas
    print(('ok    ' if c else 'FALHA ') + nome + ('' if c else f'  -> {extra}'))
    falhas += 0 if c else 1


db.migrar()
api_v1.iniciar()
pg.acordar = lambda: None
ag.enviar_email = lambda *a, **k: 'mid'
ag.salvar_config({'postagem': {'redes': ['youtube']}})
(pg.VIDEOS / 'v1.mp4').write_bytes(b'a' * 500)
(pg.VIDEOS / 'v2.mp4').write_bytes(b'b' * 500)
ag._mudar(lambda e: e['canais'].append({'id': 'UCx', 'nome': 'Canal X', 'status': 'recusado', 'motivo': '', 'comercial': False, 'nicho': 'Games', 'media': 1, 'videos': 1, 'inscritos': 1}))
base = dict(titulo='T', gancho='g', hashtags=['#a'], motivo='m', nota=80, ini=0, fim=60, status='pronto', post='', origem='vidx', origem_titulo='O', canal='UCx', canal_nome='Canal X',
            variacoes=[], fala='IA', tamanho=500, email=False, tipo='agente', legendado=True, qa={'diretor': {'veredito': 'aprovado', 'motivos': [], 'tentativas': 0}})
ag._mudar(lambda e: e['cortes'].extend([dict(base, id='c1', video='v1', chave='k1', criado=1, hash='h1'),
                                        dict(base, id='c2', video='v2', chave='k2', criado=2, hash='h2', qa={'erros': ['sem som'], 'avisos': []})]))
c1 = next(c for c in ag.estado()['cortes'] if c['id'] == 'c1')
conf = ag.conferir(c1)
confere(conf['bloqueios'] and conf['liberavel'], 'restrição de canal/direitos pode ser liberada por você', conf)
c2 = next(c for c in ag.estado()['cortes'] if c['id'] == 'c2')
confere(not ag.conferir(c2)['liberavel'], 'problema técnico não pode ser liberado', ag.conferir(c2))

try:
    ag.acao_corte('c1', 'agendar')
    confere(False, 'agendar normal continua barrado pela restrição')
except ag.ErroAgente as e:
    confere('Liberar e agendar' in str(e), 'agendar normal continua barrado pela restrição e indica o caminho', str(e))
try:
    ag.acao_corte('c2', 'liberar')
    confere(False, 'liberar não passa por cima do problema técnico')
except ag.ErroAgente as e:
    confere('Não agendei' in str(e), 'liberar não passa por cima do problema técnico')

ag.acao_corte('c1', 'liberar')
c1 = next(c for c in ag.estado()['cortes'] if c['id'] == 'c1')
post = next(x for x in pg.posts() if x['id'] == c1['post'])
confere(c1['status'] == 'agendado' and c1['liberacao']['restricoes'] and c1.get('aprovado_voce'), 'corte liberado e agendado, com as restrições registradas', c1)
confere(post.get('liberacao', {}).get('itens') == ['direitos'] and any(r['evento'] == 'liberado' for r in post['relatorio']), 'a liberação vai para o post e para o relatório')

# reprovado pelo diretor continua sem liberação
ag._mudar(lambda e: e['cortes'].append(dict(base, id='c3', video='v1', chave='k3', criado=3, status='reprovado', qa={'diretor': {'veredito': 'reprovado', 'motivos': ['x'], 'tentativas': 3}})))
try:
    ag.acao_corte('c3', 'liberar')
    confere(False, 'reprovado pelo diretor não é liberado')
except ag.ErroAgente as e:
    confere('diretor de qualidade reprovou' in str(e), 'reprovado pelo diretor não é liberado')

# WhatsApp
ag._mudar(lambda e: e['cortes'].append(dict(base, id='c4', video='v2', chave='k4', criado=4, hash='h4')))
ag.salvar_config({'postagem': {'faixas': [{'dia': d, 'hora': h} for d in range(7) for h in ('06:00', '09:00', '12:00', '15:00', '18:00', '21:00')]}})
r = cm.responder('liberar corte 1', 'w')      # a lista de pendentes é c2 (erro técnico) e c4
confere('não dá para liberar' in r, 'WhatsApp: corte com problema técnico não é liberado', r)
r = cm.responder('liberar corte 2', 'w')
confere('SIM' in r and 'restrições' in r and 'não está mais na sua lista' in r and next(c for c in ag.estado()['cortes'] if c['id'] == 'c4')['status'] == 'pronto',
        'WhatsApp: mostra as restrições e pede SIM antes', r)
r = cm.responder('sim', 'w')
c4 = next(c for c in ag.estado()['cortes'] if c['id'] == 'c4')
confere(c4['status'] == 'agendado' and c4.get('liberacao') and 'liberado por você' in r, 'WhatsApp: SIM libera e agenda', r)

print('\nTUDO OK' if not falhas else f'\n{falhas} FALHA(S)')
sys.exit(1 if falhas else 0)
