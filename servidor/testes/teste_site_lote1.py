"""Lote 1 do site (S1–S6), pelo lado do servidor, sem internet: o que o site grava volta igual ao reabrir.

Rodar: cd servidor && PYTHONPATH=. python3 testes/teste_site_lote1.py
Cobre: S2 cena de 10 s com 3 planos (tempo, ação, trava) salva e reaberta + projeto antigo sem planos;
S3 série com temporada, 2 episódios, personagem com voz, rig, pose desenhada pelo motor e boca de uma fala WAV;
S4 quadro real de duas versões do vídeo e correção registrada sem aprovar sozinha; S5 demonstração "atualizar"
não apaga a antiga; S6 GET de um trabalho da fila (progresso que sobrevive ao recarregar).
FFmpeg de verdade. Não vale como teste no Android.
"""
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='site-lote1-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import banco as db  # noqa: E402
import api_v1  # noqa: E402
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
    """Pedido falso para api_v1.tratar (corpo e cabeçalhos)."""
    def __init__(self, caminho, corpo=None):
        self.path = caminho
        self.corpo = json.dumps(corpo or {}).encode()
        self.headers = {}


def api(metodo, caminho, corpo=None):
    return api_v1.tratar(H(caminho, corpo), metodo, caminho.split('?')[0], {'nome': 'teste', 'id': 's1'})


class Ctx:
    def __init__(self, dados):
        self.dados, self.id = dados, 'j-teste'

    def progresso(self, *a):
        pass

    def cancelado(self):
        return False


db.migrar()
api_v1.iniciar()
productor_ini = getattr(produtor, 'iniciar', None)
productor_ini() if productor_ini else None

# ---------------------------------------------------------------- S2
print('\nS2 — planos dentro da cena')
p = produtor.novo({'briefing': {'tema': 'Teste de planos', 'estilo': 'animado2d'},
                   'roteiro': {'titulo': 'Planos', 'cenas': [{'titulo': 'Cena longa', 'texto': 'Uma cena de dez segundos.'}]}})
pid = p['id']
cena = dict(pj.obter(pid)['dados']['cenas'][0])
cena['duracao_alvo'] = 10
cena['planos'] = [{'id': 'p1', 'plano': 'WS', 'peso': 0.8, 'acao': 'Ana entra pela esquerda', 'camera': 'aproximar'},
                  {'id': 'p2', 'plano': 'MS', 'peso': 1.2, 'acao': 'Ana olha o céu', 'bloqueado': True},
                  {'id': 'p3', 'plano': 'CU', 'peso': 1.0, 'acao': 'Ana sorri', 'foco_x': 0.4, 'foco_y': 0.35}]
rev = pj.obter(pid)['revisao']
produtor.salvar_storyboard(pid, rev, {'cenas': [cena]})
volta = pj.obter(pid)['dados']['cenas'][0]
pls = volta.get('planos') or []
confere(len(pls) == 3, 'cena reaberta com 3 planos')
confere([x.get('peso') for x in pls] == [0.8, 1.2, 1.0], f'tempos (pesos) preservados: {[x.get("peso") for x in pls]}')
confere([x.get('acao') for x in pls] == ['Ana entra pela esquerda', 'Ana olha o céu', 'Ana sorri'], 'ações preservadas')
confere(pls[1].get('bloqueado') is True and not pls[0].get('bloqueado'), 'trava só no plano 2')
confere(volta.get('duracao_alvo') == 10, 'duração da cena = 10 s')
tempos = [round(10 * x['peso'] / sum(y['peso'] for y in pls), 2) for x in pls]
confere(abs(sum(tempos) - 10) < 0.05, f'segundos por plano somam 10: {tempos}')
try:
    produtor.refazer_cena(pid, 0, plano='p2')
    confere(False, 'refazer plano travado deveria ser recusado')
except pj.ErroProjeto as e:
    confere(e.status == 409 if hasattr(e, 'status') else '409' in str(e) or 'travado' in str(e), 'refazer plano travado: recusado (409)')
# projeto antigo: cena sem planos[] continua abrindo e validando
antigo = produtor.novo({'briefing': {'tema': 'Antigo'}, 'roteiro': {'titulo': 'Antigo', 'cenas': [{'titulo': 'A', 'texto': 'Sem planos.'}]}})
def tirar_planos(d, _p):
    for c in d['cenas']:
        c.pop('planos', None)
pj.mudar_dados(antigo['id'], tirar_planos)
d_ant = api('GET', f'/api/v1/projetos/{antigo["id"]}')
confere(d_ant['dados']['cenas'][0].get('planos') in (None, []), 'projeto antigo abre sem planos[]')
produtor.salvar_storyboard(antigo['id'], d_ant['revisao'], {'cenas': d_ant['dados']['cenas']})
confere(pj.obter(antigo['id'])['dados']['cenas'][0]['texto'] == 'Sem planos.', 'projeto antigo salva de novo sem erro')

# ---------------------------------------------------------------- S3
print('\nS3 — série, temporada, episódios, personagem, voz, pose e boca')
s = api('POST', '/api/v1/series', {'titulo': 'Série teste', 'genero': 'aventura'})
sid = s['id']
t1 = api('POST', f'/api/v1/series/{sid}/temporadas', {})
per = api('POST', '/api/v1/personagens', {'serie_id': sid, 'dados': {'nome': 'Ana', 'voz': 'Kore', 'cabelo_tipo': 'longo', 'roupa': '#e63946'}})
e1 = api('POST', f'/api/v1/series/{sid}/episodios', {'titulo': 'Um', 'resumo': 'Ana acha um mapa.', 'produzir': False, 'temporada_id': t1['id']})
e2 = api('POST', f'/api/v1/series/{sid}/episodios', {'titulo': 'Dois', 'resumo': 'Ana segue o mapa.', 'produzir': False, 'temporada_id': t1['id']})
s2 = api('GET', f'/api/v1/series/{sid}')
confere(len(s2['episodios']) == 2 and all(e['temporada_id'] == t1['id'] for e in s2['episodios']), 'dois episódios na temporada 1')
confere(len({e['projeto_id'] for e in s2['episodios']}) == 2, 'cada episódio é um projeto (sem duplicar)')
confere(s2['personagens'][0]['dados']['voz'] == 'Kore', 'personagem ligado à voz Kore')
rig = api('GET', f'/api/v1/personagens/{per["id"]}/rig')
confere(len(rig['biblioteca']['pecas']) > 10 and 'Só vista de frente' in rig['biblioteca']['limites'], 'rig: peças e limites (modo não suportado) informados')
r = api('POST', f'/api/v1/personagens/{per["id"]}/pose', {'pose': 'maos_na_cintura', 'objeto': 'livro', 'expressao': 'feliz'})
confere(bool(r.get('job')), 'pose entra na fila do celular (trabalho pesado)')
job = fila.obter(r['job'])
res = api_v1.job_pose(Ctx(json.loads(job['dados'])))
png = res['resultado']['png']
confere(png.startswith('data:image/png;base64,') and len(png) > 5000, 'motor desenhou a pose (PNG real)')
r2 = api('POST', f'/api/v1/personagens/{per["id"]}/pose', {'pose': 'maos_na_cintura', 'objeto': 'livro', 'expressao': 'feliz'})
confere(r2.get('png') == png, 'segunda vez sai do cache')
api('PUT', f'/api/v1/series/{sid}/biblia', {'entradas': [{'tipo': 'pose', 'alvo': per['id'], 'texto': 'Pose aprovada de Ana: Mãos na cintura, segurando livro, rosto feliz.', 'estado': 'aprovada'}]})
confere(any(b['tipo'] == 'pose' for b in api('GET', f'/api/v1/series/{sid}')['biblia']), 'pose aprovada guardada na série (recuperável)')
# boca: fala WAV real (sílabas em volume variado)
wav = TMP / 'fala.wav'
with wave.open(str(wav), 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
    w.writeframes(b''.join(struct.pack('<h', int(9000 * math.sin(2 * math.pi * 220 * i / 24000) * max(0, math.sin(2 * math.pi * 3 * i / 24000))))
                           for i in range(24000 * 2)))
a = pj.registrar_asset(wav, 'fala.wav', 'audio/wav', '', 'teste')['asset']
v = api('POST', '/api/v1/personagens/visemas', {'asset': a['id'], 'texto': 'Quem está aí?'})
confere(abs(v['dur'] - 2.0) < 0.1 and len(v['niveis']) >= 22 and max(v['niveis']) >= 2 and min(v['niveis']) == 0,
        f'boca calculada da fala: {len(v["niveis"])} quadros, modo {v["modo"]}')
confere(next((e for e in s2['episodios'] if e['id'] == e1['id']), None) is not None and e2['ordem'] == 2, 'ordem dos episódios 1 e 2')

# ---------------------------------------------------------------- S4
print('\nS4 — quadro real por versão e correção sem aprovar sozinho')
vids = []
for k, cor in enumerate(('red', 'blue')):
    arq = TMP / f'v{k + 1}.mp4'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'color=c={cor}:s=360x640:d=3', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(arq)], check=True)
    rid = f'r{k + 1}teste'
    db.executar('INSERT INTO renders (id, projeto, versao, arquivo, sha256, duracao, codec, largura, altura, validado, alertas, criado) VALUES (?,?,?,?,?,?,?,?,?,1,?,?)',
                rid, pid, k + 1, str(arq), 'x' * 64, 3.0, 'h264', 360, 640, '[]', 0)
    vids.append(rid)
q = api('POST', f'/api/v1/projetos/{pid}/quadros', {'t': 1.5, 'renders': vids + ['naoexiste']})['quadros']
confere(q['r1teste']['jpg'].startswith('data:image/jpeg') and q['r2teste']['jpg'].startswith('data:image/jpeg'), 'quadro de verdade das versões 1 e 2 no mesmo instante')
confere(q['r1teste']['jpg'] != q['r2teste']['jpg'], 'as duas versões dão quadros diferentes (antes x depois)')
confere('erro' in q['naoexiste'], 'versão de outro projeto/inexistente: erro legível')
def por_render(d, _p):
    d['render'] = {'id': 'r1teste', 'versao': 1}
    d['qualidade'] = {'status': 'alerta_visual', 'problemas': [{'tipo': 'quadro_escuro', 'severidade': 'media', 'cena_id': d['cenas'][0]['id'], 'plano_id': 'p1', 'timecode': '00:01.500', 'tentativas': 0}],
                      'tecnico': {'erros': [], 'avisos': []}}
    return {'status': 'ready_for_review'}
pj.mudar_dados(pid, por_render)
cid = pj.obter(pid)['dados']['cenas'][0]['id']
api('POST', f'/api/v1/projetos/{pid}/cenas/0/refazer', {'plano': 'p1', 'problema': {'tipo': 'quadro_escuro', 'cena_id': cid, 'plano_id': 'p1', 'timecode': '00:01.500'}})
d4 = pj.obter(pid)
cor = (d4['dados'].get('correcoes') or [{}])[-1]
confere(cor.get('tipo') == 'quadro_escuro' and cor.get('render_antes') == 'r1teste' and cor.get('versao_antes') == 1, 'correção registra o defeito e a versão de antes')
confere(d4['dados']['qualidade']['problemas'][0]['tentativas'] == 1, 'tentativa contada no apontamento')
confere(d4['status'] != 'approved', f'não aprova sozinho (status {d4["status"]})')

# ---------------------------------------------------------------- S6 / S5
print('\nS6 / S5 — trabalho da fila por id e atualizar demonstração')
j = api('GET', f'/api/v1/fila/{r["job"]}')
confere(j['id'] == r['job'] and isinstance(j['dados'], dict), 'GET de um trabalho da fila (o site retoma o progresso depois de recarregar)')
try:
    api('GET', '/api/v1/fila/naoexiste')
    confere(False, 'trabalho inexistente deveria dar 404')
except pj.ErroProjeto:
    confere(True, 'trabalho inexistente: 404 legível')
db.kv_gravar('demo:lousa_giz:9:16:%s' % api_v1.ec.VERSAO_MOTOR, {'asset': 'antigo', 'segundos': 1})
rj = api('POST', '/api/v1/estilos/lousa_giz/demo', {'formato': '9:16', 'refazer': True})
confere('job' in rj and json.loads(fila.obter(rj['job']['id'])['dados'])['refazer'] is True, 'atualizar demonstração entra na fila')
confere(db.kv('demo:lousa_giz:9:16:%s' % api_v1.ec.VERSAO_MOTOR)['asset'] == 'antigo', 'a demonstração antiga continua valendo até a nova passar')
rs = api('POST', '/api/v1/estilos/lousa_giz/demo', {'formato': '9:16'})
confere(rs.get('pronto', {}).get('asset') == 'antigo', 'sem "atualizar", devolve a pronta (nada muda pelo card)')

print(f'\n{"TUDO OK" if not falhas else f"{falhas} FALHA(S)"}  (pasta {TMP})')
sys.exit(1 if falhas else 0)
