"""Operational dashboard with clear readiness and classroom entry points."""
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from ..theme import button, card, label

class DashboardPage(QWidget):
    refresh_requested = Signal()
    restart_requested = Signal()
    repair_requested = Signal()
    update_check_requested = Signal()
    install_update_requested = Signal()
    uninstall_requested = Signal()
    purge_requested = Signal()
    logs_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.lan_url = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(18)
        layout.addWidget(label("SERVER OVERVIEW", "eyebrow"))
        layout.addWidget(label("Your classroom starts here.", "heading"))
        layout.addWidget(label("Manage this computer, open Weave and connect students on your school network."))
        status_card, status_layout = card()
        heading = QHBoxLayout()
        self.status = label("Checking your server", "section")
        heading.addWidget(self.status, 1)
        self.open_button = button("Open Weave  ↗", lambda: QDesktopServices.openUrl(QUrl("http://localhost/staff")), primary=True)
        self.open_button.setEnabled(False)
        heading.addWidget(self.open_button)
        status_layout.addLayout(heading)
        self.detail = label("Preparing a live status check…")
        status_layout.addWidget(self.detail)
        self.indicators = []
        checks = QHBoxLayout()
        for text in ("Local runtime", "Application services", "Staff portal"):
            item = label("○  " + text)
            checks.addWidget(item)
            self.indicators.append(item)
        status_layout.addLayout(checks)
        layout.addWidget(status_card)
        network, net_layout = card()
        net_layout.addWidget(label("Connect your classroom", "section"))
        net_layout.addWidget(label("Students open this address on computers connected to the same school network."))
        row = QHBoxLayout()
        self.network_address = label("Checking network address…", "section")
        self.network_address.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(self.network_address, 1)
        self.copy_button = button("Copy student link", self._copy)
        self.copy_button.setEnabled(False)
        row.addWidget(self.copy_button)
        net_layout.addLayout(row)
        net_layout.addWidget(label("Use a Private or Domain network in Windows. Keep this server awake and signed in during exams."))
        layout.addWidget(network)
        actions = QHBoxLayout()
        self.action_buttons = []
        for text, signal in [("Refresh status", self.refresh_requested), ("Restart server", self.restart_requested),
                             ("Repair server", self.repair_requested), ("Check for updates", self.update_check_requested)]:
            item = button(text, signal.emit)
            self.action_buttons.append(item)
            actions.addWidget(item)
        layout.addLayout(actions)
        self.update_message = label("Check for updates when you are connected to the internet.")
        layout.addWidget(self.update_message)
        self.install_update_button = button("Install available update", self.install_update_requested.emit, primary=True)
        self.install_update_button.hide()
        layout.addWidget(self.install_update_button)
        maintenance_toggle = button("Diagnostics and installation settings", self._toggle_maintenance)
        maintenance_toggle.setObjectName("link")
        layout.addWidget(maintenance_toggle, alignment=Qt.AlignLeft)
        self.maintenance, maintenance_layout = card()
        maintenance_layout.addWidget(label("Installation settings", "section"))
        maintenance_layout.addWidget(label("Uninstalling the manager keeps school data. Permanent removal cannot be undone."))
        row = QHBoxLayout()
        for text, signal in [("Open logs", self.logs_requested), ("Uninstall manager", self.uninstall_requested), ("Delete local data", self.purge_requested)]:
            item = button(text, signal.emit)
            if signal == self.purge_requested:
                item.setObjectName("danger")
            row.addWidget(item)
            self.action_buttons.append(item)
        maintenance_layout.addLayout(row)
        self.maintenance.hide()
        layout.addWidget(self.maintenance)
        layout.addStretch()

    def _toggle_maintenance(self) -> None:
        self.maintenance.setVisible(not self.maintenance.isVisible())

    def _copy(self) -> None:
        if self.lan_url:
            QApplication.clipboard().setText(self.lan_url)
            self.copy_button.setText("Link copied")

    def set_busy(self, busy: bool) -> None:
        for widget in [*self.action_buttons, self.install_update_button]:
            widget.setEnabled(not busy)

    def set_health(self, snapshot, lan_ip: str | None) -> None:
        self.status.setText("●  Your server is ready" if snapshot.healthy else "●  Your server needs attention")
        self.status.setStyleSheet("color: #047857;" if snapshot.healthy else "color: #b45309;")
        self.detail.setText("Weave is ready to open on this computer." if snapshot.healthy else snapshot.detail)
        self.open_button.setEnabled(snapshot.healthy)
        for widget, title, ready in zip(self.indicators, ("Local runtime", "Application services", "Staff portal"),
                                        (snapshot.runtime_ready, snapshot.services_ready, snapshot.web_reachable)):
            widget.setText(("✓  " if ready else "○  ") + title)
            widget.setStyleSheet("color: #047857;" if ready else "color: #64748b;")
        self.lan_url = f"http://{lan_ip}/student" if lan_ip and snapshot.healthy else ""
        self.network_address.setText(self.lan_url or "Available when the server and school network are ready")
        self.copy_button.setEnabled(bool(self.lan_url))
        self.copy_button.setText("Copy student link")

    def set_update(self, message: str, *, available: bool) -> None:
        self.update_message.setText(message)
        self.install_update_button.setVisible(available)
