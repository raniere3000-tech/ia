"""Agente 6: capas (thumbnails) dos cortes do Agente 1 e dos vídeos do Agente 3.

Recebe o arquivo FINAL (o mesmo que vai ser postado), tira quadros reais com o FFmpeg, escolhe os mais nítidos e diferentes
entre si, desenha de 1 a 4 capas com o Pillow (texto sempre pelo desenho próprio, nunca pela IA, para não sair com erro
de escrita) e entrega cada capa com o seu hash. O diretor (Agente 4) confere cada capa: legibilidade medida em tamanho
pequeno (120 px), área segura, arquivo, formato e identidade. A escolha fica presa ao hash do vídeo E da capa: se um
dos dois mudar, a escolha cai sozinha.

Regras fixas:
- nenhum caminho de arquivo vem do site: o vídeo é achado pelo id do corte, do render ou do post, dentro da pasta de dados;
- o FFmpeg roda com lista de argumentos (sem shell) e tempo limite; o texto nunca entra em comando;
- a capa não passa por cima de nenhum portão do Agente 2: só é enviada junto quando o post sai pelos caminhos de sempre;
- "nota" é conferência técnica: não prevê cliques (CTR) e não é teste A/B oficial de rede nenhuma.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
import unicodedata
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat
    Image.MAX_IMAGE_PIXELS = 40_000_000           # contra imagem "bomba" (descompressão gigante)
    PIL_OK = True
except ImportError:                               # sem Pillow o servidor sobe normal; só as capas ficam desligadas
    Image = ImageDraw = ImageFilter = ImageFont = ImageOps = ImageStat = None
    PIL_OK = False

import banco as db
import fila
import postagem as pg

SEM_PIL = 'Falta o Pillow para desenhar as capas. No Termux rode:  pkg install python-pillow  (no PC: pip install pillow) e reinicie o servidor.'

PASTA = pg.DADOS / 'thumbnails'
FONTE = Path(__file__).resolve().parent / 'fontes' / 'Inter-Bold.otf'
FORMATOS = {'16:9': (1280, 720), '9:16': (1080, 1920), '4:5': (1080, 1350), '1:1': (1080, 1080)}
METODOS = ('frame', 'editorial', 'ia', 'inteligente')
TEXTO_MODOS = ('auto', 'exato', 'sem')
ORIGENS = ('corte', 'render', 'post')
ESTADOS = ('aguardando_video', 'na_fila', 'analisando', 'criando', 'validando', 'aguardando_escolha', 'pronto', 'falhou', 'cancelado', 'revisao_manual')
LAYOUTS = {         # três ou quatro composições DIFERENTES por método (não só outra cor)
    'frame': ['cheia', 'moldura', 'cheia_topo', 'dividido'],
    'editorial': ['faixa', 'dividido', 'moldura', 'cheia'],
    'inteligente': ['cheia', 'faixa', 'dividido', 'moldura'],
    'ia': ['cheia', 'faixa', 'dividido', 'moldura'],
}
MAX_BYTES = 2 * 1024 * 1024             # limite do YouTube para capa (2 MB); vale para todas
LIMIAR_CONTRASTE = 4.5
TEXTO_MIN_PX_120 = 7                    # altura mínima da letra quando a capa aparece com 120 px de largura
CUSTO_IMAGEM_USD = 0.04                 # mesma estimativa usada pelo Agente 3 para uma imagem do Gemini

CONFIG_PADRAO = {
    'modo': 'automatico',               # automatico: escolhe sozinho a melhor aprovada | supervisionado: você escolhe | manual: só quando você pede
    'criar_sozinho': True,              # cria capas sozinho para cortes e vídeos do Agente 3 (automático e supervisionado; no manual, não)
    'metodo_padrao': 'inteligente',
    'variantes_padrao': 3,
    'max_variantes': 4,
    'max_correcoes': 5,
    'nota_min': 70,
    'ia': False,                        # usar o gerador de imagens (Gemini) para o fundo; o texto continua pelo desenho próprio
    'ia_max_por_pedido': 2,
    'ia_fallback_local': False,         # regra salva: se a IA falhar, fazer do jeito local sem perguntar
    'exigir_capa_youtube': True,        # (antigo) o Agente 2 só posta no YouTube com capa aprovada para o arquivo
    'exigir_capa': True,                # o Agente 2 só publica com capa válida PARA ESTE ARQUIVO nas redes de `redes_exigem_capa`
    'redes_exigem_capa': ['youtube', 'tiktok', 'instagram', 'facebook', 'kwai'],
    'recuperacao_automatica': True,     # vídeo mudou, pedido falhou ou ficou sem escolha: o Agente 6 refaz/escolhe sozinho
    'max_recuperacoes': 3,              # pedidos automáticos novos para a MESMA versão do vídeo (depois disso, exceção para você)
    'reenviar_capa': True,              # YouTube: se a capa não entrou, tenta de novo só a capa, no vídeo já postado
    'max_envios_capa': 5,
    'estrategia_rede': {'youtube': 'imagem', 'tiktok': 'quadro', 'instagram': 'quadro', 'facebook': 'manual', 'kwai': 'manual'},
    'formato_por_rede': {'youtube': 'auto', 'tiktok': '9:16', 'instagram': '9:16', 'facebook': '9:16', 'kwai': '9:16'},
}

# o que cada rede aceita de verdade (só vira "testado" depois de um envio real que deu certo)
REDES_CAPA = {
    'youtube': ('custom_image_upload', 'Envia a imagem pela API do YouTube (thumbnails.set) logo depois do vídeo. A conta precisa estar verificada '
                'no YouTube para aceitar capa personalizada. Em Shorts, o YouTube pode mostrar outro quadro no feed.'),
    'tiktok': ('frame_timestamp_only', 'O TikTok só deixa escolher um momento do vídeo como capa, e só no modo "postar direto". '
               'A arte com texto não vai; vai o segundo do quadro usado na capa.'),
    'instagram': ('frame_timestamp_only', 'O Reels recebe o momento do vídeo (thumb_offset). Para usar a arte com texto, baixe a capa e troque no app.'),
    'facebook': ('manual_only', 'Sem envio de capa pela integração atual. Baixe a capa e troque no app.'),
    'kwai': ('manual_only', 'O Kwai já é postado à mão: baixe a capa e use no app.'),
}


class ErroThumb(Exception):
    def __init__(self, status: int, msg: str):
        super().__init__(msg)
        self.status = status


class _Definitivo(RuntimeError):
    definitivo = True


# ---------------------------------------------------------------- configuração
ESTRATEGIAS = {'imagem': 'Enviar a arte como capa (YouTube)', 'quadro': 'Usar o quadro da capa no próprio vídeo (momento escolhido)',
               'manual': 'Você troca a capa no app', 'nenhuma': 'Não mexer na capa'}
AUTONOMIA_V1 = {'modo': 'automatico', 'variantes_padrao': 3, 'nota_min': 70, 'max_correcoes': 5, 'criar_sozinho': True, 'exigir_capa': True,
                'exigir_capa_youtube': True, 'recuperacao_automatica': True}


def config() -> dict:
    salvo = db.kv('agente6.config', {}) or {}
    if salvo and not db.kv('agente6.criar_sozinho_v2'):      # 19/11: criar sozinho passa a ser o padrão (antes vinha desligado e nada era feito)
        salvo['criar_sozinho'] = True
        db.kv_gravar('agente6.config', salvo)
        db.kv_gravar('agente6.criar_sozinho_v2', True)
    if not db.kv('agente6.autonomia_v1'):
        # 24/11: configuração aprovada pelo dono (automático, 3 capas, nota 70, 5 correções, capa obrigatória). Roda uma vez;
        # depois disso o que você mudar na tela vale (inclusive voltar para supervisionado ou manual).
        antes = {k: salvo.get(k) for k in AUTONOMIA_V1}
        if salvo:
            salvo.update(AUTONOMIA_V1)
            db.kv_gravar('agente6.config', salvo)
        db.kv_gravar('agente6.autonomia_v1', {'t': time.time(), 'antes': antes})
        try:
            db.evento('agente6', 'agente6_autonomia_v1', 'agente6', {'antes': antes})
        except Exception:  # noqa: BLE001
            pass
    c = {**CONFIG_PADRAO, **{k: v for k, v in salvo.items() if k in CONFIG_PADRAO}}
    c['formato_por_rede'] = {**CONFIG_PADRAO['formato_por_rede'], **(salvo.get('formato_por_rede') or {})}
    c['estrategia_rede'] = {**CONFIG_PADRAO['estrategia_rede'], **{r: e for r, e in (salvo.get('estrategia_rede') or {}).items() if e in ESTRATEGIAS}}
    c['redes_exigem_capa'] = [r for r in (c.get('redes_exigem_capa') or []) if r in REDES_CAPA]
    return c


def exige_capa(rede: str) -> bool:
    """O Agente 2 deve barrar esta rede sem capa válida para o arquivo?"""
    c = config()
    if rede == 'youtube' and c['exigir_capa_youtube']:
        return True
    return bool(c['exigir_capa']) and rede in c['redes_exigem_capa'] and c['estrategia_rede'].get(rede) != 'nenhuma'


def salvar_config(d: dict, quem: str = 'site') -> dict:
    c = config()
    if 'modo' in d:
        if d['modo'] not in ('automatico', 'supervisionado', 'manual'):
            raise ErroThumb(400, 'Modo inválido.')
        c['modo'] = d['modo']
    for k in ('criar_sozinho', 'ia', 'ia_fallback_local', 'exigir_capa_youtube', 'exigir_capa', 'recuperacao_automatica', 'reenviar_capa'):
        if k in d:
            c[k] = bool(d[k])
    if isinstance(d.get('redes_exigem_capa'), list):
        c['redes_exigem_capa'] = [r for r in REDES_CAPA if r in d['redes_exigem_capa']]
    if isinstance(d.get('estrategia_rede'), dict):
        for r, e in d['estrategia_rede'].items():
            if r in REDES_CAPA and e in ESTRATEGIAS:
                c['estrategia_rede'][r] = e
    if 'metodo_padrao' in d:
        if d['metodo_padrao'] not in METODOS:
            raise ErroThumb(400, 'Método inválido.')
        c['metodo_padrao'] = d['metodo_padrao']
    for k, lo, hi in (('variantes_padrao', 1, 4), ('max_variantes', 1, 4), ('max_correcoes', 0, 5), ('nota_min', 50, 95), ('ia_max_por_pedido', 0, 4),
                      ('max_recuperacoes', 0, 10), ('max_envios_capa', 1, 10)):
        if k in d:
            try:
                c[k] = max(lo, min(hi, int(d[k])))
            except (TypeError, ValueError):
                raise ErroThumb(400, f'Valor inválido em {k}.')
    c['variantes_padrao'] = min(c['variantes_padrao'], c['max_variantes'])
    if isinstance(d.get('formato_por_rede'), dict):
        for r, f in d['formato_por_rede'].items():
            if r in REDES_CAPA and (f in FORMATOS or f == 'auto'):
                c['formato_por_rede'][r] = f
    db.kv_gravar('agente6.config', c)
    db.evento(quem, 'agente6_config', 'agente6', {k: c[k] for k in ('modo', 'criar_sozinho', 'ia', 'exigir_capa_youtube', 'exigir_capa',
                                                                   'recuperacao_automatica', 'variantes_padrao', 'nota_min', 'max_correcoes')})
    return c


def ia_disponivel() -> tuple[bool, str]:
    if not config()['ia']:
        return False, 'A geração com IA está desligada nas Configurações do Agente 6.'
    try:
        import agente as ag
        if not ag.chaves_gemini('imagens'):
            return False, 'Falta a chave do Gemini para imagens (Configurações > Chaves).'
    except Exception as e:  # noqa: BLE001
        return False, f'Gerador de imagens indisponível: {str(e)[:120]}'
    return True, ''


def rejeicao_ativa() -> bool:
    return os.getenv('THUMB_REJEICAO', '0').lower() in ('1','true','sim')


def capacidades() -> dict:
    ok_ia, motivo_ia = ia_disponivel()
    redes = {}
    for r, (tipo, det) in REDES_CAPA.items():
        t = db.kv('agente6.rede_ok.' + r)
        redes[r] = {'tipo': tipo, 'detalhe': det, 'testado': bool(t), 'testado_em': t,
                    'estado': 'funcionou num envio real' if t else ('não testado com conta real' if tipo != 'manual_only' else 'manual')}
    return {'rejeicao_habilitada': rejeicao_ativa(), 'ffmpeg': bool(shutil.which('ffmpeg')) and bool(shutil.which('ffprobe')), 'pillow': PIL_OK, 'pillow_aviso': '' if PIL_OK else SEM_PIL, 'fonte': FONTE.exists(),
            'ia': {'disponivel': ok_ia, 'motivo': motivo_ia}, 'redes': redes, 'formatos': list(FORMATOS), 'metodos': list(METODOS),
            'aviso': 'A nota das capas é conferência técnica (leitura, área segura, arquivo). Não prevê cliques e não é teste A/B oficial.'}


# ---------------------------------------------------------------- de onde vem o vídeo (nunca um caminho mandado pelo site)
def _dentro_dos_dados(arq: Path) -> Path:
    try:
        real = Path(arq).resolve(strict=True)
    except (OSError, RuntimeError):
        raise ErroThumb(404, 'O arquivo do vídeo não está no servidor.')
    base = pg.DADOS.resolve()
    if base not in real.parents or not real.is_file():
        raise ErroThumb(403, 'Arquivo fora da pasta do EstúdioClip: recusado.')
    if real.suffix.lower() not in ('.mp4', '.mov', '.m4v', '.webm'):
        raise ErroThumb(422, 'Só vídeos MP4, MOV ou WebM.')
    return real


def _ref_ok(ref: str) -> str:
    ref = str(ref or '')
    if not re.fullmatch(r'[\w-]{1,64}', ref):
        raise ErroThumb(400, 'Referência inválida.')
    return ref


def resolver(origem: str, ref: str) -> dict:
    """Acha o vídeo final pelo id. Devolve arquivo, título e textos sugeridos."""
    ref = _ref_ok(ref)
    if origem == 'corte':
        import agente as ag
        c = next((x for x in ag.estado()['cortes'] if x['id'] == ref), None)
        if not c or not c.get('video'):
            raise ErroThumb(404, 'Corte não encontrado.')
        try:
            arq = pg.video_path(c['video'])
        except pg.ErroRede:
            raise ErroThumb(404, 'O arquivo deste corte não está mais no servidor.')
        return {'arquivo': _dentro_dos_dados(arq), 'titulo': c.get('titulo') or 'Corte', 'gancho': c.get('gancho') or '', 'agente': 'Agente 1',
                'status': c.get('status', ''), 'perfil': c.get('perfil') or '', 'canal': c.get('canal_nome') or '', 'linha': ''}
    if origem == 'render':
        import aprovacoes as apv
        import projetos as pj
        try:
            p = pj.obter(ref)
        except pj.ErroProjeto:
            raise ErroThumb(404, 'Vídeo do Agente 3 não encontrado.')
        r = apv._render_atual(p)
        if not r:
            raise ErroThumb(404, 'Este vídeo do Agente 3 ainda não tem a versão final pronta.')
        rot = p['dados'].get('roteiro') or {}
        return {'arquivo': _dentro_dos_dados(Path(r['arquivo'])), 'titulo': rot.get('titulo') or p.get('titulo') or 'Vídeo', 'agente': 'Agente 3',
                'gancho': rot.get('gancho') or '', 'status': p.get('status', ''), 'perfil': '', 'canal': '',
                'linha': str((p['dados'].get('linha') or {}).get('id') if isinstance(p['dados'].get('linha'), dict) else p['dados'].get('linha') or '')}
    if origem == 'post':
        post = next((x for x in pg.posts() if x['id'] == ref), None)
        if not post:
            raise ErroThumb(404, 'Post não encontrado.')
        try:
            arq = pg.video_path(post['video'])
        except pg.ErroRede:
            raise ErroThumb(404, 'O vídeo deste post não está mais no servidor.')
        return {'arquivo': _dentro_dos_dados(arq), 'titulo': post.get('titulo') or 'Post', 'gancho': '', 'agente': 'Agente 2',
                'status': ','.join(sorted({r['status'] for r in post['redes'].values()})), 'perfil': '', 'canal': '', 'linha': ''}
    raise ErroThumb(400, 'Origem inválida (corte, render ou post).')


def _certificado_ok(arq: Path) -> tuple[bool, str]:
    """Com a esteira ligada, a capa só começa depois que o diretor aprovou o VÍDEO final."""
    import pipeline as pl
    if not pl.ligado():
        return True, ''
    if pl.certificado(pl.sha_arquivo(arq)):
        return True, ''
    return False, 'Esperando o diretor (Agente 4) aprovar a versão final do vídeo.'


def _ultimo_job(origem: str, ref: str) -> dict | None:
    return db.um('SELECT * FROM thumbnail_jobs WHERE origem=? AND referencia=? ORDER BY criado DESC LIMIT 1', origem, ref)


def fontes(origem: str = '', termo: str = '', limite: int = 80) -> list:
    """Vídeos que podem ganhar capa: cortes do Agente 1 (prontos/agendados), vídeos finais do Agente 3 e posts."""
    import agente as ag
    out = []
    termo = (termo or '').casefold().strip()
    if origem in ('', 'corte'):
        for c in reversed(ag.estado()['cortes'][-200:]):
            if c.get('status') not in ('pronto', 'agendado', 'postado'):
                continue
            out.append({'origem': 'corte', 'referencia': c['id'], 'titulo': c.get('titulo') or 'Corte', 'agente': 'Agente 1', 'status': c.get('status'),
                        'criado': c.get('criado') or 0})
    if origem in ('', 'render'):
        for p in db.todos("SELECT id, titulo, status, atualizado FROM projetos WHERE tipo='agente3' AND apagado=0 "
                          "AND status IN ('ready_for_review','approved','scheduled','published') ORDER BY atualizado DESC LIMIT 100"):
            out.append({'origem': 'render', 'referencia': p['id'], 'titulo': p['titulo'] or 'Vídeo', 'agente': 'Agente 3', 'status': p['status'],
                        'criado': p['atualizado'] or 0})
    if origem == 'post':
        for p in sorted(pg.posts(), key=lambda x: -x['criado'])[:100]:
            out.append({'origem': 'post', 'referencia': p['id'], 'titulo': p.get('titulo') or 'Post', 'agente': 'Agente 2',
                        'status': ','.join(sorted({r['status'] for r in p['redes'].values()})), 'criado': p['criado']})
    if termo:
        out = [x for x in out if termo in x['titulo'].casefold()]
    out = out[:max(1, min(200, limite))]
    for x in out:
        j = _ultimo_job(x['origem'], x['referencia'])
        x['job'] = {'id': j['id'], 'estado': j['estado']} if j else None
    return out


# ---------------------------------------------------------------- pedidos (jobs)
def _agora():
    return time.time()


def _job(tid: str) -> dict:
    if not re.fullmatch(r'[a-f0-9]{12}', str(tid or '')):
        raise ErroThumb(400, 'Pedido inválido.')
    j = db.um('SELECT * FROM thumbnail_jobs WHERE id=?', tid)
    if not j:
        raise ErroThumb(404, 'Pedido de capa não encontrado.')
    j['config'] = json.loads(j['config'] or '{}')
    return j


def _estado(tid: str, estado: str, erro: str | None = None):
    if erro is None:
        db.executar("UPDATE thumbnail_jobs SET estado=?, atualizado=? WHERE id=? AND (estado<>'cancelado' OR ?='cancelado')", estado, _agora(), tid, estado)
    else:
        db.executar("UPDATE thumbnail_jobs SET estado=?, erro=?, atualizado=? WHERE id=? AND (estado<>'cancelado' OR ?='cancelado')", estado, erro[:500], _agora(), tid, estado)


def _limpar_texto(t: str, n: int | None = 60) -> str:
    t = unicodedata.normalize('NFC', str(t or ''))
    t = ''.join(ch for ch in t if unicodedata.category(ch)[0] != 'C' or ch == '\n')
    return re.sub(r'[ \t]+', ' ', t).strip()[:n]


def _texto_completo(t: str) -> str:
    texto = _limpar_texto(t, None)
    if len(texto) > 500:
        raise ErroThumb(400, 'O texto da capa pode ter até 500 caracteres. Ajuste a frase antes de enviar.')
    return texto


def criar(d: dict, quem: str = 'site') -> dict:
    if not PIL_OK:
        raise ErroThumb(503, SEM_PIL)
    cfg = config()
    origem = d.get('origem')
    if origem not in ORIGENS:
        raise ErroThumb(400, 'Escolha de onde vem o vídeo: corte, render ou post.')
    ref = _ref_ok(d.get('referencia'))
    metodo = d.get('metodo') or cfg['metodo_padrao']
    if metodo not in METODOS:
        raise ErroThumb(400, 'Método inválido (frame, editorial, ia ou inteligente).')
    try:
        n = int(d.get('variantes') or cfg['variantes_padrao'])
    except (TypeError, ValueError):
        raise ErroThumb(400, 'Número de variantes inválido.')
    if not 1 <= n <= cfg['max_variantes']:
        raise ErroThumb(400, f'Peça de 1 a {cfg["max_variantes"]} capas.')
    formato = d.get('formato') or 'auto'
    if formato not in FORMATOS and formato != 'auto':
        raise ErroThumb(400, 'Formato inválido (16:9, 9:16, 4:5, 1:1 ou automático).')
    texto_modo = d.get('texto_modo') or 'auto'
    if texto_modo not in TEXTO_MODOS:
        raise ErroThumb(400, 'Modo do texto inválido (auto, exato ou sem).')
    texto = _texto_completo(d.get('texto'))
    if texto_modo == 'exato' and not texto:
        raise ErroThumb(400, 'Escreva o texto exato da capa.')
    descricao = _limpar_texto(d.get('descricao'), 500)
    perfil_id = str(d.get('perfil_id') or '')
    if perfil_id:
        perfil(perfil_id)            # 404 se não existir
    info = resolver(origem, ref)
    import pipeline as pl
    sha = pl.sha_arquivo(info['arquivo'])
    if not sha:
        raise ErroThumb(404, 'Não consegui ler o vídeo.')
    if d.get('reaproveitar'):
        # Esteira e Coordenador pedem capa do MESMO vídeo por caminhos diferentes: um pedido vivo para a mesma versão serve aos dois.
        ja = db.um("SELECT id FROM thumbnail_jobs WHERE origem=? AND referencia=? AND video_sha=? AND estado NOT IN ('falhou','cancelado') "
                   "ORDER BY criado DESC LIMIT 1", origem, ref, sha)
        if ja:
            db.evento(str(quem)[:60], 'thumbnail_pedido_reaproveitado', 'thumb:' + ja['id'], {'video_sha': sha[:16]})
            return dict(obter(ja['id']), reaproveitado=True)
    aviso = ''
    if metodo == 'ia':
        ok, motivo = ia_disponivel()
        if not ok:
            if d.get('fallback_local') or cfg['ia_fallback_local']:
                metodo, aviso = 'inteligente', motivo + ' Fiz com quadros do próprio vídeo (você permitiu).'
            else:
                raise ErroThumb(503, motivo + ' Escolha "Quadro do vídeo" ou "Editorial", ou marque "usar o jeito local se a IA não der".')
    conf = {'metodo': metodo, 'variantes': n, 'formato': formato, 'texto_modo': texto_modo, 'texto': texto, 'descricao': descricao,
            'perfil_id': perfil_id, 'aviso': aviso, 'destino': d.get('destino') if d.get('destino') in REDES_CAPA else ''}
    cliente = str(d.get('chave_idempotencia') or '')[:80]
    identidade = [origem, ref, sha, conf] + ([cliente] if cliente else [])
    chave = hashlib.sha256(json.dumps(identidade, sort_keys=True).encode()).hexdigest()[:40]
    tid = secrets.token_hex(6)
    agora = _agora()
    with db.tx() as c:
        ja = c.execute('SELECT id FROM thumbnail_jobs WHERE chave=?', (chave,)).fetchone()
        repetido = bool(ja)
        if ja:
            tid = ja['id']
        else:
            c.execute('INSERT INTO thumbnail_jobs (id, origem, referencia, video_sha, config, estado, criado, atualizado, chave, titulo, metodo, por) '
                      'VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (tid, origem, ref, sha, json.dumps(conf, ensure_ascii=False), 'na_fila', agora, agora, chave,
                      info['titulo'][:150], metodo, str(quem)[:60]))
    # Se houve queda entre criar o pedido e enfileirar, o pedido repetido completa a ligação.
    if not (_job(tid).get('fila_job')):
        fj = fila.enfileirar('agente6.thumbnail', agente='agente6', dados={'job': tid}, titulo='Capa: ' + info['titulo'][:80], chave='thumb:' + tid,
                             prioridade=5, max_tentativas=3)
        db.executar('UPDATE thumbnail_jobs SET fila_job=? WHERE id=? AND fila_job IS NULL', fj['id'], tid)
    if not repetido:
        db.evento(quem, 'thumbnail_pedido', 'thumb:' + tid, {'origem': origem, 'ref': ref, 'metodo': metodo, 'variantes': n})
    return dict(obter(tid), repetido=True) if repetido else obter(tid)


def cancelar(tid: str, quem: str = 'site') -> dict:
    j = _job(tid)
    if j['estado'] in ('pronto', 'falhou', 'cancelado'):
        raise ErroThumb(409, 'Este pedido já terminou.')
    if j['fila_job']:
        try:
            fila.cancelar(j['fila_job'])
        except Exception:  # noqa: BLE001 - já terminou na fila
            pass
    _estado(tid, 'cancelado', 'Cancelado por você.')
    db.evento(quem, 'thumbnail_cancelado', 'thumb:' + tid)
    return obter(tid)


def refazer(tid: str, d: dict, quem: str = 'site') -> dict:
    """Refaz SÓ uma variante (nova versão), com texto novo se quiser. Conta como correção criativa (máx. configurado)."""
    j = _job(tid)
    cfg = config()
    try:
        numero = int(d.get('numero') or 0)
    except (TypeError, ValueError):
        numero = 0
    if not 1 <= numero <= j['config']['variantes']:
        raise ErroThumb(400, 'Diga qual capa refazer (número da variante).')
    if j['estado'] in ('na_fila', 'analisando', 'criando', 'validando'):
        raise ErroThumb(409, 'Espere terminar o que está rodando.')
    if j['correcoes'] >= cfg['max_correcoes'] + 3:
        raise ErroThumb(429, 'Limite de refações deste pedido atingido. Crie um pedido novo.')
    texto = _texto_completo(d.get('texto')) if 'texto' in d else None
    versao = (db.um('SELECT MAX(versao) v FROM thumbnail_variantes WHERE job=? AND numero=?', tid, numero) or {}).get('v') or 0
    chave = 'thumb-refazer:' + hashlib.sha256(json.dumps([tid, j['video_sha'], numero, versao, texto, j.get('fila_job')]).encode()).hexdigest()
    j2 = fila.enfileirar('agente6.thumbnail', agente='agente6', dados={'job': tid, 'refazer': numero, 'texto': texto},
                         titulo=f'Capa {numero}: refazer', prioridade=6, max_tentativas=2, chave=chave)
    if j2.get('repetido'):
        return dict(obter(tid), repetido=True)
    db.executar('UPDATE thumbnail_jobs SET fila_job=?, estado=?, atualizado=?, erro=NULL WHERE id=?', j2['id'], 'na_fila', _agora(), tid)
    db.evento(quem, 'thumbnail_refazer', 'thumb:' + tid, {'numero': numero})
    return obter(tid)


# ---------------------------------------------------------------- vídeo e quadros
def _sondar(arq: Path) -> dict:
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(arq)],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60, check=True)
        info = json.loads(r.stdout or '{}')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, OSError):
        raise _Definitivo('O vídeo não abre (arquivo incompleto ou corrompido). Nenhuma capa foi feita.')
    v = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), None)
    try:
        dur = float(info.get('format', {}).get('duration') or v.get('duration') or 0) if v else 0
    except (TypeError, ValueError):
        dur = 0
    if not v or dur < 1 or not v.get('width'):
        raise _Definitivo('O vídeo não tem imagem ou dura menos de 1 segundo. Nenhuma capa foi feita.')
    return {'duracao': dur, 'largura': int(v['width']), 'altura': int(v['height']), 'codec': v.get('codec_name', '')}


def _tempos(dur: float, n: int) -> list[float]:
    ini = min(1.0, dur * 0.1) if dur > 3 else 0.0
    fim = max(ini + 0.1, dur - (1.0 if dur > 3 else 0.2))
    return [round(ini + (fim - ini) * (i + 0.5) / n, 2) for i in range(n)]


def _extrair(arq: Path, dur: float, pasta: Path, n: int, prog) -> list[dict]:
    pasta.mkdir(parents=True, exist_ok=True)
    out = []
    for i, t in enumerate(_tempos(dur, n)):
        prog(10 + 35 * i / n, f'Tirando quadros do vídeo ({i + 1} de {n})')
        dest = pasta / f'q{i:02d}.jpg'
        if not dest.exists():
            tmp = pasta / f'q{i:02d}.tmp.jpg'
            try:
                subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-ss', f'{t:.2f}', '-i', str(arq), '-frames:v', '1',
                                '-vf', 'scale=1280:1280:force_original_aspect_ratio=decrease', '-q:v', '2', str(tmp)],
                               capture_output=True, stdin=subprocess.DEVNULL, timeout=90, check=True)
                os.replace(tmp, dest)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
                tmp.unlink(missing_ok=True)
                continue
        out.append({'arquivo': dest, 't': t})
    if not out:
        raise _Definitivo('Não consegui tirar nenhum quadro do vídeo.')
    return out


def _dhash(img: Image.Image) -> int:
    g = img.convert('L').resize((9, 8), Image.BILINEAR)
    px = list(g.getdata())
    return sum(1 << i for i in range(64) if px[(i // 8) * 9 + i % 8] > px[(i // 8) * 9 + i % 8 + 1])


def _medir_quadro(arq: Path) -> dict:
    with Image.open(arq) as im:
        im.load()
        g = im.convert('L')
        peq = g.resize((320, max(1, int(320 * g.height / g.width))))
        nit = ImageStat.Stat(peq.filter(ImageFilter.FIND_EDGES)).var[0]
        st = ImageStat.Stat(peq)
        return {'nitidez': round(nit, 1), 'brilho': round(st.mean[0], 1), 'contraste': round(st.stddev[0], 1), 'hash': _dhash(im)}


def _ranquear(quadros: list[dict], n: int) -> list[dict]:
    """Nítido, nem escuro nem estourado, com contraste; e DIFERENTES entre si (hash de imagem)."""
    for q in quadros:
        q.update(_medir_quadro(q['arquivo']))
        luz = 1.0 if 40 <= q['brilho'] <= 215 else 0.4
        q['pontos'] = round((min(q['nitidez'], 2500) / 2500 * 60 + min(q['contraste'], 80) / 80 * 40) * luz, 1)
    ordem = sorted(quadros, key=lambda q: -q['pontos'])
    escolhidos = []
    for q in ordem:
        if all(bin(q['hash'] ^ e['hash']).count('1') >= 10 for e in escolhidos):
            escolhidos.append(q)
        if len(escolhidos) == n:
            break
    for q in ordem:                    # vídeo muito parado: completa com os melhores restantes
        if len(escolhidos) == n:
            break
        if q not in escolhidos:
            escolhidos.append(q)
    while len(escolhidos) < n:
        escolhidos.append(escolhidos[len(escolhidos) % max(1, len(ordem))])
    return escolhidos


# ---------------------------------------------------------------- texto
_EMOJI = re.compile('[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0000FE0F\U0000200D\U00002B00-\U00002BFF]')


def texto_da_capa(conf: dict, info: dict) -> tuple[str, list]:
    """Preserva a frase inteira. Texto entre aspas na descrição tem prioridade no modo automático."""
    avisos = []
    if conf['texto_modo'] == 'sem':
        return '', avisos
    if conf['texto_modo'] == 'exato':
        t = conf['texto']
    else:
        m = re.search(r'["“\'‘]([^"”\'’]{1,500})["”\'’]', conf.get('descricao') or '')
        base = m.group(1) if m else (conf.get('texto') or info.get('gancho') or info.get('titulo') or '')
        base = re.sub(r'#\w+', '', base)
        t = _limpar_texto(base, None)
    return sem_emoji(t, avisos), avisos


def sem_emoji(t: str, avisos: list) -> str:
    sem = re.sub(r'[ \t]+', ' ', _EMOJI.sub('', t or '')).strip()
    if sem != (t or '').strip():
        avisos.append('Emoji removido: a fonte da capa não tem desenho de emoji.')
    return sem


def _fonte(px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTE), max(8, int(px)))


def _quebrar(draw: ImageDraw.ImageDraw, texto: str, fonte, largura: int) -> list[str]:
    linhas = []
    for par in texto.split('\n'):
        atual = ''
        for p in par.split():
            teste = (atual + ' ' + p).strip()
            if draw.textlength(teste, font=fonte) <= largura or not atual:
                atual = teste
            else:
                linhas.append(atual)
                atual = p
        if atual:
            linhas.append(atual)
    return linhas


def _caber(texto: str, caixa_w: int, caixa_h: int, px_max: int, px_min: int, max_linhas: int = 6):
    """Maior fonte em que o texto cabe na caixa (largura E altura). overflow=True se nem no mínimo couber."""
    rasc = ImageDraw.Draw(Image.new('L', (8, 8)))
    px = px_max
    while px >= px_min:
        f = _fonte(px)
        linhas = _quebrar(rasc, texto, f, caixa_w)
        alt = int(px * 1.12) * len(linhas)
        larg = max((rasc.textlength(x, font=f) for x in linhas), default=0)
        if len(linhas) <= max_linhas and alt <= caixa_h and larg <= caixa_w:
            return f, linhas, px, False
        px -= max(2, px // 14)
    f = _fonte(px_min)
    return f, _quebrar(rasc, texto, f, caixa_w), px_min, True


# ---------------------------------------------------------------- desenho
def _hex(c: str, padrao: str) -> tuple:
    c = c if isinstance(c, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', c) else padrao
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def _cobrir(img: Image.Image, w: int, h: int, foco_y: float = 0.45) -> Image.Image:
    return ImageOps.fit(img.convert('RGB'), (w, h), Image.LANCZOS, centering=(0.5, foco_y))


def area_segura(formato: str) -> tuple[int, int, int, int]:
    """Retângulo onde o texto pode ficar. 9:16: livre das barras do app (topo e base); 16:9: livre do selo de duração."""
    w, h = FORMATOS[formato]
    if formato == '9:16':
        return int(w * 0.08), int(h * 0.12), int(w * 0.84), int(h * 0.62)
    if formato == '16:9':
        return int(w * 0.05), int(h * 0.07), int(w * 0.90), int(h * 0.74)
    return int(w * 0.07), int(h * 0.08), int(w * 0.86), int(h * 0.80)


def desenhar(fundo: Image.Image, formato: str, layout: str, texto: str, perfil_cfg: dict, logo: Image.Image | None = None) -> tuple[Image.Image, dict]:
    """Desenha uma capa. Devolve a imagem e o laudo do desenho (caixa do texto, máscara do texto, overflow)."""
    w, h = FORMATOS[formato]
    cor_txt = _hex(perfil_cfg.get('cor_texto'), '#FFFFFF')
    cor_dest = _hex(perfil_cfg.get('cor_destaque'), '#FFE14D')
    cor_fundo = _hex(perfil_cfg.get('cor_faixa'), '#111111')
    forca = max(0, min(100, int(perfil_cfg.get('intensidade', 70) or 0))) / 100
    maiusc = perfil_cfg.get('maiusculas', True)
    sx, sy, sw, sh = area_segura(formato)
    canvas = _cobrir(fundo, w, h)
    caixa = (sx, sy, sw, sh)
    fundo_texto = None                 # cor sólida atrás do texto (quando há)
    cor_letra = cor_txt
    vertical = h >= w

    if layout in ('cheia', 'cheia_topo', 'caixa'):
        grad = Image.new('L', (1, 256))
        for y in range(256):
            v = y if layout != 'cheia_topo' else 255 - y
            grad.putpixel((0, y), int(max(0, v - 70) * 1.4 * forca))
        sombra = Image.new('RGB', (w, h), (0, 0, 0))
        canvas = Image.composite(sombra, canvas, grad.resize((w, h)))
        if layout == 'cheia_topo':
            caixa = (sx, sy, sw, int(sh * 0.45))
        elif layout == 'cheia':
            caixa = (sx, sy + int(sh * 0.50), sw, int(sh * 0.50))
        else:
            caixa = (sx + int(sw * 0.06), sy + int(sh * 0.30), int(sw * 0.88), int(sh * 0.40))
    elif layout == 'faixa':
        alt = int(sh * 0.36)
        caixa = (sx, sy, sw, alt)
        fundo_texto = cor_dest
        cor_letra = cor_fundo
    elif layout == 'dividido':
        if vertical:
            corte = int(h * 0.47)
            canvas.paste(_cobrir(fundo, w, corte, 0.4), (0, 0))
            ImageDraw.Draw(canvas).rectangle((0, corte, w, h), fill=cor_fundo)
            caixa = (sx, corte + int(h * 0.02), sw, max(10, sy + sh - corte - int(h * 0.02)))
        else:
            lado = int(w * 0.46)
            canvas.paste(_cobrir(fundo, w - lado, h, 0.45), (lado, 0))
            ImageDraw.Draw(canvas).rectangle((0, 0, lado, h), fill=cor_fundo)
            caixa = (sx, sy, lado - sx - int(w * 0.03), sh)
        ImageDraw.Draw(canvas).rectangle((0, 0, w, max(6, h // 120)), fill=cor_dest)
    elif layout == 'moldura':
        borrado = _cobrir(fundo, w, h).filter(ImageFilter.GaussianBlur(max(8, w // 60)))
        canvas = Image.blend(borrado, Image.new('RGB', (w, h), cor_fundo), 0.45)
        borda = max(6, w // 110)
        iw = int(w * (0.84 if vertical else 0.50))
        ih = int(h * (0.46 if vertical else 0.66))
        if vertical:
            ix, iy = (w - iw) // 2, sy + int(sh * 0.40)
        else:
            ix, iy = w - iw - int(w * 0.05), (h - ih) // 2
        ImageDraw.Draw(canvas).rectangle((ix - borda, iy - borda, ix + iw + borda, iy + ih + borda), fill=cor_dest)
        canvas.paste(_cobrir(fundo, iw, ih), (ix, iy))
        caixa = (sx, sy, sw, int(sh * 0.36)) if vertical else (sx, sy, ix - sx - int(w * 0.04), sh)
    else:
        raise ValueError('layout desconhecido: ' + layout)

    laudo = {'layout': layout, 'texto': texto, 'caixa_texto': None, 'overflow': False, 'fonte_px': 0, 'mascara': None, 'area_segura': [sx, sy, sw, sh]}
    if texto:
        t = texto.upper() if maiusc else texto
        bx, by, bw, bh = caixa
        pad = int(min(w, h) * 0.025) if fundo_texto or layout == 'caixa' else 0
        f, linhas, px, over = _caber(t, bw - 2 * pad, bh - 2 * pad, int(min(w, h) * (0.20 if not vertical else 0.17)), int(min(w, h) * 0.045))
        lh = int(px * 1.12)
        bloco_h = lh * len(linhas)
        rasc = ImageDraw.Draw(canvas)
        larg = int(max(rasc.textlength(x, font=f) for x in linhas))
        y0 = by + (bh - bloco_h) // 2 if layout != 'cheia' else by + bh - bloco_h - pad
        if fundo_texto or layout == 'caixa':
            cor_caixa = fundo_texto or (0, 0, 0)
            camada = Image.new('RGBA', (w, h), (0, 0, 0, 0))
            ImageDraw.Draw(camada).rounded_rectangle((bx, y0 - pad, bx + larg + 2 * pad, y0 + bloco_h + pad), radius=max(6, pad), fill=(*cor_caixa, 235))
            canvas = Image.alpha_composite(canvas.convert('RGBA'), camada).convert('RGB')
            if layout == 'caixa':
                cor_letra = cor_txt
        draw = ImageDraw.Draw(canvas)
        mascara = Image.new('L', (w, h), 0)
        dm = ImageDraw.Draw(mascara)
        contorno = 0 if fundo_texto or layout == 'caixa' else max(2, px // 14)
        for i, linha in enumerate(linhas):
            x = bx + pad
            y = y0 + i * lh
            ultima = i == len(linhas) - 1 and len(linhas) > 1 and not fundo_texto
            draw.text((x, y), linha, font=f, fill=cor_dest if ultima and layout != 'caixa' else cor_letra, stroke_width=contorno, stroke_fill=(0, 0, 0))
            dm.text((x, y), linha, font=f, fill=255)
        caixa_txt = (bx, y0 - pad, bx + larg + 2 * pad, y0 + bloco_h + pad)
        laudo.update(caixa_texto=list(caixa_txt), overflow=over, fonte_px=px, mascara=mascara, linhas=linhas)
    if logo is not None:
        lw = int(w * 0.13)
        lg = ImageOps.contain(logo.convert('RGBA'), (lw, lw))
        pos = (sx + sw - lg.width, sy) if not (texto and laudo['caixa_texto'] and laudo['caixa_texto'][2] > sx + sw - lg.width
                                               and laudo['caixa_texto'][1] < sy + lg.height) else (sx + sw - lg.width, sy + sh - lg.height)
        base = canvas.convert('RGBA')
        base.alpha_composite(lg, pos)
        canvas = base.convert('RGB')
        laudo['logo'] = True
    return canvas, laudo


# ---------------------------------------------------------------- conferência do diretor (Agente 4) para capas
def _lum(rgb) -> float:
    def c(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * c(rgb[0]) + 0.7152 * c(rgb[1]) + 0.0722 * c(rgb[2])


def legibilidade(img: Image.Image, mascara: Image.Image | None, fonte_px: int) -> dict:
    """Mede o texto como ele aparece pequeno (120 px de largura): contraste entre letras e o que está em volta, e altura da letra."""
    if mascara is None:
        return {'contraste': None, 'altura_120': None, 'medido': False}
    escala = 120 / img.width
    peq_h = max(1, int(img.height * escala))
    peq = img.resize((120, peq_h), Image.LANCZOS)
    m = mascara.resize((120, peq_h), Image.LANCZOS)
    volta = m.filter(ImageFilter.MaxFilter(5))
    letras, fundo = [], []
    for (px, mk, vk) in zip(peq.getdata(), m.getdata(), volta.getdata()):
        if mk > 140:
            letras.append(px)
        elif vk > 60 and mk < 20:
            fundo.append(px)
    if not letras or not fundo:
        return {'contraste': None, 'altura_120': round(fonte_px * escala, 1), 'medido': False}
    def media(lst):
        return tuple(sum(p[i] for p in lst) / len(lst) for i in range(3))
    l1, l2 = _lum(media(letras)), _lum(media(fundo))
    ratio = (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)
    return {'contraste': round(ratio, 2), 'altura_120': round(fonte_px * escala, 1), 'medido': True}


def conferir(arq: Path, laudo: dict, formato: str, metodo: str, quadro: dict | None, perfil_usado: bool, destino_formato: str) -> dict:
    """Nota 0–100 com os critérios do pacote: fidelidade 25, legibilidade 20, área segura 15, técnica 15, identidade 15, rede 10.
    Bloqueio crítico reprova mesmo com nota alta. O laudo diz o MÉTODO (não é inspeção de todos os quadros)."""
    crit, bloq, notas = {}, [], []
    w, h = FORMATOS[formato]
    # técnica: o arquivo abre de verdade, tem o tamanho certo e cabe no limite
    try:
        with Image.open(arq) as im:
            im.verify()
        with Image.open(arq) as im:
            im.load()
            dims = im.size
            img = im.convert('RGB')
    except Exception:  # noqa: BLE001
        return {'nota': 0, 'aprovado': False, 'criterios': {}, 'bloqueios': ['A capa não abre (arquivo quebrado).'], 'notas': [], 'metodo': 'arquivo'}
    tam = arq.stat().st_size
    tec = 15
    if dims != (w, h):
        bloq.append(f'Tamanho errado: {dims[0]}x{dims[1]} (esperado {w}x{h}).')
        tec = 0
    if tam > MAX_BYTES:
        bloq.append(f'Arquivo grande demais ({tam // 1024} KB; limite 2048 KB).')
        tec = 0
    if quadro and quadro.get('nitidez', 999) < 60:
        tec -= 5
        notas.append('Quadro pouco nítido.')
    if quadro and not 40 <= quadro.get('brilho', 128) <= 215:
        tec -= 4
        notas.append('Quadro muito escuro ou muito claro.')
    crit['tecnica'] = max(0, tec)
    # fidelidade: quadro real do próprio vídeo vale inteiro; imagem gerada pede conferência humana
    if metodo == 'ia':
        crit['fidelidade'] = 15
        notas.append('Fundo gerado por IA: confira se representa o vídeo (a IA não confere isso sozinha).')
    else:
        crit['fidelidade'] = 25
        notas.append(f'Fundo é um quadro real do vídeo (segundo {quadro["t"]:.1f}).' if quadro else 'Fundo é um quadro real do vídeo.')
    # legibilidade
    if laudo.get('texto'):
        leg = legibilidade(img, laudo.get('mascara'), laudo.get('fonte_px') or 0)
        pts = 20
        if leg['contraste'] is not None:
            if leg['contraste'] < 3:
                pts -= 14
                notas.append(f'Pouco contraste do texto em tamanho pequeno ({leg["contraste"]}:1).')
            elif leg['contraste'] < LIMIAR_CONTRASTE:
                pts -= 6
                notas.append(f'Contraste do texto razoável ({leg["contraste"]}:1); o ideal é 4,5:1.')
        if (leg['altura_120'] or 0) < TEXTO_MIN_PX_120:
            pts -= 8
            notas.append(f'Letra pequena demais no celular ({leg["altura_120"]} px a 120 px de largura).')
        crit['legibilidade'] = max(0, pts)
        crit['legibilidade_medida'] = leg
    else:
        crit['legibilidade'] = 20
    # área segura
    seg = 15
    if laudo.get('overflow'):
        bloq.append('O gancho completo não cabe neste layout. Ajuste as quebras de linha ou escolha outra composição.')
        seg = 0
    cx = laudo.get('caixa_texto')
    if cx:
        sx, sy, sw, sh = laudo['area_segura']
        folga = int(min(w, h) * 0.01)
        if cx[0] < sx - folga or cx[1] < sy - folga or cx[2] > sx + sw + folga or cx[3] > sy + sh + folga:
            bloq.append('Texto fora da área segura (pode ficar escondido pelos botões do app).')
            seg = 0
    crit['area_segura'] = seg
    crit['identidade'] = 15 if perfil_usado else 10
    if not perfil_usado:
        notas.append('Sem perfil de marca: usei as cores padrão.')
    crit['rede'] = 10 if formato == destino_formato else 5
    if formato != destino_formato:
        notas.append(f'O formato {formato} não é o do destino ({destino_formato}).')
    nota = sum(v for k, v in crit.items() if isinstance(v, (int, float)))
    nota = max(0, min(100, int(nota)))
    return {'nota': nota, 'aprovado': nota >= config()['nota_min'] and not bloq, 'criterios': crit, 'bloqueios': bloq, 'notas': notas,
            'metodo': 'conferência automática da imagem final (abre o arquivo, mede o texto a 120 px e a área segura); '
                      'não confere se o texto é verdadeiro nem se a pessoa da imagem autorizou.'}


# ---------------------------------------------------------------- perfis de marca
def _perfil_cfg(d: dict, base: dict | None = None) -> dict:
    c = dict(base or {'cor_texto': '#FFFFFF', 'cor_destaque': '#FFE14D', 'cor_faixa': '#111111', 'intensidade': 70, 'maiusculas': True,
                      'logo_asset': '', 'nicho': '', 'exemplos': ''})
    for k in ('cor_texto', 'cor_destaque', 'cor_faixa'):
        if k in d:
            if not re.fullmatch(r'#[0-9a-fA-F]{6}', str(d[k] or '')):
                raise ErroThumb(400, f'Cor inválida em {k} (use #RRGGBB).')
            c[k] = d[k]
    if 'intensidade' in d:
        try:
            c['intensidade'] = max(0, min(100, int(d['intensidade'])))
        except (TypeError, ValueError):
            raise ErroThumb(400, 'Intensidade inválida.')
    if 'maiusculas' in d:
        c['maiusculas'] = bool(d['maiusculas'])
    for k in ('nicho', 'exemplos'):
        if k in d:
            c[k] = _limpar_texto(d[k], 300)
    if 'logo_asset' in d:
        aid = str(d['logo_asset'] or '')
        if aid:
            _logo(aid)            # confere que é imagem de verdade
        c['logo_asset'] = aid
    return c


def perfis() -> list:
    out = []
    for p in db.todos('SELECT * FROM thumbnail_perfis ORDER BY atualizado DESC'):
        p['config'] = json.loads(p['config'] or '{}')
        out.append(p)
    return out


def perfil(pid: str) -> dict:
    if not re.fullmatch(r'[a-f0-9]{10}', str(pid or '')):
        raise ErroThumb(400, 'Perfil inválido.')
    p = db.um('SELECT * FROM thumbnail_perfis WHERE id=?', pid)
    if not p:
        raise ErroThumb(404, 'Perfil de capa não encontrado.')
    p['config'] = json.loads(p['config'] or '{}')
    return p


def criar_perfil(d: dict, quem: str = 'site') -> dict:
    nome = _limpar_texto(d.get('nome'), 60)
    if not nome:
        raise ErroThumb(400, 'Dê um nome ao perfil.')
    escopo = str(d.get('escopo') or 'geral')
    if not re.fullmatch(r'geral|(canal|linha|perfil):[\w-]{1,64}', escopo):
        raise ErroThumb(400, 'Escopo inválido (geral, canal:..., linha:... ou perfil:...).')
    pid = secrets.token_hex(5)
    agora = _agora()
    db.executar('INSERT INTO thumbnail_perfis (id, nome, escopo, config, versao, criado, atualizado) VALUES (?,?,?,?,1,?,?)',
                pid, nome, escopo, json.dumps(_perfil_cfg(d), ensure_ascii=False), agora, agora)
    db.evento(quem, 'thumbnail_perfil_criado', 'thumbperfil:' + pid)
    return perfil(pid)


def mudar_perfil(pid: str, d: dict, quem: str = 'site') -> dict:
    p = perfil(pid)
    nome = _limpar_texto(d.get('nome'), 60) or p['nome']
    cfg = _perfil_cfg(d, p['config'])
    db.executar('UPDATE thumbnail_perfis SET nome=?, config=?, versao=versao+1, atualizado=? WHERE id=?', nome, json.dumps(cfg, ensure_ascii=False), _agora(), pid)
    db.evento(quem, 'thumbnail_perfil_mudou', 'thumbperfil:' + pid)
    return perfil(pid)


def _logo(aid: str) -> Image.Image:
    if not re.fullmatch(r'[\w-]{4,64}', aid):
        raise ErroThumb(400, 'Logo inválido.')
    a = db.um('SELECT * FROM assets WHERE id=?', aid)
    if not a:
        raise ErroThumb(404, 'Logo não encontrado na biblioteca de arquivos.')
    arq = Path(a['caminho'])
    try:
        real = arq.resolve(strict=True)
    except OSError:
        raise ErroThumb(404, 'O arquivo do logo sumiu.')
    if pg.DADOS.resolve() not in real.parents:
        raise ErroThumb(403, 'Logo fora da pasta do EstúdioClip.')
    try:
        with Image.open(real) as im:
            im.verify()
        im = Image.open(real)
        im.load()
        if im.width * im.height > 16_000_000:
            raise ErroThumb(413, 'Logo grande demais.')
        return im
    except ErroThumb:
        raise
    except Exception:  # noqa: BLE001
        raise ErroThumb(422, 'O logo não é uma imagem válida.')


def _perfil_para(conf: dict, info: dict) -> tuple[dict, bool, Image.Image | None]:
    """Perfil escolhido, ou o do canal/perfil/linha do vídeo, ou o geral. Nunca altera a biblioteca original."""
    p = None
    if conf.get('perfil_id'):
        p = perfil(conf['perfil_id'])
    else:
        for esc in ([f'perfil:{info["perfil"]}'] if info.get('perfil') else []) + ([f'linha:{info["linha"]}'] if info.get('linha') else []) + ['geral']:
            p = db.um('SELECT * FROM thumbnail_perfis WHERE escopo=? ORDER BY atualizado DESC LIMIT 1', esc)
            if p:
                p['config'] = json.loads(p['config'] or '{}')
                break
    if not p:
        return {}, False, None
    logo = None
    if p['config'].get('logo_asset'):
        try:
            logo = _logo(p['config']['logo_asset'])
        except ErroThumb:
            logo = None
    return dict(p['config'], _id=p['id'], _versao=p['versao']), True, logo


# ---------------------------------------------------------------- trabalho da fila
def _formato(conf: dict, meta: dict) -> str:
    if conf['formato'] in FORMATOS:
        return conf['formato']
    dest = conf.get('destino')
    if dest:
        f = config()['formato_por_rede'].get(dest, 'auto')
        if f in FORMATOS:
            return f
    return '9:16' if meta['altura'] > meta['largura'] else '16:9'


def _salvar_imagem(img: Image.Image, dest: Path) -> tuple[str, int]:
    """JPEG com qualidade que cabe em 2 MB; grava em arquivo temporário e troca de uma vez (os.replace)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix('.tmp')
    for q in (92, 86, 80, 72, 64):
        img.save(tmp, 'JPEG', quality=q, optimize=True, progressive=True)
        if tmp.stat().st_size <= MAX_BYTES:
            break
    os.replace(tmp, dest)
    h = hashlib.sha256(dest.read_bytes()).hexdigest()
    return h, dest.stat().st_size


def _fundo_ia(conf: dict, info: dict, formato: str, pasta: Path, i: int, tid: str) -> Path | None:
    """Fundo pelo gerador de imagens (sem texto). Falha -> None (usa o quadro do vídeo e avisa)."""
    import produtor
    prompt = (f'Fundo para capa de vídeo, sem nenhum texto escrito. Assunto: {info["titulo"][:120]}. '
              f'{conf.get("descricao") or ""} Composição forte, alto contraste, espaço livre para título.')
    dest = pasta / f'ia{i}.png'
    if dest.exists():
        return dest
    try:
        produtor.gerar_imagem(prompt, dest, formato)
        import agente as ag
        custo = CUSTO_IMAGEM_USD * float(ag.config()['orcamento'].get('dolar', 5.5))
        db.executar('UPDATE thumbnail_jobs SET custo=custo+? WHERE id=?', round(custo, 4), tid)
        with Image.open(dest) as im:
            im.verify()
        return dest
    except Exception as e:  # noqa: BLE001
        dest.unlink(missing_ok=True)
        db.evento('agente6', 'thumbnail_ia_falhou', 'thumb:' + tid, {'motivo': str(e)[:200]})
        return None


def _variante_existe(tid: str, numero: int, versao: int) -> dict | None:
    return db.um('SELECT * FROM thumbnail_variantes WHERE job=? AND numero=? AND versao=?', tid, numero, versao)


def _uma_variante(tid, j, conf, info, formato, destino_formato, numero, versao, layout, quadro, texto, perfil_cfg, perfil_usado, logo, pasta, metodo, fundo_arq=None):
    with Image.open(fundo_arq or quadro['arquivo']) as im:
        im.load()
        fundo = im.convert('RGB')
    img, laudo = desenhar(fundo, formato, layout, texto, perfil_cfg, logo)
    dest = PASTA / tid / f'capa-{numero}-v{versao}.jpg'
    sha, _tam = _salvar_imagem(img, dest)
    rel = conferir(dest, laudo, formato, 'ia' if fundo_arq else 'frame', quadro, perfil_usado, destino_formato)
    rel['layout'] = layout
    rel['texto'] = texto
    vid = secrets.token_hex(6)
    db.executar('INSERT OR IGNORE INTO thumbnail_variantes (id, job, numero, versao, arquivo, sha256, formato, largura, altura, conceito, nota, relatorio, estado, criado, '
                'layout, quadro_t, metodo, custo) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', vid, tid, numero, versao, str(dest), sha, formato,
                FORMATOS[formato][0], FORMATOS[formato][1], f'{layout} · {"fundo IA" if fundo_arq else "quadro do vídeo"}', rel['nota'],
                json.dumps({k: v for k, v in rel.items()}, ensure_ascii=False, default=str), 'aprovada' if rel['aprovado'] else 'reprovada', _agora(),
                layout, quadro['t'] if quadro else None, 'ia' if fundo_arq else metodo, 0)
    return _variante_existe(tid, numero, versao), rel


def _correcao(layout: str, texto: str) -> tuple[str, str]:
    """Melhora o contraste e reorganiza o texto sem remover palavras do gancho."""
    return 'caixa', texto


def job_thumbnail(ctx) -> dict:
    tid = ctx.dados.get('job', '')
    if not PIL_OK:
        raise _Definitivo(SEM_PIL)
    j = _job(tid)
    if j['estado'] == 'cancelado':
        return {'etapa': 'Cancelado'}
    conf = j['config']
    cfg = config()
    info = resolver(j['origem'], j['referencia'])
    import pipeline as pl
    arq = info['arquivo']
    if pl.sha_arquivo(arq) != j['video_sha']:
        _estado(tid, 'falhou', 'O vídeo mudou depois do pedido (outra versão). Peça a capa de novo para a versão nova.')
        raise _Definitivo('O vídeo mudou depois do pedido.')
    ok, motivo = _certificado_ok(arq)
    if not ok:
        _estado(tid, 'aguardando_video', motivo)
        raise fila.Esperar(300, motivo)
    _estado(tid, 'analisando', '')
    ctx.progresso(5, 'Conferindo o vídeo')
    meta = _sondar(arq)
    formato = _formato(conf, meta)
    destino_formato = '9:16' if meta['altura'] > meta['largura'] else '16:9'
    if conf.get('destino') and cfg['formato_por_rede'].get(conf['destino']) in FORMATOS:
        destino_formato = cfg['formato_por_rede'][conf['destino']]
    pasta = PASTA / tid / 'trabalho'
    n = conf['variantes']
    quadros = _extrair(arq, meta['duracao'], pasta, max(6, n * 3), ctx.progresso)
    escolhidos = _ranquear(quadros, n)
    _estado(tid, 'criando')
    perfil_cfg, perfil_usado, logo = _perfil_para(conf, info)
    texto, avisos = texto_da_capa(conf, info)
    refazer_n = ctx.dados.get('refazer')
    if refazer_n and ctx.dados.get('texto') is not None:
        texto = sem_emoji(ctx.dados['texto'], avisos)
    metodo = conf['metodo']
    layouts = LAYOUTS[metodo]
    ia_restantes = cfg['ia_max_por_pedido'] if metodo == 'ia' else 0
    correcoes = j['correcoes']
    feitas = []
    numeros = [int(refazer_n)] if refazer_n else list(range(1, n + 1))
    for k, numero in enumerate(numeros):
        ctx.progresso(50 + 40 * k / len(numeros), f'Desenhando a capa {numero} de {n}')
        ult = db.um('SELECT MAX(versao) AS v FROM thumbnail_variantes WHERE job=? AND numero=?', tid, numero)['v'] or 0
        if refazer_n:
            versao = ult + 1 if not ctx.dados.get('versao_feita') else ctx.dados['versao_feita']
            ctx.dados['versao_feita'] = versao
            ctx.salvar()
        else:
            versao = 1
            if _variante_existe(tid, numero, 1):        # reinício: não refaz o que já foi gravado
                continue
        if _variante_existe(tid, numero, versao):
            continue
        quadro = escolhidos[(numero - 1) % len(escolhidos)]
        if refazer_n:
            quadro = escolhidos[(numero - 1 + ult) % len(escolhidos)]        # outro quadro na refação
        layout = layouts[(numero - 1) % len(layouts)]
        fundo_arq = None
        if metodo == 'ia' and ia_restantes > 0:
            ia_restantes -= 1
            fundo_arq = _fundo_ia(conf, info, formato, pasta, numero, tid)
            if fundo_arq is None:
                avisos.append(f'Capa {numero}: a IA não gerou o fundo; usei um quadro do vídeo.')
        _estado(tid, 'validando')
        v, rel = _uma_variante(tid, j, conf, info, formato, destino_formato, numero, versao, layout, quadro, texto, perfil_cfg, perfil_usado, logo, pasta,
                               metodo, fundo_arq)
        t_corr = texto
        while not rel['aprovado'] and correcoes < cfg['max_correcoes'] and not any('não abre' in b for b in rel['bloqueios']):
            correcoes += 1
            db.executar('UPDATE thumbnail_jobs SET correcoes=? WHERE id=?', correcoes, tid)
            db.executar("UPDATE thumbnail_variantes SET estado='substituida' WHERE id=?", v['id'])
            layout, t_corr = _correcao(layout, t_corr)
            versao += 1
            if _variante_existe(tid, numero, versao):
                v = _variante_existe(tid, numero, versao)
                rel = json.loads(v['relatorio'])
                continue
            v, rel = _uma_variante(tid, j, conf, info, formato, destino_formato, numero, versao, layout, quadro, t_corr, perfil_cfg, perfil_usado, logo, pasta,
                                   metodo, fundo_arq)
            if layout == 'caixa' and not rel['aprovado']:
                break
        feitas.append({'numero': numero, 'versao': v['versao'], 'nota': v['nota'], 'aprovada': v['estado'] == 'aprovada'})
    if avisos or conf.get('aviso'):
        conf['avisos'] = list(dict.fromkeys([*(conf.get('avisos') or []), *avisos, *([conf['aviso']] if conf.get('aviso') else [])]))[:10]
        db.executar('UPDATE thumbnail_jobs SET config=? WHERE id=?', json.dumps(conf, ensure_ascii=False), tid)
    shutil.rmtree(pasta, ignore_errors=True) if not refazer_n else None
    ativas = db.todos("SELECT * FROM thumbnail_variantes WHERE job=? AND estado IN ('aprovada','reprovada') ORDER BY numero, versao DESC", tid)
    aprovadas = [x for x in ativas if x['estado'] == 'aprovada']
    if not aprovadas:
        _estado(tid, 'revisao_manual', 'Nenhuma capa passou na conferência depois das correções. Veja o motivo em cada uma, ou refaça uma.')
    elif cfg['modo'] == 'automatico' and (not refazer_n or not selecao_ativa(tid) or ctx.dados.get('auto')):
        # automático: escolhe a melhor aprovada, também depois de refazer (se ninguém escolheu ainda, ou se foi o próprio A6 que refez)
        selecionar_melhor(tid, 'agente6-automatico')
    else:
        _estado(tid, 'aguardando_escolha', '')
    ctx.progresso(100, 'Capas prontas')
    return {'etapa': 'Capas prontas', 'resultado': {'job': tid, 'feitas': feitas}}


def _ao_falhar(job: dict, msg: str):
    if not job or job.get('tipo') != 'agente6.thumbnail':
        return
    try:
        tid = json.loads(job.get('dados') or '{}').get('job')
        if tid:
            _estado(tid, 'falhou', msg)
            import agente as ag
            ag.avisar('falha', 'Capa não saiu', f'O Agente 6 não conseguiu fazer a capa.\n\nMotivo: {msg[:300]}\n')
    except Exception as e:  # noqa: BLE001
        print('agente6: aviso de falha:', e)


# ---------------------------------------------------------------- escolha, aprovação e pacote
def _video_atual_sha(j: dict) -> str:
    try:
        import pipeline as pl
        return pl.sha_arquivo(resolver(j['origem'], j['referencia'])['arquivo'])
    except ErroThumb:
        return ''


def _arquivo_sha(caminho: str) -> str:
    try:
        return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()
    except OSError:
        return ''


def selecao_ativa(tid: str) -> dict | None:
    return db.um('SELECT * FROM thumbnail_selecoes WHERE job=? AND revogado IS NULL ORDER BY criado DESC LIMIT 1', tid)


def _revogar(sid: str, motivo: str):
    n = db.executar('UPDATE thumbnail_selecoes SET revogado=?, motivo=? WHERE id=? AND revogado IS NULL', _agora(), motivo[:200], sid)
    if n:
        db.evento('agente6', 'thumbnail_selecao_revogada', 'thumbsel:' + sid, {'motivo': motivo[:200]})


def revalidar(tid: str) -> dict | None:
    """A escolha só vale para o MESMO vídeo e a MESMA capa. Mudou o vídeo: cai a escolha. Mudou a capa: cai a aprovação."""
    s = selecao_ativa(tid)
    if not s:
        return None
    j = db.um('SELECT * FROM thumbnail_jobs WHERE id=?', tid)
    v = db.um('SELECT * FROM thumbnail_variantes WHERE id=?', s['variante'])
    if not j or _video_atual_sha(j) != s['video_sha']:
        _revogar(s['id'], 'O vídeo mudou depois da escolha da capa.')
        db.executar("UPDATE thumbnail_jobs SET estado='aguardando_escolha', erro=?, atualizado=? WHERE id=?", 'O vídeo mudou: peça capas para a versão nova.', _agora(), tid)
        return None
    if not v or _arquivo_sha(v['arquivo']) != s['thumb_sha']:
        _revogar(s['id'], 'A capa mudou depois da aprovação.')
        db.executar("UPDATE thumbnail_jobs SET estado='aguardando_escolha', atualizado=? WHERE id=?", _agora(), tid)
        return None
    return s


def rejeitar(tid: str, d: dict, quem: str = 'site') -> dict:
    """Recusa proposta sem gerar outra nem revogar a seleção atual."""
    if not rejeicao_ativa():
        raise ErroThumb(409, 'A recusa de propostas ainda não está habilitada no servidor.')
    j = _job(tid)
    if j['estado'] in ('na_fila','analisando','criando','validando'):
        raise ErroThumb(409, 'Espere terminar a geração das capas.')
    if _video_atual_sha(j) != j['video_sha']:
        raise ErroThumb(409, 'O vídeo mudou. Abra o pedido da versão atual.')
    vid = str(d.get('variante_id') or '')
    repetido = False
    with db.tx() as c:
        v = c.execute('SELECT * FROM thumbnail_variantes WHERE id=? AND job=?', (vid,tid)).fetchone()
        if not v:
            raise ErroThumb(404, 'Proposta não encontrada neste pedido.')
        if d.get('versao') != v['versao']:
            raise ErroThumb(409, 'A versão da capa mudou. Atualize a tela.')
        if v['estado'] == 'substituida':
            raise ErroThumb(409, 'Esta proposta já foi substituída.')
        if c.execute('SELECT id FROM thumbnail_selecoes WHERE variante=? AND revogado IS NULL', (vid,)).fetchone():
            raise ErroThumb(409, 'Esta é a capa escolhida. Escolha uma substituta antes de recusar esta versão.')
        repetido = v['estado'] == 'rejeitada'
        if not repetido:
            rel = json.loads(v['relatorio'] or '{}')
            rel['rejeicao'] = {'por': str(quem)[:80], 't': _agora(), 'motivo': str(d.get('motivo') or '')[:500]}
            c.execute("UPDATE thumbnail_variantes SET estado='rejeitada', relatorio=? WHERE id=?", (json.dumps(rel,ensure_ascii=False),vid))
    if not repetido:
        db.evento(quem, 'thumbnail_proposta_rejeitada', 'thumb:' + tid, {'variante': vid, 'versao': d['versao']})
    return dict(obter(tid), repetido=True) if repetido else obter(tid)


def selecionar(tid: str, d: dict, quem: str = 'site') -> dict:
    j = _job(tid)
    vid = str(d.get('variante_id') or '')
    v = db.um('SELECT * FROM thumbnail_variantes WHERE id=? AND job=?', vid, tid)
    if not v:
        raise ErroThumb(404, 'Capa não encontrada neste pedido.')
    if d.get('versao') is not None and int(d['versao']) != v['versao']:
        raise ErroThumb(409, 'Esta capa tem uma versão mais nova. Atualize a tela.')
    if v['estado'] in ('substituida','rejeitada'):
        raise ErroThumb(409, 'Esta versão foi substituída ou recusada. Escolha outra proposta.')
    video_sha = _video_atual_sha(j)
    if video_sha != j['video_sha']:
        raise ErroThumb(409, 'O vídeo mudou depois que as capas foram feitas. Peça capas para a versão nova.')
    sha = _arquivo_sha(v['arquivo'])
    if sha != v['sha256']:
        raise ErroThumb(409, 'O arquivo da capa mudou. Refaça esta capa.')
    rel = json.loads(v['relatorio'] or '{}')
    if rel.get('bloqueios'):
        raise ErroThumb(409, 'Esta capa tem bloqueio do diretor e não pode ser usada: ' + ' '.join(rel['bloqueios'])[:300])
    manual = v['estado'] != 'aprovada'
    if manual and not d.get('confirmacao'):
        raise ErroThumb(409, f'O diretor deu nota {v["nota"]} (mínimo {config()["nota_min"]}). Para usar mesmo assim, confirme.')
    with db.tx() as c:
        atual = c.execute('SELECT estado FROM thumbnail_variantes WHERE id=?', (vid,)).fetchone()
        if not atual or atual['estado'] in ('substituida','rejeitada'):
            raise ErroThumb(409, 'Esta proposta foi substituída ou recusada. Atualize a tela.')
        repetido = c.execute('SELECT id FROM thumbnail_selecoes WHERE job=? AND variante=? AND video_sha=? AND thumb_sha=? AND revogado IS NULL',
                             (tid,vid,video_sha,sha)).fetchone()
        antigas = []
        if not repetido:
            antigas = c.execute('SELECT id FROM thumbnail_selecoes WHERE (job=? OR video_sha=?) AND revogado IS NULL', (tid,video_sha)).fetchall()
            c.execute('UPDATE thumbnail_selecoes SET revogado=?, motivo=? WHERE (job=? OR video_sha=?) AND revogado IS NULL',
                      (_agora(),'Outra capa foi escolhida para este vídeo.',tid,video_sha))
            sid = secrets.token_hex(6)
            c.execute('INSERT INTO thumbnail_selecoes (id, job, variante, video_sha, thumb_sha, escolha, por, aprovado, criado) VALUES (?,?,?,?,?,?,?,?,?)',
                      (sid,tid,v['id'],video_sha,sha,'manual' if manual else ('automatica' if quem.startswith('agente6') else 'voce'),str(quem)[:60],1,_agora()))
    if repetido:
        return dict(obter(tid), repetido=True)
    for antiga in antigas:
        db.evento('agente6','thumbnail_selecao_revogada','thumbsel:'+antiga['id'],{'motivo':'Outra capa foi escolhida para este vídeo.'})
    _estado(tid, 'pronto', '')
    if j['origem'] == 'corte':
        try:
            import agente as ag
            ag._mudar(lambda e: [x.update(capa={'job': tid, 'variante': v['id'], 'sha': sha[:16]}) for x in e['cortes'] if x['id'] == j['referencia']])
        except Exception:  # noqa: BLE001
            pass
    # evento para o Coordenador (Agente 7) que vem depois: entra entre esta escolha e a liberação ao Agente 2
    db.evento('agente6', 'thumbnail.pacote_pronto', 'thumb:' + tid, {'origem': j['origem'], 'ref': j['referencia'], 'video_sha': video_sha[:16],
                                                                     'thumb_sha': sha[:16], 'escolha': 'manual' if manual else 'diretor'})
    return obter(tid)


def selecionar_melhor(tid: str, quem: str = 'agente6-automatico') -> dict | None:
    """Escolhe a capa aprovada de maior nota (empate: a de número menor). Sem aprovada: None. Não troca uma escolha válida feita por você."""
    j = _job(tid)
    s = selecao_ativa(tid)
    if s and s['escolha'] in ('voce', 'manual') and revalidar(tid):
        return None
    aprovadas = db.todos("SELECT * FROM thumbnail_variantes WHERE job=? AND estado='aprovada' ORDER BY nota DESC, numero, versao DESC", tid)
    for v in aprovadas:
        try:
            r = selecionar(tid, {'variante_id': v['id'], 'versao': v['versao']}, quem)
            db.evento(quem, 'thumbnail_auto_selecao', 'thumb:' + tid, {'variante': v['id'], 'nota': v['nota'], 'video_sha': j['video_sha'][:16]})
            return r
        except ErroThumb as e:
            print('agente6: seleção automática pulou', v['id'], e)
            continue
    return None


def pacote(tid: str) -> dict:
    """Vínculo imutável vídeo + capa + metadados. valido=False se o vídeo ou a capa mudaram."""
    j = _job(tid)
    s = revalidar(tid)
    if not s:
        return {'valido': False, 'motivo': 'Nenhuma capa escolhida (ou a escolha caiu porque algo mudou).'}
    v = db.um('SELECT * FROM thumbnail_variantes WHERE id=?', s['variante'])
    return {'valido': True, 'job': tid, 'origem': j['origem'], 'referencia': j['referencia'], 'video_sha': s['video_sha'], 'thumb_sha': s['thumb_sha'],
            'variante': v['id'], 'numero': v['numero'], 'versao': v['versao'], 'formato': v['formato'], 'escolha': s['escolha'],
            'titulo': j['titulo'], 'texto': json.loads(v['relatorio'] or '{}').get('texto', ''), 'quadro_t': v['quadro_t']}


def capa_para_video(arq: Path) -> dict | None:
    """Usado pelo Agente 2 na hora de postar: a capa aprovada PARA ESTE ARQUIVO, ou None."""
    try:
        import pipeline as pl
        sha = pl.sha_arquivo(arq)
    except Exception:  # noqa: BLE001
        return None
    if not sha:
        return None
    e = db.um('SELECT * FROM thumbnail_embutidos WHERE video_sha=?', sha)
    if e:                         # versão de publicação com a capa embutida: vale a MESMA escolha do vídeo original
        s = db.um('SELECT * FROM thumbnail_selecoes WHERE id=? AND revogado IS NULL AND aprovado=1', e['selecao'])
        v = db.um('SELECT * FROM thumbnail_variantes WHERE id=?', s['variante']) if s else None
        if not s or not v or s['thumb_sha'] != e['thumb_sha'] or _arquivo_sha(v['arquivo']) != s['thumb_sha']:
            return None
        return {'arquivo': Path(v['arquivo']), 'sha': s['thumb_sha'], 'formato': v['formato'], 'tempo_ms': e['tempo_ms'], 'job': s['job'],
                'variante': v['id'], 'selecao': s['id'], 'embutida': True, 'original_sha': e['original_sha']}
    for s in db.todos('SELECT * FROM thumbnail_selecoes WHERE video_sha=? AND revogado IS NULL AND aprovado=1 ORDER BY criado DESC', sha):
        v = db.um('SELECT * FROM thumbnail_variantes WHERE id=?', s['variante'])
        if not v or _arquivo_sha(v['arquivo']) != s['thumb_sha']:
            _revogar(s['id'], 'A capa mudou ou sumiu depois da aprovação.')
            continue
        return {'arquivo': Path(v['arquivo']), 'sha': s['thumb_sha'], 'formato': v['formato'], 'tempo_ms': int((v['quadro_t'] or 0) * 1000),
                'job': s['job'], 'variante': v['id'], 'selecao': s['id'], 'embutida': False, 'original_sha': sha}
    return None


SEG_CAPA_EMBUTIDA = 0.5      # quadro final curto: não mexe no gancho (começo) nem corta o conteúdo


def _sondar_pub(arq: Path) -> dict:
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(arq)],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60, check=True)
    info = json.loads(r.stdout or '{}')
    v = next(s for s in info.get('streams', []) if s.get('codec_type') == 'video')
    a = any(s.get('codec_type') == 'audio' for s in info.get('streams', []))
    num, _, den = str(v.get('r_frame_rate') or '30/1').partition('/')
    try:
        fps = float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        fps = 30.0
    fps = fps if 10 <= fps <= 120 else 30.0
    return {'w': int(v['width']), 'h': int(v['height']), 'fps': round(fps, 3), 'audio': a,
            'dur': float(info.get('format', {}).get('duration') or v.get('duration') or 0)}


def video_com_capa(arq: Path) -> dict | None:
    """Versão de PUBLICAÇÃO para redes que só aceitam um momento do vídeo como capa (TikTok, Instagram).

    A arte escolhida vira um quadro final curto (SEG_CAPA_EMBUTIDA s) e a rede recebe o tempo desse quadro. O arquivo
    derivado fica registrado em thumbnail_embutidos preso à MESMA escolha (vídeo original + capa): não é um vídeo novo
    para o Agente 6 (não gera pedido de capa) nem muda o vídeo aprovado/liberado — o que o A7 liberou continua igual.
    Devolve None quando não há capa escolhida e válida para este arquivo."""
    cap = capa_para_video(arq)
    if not cap:
        return None
    if cap.get('embutida'):
        return {'arquivo': Path(arq), 'tempo_ms': cap['tempo_ms'], 'capa': cap, 'original_sha': cap['original_sha'], 'reaproveitado': True}
    orig = cap['original_sha']
    ja = db.um('SELECT * FROM thumbnail_embutidos WHERE original_sha=? AND thumb_sha=? AND selecao=? ORDER BY criado DESC LIMIT 1',
               orig, cap['sha'], cap['selecao'])
    if ja and Path(ja['arquivo']).exists() and _arquivo_sha(ja['arquivo']) == ja['video_sha']:
        return {'arquivo': Path(ja['arquivo']), 'tempo_ms': ja['tempo_ms'], 'capa': cap, 'original_sha': orig, 'sha': ja['video_sha'], 'reaproveitado': True}
    try:
        m = _sondar_pub(Path(arq))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, OSError, StopIteration):
        return None
    if m['dur'] <= 0:
        return None
    pasta = PASTA / 'embutidos'
    pasta.mkdir(parents=True, exist_ok=True)
    dest = pasta / f'{orig[:16]}_{cap["sha"][:16]}.mp4'
    tmp = pasta / f'{orig[:16]}_{cap["sha"][:16]}.tmp.mp4'
    seg = SEG_CAPA_EMBUTIDA
    w, h, fps = m['w'] - m['w'] % 2, m['h'] - m['h'] % 2, m['fps']
    filtro = (f'[0:v]scale={w}:{h},setsar=1,fps={fps},format=yuv420p[v0];'
              f'[1:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={fps},format=yuv420p[c];'
              '[v0][c]concat=n=2:v=1:a=0[v]')
    cmd = ['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(arq), '-loop', '1', '-t', f'{seg}', '-i', str(cap['arquivo'])]
    mapa = ['-map', '[v]']
    if m['audio']:
        filtro += f';[0:a]apad=pad_dur={seg}[a]'
        mapa += ['-map', '[a]', '-c:a', 'aac', '-b:a', '128k']
    cmd += ['-filter_complex', filtro] + mapa + ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p',
                                                  '-t', f'{m["dur"] + seg:.3f}', '-movflags', '+faststart', str(tmp)]
    try:
        subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=1800, check=True)
        os.replace(tmp, dest)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        tmp.unlink(missing_ok=True)
        print('agente6: não consegui embutir a capa no vídeo:', e)
        return None
    sha = _arquivo_sha(str(dest))
    tempo_ms = int(m['dur'] * 1000 + seg * 500)          # meio do quadro final
    with db.tx() as c:
        c.execute('INSERT OR REPLACE INTO thumbnail_embutidos (video_sha, original_sha, selecao, thumb_sha, tempo_ms, segundos, arquivo, criado) '
                  'VALUES (?,?,?,?,?,?,?,?)', (sha, orig, cap['selecao'], cap['sha'], tempo_ms, seg, str(dest), _agora()))
    db.evento('agente6', 'thumbnail_capa_embutida', 'thumb:' + cap['job'], {'original_sha': orig[:16], 'video_sha': sha[:16], 'tempo_ms': tempo_ms})
    return {'arquivo': dest, 'tempo_ms': tempo_ms, 'capa': cap, 'original_sha': orig, 'sha': sha, 'reaproveitado': False}


def registrar_aplicacao(post: str, rede: str, c: dict, quem: str = 'agente2'):
    """Estado da capa por post e rede, SEPARADO do estado do post (o vídeo pode estar postado e a capa ter falhado)."""
    agora = _agora()
    with db.tx() as cx:
        cx.execute('INSERT INTO thumbnail_aplicacoes (post, rede, estrategia, estado, video_sha, thumb_sha, ref_rede, tentativas, erro, criado, atualizado) '
                   'VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(post, rede) DO UPDATE SET estrategia=excluded.estrategia, estado=excluded.estado, '
                   'thumb_sha=excluded.thumb_sha, ref_rede=COALESCE(NULLIF(excluded.ref_rede, \'\'), ref_rede), tentativas=excluded.tentativas, '
                   'erro=excluded.erro, atualizado=excluded.atualizado',
                   (post, rede, c.get('estrategia') or '', c.get('estado') or '', c.get('original_sha') or '', c.get('sha') or '',
                    c.get('ref_rede') or '', int(c.get('tentativas') or 0), (c.get('detalhe') or '')[:300] if c.get('estado') != 'aplicada' else '',
                    agora, agora))
    db.evento(quem, 'thumbnail_aplicacao', f'post:{post}', {'rede': rede, 'estado': c.get('estado'), 'thumb_sha': (c.get('sha') or '')[:16]})


def marcar_rede_ok(rede: str):
    db.kv_gravar('agente6.rede_ok.' + rede, _agora())


# ---------------------------------------------------------------- consulta
def _variante_publica(v: dict) -> dict:
    import autenticacao as au
    rel = json.loads(v['relatorio'] or '{}')
    rel.pop('mascara', None)
    return {k: v[k] for k in ('id', 'numero', 'versao', 'sha256', 'formato', 'largura', 'altura', 'conceito', 'nota', 'estado', 'criado', 'layout',
                              'quadro_t', 'metodo', 'custo')} | {
        'relatorio': rel, 'url': au.assinar_url(f'/api/v1/thumbnails/midia/{v["id"]}', 3 * 3600),
        'baixar': au.assinar_url(f'/api/v1/thumbnails/midia/{v["id"]}', 3 * 3600) + '&baixar=1'}


def obter(tid: str) -> dict:
    j = _job(tid)
    s = revalidar(tid) if j['estado'] == 'pronto' else selecao_ativa(tid)
    j = _job(tid)
    fj = fila.obter(j['fila_job']) if j['fila_job'] else None
    progresso = None
    if fj:
        rest, est = (None, False)
        try:
            if fj['status'] in fila.ATIVOS:
                rest, est = fila.restante(fj)
        except Exception:  # noqa: BLE001
            pass
        progresso = {'status': fj['status'], 'pct': fj['progresso'], 'etapa': fj['etapa'], 'restante_s': rest, 'estimado': est,
                     'criado': fj['criado'], 'iniciado': fj['iniciado'], 'terminado': fj['terminado'], 'decorrido': fj['decorrido'],
                     'tentativas': fj['tentativas']}
    vs = db.todos('SELECT * FROM thumbnail_variantes WHERE job=? ORDER BY numero, versao DESC', tid)
    return {**{k: j[k] for k in ('id', 'origem', 'referencia', 'video_sha', 'estado', 'criado', 'atualizado', 'erro', 'titulo', 'metodo', 'correcoes', 'custo', 'por')},
            'rejeicao_habilitada': rejeicao_ativa(), 'config': j['config'], 'progresso': progresso, 'selecao': s, 'variantes': [_variante_publica(v) for v in vs]}


def listar(estado: str = '', limite: int = 50) -> dict:
    limite = max(1, min(200, int(limite or 50)))
    if estado:
        js = db.todos('SELECT id FROM thumbnail_jobs WHERE estado=? ORDER BY criado DESC LIMIT ?', estado, limite)
    else:
        js = db.todos('SELECT id FROM thumbnail_jobs ORDER BY criado DESC LIMIT ?', limite)
    return {'jobs': [obter(x['id']) for x in js]}


def midia(variante_id: str) -> tuple[Path, str]:
    if not re.fullmatch(r'[a-f0-9]{12}', str(variante_id or '')):
        raise ErroThumb(400, 'Capa inválida.')
    v = db.um('SELECT * FROM thumbnail_variantes WHERE id=?', variante_id)
    if not v:
        raise ErroThumb(404, 'Capa não encontrada.')
    arq = Path(v['arquivo'])
    try:
        real = arq.resolve(strict=True)
    except OSError:
        raise ErroThumb(404, 'O arquivo da capa sumiu.')
    if PASTA.resolve() not in real.parents:
        raise ErroThumb(403, 'Arquivo fora da pasta das capas.')
    return real, f'capa-{v["numero"]}-v{v["versao"]}.jpg'


def desempenho() -> dict:
    """Só o que foi medido: tempos da fila, tentativas, correções, custo e quais capas você escolheu. Sem CTR inventado."""
    js = db.todos('SELECT t.*, j.criado AS f_criado, j.iniciado AS f_iniciado, j.terminado AS f_terminado, j.decorrido AS f_decorrido, '
                  'j.tentativas AS f_tentativas FROM thumbnail_jobs t LEFT JOIN jobs j ON j.id=t.fila_job ORDER BY t.criado DESC LIMIT 200')
    feitos = [x for x in js if x['f_terminado']]
    def media(lst):
        return round(sum(lst) / len(lst), 1) if lst else None
    escolhas = db.todos('SELECT s.escolha, v.numero, v.layout FROM thumbnail_selecoes s JOIN thumbnail_variantes v ON v.id=s.variante')
    por_layout: dict = {}
    for e in escolhas:
        por_layout[e['layout'] or '?'] = por_layout.get(e['layout'] or '?', 0) + 1
    media_job, tem = fila.media('job:agente6.thumbnail')
    return {'pedidos': len(js), 'por_estado': {e: sum(1 for x in js if x['estado'] == e) for e in ESTADOS if any(x['estado'] == e for x in js)},
            'tempo_ativo_medio_s': media([x['f_decorrido'] for x in feitos if x['f_decorrido']]),
            'espera_fila_media_s': media([x['f_iniciado'] - x['f_criado'] for x in feitos if x['f_iniciado'] and x['f_criado']]),
            'tempo_total_medio_s': media([x['f_terminado'] - x['f_criado'] for x in feitos if x['f_terminado'] and x['f_criado']]),
            'previsao_por_pedido_s': round(media_job) if tem else None,
            'falhas': sum(1 for x in js if x['estado'] == 'falhou'), 'tentativas_fila': sum((x['f_tentativas'] or 0) for x in js),
            'correcoes_criativas': sum(x['correcoes'] or 0 for x in js), 'custo_estimado_reais': round(sum(x['custo'] or 0 for x in js), 2),
            'escolhas': {'total': len(escolhas), 'por_layout': por_layout, 'manuais': sum(1 for e in escolhas if e['escolha'] == 'manual')},
            'aviso': 'Tempos medidos neste servidor. Não há dado de cliques (CTR): as redes não devolvem isso por aqui.'}


# ---------------------------------------------------------------- automático
def _sha_atual(origem: str, ref: str) -> str:
    try:
        import pipeline as pl
        return pl.sha_arquivo(resolver(origem, ref)['arquivo']) or ''
    except (ErroThumb, Exception):  # noqa: BLE001 - vídeo sumiu: nada a recuperar
        return ''


def _recuperacoes(origem: str, ref: str, sha: str) -> int:
    r = db.um("SELECT COUNT(*) n FROM thumbnail_jobs WHERE origem=? AND referencia=? AND video_sha=? AND por='agente6-recuperacao'", origem, ref, sha)
    return int(r['n'] if r else 0)


def diagnosticar(f: dict, cfg: dict | None = None) -> dict:
    """O que o Agente 6 precisa fazer por este vídeo agora. acao: nada | criar | selecionar | refazer_pedido | excecao."""
    cfg = cfg or config()
    origem, ref = f['origem'], f['referencia']
    j = _ultimo_job(origem, ref)
    sha = _sha_atual(origem, ref)
    if not sha:
        return {'acao': 'nada', 'motivo': 'Vídeo não encontrado no servidor.'}
    if not j:
        return {'acao': 'criar', 'motivo': 'Vídeo sem pedido de capa.', 'sha': sha}
    base = {'job': j['id'], 'estado': j['estado'], 'sha': sha}
    if j['video_sha'] != sha:
        atual = db.um('SELECT * FROM thumbnail_jobs WHERE origem=? AND referencia=? AND video_sha=? ORDER BY criado DESC LIMIT 1', origem, ref, sha)
        if not atual:
            return {**base, 'acao': 'criar', 'motivo': 'O vídeo mudou: a capa precisa ser da versão nova.', 'recuperacao': True}
        j = atual
        base = {'job': j['id'], 'estado': j['estado'], 'sha': sha}
    est = j['estado']
    if est in ('na_fila', 'analisando', 'criando', 'validando', 'aguardando_video'):
        return {**base, 'acao': 'nada', 'motivo': 'Pedido em andamento.'}
    if est == 'cancelado' and (j.get('erro') or '').startswith('Cancelado por você'):
        return {**base, 'acao': 'nada', 'motivo': 'Você cancelou este pedido.'}
    if est in ('pronto', 'aguardando_escolha'):
        s = revalidar(j['id']) if est == 'pronto' else selecao_ativa(j['id'])
        if s and s.get('video_sha') == sha:
            return {**base, 'acao': 'nada', 'motivo': 'Capa escolhida e válida.'}
        tem_aprovada = db.um("SELECT 1 FROM thumbnail_variantes WHERE job=? AND estado='aprovada'", j['id'])
        if tem_aprovada:
            return {**base, 'acao': 'selecionar' if cfg['modo'] == 'automatico' else 'excecao',
                    'motivo': 'Há capa aprovada sem escolha.' if cfg['modo'] == 'automatico' else 'Capas prontas esperando a sua escolha (modo supervisionado).'}
    # falhou, cancelado pelo sistema, revisão manual ou sem nenhuma aprovada: pedido novo, até o limite
    if _recuperacoes(origem, ref, sha) >= cfg['max_recuperacoes']:
        return {**base, 'acao': 'excecao', 'motivo': f'Nenhuma capa válida depois de {cfg["max_recuperacoes"]} pedidos automáticos: precisa de você.'}
    return {**base, 'acao': 'refazer_pedido', 'motivo': {'falhou': 'O pedido falhou.', 'revisao_manual': 'Nenhuma capa passou no diretor.',
                                                        'cancelado': 'O pedido foi cancelado pelo sistema.'}.get(est, 'Sem capa aprovada.')}


def _candidatas() -> list:
    """Vídeos que precisam de capa: cortes prontos/agendados e vídeos finais do Agente 3, os que vão ao ar mais cedo primeiro."""
    import agente as ag
    quando = {c['id']: c.get('quando') or 0 for c in ag.estado()['cortes']}
    cand = [f for f in fontes(limite=200) if
            ((f['origem'] == 'corte' and f['status'] in ('pronto', 'agendado')) or (f['origem'] == 'render' and f['status'] in ('ready_for_review', 'approved', 'scheduled')))]
    cand.sort(key=lambda f: (quando.get(f['referencia']) or float('inf')) if f['origem'] == 'corte' else float('inf'))
    return cand


def recuperar(limite_pesados: int = 2, simular: bool = False) -> dict:
    """Uma passada do Agente 6 autônomo: cria o que falta, escolhe a melhor aprovada e refaz pedidos que não deram capa.
    Pedidos novos são pesados (FFmpeg + Pillow), então no máximo `limite_pesados` por passada."""
    cfg = config()
    out = {'criados': [], 'selecionados': [], 'excecoes': [], 'simulado': simular}
    if cfg['modo'] == 'manual':
        return out
    novos = 0
    for f in _candidatas():
        d = diagnosticar(f, cfg)
        item = {'origem': f['origem'], 'referencia': f['referencia'], 'titulo': f['titulo'], **{k: d.get(k) for k in ('acao', 'motivo', 'job')}}
        if d['acao'] == 'selecionar':
            if not simular:
                r = selecionar_melhor(d['job'], 'agente6-automatico')
                if not r:
                    continue
            out['selecionados'].append(item)
        elif d['acao'] in ('criar', 'refazer_pedido'):
            if not cfg['criar_sozinho'] or novos >= limite_pesados:
                continue
            if d['acao'] == 'refazer_pedido' or d.get('recuperacao'):
                if not cfg['recuperacao_automatica']:
                    continue
                quem = 'agente6-recuperacao'
                chave = f'recuperar:{f["referencia"]}:{d["sha"][:16]}:{_recuperacoes(f["origem"], f["referencia"], d["sha"])}'
                # a cada nova tentativa muda o método, para não repetir a mesma composição que não passou
                metodo = ('inteligente', 'editorial', 'frame')[_recuperacoes(f['origem'], f['referencia'], d['sha']) % 3]
            else:
                quem, chave, metodo = 'agente6-automatico', '', (cfg['metodo_padrao'] if cfg['metodo_padrao'] != 'ia' else 'inteligente')
            if not simular:
                try:
                    j = criar({'origem': f['origem'], 'referencia': f['referencia'], 'metodo': metodo, 'variantes': cfg['variantes_padrao'],
                               'formato': 'auto', 'texto_modo': 'auto', **({'chave_idempotencia': chave} if chave else {})}, quem)
                    item['job'] = j['id']
                except ErroThumb as e:
                    item['motivo'] = str(e)
                    out['excecoes'].append(item)
                    continue
            novos += 1
            out['criados'].append(item)
        elif d['acao'] == 'excecao':
            out['excecoes'].append(item)
    return out


def varrer() -> int:
    """Cria capas sozinho (modos automático e supervisionado, com "criar sozinho" ligado), recupera pedidos que não deram capa e,
    no automático, escolhe a melhor aprovada. Até 2 pedidos novos por vez, primeiro os vídeos que vão ao ar mais cedo."""
    cfg = config()
    if cfg['modo'] == 'manual' or not cfg['criar_sozinho']:
        return 0
    if not PIL_OK:
        if not db.kv('agente6.aviso_sem_pil'):
            db.kv_gravar('agente6.aviso_sem_pil', _agora())
            try:
                import agente as ag
                ag.avisar('falha', 'Agente 6 parado: falta o Pillow', SEM_PIL + '\n\nNo Termux: pkg install python-pillow (ou rode de novo: bash iniciar-termux.sh link).')
            except Exception as e:  # noqa: BLE001
                print('agente6: aviso', e)
        return 0
    r = recuperar()
    return len(r['criados']) + len(r['selecionados'])


def _vigia():
    while True:
        time.sleep(float(os.getenv('AGENTE6_INTERVALO', '120')))
        try:
            varrer()
        except Exception as e:  # noqa: BLE001
            print('agente6: varredura:', e)


_iniciado = False


def iniciar():
    global _iniciado
    fila.registrar('agente6.thumbnail', job_thumbnail, 'pesado')
    if _iniciado:
        return
    _iniciado = True
    fila.AO_FALHAR.append(_ao_falhar)
    if not os.getenv('AGENTE6_SEM_VIGIA'):
        threading.Thread(target=_vigia, daemon=True, name='agente6').start()
