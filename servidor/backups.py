"""Backups do servidor (no próprio celular) e diagnóstico.

- Cópia consistente do SQLite (API de backup, sem parar o servidor) + arquivos JSON do agente e da postagem.
- Manifesto com sha256 de cada arquivo; retenção configurável (padrão: 7 diários).
- Os vídeos e assets NÃO entram (são grandes); o manifesto lista quantos existem.
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


def diagnostico() -> dict:
    import fila
    import renderizador as rd
    jobs = db.todos('SELECT status, COUNT(*) AS n FROM jobs GROUP BY status')
    ult = db.todos("SELECT t, ator, acao, recurso FROM eventos WHERE acao LIKE '%falh%' OR acao LIKE '%erro%' ORDER BY n DESC LIMIT 10")
    return {'ffmpeg': rd.tem_ffmpeg(), 'livre_mb': rd.livre_mb(pg.DADOS), 'minimo_mb': rd.MIN_LIVRE_MB, 'capacidade': fila.capacidade(),
            'jobs': {j['status']: j['n'] for j in jobs}, 'falhas_recentes': ult, 'backups': listar()[:3],
            'banco': {'arquivo': str(db.ARQ), 'tamanho': db.ARQ.stat().st_size if db.ARQ.exists() else 0}}


def iniciar():
    def laco():
        while True:
            try:
                ult = listar()
                if not ult or time.time() - ult[0]['criado'] > 86400:
                    fazer('diário')
            except Exception as e:  # noqa: BLE001
                print('backup:', e)
            time.sleep(3600)
    threading.Thread(target=laco, daemon=True, name='backup').start()
