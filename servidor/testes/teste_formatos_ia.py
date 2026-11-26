"""F3.04: três formatos editáveis no armazenamento existente, sem geração/postagem."""
import copy,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
TMP=Path(tempfile.mkdtemp(prefix='ec-formatos-'))
os.environ.update(DADOS=str(TMP),BANCO_ARQ=str(TMP/'studio.sqlite'),ESTEIRA_COMPLETA='0')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import api_v1
import banco as db
import criativo as cr
import produtor as pr
import projetos as pj

db.migrar();api_v1.iniciar()
class H:
    def __init__(self,path,d=None):self.path=path;self.corpo=json.dumps(d or {}).encode();self.headers={}
def api(m,path,d=None):return api_v1.tratar(H(path,d),m,path,{'nome':'teste','id':'teste'})

class Formatos(unittest.TestCase):
    def setUp(self):
        self.flag=patch.dict(os.environ,{'FORMATOS_IA':'1'});self.flag.start();self.addCleanup(self.flag.stop)
        self.ai=patch.object(pr.ag,'gemini',side_effect=AssertionError('Não deve gerar nada'));self.ai.start();self.addCleanup(self.ai.stop)
    def padrao(self,n='curiosidade'):
        return next(x for x in api('GET','/api/v1/criativo/formatos')['padroes'] if x['id']==n)
    def salvar(self,p):
        return api('POST','/api/v1/criativo/biblioteca',{'tipo':'template_pack','nome':p['nome'],'dados':p['dados']})
    def test_flag_desligada_sem_escrita_ou_modelos_automaticos(self):
        antes=db.um('SELECT COUNT(*) n FROM criativo_assets')['n']
        with patch.dict(os.environ,{'FORMATOS_IA':'0'}):
            self.assertEqual(api('GET','/api/v1/criativo/formatos'),{'habilitado':False,'padroes':[],'salvos':[]})
        r=api('GET','/api/v1/criativo/formatos');self.assertEqual(len(r['padroes']),3)
        api('GET','/api/v1/criativo/formatos')
        self.assertEqual(db.um('SELECT COUNT(*) n FROM criativo_assets')['n'],antes)
    def test_tres_presets_usam_tipos_e_estilos_existentes(self):
        r=api('GET','/api/v1/criativo/formatos')
        self.assertEqual({x['id'] for x in r['padroes']},{'curiosidade','historia','explicativo'})
        for p in r['padroes']:
            b=p['dados']['briefing'];self.assertIn(b['tipo'],pr.TIPOS)
            self.assertIn(b['estilo'],[x[0] for x in pr.ec.ESTILOS])
            self.assertEqual(set(b),set(cr.FORMATO_CAMPOS))
    def test_salvar_repetido_editar_versionar_e_conflito(self):
        p=self.padrao();a=self.salvar(p);b=self.salvar(p)
        self.assertEqual(a['id'],b['id']);self.assertTrue(b['repetido'])
        d=copy.deepcopy(a['dados']);d['briefing']['duracao_alvo']=70
        novo=api('PATCH','/api/v1/criativo/assets/'+a['id'],{'versao':1,'dados':d})
        self.assertEqual(novo['versao'],2)
        self.assertEqual(novo['dados']['briefing']['duracao_alvo'],70)
        vs=api('GET','/api/v1/criativo/assets/'+a['id']+'/versoes')['versoes']
        self.assertEqual([x['versao'] for x in vs],[1,2])
        self.assertEqual(vs[0]['dados']['briefing']['duracao_alvo'],30)
        with self.assertRaises(cr.ErroCriativo) as e:
            api('PATCH','/api/v1/criativo/assets/'+a['id'],{'versao':1,'dados':d})
        self.assertEqual(e.exception.status,409)
    def test_aplicar_config_preserva_tema_voz_portas_e_destinos(self):
        for n in ['curiosidade','historia','explicativo']:
            a=self.salvar(self.padrao(n));b=a['dados']['briefing']
            p=pr.novo({'briefing':{'tema':'Minha ideia','voz':'Kore','modo_aprovacao':'assistido','porta_storyboard':True,
                                   'destinos':{'redes':['kwai'],'quando':'proximo'},**b}})
            atual=p['dados']['briefing']
            self.assertEqual((atual['tema'],atual['voz'],atual['modo_aprovacao']),('Minha ideia','Kore','assistido'))
            self.assertTrue(atual['porta_storyboard']);self.assertEqual(atual['destinos']['redes'],['kwai'])
            self.assertEqual(atual['tipo'],b['tipo'])
            self.assertFalse(db.um('SELECT id FROM jobs WHERE projeto=?',p['id']))
        self.assertFalse(db.um('SELECT id FROM renders'));self.assertFalse(db.um('SELECT id FROM publicacoes'))
    def test_formato_nao_guarda_credenciais_publicacao_ou_aprovacao(self):
        p=self.padrao('historia');p['dados']['briefing'].update(voz='Charon',modo_aprovacao='supervisionado',destinos={'redes':['youtube']},gemini='segredo')
        a=self.salvar(p)
        self.assertEqual(set(a['dados']['briefing']),set(cr.FORMATO_CAMPOS))
        self.assertNotIn('segredo',json.dumps(a['dados']))
    def test_modelo_invalido_recusado_e_nao_altera_padroes(self):
        p=self.padrao('explicativo');p['dados']['formato_ia']='inexistente'
        with self.assertRaises(cr.ErroCriativo):self.salvar(p)
        p=self.padrao('explicativo');p['dados']['briefing']['duracao_alvo']='NaN'
        with self.assertRaises(cr.ErroCriativo):self.salvar(p)
        self.assertEqual(self.padrao('explicativo')['dados']['briefing']['duracao_alvo'],45)
    def test_arquivamento_e_modelo_antigo_preservados(self):
        p=self.padrao('historia');a=self.salvar(p)
        api('PATCH','/api/v1/criativo/assets/'+a['id'],{'versao':a['versao'],'status':'arquivado'})
        r=api('GET','/api/v1/criativo/formatos')
        self.assertNotIn(a['id'],[x['id'] for x in r['salvos']])
        outro=api('POST','/api/v1/criativo/biblioteca',{'tipo':'template_pack','nome':'Antigo','dados':{'livre':True}})
        self.assertEqual(api('GET','/api/v1/criativo/assets/'+outro['id'])['dados'],{'livre':True})

if __name__=='__main__':unittest.main()
