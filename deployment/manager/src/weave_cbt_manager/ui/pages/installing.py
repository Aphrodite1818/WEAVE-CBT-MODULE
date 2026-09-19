"""Installation progress page."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


class InstallingPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        title = QLabel("Installing WEAVE CBT")
        title.setObjectName("pageTitle")

        self.message = QLabel("Preparing installation...")
        self.message.setObjectName("pageDescription")
        self.message.setWordWrap(True)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(20)
        layout.addWidget(title)
        layout.addWidget(self.message)
        layout.addWidget(self.progress)
        layout.addStretch()

    def update_progress(self, value: int, message: str) -> None:
        self.progress.setValue(value)
        self.message.setText(message)
