import importlib.util,os,sys,unittest
from pathlib import Path
p=Path('/workspace/scratch/ecb4bcf1d97f/estudioclip/servidor/testes/teste_a3_editor_compartilhado.py')
spec=importlib.util.spec_from_file_location('matrizbase',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from unittest.mock import patch
FLAGS='A1_MESMA_FONTE A1_GANCHO_INTEGRO THUMB_REJEICAO A5_EFEITOS_REAIS RENDER_INTEGRIDADE DNA_CORTE A3_EDICAO_COMPARTILHADA FORMATOS_IA METRICAS_PUBLICACOES PUBLICACAO_CONTEXTO INTELIGENCIA_METRICAS'.split()
class TodosAtivos(m.Compartilhado):
    def setUp(self):
        super().setUp()
        contexto=patch.dict(os.environ,dict.fromkeys(FLAGS,'1'));contexto.start();self.addCleanup(contexto.stop)
        assert all(os.environ[k]=='1' for k in FLAGS)
r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TodosAtivos))
sys.exit(not r.wasSuccessful())
