"""Busca automática de canais do Agente 1 (pedido de 21/11): ligar/desligar, intervalo, máximo de sugestões,
e nunca repetir sem parar quando a busca dá erro.

Rodar: cd servidor && python3 testes/teste_busca_canais.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault('ESTEIRA_COMPLETA', '0')
TMP = Path(tempfile.mkdtemp(prefix='ec-busca-'))
os.environ.update(DADOS=str(TMP / 'dados'), BANCO_ARQ=str(TMP / 'dados' / 'database' / 'studio.sqlite'), CHAVE_MESTRA_ARQ=str(TMP / 'chave'),
                  COORDENADOR_SEM_VIGIA='1')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agente as ag
import banco as db
import orquestrador as oq

db.migrar()
ok_n = falhas = 0


def confere(c, nome):
    global ok_n, falhas
    ok_n += bool(c)
    falhas += not c
    print('  ok ' if c else '  FALHOU', nome)


print('1. Padrão e limites')
co = ag.config()['cortes']
confere(co['busca_auto'] is True and co['busca_horas'] == 24 and co['busca_max'] == 25, 'padrão: ligada, a cada 24 h, até 25 sugestões')
co = ag.salvar_config({'cortes': {'busca_horas': 999, 'busca_max': 0}})['cortes']
confere(co['busca_horas'] == 168 and co['busca_max'] == 1, 'valores fora da faixa são ajustados (máx. 168 h, mín. 1 canal)')
co = ag.salvar_config({'cortes': {'busca_horas': 'abc', 'busca_max': 10}})['cortes']
confere(co['busca_horas'] in (24, 168) and co['busca_max'] == 10, f'valor inválido não quebra a configuração ({co["busca_horas"]} h)')

print('2. Erro na busca não vira repetição sem parar')
chamadas = []


def yt_quebrado(caminho, **q):
    chamadas.append(caminho)
    raise ag.ErroAgente('O YouTube recusou a busca: cota esgotada')


ag.yt = yt_quebrado
ag.salvar_config({'cortes': {'busca_horas': 6, 'nichos': ['Games']}})
confere(ag.busca_vencida(), 'nunca buscou: a busca automática está vencida')
try:
    ag.buscar_canais()
    deu_erro = False
except ag.ErroAgente:
    deu_erro = True
confere(deu_erro and chamadas, 'a busca tentou e deu erro (cota)')
confere(not ag.busca_vencida(), 'mesmo com erro, a próxima tentativa só depois do intervalo (sem repetir a cada volta)')
s = ag.busca_situacao()
confere('cota' in s['erro'] and s['ultima'] and abs(s['proxima'] - s['ultima'] - 6 * 3600) < 1, f'tela mostra o erro e a próxima busca em 6 h: "{s["erro"]}"')

print('3. Sucesso respeita o máximo de sugestões')
VIDEOS = [{'id': f'v{i}', 'snippet': {'title': f'Vídeo {i}', 'channelId': f'UCcanal{i:02d}', 'channelTitle': f'Canal {i}', 'publishedAt': '2026-11-20T10:00:00Z',
                                       'defaultAudioLanguage': 'pt'},
           'statistics': {'viewCount': str(900000 + i)}, 'contentDetails': {'duration': 'PT20M'}} for i in range(12)]


def yt_ok(caminho, **q):
    if caminho == 'search':
        return {'items': [{'id': {'videoId': v['id']}} for v in VIDEOS]}
    if caminho == 'videos':
        return {'items': VIDEOS}
    return {'items': [{'id': c, 'statistics': {'subscriberCount': '1000'}} for c in q['id'].split(',')]}


ag.yt = yt_ok
ag.avisar = lambda *a, **k: True
ag.salvar_config({'cortes': {'busca_max': 5, 'min_views': 500000}})
n = ag.buscar_canais()
confere(n == 5 and len([c for c in ag.estado()['canais'] if c['status'] == 'sugerido']) == 5, f'sugeriu {n} canais (máximo 5)')
s = ag.busca_situacao()
confere(s['erro'] == '' and s['achados'] == 5 and s['ultima_ok'], 'erro anterior limpo e quantidade achada registrada')

print('4. Desligada: nem o relógio nem a Central mandam procurar')
ag.salvar_config({'cortes': {'busca_auto': False}})
ag._mudar(lambda e: e['marcas'].update(busca=time.time() - 30 * 86400))
confere(not ag.busca_vencida() and ag.busca_situacao()['proxima'] is None, 'desligada: busca nunca vence e a tela diz "desativada"')
cfg = oq.config()
est = {'efetivo': 0, 'disponiveis': 0, 'taxa_aprovacao': 1.0}
cfg2, ult = oq._com_busca_do_agente1(cfg, ag.estado()['marcas'], time.time())
d = oq.decidir_cortes(cfg2, est, True, time.time(), 0, ult)
confere(d['acao'] == 'cortar', f'Central com estoque vazio e busca desligada: corta dos canais aprovados, não procura ({d["acao"]})')
ag.salvar_config({'cortes': {'busca_auto': True, 'busca_horas': 2}})
cfg2, ult = oq._com_busca_do_agente1(cfg, ag.estado()['marcas'], time.time())
d = oq.decidir_cortes(cfg2, est, True, time.time(), 0, ult)
confere(d['acao'] == 'buscar_canais' and cfg2['cortes']['busca_horas'] == 2, 'ligada de novo: a Central usa o intervalo do Agente 1 (2 h)')
ag._mudar(lambda e: e['marcas'].update(busca=time.time()))
cfg2, ult = oq._com_busca_do_agente1(cfg, ag.estado()['marcas'], time.time())
confere(oq.decidir_cortes(cfg2, est, True, time.time(), 0, ult)['acao'] == 'cortar', 'buscou agora há pouco: não procura de novo')

print(f'\n{ok_n} ok, {falhas} falhas')
sys.exit(1 if falhas else 0)
