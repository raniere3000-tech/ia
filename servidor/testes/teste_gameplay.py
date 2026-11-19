"""Gameplay Narrativa: destaques medidos de verdade (cena e som), ganchos sem inventar eventos, direitos obrigatórios. FFmpeg real."""
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')  # fluxo anterior; a esteira obrigatória dos 7 agentes tem o teste próprio (teste_esteira_7.py)
import os, sys, subprocess, tempfile
from pathlib import Path
TMP = Path(tempfile.mkdtemp(prefix='ec-gp-'))
os.environ['DADOS'] = str(TMP / 'dados')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agente as ag, gameplay_indexer as gi
ok = falhas = 0
def check(c, m):
    global ok, falhas
    if c: ok += 1
    else: falhas += 1; print('  FALHOU:', m)
def ff(*a): subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', *a], check=True)
# vídeo de 40 s: cenas trocam aos 12 s e 27 s; o som é baixo e sobe forte em 12-13.5 s e 27-28 s
for i, (fonte, d) in enumerate([('testsrc2', 12), ('smptehdbars', 15), ('mandelbrot', 13)]):
    ff('-f', 'lavfi', '-i', f'{fonte}=s=320x180:r=15:d={d}' if fonte != 'mandelbrot' else f'mandelbrot=s=320x180:r=15', '-t', str(d), '-pix_fmt', 'yuv420p', str(TMP / f'p{i}.mp4'))
(TMP / 'l.txt').write_text(''.join(f"file 'p{i}.mp4'\n" for i in range(3)))
ff('-f', 'concat', '-safe', '0', '-i', str(TMP / 'l.txt'), '-c', 'copy', str(TMP / 'v.mp4'))
ff('-f', 'lavfi', '-i', 'anoisesrc=a=0.004:d=40', '-f', 'lavfi', '-i', "sine=f=500:d=40,volume='if(between(t,12,13.5)+between(t,27,28),0.7,0)':eval=frame",
   '-filter_complex', 'amix=inputs=2:duration=first:normalize=0', '-c:a', 'aac', str(TMP / 'a.m4a'))
ff('-i', str(TMP / 'v.mp4'), '-i', str(TMP / 'a.m4a'), '-c:v', 'copy', '-c:a', 'copy', '-shortest', str(TMP / 'jogo.mp4'))
V = TMP / 'jogo.mp4'
palavras = [(12.2, 12.6, 'NOSSA!'), (12.7, 13.2, 'olha'), (13.3, 13.8, 'isso!'), (30.0, 30.4, 'tranquilo')]
cenas = gi.mudancas_de_cena(V)
check(any(abs(t - 12) < 1 for t in cenas) and any(abs(t - 27) < 1 for t in cenas), f'achou as mudanças de cena em 12 s e 27 s ({cenas})')
picos = gi._picos(gi.picos_de_audio(V))
check(any(12 <= p['t'] <= 13.6 for p in picos) and any(26.8 <= p['t'] <= 28.2 for p in picos) and not any(5 < p['t'] < 10 for p in picos), f'achou os dois picos de som e nenhum no silêncio ({[round(p["t"],1) for p in picos]})')
# sem direitos não analisa
try: gi.analisar_arquivo(V, palavras, fonte='teste', direitos={'origem': ''}, usar_ia=False); check(False, 'sem direitos deveria recusar')
except gi.ErroGameplay: check(True, '')
r = gi.analisar_arquivo(V, palavras, fonte='arquivo próprio', direitos={'origem': 'meu', 'nota': 'gravei eu'}, titulo='Teste', historia='suspense', usar_ia=False)
check(r['analise'] == 'parcial' and r['analise_motivo'], 'sem IA a análise sai marcada como parcial')
check(len(r['destaques']) >= 2, f'destaques ({len(r["destaques"])})')
ids = {e['id'] for e in r['eventos']}
check(all(e['observado'] and e['t'] >= 0 for e in r['eventos']) and any(e['tipo'] == 'fala_forte' for e in r['eventos']), 'eventos observados, com a fala forte')
for d in r['destaques']:
    check(len(d['ganchos']) >= 3, f'{d["id"]}: pelo menos 3 ganchos ({len(d["ganchos"])})')
    check(all(set(g['eventos']) <= set(d['eventos']) and d['ini'] <= g['primeiro_quadro_t'] <= d['fim'] for g in d['ganchos']), f'{d["id"]}: ganchos só citam eventos do destaque e tempo dentro da janela')
    check(len({g['abertura_falada'] for g in d['ganchos']}) >= 3, f'{d["id"]}: ganchos diferentes')
    check(d['porque'] and 0 < d['confianca'] <= 0.95, f'{d["id"]}: tem porquê e confiança')
check(r['direitos']['origem'] == 'meu' and r['fonte'] and 'Nada foi publicado' in r['aviso'], 'relatório com fonte, direitos e aviso')
check(any('NOSSA' in (g['abertura_falada']) for d in r['destaques'] for g in d['ganchos']), 'um gancho usa a fala real do vídeo')
# IA que inventa: ganchos com evento que não existe ou fora da janela são descartados
d0 = r['destaques'][0]; evs = {e['id']: e for e in r['eventos']}
ruins = [{'abertura_falada': 'Ele ganhou a partida!', 'texto_na_tela': 'GANHOU', 'primeiro_quadro_t': d0['ini'], 'eventos': ['e999']},
         {'abertura_falada': 'Olha', 'texto_na_tela': 'X', 'primeiro_quadro_t': 9999, 'eventos': d0['eventos'][:1]},
         {'abertura_falada': 'Bom gancho', 'texto_na_tela': 'OLHA ISSO', 'primeiro_quadro_t': d0['ini'] + 1, 'eventos': d0['eventos'][:1]}]
v = gi.validar_ganchos(ruins, d0, evs)
check(len(v) == 1 and v[0]['abertura_falada'] == 'Bom gancho', 'a validação derruba gancho com evento inventado ou tempo fora da janela')
ag.gemini = lambda *a, **k: {'ganchos': ruins}
pr = gi.propor_ganchos(d0, r['eventos'], 'desafio', usar_ia=True)
check(len(pr['ganchos']) >= 3 and pr['ganchos'][0]['abertura_falada'] == 'Bom gancho' and pr['origem'] == 'ia', 'ganchos da IA válidos vêm primeiro e as regras completam até 3')
def cai(*a, **k): raise ag.ErroAgente('sem chave')
ag.gemini = cai
pr = gi.propor_ganchos(d0, r['eventos'], 'desafio', usar_ia=True)
check(pr['origem'] == 'regras' and pr['aviso'] and len(pr['ganchos']) >= 3, 'IA fora do ar: usa as regras e avisa')
rel = gi.relatorio(r['id']); check('palavras' not in rel and rel['tem_video'] and gi.listar()[0]['id'] == r['id'], 'relatório enxuto e lista de análises')
r2 = gi.propor_de_novo(r['id'], 'reviravolta', usar_ia=False); check(r2['historia'] == 'reviravolta', 'trocar a história refaz os ganchos')
# corte de verdade: destaque + gancho escolhido + template + estilo visual; passa pelo diretor e NÃO sai aprovado sozinho
class Ctx:
    def __init__(self, dados): self.dados = dados; self.id = 'x'
    def progresso(self, *a): pass
    def cancelado(self): return False
ag.gemini = cai
r = gi.ler(r['id'])
d1 = r['destaques'][0]
res = gi.job_cortar(Ctx({'gid': r['id'], 'destaque': d1['id'], 'gancho': d1['ganchos'][0], 'estilo': 'retro_vhs', 'estilo_forca': 0.8}))['resultado']
cs = [c for c in ag.estado()['cortes'] if c['id'] == res['corte']]
check(len(cs) == 1 and cs[0]['tipo'] == 'gameplay' and cs[0]['status'] in ('pronto', 'reprovado'), f'corte registrado ({res})')
c = cs[0]
check(c.get('aprovado_voce') in (None, False, ''), 'não vem aprovado por você: a aprovação final continua sendo sua')
check(c['direitos']['origem'] == 'meu' and c['gameplay']['fonte'] and c['gameplay']['eventos'] and c['gameplay']['gancho'], 'o corte guarda fonte, direitos, eventos e gancho')
arq = ag.pg.video_path(c['video']); dd = ag.duracao(arq)
check(abs(dd - (c['fim'] - c['ini'])) < 0.6 and arq.stat().st_size > 5000, f'vídeo renderizado com a duração do trecho ({dd:.1f}s)')
check(c['qa'].get('diretor', {}).get('veredito') in ('aprovado', 'reprovado'), 'o diretor de qualidade olhou o corte')
import modo_render as mr
cmp_ = gi.comparar_modos(r['id'], d1['id'], 'gamer_neon')
rp, cp = cmp_['rapido'], cmp_['caprichado']
check(rp['operacoes'] and cp['operacoes'] and rp['operacoes'] != cp['operacoes'], 'os dois modos ativam operações diferentes')
check(any('loudnorm' in o for o in cp['operacoes']) and not any('loudnorm' in o for o in rp['operacoes']), 'caprichado normaliza o volume e o rápido não')
check(any('peças pesadas' in o for o in rp['operacoes']) and not any('peças pesadas' in o for o in cp['operacoes']), 'rápido tira as peças pesadas do estilo; caprichado mantém')
check(cp['volume'] and rp['volume'] and abs(cp['volume']['lufs'] - (-16)) < abs(rp['volume']['lufs'] - (-16)) + 0.01, f'volume do caprichado mais perto de -16 LUFS ({cp["volume"]} vs {rp["volume"]})')
check(abs(rp['duracao'] - cp['duracao']) < 0.3 and rp['tamanho_bytes'] > 1000 and cp['tamanho_bytes'] > 1000, 'mesma duração nos dois modos')
print(f"     (rápido {rp['segundos_de_render']}s e {rp['tamanho_bytes']//1024} KB; caprichado {cp['segundos_de_render']}s e {cp['tamanho_bytes']//1024} KB)")
mr.ARQ = TMP / 'medidas_vazias.json'
check(mr.estimar('rapido', 30)['segundos'] is None and 'não medido' in mr.estimar('rapido', 30)['motivo'], 'sem dados suficientes: "não medido", sem chute')
for _ in range(3): mr.registrar_tempo('rapido', 6.0, 30.0)
check(mr.estimar('rapido', 15)['segundos'] == 3.0, 'com 3 cortes medidos a estimativa vem da média real')
t2 = {'estilo_visual': 'gamer_neon', 'efeito': 'zoom-acao', 'crf': 23}; mr.aplicar(t2, 'rapido')
check(t2['efeito'] == 'nenhum' and 'brilho' in t2['estilo_off'] and t2['x264_preset'] == 'veryfast', 'rápido ajusta o template')
print('TUDO OK' if not falhas else f'{falhas} FALHAS', f'({ok} ok)'); sys.exit(1 if falhas else 0)
