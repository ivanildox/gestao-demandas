// Previne a abertura do console no Windows em builds de release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod app_ui;
mod banco;
mod classificacao;
mod config;
mod importacao;
mod models;
mod relatorios;
mod servicos;

use eframe::egui;

const ICONE_PNG: &[u8] = include_bytes!("../icons/128x128.png");

fn main() -> eframe::Result<()> {
    // Garante inicialização e migrações do banco SQLite na inicialização
    if let Err(e) = banco::conectar() {
        eprintln!(
            "Aviso: Falha ao inicializar o banco SQLite na inicialização: {}",
            e
        );
    }

    let icone = eframe::icon_data::from_png_bytes(ICONE_PNG).ok();

    let mut viewport = egui::ViewportBuilder::default()
        .with_title("Gestão de Demandas")
        .with_inner_size([1280.0, 820.0])
        .with_min_inner_size([960.0, 640.0]);

    if let Some(icone) = icone {
        viewport = viewport.with_icon(icone);
    }

    let opcoes_janela = eframe::NativeOptions {
        viewport,
        ..Default::default()
    };

    eframe::run_native(
        "Gestão de Demandas",
        opcoes_janela,
        Box::new(|cc| {
            cc.egui_ctx.set_visuals(egui::Visuals::light());
            Ok(Box::new(app_ui::GestaoDemandasApp::new(cc)))
        }),
    )
}
