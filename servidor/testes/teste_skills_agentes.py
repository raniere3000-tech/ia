"""K4/K5 de ponta a ponta, sem internet: Radar, Agente 1, Agente 2, Agente 3 e Diretor de Qualidade usam as skills e o registro
mostra skill, versão, decisão, saída útil e artefato. Depois, com os perfis desligados, tudo continua funcionando (fallback).

Rodar: cd servidor && PYTHONPATH=. python3 testes/teste_skills_agentes.py
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='skills-agentes-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')

REAL = json.loads((Path(__file__).parents[1] / 'skills' / 'manifesto.json').read_text())
TXT = lambda sid: f"""---
name: {sid}
description: Guia de teste para {sid}.
---
## Rules
- Regra um de {sid}: keep the subject readable in the frame.
- Regra dois de {sid}: check the result against the plan.
- Regra três de {sid}: avoid repeating the same idea.
""".encode()
ARQS = {}
man = dict(REAL, skills=[])
for s in REAL['skills']:
    b = TXT(s['id'])
    ARQS[s['id']] = b
    man['skills'].append(dict(s, sha256=hashlib.sha256(b).hexdigest(), licenca=s.get('licenca') or 'MIT'))
arq = TMP / 'manifesto.json'
arq.write_text(json.dumps(man))
os.environ['SKILLS_MANIFESTO'] = str(arq)

import banco as db  # noqa: E402
from skills import catalogo as cat, roteador as rot  # noqa: E402
import agente as ag  # noqa: E402
import postagem as pg  # noqa: E402
import produtor  # noqa: E402
import projetos as pj  # noqa: E402

POR_URL = {cat._raw(s, s['commit']): ARQS[s['id']] for s in man['skills']}
cat._baixar = lambda url: POR_URL[url]
falhas = 0


def confere(c, nome):
    global falhas
    print(('ok    ' if c else 'FALHA ') + nome)
    falhas += 0 if c else 1


db.migrar()
rel = cat.instalar()
confere(len(rel['instaladas']) == 133 and not rel['falhas'], '133 definições instaladas (arquivos simulados, hash conferido)')

PEDIDOS = []


def gemini_falso(partes, *a, uso='', **k):
    t = partes[0]['text']
    PEDIDOS.append(t + ' ' + ' '.join(str(x.get('text', '')) for x in partes[1:]))
    if 'pauteiro' in t:
        return {'ideias': [{'titulo': 'Por que o céu é azul', 'gancho': 'Você já viu?', 'porque': 'curiosidade', 'tipo': 'curiosidade', 'fato': True,
                            'risco': 'baixo', 'fontes': [{'titulo': 'NASA', 'url': 'https://nasa.gov/x'}]}]}
    if 'trechos de um vídeo' in t:
        return [{'inicio': 0, 'fim': 62, 'nota': 80, 'titulo': 'Trecho bom', 'gancho': 'Olha isso', 'hashtags': ['#a'], 'motivo': 'forte'}]
    if 'AVALIADOR VISUAL' in t:
        return {'pontos': [{'cena': 'c1', 'plano': 'p1', 'problema': 'rosto cortado', 'sugestao': 'abrir o plano', 'confianca': 0.9}]}
    return {'titulo': 'Céu azul', 'gancho': 'Por quê?', 'cenas': [
        {'id': 'c1', 'titulo': 'Começo', 'texto': 'O céu é azul por causa da luz.', 'planos': [{'id': 'p1', 'plano': 'WS'}, {'id': 'p2', 'plano': 'CU'}]},
        {'id': 'c2', 'titulo': 'Fim', 'texto': 'A luz azul se espalha mais.'}]}


ag.gemini = gemini_falso
ag.segredos = lambda: {'gemini': 'chave-de-teste'}


def rodada(tag: str):
    """Roda os cinco consumidores e devolve o que cada um produziu."""
    out = {}
    out['radar'] = produtor.ideias({'nicho': 'ciência', 'tema': 'céu', 'quantidade': 3, 'usar_radar': False})['ideias']
    frs = [{'ini': float(i * 5), 'fim': float(i * 5 + 4.8), 'texto': f'frase {i} do vídeo.'} for i in range(20)]
    co = {'nichos': ['ciência'], 'dur_min': 60, 'dur_max': 65, 'proibidos': [], 'idioma': 'pt', 'nota_min': 0}
    out['a1'] = ag.escolher(frs, 'Vídeo ' + tag, 1, co)
    vid = 'teste-' + tag
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=180x320:d=1', '-f', 'lavfi', '-i', 'sine=d=1',
                    '-c:v', 'libx264', '-c:a', 'aac', '-shortest', str(pg.VIDEOS / (vid + '.mp4'))], check=True)
    out['a2'] = pg.conferencia({'id': 'post-' + tag, 'video': vid, 'origem': 'manual'}, 'kwai')
    b = produtor.limpar_briefing({'tema': 'céu azul', 'estilo': 'animado2d'})
    p = pj.criar({'titulo': 'Céu ' + tag, 'tipo': 'agente3', 'dados': {}})
    out['pid'] = p['id']
    out['a3'] = produtor.gerar_roteiro(b, 'céu azul', p['id'], 'job-' + tag)
    video = TMP / f'video-{tag}.mp4'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=red:s=180x320:d=4', '-c:v', 'libx264', str(video)], check=True)
    cenas = [{'id': 'c1', 'planos': [{'id': 'p1', 'plano': 'CU', 'peso': 1.0}], 'clipe': {'dur': 4.0}}]
    out['qc'] = produtor.visao_ia(p['id'], video, 'sha-' + tag, cenas, {'qa_visao': True})
    return out


r = rodada('um')
confere(r['radar'] and r['radar'][0]['ficha'].get('skills'), 'Radar: ficha de oportunidade guarda as skills usadas')
confere(r['a1'] and r['a1'][0].get('skills') and any('analyze-video-editing' in t for t in PEDIDOS if 'trechos' in t), 'Agente 1: corte real com as skills que entraram na escolha')
bp = next((x for x in r['a2'] if x['item'] == 'boas_praticas'), {})
fm = next((x for x in r['a2'] if x['item'] == 'formato'), {})
confere('[media-provenance-rights]' in bp.get('detalhe', '') and not bp.get('bloqueia'), 'Agente 2: regras viram lista para você conferir (não liberam nada)')
confere(fm.get('ok') and 'h264' in fm.get('detalhe', ''), 'Agente 2: formato do arquivo (codec) conferido')
confere(r['a3']['skills_campos']['agente3.storyboard']['campos'] == 2, 'Agente 3: direção virou 2 planos tipados')
confere(r['qc'] and any('AVALIADOR VISUAL' in t and '[generated-media-qa]' in t and 'planejado: CU' in t for t in PEDIDOS),
        'Qualidade: o pedido visual leva as skills de QC e o enquadramento planejado')
pa = {x['id']: x for x in rot.ponta_a_ponta()}
for cid, pref in (('radar', 'fichas:'), ('agente1', 'cortes:'), ('agente2', 'post:post-um'), ('agente3', 'roteiro:'), ('qualidade', 'qualidade:sha-um')):
    x = pa[cid]
    confere(x['artefato'].startswith(pref) and x['skills'] and all(s['versao'] and s['decisao'] for s in x['skills']) and x['saida'],
            f'ponta a ponta {x["nome"]}: skill, versão, decisão, saída útil e artefato')
n = len(rot.historico(etapa='utilizada', limite=500))
pg.conferencia({'id': 'post-um', 'video': 'teste-um', 'origem': 'manual'}, 'kwai')
confere(len(rot.historico(etapa='utilizada', limite=500)) == n, 'abrir a conferência de novo não duplica o registro')

# regressão (K5): perfis desligados -> os agentes continuam funcionando, com fallback registrado
for pid in rot.PERFIS:
    rot.salvar_perfil(pid, {'ligado': False})
PEDIDOS.clear()
r2 = rodada('dois')
confere(r2['radar'] and r2['a1'] and r2['a3']['cenas'] and r2['qc'] and any(x['item'] == 'arquivo' and x['ok'] for x in r2['a2']),
        'perfis desligados: Radar, A1, A2, A3 e Qualidade continuam produzindo')
confere(not any('MATERIAL DE APOIO' in t for t in PEDIDOS), 'perfis desligados: nenhum texto de skill nos pedidos')
fb = {x['perfil'] for x in rot.historico(etapa='fallback', limite=500)}
confere({'radar.temas', 'agente1.analisar', 'agente2.publicar', 'agente3.roteiro', 'qc.validar'} <= fb, 'fallback explícito registrado em cada consumidor')
confere(not rot.historico(projeto_id=r2['pid'], etapa='utilizada'), 'sem skill, nada é registrado como "utilizada"')
print('falhas:', falhas)
sys.exit(1 if falhas else 0)
