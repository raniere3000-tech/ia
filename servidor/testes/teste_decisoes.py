"""Faixa "Espera a sua decisão" (topo de todas as telas): junta tudo o que está parado esperando você.

Rodar: cd servidor && python3 testes/teste_decisoes.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-decisoes-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
os.environ['CENTRAL_SEM_ACORDAR'] = '1'
os.environ['ESTEIRA_COMPLETA'] = '0'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import banco as db  # noqa: E402
import agente as ag  # noqa: E402
import decisoes  # noqa: E402
import painel  # noqa: E402
import postagem as pg  # noqa: E402
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


def rota():
    return rt.tratar('GET', '/api/v1/alertas/decisoes', {}, lambda: {}, 'teste')


agora = time.time()
print('1. Nada esperando')
r = rota()
check(r['total'] == 0 and r['urgentes'] == 0 and not r['fontes_com_erro'], 'servidor vazio: faixa some (0 itens, nenhuma fonte com erro)')

print('2. Cada tipo de decisão aparece')
db.executar("INSERT INTO projetos (id, titulo, tipo, status, dados, criado, atualizado, apagado) VALUES (?,?,?,?,?,?,?,0)",
            'p1', 'Vídeo do café', 'agente3', 'ready_for_review', '{"briefing":{},"render":{"sha":"video-teste"},"diretor":{"sha":"video-teste","veredito":"aprovado"},"qualidade":{"status":"apto_para_revisao_humana"}}', agora, agora - 300)
db.executar("INSERT INTO projetos (id, titulo, tipo, status, dados, criado, atualizado, apagado) VALUES (?,?,?,?,?,?,?,0)",
            'p2', 'Roteiro do chá', 'agente3', 'waiting_brief_approval', '{"briefing":{}}', agora, agora - 200)
db.executar("INSERT INTO projetos (id, titulo, tipo, status, dados, criado, atualizado, apagado) VALUES (?,?,?,?,?,?,?,0)",
            'p3', 'Corrigindo', 'agente3', 'changes_requested', '{"briefing":{}}', agora, agora)
db.executar("INSERT INTO coordenador_ordens (id, autor, texto, plano_json, status, criado, atualizado) VALUES (?,?,?,?,?,?,?)",
            'o1', 'eu', 'Faça 3 vídeos sobre café', '{}', 'aguardando_confirmacao', agora, agora - 1000)
db.executar("INSERT INTO coordenador_ordens (id, autor, texto, plano_json, status, criado, atualizado) VALUES (?,?,?,?,?,?,?)",
            'o2', 'eu', 'rascunho velho', '{}', 'rascunho', agora, agora - 10 * 86400)
db.executar("INSERT INTO coordenador_tarefas (id, ordem_id, agente, acao, parametros_json, estado, criado, atualizado, erro) VALUES (?,?,?,?,?,?,?,?,?)",
            't1', 'o1', 'agente7', 'a7.liberar', '{}', 'aguardando_voce', agora, agora, 'espera liberação')
db.executar("INSERT INTO coordenador_tarefas (id, ordem_id, agente, acao, parametros_json, estado, criado, atualizado, erro) VALUES (?,?,?,?,?,?,?,?,?)",
            't2', 'o1', 'agente2', 'a2.agendar', '{}', 'aguardando_voce', agora, agora, 'Conecte a conta do YouTube.')
db.executar("INSERT INTO coordenador_aprovacoes (id, ordem_id, tarefa_id, origem, referencia, video_sha256, pacote_hash, relatorio, decisao, criado) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)", 'a1', 'o1', 't1', 'render', 'p9', 'x' * 64, 'h', '{"titulo": "Pacote do café"}', 'pendente', agora - 50)
db.executar("INSERT INTO pipeline_runs (id, origem, ref, titulo, estado, criado, atualizado) VALUES (?,?,?,?,?,?,?)",
            'r1', 'corte', 'c1', 'Corte do jogo', 'manual_review_required', agora, agora - 400)
db.executar("INSERT INTO thumbnail_jobs (id, origem, referencia, video_sha, config, estado, criado, atualizado, titulo) VALUES (?,?,?,?,?,?,?,?,?)",
            'j1', 'corte', 'c1', 'y' * 64, '{}', 'aguardando_escolha', agora, agora - 100, 'Capa do corte')
db.executar("INSERT INTO thumbnail_jobs (id, origem, referencia, video_sha, config, estado, criado, atualizado, titulo) VALUES (?,?,?,?,?,?,?,?,?)",
            'j2', 'corte', 'c2', 'z' * 64, '{}', 'aguardando_escolha', agora, agora - 30 * 86400, 'Capa esquecida')
pg.salvar_posts([
    {'id': 'post1', 'titulo': 'Post barrado', 'quando': agora - 60, 'redes': {'youtube': {'status': 'liberacao', 'erro': 'Sem certificado.'}, 'tiktok': {'status': 'agendado'}}},
    {'id': 'post2', 'titulo': 'Post com erro', 'quando': agora - 60, 'redes': {'instagram': {'status': 'erro', 'erro': 'Conta desconectada.'}}},
    {'id': 'post3', 'titulo': 'Kwai de hoje', 'quando': agora - 60, 'redes': {'kwai': {'status': 'manual'}}},
    {'id': 'post4', 'titulo': 'Kwai de amanhã', 'quando': agora + 86400, 'redes': {'kwai': {'status': 'manual'}}},
    {'id': 'post5', 'titulo': 'Tudo certo', 'quando': agora + 60, 'redes': {'youtube': {'status': 'agendado'}}},
])
ag._mudar(lambda e: e['canais'].extend([{'id': 'ch1', 'nome': 'Canal A', 'status': 'sugerido'}, {'id': 'ch2', 'nome': 'Canal B', 'status': 'aprovado'}]))

r = rota()
ch = {x['chave']: x for x in r['itens']}
check(not r['fontes_com_erro'], 'todas as fontes leram sem erro: ' + ','.join(r['fontes_com_erro']))
check('a3:p1' in ch and ch['a3:p1']['tipo'] == 'video' and ch['a3:p1']['ir'] == {'aba': 'revisar', 'extra': 'p1', 'area': 'agentes'}, 'vídeo do Agente 3 leva direto para ele em Aprovações')
check('a3:p2' in ch and ch['a3:p2']['tipo'] == 'roteiro', 'roteiro esperando aprovação aparece')
check('a3:p3' not in ch, 'correção já pedida não aparece (é a vez do agente)')
check('ord:o1' in ch and ch['ord:o1']['urgente'] and ch['ord:o1']['ir']['extra'] == 'ordens:o1', 'plano do Coordenador para confirmar abre a ordem certa')
check('ord:o2' not in ch, 'rascunho com mais de 3 dias não vira alarme')
check('lib:a1' in ch and ch['lib:a1']['detalhe'] == 'Pacote do café' and ch['lib:a1']['ir']['extra'] == 'aprovacoes', 'liberação pendente leva para Coordenador > Liberar')
check('tar:t1' not in ch, 'etapa de liberação não aparece duas vezes (já tem o item da liberação)')
check('tar:t2' in ch and 'YouTube' in ch['tar:t2']['detalhe'], 'etapa parada por outro motivo aparece com o motivo')
check('run:r1' in ch, 'revisão manual da esteira aparece')
check('capa:j1' in ch and ch['capa:j1']['ir']['extra'] == 'galeria:j1', 'capa para escolher abre a galeria do pedido')
check('capa:j2' not in ch, 'capa parada há mais de 14 dias não vira alarme')
check('plib:post1' in ch and 'youtube' in ch['plib:post1']['detalhe'] and 'tiktok' not in ch['plib:post1']['detalhe'], 'post pedindo liberação mostra só a rede travada')
check('perr:post2' in ch and ch['perr:post2']['urgente'], 'post com erro é urgente')
check('pkw:post3' in ch and not ch['pkw:post3']['urgente'], 'Kwai na hora de postar aparece como "quando puder"')
check('pkw:post4' not in ch and not any(k.endswith('post5') for k in ch), 'Kwai de amanhã e post normal não aparecem')
check('canais' in ch and not ch['canais']['urgente'] and 'Canal A' in ch['canais']['detalhe'] and 'Canal B' not in ch['canais']['detalhe'], 'canais sugeridos viram 1 item "quando puder"')
urg = [x for x in r['itens'] if x['urgente']]
check(r['urgentes'] == len(urg) == 9, f'conta de urgentes certa ({r["urgentes"]})')
check(all(x['urgente'] for x in r['itens'][:len(urg)]), 'urgentes vêm primeiro')
check(urg[0]['chave'] == 'ord:o1', 'o que espera há mais tempo vem primeiro')
check(painel.resumo('hoje')['totais']['esperando_decisao'] == r['urgentes'], 'o número do Início é o mesmo da faixa')

print('3. Uma fonte quebrada não derruba as outras')
orig = decisoes._esteira
decisoes._esteira = lambda: 1 / 0
r2 = rota()
decisoes._esteira = orig
check(r2['fontes_com_erro'] == ['esteira'] and r2['total'] == r['total'] - 1, 'esteira com erro: o resto continua aparecendo')

print('4. Remover avisos persiste no servidor sem aprovar nem cancelar tarefas')
antes = db.um('SELECT status FROM projetos WHERE id=?', 'p1')['status']
rem = rt.tratar('POST', '/api/v1/alertas/decisoes/remover', {},
                lambda: {'chave': 'a3:p1', 'versao': ch['a3:p1']['versao']}, 'teste')
check(not any(x['chave'] == 'a3:p1' for x in rem['itens']) and rem['urgentes'] == r['urgentes'] - 1,
      'remover tira o item e reduz o contador imediatamente')
check(db.um('SELECT status FROM projetos WHERE id=?', 'p1')['status'] == antes,
      'remover aviso preserva a tarefa, sem aprovar, postar ou rejeitar')
check(painel.resumo('hoje')['totais']['esperando_decisao'] == rem['urgentes'],
      'contador do Início acompanha a remoção do aviso')
db.con().close()
del db._local.c
check(not any(x['chave'] == 'a3:p1' for x in rota()['itens']), 'outra conexão mantém o aviso removido')
db.executar('UPDATE projetos SET atualizado=? WHERE id=?', agora + 5, 'p1')
novo = next(x for x in rota()['itens'] if x['chave'] == 'a3:p1')
check(novo['versao'] != ch['a3:p1']['versao'], 'nova revisão do mesmo projeto volta à lista')
try:
    rt.tratar('POST', '/api/v1/alertas/decisoes/remover', {},
              lambda: {'chave': 'a3:p1', 'versao': ch['a3:p1']['versao']}, 'teste')
    check(False, 'remoção desatualizada deve falhar')
except rt.ErroRota as e:
    check(e.status == 409, 'remoção desatualizada não esconde uma decisão nova')
try:
    rt.tratar('POST', '/api/v1/alertas/decisoes/remover', {}, lambda: {}, 'teste')
    check(False, 'pedido vazio deve falhar')
except rt.ErroRota as e:
    check(e.status == 404, 'pedido vazio não remove outros itens')

print(f'\n{ok} ok, {falhas} falha(s)')
sys.exit(1 if falhas else 0)
