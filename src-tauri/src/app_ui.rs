use chrono::NaiveDate;
use eframe::egui;
use egui_extras::{Column, DatePickerButton, TableBuilder};
use rusqlite::Connection;
use std::time::{Duration, Instant};

const FORMATO_DATA: &str = "%Y-%m-%d";

fn data_para_texto(d: Option<NaiveDate>) -> Option<String> {
    d.map(|v| v.format(FORMATO_DATA).to_string())
}

fn texto_para_data(s: &Option<String>) -> Option<NaiveDate> {
    s.as_deref()
        .filter(|v| !v.trim().is_empty())
        .and_then(|v| NaiveDate::parse_from_str(v, FORMATO_DATA).ok())
}

/// Cor de fundo da linha da tabela, de acordo com o status da demanda.
fn cor_status(status: &str) -> egui::Color32 {
    match status {
        "Novo" => egui::Color32::from_rgb(222, 235, 255),
        "Em andamento" => egui::Color32::from_rgb(255, 243, 205),
        "Aguardando terceiros" => egui::Color32::from_rgb(237, 225, 255),
        "Concluída" => egui::Color32::from_rgb(212, 237, 218),
        "Cancelada" => egui::Color32::from_rgb(233, 236, 239),
        _ => egui::Color32::TRANSPARENT,
    }
}

/// Pinta o fundo da célula atual com a cor indicada, preenchendo todo o
/// retângulo disponível antes de desenhar o conteúdo por cima.
fn pintar_fundo_celula(ui: &mut egui::Ui, cor: egui::Color32) {
    if cor != egui::Color32::TRANSPARENT {
        ui.painter().rect_filled(ui.max_rect(), 0.0, cor);
    }
}

/// Desenha um seletor de data opcional: uma caixa de marcação para habilitar
/// a data, seguida do calendário (`egui_extras::DatePickerButton`).
fn editor_data_opcional(ui: &mut egui::Ui, id_salt: &str, valor: &mut Option<NaiveDate>) {
    ui.push_id(id_salt, |ui| {
        let mut tem_data = valor.is_some();
        let mut data = valor.unwrap_or_else(|| chrono::Local::now().date_naive());
        ui.horizontal(|ui| {
            if ui.checkbox(&mut tem_data, "").changed() {
                *valor = if tem_data { Some(data) } else { None };
            }
            ui.add_enabled_ui(tem_data, |ui| {
                if ui.add(DatePickerButton::new(&mut data)).changed() && tem_data {
                    *valor = Some(data);
                }
            });
        });
    });
}

use crate::models::{
    Anexo, Demanda, Estatisticas, FiltroDemandas, FormDemanda, Historico, OpcoesFormulario,
};
use crate::{banco, classificacao, config, importacao, relatorios, servicos};

#[derive(Clone, Copy, PartialEq, Eq)]
enum Aba {
    Geral,
    Anexos,
    Historico,
    Email,
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum TipoToast {
    Sucesso,
    Erro,
}

struct Toast {
    mensagem: String,
    tipo: TipoToast,
    criado_em: Instant,
}

/// Estado editável do formulário de demanda (espelha `FormDemanda`, mas com
/// campos simples de texto para facilitar a edição na UI).
#[derive(Default, Clone)]
struct FormUi {
    titulo: String,
    descricao: String,
    entregavel: String,
    ente: String,
    tipo: String,
    prioridade: String,
    status: String,
    responsavel: String,
    processo_sei: String,
    remetente: String,
    remetente_email: String,
    recebido_em: Option<NaiveDate>,
    prazo: Option<NaiveDate>,
    prazo_interno: Option<NaiveDate>,
}

impl FormUi {
    fn nova(opcoes: &OpcoesFormulario) -> Self {
        Self {
            tipo: opcoes
                .tipos
                .first()
                .cloned()
                .unwrap_or_else(|| "Expediente".to_string()),
            prioridade: "Média".to_string(),
            status: opcoes
                .status
                .first()
                .cloned()
                .unwrap_or_else(|| "Novo".to_string()),
            ..Default::default()
        }
    }

    fn de_demanda(d: &Demanda) -> Self {
        Self {
            titulo: d.titulo.clone(),
            descricao: d.descricao.clone(),
            entregavel: d.entregavel.clone(),
            ente: d.ente.clone(),
            tipo: d.tipo.clone(),
            prioridade: d.prioridade.clone(),
            status: d.status.clone(),
            responsavel: d.responsavel.clone(),
            processo_sei: d.processo_sei.clone(),
            remetente: d.remetente.clone(),
            remetente_email: d.remetente_email.clone(),
            recebido_em: texto_para_data(&d.recebido_em),
            prazo: texto_para_data(&d.prazo),
            prazo_interno: texto_para_data(&d.prazo_interno),
        }
    }

    fn para_form_demanda(&self) -> FormDemanda {
        FormDemanda {
            titulo: self.titulo.trim().to_string(),
            descricao: self.descricao.trim().to_string(),
            entregavel: self.entregavel.trim().to_string(),
            ente: self.ente.trim().to_string(),
            tipo: self.tipo.trim().to_string(),
            prioridade: self.prioridade.trim().to_string(),
            status: self.status.trim().to_string(),
            responsavel: self.responsavel.trim().to_string(),
            processo_sei: self.processo_sei.trim().to_string(),
            remetente: self.remetente.trim().to_string(),
            remetente_email: self.remetente_email.trim().to_string(),
            email_corpo: String::new(),
            recebido_em: data_para_texto(self.recebido_em),
            prazo: data_para_texto(self.prazo),
            prazo_interno: data_para_texto(self.prazo_interno),
        }
    }
}

struct ModalDemanda {
    id: Option<i64>,
    form: FormUi,
    aba: Aba,
    anexos: Vec<Anexo>,
    historico: Vec<Historico>,
    email_corpo: Option<String>,
    confirmar_exclusao: bool,
}

struct FiltroUi {
    busca: String,
    status: String,
    somente_abertas: bool,
    recebido_de: Option<NaiveDate>,
    recebido_ate: Option<NaiveDate>,
}

impl Default for FiltroUi {
    fn default() -> Self {
        Self {
            busca: String::new(),
            status: "Todas".to_string(),
            somente_abertas: true,
            recebido_de: None,
            recebido_ate: None,
        }
    }
}

impl FiltroUi {
    fn para_filtro(&self) -> FiltroDemandas {
        let opt = |s: &str| {
            if s.trim().is_empty() {
                None
            } else {
                Some(s.trim().to_string())
            }
        };
        FiltroDemandas {
            status: Some(self.status.clone()),
            busca: opt(&self.busca),
            somente_abertas: Some(self.somente_abertas),
            recebido_de: data_para_texto(self.recebido_de),
            recebido_ate: data_para_texto(self.recebido_ate),
        }
    }
}

pub struct GestaoDemandasApp {
    conn: Connection,
    opcoes: OpcoesFormulario,
    filtro: FiltroUi,
    demandas: Vec<Demanda>,
    estatisticas: Estatisticas,
    modal: Option<ModalDemanda>,
    toasts: Vec<Toast>,
}

impl GestaoDemandasApp {
    pub fn new(_cc: &eframe::CreationContext<'_>) -> Self {
        let conn = banco::conectar().expect("Falha ao conectar ao banco de dados SQLite");

        let mut entes: Vec<String> = classificacao::ENTES
            .iter()
            .map(|(_, nome)| nome.to_string())
            .collect();
        entes.sort();
        let opcoes = OpcoesFormulario {
            entes,
            tipos: config::TIPOS.iter().map(|s| s.to_string()).collect(),
            prioridades: config::PRIORIDADES.iter().map(|s| s.to_string()).collect(),
            status: config::STATUS.iter().map(|s| s.to_string()).collect(),
        };

        let mut app = Self {
            conn,
            opcoes,
            filtro: FiltroUi::default(),
            demandas: Vec::new(),
            estatisticas: Estatisticas {
                total: 0,
                abertas: 0,
                atrasadas: 0,
                vencendo: 0,
                por_status: Vec::new(),
                por_ente: Vec::new(),
                por_tipo: Vec::new(),
            },
            modal: None,
            toasts: Vec::new(),
        };
        app.recarregar_tudo();
        app
    }

    fn toast_sucesso(&mut self, msg: impl Into<String>) {
        self.toasts.push(Toast {
            mensagem: msg.into(),
            tipo: TipoToast::Sucesso,
            criado_em: Instant::now(),
        });
    }

    fn toast_erro(&mut self, msg: impl Into<String>) {
        self.toasts.push(Toast {
            mensagem: msg.into(),
            tipo: TipoToast::Erro,
            criado_em: Instant::now(),
        });
    }

    fn carregar_demandas(&mut self) {
        let filtro = self.filtro.para_filtro();
        match servicos::listar_demandas(&self.conn, &filtro) {
            Ok(lista) => self.demandas = lista,
            Err(e) => self.toast_erro(format!("Erro ao carregar demandas: {}", e)),
        }
    }

    fn carregar_estatisticas(&mut self) {
        match servicos::obter_estatisticas(&self.conn) {
            Ok(est) => self.estatisticas = est,
            Err(e) => self.toast_erro(format!("Erro ao carregar estatísticas: {}", e)),
        }
    }

    fn recarregar_tudo(&mut self) {
        self.carregar_demandas();
        self.carregar_estatisticas();
    }

    fn abrir_modal_nova(&mut self) {
        self.modal = Some(ModalDemanda {
            id: None,
            form: FormUi::nova(&self.opcoes),
            aba: Aba::Geral,
            anexos: Vec::new(),
            historico: Vec::new(),
            email_corpo: None,
            confirmar_exclusao: false,
        });
    }

    fn abrir_modal_edicao(&mut self, id: i64) {
        match servicos::obter_demanda(&self.conn, id) {
            Ok(Some(d)) => {
                let anexos = servicos::anexos(&self.conn, id).unwrap_or_default();
                let historico = servicos::historico(&self.conn, id).unwrap_or_default();
                let email_corpo = if d.origem == "email" && !d.email_corpo.trim().is_empty() {
                    Some(d.email_corpo.clone())
                } else {
                    None
                };
                self.modal = Some(ModalDemanda {
                    id: Some(id),
                    form: FormUi::de_demanda(&d),
                    aba: Aba::Geral,
                    anexos,
                    historico,
                    email_corpo,
                    confirmar_exclusao: false,
                });
            }
            Ok(None) => self.toast_erro(format!("Demanda #{} não encontrada.", id)),
            Err(e) => self.toast_erro(format!("Erro ao carregar demanda: {}", e)),
        }
    }

    fn salvar_modal(&mut self) {
        let Some(modal) = &self.modal else { return };
        if modal.form.titulo.trim().is_empty() {
            self.toast_erro("Por favor, informe o título da demanda.");
            return;
        }

        let form = modal.form.para_form_demanda();
        let resultado = if let Some(id) = modal.id {
            servicos::atualizar_demanda(&self.conn, id, &form).map(|_| id)
        } else {
            servicos::criar_demanda(&self.conn, &form, "manual", None)
        };

        match resultado {
            Ok(id) => {
                if modal.id.is_some() {
                    self.toast_sucesso("Demanda atualizada com sucesso!");
                } else {
                    self.toast_sucesso(format!("Demanda #{} criada com sucesso!", id));
                }
                self.modal = None;
                self.recarregar_tudo();
            }
            Err(e) => self.toast_erro(format!("Erro ao salvar: {}", e)),
        }
    }

    fn excluir_modal(&mut self) {
        let Some(id) = self.modal.as_ref().and_then(|m| m.id) else {
            return;
        };
        match servicos::excluir_demanda(&self.conn, id) {
            Ok(true) => {
                self.toast_sucesso("Demanda excluída com sucesso!");
                self.modal = None;
                self.recarregar_tudo();
            }
            Ok(false) => self.toast_erro("Demanda não encontrada."),
            Err(e) => self.toast_erro(format!("Erro ao excluir demanda: {}", e)),
        }
    }

    fn adicionar_anexo_modal(&mut self, caminho: std::path::PathBuf) {
        let Some(id) = self.modal.as_ref().and_then(|m| m.id) else {
            return;
        };
        match servicos::adicionar_anexo(&self.conn, id, &caminho) {
            Ok(_) => {
                let nome = caminho
                    .file_name()
                    .map(|n| n.to_string_lossy().to_string())
                    .unwrap_or_default();
                self.toast_sucesso(format!("Anexo adicionado: {}", nome));
                if let Some(modal) = &mut self.modal {
                    modal.anexos = servicos::anexos(&self.conn, id).unwrap_or_default();
                    modal.historico = servicos::historico(&self.conn, id).unwrap_or_default();
                }
            }
            Err(e) => self.toast_erro(format!("Erro ao adicionar anexo: {}", e)),
        }
    }

    fn abrir_arquivo(&mut self, caminho: &str) {
        let path = if caminho.starts_with("anexos/") || caminho.starts_with("anexos\\") {
            config::get_dados_dir().join(caminho)
        } else {
            std::path::PathBuf::from(caminho)
        };

        if let Err(e) = open::that(&path) {
            self.toast_erro(format!("Erro ao abrir arquivo: {}", e));
        }
    }

    fn importar_inbox(&mut self) {
        let mensagens = importacao::importar_inbox(&self.conn);
        if mensagens.is_empty() {
            self.toast_sucesso("Nenhum e-mail novo encontrado na fila de importação.");
        } else {
            for m in &mensagens {
                self.toast_sucesso(m.clone());
            }
        }
        self.recarregar_tudo();
    }

    fn gerar_relatorio_html(&mut self) {
        match relatorios::gerar_html(&self.conn, "Todas") {
            Ok(path) => {
                self.toast_sucesso("Relatório HTML gerado com sucesso!");
                let path_str = path.to_string_lossy().to_string();
                self.abrir_arquivo(&path_str);
            }
            Err(e) => self.toast_erro(format!("Erro ao gerar relatório: {}", e)),
        }
    }

    fn exportar_csv(&mut self) {
        match relatorios::exportar_csv(&self.conn) {
            Ok(path) => {
                self.toast_sucesso("Planilha CSV exportada com sucesso!");
                let path_str = path.to_string_lossy().to_string();
                self.abrir_arquivo(&path_str);
            }
            Err(e) => self.toast_erro(format!("Erro ao exportar CSV: {}", e)),
        }
    }

    fn limpar_filtros(&mut self) {
        self.filtro = FiltroUi::default();
        self.carregar_demandas();
    }

    // ---------- Desenho da UI ----------

    fn desenhar_header(&mut self, ctx: &egui::Context) {
        egui::TopBottomPanel::top("header").show(ctx, |ui| {
            ui.add_space(6.0);
            ui.horizontal(|ui| {
                ui.heading("📋 Gestão de Demandas");
                ui.add_space(16.0);
                if ui.button("➕ Nova Demanda").clicked() {
                    self.abrir_modal_nova();
                }
                if ui.button("📥 Importar E-mails").clicked() {
                    self.importar_inbox();
                }
                if ui.button("📊 Relatório HTML").clicked() {
                    self.gerar_relatorio_html();
                }
                if ui.button("📄 Exportar CSV").clicked() {
                    self.exportar_csv();
                }
                if ui.button("🔄 Recarregar").clicked() {
                    self.recarregar_tudo();
                }
            });
            ui.add_space(6.0);
        });
    }

    fn desenhar_estatisticas(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            self.card_estatistica(ui, "Total de Demandas", self.estatisticas.total, None);
            self.card_estatistica(ui, "Demandas Abertas", self.estatisticas.abertas, None);
            self.card_estatistica(
                ui,
                "Prazos Atrasados",
                self.estatisticas.atrasadas,
                Some(egui::Color32::from_rgb(220, 53, 69)),
            );
            self.card_estatistica(
                ui,
                "Vencendo em 7 dias",
                self.estatisticas.vencendo,
                Some(egui::Color32::from_rgb(214, 158, 0)),
            );
        });
    }

    fn card_estatistica(
        &self,
        ui: &mut egui::Ui,
        titulo: &str,
        valor: usize,
        cor: Option<egui::Color32>,
    ) {
        egui::Frame::group(ui.style())
            .fill(ui.visuals().faint_bg_color)
            .show(ui, |ui| {
                ui.set_min_width(180.0);
                ui.vertical(|ui| {
                    ui.label(egui::RichText::new(titulo).weak());
                    let mut texto = egui::RichText::new(valor.to_string()).size(26.0).strong();
                    if let Some(c) = cor {
                        texto = texto.color(c);
                    }
                    ui.label(texto);
                });
            });
    }

    fn desenhar_filtros(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            ui.label("Buscar:");
            let resp = ui.add(
                egui::TextEdit::singleline(&mut self.filtro.busca)
                    .desired_width(260.0)
                    .hint_text("Título, ente, SEI, remetente ou responsável..."),
            );

            ui.label("Status:");
            let status_atual = self.filtro.status.clone();
            egui::ComboBox::from_id_salt("filtro-status")
                .selected_text(status_atual)
                .show_ui(ui, |ui| {
                    ui.selectable_value(&mut self.filtro.status, "Todas".to_string(), "Todas");
                    for s in self.opcoes.status.clone() {
                        ui.selectable_value(&mut self.filtro.status, s.clone(), s);
                    }
                });

            if ui
                .checkbox(&mut self.filtro.somente_abertas, "Apenas abertas")
                .changed()
            {
                self.carregar_demandas();
            }

            ui.label("Recebido de:");
            let data_de_antes = self.filtro.recebido_de;
            editor_data_opcional(ui, "filtro-recebido-de", &mut self.filtro.recebido_de);

            ui.label("até:");
            let data_ate_antes = self.filtro.recebido_ate;
            editor_data_opcional(ui, "filtro-recebido-ate", &mut self.filtro.recebido_ate);

            if ui.button("Limpar").clicked() {
                self.limpar_filtros();
            }

            if resp.changed()
                || data_de_antes != self.filtro.recebido_de
                || data_ate_antes != self.filtro.recebido_ate
            {
                self.carregar_demandas();
            }
        });
    }

    fn desenhar_tabela(&mut self, ui: &mut egui::Ui) {
        let mut id_para_editar: Option<i64> = None;

        TableBuilder::new(ui)
            .striped(true)
            .resizable(true)
            .sense(egui::Sense::click())
            .cell_layout(egui::Layout::left_to_right(egui::Align::Center))
            .column(Column::remainder().at_least(180.0))
            .column(Column::auto().at_least(110.0))
            .column(Column::auto().at_least(90.0))
            .column(Column::auto().at_least(80.0))
            .column(Column::auto().at_least(120.0))
            .column(Column::auto().at_least(110.0))
            .column(Column::auto().at_least(130.0))
            .column(Column::auto().at_least(90.0))
            .column(Column::auto().at_least(90.0))
            .column(Column::auto().at_least(100.0))
            .header(22.0, |mut header| {
                for titulo in [
                    "Título",
                    "Ente",
                    "Tipo",
                    "Prioridade",
                    "Status",
                    "Responsável",
                    "Processo SEI",
                    "Recebido",
                    "Prazo",
                    "Situação",
                ] {
                    header.col(|ui| {
                        ui.strong(titulo);
                    });
                }
            })
            .body(|mut body| {
                if self.demandas.is_empty() {
                    body.row(28.0, |mut row| {
                        row.col(|ui| {
                            ui.label("Nenhuma demanda encontrada para os filtros selecionados.");
                        });
                    });
                    return;
                }

                for d in self.demandas.clone() {
                    let cor_fundo = cor_status(&d.status);
                    body.row(26.0, |mut row| {
                        row.col(|ui| {
                            pintar_fundo_celula(ui, cor_fundo);
                            ui.label(&d.titulo);
                        });
                        row.col(|ui| {
                            pintar_fundo_celula(ui, cor_fundo);
                            ui.label(&d.ente);
                        });
                        row.col(|ui| {
                            pintar_fundo_celula(ui, cor_fundo);
                            ui.label(&d.tipo);
                        });
                        row.col(|ui| {
                            pintar_fundo_celula(ui, cor_fundo);
                            ui.label(&d.prioridade);
                        });
                        row.col(|ui| {
                            pintar_fundo_celula(ui, cor_fundo);
                            ui.label(&d.status);
                        });
                        row.col(|ui| {
                            pintar_fundo_celula(ui, cor_fundo);
                            ui.label(&d.responsavel);
                        });
                        row.col(|ui| {
                            pintar_fundo_celula(ui, cor_fundo);
                            ui.label(&d.processo_sei);
                        });
                        row.col(|ui| {
                            pintar_fundo_celula(ui, cor_fundo);
                            ui.label(servicos::formatar_data_br(
                                d.recebido_em.as_deref().unwrap_or(""),
                            ));
                        });
                        row.col(|ui| {
                            pintar_fundo_celula(ui, cor_fundo);
                            ui.label(servicos::formatar_data_br(d.prazo.as_deref().unwrap_or("")));
                        });
                        row.col(|ui| {
                            pintar_fundo_celula(ui, cor_fundo);
                            let (texto, cor) = match d.situacao_prazo.as_str() {
                                "atrasada" => ("Atrasada", egui::Color32::from_rgb(220, 53, 69)),
                                "vencendo" => {
                                    ("Vence em breve", egui::Color32::from_rgb(214, 158, 0))
                                }
                                _ => ("", ui.visuals().text_color()),
                            };
                            ui.colored_label(cor, texto);
                        });

                        if row.response().clicked() {
                            id_para_editar = Some(d.id.unwrap_or(0));
                        }
                    });
                }
            });

        if let Some(id) = id_para_editar {
            self.abrir_modal_edicao(id);
        }
    }

    fn desenhar_modal(&mut self, ctx: &egui::Context) {
        if self.modal.is_none() {
            return;
        }

        let titulo = match self.modal.as_ref().unwrap().id {
            Some(id) => format!("Editar Demanda #{}", id),
            None => "Nova Demanda".to_string(),
        };

        let mut aberto = true;
        let mut fechar = false;
        let mut salvar = false;
        let mut excluir = false;
        let mut anexo_para_adicionar: Option<std::path::PathBuf> = None;
        let mut anexo_para_abrir: Option<String> = None;

        egui::Window::new(titulo)
            .open(&mut aberto)
            .collapsible(false)
            .resizable(true)
            .default_size([680.0, 560.0])
            .show(ctx, |ui| {
                let modal = self.modal.as_mut().unwrap();

                ui.horizontal(|ui| {
                    ui.selectable_value(&mut modal.aba, Aba::Geral, "Dados Gerais");
                    if modal.id.is_some() {
                        ui.selectable_value(
                            &mut modal.aba,
                            Aba::Anexos,
                            format!("Anexos ({})", modal.anexos.len()),
                        );
                        ui.selectable_value(&mut modal.aba, Aba::Historico, "Histórico");
                        if modal.email_corpo.is_some() {
                            ui.selectable_value(&mut modal.aba, Aba::Email, "E-mail Original");
                        }
                    }
                });
                ui.separator();

                egui::ScrollArea::vertical()
                    .max_height(420.0)
                    .show(ui, |ui| match modal.aba {
                        Aba::Geral => Self::desenhar_aba_geral(ui, modal, &self.opcoes),
                        Aba::Anexos => {
                            if ui.button("📎 Adicionar Arquivo").clicked() {
                                if let Some(caminho) = rfd::FileDialog::new().pick_file() {
                                    anexo_para_adicionar = Some(caminho);
                                }
                            }
                            ui.add_space(8.0);
                            if modal.anexos.is_empty() {
                                ui.weak("Nenhum anexo adicionado a esta demanda.");
                            }
                            for a in &modal.anexos {
                                ui.horizontal(|ui| {
                                    ui.label(format!("📄 {} ({} bytes)", a.nome, a.tamanho));
                                    if ui.button("Abrir ↗").clicked() {
                                        anexo_para_abrir = Some(a.caminho.clone());
                                    }
                                });
                            }
                        }
                        Aba::Historico => {
                            if modal.historico.is_empty() {
                                ui.weak("Nenhum evento registrado.");
                            }
                            for h in &modal.historico {
                                ui.label(format!("{} — {}", h.momento, h.acao));
                                ui.separator();
                            }
                        }
                        Aba::Email => {
                            if let Some(corpo) = &modal.email_corpo {
                                ui.add(
                                    egui::TextEdit::multiline(&mut corpo.clone())
                                        .desired_rows(16)
                                        .interactive(false),
                                );
                            }
                        }
                    });

                ui.separator();
                ui.horizontal(|ui| {
                    if modal.id.is_some() {
                        if modal.confirmar_exclusao {
                            ui.colored_label(
                                egui::Color32::from_rgb(220, 53, 69),
                                "Confirmar exclusão?",
                            );
                            if ui.button("Sim, excluir").clicked() {
                                excluir = true;
                            }
                            if ui.button("Cancelar").clicked() {
                                modal.confirmar_exclusao = false;
                            }
                        } else if ui.button("🗑️ Excluir Demanda").clicked() {
                            modal.confirmar_exclusao = true;
                        }
                    }

                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        if ui.button("Salvar Demanda").clicked() {
                            salvar = true;
                        }
                        if ui.button("Cancelar").clicked() {
                            fechar = true;
                        }
                    });
                });
            });

        if let Some(caminho) = anexo_para_adicionar {
            self.adicionar_anexo_modal(caminho);
        }
        if let Some(caminho) = anexo_para_abrir {
            self.abrir_arquivo(&caminho);
        }
        if excluir {
            self.excluir_modal();
        } else if salvar {
            self.salvar_modal();
        } else if fechar || !aberto {
            self.modal = None;
        }
    }

    fn desenhar_aba_geral(ui: &mut egui::Ui, modal: &mut ModalDemanda, opcoes: &OpcoesFormulario) {
        egui::Grid::new("form-demanda-grid")
            .num_columns(2)
            .spacing([12.0, 8.0])
            .show(ui, |ui| {
                ui.label("Título *");
                ui.add(egui::TextEdit::singleline(&mut modal.form.titulo).desired_width(420.0));
                ui.end_row();

                ui.label("Ente Federativo");
                egui::ComboBox::from_id_salt("campo-ente")
                    .selected_text(if modal.form.ente.is_empty() {
                        "(Selecione)"
                    } else {
                        &modal.form.ente
                    })
                    .show_ui(ui, |ui| {
                        ui.selectable_value(&mut modal.form.ente, String::new(), "(Selecione)");
                        for e in &opcoes.entes {
                            ui.selectable_value(&mut modal.form.ente, e.clone(), e);
                        }
                    });
                ui.end_row();

                ui.label("Tipo");
                egui::ComboBox::from_id_salt("campo-tipo")
                    .selected_text(modal.form.tipo.clone())
                    .show_ui(ui, |ui| {
                        for t in &opcoes.tipos {
                            ui.selectable_value(&mut modal.form.tipo, t.clone(), t);
                        }
                    });
                ui.end_row();

                ui.label("Prioridade");
                egui::ComboBox::from_id_salt("campo-prioridade")
                    .selected_text(modal.form.prioridade.clone())
                    .show_ui(ui, |ui| {
                        for p in &opcoes.prioridades {
                            ui.selectable_value(&mut modal.form.prioridade, p.clone(), p);
                        }
                    });
                ui.end_row();

                ui.label("Status");
                egui::ComboBox::from_id_salt("campo-status")
                    .selected_text(modal.form.status.clone())
                    .show_ui(ui, |ui| {
                        for s in &opcoes.status {
                            ui.selectable_value(&mut modal.form.status, s.clone(), s);
                        }
                    });
                ui.end_row();

                ui.label("Responsável");
                ui.add(
                    egui::TextEdit::singleline(&mut modal.form.responsavel).desired_width(300.0),
                );
                ui.end_row();

                ui.label("Processo SEI");
                ui.add(
                    egui::TextEdit::singleline(&mut modal.form.processo_sei)
                        .hint_text("00000.000000/0000-00"),
                );
                ui.end_row();

                ui.label("Remetente");
                ui.add(egui::TextEdit::singleline(&mut modal.form.remetente));
                ui.end_row();

                ui.label("E-mail do Remetente");
                ui.add(
                    egui::TextEdit::singleline(&mut modal.form.remetente_email)
                        .hint_text("email@orgao.gov.br"),
                );
                ui.end_row();

                ui.label("Recebido em");
                editor_data_opcional(ui, "campo-recebido-em", &mut modal.form.recebido_em);
                ui.end_row();

                ui.label("Prazo Externo");
                editor_data_opcional(ui, "campo-prazo", &mut modal.form.prazo);
                ui.end_row();

                ui.label("Prazo Interno");
                editor_data_opcional(ui, "campo-prazo-interno", &mut modal.form.prazo_interno);
                ui.end_row();
            });

        ui.add_space(8.0);
        ui.label("Descrição / Detalhes");
        ui.add(
            egui::TextEdit::multiline(&mut modal.form.descricao)
                .desired_rows(4)
                .desired_width(f32::INFINITY),
        );

        ui.add_space(8.0);
        ui.label("Entregável Esperado");
        ui.add(
            egui::TextEdit::multiline(&mut modal.form.entregavel)
                .desired_rows(3)
                .desired_width(f32::INFINITY),
        );
    }

    fn desenhar_toasts(&mut self, ctx: &egui::Context) {
        self.toasts
            .retain(|t| t.criado_em.elapsed() < Duration::from_secs(4));

        if self.toasts.is_empty() {
            return;
        }

        egui::Area::new(egui::Id::new("toasts"))
            .anchor(egui::Align2::RIGHT_BOTTOM, egui::vec2(-16.0, -16.0))
            .show(ctx, |ui| {
                for toast in self.toasts.iter().rev() {
                    let cor_fundo = match toast.tipo {
                        TipoToast::Sucesso => egui::Color32::from_rgb(40, 167, 69),
                        TipoToast::Erro => egui::Color32::from_rgb(220, 53, 69),
                    };
                    egui::Frame::popup(ui.style())
                        .fill(cor_fundo)
                        .show(ui, |ui| {
                            ui.colored_label(egui::Color32::WHITE, &toast.mensagem);
                        });
                    ui.add_space(6.0);
                }
            });

        // Mantém a UI atualizando enquanto houver toasts visíveis.
        ctx.request_repaint_after(Duration::from_millis(500));
    }
}

impl eframe::App for GestaoDemandasApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.desenhar_header(ctx);

        egui::CentralPanel::default().show(ctx, |ui| {
            self.desenhar_estatisticas(ui);
            ui.add_space(10.0);
            self.desenhar_filtros(ui);
            ui.add_space(10.0);
            egui::ScrollArea::horizontal()
                .auto_shrink([false, false])
                .show(ui, |ui| {
                    self.desenhar_tabela(ui);
                });
        });

        self.desenhar_modal(ctx);
        self.desenhar_toasts(ctx);
    }
}
