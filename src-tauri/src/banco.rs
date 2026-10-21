use crate::config;
use rusqlite::Connection;
use std::path::Path;

pub const ESQUEMA: &str = r#"
CREATE TABLE IF NOT EXISTS demandas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo          TEXT NOT NULL,
    descricao       TEXT NOT NULL DEFAULT '',
    entregavel      TEXT NOT NULL DEFAULT '',
    ente            TEXT NOT NULL DEFAULT '',
    tipo            TEXT NOT NULL DEFAULT 'Expediente',
    prioridade      TEXT NOT NULL DEFAULT 'Média',
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

CREATE INDEX IF NOT EXISTS idx_demandas_status ON demandas(status);
CREATE INDEX IF NOT EXISTS idx_demandas_prazo ON demandas(prazo);
CREATE INDEX IF NOT EXISTS idx_historico_demanda ON historico(demanda_id);
CREATE INDEX IF NOT EXISTS idx_anexos_demanda ON anexos(demanda_id);
"#;

pub fn conectar() -> Result<Connection, rusqlite::Error> {
    let caminho = config::get_db_path();
    conectar_em(&caminho)
}

pub fn conectar_em(caminho: &Path) -> Result<Connection, rusqlite::Error> {
    if let Some(parent) = caminho.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let conn = Connection::open(caminho)?;
    conn.execute_batch("PRAGMA foreign_keys = ON;")?;
    conn.execute_batch(ESQUEMA)?;

    // Migração de schema: garante a coluna email_corpo
    let tem_email_corpo = {
        let mut stmt = conn.prepare("PRAGMA table_info(demandas)")?;
        let colunas = stmt.query_map([], |row| {
            let nome: String = row.get(1)?;
            Ok(nome)
        })?;

        let mut achou = false;
        for col in colunas.flatten() {
            if col == "email_corpo" {
                achou = true;
                break;
            }
        }
        achou
    };

    if !tem_email_corpo {
        let _ = conn
            .execute_batch("ALTER TABLE demandas ADD COLUMN email_corpo TEXT NOT NULL DEFAULT '';");
    }

    Ok(conn)
}
