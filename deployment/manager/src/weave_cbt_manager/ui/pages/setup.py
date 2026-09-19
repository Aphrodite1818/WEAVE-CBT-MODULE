"""Initial WEAVE CBT setup page."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class SetupPage(QWidget):
    install_requested = Signal()

    def __init__(self) -> None:
        super().__init__()

        title = QLabel("Set up WEAVE CBT")
        title.setObjectName("pageTitle")

        description = QLabel(
            "This computer will become the local WEAVE CBT server. "
            "The Manager will prepare configuration, download required services, "
            "start the server and verify that it is ready."
        )
        description.setWordWrap(True)
        description.setObjectName("pageDescription")

        self.status = QLabel("Ready to begin setup.")
        self.status.setObjectName("statusText")

        self.install_button = QPushButton("Set Up WEAVE CBT")
        self.install_button.setObjectName("primaryButton")
        self.install_button.clicked.connect(self.install_requested.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(18)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(12)
        layout.addWidget(self.status)
        layout.addStretch()
        layout.addWidget(self.install_button)

    def set_error(self, message: str) -> None:
        self.status.setText(message)
