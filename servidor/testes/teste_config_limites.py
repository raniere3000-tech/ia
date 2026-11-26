"""Config do Agente 1 não pode reescrever valores válidos (90 por semana, 10 por vídeo, 20 trechos, 70 s)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agente as ag  # noqa: E402

c = ag._limpar_cfg(ag._mesclar(ag.PADRAO, {'cortes': {'por_semana': 90, 'por_video': 10, 'por_analise': 20, 'dur_min': 70, 'dur_max': 115, 'dur_v': 2}}))['cortes']
assert (c['por_semana'], c['por_video'], c['por_analise'], c['dur_min'], c['dur_max']) == (90, 10, 20, 70, 115), c
c = ag._limpar_cfg(ag._mesclar(ag.PADRAO, {'cortes': {'por_semana': 9999, 'por_video': 99}}))['cortes']
assert (c['por_semana'], c['por_video']) == (ag.LIM_POR_SEMANA, ag.LIM_POR_VIDEO), c
print('OK')
