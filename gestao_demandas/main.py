"""Ponto de entrada do aplicativo.

Uso:
    .venv\\Scripts\\python.exe -m gestao_demandas
    .venv\\Scripts\\python.exe principal.py
"""

from __future__ import annotations

import sys
import traceback

from PyQt6.QtWidgets import QApplication, QMessageBox

from . import banco, config
from .tema import aplicar_tema_claro


def _excepthook(tipo, valor, tb) -> None:
    """Exibe erros não capturados em janela e os escreve no console."""
    texto = "".join(traceback.format_exception(tipo, valor, tb))
    stderr = getattr(sys, "stderr", None)
    if stderr is not None:
        try:
            stderr.write(texto)
        except Exception:  # noqa: BLE001 -.stderr de janela pode falhar
            pass
    if QApplication.instance() is not None:
        QMessageBox.critical(None, "Erro inesperado", texto)
    else:
        # Nenhuma janela criada ainda: QApplication temporária só p/ o aviso.
        app_tmp = QApplication(sys.argv)
        QMessageBox.critical(None, "Erro inesperado", texto)
        app_tmp.quit()


def criar_aplicacao() -> QApplication:
    """Cria o `QApplication` já com o tema claro aplicado."""
    app = QApplication(sys.argv)
    app.setApplicationName(config.TITULO_APP)
    # Sem `setApplicationDisplayName`: no Windows o Qt acrescenta
    # " - <displayName>" a todo título de janela que não termine com ele,
    # o que duplicaria o nome no título da janela principal.
    app.setOrganizationName(config.TITULO_APP)
    aplicar_tema_claro(app)
    return app


def main() -> int:
    sys.excepthook = _excepthook
    # Garante inicialização e migrações do banco SQLite antes de abrir a janela.
    try:
        conn = banco.conectar()
    except Exception as exc:  # noqa: BLE001
        app = criar_aplicacao()
        QMessageBox.critical(
            None,
            "Erro ao abrir o banco de dados",
            f"Não foi possível inicializar o banco SQLite:\n{exc}\n\n"
            f"Caminho esperado: {config.get_db_path()}",
        )
        return 1

    app = criar_aplicacao()

    from .app_ui import JanelaPrincipal

    janela = JanelaPrincipal(conn)
    # Abre maximizada, ocupando toda a área de trabalho.
    janela.showMaximized()

    codigo = app.exec()
    conn.close()
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
