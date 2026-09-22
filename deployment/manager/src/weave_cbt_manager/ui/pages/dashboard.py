"""Operational dashboard with clear readiness and classroom entry points."""
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget
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
    database_credentials_requested = Signal()
    database_console_requested = Signal()
    network_enable_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.lan_url = ""
        self.server_ready = False
        self.current_lan_ip = None
        self.network_access = None
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
        net_layout.addWidget(label("Students open this address on computers connected to the same trusted school network."))
        row = QHBoxLayout()
        self.network_address = label("Checking network address…", "section")
        self.network_address.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(self.network_address, 1)
        self.copy_button = button("Copy student link", self._copy)
        self.copy_button.setEnabled(False)
        row.addWidget(self.copy_button)
        net_layout.addLayout(row)
        self.network_detail = label("Checking the Windows network profile…")
        net_layout.addWidget(self.network_detail)
        self.enable_network_button = button(
            "Enable school network access",
            self.network_enable_requested.emit,
            primary=True,
        )
        self.enable_network_button.hide()
        net_layout.addWidget(self.enable_network_button, alignment=Qt.AlignLeft)
        net_layout.addWidget(label("WEAVE only opens classroom access on Windows Private or Domain networks. New Public networks require one administrator approval."))
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
        maintenance_layout.addWidget(label("Database administration", "section"))
        maintenance_layout.addWidget(label("Weave generates a strong local PostgreSQL password automatically. An administrator can reveal it here when direct database access is genuinely needed. PostgreSQL remains private to this server and is not exposed to the school LAN."))
        database_row = QHBoxLayout()
        reveal = button("Reveal database credentials", self.database_credentials_requested.emit)
        console = button("Open PostgreSQL console", self.database_console_requested.emit)
        database_row.addWidget(reveal)
        database_row.addWidget(console)
        maintenance_layout.addLayout(database_row)
        self.action_buttons.extend([reveal, console])
        maintenance_layout.addSpacing(10)
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
        for widget in [*self.action_buttons, self.install_update_button, self.enable_network_button]:
            widget.setEnabled(not busy)

    def _render_network(self) -> None:
        status = self.network_access
        self.lan_url = ""
        self.copy_button.setEnabled(False)
        self.copy_button.setText("Copy student link")
        self.enable_network_button.hide()

        if status is None:
            self.network_address.setText("Checking network access…")
            self.network_detail.setText("Checking the Windows network profile…")
            return

        if not status.connected:
            self.network_address.setText("Connect this computer to the school Wi-Fi or Ethernet network")
            self.network_detail.setText("No active classroom network was detected.")
            return

        network_name = status.network_name or status.interface_alias or "Current network"
        if status.requires_approval:
            self.network_address.setText("School network access is currently blocked by Windows")
            self.network_detail.setText(
                f"{network_name} is marked Public. Approve it only if this is a trusted school network."
            )
            self.enable_network_button.show()
            return

        if not status.trusted:
            self.network_address.setText("School network access is not ready")
            self.network_detail.setText(
                f"WEAVE could not verify the Windows network profile for {network_name}."
            )
            return

        self.network_detail.setText(
            f"{network_name} · {status.category} · classroom access enabled"
        )
        if self.server_ready and status.lan_ip:
            self.lan_url = f"http://{status.lan_ip}/student"
            self.network_address.setText(self.lan_url)
            self.copy_button.setEnabled(True)
        else:
            self.network_address.setText("Available when the server is healthy")

    def set_health(self, snapshot, lan_ip: str | None) -> None:
        self.server_ready = snapshot.healthy
        self.current_lan_ip = lan_ip
        self.status.setText("●  Your server is ready" if snapshot.healthy else "●  Your server needs attention")
        self.status.setStyleSheet("color: #047857;" if snapshot.healthy else "color: #b45309;")
        self.detail.setText("Weave is ready to open on this computer." if snapshot.healthy else snapshot.detail)
        self.open_button.setEnabled(snapshot.healthy)
        for widget, title, ready in zip(self.indicators, ("Local runtime", "Application services", "Staff portal"),
                                        (snapshot.runtime_ready, snapshot.services_ready, snapshot.web_reachable)):
            widget.setText(("✓  " if ready else "○  ") + title)
            widget.setStyleSheet("color: #047857;" if ready else "color: #64748b;")
        self._render_network()

    def set_network_access(self, status) -> None:
        self.network_access = status
        self._render_network()

    def set_update(self, message: str, *, available: bool) -> None:
        self.update_message.setText(message)
        self.install_update_button.setVisible(available)
