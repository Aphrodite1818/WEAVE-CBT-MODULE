"""Operational dashboard for an installed WEAVE CBT server."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget


class DashboardPage(QWidget):
    refresh_requested = Signal()
    restart_requested = Signal()
    repair_requested = Signal()
    update_check_requested = Signal()
    install_update_requested = Signal()
    uninstall_requested = Signal()
    purge_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("WEAVE CBT Manager")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(title)
        status_group = QGroupBox("Server status")
        grid = QGridLayout(status_group)
        self.status = QLabel("Checking…")
        self.local_address = QLabel("http://localhost")
        self.network_address = QLabel("—")
        grid.addWidget(QLabel("System"), 0, 0)
        grid.addWidget(self.status, 0, 1)
        grid.addWidget(QLabel("Local address"), 1, 0)
        grid.addWidget(self.local_address, 1, 1)
        grid.addWidget(QLabel("School network"), 2, 0)
        grid.addWidget(self.network_address, 2, 1)
        layout.addWidget(status_group)
        actions = QGroupBox("Maintenance")
        action_grid = QGridLayout(actions)
        for index, (text, signal) in enumerate([
            ("Refresh status", self.refresh_requested), ("Restart server", self.restart_requested),
            ("Repair", self.repair_requested), ("Check for updates", self.update_check_requested),
        ]):
            button = QPushButton(text)
            button.clicked.connect(lambda _checked=False, target=signal: target.emit())
            action_grid.addWidget(button, index // 2, index % 2)
        layout.addWidget(actions)
        update_group = QGroupBox("Updates")
        update_layout = QVBoxLayout(update_group)
        self.update_message = QLabel("No update check has been run yet.")
        self.update_message.setWordWrap(True)
        self.install_update_button = QPushButton("Install update")
        self.install_update_button.hide()
        self.install_update_button.clicked.connect(lambda _checked=False: self.install_update_requested.emit())
        update_layout.addWidget(self.update_message)
        update_layout.addWidget(self.install_update_button)
        layout.addWidget(update_group)
        danger = QGroupBox("Installation")
        danger_layout = QGridLayout(danger)
        uninstall = QPushButton("Uninstall (keep school data)")
        purge = QPushButton("Permanently remove all local data")
        uninstall.clicked.connect(lambda _checked=False: self.uninstall_requested.emit())
        purge.clicked.connect(lambda _checked=False: self.purge_requested.emit())
        danger_layout.addWidget(uninstall, 0, 0)
        danger_layout.addWidget(purge, 0, 1)
        layout.addWidget(danger)
        layout.addStretch(1)

    def set_health(self, healthy: bool, detail: str, lan_ip: str | None) -> None:
        self.status.setText("Running" if healthy else f"Needs attention — {detail}")
        self.network_address.setText(f"http://{lan_ip}" if lan_ip else "Network address unavailable")

    def set_update(self, message: str, *, available: bool) -> None:
        self.update_message.setText(message)
        self.install_update_button.setVisible(available)
