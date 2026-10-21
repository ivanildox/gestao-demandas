use crate::config;
use crate::servicos::{formatar_data_br, obter_estatisticas};
use chrono::Local;
use rusqlite::Connection;
use std::fs::File;
use std::io::Write;
use std::path::PathBuf;

pub fn gerar_html(conn: &Connection, filtro_desc: &str) -> Result<PathBuf, String> {
    let est = obter_estatisticas(conn).map_err(|e| e.to_string())?;
    let demandas =
        crate::servicos::listar_demandas(conn, &crate::models::FiltroDemandas::default())
            .map_err(|e| e.to_string())?;

    let agora = Local::now().format("%d/%m/%Y %H:%M").to_string();
    let nome_arquivo = format!("relatorio_{}.html", Local::now().format("%Y%m%d_%H%M%S"));
    let caminho = config::get_relatorios_dir().join(nome_arquivo);

    let mut html = String::new();
    html.push_str("<!DOCTYPE html>\n<html lang=\"pt-BR\">\n<head>\n<meta charset=\"utf-8\">\n");
    html.push_str("<title>Relatório de demandas</title>\n<style>\n");
    html.push_str("body { font-family: 'Segoe UI', Arial, sans-serif; margin: 24px; color: #222; background: #fff; }\n");
    html.push_str(
        "table { border-collapse: collapse; width: 100%; margin-bottom: 24px; font-size: 13px; }\n",
    );
    html.push_str("th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; vertical-align: top; }\n");
    html.push_str("th { background: #f0f0f0; font-weight: 600; }\n");
    html.push_str("tr.atrasada { background: #f8d7da; }\n");
    html.push_str("tr.vencendo { background: #fff3cd; }\n");
    html.push_str(".cards { display: flex; gap: 20px; margin-bottom: 20px; }\n");
    html.push_str(".card { background: #f8f9fa; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 18px; }\n");
    html.push_str(".card b { font-size: 22px; display: block; color: #1e293b; }\n");
    html.push_str(".card span { font-size: 13px; color: #64748b; }\n");
    html.push_str("h1 { color: #0f172a; margin-bottom: 6px; }\n");
    html.push_str("h2 { color: #334155; margin-top: 24px; font-size: 16px; border-bottom: 2px solid #e2e8f0; padding-bottom: 4px; }\n");
    html.push_str("</style>\n</head>\n<body>\n");

    html.push_str("<h1>Relatório de Demandas</h1>\n");
    html.push_str(&format!(
        "<p>Gerado em {}. Filtro: {}.</p>\n",
        agora,
        html_escape(filtro_desc)
    ));

    // Cards
    html.push_str("<div class=\"cards\">\n");
    html.push_str(&format!(
        "<div class=\"card\"><span>Total</span><b>{}</b></div>\n",
        est.total
    ));
    html.push_str(&format!(
        "<div class=\"card\"><span>Abertas</span><b>{}</b></div>\n",
        est.abertas
    ));
    html.push_str(&format!(
        "<div class=\"card\"><span>Atrasadas</span><b>{}</b></div>\n",
        est.atrasadas
    ));
    html.push_str(&format!(
        "<div class=\"card\"><span>Vencendo em 7 dias</span><b>{}</b></div>\n",
        est.vencendo
    ));
    html.push_str("</div>\n");

    // Tabelas resumo
    html.push_str(&render_tabela_resumo("Por Status", &est.por_status));
    html.push_str(&render_tabela_resumo("Por Ente", &est.por_ente));
    html.push_str(&render_tabela_resumo("Por Tipo", &est.por_tipo));

    // Tabela detalhada
    html.push_str("<h2>Demandas</h2>\n<table>\n<tr>\n");
    let colunas = [
        "ID",
        "Título",
        "Ente",
        "Tipo",
        "Prioridade",
        "Status",
        "Responsável",
        "Processo SEI",
        "Recebido em",
        "Prazo",
        "Prazo interno",
        "Concluído em",
        "Situação",
    ];
    for col in &colunas {
        html.push_str(&format!("<th>{}</th>", col));
    }
    html.push_str("</tr>\n");

    for d in &demandas {
        let classe = &d.situacao_prazo;
        let rotulo_sit = match d.situacao_prazo.as_str() {
            "atrasada" => "Atrasada",
            "vencendo" => "Vence em breve",
            _ => "",
        };

        html.push_str(&format!("<tr class=\"{}\">", classe));
        html.push_str(&format!("<td>{}</td>", d.id.unwrap_or(0)));
        html.push_str(&format!("<td>{}</td>", html_escape(&d.titulo)));
        html.push_str(&format!("<td>{}</td>", html_escape(&d.ente)));
        html.push_str(&format!("<td>{}</td>", html_escape(&d.tipo)));
        html.push_str(&format!("<td>{}</td>", html_escape(&d.prioridade)));
        html.push_str(&format!("<td>{}</td>", html_escape(&d.status)));
        html.push_str(&format!("<td>{}</td>", html_escape(&d.responsavel)));
        html.push_str(&format!("<td>{}</td>", html_escape(&d.processo_sei)));
        html.push_str(&format!(
            "<td>{}</td>",
            formatar_data_br(d.recebido_em.as_deref().unwrap_or(""))
        ));
        html.push_str(&format!(
            "<td>{}</td>",
            formatar_data_br(d.prazo.as_deref().unwrap_or(""))
        ));
        html.push_str(&format!(
            "<td>{}</td>",
            formatar_data_br(d.prazo_interno.as_deref().unwrap_or(""))
        ));
        html.push_str(&format!(
            "<td>{}</td>",
            formatar_data_br(d.concluido_em.as_deref().unwrap_or(""))
        ));
        html.push_str(&format!("<td>{}</td>", rotulo_sit));
        html.push_str("</tr>\n");
    }

    html.push_str("</table>\n</body>\n</html>");

    std::fs::write(&caminho, html).map_err(|e| e.to_string())?;
    Ok(caminho)
}

pub fn exportar_csv(conn: &Connection) -> Result<PathBuf, String> {
    let demandas =
        crate::servicos::listar_demandas(conn, &crate::models::FiltroDemandas::default())
            .map_err(|e| e.to_string())?;

    let nome_arquivo = format!("demandas_{}.csv", Local::now().format("%Y%m%d_%H%M%S"));
    let caminho = config::get_relatorios_dir().join(nome_arquivo);

    let mut file = File::create(&caminho).map_err(|e| e.to_string())?;

    // Escreve UTF-8 BOM para Excel reconhecer acentos em português automaticamente
    file.write_all(&[0xEF, 0xBB, 0xBF])
        .map_err(|e| e.to_string())?;

    let mut writer = csv::WriterBuilder::new().delimiter(b';').from_writer(file);

    writer
        .write_record(&[
            "ID",
            "Título",
            "Ente",
            "Tipo",
            "Prioridade",
            "Status",
            "Responsável",
            "Processo SEI",
            "Recebido em",
            "Prazo",
            "Prazo interno",
            "Concluído em",
            "Situação",
        ])
        .map_err(|e| e.to_string())?;

    for d in &demandas {
        let rotulo_sit = match d.situacao_prazo.as_str() {
            "atrasada" => "Atrasada",
            "vencendo" => "Vence em breve",
            _ => "",
        };

        writer
            .write_record(&[
                d.id.unwrap_or(0).to_string(),
                d.titulo.clone(),
                d.ente.clone(),
                d.tipo.clone(),
                d.prioridade.clone(),
                d.status.clone(),
                d.responsavel.clone(),
                d.processo_sei.clone(),
                formatar_data_br(d.recebido_em.as_deref().unwrap_or("")),
                formatar_data_br(d.prazo.as_deref().unwrap_or("")),
                formatar_data_br(d.prazo_interno.as_deref().unwrap_or("")),
                formatar_data_br(d.concluido_em.as_deref().unwrap_or("")),
                rotulo_sit.to_string(),
            ])
            .map_err(|e| e.to_string())?;
    }

    writer.flush().map_err(|e| e.to_string())?;
    Ok(caminho)
}

fn render_tabela_resumo(titulo: &str, contagem: &[crate::models::ContagemItem]) -> String {
    let mut out = format!(
        "<h2>{}</h2>\n<table>\n<tr><th>Item</th><th>Quantidade</th></tr>\n",
        html_escape(titulo)
    );
    for item in contagem {
        out.push_str(&format!(
            "<tr><td>{}</td><td>{}</td></tr>\n",
            html_escape(&item.item),
            item.quantidade
        ));
    }
    out.push_str("</table>\n");
    out
}

fn html_escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#39;")
}
