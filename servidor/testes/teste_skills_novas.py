"""Etapa E: as 15 skills novas (texto REAL baixado do GitHub no commit fixado, hash conferido) e os 8 perfis novos do roteador.
Sem internet, a parte "texto real" é pulada e dita como pulada (não conta como ok).

Rodar: cd servidor && PYTHONPATH=. python3 testes/teste_skills_novas.py
"""
import hashlib
import json
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='skills-novas-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')

import banco as db  # noqa: E402
from skills import catalogo as cat, roteador as rot, seguranca as sg  # noqa: E402
import agente as ag  # noqa: E402
import gameplay_indexer as gp  # noqa: E402
import produtor  # noqa: E402

NOVAS = ['yt-script', 'yt-viral', 'yt-package', 'yt-edit', 'yt-retention', 'video-highlight-skill', 'viral-reverse-engineering',
         'scripting-and-storyboarding', 'design-and-templates', 'brand-profile', 'content-pillars', 'voice-builder', 'video-packaging',
         'analytics-and-reporting', 'experimentation-and-ab-testing']
falhas = 0


def confere(c, nome):
    global falhas
    print(('ok    ' if c else 'FALHA ') + nome)
    falhas += 0 if c else 1


man = json.loads((Path(__file__).parents[1] / 'skills' / 'manifesto.json').read_text(encoding='utf-8'))
por = {s['id']: s for s in man['skills']}
ids = [s['id'] for s in man['skills']]
confere(len(ids) == len(set(ids)) and len(ids) >= 133, 'manifesto: catálogo base preservado, sem id repetido')
confere(all(i in por for i in NOVAS), 'as 15 skills estão no manifesto')
confere(all(not sg.item_manifesto_valido(por[i]) and por[i]['licenca'] == 'MIT' and por[i].get('licenca_fonte') and por[i]['tamanho'] > 0 for i in NOVAS),
        'as 15 têm commit fixado, hash, tamanho e licença MIT com a fonte da licença')
confere(all(por[i]['caminho'].endswith('SKILL.md') for i in NOVAS), 'só SKILL.md (nenhum script entra)')
confere(all(por[i]['modalidade'] == 'runtime-auditar' for i in ('yt-script', 'yt-viral', 'yt-package', 'yt-edit', 'yt-retention', 'video-highlight-skill')),
        'as skills que trazem programa ficam marcadas "não roda aqui"')
# pedido do documento: os 8 perfis existem e só apontam para skills do catálogo
NOVOS_PERFIS = {'agente1.gameplay': ['video-highlight-skill', 'yt-edit', 'viral-reverse-engineering'],
                'radar.viralidade': ['yt-viral', 'viral-reverse-engineering', 'content-pillars'],
                'agente3.ganchos': ['yt-script', 'short-drama-hook-engineering'],
                'diretor.storyboard_visual': ['scripting-and-storyboarding', 'storyboard-shot-design'],
                'site.estilos_cortes': ['design-and-templates', 'ffmpeg-media-finishing'],
                'perfil.canal': ['brand-profile', 'content-pillars', 'voice-builder'],
                'agente2.pacote': ['video-packaging', 'media-qc-delivery'],
                'agentes.aprendizado': ['analytics-and-reporting', 'yt-retention', 'experimentation-and-ab-testing']}
confere(all(p in rot.PERFIS and rot.PERFIS[p][3] == sk and all(x in por for x in sk) for p, sk in NOVOS_PERFIS.items()), 'os 8 perfis novos têm as skills combinadas')

# ---- texto real (rede)
REAIS = {}
try:
    for sid in NOVAS:
        s = por[sid]
        b = urllib.request.urlopen(urllib.request.Request(cat._raw(s, s['commit']), headers={'User-Agent': 'estudioclip-teste'}), timeout=25).read()
        REAIS[sid] = b
    rede = True
except Exception as e:  # noqa: BLE001
    rede = False
    print('PULADO (sem internet ou GitHub fora): texto real das 15 skills não foi conferido:', str(e)[:80])

if rede:
    confere(all(hashlib.sha256(REAIS[i]).hexdigest() == por[i]['sha256'] and len(REAIS[i]) == por[i]['tamanho'] for i in NOVAS),
            'texto real baixado no commit fixado bate com o hash e o tamanho do manifesto')
    db.migrar()
    cat._baixar = lambda url: next(REAIS[i] for i in NOVAS if cat._raw(por[i], por[i]['commit']) == url) if any(cat._raw(por[i], por[i]['commit']) == url for i in NOVAS) \
        else (_ for _ in ()).throw(ConnectionError('fora do teste'))
    rel = cat.instalar(NOVAS)
    confere(len(rel['instaladas']) == 15 and not rel['falhas'], '15 definições instaladas com o texto real')
    estados = {r['id']: r for r in db.todos('SELECT id, estado FROM skills_catalogo WHERE id IN (%s)' % ','.join('?' * 15), *NOVAS)}
    sem_regra = sorted(i for i in NOVAS if not cat.regras(i))
    confere(sem_regra == ['yt-viral'], f'só yt-viral fica sem regras em lista (o texto dele é prosa): {sem_regra}')
    todas = ' '.join(x for i in NOVAS if cat.regras(i) for x in cat.regras(i)[1])
    confere('woopsocial' not in todas.lower() and not re.search(r'https?://|\bcurl\b|python3|pip install', todas, re.I),
            'nenhuma regra cita o serviço externo, link, comando ou programa')
    confere(all(len(cat.regras(i)[0]) > 20 and not cat.regras(i)[0].startswith('>') for i in NOVAS if cat.regras(i)), 'a descrição de cada skill foi lida (texto em várias linhas)')
    confere(all(estados[i]['estado'] == 'regras_disponiveis' for i in NOVAS if i != 'yt-viral'), 'estado honesto: regras disponíveis (programas não rodam)')
    # perfis de skill: o roteador escolhe pela tarefa
    casos = [({'agente': 'agente1', 'tarefa': 'melhores momentos de gameplay'}, 'agente1.gameplay', 'video-highlight-skill'),
             ({'agente': 'radar', 'tarefa': 'por que viralizou no nicho'}, 'radar.viralidade', 'viral-reverse-engineering'),
             ({'agente': 'agente3', 'tarefa': 'gancho de abertura'}, 'agente3.ganchos', 'yt-script'),
             ({'agente': 'editor', 'tarefa': 'estilo dos cortes'}, 'site.estilos_cortes', 'design-and-templates'),
             ({'agente': 'canal', 'tarefa': 'perfil do canal'}, 'perfil.canal', 'brand-profile'),
             ({'agente': 'agente2', 'tarefa': 'pacote com capa e titulo'}, 'agente2.pacote', 'video-packaging'),
             ({'agente': 'aprendizado', 'tarefa': 'aprendizado das metricas'}, 'agentes.aprendizado', 'analytics-and-reporting')]
    for ped, pid, sid in casos:
        sel = rot.escolher(dict(ped, permitir_externo=True))
        confere(pid in sel['perfis'] and any(u['id'] == sid and u['perfil'] == pid for u in sel['usar']) and sel['valido'], f'roteador: "{ped["tarefa"]}" → {pid} usa {sid}')
    sel = rot.selecionar('agentes.aprendizado')
    confere(len(sel['usar']) == 3 and sel['custo'] <= sel['orcamento'], 'aprendizado: 3 skills dentro do orçamento')
    confere(any(f['id'] == 'yt-viral' and 'texto instalado' in f['motivo'] for f in rot.selecionar('radar.viralidade')['fora']),
            'yt-viral sem regras aparece como "texto instalado" e fica de fora, dito com motivo')

    # ---- uso real nos consumidores
    PEDIDOS = []

    def gemini_falso(partes, *a, uso='', **k):
        t = partes[0]['text']
        PEDIDOS.append(t)
        if 'pauteiro' in t:
            return {'ideias': [{'titulo': 'Por que o céu é azul', 'gancho': 'Você já viu?', 'porque': 'curiosidade', 'tipo': 'curiosidade', 'fato': True,
                                'risco': 'baixo', 'fontes': [{'titulo': 'NASA', 'url': 'https://nasa.gov/x'}]}]}
        if 'ganchos para um corte de gameplay' in t:
            return {'ganchos': [{'abertura_falada': 'Olha isso', 'texto_na_tela': 'ESPERA', 'primeiro_quadro_t': 10, 'eventos': ['e1'], 'justificativa': 'x'}]}
        return {'titulo': 'Céu', 'gancho': 'Por quê?', 'cenas': [{'id': 'c1', 'titulo': 'A', 'texto': 'O céu é azul.'}]}
    ag.gemini = gemini_falso
    ag.segredos = lambda: {'gemini': 'chave-de-teste'}
    r = produtor.ideias({'nicho': 'ciência', 'tema': 'céu', 'quantidade': 3, 'usar_radar': False})['ideias']
    h = rot.historico(perfil='radar.viralidade', etapa='utilizada')
    confere(r and h and h[0]['artefato'].startswith('fichas:') and h[0]['versao'] and any('[viral-reverse-engineering]' in t for t in PEDIDOS),
            'Radar: "por que viralizou" entrou no pedido e o uso foi registrado com versão e ficha')
    dest = {'ini': 0.0, 'fim': 30.0, 'eventos': ['e1']}
    ev = {'e1': {'id': 'e1', 'tipo': 'pico_de_audio', 't': 10.0, 'confianca': 0.9, 'descricao': 'pico'}}
    PEDIDOS.clear()
    gs = gp.ganchos_por_ia(dest, ev, 'documentario')
    confere(gs and any('MATERIAL DE APOIO' in t and '[video-highlight-skill]' in t for t in PEDIDOS), 'Gameplay: o pedido dos ganchos leva as regras da skill de melhores momentos')
    b = produtor.limpar_briefing({'tema': 'céu azul', 'estilo': 'animado2d'})
    from projetos import criar
    p = criar({'titulo': 'Céu', 'tipo': 'agente3', 'dados': {}})
    PEDIDOS.clear()
    produtor.gerar_roteiro(b, 'céu azul', p['id'], 'job-x')
    confere(any('[yt-script]' in t for t in PEDIDOS), 'Agente 3: o roteiro leva as regras de ganchos (yt-script)')
    confere(rot.historico(perfil='agente3.ganchos', etapa='utilizada', projeto_id=p['id']), 'Agente 3: uso de agente3.ganchos registrado só depois do roteiro existir')
    lst = rot.lista_para_voce('agente2.pacote', 'pacote:teste:abc', 'pacote montado: teste', origem='agente2')
    confere(lst and all(x.startswith('[') for x in lst) and rot.historico(perfil='agente2.pacote', etapa='utilizada'), 'Agente 2: pacote ganha lista de boas práticas e o uso é registrado')
    lst = rot.lista_para_voce('diretor.storyboard_visual', 'quadros:p:h', '3 cenas', projeto_id=p['id'], origem='diretor')
    confere(lst and rot.historico(perfil='diretor.storyboard_visual', etapa='utilizada'), 'Diretor: storyboard visual ganha lista para você conferir e o uso é registrado')
    rot.salvar_perfil('agente3.ganchos', {'ligado': False})
    PEDIDOS.clear()
    produtor.gerar_roteiro(b, 'céu azul', p['id'], 'job-y')
    confere(not any('[yt-script]' in t for t in PEDIDOS), 'perfil de ganchos desligado: o roteiro sai igual, sem as regras')

print('falhas:', falhas)
sys.exit(1 if falhas else 0)
