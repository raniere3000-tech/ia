"""Perfis de canal: herança por camadas, versões, isolamento entre perfis e redes de destino, com cortes renderizados de verdade."""
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import os, sys, subprocess, tempfile
from pathlib import Path
TMP = Path(tempfile.mkdtemp(prefix='ec-pf-'))
os.environ['DADOS'] = str(TMP / 'dados')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agente as ag, gameplay_indexer as gi, perfis as pf, modelos as mo, postagem as pg
ok = falhas = 0
def check(c, m):
    global ok, falhas
    if c: ok += 1
    else: falhas += 1; print('  FALHOU:', m)
def ff(*a): subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', *a], check=True)
# vídeo de 30 s com um pico de som
ff('-f', 'lavfi', '-i', 'testsrc2=s=320x180:r=15:d=30', '-pix_fmt', 'yuv420p', str(TMP / 'v.mp4'))
ff('-f', 'lavfi', '-i', 'anoisesrc=a=0.004:d=30', '-f', 'lavfi', '-i', "sine=f=500:d=30,volume='if(between(t,12,13.5),0.7,0)':eval=frame", '-filter_complex', 'amix=inputs=2:duration=first:normalize=0', '-c:a', 'aac', str(TMP / 'a.m4a'))
ff('-i', str(TMP / 'v.mp4'), '-i', str(TMP / 'a.m4a'), '-c:v', 'copy', '-c:a', 'copy', '-shortest', str(TMP / 'jogo.mp4'))
# dois perfis distintos
A = pf.salvar({'nome': 'Canal Games', 'nicho': 'Games', 'tom': 'animado', 'voz': 'Puck', 'cores': {'primaria': '#ff2200'}, 'redes': ['youtube'], 'hashtags_base': ['#games', '#gameplay'],
               'estilos_permitidos': ['gamer_neon'], 'modo_qualidade': 'rapido', 'templates': ['padrao']})
B = pf.salvar({'nome': 'Canal Calmo', 'nicho': 'Relax', 'tom': 'sereno', 'voz': 'Kore', 'cores': {'primaria': '#00aa55'}, 'redes': ['tiktok'], 'hashtags_base': ['#relax'],
               'estilos_permitidos': ['porcelana_suave'], 'modo_qualidade': 'caprichado', 'templates': ['padrao']})
check(A['id'] != B['id'] and len(pf.listar()) == 2, 'dois perfis criados')
# herança por camadas
site = pf.padrao_do_site(ag.config()['cortes'], ag.config()['postagem'])
r = pf.resolver(A['id'], site, projeto={'voz': 'Charon'}, corte={'modo_qualidade': 'caprichado'})
check(r['valores']['voz'] == 'Charon' and r['origem']['voz'] == 'projeto', 'projeto vence o perfil')
check(r['valores']['modo_qualidade'] == 'caprichado' and r['origem']['modo_qualidade'] == 'corte', 'corte vence o projeto e o perfil')
check(r['valores']['nicho'] == 'Games' and r['origem']['nicho'] == 'perfil' and r['origem']['hashtags_base'] == 'perfil', 'perfil vence o padrão do site')
r0 = pf.resolver('', site); check(r0['origem'].get('voz') == 'site' and 'nicho' not in r0['valores'], 'sem perfil vale o padrão do site')
rb = pf.resolver(B['id'], site)
check(rb['valores']['voz'] == 'Kore' and rb['valores']['redes'] == ['tiktok'] and rb['valores']['hashtags_base'] == ['#relax'] and '#games' not in str(rb['valores']), 'um perfil nunca herda nada do outro')
# versões
A2 = pf.salvar({**{k: A[k] for k in pf.limpar({'nome': 'x'})}, 'tom': 'bem animado'}, A['id'])
check(A2['versao'] == 2 and A2['tom'] == 'bem animado' and len(A2['historico']) == 2, 'alterar guarda uma nova versão')
check(pf.salvar({k: A2[k] for k in pf.limpar({'nome': 'x'})}, A['id'])['versao'] == 2, 'salvar sem mudar não cria versão')
check(pf.restaurar(A['id'], 1)['tom'] == 'animado', 'voltar à versão 1')
C = pf.duplicar(B['id']); check(C['nome'] == 'Canal Calmo (cópia)' and C['id'] != B['id'] and C['redes'] == ['tiktok'], 'duplicar perfil')
pf.apagar(C['id']); check(len(pf.listar()) == 2, 'apagar perfil')
# validação com o que existe de verdade: sem conta conectada, o perfil avisa
prob = pf.validar(A['id'], [m['id'] for m in mo.biblioteca()['modelos']], ['Puck', 'Kore'])
check(any('Youtube' in p and 'não está conectada' in p for p in prob), f'rede sem conta conectada vira aviso ({prob})')
try: pf.salvar({'nome': ''}); check(False, 'nome vazio')
except pf.ErroPerfil: check(True, '')
check(pf.limpar({'nome': 'x', 'estilos_permitidos': ['nao_existe', 'retro_vhs'], 'redes': ['orkut', 'kwai'], 'cores': {'primaria': 'vermelho'}})['estilos_permitidos'] == ['retro_vhs'], 'limpeza: estilo e rede que não existem somem')
# dois cortes do MESMO trecho, um por perfil
rel = gi.analisar_arquivo(TMP / 'jogo.mp4', [(12.2, 12.6, 'NOSSA!'), (12.7, 13.2, 'olha')], fonte='arquivo', direitos={'origem': 'meu', 'nota': ''}, titulo='Teste', usar_ia=False)
d1 = rel['destaques'][0]
class Ctx:
    def __init__(self, dados): self.dados = dados; self.id = 'x'
    def progresso(self, *a): pass
    def cancelado(self): return False
cortes = {}
for nome, P in (('A', A), ('B', B)):
    res = gi.job_cortar(Ctx({'gid': rel['id'], 'destaque': d1['id'], 'ini': d1['ini'], 'fim': d1['fim'], 'perfil': P['id'], 'gancho': d1['ganchos'][0]}))['resultado']
    cortes[nome] = next(c for c in ag.estado()['cortes'] if c['id'] == res['corte'])
a, b = cortes['A'], cortes['B']
check(a['perfil'] == A['id'] and b['perfil'] == B['id'], 'cada corte guarda o seu perfil')
check(a['redes'] == ['youtube'] and b['redes'] == ['tiktok'], 'redes de destino certas em cada corte')
check('#games' in a['hashtags'] and '#relax' not in a['hashtags'] and '#relax' in b['hashtags'] and '#games' not in b['hashtags'], 'hashtags isoladas')
va = [v for v in a['variacoes'] if v.startswith('Perfil')][0]; vb = [v for v in b['variacoes'] if v.startswith('Perfil')][0]
check('#ff2200' in va and 'Neon' in va and '#00aa55' in vb and 'Porcelana' in vb and '#00aa55' not in va, f'cores e estilos isolados ({va} | {vb})')
check(any('Modo Rápido' in v for v in a['variacoes']) and any('Modo Caprichado' in v for v in b['variacoes']), 'o modo de qualidade vem do perfil')
fa, fb = ag.pg.video_path(a['video']).read_bytes(), ag.pg.video_path(b['video']).read_bytes()
check(fa != fb and a['hash'] != b['hash'], 'os dois vídeos saem diferentes')
# Agente 2: redes do perfil entram no agendamento (e redes desligadas em Postagem são recusadas)
ag.salvar_config({'postagem': {'redes': ['youtube'], 'horarios': [{'dia': d, 'hora': 10} for d in range(7)]}})
try:
    ag._mudar(lambda e: [x.update(status='pronto', espera=False) for x in e['cortes'] if x['id'] in (a['id'], b['id'])])
    ag.agendar_corte(b['id'], liberado=True); check(False, 'perfil com rede desligada em Postagem deveria ser recusado')
except ag.ErroAgente as e:
    check('Tiktok' in str(e) and 'não está ligada' in str(e), f'rede do perfil desligada em Postagem é recusada ({str(e)[:120]})')
print('TUDO OK' if not falhas else f'{falhas} FALHAS', f'({ok} ok)'); sys.exit(1 if falhas else 0)
