use chrono::{Duration, Local, NaiveDate};
use rusqlite::{params, Connection, Row};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use crate::config::{self, DIAS_ALERTA_PRAZO, STATUS_FINAIS};
use crate::models::{Anexo, ContagemItem, Demanda, Estatisticas, FiltroDemandas, FormDemanda, Historico};

pub fn agora_iso() -> String {
    Local::now().format("%Y-%m-%dT%H:%M:%S").to_string()
}

pub fn hoje_date() -> NaiveDate {
    Local::now().date_naive()
}

pub fn formatar_data_br(iso: &str) -> String {
    if let Ok(d) = NaiveDate::parse_from_str(iso, "%Y-%m-%d") {
        d.format("%d/%m/%Y").to_string()
    } else {
        iso.to_string()
    }
}

pub fn situacao_prazo(status: &str, prazo: Option<&str>, hoje: NaiveDate) -> String {
    if STATUS_FINAIS.contains(&status) {
        return String::new();
    }
    let Some(prazo_str) = prazo else {
        return String::new();
    };
    if prazo_str.trim().is_empty() {
        return String::new();
    }

    if let Ok(p) = NaiveDate::parse_from_str(prazo_str, "%Y-%m-%d") {
        if p < hoje {
            return "atrasada".to_string();
        }
        if p <= hoje + Duration::days(DIAS_ALERTA_PRAZO) {
            return "vencendo".to_string();
        }
    }
    String::new()
}

fn mapear_demanda(row: &Row) -> Result<Demanda, rusqlite::Error> {
    let status: String = row.get("status")?;
    let prazo: Option<String> = row.get("prazo")?;
    let situacao = situacao_prazo(&status, prazo.as_deref(), hoje_date());

    Ok(Demanda {
        id: row.get("id")?,
        titulo: row.get("titulo")?,
        descricao: row.get("descricao")?,
        entregavel: row.get("entregavel")?,
        ente: row.get("ente")?,
        tipo: row.get("tipo")?,
        prioridade: row.get("prioridade")?,
        status,
        responsavel: row.get("responsavel")?,
        processo_sei: row.get("processo_sei")?,
        remetente: row.get("remetente")?,
        remetente_email: row.get("remetente_email")?,
        origem: row.get("origem")?,
        email_id: row.get("email_id")?,
        email_corpo: row.get("email_corpo")?,
        recebido_em: row.get("recebido_em")?,
        prazo,
        prazo_interno: row.get("prazo_interno")?,
        concluido_em: row.get("concluido_em")?,
        criado_em: row.get("criado_em")?,
        atualizado_em: row.get("atualizado_em")?,
        situacao_prazo: situacao,
    })
}

pub fn registrar_historico(conn: &Connection, demanda_id: i64, acao: &str) -> Result<(), rusqlite::Error> {
    conn.execute(
        "INSERT INTO historico (demanda_id, momento, acao) VALUES (?, ?, ?)",
        params![demanda_id, agora_iso(), acao],
    )?;
    Ok(())
}

pub fn criar_demanda(
    conn: &Connection,
    form: &FormDemanda,
    origem: &str,
    email_id: Option<&str>,
) -> Result<i64, String> {
    let titulo = form.titulo.trim();
    if titulo.is_empty() {
        return Err("Informe o título da demanda.".to_string());
    }

    let momento = agora_iso();
    let concluido_em = if STATUS_FINAIS.contains(&form.status.as_str()) {
        Some(hoje_date().format("%Y-%m-%d").to_string())
    } else {
        None
    };

    conn.execute(
        r#"INSERT INTO demandas (
            titulo, descricao, entregavel, ente, tipo, prioridade, status,
            responsavel, processo_sei, remetente, remetente_email, origem,
            email_id, email_corpo, recebido_em, prazo, prazo_interno,
            concluido_em, criado_em, atualizado_em
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"#,
        params![
            titulo,
            form.descricao.trim(),
            form.entregavel.trim(),
            form.ente.trim(),
            form.tipo.trim(),
            form.prioridade.trim(),
            form.status.trim(),
            form.responsavel.trim(),
            form.processo_sei.trim(),
            form.remetente.trim(),
            form.remetente_email.trim(),
            origem,
            email_id,
            form.email_corpo.trim(),
            form.recebido_em.as_deref(),
            form.prazo.as_deref(),
            form.prazo_interno.as_deref(),
            concluido_em,
            momento,
            momento
        ],
    ).map_err(|e| e.to_string())?;

    let demanda_id = conn.last_insert_rowid();
    let origem_txt = if origem == "email" { "e-mail" } else { "cadastro manual" };
    let _ = registrar_historico(conn, demanda_id, &format!("Demanda criada ({})", origem_txt));

    Ok(demanda_id)
}

pub fn obter_demanda(conn: &Connection, demanda_id: i64) -> Result<Option<Demanda>, rusqlite::Error> {
    let mut stmt = conn.prepare("SELECT * FROM demandas WHERE id = ?")?;
    let mut rows = stmt.query_map([demanda_id], |row| mapear_demanda(row))?;
    if let Some(r) = rows.next() {
        r.map(Some)
    } else {
        Ok(None)
    }
}

pub fn atualizar_demanda(conn: &Connection, demanda_id: i64, form: &FormDemanda) -> Result<(), String> {
    let atual = obter_demanda(conn, demanda_id)
        .map_err(|e| e.to_string())?
        .ok_or_else(|| format!("Demanda #{} não encontrada.", demanda_id))?;

    let titulo = form.titulo.trim();
    if titulo.is_empty() {
        return Err("Informe o título da demanda.".to_string());
    }

    let mut mudancas = Vec::new();

    let checar_campo = |nome: &str, antigo: &str, novo: &str, mudancas: &mut Vec<String>| {
        if antigo != novo {
            mudancas.push(format!("{}: {} -> {}", nome, if antigo.is_empty() { "-" } else { antigo }, if novo.is_empty() { "-" } else { novo }));
        }
    };

    checar_campo("titulo", &atual.titulo, titulo, &mut mudancas);
    checar_campo("descricao", &atual.descricao, form.descricao.trim(), &mut mudancas);
    checar_campo("entregavel", &atual.entregavel, form.entregavel.trim(), &mut mudancas);
    checar_campo("ente", &atual.ente, form.ente.trim(), &mut mudancas);
    checar_campo("tipo", &atual.tipo, form.tipo.trim(), &mut mudancas);
    checar_campo("prioridade", &atual.prioridade, form.prioridade.trim(), &mut mudancas);
    checar_campo("status", &atual.status, form.status.trim(), &mut mudancas);
    checar_campo("responsavel", &atual.responsavel, form.responsavel.trim(), &mut mudancas);
    checar_campo("processo_sei", &atual.processo_sei, form.processo_sei.trim(), &mut mudancas);
    checar_campo("remetente", &atual.remetente, form.remetente.trim(), &mut mudancas);
    checar_campo("remetente_email", &atual.remetente_email, form.remetente_email.trim(), &mut mudancas);
    checar_campo("email_corpo", &atual.email_corpo, form.email_corpo.trim(), &mut mudancas);
    checar_campo("recebido_em", atual.recebido_em.as_deref().unwrap_or(""), form.recebido_em.as_deref().unwrap_or(""), &mut mudancas);
    checar_campo("prazo", atual.prazo.as_deref().unwrap_or(""), form.prazo.as_deref().unwrap_or(""), &mut mudancas);
    checar_campo("prazo_interno", atual.prazo_interno.as_deref().unwrap_or(""), form.prazo_interno.as_deref().unwrap_or(""), &mut mudancas);

    if mudancas.is_empty() {
        return Ok(());
    }

    let concluido_em = if form.status.trim() != atual.status {
        if STATUS_FINAIS.contains(&form.status.trim()) {
            Some(hoje_date().format("%Y-%m-%d").to_string())
        } else {
            None
        }
    } else {
        atual.concluido_em
    };

    let momento = agora_iso();
    conn.execute(
        r#"UPDATE demandas SET
            titulo = ?, descricao = ?, entregavel = ?, ente = ?, tipo = ?,
            prioridade = ?, status = ?, responsavel = ?, processo_sei = ?,
            remetente = ?, remetente_email = ?, email_corpo = ?,
            recebido_em = ?, prazo = ?, prazo_interno = ?, concluido_em = ?,
            atualizado_em = ?
        WHERE id = ?"#,
        params![
            titulo,
            form.descricao.trim(),
            form.entregavel.trim(),
            form.ente.trim(),
            form.tipo.trim(),
            form.prioridade.trim(),
            form.status.trim(),
            form.responsavel.trim(),
            form.processo_sei.trim(),
            form.remetente.trim(),
            form.remetente_email.trim(),
            form.email_corpo.trim(),
            form.recebido_em.as_deref(),
            form.prazo.as_deref(),
            form.prazo_interno.as_deref(),
            concluido_em,
            momento,
            demanda_id
        ],
    ).map_err(|e| e.to_string())?;

    let _ = registrar_historico(conn, demanda_id, &format!("Alterado: {}", mudancas.join("; ")));

    Ok(())
}

pub fn excluir_demanda(conn: &Connection, demanda_id: i64) -> Result<bool, rusqlite::Error> {
    let existe: Option<i64> = conn.query_row(
        "SELECT id FROM demandas WHERE id = ?",
        [demanda_id],
        |r| r.get(0),
    ).ok();

    if existe.is_none() {
        return Ok(false);
    }

    let pasta_anexos = config::get_anexos_dir().join(demanda_id.to_string());
    conn.execute("DELETE FROM demandas WHERE id = ?", [demanda_id])?;

    if pasta_anexos.exists() {
        let _ = std::fs::remove_dir_all(&pasta_anexos);
    }

    Ok(true)
}

pub fn listar_demandas(
    conn: &Connection,
    filtro: &FiltroDemandas,
) -> Result<Vec<Demanda>, rusqlite::Error> {
    let mut sql = "SELECT * FROM demandas WHERE 1 = 1".to_string();
    let mut params_vec: Vec<Box<dyn rusqlite::ToSql>> = Vec::new();

    if let Some(ref st) = filtro.status {
        if !st.trim().is_empty() && st != "Todas" {
            sql.push_str(" AND status = ?");
            params_vec.push(Box::new(st.clone()));
        }
    }

    if filtro.somente_abertas.unwrap_or(false) {
        sql.push_str(" AND status NOT IN ('Concluída', 'Cancelada')");
    }

    if let Some(ref b) = filtro.busca {
        let term = b.trim();
        if !term.is_empty() {
            sql.push_str(" AND (titulo LIKE ? OR ente LIKE ? OR processo_sei LIKE ? OR remetente LIKE ? OR responsavel LIKE ?)");
            let like_str = format!("%{}%", term);
            for _ in 0..5 {
                params_vec.push(Box::new(like_str.clone()));
            }
        }
    }

    if let Some(ref de) = filtro.recebido_de {
        if !de.trim().is_empty() {
            sql.push_str(" AND recebido_em >= ?");
            params_vec.push(Box::new(de.clone()));
        }
    }

    if let Some(ref ate) = filtro.recebido_ate {
        if !ate.trim().is_empty() {
            sql.push_str(" AND recebido_em <= ?");
            params_vec.push(Box::new(ate.clone()));
        }
    }

    sql.push_str(" ORDER BY (prazo IS NULL), prazo, id DESC");

    let params_slice: Vec<&dyn rusqlite::ToSql> = params_vec.iter().map(|b| b.as_ref()).collect();

    let mut stmt = conn.prepare(&sql)?;
    let rows = stmt.query_map(params_slice.as_slice(), |row| mapear_demanda(row))?;

    let mut lista = Vec::new();
    for r in rows {
        lista.push(r?);
    }
    Ok(lista)
}

pub fn historico(conn: &Connection, demanda_id: i64) -> Result<Vec<Historico>, rusqlite::Error> {
    let mut stmt = conn.prepare("SELECT * FROM historico WHERE demanda_id = ? ORDER BY id DESC")?;
    let rows = stmt.query_map([demanda_id], |row| {
        Ok(Historico {
            id: row.get("id")?,
            demanda_id: row.get("demanda_id")?,
            momento: row.get("momento")?,
            acao: row.get("acao")?,
        })
    })?;

    let mut lista = Vec::new();
    for r in rows {
        lista.push(r?);
    }
    Ok(lista)
}

pub fn anexos(conn: &Connection, demanda_id: i64) -> Result<Vec<Anexo>, rusqlite::Error> {
    let mut stmt = conn.prepare("SELECT * FROM anexos WHERE demanda_id = ? ORDER BY id")?;
    let rows = stmt.query_map([demanda_id], |row| {
        Ok(Anexo {
            id: row.get("id")?,
            demanda_id: row.get("demanda_id")?,
            nome: row.get("nome")?,
            caminho: row.get("caminho")?,
            tamanho: row.get("tamanho")?,
            adicionado_em: row.get("adicionado_em")?,
        })
    })?;

    let mut lista = Vec::new();
    for r in rows {
        lista.push(r?);
    }
    Ok(lista)
}

fn destino_unico(pasta: &Path, nome_original: &str) -> PathBuf {
    let mut destino = pasta.join(nome_original);
    if !destino.exists() {
        return destino;
    }

    let stem = Path::new(nome_original)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("arquivo");
    let ext = Path::new(nome_original)
        .extension()
        .and_then(|s| s.to_str())
        .map(|e| format!(".{}", e))
        .unwrap_or_default();

    let mut i = 2;
    loop {
        destino = pasta.join(format!("{} ({}){}", stem, i, ext));
        if !destino.exists() {
            return destino;
        }
        i += 1;
    }
}

pub fn adicionar_anexo(conn: &Connection, demanda_id: i64, origem: &Path) -> Result<i64, String> {
    if !origem.exists() {
        return Err(format!("Arquivo de origem não encontrado: {:?}", origem));
    }

    let nome_arquivo = origem
        .file_name()
        .and_then(|n| n.to_str())
        .ok_or_else(|| "Nome de arquivo inválido".to_string())?;

    let pasta = config::get_anexos_dir().join(demanda_id.to_string());
    std::fs::create_dir_all(&pasta).map_err(|e| e.to_string())?;

    let destino = destino_unico(&pasta, nome_arquivo);
    std::fs::copy(origem, &destino).map_err(|e| e.to_string())?;

    let tamanho = std::fs::metadata(&destino).map(|m| m.len() as i64).unwrap_or(0);
    let dados_dir = config::get_dados_dir();
    let caminho_relativo = destino
        .strip_prefix(&dados_dir)
        .unwrap_or(&destino)
        .to_string_lossy()
        .replace('\\', "/");

    let nome_final = destino.file_name().unwrap().to_string_lossy().to_string();

    conn.execute(
        "INSERT INTO anexos (demanda_id, nome, caminho, tamanho, adicionado_em) VALUES (?, ?, ?, ?, ?)",
        params![demanda_id, nome_final, caminho_relativo, tamanho, agora_iso()],
    ).map_err(|e| e.to_string())?;

    let anexo_id = conn.last_insert_rowid();
    let _ = registrar_historico(conn, demanda_id, &format!("Anexo adicionado: {}", nome_final));

    Ok(anexo_id)
}

pub fn obter_estatisticas(conn: &Connection) -> Result<Estatisticas, rusqlite::Error> {
    let todas = listar_demandas(conn, &FiltroDemandas::default())?;
    let hoje = hoje_date();

    let mut abertas = 0;
    let mut atrasadas = 0;
    let mut vencendo = 0;
    let mut por_status: HashMap<String, usize> = HashMap::new();
    let mut por_ente: HashMap<String, usize> = HashMap::new();
    let mut por_tipo: HashMap<String, usize> = HashMap::new();

    for d in &todas {
        let sit = situacao_prazo(&d.status, d.prazo.as_deref(), hoje);
        if sit == "atrasada" {
            atrasadas += 1;
        } else if sit == "vencendo" {
            vencendo += 1;
        }

        if !STATUS_FINAIS.contains(&d.status.as_str()) {
            abertas += 1;
        }

        *por_status.entry(d.status.clone()).or_insert(0) += 1;
        let ente_chave = if d.ente.trim().is_empty() { "(sem ente)".to_string() } else { d.ente.clone() };
        *por_ente.entry(ente_chave).or_insert(0) += 1;
        *por_tipo.entry(d.tipo.clone()).or_insert(0) += 1;
    }

    let mut status_vec: Vec<ContagemItem> = por_status.into_iter().map(|(item, quantidade)| ContagemItem { item, quantidade }).collect();
    status_vec.sort_by(|a, b| b.quantidade.cmp(&a.quantidade));

    let mut ente_vec: Vec<ContagemItem> = por_ente.into_iter().map(|(item, quantidade)| ContagemItem { item, quantidade }).collect();
    ente_vec.sort_by(|a, b| b.quantidade.cmp(&a.quantidade));

    let mut tipo_vec: Vec<ContagemItem> = por_tipo.into_iter().map(|(item, quantidade)| ContagemItem { item, quantidade }).collect();
    tipo_vec.sort_by(|a, b| b.quantidade.cmp(&a.quantidade));

    Ok(Estatisticas {
        total: todas.len(),
        abertas,
        atrasadas,
        vencendo,
        por_status: status_vec,
        por_ente: ente_vec,
        por_tipo: tipo_vec,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::banco;

    fn conn_em_memoria() -> Connection {
        let conn = Connection::open_in_memory().unwrap();
        conn.execute_batch("PRAGMA foreign_keys = ON;").unwrap();
        conn.execute_batch(banco::ESQUEMA).unwrap();
        conn
    }

    #[test]
    fn test_criar_e_atualizar_registra_historico() {
        let conn = conn_em_memoria();
        let form = FormDemanda {
            titulo: "Demanda Teste".to_string(),
            descricao: String::new(),
            entregavel: String::new(),
            ente: String::new(),
            tipo: "Expediente".to_string(),
            prioridade: "Média".to_string(),
            status: "Novo".to_string(),
            responsavel: String::new(),
            processo_sei: String::new(),
            remetente: String::new(),
            remetente_email: String::new(),
            email_corpo: String::new(),
            recebido_em: None,
            prazo: Some("2026-12-01".to_string()),
            prazo_interno: None,
        };

        let id = criar_demanda(&conn, &form, "manual", None).unwrap();

        let mut form_atualizar = form.clone();
        form_atualizar.status = "Concluída".to_string();
        atualizar_demanda(&conn, id, &form_atualizar).unwrap();

        let d = obter_demanda(&conn, id).unwrap().unwrap();
        assert_eq!(d.status, "Concluída");
        assert!(d.concluido_em.is_some());

        let hist = historico(&conn, id).unwrap();
        assert!(hist.iter().any(|h| h.acao.contains("status: Novo -> Concluída")));
    }

    #[test]
    fn test_titulo_obrigatorio() {
        let conn = conn_em_memoria();
        let form = FormDemanda {
            titulo: "   ".to_string(),
            descricao: String::new(),
            entregavel: String::new(),
            ente: String::new(),
            tipo: "Expediente".to_string(),
            prioridade: "Média".to_string(),
            status: "Novo".to_string(),
            responsavel: String::new(),
            processo_sei: String::new(),
            remetente: String::new(),
            remetente_email: String::new(),
            email_corpo: String::new(),
            recebido_em: None,
            prazo: None,
            prazo_interno: None,
        };

        assert!(criar_demanda(&conn, &form, "manual", None).is_err());
    }

    #[test]
    fn test_excluir_demanda_inexistente_retorna_false() {
        let conn = conn_em_memoria();
        assert!(!excluir_demanda(&conn, 9999).unwrap());
    }
}
