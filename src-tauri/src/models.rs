use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Demanda {
    pub id: Option<i64>,
    pub titulo: String,
    pub descricao: String,
    pub entregavel: String,
    pub ente: String,
    pub tipo: String,
    pub prioridade: String,
    pub status: String,
    pub responsavel: String,
    pub processo_sei: String,
    pub remetente: String,
    pub remetente_email: String,
    pub origem: String,
    pub email_id: Option<String>,
    pub email_corpo: String,
    pub recebido_em: Option<String>,
    pub prazo: Option<String>,
    pub prazo_interno: Option<String>,
    pub concluido_em: Option<String>,
    pub criado_em: String,
    pub atualizado_em: String,
    #[serde(default)]
    pub situacao_prazo: String, // "atrasada", "vencendo" ou ""
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FormDemanda {
    pub titulo: String,
    #[serde(default)]
    pub descricao: String,
    #[serde(default)]
    pub entregavel: String,
    #[serde(default)]
    pub ente: String,
    #[serde(default = "padrao_tipo")]
    pub tipo: String,
    #[serde(default = "padrao_prioridade")]
    pub prioridade: String,
    #[serde(default = "padrao_status")]
    pub status: String,
    #[serde(default)]
    pub responsavel: String,
    #[serde(default)]
    pub processo_sei: String,
    #[serde(default)]
    pub remetente: String,
    #[serde(default)]
    pub remetente_email: String,
    #[serde(default)]
    pub email_corpo: String,
    pub recebido_em: Option<String>,
    pub prazo: Option<String>,
    pub prazo_interno: Option<String>,
}

fn padrao_tipo() -> String { "Expediente".to_string() }
fn padrao_prioridade() -> String { "Média".to_string() }
fn padrao_status() -> String { "Novo".to_string() }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Historico {
    pub id: Option<i64>,
    pub demanda_id: i64,
    pub momento: String,
    pub acao: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Anexo {
    pub id: Option<i64>,
    pub demanda_id: i64,
    pub nome: String,
    pub caminho: String,
    pub tamanho: i64,
    pub adicionado_em: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Classificacao {
    pub titulo: String,
    pub ente: String,
    pub tipo: String,
    pub prioridade: String,
    pub processo_sei: String,
    pub prazo: Option<String>,
    pub prazo_interno: Option<String>,
    pub dias_uteis: bool,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct FiltroDemandas {
    pub status: Option<String>,
    pub busca: Option<String>,
    pub somente_abertas: Option<bool>,
    pub recebido_de: Option<String>,
    pub recebido_ate: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContagemItem {
    pub item: String,
    pub quantidade: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Estatisticas {
    pub total: usize,
    pub abertas: usize,
    pub atrasadas: usize,
    pub vencendo: usize,
    pub por_status: Vec<ContagemItem>,
    pub por_ente: Vec<ContagemItem>,
    pub por_tipo: Vec<ContagemItem>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PacoteEmail {
    pub entry_id: String,
    #[serde(default)]
    pub assunto: String,
    #[serde(default)]
    pub remetente_nome: String,
    #[serde(default)]
    pub remetente_email: String,
    pub recebido: String,
    #[serde(default)]
    pub corpo: String,
    #[serde(default)]
    pub pasta_anexos: String,
    #[serde(default)]
    pub anexos: Vec<AnexoPacoteEmail>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnexoPacoteEmail {
    pub nome: String,
    pub caminho: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpcoesFormulario {
    pub entes: Vec<String>,
    pub tipos: Vec<String>,
    pub prioridades: Vec<String>,
    pub status: Vec<String>,
}
