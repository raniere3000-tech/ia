"""Banco de dados do servidor (SQLite no próprio celular): projetos, versões, arquivos, fila, aprovações.

Só biblioteca padrão. Modo WAL, transações curtas, uma conexão por thread.
O esquema é versionado (PRAGMA user_version): cada versão nova só ACRESCENTA tabelas/colunas,
nunca apaga dados de quem já usa.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import postagem as pg

PASTA = pg.DADOS / 'database'
ARQ = Path(os.getenv('BANCO_ARQ', str(PASTA / 'studio.sqlite')))
PROJETOS = pg.DADOS / 'projects'
_local = threading.local()
_LOCK_ESCRITA = threading.RLock()   # um escritor por vez (SQLite gosta assim)

ESQUEMA = [
    # 1: base
    """
    CREATE TABLE IF NOT EXISTS sessoes (id TEXT PRIMARY KEY, nome TEXT, token_hash TEXT UNIQUE, criado REAL, visto REAL,
        expira REAL, revogado INTEGER DEFAULT 0, origem TEXT);
    CREATE TABLE IF NOT EXISTS pareamentos (codigo_hash TEXT PRIMARY KEY, nome TEXT, criado REAL, expira REAL, usado REAL);
    CREATE TABLE IF NOT EXISTS projetos (id TEXT PRIMARY KEY, titulo TEXT, tipo TEXT, modo TEXT, status TEXT, revisao INTEGER,
        schema INTEGER, dados TEXT, criado REAL, atualizado REAL, dispositivo TEXT, origem TEXT, origem_chave TEXT, apagado INTEGER DEFAULT 0);
    CREATE INDEX IF NOT EXISTS projetos_tipo ON projetos(tipo, atualizado);
    CREATE INDEX IF NOT EXISTS projetos_origem ON projetos(origem_chave);
    CREATE TABLE IF NOT EXISTS versoes (projeto TEXT, revisao INTEGER, dados TEXT, criado REAL, dispositivo TEXT, origem TEXT,
        PRIMARY KEY(projeto, revisao));
    CREATE TABLE IF NOT EXISTS assets (id TEXT PRIMARY KEY, projeto TEXT, nome TEXT, mime TEXT, tamanho INTEGER, sha256 TEXT,
        caminho TEXT, criado REAL, origem TEXT);
    CREATE INDEX IF NOT EXISTS assets_sha ON assets(sha256);
    CREATE TABLE IF NOT EXISTS uploads (id TEXT PRIMARY KEY, projeto TEXT, nome TEXT, mime TEXT, tamanho INTEGER, sha256 TEXT,
        recebido INTEGER, criado REAL);
    CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, agente TEXT, tipo TEXT, projeto TEXT, titulo TEXT, status TEXT,
        run_at REAL, prioridade INTEGER DEFAULT 0, recurso TEXT, tentativas INTEGER DEFAULT 0, max_tentativas INTEGER DEFAULT 3,
        proxima REAL DEFAULT 0, lease REAL DEFAULT 0, heartbeat REAL DEFAULT 0, progresso REAL DEFAULT 0, etapa TEXT,
        criado REAL, iniciado REAL, terminado REAL, erro TEXT, dados TEXT, resultado TEXT, chave TEXT UNIQUE,
        pausado INTEGER DEFAULT 0, cancelar INTEGER DEFAULT 0, espera_api REAL DEFAULT 0, decorrido REAL DEFAULT 0);
    CREATE INDEX IF NOT EXISTS jobs_fila ON jobs(status, recurso, run_at);
    CREATE TABLE IF NOT EXISTS agendas (id TEXT PRIMARY KEY, nome TEXT, dias TEXT, hora TEXT, quantidade INTEGER, ativo INTEGER,
        proxima REAL, briefing TEXT, criado REAL);
    CREATE TABLE IF NOT EXISTS renders (id TEXT PRIMARY KEY, projeto TEXT, versao INTEGER, arquivo TEXT, sha256 TEXT, duracao REAL,
        codec TEXT, largura INTEGER, altura INTEGER, validado INTEGER, alertas TEXT, criado REAL);
    CREATE TABLE IF NOT EXISTS aprovacoes (id TEXT PRIMARY KEY, projeto TEXT, render_sha TEXT, decisao TEXT, origem TEXT, por TEXT,
        texto TEXT, destinos TEXT, publicar_em REAL, criado REAL, chave TEXT UNIQUE);
    CREATE TABLE IF NOT EXISTS desafios (id TEXT PRIMARY KEY, projeto TEXT, render_sha TEXT, codigo_hash TEXT, expira REAL,
        usado REAL, erros INTEGER DEFAULT 0, message_id TEXT, criado REAL);
    CREATE TABLE IF NOT EXISTS publicacoes (id TEXT PRIMARY KEY, aprovacao TEXT, render_sha TEXT, post TEXT, rede TEXT,
        chave TEXT UNIQUE, criado REAL);
    CREATE TABLE IF NOT EXISTS eventos (n INTEGER PRIMARY KEY AUTOINCREMENT, t REAL, ator TEXT, acao TEXT, recurso TEXT, detalhe TEXT);
    CREATE TABLE IF NOT EXISTS custos (id INTEGER PRIMARY KEY AUTOINCREMENT, job TEXT, provedor TEXT, modelo TEXT, etapa TEXT,
        estimado REAL, real REAL, moeda TEXT, t REAL);
    CREATE TABLE IF NOT EXISTS medidas (id INTEGER PRIMARY KEY AUTOINCREMENT, etapa TEXT, segundos REAL, unidades REAL, t REAL);
    CREATE TABLE IF NOT EXISTS kv (chave TEXT PRIMARY KEY, valor TEXT);
    CREATE TABLE IF NOT EXISTS emails_lidos (message_id TEXT PRIMARY KEY, t REAL, resultado TEXT);
    """,
    # 2: biblioteca de skills (só acrescenta)
    """
    CREATE TABLE IF NOT EXISTS skills_catalogo (id TEXT PRIMARY KEY, nome TEXT NOT NULL, origem_url TEXT NOT NULL, arquivo_origem TEXT NOT NULL,
        commit_sha TEXT NOT NULL, sha256 TEXT NOT NULL, categoria TEXT NOT NULL, tipo TEXT NOT NULL, estado TEXT NOT NULL, licenca TEXT,
        versao TEXT, deps_json TEXT NOT NULL DEFAULT '[]', capacidades_json TEXT NOT NULL DEFAULT '[]', atualizado REAL,
        ativa INTEGER NOT NULL DEFAULT 1, motivo TEXT, ultimo_teste REAL, versao_anterior TEXT, regras_json TEXT NOT NULL DEFAULT '{}');
    CREATE TABLE IF NOT EXISTS skills_perfis (id TEXT PRIMARY KEY, agente TEXT NOT NULL, tipo_tarefa TEXT NOT NULL,
        skills_json TEXT NOT NULL DEFAULT '[]', limite INTEGER NOT NULL DEFAULT 4, versao INTEGER NOT NULL DEFAULT 1, ligado INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS skills_ativacoes (id TEXT PRIMARY KEY, skill_id TEXT NOT NULL, job_id TEXT, projeto_id TEXT, origem TEXT NOT NULL,
        resultado TEXT, custo REAL, t REAL NOT NULL);
    CREATE INDEX IF NOT EXISTS skills_ativacoes_job ON skills_ativacoes (job_id);
    CREATE INDEX IF NOT EXISTS skills_ativacoes_projeto ON skills_ativacoes (projeto_id);
    """,
    # 3: séries animadas (só acrescenta)
    """
    CREATE TABLE IF NOT EXISTS series (id TEXT PRIMARY KEY, titulo TEXT NOT NULL, dados TEXT NOT NULL DEFAULT '{}', versao INTEGER NOT NULL DEFAULT 1,
        criado REAL, atualizado REAL);
    CREATE TABLE IF NOT EXISTS temporadas (id TEXT PRIMARY KEY, serie_id TEXT NOT NULL, ordem INTEGER NOT NULL, titulo TEXT, arco TEXT, metas TEXT, criado REAL);
    CREATE TABLE IF NOT EXISTS episodios (id TEXT PRIMARY KEY, serie_id TEXT NOT NULL, temporada_id TEXT, ordem INTEGER NOT NULL, titulo TEXT, resumo TEXT,
        projeto_id TEXT, criado REAL, atualizado REAL);
    CREATE TABLE IF NOT EXISTS personagens (id TEXT PRIMARY KEY, serie_id TEXT, nome TEXT NOT NULL, dados TEXT NOT NULL, versao INTEGER NOT NULL DEFAULT 1,
        aprovado INTEGER NOT NULL DEFAULT 0, criado REAL, atualizado REAL);
    CREATE TABLE IF NOT EXISTS personagens_versoes (personagem_id TEXT NOT NULL, versao INTEGER NOT NULL, dados TEXT NOT NULL, t REAL,
        PRIMARY KEY (personagem_id, versao));
    CREATE TABLE IF NOT EXISTS cenarios (id TEXT PRIMARY KEY, serie_id TEXT, nome TEXT NOT NULL, dados TEXT NOT NULL, versao INTEGER NOT NULL DEFAULT 1,
        criado REAL, atualizado REAL);
    CREATE TABLE IF NOT EXISTS biblia (id TEXT PRIMARY KEY, serie_id TEXT NOT NULL, tipo TEXT NOT NULL, alvo TEXT, texto TEXT NOT NULL,
        episodio_id TEXT, estado TEXT NOT NULL, substitui TEXT, criado REAL);
    CREATE INDEX IF NOT EXISTS episodios_serie ON episodios (serie_id, ordem);
    CREATE INDEX IF NOT EXISTS biblia_serie ON biblia (serie_id, estado);
    """,
    # 4: skills ligadas ao que cada agente produz (lote 2, K1–K5; só acrescenta)
    """
    ALTER TABLE skills_ativacoes ADD COLUMN perfil TEXT;
    ALTER TABLE skills_ativacoes ADD COLUMN etapa TEXT;
    ALTER TABLE skills_ativacoes ADD COLUMN versao TEXT;
    ALTER TABLE skills_ativacoes ADD COLUMN artefato TEXT;
    ALTER TABLE skills_ativacoes ADD COLUMN decisao TEXT;
    ALTER TABLE skills_ativacoes ADD COLUMN chars INTEGER;
    ALTER TABLE skills_perfis ADD COLUMN config_json TEXT NOT NULL DEFAULT '{}';
    CREATE TABLE IF NOT EXISTS skills_manifestos (sha256 TEXT PRIMARY KEY, versao TEXT, total INTEGER, fonte TEXT, conteudo TEXT NOT NULL, t REAL);
    CREATE INDEX IF NOT EXISTS skills_ativacoes_etapa ON skills_ativacoes (etapa, t);
    """,
    # 5: núcleo criativo (biblioteca compartilhada e propostas da Modelagem com IA; só acrescenta)
    """
    CREATE TABLE IF NOT EXISTS criativo_assets (id TEXT PRIMARY KEY, tipo TEXT NOT NULL, nome TEXT NOT NULL, descricao TEXT, dados TEXT NOT NULL,
        origem TEXT NOT NULL, status TEXT NOT NULL, versao INTEGER NOT NULL DEFAULT 1, hash TEXT, proveniencia TEXT, modalidades TEXT,
        escopo TEXT NOT NULL DEFAULT 'servidor', schema_version INTEGER NOT NULL DEFAULT 1, criado REAL, atualizado REAL);
    CREATE TABLE IF NOT EXISTS criativo_assets_versoes (asset_id TEXT NOT NULL, versao INTEGER NOT NULL, dados TEXT NOT NULL, hash TEXT, t REAL, por TEXT,
        PRIMARY KEY (asset_id, versao));
    CREATE TABLE IF NOT EXISTS criativo_propostas (id TEXT PRIMARY KEY, lote TEXT, tipo TEXT, contexto TEXT, status TEXT NOT NULL, revisao INTEGER NOT NULL,
        dados TEXT NOT NULL, schema_version INTEGER NOT NULL DEFAULT 1, criado REAL, atualizado REAL);
    CREATE INDEX IF NOT EXISTS criativo_assets_tipo ON criativo_assets (tipo, status);
    CREATE INDEX IF NOT EXISTS criativo_assets_hash ON criativo_assets (hash);
    CREATE INDEX IF NOT EXISTS criativo_propostas_atual ON criativo_propostas (atualizado);
    """,
]


def con() -> sqlite3.Connection:
    c = getattr(_local, 'c', None)
    if c is None:
        ARQ.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(ARQ), timeout=15, isolation_level=None, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA journal_mode=WAL')
        c.execute('PRAGMA synchronous=NORMAL')
        c.execute('PRAGMA busy_timeout=15000')
        _local.c = c
    return c


@contextmanager
def tx():
    """Transação de escrita curta (BEGIN IMMEDIATE)."""
    with _LOCK_ESCRITA:
        c = con()
        c.execute('BEGIN IMMEDIATE')
        try:
            yield c
            c.execute('COMMIT')
        except BaseException:
            c.execute('ROLLBACK')
            raise


def um(sql: str, *a) -> dict | None:
    r = con().execute(sql, a).fetchone()
    return dict(r) if r else None


def todos(sql: str, *a) -> list[dict]:
    return [dict(r) for r in con().execute(sql, a).fetchall()]


def executar(sql: str, *a) -> int:
    with tx() as c:
        return c.execute(sql, a).rowcount


def migrar():
    ARQ.parent.mkdir(parents=True, exist_ok=True)
    PROJETOS.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(ARQ.parent, 0o700)
    except OSError:
        pass
    c = con()
    v = c.execute('PRAGMA user_version').fetchone()[0]
    if 0 < v < len(ESQUEMA):
        # mudança de estrutura: guarda uma cópia do banco antes (uma por versão), para poder voltar
        copia = ARQ.with_name(f'{ARQ.stem}-antes-v{len(ESQUEMA)}.sqlite')
        if not copia.exists():
            try:
                copia_consistente(copia)
            except (sqlite3.Error, OSError) as e:
                print('banco: cópia antes da migração falhou:', e)
    for i, sql in enumerate(ESQUEMA[v:], start=v + 1):
        with _LOCK_ESCRITA:
            c.executescript(sql)
            c.execute(f'PRAGMA user_version={i}')
    try:
        os.chmod(ARQ, 0o600)
    except OSError:
        pass


def evento(ator: str, acao: str, recurso: str = '', detalhe=None):
    executar('INSERT INTO eventos (t, ator, acao, recurso, detalhe) VALUES (?,?,?,?,?)', time.time(), ator, acao, recurso,
             json.dumps(detalhe, ensure_ascii=False)[:4000] if detalhe is not None else '')


def kv(chave: str, padrao=None):
    r = um('SELECT valor FROM kv WHERE chave=?', chave)
    if not r:
        return padrao
    try:
        return json.loads(r['valor'])
    except ValueError:
        return padrao


def kv_gravar(chave: str, valor):
    executar('INSERT INTO kv (chave, valor) VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor', chave, json.dumps(valor, ensure_ascii=False))


def copia_consistente(destino: Path):
    """Cópia do banco sem parar o servidor (API de backup do SQLite)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    alvo = sqlite3.connect(str(destino))
    with _LOCK_ESCRITA:
        con().backup(alvo)
    alvo.close()
