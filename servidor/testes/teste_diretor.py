"""Diretor de qualidade: só chega para a sua aprovação o vídeo que ele aprovou; o que ele reprova é refeito.

Rodar:  python servidor/testes/teste_diretor.py
Sem internet e sem FFmpeg: confere as decisões do diretor com dados montados à mão.
"""
import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='diretor-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import banco as db  # noqa: E402
import api_v1  # noqa: E402
import aprovacoes as apv  # noqa: E402
import emails  # noqa: E402
import produtor  # noqa: E402
import projetos as pj  # noqa: E402
import qualidade as qd  # noqa: E402

falhas = 0


def confere(c, nome):
    global falhas
    print(('ok    ' if c else 'FALHA ') + nome)
    falhas += 0 if c else 1


db.migrar()
api_v1.iniciar()
avisos = []
emails.avisar_falha = lambda pid, msg: avisos.append((pid, msg))


def prob(tipo, sev='media', cena='c1', natureza='objetivo', status='aberto'):
    return {'tipo': tipo, 'severidade': sev, 'descricao': f'{tipo} na cena {cena}', 'cena_id': cena, 'natureza': natureza, 'status': status}


# ---- veredito
confere(not qd.veredito({'status': 'falha_tecnica', 'tecnico': {'erros': ['sem som']}})['aprovado'], 'falha técnica reprova')
confere(qd.veredito({'status': 'falha_tecnica'})['tecnico'], 'falha técnica pede refazer tudo')
confere(not qd.veredito(None)['aprovado'], 'vídeo sem conferência não é aprovado')
v = qd.veredito({'status': 'alerta_visual', 'problemas': [prob('cabeca_cortada', 'alta', 'c2')]})
confere(not v['aprovado'] and v['cenas'] == ['c2'], 'cabeça cortada (grave) reprova e aponta a cena')
confere(qd.veredito({'status': 'alerta_visual', 'problemas': [prob('quadro_escuro', 'baixa')]})['aprovado'], 'problema leve não reprova')
confere(qd.veredito({'status': 'alerta_visual', 'problemas': [prob('narrativa'), prob('ritmo', 'alta')]})['aprovado'], 'nota de roteiro e ritmo não reprova')
confere(qd.veredito({'status': 'alerta_visual', 'problemas': [prob('sobreposicao', natureza='julgamento')]})['aprovado'], 'opinião da IA não reprova')
confere(qd.veredito({'status': 'alerta_visual', 'problemas': [prob('sai_do_quadro', status='resolvido')]})['aprovado'], 'problema já resolvido não reprova')
confere(qd.veredito({'status': 'apto_para_revisao_humana', 'problemas': []})['aprovado'], 'tudo certo aprova')

# ---- correção forte do desenho
c = {'planos': [{'id': 'p1', 'plano': 'CU'}, {'id': 'p2', 'plano': 'MS'}], 'elenco': [{'id': 'a', 'posicao': 'centro'}, {'id': 'b', 'posicao': 'centro'}]}
f = qd.correcao_forte(c)
confere(f and all(p['plano'] == 'WS' for p in f['planos']) and [e['posicao'] for e in f['elenco']] == ['esquerda', 'direita'], 'desenho: planos abertos e personagens afastados')
confere(qd.correcao_forte(dict(c, **f)) is None, 'desenho: sem mais nada a mudar, não finge que refez')


# ---- decisão do diretor no Agente 3
class Ctx:
    def __init__(self, id_):
        self.id = id_


def projeto(estilo):
    p = produtor.novo({'briefing': {'tema': 'Teste', 'estilo': estilo, 'destinos': {'redes': ['youtube']}},
                       'roteiro': {'titulo': 'T', 'legenda': 'x', 'hashtags': [], 'cenas': [{'titulo': 'A', 'texto': 'um'}, {'titulo': 'B', 'texto': 'dois'}]}})
    pid = p['id']

    def f(d, _p):
        for k, cn in enumerate(d['cenas']):
            cn['id'] = f'c{k + 1}'
            cn['clipe'] = 'x.mp4'
            cn['planos'] = [{'id': 'p1', 'plano': 'CU'}]
            cn['elenco'] = [{'id': 'a', 'posicao': 'centro'}, {'id': 'b', 'posicao': 'centro'}]
            cn['imagem'] = {'id': 'foto1', 'arquivo': 'a.jpg'}
    pj.mudar_dados(pid, f)
    return pid


def render_de(sha):
    return {'id': 'r' + sha[:6], 'sha': sha, 'versao': 1, 'duracao': 3.0, 'criado': 0, 'validado': True}


def qa(pid, q):
    pj.mudar_dados(pid, lambda d, _p: d.update(qualidade=q))


ruim = {'status': 'alerta_visual', 'problemas': [prob('cabeca_cortada', 'alta', 'c2')]}
bom = {'status': 'apto_para_revisao_humana', 'problemas': []}
conf = {'avisos': []}

pid = projeto('animado2d')
ctx = Ctx('job1')
qa(pid, ruim)
r = produtor.decisao_do_diretor(ctx, pid, {'estilo': 'animado2d'}, render_de('a' * 64), 'a' * 64, 1, conf)
p = pj.obter(pid)
confere(r.get('refazer') and p['status'] == 'rendering', 'reprovado: volta a produzir em vez de chegar para você')
confere(p['dados']['diretor']['veredito'] == 'refazendo' and p['dados']['diretor']['tentativas'] == 1, 'conta a tentativa de refazer')
c1, c2 = p['dados']['cenas']
confere('clipe' not in c2 and c2['refazer'] == 1 and c2['planos'][0]['plano'] == 'WS', 'só a cena reprovada é refeita, com planos abertos')
confere(c1.get('clipe') == 'x.mp4' and not c1.get('refazer'), 'a cena boa não é mexida')
confere(not p['dados'].get('render'), 'o vídeo reprovado não vira o vídeo para aprovar')
try:
    apv.aprovar(pid, 'a' * 64, {'redes': ['youtube'], 'quando': 'agora'}, 'site', 'teste')
    confere(False, 'você não consegue aprovar o vídeo reprovado')
except Exception as e:  # noqa: BLE001
    confere('diretor' in str(e).lower() or 'versão' in str(e).lower(), 'você não consegue aprovar o vídeo reprovado')

qa(pid, bom)
r = produtor.decisao_do_diretor(ctx, pid, {'estilo': 'animado2d'}, render_de('b' * 64), 'b' * 64, 2, conf)
p = pj.obter(pid)
confere(p['status'] == 'ready_for_review' and p['dados']['render']['sha'] == 'b' * 64, 'refeito e aprovado: chega para a sua aprovação final')
confere(p['dados']['diretor']['veredito'] == 'aprovado' and p['dados']['diretor']['tentativas'] == 1, 'registra que foi aprovado depois de refazer 1 vez')
confere(apv.diretor_ok(p, 'b' * 64)['aprovado'], 'a sua aprovação aceita o arquivo que o diretor aprovou')
qa(pid, ruim)
confere(not apv.diretor_ok(pj.obter(pid), 'c' * 64)['aprovado'], 'outro arquivo, sem aprovação do diretor, não passa')
qa(pid, bom)

# esgota as tentativas
pid = projeto('documentario')
ctx = Ctx('job2')
for k in range(qd.MAX_REFAZER):
    qa(pid, ruim)
    r = produtor.decisao_do_diretor(ctx, pid, {'estilo': 'documentario'}, render_de(str(k) * 64), str(k) * 64, k + 1, conf)
    confere(r.get('refazer'), f'documentário: tentativa {k + 1} refaz')
c2 = pj.obter(pid)['dados']['cenas'][1]
confere('foto1' in (c2.get('fotos_recusadas') or []) and not c2.get('imagem'), 'documentário: troca a foto recusada')
qa(pid, ruim)
r = produtor.decisao_do_diretor(ctx, pid, {'estilo': 'documentario'}, render_de('z' * 64), 'z' * 64, 9, conf)
p = pj.obter(pid)
confere(not r.get('refazer') and p['status'] == 'failed' and p['dados']['diretor']['veredito'] == 'reprovado', 'acabaram as tentativas: para com o motivo')
confere('diretor de qualidade' in p['dados']['producao']['erro'] and not p['dados'].get('render'), 'não chega para você e diz o motivo')
confere(avisos and avisos[-1][0] == pid, 'avisa por e-mail que parou')

# novo pedido de produção (outro job) começa a contagem do zero
ctx3 = Ctx('job3')
qa(pid, ruim)
r = produtor.decisao_do_diretor(ctx3, pid, {'estilo': 'documentario'}, render_de('y' * 64), 'y' * 64, 10, conf)
confere(r.get('refazer') and pj.obter(pid)['dados']['diretor']['tentativas'] == 1, 'mandar produzir de novo zera as tentativas')

# ---- cortes do Radar (Agente 1)
import agente  # noqa: E402

co = {'dur_min': 20, 'dur_max': 60}
pal = [(5.0, 5.4, 'Olá'), (5.5, 6.0, 'pessoal.'), (10.0, 10.5, 'Hoje'), (30.0, 30.5, 'vamos'), (31.0, 31.5, 'falar'), (40.0, 40.4, 'disso.'), (50.0, 50.5, 'Fim.')]
confere(not agente.veredito_corte({'erros': [], 'avisos': ['O corte demora 5 s para alguém falar.']})['aprovado'], 'corte que demora para falar é reprovado')
confere(not agente.veredito_corte({'erros': ['sem som'], 'avisos': []})['aprovado'], 'corte com erro técnico é reprovado')
confere(agente.veredito_corte({'erros': [], 'avisos': ['Legenda com 3 linhas.']})['aprovado'], 'aviso leve não reprova o corte')
aj = agente.ajustar_corte({'ini': 0.0, 'fim': 31.0}, pal, {}, co, 120)
confere(aj and abs(aj['ini'] - 4.7) < 0.01 and abs(aj['fim'] - 40.7) < 0.01, 'ajuste: começa logo antes da fala e termina no fim da frase')
sem_ponto = [(1.0, 1.4, 'olha'), (1.5, 2.0, 'isso'), (3.0, 3.4, 'que'), (3.5, 3.9, 'coisa')]
confere(agente.fins_de_frase(sem_ponto) == {2.0, 3.9}, 'legenda automática sem pontuação: a pausa marca o fim da frase')
confere(agente.fins_de_frase([(0, 0.4, 'a'), (0.5, 0.9, 'b'), (1.0, 1.4, 'c')]) is None, 'sem pontuação e sem pausa: não reprova por não saber')
confere(agente.ajustar_corte({'ini': 60.0, 'fim': 90.0}, pal, {}, co, 120) is None, 'sem fala no trecho: não inventa ajuste')

agendados = []
agente.agendar_corte = lambda cid: agendados.append(cid)
agente.ver = lambda: {}
agente.acompanhar = lambda: None
agente.conferir = lambda c: {'bloqueios': [], 'avisos': []}
agente._mudar(lambda e: e['cortes'].extend([
    {'id': 'ok1', 'titulo': 'a', 'status': 'pronto', 'qa': {'diretor': {'veredito': 'aprovado', 'motivos': []}}, 'criado': 0},
    {'id': 'rep', 'titulo': 'b', 'status': 'reprovado', 'qa': {'diretor': {'veredito': 'reprovado', 'motivos': ['O corte demora']}}, 'criado': 0}]))
agente.trabalhar_postagem()
confere(not agendados, 'corte aprovado pelo diretor não é postado sem a sua aprovação')
try:
    agente.acao_corte('rep', 'agendar')
    confere(False, 'corte reprovado não pode ser agendado')
except agente.ErroAgente:
    confere(not agendados, 'corte reprovado não pode ser agendado')
agente.acao_corte('ok1', 'agendar')
c = next(x for x in agente.estado()['cortes'] if x['id'] == 'ok1')
confere(agendados == ['ok1'] and c.get('aprovado_voce'), 'você aprova e ele agenda')

print('\nTUDO OK' if not falhas else f'\n{falhas} FALHA(S)')
sys.exit(1 if falhas else 0)
