"""Gancho completo na seleção, no desenho e nas correções das capas."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-gancho-'))
os.environ.update(DADOS=str(TMP), BANCO_ARQ=str(TMP / 'studio.sqlite'))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image
import thumbnails as th

GANCHO = 'Ninguém esperava essa jogada no último segundo, quando tudo parecia perdido!'


class GanchoCompleto(unittest.TestCase):
    def test_automatico_preserva_fim_e_pontuacao(self):
        texto, avisos = th.texto_da_capa({'texto_modo': 'auto'}, {'gancho': GANCHO, 'titulo': 'Outro título'})
        self.assertEqual(texto, GANCHO)
        self.assertEqual(avisos, [])

    def test_descricao_entre_aspas_preserva_mais_de_quarenta_caracteres(self):
        texto, _ = th.texto_da_capa({'texto_modo': 'auto', 'descricao': f'Use a frase “{GANCHO}”'}, {})
        self.assertEqual(texto, GANCHO)

    def test_titulo_e_texto_exato_nao_sao_cortados(self):
        self.assertEqual(th.texto_da_capa({'texto_modo': 'auto'}, {'titulo': GANCHO})[0], GANCHO)
        self.assertEqual(th._texto_completo(GANCHO), GANCHO)
        self.assertEqual(th.texto_da_capa({'texto_modo': 'exato', 'texto': GANCHO}, {})[0], GANCHO)
        with self.assertRaises(th.ErroThumb):
            th._texto_completo('a' * 501)

    def test_correcao_preserva_frase_e_quebras(self):
        frase = GANCHO.replace(', ', ',\n')
        layout, texto = th._correcao('faixa', frase)
        self.assertEqual(layout, 'caixa')
        self.assertEqual(texto, frase)
        self.assertEqual(th._correcao(layout, texto)[1], frase)

    def test_frase_cabe_inteira_nos_formatos_e_layouts(self):
        fundo = Image.new('RGB', (1280, 720), (30, 120, 200))
        for formato in ('16:9', '9:16', '4:5', '1:1'):
            for layout in ('cheia', 'faixa', 'dividido', 'moldura', 'cheia_topo', 'caixa'):
                with self.subTest(formato=formato, layout=layout):
                    img, laudo = th.desenhar(fundo, formato, layout, GANCHO, {})
                    self.assertEqual(laudo['texto'], GANCHO)
                    self.assertEqual(' '.join(laudo['linhas']), GANCHO.upper())
                    self.assertFalse(laudo['overflow'])
                    sx, sy, sw, sh = laudo['area_segura']
                    x0, y0, x1, y1 = laudo['mascara'].getbbox()
                    self.assertGreaterEqual(x0, sx - 12)
                    self.assertGreaterEqual(y0, sy - 12)
                    self.assertLessEqual(x1, sx + sw + 12)
                    self.assertLessEqual(y1, sy + sh + 12)

    def test_texto_impossivel_e_detectado_sem_remover_palavras(self):
        texto = 'PALAVRA' * 100
        _, laudo = th.desenhar(Image.new('RGB', (1280, 720)), '9:16', 'caixa', texto, {})
        self.assertTrue(laudo['overflow'])
        self.assertEqual(laudo['texto'], texto)
        self.assertEqual(''.join(laudo['linhas']), texto)


if __name__ == '__main__':
    unittest.main()
