use chrono::{Datelike, Duration, NaiveDate, NaiveDateTime};
use regex::Regex;
use std::sync::LazyLock;
use unicode_normalization::UnicodeNormalization;
use crate::models::Classificacao;

pub const DIAS_INTERNOS_CONTROLE: i64 = 3;
pub const DIAS_INTERNOS_PADRAO: i64 = 2;
pub const DIAS_CURTO_PRAZO: i64 = 4;
pub const DIAS_PRIORIDADE_ALTA: i64 = 5;
pub const JANELA_DIAS_UTEIS: usize = 40;

pub const PREFIXOS_ASSUNTO: &[&str] = &["re:", "fw:", "fwd:", "enc:", "res:", "tr:"];

static RE_SEI: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\b\d{5}\.\d{6}/\d{4}-\d{2}\b").unwrap()
});

static RE_PRAZO_DATA: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?:prazo|ate|limite)[^0-9]{0,30}(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})").unwrap()
});

static RE_PRAZO_DIAS: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?:prazo\s*(?:de|:)?\s*)?(\d{1,3})\s*dias?").unwrap()
});

pub const ENTES: &[(&str, &str)] = &[
    ("barra de santo antonio", "Barra de Santo Antonio_AL"),
    ("cajueiro", "Cajueiro_AL"),
    ("coqueiro seco", "Coqueiro Seco_AL"),
    ("sao sebastiao", "São Sebastião_AL"),
    ("agua branca", "Agua Branca_PB"),
    ("arara", "Arara_PB"),
    ("bom jesus", "Bom Jesus_PB"),
    ("sao jose da lagoa tapada", "São José da Lagoa Tapada_PB"),
    ("sape", "Sape_PB"),
];

fn is_combining(c: char) -> bool {
    matches!(c, '\u{0300}'..='\u{036f}' | '\u{1ab0}'..='\u{1aff}' | '\u{1dc0}'..='\u{1dff}' | '\u{20d0}'..='\u{20ff}' | '\u{fe20}'..='\u{fe2f}')
}

pub fn normalizar(texto: &str) -> String {
    texto
        .nfkd()
        .filter(|&c| !is_combining(c))
        .collect::<String>()
        .to_lowercase()
}

pub fn limpar_assunto(assunto: &str) -> String {
    let mut s = assunto.split_whitespace().collect::<Vec<_>>().join(" ");
    let mut alterou = true;
    while alterou {
        alterou = false;
        let lower = s.to_lowercase();
        for prefixo in PREFIXOS_ASSUNTO {
            if lower.starts_with(prefixo) {
                s = s[prefixo.len()..].trim().to_string();
                alterou = true;
                break;
            }
        }
    }
    if s.is_empty() {
        "(sem assunto)".to_string()
    } else {
        s
    }
}

pub fn extrair_sei(texto: &str) -> String {
    RE_SEI.find(texto).map(|m| m.as_str().to_string()).unwrap_or_default()
}

pub fn e_controle(texto: &str) -> bool {
    let t = normalizar(texto);
    t.contains("ministerio publico") || t.contains("tribunal de contas")
}

pub fn inferir_tipo(texto: &str) -> String {
    let t = normalizar(texto);
    if t.contains("relatorio") {
        "Relatório".to_string()
    } else if t.contains("oficio") || t.contains("despacho") || t.contains("expediente") {
        "Despacho".to_string()
    } else if t.contains("reuniao") {
        "Reunião".to_string()
    } else {
        "Expediente".to_string()
    }
}

pub fn inferir_ente(texto: &str) -> String {
    let t = normalizar(texto);
    for (chave, nome) in ENTES {
        if t.contains(chave) {
            return nome.to_string();
        }
    }
    String::new()
}

fn data_valida(dia_str: &str, mes_str: &str, ano_str: &str) -> Option<NaiveDate> {
    let mut ano: i32 = ano_str.parse().ok()?;
    if ano < 100 {
        ano += 2000;
    }
    let mes: u32 = mes_str.parse().ok()?;
    let dia: u32 = dia_str.parse().ok()?;
    NaiveDate::from_ymd_opt(ano, mes, dia)
}

fn adicionar_dias_uteis(inicio: NaiveDate, n: i64) -> NaiveDate {
    let mut atual = inicio;
    let mut contados = 0;
    while contados < n {
        atual += Duration::days(1);
        if atual.weekday().num_days_from_monday() < 5 {
            contados += 1;
        }
    }
    atual
}

fn menciona_uteis(texto_normalizado: &str, inicio: usize, tamanho: usize) -> bool {
    let fim = std::cmp::min(inicio + tamanho, texto_normalizado.len());
    if inicio >= texto_normalizado.len() {
        return false;
    }
    let janela = &texto_normalizado[inicio..fim];
    janela.contains("uteis") || janela.contains("util")
}

pub fn extrair_prazo(texto: &str, recebido: NaiveDate) -> (Option<NaiveDate>, bool) {
    let t = normalizar(texto);

    if let Some(m) = RE_PRAZO_DATA.captures(&t) {
        if let (Some(d), Some(mes), Some(a)) = (m.get(1), m.get(2), m.get(3)) {
            if let Some(data) = data_valida(d.as_str(), mes.as_str(), a.as_str()) {
                let match_obj = m.get(0).unwrap();
                let uteis = menciona_uteis(&t, match_obj.start(), (match_obj.end() - match_obj.start()) + JANELA_DIAS_UTEIS);
                return (Some(data), uteis);
            }
        }
    }

    if let Some(m) = RE_PRAZO_DIAS.captures(&t) {
        if let Some(n_match) = m.get(1) {
            if let Ok(n) = n_match.as_str().parse::<i64>() {
                let match_obj = m.get(0).unwrap();
                let uteis = menciona_uteis(&t, match_obj.start(), (match_obj.end() - match_obj.start()) + JANELA_DIAS_UTEIS);
                if uteis {
                    return (Some(adicionar_dias_uteis(recebido, n)), true);
                } else {
                    return (Some(recebido + Duration::days(n)), false);
                }
            }
        }
    }

    (None, false)
}

pub fn calcular_prazo_interno(prazo: NaiveDate, recebido: NaiveDate, controle: bool) -> NaiveDate {
    let dias_total = (prazo - recebido).num_days();
    let mut d = if controle {
        prazo - Duration::days(DIAS_INTERNOS_CONTROLE)
    } else if dias_total <= DIAS_CURTO_PRAZO {
        prazo - Duration::days(1)
    } else {
        prazo - Duration::days(DIAS_INTERNOS_PADRAO)
    };

    while d.weekday().num_days_from_monday() >= 5 {
        d -= Duration::days(1);
    }
    std::cmp::max(d, recebido)
}

pub fn inferir_prioridade(controle: bool, prazo: Option<NaiveDate>, recebido: NaiveDate) -> String {
    if controle {
        return "Alta".to_string();
    }
    if let Some(p) = prazo {
        if (p - recebido).num_days() <= DIAS_PRIORIDADE_ALTA {
            return "Alta".to_string();
        }
    }
    "Média".to_string()
}

pub fn classificar(assunto: &str, corpo: &str, remetente_nome: &str, recebido: NaiveDate) -> Classificacao {
    let texto_assunto_corpo = format!("{} {}", assunto, corpo);
    let controle = e_controle(&format!("{} {}", texto_assunto_corpo, remetente_nome));
    let (prazo, uteis) = extrair_prazo(&texto_assunto_corpo, recebido);
    let prazo_interno = prazo.map(|p| calcular_prazo_interno(p, recebido, controle));

    Classificacao {
        titulo: limpar_assunto(assunto),
        ente: inferir_ente(&texto_assunto_corpo),
        tipo: inferir_tipo(&texto_assunto_corpo),
        prioridade: inferir_prioridade(controle, prazo, recebido),
        processo_sei: extrair_sei(&format!("{} {}", corpo, assunto)),
        prazo: prazo.map(|p| p.format("%Y-%m-%d").to_string()),
        prazo_interno: prazo_interno.map(|p| p.format("%Y-%m-%d").to_string()),
        dias_uteis: uteis,
    }
}

pub fn parse_data_ou_datetime(texto: &str) -> Option<NaiveDate> {
    if let Ok(dt) = NaiveDateTime::parse_from_str(texto, "%Y-%m-%dT%H:%M:%S") {
        return Some(dt.date());
    }
    if let Ok(d) = NaiveDate::parse_from_str(texto, "%Y-%m-%d") {
        return Some(d);
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    const RECEBIDO: NaiveDate = NaiveDate::from_ymd_opt(2026, 10, 20).unwrap();

    #[test]
    fn test_limpa_prefixos_do_assunto() {
        assert_eq!(limpar_assunto("RE: FW: Ofício 12/2026"), "Ofício 12/2026");
        assert_eq!(limpar_assunto(""), "(sem assunto)");
    }

    #[test]
    fn test_extrai_sei() {
        assert_eq!(extrair_sei("processo 12345.000123/2026-45 aberto"), "12345.000123/2026-45");
        assert_eq!(extrair_sei("sem numero"), "");
    }

    #[test]
    fn test_prazo_em_dias_corridos() {
        let (prazo, uteis) = extrair_prazo("Favor responder no prazo de 10 dias.", RECEBIDO);
        assert_eq!(prazo, NaiveDate::from_ymd_opt(2026, 10, 30));
        assert!(!uteis);
    }

    #[test]
    fn test_prazo_em_dias_uteis() {
        let (prazo, uteis) = extrair_prazo("prazo de 5 dias úteis", RECEBIDO);
        assert_eq!(prazo, NaiveDate::from_ymd_opt(2026, 10, 27));
        assert!(uteis);
    }

    #[test]
    fn test_prazo_com_data_explicita() {
        let (prazo, uteis) = extrair_prazo("Resposta até 15/11/2026, sem falta.", RECEBIDO);
        assert_eq!(prazo, NaiveDate::from_ymd_opt(2026, 11, 15));
        assert!(!uteis);
    }

    #[test]
    fn test_data_invalida_nao_gera_prazo() {
        let (prazo, _) = extrair_prazo("prazo 31/02/2026", RECEBIDO);
        assert_eq!(prazo, None);
    }

    #[test]
    fn test_prazo_interno_pula_fim_de_semana() {
        let prazo = NaiveDate::from_ymd_opt(2026, 10, 26).unwrap();
        assert_eq!(
            calcular_prazo_interno(prazo, RECEBIDO, false),
            NaiveDate::from_ymd_opt(2026, 10, 23).unwrap()
        );
    }

    #[test]
    fn test_controle_usa_antecedencia_maior_e_prioridade_alta() {
        let cls = classificar("Solicitação do Ministério Público", "Prazo de 30 dias", "Fulano", RECEBIDO);
        assert_eq!(cls.prioridade, "Alta");
        assert_eq!(cls.prazo, Some("2026-11-19".to_string()));
        assert_eq!(cls.prazo_interno, Some("2026-11-16".to_string()));
    }

    #[test]
    fn test_ente_sem_acento() {
        assert_eq!(inferir_ente("Prefeitura de Sapé"), "Sape_PB");
        assert_eq!(inferir_ente("Prefeitura de São Sebastião"), "São Sebastião_AL");
        assert_eq!(inferir_ente("Assunto qualquer"), "");
    }

    #[test]
    fn test_tipo() {
        assert_eq!(inferir_tipo("Relatório mensal"), "Relatório");
        assert_eq!(inferir_tipo("Ofício 10"), "Despacho");
        assert_eq!(inferir_tipo("Reunião de alinhamento"), "Reunião");
        assert_eq!(inferir_tipo("Outro assunto"), "Expediente");
    }
}
