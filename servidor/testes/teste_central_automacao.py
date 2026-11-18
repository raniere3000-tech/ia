"""Central de Automação: estoque decide quando o Agente 1 corta, linhas de conteúdo do Agente 3 (pautas sem repetir, lote de N
episódios independentes, modo contínuo), simulação sem efeito, pausa, e vídeo da linha entrando na programação do Agente 2.

Rodar: cd servidor && PYTHONPATH=. python3 testes/teste_central_automacao.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-central-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
os.environ.pop('PIPELINE_V2', None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import banco as db  # noqa: E402
import agente as ag  # noqa: E402
import postagem as pg  # noqa: E402
import pipeline as pl  # noqa: E402
import projetos as pj  # noqa: E402
import agenda_postagem as a2  # noqa: E402
import linhas_conteudo as lc  # noqa: E402
import orquestrador as oq  # noqa: E402
import rotas_esteira as rt  # noqa: E402

db.migrar()
pg.acordar = lambda: None
ag.enviar_email = lambda *a, **k: 'mid'
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
    except (lc.ErroLinha, oq.ErroAutomacao, rt.ErroRota) as e:
        return e
    return None


def rota(metodo, caminho, corpo=None, q=None):
    return rt.tratar(metodo, caminho, q or {}, lambda: corpo or {}, 'teste')


def contar_tudo():
    tabs = ('kv', 'automacao_eventos', 'jobs', 'conteudo_pautas', 'conteudo_episodios', 'conteudo_lotes', 'projetos', 'eventos', 'posting_slots')
    return {t: db.um(f'SELECT COUNT(*) n FROM {t}')['n'] for t in tabs} | {'kv_txt': json.dumps(db.todos('SELECT * FROM kv ORDER BY chave'))}


print('1. Regra do estoque (função pura, com histerese)')
cfg = oq.config()
est = lambda n, taxa=0.6: {'disponiveis': n, 'efetivo': n, 'taxa_aprovacao': taxa}  # noqa: E731
agora = time.time()
d = oq.decidir_cortes(cfg, est(21), False, agora, 0, 0)
check(d['acao'] == 'nada', 'estoque 21 (alvo 21): não procura nem corta')
d = oq.decidir_cortes(cfg, est(15), False, agora, 0, 0)
check(d['acao'] == 'nada' and not d['repondo'], 'estoque 15, acima do mínimo 9 e sem reposição em curso: continua parado')
d = oq.decidir_cortes(cfg, est(8), False, agora, 0, agora)
check(d['acao'] == 'cortar' and d['repondo'] and d['quantos'] == 22, 'estoque 8 < mínimo 9: corta (13 faltando / 60% de aprovação = 22)')
d = oq.decidir_cortes(cfg, est(15), True, agora, 0, agora)
check(d['acao'] == 'cortar', 'histerese: já repondo, com 15 ainda segue até o alvo 21')
d = oq.decidir_cortes(cfg, est(8), False, agora, agora - 60, agora)
check(d['acao'] == 'esperar', 'intervalo entre rodadas respeitado (última rodada há 1 min)')
d = oq.decidir_cortes(cfg, est(8), False, agora, 0, 0)
check(d['acao'] == 'buscar_canais', 'estoque baixo e busca velha: primeiro procura canais')

print('2. Configuração da central')
check(oq.config()['estado'] == 'desligada' and oq.decisao_cortes() is None, 'padrão: desligada, Agente 1 segue a meta semanal antiga')
check(erro(oq.salvar, {'cortes': {'minimo': 10, 'alvo': 10}}) is not None, 'alvo igual ao mínimo é recusado')
c1 = oq.salvar({'modo': 'economico'}, 0, 'teste')
check(c1['cortes']['minimo'] == 5 and c1['cortes']['alvo'] == 10 and c1['versao'] == 1, 'modo econômico preenche números visíveis')
check(erro(oq.salvar, {'cortes': {'minimo': 3}}, 0) is not None and erro(oq.salvar, {'cortes': {'minimo': 3}}, 0).status == 409, 'versão velha dá conflito')
c2 = oq.salvar({'cortes': {'minimo': 9, 'alvo': 21}}, 1, 'teste')
check(c2['modo'] == 'personalizado', 'mexer nos números vira "personalizado"')

print('3. Agente 1 obedece ao estoque')
base = dict(gancho='', hashtags=[], motivo='m', nota=80, ini=0, fim=4, post='', origem='', origem_titulo='', canal='', canal_nome='', variacoes=[],
            fala='site', tamanho=1, email=False, tipo='manual', direitos={'origem': 'meu', 'nota': ''}, qa={'diretor': {'aprovado': True}}, video='x')
ag._mudar(lambda e: e['cortes'].extend([dict(base, id=f'c{i}', titulo=f'C{i}', chave=f'k{i}', criado=time.time(), status='pronto') for i in range(21)]))
oq.salvar({'estado': 'ativa'}, None, 'teste')
chamadas = []
ag._em_fundo = lambda nome, f, *a: chamadas.append(nome)
ag.segredos = lambda: {'youtube': 'x', 'gemini': 'x', 'gemini_pago': ''}
for nome in ('acompanhar', 'limpar', 'relatorio_semana', 'aprender', 'trabalhar_postagem'):
    setattr(ag, nome, lambda *a, **k: None)
ag.salvar_config({'cortes': {'ligado': True, 'hora_ini': 0, 'hora_fim': 0}})
ag._mudar(lambda e: e['marcas'].update(busca=time.time(), tentativa=0))
ag.passo()
check(chamadas == [], 'com 21 cortes aprovados (alvo 21) o Agente 1 não procura nem corta')
ag._mudar(lambda e: [x.update(status='postado') for x in e['cortes'] if int(x['id'][1:]) >= 8])
ag.passo()
check(chamadas == ['Agente de cortes'], 'caiu para 8 (< mínimo 9): o Agente 1 volta a cortar')
ag.passo()
check(chamadas == ['Agente de cortes'], 'logo depois não corta de novo (intervalo entre rodadas)')
ev = oq.eventos(20, 'agente1')
check(any(e['decisao'] == 'cortar' for e in ev) and any(e['decisao'] == 'nada' for e in ev), 'histórico guarda só as mudanças de decisão, com o motivo')
n_ev = len(oq.eventos(500))
ag.passo()
check(len(oq.eventos(500)) == n_ev, 'decisão repetida não enche o histórico')
oq.pausar('teste')
check(oq.decisao_cortes()['acao'] == 'nada', 'pausada: o Agente 1 não começa nada')
oq.retomar('teste')

print('4. Linhas de conteúdo: validação')
L = {'titulo': 'Curiosidades Científicas', 'tema': 'ciência do dia a dia', 'quantidade_lote': 6, 'estilo': 'documentario', 'modo_pautas': 'supervisionado'}
check('não roda' in str(erro(lc.criar, dict(L, estilo='mapas_animados'))), 'estilo indisponível é recusado com o motivo')
check('beta' in str(erro(lc.criar, dict(L, estilo='animado2d'))), 'estilo beta pede confirmação')
check(erro(lc.criar, dict(L, estilo='animado2d', confirmar_beta=True)) is None, 'estilo beta confirmado é aceito')
check('personagem' in str(erro(lc.criar, dict(L, personagens={'modo': 'fixo', 'descricao': 'um gato curioso de óculos'}))).lower(),
      'personagem com estilo sem animação é recusado')
check(erro(lc.criar, dict(L, estilo='nao_existe')) is not None, 'estilo fora do catálogo é recusado')
check(erro(lc.criar, dict(L, publicacao='automatica')) is not None, 'publicação automática sem rede é recusada')
linha = lc.criar(dict(L, travas=['estilo']), 'teste')
lid = linha['id']
check(linha['quantidade_lote'] == 6 and linha['estado'] == 'ativa', 'linha criada')
lc.atualizar(lid, {'estilo': 'quadrinhos', 'duracao_seg': 60, '_sugestao': True}, 'teste')
x = lc.obter(lid)
check(x['estilo'] == 'documentario' and x['duracao_seg'] == 60, 'sugestão automática não mexe no campo travado (estilo), mas muda o resto')
check(erro(lc.atualizar, lid, {'versao': 1, 'tom': 'leve'}) is not None, 'versão velha da linha dá conflito')

print('5. Pautas sem repetir')


def ia_falsa(prompt):
    return {'pautas': [
        {'titulo': 'Por que o céu é azul', 'resumo': 'luz do sol espalhada', 'classificacao': 'fato', 'fontes': [{'url': 'https://exemplo.org/ceu'}]},
        {'titulo': 'Por que o céu fica azul', 'resumo': 'luz do sol espalhada', 'classificacao': 'fato', 'fontes': []},
        {'titulo': 'Como o micro-ondas esquenta comida', 'resumo': 'água vibra', 'classificacao': 'entretenimento'},
        {'titulo': 'O que faz o pão crescer', 'resumo': 'fermento e gás', 'classificacao': 'entretenimento'},
        {'titulo': 'Por que a cebola faz chorar', 'resumo': 'gás irritante', 'classificacao': 'entretenimento'},
        {'titulo': 'Como funciona o ímã de geladeira', 'resumo': 'campo magnético', 'classificacao': 'entretenimento'},
        {'titulo': 'Por que o gelo boia', 'resumo': 'densidade da água', 'classificacao': 'entretenimento'},
        {'titulo': 'Horóscopo de amanhã', 'resumo': 'signos', 'classificacao': 'entretenimento'},
    ]}


lc._fonte_abre = lambda url: True
lc.atualizar(lid, {'excluir': ['horóscopo']}, 'teste')
r = lc.planejar_pautas(lid, 6, ia=ia_falsa)
tit = [p['titulo'] for p in r['pautas']]
check(len(r['pautas']) == 6 and 'Por que o céu fica azul' not in tit, 'pauta quase igual a outra do mesmo lote cai como repetida')
check('Horóscopo de amanhã' not in tit, 'assunto excluído não entra')
check(all(p['status'] == 'proposta' for p in r['pautas']), 'modo supervisionado: pautas ficam como propostas para você')
ceu = next(p for p in r['pautas'] if p['titulo'] == 'Por que o céu é azul')
check(ceu['verificacao'].startswith('fonte encontrada') and 'não foi conferido' in ceu['verificacao'], 'fato com fonte: diz que a fonte abre, sem fingir que conferiu o texto')
r2 = lc.planejar_pautas(lid, 6, ia=ia_falsa)
check(len(r2['pautas']) == 0 and r2['aviso'], 'planejar de novo não repete nenhuma pauta já proposta')
rr = lc.escrever_pautas(lid, ['Por que o céu é azul', 'Como o arco-íris se forma'])
check(len(rr['pautas']) == 1 and len(rr['repetidas']) == 1, 'pauta escrita por você também é conferida contra repetição')
check(erro(lc.iniciar_lote, lid, 6, produzir=lambda *a: None) is None, 'há 1 pauta aceita (a sua): começa 1')
for p in lc.pautas(lid):
    if p['status'] == 'proposta':
        rota('PATCH', f'/api/v1/linhas-conteudo/pautas/{p["id"]}', {'acao': 'aceitar'})

print('6. Lote de N episódios independentes')
produzidos = []
lc.atualizar(lid, {'limite_dia': 12}, 'teste')
r = lc.iniciar_lote(lid, 6, 'teste', produzir=lambda pid, chave: produzidos.append((pid, chave)))
eps = r['episodios']
check(len(eps) == 6 and len({e['projeto'] for e in eps}) == 6 and len({e['episodio'] for e in eps}) == 6, 'lote de 6 = 6 projetos e 6 episódios com ids diferentes')
check(len({e['titulo'] for e in eps}) == 6, 'cada episódio tem a sua pauta (nenhuma repetida)')
check(len(produzidos) == 6 and all(c.startswith('linha:ep_') for _, c in produzidos), 'cada episódio entra na produção com chave própria')
p0 = pj.obter(eps[0]['projeto'])
check(p0['dados']['linha']['id'] == lid and p0['dados']['briefing']['destinos']['redes'] == [], 'projeto sabe de que linha veio e não posta sozinho')
check(erro(lc.iniciar_lote, lid, 6, produzir=lambda *a: None) is not None, 'sem pauta aceita sobrando: não inventa vídeo')
check(all(x['status'] == 'usada' for x in lc.pautas(lid) if x['titulo'] in {e['titulo'] for e in eps}), 'pautas usadas não voltam')
lc.atualizar(lid, {'limite_dia': 7}, 'teste')
lc.escrever_pautas(lid, ['Por que o mar é salgado'])
check(erro(lc.iniciar_lote, lid, 1, produzir=lambda *a: None) is not None, 'limite por dia (7) respeitado')

print('7. Simulação não grava nada')
antes = contar_tudo()
s = rota('POST', '/api/v1/automacao/simular')
check(contar_tudo() == antes, 'simular não muda nenhuma tabela')
check(s['cortes']['decisao']['acao'] in ('cortar', 'esperar', 'nada', 'buscar_canais') and isinstance(s['linhas'], list), 'simulação traz decisão e motivo de cada agente')

print('8. Linha em modo contínuo')
l2 = lc.criar({'titulo': 'Fatos de bichos', 'tema': 'animais curiosos', 'quantidade_lote': 3, 'modo_pautas': 'automatico', 'modo_execucao': 'continuo',
               'estoque': {'minimo': 2, 'alvo': 4}, 'limite_dia': 12}, 'teste')
bichos = [{'titulo': t, 'resumo': t, 'classificacao': 'entretenimento'} for t in
          ('Polvo tem três corações', 'Coruja gira a cabeça', 'Formiga carrega peso', 'Girafa dorme pouco', 'Golfinho dá nome aos outros', 'Camelo guarda gordura')]
feitos = []
res = oq.ciclo(ia=lambda p: {'pautas': bichos}, produzir=lambda pid, ch: feitos.append(pid), em_fundo=False)
check(l2['id'] in res['lotes'] and len(feitos) == 3, 'estoque 0 < mínimo 2: planeja pautas e começa um lote de 3')
check(lc.estoque(l2['id'])['em_producao'] == 3, 'os 3 contam como "em produção"')
db.kv_gravar('automacao_mem', dict(oq._mem(), ultimo={}))      # sem esperar o intervalo
feitos.clear()
oq.ciclo(ia=lambda p: {'pautas': bichos}, produzir=lambda pid, ch: feitos.append(pid), em_fundo=False)
check(len(feitos) == 1, 'histerese: 3 em produção, alvo 4 -> começa só 1 a mais')
db.kv_gravar('automacao_mem', dict(oq._mem(), ultimo={}))
feitos.clear()
oq.ciclo(ia=lambda p: {'pautas': bichos}, produzir=lambda pid, ch: feitos.append(pid), em_fundo=False)
check(feitos == [], 'chegou no alvo (4): para de produzir')
oq.pausar('teste')
db.kv_gravar('automacao_mem', dict(oq._mem(), ultimo={}))
check(oq.ciclo(em_fundo=False) == {'ativa': False}, 'pausada: o ciclo não faz nada')
oq.retomar('teste')

print('9. Vídeo aprovado da linha entra na programação diária (1 vídeo, 2 redes)')
pl.ligar(True, 'teste')
l3 = lc.criar({'titulo': 'Linha publicada', 'tema': 'teste de agenda', 'publicacao': 'automatica', 'agenda': {'redes': ['youtube', 'instagram']}}, 'teste')
lc.escrever_pautas(l3['id'], ['Um vídeo de teste da agenda'])
ep = lc.iniciar_lote(l3['id'], 1, 'teste', produzir=lambda *a: None)['episodios'][0]
arq = TMP / 'render.mp4'
subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=720x1280:d=3:r=30', '-f', 'lavfi', '-i', 'sine=f=300:d=3',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(arq)], check=True)
sha = pl.sha_arquivo(arq)
db.executar('INSERT INTO renders (id, projeto, versao, arquivo, sha256, duracao, codec, largura, altura, validado, alertas, criado) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            'r1', ep['projeto'], 1, str(arq), sha, 3, 'h264', 720, 1280, 1, '[]', time.time())
pj.mudar_dados(ep['projeto'], lambda d, _p: (d.update(render={'sha': sha, 'validado': True}), {'status': 'ready_for_review'})[1])
check(lc.aprovar_automaticos() == 0, 'sem certificado do diretor: a publicação automática não aprova')
pl.emitir_certificado(ep['projeto'], sha, {'score': 82, 'blocking_findings': []})
check(lc.aprovar_automaticos() == 1 and pj.obter(ep['projeto'])['status'] == 'approved', 'com certificado: aprovado pela automação (registrado como automação)')
check(lc.estoque(l3['id'])['livres'] == 1, 'vídeo aprovado conta no estoque da linha')
for rede in ('youtube', 'instagram'):
    rota('POST', '/api/v1/agent2/schedules', {'platform': rede, 'mode': 'fixed', 'fixed_times': ['09:00', '15:00', '21:00']})
r = a2.ciclo()
sl = db.todos("SELECT * FROM posting_slots WHERE ref=? AND estado='agendado'", 'p:' + ep['projeto'])
check(len(sl) == 2 and {x['rede'] for x in sl} == {'youtube', 'instagram'}, 'um vídeo, duas redes: dois horários, um por rede')
check(db.um('SELECT COUNT(*) n FROM publicacoes WHERE render_sha=?', sha)['n'] == 2, 'duas publicações registradas (uma por rede)')
check(a2.ciclo()['agendados'] == 0, 'rodar de novo não repete o vídeo na mesma rede')
post = next(p for p in pg.posts() if p['id'] == sl[0]['post'])
check(post['origem'] == 'agente3' and post['render_sha'] == sha and post['projeto'] == ep['projeto'], 'post leva o projeto e o SHA aprovado')
rota('PATCH', f'/api/v1/agent2/slots/{sl[0]["id"]}', {'acao': 'cancelar'})
check(db.um('SELECT COUNT(*) n FROM publicacoes WHERE render_sha=? AND rede=?', sha, sl[0]['rede'])['n'] == 0,
      'cancelar o horário devolve o vídeo para aquela rede')

print('10. Painel e rotas')
res = rota('GET', '/api/v1/automacao/resumo')
check({'estoque_cortes', 'rodando', 'esperando_voce', 'falhas_24h', 'revisao_manual'} <= set(res['indicadores']) and res['proximas'], 'resumo com indicadores e próximas postagens')
check(isinstance(rota('GET', '/api/v1/automacao/sugestoes')['sugestoes'], list), 'sugestões por regra')
n_linhas = len(rota('GET', '/api/v1/linhas-conteudo')['linhas'])
check(n_linhas == db.um("SELECT COUNT(*) n FROM linhas_conteudo")['n'] and n_linhas >= 3, 'lista de linhas')
check(rota('POST', f'/api/v1/linhas-conteudo/{lid}/pausar')['estado'] == 'pausada', 'pausar uma linha')
check(erro(lc.iniciar_lote, lid, 1, produzir=lambda *a: None) is not None, 'linha pausada não começa lote')
rota('DELETE', f'/api/v1/linhas-conteudo/{l2["id"]}')
check(len(rota('GET', '/api/v1/linhas-conteudo')['linhas']) == n_linhas - 1, 'apagar some da lista')

print(f'\n{ok} ok, {falhas} falha(s)')
sys.exit(1 if falhas else 0)
