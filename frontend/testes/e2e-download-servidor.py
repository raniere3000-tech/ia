"""Servidor de teste para testes/e2e-download.cjs: porta 8798, 4 posts (um sem arquivo). Rodar: python3 testes/e2e-download-servidor.py & npx vite preview --port 4173 ; SP=/tmp node testes/e2e-download.cjs"""
import os, sys, tempfile, time, subprocess
from pathlib import Path
TMP = Path(tempfile.mkdtemp(prefix='ec-dl-e2e-'))
os.environ.update(DADOS=str(TMP/'dados'), BANCO_ARQ=str(TMP/'dados'/'studio.sqlite'), CHAVE_MESTRA_ARQ=str(TMP/'chave'), TOKEN='senha-e2e-123',
                  FILA_INTERVALO='0.3', ESPERA_INICIAL_AGENTE='99999', BACKUP_DIARIO='0', INTERVALO_AGENDA='600', INTERVALO_AGENDA2='600',
                  CENTRAL_SEM_ACORDAR='1', AGENTE6_SEM_VIGIA='1', COORDENADOR_SEM_VIGIA='1', ESTEIRA_COMPLETA='0')
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'servidor'))
from http.server import ThreadingHTTPServer
import servidor as S, postagem as pg
S.ligar_servicos()
pg.VIDEOS.mkdir(parents=True, exist_ok=True)
agora = time.time()
posts = []
for i, (tit, st) in enumerate([('Rolê noturno de jet ski no GTA 6 🔥', 'agendado'), ('Rolê noturno de jet ski no GTA 6 🔥', 'postado'), ('Melhores momentos da live', 'agendado'), ('Sem arquivo', 'agendado')]):
    vid = f'v{i}'
    if tit != 'Sem arquivo':
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=s=360x640:r=25:d=3','-f','lavfi','-i','sine=d=3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(pg.VIDEOS/f'{vid}.mp4')],check=True)
    posts.append({'id': f'p{i}abcdef12', 'video': vid, 'quando': agora + 3600*(i+1), 'titulo': tit, 'legenda': tit + '\nTexto da legenda!\n\n#GTA6 #Games', 'criado': agora-100, 'origem': 'manual', 'hash': '',
                  'opcoes': {}, 'redes': {'youtube': {'status': st, 'link': 'https://youtube.com/shorts/abc123XYZ' if st == 'postado' else '', 'erro': '', **({'feito': agora-60} if st=='postado' else {})}}})
pg.salvar_posts(posts)
print('PRONTO', flush=True)
ThreadingHTTPServer(('127.0.0.1', 8798), S.Handler).serve_forever()
