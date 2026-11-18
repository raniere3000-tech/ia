"""Esteira dos 5 agentes: regra 70/100, 5 correções (a 1ª avaliação não conta), correção que não muda nada, certificado preso ao arquivo,
direitos que a revisão manual não libera, assinatura adulterada, plano de edição com lista fechada e o ciclo editor <-> diretor com vídeos reais.

Rodar: cd servidor && PYTHONPATH=. python3 testes/teste_pipeline_5_agentes.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-pl-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
os.environ.pop('PIPELINE_V2', None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import banco as db  # noqa: E402
import contratos as ct  # noqa: E402
import pipeline as pl  # noqa: E402
import editor_ia as ed  # noqa: E402
import diretor_qualidade as dq  # noqa: E402

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


def erro(tipo, f, *a, **k):
    try:
        f(*a, **k)
    except tipo as e:
        return e
    return None


def rel(nota, bloq=()):
    return {'score': nota, 'blocking_findings': [ct.achado(c, 'bloqueio', 'x ' + c, 'y', alvo='pessoa' if c == 'direitos' else 'agent5') for c in bloq],
            'findings': [], 'partes': {}, 'passed': ct.decidir(nota, list(bloq))}


def video(nome, filtro=''):
    arq = TMP / nome
    cmd = ['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=720x1280:d=8:r=30', '-f', 'lavfi', '-i', 'sine=f=440:d=8',
           *(['-vf', filtro] if filtro else []), '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(arq)]
    subprocess.run(cmd, check=True)
    return arq


print('1. Regra fixa da nota')
check(not ct.decidir(69, []), 'nota 69 reprova')
check(ct.decidir(70, []), 'nota 70 aprova')
check(not ct.decidir(100, [{'category': 'audio'}]), 'nota 100 com bloqueio reprova')
check(sum(ct.PESOS['final_release'].values()) == 100 and sum(ct.PESOS['creative_preedit'].values()) == 100, 'pesos somam 100')

print('2. Cinco correções; a 1ª avaliação não conta')
r = pl.criar('corte', 'c-politica', 'teste')
decs = [pl.registrar_avaliacao(r['id'], 'final_release', rel(50), mudou=True)['decisao'] for _ in range(6)]
check(decs[:5] == ['corrigir'] * 5, 'avaliação inicial + 4 correções reprovadas ainda pedem correção')
check(decs[5] == 'revisao_manual', 'a 5ª correção reprovada vai para revisão manual')
check(erro(pl.ErroPipeline, pl.registrar_avaliacao, r['id'], 'final_release', rel(90)) is not None, 'etapa encerrada não aceita nova avaliação')
s = pl.etapa(r['id'], 'creative_preedit')
check(s['avaliacoes'] == 0 and s['correcoes'] == 0, 'contador da etapa criativa é separado')

print('3. Correção que não muda nada')
r2 = pl.criar('corte', 'c-igual', 'teste')
pl.registrar_avaliacao(r2['id'], 'final_release', rel(40), mudou=True)
d = pl.registrar_avaliacao(r2['id'], 'final_release', rel(40), mudou=False)
check(d['decisao'] == 'revisao_manual', 'mesmo plano e mesmo arquivo -> revisão manual, sem gastar as 5')
check(pl.criar('corte', 'c-igual')['id'] == r2['id'], 'mesma chave de idempotência devolve a mesma execução')

print('4. Certificado preso ao arquivo')
bom = video('bom.mp4')
sha = pl.sha_arquivo(bom)
check(pl.portao_postagem(bom)['ok'] and not pl.portao_postagem(bom)['ativo'], 'esteira desligada: postagem segue como antes')
pl.ligar(True, 'teste')
check(not pl.portao_postagem(bom)['ok'], 'esteira ligada e sem certificado: postagem barrada')
check(erro(pl.ErroPipeline, pl.emitir_certificado, 'ref1', sha, rel(65)) is not None, 'nota 65 não recebe certificado')
c = pl.emitir_certificado('ref1', sha, rel(82))
check(pl.portao_postagem(bom)['ok'], 'com certificado: postagem liberada')
copia = TMP / 'copia.mp4'
shutil.copy(bom, copia)
with open(copia, 'ab') as f:
    f.write(b'\0' * 64)
check(not pl.portao_postagem(copia)['ok'], 'arquivo exportado de novo (SHA diferente): postagem barrada')
db.executar('UPDATE approval_certificates SET nota=99 WHERE id=?', c['id'])
check(pl.certificado(sha) is None, 'certificado adulterado no banco não vale')
db.executar('UPDATE approval_certificates SET nota=82 WHERE id=?', c['id'])
check(pl.certificado(sha) is not None, 'certificado original volta a valer')
pl.emitir_certificado('ref1', pl.sha_arquivo(copia), rel(80))
check(pl.certificado(sha) is None, 'certificado novo da mesma ref revoga o do arquivo antigo')

print('5. Revisão manual não passa por cima de direitos')
e = erro(pl.ErroPipeline, pl.emitir_certificado, 'ref2', sha, rel(95, ['direitos']), manual=True, por='Raniere', motivo='quero postar')
check(e is not None and 'direitos' in str(e), 'direitos bloqueiam mesmo na revisão manual')
check(erro(pl.ErroPipeline, pl.emitir_certificado, 'ref2', sha, rel(95, ['audio']), manual=True) is not None, 'bloqueio técnico também segura a revisão manual')
check(pl.emitir_certificado('ref3', sha, rel(55), manual=True, por='Raniere', motivo='nota baixa mas ok')['manual'] == 1,
      'nota baixa sem bloqueio pode ser liberada por você (fica registrado)')

print('6. Plano de edição com lista fechada')
tpl = {'zoom': 1.1, 'enquadramento': 'desfoque', 'legenda': 'destaque', 'tamanho': 'pequeno', 'legenda_pos': 'baixo', 'loudnorm': False,
       'modelo': 'm1', 'formato': '9:16'}
p = ed.plano_do_corte({'ini': 10.0, 'fim': 40.0}, tpl, 120)
check(p['clips'] == [{'source': 'principal', 'in_ms': 10000, 'out_ms': 40000}], 'trecho vira plano em milissegundos')
check(erro(ct.ErroContrato, ct.validar_plano, dict(p, effects=[{'tipo': 'drawtext', 'text': 'x'}])) is not None, 'efeito fora da lista é recusado')
check(erro(ct.ErroContrato, ct.validar_plano, dict(p, effects=[{'tipo': 'zoom', 'nivel': 9}])) is not None, 'zoom fora da faixa é recusado')
check(erro(ct.ErroContrato, ct.validar_plano, dict(p, effects=[{'tipo': 'fade', 'entrada_ms': '1;rm -rf /'}])) is not None, 'texto no lugar de número é recusado')
check(erro(ct.ErroContrato, ct.validar_plano, dict(p, clips=[{'in_ms': 0, 'out_ms': 200000}]), 120) is not None, 'trecho além do fim da fonte é recusado')
check(erro(ct.ErroContrato, ct.validar_acao, {'acao': 'rodar_comando', 'cmd': 'ls'}) is not None, 'correção fora da lista é recusada')
n, f = ed.corrigir(p, [{'acao': 'ajustar_inicio', 'delta_ms': -2000}, {'acao': 'aumentar_legenda'}, {'acao': 'encurtar_pausa', 'ini_ms': 5000, 'fim_ms': 8000}])
check(n['clips'][0]['in_ms'] == 8000, 'começo adiantado 2 s')
check(len(n['clips']) == 2 and n['clips'][0]['out_ms'] == 8000 + 5250 and n['clips'][1]['in_ms'] == 8000 + 7750, 'pausa tirada deixando 0,25 s de cada lado')
check(ed.tpl_do_plano(tpl, n)['tamanho'] == 'medio', 'legenda pequena sobe para média')
check(len(f) == 3 and n['timeline_version'] == p['timeline_version'] + 1, 'cada mudança é registrada e a versão sobe')
travado = dict(p, manual_locks=[[9000, 11000]])
n2, f2 = ed.corrigir(travado, [{'acao': 'ajustar_inicio', 'delta_ms': -2000}])
check(n2['clips'][0]['in_ms'] == 10000 and not f2, 'trecho travado por você não é mexido')
n3, f3 = ed.corrigir(p, [{'acao': 'subir_legenda'}, {'acao': 'refazer_cenas', 'cenas': ['c1']}])
n4, f4 = ed.corrigir(n3, [{'acao': 'subir_legenda'}])
check(f3 and not f4 and ct.hash_plano(n3) == ct.hash_plano(n4), 'correção repetida não muda o plano')
check(ed.palavras_saida(n, [(9.0, 9.5, 'a'), (14.0, 14.4, 'b'), (16.0, 16.5, 'c')]) == [(1.0, 1.5, 'a'), (5.5, 6.0, 'c')],
      'palavras levadas para o tempo do vídeo final (a da pausa sai)')

print('7. Ciclo editor <-> diretor com vídeos de verdade')
preto = video('preto.mp4', "drawbox=enable='between(t,3,5)':c=black:t=fill")
ctx = lambda _p: {'aspecto': '9:16', 'sem_audio_ok': True, 'direitos_ok': True}
ra = pl.criar('corte', 'c-bom', 'bom')
res = ed.rodar(ra['id'], 'c-bom', ed.plano_do_corte({'ini': 0, 'fim': 8}, tpl, 8), lambda _p: bom, ctx, dur_fonte=8)
check(res['resultado'] == 'aprovado' and res['certificado'], f'vídeo bom aprovado com certificado (nota {res["relatorio"]["score"]})')
check(pl.obter(ra['id'])['estado'] == 'final_approved', 'estado final_approved')
check(pl.portao_postagem(bom)['ok'], 'Agente 2 aceita o arquivo aprovado')
rb = pl.criar('corte', 'c-preto', 'preto')
renders = []
res = ed.rodar(rb['id'], 'c-preto', ed.plano_do_corte({'ini': 0, 'fim': 8}, tpl, 8), lambda pp: renders.append(pp) or preto, ctx, dur_fonte=8)
check(res['resultado'] == 'revisao_manual', 'tela preta que o editor não consegue tirar acaba em revisão manual')
check(any('Tela preta' in b['evidence'] for b in res['relatorio']['blocking_findings']), 'motivo: tela preta no meio')
check(len(renders) == 2 and ed._efeito(renders[1], 'fade'), 'editor tentou suavizar uma vez e parou quando não havia mais o que mudar')
check(pl.obter(rb['id'])['estado'] == 'manual_review_required', 'estado manual_review_required')
check(not pl.portao_postagem(preto)['ok'], 'Agente 2 recusa o vídeo reprovado')
e = erro(pl.ErroPipeline, pl.decidir_manual, rb['id'], 'aprovar', 'quero postar assim', 'Raniere')
check(e is not None, 'revisão manual não libera vídeo com bloqueio técnico')
check(pl.decidir_manual(rb['id'], 'cancelar', 'vou refazer', 'Raniere')['estado'] == 'cancelled', 'você pode cancelar')
res2 = ed.rodar(ra['id'], 'c-bom', {}, lambda _p: 1 / 0, ctx)
check(res2['resultado'] == 'aprovado', 'retomada depois de queda não refaz etapa já aprovada')

print('8. Falha técnica não conta como correção')
rc = pl.criar('corte', 'c-falha', 'falha')
e = erro(RuntimeError, ed.rodar, rc['id'], 'c-falha', ed.plano_do_corte({'ini': 0, 'fim': 8}, tpl, 8), lambda _p: (_ for _ in ()).throw(RuntimeError('ffmpeg')), ctx)
check(e is not None and pl.etapa(rc['id'], 'final_release')['avaliacoes'] == 0, 'erro de render sobe para a fila e não gasta avaliação')

print('9. Corte real do Agente 1 com pausas tiradas e fade (executar_corte)')
try:
    import agente as ag
    tpl_real = ed.tpl_do_plano(ag.mo.tpl(ag.mo.ativos(ag.config()['cortes']['modelos'])[0]), p)
    pp = ed.plano_do_corte({'ini': 0.5, 'fim': 7.5}, tpl_real, 8)
    pp, _ = ed.corrigir(pp, [{'acao': 'encurtar_pausa', 'ini_ms': 2000, 'fim_ms': 4000}, {'acao': 'suavizar_cortes'}], 8)
    pasta = TMP / 'trab'
    pasta.mkdir()
    saida = ed.executar_corte(pp, bom, {'ini': 0.5, 'fim': 7.5, 'gancho': ''}, [], tpl_real, TMP / 'corte.mp4', pasta)
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(saida)], capture_output=True, text=True).stdout)
    check(abs(dur - ed.duracao_saida(pp)) < 0.3, f'vídeo final com {dur:.2f}s (plano pede {ed.duracao_saida(pp):.2f}s)')
    md = dq.medir(saida)
    check(md['n_erros_decodificacao'] == 0 and not md['travadas'], 'saída sem erro de decodificação nem travada')
except Exception as ex:  # noqa: BLE001
    check(False, f'executar_corte: {ex}')

shutil.rmtree(TMP, ignore_errors=True)
print(f'\n{ok} ok, {falhas} falhas')
sys.exit(1 if falhas else 0)
