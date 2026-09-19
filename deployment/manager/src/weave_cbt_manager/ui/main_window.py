"""Main desktop window for the WEAVE CBT Manager."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QMainWindow, QStackedWidget

from weave_cbt_manager.constants import APP_NAME, DEFAULT_SERVER_URL
from weave_cbt_manager.core.installer import InstallEvent, InstallerService
from weave_cbt_manager.platforms.base import PlatformAdapter
from weave_cbt_manager.ui.pages.dashboard import DashboardPage
from weave_cbt_manager.ui.pages.installing import InstallingPage
from weave_cbt_manager.ui.pages.setup import SetupPage


class InstallWorker(QObject):
    progress = Signal(object)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, installer: InstallerService) -> None:
        super().__init__()
        self.installer = installer

    @Slot()
    def run(self) -> None:
        try:
            self.installer.install(callback=self.progress.emit)
        except Exception as exc:  # UI boundary: surface a safe message to the user.
            self.failed.emit(str(exc))
            return
        self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        platform: PlatformAdapter,
        installer: InstallerService,
    ) -> None:
        super().__init__()
        self.platform = platform
        self.installer = installer
        self._install_thread: QThread | None = None
        self._install_worker: InstallWorker | None = None

        self.setWindowTitle(APP_NAME)
        self.resize(780, 540)
        self.setMinimumSize(680, 480)

        self.stack = QStackedWidget()
        self.setup_page = SetupPage()
        self.installing_page = InstallingPage()
        self.dashboard_page = DashboardPage()

        self.stack.addWidget(self.setup_page)
        self.stack.addWidget(self.installing_page)
        self.stack.addWidget(self.dashboard_page)
        self.setCentralWidget(self.stack)

        self.setup_page.install_requested.connect(self.start_installation)
        self.dashboard_page.refresh_requested.connect(self.refresh_dashboard)
        self.dashboard_page.open_requested.connect(self.open_cbt)
        self.dashboard_page.restart_requested.connect(self.restart_server)

        state = self.installer.state_store.load()
        if state.installed:
            self.stack.setCurrentWidget(self.dashboard_page)
            self.refresh_dashboard()
        else:
            self.stack.setCurrentWidget(self.setup_page)

    @Slot()
    def start_installation(self) -> None:
        if self._install_thread and self._install_thread.isRunning():
            return

        self.stack.setCurrentWidget(self.installing_page)
        self.installing_page.update_progress(0, "Starting setup...")

        thread = QThread(self)
        worker = InstallWorker(self.installer)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self.on_install_progress)
        worker.finished.connect(self.on_install_complete)
        worker.failed.connect(self.on_install_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_install_worker)

        self._install_thread = thread
        self._install_worker = worker
        thread.start()

    @Slot(object)
    def on_install_progress(self, event: InstallEvent) -> None:
        self.installing_page.update_progress(event.progress, event.message)

    @Slot()
    def on_install_complete(self) -> None:
        self.stack.setCurrentWidget(self.dashboard_page)
        self.refresh_dashboard()

    @Slot(str)
    def on_install_failed(self, message: str) -> None:
        self.setup_page.set_error(message)
        self.stack.setCurrentWidget(self.setup_page)

    @Slot()
    def _clear_install_worker(self) -> None:
        self._install_thread = None
        self._install_worker = None

    @Slot()
    def refresh_dashboard(self) -> None:
        report = self.installer.health.inspect()
        self.dashboard_page.set_report(
            report,
            lan_address=self.platform.lan_address(),
        )

    @Slot()
    def open_cbt(self) -> None:
        self.platform.open_url(f"{DEFAULT_SERVER_URL}/staff")

    @Slot()
    def restart_server(self) -> None:
        self.installer.docker.restart()
        self.refresh_dashboard()
