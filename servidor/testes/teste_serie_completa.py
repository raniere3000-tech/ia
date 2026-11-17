"""Série completa com IA: tema + explicação -> série, elenco (principais e extras), cenários e N episódios com roteiro.

Rodar:  python servidor/testes/teste_serie_completa.py
Sem internet: o Gemini é simulado. Nada é produzido nem postado (só rascunhos).
"""
import json
import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='serie-completa-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agente as ag  # noqa: E402
import banco as db  # noqa: E402
import api_v1  # noqa: E402
import criativo as cri  # noqa: E402
import fila  # noqa: E402
import produtor  # noqa: E402
import projetos as pj  # noqa: E402
import series as srs  # noqa: E402

falhas = 0


def confere(c, nome):
    global falhas
    print(('ok    ' if c else 'FALHA ') + nome)
    falhas += 0 if c else 1


class H:
    def __init__(self, caminho, corpo=None):
        self.path = caminho
        self.corpo = json.dumps(corpo or {}).encode()
        self.headers = {}


def api(metodo, caminho, corpo=None):
    return api_v1.tratar(H(caminho, corpo), metodo, caminho.split('?')[0], {'nome': 'teste', 'id': 's1'})


def erro(f):
    try:
        f()
    except Exception as e:  # noqa: BLE001
        return getattr(e, 'status', 0), str(e)
    return 0, ''


db.migrar()
api_v1.iniciar()
produtor.iniciar()
SEG = {'gemini': '', 'gemini_pago': ''}
ag.segredos = lambda: dict(SEG)

st, msg = erro(lambda: api('POST', '/api/v1/criativo/serie-completa', {'tema': 'Robôs'}))
confere(st == 409 and 'chave do Gemini' in msg, 'sem chave do Gemini: avisa (não inventa série)')
SEG['gemini'] = 'x'
st, _ = erro(lambda: api('POST', '/api/v1/criativo/serie-completa', {'tema': ''}))
confere(st == 400, 'sem tema: pede o tema')

PROMPTS = []
FALHAR_EP = {'n': 0}


def gemini_falso(partes, **k):
    t = partes[0]['text']
    PROMPTS.append(t)
    if 'roteirista de séries animadas' in t:
        return {'titulo': 'Os Guardiões do Bairro', 'premissa': 'Três amigos protegem o bairro de um mistério.', 'genero': 'aventura', 'tom': 'divertido',
                'regras_mundo': ['Ninguém sabe que eles são guardiões'], 'hashtags': ['#serie', '#animacao'],
                'personagens': [{'nome': 'Bia', 'papel': 'principal', 'descricao': 'inventora', 'roupa': '#22aa55'},
                                {'nome': 'Zeca', 'papel': 'principal', 'descricao': 'atrapalhado'},
                                {'nome': 'Lia', 'papel': 'principal', 'descricao': 'detetive'},
                                {'nome': 'Seu Juca', 'papel': 'extra', 'descricao': 'dono da padaria'},
                                {'nome': 'Dona Rosa', 'papel': 'extra', 'descricao': 'vizinha'},
                                {'nome': 'Sobra', 'papel': 'extra', 'descricao': 'não pedido'}],
                'cenarios': [{'nome': 'Praça', 'tipo': 'parque', 'horario': 'tarde'}, {'nome': 'Padaria', 'tipo': 'casa'}],
                'episodios': [{'titulo': f'Ep {i}', 'resumo': f'No episódio {i} o mistério avança com uma virada.', 'personagens': ['Bia', 'Zeca'], 'cenario': 'Praça'}
                              for i in range(1, 7)]}
    if FALHAR_EP['n'] and len([x for x in PROMPTS if 'roteirista de séries animadas' not in x]) == FALHAR_EP['n']:
        raise RuntimeError('Gemini caiu (teste)')
    return {'titulo': 'Episódio', 'legenda': 'L', 'hashtags': [], 'cenas': [
        {'titulo': 'Gancho', 'texto': 'Bia vê algo estranho na praça.', 'personagem': 'bia'},
        {'titulo': 'Virada', 'texto': 'Zeca tropeça e descobre a pista.', 'personagem': 'zeca'},
        {'titulo': 'Final', 'texto': 'E agora, quem estava lá?'}]}


ag.gemini = gemini_falso
r = api('POST', '/api/v1/criativo/serie-completa', {'tema': 'Guardiões do bairro', 'explicacao': 'Quero que no fim descubram que o padeiro é o vilão.',
                                                     'episodios': 5, 'principais': 3, 'extras': 2, 'dur_min': 60, 'dur_max': 90, 'chave': 'k1'})
j = fila.obter(r['job'])
confere(j and j['tipo'] == 'criativo.serie_completa', 'pedido vira trabalho na fila (não trava a tela)')
r2 = api('POST', '/api/v1/criativo/serie-completa', {'tema': 'Guardiões do bairro', 'explicacao': 'Quero que no fim descubram que o padeiro é o vilão.',
                                                      'episodios': 5, 'principais': 3, 'extras': 2, 'dur_min': 60, 'dur_max': 90, 'chave': 'k1'})
confere(r2['job'] == r['job'], 'duplo toque não cria duas séries')


class Ctx:
    def __init__(self, dados):
        self.dados = dados
        self.etapas = []

    def progresso(self, pct=None, etapa=None):
        self.etapas.append((pct, etapa))


ctx = Ctx(json.loads(j['dados']))
FALHAR_EP['n'] = 3
st, _ = erro(lambda: cri.job_serie_completa(ctx))
confere(st == 0 and len(ctx.dados['episodios']) == 3 and [e['roteiro'] for e in ctx.dados['episodios']] == [True, True, False], 'IA caiu no episódio 3: guarda o que já fez')
FALHAR_EP['n'] = 0
res = cri.job_serie_completa(ctx)
sid = res['resultado']['serie_id']
s = srs.obter(sid)
eps = srs.listar_episodios(sid)
confere(len([x for x in srs.listar_series() if x['id'] == sid] if hasattr(srs, 'listar_series') else srs.listar()) >= 1 and len(eps) == 5, 'nova tentativa continua: 5 episódios, sem repetir')
confere(len(s['personagens']) == 5 and sum('Extra' in p['dados'].get('descricao', '') for p in s['personagens']) == 2, '3 principais e 2 extras (o que passou do pedido fica de fora)')
confere(len(s['cenarios']) == 2, 'cenários criados')
confere('padeiro é o vilão' in s['regras'] and s['duracao_alvo'] == 75, 'pedido original guardado nas regras; duração entre 60 e 90 s')
ps = [pj.obter(e['projeto_id']) for e in eps]
confere(all(p['status'] == 'storyboard_ready' and len(p['dados']['cenas']) == 3 for p in ps), 'cada episódio já tem roteiro (cenas) pronto para revisar')
confere(all(p['dados']['serie']['serie_id'] == sid for p in ps), 'episódios usam o elenco da série')
confere(not db.um("SELECT id FROM jobs WHERE tipo='agente3.produzir'"), 'nada foi produzido nem postado')
ep_prompts = [x for x in PROMPTS if 'roteirista de séries animadas' not in x]
confere(any('Bia' in x for x in ep_prompts) and any('No episódio 4' in x for x in ep_prompts), 'roteiro de cada episódio escrito com o resumo dele e o elenco')
confere(ctx.etapas[-1][1] == 'Série pronta para revisar', 'progresso mostra quando terminou')
confere('5 episódio(s)' in PROMPTS[0] and '60 a 90 segundos' in PROMPTS[0] and '3 personagem(ns) principal(is) e 2 extra(s)' in PROMPTS[0], 'pedido à IA tem quantidade, duração e elenco escolhidos')
c = cri._pedido_serie({'tema': 'x', 'episodios': 50, 'principais': 9, 'extras': 9, 'dur_min': 5, 'dur_max': 999})
confere(c['episodios'] == 12 and c['principais'] == 4 and c['extras'] == 4 and c['dur_min'] == 30 and c['dur_max'] == 180, 'limites: até 12 episódios, 4+4 personagens, 30 a 180 s')

print('\n' + ('TUDO OK' if not falhas else f'{falhas} FALHA(S)'))
sys.exit(1 if falhas else 0)
