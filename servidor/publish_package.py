"""Pacote de publicação: tudo que vai junto com o vídeo, conferido e aprovado ANTES de publicar (cortes do Agente 1, manuais e de gameplay).

Inclui o MP4 conferido, 3 sugestões de capa (quadros reais do vídeo), títulos e descrição, relatório de conformidade por rede,
texto do comentário fixado (para copiar: não é postado sozinho) e os créditos/direitos. A descrição segue o formato fixo do Agente 3
(título, hashtags, ". . ." e "Link original do vídeo []") e NADA é acrescentado depois dessa linha.
A aprovação fica presa a um hash do arquivo + descrição + capa: mudar o texto ou a capa pede aprovação de novo e revalida as redes,
mas NÃO refaz o vídeo. Quem decide o que sai continua sendo você.
Os limites de cada rede abaixo são os do EstúdioClip (configuração própria): confira nas regras atuais de cada rede antes de confiar.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

import descricao as ds
import postagem as pg
import renderizador as rd

PASTA = pg.DADOS / 'pacotes'
# limites usados pelo EstúdioClip. duracao_max em segundos, tamanho em MB. Conservadores de propósito.
REDES = {
    'youtube': {'nome': 'YouTube Shorts', 'duracao_max': 180, 'titulo_max': 100, 'desc_max': 5000, 'hashtags_max': 15, 'tam_max_mb': 500, 'manual': False},
    'instagram': {'nome': 'Instagram Reels', 'duracao_max': 90, 'titulo_max': 0, 'desc_max': 2200, 'hashtags_max': 30, 'tam_max_mb': 300, 'manual': False},
    'tiktok': {'nome': 'TikTok', 'duracao_max': 600, 'titulo_max': 0, 'desc_max': 2200, 'hashtags_max': 30, 'tam_max_mb': 287, 'manual': False},
    'facebook': {'nome': 'Facebook Reels', 'duracao_max': 90, 'titulo_max': 0, 'desc_max': 2200, 'hashtags_max': 30, 'tam_max_mb': 300, 'manual': False},
    'kwai': {'nome': 'Kwai', 'duracao_max': 300, 'titulo_max': 0, 'desc_max': 2200, 'hashtags_max': 30, 'tam_max_mb': 300, 'manual': True},
}
PROVEDOR = {'youtube': 'google', 'instagram': 'meta', 'facebook': 'meta', 'tiktok': 'tiktok'}
AVISO_LIMITES = 'Limites configurados no EstúdioClip; as redes mudam as regras, confira nas regras atuais de cada uma.'


_FIM = re.compile(r'\.\n\.\n\.\nLink original do vídeo \[[^\]\n]*\]\Z')


def termina_no_rodape(t: str) -> bool:
    """A descrição TERMINA na linha do link original (nada depois dela)."""
    return bool(_FIM.search(str(t or '').rstrip()))


class ErroPacote(Exception):
    pass


def _arq(pid: str) -> Path:
    return PASTA / f'{re.sub(r"[^a-z0-9]", "", pid)}.json'


def ler(corte_id: str) -> dict | None:
    return pg._ler(_arq(corte_id), None)


def _gravar(p: dict):
    PASTA.mkdir(parents=True, exist_ok=True)
    with pg.LOCK:
        pg._gravar(_arq(p['corte']), p)


def hash_do_pacote(p: dict) -> str:
    return hashlib.sha256(json.dumps([p['video_hash'], p['titulo'], p['descricao'], p['capa_escolhida'], p['capas'][p['capa_escolhida']]['sha'] if p['capas'] else ''],
                                     ensure_ascii=False).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- vídeo e capas
def fatos_do_video(arq: Path) -> dict:
    info = rd.sonda(arq)
    v = next((x for x in info.get('streams', []) if x.get('codec_type') == 'video'), {})
    a = next((x for x in info.get('streams', []) if x.get('codec_type') == 'audio'), None)
    return {'largura': int(v.get('width') or 0), 'altura': int(v.get('height') or 0), 'codec_video': v.get('codec_name', ''), 'codec_audio': (a or {}).get('codec_name', ''),
            'tem_audio': bool(a), 'duracao': round(rd.duracao(arq), 2), 'tamanho_mb': round(arq.stat().st_size / 1048576, 2), 'fps': v.get('avg_frame_rate', '')}


def sugerir_capas(arq: Path, dur: float, pasta: Path, n: int = 3) -> list:
    """Tira 6 quadros reais e fica com os 3 de mais detalhe (maior JPEG), afastados entre si. É escolha técnica: quem decide a capa é você."""
    pasta.mkdir(parents=True, exist_ok=True)
    cand = []
    for k, f in enumerate((0.08, 0.2, 0.35, 0.5, 0.65, 0.8)):
        t = max(0.2, min(dur - 0.3, dur * f))
        q = pasta / f'cand-{k}.jpg'
        subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-ss', f'{t:.2f}', '-i', str(arq), '-frames:v', '1', '-vf', 'scale=1080:-2', '-q:v', '3', str(q)],
                       stdin=subprocess.DEVNULL, capture_output=True)
        if q.exists() and q.stat().st_size > 1500:
            cand.append({'t': round(t, 2), 'arq': q, 'det': q.stat().st_size})
    cand.sort(key=lambda c: -c['det'])
    escolhidas = []
    for c in cand:
        if all(abs(c['t'] - e['t']) > dur * 0.12 for e in escolhidas):
            escolhidas.append(c)
        if len(escolhidas) == n:
            break
    out = []
    for i, c in enumerate(escolhidas):
        dest = pasta / f'capa-{i + 1}.jpg'
        c['arq'].replace(dest)
        sha = hashlib.sha256(dest.read_bytes()).hexdigest()[:16]
        out.append({'arquivo': str(dest), 't': c['t'], 'bytes': dest.stat().st_size, 'sha': sha})
    for c in cand:
        c['arq'].unlink(missing_ok=True)
    return out


# ---------------------------------------------------------------- conformidade por rede
def conformidade(p: dict, fatos: dict) -> dict:
    """Uma linha por rede, com cada verificação (ok / aviso / erro / não verificado) e o que fazer. Erro bloqueia a aprovação dessa rede."""
    contas = pg.status_contas()
    tags = ds.hashtags(re.findall(r'#\w+', p['descricao']))
    out = {}
    for rede in p['redes']:
        r = REDES.get(rede)
        if not r:
            continue
        itens = []

        def add(nome, estado, detalhe, corrigir=''):
            itens.append({'item': nome, 'estado': estado, 'detalhe': detalhe, 'corrigir': corrigir})
        razao = fatos['largura'] / max(1, fatos['altura'])
        add('Formato vertical 9:16', 'ok' if abs(razao - 9 / 16) < 0.02 else 'erro', f'{fatos["largura"]}x{fatos["altura"]}', 'Refaça o corte em 9:16 (vertical).')
        add('Resolução mínima', 'ok' if fatos['largura'] >= 540 and fatos['altura'] >= 960 else 'aviso', f'{fatos["largura"]}x{fatos["altura"]}', 'Use pelo menos 540x960.')
        add('Codec', 'ok' if fatos['codec_video'] == 'h264' and fatos['codec_audio'] in ('aac', '') else 'aviso', f'vídeo {fatos["codec_video"]}, áudio {fatos["codec_audio"] or "sem"}', 'O ideal é H.264 com áudio AAC.')
        add('Duração', 'ok' if fatos['duracao'] <= r['duracao_max'] else 'erro', f'{fatos["duracao"]} s (limite configurado {r["duracao_max"]} s)', 'Corte um trecho mais curto.')
        add('Tamanho do arquivo', 'ok' if fatos['tamanho_mb'] <= r['tam_max_mb'] else 'erro', f'{fatos["tamanho_mb"]} MB (limite configurado {r["tam_max_mb"]} MB)', 'Exporte em qualidade mais leve.')
        add('Áudio', 'ok' if fatos['tem_audio'] else 'aviso', 'tem áudio' if fatos['tem_audio'] else 'sem áudio', 'Vídeo sem som costuma render menos; confira se é isso mesmo.')
        if r['titulo_max']:
            add('Título', 'ok' if len(p['titulo']) <= r['titulo_max'] else 'erro', f'{len(p["titulo"])} de {r["titulo_max"]} caracteres', 'Encurte o título.')
        add('Descrição', 'ok' if len(p['descricao']) <= r['desc_max'] else 'erro', f'{len(p["descricao"])} de {r["desc_max"]} caracteres', 'Encurte a descrição.')
        add('Hashtags', 'ok' if len(tags) <= r['hashtags_max'] else 'aviso', f'{len(tags)} de {r["hashtags_max"]}', 'Tire algumas hashtags.')
        add('Formato da descrição', 'ok' if termina_no_rodape(p['descricao']) else 'erro', 'termina com ". . ." e "Link original do vídeo []"' if termina_no_rodape(p['descricao']) else 'o texto não termina no rodapé fixo',
            'Restaure o formato padrão da descrição.')
        add('Música e legendas da rede', 'nao_verificado', 'o EstúdioClip não consegue ver a música nem as legendas automáticas da rede', 'Confira no aplicativo da rede.')
        add('Áreas seguras (botões da rede)', 'nao_verificado', 'não é checado automaticamente', 'Deixe o texto importante longe das bordas (principalmente embaixo).')
        if r['manual']:
            add('Conta conectada', 'aviso', 'esta rede não aceita postagem automática', 'Use o arquivo e o texto copiável e poste à mão no aplicativo.')
        else:
            prov = contas.get(PROVEDOR[rede], {})
            add('Conta conectada', 'ok' if prov.get('conectado') else 'erro', (prov.get('nome') or 'conectada') if prov.get('conectado') else 'conta não conectada/autorizada em Postagem',
                'Conecte a conta em Postagem.')
        erros = [i for i in itens if i['estado'] == 'erro']
        out[rede] = {'nome': r['nome'], 'manual': r['manual'], 'itens': itens, 'pode_aprovar': not erros, 'erros': [f'{i["item"]}: {i["detalhe"]}. {i["corrigir"]}' for i in erros]}
    return out


# ---------------------------------------------------------------- montar, editar, aprovar
def _link_original(c: dict) -> str:
    if c.get('origem') and re.fullmatch(r'[\w-]{11}', str(c['origem'])):
        return ds.link_valido('https://www.youtube.com/watch?v=' + c['origem'])
    return ds.link_valido((c.get('gameplay') or {}).get('fonte', ''))


def _sugestoes_titulo(c: dict) -> list:
    base = ds.titulo_limpo(c.get('titulo', ''))
    out = [base]
    g = ds.titulo_limpo(c.get('gancho', ''))
    if g and g.casefold() != base.casefold():
        out.append(g)
    curto = base if len(base) <= 60 else base[:57].rsplit(' ', 1)[0] + '…'
    if curto.casefold() not in {x.casefold() for x in out}:
        out.append(curto)
    return [x for x in out if x][:3]


def montar(c: dict, redes_padrao: list | None = None, redes: list | None = None) -> dict:
    """Cria (ou refaz) o pacote de um corte. Refazer apaga a aprovação, porque o conteúdo pode ter mudado."""
    arq = pg.video_path(c['video'])
    if not arq.exists():
        raise ErroPacote('O vídeo deste corte não está mais no servidor.')
    fatos = fatos_do_video(arq)
    redes = [r for r in (redes or c.get('redes') or redes_padrao or []) if r in REDES] or ['youtube']
    tags = ds.hashtags(c.get('hashtags') or [])
    link = _link_original(c)
    titulo = ds.titulo_limpo(c.get('titulo', '')) or 'Corte'
    antigo = ler(c['id']) or {}
    capas = sugerir_capas(arq, fatos['duracao'], PASTA / c['id'])
    p = {'corte': c['id'], 'versao': antigo.get('versao', 0) + 1, 'criado': time.time(), 'video': c['video'], 'video_hash': c.get('hash', ''), 'fatos': fatos,
         'titulo': titulo, 'titulos_sugeridos': _sugestoes_titulo(c), 'descricao': ds.compor(titulo, tags, link), 'descricao_editada': False,
         'link_original': link, 'capas': capas, 'capa_escolhida': 0, 'redes': redes, 'direitos': c.get('direitos') or {}, 'fonte': {'link': link, 'canal': c.get('canal_nome', '')},
         'comentario_fixado': {'texto': _comentario(c, link), 'automatico': False, 'aviso': 'O EstúdioClip não consegue fixar comentários sozinho: copie e fixe no aplicativo da rede.'},
         'aprovado': None, 'aviso_limites': AVISO_LIMITES}
    p['conformidade'] = conformidade(p, fatos)
    p['hash'] = hash_do_pacote(p)
    _gravar(p)
    return resumo(p)


def _comentario(c: dict, link: str) -> str:
    partes = []
    if c.get('canal_nome') and c['canal_nome'] != 'link enviado por você':
        partes.append(f'Vídeo original do canal {c["canal_nome"]}.')
    if link:
        partes.append(f'Link original: {link}')
    return ' '.join(partes) or 'Se gostou, siga o canal.'


def resumo(p: dict) -> dict:
    return {**{k: v for k, v in p.items() if k != 'capas'}, 'capas': [{k: v for k, v in c.items() if k != 'arquivo'} | {'indice': i} for i, c in enumerate(p['capas'])],
            'aprovado_agora': bool(p['aprovado'] and p['aprovado']['hash'] == p['hash']),
            'tudo_ok': all(r['pode_aprovar'] for r in p['conformidade'].values()) if p['conformidade'] else False}


def obter(corte_id: str) -> dict:
    p = ler(corte_id)
    if not p:
        raise ErroPacote('Este corte ainda não tem pacote de publicação.')
    return resumo(p)


def editar(corte_id: str, d: dict) -> dict:
    """Muda descrição, título, capa ou redes. Revalida as redes (sem refazer o vídeo) e derruba a aprovação."""
    p = ler(corte_id)
    if not p:
        raise ErroPacote('Este corte ainda não tem pacote de publicação.')
    if 'titulo' in d:
        p['titulo'] = ds.titulo_limpo(d['titulo']) or p['titulo']
        if not p['descricao_editada']:
            p['descricao'] = ds.compor(p['titulo'], re.findall(r'#\w+', p['descricao']), p['link_original'])
    if 'descricao' in d:
        txt = str(d['descricao']).strip()
        if not termina_no_rodape(txt):
            raise ErroPacote('A descrição precisa terminar com os três pontos e a linha "Link original do vídeo []". Nada pode vir depois dela.')
        p['descricao'], p['descricao_editada'] = txt, True
    if 'capa' in d:
        i = int(d['capa'])
        if not 0 <= i < len(p['capas']):
            raise ErroPacote('Capa inexistente.')
        p['capa_escolhida'] = i
    if 'redes' in d:
        p['redes'] = [r for r in d['redes'] if r in REDES] or p['redes']
    p['conformidade'] = conformidade(p, p['fatos'])           # só revalida; o vídeo NÃO é refeito
    novo = hash_do_pacote(p)
    if novo != p['hash']:
        p['hash'], p['aprovado'] = novo, None
    _gravar(p)
    return resumo(p)


def aprovar(corte_id: str, por: str) -> dict:
    p = ler(corte_id)
    if not p:
        raise ErroPacote('Este corte ainda não tem pacote de publicação.')
    p['conformidade'] = conformidade(p, p['fatos'])
    erros = [f'{r["nome"]}: {e}' for r in p['conformidade'].values() for e in r['erros']]
    if erros:
        raise ErroPacote('Ainda há erros a corrigir: ' + ' | '.join(erros[:4]))
    p['hash'] = hash_do_pacote(p)
    p['aprovado'] = {'hash': p['hash'], 't': time.time(), 'por': por[:60], 'video_hash': p['video_hash']}
    _gravar(p)
    return resumo(p)


def capa_arquivo(corte_id: str, indice: int) -> Path:
    p = ler(corte_id)
    if not p or not 0 <= indice < len(p['capas']):
        raise ErroPacote('Capa não encontrada.')
    return Path(p['capas'][indice]['arquivo'])


def situacao(c: dict) -> dict | None:
    """Para o agendamento: None se o corte não tem pacote (fluxo antigo); senão, se está aprovado AGORA e o texto aprovado."""
    p = ler(c['id'])
    if not p:
        return None
    ok = bool(p['aprovado'] and p['aprovado']['hash'] == hash_do_pacote(p) and p['video_hash'] == c.get('hash', ''))
    return {'aprovado': ok, 'titulo': p['titulo'], 'descricao': p['descricao'], 'redes': p['redes'], 'hash': p['hash']}
