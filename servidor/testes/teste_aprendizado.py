"""Aprendizado dos agentes: retratos sem edição, importação CSV/JSON, "dados insuficientes", pesos com versão e desfazer, apagar tira o efeito,
teste A/B de uma variável, e nada disso mexe na frequência de postagem.

Rodar: cd servidor && PYTHONPATH=. python3 testes/teste_aprendizado.py
"""
import json
import os
import random
import sys
import tempfile
from collections import Counter
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-apr-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import banco as db  # noqa: E402
import agente as ag  # noqa: E402
import aprendizado as ap  # noqa: E402

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


def erro(f, *a, **k):
    try:
        f(*a, **k)
    except ap.ErroAprendizado as e:
        return e
    return None


post_antes = json.dumps(ag.config()['postagem'], sort_keys=True)
print('Painel vazio')
p = ap.painel()
check(p['retratos'] == 0 and all(v['estado'] == 'dados insuficientes' for v in p['variaveis']), 'sem dados: todas as variáveis dizem "dados insuficientes"')
check('não o motivo' in p['aviso_causa'] and 'só seu' in p['aviso_frequencia'], 'o painel diz que não é causa e que a frequência é sua')
check(erro(ap.aplicar, 'estilo').codigo == 409, 'não aplica peso sem dados')

print('Importação')
linhas = ['rede,id,data,views,curtidas,estilo,modelo,duracao,gancho']
for i in range(6):
    linhas.append(f'youtube,n{i},2026-11-0{i + 1},{1200 + i * 50},30,neon,T1,{25 + i},Você sabia disso?')
    linhas.append(f'youtube,v{i},2026-11-0{i + 1},{500 + i * 20},10,vhs,T1,{40 + i},Isso mudou tudo')
linhas += ['tiktok,ruim1,2026-11-01,-5,1,neon,T1,30,x', 'orkut,ruim2,2026-11-01,10,1,neon,T1,30,x', 'youtube,ruim3,,10,1,neon,T1,30,x', 'youtube,ruim4,2026-11-01,,,neon,T1,30,x']
r = ap.importar('teste.csv', 'csv', '\n'.join(linhas))
check(r['aceitas'] == 12 and r['total_recusadas'] == 4, f'12 linhas aceitas e 4 recusadas ({r["aceitas"]}/{r["total_recusadas"]})')
check({x['linha'] for x in r['recusadas']} == {14, 15, 16, 17} and all(x['motivo'] for x in r['recusadas']), 'cada recusada diz a linha e o motivo')
r2 = ap.importar('teste.csv', 'csv', '\n'.join(linhas))
check(r2['aceitas'] == 0 and r2['repetidas'] == 12 and not r2['importacao'], 'importar o mesmo arquivo de novo não duplica')
n_ret = db.um('SELECT COUNT(*) n FROM aprendizado_snapshots')['n']
check(n_ret == 12, f'12 retratos guardados, sem duplicar ({n_ret})')
check(erro(ap.importar, 'x', 'csv', '').codigo == 400 and erro(ap.importar, 'x', 'xml', 'a').codigo == 400, 'vazio e formato errado são recusados')
check(erro(ap.importar, 'x', 'json', '{ruim').codigo == 400, 'JSON quebrado é recusado')
check(erro(ap.importar, 'x', 'csv', 'a' * 1_100_000).codigo == 400, 'arquivo acima de 1 MB é recusado')
s = db.um('SELECT * FROM aprendizado_snapshots LIMIT 1')
check(s['fonte'] == 'importado' and s['rede'] == 'youtube' and s['periodo_ini'] and s['importacao_id'], 'retrato guarda fonte, rede e período')

print('Leitura honesta')
a = ap.analisar('estilo')
check(a['estado'] == 'tendência' and a['melhor'] == 'neon', 'estilo: neon na frente com amostra suficiente')
check('não o motivo' in a['mensagem'] and 'causou' not in a['mensagem'].lower() and 'causa' not in a['mensagem'].lower().replace('não o motivo', ''), 'a mensagem nunca afirma causa')
check(ap.analisar('modelo')['estado'] == 'dados insuficientes', 'modelo: só um valor com amostra → dados insuficientes')
check(ap.analisar('gancho')['estado'] in ('tendência', 'sem diferença clara'), 'gancho (pergunta × afirmação) é lido')
check(ap.analisar('estilo', rede='tiktok')['estado'] == 'dados insuficientes', 'por rede sem dados → dados insuficientes')
check(ap.analisar('duracao')['valores'] and ap.faixa_duracao(25) == 'até 30 s' and ap.faixa_duracao(50) == '30 a 60 s', 'duração vira faixa')

print('Pesos com versão')
pc = ap.pesos_calculados('estilo')
check(pc['neon'] > pc['vhs'] and abs(sum(pc.values()) - 1) < 0.01 and min(pc.values()) >= 0.14, f'pesos favorecem o melhor, com piso de variedade ({pc})')
check(erro(ap.aplicar, 'gancho').codigo == 409, 'variável sem sorteio só é lida, não recebe peso')
ap.aplicar('estilo')
rnd = random.Random(7)
cont = Counter(ap.sortear_estilo(['neon', 'vhs'], rnd) for _ in range(2000))
check(cont['neon'] > cont['vhs'] * 1.2, f'o sorteio de estilo passa a favorecer neon ({dict(cont)})')
check(cont['vhs'] > 300, 'o estilo pior continua saindo (variedade)')
ap.aplicar('estilo')
v = db.todos("SELECT versao, ativo, anterior FROM aprendizado_pesos WHERE variavel='estilo' ORDER BY versao")
check(len(v) == 2 and v[0]['ativo'] == 0 and v[1]['ativo'] == 1 and v[1]['anterior'] == v[0]['versao'], 'cada aplicação é uma versão nova ligada à anterior')
ap.desfazer('estilo')
check(db.um("SELECT ativo FROM aprendizado_pesos WHERE versao=?", v[0]['versao'])['ativo'] == 1, 'desfazer volta à versão anterior')
ap.desfazer('estilo')
check(not ap.pesos_ativos('estilo') and erro(ap.desfazer, 'estilo').codigo == 409, 'desfazer de novo volta ao sorteio igual')
rnd = random.Random(3)
cont = Counter(ap.sortear_estilo(['neon', 'vhs'], rnd) for _ in range(2000))
check(abs(cont['neon'] - 1000) < 150, f'sem pesos o sorteio é igual ({dict(cont)})')

print('Apagar dados tira o efeito')
ap.aplicar('estilo')
check(bool(ap.pesos_ativos('estilo')), 'pesos ligados antes de apagar')
apagou = ap.apagar({'alvo': 'importacao', 'id': r['importacao']})
check(apagou['apagados'] == 12 and not ap.pesos_ativos('estilo') and 'estilo' in apagou['pesos_desligados'], 'apagar a importação desliga os pesos que dependiam dela')
check(db.um('SELECT COUNT(*) n FROM aprendizado_snapshots')['n'] == 0 and ap.painel()['retratos'] == 0, 'os retratos sumiram')
check(erro(ap.apagar, {'alvo': 'importacao', 'id': 'nao-existe'}).codigo == 404 and erro(ap.apagar, {'alvo': '?'}).codigo == 400, 'apagar algo que não existe ou sem dizer o quê é recusado')

print('JSON e captura das redes')
itens = [{'rede': 'instagram', 'id': f'j{i}', 'data': '2026-11-02', 'views': 300 + i, 'estilo': 'glow', 'perfil': 'canal A'} for i in range(5)] + \
        [{'rede': 'instagram', 'id': f'k{i}', 'data': '2026-11-02', 'curtidas': 20, 'comentarios': 3, 'estilo': 'sepia', 'perfil': 'canal A'} for i in range(5)]
rj = ap.importar('j.json', 'json', json.dumps(itens))
check(rj['aceitas'] == 10, 'JSON em lista é aceito (curtidas+comentários quando não há views)')
ap.apagar({'alvo': 'tudo'})
cortes = [{'id': 'c%d' % i, 'status': 'postado', 'medido': True, 'estilo_visual': 'neon' if i % 2 else 'vhs', 'modelo': 'T1', 'modelo_nome': 'Template um', 'faixa': 'seg-18',
           'ini': 10.0, 'fim': 55.0, 'gancho': 'E se fosse você?', 'postado': 1790000000 + i, 'metricas': {'youtube': {'views': 100 * (i + 1), 'curtidas': 5, 'comentarios': 1}}} for i in range(6)]
ag._mudar(lambda e: e['cortes'].extend(cortes))
cp = ap.capturar()
check(cp['novos'] == 6 and ap.capturar()['novos'] == 0, 'capturar guarda um retrato por corte medido e não repete')
sn = db.um("SELECT * FROM aprendizado_snapshots WHERE fonte='rede' LIMIT 1")
vv = json.loads(sn['variaveis'])
check(vv.get('estilo') in ('neon', 'vhs') and vv.get('duracao') == '30 a 60 s' and vv.get('gancho') == 'pergunta' and vv.get('faixa') == 'seg-18', f'variáveis do corte registradas ({vv})')
check(ap.painel()['fontes'] and ap.painel()['fontes'][0]['fonte'] == 'rede', 'o painel mostra fonte, rede e período')
ap.apagar({'alvo': 'tudo'})

print('Teste A/B')
check(erro(ap.criar_experimento, {'variavel': 'estilo', 'a': 'neon', 'b': 'neon'}) is not None, 'A e B iguais são recusados')
check(erro(ap.criar_experimento, {'variavel': 'estilo', 'a': 'neon', 'b': 'vhs', 'fixos': {'estilo': 'neon'}}) is not None, 'fixar a própria variável é recusado (uma por vez)')
check(erro(ap.criar_experimento, {'variavel': 'estilo', 'a': 'neon', 'b': 'vhs', 'fixos': {'xyz': '1'}}) is not None, 'fixar variável desconhecida é recusado')
ex = ap.criar_experimento({'variavel': 'estilo', 'a': 'neon', 'b': 'vhs', 'fixos': {'modelo': 'T1'}})
check(ex['resultado'] == 'dados insuficientes' and ex['status'] == 'ativo', 'sem vídeos medidos: dados insuficientes')
check(erro(ap.criar_experimento, {'variavel': 'duracao', 'a': 'x', 'b': 'y'}).codigo == 409, 'só um teste ativo por vez')
rnd = random.Random(1)
cont = Counter(ap.sortear_estilo(['neon', 'vhs', 'glow', 'sepia'], rnd) for _ in range(400))
check(set(cont) == {'neon', 'vhs'}, f'com teste de estilo ativo o Agente 1 só sorteia A ou B ({dict(cont)})')
ap.importar('mesmo.csv', 'csv', '\n'.join(['rede,id,data,views,estilo,modelo'] + [f'youtube,a{i},2026-11-02,{1000 + (i * 7) % 40},neon,T1' for i in range(6)] +
                                           [f'youtube,b{i},2026-11-02,{1000 + (i * 11) % 40},vhs,T1' for i in range(6)] + [f'youtube,c{i},2026-11-02,9999,vhs,OUTRO' for i in range(6)]))
e1 = ap.ler_experimento(ex['id'])
check(e1['lados']['a']['n'] == 6 and e1['lados']['b']['n'] == 6, 'só entram vídeos que combinam com os valores fixos (OUTRO ficou de fora)')
check(e1['resultado'] == 'inconclusivo' and 'não dá para dizer' in e1['mensagem'], f'diferença pequena → inconclusivo ({e1["resultado"]})')
ap.apagar({'alvo': 'tudo'})
ap.importar('forte.csv', 'csv', '\n'.join(['rede,id,data,views,estilo,modelo'] + [f'youtube,a{i},2026-11-02,{3000 + i * 10},neon,T1' for i in range(6)] +
                                           [f'youtube,b{i},2026-11-02,{500 + i * 10},vhs,T1' for i in range(6)]))
e2 = ap.ler_experimento(ex['id'])
check(e2['resultado'] == 'sinal a favor de A' and 'não o motivo' in e2['mensagem'], f'diferença grande → "sinal", com aviso de que não prova causa ({e2["resultado"]})')
en = ap.encerrar_experimento(ex['id'])
check(en['status'] == 'encerrado' and not ap.experimento_ativo(), 'encerrar libera um novo teste')

print('Garantias')
check(json.dumps(ag.config()['postagem'], sort_keys=True) == post_antes, 'nada aqui mexeu na frequência ou nos horários de postagem')
check(db.um("SELECT COUNT(*) n FROM eventos WHERE ator='aprendizado'")['n'] >= 8, 'cada ação ficou no registro (importar, aplicar, desfazer, apagar, teste)')
src = Path(ap.__file__).read_text(encoding='utf-8')
check('postagem' not in src.replace('frequência de postagem', '').replace('Nada aqui muda quantos posts', '') or 'pg.' not in src, 'o módulo não chama a postagem')
ap.apagar({'alvo': 'tudo'})
sk = ap.painel()['boas_praticas']
check(isinstance(sk, list), 'o painel lê as boas práticas das skills de aprendizado (lista, pode ficar vazia se não instaladas)')
print(f'\n{"TUDO OK" if not falhas else "COM FALHAS"} ({ok} ok, {falhas} falhas)')
sys.exit(1 if falhas else 0)
