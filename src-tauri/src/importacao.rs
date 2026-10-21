use crate::classificacao;
use crate::config;
use crate::models::{FormDemanda, PacoteEmail};
use crate::servicos;
use rusqlite::Connection;
use std::fs;
use std::path::{Path, PathBuf};

pub fn importar_inbox(conn: &Connection) -> Vec<String> {
    let inbox = config::get_inbox_dir();
    let processados = config::get_processados_dir();
    let _ = fs::create_dir_all(&inbox);
    let _ = fs::create_dir_all(&processados);

    let mut resultados = Vec::new();

    let mut arquivos: Vec<PathBuf> = Vec::new();
    if let Ok(entradas) = fs::read_dir(&inbox) {
        for entrada in entradas.flatten() {
            let path = entrada.path();
            if path.is_file() && path.extension().and_then(|s| s.to_str()) == Some("json") {
                arquivos.push(path);
            }
        }
    }
    arquivos.sort();

    for arq in arquivos {
        let nome_arquivo = arq.file_name().unwrap().to_string_lossy().to_string();
        match importar_arquivo_email(conn, &arq) {
            Ok(msg) => resultados.push(msg),
            Err(e) => resultados.push(format!("ERRO em {}: {}", nome_arquivo, e)),
        }
    }

    resultados
}

fn importar_arquivo_email(conn: &Connection, arquivo: &Path) -> Result<String, String> {
    let nome_arquivo = arquivo.file_name().unwrap().to_string_lossy().to_string();
    let conteudo_bytes = fs::read(arquivo).map_err(|e| e.to_string())?;

    // Trata UTF-8 com ou sem BOM
    let conteudo = if conteudo_bytes.starts_with(&[0xEF, 0xBB, 0xBF]) {
        String::from_utf8_lossy(&conteudo_bytes[3..]).to_string()
    } else {
        String::from_utf8_lossy(&conteudo_bytes).to_string()
    };

    let dados: PacoteEmail =
        serde_json::from_str(&conteudo).map_err(|e| format!("JSON inválido: {}", e))?;

    let ja_existe: Option<i64> = conn
        .query_row(
            "SELECT id FROM demandas WHERE email_id = ?",
            [&dados.entry_id],
            |r| r.get(0),
        )
        .ok();

    if let Some(demanda_id) = ja_existe {
        remover_pasta_de_anexos(&dados.pasta_anexos);
        arquivar_json(arquivo)?;
        return Ok(format!(
            "Já importado (demanda #{}): {}",
            demanda_id, nome_arquivo
        ));
    }

    let recebido_date = classificacao::parse_data_ou_datetime(&dados.recebido)
        .unwrap_or_else(|| servicos::hoje_date());

    let c = classificacao::classificar(
        &dados.assunto,
        &dados.corpo,
        &dados.remetente_nome,
        recebido_date,
    );

    let form = FormDemanda {
        titulo: c.titulo.clone(),
        descricao: dados.corpo.clone(),
        entregavel: String::new(),
        ente: c.ente,
        tipo: c.tipo,
        prioridade: c.prioridade,
        status: "Novo".to_string(),
        responsavel: String::new(),
        processo_sei: c.processo_sei,
        remetente: dados.remetente_nome,
        remetente_email: dados.remetente_email,
        email_corpo: dados.corpo,
        recebido_em: Some(recebido_date.format("%Y-%m-%d").to_string()),
        prazo: c.prazo,
        prazo_interno: c.prazo_interno,
    };

    let demanda_id = servicos::criar_demanda(conn, &form, "email", Some(&dados.entry_id))?;

    for anexo in &dados.anexos {
        let caminho = Path::new(&anexo.caminho);
        if caminho.exists() {
            let _ = servicos::adicionar_anexo(conn, demanda_id, caminho);
        }
    }

    remover_pasta_de_anexos(&dados.pasta_anexos);
    arquivar_json(arquivo)?;

    Ok(format!(
        "Importado como demanda #{}: {}",
        demanda_id, c.titulo
    ))
}

fn remover_pasta_de_anexos(pasta_str: &str) {
    if pasta_str.trim().is_empty() {
        return;
    }
    let pasta = Path::new(pasta_str);
    if let Ok(caminho) = pasta.canonicalize() {
        let inbox = config::get_inbox_dir();
        if let Ok(inbox_can) = inbox.canonicalize() {
            if caminho != inbox_can && caminho.starts_with(&inbox_can) && caminho.is_dir() {
                let _ = fs::remove_dir_all(caminho);
            }
        }
    }
}

fn arquivar_json(arquivo: &Path) -> Result<(), String> {
    let destino = config::get_processados_dir().join(arquivo.file_name().unwrap());
    if destino.exists() {
        let _ = fs::remove_file(&destino);
    }
    fs::rename(arquivo, &destino)
        .or_else(|_| {
            fs::copy(arquivo, &destino)?;
            fs::remove_file(arquivo)?;
            Ok(())
        })
        .map_err(|e: std::io::Error| e.to_string())
}
