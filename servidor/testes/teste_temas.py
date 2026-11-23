"""Agente 1 por tema: só vídeos do tema; canais aprovados primeiro; busca em outros canais só quando você pede.

Rodar:  python servidor/testes/teste_temas.py      (sem internet: o YouTube é simulado)
"""
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='temas-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import banco as db  # noqa: E402
import agente as ag  # noqa: E402
import comandos as cm  # noqa: E402

falhas = 0


def confere(c, nome, extra=''):
    global falhas
    print(('ok    ' if c else 'FALHA ') + nome + ('' if c else f'  -> {extra}'))
    falhas += 0 if c else 1


db.migrar()
agora = datetime.now(UTC).replace(tzinfo=None).strftime('%Y-%m-%dT%H:%M:%SZ')
VIDEOS = {
    'aaaaaaaaaaa': dict(id='aaaaaaaaaaa', titulo='Elden Ring: chefe final sem tomar dano', canal='UCaprovado', canal_nome='Canal A', views=1000, dur=900, publicado=agora, idioma='pt'),
    'bbbbbbbbbbb': dict(id='bbbbbbbbbbb', titulo='Minecraft survival dia 100', canal='UCaprovado', canal_nome='Canal A', views=9000, dur=900, publicado=agora, idioma='pt'),
    'ccccccccccc': dict(id='ccccccccccc', titulo='Tudo sobre ELDEN RING em 15 minutos', canal='UCoutro', canal_nome='Canal Outro', views=500000, dur=900, publicado=agora, idioma='pt'),
}
buscas = []
legendas = {'aaaaaaaaaaa': 'true', 'bbbbbbbbbbb': 'false'}


def yt(caminho, **q):
    if caminho == 'playlistItems':
        return {'items': [{'contentDetails': {'videoId': 'aaaaaaaaaaa'}}, {'contentDetails': {'videoId': 'bbbbbbbbbbb'}}]}
    if caminho == 'search':
        buscas.append(q['q'])
        return {'items': [{'id': {'videoId': 'ccccccccccc'}}]}
    if caminho == 'videos':
        items = []
        for vid in q['id'].split(','):
            v = VIDEOS[vid]
            detalhes = {'duration': 'PT15M'}
            if vid in legendas:
                detalhes['caption'] = legendas[vid]
            items.append({'id': vid, 'snippet': {'title': v['titulo'], 'channelId': v['canal'],
                                                    'channelTitle': v['canal_nome'], 'publishedAt': v['publicado'],
                                                    'defaultAudioLanguage': v['idioma']},
                          'statistics': {'viewCount': str(v['views'])}, 'contentDetails': detalhes})
        return {'items': items}
    raise AssertionError(caminho)


ag.yt = yt
ag._mudar(lambda e: e['canais'].append({'id': 'UCaprovado', 'nome': 'Canal A', 'status': 'aprovado', 'motivo': 'meu', 'nicho': 'Games', 'media': 1, 'videos': 1, 'inscritos': 1}))

v = ag.proximo_video()
confere(v and v['id'] == 'aaaaaaaaaaa', 'prioridade padrão: legenda ganha de mais visualizações')
ag.salvar_config({'cortes': {'priorizar_legendas': False}})
v = ag.proximo_video()
confere(v and v['id'] == 'bbbbbbbbbbb', 'sem prioridade: o mais visto dos canais aprovados')
ag.salvar_config({'cortes': {'priorizar_legendas': True}})
legendas.clear()
v = ag.proximo_video()
confere(v and v['id'] == 'bbbbbbbbbbb', 'sem legendas disponíveis: escolhe o vídeo mais visto')

ag.salvar_config({'cortes': {'temas': ['elden ring']}})
v = ag.proximo_video()
confere(v and v['id'] == 'aaaaaaaaaaa' and not v['fora_aprovados'] and v['tema'] == 'elden ring' and not buscas,
        'com tema: só o vídeo do tema, nos canais aprovados, sem gastar busca', v)

ag._mudar(lambda e: e['vistos'].update(aaaaaaaaaaa={'t': 1, 'r': 'ok'}))
msg = ag.trabalhar_cortes(True)
confere('Não achei vídeo novo sobre os seus temas' in msg and 'outros canais' in msg, 'sem vídeo do tema: explica e sugere buscar em outros canais', msg)

ag.salvar_config({'cortes': {'temas_outros': True}})
v = ag.proximo_video()
confere(v and v['id'] == 'ccccccccccc' and v['fora_aprovados'] and set(buscas) == {'elden ring'}, 'com "outros canais" ligado: busca no YouTube e marca como fora dos aprovados', v)

ag.salvar_config({'cortes': {'temas': [], 'temas_outros': False}})
buscas.clear()
v = ag.proximo_video('Minecraft')
confere(v and v['id'] == 'bbbbbbbbbbb' and not v['fora_aprovados'], 'tema pedido na hora: canal aprovado tem prioridade', v)
ag._mudar(lambda e: e['vistos'].update(bbbbbbbbbbb={'t': 1, 'r': 'ok'}))
v = ag.proximo_video('elden ring')
confere(v and v['id'] == 'ccccccccccc' and v['fora_aprovados'] and buscas, 'tema pedido na hora busca no YouTube todo', v)
ag._mudar(lambda e: e['vistos'].update(ccccccccccc={'t': 1, 'r': 'ok'}))
confere('Não achei vídeo novo sobre "elden ring"' in ag.trabalhar_cortes(True, '', 'elden ring'), 'nada novo sobre o tema: avisa')

try:
    ag.rodar_agora('tema', ' ')
    confere(False, 'tema vazio é recusado')
except ag.ErroAgente:
    confere(True, 'tema vazio é recusado')

pedidos = []
ag.rodar_agora = lambda oque, link='': pedidos.append((oque, link))
r = cm.responder('corta um vídeo sobre Elden Ring pra mim', 'w')
confere(pedidos == [('tema', 'Elden Ring')], 'WhatsApp: "corta um vídeo sobre Elden Ring" manda o Agente 1 buscar o tema', f'{pedidos} {r}')
pedidos.clear()
cm.responder('cortar sobre minecraft survival', 'w')
confere(pedidos == [('tema', 'minecraft survival')], 'WhatsApp: "cortar sobre ..."', pedidos)

print('\nTUDO OK' if not falhas else f'\n{falhas} FALHA(S)')
sys.exit(1 if falhas else 0)
