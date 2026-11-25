"""F1.01: aprovação concorrente e retomada, sem rede e com SQLite temporário."""
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

TMP = Path(tempfile.mkdtemp(prefix='ec-aprovacao-corrida-'))
os.environ.update(DADOS=str(TMP), BANCO_ARQ=str(TMP / 'studio.sqlite'), CENTRAL_SEM_ACORDAR='1')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import banco as db
import fila
import projetos as pj
import produtor as pr
import aprovacoes as ap

db.migrar()


class AprovacaoRoteiro(unittest.TestCase):
    def setUp(self):
        self.p = pj.criar({'tipo': 'agente3', 'dados': {
            'briefing': {'modo_aprovacao': 'assistido'}, 'roteiro': {'titulo': 'Teste'},
            'cenas': [{'id': 'c1', 'texto': 'Primeira revisão'}],
            'pareceres_etapas': {'roteiro': {'reprovacoes': pr.MAX_REPROVACOES_ETAPA}},
            'aprovacao_roteiro': {'aprovado': False}}})
        self.pid = self.p['id']
        fila.registrar('agente3.produzir', lambda ctx: {})
        self.j = fila.enfileirar('agente3.produzir', agente='agente3', projeto=self.pid,
                                dados={'projeto': self.pid, 'etapa': 'roteiro'})
        db.executar("UPDATE jobs SET status='rodando' WHERE id=?", self.j['id'])
        self.j = fila.obter(self.j['id'])
        self.key = pj.hash_roteiro(self.p['dados'])

    def esperar(self, ctx):
        raise fila.Esperar(0, 'Roteiro', 'aguardando_aprovacao', chave_aprovacao=self.key)

    def executar(self, f):
        fila.registrar('agente3.produzir', f)
        fila._executar(fila.obter(self.j['id']))

    def test_aprovar_enquanto_rodando_nao_regride(self):
        entrou, continuar = threading.Event(), threading.Event()
        original = pj.mudar_dados
        erros = []
        def interceptar(pid, f, *args, **kw):
            if f.__name__ == 'esperar_aprovacao':
                entrou.set()
                if not continuar.wait(5):
                    raise RuntimeError('Teste não liberou a escrita')
            return original(pid, f, *args, **kw)
        def worker():
            try:
                self.executar(lambda ctx: pr.corrigir_etapa(ctx, self.pid, 'roteiro', 'revisar', ['Problema']))
            except BaseException as e:
                erros.append(e)
        with patch.object(pj, 'mudar_dados', side_effect=interceptar), patch('emails.avisar_roteiro'):
            t = threading.Thread(target=worker)
            t.start()
            try:
                self.assertTrue(entrou.wait(5))
                ap.aprovar_roteiro(self.pid, 'teste')
            finally:
                continuar.set()
                t.join(5)
        self.assertFalse(t.is_alive())
        self.assertEqual(erros, [])
        self.assertTrue(pj.roteiro_aprovado(pj.obter(self.pid)['dados']))
        self.assertEqual(fila.obter(self.j['id'])['status'], 'na_fila')
        self.assertIsNone(db.kv('liberar:' + self.j['id']))
        with patch('diretor_qualidade.avaliar_criativo', return_value={'passed': False, 'findings': []}), \
             patch.object(pr, 'revisao_narrativa', return_value=[{'descricao': 'Problema'}]):
            self.assertIsNone(pr.conferir_roteiro(fila.Contexto(self.j), self.pid, self.p, self.p['dados']['briefing']))

    def test_espera_visivel_com_job_persistido(self):
        self.executar(self.esperar)
        self.assertEqual(pj.obter(self.pid)['status'], 'waiting_brief_approval')
        self.assertEqual(fila.obter(self.j['id'])['status'], 'aguardando_aprovacao')
        ap.aprovar_roteiro(self.pid, 'teste')
        self.assertEqual(fila.obter(self.j['id'])['status'], 'na_fila')

    def test_sinal_antigo_nao_libera_nova_revisao(self):
        ap.aprovar_roteiro(self.pid, 'teste')
        pj.mudar_dados(self.pid, lambda d, _: d['cenas'][0].update(texto='Nova revisão'))
        self.key = pj.hash_roteiro(pj.obter(self.pid)['dados'])
        self.executar(self.esperar)
        self.assertFalse(pj.roteiro_aprovado(pj.obter(self.pid)['dados']))
        self.assertEqual(fila.obter(self.j['id'])['status'], 'aguardando_aprovacao')
        fila.liberar(self.j['id'], chave_aprovacao=pj.hash_roteiro(self.p['dados']))
        self.assertEqual(fila.obter(self.j['id'])['status'], 'aguardando_aprovacao')
        ap.aprovar_roteiro(self.pid, 'teste')
        self.assertEqual(fila.obter(self.j['id'])['status'], 'na_fila')

    def test_edicao_durante_aprovar_recusada(self):
        original = pj.mudar_dados
        def editar(pid, f):
            original(pid, lambda d, _: d['roteiro'].update(titulo='Mudou'))
            return original(pid, f)
        with patch.object(pj, 'mudar_dados', side_effect=editar):
            with self.assertRaises(ap.ErroAprovacao) as erro:
                ap.aprovar_roteiro(self.pid, 'teste')
        self.assertEqual(erro.exception.status, 409)
        self.assertFalse(pj.roteiro_aprovado(pj.obter(self.pid)['dados']))

    def test_reinicio_entre_aprovacao_e_liberacao(self):
        with patch.object(fila, 'liberar'):
            ap.aprovar_roteiro(self.pid, 'teste')
        codigo = '''
import banco as db, fila, projetos as pj
jid, pid, key = __import__('sys').argv[1:]
assert fila.recuperar() >= 1
j = fila._proximo('leve')
assert j['id'] == jid
def handler(ctx):
    raise fila.Esperar(0, 'Roteiro', 'aguardando_aprovacao', chave_aprovacao=key)
fila.registrar('agente3.produzir', handler)
fila._executar(j)
assert fila.obter(jid)['status'] == 'na_fila'
assert pj.roteiro_aprovado(pj.obter(pid)['dados'])
'''
        db.executar("UPDATE jobs SET status='concluido' WHERE id<>?", self.j['id'])
        r = subprocess.run([sys.executable, '-c', codigo, self.j['id'], self.pid, self.key],
                           capture_output=True, text=True, timeout=15)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_espera_legada_pode_ser_aprovada(self):
        db.executar("UPDATE jobs SET status='aguardando_aprovacao' WHERE id=?", self.j['id'])
        ap.aprovar_roteiro(self.pid, 'teste')
        self.assertEqual(fila.obter(self.j['id'])['status'], 'na_fila')

    def test_aprovar_edicao_enquanto_esperando(self):
        self.executar(self.esperar)
        pj.mudar_dados(self.pid, lambda d, _: d['cenas'][0].update(texto='Revisão editada'))
        ap.aprovar_roteiro(self.pid, 'teste')
        self.assertEqual(fila.obter(self.j['id'])['status'], 'na_fila')
        self.assertTrue(pj.roteiro_aprovado(pj.obter(self.pid)['dados']))

    def test_midias_nao_invalidam_texto_e_nova_cena_invalida(self):
        ap.aprovar_roteiro(self.pid, 'teste')
        pj.mudar_dados(self.pid, lambda d, _: d['cenas'][0].update(
            audio={'arquivo': 'audio.wav'}, clipe={'chave': 'x'}, duracao_real=3))
        self.assertTrue(pj.roteiro_aprovado(pj.obter(self.pid)['dados']))
        pj.mudar_dados(self.pid, lambda d, _: d['cenas'][0].update(texto='Texto alterado'))
        self.assertFalse(pj.roteiro_aprovado(pj.obter(self.pid)['dados']))

    def test_render_respeita_aceite_narrativo_sem_liberar_defeito_tecnico(self):
        ap.aprovar_roteiro(self.pid, 'teste')
        pj.mudar_dados(self.pid, lambda d, _: d['pareceres_etapas']['roteiro'].update(
            reprovacoes=pr.MAX_REPROVACOES_ETAPA + 1))
        ponto = {'tipo': 'narrativa', 'descricao': 'Gancho fraco', 'proposta': 'Trocar gancho', 'status': 'aberto'}
        tecnico = {'tipo': 'audio', 'descricao': 'Sem áudio', 'proposta': 'Gerar áudio', 'status': 'aberto'}
        b = {'formato': '9:16', 'estilo': 'quadro_branco'}
        with patch.object(pr.rd, 'tem_ffmpeg', return_value=True), \
             patch.object(pr.rd, 'livre_mb', return_value=999999), \
             patch('storyboard.porta_ativa', return_value=False), \
             patch.object(pr, 'revisao_narrativa', return_value=[ponto]), \
             patch.object(pr, 'continuidade_serie', return_value=[]), \
             patch.object(pr, '_render_cena', return_value=('quadro_branco', TMP / 'fake.mp4')), \
             patch.object(pr, '_refazer_pelo_diretor', return_value=False), \
             patch.object(pr.qd, 'antes', return_value=[]) as antes:
            ctx = fila.Contexto(self.j)
            r = pr.etapa_render(ctx, self.pid, pj.obter(self.pid), b)
            self.assertEqual(r['etapa'], 'Vídeo final')
            achado = pj.obter(self.pid)['dados']['qualidade']['problemas'][0]
            self.assertEqual(achado['status'], 'resolvido')
            self.assertEqual(achado['aprovacao_hash'], self.key)
            self.assertEqual(ponto['status'], 'aberto')  # cache original preservado
            antes.return_value = [tecnico]
            r = pr.etapa_render(ctx, self.pid, pj.obter(self.pid), b)
            self.assertEqual(r['retomar'], 'revisar')
            antes.return_value = []
            pj.mudar_dados(self.pid, lambda d, _: d['cenas'][0].update(texto='Nova revisão'))
            r = pr.etapa_render(ctx, self.pid, pj.obter(self.pid), b)
            self.assertEqual(r['retomar'], 'revisar')

    def test_sinal_de_outra_etapa_e_legacy_ignorado(self):
        for sinal in (123.0, {'chave': '', 'etapa': 'outra'}):
            db.executar("UPDATE jobs SET status='rodando' WHERE id=?", self.j['id'])
            db.kv_gravar('liberar:' + self.j['id'], sinal)
            def generico(ctx):
                raise fila.Esperar(0, 'Outra porta', 'aguardando_aprovacao')
            self.executar(generico)
            self.assertEqual(fila.obter(self.j['id'])['status'], 'aguardando_aprovacao')
            self.assertIsNone(db.kv('liberar:' + self.j['id']))


if __name__ == '__main__':
    unittest.main()
