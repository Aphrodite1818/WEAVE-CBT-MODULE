"""Responsive Windows manager; all runtime work stays off the Qt UI thread."""
from __future__ import annotations

import logging
import subprocess

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QMainWindow, QMessageBox, QScrollArea, QStackedWidget, QVBoxLayout, QWidget

from .. import __version__
from ..app import ManagerController
from ..build_metadata import BUILD_METADATA
from ..constants import application_root, log_directory
from ..core.updates import ReleaseInfo, is_newer
from .pages.dashboard import DashboardPage
from .pages.installing import InstallingPage
from .pages.setup import SetupPage
from .theme import STYLESHEET, label

logger = logging.getLogger(__name__)

from .brand import application_icon, mark_pixmap

class WorkerSignals(QObject):
    completed = Signal(object, object)
    progress = Signal(str)

class Worker(QRunnable):
    def __init__(self, function, *, on_result=None, on_error=None, with_progress=False):
        super().__init__()
        self.function = function
        self.on_result = on_result
        self.on_error = on_error
        self.with_progress = with_progress
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            kwargs = {"progress": self.signals.progress.emit} if self.with_progress else {}
            value = self.function(**kwargs)
        except Exception as exc:
            logger.exception("Manager operation failed")
            self.signals.completed.emit(None, str(exc))
        else:
            self.signals.completed.emit(value, None)

class MainWindow(QMainWindow):
    def __init__(self, controller: ManagerController, *, force_setup: bool = False) -> None:
        super().__init__()
        self.controller = controller
        self.latest_release: ReleaseInfo | None = None
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self._workers = {}
        self.busy = False
        self.setWindowTitle("Weave CBT · Server Manager")
        self.resize(1060, 820)
        self.setMinimumSize(860, 640)
        available = self.screen().availableGeometry()
        self.resize(min(1060, available.width() - 40), min(820, available.height() - 60))
        self.setStyleSheet(STYLESHEET)
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(36, 20, 36, 14)
        outer.setSpacing(10)
        header = QHBoxLayout()
        mark = label("")
        mark.setPixmap(mark_pixmap(48))
        mark.setFixedSize(48, 48)
        self.setWindowIcon(application_icon())
        header.addWidget(mark)
        header.addWidget(label("Weave", "brand"))
        header.addWidget(label("CBT  /  SERVER MANAGER"))
        header.addStretch()
        header.addWidget(label(BUILD_METADATA.channel.title(), "badge"))
        outer.addLayout(header)
        self.stack = QStackedWidget()
        self.installing = InstallingPage()
        self.setup = SetupPage()
        self.dashboard = DashboardPage()
        self.pages = {}
        for page in (self.installing, self.setup, self.dashboard):
            page.setObjectName("page")
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.pages[page] = scroll
            self.stack.addWidget(scroll)
        outer.addWidget(self.stack, 1)
        footer = QHBoxLayout()
        footer.addWidget(label("WEAVE CBT · WINDOWS"))
        footer.addStretch()
        footer.addWidget(label(f"Manager {__version__}"))
        outer.addLayout(footer)
        self.setCentralWidget(root)
        self.setup.install_requested.connect(self._prepare_system)
        self.installing.restart_requested.connect(self._restart_windows)
        self.installing.retry_requested.connect(self._prepare_system)
        self.installing.logs_requested.connect(self._open_logs)
        self.dashboard.logs_requested.connect(self._open_logs)
        self.dashboard.refresh_requested.connect(self._refresh_health)
        self.dashboard.restart_requested.connect(self._restart_server)
        self.dashboard.repair_requested.connect(self._repair)
        self.dashboard.update_check_requested.connect(self._check_updates)
        self.dashboard.install_update_requested.connect(self._install_update)
        self.dashboard.uninstall_requested.connect(self._launch_uninstaller)
        self.dashboard.purge_requested.connect(self._purge)
        self._show(self.installing)
        QTimer.singleShot(0, self._discover)

    def _show(self, page):
        self.stack.setCurrentWidget(self.pages[page])

    def _run(self, function, *, on_result=None, on_error=None, with_progress=False):
        if self.busy:
            return
        self.busy = True
        self.dashboard.set_busy(True)
        worker = Worker(function, on_result=on_result, on_error=on_error, with_progress=with_progress)
        self._workers[worker.signals] = worker
        worker.signals.completed.connect(self._completed)
        worker.signals.progress.connect(self._progress)
        self.pool.start(worker)

    @Slot(str)
    def _progress(self, message):
        logger.info("Setup: %s", message)
        self.installing.set_message(message)

    @Slot(object, object)
    def _completed(self, value, error):
        worker = self._workers.pop(self.sender())
        self.busy = False
        self.dashboard.set_busy(False)
        if error is not None:
            (worker.on_error or self._show_error)(error)
        elif worker.on_result:
            worker.on_result(value)

    def _discover(self):
        def discover():
            self.controller._check_channel()
            return self.controller.installation_present(), self.controller.state.installation_status
        def completed(result):
            installed, status = result
            if installed:
                self._show_dashboard()
                self._run(self.controller.background_start, on_result=lambda _: self._refresh_health(), on_error=self._startup_failed)
            elif status in {"awaiting_reboot", "setup_failed", "configuring"}:
                self._prepare_system()
            else:
                self._show(self.setup)
        self._run(discover, on_result=completed, on_error=self.installing.show_error)

    def _prepare_system(self):
        self._show(self.installing)
        self.installing.begin("Checking Windows and preparing your server…")
        def prepare(*, progress):
            return self.controller.prepare_infrastructure(lambda item: progress(item.message))
        def completed(result):
            if result.reboot_required:
                self.installing.show_reboot()
            else:
                self._install_application()
        self._run(prepare, on_result=completed, on_error=self.installing.show_error, with_progress=True)

    def _install_application(self):
        self.installing.begin("Preparing your Weave services…")
        self._run(self.controller.install_application, on_result=self._installed,
                  on_error=self.installing.show_error, with_progress=True)

    def _installed(self, snapshot):
        self._show_dashboard()
        self._render_health(snapshot, self.controller.platform.lan_ip())

    def _render_health(self, snapshot, lan_ip):
        self.dashboard.set_health(snapshot, lan_ip)
        if self.controller.state.startup_warning:
            self.dashboard.detail.setText(self.controller.state.startup_warning)

    def _startup_failed(self, message):
        from ..core.health import HealthSnapshot
        self.dashboard.set_health(HealthSnapshot(False, False, False, message), None)

    def _show_dashboard(self):
        self._show(self.dashboard)

    def _refresh_health(self):
        def inspect():
            return self.controller.status(), self.controller.platform.lan_ip()
        self._run(inspect, on_result=lambda result: self._render_health(*result), on_error=self._startup_failed)

    def _restart_server(self):
        if QMessageBox.question(self, "Restart server", "Restarting interrupts connected staff and students. Continue only when no exam is in progress.") != QMessageBox.Yes:
            return
        def restart():
            self.controller.docker.ensure_ready()
            if self.controller.deployment.has_exam_in_progress():
                raise RuntimeError("An examination is active. Close it before restarting the server.")
            self.controller.deployment.restart()
            return self.controller.health.wait_until_healthy(timeout_seconds=120)
        self._run(restart, on_result=lambda snapshot: self.dashboard.set_health(snapshot, self.controller.platform.lan_ip()))

    def _repair(self):
        self._run(self.controller.repair, on_result=lambda snapshot: self.dashboard.set_health(snapshot, self.controller.platform.lan_ip()))

    def _check_updates(self):
        def completed(release):
            self.latest_release = release
            state = self.controller.state
            available = bool(state.current_cbt_version and is_newer(release.cbt_version, state.current_cbt_version)) or is_newer(release.manager_version, __version__)
            message = f"Available: Weave {release.cbt_version} · Manager {release.manager_version}" if available else "You're up to date."
            self.dashboard.set_update(message, available=available)
        self._run(self.controller.check_updates, on_result=completed,
                  on_error=lambda message: self.dashboard.set_update(message, available=False))

    def _install_update(self):
        if not self.latest_release:
            return
        if QMessageBox.question(self, "Install update", "Back up the database and install the available update? Services will restart. Finish any examinations first.") != QMessageBox.Yes:
            return
        self._run(lambda: self.controller.install_available_update(self.latest_release),
                  on_result=lambda message: (self._refresh_health(), QMessageBox.information(self, "Update", message)))

    def _restart_windows(self):
        if QMessageBox.question(self, "Restart Windows", "Save your work in other applications before restarting. Restart now?") == QMessageBox.Yes:
            self.controller.startup.restart_windows()

    def _open_logs(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_directory())))

    def _launch_uninstaller(self):
        if QMessageBox.question(self, "Uninstall manager", "Remove the Windows manager and stop the server? School data is kept for reinstallation.") != QMessageBox.Yes:
            return
        candidate = application_root() / "unins000.exe"
        if not candidate.exists():
            self._show_error("Use Windows Settings > Installed apps > WEAVE CBT to uninstall.")
            return
        subprocess.Popen([str(candidate)], creationflags=subprocess.CREATE_NO_WINDOW)
        self.close()

    def _purge(self):
        value, accepted = QInputDialog.getText(self, "Delete local school data", "This permanently deletes local exams, results and configuration. Type DELETE to continue:")
        if accepted and value == "DELETE":
            self._run(self.controller.purge_all_data, on_result=lambda _: self._show(self.setup))

    def _show_error(self, message):
        QMessageBox.critical(self, "Weave needs attention", message)

    def closeEvent(self, event):
        if self.busy:
            QMessageBox.information(self, "Operation in progress", "Wait for the current operation to finish before closing the manager.")
            event.ignore()
        else:
            event.accept()
