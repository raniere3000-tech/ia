"""Custo por corte e banco de trechos: cada chamada ao Gemini fica registrada (tokens × tabela) e ligada à análise;
a mesma análise vira mais cortes depois, sem chamar a IA de novo; a aba Custos mostra a média e as sugestões. FFmpeg real, Gemini falso.

Rodar: cd servidor && python3 testes/teste_custo_corte.py
"""
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-custo-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
os.environ['CENTRAL_SEM_ACORDAR'] = '1'
os.environ['COORDENADOR_SEM_VIGIA'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agente as ag  # noqa: E402
import banco as db  # noqa: E402
import coordenador as co  # noqa: E402
import custo_corte as cc  # noqa: E402

db.migrar()
ok = falhas = 0


def check(c, m):
    global ok, falhas
    if c:
        ok += 1
    else:
        falhas += 1
        print('FALHA:', m)


# vídeo de 2 minutos com som
FONTE = TMP / 'fonte.mp4'
subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=320x180:r=15:d=120', '-f', 'lavfi', '-i', 'sine=f=300:d=120',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', '-shortest', str(FONTE)], check=True)
BAIXADOS = []


def baixar(url, pasta, idioma, prog):
    BAIXADOS.append(url)
    destino = Path(pasta) / 'video.mp4'
    shutil.copy(FONTE, destino)
    return destino, {'duration': 120.0, 'title': 'Podcast muito bom'}, None      # sem legenda do YouTube: a IA precisa ouvir


ag.BAIXAR = baixar
CHAMADAS = []
CANDIDATOS = [{'inicio': 2 + i * 14, 'fim': 13 + i * 14, 'nota': 90 - i, 'titulo': f'Trecho {i + 1}', 'gancho': 'olha isso', 'hashtags': ['#a', '#b'],
               'motivo': 'bom', 'proibido': False} for i in range(8)]


def falso(caminho, corpo, chave, tempo):
    """Gemini falso: áudio -> transcrição; texto -> trechos. Devolve tokens como o Google."""
    partes = corpo['contents'][0]['parts']
    audio = any('inline_data' in p for p in partes)
    camera = 'CÂMERA DO STREAMER' in partes[0].get('text', '')
    CHAMADAS.append('ouvir' if audio else 'camera' if camera else 'escolher')
    if camera:
        return 200, {'candidates': [{'content': {'parts': [{'text': '{"tem_camera": false}'}]}}], 'usageMetadata': {'promptTokenCount': 1500, 'candidatesTokenCount': 20}}
    if audio:
        frs = [{'inicio': i * 3, 'fim': i * 3 + 2.8, 'texto': 'essa é uma frase falada no podcast.'} for i in range(40)]
        texto, uso = json.dumps(frs), {'promptTokenCount': 1_000_000, 'candidatesTokenCount': 10_000}      # áudio: caro
    else:
        texto, uso = json.dumps(CANDIDATOS), {'promptTokenCount': 100_000, 'candidatesTokenCount': 4_000}
    return 200, {'candidates': [{'content': {'parts': [{'text': texto}]}}], 'usageMetadata': uso}


ag._pedir_gemini = falso
_veredito = ag.veredito_corte
DIRETOR = []
ag.veredito_corte = lambda qa: DIRETOR.append(_veredito(qa)) or {'aprovado': True, 'motivos': []}   # vídeo sintético (só um tom): o diretor roda, o teste aprova
ag.salvar_segredos({'gemini_pago': 'chave-paga-falsa'})
ag.salvar_config({'cortes': {'dur_min': 8, 'dur_max': 15, 'nota_min': 60, 'por_video': 2, 'por_semana': 21, 'por_analise': 6, 'dur_v': 2,
                             'template': {'qualidade': 720}},
                  'chaves_uso': {'cortes': 'paga'}, 'orcamento': {'teto': 0}})
check(ag.config()['cortes']['por_analise'] == 6, 'config guarda trechos por análise')
check(ag.PADRAO['cortes']['por_analise'] == 12, 'banco de trechos ligado por padrão (12 por análise)')

# 1) primeira rodada: análise paga, 2 cortes agora e 4 guardados
r = ag.trabalhar_cortes(link='https://www.youtube.com/watch?v=abcdefghijk')
cortes = ag.estado()['cortes']
check(len(cortes) == 2, f'2 cortes na primeira rodada ({len(cortes)}): {r}')
check([x for x in CHAMADAS if x != 'camera'] == ['ouvir', 'escolher'], f'uma chamada para ouvir e uma para escolher ({CHAMADAS})')
ref = cortes[0].get('analise')
check(ref and all(c.get('analise') == ref for c in cortes) and not any(c.get('da_reserva') for c in cortes), 'cortes ligados à análise')
check(all(c.get('qa', {}).get('diretor') for c in cortes), 'diretor de qualidade conferiu os cortes')
usos = db.todos('SELECT * FROM ia_uso ORDER BY id')
check(len(usos) == len(CHAMADAS) and all(u['ref'] == ref and u['cobrado'] == 1 for u in usos), f'cada chamada registrada na análise, na chave paga ({len(usos)})')
usos = [u for u in usos if u['etapa'] != 'camera']
o = ag.config()['orcamento']
esperado = (1.0 * o['preco_audio'] + 0.01 * o['preco_saida'] + 0.1 * o['preco_texto'] + 0.004 * o['preco_saida']) * o['dolar']
check(abs(sum(u['reais'] for u in usos) - esperado) < 0.001, f'R$ = tokens × tabela ({sum(u["reais"] for u in usos):.4f} vs {esperado:.4f})')
check({u['etapa'] for u in usos} == {'ouvir', 'escolher'}, 'etapas separadas (ouvir / escolher)')
an = db.um('SELECT * FROM ia_analises WHERE id=?', ref)
check(an and an['achados'] == 6 and an['usados'] == 2 and an['guardados'] == 4, f'análise: 6 achados, 2 usados, 4 guardados ({an})')
check(len(cc.disponiveis()) == 4, f'4 trechos no banco ({len(cc.disponiveis())})')
check(not any(min(a['fim'], b['fim']) - max(a['ini'], b['ini']) > 0.3 * (b['fim'] - b['ini']) for a in cortes for b in cc.disponiveis()),
      'guardados não repetem os cortes feitos')
check(DIRETOR, 'diretor de qualidade rodou')
check(cc.ref_atual() == '', 'referência limpa depois do trabalho')

# 2) segunda rodada: sai do banco de trechos, sem chamar a IA e sem procurar vídeo novo
ag.proximo_video = lambda tema='': check(False, 'não devia procurar vídeo novo com trechos guardados')
n0 = len(CHAMADAS)
r = ag.trabalhar_cortes(forcar=True)
cortes = ag.estado()['cortes']
novos = [c for c in cortes if c.get('da_reserva')]
check(len(novos) == 2, f'2 cortes da reserva ({len(novos)}): {r}')
check(not [x for x in CHAMADAS[n0:] if x != 'camera'], f'nenhuma chamada nova à IA para ouvir ou escolher ({CHAMADAS[n0:]})')
check(all(c['analise'] == ref and c['fala'].startswith('banco de trechos') for c in novos), 'cortes da reserva dividem o custo da mesma análise')
check(all(c.get('qa', {}).get('diretor') for c in novos), 'diretor de qualidade também confere os cortes da reserva')
check(len(BAIXADOS) == 2 and BAIXADOS[1] == 'https://www.youtube.com/watch?v=abcdefghijk', 'baixou de novo o mesmo vídeo (download não custa IA)')
check(len(cc.disponiveis()) == 2, 'sobraram 2 no banco')

# 3) resumo da aba Custos
rs = cc.resumo(30)
total = sum(u['reais'] for u in db.todos('SELECT reais FROM ia_uso'))
check(rs['cortes']['feitos'] + rs['cortes']['reprovados'] == 4, f'4 cortes no período ({rs["cortes"]})')
bons = rs['cortes']['medidos']
check(bons and abs(rs['por_corte']['tabela'] - total / bons) < 0.001 and abs(rs['por_corte']['pago'] - total / bons) < 0.001,
      f'custo por corte = análise ÷ cortes ({rs["por_corte"]}, {bons})')
check(rs['analises']['total'] == 1 and rs['analises']['lista'][0]['guardados'] == 2, 'lista da análise com guardados')
check(abs(sum(e['parte'] for e in rs['a1']['etapas']) - 1) < 0.01 and rs['a1']['etapas'][0]['etapa'] == 'ouvir', 'ouvir aparece como a parte mais cara')
check(rs['cortes']['feitos'] == 4 and rs['analises']['cortes_por_analise'] == 4, f'4 cortes de 1 análise ({rs["analises"]["cortes_por_analise"]})')
ids = [s['id'] for s in rs['sugestoes']]
check(any(s['id'] == 'priorizar_legendas' and s['feito'] for s in rs['sugestoes']), 'prioridade por legenda ligada por padrão')
check('mais_por_analise' in ids, f'4 cortes por vídeo: sugere pedir mais trechos por análise ({ids})')
check('chave_gratis' not in ids, 'sem chave grátis guardada, não sugere trocar')
ag.salvar_segredos({'gemini': 'chave-gratis-falsa'})
check('chave_gratis' in [s['id'] for s in cc.resumo(30)['sugestoes']], 'com chave grátis guardada, sugere usar nos cortes')
check(cc.aplicar('chave_gratis')['ok'] and ag.config()['chaves_uso']['cortes'] == 'gratis', 'aplicar troca a chave dos cortes')
ag.salvar_config({'cortes': {'por_analise': 0, 'priorizar_legendas': False}})
cc.aplicar('mais_por_analise')
check(ag.config()['cortes']['por_analise'] == 16, f'aplicar pede 16 trechos por análise ({ag.config()["cortes"]["por_analise"]})')
check(next(x for x in cc.resumo(30)['sugestoes'] if x['id'] == 'mais_por_analise')['feito'], 'depois de aplicar, a sugestão aparece como feita')
try:
    cc.aplicar('nao_existe')
    check(False, 'sugestão que não existe não aplica nada')
except ValueError:
    check(True, '')

# histórico de antes do registro: cortes antigos, troca para a chave paga e contador do mês
antigo = time.time() - 3 * 86400
def _hist(e):
    for k, (vid, fala) in enumerate([('v1', 'IA'), ('v1', 'IA'), ('v2', 'IA'), ('v2', 'IA'), ('v3', 'legenda do YouTube'), ('v3', 'legenda do YouTube')]):
        e['cortes'].append({'id': f'h{k}', 'criado': antigo + k, 'status': 'postado', 'tipo': 'agente', 'video': f'hv{k}', 'origem': vid, 'origem_titulo': vid, 'fala': fala})
    e['log'].append({'t': antigo, 'tipo': 'aviso', 'texto': 'A chave grátis estava sem cota; usei a outra para "Agente 1: ouvir e escolher os cortes".'})
ag._mudar(_hist)
h = cc.historico(30)
check(h['analises'] == 4 and h['cortes'] == 10, f'histórico junta os cortes por vídeo de origem ({h["analises"]} vídeos, {h["cortes"]} cortes)')
check(h['ouvidos_pela_ia'] == 3 and h['trocas_para_paga'] == 1, f'histórico conta vídeos ouvidos pela IA e trocas para a paga ({h})')
check(h['por_corte_contador'] and h['reais_pago_meses'] > 0, 'histórico divide o contador da chave paga pelos cortes')
ids = [x['id'] for x in cc.resumo(30)['sugestoes'] if not x['feito']]
check('sem_reserva_paga' in ids, f'histórico com troca para a paga: sugere não usar a paga ({ids})')
r = cc.aplicar('todas')
cfg = ag.config()
check(r['ok'] and cfg['chaves_uso']['reserva'] is False and cfg['cortes']['priorizar_legendas'] is True, f'"aplicar todas" faz todas as configurações ({r["acao"]})')
check(not [x for x in cc.resumo(30)['sugestoes'] if x.get('acao') and not x['feito']], 'depois de aplicar todas, nada pendente')
try:
    cc.aplicar('todas')
    check(False, 'nada pendente: aplicar todas avisa')
except ValueError:
    check(True, '')
check(any(e['categoria'] == 'custos' for e in co.eventos(categoria='custos')), 'o Coordenador registra o que aplicou no histórico')

# Mesmo com prioridade por legenda, o agente corta o vídeo escolhido quando precisa transcrever o áudio.
n0 = len(CHAMADAS)
r = ag.trabalhar_cortes(link='https://www.youtube.com/watch?v=zzzzzzzzzzz')
check('ouvir' in CHAMADAS[n0:] and any(c['origem'] == 'zzzzzzzzzzz' and c['fala'] == 'IA' for c in ag.estado()['cortes']),
      f'vídeo sem legenda transcrito e cortado ({r})')

txt = cc.texto_aviso(rs)
check('Custo médio da IA por corte' in txt and 'estimado' in txt, 'texto do aviso diz o custo médio e que é estimado')

# chave grátis: conta a chamada, mas R$ 0 de verdade
gratuitas_antes = cc.resumo(30)['a1']['chave_gratis']
cc.definir_ref('x1')
cc.registrar('cortes', 'gemini-flash-latest', 'gratis', {'contents': []}, {'promptTokenCount': 1000, 'candidatesTokenCount': 10}, False)
cc.definir_ref('')
u = db.um("SELECT * FROM ia_uso WHERE ref='x1'")
check(u and u['cobrado'] == 0 and u['reais'] > 0, 'chave grátis: valor de tabela guardado, marcado como não cobrado')
check(cc.resumo(30)['a1']['chave_gratis'] == gratuitas_antes + 1, 'resumo conta as chamadas na chave grátis')

# 4) Coordenador: chat e aviso semanal
ag._endereco = lambda: ''
r = co.interpretar('quanto está custando cada corte?')
check(r['tipo'] == 'resposta' and 'por corte' in r['resposta'], f'chat responde o custo por corte ({r["resposta"][:80]})')
enviados = []
ag.avisar = lambda tipo, assunto, corpo, *a, **k: enviados.append((tipo, assunto, k.get('zap_tipo'))) or True
dom = time.mktime(time.strptime('2026-11-22 20:30', '%Y-%m-%d %H:%M'))     # domingo
check(co.resumo_custos_da_semana(dom - 3600) is None, 'antes das 20:00 não manda')
check(co.resumo_custos_da_semana(dom - 86400) is None, 'sábado não manda (padrão domingo)')
check(co.resumo_custos_da_semana(dom) and enviados and enviados[-1][2] == 'a7_custos', f'domingo 20:30 manda no WhatsApp/e-mail ({enviados})')
n = len(enviados)
check(co.resumo_custos_da_semana(dom + 600) is None and len(enviados) == n, 'só uma vez por semana')
check(ag.PADRAO['whatsapp']['avisos']['a7_custos'] is True, 'aviso de custos no WhatsApp ligado por padrão')
co.salvar_config({'custos_dia': 1, 'custos_hora': '08:00'})
check(co.config()['custos_dia'] == 1 and co.config()['custos_hora'] == '08:00', 'dia e hora do resumo configuráveis')
try:
    co.salvar_config({'custos_hora': '25:00'})
    check(False, 'hora inválida devia dar erro')
except co.ErroCoord:
    check(True, '')

# teto: aviso uma vez no mês quando passa de 80%
ag.salvar_config({'orcamento': {'teto': 1.0}})
gasto = ag.gasto_mes()['reais']
check(gasto > 0.8, f'contador do mês somou o gasto da chave paga ({gasto})')
enviados.clear()
co.resumo_custos_da_semana(dom + 86400 * 2)
co.resumo_custos_da_semana(dom + 86400 * 2 + 60)
check(sum(1 for e in enviados if 'teto' in e[1]) == 1, f'aviso de teto uma vez ({enviados})')

# 5) banco de trechos vence e devolve
cc.limpar()
vivos = cc.disponiveis()
db.executar('UPDATE cortes_reserva SET criado=? WHERE usado IS NULL', time.time() - 30 * 86400)
cc.limpar()
check(vivos and not cc.disponiveis() and not list(cc.PASTA_RESERVA.glob('*.json.gz')), 'trecho vencido sai e a transcrição é apagada')
check(cc.tomar(2) is None, 'sem trechos guardados, não toma nada')

print(f'\n{ok} ok, {falhas} falha(s)')
sys.exit(1 if falhas else 0)
