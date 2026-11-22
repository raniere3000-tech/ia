"""Conserto de 22/11: corte recém-aprovado pelo diretor era cancelado ("O vídeo foi apagado ou descartado") porque o Agente 1
ainda não tinha gravado o corte na lista. Confere que isso não cancela mais e que os cancelados por engano voltam a andar.

Rodar: cd servidor && python3 testes/teste_esteira_corte_salvo.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-salvo-'))
os.environ.update(DADOS=str(TMP / 'dados'), BANCO_ARQ=str(TMP / 'dados' / 'database' / 'studio.sqlite'), CHAVE_MESTRA_ARQ=str(TMP / 'chave'),
                  COORDENADOR_SEM_VIGIA='1')
os.environ.pop('ESTEIRA_COMPLETA', None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agente as ag
import banco as db
import esteira as es
import postagem as pg

db.migrar()
ok_n = falhas = 0


def confere(c, nome):
    global ok_n, falhas
    ok_n += bool(c)
    falhas += not c
    print('  ok ' if c else '  FALHOU', nome)


def aprovado_pelo_diretor(cid):
    vid = es.garantir('corte', cid, 'Corte de teste')
    es.marcar(vid, 'producao', 'concluida', recibo={'corte': cid})
    es.marcar(vid, 'a4_previo', 'concluida', recibo={'nota': 100})
    es.marcar(vid, 'a5_edicao', 'concluida', recibo={'plano_versao': 1}, saida_sha='x' * 64)
    es.marcar(vid, 'a4_final', 'concluida', recibo={'nota': 100, 'certificado': 'c1'}, saida_sha='x' * 64)
    return vid


print('1. Diretor aprovou, Agente 1 ainda não salvou o corte')
V1 = aprovado_pelo_diretor('corteA')
es.avancar(V1)
v = db.um('SELECT * FROM esteira_videos WHERE id=?', V1)
confere(v['estado'] != 'cancelado' and es._etapa(V1, 'a6_capa')['estado'] != 'cancelada', f'não cancela enquanto o corte não foi salvo (estado: {v["estado"]})')

print('2. Corte descartado de verdade: cancela')
V2 = aprovado_pelo_diretor('corteB')
ag._mudar(lambda e: e['cortes'].append({'id': 'corteB', 'video': 'arqB', 'status': 'descartado', 'titulo': 'B', 'criado': time.time()}))
es.avancar(V2)
confere(db.um('SELECT estado FROM esteira_videos WHERE id=?', V2)['estado'] == 'cancelado', 'corte descartado cancela a esteira')

print('3. Cancelado por engano volta a andar quando o corte existe')
V3 = aprovado_pelo_diretor('corteC')
es.cancelar(V3, es.MOTIVO_SUMIU)
confere(db.um('SELECT estado FROM esteira_videos WHERE id=?', V3)['estado'] == 'cancelado', 'situação do celular: cancelado com "O vídeo foi apagado ou descartado."')
pg.VIDEOS.mkdir(parents=True, exist_ok=True)
(pg.VIDEOS / 'arqC.mp4').write_bytes(b'0' * 5000)
ag._mudar(lambda e: e['cortes'].append({'id': 'corteC', 'video': 'arqC', 'status': 'pronto', 'titulo': 'C', 'criado': time.time()}))
n = es.reabrir_cancelados_por_engano()
v3 = db.um('SELECT * FROM esteira_videos WHERE id=?', V3)
confere(n == 1 and v3['estado'] != 'cancelado' and es._etapa(V3, 'a6_capa')['estado'] == 'aguardando_dependencia', f'reaberto: segue para a capa ({v3["estado"]})')
confere(es._etapa(V3, 'a4_final')['estado'] == 'concluida', 'o que já estava feito (diretor) continua valendo')
confere(es.reabrir_cancelados_por_engano() == 0, 'não reabre duas vezes')
es.cancelar(V2, es.MOTIVO_SUMIU)
confere(es.reabrir_cancelados_por_engano() == 0, 'descartado de verdade não é reaberto')

print(f'\n{ok_n} ok, {falhas} falhas')
sys.exit(1 if falhas else 0)
