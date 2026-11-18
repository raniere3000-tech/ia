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


PAGINA = ('<html><body><nav>menu</nav><p>O céu parece azul porque a luz do Sol é espalhada pelas moléculas do ar, e o azul se espalha mais '
          'do que o vermelho.</p>' + '<p>texto de enchimento da página da fonte.</p>' * 10 + '</body></html>')


def buscar_falso(url):
    import checagem_fatos as cf
    if 'ceu' in url:
        return {'ok': True, 'texto': cf.texto_da_pagina(PAGINA.encode(), 'text/html'), 'motivo': ''}
    return {'ok': False, 'texto': '', 'motivo': 'a página respondeu 404'}


def ia_falsa(prompt):
    if 'Você confere afirmações' in prompt:
        return {'itens': [{'n': 1, 'fonte': 1, 'trecho': 'a luz do Sol é espalhada pelas moléculas do ar, e o azul se espalha mais do que o vermelho'},
                          {'n': 2, 'fonte': 1, 'trecho': 'o céu de Marte é rosa segundo a NASA em 1976'}]}
    return {'pautas': [
        {'titulo': 'Por que o céu é azul', 'resumo': 'luz do sol espalhada', 'classificacao': 'fato', 'fontes': [{'url': 'https://exemplo.org/ceu'}],
         'afirmacoes': ['A luz azul se espalha mais no ar', 'O céu de Marte é rosa']},
        {'titulo': 'Por que o céu fica azul', 'resumo': 'luz do sol espalhada', 'classificacao': 'fato', 'fontes': []},
        {'titulo': 'Como o micro-ondas esquenta comida', 'resumo': 'água vibra', 'classificacao': 'entretenimento'},
        {'titulo': 'O que faz o pão crescer', 'resumo': 'fermento e gás', 'classificacao': 'entretenimento'},
        {'titulo': 'Por que a cebola faz chorar', 'resumo': 'gás irritante', 'classificacao': 'entretenimento'},
        {'titulo': 'Como funciona o ímã de geladeira', 'resumo': 'campo magnético', 'classificacao': 'entretenimento'},
        {'titulo': 'Por que o gelo boia', 'resumo': 'densidade da água', 'classificacao': 'entretenimento'},
        {'titulo': 'Horóscopo de amanhã', 'resumo': 'signos', 'classificacao': 'entretenimento'},
    ]}


lc.atualizar(lid, {'excluir': ['horóscopo']}, 'teste')
r = lc.planejar_pautas(lid, 6, ia=ia_falsa, buscar=buscar_falso)
tit = [p['titulo'] for p in r['pautas']]
check(len(r['pautas']) == 6 and 'Por que o céu fica azul' not in tit, 'pauta quase igual a outra do mesmo lote cai como repetida')
check('Horóscopo de amanhã' not in tit, 'assunto excluído não entra')
check(all(p['status'] == 'proposta' for p in r['pautas']), 'modo supervisionado: pautas ficam como propostas para você')
ceu = next(p for p in r['pautas'] if p['titulo'] == 'Por que o céu é azul')
cc = ceu['conferencia']
check(cc[0]['ok'] and cc[0]['trecho'] and not cc[1]['ok'] and ceu['verificacao'] == 'parcial',
      'checagem: afirmação com trecho achado no texto da fonte é confirmada; trecho que a IA inventou NÃO é')
check(lc._briefing(lc.obter(lid), ceu)['descricao'].count('NÃO foram confirmadas') == 1 and 'Marte' in lc._briefing(lc.obter(lid), ceu)['descricao'],
      'o roteiro recebe a lista do que não pode ser dito como fato')
import checagem_fatos as cf  # noqa: E402
saude = cf.conferir({'titulo': 'Chá cura gripe', 'classificacao': 'fato', 'afirmacoes': ['Chá de alho cura gripe'], 'fontes': []}, ia_falsa, buscar_falso)
check(saude['risco'] == 'alto' and saude['verificacao'] == 'não verificado' and not cf.pode_aceitar_sozinha(saude),
      'saúde sem fonte: risco alto, não verificado, nunca aceito sozinho')
r2 = lc.planejar_pautas(lid, 6, ia=ia_falsa, buscar=buscar_falso)
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

print('11. Linha a partir de uma descrição (a IA propõe, nada é gravado)')
DESCR = ('Quero uma linha de Curiosidades Científicas com 6 vídeos de 45 segundos, estilo Documentário, narração masculina, imagens de apoio, '
         'sem personagem, um vídeo por dia às 18:00 no YouTube.')


def ia_config(prompt):
    check('PEDIDO: Quero uma linha' in prompt and 'documentario = ' in prompt, 'a IA recebe o pedido e o catálogo REAL de estilos')
    return {'config': {'titulo': 'Curiosidades Científicas', 'tema': 'ciência', 'quantidade_lote': 6, 'duracao_seg': 45, 'estilo': 'documentario',
                       'voz': 'Charon', 'imagens': 'busca', 'personagens': {'modo': 'nenhum'},
                       'agenda': {'redes': ['youtube', 'tiktok'], 'horarios': ['18:00'], 'dias': [0, 1, 2, 3, 4, 5, 6]}},
            'duvidas': ['Não ficou claro o público.']}


n0 = db.um('SELECT COUNT(*) n FROM linhas_conteudo')['n']
sg = lc.sugerir_config(DESCR, ia=ia_config)
pr = sg['proposta']
check(pr['quantidade_lote'] == 6 and pr['duracao_seg'] == 45 and pr['estilo'] == 'documentario' and pr['voz'] == 'Charon' and pr['imagens'] == 'busca'
      and pr['agenda']['horarios'] == ['18:00'], 'proposta: 6 vídeos de 45 s, Documentário, voz masculina, imagens de apoio, 18:00')
check(db.um('SELECT COUNT(*) n FROM linhas_conteudo')['n'] == n0, 'sugerir não grava nada')
check(any(m['campo'] == 'agenda' for m in sg['mudancas']) and 'Não ficou claro o público.' in sg['avisos'], 'mostra o que muda e as dúvidas')
sg_beta = lc.sugerir_config(DESCR, ia=lambda p: {'config': {'titulo': 'X linha', 'tema': 'tema x', 'estilo': 'animado2d'}})
check(sg_beta['proposta']['estilo'] == 'documentario' and any('em teste' in a for a in sg_beta['avisos']), 'IA não escolhe estilo beta sozinha')
sg_ind = lc.sugerir_config(DESCR, ia=lambda p: {'config': {'titulo': 'X linha', 'tema': 'tema x', 'estilo': 'mapas_animados'}})
check(any('não roda' in a for a in sg_ind['avisos']), 'IA não escolhe estilo indisponível')
travada = lc.criar(dict(L, titulo='Linha travada', travas=['estilo', 'voz'], voz='Kore'), 'teste')
sg_t = lc.sugerir_config(DESCR + ' Use a voz Puck e estilo quadrinhos.', travada['id'], ia=lambda p: {'config': {'voz': 'Puck', 'estilo': 'quadrinhos', 'duracao_seg': 30}})
check(sg_t['proposta']['voz'] == 'Kore' and sg_t['proposta']['estilo'] == 'documentario' and sg_t['proposta']['duracao_seg'] == 30,
      'campos com cadeado não mudam; o resto muda')
check(erro(lc.sugerir_config, DESCR, ia=lambda p: {'config': {'titulo': 'Y', 'tema': 'z'}}) is not None, 'proposta que não passa nas regras é recusada com o motivo')
nova = rota('POST', '/api/v1/linhas-conteudo', pr)
ap = {x['rede']: x for x in nova['agenda_aplicada']}
yt = next(a for a in a2.listar() if a['platform'] == 'youtube')
tk = next((a for a in a2.listar() if a['platform'] == 'tiktok'), None)
check(ap['youtube']['ok'] and '18:00' in yt['weekly_rules']['0'] and '09:00' in yt['weekly_rules']['0'], 'YouTube: 18:00 somado aos horários que já existiam')
check(ap['tiktok']['ok'] and tk and tk['weekly_rules']['3'] == ['18:00'], 'TikTok sem programação: criada com 18:00 todos os dias')

print('12. Prioridade da linha e mover um horário')
c1 = {'criado': 1, 'nota': 90, 'prioridade': 3, 'ref': 'a'}
c2 = {'criado': 5, 'nota': 70, 'prioridade': 5, 'ref': 'b'}
check(a2.ordenar([c1, c2], 'oldest_approved')[0]['ref'] == 'b' and a2.ordenar([c1, c2], 'best_score')[0]['ref'] == 'b',
      'linha com prioridade maior ocupa o horário primeiro')
check(a2.ordenar([c1, dict(c2, prioridade=3)], 'best_score')[0]['ref'] == 'a', 'mesma prioridade: vale a regra da programação')
sv = db.um("SELECT * FROM posting_slots WHERE estado='vazio' AND rede='tiktok' AND quando_utc>? ORDER BY quando_utc LIMIT 1", time.time() + 86400)
mv = rota('PATCH', f'/api/v1/agent2/slots/{sv["id"]}', {'acao': 'mover', 'data_local': sv['data_local'], 'hora_local': '20:30'})
check(mv['hora_local'] == '20:30' and mv['tipo'] == 'movido', 'horário movido para 20:30 só naquele dia')
a2.reconciliar(sv['agenda'])
check(db.um('SELECT estado FROM posting_slots WHERE id=?', sv['id'])['estado'] == 'vazio' and
      db.um("SELECT COUNT(*) n FROM posting_slots WHERE rede='tiktok' AND data_local=? AND estado<>'cancelado'", sv['data_local'])['n'] == 1,
      'a programação não recria o horário antigo nem cancela o movido')
check(erro(rota, 'PATCH', f'/api/v1/agent2/slots/{sv["id"]}', {'acao': 'mover', 'data_local': sv['data_local'], 'hora_local': '99:00'}) is not None,
      'horário inválido é recusado')
outro = db.um("SELECT * FROM posting_slots WHERE rede='tiktok' AND id<>? AND estado='vazio' AND quando_utc>? ORDER BY quando_utc LIMIT 1", sv['id'], time.time() + 86400)
check('menos de' in str(erro(rota, 'PATCH', f'/api/v1/agent2/slots/{outro["id"]}', {'acao': 'mover', 'data_local': sv['data_local'], 'hora_local': '20:45'})),
      'mover para perto de outro horário da mesma rede é recusado')

print('13. Biblioteca Criativa (versões e cadeados)')
import biblioteca_criativa as bc  # noqa: E402
perfil = rota('POST', '/api/v1/biblioteca-criativa', {'tipo': 'perfil_narracao', 'nome': 'Narrador grave', 'dados': {'voz': 'Kore', 'ritmo': 'calmo'}, 'travas': ['voz']})
check(perfil['versao'] == 1 and perfil['dados']['voz'] == 'Kore', 'perfil de narração criado (versão 1)')
check(erro(rota, 'POST', '/api/v1/biblioteca-criativa', {'tipo': 'pacote_visual', 'nome': 'X', 'dados': {'estilo': 'mapas_animados'}}) is not None,
      'pacote visual com estilo indisponível é recusado')
e423 = erro(rota, 'PATCH', f'/api/v1/biblioteca-criativa/{perfil["id"]}', {'versao': 1, 'dados': {'voz': 'Puck'}})
check(e423 is not None and e423.status == 423, 'campo com cadeado não muda sem tirar o cadeado')
auto = bc.atualizar(perfil['id'], {'dados': {'voz': 'Puck', 'ritmo': 'normal'}}, 1, 'teste', automatico=True)
check(auto['dados']['voz'] == 'Kore' and auto['dados']['ritmo'] == 'normal' and auto['versao'] == 2, 'sugestão automática ignora o campo travado')
modelo = bc.criar('modelo_roteiro', 'Pergunta e resposta', {'estrutura': 'pergunta, 3 fatos, conclusão', 'final': 'pergunte ao público'}, quem='teste')
lb = lc.criar(dict(L, titulo='Linha com biblioteca', biblioteca={'perfil_narracao': perfil['id'], 'modelo_roteiro': modelo['id']}, limite_dia=12), 'teste')
lc.escrever_pautas(lb['id'], ['Como nascem as estrelas'])
epb = lc.iniciar_lote(lb['id'], 1, 'teste', produzir=lambda *a: None)['episodios'][0]
pb = pj.obter(epb['projeto'])
check(pb['dados']['briefing']['voz'] == 'Kore' and 'pergunta, 3 fatos' in pb['dados']['briefing']['descricao'], 'episódio usa o perfil e o modelo da biblioteca')
check(pb['dados']['linha']['biblioteca']['perfil_narracao']['versao'] == 2, 'episódio guarda a versão usada (2)')
bc.atualizar(perfil['id'], {'dados': {'ritmo': 'rapido'}}, 2, 'teste')
check(pj.obter(epb['projeto'])['dados']['linha']['biblioteca']['perfil_narracao']['versao'] == 2 and len(bc.versoes(perfil['id'])) == 3,
      'mudar o item cria a versão 3 e NÃO mexe no episódio já feito')

print('14. Orçamento do dia da linha')
lo = lc.criar(dict(L, titulo='Linha com orçamento', orcamento_dia=1.0, orcamento_video=0.4, limite_dia=12), 'teste')
lc.escrever_pautas(lo['id'], ['Pauta um do orçamento', 'Pauta dois sobre outra coisa', 'Pauta três bem diferente', 'Quarta pauta nova'])
r = lc.iniciar_lote(lo['id'], 4, 'teste', produzir=lambda *a: None)
check(len(r['episodios']) == 2, 'R$ 1,00 por dia e até R$ 0,40 por vídeo: começa só 2 (não os 4 pedidos)')
for e in r['episodios']:
    db.executar("INSERT INTO jobs (id, agente, tipo, projeto, status, criado) VALUES (?,?,?,?,?,?)", 'j' + e['projeto'], 'agente3', 'producao', e['projeto'], 'concluido', time.time())
    db.executar("INSERT INTO custos (job, provedor, modelo, etapa, estimado, moeda, t) VALUES (?,?,?,?,?,?,?)", 'j' + e['projeto'], 'gemini', 'm', 'imagem', 0.45, 'BRL', time.time())
check(lc.gasto_24h(lo['id']) == 0.9, 'gasto da linha vem do que o produtor registrou (R$ 0,90)')
eo = erro(lc.iniciar_lote, lo['id'], 1, produzir=lambda *a: None)
check(eo is not None and 'Orçamento do dia' in str(eo), 'orçamento do dia alcançado: não começa mais nenhum')

print('15. Agente 1: híbrido e fontes por rodada')
d = oq.meta_semanal({'acao': 'nada', 'repondo': False, 'quantos': 0, 'motivo': ''}, 2, 6, oq.config(), time.time(), 0)
check(d['acao'] == 'cortar' and d['quantos'] == 4, 'híbrido: estoque bom, mas a meta da semana pede mais 4')
check(oq.meta_semanal({'acao': 'nada'}, 6, 6, oq.config(), time.time(), 0)['acao'] == 'nada', 'híbrido com a meta cumprida: parado')
oq.salvar({'cortes': {'frequencia': 'agenda'}}, None, 'teste')
check(oq.decisao_cortes() is None, 'modo agenda: volta à meta de cortes por semana')
oq.salvar({'cortes': {'frequencia': 'estoque', 'fontes_rodada': 3}}, None, 'teste')
check(oq.decisao_cortes()['fontes'] == 3, 'até 3 vídeos-fonte por rodada')
check(erro(oq.salvar, {'cortes': {'fontes_rodada': 9}}) is not None, 'mais de 5 fontes por rodada é recusado')

print('16. Editor supervisionado (você libera) e manual')
import editor_ia as ed  # noqa: E402
import fila  # noqa: E402
check(ed.modo_editor() == 'automatico', 'padrão: editor automático')
oq.salvar({'editor': {'modo': 'supervisionado'}}, None, 'teste')
check(ed.modo_editor() == 'supervisionado', 'modo supervisionado salvo')
fila.registrar('esteira.recebido', ag.job_esteira_recebido, 'pesado')
vs = pg.VIDEOS / 'sup1.mp4'
subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=720x1280:d=4:r=30', '-f', 'lavfi', '-i', 'sine=f=300:d=4',
                '-vf', 'noise=alls=20:allf=t', '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(vs)], check=True)
rm = ag.receber_manual({'video': 'sup1', 'titulo': 'Supervisionado', 'direitos': {'origem': 'meu'}, 'destino': 'pronto'})
jb = db.um("SELECT * FROM jobs WHERE tipo='esteira.recebido' ORDER BY criado DESC LIMIT 1")


class Ctx:
    def __init__(self, d):
        self.dados = d

    def progresso(self, *a):
        pass


ag.job_esteira_recebido(Ctx(json.loads(jb['dados'])))
cs = next(x for x in ag.estado()['cortes'] if x['id'] == rm['id'])
run = db.um("SELECT * FROM pipeline_runs WHERE ref=? ORDER BY criado DESC LIMIT 1", rm['id'])
check(run['estado'] == 'manual_review_required' and 'supervisionado' in run['etapa'] and not pl.portao_postagem(vs)['ok'] and cs['status'] != 'pronto',
      'supervisionado: o diretor aprovou, mas sem certificado e fora da agenda até você liberar')
lib = rota('POST', f'/api/v1/pipeline/jobs/{run["id"]}/manual-review', {'decisao': 'aprovar', 'motivo': 'Conferi a edição, pode ir'})
cs = next(x for x in ag.estado()['cortes'] if x['id'] == rm['id'])
check(lib['estado'] == 'final_approved' and pl.portao_postagem(vs)['ok'] and cs['status'] == 'pronto', 'você liberou: certificado do arquivo e corte pronto')
oq.salvar({'editor': {'modo': 'automatico'}}, None, 'teste')

print('17. Ferramentas externas (ficha, teste, ligar)')
import integracoes as ig  # noqa: E402
fs = {f['id']: f for f in rota('GET', '/api/v1/integracoes/capacidades')['ferramentas']}
check({'moneyprinterturbo', 'openreels', 'cuesync', 'yt-factcheck', 'postiz', 'auto-editor', 'remotion'} <= set(fs), 'todas as ferramentas da seção 7.2 têm ficha')
check(all(not f['licenca_auditada'] and not f['habilitada'] for k, f in fs.items() if k != 'ffmpeg'), 'nenhuma vem ligada nem com licença dada como conferida')
check(fs['postiz']['status'] == 'so_referencia' and 'AGPL' in fs['postiz']['licenca_declarada'], 'Postiz: só referência (AGPL)')
check(rota('POST', '/api/v1/integracoes/ffmpeg/teste')['ok'], 'teste do FFmpeg passa neste aparelho')
ta = rota('POST', '/api/v1/integracoes/auto-editor/teste')
check(not ta['ok'] and 'não está instalado' in ta['detalhe'], 'Auto-Editor ausente: teste falha e diz que o FFmpeg continua')
e412 = erro(rota, 'POST', '/api/v1/integracoes/auto-editor/ligar', {})
check(e412 is not None and e412.status == 412, 'não liga sem licença conferida')
e412b = erro(rota, 'POST', '/api/v1/integracoes/auto-editor/ligar', {'licenca_conferida': True, 'nota': 'li o LICENSE'})
check(e412b is not None and 'teste' in str(e412b), 'com licença conferida, ainda não liga sem o teste passar')
check(erro(rota, 'POST', '/api/v1/integracoes/moneyprinterturbo/ligar', {'licenca_conferida': True}).status == 409, 'ferramenta só com ficha não pode ser ligada')
pz = ig.pausas(vs)
check(pz['fonte'] == 'ffmpeg' and isinstance(pz['pausas'], list), 'pausas: sem Auto-Editor ligado, usa o FFmpeg')

print(f'\n{ok} ok, {falhas} falha(s)')
sys.exit(1 if falhas else 0)
