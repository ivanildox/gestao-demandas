use std::path::PathBuf;

pub const STATUS_FINAIS: &[&str] = &["Concluída", "Cancelada"];
pub const STATUS: &[&str] = &["Novo", "Em andamento", "Aguardando terceiros", "Concluída", "Cancelada"];
pub const TIPOS: &[&str] = &["Expediente", "Despacho", "Relatório", "Reunião", "Outro"];
pub const PRIORIDADES: &[&str] = &["Alta", "Média", "Baixa"];
pub const DIAS_ALERTA_PRAZO: i64 = 7;

/// Retorna a pasta de dados do sistema, buscando na raiz do projeto ou no diretório do executável.
pub fn get_dados_dir() -> PathBuf {
    // 1. Verifica se existe pasta 'dados' no diretório de trabalho atual
    let cwd_dados = PathBuf::from("dados");
    if cwd_dados.exists() {
        return cwd_dados;
    }

    // 2. Verifica se existe subindo um nível (caso executado a partir de src-tauri)
    let parent_dados = PathBuf::from("../dados");
    if parent_dados.exists() {
        return parent_dados;
    }

    // 3. Verifica no diretório onde o executável se encontra
    if let Ok(exe) = std::env::current_exe() {
        if let Some(exe_dir) = exe.parent() {
            let exe_dados = exe_dir.join("dados");
            if exe_dados.exists() {
                return exe_dados;
            }
            // Modo debug do cargo target/debug
            let target_dados = exe_dir.join("../../../dados");
            if target_dados.exists() {
                return target_dados;
            }
        }
    }

    // Padrão: cria 'dados' no diretório atual
    let padrao = PathBuf::from("dados");
    let _ = std::fs::create_dir_all(&padrao);
    padrao
}

pub fn get_db_path() -> PathBuf {
    get_dados_dir().join("gestao.db")
}

pub fn get_anexos_dir() -> PathBuf {
    let p = get_dados_dir().join("anexos");
    let _ = std::fs::create_dir_all(&p);
    p
}

pub fn get_inbox_dir() -> PathBuf {
    let p = get_dados_dir().join("inbox");
    let _ = std::fs::create_dir_all(&p);
    p
}

pub fn get_processados_dir() -> PathBuf {
    let p = get_inbox_dir().join("processados");
    let _ = std::fs::create_dir_all(&p);
    p
}

pub fn get_relatorios_dir() -> PathBuf {
    let p = get_dados_dir().join("relatorios");
    let _ = std::fs::create_dir_all(&p);
    p
}
