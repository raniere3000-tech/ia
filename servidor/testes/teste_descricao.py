"""Descrição de publicação do Agente 3 (formato fixo) e o caminho prévia -> aprovação -> post do Agente 2.

Rodar:  python servidor/testes/teste_descricao.py
Sem internet. O vídeo é um arquivo pequeno qualquer: aqui só importa a descrição, não o vídeo.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='descricao-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import banco as db  # noqa: E402
import api_v1  # noqa: E402
import aprovacoes as apv  # noqa: E402
import descricao as ds  # noqa: E402
import postagem as pg  # noqa: E402
import produtor  # noqa: E402
import projetos as pj  # noqa: E402

falhas = 0


def confere(c, nome):
    global falhas
    print(('ok    ' if c else 'FALHA ') + nome)
    falhas += 0 if c else 1


class H:
    def __init__(self, caminho, corpo=None):
        self.path = caminho
        self.corpo = json.dumps(corpo or {}).encode()
        self.headers = {}


def api(metodo, caminho, corpo=None):
    return api_v1.tratar(H(caminho, corpo), metodo, caminho.split('?')[0], {'nome': 'teste', 'id': 's1'})


# ---------------------------------------------------------------- a função
print('Formato')
SEM_LINK = 'Por que o céu é azul\n\n#Ciência #CéuAzul #curiosidades\n\n.\n.\n.\nLink original do vídeo []'
d0 = ds.compor('[Por que o céu é azul]', ['#Ciência', 'CéuAzul', '#ciência', 'curiosidades'])
confere(d0 == SEM_LINK, 'sem link: título, hashtags, três pontos e "Link original do vídeo []" (exato)')
print('---\n' + d0 + '\n---')
d1 = ds.compor('Por que o céu é azul', ['#Ciência', '#CéuAzul', '#curiosidades'], 'https://www.youtube.com/watch?v=abc123')
confere(d1 == SEM_LINK.replace('[]', '[https://www.youtube.com/watch?v=abc123]'), 'link válido entra só dentro dos colchetes')
for ruim in ('www.site.com', 'javascript:alert(1)', 'https://x y.com', 'https://a.com/[x]', 'https://localhost', 'qualquer coisa'):
    confere(ds.compor('T', ['#a'], ruim).endswith('Link original do vídeo []'), f'link inválido não entra: {ruim!r}')
confere(ds.hashtags(['#Ciência', 'ciência', 'CIÊNCIA', 'céu azul', '##x', '']) == ['#Ciência', '#céuazul', '#x'], 'hashtags com # e sem repetir')
confere(ds.hashtags(['#a%d' % i for i in range(12)]) == ['#a%d' % i for i in range(12)], 'mantém a quantidade de hashtags do projeto')
confere(ds.compor('- **Título** ', []) == 'Título\n\n.\n.\n.\nLink original do vídeo []', 'sem hashtags: não fica linha vazia sobrando')
confere(ds.compor('Uma\nlinha   só', ['#a']).startswith('Uma linha só\n\n#a\n\n'), 'título numa linha só')
confere(d0.count('Link original do vídeo') == 1 and d0.count('\n.\n') == 2 and ds.aplicado(d0), 'rodapé e pontos aparecem uma vez')
cred = 'Ana, Wikimedia Commons (CC BY 4.0)'
dc = ds.compor('T', ['#a'], '', [cred])
confere(dc == f'T\n\n#a\n\nImagens: {cred}\n\n.\n.\n.\nLink original do vídeo []', 'créditos antes dos três pontos, modelo mantido')
confere(ds.com_creditos(dc, [cred]) == dc, 'crédito já presente não é repetido')
ed = 'Meu texto\n\n#a\n\n.\n.\n.\nLink original do vídeo []'
confere(ds.com_creditos(ed, [cred]) == f'Meu texto\n\n#a\n\nImagens: {cred}\n\n.\n.\n.\nLink original do vídeo []', 'crédito obrigatório entra na editada antes do rodapé')
confere(ds.com_creditos('Só texto', [cred]) == f'Só texto\n\nImagens: {cred}', 'editada sem rodapé: crédito no fim, nada inventado')
confere(ds.excede('x' * 2201, ['youtube', 'instagram']) == ['Instagram: a descrição tem 2201 caracteres e o limite é 2200 (passa 1).'], 'aviso só para a rede que passa do limite')
confere(ds.excede('x' * 2200, ['instagram', 'kwai']) == [], 'no limite: sem aviso')

# ---------------------------------------------------------------- aprovação
print('\nAprovação e post do Agente 2')
db.migrar()
api_v1.iniciar()


def projeto(titulo, hashtags, link=''):
    p = produtor.novo({'briefing': {'tema': 'Céu', 'estilo': 'animado2d', 'destinos': {'redes': ['kwai'], 'link_original': link}},
                       'roteiro': {'titulo': titulo, 'legenda': 'A luz explica.', 'hashtags': hashtags,
                                   'cenas': [{'titulo': 'A', 'texto': 'Por que o céu é azul?'}]}})
    pid = p['id']
    arq = TMP / f'{pid}.mp4'
    arq.write_bytes(pid.encode() * 100)
    sha = (pid * 8)[:64]
    db.executar('INSERT INTO renders (id, projeto, versao, arquivo, sha256, duracao, codec, largura, altura, validado, alertas, criado) VALUES (?,?,?,?,?,?,?,?,?,1,?,?)',
                'r' + pid, pid, 1, str(arq), sha, 3.0, 'h264', 360, 640, '[]', 0)

    def pronto(d, _p):
        d['render'] = {'id': 'r' + pid, 'versao': 1, 'sha': sha, 'validado': True}
        d['cenas'][0]['imagem'] = {'credito': cred}
        d['qualidade'] = {'status': 'apto_para_revisao_humana', 'problemas': []}   # passou no diretor de qualidade
        return {'status': 'ready_for_review'}
    pj.mudar_dados(pid, pronto)
    return pid, sha


def post_de(pid):
    return next(x for x in pg.posts() if x.get('projeto') == pid)


# 1) sem edição: o modelo padrão vai igual ao Agente 2
pid, sha = projeto('[Por que o céu é azul]', ['#Ciência', '#CéuAzul', '#ciência'])
pv = api('GET', f'/api/v1/projetos/{pid}/descricao')
esperado = f'Por que o céu é azul\n\n#Ciência #CéuAzul\n\nImagens: {cred}\n\n.\n.\n.\nLink original do vídeo []'
confere(pv['legenda'] == esperado and pv['padrao'] == esperado and not pv['editada'], 'prévia pronta antes de aprovar, no formato')
r = apv.aprovar(pid, sha, None, 'site', 'teste')
confere(post_de(pid)['legenda'] == pv['legenda'], 'legenda do Agente 2 = descrição da prévia')
n = len(pg.posts())
r2 = apv.aprovar(pid, sha, None, 'site', 'teste')
confere(r2.get('repetido') and len(pg.posts()) == n and post_de(pid)['legenda'].count('Link original do vídeo') == 1, 'aprovar de novo não duplica post, rodapé nem pontos')
confere(not [x for x in pg.conferencia(post_de(pid), 'kwai') if x['item'] == 'creditos' and x.get('bloqueia')], 'crédito obrigatório presente (Agente 2 não barra)')

# 2) link original informado no projeto
pid2, sha2 = projeto('Céu', ['#a'], 'https://exemplo.com/video/1')
apv.aprovar(pid2, sha2, None, 'site', 'teste')
confere(post_de(pid2)['legenda'].endswith('Link original do vídeo [https://exemplo.com/video/1]'), 'link válido do projeto vai dentro dos colchetes')

# 3) edição à mão guardada pelo site, respeitada na aprovação; restaurar volta ao padrão
pid3, sha3 = projeto('Céu azul', ['#ciencia'])
minha = 'Meu título do jeito que eu quero\n\n#ciencia #ceu\n\n.\n.\n.\nLink original do vídeo []'
pv3 = api('POST', f'/api/v1/projetos/{pid3}/descricao', {'legenda': minha})
confere(pv3['editada'] and pv3['legenda'].startswith('Meu título do jeito') and cred in pv3['legenda'], 'edição guardada (com o crédito obrigatório garantido)')
confere(api('GET', f'/api/v1/projetos/{pid3}/descricao')['legenda'] == pv3['legenda'], 'edição continua lá ao reabrir')
pv3b = api('POST', f'/api/v1/projetos/{pid3}/descricao', {'link_original': 'https://exemplo.com/x'})
confere(pv3b['legenda'] == pv3['legenda'] and pv3b['padrao'].endswith('[https://exemplo.com/x]'), 'mudar o link não apaga a edição à mão')
rs = api('POST', f'/api/v1/projetos/{pid3}/descricao', {'restaurar': True})
confere(not rs['editada'] and rs['legenda'] == rs['padrao'], 'restaurar o modelo padrão')
api('POST', f'/api/v1/projetos/{pid3}/descricao', {'legenda': minha})
apv.aprovar(pid3, sha3, {'redes': ['kwai'], 'quando': 'data', 'data': 4102444800}, 'site', 'teste')
p3 = post_de(pid3)
confere(p3['legenda'] == pv3['legenda'], 'aprovar e agendar mantém a edição à mão')
confere(p3['legenda'].count('Imagens:') == 1, 'crédito não duplicado na editada')

# 4) editada mandada junto com a aprovação (sem salvar antes)
pid4, sha4 = projeto('Céu', ['#a'])
apv.aprovar(pid4, sha4, {'legenda': 'Texto enviado na hora\n\n.\n.\n.\nLink original do vídeo []'}, 'site', 'teste')
confere(post_de(pid4)['legenda'].startswith('Texto enviado na hora\n\nImagens:'), 'legenda enviada na aprovação é a usada')

# 5) passou do limite: aviso e nada é cortado em silêncio
pid5, sha5 = projeto('Céu', ['#a'])
api('POST', f'/api/v1/projetos/{pid5}/descricao', {'legenda': 'x' * 2300})
pv5 = api('GET', f'/api/v1/projetos/{pid5}/descricao')
confere(pv5['avisos'] and 'Kwai' in pv5['avisos'][0], 'prévia avisa que passa do limite da rede')
try:
    apv.aprovar(pid5, sha5, None, 'site', 'teste')
    confere(False, 'aprovação acima do limite é recusada')
except apv.ErroAprovacao as e:
    confere(e.status == 422 and 'não cabe' in str(e), 'aprovação acima do limite é recusada com aviso (nada cortado)')
confere(not [x for x in pg.posts() if x.get('projeto') == pid5], 'nenhum post criado com texto cortado')

# 6) YouTube: nada é acrescentado depois do rodapé; posts antigos (sem o modelo) continuam ganhando #shorts
enviados = []
pg._token_google = lambda: 'x'
def _http(metodo, url, js=None, **k):
    enviados.append(js['snippet']['description'])
    raise RuntimeError('parou aqui (teste)')
pg.http, _http_antes = _http, pg.http
(TMP / 'x.mp4').write_bytes(b'x')
for leg in (SEM_LINK, 'Corte antigo'):
    try:
        pg.postar_youtube({'titulo': 'T', 'legenda': leg, 'opcoes': {}}, TMP / 'x.mp4')
    except RuntimeError:
        pass
pg.http = _http_antes
confere(enviados[:1] == [SEM_LINK], 'YouTube recebe a descrição terminando no "Link original do vídeo []"')
confere(len(enviados) > 1 and enviados[1].endswith('#shorts'), 'post sem o modelo continua como antes (#shorts)')

print('\n' + ('TUDO OK' if not falhas else f'{falhas} FALHA(S)'))
sys.exit(1 if falhas else 0)
