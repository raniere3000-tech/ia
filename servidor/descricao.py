"""Descrição de publicação dos vídeos do Agente 3, num formato fixo:

    TÍTULO

    #tag1 #tag2 #tag3

    .
    .
    .
    Link original do vídeo []

Uma função só (compor) monta o modelo; o site mostra a prévia que o servidor devolve (a lógica não é repetida no site).
Créditos obrigatórios das imagens entram antes dos três pontos, sem tirar título, hashtags nem rodapé.
Nada é cortado em silêncio: passar do limite de uma rede vira aviso (e a aprovação para essa rede é recusada).
"""
import re

SEPARADOR = '.\n.\n.'
RODAPE = 'Link original do vídeo [{}]'
_RE_RODAPE = re.compile(r'(?m)^\.\n\.\n\.\nLink original do vídeo \[[^\]\n]*\]\s*$')
# limite de descrição/legenda que o Agente 2 usa em cada rede (YouTube 5000; as outras 2200)
LIMITES = {'youtube': 5000, 'instagram': 2200, 'tiktok': 2200, 'facebook': 2200, 'kwai': 2200}


def titulo_limpo(t: str) -> str:
    """Título publicado: sem colchetes nem marcadores, numa linha só."""
    t = re.sub(r'[\[\]*]', '', str(t or ''))
    t = re.sub(r'^\s*(?:[-*•#>]+\s*)+', '', t)
    return re.sub(r'\s+', ' ', t).strip()[:150]


def hashtags(lista) -> list:
    """'#Ciência', 'ciência', 'ciencia curiosa' -> ['#Ciência', '#cienciacuriosa'], sem repetir (maiúscula/minúscula conta igual)."""
    if isinstance(lista, str):
        lista = lista.split()
    out, vistos = [], set()
    for h in lista or []:
        h = re.sub(r'[^\w]', '', str(h).lstrip('#'), flags=re.UNICODE)
        if not h or h.casefold() in vistos:
            continue
        vistos.add(h.casefold())
        out.append('#' + h)
    return out[:30]


def link_valido(u) -> str:
    """Só um endereço http(s) inteiro, sem espaço nem colchete; senão, vazio (nunca inventa link)."""
    u = str(u or '').strip()
    return u if re.fullmatch(r'https?://[^\s\[\]<>"]{3,500}', u) and '.' in u.split('/')[2] else ''


def aplicado(texto: str) -> bool:
    """O texto já termina com os três pontos e o rodapé?"""
    return bool(_RE_RODAPE.search(str(texto or '').rstrip()))


def compor(titulo: str, tags, link: str = '', creditos=()) -> str:
    partes = [titulo_limpo(titulo)]
    hs = hashtags(tags)
    if hs:
        partes.append(' '.join(hs))
    creds = [str(c).strip() for c in creditos or [] if str(c).strip()]
    if creds:
        partes.append('Imagens: ' + '; '.join(creds))
    partes.append(SEPARADOR + '\n' + RODAPE.format(link_valido(link)))
    return '\n\n'.join(p for p in partes if p)


def com_creditos(texto: str, exigidos) -> str:
    """Garante os créditos obrigatórios (ex.: CC BY) numa descrição editada à mão. Entram antes dos três pontos;
    se o modelo não estiver aplicado, entram no fim. O que já está no texto não é repetido."""
    texto = str(texto or '').rstrip()
    faltam = [c for c in exigidos or [] if c and c not in texto]
    if not faltam:
        return texto
    bloco = 'Imagens: ' + '; '.join(faltam)
    m = _RE_RODAPE.search(texto)
    if m:
        return (texto[:m.start()].rstrip() + '\n\n' + bloco + '\n\n' + texto[m.start():]).strip()
    return texto + '\n\n' + bloco


def excede(texto: str, redes) -> list:
    """Avisos das redes cujo limite a descrição passa (não corta nada)."""
    n = len(texto or '')
    return [f'{r.capitalize()}: a descrição tem {n} caracteres e o limite é {LIMITES[r]} (passa {n - LIMITES[r]}).'
            for r in redes or [] if r in LIMITES and n > LIMITES[r]]


def do_projeto(dados: dict, creditos=(), titulo_projeto: str = '') -> str:
    """Modelo padrão de um projeto do Agente 3 (título e hashtags do roteiro, link original só se informado e válido)."""
    b = dados.get('briefing') or {}
    de = b.get('destinos') or {}
    rot = dados.get('roteiro') or {}
    titulo = de.get('titulo') or rot.get('titulo') or titulo_projeto or b.get('tema') or ''
    return compor(titulo, rot.get('hashtags') or [], de.get('link_original') or b.get('link_original') or '', creditos)
