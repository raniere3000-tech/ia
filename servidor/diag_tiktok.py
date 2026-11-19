"""Diagnóstico do TikTok: mostra o que o TikTok responde, sem passar pelo site.
Uso no Termux:  cd ~/ia/servidor && python diag_tiktok.py
Para mandar um vídeo de verdade para os rascunhos:  python diag_tiktok.py ultimo   (ou o caminho do .mp4)
Não mostra chaves nem tokens."""
import json
import subprocess
import sys
from pathlib import Path

import postagem as pg


def mostrar(titulo, st, j):
    j = dict(j) if isinstance(j, dict) else {'resposta': j}
    if isinstance(j.get('data'), dict):
        j['data'] = {k: ('(oculto)' if 'url' in k else v) for k, v in j['data'].items()}
    print(f'\n== {titulo}: HTTP {st}')
    print(json.dumps(j, ensure_ascii=False, indent=1)[:1500])


try:
    print('Versão do código:', subprocess.run(['git', 'log', '--oneline', '-1'], capture_output=True, text=True).stdout.strip())
except Exception:
    pass
c = pg.contas().get('tiktok', {})
print('App TikTok salvo:', bool(c.get('client_id')), '| client key começa com:', (c.get('client_id') or '')[:4], '| conectado:', bool(c.get('token')), '| conta:', c.get('nome', ''))
if not c.get('token'):
    raise SystemExit('Não há login do TikTok salvo neste servidor. Entre de novo em Suas contas.')
t = pg._token_tiktok()
cab = {'Authorization': 'Bearer ' + t['access']}
base = pg.URL['tiktok_api']
st, _, j = pg.http('GET', base + '/v2/user/info/?fields=display_name', cab=cab)
mostrar('1. Quem está conectado', st, j)
st, _, j = pg.http('POST', base + '/v2/post/publish/creator_info/query/', js={}, cab=cab)
mostrar('2. Opções da conta (creator_info)', st, j)
fonte = {'source': 'FILE_UPLOAD', 'video_size': 1000000, 'chunk_size': 1000000, 'total_chunk_count': 1}
st, _, j = pg.http('POST', base + '/v2/post/publish/inbox/video/init/', js={'source_info': fonte}, cab=cab)
mostrar('3. Iniciar envio como RASCUNHO (nada é publicado)', st, j)
if len(sys.argv) > 1:
    if sys.argv[1] == 'ultimo':
        vids = sorted(pg.VIDEOS.glob('*.mp4'), key=lambda f: f.stat().st_mtime)
        if not vids:
            raise SystemExit('Nenhum vídeo em ' + str(pg.VIDEOS))
        arq = vids[-1]
    else:
        arq = Path(sys.argv[1]).expanduser()
    print(f'\n== 4. Enviando {arq.name} ({arq.stat().st_size // 1024} KB) como rascunho...')
    try:
        print('Resultado:', pg.postar_tiktok({'opcoes': {'tiktok_modo': 'rascunho'}}, arq))
    except Exception as e:  # noqa: BLE001
        print('Erro:', e)
print('\nCopie tudo acima e mande para o Claude.')
