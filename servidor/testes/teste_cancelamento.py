"""Cancelamento durante sucesso, transição, espera, falha e recuperação."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

TMP = Path(tempfile.mkdtemp(prefix='ec-cancelamento-'))
os.environ.update(DADOS=str(TMP), BANCO_ARQ=str(TMP / 'studio.sqlite'), CENTRAL_SEM_ACORDAR='1')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import banco as db
import fila
import agente as ag
import thumbnails as th

db.migrar()


class Cancelamento(unittest.TestCase):
    def setUp(self):
        db.executar('DELETE FROM jobs')
        db.executar('DELETE FROM projetos')
        db.executar('DELETE FROM thumbnail_jobs')
        fila.registrar('teste.cancelar', lambda ctx: {})

    def job(self, status='na_fila', projeto=''):
        j = fila.enfileirar('teste.cancelar', agente='agente3', projeto=projeto)
        db.executar('UPDATE jobs SET status=? WHERE id=?', status, j['id'])
        return fila.obter(j['id'])

    def test_cancelar_em_todas_as_esperas(self):
        for status in ('na_fila', 'agendado', 'aguardando_tentativa', 'aguardando_aprovacao'):
            with self.subTest(status=status):
                j = self.job(status)
                r = fila.cancelar(j['id'])
                self.assertEqual(r['status'], 'cancelado')
                self.assertEqual(r['cancelar'], 1)
                fila.liberar(j['id'])
                fila.retomar(j['id'])
                self.assertEqual(fila.obter(j['id'])['status'], 'cancelado')
        self.assertIsNone(fila._proximo('leve'))

    def test_final_da_etapa_nao_sobrescreve_cancelamento(self):
        def sucesso(ctx):
            return {}
        def transicao(ctx):
            return {'proxima': True, 'etapa': 'Próxima etapa'}
        def espera(ctx):
            raise fila.Esperar(60, 'Esperando aprovação', 'aguardando_aprovacao')
        def erro(ctx):
            raise RuntimeError('Erro depois de cancelar')
        for terminar in (sucesso, transicao, espera, erro):
            with self.subTest(terminar=terminar.__name__):
                j = self.job('rodando')
                def handler(ctx):
                    fila.cancelar(ctx.id)
                    return terminar(ctx)
                fila.registrar('teste.cancelar', handler)
                fila._executar(j)
                r = fila.obter(j['id'])
                self.assertEqual(r['status'], 'cancelado')
                self.assertEqual(r['tentativas'], 0)
                self.assertEqual(r['lease'], 0)
                self.assertIsNotNone(r['terminado'])

    def test_ignorar_nao_interrompe_outra_tarefa(self):
        j = self.job()
        rodando = self.job('rodando')
        self.assertEqual(fila.ignorar(j['id'])['etapa'], 'Ignorado por você')
        self.assertEqual(fila.ignorar(rodando['id'])['status'], 'rodando')
        self.assertEqual(fila.obter(rodando['id'])['cancelar'], 0)

    def test_cancelar_antes_do_handler(self):
        j = self.job('rodando')
        fila.cancelar(j['id'])
        with patch.dict(fila.HANDLERS, {'teste.cancelar': (lambda ctx: self.fail('executou depois de cancelar'), 'leve')}):
            fila._executar(j)
        self.assertEqual(fila.obter(j['id'])['status'], 'cancelado')

    def test_progresso_nao_apaga_cancelando(self):
        j = self.job('rodando')
        ctx = fila.Contexto(j)
        fila.cancelar(j['id'])
        with self.assertRaises(fila.Cancelado):
            ctx.progresso(90, 'Quase pronto')
        self.assertEqual(fila.obter(j['id'])['etapa'], 'Cancelando…')

    def test_reinicio_nao_reativa_cancelado(self):
        j = self.job('rodando')
        fila.cancelar(j['id'])
        fila.recuperar()
        self.assertEqual(fila.obter(j['id'])['status'], 'cancelado')
        self.assertIsNone(fila._proximo('leve'))

    def test_cancelar_projeto_remove_aprovacao_pendente(self):
        import aprovacoes
        db.executar("INSERT INTO projetos (id, titulo, tipo, status, dados, criado, atualizado) VALUES (?,?,?,?,?,?,?)",
                    'a' * 12, 'Roteiro', 'agente3', 'waiting_brief_approval', '{"briefing":{}}', time.time(), time.time())
        j = self.job('aguardando_aprovacao', 'a' * 12)
        self.assertTrue(any(p['projeto'] == 'a' * 12 for p in aprovacoes.pendentes()))
        fila.cancelar(j['id'])
        self.assertEqual(db.um('SELECT status FROM projetos WHERE id=?', 'a' * 12)['status'], 'cancelled')
        self.assertFalse(any(p['projeto'] == 'a' * 12 for p in aprovacoes.pendentes()))

    def test_capa_cancelada_nao_volta(self):
        j = self.job('rodando')
        tid = 'b' * 12
        db.executar("INSERT INTO thumbnail_jobs (id, origem, referencia, video_sha, config, estado, criado, atualizado, fila_job) VALUES (?,?,?,?,?,?,?,?,?)",
                    tid, 'corte', 'c1', 'x' * 64, '{}', 'criando', time.time(), time.time(), j['id'])
        fila.cancelar(j['id'])
        th._estado(tid, 'aguardando_escolha')
        self.assertEqual(db.um('SELECT estado FROM thumbnail_jobs WHERE id=?', tid)['estado'], 'cancelado')

    def test_render_do_corte_recebe_cancelamento(self):
        # O cancelamento é encaminhado ao executor do FFmpeg pelo contexto da thread.
        import renderizador
        with patch.object(renderizador, 'rodar', side_effect=InterruptedError('cancelado')) as rodar:
            ag.CONTROLE_TRABALHO.cancelado = lambda: True
            try:
                with self.assertRaises(fila.Cancelado):
                    ag.editar(TMP / 'video.mp4', {'ini': 0, 'fim': 5, 'titulo': 'Teste'}, [],
                              dict(ag.PADRAO['cortes']['template'], legenda='nenhuma'), TMP / 'saida.mp4', TMP)
                self.assertIs(rodar.call_args.kwargs['cancelado'], ag.CONTROLE_TRABALHO.cancelado)
            finally:
                del ag.CONTROLE_TRABALHO.cancelado

    def test_executor_encerra_processo_cancelado(self):
        import renderizador
        inicio = time.monotonic()
        with self.assertRaises(InterruptedError):
            renderizador.rodar([sys.executable, '-c', 'import time; time.sleep(60)'], cancelado=lambda: True)
        self.assertLess(time.monotonic() - inicio, 5)

    def test_rotina_automatica_unica_e_cancelavel(self):
        import servidor as S
        fila.registrar('agente1.pesado', S._job_agente1, 'pesado')
        S._enfileirar_rotina_agente1('estoque', 'Reposição', 3, 1)
        S._enfileirar_rotina_agente1('estoque', 'Reposição', 3, 1)
        self.assertEqual(len(db.todos("SELECT id FROM jobs WHERE agente='agente1'")), 1)
        job = fila._proximo('pesado')
        def cortar(*args):
            fila.cancelar(job['id'])
            ag.etapa('Não deve continuar', 50)
        with patch.object(ag, 'config', return_value={'cortes': {'ligado': True}}), \
             patch.object(ag, 'rodada_estoque', side_effect=cortar), \
             patch.object(ag, 'depois_do_trabalho') as continuar:
            fila._executar(job)
            continuar.assert_not_called()
        self.assertEqual(fila.obter(job['id'])['status'], 'cancelado')
        self.assertFalse(hasattr(ag.CONTROLE_TRABALHO, 'cancelado'))

    def test_cancelamento_impede_nova_chamada_de_ia(self):
        ag.CONTROLE_TRABALHO.cancelado = lambda: True
        try:
            with patch.object(ag.pg, 'http') as http:
                with self.assertRaises(fila.Cancelado):
                    ag._pedir_gemini('modelo', {}, 'teste', 1)
                http.assert_not_called()
        finally:
            del ag.CONTROLE_TRABALHO.cancelado

    def test_interrupcao_tira_etapas_do_painel(self):
        import esteira as es
        import pipeline as pl
        cid = 'corte-parcial'
        vid = es.garantir('corte', cid, 'Corte parcial')
        es.marcar(vid, 'a4_previo', 'executando')
        run = pl.criar('corte', cid, 'Corte parcial')
        self.assertEqual(es.situacao_agente('agente4')['estado'], 'ativo')
        ag.encerrar_corte_interrompido(cid)
        self.assertNotEqual(es.situacao_agente('agente4')['estado'], 'ativo')
        self.assertEqual(pl.obter(run['id'])['estado'], 'cancelled')


if __name__ == '__main__':
    unittest.main()
