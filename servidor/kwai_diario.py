"""Pacote diário do Kwai: o Coordenador (Agente 7) junta, no fim do dia, tudo o que foi postado/agendado naquele dia
para você postar à mão no Kwai (o Kwai não tem API pública).

Para cada vídeo do dia: nome (título), descrição pronta (com o link do vídeo original), hashtags, link original,
em quais redes foi e o link para baixar o vídeo.

Sai em dois arquivos, guardados em ~/.estudioclip/kwai/:
  - kwai-AAAA-MM-DD.html  página para abrir no celular, com "Copiar" e "Baixar vídeo" em cada item
  - kwai-AAAA-MM-DD.txt   o mesmo em texto puro (vai anexado no e-mail)
O aviso do fim do dia vai pelo WhatsApp (link da página) e por e-mail (com o .txt anexado).
Os links são assinados e valem 3 dias, enquanto o endereço do servidor não mudar. No site, a aba
Coordenador > Kwai sempre gera links novos.
Só biblioteca padrão (roda no Termux).
"""
from __future__ import annotations

import html
import re
import time
from pathlib import Path

import postagem as pg

PASTA = pg.DADOS / 'kwai'
VALIDADE = 3 * 86400       # segundos que os links do pacote valem
REDE_NOME = {'youtube': 'YouTube', 'tiktok': 'TikTok', 'instagram': 'Instagram', 'facebook': 'Facebook', 'kwai': 'Kwai'}
STATUS_NOME = {'postado': 'postado', 'agendado': 'agendado', 'manual': 'manual', 'erro': 'com erro', 'liberacao': 'esperando liberação'}


class ErroKwai(Exception):
    pass


def data_valida(data: str) -> str:
    data = str(data or '').strip() or hoje()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', data):
        raise ErroKwai('Data inválida (use AAAA-MM-DD).')
    try:
        time.strptime(data, '%Y-%m-%d')
    except ValueError:
        raise ErroKwai('Data inválida (use AAAA-MM-DD).') from None
    return data


def hoje() -> str:
    return time.strftime('%Y-%m-%d', time.localtime())


def _dia(ts: float) -> str:
    return time.strftime('%Y-%m-%d', time.localtime(ts))


def _corte_do_post(p: dict) -> dict | None:
    try:
        import agente as ag
        cortes = ag.estado()['cortes']
    except Exception:  # noqa: BLE001
        return None
    return next((x for x in cortes if x.get('post') == p['id']), None) or next((x for x in cortes if x.get('video') == p['video']), None)


def _item(p: dict) -> dict:
    import descricao as ds
    c = _corte_do_post(p) if str(p.get('origem') or '') not in ('agente3', 'coordenador') else None
    link = ''
    if c:
        try:
            import agente as ag
            link = ag.link_original(c)
        except Exception:  # noqa: BLE001
            link = ''
    titulo = ds.titulo_limpo(p.get('titulo') or (c or {}).get('titulo') or '') or 'Vídeo'
    legenda = (p.get('legenda') or '').strip() or ds.compor(titulo, (c or {}).get('hashtags') or [], link)
    if link:
        legenda = ds.com_link(legenda, link)
    else:   # sem link conhecido: tira o rodapé com o colchete vazio (não serve para nada no Kwai)
        legenda = re.sub(r'\s*(?:\.\s*){3}Link original do vídeo \[\s*\]\s*$', '', legenda).strip() or titulo
    tags = ds.hashtags(re.findall(r'#[\w]+', legenda, flags=re.UNICODE)) or ds.hashtags((c or {}).get('hashtags') or [])
    try:
        arq = pg.video_path(p['video'])
        tem_video = pg.video_pronto(p['video'])
        mb = round(arq.stat().st_size / 1e6, 1)
    except (pg.ErroRede, OSError):
        tem_video, mb = False, 0.0
    return {
        'post': p['id'], 'titulo': titulo, 'descricao': legenda, 'hashtags': tags, 'link_original': link,
        'proprio': str(p.get('origem') or '') in ('agente3', 'coordenador'),
        'quando': p['quando'], 'hora': time.strftime('%H:%M', time.localtime(p['quando'])),
        'redes': {r: x.get('status', '') for r, x in p['redes'].items()},
        'links_redes': {r: x.get('link') for r, x in p['redes'].items() if x.get('link')},
        'kwai_marcado': 'kwai' in p['redes'], 'kwai_feito': (p['redes'].get('kwai') or {}).get('status') == 'postado',
        'tem_video': tem_video, 'mb': mb,
    }


def itens(data: str = '') -> list:
    """Os vídeos do dia (pela hora marcada do post), em ordem de horário."""
    data = data_valida(data)
    return [_item(p) for p in sorted(pg.posts(), key=lambda x: x['quando']) if _dia(p['quando']) == data]


def _links(data: str, its: list) -> dict:
    import autenticacao as au
    return {
        'pagina': au.assinar_url(f'/api/v1/kwai/{data}/pagina', VALIDADE),
        'texto': au.assinar_url(f'/api/v1/kwai/{data}/texto', VALIDADE),
        'zip': au.assinar_url(f'/api/v1/kwai/{data}/zip', VALIDADE),
        'videos': {i['post']: au.assinar_url(f'/api/v1/kwai/video/{i["post"]}', VALIDADE) for i in its if i['tem_video']},
    }


def _endereco() -> str:
    try:
        import agente as ag
        return ag._endereco().rstrip('/')
    except Exception:  # noqa: BLE001
        return ''


def _redes_txt(i: dict) -> str:
    return ', '.join(f'{REDE_NOME.get(r, r)} ({STATUS_NOME.get(s, s)})' for r, s in i['redes'].items()) or '-'


def texto(data: str, its: list, links: dict, base: str) -> str:
    dd = time.strftime('%d/%m/%Y', time.strptime(data, '%Y-%m-%d'))
    linhas = [f'EstúdioClip — pacote do Kwai de {dd}', f'{len(its)} vídeo(s). Copie a descrição de cada um e poste no Kwai.', '']
    for n, i in enumerate(its, 1):
        v = links['videos'].get(i['post'])
        linhas += [
            '=' * 40,
            f'{n}. {i["titulo"]}',
            f'Horário: {i["hora"]} · Redes: {_redes_txt(i)}',
            'Link original: ' + (i['link_original'] or ('vídeo próprio (não tem)' if i['proprio'] else 'não sei de qual vídeo saiu')),
            'Hashtags: ' + (' '.join(i['hashtags']) or '-'),
            'Vídeo: ' + ((base + v) if v and base else 'baixe pelo site (Coordenador > Kwai)' if i['tem_video'] else 'o arquivo não está mais no servidor'),
            '', '--- DESCRIÇÃO (copie daqui) ---', i['descricao'], '--- fim da descrição ---', '',
        ]
    if not its:
        linhas.append('Nenhum vídeo neste dia.')
    linhas.append(f'Os links valem até {time.strftime("%d/%m %H:%M", time.localtime(time.time() + VALIDADE))}, enquanto o servidor não trocar de endereço.')
    return '\r\n'.join('\n'.join(linhas).split('\n')) + '\r\n'


def _ascii(t: str) -> str:
    import unicodedata
    t = unicodedata.normalize('NFKD', str(t or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', re.sub(r'[^A-Za-z0-9\- ]+', '', t)).strip()


def nome_base(n: int, titulo: str) -> str:
    """'01 - Fuga insana no GTA 6': o vídeo e o texto dele ficam com o mesmo nome, um ao lado do outro."""
    return f'{n:02d} - ' + (_ascii(titulo)[:50].strip() or 'video')


def nota(n: int, i: dict) -> str:
    """Texto de um vídeo, para abrir no bloco de notas e copiar: só o que vai no Kwai."""
    linhas = [f'{n}. {i["titulo"]}', '',
              'DESCRIÇÃO (copie tudo abaixo até a linha de traços):', i['descricao'], '-' * 30, '',
              'Hashtags: ' + (' '.join(i['hashtags']) or '-'),
              'Link original: ' + (i['link_original'] or ('vídeo próprio (não tem)' if i['proprio'] else 'não sei de qual vídeo saiu'))]
    return '\r\n'.join('\r\n'.join(x.split('\n')) for x in linhas) + '\r\n'


def montar_zip(data: str = '') -> Path:
    """Um ZIP do dia: cada vídeo com o texto dele do lado (mesmo nome) e um '00 - LEIA PRIMEIRO.txt' com todos os textos.
    Os vídeos entram sem recompressão (já são MP4). Só refaz se algo mudou; ZIPs com mais de 3 dias são apagados."""
    import zipfile
    data = data_valida(data)
    its = itens(data)
    PASTA.mkdir(parents=True, exist_ok=True)
    for velho in PASTA.glob('kwai-*.zip'):
        if velho.stat().st_mtime < time.time() - VALIDADE:
            velho.unlink(missing_ok=True)
    destino = PASTA / f'kwai-{data}.zip'
    conteudo = [(nome_base(n, i['titulo']), i) for n, i in enumerate(its, 1)]
    assinatura = repr([(b, i['descricao'], i['tem_video'], i['mb']) for b, i in conteudo])
    marca = PASTA / f'kwai-{data}.zip.marca'
    if destino.exists() and marca.exists() and marca.read_text(encoding='utf-8') == assinatura:
        return destino
    tmp = destino.with_suffix('.zip.tmp')
    with zipfile.ZipFile(tmp, 'w') as z:
        todos = [f'EstúdioClip - Kwai de {time.strftime("%d/%m/%Y", time.strptime(data, "%Y-%m-%d"))}', f'{len(its)} vídeo(s). Cada vídeo tem um .txt com o mesmo nome.', '']
        for (base, i), n in zip(conteudo, range(1, len(conteudo) + 1)):
            z.writestr(base + '.txt', nota(n, i).encode('utf-8'), zipfile.ZIP_DEFLATED)
            todos += ['=' * 30, nota(n, i).replace('\r\n', '\n')]
            if i['tem_video']:
                try:
                    arq = pg.video_path(next(p['video'] for p in pg.posts() if p['id'] == i['post']))
                    z.write(arq, base + arq.suffix, zipfile.ZIP_STORED)
                except (pg.ErroRede, OSError, StopIteration):
                    pass
        if not its:
            todos.append('Nenhum vídeo neste dia.')
        z.writestr('00 - LEIA PRIMEIRO.txt', '\r\n'.join('\n'.join(todos).split('\n')).encode('utf-8'), zipfile.ZIP_DEFLATED)
    tmp.replace(destino)
    marca.write_text(assinatura, encoding='utf-8')
    return destino


def pagina(data: str, its: list, links: dict) -> str:
    e = html.escape
    dd = time.strftime('%d/%m/%Y', time.strptime(data, '%Y-%m-%d'))
    blocos = []
    for n, i in enumerate(its, 1):
        v = links['videos'].get(i['post'])
        orig = (f'<a href="{e(i["link_original"])}" target="_blank" rel="noopener">{e(i["link_original"])}</a>' if i['link_original']
                else 'vídeo próprio (não tem)' if i['proprio'] else '<b class="bad">não sei de qual vídeo saiu</b>')
        blocos.append(
            f'<section><h2>{n}. {e(i["titulo"])}</h2>'
            f'<p class="m">{e(i["hora"])} · {e(_redes_txt(i))}{" · <b>Kwai já marcado como feito</b>" if i["kwai_feito"] else ""}</p>'
            f'<p><b>Link original:</b> {orig}</p>'
            f'<p><b>Hashtags:</b> {e(" ".join(i["hashtags"]) or "-")}' + (f' <button data-c="h{n}">Copiar hashtags</button>' if i['hashtags'] else '') + '</p>'
            f'<textarea id="h{n}" hidden>{e(" ".join(i["hashtags"]))}</textarea>'
            f'<p><b>Descrição:</b> <button data-c="d{n}">Copiar descrição</button></p><textarea id="d{n}" readonly rows="8">{e(i["descricao"])}</textarea>'
            + (f'<p><a class="b" href="{e(v)}" download>Baixar vídeo ({i["mb"]} MB)</a></p>' if v else '<p class="bad">O arquivo do vídeo não está mais no servidor.</p>')
            + '</section>')
    corpo = ''.join(blocos) or '<p>Nenhum vídeo neste dia.</p>'
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kwai {dd}</title><style>
:root{{color-scheme:light dark;--f:#fff;--t:#16181d;--m:#5b6170;--b:#d8dbe2;--a:#ff6a00}}
@media (prefers-color-scheme:dark){{:root{{--f:#121418;--t:#eef0f4;--m:#9aa1ae;--b:#2a2e36}}}}
body{{margin:0;padding:16px;background:var(--f);color:var(--t);font:16px/1.45 system-ui,sans-serif;max-width:720px;margin:auto}}
h1{{font-size:20px}}h2{{font-size:17px;margin:0 0 6px}}section{{border:1px solid var(--b);border-radius:12px;padding:12px;margin:12px 0}}
.m{{color:var(--m);font-size:14px;margin:0 0 8px}}textarea{{width:100%;box-sizing:border-box;font:inherit;font-size:14px;border:1px solid var(--b);border-radius:8px;padding:8px;background:transparent;color:inherit}}
button,.b{{font:inherit;font-size:14px;border:0;border-radius:8px;padding:8px 12px;background:var(--a);color:#fff;text-decoration:none;display:inline-block}}
a{{color:var(--a);word-break:break-all}}.bad{{color:#d33}}
</style></head><body><h1>Pacote do Kwai · {dd}</h1>
<p class="m">{len(its)} vídeo(s). Para cada um: baixe o vídeo, copie a descrição e poste no Kwai. Os links valem 3 dias.</p>
{(f'<p><a class="b" href="{e(links["zip"])}" download>Baixar tudo (ZIP com vídeos e textos)</a></p>' if its else '')}
{corpo}
<script>document.querySelectorAll('button[data-c]').forEach(b=>b.onclick=async()=>{{const t=document.getElementById(b.dataset.c);
try{{await navigator.clipboard.writeText(t.value)}}catch(_){{t.hidden=false;t.select();document.execCommand('copy')}}b.textContent='Copiado!'}});</script>
</body></html>'''


def montar(data: str = '') -> dict:
    """Gera (de novo) os arquivos do dia e devolve a lista com os links assinados (caminhos relativos ao servidor)."""
    data = data_valida(data)
    its = itens(data)
    links = _links(data, its)
    base = _endereco()
    PASTA.mkdir(parents=True, exist_ok=True)
    (PASTA / f'kwai-{data}.txt').write_text(texto(data, its, links, base), encoding='utf-8')
    (PASTA / f'kwai-{data}.html').write_text(pagina(data, its, links), encoding='utf-8')
    return {'data': data, 'itens': its, 'links': links, 'endereco': base,
            'arquivos': {'texto': str(PASTA / f'kwai-{data}.txt'), 'pagina': str(PASTA / f'kwai-{data}.html')}}


def arquivo(data: str, tipo: str) -> Path:
    """Arquivo do dia para baixar/abrir. Monta na hora (os links dentro dele ficam novos)."""
    data = data_valida(data)
    if tipo == 'zip':
        return montar_zip(data)
    montar(data)
    return PASTA / (f'kwai-{data}.html' if tipo == 'pagina' else f'kwai-{data}.txt')


def video(pid: str) -> tuple[Path, str]:
    p = next((x for x in pg.posts() if x['id'] == pid), None)
    if not p:
        raise ErroKwai('Post não encontrado.')
    import descricao as ds
    arq = pg.video_path(p['video'])
    nome = (_ascii(ds.titulo_limpo(p.get('titulo') or ''))[:60].strip() or 'video') + arq.suffix
    return arq, nome


def enviar(data: str = '', quem: str = 'agente7') -> dict:
    """Manda o aviso do pacote: WhatsApp com o link da página e e-mail com o .txt anexado. Também fica no sino do site."""
    import agente as ag
    r = montar(data)
    its, base = r['itens'], r['endereco']
    if its:
        try:
            montar_zip(r['data'])      # já deixa pronto: o download começa na hora
        except OSError as e:
            print('kwai: zip', e)
    dd = time.strftime('%d/%m', time.strptime(r['data'], '%Y-%m-%d'))
    site = __import__('os').getenv('SITE', 'https://raniere3000-tech.github.io/ia/').rstrip('/') + '/#coordenador/kwai'
    link_pag = (base + r['links']['pagina']) if base else ''
    link_zip = (base + r['links']['zip']) if base and its else ''
    lista = '\n'.join(f'{n}. {i["titulo"][:70]}' for n, i in enumerate(its, 1))
    corpo = (f'{len(its)} vídeo(s) de hoje para postar à mão no Kwai. O arquivo anexo tem o nome, a descrição pronta, as hashtags, '
             f'o link original e o link para baixar cada vídeo.\n\n{lista}\n\n'
             + (f'Baixar tudo de uma vez (ZIP com os vídeos e um texto para cada um, vale 3 dias):\n{link_zip}\n\n' if link_zip else '')
             + (f'Página para abrir no celular (vale 3 dias):\n{link_pag}\n\n' if link_pag else '')
             + f'Ou no site: Coordenador > Kwai\n{site}\n')
    zap = (f'*EstúdioClip — Kwai de {dd}*\n\n{len(its)} vídeo(s) para postar no Kwai:\n{lista}\n\n'
           + (f'Baixar tudo em ZIP (vídeos + texto de cada um):\n{link_zip}\n\n' if link_zip else '')
           + (f'Ou abra a página para copiar as descrições:\n{link_pag}\n\n' if link_pag else '')
           + f'No site: {site}')
    ag.avisar('kwai', f'Pacote do Kwai de {dd} ({len(its)} vídeo(s))', corpo, Path(r['arquivos']['texto']), f'kwai-{r["data"]}.txt',
              zap=zap, zap_tipo='a7_kwai')
    return {'ok': True, 'data': r['data'], 'videos': len(its), 'quem': quem}
