"""Executa o iniciador real em cópia isolada, sem servidor, rede ou pkill reais."""
import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
FLAGS=('A1_MESMA_FONTE','A1_GANCHO_INTEGRO','THUMB_REJEICAO','A5_EFEITOS_REAIS','RENDER_INTEGRIDADE','DNA_CORTE','A3_EDICAO_COMPARTILHADA','FORMATOS_IA','METRICAS_PUBLICACOES','PUBLICACAO_CONTEXTO','INTELIGENCIA_METRICAS')
ROOT=Path(__file__).resolve().parent.parent
class Ativacao(unittest.TestCase):
    def iniciar(self,overrides=None):
        with tempfile.TemporaryDirectory(prefix='ec-start-') as d:
            p=Path(d);(p/'iniciar-termux.sh').write_text((ROOT/'iniciar-termux.sh').read_text());(p/'.instalado').touch()
            b=p/'bin';b.mkdir()
            for nome,body in {'pip':'exit 0','pkill':'exit 1','pkg':'exit 97','termux-wake-lock':'exit 0'}.items():
                f=b/nome;f.write_text('#!/bin/sh\n'+body+'\n');f.chmod(0o755)
            f=b/'python';f.write_text('#!'+sys.executable+'\nimport json,os,sys\nif sys.argv[1:]==["-c","import PIL"]:sys.exit(0)\nassert sys.argv[1:]==["servidor.py"],sys.argv\nprint(json.dumps({k:os.environ.get(k) for k in '+repr(FLAGS)+'}))\n');f.chmod(0o755)
            env={k:v for k,v in os.environ.items() if k not in FLAGS}
            env.update(overrides or {});env['PATH']=str(b)+os.pathsep+env['PATH']
            r=subprocess.run(['bash',str(p/'iniciar-termux.sh')],env=env,capture_output=True,text=True,timeout=15,check=True)
            return json.loads(r.stdout.strip().splitlines()[-1])
    def test_iniciador_entrega_todos_os_recursos_ao_servidor(self):
        self.assertEqual(self.iniciar(),dict.fromkeys(FLAGS,'1'))
    def test_desativacao_explicita_preserva_demais_recursos(self):
        r=self.iniciar({'A3_EDICAO_COMPARTILHADA':'0','RENDER_INTEGRIDADE':'0'})
        self.assertEqual(r.pop('A3_EDICAO_COMPARTILHADA'),'0');self.assertEqual(r.pop('RENDER_INTEGRIDADE'),'0')
        self.assertTrue(all(v=='1' for v in r.values()))
    def test_modulos_enxergam_configuracao_do_iniciador(self):
        env=self.iniciar()
        with tempfile.TemporaryDirectory(prefix='ec-ativacao-') as d,patch.dict(os.environ,dict(env,DADOS=d,BANCO_ARQ=str(Path(d)/'db.sqlite'))):
            sys.path.insert(0,str(ROOT))
            import banco as db,agente as ag,contratos as ct,thumbnails as th,perfis as pf,produtor as pr,criativo as cr,aprendizado as ap
            db.migrar()
            self.assertTrue(ag.gancho_integro_ativo());self.assertTrue(ct.efeitos_reais_ativos());self.assertTrue(th.rejeicao_ativa())
            self.assertTrue(pf.dna_ativo());self.assertTrue(pr.edicao_compartilhada_ativa());self.assertTrue(cr.formatos_ia()['habilitado'])
            self.assertTrue(ap.inteligencia_ativa());self.assertTrue(ag.inventario_metricas()['publicacoes_habilitadas'])
if __name__=='__main__':unittest.main()
