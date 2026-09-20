"""First-install database configuration page."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget


class SetupPage(QWidget):
    install_requested = Signal(str, str, str)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Set up your local CBT server")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        body = QLabel("Choose the local PostgreSQL details used only by this WEAVE CBT server. WEAVE manages the cloud connection automatically.")
        body.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(body)
        group = QGroupBox("Database configuration")
        form = QFormLayout(group)
        self.database_name = QLineEdit("weave_cbt")
        self.database_user = QLineEdit("weave")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.Password)
        form.addRow("Database name", self.database_name)
        form.addRow("Database username", self.database_user)
        form.addRow("Database password", self.password)
        form.addRow("Confirm password", self.confirm_password)
        layout.addWidget(group)
        self.error = QLabel("")
        self.error.setStyleSheet("color: #b91c1c;")
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.install_button = QPushButton("Install WEAVE CBT")
        self.install_button.clicked.connect(self._submit)
        layout.addWidget(self.install_button)
        layout.addStretch(1)

    def _submit(self) -> None:
        if self.password.text() != self.confirm_password.text():
            self.error.setText("The database passwords do not match.")
            return
        self.error.clear()
        self.install_requested.emit(self.database_name.text(), self.database_user.text(), self.password.text())
