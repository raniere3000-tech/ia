"""Testes do lote 3 (motor do servidor Termux): T2 rig 2D, T3 planos por pedaço, T4 qualidade, T5 efeitos, T6 backup/métricas.
Rodam no computador: provam que o código funciona, NÃO medem o celular.

Uso: cd servidor && python testes/teste_motor.py
"""
from __future__ import annotations

import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import sys
import tempfile
import time
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-motor-'))
os.environ['DADOS'] = str(TMP / 'dados')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import estilos_codigo as ec  # noqa: E402
import renderizador as rd  # noqa: E402
import rig2d  # noqa: E402

ok_n = falhas = 0


def confere(cond, nome):
    global ok_n, falhas
    if cond:
        ok_n += 1
        print('  ok ', nome)
    else:
        falhas += 1
        print('  FALHA', nome)


def secao(nome):
    print(nome, flush=True)


# ---------------------------------------------------------------- T2
secao('T2: boneco 2D articulado')
erro_max = 0.0
for alvo in rig2d.ALVOS_ALCANCE.values():
    for ld in (1, -1):
        a1, a2 = rig2d.ik2(alvo[0] * ld, alvo[1], dobra=-ld)
        hx, hy = rig2d.mao(a1, a2)
        erro_max = max(erro_max, abs(hx - alvo[0] * ld) + abs(hy - alvo[1]))
confere(erro_max < 0.05, f'IK leva a mão exatamente ao alvo em todos os pontos de alcance (erro {erro_max:.4f})')
a1, a2 = rig2d.ik2(80, 0)
hx, hy = rig2d.mao(a1, a2)
confere(abs(hy) < 0.5 and hx > 28, 'alvo fora do alcance: o braço estica na direção dele, sem quebrar')
el = rig2d.validar_elenco([{'personagem_id': 'ana', 'acoes': [
    {'t': 0, 'tipo': 'pose', 'pose': 'comemorar'}, {'t': 1, 'tipo': 'pose', 'pose': 'voar'}, {'t': 2, 'tipo': 'segurar', 'objeto': 'bola'},
    {'t': 3, 'tipo': 'segurar', 'objeto': 'espada'}, {'t': 4, 'tipo': 'alcancar', 'alvo': 'mesa', 'lado': 'esquerda'}, {'t': 5, 'tipo': 'olhar', 'objeto': 'bola'}]}])
ac = el[0]['acoes']
confere([a['tipo'] for a in ac] == ['pose', 'segurar', 'segurar', 'alcancar', 'olhar'], 'pose desconhecida é descartada; ações do catálogo ficam')
confere(ac[1].get('objeto') == 'bola' and 'objeto' not in ac[2] and 'objeto' not in ac[4], 'só objetos da lista e só em ações de mão')
confere(ac[3]['alvo'] == 'mesa' and ac[3]['lado'] == 'esquerda', 'alcançar guarda alvo e lado')
confere(rig2d.nucleos('Bola azul e pipa') == [3, 2, 2, 3, 4, 4, 2], 'vogais do texto viram formas de boca (a, o/u, e/i)')
wav = TMP / 'fala.wav'
rd.rodar(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', "aevalsrc='0.6*sin(2*PI*220*t)*max(0,sin(2*PI*2*t))':s=24000:d=3",
          '-ac', '1', '-c:a', 'pcm_s16le', str(wav)])
nv, modo = rig2d.visemas(wav, 3.0, 'Olá, tudo bem?')
confere(modo.startswith('texto + volume') and set(nv) - {0, 1} <= {2, 3, 4} and any(v >= 2 for v in nv), 'com texto: boca por texto + volume (marcado como aproximação)')
confere(rig2d.visemas(wav, 3.0, '')[1].startswith('volume') and rig2d.visemas(None, 3.0, 'oi')[1] == 'sem fala', 'sem texto: só volume; sem áudio: boca parada')
pasta_rig = TMP / 'rig'
p = rig2d.validar_personagem({'nome': 'Ana', 'cabelo_tipo': 'longo', 'roupa': '#e63946'})
b1 = rig2d.biblioteca(p, pasta_rig)
b2 = rig2d.biblioteca(dict(p, nome='Ana renomeada', voz='Kore'), pasta_rig)
confere(b1['pecas'] == b2['pecas'] and b1['assinatura'] == b2['assinatura'], 'mesmo personagem = mesmas peças (nome e voz não mexem no desenho)')
b3 = rig2d.biblioteca(dict(p, roupa='#00ff00'), pasta_rig)
confere(b3['assinatura'] != b1['assinatura'] and b3['pecas']['tronco'] != b1['pecas']['tronco'], 'trocar a roupa muda a assinatura (nada muda escondido)')
confere(set(b1['poses']) == set(rig2d.POSES) and 'alcancar' in b1['acoes'] and b1['versao_rig'] == rig2d.VERSAO_RIG, 'biblioteca lista poses, ações e versão do rig')
cena = ec.validar_cena({'texto': 'Peguei a bola!', 'personagem': 'ana', 'elenco': [
    {'personagem_id': 'ana', 'posicao': 'centro', 'expressao': 'feliz', 'acoes': [
        {'t': 0.1, 'tipo': 'alcancar', 'alvo': 'chao', 'lado': 'direita', 'objeto': 'bola', 'dur': 1.0},
        {'t': 1.2, 'tipo': 'pose', 'pose': 'comemorar', 'dur': 0.8}]}], 'planos': [{'plano': 'WS'}, {'plano': 'MS', 'personagem': 'ana'}]})
cena['_personagens'] = {'ana': p}
cena['_audio'] = str(wav)
pasta = TMP / 'cena2d'
pasta.mkdir()
arq = pasta / 'c.mp4'
cmd = ec.montar('animado2d', cena, 270, 480, 2.0, pasta, None, wav, arq)
confere(any('objetos-v' in x for x in cmd), 'o objeto entra no desenho da cena')
rd.rodar(cmd, tempo_max=300)
conf = rd.conferir(arq, pasta, {'largura': 270, 'altura': 480, 'duracao': 2.0})
confere(conf['ok'], f'cena com IK, objeto e pose renderiza e passa na conferência {conf["erros"]}')
# determinismo: o mesmo pedido gera exatamente o mesmo vídeo
arq2 = pasta / 'c2.mp4'
rd.rodar(ec.montar('animado2d', cena, 270, 480, 2.0, pasta, None, wav, arq2), tempo_max=300)
confere(rd.sha256(arq) == rd.sha256(arq2), 'render determinístico: mesma cena, mesmo arquivo (sha256 igual)')

# ---------------------------------------------------------------- T3
secao('T3: render por plano')
import segmentos  # noqa: E402
c3 = ec.validar_cena({'texto': 'Três planos, um de cada vez.', 'personagem': 'ana', 'elenco': [
    {'personagem_id': 'ana', 'posicao': 'esquerda', 'expressao': 'neutro', 'acoes': [{'t': 0.2, 'tipo': 'andar', 'alvo': 'centro', 'dur': 1.5}]}],
    'planos': [{'plano': 'WS'}, {'plano': 'MS', 'personagem': 'ana'}, {'plano': 'CU', 'personagem': 'ana'}]})
c3['_personagens'] = {'ana': p}
c3['_audio'] = str(wav)
confere(segmentos.usa_segmentos('animado2d', c3) and not segmentos.usa_segmentos('animado2d', dict(c3, planos=[{'plano': 'WS'}]))
        and not segmentos.usa_segmentos('animado3d', c3), 'só cenas com 2+ planos (e fora do 3D) vão por pedaço; o resto segue o caminho antigo')
pj3 = TMP / 'seg'
pj3.mkdir()
s1 = pj3 / 'cena-a.mp4'
r1 = segmentos.renderizar('animado2d', c3, 270, 480, 3.0, pj3, None, wav, None, [], 'base1', s1)
confere(r1['refeitos'] == 3 and r1['reaproveitados'] == 0, 'primeira vez: os 3 planos são feitos')
conf1 = rd.conferir(s1, pj3, {'largura': 270, 'altura': 480, 'duracao': 3.0})
confere(conf1['ok'] and abs(conf1['duracao'] - 3.0) < 0.08, f'cena montada dos pedaços tem a duração certa ({conf1["duracao"]:.3f} s) e passa na conferência {conf1["erros"]}')
cheio = pj3 / 'inteira.mp4'
t_ini = time.time()
rd.rodar(ec.montar('animado2d', c3, 270, 480, 3.0, pj3 / 'tr', None, wav, cheio) if (pj3 / 'tr').mkdir() is None else [], tempo_max=300)
t_cheia = time.time() - t_ini
confere(abs(rd.duracao(cheio) - rd.duracao(s1)) < 0.08, 'mesma duração do jeito antigo (cena inteira)')
c3b = dict(c3, planos=[c3['planos'][0], dict(c3['planos'][1], plano='CU'), c3['planos'][2]])
s2 = pj3 / 'cena-b.mp4'
r2 = segmentos.renderizar('animado2d', c3b, 270, 480, 3.0, pj3, None, wav, None, [], 'base1', s2)
confere(r2['refeitos'] == 1 and r2['reaproveitados'] == 2 and r2['planos'][1]['refeito'], 'mudou só o plano 2: só ele é refeito, os outros vêm do cache')
confere(rd.sha256(s1) != rd.sha256(s2) and rd.conferir(s2, pj3, {'largura': 270, 'altura': 480, 'duracao': 3.0})['ok'], 'vídeo novo (hash novo) e completo')
print(f'     (plano 2 sozinho: {r2["planos"][1]["segundos"]:.2f} s; cena inteira: {t_cheia:.2f} s)')
c3c = dict(c3, refazer_planos={'p1': 1})
k_a, k_c = segmentos.chaves('animado2d', 'base1', c3, 3.0), segmentos.chaves('animado2d', 'base1', c3c, 3.0)
confere(k_a[0] != k_c[0] and k_a[1:] == k_c[1:], '"refazer este plano" muda só a chave dele')
confere(segmentos.chaves('animado2d', 'base2', c3, 3.0)[1] != k_a[1], 'mudou o conteúdo da cena (texto, voz, personagem): todos os planos refazem')
# cancelar no meio e retomar
c3d = dict(c3, planos=[dict(x, peso=1.0 + k / 10) for k, x in enumerate(c3['planos'])])
feitos = []
try:
    segmentos.renderizar('animado2d', c3d, 270, 480, 3.0, pj3, None, wav, None, [], 'base1', pj3 / 'cena-d.mp4',
                         cancelado=lambda: len(feitos) >= 1, progresso=lambda x, et: feitos.append(et))
    cancelou = False
except (InterruptedError, rd.ErroRender):
    cancelou = True
confere(cancelou and not list((pj3 / 'planos').glob('*.tmp.mov')) and not (pj3 / 'cena-d.mp4').exists(), 'cancelar no meio não deixa arquivo pela metade')
r4 = segmentos.renderizar('animado2d', c3d, 270, 480, 3.0, pj3, None, wav, None, [], 'base1', pj3 / 'cena-d.mp4')
confere(r4['refeitos'] + r4['reaproveitados'] == 3 and (pj3 / 'cena-d.mp4').exists(), 'retomar termina a cena reaproveitando o que já estava pronto')

# ---------------------------------------------------------------- T4
secao('T4: diretor de qualidade')
import qualidade as qd  # noqa: E402
c4 = ec.validar_cena({'id': 'c4', 'texto': 'Vou correr até lá!', 'personagem': 'ana', 'elenco': [
    {'personagem_id': 'ana', 'posicao': 'esquerda', 'acoes': [{'t': 0.0, 'tipo': 'correr', 'alvo': 'direita', 'dur': 1.5}]},
    {'personagem_id': 'beto', 'posicao': 'direita', 'acoes': []}],
    'planos': [{'plano': 'CU', 'personagem': 'ana'}, {'plano': 'WS'}]})
ach = qd.geometria(c4, 4.0, 1080, 1920)
tipos = {a['tipo'] for a in ach}
confere('sai_do_quadro' in tipos, 'close em quem corre: "sai do quadro" com evidência e instante')
confere('sobreposicao' in tipos, 'dois personagens no mesmo lugar: "um esconde o outro"')
a0 = next(a for a in ach if a['tipo'] == 'sai_do_quadro')
confere(all(k in a0 for k in ('status', 'cena_id', 'plano_id', 'timecode', 'evidencia', 'tipo', 'severidade', 'proposta', 'tentativas', 'natureza'))
        and a0['natureza'] == 'objetivo', 'laudo com todos os campos pedidos (status, cena, plano, timecode, evidência, tipo, severidade, proposta, tentativas)')
m1 = qd.correcao(c4, ach, 'animado2d')
confere(m1 and m1['planos'][0]['plano'] == 'WS' and next(e for e in m1['elenco'] if e['personagem_id'] == 'beto')['posicao'] == 'centro',
        'correção localizada: close vira aberto e quem não fala vai para um lado livre')
c4b = dict(c4, **m1)
confere(not {'sai_do_quadro', 'sobreposicao'} & {a['tipo'] for a in qd.geometria(c4b, 4.0, 1080, 1920)}, 'depois da correção o defeito some')
# defeito que não tem correção segura: os dois andam para o mesmo lugar
c4c = ec.validar_cena({'id': 'c5', 'texto': 'x', 'personagem': 'ana', 'elenco': [
    {'personagem_id': 'ana', 'posicao': 'esquerda', 'acoes': [{'t': 0, 'tipo': 'andar', 'alvo': 'centro', 'dur': 0.5}]},
    {'personagem_id': 'beto', 'posicao': 'direita', 'acoes': [{'t': 0, 'tipo': 'andar', 'alvo': 'centro', 'dur': 0.5}]}], 'planos': [{'plano': 'WS'}, {'plano': 'WS'}]})
voltas, cc = 0, c4c
while voltas < 10:
    achados_ = qd.geometria(cc, 4.0, 1080, 1920)
    mm = qd.correcao(cc, achados_, 'animado2d') if voltas < qd.MAX_CORRECOES else None
    if not mm:
        break
    cc = dict(cc, **mm)
    voltas += 1
confere(voltas <= qd.MAX_CORRECOES and any(a['tipo'] == 'sobreposicao' for a in achados_), f'sem correção segura: para em {voltas} tentativa(s) e vai para revisão humana (sem laço)')
confere(qd.MAX_CORRECOES == 2, 'limite padrão: 2 correções por defeito')
r = qd.resumo([dict(a0, status='revisao_humana', tentativas=2), qd._problema('visual_ia', 'baixa', 'opinião', '', natureza='julgamento')], {'ok': True})
confere(r['status'] == 'alerta_visual' and r['revisao_humana'] == 1 and r['contagem'] == {'objetivo': 1, 'julgamento': 1},
        'alerta estético só sinaliza (não reprova); laudo separa medido de opinião')
confere(qd.resumo([], {'ok': False, 'erros': ['x']})['status'] == 'falha_tecnica', 'falha técnica reprova')
# fixtures técnicas
bom = TMP / 'bom.mp4'
rd.rodar(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=270x480:r=30:d=3', '-f', 'lavfi', '-i', 'sine=d=3',
          '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(bom)])
confere(rd.conferir(bom, TMP, {'largura': 270, 'altura': 480, 'duracao': 3})['ok'], 'vídeo bom passa')
ruim = TMP / 'ruim.mp4'
dados_ = bytearray(bom.read_bytes())
for k in range(len(dados_) // 3, len(dados_) // 3 + 4000, 7):
    dados_[k] ^= 0x5A
ruim.write_bytes(bytes(dados_))
cr = rd.conferir(ruim, TMP, {'largura': 270, 'altura': 480, 'duracao': 3})
confere(not cr['ok'] and any('decodifica' in e for e in cr['erros']), f'fixture com defeito técnico (bytes estragados) é reprovada: {cr["erros"][:1]}')
confere(not rd.conferir(bom, TMP, {'largura': 1080, 'altura': 1920, 'duracao': 3})['ok'], 'tamanho errado reprova')
srt = TMP / 'l.srt'
srt.write_text('1\n00:00:00,000 --> 00:00:02,000\noi\n\n2\n00:00:01,000 --> 00:00:00,500\nerrado\n', encoding='utf-8')
confere(not rd.conferir(bom, TMP, {'largura': 270, 'altura': 480, 'duracao': 3, 'srt': str(srt)})['ok'], 'legenda com tempo errado reprova')

# ---------------------------------------------------------------- T5
secao('T5: efeitos, som e área segura')
c5 = ec.validar_cena({'texto': 'Cuidado!', 'personagem': 'ana', 'clima': 'fumaca', 'luz': 'dramatica',
                      'sfx': [{'t': 0.5, 'tipo': 'impacto'}, {'t': 0.2, 'tipo': 'pop'}, {'t': 1, 'tipo': 'explosao_nuclear'}],
                      'elenco': [{'personagem_id': 'ana', 'posicao': 'centro', 'acoes': [{'t': 0.4, 'tipo': 'assustar'}]}],
                      'planos': [{'plano': 'WS'}, {'plano': 'MS', 'personagem': 'ana', 'tremor': True}, {'plano': 'CU', 'tremor': 'sim'}]})
confere([x['tipo'] for x in c5['sfx']] == ['pop', 'impacto'], 'efeitos sonoros: só os da lista, em ordem de tempo')
confere(c5['planos'][1].get('tremor') is True and 'tremor' not in c5['planos'][2], 'tremor só quando pedido de verdade (true)')
c5['_personagens'] = {'ana': p}
p5 = TMP / 'fx'
p5.mkdir()
cmd5 = ec.montar('animado2d', c5, 270, 480, 2.0, p5, None, wav, p5 / 'fx.mp4')
g5 = cmd5[cmd5.index('-filter_complex') + 1]
confere("sin(t*47)" in g5 and 'crop=w=iw*0.96' in g5, 'câmera treme só na janela do plano pedido (sem borda preta)')
confere(sum(1 for x in cmd5 if 'anoisesrc' in x or 'aevalsrc' in x) >= 2 and 'adelay=500|500' in g5, 'sons sintetizados entram no instante certo')
confere(any('clima-fumaca' in x for x in cmd5) and any('nuvens-' in x for x in cmd5), 'fumaça e nuvens em camada (paralaxe) entram no desenho')
rd.rodar(cmd5, tempo_max=300)
c5c = rd.conferir(p5 / 'fx.mp4', p5, {'largura': 270, 'altura': 480, 'duracao': 2.0})
confere(c5c['ok'] and not any('Silêncio' in a for a in c5c['avisos']), f'cena com efeitos e som passa na conferência {c5c["erros"]}')
ass = (p5 / 'legenda.ass').read_text(encoding='utf-8')
mv = int(next(ln for ln in ass.splitlines() if ln.startswith('Style:')).split(',')[-2])
confere(mv >= int(480 * (1 - ec.AREA_SEGURA[1])) - 1, f'legenda dentro da área segura das redes (margem de baixo {mv}px)')
cat5 = {e['id']: e for e in ec.catalogo()}
confere(all(cat5[k]['tecnologia'] and cat5[k]['limites'] for k in ('animado2d', 'documentario', 'quadrinhos')), 'Galeria: cada estilo diz como é feito e o que não faz')
confere(len(cat5) == len(ec.ESTILOS), 'nenhum cartão de estilo duplicado')

# ---------------------------------------------------------------- T7
secao('T7: 3D')
import hardware  # noqa: E402
import personagens3d as p3d  # noqa: E402
fake = Path(os.environ['DADOS']) / 'cache3d' / 'cenas'
fake.mkdir(parents=True, exist_ok=True)
import shutil  # noqa: E402
shutil.copy(bom, fake / 'antiga.mp4')
v3 = hardware.videos_3d()
confere(any(v['arquivo'].name == 'antiga.mp4' and v['tipo'].startswith('personagens') for v in v3), 'acha o vídeo 3D já feito (sem mover nem apagar)')
if p3d.disponivel():
    l3 = hardware.testar_3d(TMP / 't3d')
    t3 = {t['estilo']: t for t in l3['testes']}
    confere(t3['animado3d']['ok'] and t3['animado2d']['ok'], f'3D e 2D renderizam a mesma cena e passam na conferência ({t3["animado3d"].get("erro", "")})')
    confere(l3['estado'] == 'beta' and 'fora do celular' in l3['conclusao'], 'fora do celular: continua beta e diz que não serve para decidir')
    print(f'     (sandbox: 2D {t3["animado2d"]["seg_por_seg"]} s/s, 3D {t3["animado3d"]["seg_por_seg"]} s/s, loop 3D {t3.get("cinema3d", {}).get("seg_por_seg")} s/s)')
    confere((TMP / 't3d' / 'laudo-3d.json').exists(), 'laudo do 3D gravado')

print(f'\n{ok_n} ok, {falhas} falhas   (pasta {TMP})')
sys.exit(1 if falhas else 0)
