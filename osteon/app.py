"""Ponto de entrada da aplicação Osteon (desktop)."""
from __future__ import annotations
import sys
from PySide6 import QtWidgets
from .ui.main_window import MainWindow


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Osteon Viewer")
    app.setOrganizationName("Osteon")
    win = MainWindow()
    win.show()
    win.open_demo()  # abre com o fantoma para o app não iniciar vazio
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
