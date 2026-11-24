"""F1.02: porta real de aprovação e confirmação WhatsApp por SHA, sem redes reais."""
import hashlib
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='ec-portao-diretor-'))
os.environ.update(DADOS=str(TMP / 'dados'), BANCO_ARQ=str(TMP / 'dados/studio.sqlite'),
                  ESTEIRA_COMPLETA='0', PIPELINE_V2='0', CENTRAL_SEM_ACORDAR='1')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import banco as db
import aprovacoes as ap
import comandos as cm
import pipeline as pl
import postagem as pg
import produtor as pr
import projetos as pj

db.migrar()
pg.VIDEOS.mkdir(parents=True, exist_ok=True)


class PortaoDiretor(unittest.TestCase):
    def setUp(self):
        pl.ligar(True, 'teste')
        self.p = pr.novo({'briefing': {'tema': 'Teste', 'destinos': {'redes': ['kwai']}},
                         'roteiro': {'titulo': 'Vídeo teste', 'cenas': [{'texto': 'Teste', 'titulo': 'Cena'}]}})
        self.pid = self.p['id']
        self.sha = self.render('primeira versao', 1)
        self.por = self.pid  # confirmações independentes entre casos
        self.parecer()

    def render(self, texto, versao):
        # Fixture de aprovação: não testa codec/render, apenas identidade e gates.
        arquivo = TMP / f'{self.pid}-{versao}.mp4'
        arquivo.write_bytes((self.pid + texto).encode())
        sha = hashlib.sha256(arquivo.read_bytes()).hexdigest()
        rid = self.pid + str(versao)
        db.executar('INSERT INTO renders (id, projeto, versao, arquivo, sha256, duracao, codec, largura, altura, validado, alertas, criado) '
                    'VALUES (?,?,?,?,?,?,?,?,?,1,?,?)', rid, self.pid, versao, str(arquivo), sha, 3, 'h264', 360, 640, '[]', time.time())
        pj.mudar_dados(self.pid, lambda d, _: (d.update(render={'id': rid, 'sha': sha, 'versao': versao, 'validado': True}),
                                             {'status': 'ready_for_review'})[1])
        return sha

    def parecer(self, sha=None):
        sha = sha or self.sha
        pj.mudar_dados(self.pid, lambda d, _: d.update(
            diretor={'sha': sha, 'veredito': 'aprovado', 'motivos': []},
            qualidade={'status': 'apto_para_revisao_humana', 'problemas': []}))

    def certificado(self, sha=None):
        return pl.emitir_certificado(self.pid, sha or self.sha, {'score': 82, 'blocking_findings': []})

    def sem_publicacao(self):
        self.assertEqual(db.um('SELECT COUNT(*) n FROM aprovacoes WHERE projeto=?', self.pid)['n'], 0)
        self.assertEqual(db.um('SELECT COUNT(*) n FROM publicacoes WHERE aprovacao IN (SELECT id FROM aprovacoes WHERE projeto=?)', self.pid)['n'], 0)
        self.assertFalse(any(p.get('projeto') == self.pid for p in pg.posts()))

    def negar(self):
        with self.assertRaises(ap.ErroAprovacao) as erro:
            ap.aprovar(self.pid, self.sha, None, 'site', 'teste')
        self.assertEqual(erro.exception.status, 409)
        self.sem_publicacao()

    def test_sem_parecer_do_diretor(self):
        self.certificado()
        pj.mudar_dados(self.pid, lambda d, _: (d.pop('diretor', None), None)[1])
        self.negar()

    def test_sem_relatorio_de_qualidade(self):
        self.certificado()
        pj.mudar_dados(self.pid, lambda d, _: (d.pop('qualidade', None), None)[1])
        self.negar()

    def test_certificado_nao_suprime_pendencia_tecnica(self):
        self.certificado()
        pj.mudar_dados(self.pid, lambda d, _: d.update(qualidade={
            'status': 'falha_tecnica', 'tecnico': {'erros': ['Sem áudio']}}))
        self.negar()

    def test_pendencia_de_qualidade_bloqueia(self):
        self.certificado()
        pj.mudar_dados(self.pid, lambda d, _: d['qualidade'].update(
            problemas=[{'tipo': 'narrativa', 'descricao': 'Sem fechamento', 'status': 'aberto'}]))
        self.negar()

    def test_sem_certificado_no_pipeline(self):
        self.negar()

    def test_certificado_da_versao_antiga_nao_libera_nova(self):
        self.certificado()
        self.sha = self.render('versao nova', 2)
        self.parecer()
        self.negar()

    def test_parecer_da_versao_antiga_nao_libera_nova(self):
        self.sha = self.render('versao nova', 2)
        self.certificado()
        self.negar()

    def test_certificado_revogado_bloqueia(self):
        self.certificado()
        pl.revogar(self.pid, 'Precisa conferir de novo')
        self.negar()

    def test_aprovacao_valida_e_repeticao(self):
        self.certificado()
        ap.aprovar(self.pid, self.sha, None, 'site', 'teste')
        r = ap.aprovar(self.pid, self.sha, None, 'site', 'teste')
        self.assertTrue(r['repetido'])
        self.assertEqual(db.um('SELECT COUNT(*) n FROM aprovacoes WHERE projeto=?', self.pid)['n'], 1)
        self.assertEqual(db.um('SELECT COUNT(*) n FROM publicacoes WHERE aprovacao IN (SELECT id FROM aprovacoes WHERE projeto=?)', self.pid)['n'], 1)
        self.assertEqual(len([p for p in pg.posts() if p.get('projeto') == self.pid]), 1)

    def test_rejeicao_nao_cria_posts(self):
        self.certificado()
        ap.rejeitar(self.pid, self.sha, 'Não gostei', 'site', 'teste')
        self.assertEqual(pj.obter(self.pid)['status'], 'rejected')
        self.assertEqual(db.um('SELECT COUNT(*) n FROM publicacoes WHERE aprovacao IN (SELECT id FROM aprovacoes WHERE projeto=?)', self.pid)['n'], 0)
        self.assertEqual(db.um('SELECT decisao FROM aprovacoes WHERE projeto=?', self.pid)['decisao'], 'rejeitado')

    def pedir_zap(self):
        resposta = cm.responder('aprovar ' + ap.ref(self.pid), self.por)
        self.assertIn('SIM', resposta)
        self.sem_publicacao()

    def test_whatsapp_real_so_publica_depois_do_sim(self):
        self.certificado()
        self.pedir_zap()
        self.assertIn('aprovado por você', cm.responder('sim', self.por))
        self.assertEqual(db.um('SELECT origem FROM aprovacoes WHERE projeto=?', self.pid)['origem'], 'whatsapp')
        self.assertIn('Não há nada', cm.responder('sim', self.por))
        self.assertEqual(db.um('SELECT COUNT(*) n FROM publicacoes WHERE aprovacao IN (SELECT id FROM aprovacoes WHERE projeto=?)', self.pid)['n'], 1)

    def test_certificado_revogado_entre_pedido_e_sim(self):
        self.certificado()
        self.pedir_zap()
        pl.revogar(self.pid, 'Refazer')
        self.assertNotIn('aprovado por você', cm.responder('sim', self.por))
        self.sem_publicacao()

    def test_sim_antigo_nao_aprova_render_novo_mesmo_com_novo_certificado(self):
        self.certificado()
        self.pedir_zap()
        self.sha = self.render('nova versao antes do SIM', 2)
        self.parecer()
        self.certificado()
        self.assertIn('vídeo mudou', cm.responder('sim', self.por))
        self.sem_publicacao()
        self.pedir_zap()
        self.assertIn('aprovado por você', cm.responder('sim', self.por))
        self.assertEqual(db.um('SELECT render_sha FROM aprovacoes WHERE projeto=?', self.pid)['render_sha'], self.sha)


if __name__ == '__main__':
    unittest.main()
