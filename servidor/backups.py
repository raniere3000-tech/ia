"""Backups do servidor (no próprio celular) e diagnóstico.

- Cópia consistente do SQLite (API de backup, sem parar o servidor) + arquivos JSON do agente e da postagem.
- Manifesto com sha256 de cada arquivo; retenção configurável (padrão: 7 diários).
- Os vídeos e assets NÃO entram no zip diário (são grandes). Eles têm um backup próprio, opcional e incremental
  (fazer_midias): cada arquivo é guardado uma vez só, pelo sha256, com manifesto e teste de restauração.
- O cofre (chave mestra e segredos cifrados) entra cifrado como está; a chave mestra NÃO é copiada
  para dentro do backup por padrão (guarde-a à parte, como o README explica).
- Restaurar é sempre para uma pasta de TESTE; trocar os dados de verdade é um passo manual descrito no README.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path

import banco as db
import postagem as pg

PASTA = Path(os.getenv('PASTA_BACKUP', str(pg.DADOS / 'backups')))
MANTER = int(os.getenv('BACKUPS_MANTER', '7'))
NUNCA = {'.chave', 'chave.bin', 'mestra.key'}


def _sha(arq: Path) -> str:
    h = hashlib.sha256()
    with open(arq, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def fazer(motivo: str = 'manual') -> dict:
    PASTA.mkdir(parents=True, exist_ok=True)
    nome = datetime.now().strftime('backup-%Y%m%d-%H%M%S')
    trab = PASTA / (nome + '.trabalho')
    shutil.rmtree(trab, ignore_errors=True)
    trab.mkdir()
    db.copia_consistente(trab / 'studio.sqlite')
    for arq in sorted(pg.DADOS.glob('*.json')):
        if arq.name not in NUNCA:
            shutil.copy2(arq, trab / arq.name)
    manifesto = {'criado': time.time(), 'motivo': motivo, 'arquivos': {}, 'videos': len(list(pg.VIDEOS.glob('*.mp4'))),
                 'assets': (db.um('SELECT COUNT(*) AS n FROM assets') or {'n': 0})['n'], 'versao_banco': db.con().execute('PRAGMA user_version').fetchone()[0]}
    for arq in sorted(trab.iterdir()):
        manifesto['arquivos'][arq.name] = {'sha256': _sha(arq), 'tamanho': arq.stat().st_size}
    (trab / 'manifesto.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=1), encoding='utf-8')
    final = PASTA / (nome + '.zip')
    tmp = PASTA / (nome + '.zip.tmp')
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        for arq in sorted(trab.iterdir()):
            z.write(arq, arq.name)
    tmp.replace(final)
    shutil.rmtree(trab, ignore_errors=True)
    velhos = sorted(PASTA.glob('backup-*.zip'))[:-MANTER] if MANTER > 0 else []
    for v in velhos:
        v.unlink(missing_ok=True)
    db.evento('servidor', 'backup', final.name, {'motivo': motivo, 'tamanho': final.stat().st_size})
    return {'arquivo': final.name, 'tamanho': final.stat().st_size, 'manifesto': manifesto}


def listar() -> list:
    PASTA.mkdir(parents=True, exist_ok=True)
    return [{'arquivo': a.name, 'tamanho': a.stat().st_size, 'criado': a.stat().st_mtime} for a in sorted(PASTA.glob('backup-*.zip'), reverse=True)]


def testar_restauracao(nome: str) -> dict:
    """Abre o backup numa pasta de teste, confere os sha256 e se o banco abre e responde. Não toca nos dados reais."""
    arq = PASTA / Path(nome).name
    if not arq.exists():
        raise FileNotFoundError('Backup não encontrado.')
    destino = PASTA / 'teste-restauracao'
    shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir()
    with zipfile.ZipFile(arq) as z:
        for n in z.namelist():
            if '/' in n or '\\' in n or n.startswith('.'):
                raise ValueError('Backup com caminho estranho: ' + n)
        z.extractall(destino)
    man = json.loads((destino / 'manifesto.json').read_text(encoding='utf-8'))
    erros = [n for n, info in man['arquivos'].items() if not (destino / n).exists() or _sha(destino / n) != info['sha256']]
    import sqlite3
    c = sqlite3.connect(destino / 'studio.sqlite')
    try:
        ok_banco = c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        projetos = c.execute('SELECT COUNT(*) FROM projetos').fetchone()[0]
    finally:
        c.close()
    return {'ok': not erros and ok_banco, 'erros': erros, 'banco_ok': ok_banco, 'projetos': projetos, 'pasta': str(destino)}


def _memoria_mb() -> float | None:
    """Memória usada pelo servidor agora (lida do próprio sistema; None se não der para ler)."""
    try:
        for ln in open('/proc/self/status', encoding='utf-8'):
            if ln.startswith('VmRSS:'):
                return round(int(ln.split()[1]) / 1024, 1)
    except OSError:
        pass
    return None


def _temperatura() -> float | None:
    """Temperatura do aparelho só se o Android deixar ler (muitos não deixam). Nunca inventa um número."""
    for z in sorted(Path('/sys/class/thermal').glob('thermal_zone*/temp'))[:12]:
        try:
            v = int(z.read_text().strip())
        except (OSError, ValueError):
            continue
        c = v / 1000 if v > 1000 else v
        if 15 <= c <= 110:
            return round(c, 1)
    return None


def motores() -> list:
    """Quanto tempo o celular leva por segundo de vídeo em cada estilo (medido de verdade nas últimas 20 cenas),
    e quantas correções o diretor de qualidade fez e quantas falhas de FFmpeg houve na última semana."""
    out = []
    for r in db.todos("SELECT etapa, SUM(segundos) AS s, SUM(unidades) AS u, COUNT(*) AS n FROM (SELECT * FROM medidas WHERE etapa LIKE 'render_cena_%' ORDER BY id DESC LIMIT 400) GROUP BY etapa"):
        if r['u']:
            out.append({'estilo': r['etapa'].replace('render_cena_', ''), 'seg_por_seg': round(r['s'] / r['u'], 2), 'cenas': r['n']})
    semana = time.time() - 7 * 86400
    corr = (db.um("SELECT COUNT(*) AS n FROM eventos WHERE acao='qualidade_corrigiu' AND t>?", semana) or {'n': 0})['n']
    falhas = (db.um("SELECT COUNT(*) AS n FROM eventos WHERE detalhe LIKE '%FFmpeg%' AND t>?", semana) or {'n': 0})['n']
    return sorted(out, key=lambda x: -x['cenas']) + [{'estilo': '_resumo', 'correcoes_qualidade': corr, 'falhas_ffmpeg': falhas}]


def diagnostico() -> dict:
    import fila
    import renderizador as rd
    jobs = db.todos('SELECT status, COUNT(*) AS n FROM jobs GROUP BY status')
    ult = db.todos("SELECT t, ator, acao, recurso FROM eventos WHERE acao LIKE '%falh%' OR acao LIKE '%erro%' ORDER BY n DESC LIMIT 10")
    return {'ffmpeg': rd.tem_ffmpeg(), 'livre_mb': rd.livre_mb(pg.DADOS), 'minimo_mb': rd.MIN_LIVRE_MB, 'capacidade': fila.capacidade(),
            'motores': motores(), 'memoria_mb': _memoria_mb(), 'temperatura': _temperatura(),
            'jobs': {j['status']: j['n'] for j in jobs}, 'falhas_recentes': ult, 'backups': listar()[:3],
            'banco': {'arquivo': str(db.ARQ), 'tamanho': db.ARQ.stat().st_size if db.ARQ.exists() else 0}}


def iniciar():
    def laco():
        while True:
            try:
                ult = listar()
                if not ult or time.time() - ult[0]['criado'] > 86400:
                    fazer('diário')
                    if config_midias()['ligado']:
                        fazer_midias('diário')
            except Exception as e:  # noqa: BLE001
                print('backup:', e)
            time.sleep(3600)
    threading.Thread(target=laco, daemon=True, name='backup').start()


# ---------------------------------------------------------------- backup das mídias importantes (opcional, incremental)
CATEGORIAS = {'finais': 'Vídeos finais aprovados ou prontos', 'audios': 'Narrações e áudios', 'imagens': 'Fotos e imagens das cenas'}
PADRAO_MIDIAS = {'ligado': False, 'categorias': ['finais', 'audios'], 'destino': ''}


def _destino(cfg: dict) -> Path:
    d = (cfg.get('destino') or '').strip()
    return Path(d).expanduser() if d else PASTA / 'midias'


def config_midias() -> dict:
    c = {**PADRAO_MIDIAS, **(db.kv('backup_midias', {}) or {})}
    c['categorias'] = [x for x in c['categorias'] if x in CATEGORIAS]
    return c


def salvar_config_midias(d: dict) -> dict:
    c = config_midias()
    if 'ligado' in d:
        c['ligado'] = bool(d['ligado'])
    if isinstance(d.get('categorias'), list):
        c['categorias'] = [x for x in d['categorias'] if x in CATEGORIAS]
    if 'destino' in d:
        dest = str(d.get('destino') or '').strip()
        if dest:
            p = Path(dest).expanduser()
            casa = Path.home().resolve()
            ok = p.is_absolute() and (str(p.resolve()).startswith(str(casa)) or str(p).startswith(('/sdcard', '/storage')))
            if not ok:
                raise ValueError('Escolha uma pasta dentro do Termux (~) ou do armazenamento do celular (/sdcard ou /storage).')
        c['destino'] = dest
    db.kv_gravar('backup_midias', c)
    return estado_midias()


def _midias(categorias: list) -> list:
    """Lista o que entra no backup: cada item com sha256, tamanho, caminho, projeto e categoria."""
    out, vistos = [], set()
    if 'finais' in categorias:
        for r in db.todos('SELECT projeto, arquivo, sha256, versao FROM renders WHERE validado=1'):
            a = Path(r['arquivo'] or '')
            if r['sha256'] and r['sha256'] not in vistos and a.exists():
                vistos.add(r['sha256'])
                out.append({'sha256': r['sha256'], 'tamanho': a.stat().st_size, 'caminho': str(a), 'projeto': r['projeto'], 'nome': f'final-v{r["versao"]}{a.suffix}', 'categoria': 'finais'})
    for r in db.todos('SELECT projeto, nome, mime, sha256, caminho, tamanho FROM assets'):
        cat = 'audios' if (r['mime'] or '').startswith('audio/') else 'imagens' if (r['mime'] or '').startswith('image/') else ''
        if cat in categorias and r['sha256'] and r['sha256'] not in vistos:
            vistos.add(r['sha256'])
            out.append({'sha256': r['sha256'], 'tamanho': r['tamanho'] or 0, 'caminho': r['caminho'], 'projeto': r['projeto'], 'nome': r['nome'], 'categoria': cat})
    return out


def estado_midias() -> dict:
    c = config_midias()
    dest = _destino(c)
    tudo = _midias(list(CATEGORIAS))
    por = {k: {'nome': v, 'arquivos': 0, 'mb': 0.0} for k, v in CATEGORIAS.items()}
    for m in tudo:
        por[m['categoria']]['arquivos'] += 1
        por[m['categoria']]['mb'] += m['tamanho'] / 1048576
    escolhidas = [m for m in tudo if m['categoria'] in c['categorias']]
    ja = sum(1 for m in escolhidas if (dest / 'objetos' / m['sha256'][:2] / m['sha256']).exists())
    falta_mb = sum(m['tamanho'] for m in escolhidas if not (dest / 'objetos' / m['sha256'][:2] / m['sha256']).exists()) / 1048576
    mesmo = not str(dest).startswith(('/sdcard', '/storage'))
    manis = sorted(dest.glob('manifesto-*.json'), reverse=True) if dest.exists() else []
    return {'config': c, 'destino': str(dest), 'categorias': por, 'escolhidos': len(escolhidas), 'ja_copiados': ja, 'falta_mb': round(falta_mb, 1),
            'livre_mb': __import__('renderizador').livre_mb(dest if dest.exists() else PASTA), 'mesmo_aparelho': mesmo,
            'ultimos': [{'arquivo': m.name, 'criado': m.stat().st_mtime} for m in manis[:3]]}


def fazer_midias(motivo: str = 'manual') -> dict:
    """Copia só o que ainda não está no destino (endereçado pelo sha256: o mesmo arquivo nunca é copiado duas vezes)
    e grava um manifesto com o que este backup cobre."""
    c = config_midias()
    dest = _destino(c)
    (dest / 'objetos').mkdir(parents=True, exist_ok=True)
    itens = _midias(c['categorias'])
    precisa = sum(m['tamanho'] for m in itens if not (dest / 'objetos' / m['sha256'][:2] / m['sha256']).exists()) / 1048576
    import renderizador as rd
    livre = rd.livre_mb(dest)
    if 0 <= livre < precisa + rd.MIN_LIVRE_MB:
        raise OSError(f'Falta espaço: o backup precisa de {precisa:.0f} MB e o destino tem {livre} MB livres (fora a reserva de {rd.MIN_LIVRE_MB} MB).')
    novos, ja, faltando = 0, 0, []
    for m in itens:
        alvo = dest / 'objetos' / m['sha256'][:2] / m['sha256']
        if alvo.exists():
            ja += 1
            continue
        orig = Path(m['caminho'])
        if not orig.exists():
            faltando.append(m['nome'])
            continue
        alvo.parent.mkdir(parents=True, exist_ok=True)
        tmp = alvo.with_suffix('.tmp')
        shutil.copy2(orig, tmp)
        if _sha(tmp) != m['sha256']:
            tmp.unlink(missing_ok=True)
            faltando.append(m['nome'] + ' (mudou desde que foi registrado)')
            continue
        tmp.replace(alvo)
        novos += 1
    nome = datetime.now().strftime('manifesto-%Y%m%d-%H%M%S.json')
    man = {'criado': time.time(), 'motivo': motivo, 'categorias': c['categorias'],
           'itens': [{k: m[k] for k in ('sha256', 'tamanho', 'projeto', 'nome', 'categoria')} | {'caminho': m['caminho']} for m in itens if m['nome'] not in faltando]}
    (dest / nome).write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding='utf-8')
    for velho in sorted(dest.glob('manifesto-*.json'))[:-MANTER]:
        velho.unlink(missing_ok=True)
    db.evento('servidor', 'backup_midias', nome, {'novos': novos, 'ja': ja, 'faltando': len(faltando)})
    return {'manifesto': nome, 'novos': novos, 'ja_existiam': ja, 'faltando': faltando, 'destino': str(dest)}


def testar_midias(nome: str = '') -> dict:
    """Confere um manifesto: cada arquivo existe no destino e o sha256 bate. Restaura numa pasta de TESTE e
    aponta referências do banco que estão sem arquivo. Nunca diz 'ok' se faltar alguma mídia."""
    dest = _destino(config_midias())
    manis = sorted(dest.glob('manifesto-*.json'), reverse=True)
    if nome:
        manis = [m for m in manis if m.name == Path(nome).name]
    if not manis:
        raise FileNotFoundError('Nenhum backup de mídias ainda.')
    man = json.loads(manis[0].read_text(encoding='utf-8'))
    teste = PASTA / 'teste-midias'
    shutil.rmtree(teste, ignore_errors=True)
    teste.mkdir(parents=True)
    ruins, ok_n = [], 0
    for it in man['itens']:
        obj = dest / 'objetos' / it['sha256'][:2] / it['sha256']
        if not obj.exists():
            ruins.append(f'{it["nome"]}: não está no backup')
            continue
        saida = teste / (it['projeto'] or 'sem-projeto') / Path(it['nome']).name
        saida.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(obj, saida)
        if _sha(saida) != it['sha256']:
            ruins.append(f'{it["nome"]}: arquivo corrompido')
        else:
            ok_n += 1
    sem_arquivo = [a['nome'] for a in db.todos('SELECT nome, caminho FROM assets') if not Path(a['caminho'] or '').exists()][:20]
    shutil.rmtree(teste, ignore_errors=True)
    return {'ok': not ruins, 'conferidos': ok_n, 'problemas': ruins[:30], 'manifesto': manis[0].name, 'referencias_sem_arquivo': sem_arquivo}
