"""Conexão SQLite, criação de tabelas e migrações.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from . import config

ESQUEMA: str = """
CREATE TABLE IF NOT EXISTS demandas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo          TEXT NOT NULL,
    descricao       TEXT NOT NULL DEFAULT '',
    entregavel      TEXT NOT NULL DEFAULT '',
    ente            TEXT NOT NULL DEFAULT '',
    tipo            TEXT NOT NULL DEFAULT 'Expediente',
    prioridade      TEXT NOT NULL DEFAULT 'Média',
    tipo_atendimento TEXT NOT NULL DEFAULT 'Encaminhar',
    status          TEXT NOT NULL DEFAULT 'Novo',
    responsavel     TEXT NOT NULL DEFAULT '',
    processo_sei    TEXT NOT NULL DEFAULT '',
    remetente       TEXT NOT NULL DEFAULT '',
    remetente_email TEXT NOT NULL DEFAULT '',
    origem          TEXT NOT NULL DEFAULT 'manual' CHECK (origem IN ('manual', 'email')),
    email_id        TEXT UNIQUE,
    email_corpo     TEXT NOT NULL DEFAULT '',
    recebido_em     TEXT,
    prazo           TEXT,
    prazo_interno   TEXT,
    concluido_em    TEXT,
    criado_em       TEXT NOT NULL,
    atualizado_em   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS historico (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    demanda_id  INTEGER NOT NULL REFERENCES demandas(id) ON DELETE CASCADE,
    momento     TEXT NOT NULL,
    acao        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS anexos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    demanda_id    INTEGER NOT NULL REFERENCES demandas(id) ON DELETE CASCADE,
    nome          TEXT NOT NULL,
    caminho       TEXT NOT NULL,
    tamanho       INTEGER NOT NULL DEFAULT 0,
    adicionado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS andamentos (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    demanda_id     INTEGER NOT NULL REFERENCES demandas(id) ON DELETE CASCADE,
    momento        TEXT NOT NULL,
    tipo           TEXT NOT NULL,
    destinatario   TEXT NOT NULL DEFAULT '',
    descricao      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_demandas_status ON demandas(status);
CREATE INDEX IF NOT EXISTS idx_demandas_prazo ON demandas(prazo);
CREATE INDEX IF NOT EXISTS idx_historico_demanda ON historico(demanda_id);
CREATE INDEX IF NOT EXISTS idx_anexos_demanda ON anexos(demanda_id);
CREATE INDEX IF NOT EXISTS idx_andamentos_demanda ON andamentos(demanda_id);
"""


def conectar() -> sqlite3.Connection:
    """Abre a conexão com o banco padrão do sistema (`dados/gestao.db`)."""
    return conectar_em(config.get_db_path())


def conectar_em(caminho: str | Path) -> sqlite3.Connection:
    """Abre (criando se necessário) o banco no caminho indicado."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(caminho))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(ESQUEMA)

    # Migrações aditivas mantêm bancos existentes compatíveis.
    colunas = {linha["name"] for linha in conn.execute("PRAGMA table_info(demandas)")}
    if "email_corpo" not in colunas:
        conn.execute(
            "ALTER TABLE demandas ADD COLUMN email_corpo TEXT NOT NULL DEFAULT '';"
        )
    if "tipo_atendimento" not in colunas:
        conn.execute(
            "ALTER TABLE demandas ADD COLUMN tipo_atendimento "
            "TEXT NOT NULL DEFAULT 'Encaminhar';"
        )

    conn.commit()
    return conn
