"""Mede no celular quanto tempo o 3D com personagens leva (rode no Termux, dentro da pasta servidor):

    python testes/medir_personagens3d.py

Desenha a cena de demonstração (dois personagens, 5 s, vertical 1080x1920) e diz quantos segundos leva cada segundo de vídeo.
Não mexe nos seus projetos: usa uma pasta temporária.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

PASTA = Path(tempfile.mkdtemp(prefix='medir3d-'))
os.environ['DADOS'] = str(PASTA)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import estilos_codigo as ec  # noqa: E402
import personagens3d as p3  # noqa: E402

if not p3.disponivel():
    print('Falta o numpy. Rode:  pkg install -y python-numpy   e tente de novo.')
    sys.exit(1)
cena = ec.demo_cena('animado3d')
print('Desenhando 5 s de vídeo com dois personagens em 3D (vertical)...')
t = time.time()
arq = p3.preparar_cena(cena, 1080, 1920, 5.0, progresso=lambda x: print(f'\r  {x * 100:.0f}%', end='', flush=True))
seg = time.time() - t
print(f'\n\nLevou {seg:.0f} s para 5 s de vídeo: cerca de {seg / 5:.1f} s por segundo de vídeo.')
print(f'Um episódio de 45 s levaria cerca de {seg / 5 * 45 / 60:.1f} minutos só no 3D (a cena pronta fica guardada).')
import shutil  # noqa: E402
guardado = Path.home() / 'estudioclip-3d-teste.mp4'
shutil.copy(arq, guardado)       # fica guardado: o servidor acha e mostra na Galeria para revisar
print(f'Vídeo de teste: {guardado}')
print('\nMande para o Claude as linhas acima (de "Levou" até "Vídeo de teste").')
