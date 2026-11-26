"""Comandos por mensagem (WhatsApp): entende, pede SIM antes de publicar e respeita o diretor de qualidade.

Rodar:  python servidor/testes/teste_comandos.py      (sem internet: a IA é simulada)
"""
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='comandos-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import banco as db  # noqa: E402
import api_v1  # noqa: E402
import agente as ag  # noqa: E402
import aprovacoes as apv  # noqa: E402
import comandos as cm  # noqa: E402
import produtor  # noqa: E402
import projetos as pj  # noqa: E402

falhas = 0


def confere(c, nome, extra=''):
    global falhas
    print(('ok    ' if c else 'FALHA ') + nome + ('' if c else f'  -> {extra}'))
    falhas += 0 if c else 1


db.migrar()
api_v1.iniciar()
ag.enviar_email = lambda *a, **k: 'mid'
pedidos_ia = []
ag.gemini = lambda partes, **k: (pedidos_ia.append(partes[0]['text']), {'acao': 'corrigir', 'ref': REF, 'texto': 'música mais baixa'})[1]
aprovados, agendados, rodados = [], [], []
apv_aprovar = apv.aprovar
apv.aprovar = lambda pid, sha, dest, origem, por, chave='': (aprovados.append((pid, sha, origem)), {'posts': [{'id': 'p1'}]})[1]
apv.pedir_alteracao = lambda pid, sha, texto, origem, por: aprovados.append(('corrigir', pid, texto))
ag.agendar_corte = lambda cid: agendados.append(cid)
ag.ver = lambda: {}
ag.rodar_agora = lambda oque, link='': rodados.append((oque, link))


def video(titulo, diretor_ok=True):
    p = produtor.novo({'briefing': {'tema': 'T', 'estilo': 'animado2d', 'destinos': {'redes': ['youtube']}},
                       'roteiro': {'titulo': titulo, 'legenda': 'x', 'hashtags': [], 'cenas': [{'titulo': 'A', 'texto': 'b'}]}})
    sha = (p['id'] * 8)[:64]
    q = {'status': 'apto_para_revisao_humana', 'problemas': []} if diretor_ok else \
        {'status': 'alerta_visual', 'problemas': [{'tipo': 'cabeca_cortada', 'severidade': 'alta', 'descricao': 'x', 'cena_id': 'c1', 'natureza': 'objetivo'}]}
    pj.mudar_dados(p['id'], lambda d, _p: (d.update(render={'id': 'r', 'versao': 1, 'sha': sha, 'duracao': 50.0}, qualidade=q,
        diretor={'sha': sha, 'veredito': 'aprovado' if diretor_ok else 'reprovado', 'motivos': []}), {'status': 'ready_for_review'})[1])
    return p['id'], sha


pid, sha = video('Vídeo bom')
pid2, _ = video('Vídeo reprovado', diretor_ok=False)
REF, REF2 = apv.ref(pid), apv.ref(pid2)
ag._mudar(lambda e: e['cortes'].extend([
    {'id': 'c1', 'titulo': 'Corte A', 'status': 'pronto', 'ini': 0, 'fim': 60, 'nota': 80, 'criado': 1},
    {'id': 'c2', 'titulo': 'Corte B', 'status': 'pronto', 'ini': 0, 'fim': 62, 'nota': 70, 'criado': 2},
    {'id': 'c3', 'titulo': 'Corte reprovado', 'status': 'reprovado', 'ini': 0, 'fim': 60, 'nota': 90, 'criado': 3}]))

r = cm.responder('pendentes', 'w')
confere(REF in r and 'Vídeo bom' in r and REF2 not in r and 'corte 1: Corte A' in r and 'Corte reprovado' not in r,
        'pendentes: só o que o diretor aprovou, com os códigos', r)
confere('Comandos' in cm.responder('ajuda', 'w'), 'ajuda lista os comandos')
confere('Cortes esperando você: 2' in cm.responder('status', 'w'), 'status conta o que espera você')

r = cm.responder(f'aprova o {REF}', 'w')
confere('SIM' in r and not aprovados, 'aprovar pede SIM antes de mandar para a postagem', r)
r = cm.responder('sim', 'w')
confere(aprovados == [(pid, sha, 'whatsapp')] and 'agente de postagem' in r, 'SIM: aprovação final registrada como sua, pelo WhatsApp', r)
confere('Não há nada' in cm.responder('sim', 'w'), 'SIM repetido não aprova de novo')

r = cm.responder(f'aprovar {REF2}', 'w')
confere('não está esperando' in r, 'vídeo reprovado pelo diretor não pode ser aprovado pelo WhatsApp', r)

cm.responder('agenda o corte 2', 'w')
confere(not agendados, 'agendar corte pede SIM')
r = cm.responder('não', 'w')
confere('Cancelado' in r and not agendados, 'NÃO cancela')
cm.responder('agendar corte 1', 'w')
r = cm.responder('SIM', 'w')
c1 = next(c for c in ag.estado()['cortes'] if c['id'] == 'c1')
confere(agendados == ['c1'] and c1.get('aprovado_voce'), 'SIM: corte aprovado por você e agendado', r)
confere('Não achei o corte 9' in cm.responder('agendar corte 9', 'w'), 'corte que não existe: avisa')

r = cm.responder('descarta o corte 1', 'w')
confere('descartado' in r, 'descartar corte', r)

r = cm.responder(f'corrigir {REF} deixe a narração mais curta na cena 3', 'w')
confere(('corrigir', pid, 'deixe a narração mais curta na cena 3') in aprovados, 'corrigir pelas regras, sem gastar IA', r)
confere(not pedidos_ia, 'comandos simples não chamam a IA')

r = cm.responder('acho que a música do vídeo ficou alta demais, abaixa ela', 'w')
confere(pedidos_ia and ('corrigir', pid, 'música mais baixa') in aprovados, 'frase solta: a IA entende e vira correção', r)

r = cm.responder('corta esse vídeo pra mim https://youtu.be/abcdefghijk', 'w')
confere(rodados == [('link', 'https://youtu.be/abcdefghijk')], 'cortar link manda para o Agente 1', r)

ag.gemini = lambda partes, **k: {'acao': 'apagar_tudo'}
confere('Não entendi' in cm.responder('apaga tudo', 'w'), 'ação fora da lista é recusada')

print('\nTUDO OK' if not falhas else f'\n{falhas} FALHA(S)')
sys.exit(1 if falhas else 0)
