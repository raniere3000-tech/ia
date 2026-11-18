"""Sino de alertas do site e previsão de tempo dos trabalhos.

Rodar: cd servidor && python3 testes/teste_alertas.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-alertas-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
os.environ['CENTRAL_SEM_ACORDAR'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import banco as db  # noqa: E402
import agente as ag  # noqa: E402
import alertas  # noqa: E402
import fila  # noqa: E402
import orquestrador as oq  # noqa: E402
import rotas_esteira as rt  # noqa: E402

db.migrar()
ok = falhas = 0


def check(c, m):
    global ok, falhas
    if c:
        ok += 1
        print('  ok  ', m)
    else:
        falhas += 1
        print('  FALHOU:', m)


def rota(metodo, caminho, corpo=None, q=None):
    return rt.tratar(metodo, caminho, q or {}, lambda: corpo or {}, 'teste')


print('1. Sino de alertas')
ag.avisar('falha', 'Um post falhou em youtube', 'Corte: X\nMotivo: conta desconectada')
ag.avisar('postado', 'Post enviado: Y', 'Corte: Y')
r = rota('GET', '/api/v1/alertas')
check(r['nao_lidas'] == 2 and r['alertas'][0]['assunto'] == 'Post enviado: Y', 'o aviso do e-mail/WhatsApp também aparece no sino (mais novo primeiro)')
check(r['alertas'][1]['nivel'] == 'erro' and r['alertas'][1]['destino'] == 'agendar', 'falha aparece como erro e leva para Publicações')
check(len(rota('GET', '/api/v1/alertas', q={'desde': [str(r['alertas'][1]['n'])]})['alertas']) == 1, 'pede só os novos (desde)')
check(rota('POST', '/api/v1/alertas/lidas', {})['nao_lidas'] == 0, 'marcar como lidas zera o contador')
ag.avisar('live', 'Live: gravação encerrada', 'A live terminou.')
check(alertas.listar()['nao_lidas'] == 1, 'alerta novo depois de ler conta de novo')
for i in range(alertas.MAX + 5):
    alertas.registrar('canal', f'a{i}')
check(len(alertas._ler()['itens']) == alertas.MAX, f'guarda só os últimos {alertas.MAX}')

print('2. Porcentagem e tempo que falta')
fila.registrar('teste.x', lambda ctx: {}, 'pesado')
j = fila.enfileirar('teste.x', agente='agente1', titulo='Cortando')
db.executar("UPDATE jobs SET status='rodando', progresso=25, iniciado=? WHERE id=?", time.time() - 60, j['id'])
rest, medido = fila.restante(fila.obter(j['id']))
check(170 < rest < 190 and medido, f'25% em 1 min: faltam ~3 min ({rest:.0f} s), pelo ritmo de agora')
t = next(x for x in oq._trabalhos() if x['titulo'] == 'Cortando')
check(t['restante_s'] and 170 < t['restante_s'] < 190 and t['progresso'] == 25, 'a Central recebe a % e o tempo que falta')
fila.medir('job:teste.x', 600)
j2 = fila.enfileirar('teste.x', agente='agente1', titulo='Próximo')
t2 = next(x for x in oq._trabalhos() if x['titulo'] == 'Próximo')
check(t2['restante_s'] == 600 and 170 < t2['comeca_em_s'] < 190, 'o que está na fila: leva ~10 min (medido) e começa depois do atual')
vistos = []
ag.AO_ETAPA = lambda p, tx: vistos.append((p, tx))
ag.etapa('Editando o corte 1 de 3', 62)
ag.AO_ETAPA = None
check(vistos == [(62, 'Editando o corte 1 de 3')], 'cada etapa do Agente 1 vira progresso do trabalho na fila')

print(f'\n{ok} ok, {falhas} falha(s)')
sys.exit(1 if falhas else 0)
