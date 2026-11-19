"""Pacote de publicação: capas reais, conformidade por rede, descrição no formato fixo, aprovação presa ao hash, sem refazer o vídeo."""
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import os, sys, subprocess, tempfile, hashlib
from pathlib import Path
TMP = Path(tempfile.mkdtemp(prefix='ec-pk-'))
os.environ['DADOS'] = str(TMP / 'dados')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agente as ag, gameplay_indexer as gi, publish_package as pub, descricao as ds, postagem as pg
ok = falhas = 0
def check(c, m):
    global ok, falhas
    if c: ok += 1
    else: falhas += 1; print('  FALHOU:', m)
def ff(*a): subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', *a], check=True)
ff('-f', 'lavfi', '-i', 'testsrc2=s=320x180:r=15:d=30', '-pix_fmt', 'yuv420p', str(TMP / 'v.mp4'))
ff('-f', 'lavfi', '-i', 'anoisesrc=a=0.004:d=30', '-f', 'lavfi', '-i', "sine=f=500:d=30,volume='if(between(t,12,13.5),0.7,0)':eval=frame", '-filter_complex', 'amix=inputs=2:duration=first:normalize=0', '-c:a', 'aac', str(TMP / 'a.m4a'))
ff('-i', str(TMP / 'v.mp4'), '-i', str(TMP / 'a.m4a'), '-c:v', 'copy', '-c:a', 'copy', '-shortest', str(TMP / 'jogo.mp4'))
rel = gi.analisar_arquivo(TMP / 'jogo.mp4', [(12.2, 12.6, 'NOSSA!')], fonte='https://exemplo.com/video', direitos={'origem': 'meu', 'nota': ''}, titulo='Meu gameplay', usar_ia=False)
d1 = rel['destaques'][0]
class Ctx:
    def __init__(self, dados): self.dados = dados; self.id = 'x'
    def progresso(self, *a): pass
    def cancelado(self): return False
res = gi.job_cortar(Ctx({'gid': rel['id'], 'destaque': d1['id'], 'ini': d1['ini'], 'fim': d1['fim'], 'gancho': d1['ganchos'][0]}))['resultado']
c = next(x for x in ag.estado()['cortes'] if x['id'] == res['corte'])
c['hashtags'] = ['#games', 'gameplay', '#Games']
pk = pub.montar(c, ['youtube', 'tiktok', 'kwai'])
check(len(pk['capas']) == 3 and all(x['bytes'] > 1500 for x in pk['capas']), f'3 sugestões de capa, quadros reais ({len(pk["capas"])})')
arq = pub.capa_arquivo(c['id'], 0); check(arq.read_bytes()[:3] == b'\xff\xd8\xff', 'a capa é um JPEG de verdade')
check(len({x['t'] for x in pk['capas']}) == 3, 'capas de momentos diferentes')
f = pk['fatos']; check(f['tem_audio'] and f['codec_video'] == 'h264' and f['altura'] > f['largura'], f'fatos do MP4 lidos ({f["largura"]}x{f["altura"]}, {f["codec_video"]})')
d = pk['descricao']
check(d.startswith(pk['titulo']) and '#games #gameplay' in d and d.endswith('.\n.\n.\nLink original do vídeo [https://exemplo.com/video]'), f'descrição no formato fixo ({d!r})')
check(d.rstrip().split('\n')[-1].startswith('Link original do vídeo [') and ds.aplicado(d), 'nada depois do rodapé')
check(pk['comentario_fixado']['automatico'] is False and 'copie' in pk['comentario_fixado']['aviso'], 'comentário fixado é só texto copiável')
conf = pk['conformidade']
check(set(conf) == {'youtube', 'tiktok', 'kwai'} and all(i['item'] for r in conf.values() for i in r['itens']), 'relatório por rede')
check(any(i['item'] == 'Conta conectada' and i['estado'] == 'erro' for i in conf['youtube']['itens']) and not conf['youtube']['pode_aprovar'], 'conta não conectada bloqueia a aprovação dessa rede')
check(any(i['item'] == 'Conta conectada' and i['estado'] == 'aviso' for i in conf['kwai']['itens']) and conf['kwai']['pode_aprovar'], 'Kwai é manual (aviso, não bloqueia)')
check(any(i['estado'] == 'nao_verificado' for i in conf['youtube']['itens']), 'o que não dá para checar aparece como "não verificado"')
check(all(i['estado'] == 'ok' for r in conf.values() for i in r['itens'] if i['item'] in ('Formato vertical 9:16', 'Codec', 'Duração', 'Formato da descrição')), 'formato, codec, duração e descrição passam')
# sem conta conectada o pacote não aprova; só com a rede manual aprova
try: pub.aprovar(c['id'], 'teste'); check(False, 'deveria recusar (YouTube/TikTok sem conta)')
except pub.ErroPacote as e: check('Conta conectada' in str(e), 'aprovar recusa enquanto houver erro')
pk = pub.editar(c['id'], {'redes': ['kwai']})
ap = pub.aprovar(c['id'], 'teste'); check(ap['aprovado_agora'] and ap['aprovado']['hash'] == ap['hash'], 'aprova o pacote exato')
h1, vid_sha = ap['hash'], hashlib.sha256(pg.video_path(c['video']).read_bytes()).hexdigest()
# mudar a descrição: revalida, derruba a aprovação, NÃO refaz o vídeo
novo = ds.compor('Outro título', ['#novo'], 'https://exemplo.com/video')
e = pub.editar(c['id'], {'descricao': novo})
check(not e['aprovado_agora'] and e['hash'] != h1 and e['descricao_editada'], 'editar a descrição derruba a aprovação')
check(hashlib.sha256(pg.video_path(c['video']).read_bytes()).hexdigest() == vid_sha, 'o vídeo não foi refeito')
try: pub.editar(c['id'], {'descricao': novo + '\nMais um texto depois'}); check(False, 'texto depois do rodapé')
except pub.ErroPacote: check(True, '')
e = pub.editar(c['id'], {'descricao': 'sem formato nenhum'}) if False else None
e = pub.editar(c['id'], {'capa': 2}); check(e['capa_escolhida'] == 2 and not e['aprovado_agora'], 'trocar a capa também pede nova aprovação')
ap = pub.aprovar(c['id'], 'teste'); check(ap['aprovado_agora'], 'aprova de novo')
# o agendamento só usa pacote aprovado
sit = pub.situacao(c); check(sit['aprovado'] and sit['descricao'] == novo, 'a situação usa o texto aprovado')
pub.editar(c['id'], {'titulo': 'Título novo'}); check(not pub.situacao(c)['aprovado'], 'mudou depois de aprovar: a publicação é barrada')
conf2 = ag.conferir(next(x for x in ag.estado()['cortes'] if x['id'] == c['id']))
check(any('pacote de publicação' in b for b in conf2['bloqueios']) and not any('pacote de publicação' in b for b in conf2['liberaveis']), 'conferir barra o corte e a liberação especial não passa por cima')
c2 = dict(c, id='semPacote'); check(pub.situacao(c2) is None, 'corte sem pacote segue o fluxo antigo')
print('TUDO OK' if not falhas else f'{falhas} FALHAS', f'({ok} ok)'); sys.exit(1 if falhas else 0)
