"""Agente 3 — Produtor de vídeos ORIGINAIS, rodando no servidor (Termux), com o navegador fechado.

Linha de produção (cada etapa fica salva no projeto; se o servidor reiniciar, continua de onde parou):
  pauta (opcional) -> roteiro e storyboard -> [aprovação do roteiro, no modo assistido]
  -> narração por cena -> imagens (opcional) -> render de cada cena -> vídeo final -> conferência
  -> e-mail com código de aprovação -> REVISÃO HUMANA.

Nada é publicado aqui. Só o serviço de aprovação (aprovacoes.py), depois de uma aprovação válida da
versão final, entrega o vídeo ao Agente 2.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import time
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

import agente as ag
import banco as db
import estilos_codigo as ec
import fila
import imagens as im
import projetos as pj
import renderizador as rd

MODELO_TTS = os.getenv('MODELO_TTS', 'gemini-2.5-flash-preview-tts')
MODELO_IMAGEM = os.getenv('MODELO_IMAGEM', 'gemini-2.5-flash-image')
VOZES = ['Puck', 'Kore', 'Charon', 'Fenrir', 'Aoede', 'Leda', 'Orus', 'Zephyr']
TIPOS = ['curiosidades', 'história narrada', 'documentário', 'games', 'explicativo', 'tutorial', 'quiz', 'motivacional',
         'animação com personagens', 'motion graphics', 'outro']
RITMOS = {'calmo': 0.97, 'normal': 1.0, 'agil': 1.06, 'rapido': 1.12}      # velocidade da narração (sem mudar o tom da voz)
# Como o narrador deve falar em cada tipo de vídeo (instrução de estilo do Gemini TTS).
TONS = {'curiosidades': 'animado e curioso, como quem conta uma descoberta', 'história narrada': 'envolvente, de contador de histórias, com suspense leve',
        'documentário': 'firme e claro, de documentário', 'games': 'empolgado e rápido, de quem fala com amigos', 'explicativo': 'claro e simpático, de professor que explica fácil',
        'tutorial': 'direto e calmo, passo a passo', 'quiz': 'animado, de apresentador de jogo', 'motivacional': 'confiante e inspirador, com pausas curtas',
        'animação com personagens': 'expressivo e divertido', 'motion graphics': 'claro, moderno e direto', 'outro': 'natural e animado'}
ESTADOS = {
    'draft': 'Rascunho', 'researching': 'Pesquisando', 'script_ready': 'Roteiro pronto', 'storyboard_ready': 'Roteiro pronto para conferir',
    'waiting_brief_approval': 'Esperando você aprovar o roteiro', 'scheduled': 'Agendado', 'queued': 'Na fila',
    'generating_assets': 'Gerando imagens', 'narrating': 'Narrando', 'assembling': 'Montando', 'rendering': 'Renderizando',
    'validating': 'Conferindo o vídeo', 'ready_for_review': 'Pronto para revisão', 'approved': 'Aprovado',
    'queued_to_publish': 'Na fila de postagem', 'posted': 'Publicado', 'paused': 'Pausado', 'retry_wait': 'Esperando nova tentativa',
    'failed': 'Falhou', 'cancelled': 'Cancelado', 'changes_requested': 'Correção pedida', 'rejected': 'Rejeitado',
}
BRIEFING_PADRAO = {
    'tema': '', 'nicho': 'Curiosidades', 'publico': '', 'objetivo': '', 'idioma': 'pt-BR', 'tipo': 'curiosidades',
    'descricao': '', 'origem': 'manual', 'referencias': '', 'duracao_alvo': 45, 'formato': '9:16', 'cenas_qtd': 6,
    'estilo': 'vetor_chapado', 'paleta': [], 'voz': 'Puck', 'ritmo': 'agil', 'trilha': '', 'imagens': 'nenhuma',
    'modo_aprovacao': 'assistido', 'prioridade': 0, 'orcamento_max': 2.0, 'max_tentativas': 3,
    'destinos': {'redes': [], 'quando': 'proximo', 'titulo': '', 'legenda': ''}, 'temas': [],
}


class ErroProdutor(Exception):
    def __init__(self, msg: str, definitivo: bool = False):
        super().__init__(msg)
        self.definitivo = definitivo


def requisitos() -> dict:
    """O que já está pronto no servidor para o Agente 3 trabalhar (o site mostra o que falta e onde resolver)."""
    seg, em = ag.segredos(), ag.config().get('email', {})
    return {'ffmpeg': rd.tem_ffmpeg(), 'gemini': bool(seg.get('gemini') or seg.get('gemini_pago')), 'email': bool(em.get('para') and seg.get('email_senha')),
            'pexels': bool(seg.get('pexels')), 'numpy': ec.motor3d.disponivel()}


def limpar_briefing(d: dict) -> dict:
    b = dict(BRIEFING_PADRAO)
    for k in ('tema', 'nicho', 'publico', 'objetivo', 'idioma', 'descricao', 'origem', 'referencias'):
        if d.get(k) is not None:
            b[k] = str(d[k])[:1500 if k in ('descricao', 'referencias') else 200].strip()
    b['tipo'] = d.get('tipo') if d.get('tipo') in TIPOS else b['tipo']
    b['formato'] = d.get('formato') if d.get('formato') in ec.FORMATOS else '9:16'
    try:
        b['duracao_alvo'] = max(10, min(int(float(d.get('duracao_alvo') or 45)), 600))
        b['cenas_qtd'] = max(2, min(int(d.get('cenas_qtd') or 6), 30))
        b['prioridade'] = max(-5, min(int(d.get('prioridade') or 0), 5))
        b['orcamento_max'] = max(0.0, min(float(d.get('orcamento_max') if d.get('orcamento_max') is not None else 2), 100.0))
        b['max_tentativas'] = max(1, min(int(d.get('max_tentativas') or 3), 6))
    except (TypeError, ValueError):
        raise ErroProdutor('Números do briefing inválidos.')
    b['estilo'] = d.get('estilo') if d.get('estilo') in [e[0] for e in ec.ESTILOS] else 'vetor_chapado'
    b['voz'] = d.get('voz') if d.get('voz') in VOZES + ['nenhuma'] else 'Puck'
    b['ritmo'] = d.get('ritmo') if d.get('ritmo') in RITMOS else 'agil'
    b['imagens'] = d.get('imagens') if d.get('imagens') in ('nenhuma', 'gemini', 'busca') else 'nenhuma'
    b['modo_aprovacao'] = d.get('modo_aprovacao') if d.get('modo_aprovacao') in ('assistido', 'supervisionado') else 'assistido'
    b['trilha'] = re.sub(r'[^a-f0-9]', '', str(d.get('trilha') or ''))[:16]
    b['paleta'] = [c for c in (d.get('paleta') or []) if re.fullmatch(r'#[0-9a-fA-F]{6}', str(c))][:3]
    b['temas'] = [str(t)[:200] for t in (d.get('temas') or []) if str(t).strip()][:30]
    de = d.get('destinos') if isinstance(d.get('destinos'), dict) else {}
    b['destinos'] = {'redes': [r for r in de.get('redes', []) if r in ag.REDES], 'quando': de.get('quando') if de.get('quando') in ('proximo', 'agora', 'data') else 'proximo',
                     'data': float(de.get('data') or 0), 'titulo': str(de.get('titulo') or '')[:100], 'legenda': str(de.get('legenda') or '')[:2200]}
    if not ec.utilizavel(b['estilo'], b['imagens'] == 'gemini'):
        raise ErroProdutor(f'O estilo "{ec.estilo(b["estilo"])["nome"]}" ainda não roda no servidor ({ec.estilo(b["estilo"])["descricao"]}). Escolha outro.', True)
    return b


# ---------------------------------------------------------------- IA: pautas e roteiro
def _gasto_job(job_id: str) -> float:
    r = db.um('SELECT COALESCE(SUM(estimado),0) AS s FROM custos WHERE job=?', job_id)
    return float(r['s'] if r else 0)


def _custo(job_id: str, provedor: str, modelo: str, etapa: str, reais: float):
    db.executar('INSERT INTO custos (job, provedor, modelo, etapa, estimado, real, moeda, t) VALUES (?,?,?,?,?,NULL,?,?)',
                job_id, provedor, modelo, etapa, round(reais, 4), 'BRL', time.time())


def _conferir_orcamento(job_id: str, b: dict, previsto: float = 0):
    if b.get('orcamento_max') and _gasto_job(job_id) + previsto > b['orcamento_max']:
        raise ErroProdutor(f'O limite de gasto deste vídeo (R$ {b["orcamento_max"]:.2f}) seria passado. Aumente o limite no briefing ou reduza cenas/imagens.', True)


def ideias(d: dict) -> dict:
    """De 3 a 10 pautas ORIGINAIS a partir de um nicho/tema. Títulos em alta no YouTube (se houver chave) servem só de termômetro."""
    b = limpar_briefing({**d, 'estilo': 'vetor_chapado'})
    qtd = max(3, min(int(d.get('quantidade') or 5), 10))
    radar = []
    if ag.segredos().get('youtube') and d.get('usar_radar', True):
        try:
            depois = (datetime.now(timezone.utc) - timedelta(days=int(d.get('dias') or 30))).strftime('%Y-%m-%dT%H:%M:%SZ')
            r = ag.yt('/youtube/v3/search', part='snippet', q=b['tema'] or b['nicho'], type='video', order='viewCount', publishedAfter=depois,
                      maxResults=15, relevanceLanguage=(b['idioma'] or 'pt')[:2], regionCode='BR')
            radar = [{'titulo': it['snippet']['title'][:120], 'canal': it['snippet']['channelTitle'][:60]} for it in r.get('items', []) if it.get('snippet')]
        except Exception as e:  # noqa: BLE001
            radar = []
            print('produtor: radar', e)
    prompt = (f'Você é pauteiro de vídeos curtos ORIGINAIS em {b["idioma"]}. Nicho: {b["nicho"]}. Tema pedido: {b["tema"] or "livre dentro do nicho"}. '
              f'Tipo: {b["tipo"]}. Público: {b["publico"] or "geral"}. Proponha {qtd} pautas originais (não copie títulos nem conteúdo de terceiros). '
              'Para cada uma: titulo, gancho (1 frase), porque (por que deve interessar agora), tipo, fontes (lista de {titulo, url} de fontes confiáveis '
              'que um humano deve conferir; deixe vazio se não souber), e se é tema de fato (fato:true) ou opinião. '
              'Responda só JSON: {"ideias":[{"titulo":"","gancho":"","porque":"","tipo":"","fato":true,"fontes":[{"titulo":"","url":""}]}]}')
    if radar:
        prompt += ('\nTítulos que estão em alta no YouTube neste nicho (use SÓ como termômetro de interesse; '
                   'interesse no YouTube não prova que o assunto é popular fora dele): ' + json.dumps(radar[:15], ensure_ascii=False))
    j = ag.gemini([{'text': prompt}], uso='roteiro')
    out = []
    for it in (j.get('ideias') if isinstance(j, dict) else []) or []:
        if not isinstance(it, dict) or not str(it.get('titulo', '')).strip():
            continue
        fontes = [{'titulo': str(f.get('titulo', ''))[:120], 'url': str(f.get('url', ''))[:300]} for f in (it.get('fontes') or [])[:5]
                  if isinstance(f, dict) and re.match(r'https?://', str(f.get('url', '')))]
        out.append({'titulo': str(it['titulo'])[:140], 'gancho': str(it.get('gancho', ''))[:240], 'porque': str(it.get('porque', ''))[:400],
                    'tipo': str(it.get('tipo', ''))[:40], 'fato': bool(it.get('fato', True)), 'fontes': fontes})
    return {'ideias': out[:qtd], 'radar': radar, 'consultado_em': time.time()}


def _prompt_roteiro(b: dict, ideia: str, extra: str = '') -> str:
    e = ec.estilo(b['estilo'])
    palavras = int(b['duracao_alvo'] * 2.4)
    return (f'Você é roteirista de vídeos curtos que prendem a atenção até o fim. Escreva o roteiro e o storyboard de um vídeo ORIGINAL em {b["idioma"]}. '
            f'Tema: {ideia or b["tema"]}. Nicho: {b["nicho"]}. Tipo: {b["tipo"]}. Público: {b["publico"] or "geral"}. '
            f'Objetivo: {b["objetivo"] or "informar e prender a atenção"}. Detalhes do pedido: {b["descricao"] or "-"}. Referências do usuário: {b["referencias"] or "-"}. '
            f'Duração total: cerca de {b["duracao_alvo"]} segundos (perto de {palavras} palavras narradas no total), em {b["cenas_qtd"]} cenas. '
            f'Estilo visual: {e["nome"]} ({e["descricao"]}).\n'
            'REGRAS DO ROTEIRO (siga todas):\n'
            '1. A cena 1 é o GANCHO: uma pergunta ou um fato surpreendente em até 12 palavras. Sem cumprimento, sem "olá", sem apresentar canal, sem "neste vídeo".\n'
            '2. Cada cena tem UMA ideia, em 1 ou 2 frases curtas (8 a 24 palavras), em linguagem falada e simples. Nada de listas, emojis, parênteses ou siglas difíceis de ler em voz alta.\n'
            '3. Cada cena deixa um motivo para ver a próxima (uma pergunta aberta, um "mas", um detalhe que falta). A resposta principal vem perto do fim, não no começo.\n'
            '4. A última cena fecha a ideia em uma frase e termina com um convite curto (uma pergunta para comentar ou "segue para mais").\n'
            '5. titulo de cada cena: até 5 palavras para aparecer na tela, SEM repetir a narração palavra por palavra. destaque: a palavra-chave da cena (1 a 3 palavras).\n'
            '6. numero: só se a cena girar em torno de um número importante (senão null); unidade: "%", "anos", "km" ou "". elementos: até 4 itens {rotulo, valor de 0 a 100} só quando a cena compara coisas (senão []).\n'
            '7. busca: 2 a 4 palavras EM INGLÊS de algo concreto que dá para fotografar e que mostra a cena (ex.: "lightning storm night", "astronaut in space"). '
            'Nada abstrato ("success", "idea") e não repita a mesma busca em cenas diferentes.\n'
            '8. camera: varie entre aproximar, afastar e panoramica (parado só em cena de número). visual: descrição da imagem da cena. duracao_alvo: segundos da cena.\n'
            '9. Não invente dados. Em temas de fato (história, ciência, saúde), liste fontes confiáveis para conferir e, se não tiver certeza, diga isso no texto. '
            'Não use marcas, personagens ou músicas de terceiros.\n'
            '10. titulo do vídeo: até 60 caracteres, curioso e verdadeiro. legenda: 1 ou 2 frases com um convite para comentar. hashtags: 5 a 8, do tema.\n'
            'Antes de responder, releia: o gancho prende em 2 segundos? Alguma cena está longa ou repetida? O total cabe na duração? Corrija e só então responda.\n'
            f'{extra}Responda só JSON: {{"titulo":"","alternativas":["",""],"gancho":"","publico":"","legenda":"","hashtags":[""],'
            '"fontes":[{"titulo":"","url":""}],"cenas":[{"texto":"","titulo":"","destaque":"","numero":null,"unidade":"","elementos":[],'
            '"camera":"aproximar","personagem":"","emocao":"","cenario":"","visual":"","busca":"","movimento":"","enquadramento":"","duracao_alvo":6}]}')


_VAZIAS = set('a o e de da do das dos um uma uns umas que em no na nos nas por para com sem se mas ou como mais muito isso esse essa este esta ele ela eles elas seu sua foi ser tem não sim já quando onde porque você the and of'.split())


def afinar_roteiro(cenas: list) -> tuple[list, list]:
    """Ajustes automáticos (sem IA) que deixam o vídeo com ritmo melhor: divide narrações longas, encurta títulos,
    varia a câmera e preenche o destaque. Devolve (cenas, avisos em português para mostrar no storyboard)."""
    out, avisos = [], []
    for c in cenas:
        pal = (c.get('texto') or '').split()
        partes = [c]
        if len(pal) > 34 and not c.get('bloqueada'):
            frases = re.split(r'(?<=[.!?])\s+', c['texto'].strip())
            if len(frases) > 1:
                meio, acum, corte = len(pal) / 2, 0, 1
                for k, f in enumerate(frases[:-1]):
                    acum += len(f.split())
                    corte = k + 1
                    if acum >= meio:
                        break
                a, b2 = ' '.join(frases[:corte]), ' '.join(frases[corte:])
                seg = dict(c, texto=b2, titulo=c.get('destaque') or ' '.join(b2.split()[:4]), numero=None, elementos=[], destaque='', busca='')
                seg.pop('audio', None); seg.pop('imagem', None); seg.pop('clipe', None)
                partes = [dict(c, texto=a), seg]
                avisos.append(f'A cena "{c.get("titulo") or c["texto"][:30]}" tinha narração longa e foi dividida em duas (cenas curtas prendem mais).')
        out += partes
    out = out[:30]
    cams = ('aproximar', 'panoramica', 'afastar')
    for i, c in enumerate(out):
        c['id'] = f'c{i + 1}'
        t = (c.get('titulo') or '').split()
        if len(t) > 7:
            c['titulo'] = ' '.join(t[:7])
        if not c.get('destaque') and c.get('texto'):
            cand = [w.strip('.,!?;:"“”()').lower() for w in c['texto'].split()]
            cand = [w for w in cand if len(w) > 4 and w not in _VAZIAS]
            if cand:
                c['destaque'] = max(cand, key=len)[:24]
        if c.get('camera') in (None, '', 'parado') and c.get('numero') is None:
            c['camera'] = cams[i % 3]
        c['duracao_alvo'] = 0.0 if c.get('texto') else c.get('duracao_alvo') or 3.0     # com narração, a fala manda na duração
    total = sum(len((c.get('texto') or '').split()) for c in out)
    if out and len((out[0].get('texto') or '').split()) > 18:
        avisos.append('O gancho (cena 1) está longo. O ideal é até 12 palavras: quem assiste decide em 2 segundos se fica.')
    return out, avisos + ([f'Narração com {total} palavras: cerca de {round(total / 2.5)} s de vídeo.'] if total else [])


def validar_roteiro(j: dict, b: dict) -> dict:
    if not isinstance(j, dict) or not isinstance(j.get('cenas'), list) or not j['cenas']:
        raise ErroProdutor('A IA não devolveu cenas. Tente de novo.')
    cenas = [ec.validar_cena(c, i) for i, c in enumerate(j['cenas'][:30]) if isinstance(c, dict)]
    cenas = [c for c in cenas if c['texto'] or c['titulo']]
    if not cenas:
        raise ErroProdutor('As cenas vieram vazias.')
    cenas, avisos = afinar_roteiro(cenas)
    return {
        'avisos': avisos,
        'titulo': str(j.get('titulo') or b['tema'] or 'Vídeo')[:120],
        'alternativas': [str(x)[:120] for x in (j.get('alternativas') or [])[:4]],
        'gancho': str(j.get('gancho') or '')[:300], 'publico': str(j.get('publico') or b['publico'])[:200],
        'legenda': str(j.get('legenda') or '')[:2000], 'hashtags': [re.sub(r'[^\w#]', '', str(h))[:40] for h in (j.get('hashtags') or [])[:12]],
        'fontes': [{'titulo': str(f.get('titulo', ''))[:150], 'url': str(f.get('url', ''))[:300]} for f in (j.get('fontes') or [])[:10]
                   if isinstance(f, dict) and re.match(r'https?://', str(f.get('url', '')))],
        'cenas': cenas,
    }


def gerar_roteiro(b: dict, ideia: str = '') -> dict:
    return validar_roteiro(ag.gemini([{'text': _prompt_roteiro(b, ideia)}], uso='roteiro'), b)


def ler_roteiro_colado(texto: str, b: dict) -> dict:
    """Roteiro escrito pela pessoa: linhas 'NOME: fala' ou parágrafos. Cada parágrafo/fala vira uma cena (sem IA)."""
    blocos = [x.strip() for x in re.split(r'\n\s*\n', texto.replace('\r', '')) if x.strip()]
    if len(blocos) == 1:
        blocos = [x.strip() for x in blocos[0].split('\n') if x.strip()]
    cenas = []
    for i, bl in enumerate(blocos[:30]):
        m = re.match(r'^\**\s*([^:\n]{1,40}?)\s*\**\s*:\s*(.+)$', bl, re.S)
        pers, fala = (m.group(1).strip(), m.group(2).strip()) if m else ('', bl)
        if re.match(r'^(cena|quadro)\s*\d+', pers, re.I):
            pers = ''
        palavras = fala.split()
        cenas.append(ec.validar_cena({'texto': fala, 'titulo': ' '.join(palavras[:6]), 'personagem': pers, 'destaque': '',
                                      'duracao_alvo': max(2.5, len(palavras) / 2.6)}, i))
    if not cenas:
        raise ErroProdutor('O roteiro está vazio.')
    return {'titulo': b['tema'] or cenas[0]['titulo'], 'alternativas': [], 'gancho': '', 'publico': b['publico'], 'legenda': '', 'hashtags': [], 'fontes': [], 'cenas': cenas}


# ---------------------------------------------------------------- projeto
def novo(d: dict, dispositivo: str = '') -> dict:
    b = limpar_briefing(d.get('briefing') or d)
    dados = {'schema': 1, 'briefing': b, 'ideias': [], 'roteiro': None, 'cenas': [], 'aprovacao_roteiro': {'aprovado': False},
             'render': None, 'renders': [], 'revisao': {'status': '', 'historico': []}}
    st = 'draft'
    if isinstance(d.get('roteiro'), dict) and d['roteiro'].get('cenas'):
        r = validar_roteiro(d['roteiro'], b)
        dados['roteiro'] = {k: v for k, v in r.items() if k != 'cenas'}
        dados['cenas'] = r['cenas']
        st = 'storyboard_ready'
    elif str(d.get('roteiro_texto') or '').strip():
        r = ler_roteiro_colado(str(d['roteiro_texto'])[:20000], b)
        dados['roteiro'] = {k: v for k, v in r.items() if k != 'cenas'}
        dados['cenas'] = r['cenas']
        st = 'storyboard_ready'
    titulo = (dados['roteiro'] or {}).get('titulo') or b['tema'] or 'Vídeo do Agente 3'
    return pj.criar({'tipo': 'agente3', 'modo': d.get('modo') or 'automatico', 'titulo': titulo, 'status': st, 'dados': dados}, dispositivo, d.get('origem') or 'site')


def salvar_storyboard(pid: str, revisao: int, d: dict, dispositivo: str = '') -> dict:
    """Storyboard editado no site: valida cada cena, mantém o que já foi gerado (narração, imagem, clipe) das cenas
    com o mesmo id (o cache por conteúdo decide o que refazer) e guarda numa revisão nova (409 se mudou em outro aparelho)."""
    p = pj.obter(pid)
    if p['tipo'] != 'agente3':
        raise ErroProdutor('Este projeto não é do Agente 3.')
    dados = p['dados']
    b = limpar_briefing({**dados.get('briefing', {}), **(d.get('briefing') or {})}) if isinstance(d.get('briefing'), dict) else dados['briefing']
    antigas = {c.get('id'): c for c in dados.get('cenas') or []}
    cenas, vistos = [], set()
    for i, c in enumerate((d.get('cenas') if isinstance(d.get('cenas'), list) else dados.get('cenas') or [])[:30]):
        if not isinstance(c, dict):
            continue
        v = ec.validar_cena(c, i)
        if v['id'] in vistos:
            v['id'] = f'c{i + 1}x{len(vistos)}'
        vistos.add(v['id'])
        if not (v['texto'] or v['titulo']):
            continue
        velha = antigas.get(v['id']) or {}
        for k in ('audio', 'imagem', 'clipe'):
            if velha.get(k):
                v[k] = velha[k]
        if c.get('bloqueada'):
            v['bloqueada'] = True
        cenas.append(v)
    if not cenas:
        raise ErroProdutor('O storyboard precisa de pelo menos uma cena com texto.')
    novos = dict(dados, briefing=b, cenas=cenas)
    if isinstance(d.get('roteiro'), dict):
        r = dict(dados.get('roteiro') or {})
        for k in ('titulo', 'legenda', 'gancho'):
            if k in d['roteiro']:
                r[k] = str(d['roteiro'][k] or '')[:2000 if k == 'legenda' else 160]
        if isinstance(d['roteiro'].get('hashtags'), list):
            r['hashtags'] = [re.sub(r'[^\w#]', '', str(h))[:40] for h in d['roteiro']['hashtags'][:12]]
        novos['roteiro'] = r
    if cenas != dados.get('cenas'):
        novos['aprovacao_roteiro'] = {'aprovado': False}      # mudou: precisa aprovar de novo antes de produzir
    titulo = (novos.get('roteiro') or {}).get('titulo') or p['titulo']
    st = p['status'] if p['status'] not in ('draft', 'ready_for_review', 'rejected', 'failed', 'changes_requested') else 'storyboard_ready'
    return pj.atualizar(pid, {'revisao': revisao, 'dados': novos, 'titulo': titulo, 'status': st}, dispositivo, 'site')


def _status(pid: str, st: str, extra=None):
    def f(dados, p):
        dados.setdefault('producao', {})['status'] = st
        if extra:
            extra(dados)
        return {'status': st}
    pj.mudar_dados(pid, f)


def produzir(pid: str, quando: float | None = None, chave: str = '', etapa: str = '', dispositivo: str = '', extra: dict | None = None) -> dict:
    p = pj.obter(pid)
    if p['tipo'] != 'agente3':
        raise ErroProdutor('Este projeto não é do Agente 3.')
    b = p['dados']['briefing']
    ativo = db.um("SELECT id FROM jobs WHERE projeto=? AND status IN ('agendado','na_fila','rodando','aguardando_tentativa','aguardando_aprovacao')", pid)
    if ativo and not chave:
        raise ErroProdutor('Este projeto já está na fila. Veja em Fila e aprovações.')
    if not etapa:
        etapa = 'roteiro' if (p['dados'].get('cenas') or b['tema'] or b['temas']) else 'pauta'
    titulo = p['titulo']
    job = fila.enfileirar('agente3.produzir', agente='agente3', dados={'projeto': pid, 'etapa': etapa, **(extra or {})}, run_at=quando,
                          prioridade=b['prioridade'], recurso='leve', projeto=pid, titulo=titulo, chave=chave, max_tentativas=b['max_tentativas'])
    st = 'scheduled' if job['status'] == 'agendado' else 'queued'
    _status(pid, st, lambda d: d['producao'].update(job=job['id'], pedido=time.time()))
    db.evento(dispositivo or 'agente3', 'producao_pedida', 'projeto:' + pid, {'job': job['id'], 'quando': job['run_at']})
    return job


# ---------------------------------------------------------------- áudio e imagem
def _wav(pcm: bytes, arq: Path, taxa: int = 24000):
    with wave.open(str(arq), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes(pcm)


def _tts_bruto(texto: str, voz: str, arq: Path) -> float:
    corpo = {'contents': [{'parts': [{'text': texto}]}],
             'generationConfig': {'responseModalities': ['AUDIO'], 'speechConfig': {'voiceConfig': {'prebuiltVoiceConfig': {'voiceName': voz}}}}}
    try:
        st, j, nome = ag.http_gemini('voz', f'{MODELO_TTS}:generateContent', corpo, 180)
    except ag.ErroAgente as e:
        raise ErroProdutor(str(e), True)
    if st == 429:
        raise fila.Esperar(90, 'A voz do Gemini pediu para esperar (limite por minuto)')
    if st >= 300:
        raise ErroProdutor(ag.erro_gemini(st, j, nome).replace('A IA (Gemini', 'A voz do Gemini'))
    try:
        dados = next(p['inlineData']['data'] for p in j['candidates'][0]['content']['parts'] if p.get('inlineData'))
    except (KeyError, IndexError, StopIteration, TypeError):
        raise ErroProdutor('A voz do Gemini veio vazia.')
    pcm = base64.b64decode(dados)
    _wav(pcm, arq)
    return len(pcm) / 2 / 24000


def _aparar(arq: Path, ritmo: float) -> float:
    """Tira o silêncio do começo e do fim da fala (a legenda acompanha melhor e o vídeo não tem 'buracos') e aplica o ritmo.
    Se o FFmpeg falhar, a narração fica como veio."""
    tmp = arq.with_suffix('.ap.wav')
    corte = 'silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.04'
    filtro = f'{corte},areverse,{corte},areverse' + (f',atempo={ritmo:.3f}' if abs(ritmo - 1) > 0.005 else '')
    try:
        rd.rodar(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(arq), '-af', filtro, '-ar', '24000', '-ac', '1', str(tmp)], tempo_max=120)
        d = rd.duracao(tmp)
        if d > 0.3:
            tmp.replace(arq)
            return d
    except (rd.ErroRender, OSError):
        pass
    tmp.unlink(missing_ok=True)
    return rd.duracao(arq)


def tts(texto: str, voz: str, arq: Path, tom: str = '', ritmo: float = 1.0) -> float:
    """Narra uma cena. Com `tom`, pede ao Gemini o jeito de falar; se a fala vier longa demais para o texto
    (sinal de que ele leu a instrução em voz alta), narra de novo só o texto."""
    palavras = max(1, len(texto.split()))
    dur = _tts_bruto(f'Diga em tom {tom}: {texto}' if tom else texto, voz, arq)
    if tom and dur > palavras / 1.4 + 3.5:
        dur = _tts_bruto(texto, voz, arq)
    return _aparar(arq, ritmo) or dur


def gerar_imagem(prompt: str, arq: Path, formato: str):
    corpo = {'contents': [{'parts': [{'text': prompt + f' Formato {formato}. Sem texto escrito na imagem, sem marcas registradas.'}]}],
             'generationConfig': {'responseModalities': ['IMAGE']}}
    try:
        st, j, nome = ag.http_gemini('imagens', f'{MODELO_IMAGEM}:generateContent', corpo, 180)
    except ag.ErroAgente as e:
        raise ErroProdutor(str(e), True)
    if st == 429:
        raise fila.Esperar(120, 'O gerador de imagens pediu para esperar')
    if st >= 300:
        raise ErroProdutor(ag.erro_gemini(st, j, nome).replace('A IA (Gemini', 'O gerador de imagens (Gemini'))
    try:
        dados = next(p['inlineData']['data'] for p in j['candidates'][0]['content']['parts'] if p.get('inlineData'))
    except (KeyError, IndexError, StopIteration, TypeError):
        raise ErroProdutor('O gerador de imagens não devolveu imagem (pode ter bloqueado o pedido).')
    arq.write_bytes(base64.b64decode(dados))


def _h(*partes) -> str:
    return hashlib.sha256(json.dumps(partes, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]


PAUSA = 0.3        # respiro entre uma cena e outra, em segundos


def _dur_cena(c: dict) -> float:
    falada = (c.get('audio') or {}).get('dur') or 0
    if falada:
        return round(falada + PAUSA, 2)
    estimada = max(2.5, len((c.get('texto') or '').split()) / 2.6 + 0.6)
    return round(max(estimada, min(c.get('duracao_alvo') or 0, 30)), 2)


# ---------------------------------------------------------------- etapas
def _pasta(pid: str, sub: str) -> Path:
    p = pj.pasta(pid) / sub
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cancelado(ctx):
    return lambda: ctx.cancelado()


def etapa_pauta(ctx, pid, p, b):
    _status(pid, 'researching')
    tema = ''
    if b['temas']:
        usados = db.kv('temas_usados:' + pid, []) or []
        livres = [t for t in b['temas'] if t not in usados] or b['temas']
        tema = livres[0]
    else:
        r = ideias({**b, 'quantidade': 5})
        ja = set(db.kv('pautas_usadas', []) or [])
        escolha = next((i for i in r['ideias'] if i['titulo'] not in ja), r['ideias'][0] if r['ideias'] else None)
        if not escolha:
            raise ErroProdutor('A pesquisa de pautas voltou vazia.')
        tema = escolha['titulo']
        db.kv_gravar('pautas_usadas', list(ja | {tema})[-300:])
        pj.mudar_dados(pid, lambda d, _p: d.update(ideias=r['ideias']))
    pj.mudar_dados(pid, lambda d, _p: (d['briefing'].update(tema=tema), {'titulo': tema})[1])
    return {'proxima': True, 'recurso': 'leve', 'etapa': 'Roteiro'}


def etapa_roteiro(ctx, pid, p, b):
    ctx.progresso(5, 'Escrevendo roteiro e storyboard')
    if not p['dados'].get('cenas'):
        t0 = time.time()
        _conferir_orcamento(ctx.id, b, 0.05)
        r = gerar_roteiro(b, b['tema'])
        _custo(ctx.id, 'gemini', ag.MODELO, 'roteiro', 0.03)
        fila.medir('roteiro', time.time() - t0)

        def f(d, _p):
            d['roteiro'] = {k: v for k, v in r.items() if k != 'cenas'}
            d['cenas'] = r['cenas']
            return {'titulo': r['titulo'], 'status': 'storyboard_ready'}
        pj.mudar_dados(pid, f)
        p = pj.obter(pid)
    if b['modo_aprovacao'] == 'assistido' and not p['dados'].get('aprovacao_roteiro', {}).get('aprovado'):
        _status(pid, 'waiting_brief_approval')
        try:
            import emails
            emails.avisar_roteiro(pid)
        except Exception as e:  # noqa: BLE001
            print('produtor: aviso de roteiro', e)
        raise fila.Esperar(0, 'Esperando você aprovar o roteiro e o storyboard', 'aguardando_aprovacao')
    return {'proxima': True, 'recurso': 'leve', 'etapa': 'Narração'}


def etapa_revisar(ctx, pid, p, b):
    """Correção pedida (pelo site ou e-mail): a IA ajusta SÓ o que foi pedido; cenas bloqueadas não mudam."""
    pedido = ctx.dados.get('correcao') or ''
    if not pedido:
        return {'proxima': True, 'recurso': 'leve', 'etapa': 'Narração'}
    ctx.progresso(5, 'Aplicando a correção pedida')
    _conferir_orcamento(ctx.id, b, 0.05)
    atual = p['dados']['cenas']
    prompt = (_prompt_roteiro(b, b['tema'], 'Este é o roteiro atual (JSON): ' + json.dumps({'cenas': atual}, ensure_ascii=False)[:30000] +
                              f'\nPEDIDO DE CORREÇÃO do dono do canal: "{pedido[:2000]}". Mude só o necessário para atender o pedido; '
                              f'mantenha iguais as cenas com "bloqueada": true. ') + ' Devolva o roteiro completo corrigido.')
    r = validar_roteiro(ag.gemini([{'text': prompt}], uso='roteiro'), b)
    _custo(ctx.id, 'gemini', ag.MODELO, 'correcao', 0.03)

    def f(d, _p):
        novas = r['cenas']
        for i, c in enumerate(d['cenas']):
            if c.get('bloqueada') and i < len(novas):
                novas[i] = c
        d['cenas'] = novas
        (d.get('roteiro') or d.setdefault('roteiro', {})).update({k: v for k, v in r.items() if k not in ('cenas',)})
        if not d.get('render') and b['modo_aprovacao'] == 'assistido':
            d['aprovacao_roteiro'] = {'aprovado': False}       # correção do roteiro: você confere de novo antes de produzir
        return {}
    pj.mudar_dados(pid, f)
    ctx.dados['correcao'] = ''
    if not p['dados'].get('render') and b['modo_aprovacao'] == 'assistido':
        return {'proxima': True, 'recurso': 'leve', 'etapa': 'Roteiro'}
    return {'proxima': True, 'recurso': 'leve', 'etapa': 'Narração'}


def etapa_narracao(ctx, pid, p, b):
    _status(pid, 'narrating')
    cenas = p['dados']['cenas']
    pasta = _pasta(pid, 'audio')
    for i, c in enumerate(cenas):
        ctx.progresso(10 + 25 * i / max(1, len(cenas)), f'Narrando cena {i + 1} de {len(cenas)}')
        if b['voz'] == 'nenhuma' or not c.get('texto'):
            if c.get('audio'):
                pj.mudar_dados(pid, lambda d, _p, i=i: d['cenas'][i].pop('audio', None))
            continue
        tom = TONS.get(b.get('tipo'), TONS['outro']) if os.getenv('TTS_TOM', '1') != '0' else ''
        ritmo = RITMOS.get(b.get('ritmo') or 'agil', 1.0)
        h = _h(c['texto'], b['voz'], MODELO_TTS, tom, ritmo, 2)
        if (c.get('audio') or {}).get('h') == h and Path((c['audio'] or {}).get('arquivo', '')).exists():
            continue
        _conferir_orcamento(ctx.id, b, 0.02)
        arq = pasta / f'{h}.wav'
        t0 = time.time()
        if not arq.exists():
            dur = tts(c['texto'], b['voz'], arq, tom, ritmo)
            _custo(ctx.id, 'gemini', MODELO_TTS, 'narracao', 0.002 * max(1, len(c['texto']) / 100) * float(ag.config()['orcamento'].get('dolar', 5.5)))
        else:
            dur = rd.duracao(arq)
        fila.medir('narracao', time.time() - t0)
        info = pj.registrar_asset(arq, f'narracao-{c["id"]}.wav', 'audio/wav', pid, 'agente3')['asset']
        pj.mudar_dados(pid, lambda d, _p, i=i: d['cenas'][i].update(audio={'h': h, 'arquivo': str(arq), 'asset': info['id'], 'dur': round(dur, 3)}))
    precisa = b['imagens'] in ('gemini', 'busca') or ec.estilo(b['estilo'])['precisa_imagem']
    return {'proxima': True, 'recurso': 'leve' if precisa else 'pesado', 'etapa': 'Imagens' if precisa else 'Render'}


def _foto_da_cena(pid, i, c, b, pasta, cenas):
    """Busca uma foto real para a cena (Pexels ou Wikimedia). O estilo a remodela no render. Se não achar, a cena segue sem foto."""
    consulta = c.get('busca') or ' '.join((c.get('destaque') or c.get('titulo') or '').split()[:4])
    h = _h('busca', consulta, b['formato'])
    atual = c.get('imagem') or {}
    if atual.get('h') == h and Path(atual.get('arquivo', '')).exists():
        return
    atuais = pj.obter(pid)['dados'].get('cenas') or cenas          # relê: as fotos das cenas anteriores acabaram de ser gravadas
    usadas = {str((x.get('imagem') or {}).get('id')) for j, x in enumerate(atuais) if j != i and (x.get('imagem') or {}).get('id')}
    t0 = time.time()
    tentativas = [consulta]
    if len(consulta.split()) > 2:
        tentativas.append(' '.join(consulta.split()[:2]))
    reserva = ' '.join((c.get('destaque') or c.get('titulo') or '').split()[:3])
    if reserva and reserva not in tentativas:
        tentativas.append(reserva)
    foto, e = None, None
    for q in tentativas:
        try:
            foto = im.buscar(q, b['formato'], pasta, ag.segredos().get('pexels', ''), usadas)
            break
        except im.SemFoto as x:
            e = x
    if not foto:
        db.evento('agente3', 'foto_nao_achada', 'projeto:' + pid, {'cena': c.get('id'), 'consulta': consulta, 'motivo': str(e)[:200]})
        pj.mudar_dados(pid, lambda d, _p, i=i: d['cenas'][i].pop('imagem', None))
        return
    fila.medir('visual', time.time() - t0)
    arq = Path(foto['arquivo'])
    info = pj.registrar_asset(arq, f'foto-{c["id"]}.jpg', 'image/jpeg', pid, 'agente3')['asset']
    pj.mudar_dados(pid, lambda d, _p, i=i: d['cenas'][i].update(imagem={'h': h, 'arquivo': str(arq), 'asset': info['id'], 'id': foto['id'], 'fonte': foto['fonte'],
                                                                         'credito': foto['credito'], 'link': foto['link']}))


def creditos(dados: dict) -> list:
    """Créditos das fotos usadas (sem repetir), para o e-mail e para a legenda."""
    out = []
    for c in dados.get('cenas') or []:
        cr = (c.get('imagem') or {}).get('credito')
        if cr and cr not in out:
            out.append(cr)
    return out


def etapa_visual(ctx, pid, p, b):
    _status(pid, 'generating_assets')
    cenas = p['dados']['cenas']
    pasta = _pasta(pid, 'images')
    estilo = ec.estilo(b['estilo'])
    for i, c in enumerate(cenas):
        ctx.progresso(35 + 15 * i / max(1, len(cenas)), f'Imagem da cena {i + 1} de {len(cenas)}')
        if (c.get('imagem') or {}).get('manual'):
            continue        # imagem escolhida pela pessoa: não troca
        if b['imagens'] == 'busca' and not estilo['precisa_imagem']:
            _foto_da_cena(pid, i, c, b, pasta, cenas)
            continue
        prompt = (f'Ilustração original no estilo "{estilo["nome"]}" ({estilo["tecnica"]}). Cena: {c.get("visual") or c.get("titulo")}. '
                  f'Cenário: {c.get("cenario") or "-"}. Personagem: {c.get("personagem") or "nenhum"}, {c.get("emocao") or ""}. '
                  f'Enquadramento: {c.get("enquadramento") or "plano médio"}.')
        h = _h(prompt, MODELO_IMAGEM, b['formato'])
        if (c.get('imagem') or {}).get('h') == h and Path((c['imagem'] or {}).get('arquivo', '')).exists():
            continue
        _conferir_orcamento(ctx.id, b, 0.25)
        arq = pasta / f'{h}.png'
        t0 = time.time()
        if not arq.exists():
            gerar_imagem(prompt, arq, b['formato'])
            _custo(ctx.id, 'gemini', MODELO_IMAGEM, 'imagem', 0.04 * float(ag.config()['orcamento'].get('dolar', 5.5)))
        fila.medir('visual', time.time() - t0)
        info = pj.registrar_asset(arq, f'imagem-{c["id"]}.png', 'image/png', pid, 'agente3')['asset']
        pj.mudar_dados(pid, lambda d, _p, i=i: d['cenas'][i].update(imagem={'h': h, 'arquivo': str(arq), 'asset': info['id']}))
    return {'proxima': True, 'recurso': 'pesado', 'etapa': 'Render'}


def _imagem_da_cena(c: dict) -> Path | None:
    im = c.get('imagem') or {}
    if im.get('arquivo') and Path(im['arquivo']).exists():
        return Path(im['arquivo'])
    if im.get('asset'):
        try:
            return Path(pj.asset(im['asset'])['caminho'])
        except pj.ErroProjeto:
            return None
    return None


def etapa_render(ctx, pid, p, b):
    if not rd.tem_ffmpeg():
        raise ErroProdutor('Falta o FFmpeg no servidor (Termux: pkg install ffmpeg).', True)
    if 0 <= rd.livre_mb(pj.pasta(pid)) < rd.MIN_LIVRE_MB:
        raise fila.Esperar(1800, f'Pouco espaço livre no celular (menos de {rd.MIN_LIVRE_MB} MB). Libere espaço; tento de novo em 30 min.')
    _status(pid, 'rendering')
    W, H = ec.FORMATOS[b['formato']]
    cenas = p['dados']['cenas']
    pasta = _pasta(pid, 'scenes')
    total = sum(_dur_cena(c) for c in cenas) or 1
    feito = 0.0
    for i, c in enumerate(cenas):
        dur = _dur_cena(c)
        eid = c.get('estilo') or b['estilo']
        img = _imagem_da_cena(c)
        if not ec.utilizavel(eid, bool(img)):
            eid = b['estilo'] if ec.utilizavel(b['estilo'], bool(img)) else 'vetor_chapado'
        audio = Path(c['audio']['arquivo']) if (c.get('audio') or {}).get('arquivo') and Path(c['audio']['arquivo']).exists() else None
        chave = ec.chave_cena(eid, {k: c.get(k) for k in ('texto', 'titulo', 'destaque', 'numero', 'unidade', 'elementos', 'camera')}, W, H, dur,
                              (c.get('audio') or {}).get('h', ''), (c.get('imagem') or {}).get('h', '') + (str(img) if img else ''), b['paleta'])
        saida = pasta / f'{chave}.mp4'
        if not (saida.exists() and saida.stat().st_size > 1000 and (c.get('clipe') or {}).get('chave') == chave):
            trab = pasta / f'trab-{chave}'
            shutil.rmtree(trab, ignore_errors=True)
            trab.mkdir(parents=True)
            tmp = pasta / f'{chave}.tmp.mp4'
            t0 = time.time()
            base_pct = 50 + 35 * feito / total
            try:
                ec.preparar(eid, W, H, dur, b['paleta'] or None, _cancelado(ctx))
                rd.rodar(ec.montar(eid, c, W, H, dur, trab, img, audio, tmp, b['paleta'] or None), _cancelado(ctx),
                         progresso=lambda x, i=i, base_pct=base_pct, dur=dur: ctx.progresso(base_pct + 35 * dur / total * x, f'Renderizando cena {i + 1} de {len(cenas)}'),
                         dur=dur)
            except InterruptedError:
                tmp.unlink(missing_ok=True)
                raise fila.Cancelado()
            tmp.replace(saida)
            shutil.rmtree(trab, ignore_errors=True)
            fila.medir('render_cena', time.time() - t0, dur)
            pj.mudar_dados(pid, lambda d, _p, i=i: d['cenas'][i].update(clipe={'chave': chave, 'arquivo': str(saida), 'dur': dur, 'estilo': eid}, duracao_real=dur))
        feito += dur
        ctx.progresso(50 + 35 * feito / total, f'Cena {i + 1} de {len(cenas)} pronta')
    return {'proxima': True, 'recurso': 'pesado', 'etapa': 'Vídeo final'}


def _srt(cenas: list) -> str:
    out, t = [], 0.0

    def ts(x):
        return f'{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{int(x % 60):02d},{int(x * 1000 % 1000):03d}'
    for i, c in enumerate(cenas):
        d = (c.get('clipe') or {}).get('dur') or _dur_cena(c)
        if c.get('texto'):
            out.append(f'{len(out) + 1}\n{ts(t)} --> {ts(t + d)}\n{c["texto"]}\n')
        t += d
    return '\n'.join(out)


def etapa_final(ctx, pid, p, b):
    _status(pid, 'assembling')
    cenas = p['dados']['cenas']
    clipes = [Path((c.get('clipe') or {}).get('arquivo', '')) for c in cenas]
    if not all(x.exists() for x in clipes):
        return {'proxima': True, 'recurso': 'pesado', 'etapa': 'Render'}       # algum clipe sumiu: refaz só os que faltam
    pasta = _pasta(pid, 'renders')
    trab = pasta / 'trabalho'
    shutil.rmtree(trab, ignore_errors=True)
    trab.mkdir()
    t0 = time.time()
    ctx.progresso(86, 'Juntando as cenas')
    junto = trab / 'junto.mp4'
    rd.concatenar(clipes, junto, trab, _cancelado(ctx))
    trilha = None
    if b['trilha']:
        try:
            trilha = Path(pj.asset(b['trilha'])['caminho'])
        except pj.ErroProjeto:
            trilha = None
    ctx.progresso(89, 'Mixando o som')
    final_tmp = trab / 'final.tmp.mp4'
    rd.mixar_trilha(junto, trilha, final_tmp, _cancelado(ctx))
    dur_esperada = sum((c.get('clipe') or {}).get('dur') or 0 for c in cenas)
    W, H = ec.FORMATOS[b['formato']]
    _status(pid, 'validating')
    ctx.progresso(92, 'Conferindo o vídeo (codec, som, começo/meio/fim, tela preta)')
    conf = rd.conferir(final_tmp, trab, {'largura': W, 'altura': H, 'duracao': dur_esperada}, _cancelado(ctx))
    fila.medir('final', time.time() - t0, max(1, dur_esperada))
    if not conf['ok']:
        raise ErroProdutor('O vídeo final não passou na conferência: ' + '; '.join(conf['erros']))
    sha = rd.sha256(final_tmp)
    final = pasta / f'{sha[:16]}.mp4'
    final_tmp.replace(final)                       # só agora o arquivo vira "final"
    prev = pasta / f'{sha[:16]}.preview.mp4'
    try:
        rd.preview_leve(final, prev, _cancelado(ctx))
    except rd.ErroRender:
        prev = final
    thumb = pasta / f'{sha[:16]}.jpg'
    if not rd.capa(final, thumb, min(1.6, conf['duracao'] * 0.2)):      # capa: o gancho já com o título na tela
        meio = next((Path(q) for q in conf['quadros'] if 'meio' in q), None)
        if meio:
            shutil.copy(meio, thumb)
    srt = pasta / f'{sha[:16]}.srt'
    srt.write_text(_srt(cenas), encoding='utf-8')
    ids = {}
    for nome, arq, mime in (('video', final, 'video/mp4'), ('preview', prev, 'video/mp4'), ('thumb', thumb, 'image/jpeg'), ('srt', srt, 'application/octet-stream')):
        if arq.exists():
            ids[nome] = pj.registrar_asset(arq, f'{nome}-{sha[:8]}{arq.suffix}', mime, pid, 'agente3')['asset']['id']
    versao = (db.um('SELECT COALESCE(MAX(versao),0) AS v FROM renders WHERE projeto=?', pid) or {'v': 0})['v'] + 1
    rid = sha[:16]
    db.executar('INSERT OR REPLACE INTO renders (id, projeto, versao, arquivo, sha256, duracao, codec, largura, altura, validado, alertas, criado) VALUES (?,?,?,?,?,?,?,?,?,1,?,?)',
                rid, pid, versao, str(final), sha, conf['duracao'], conf['codec'], conf['largura'], conf['altura'], json.dumps(conf['avisos'], ensure_ascii=False), time.time())
    shutil.rmtree(trab, ignore_errors=True)
    render = {'id': rid, 'sha': sha, 'versao': versao, 'duracao': conf['duracao'], 'validado': True, 'avisos': conf['avisos'], 'assets': ids,
              'tamanho': final.stat().st_size, 'criado': time.time(), 'codec': f'{conf["codec"]}/{conf["audio"]}', 'largura': W, 'altura': H}

    def f(d, _p):
        d['render'] = render
        d.setdefault('renders', []).append({k: render[k] for k in ('id', 'sha', 'versao', 'duracao', 'criado')})
        d['revisao'] = {'status': 'pendente', 'historico': d.get('revisao', {}).get('historico', [])}
        return {'status': 'ready_for_review'}
    pj.mudar_dados(pid, f)
    db.evento('agente3', 'render_pronto', 'projeto:' + pid, {'sha': sha, 'versao': versao, 'avisos': conf['avisos']})
    return {'proxima': True, 'recurso': 'leve', 'etapa': 'Avisando por e-mail'}


def etapa_notificar(ctx, pid, p, b):
    ctx.progresso(98, 'Avisando por e-mail')
    import emails
    r = p['dados'].get('render') or {}
    enviado = False
    try:
        enviado = emails.enviar_pronto(pid, r.get('sha', ''))
    except Exception as e:  # noqa: BLE001
        ag.anotar(f'Agente 3: e-mail do vídeo pronto não foi enviado: {e}', 'erro')
    return {'resultado': {'render': r.get('sha'), 'email': enviado}, 'etapa': 'Pronto para revisão'}


ETAPAS = {'pauta': etapa_pauta, 'roteiro': etapa_roteiro, 'revisar': etapa_revisar, 'narracao': etapa_narracao,
          'visual': etapa_visual, 'render': etapa_render, 'final': etapa_final, 'notificar': etapa_notificar}
SEGUINTE = {'pauta': 'roteiro', 'roteiro': 'narracao', 'revisar': 'narracao', 'narracao': None, 'visual': 'render', 'render': 'final', 'final': 'notificar'}


def job_produzir(ctx):
    pid = ctx.dados['projeto']
    try:
        p = pj.obter(pid)
    except pj.ErroProjeto:
        raise ErroProdutor('O projeto deste trabalho foi apagado.', True)
    b = p['dados']['briefing']
    etapa = ctx.dados.get('etapa') or 'roteiro'
    try:
        r = ETAPAS[etapa](ctx, pid, p, b)
    except ag.ErroAgente as e:
        raise ErroProdutor(str(e), 'teto' in str(e) or 'Falta a chave' in str(e))
    except fila.Esperar:
        raise
    if r.get('proxima'):
        if etapa == 'narracao':
            ctx.dados['etapa'] = 'visual' if r.get('etapa') == 'Imagens' else 'render'
        elif etapa == 'revisar' and r.get('etapa') == 'Roteiro':
            ctx.dados['etapa'] = 'roteiro'
        else:
            ctx.dados['etapa'] = SEGUINTE[etapa]
    return r


def _falhou(job, msg):
    if job and job['agente'] == 'agente3' and job.get('projeto'):
        try:
            _status(job['projeto'], 'failed', lambda d: d['producao'].update(erro=msg[:500]))
            import emails
            emails.avisar_falha(job['projeto'], msg)
        except Exception as e:  # noqa: BLE001
            print('produtor: falha', e)


def estimar(job: dict) -> tuple[float, bool]:
    """Quanto falta (segundos), pelas medidas reais deste aparelho; sem medida, usa chutes iniciais."""
    dados = json.loads(job['dados']) if isinstance(job.get('dados'), str) else (job.get('dados') or {})
    try:
        p = pj.obter(dados.get('projeto', ''))
    except pj.ErroProjeto:
        return 0, False
    b = p['dados']['briefing']
    cenas = p['dados'].get('cenas') or [None] * b['cenas_qtd']
    etapa = dados.get('etapa') or 'roteiro'
    ordem = ['pauta', 'roteiro', 'revisar', 'narracao', 'visual', 'render', 'final', 'notificar']
    depois = ordem[ordem.index(etapa):] if etapa in ordem else ordem
    total, todas_medidas = 0.0, True
    seg_video = sum(_dur_cena(c) if c else b['duracao_alvo'] / max(1, b['cenas_qtd']) for c in cenas)
    for e in depois:
        if e in ('pauta', 'roteiro', 'revisar') and (e != 'roteiro' or not p['dados'].get('cenas')):
            s, m = fila.media('roteiro')
            total += s
        elif e == 'narracao' and b['voz'] != 'nenhuma':
            s, m = fila.media('narracao')
            total += s * sum(1 for c in cenas if not c or not c.get('audio'))
        elif e == 'visual' and (b['imagens'] in ('gemini', 'busca') or ec.estilo(b['estilo'])['precisa_imagem']):
            s, m = fila.media('visual')
            total += s * sum(1 for c in cenas if not c or not c.get('imagem'))
        elif e == 'render':
            s, m = fila.media('render_cena')
            if not m:
                s = 1.2       # chute: 1,2 s de processamento por segundo de vídeo (só até medir neste aparelho)
            total += s * sum((_dur_cena(c) if c else b['duracao_alvo'] / max(1, b['cenas_qtd'])) for c in cenas if not c or not c.get('clipe'))
        elif e == 'final':
            s, m = fila.media('final')
            if not m:
                s = 0.8
            total += s * seg_video
        else:
            continue
        todas_medidas = todas_medidas and m
    if job['status'] == 'rodando':
        total *= max(0.05, 1 - ((job['progresso'] or 0) % 100) / 400)
    return total, todas_medidas


def criar_da_rotina(agenda: dict, ocorr: float, i: int):
    chave = f'rotina:{agenda["id"]}:{int(ocorr)}:{i}'
    if db.um('SELECT id FROM jobs WHERE chave=?', chave):
        return
    b = dict(agenda['briefing'] or {})
    if b.get('temas'):
        b['tema'] = b['temas'][(int(ocorr // 86400) + i) % len(b['temas'])]
    proj = novo({'briefing': b, 'modo': 'automatico', 'origem': 'rotina:' + agenda['id']})
    produzir(proj['id'], ocorr, chave)


def iniciar():
    fila.registrar('agente3.produzir', job_produzir, 'leve')
    fila.ESTIMADORES['agente3.produzir'] = estimar
    fila.AO_FALHAR.append(_falhou)
    import agendador
    agendador.CRIAR = criar_da_rotina
