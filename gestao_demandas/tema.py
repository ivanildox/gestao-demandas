"""Tema claro da interface.

O Windows 11 aplica o "modo escuro" ao sistema e as aplicações PyQt6 o
herdam por padrão, o que deixa o sistema Gestion de Demandas com o fundo
cinza-escuro. Aqui o tema é fixado em **claro**, independentemente da
configuração do sistema operacional.

A abordagem usa o estilo **Fusion** (consistente em qualquer Windows) com uma
paleta explicitamente clara, de modo que nenhum componente fique com cores
invertidas.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QStyledItemDelegate,
    QStyleFactory,
    QWidget,
)

# Paleta de cores do tema claro.
FUNDO = "#f1f5f9"  # fundo das janelas
CARTAO = "#ffffff"  # campos de texto, tabelas e botões
TEXTO = "#0f172a"  # texto principal
TEXTO_SUAVE = "#64748b"  # legendas e textos secundários
BORDA = "#cbd5e1"
DESTAQUE = "#2563eb"  # azul de seleção e foco


def paleta_clara() -> QPalette:
    """Monta a paleta de cores clara do aplicativo."""
    paleta = QPalette()

    paleta.setColor(QPalette.ColorRole.Window, QColor(FUNDO))
    paleta.setColor(QPalette.ColorRole.WindowText, QColor(TEXTO))
    paleta.setColor(QPalette.ColorRole.Base, QColor(CARTAO))
    paleta.setColor(QPalette.ColorRole.AlternateBase, QColor("#f8fafc"))
    paleta.setColor(QPalette.ColorRole.Text, QColor(TEXTO))
    paleta.setColor(QPalette.ColorRole.Button, QColor(CARTAO))
    paleta.setColor(QPalette.ColorRole.ButtonText, QColor(TEXTO))
    paleta.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    paleta.setColor(QPalette.ColorRole.ToolTipBase, QColor(TEXTO))
    paleta.setColor(QPalette.ColorRole.ToolTipText, QColor("#ffffff"))
    paleta.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXTO_SUAVE))
    paleta.setColor(QPalette.ColorRole.Light, QColor("#e2e8f0"))
    paleta.setColor(QPalette.ColorRole.Midlight, QColor(BORDA))
    paleta.setColor(QPalette.ColorRole.Mid, QColor("#94a3b8"))
    paleta.setColor(QPalette.ColorRole.Dark, QColor(TEXTO_SUAVE))
    paleta.setColor(QPalette.ColorRole.Shadow, QColor("#94a3b8"))
    paleta.setColor(QPalette.ColorRole.Link, QColor(DESTAQUE))
    paleta.setColor(QPalette.ColorRole.LinkVisited, QColor("#7c3aed"))
    paleta.setColor(QPalette.ColorRole.Highlight, QColor(DESTAQUE))
    paleta.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))

    # Cores dos widgets desabilitados.
    desabilitado = QPalette.ColorGroup.Disabled
    paleta.setColor(desabilitado, QPalette.ColorRole.WindowText, QColor("#94a3b8"))
    paleta.setColor(desabilitado, QPalette.ColorRole.Text, QColor("#94a3b8"))
    paleta.setColor(desabilitado, QPalette.ColorRole.ButtonText, QColor("#94a3b8"))
    paleta.setColor(desabilitado, QPalette.ColorRole.Window, QColor(FUNDO))

    return paleta


# Folha de estilo do calendário dos campos de data.
#
# A paleta do aplicativo não alcança esse calendário: ele abre como janela
# popup e, dentro de um diálogo, acaba herdando a paleta escura do Windows.
# Estas regras são aplicadas **no próprio calendário** (é o único jeito de
# vencer a herança) e o mantêm no tema claro.
ESTILO_CALENDARIO = """
QWidget {
    background-color: #ffffff;
    color: #0f172a;
}
QWidget#qt_calendar_navigationbar {
    background-color: #f1f5f9;
}
QToolButton {
    color: #0f172a;
    background-color: transparent;
    border: none;
    border-radius: 4px;
    padding: 3px 8px;
    font-weight: 600;
}
QToolButton:hover {
    background-color: #e2e8f0;
}
QToolButton:pressed {
    background-color: #cbd5e1;
}
QToolButton::menu-indicator {
    image: none;
}
QSpinBox {
    color: #0f172a;
    background-color: transparent;
    border: none;
}
QSpinBox::up-button, QSpinBox::down-button {
    width: 0;
}
QAbstractItemView {
    background-color: #ffffff;
    color: #0f172a;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    outline: 0;
}
QMenu {
    background-color: #ffffff;
    color: #0f172a;
}
"""

ESTILO_POPUP_COMBO = """
QListView {
    background-color: #ffffff;
    color: #0f172a;
    outline: 0;
}
QListView::item:hover {
    background-color: #dbeafe;
    color: #0f172a;
}
QListView::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}
QListView::item:selected:hover {
    background-color: #1d4ed8;
    color: #ffffff;
}
"""


def estilizar_combo(combo: QComboBox) -> None:
    """Aplica destaque de hover diretamente à lista popup do combo.

    O QComboBox usa por padrão um delegate interno (QComboMenuDelegate) que
    não renderiza o fundo definido na folha de estilo (QSS) para os itens
    selecionados/sob o mouse, mas aplica a cor branca de texto de destaque
    (HighlightedText) da paleta, tornando a opção sob o mouse invisível
    (branco sobre branco). O uso de `QStyledItemDelegate` garante que tanto
    o fundo quanto o texto sejam renderizados corretamente conforme o estilo.
    """
    combo.setItemDelegate(QStyledItemDelegate(combo))
    popup = combo.view()
    popup.setMouseTracking(True)
    popup.viewport().setMouseTracking(True)
    popup.setStyleSheet(ESTILO_POPUP_COMBO)


def estilizar_calendario(calendario: QWidget) -> None:
    """Deixa o calendário de um `QDateEdit` no tema claro.

    Deve ser chamada no `QCalendarWidget` devolvido por
    `QDateEdit.calendarWidget()`. Sem isso o popup aparece escuro quando o
    Windows está no modo escuro, mesmo com a paleta clara do aplicativo.
    """
    calendario.setPalette(paleta_clara())
    calendario.setStyleSheet(ESTILO_CALENDARIO)

    # O popup que envolve o calendário também herda a paleta do sistema.
    pai = calendario.parentWidget()
    if pai is not None:
        pai.setPalette(paleta_clara())
        pai.setAutoFillBackground(True)


def aplicar_tema_claro(app: QApplication) -> None:
    """Aplica o tema claro ao aplicativo.

    Deve ser chamada logo após a criação do `QApplication`, antes de
    qualquer widget ser instanciado.
    """
    estilo = QStyleFactory.create("Fusion")
    if estilo is not None:
        app.setStyle(estilo)

    # A paleta explícita é o que garante o tema claro: todos os widgets
    # (janelas, campos, tabelas, menus e tooltips) passam a usar cores
    # claras, independentemente do modo escuro do sistema operacional.
    app.setPalette(paleta_clara())

    # O calendário dos campos de data recebe a folha de estilo própria em
    # `estilizar_calendario()`, chamada por `EditorDataOpcional`.
