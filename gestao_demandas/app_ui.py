"""Interface gráfica em PyQt6.

Layout:
  * janela principal aberta maximizada;
  * cabeçalho com os botões de ação;
  * cards de estatística e barra de filtros;
  * relação de demandas na parte de cima (~2/3) e detalhamento da demanda
    selecionada — prazo interno, prazo externo e entregável esperado — na
    parte de baixo (~1/3);
  * tela de cadastro/edição exibida centralizada, com abas Dados Gerais,
    Anexos e E-mail Original;
  * avisos ("toasts") no canto inferior direito.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime

from PyQt6.QtCore import QDate, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import banco, config, importacao, relatorios, servicos
from .tema import estilizar_calendario, estilizar_combo
from .models import (
    Anexo,
    Andamento,
    Classificacao,
    Demanda,
    FiltroDemandas,
    FormDemanda,
    OpcoesFormulario,
    PacoteEmail,
)

FORMATO_DATA = "yyyy-MM-dd"

# Cor de fundo da linha da tabela, por status.
CORES_STATUS: dict[str, str] = {
    "Novo": "#deebff",
    "Em triagem": "#dbeafe",
    "Aguardando informações": "#fff3cd",
    "Encaminhada": "#ede1ff",
    "Em atendimento": "#fff3cd",
    "Aguardando resposta": "#fff3cd",
    "Em andamento": "#fff3cd",
    "Aguardando terceiros": "#ede1ff",
    "Concluída": "#d4edda",
    "Cancelada": "#e9ecef",
}

VERMELHO = "#dc3545"
AMBAR = "#d69e00"
VERDE = "#28a745"

COLUNAS: tuple[tuple[str, int], ...] = (
    ("", 150),
    ("Título", 300),
    ("Ente", 170),
    ("Tipo", 110),
    ("Ação", 150),
    ("Prioridade", 90),
    ("Status", 150),
    ("Responsável", 150),
    ("Processo SEI", 170),
    ("Recebido", 100),
    ("Situação", 120),
)


def _para_qdate(texto: str | None) -> QDate | None:
    if not texto:
        return None
    d = QDate.fromString(texto, FORMATO_DATA)
    return d if d.isValid() else None


def _texto_de_qdate(valor: QDate | None) -> str | None:
    return valor.toString(FORMATO_DATA) if valor is not None else None


class EditorDataOpcional(QWidget):
    """Caixa de marcação + calendário. Sem marcação, o campo fica nulo.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.check = QCheckBox()
        self.editor = QDateEdit()
        self.editor.setCalendarPopup(True)
        self.editor.setDisplayFormat("dd/MM/yyyy")
        self.editor.setDate(QDate.currentDate())
        self.editor.setEnabled(False)

        # O calendário do popup não segue a paleta do app: recebe tema claro próprio.
        calendario = self.editor.calendarWidget()
        if calendario is not None:
            estilizar_calendario(calendario)

        self.check.toggled.connect(self.editor.setEnabled)
        if hasattr(self.editor, "setSpecialValueText"):
            self.editor.setMinimumDate(QDate(1900, 1, 1))

        layout.addWidget(self.check)
        layout.addWidget(self.editor, 1)

    def valor(self) -> str | None:
        if not self.check.isChecked():
            return None
        return self.editor.date().toString(FORMATO_DATA)

    def definir(self, texto: str | None) -> None:
        d = _para_qdate(texto)
        if d is None:
            self.check.setChecked(False)
            self.editor.setDate(QDate.currentDate())
        else:
            self.editor.setDate(d)
            self.check.setChecked(True)


class Toast(QLabel):
    """Aviso flutuante no canto inferior direito, some após alguns segundos."""

    def __init__(self, parent: QWidget, mensagem: str, erro: bool = False) -> None:
        super().__init__(mensagem, parent)
        cor = VERMELHO if erro else VERDE
        self.setStyleSheet(
            f"background-color: {cor}; color: white; padding: 8px 14px;"
            "border-radius: 5px; font-weight: 600;"
        )
        self.setWordWrap(True)
        self.setMaximumWidth(520)
        self.adjustSize()
        self._reposicionar()
        self.show()
        QTimer.singleShot(4000, self.close)

    def _reposicionar(self) -> None:
        p = self.parentWidget()
        if p is not None:
            self.move(
                max(8, p.width() - self.width() - 18),
                max(8, p.height() - self.height() - 18),
            )


class AbaGeral(QWidget):
    """Aba "Dados Gerais" do formulário de demanda."""

    def __init__(self, opcoes: OpcoesFormulario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.opcoes = opcoes

        raiz = QVBoxLayout(self)

        grade = QGridLayout()
        grade.setHorizontalSpacing(12)
        grade.setVerticalSpacing(8)
        raiz.addLayout(grade)

        self.titulo = QLineEdit()
        self.ente = QLineEdit()
        self.ente.setPlaceholderText("Nome do ente federativo")
        self.tipo = QComboBox()
        self.tipo.addItems(opcoes.tipos)
        estilizar_combo(self.tipo)
        self.prioridade = QComboBox()
        self.prioridade.addItems(opcoes.prioridades)
        estilizar_combo(self.prioridade)
        self.tipo_atendimento = QComboBox()
        self.tipo_atendimento.addItems(opcoes.tipos_atendimento)
        estilizar_combo(self.tipo_atendimento)
        self.status = QComboBox()
        self.status.addItems(opcoes.status)
        estilizar_combo(self.status)
        self.responsavel = QLineEdit()
        self.processo_sei = QLineEdit()
        self.processo_sei.setPlaceholderText("00000.000000/0000-00")
        self.remetente = QLineEdit()
        self.remetente_email = QLineEdit()
        self.remetente_email.setPlaceholderText("email@orgao.gov.br")

        self.recebido_em = EditorDataOpcional()
        self.prazo = EditorDataOpcional()
        self.prazo_interno = EditorDataOpcional()

        linha = 0

        def adicionar(rotulo: str, campo: QWidget) -> None:
            nonlocal linha
            grade.addWidget(QLabel(rotulo), linha, 0, Qt.AlignmentFlag.AlignTop)
            grade.addWidget(campo, linha, 1)
            linha += 1

        adicionar("Título *", self.titulo)
        adicionar("Ente Federativo", self.ente)
        adicionar("Tipo", self.tipo)
        adicionar("Ação necessária", self.tipo_atendimento)
        adicionar("Prioridade", self.prioridade)
        adicionar("Status", self.status)
        adicionar("Responsável", self.responsavel)
        adicionar("Processo SEI", self.processo_sei)
        adicionar("Remetente", self.remetente)
        adicionar("E-mail do Remetente", self.remetente_email)
        adicionar("Recebido em", self.recebido_em)
        adicionar("Prazo Externo", self.prazo)
        adicionar("Prazo Interno", self.prazo_interno)

        # Descrição: várias linhas.
        raiz.addWidget(QLabel("Descrição / Detalhes"))
        self.descricao = QPlainTextEdit()
        self.descricao.setFixedHeight(90)
        raiz.addWidget(self.descricao)

        # Entregável: fonte dois pontos maior, como no original.
        rotulo_entregavel = QLabel("Entregável Esperado")
        fonte = rotulo_entregavel.font()
        fonte.setPointSize(fonte.pointSize() + 2)
        rotulo_entregavel.setFont(fonte)
        raiz.addWidget(rotulo_entregavel)

        self.entregavel = QPlainTextEdit()
        self.entregavel.setFont(fonte)
        self.entregavel.setFixedHeight(90)
        raiz.addWidget(self.entregavel)
        raiz.addStretch(1)

    def preencher(self, form: "FormUi") -> None:
        self.titulo.setText(form.titulo)
        self.ente.setText(form.ente)
        self._selecionar(self.tipo, form.tipo)
        self._selecionar(self.tipo_atendimento, form.tipo_atendimento)
        self._selecionar(self.prioridade, form.prioridade)
        self._selecionar(self.status, form.status)
        self.responsavel.setText(form.responsavel)
        self.processo_sei.setText(form.processo_sei)
        self.remetente.setText(form.remetente)
        self.remetente_email.setText(form.remetente_email)
        self.recebido_em.definir(form.recebido_em)
        self.prazo.definir(form.prazo)
        self.prazo_interno.definir(form.prazo_interno)
        self.descricao.setPlainText(form.descricao)
        self.entregavel.setPlainText(form.entregavel)

    def coletar(self, form: "FormUi") -> None:
        form.titulo = self.titulo.text().strip()
        form.ente = self.ente.text().strip()
        form.tipo = self.tipo.currentText()
        form.tipo_atendimento = self.tipo_atendimento.currentText()
        form.prioridade = self.prioridade.currentText()
        form.status = self.status.currentText()
        form.responsavel = self.responsavel.text().strip()
        form.processo_sei = self.processo_sei.text().strip()
        form.remetente = self.remetente.text().strip()
        form.remetente_email = self.remetente_email.text().strip()
        form.recebido_em = self.recebido_em.valor()
        form.prazo = self.prazo.valor()
        form.prazo_interno = self.prazo_interno.valor()
        form.descricao = self.descricao.toPlainText().strip()
        form.entregavel = self.entregavel.toPlainText().strip()

    @staticmethod
    def _selecionar(combo: QComboBox, valor: str) -> None:
        idx = combo.findText(valor)
        if idx < 0 and valor:
            combo.addItem(valor)
            idx = combo.findText(valor)
        if idx >= 0:
            combo.setCurrentIndex(idx)


class FormUi:
    """Estado editável do formulário (espelha `FormDemanda`)."""

    def __init__(self, **kwargs) -> None:
        self.titulo: str = kwargs.get("titulo", "")
        self.descricao: str = kwargs.get("descricao", "")
        self.entregavel: str = kwargs.get("entregavel", "")
        self.ente: str = kwargs.get("ente", "")
        self.tipo: str = kwargs.get("tipo", "Expediente")
        self.prioridade: str = kwargs.get("prioridade", "Média")
        self.tipo_atendimento: str = kwargs.get("tipo_atendimento", "Encaminhar")
        self.status: str = kwargs.get("status", "Novo")
        self.responsavel: str = kwargs.get("responsavel", "")
        self.processo_sei: str = kwargs.get("processo_sei", "")
        self.remetente: str = kwargs.get("remetente", "")
        self.remetente_email: str = kwargs.get("remetente_email", "")
        self.recebido_em: str | None = kwargs.get("recebido_em")
        self.prazo: str | None = kwargs.get("prazo")
        self.prazo_interno: str | None = kwargs.get("prazo_interno")
        self.email_corpo: str = kwargs.get("email_corpo", "")

    @classmethod
    def de_demanda(cls, d: Demanda) -> "FormUi":
        return cls(
            titulo=d.titulo,
            descricao=d.descricao,
            entregavel=d.entregavel,
            ente=d.ente,
            tipo=d.tipo,
            prioridade=d.prioridade,
            tipo_atendimento=d.tipo_atendimento,
            status=d.status,
            responsavel=d.responsavel,
            processo_sei=d.processo_sei,
            remetente=d.remetente,
            remetente_email=d.remetente_email,
            recebido_em=d.recebido_em,
            prazo=d.prazo,
            prazo_interno=d.prazo_interno,
            email_corpo=d.email_corpo,
        )

    def para_form_demanda(self) -> FormDemanda:
        return FormDemanda(
            titulo=self.titulo.strip(),
            descricao=self.descricao.strip(),
            entregavel=self.entregavel.strip(),
            ente=self.ente.strip(),
            tipo=self.tipo.strip(),
            prioridade=self.prioridade.strip(),
            tipo_atendimento=self.tipo_atendimento.strip(),
            status=self.status.strip(),
            responsavel=self.responsavel.strip(),
            processo_sei=self.processo_sei.strip(),
            remetente=self.remetente.strip(),
            remetente_email=self.remetente_email.strip(),
            email_corpo=self.email_corpo.strip(),
            recebido_em=self.recebido_em,
            prazo=self.prazo,
            prazo_interno=self.prazo_interno,
        )


class DialogoDemanda(QDialog):
    """Tela de cadastro/edição, exibida centralizada sobre a janela principal."""

    def __init__(
        self,
        parent: QWidget,
        conn: sqlite3.Connection,
        opcoes: OpcoesFormulario,
        form: FormUi,
        demanda_id: int | None,
        anexos: list[Anexo],
        email_corpo: str | None,
    ) -> None:
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle(
            f"Editar Demanda #{demanda_id}" if demanda_id else "Nova Demanda"
        )
        self.setModal(True)
        self.setMinimumSize(480, 320)
        self.resize(880, 720)

        self.demanda_id = demanda_id
        self.form = form
        self.anexos = list(anexos)
        self.email_corpo = email_corpo

        self.acao: str | None = None  # "salvar" | "excluir" | None
        self.anexo_para_adicionar: str | None = None
        self.anexo_para_abrir: str | None = None

        raiz = QVBoxLayout(self)

        self.abas = QTabWidget()
        raiz.addWidget(self.abas, 1)

        self.aba_geral = AbaGeral(opcoes)
        self.aba_geral.preencher(self.form)
        self.abas.addTab(self._com_rolagem(self.aba_geral), "Dados Gerais")

        if self.demanda_id is not None:
            self.abas.addTab(self._montar_aba_anexos(), f"Anexos ({len(self.anexos)})")
            if self.email_corpo:
                self.abas.addTab(self._montar_aba_email(), "E-mail Original")

        raiz.addWidget(self._montar_botoes())

    # ---------- Abas ----------

    def showEvent(self, event) -> None:  # noqa: N802 (API do Qt)
        """Enquadra o diálogo na área útil da tela assim que ele aparece."""
        super().showEvent(event)
        self._enquadrar_na_tela()

    def _enquadrar_na_tela(self) -> None:
        """Garante que o diálogo inteiro (com moldura) caiba na área útil.

        Sem isto, em telas baixas o diálogo fica mais alto que a área útil e a
        barra de botões (Salvar/Cancelar) some atrás da barra de tarefas.
        """
        tela = self.screen() or QApplication.primaryScreen()
        if tela is None:
            return
        area = tela.availableGeometry()

        # A moldura (barra de título + bordas) só é conhecida depois que a
        # janela do sistema operacional foi criada.
        frame = self.frameGeometry().size() - self.size()

        margem = 24
        largura = min(self.width(), area.width() - frame.width() - margem)
        altura = min(self.height(), area.height() - frame.height() - margem)
        self.resize(max(320, largura), max(240, altura))

        pai = self.parentWidget()
        centro = pai.frameGeometry().center() if pai is not None else area.center()

        x = centro.x() - self.width() // 2
        y = centro.y() - self.height() // 2

        # Mantém o diálogo inteiro dentro da área útil da tela.
        x = max(area.x(), min(x, area.x() + area.width() - self.width() - frame.width()))
        y = max(area.y(), min(y, area.y() + area.height() - self.height() - frame.height()))
        self.move(x, y)

    @staticmethod
    def _com_rolagem(widget: QWidget) -> QScrollArea:
        """Envolve um widget numa área rolável.

        Permite que o conteúdo encolha além da altura natural: a barra de
        botões permanece visível e o usuário rola o formulário.
        """
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        area.viewport().setStyleSheet("background: transparent;")
        area.setWidget(widget)
        return area

    def _montar_aba_anexos(self) -> QWidget:
        pagina = QWidget()
        layout = QVBoxLayout(pagina)

        botao = QPushButton("📎 Adicionar Arquivo")
        botao.clicked.connect(self._escolher_anexo)
        layout.addWidget(botao, alignment=Qt.AlignmentFlag.AlignLeft)

        self.lista_anexos = QTableWidget(0, 3)
        self.lista_anexos.setHorizontalHeaderLabels(["Arquivo", "Tamanho", ""])
        self.lista_anexos.verticalHeader().setVisible(False)
        self.lista_anexos.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        cabecalho = self.lista_anexos.horizontalHeader()
        cabecalho.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        cabecalho.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        cabecalho.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.lista_anexos, 1)

        self._preencher_anexos()
        return pagina

    def _preencher_anexos(self) -> None:
        self.lista_anexos.setRowCount(0)
        for a in self.anexos:
            linha = self.lista_anexos.rowCount()
            self.lista_anexos.insertRow(linha)
            self.lista_anexos.setItem(linha, 0, QTableWidgetItem(a.nome))
            self.lista_anexos.setItem(
                linha, 1, QTableWidgetItem(f"{a.tamanho:,} bytes".replace(",", "."))
            )
            botao = QPushButton("Abrir ↗")
            botao.clicked.connect(
                lambda _=False, caminho=a.caminho: self._pedir_abertura_anexo(caminho)
            )
            self.lista_anexos.setCellWidget(linha, 2, botao)

    def _montar_aba_email(self) -> QWidget:
        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        texto = QTextEdit()
        texto.setReadOnly(True)
        texto.setPlainText(self.email_corpo or "")
        layout.addWidget(texto)
        return pagina

    def _montar_botoes(self) -> QWidget:
        barra = QWidget()
        layout = QHBoxLayout(barra)
        layout.setContentsMargins(0, 0, 0, 0)

        self.botao_excluir = QPushButton("🗑️ Excluir Demanda")
        self.botao_excluir.setStyleSheet(f"color: {VERMELHO};")
        self.botao_excluir.clicked.connect(self._confirmar_exclusao)
        if self.demanda_id is None:
            self.botao_excluir.setEnabled(False)
        layout.addWidget(self.botao_excluir)

        if self.demanda_id is not None:
            self.botao_relatorio = QPushButton("📄 Relatório HTML (do Ente)")
            self.botao_relatorio.setToolTip(
                "Gera um relatório HTML com todas as demandas deste ente federativo"
            )
            self.botao_relatorio.clicked.connect(self._gerar_relatorio_ente)
            layout.addWidget(self.botao_relatorio)

        layout.addStretch(1)

        cancelar = QPushButton("cancelar")
        cancelar.clicked.connect(self.reject)
        layout.addWidget(cancelar)

        salvar = QPushButton(" salvar Demanda")
        salvar.setDefault(True)
        salvar.clicked.connect(self._salvar)
        layout.addWidget(salvar)

        return barra

    # ---------- Ações ----------

    def _gerar_relatorio_ente(self) -> None:
        """Gera relatório HTML filtrado pelo ente da demanda em edição."""
        self.aba_geral.coletar(self.form)
        ente = self.form.ente.strip()
        if not ente:
            Toast(self, "A demanda não possui ente federativo.", erro=True)
            return
        try:
            caminho = relatorios.gerar_html_ente(self.conn, ente)
        except Exception as exc:  # noqa: BLE001
            Toast(self, f"Erro ao gerar relatório: {exc}", erro=True)
            return
        Toast(self, f"Relatório gerado para o ente: {ente}")
        self._abrir_caminho(str(caminho))

    def _abrir_caminho(self, caminho: str) -> None:
        try:
            servicos.abrir_arquivo(caminho)
        except Exception as exc:  # noqa: BLE001
            try:
                servicos.abrir_arquivo(servicos.resolver_caminho_anexo(caminho))
            except Exception:  # noqa: BLE001
                Toast(self, f"Erro ao abrir arquivo: {exc}", erro=True)

    def _salvar(self) -> None:
        self.aba_geral.coletar(self.form)
        if not self.form.titulo.strip():
            QMessageBox.warning(
                self, "Campo obrigatório", "Por favor, informe o título da demanda."
            )
            self.abas.setCurrentIndex(0)
            self.aba_geral.titulo.setFocus()
            return
        self.acao = "salvar"
        self.accept()

    def _confirmar_exclusao(self) -> None:
        resposta = QMessageBox.question(
            self,
            "Confirmar exclusão",
            "Deseja realmente excluir esta demanda?\n"
            "Os anexos e o histórico também serão removidos.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resposta == QMessageBox.StandardButton.Yes:
            self.acao = "excluir"
            self.accept()

    def _escolher_anexo(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecionar arquivo para anexar"
        )
        if caminho:
            self.anexo_para_adicionar = caminho
            self.accept()

    def _pedir_abertura_anexo(self, caminho: str) -> None:
        self.anexo_para_abrir = caminho
        self.accept()

    def atualizar_anexos(self, anexos: list[Anexo]) -> None:
        self.anexos = list(anexos)
        self.abas.setTabText(1, f"Anexos ({len(self.anexos)})")
        self._preencher_anexos()


class DialogoMovimento(QDialog):
    """Formulário para registrar uma movimentação na tramitação."""

    def __init__(
        self,
        parent: QWidget,
        conn: sqlite3.Connection,
        demanda_id: int,
        titulo_demanda: str,
        andamentos: list[Andamento],
        status_atual: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Registrar movimentação")
        self.setModal(True)
        self.setMinimumSize(620, 520)
        self.resize(720, 600)
        self.conn = conn
        self.demanda_id = demanda_id
        self.titulo_demanda = titulo_demanda
        self._andamentos: list[Andamento] = list(andamentos)

        layout = QVBoxLayout(self)
        formulario = QGridLayout()

        self.data_movimento = QDateEdit()
        self.data_movimento.setCalendarPopup(True)
        self.data_movimento.setDisplayFormat("dd/MM/yyyy")
        self.data_movimento.setDate(QDate.currentDate())
        calendario = self.data_movimento.calendarWidget()
        if calendario is not None:
            estilizar_calendario(calendario)

        self.destino = QLineEdit()
        self.destino.setPlaceholderText("Pessoa, setor ou órgão")
        self.observacao = QPlainTextEdit()
        self.observacao.setPlaceholderText(
            "Observações sobre a movimentação (opcional)"
        )
        self.observacao.setFixedHeight(62)

        formulario.addWidget(QLabel("Data do Movimento"), 0, 0)
        formulario.addWidget(self.data_movimento, 0, 1)
        formulario.addWidget(QLabel("Destino"), 0, 2)
        formulario.addWidget(self.destino, 0, 3)
        formulario.addWidget(QLabel("Observação"), 1, 0, Qt.AlignmentFlag.AlignTop)
        formulario.addWidget(self.observacao, 1, 1, 1, 3)
        formulario.setColumnStretch(1, 1)
        formulario.setColumnStretch(3, 2)
        layout.addLayout(formulario)

        # --- Linha de status (antes do histórico) ---
        linha_status = QHBoxLayout()
        linha_status.addWidget(QLabel("Alterar Status:"))
        self.combo_status = QComboBox()
        self.combo_status.addItems(list(config.STATUS))
        estilizar_combo(self.combo_status)
        if status_atual:
            idx = self.combo_status.findText(status_atual)
            if idx >= 0:
                self.combo_status.setCurrentIndex(idx)
        self.botao_alterar_status = QPushButton("✔ Aplicar Status")
        self.botao_alterar_status.clicked.connect(self._alterar_status)
        linha_status.addWidget(self.combo_status)
        linha_status.addWidget(self.botao_alterar_status)
        linha_status.addStretch(1)
        layout.addLayout(linha_status)

        layout.addWidget(QLabel("Histórico"))
        self.lista_historico = QTableWidget(0, 3)
        self.lista_historico.setHorizontalHeaderLabels(
            ["Data do Movimento", "Destino", "Observação"]
        )
        self.lista_historico.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.lista_historico.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.lista_historico.setAlternatingRowColors(True)
        self.lista_historico.verticalHeader().setVisible(False)
        self.lista_historico.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.lista_historico.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.lista_historico.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.lista_historico, 1)
        self.atualizar_historico(andamentos)

        exportar = QPushButton("Exportar Histórico HTML")
        exportar.clicked.connect(self._exportar_historico)

        self.botao_excluir_registro = QPushButton("🗑️ Excluir Registro")
        self.botao_excluir_registro.setStyleSheet(f"color: {VERMELHO};")
        self.botao_excluir_registro.setToolTip(
            "Excluir o registro de movimentação selecionado no histórico"
        )
        self.botao_excluir_registro.clicked.connect(self._excluir_registro)

        botoes = QDialogButtonBox()
        registrar = botoes.addButton(
            "Registrar", QDialogButtonBox.ButtonRole.ActionRole
        )
        cancelar = botoes.addButton(
            "Cancelar", QDialogButtonBox.ButtonRole.RejectRole
        )
        registrar.clicked.connect(self._registrar)
        cancelar.clicked.connect(self.reject)
        linha_botoes = QHBoxLayout()
        linha_botoes.addWidget(exportar)
        linha_botoes.addWidget(self.botao_excluir_registro)
        linha_botoes.addStretch(1)
        linha_botoes.addWidget(botoes)
        layout.addLayout(linha_botoes)

    def atualizar_historico(self, andamentos: list[Andamento]) -> None:
        self._andamentos = list(andamentos)
        self.lista_historico.setRowCount(0)
        for andamento in andamentos:
            momento = (
                servicos.formatar_data_br(andamento.momento)
                if len(andamento.momento) == 10
                else andamento.momento
            )
            linha = self.lista_historico.rowCount()
            self.lista_historico.insertRow(linha)
            for coluna, valor in enumerate(
                (momento, andamento.destinatario, andamento.descricao)
            ):
                item = QTableWidgetItem(valor)
                item.setData(Qt.ItemDataRole.UserRole, andamento.id)
                self.lista_historico.setItem(linha, coluna, item)

    def _alterar_status(self) -> None:
        novo_status = self.combo_status.currentText()
        try:
            servicos.atualizar_status_demanda(self.conn, self.demanda_id, novo_status)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Erro ao alterar status",
                f"Não foi possível alterar o status: {exc}",
            )
            return
        QMessageBox.information(
            self, "Status atualizado", f"Status alterado para: {novo_status}"
        )

    def _excluir_registro(self) -> None:
        linhas = self.lista_historico.selectionModel().selectedRows()
        if not linhas:
            QMessageBox.warning(
                self,
                "Nenhum registro selecionado",
                "Selecione um registro no histórico para excluir.",
            )
            return
        linha = linhas[0].row()
        item = self.lista_historico.item(linha, 0)
        andamento_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        if andamento_id is None:
            QMessageBox.warning(self, "Erro", "Não foi possível identificar o registro.")
            return
        resposta = QMessageBox.question(
            self,
            "Confirmar exclusão",
            "Deseja realmente excluir este registro de movimentação?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resposta != QMessageBox.StandardButton.Yes:
            return
        try:
            excluido = servicos.excluir_andamento(self.conn, andamento_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self, "Erro ao excluir registro", f"Não foi possível excluir: {exc}"
            )
            return
        if excluido:
            self.atualizar_historico(
                servicos.listar_andamentos(self.conn, self.demanda_id)
            )
        else:
            QMessageBox.warning(self, "Registro não encontrado", "O registro não foi encontrado no banco.")

    def _exportar_historico(self) -> None:
        try:
            caminho = relatorios.exportar_historico_html(
                self.demanda_id,
                self.titulo_demanda,
                servicos.listar_andamentos(self.conn, self.demanda_id),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self, "Erro ao exportar histórico", f"Não foi possível gerar o HTML: {exc}"
            )
            return

        try:
            servicos.abrir_arquivo(caminho)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self,
                "Histórico exportado",
                f"O arquivo foi salvo em:\n{caminho}\n\n"
                f"Não foi possível abri-lo automaticamente: {exc}",
            )
            return
        QMessageBox.information(
            self, "Histórico exportado", f"Arquivo gerado:\n{caminho}"
        )

    def _registrar(self) -> None:
        if not self.destino.text().strip():
            QMessageBox.warning(
                self, "Destino obrigatório", "Informe o destino da movimentação."
            )
            self.destino.setFocus()
            return
        try:
            servicos.registrar_movimento(
                self.conn,
                self.demanda_id,
                self.data_movimento.date().toString(FORMATO_DATA),
                self.destino.text(),
                self.observacao.toPlainText(),
            )
            self.atualizar_historico(
                servicos.listar_andamentos(self.conn, self.demanda_id)
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Erro ao registrar movimentação",
                f"Não foi possível registrar a movimentação: {exc}",
            )


class JanelaPrincipal(QMainWindow):
    """Janela principal do sistema."""

    def __init__(self, conn) -> None:
        super().__init__()
        self.conn = conn
        self.opcoes = OpcoesFormulario(
            tipos=list(config.TIPOS),
            prioridades=list(config.PRIORIDADES),
            tipos_atendimento=list(config.TIPOS_ATENDIMENTO),
            status=list(config.STATUS),
        )

        self.demandas: list[Demanda] = []
        self.demanda_selecionada: int | None = None

        self.setWindowTitle(config.TITULO_JANELA)
        self.setWindowIcon(QIcon(str(config.get_icone_path())))
        self.resize(1280, 820)
        self.setMinimumSize(960, 640)

        self._montar_interface()
        self.recarregar_tudo()

    # ---------- Construção da interface ----------

    def _montar_interface(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        raiz = QVBoxLayout(central)
        raiz.setContentsMargins(10, 10, 10, 10)
        raiz.setSpacing(8)

        raiz.addWidget(self._montar_cabecalho())
        raiz.addWidget(self._montar_cards())
        raiz.addWidget(self._montar_filtros())

        divisor = QSplitter(Qt.Orientation.Vertical)
        divisor.addWidget(self._montar_tabela())
        divisor.addWidget(self._montar_detalhes())
        divisor.setStretchFactor(0, 65)
        divisor.setStretchFactor(1, 35)
        divisor.setSizes([520, 280])
        raiz.addWidget(divisor, 1)

        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Pronto.")

        # Atalho discreto para a pasta de dados em uso (banco, anexos e fila).
        self.botao_dados = QPushButton("📁 Pasta de dados")
        self.botao_dados.setFlat(True)
        self.botao_dados.setCursor(Qt.CursorShape.PointingHandCursor)
        self.botao_dados.setToolTip(
            "Abrir a pasta de dados em uso (banco, anexos e fila de e-mails):\n"
            f"{config.get_dados_dir()}"
        )
        self.botao_dados.clicked.connect(self.abrir_pasta_dados)
        self.status_bar.addPermanentWidget(self.botao_dados)

    def _montar_cabecalho(self) -> QWidget:
        barra = QWidget()
        layout = QHBoxLayout(barra)
        layout.setContentsMargins(0, 0, 0, 0)

        titulo = QLabel("📋 Gestão de Demandas")
        fonte = titulo.font()
        fonte.setPointSize(fonte.pointSize() + 6)
        fonte.setBold(True)
        titulo.setFont(fonte)
        layout.addWidget(titulo)
        layout.addSpacing(16)

        for rotulo, slot, dica in (
            ("➕ Nova Demanda", self.nova_demanda, "Cadastrar uma demanda manualmente"),
            ("📥 Importar E-mails", self.importar_inbox, "Processar a fila dados/inbox"),
            ("📊 Relatório HTML", self.gerar_html, "Gerar relatório e abrir no navegador"),
            ("📄 Exportar CSV", self.exportar_csv, "Exportar planilha para o Excel"),
            ("🔄 Recarregar", self.recarregar_tudo, "Recarregar a lista"),
        ):
            botao = QPushButton(rotulo)
            botao.clicked.connect(slot)
            botao.setToolTip(dica)
            layout.addWidget(botao)

        layout.addStretch(1)
        return barra

    def _montar_cards(self) -> QWidget:
        barra = QWidget()
        layout = QHBoxLayout(barra)
        layout.setContentsMargins(0, 0, 0, 0)

        self.cards: dict[str, QLabel] = {}
        definicoes = (
            ("Total de Demandas", "total", None),
            ("Demandas Abertas", "abertas", None),
            ("Prazos Atrasados", "atrasadas", VERMELHO),
            ("Vencendo em 7 dias", "vencendo", AMBAR),
        )

        for rotulo, chave, cor in definicoes:
            caixa = QGroupBox()
            caixa.setStyleSheet(
                "QGroupBox { background: #f8f9fa; border: 1px solid #e2e8f0;"
                "border-radius: 8px; }"
            )
            interior = QVBoxLayout(caixa)
            interior.setContentsMargins(14, 10, 14, 10)
            interior.setSpacing(0)

            legenda = QLabel(rotulo)
            legenda.setStyleSheet("color: #64748b; border: none;")
            interior.addWidget(legenda)

            valor = QLabel("0")
            fonte = valor.font()
            fonte.setPointSize(fonte.pointSize() + 12)
            fonte.setBold(True)
            valor.setFont(fonte)
            estilo = "border: none;"
            if cor:
                estilo += f" color: {cor};"
            valor.setStyleSheet(estilo)
            interior.addWidget(valor)

            self.cards[chave] = valor
            caixa.setMinimumWidth(190)
            layout.addWidget(caixa)

        layout.addStretch(1)
        return barra

    def _montar_filtros(self) -> QWidget:
        barra = QWidget()
        layout = QHBoxLayout(barra)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Buscar:"))
        self.campo_busca = QLineEdit()
        self.campo_busca.setPlaceholderText(
            "Título, ente, SEI, remetente ou responsável..."
        )
        self.campo_busca.setMinimumWidth(280)
        self.campo_busca.textChanged.connect(self._agendar_recarga)
        layout.addWidget(self.campo_busca)

        layout.addWidget(QLabel("Status:"))
        self.combo_status = QComboBox()
        self.combo_status.addItem("Todas")
        self.combo_status.addItems(list(config.STATUS))
        estilizar_combo(self.combo_status)
        self.combo_status.currentIndexChanged.connect(self.carregar_demandas)
        layout.addWidget(self.combo_status)

        self.check_abertas = QCheckBox("Apenas abertas")
        self.check_abertas.setChecked(True)
        self.check_abertas.toggled.connect(self.carregar_demandas)
        layout.addWidget(self.check_abertas)

        layout.addWidget(QLabel("Recebido de:"))
        self.filtro_de = EditorDataOpcional()
        self.filtro_de.check.toggled.connect(self.carregar_demandas)
        self.filtro_de.editor.dateChanged.connect(self.carregar_demandas)
        layout.addWidget(self.filtro_de)

        layout.addWidget(QLabel("até:"))
        self.filtro_ate = EditorDataOpcional()
        self.filtro_ate.check.toggled.connect(self.carregar_demandas)
        self.filtro_ate.editor.dateChanged.connect(self.carregar_demandas)
        layout.addWidget(self.filtro_ate)

        botao = QPushButton("Limpar")
        botao.clicked.connect(self.limpar_filtros)
        layout.addWidget(botao)

        layout.addStretch(1)
        return barra

    def _montar_tabela(self) -> QWidget:
        self.tabela = QTableWidget(0, len(COLUNAS))
        self.tabela.setHorizontalHeaderLabels([c[0] for c in COLUNAS])
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tabela.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setSortingEnabled(False)

        cabecalho = self.tabela.horizontalHeader()
        for i, (_, largura) in enumerate(COLUNAS):
            cabecalho.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
            self.tabela.setColumnWidth(i, largura)
        cabecalho.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.tabela.itemSelectionChanged.connect(self._ao_selecionar_linha)
        return self.tabela

    def _montar_detalhes(self) -> QWidget:
        caixa = QGroupBox("Detalhamento da Demanda")
        layout = QVBoxLayout(caixa)

        self.detalhe_titulo = QLabel("")
        fonte = self.detalhe_titulo.font()
        fonte.setBold(True)
        fonte.setPointSize(fonte.pointSize() + 1)
        self.detalhe_titulo.setFont(fonte)
        self.detalhe_titulo.setWordWrap(True)
        layout.addWidget(self.detalhe_titulo)

        self.detalhe_proxima_acao = QLabel("")
        self.detalhe_proxima_acao.setWordWrap(True)
        layout.addWidget(self.detalhe_proxima_acao)

        prazos = QHBoxLayout()
        self.detalhe_prazo_interno = QLabel("")
        self.detalhe_prazo_externo = QLabel("")
        prazos.addWidget(QLabel("<b>Prazo Interno:</b>"))
        prazos.addWidget(self.detalhe_prazo_interno)
        prazos.addSpacing(28)
        prazos.addWidget(QLabel("<b>Prazo Externo:</b>"))
        prazos.addWidget(self.detalhe_prazo_externo)
        prazos.addStretch(1)
        layout.addLayout(prazos)

        self.detalhe_entregavel = QPlainTextEdit()
        self.detalhe_entregavel.setReadOnly(True)
        fonte_entregavel = self.detalhe_entregavel.font()
        fonte_entregavel.setPointSize(fonte_entregavel.pointSize() + 2)
        self.detalhe_entregavel.setFont(fonte_entregavel)
        layout.addWidget(QLabel("<b>Entregável Esperado</b>"))
        layout.addWidget(self.detalhe_entregavel, 1)

        self._limpar_detalhes()
        return caixa

    # ---------- Recarga de dados ----------

    def _agendar_recarga(self) -> None:
        """Evita recarregar a cada tecla digitada na busca."""
        if not hasattr(self, "_timer_busca"):
            self._timer_busca = QTimer(self)
            self._timer_busca.setSingleShot(True)
            self._timer_busca.setInterval(250)
            self._timer_busca.timeout.connect(self.carregar_demandas)
        self._timer_busca.start()

    def _filtro_atual(self) -> FiltroDemandas:
        return FiltroDemandas(
            status=self.combo_status.currentText(),
            busca=self.campo_busca.text().strip() or None,
            somente_abertas=self.check_abertas.isChecked(),
            recebido_de=self.filtro_de.valor(),
            recebido_ate=self.filtro_ate.valor(),
        )

    def carregar_demandas(self) -> None:
        try:
            self.demandas = servicos.listar_demandas(self.conn, self._filtro_atual())
        except Exception as exc:  # noqa: BLE001
            self.avisar(f"Erro ao carregar demandas: {exc}", erro=True)
            return
        self._preencher_tabela()

    def carregar_estatisticas(self) -> None:
        try:
            est = servicos.obter_estatisticas(self.conn)
        except Exception as exc:  # noqa: BLE001
            self.avisar(f"Erro ao carregar estatísticas: {exc}", erro=True)
            return
        self.cards["total"].setText(str(est.total))
        self.cards["abertas"].setText(str(est.abertas))
        self.cards["atrasadas"].setText(str(est.atrasadas))
        self.cards["vencendo"].setText(str(est.vencendo))

    def recarregar_tudo(self) -> None:
        self.carregar_demandas()
        self.carregar_estatisticas()
        self.status_bar.showMessage(
            f"{len(self.demandas)} demanda(s) listada(s) — "
            f"banco: {config.get_db_path()}"
        )

    def _preencher_tabela(self) -> None:
        self.tabela.blockSignals(True)
        self.tabela.setRowCount(0)

        for d in self.demandas:
            linha = self.tabela.rowCount()
            self.tabela.insertRow(linha)

            acoes = QWidget()
            layout_acoes = QHBoxLayout(acoes)
            layout_acoes.setContentsMargins(2, 0, 2, 0)
            layout_acoes.setSpacing(3)

            botao_editar = QPushButton("Editar")
            botao_editar.setFixedWidth(68)
            botao_editar.setStyleSheet(
                f"background-color: {VERDE}; color: white; font-weight: 600;"
                "padding: 2px 8px; border-radius: 3px;"
            )
            botao_editar.setToolTip("Abrir a tela de edição desta demanda")
            botao_editar.clicked.connect(
                lambda _=False, i=d.id: self.abrir_edicao(i or 0)
            )
            layout_acoes.addWidget(botao_editar)

            botao_mover = QPushButton("Histórico")
            botao_mover.setFixedWidth(80)
            botao_mover.setToolTip("Registrar uma movimentação desta demanda")
            botao_mover.clicked.connect(
                lambda _=False, i=d.id: self.abrir_movimento(i or 0)
            )
            layout_acoes.addWidget(botao_mover)
            self.tabela.setCellWidget(linha, 0, acoes)

            valores = (
                d.titulo,
                d.ente,
                d.tipo,
                d.tipo_atendimento,
                d.prioridade,
                d.status,
                d.responsavel,
                d.processo_sei,
                servicos.formatar_data_br(d.recebido_em),
            )
            for offset, valor in enumerate(valores, start=1):
                item = QTableWidgetItem(str(valor))
                item.setData(Qt.ItemDataRole.UserRole, d.id)
                if d.id == self.demanda_selecionada:
                    item.setBackground(QColor(13, 110, 253, 60))
                self.tabela.setItem(linha, offset, item)

            rotulo, cor = {
                "atrasada": ("Atrasada", VERMELHO),
                "vencendo": ("Vence em breve", AMBAR),
            }.get(d.situacao_prazo, ("", ""))

            item_situacao = QTableWidgetItem(rotulo)
            item_situacao.setData(Qt.ItemDataRole.UserRole, d.id)
            if cor:
                item_situacao.setForeground(QColor(cor))
                fonte = item_situacao.font()
                fonte.setBold(True)
                item_situacao.setFont(fonte)
            self.tabela.setItem(linha, len(COLUNAS) - 1, item_situacao)

            # Fundo por status (as células com botão ficam com o botão por cima).
            cor_fundo = CORES_STATUS.get(d.status)
            if cor_fundo:
                for col in range(1, len(COLUNAS)):
                    celula = self.tabela.item(linha, col)
                    if celula is not None and d.id != self.demanda_selecionada:
                        celula.setBackground(QColor(cor_fundo))

        self.tabela.blockSignals(False)
        self._sincronizar_selecao()

    def _sincronizar_selecao(self) -> None:
        if self.demanda_selecionada is None:
            self._limpar_detalhes()
            return
        for linha in range(self.tabela.rowCount()):
            item = self.tabela.item(linha, 1)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == self.demanda_selecionada:
                self.tabela.selectRow(linha)
                self._mostrar_detalhes(self.demanda_selecionada)
                return
        self._limpar_detalhes()

    def _ao_selecionar_linha(self) -> None:
        linhas = self.tabela.selectionModel().selectedRows()
        if not linhas:
            return
        item = self.tabela.item(linhas[0].row(), 1)
        if item is None:
            return
        self.demanda_selecionada = item.data(Qt.ItemDataRole.UserRole)
        self._mostrar_detalhes(self.demanda_selecionada)

    def _mostrar_detalhes(self, demanda_id: int | None) -> None:
        d = next((x for x in self.demandas if x.id == demanda_id), None)
        if d is None:
            self._limpar_detalhes()
            return

        self.detalhe_titulo.setText(
            f"Demanda #{d.id or 0} — {d.titulo}   ({d.ente or 'sem ente'} · {d.status})"
        )
        self.detalhe_proxima_acao.setText(
            f"<b>Ação necessária:</b> {d.tipo_atendimento}  ·  "
            f"<b>Responsável:</b> {d.responsavel or 'não atribuído'}"
        )
        self.detalhe_prazo_interno.setText(
            servicos.formatar_data_br(d.prazo_interno) or "—"
        )
        self.detalhe_prazo_externo.setText(servicos.formatar_data_br(d.prazo) or "—")

        texto = d.entregavel.strip() or "(entregável ainda não informado)"
        self.detalhe_entregavel.setPlainText(texto)

    def _limpar_detalhes(self) -> None:
        self.detalhe_titulo.setText(
            "Selecione uma demanda na tabela para ver o prazo interno, "
            "o prazo externo e o entregável esperado."
        )
        self.detalhe_proxima_acao.setText("")
        self.detalhe_prazo_interno.setText("—")
        self.detalhe_prazo_externo.setText("—")
        self.detalhe_entregavel.setPlainText("")

    # ---------- Ações ----------

    def avisar(self, mensagem: str, erro: bool = False) -> None:
        Toast(self, mensagem, erro=erro)
        self.status_bar.showMessage(mensagem, 8000)

    def nova_demanda(self) -> None:
        form = FormUi(
            tipo=self.opcoes.tipos[0] if self.opcoes.tipos else "Expediente",
            prioridade="Média",
            status=self.opcoes.status[0] if self.opcoes.status else "Novo",
        )
        self._abrir_dialogo(None, form, [], None)

    def abrir_edicao(self, demanda_id: int) -> None:
        d = servicos.obter_demanda(self.conn, demanda_id)
        if d is None:
            self.avisar(f"Demanda #{demanda_id} não encontrada.", erro=True)
            return
        self.demanda_selecionada = demanda_id
        anexos = servicos.anexos(self.conn, demanda_id)
        corpo = d.email_corpo if (d.origem == "email" and d.email_corpo.strip()) else None
        self._abrir_dialogo(
            demanda_id,
            FormUi.de_demanda(d),
            anexos,
            corpo,
        )

    def abrir_movimento(self, demanda_id: int) -> None:
        demanda = servicos.obter_demanda(self.conn, demanda_id)
        if demanda is None:
            self.avisar(f"Demanda #{demanda_id} não encontrada.", erro=True)
            return

        andamentos = servicos.listar_andamentos(self.conn, demanda_id)
        dialogo = DialogoMovimento(
            self, self.conn, demanda_id, demanda.titulo, andamentos,
            status_atual=demanda.status,
        )
        dialogo.exec()
        self.recarregar_tudo()

    def _abrir_dialogo(
        self,
        demanda_id: int | None,
        form: FormUi,
        anexos: list[Anexo],
        email_corpo: str | None,
    ) -> None:
        dialogo = DialogoDemanda(
            self,
            self.conn,
            self.opcoes,
            form,
            demanda_id,
            anexos,
            email_corpo,
        )

        while True:
            resultado = dialogo.exec()
            acao = dialogo.acao
            dialogo.acao = None

            if dialogo.anexo_para_adicionar:
                caminho = dialogo.anexo_para_adicionar
                dialogo.anexo_para_adicionar = None
                try:
                    servicos.adicionar_anexo(self.conn, demanda_id or 0, caminho)
                    self.avisar(f"Anexo adicionado: {caminho.rsplit('/', 1)[-1]}")
                    dialogo.atualizar_anexos(servicos.anexos(self.conn, demanda_id or 0))
                except Exception as exc:  # noqa: BLE001
                    self.avisar(f"Erro ao adicionar anexo: {exc}", erro=True)
                continue

            if dialogo.anexo_para_abrir:
                self._abrir_caminho(dialogo.anexo_para_abrir)
                dialogo.anexo_para_abrir = None
                continue

            break

        if acao == "excluir" and demanda_id is not None:
            try:
                if servicos.excluir_demanda(self.conn, demanda_id):
                    self.avisar("Demanda excluída com sucesso!")
                    self.demanda_selecionada = None
                    self.recarregar_tudo()
                else:
                    self.avisar("Demanda não encontrada.", erro=True)
            except Exception as exc:  # noqa: BLE001
                self.avisar(f"Erro ao excluir demanda: {exc}", erro=True)
        elif acao == "salvar":
            self._salvar(demanda_id, form)

        if resultado == QDialog.DialogCode.Rejected and acao is None:
            self.recarregar_tudo()

    def _salvar(self, demanda_id: int | None, form: FormUi) -> None:
        dados = form.para_form_demanda()
        try:
            if demanda_id is None:
                novo_id = servicos.criar_demanda(self.conn, dados, "manual", None)
                self.demanda_selecionada = novo_id
                self.avisar(f"Demanda #{novo_id} criada com sucesso!")
            else:
                servicos.atualizar_demanda(self.conn, demanda_id, dados)
                self.demanda_selecionada = demanda_id
                self.avisar("Demanda atualizada com sucesso!")
            self.recarregar_tudo()
        except Exception as exc:  # noqa: BLE001
            self.avisar(f"Erro ao salvar: {exc}", erro=True)

    def abrir_pasta_dados(self) -> None:
        """Abre no Explorer a pasta de dados que o programa está usando."""
        pasta = config.get_dados_dir()
        (pasta / "inbox").mkdir(parents=True, exist_ok=True)
        self.avisar(f"Pasta de dados: {pasta}")
        try:
            servicos.abrir_arquivo(pasta)
        except Exception as exc:  # noqa: BLE001
            self.avisar(f"Não foi possível abrir a pasta: {exc}", erro=True)

    def importar_inbox(self) -> None:
        try:
            mensagens = importacao.importar_inbox(self.conn)
        except Exception as exc:  # noqa: BLE001
            self.avisar(f"Erro ao importar e-mails: {exc}", erro=True)
            return

        if not mensagens:
            self.avisar(
                "Nenhum e-mail novo na fila de importação.\n"
                f"Pasta verificada: {config.get_inbox_dir()}"
            )
        else:
            for m in mensagens:
                self.avisar(m, erro=m.startswith("ERRO"))
        self.recarregar_tudo()

    def gerar_html(self) -> None:
        try:
            caminho = relatorios.gerar_html(self.conn, self.combo_status.currentText())
        except Exception as exc:  # noqa: BLE001
            self.avisar(f"Erro ao gerar relatório: {exc}", erro=True)
            return
        self.avisar("Relatório HTML gerado com sucesso!")
        self._abrir_caminho(str(caminho))

    def exportar_csv(self) -> None:
        try:
            caminho = relatorios.exportar_csv(self.conn)
        except Exception as exc:  # noqa: BLE001
            self.avisar(f"Erro ao exportar CSV: {exc}", erro=True)
            return
        self.avisar("Planilha CSV exportada com sucesso!")
        self._abrir_caminho(str(caminho))

    def _abrir_caminho(self, caminho: str) -> None:
        try:
            servicos.abrir_arquivo(caminho)
        except Exception as exc:  # noqa: BLE001
            # O anexo pode estar fora da pasta do sistema (caminho absoluto).
            try:
                servicos.abrir_arquivo(servicos.resolver_caminho_anexo(caminho))
            except Exception:  # noqa: BLE001
                self.avisar(f"Erro ao abrir arquivo: {exc}", erro=True)

    def limpar_filtros(self) -> None:
        self.campo_busca.clear()
        self.combo_status.setCurrentIndex(0)
        self.check_abertas.setChecked(True)
        self.filtro_de.definir(None)
        self.filtro_ate.definir(None)
        self.carregar_demandas()

    def resizeEvent(self, event) -> None:  # noqa: N802 - API do Qt
        super().resizeEvent(event)
        for filho in self.findChildren(Toast):
            filho._reposicionar()
