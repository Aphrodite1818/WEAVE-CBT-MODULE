"""Main PySide6 window for installation and maintenance."""

from __future__ import annotations

import subprocess
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtWidgets import QInputDialog, QMainWindow, QMessageBox, QStackedWidget

from .. import __version__
from ..app import ManagerController
from ..constants import application_root
from ..core.installer import InstallationProgress
from ..core.updates import ReleaseInfo, is_newer
from .pages.dashboard import DashboardPage
from .pages.installing import InstallingPage
from .pages.setup import SetupPage


class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal()
    progress = Signal(str)


class Worker(QRunnable):
    def __init__(self, function: Callable[..., Any], *args: Any, with_progress: bool = False, **kwargs: Any) -> None:
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.with_progress = with_progress
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            if self.with_progress:
                self.kwargs["progress"] = self.signals.progress.emit
            value = self.function(*self.args, **self.kwargs)
        except Exception as exc:
            self.signals.error.emit(str(exc))
        else:
            self.signals.result.emit(value)
        finally:
            self.signals.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self, controller: ManagerController, *, force_setup: bool = False) -> None:
        super().__init__()
        self.controller = controller
        self.latest_release: ReleaseInfo | None = None
        self.pool = QThreadPool.globalInstance()
        self.setWindowTitle("WEAVE CBT Manager")
        self.resize(760, 600)
        self.stack = QStackedWidget()
        self.installing = InstallingPage()
        self.setup = SetupPage()
        self.dashboard = DashboardPage()
        for page in (self.installing, self.setup, self.dashboard):
            self.stack.addWidget(page)
        self.setCentralWidget(self.stack)
        self.setup.install_requested.connect(self._install_application)
        self.installing.restart_requested.connect(self.controller.startup.restart_windows)
        self.dashboard.refresh_requested.connect(self._refresh_health)
        self.dashboard.restart_requested.connect(self._restart_server)
        self.dashboard.repair_requested.connect(self._repair)
        self.dashboard.update_check_requested.connect(self._check_updates)
        self.dashboard.install_update_requested.connect(self._install_update)
        self.dashboard.uninstall_requested.connect(self._launch_uninstaller)
        self.dashboard.purge_requested.connect(self._purge)
        if controller.installation_present():
            self._show_dashboard()
        else:
            self._prepare_system()

    def _run(self, function: Callable[..., Any], *args: Any, on_result: Callable[[Any], None] | None = None, on_error: Callable[[str], None] | None = None, with_progress: bool = False, **kwargs: Any) -> None:
        worker = Worker(function, *args, with_progress=with_progress, **kwargs)
        if on_result is not None:
            worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error or self._show_error)
        if with_progress:
            worker.signals.progress.connect(self.installing.set_message)
        self.pool.start(worker)

    def _prepare_system(self) -> None:
        self.stack.setCurrentWidget(self.installing)
        self.installing.set_message("Checking Windows and preparing the local server…")
        def prepare(*, progress: Callable[[str], None]) -> Any:
            return self.controller.prepare_infrastructure(lambda item: progress(item.message))
        def completed(result: Any) -> None:
            if result.reboot_required:
                self.installing.show_reboot()
            else:
                self.stack.setCurrentWidget(self.setup)
        self._run(prepare, on_result=completed, on_error=self.installing.show_error, with_progress=True)

    def _install_application(self, database_name: str, database_user: str, database_password: str) -> None:
        self.stack.setCurrentWidget(self.installing)
        self.installing.progress.show()
        self.installing.set_message("Creating the database and starting WEAVE CBT services…")
        self._run(
            self.controller.install_application,
            database_name=database_name, database_user=database_user, database_password=database_password,
            on_result=lambda _snapshot: (self._show_dashboard(), QMessageBox.information(self, "WEAVE CBT", "WEAVE CBT is installed and ready on this computer.")),
            on_error=self.installing.show_error,
        )

    def _show_dashboard(self) -> None:
        try:
            self.controller.startup.install_tasks()
        except Exception:
            pass
        self.stack.setCurrentWidget(self.dashboard)
        self._refresh_health()
        self._check_updates(silent=True)

    def _refresh_health(self) -> None:
        self._run(self.controller.status, on_result=lambda snapshot: self.dashboard.set_health(snapshot.healthy, snapshot.detail, self.controller.platform.lan_ip))

    def _restart_server(self) -> None:
        def restart() -> Any:
            self.controller.deployment.restart()
            return self.controller.health.wait_until_healthy(timeout_seconds=120)
        self._run(restart, on_result=lambda _value: self._refresh_health())

    def _repair(self) -> None:
        self._run(self.controller.repair, on_result=lambda _value: (self._refresh_health(), QMessageBox.information(self, "Repair complete", "WEAVE CBT services are healthy.")))

    def _check_updates(self, _checked: bool = False, *, silent: bool = False) -> None:
        def completed(release: ReleaseInfo) -> None:
            self.latest_release = release
            state = self.controller.state
            cbt_newer = bool(state.current_cbt_version and is_newer(release.cbt_version, state.current_cbt_version))
            manager_newer = is_newer(release.manager_version, __version__)
            available = cbt_newer or manager_newer
            if available:
                parts = []
                if cbt_newer:
                    parts.append(f"CBT {release.cbt_version}")
                if manager_newer:
                    parts.append(f"Manager {release.manager_version}")
                message = "Update available: " + " / ".join(parts)
                if release.release_notes:
                    message += f"\n\n{release.release_notes}"
            else:
                message = "WEAVE CBT is up to date."
            self.dashboard.set_update(message, available=available)
        def failed(message: str) -> None:
            self.dashboard.set_update(message, available=False)
            if not silent:
                self._show_error(message)
        self._run(self.controller.check_updates, on_result=completed, on_error=failed)

    def _install_update(self) -> None:
        if self.latest_release is None:
            self._check_updates()
            return
        answer = QMessageBox.question(self, "Install update", "WEAVE CBT will back up the database and restart local CBT services. Do not continue while an examination is running. Install the update now?")
        if answer != QMessageBox.Yes:
            return
        self._run(self.controller.install_available_update, self.latest_release, on_result=lambda message: QMessageBox.information(self, "Update", str(message)))

    def _launch_uninstaller(self) -> None:
        answer = QMessageBox.question(self, "Uninstall WEAVE CBT", "The Windows application will be removed, but local school data will be kept for recovery/reinstallation. Continue?")
        if answer != QMessageBox.Yes:
            return
        candidate = application_root() / "unins000.exe"
        if not candidate.exists():
            self._show_error("The Windows uninstaller could not be found. Use Windows Settings > Installed apps > WEAVE CBT.")
            return
        subprocess.Popen([str(candidate)], creationflags=subprocess.CREATE_NO_WINDOW)
        self.close()

    def _purge(self) -> None:
        value, accepted = QInputDialog.getText(self, "Permanently remove local data", "This permanently deletes the local CBT database, exams, results and configuration. Type DELETE to continue:")
        if not accepted or value != "DELETE":
            return
        self._run(self.controller.purge_all_data, on_result=lambda _value: QMessageBox.information(self, "WEAVE CBT", "All local WEAVE CBT data has been removed."))

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "WEAVE CBT", message)
