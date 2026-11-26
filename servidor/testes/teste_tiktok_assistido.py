"""Agente 2: publicação assistida do TikTok + atualização retroativa dos posts antigos.

Rodar:  python servidor/testes/teste_tiktok_assistido.py   (sem internet; o TikTok é simulado)
"""
import os
os.environ.setdefault('ESTEIRA_COMPLETA', '0')
import json
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='tkassist-'))
os.environ['DADOS'] = str(TMP / 'dados')
os.environ['BANCO_ARQ'] = str(TMP / 'dados' / 'database' / 'studio.sqlite')
os.environ['CHAVE_MESTRA_ARQ'] = str(TMP / 'chave')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import banco as db  # noqa: E402
import agente as ag  # noqa: E402
import postagem as pg  # noqa: E402
import tiktok_assistido as ta  # noqa: E402

falhas = ok = 0


def confere(c, nome):
    global falhas, ok
    print(('ok    ' if c else 'FALHA ') + nome)
    falhas += 0 if c else 1
    ok += 1 if c else 0


db.migrar()
pg.status_contas = lambda: {k: {'conectado': True, 'erro': '', 'paginas': [], 'pagina': ''} for k in set(pg.PROV.values())}
pg.conferencia = lambda p, rede: [{'item': 'arquivo', 'ok': True, 'bloqueia': False, 'detalhe': ''}]
AVISOS = []
ag.avisar = lambda tipo, assunto, corpo, *a, **k: AVISOS.append((tipo, assunto, corpo)) or True
ENVIOS = []
pg.PUBLICAR['tiktok'] = lambda p, arq: (ENVIOS.append(p['id']), 'Está nos rascunhos/notificações do TikTok: abra o app e toque em Postar')[1]
pg.PUBLICAR['youtube'] = lambda p, arq: 'https://youtu.be/abc'
pg.VIDEOS.mkdir(parents=True, exist_ok=True)
AGORA = pg.agora()

# ---- registros antigos (formato anterior: sem tiktok_meta nem tiktok_estado)
def antigo(i, redes, titulo, legenda, **extra):
    (pg.VIDEOS / f'a{i}.mp4').write_bytes(os.urandom(3000))
    p = {'id': f'old{i}', 'video': f'a{i}', 'criado': AGORA - 9999, 'quando': AGORA - 5000 + i, 'titulo': titulo, 'legenda': legenda,
         'opcoes': {'youtube_privacidade': 'public', 'tiktok_modo': 'rascunho'}, 'redes': redes, 'hash': f'h{i}', 'relatorio': [{'t': 1, 'rede': 'youtube', 'evento': 'postado', 'detalhe': 'x'}]}
    p.update(extra)
    return p


rodape = 'Titulo A\n\n#gta #games\n\n.\n.\n.\nLink original do vídeo [https://youtu.be/orig1]'
antigos = [
    antigo(1, {'youtube': {'status': 'postado', 'link': 'https://youtu.be/y1', 'erro': ''}}, 'Titulo A', rodape),
    antigo(2, {'youtube': {'status': 'postado', 'link': 'https://youtu.be/y2', 'erro': ''}}, 'Liberando o código do GTA 6', ''),
    antigo(3, {'tiktok': {'status': 'postado', 'link': 'Está nos rascunhos/notificações do TikTok: abra o app e toque em Postar', 'erro': ''}}, 'Rascunho no TikTok', 'texto livre'),
    antigo(4, {'tiktok': {'status': 'postado', 'link': 'https://www.tiktok.com/@x/video/1', 'erro': ''}}, 'Já publicado', 'texto'),
    antigo(5, {'tiktok': {'status': 'erro', 'link': '', 'erro': 'TikTok recusou'}}, 'Com falha', 'texto'),
    antigo(6, {'tiktok': {'status': 'agendado', 'link': '', 'erro': '', 'quando': AGORA + 86400}}, 'Agendado', 'texto', quando=AGORA + 86400),
    antigo(7, {'tiktok': {'status': 'cancelado', 'link': '', 'erro': ''}}, 'Cancelado', 'texto'),
    antigo(8, {'tiktok': {'status': 'postado', 'link': 'Enviado ao TikTok', 'erro': ''}}, 'Enviado direto', 'texto'),
    antigo(9, {'tiktok': {'status': 'agendado', 'link': '', 'erro': '', 'quando': AGORA - 100}}, 'Atrasado', 'texto'),
    antigo(10, {'youtube': {'status': 'postado', 'link': 'https://youtu.be/y10', 'erro': ''}}, '', ''),
]
ja_editado = antigo(11, {'youtube': {'status': 'postado', 'link': 'https://youtu.be/y11', 'erro': ''}}, 'Original', 'legenda original',
                    tiktok_meta={'v': 1, 'titulo': 'Meu título', 'descricao': 'Minha descrição', 'hashtags': ['#meu'], 'links': [{'rotulo': 'x', 'url': 'https://a.com/x'}], 'origem': {'titulo': 'editado'}})
antigos.append(ja_editado)
pg.salvar_posts(antigos)
copia_ids = [p['id'] for p in antigos]
videos_antes = sorted(x.name for x in pg.VIDEOS.glob('*'))
bytes_antes = {x.name: x.read_bytes() for x in pg.VIDEOS.glob('*')}
leg_antes = {p['id']: (p['titulo'], p['legenda'], json.dumps(p['redes'], sort_keys=True), p['relatorio']) for p in antigos}

# ---- 1. simulação não grava nada
r = ta.migrar(simular=True)
confere(r['simulado'] and r['atualizados'] == 10 and not any('tiktok_meta' in p for p in pg.posts() if p['id'] != 'old11'), f'simular não grava: {r}')

# ---- 2. migração real
r = ta.migrar()
ps = {p['id']: p for p in pg.posts()}
confere(r['posts'] == 11 and r['atualizados'] == 10 and r['ja_prontos'] == 1, f'migração: 10 atualizados, 1 já pronto: {r}')
confere(sorted(ps) == sorted(copia_ids), 'nenhum registro apagado')
confere(all(ps[i]['titulo'] == leg_antes[i][0] and ps[i]['legenda'] == leg_antes[i][1] and json.dumps(ps[i]['redes'], sort_keys=True) == leg_antes[i][2]
            and ps[i]['relatorio'] == leg_antes[i][3] for i in ps), 'título, legenda, redes e relatório antigos intactos')
confere(sorted(x.name for x in pg.VIDEOS.glob('*')) == videos_antes and all((pg.VIDEOS / n).read_bytes() == b for n, b in bytes_antes.items()),
        'vídeos não foram renderizados nem trocados; nenhuma capa nova')
confere((pg.DADOS / 'posts.antes-tiktok.json').exists(), 'cópia de segurança dos posts feita antes de gravar')
m1 = ps['old1']['tiktok_meta']
confere(m1['titulo'] == 'Titulo A' and m1['hashtags'] == ['#gta', '#games'] and m1['links'][0]['url'] == 'https://youtu.be/orig1'
        and any(l['url'] == 'https://youtu.be/y1' for l in m1['links']), f'recupera título, hashtags e links já existentes: {m1["hashtags"]} {[l["url"] for l in m1["links"]]}')
m2 = ps['old2']['tiktok_meta']
confere(m2['titulo'] == 'Liberando o código do GTA 6' and m2['descricao'].startswith('Liberando o código do GTA 6') and m2['origem']['descricao'] == 'gerado'
        and m2['hashtags'] and m2['origem']['hashtags'] == 'gerado', 'gera só o que faltava (descrição e hashtags) a partir do título')
confere(ps['old11']['tiktok_meta']['titulo'] == 'Meu título' and ps['old11']['tiktok_meta']['descricao'] == 'Minha descrição', 'o que já estava editado é preservado')
confere(ps['old10']['tiktok_meta']['titulo'] == '' and ps['old10']['tiktok_meta']['descricao'] == '', 'post sem nenhum texto não ganha texto inventado')
r2 = ta.migrar()
confere(r2['atualizados'] == 0 and r2['campos_gerados'] == 0, 'rodar de novo não muda nada (idempotente)')
confere(not ENVIOS, 'a migração não enviou nada ao TikTok')

# ---- 3. status
est = {i: ta.estado(ps[i]) for i in ps}
esperado = {'old1': 'pendente_envio', 'old2': 'pendente_envio', 'old3': 'aguardando_publicacao_manual', 'old4': 'publicado', 'old5': 'falha',
            'old6': 'agendado', 'old7': 'cancelado', 'old8': 'enviado_tiktok', 'old9': 'pendente_envio', 'old10': 'pendente_envio', 'old11': 'pendente_envio'}
confere(est == esperado, f'status de cada registro antigo: {[k for k in esperado if est[k] != esperado[k]]}')
confere(set(est.values()) | {'aguardando_confirmacao'} == set(ta.ESTADOS), 'os 8 status existem (confirmação vem pela ação do usuário)')
lista = {p['id']: p for p in pg.lista_posts()}
confere(all('tiktok' in p and p['tiktok']['estado'] == esperado[p['id']] for p in lista.values()), 'a lista de posts traz status e informações de TODOS os vídeos')

pg._mudar('old9', lambda p: p['redes']['tiktok'].update(status='cancelado'))   # o agendador real não pode pegar este nos testes seguintes

# ---- 4. editar (qualquer status) e copiar
v = ta.editar('old4', {'titulo': ' Novo *título* ', 'descricao': 'Nova descrição', 'hashtags': 'gta  jogos #gta', 'links': ['https://exemplo.com/a', 'lixo', {'rotulo': 'Fonte', 'url': 'https://exemplo.com/b'}]})
confere(v['meta']['titulo'] == 'Novo título' and v['meta']['hashtags'] == ['#gta', '#jogos'] and [l['url'] for l in v['meta']['links']] == ['https://exemplo.com/a', 'https://exemplo.com/b'],
        f'edita título, hashtags (sem repetir) e links (só válidos): {v["meta"]}')
confere('Novo título' in v['texto'] and '#jogos' in v['texto'] and 'Fonte: https://exemplo.com/b' in v['texto'], 'texto para copiar traz tudo')
confere(pg.posts()[3]['legenda'] == 'texto' and pg.posts()[3]['titulo'] == 'Já publicado', 'editar o TikTok não muda título e legenda do YouTube/Instagram')
v = ta.editar('old7', {'titulo': 'Mesmo cancelado'})
confere(v['meta']['titulo'] == 'Mesmo cancelado' and v['estado'] == 'cancelado', 'editar funciona até em post cancelado, sem mudar o status')
try:
    ta.editar('old7', {})
    confere(False, 'edição vazia recusada')
except pg.ErroRede:
    confere(True, 'edição vazia recusada')

# ---- 5. copiar e abrir TikTok → aguardando confirmação → publicado
v = ta.registrar('old3', 'abrir')
confere(v['estado'] == 'aguardando_confirmacao' and not ENVIOS, 'copiar e abrir TikTok: aguardando confirmação, sem novo upload')
v = ta.registrar('old3', 'confirmar', {'link': 'https://www.tiktok.com/@x/video/9'})
confere(v['estado'] == 'publicado' and pg.posts()[2]['redes']['tiktok']['link'] == 'https://www.tiktok.com/@x/video/9', 'confirmar publicação guarda o link')
v = ta.registrar('old1', 'abrir')
confere(v['estado'] == 'aguardando_confirmacao', 'vídeo que nunca foi ao TikTok também pode ser publicado à mão')
v = ta.registrar('old1', 'confirmar')
p1 = next(p for p in pg.posts() if p['id'] == 'old1')
confere(v['estado'] == 'publicado' and p1['redes']['tiktok']['status'] == 'postado' and 'youtube' in p1['redes'], 'publicado à mão entra na rede TikTok sem mexer no YouTube')
v = ta.registrar('old6', 'confirmar')
confere(v['estado'] == 'publicado', 'agendado confirmado à mão vira publicado (não envia de novo)')
pg.ciclo()
confere(not ENVIOS, 'o agendador não envia ao TikTok um vídeo já publicado/encaminhado')
v = ta.registrar('old4', 'reabrir')
confere(v['estado'] == 'publicado', 'link http continua publicado')

# ---- 6. vídeo novo: metadados antes do envio + aviso
(pg.VIDEOS / 'novo1.mp4').write_bytes(os.urandom(4000))
n = pg.criar_post({'video': 'novo1', 'redes': ['tiktok', 'youtube'], 'quando': AGORA - 5, 'titulo': 'Vídeo novo', 'legenda': 'Vídeo novo\n\n#novo #teste'})
confere(n['tiktok_meta']['titulo'] == 'Vídeo novo' and n['tiktok_meta']['hashtags'] == ['#novo', '#teste'], 'vídeo novo já nasce com as informações do TikTok preparadas')
confere(not AVISOS, 'ainda não avisou (o vídeo nem foi enviado)')
pg.ciclo()
nn = next(p for p in pg.posts() if p['id'] == n['id'])
confere(ENVIOS == [n['id']] and ta.estado(nn) == 'aguardando_publicacao_manual', 'enviado 1x aos rascunhos: aguardando publicação manual')
confere(len([a for a in AVISOS if a[0] == 'tiktok_pronto']) == 1 and 'Vídeo novo' in AVISOS[0][2], 'avisa que as informações estão prontas para publicar')
ta.notificar_pronto(n['id'])
confere(len([a for a in AVISOS if a[0] == 'tiktok_pronto']) == 1, 'o aviso não se repete')
pg.ciclo()
confere(ENVIOS == [n['id']], 'não reenvia o vídeo já encaminhado')

# ---- 6b. publicar novamente (mesmo arquivo, sem procurar o envio antigo)
ENVIOS.clear()
v = ta.registrar(n['id'], 'reenviar')
confere(v['estado'] == 'pendente_envio' and not v['pode_reenviar'], 'publicar novamente: entra na fila do TikTok')
try:
    ta.reenviar(n['id'])
    confere(False, 'não enfileira duas vezes')
except pg.ErroRede:
    confere(True, 'não enfileira duas vezes')
pg.ciclo()
nn = next(p for p in pg.posts() if p['id'] == n['id'])
confere(ENVIOS == [n['id']] and ta.estado(nn) == 'aguardando_publicacao_manual' and len(nn['redes']['tiktok']['envios_anteriores']) == 1
        and nn['redes']['youtube']['status'] == 'postado', 'reenviou o mesmo arquivo 1x, guardou o envio anterior e não mexeu no YouTube')
ENVIOS.clear()
v = ta.registrar('old4', 'reenviar')
pg.ciclo()
confere(ENVIOS == ['old4'], 'também vale para vídeos antigos já publicados')
(pg.VIDEOS / 'a8.mp4').unlink()
try:
    ta.reenviar('old8')
    confere(False, 'sem o arquivo no servidor, recusa')
except pg.ErroRede:
    confere(True, 'sem o arquivo no servidor, recusa')

# ---- 7. Direct Post preparado
confere(ta.modo_envio({'opcoes': {'tiktok_modo': 'direto'}}) == 'assistido', 'antes da aprovação: pediu direto, mas fica assistido')
ta.ligar_direct_post(True)
confere(ta.modo_envio({'opcoes': {'tiktok_modo': 'direto'}}) == 'direto' and ta.modo_envio({'opcoes': {'tiktok_modo': 'rascunho'}}) == 'assistido', 'depois de ligar: direto só para quem pediu direto')
ta.ligar_direct_post(False)

# ---- 8. rota HTTP existe e a lista de filtros cobre os 8 status
src = (Path(__file__).resolve().parent.parent / 'servidor.py').read_text()
confere("/posts/tiktok/migrar" in src and "(\\w+)/tiktok" in src, 'rotas do TikTok assistido registradas no servidor')

print(f'\n{ok} ok, {falhas} falha(s)')
sys.exit(1 if falhas else 0)
