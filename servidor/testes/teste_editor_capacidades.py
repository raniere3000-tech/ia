"""Sondagem do Editor Pro sem instalar dependências."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TMP = tempfile.TemporaryDirectory(prefix='ec-editor-cap-')
os.environ.update(DADOS=TMP.name, BANCO_ARQ=str(Path(TMP.name) / 'teste.sqlite'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import banco as db
import capacidades as cap


class CapacidadesEditor(unittest.TestCase):
    def test_continua_quando_filtro_ou_encoder_falta(self):
        with patch.object(cap, 'filtros_disponiveis', return_value=frozenset({'ass', 'loudnorm'})), \
             patch.object(cap, '_rodar', return_value=' V....D libx264 encoder\n'), \
             patch.object(cap.shutil, 'which', return_value='/bin/ffprobe'):
            itens = {x['id']: x for x in cap._editor()}
        self.assertEqual(itens['editor-legenda']['faltam'], ['aac'])
        self.assertEqual(itens['editor-zoom']['faltam'], ['crop', 'overlay', 'scale', 'aac'])
        self.assertTrue(all(x['estado'] == 'ausente' and x['fallback'] for x in itens.values()))

    def test_sondagem_real_e_persistencia(self):
        if not cap.shutil.which('ffmpeg') or not cap.shutil.which('ffprobe'):
            self.skipTest('FFmpeg/ffprobe ausentes')
        db.migrar()
        itens = {x['id']: x for x in cap.listar(forcar=True)['capacidades']}
        for nome in cap.EDITOR:
            item = itens['editor-' + nome]
            self.assertEqual(item['estado'], 'ausente' if item['faltam'] else 'ok')
            self.assertEqual(db.um('SELECT estado FROM capability_installs WHERE id=?', item['id'])['estado'], item['estado'])
        self.assertIn('trim', cap.filtros_disponiveis())


if __name__ == '__main__':
    unittest.main()
