"""Executa o script real com origem Git local e processos de sistema simulados."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path('/workspace/scratch/ecb4bcf1d97f/estudioclip')
class Atualizador(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='ec-updater-');self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name);self.origin=self.p/'origin.git';self.up=self.p/'upstream';self.clone=self.p/'celular'
        self.git(self.p,'init','--bare',str(self.origin));self.up.mkdir();self.git(self.up,'init','-b','main')
        self.git(self.up,'config','user.name','Teste');self.git(self.up,'config','user.email','teste@example.invalid')
        (self.up/'servidor').mkdir();(self.up/'servidor/atualizar-termux.sh').write_text((ROOT/'servidor/atualizar-termux.sh').read_text())
        (self.up/'servidor/iniciar-termux.sh').write_text('#!/bin/sh\nprintf "INICIADOR:%s:%s\\n" "$1" "$RENDER_INTEGRIDADE"\n')
        (self.up/'versao.txt').write_text('v1');self.git(self.up,'add','.');self.git(self.up,'-c','commit.gpgsign=false','commit','-m','v1')
        self.git(self.up,'remote','add','origin',str(self.origin));self.git(self.up,'push','-u','origin','main')
        self.git(self.p,'clone','--branch','main',str(self.origin),str(self.clone))
        (self.up/'versao.txt').write_text('v2');self.git(self.up,'add','.');self.git(self.up,'-c','commit.gpgsign=false','commit','-m','v2');self.git(self.up,'push')
        b=self.p/'bin';b.mkdir()
        for nome,code in [('pkill',1),('pkg',0),('termux-wake-lock',0)]:
            f=b/nome;f.write_text('#!/bin/sh\nexit '+str(code)+'\n');f.chmod(0o755)
        self.env=dict(os.environ,PATH=str(b)+os.pathsep+os.environ['PATH'])
    def git(self,cwd,*args):
        return subprocess.check_output(['git',*args],cwd=cwd,text=True,stderr=subprocess.STDOUT).strip()
    def executar(self,env=None):
        return subprocess.run(['bash','servidor/atualizar-termux.sh'],cwd=self.clone,env=env or self.env,capture_output=True,text=True,timeout=15)
    def test_atualiza_main_e_inicia_modo_link(self):
        r=self.executar();self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual((self.clone/'versao.txt').read_text(),'v2');self.assertIn('INICIADOR:link:',r.stdout)
        self.assertEqual(self.git(self.clone,'rev-parse','HEAD'),self.git(self.up,'rev-parse','HEAD'))
    def test_override_de_recurso_chega_ao_iniciador(self):
        r=self.executar(dict(self.env,RENDER_INTEGRIDADE='0'));self.assertEqual(r.returncode,0,r.stderr);self.assertIn('INICIADOR:link:0',r.stdout)
    def test_conflito_local_nao_descarta_edicao_ou_inicia_codigo_incompleto(self):
        (self.clone/'versao.txt').write_text('edicao-local')
        r=self.executar();self.assertNotEqual(r.returncode,0);self.assertEqual((self.clone/'versao.txt').read_text(),'edicao-local')
        self.assertNotIn('INICIADOR:',r.stdout)
if __name__=='__main__':unittest.main()
