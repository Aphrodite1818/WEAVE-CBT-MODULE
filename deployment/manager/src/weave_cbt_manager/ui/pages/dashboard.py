"""Operational dashboard for an installed WEAVE CBT server."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from weave_cbt_manager.core.health import HealthReport


class DashboardPage(QWidget):
    refresh_requested = Signal()
    open_requested = Signal()
    restart_requested = Signal()

    def __init__(self) -> None:
        super().__init__()

        title = QLabel("WEAVE CBT Server")
        title.setObjectName("pageTitle")

        self.overall = QLabel("Checking server status...")
        self.overall.setObjectName("statusText")

        self.service_labels: dict[str, QLabel] = {}
        service_grid = QGridLayout()
        for row, service in enumerate(("postgres", "redis", "api", "worker", "nginx")):
            name = QLabel(service.capitalize())
            status = QLabel("Unknown")
            self.service_labels[service] = status
            service_grid.addWidget(name, row, 0)
            service_grid.addWidget(status, row, 1)

        self.address = QLabel("")
        self.address.setObjectName("pageDescription")

        self.open_button = QPushButton("Open WEAVE CBT")
        self.open_button.setObjectName("primaryButton")
        self.open_button.clicked.connect(self.open_requested.emit)

        refresh_button = QPushButton("Refresh Status")
        refresh_button.clicked.connect(self.refresh_requested.emit)

        restart_button = QPushButton("Restart Server")
        restart_button.clicked.connect(self.restart_requested.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(18)
        layout.addWidget(title)
        layout.addWidget(self.overall)
        layout.addLayout(service_grid)
        layout.addWidget(self.address)
        layout.addStretch()
        layout.addWidget(self.open_button)
        layout.addWidget(refresh_button)
        layout.addWidget(restart_button)

    def set_report(self, report: HealthReport, *, lan_address: str | None) -> None:
        self.overall.setText("Server Running" if report.healthy else "Server Needs Attention")
        for service, label in self.service_labels.items():
            label.setText("Running" if service in report.running_services else "Stopped")

        if lan_address:
            self.address.setText(
                f"Staff: http://{lan_address}/staff\n"
                f"Student: http://{lan_address}/student"
            )
        else:
            self.address.setText("Staff: http://localhost/staff")
