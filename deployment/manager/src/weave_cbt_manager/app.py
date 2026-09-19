"""PySide6 desktop application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from weave_cbt_manager.constants import APP_NAME
from weave_cbt_manager.core.installer import InstallerService
from weave_cbt_manager.platforms.windows import WindowsPlatform
from weave_cbt_manager.ui.main_window import MainWindow


STYLESHEET = """
QWidget {
    background: #f7f9fc;
    color: #172033;
    font-family: "Segoe UI";
    font-size: 14px;
}
QLabel#pageTitle {
    font-size: 28px;
    font-weight: 700;
}
QLabel#pageDescription {
    color: #5c667a;
    font-size: 14px;
}
QLabel#statusText {
    font-size: 16px;
    font-weight: 600;
}
QPushButton {
    min-height: 38px;
    padding: 0 18px;
    border: 1px solid #d7ddea;
    border-radius: 8px;
    background: #ffffff;
}
QPushButton:hover {
    background: #f0f4fa;
}
QPushButton#primaryButton {
    background: #1f4fd6;
    color: white;
    border: none;
    font-weight: 600;
}
QPushButton#primaryButton:hover {
    background: #173fab;
}
QProgressBar {
    min-height: 18px;
    border: 1px solid #d7ddea;
    border-radius: 8px;
    background: #ffffff;
    text-align: center;
}
QProgressBar::chunk {
    border-radius: 7px;
    background: #1f4fd6;
}
"""


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(STYLESHEET)

    platform = WindowsPlatform()
    installer = InstallerService(platform)
    window = MainWindow(platform=platform, installer=installer)
    window.show()

    return app.exec()
