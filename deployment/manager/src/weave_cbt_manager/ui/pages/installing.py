"""Installation progress and reboot page."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget


class InstallingPage(QWidget):
    restart_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.title = QLabel("Preparing WEAVE CBT")
        self.title.setStyleSheet("font-size: 24px; font-weight: 600;")
        self.message = QLabel("Checking this computer and preparing the local server…")
        self.message.setWordWrap(True)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.restart_button = QPushButton("Restart Windows and continue")
        self.restart_button.hide()
        self.restart_button.clicked.connect(lambda _checked=False: self.restart_requested.emit())
        layout.addWidget(self.title)
        layout.addWidget(self.message)
        layout.addWidget(self.progress)
        layout.addWidget(self.restart_button)
        layout.addStretch(1)

    def set_message(self, message: str) -> None:
        self.message.setText(message)

    def show_reboot(self) -> None:
        self.title.setText("Windows restart required")
        self.message.setText("WEAVE CBT saved your setup progress. Restart Windows to continue configuring this server.")
        self.progress.hide()
        self.restart_button.show()

    def show_error(self, message: str) -> None:
        self.title.setText("Setup needs attention")
        self.message.setText(message)
        self.progress.hide()
