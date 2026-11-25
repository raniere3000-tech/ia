"""Contratos de timeline e proteção das regiões aprovadas."""
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import contratos as ct
import editor_ia as ed


def plano(schema=ct.SCHEMA_TIMELINE):
    return {
        'schema_version': schema,
        'clips': [{'in_ms': 1000, 'out_ms': 7000}],
        'manual_locks': [[4500, 5000]],
    }


class TimelineEditor(unittest.TestCase):
    def test_legado_preserva_forma_e_hash(self):
        antigo = ct.validar_plano(plano(ct.SCHEMA))
        esperado = {
            'schema_version': 1, 'source_assets': ['principal'], 'timeline_version': 1,
            'clips': [{'source': 'principal', 'in_ms': 1000, 'out_ms': 7000}],
            'effects': [], 'template_id': '', 'target_aspect_ratio': '9:16',
            'output_profile': 'final', 'manual_locks': [[4500, 5000]],
        }
        self.assertEqual(antigo, dict(esperado, edit_reason=''))
        self.assertEqual(ct.hash_plano(antigo), hashlib.sha256(json.dumps(esperado, sort_keys=True).encode()).hexdigest())

    def test_travas_e_versao_apos_correcao(self):
        original = ct.validar_plano(dict(plano(), protected_hook={'in_ms': 1000, 'out_ms': 2800}))
        mantido, feitas = ed.corrigir(original, [
            {'acao': 'ajustar_inicio', 'delta_ms': 550},
            {'acao': 'encurtar_pausa', 'ini_ms': 3000, 'fim_ms': 4600},
        ])
        self.assertEqual(feitas, [])
        self.assertEqual(mantido, original)
        novo, feitas = ed.corrigir(original, [{'acao': 'encurtar_pausa', 'ini_ms': 4600, 'fim_ms': 5600}])
        self.assertEqual(len(feitas), 1)
        self.assertEqual(novo['timeline_version'], 2)
        self.assertEqual(novo['protected_hook'], original['protected_hook'])
        self.assertEqual(ct.validar_plano(novo), novo)

    def test_recusa_revisao_intervalos_e_fontes_invalidas(self):
        for extra in [
            {'schema_version': 3}, {'timeline_version': []}, {'timeline_version': True},
            {'clips': [{'in_ms': 900, 'out_ms': 1600}, {'in_ms': 1200, 'out_ms': 2300}]},
            {'source_assets': ['../video.mp4']},
            {'effects': [{'tipo': 'fade'}] * 25},
            {'effects': [{'tipo': 'cor', 'exposicao_ev': '0;scale=200:200'}]},
            {'delivery': {'fps': 29}},
            {'delivery': {'crf': True}},
            {'delivery': {'limite_kbps': 30000}},
            {'manual_locks': [[5000, 4500]]},
            {'protected_hook': {'in_ms': 1000, 'out_ms': 7900}},
            {'protected_hook': {'in_ms': 1000, 'out_ms': 1500, 'path': '/tmp/video'}},
        ]:
            with self.subTest(extra=extra), self.assertRaises(ct.ErroContrato):
                ct.validar_plano(dict(plano(), **extra))


if __name__ == '__main__':
    unittest.main()
