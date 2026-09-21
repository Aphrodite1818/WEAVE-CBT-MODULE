"""Composition root for the Windows WEAVE CBT Manager."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import shutil
import subprocess
from typing import Callable

from . import __version__
from .build_metadata import BUILD_METADATA
from .constants import compose_asset_path, log_directory, nginx_asset_path, rootfs_archive_path, runtime_install_directory, state_file
from .core.backup import BackupService
from .core.config import ConfigService, InstallationConfigInput, render_runtime_env
from .core.deployment import DeploymentService
from .core.health import HealthService, HealthSnapshot
from .core.installer import InstallationProgress, InstallationResult, InstallerService
from .core.prerequisites import PrerequisitePolicy, PrerequisiteService
from .core.startup import WindowsStartupService
from .core.updates import ReleaseInfo, UpdateService, is_newer
from .platforms.windows import WindowsPlatform
from .runtime.docker import DockerService
from .runtime.providers.windows_wsl import WindowsWSLRuntime
from .state import ManagerState, StateStore

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    directory = log_directory()
    directory.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(logging.INFO)
    handler = RotatingFileHandler(directory / "manager.log", maxBytes=2_000_000, backupCount=4, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)


class ManagerController:
    def __init__(self) -> None:
        self.platform = WindowsPlatform()
        self.runtime = WindowsWSLRuntime(rootfs_archive=rootfs_archive_path(), install_directory=runtime_install_directory())
        self.docker = DockerService(self.runtime)
        self.prerequisites = PrerequisiteService(
            platform=self.platform, runtime=self.runtime, docker=self.docker,
            policy=PrerequisitePolicy(minimum_memory_gb=8.0, minimum_free_disk_gb=4.0, supported_architectures=frozenset({"x86_64"})),
        )
        self.deployment = DeploymentService(self.runtime, self.docker)
        self.health = HealthService(self.deployment)
        self.state_store = StateStore(state_file())
        self.startup = WindowsStartupService()
        self.backup = BackupService(self.runtime, self.deployment)
        self.updates = UpdateService(build_metadata=BUILD_METADATA, manager_version=__version__, deployment=self.deployment, health=self.health, backup=self.backup, state_store=self.state_store)
        self.config = ConfigService(BUILD_METADATA)

    @property
    def state(self) -> ManagerState:
        return self.state_store.load()

    def installation_present(self) -> bool:
        """Return true only for a complete or intentionally retained install.

        Merely finding runtime.env is not enough: a failed first-time setup may
        have written some deployment files before Docker/health checks failed.
        Conversely, a normal uninstall intentionally retains a complete local
        runtime and should be recoverable without asking for new DB credentials.
        """

        try:
            if not self.runtime.is_installed() or not self.deployment.config_exists():
                return False
            state = self.state_store.load()
            return state.installation_status in {
                "installed",
                "retained",
                "recovery_required",
            }
        except Exception:
            return False

    def prepare_infrastructure(self, progress: Callable[[InstallationProgress], None] | None = None) -> InstallationResult:
        installer = InstallerService(prerequisites=self.prerequisites, runtime=self.runtime, docker=self.docker, progress_callback=progress)
        result = installer.install()
        if result.reboot_required:
            self.state_store.update(installation_status="awaiting_reboot", channel=BUILD_METADATA.channel, manager_version=__version__)
            self.startup.register_resume_after_reboot()
        else:
            self.startup.clear_resume_after_reboot()
        return result

    def install_application(self, *, database_name: str, database_user: str, database_password: str) -> HealthSnapshot:
        self.state_store.update(
            installation_status="configuring",
            channel=BUILD_METADATA.channel,
            manager_version=__version__,
            last_error=None,
        )
        try:
            runtime_config = self.config.create_runtime_config(
                InstallationConfigInput(
                    database_name=database_name,
                    database_user=database_user,
                    database_password=database_password,
                )
            )
            self.deployment.prepare_assets(
                runtime_env=render_runtime_env(runtime_config),
                compose_yaml=self.deployment.read_asset(compose_asset_path()),
                nginx_config=self.deployment.read_asset(nginx_asset_path()),
            )
            self.deployment.deploy()
            snapshot = self.health.wait_until_healthy(timeout_seconds=180)
            if not snapshot.healthy:
                raise RuntimeError(f"WEAVE CBT did not become healthy: {snapshot.detail}")
        except Exception as exc:
            self.state_store.update(
                installation_status="setup_failed",
                channel=BUILD_METADATA.channel,
                manager_version=__version__,
                last_error=str(exc),
            )
            raise

        state = self.state_store.load()
        state.mark_installed(
            channel=BUILD_METADATA.channel,
            manager_version=__version__,
            cbt_version=BUILD_METADATA.cbt_version,
            image=BUILD_METADATA.weave_image,
        )
        self.state_store.save(state)

        # The local server is already healthy at this point. Scheduled-task
        # creation is desirable for reboot persistence, but must not turn a
        # healthy installation into a false setup failure. The dashboard also
        # retries task registration whenever it is opened.
        try:
            self.startup.install_tasks()
        except Exception:
            logger.exception("WEAVE CBT installed, but startup tasks could not be registered yet.")
        return snapshot

    def status(self) -> HealthSnapshot:
        if not self.installation_present():
            return HealthSnapshot(False, False, False, "WEAVE CBT has not been configured on this computer.")
        return self.health.snapshot()

    def repair(self) -> HealthSnapshot:
        if not self.runtime.is_installed():
            raise RuntimeError("The WEAVE CBT runtime is missing. Run setup again.")
        self.docker.ensure_ready()
        if not self.deployment.config_exists():
            raise RuntimeError("Runtime configuration is missing. Re-run setup to restore it.")
        self.deployment.ensure_running()
        snapshot = self.health.wait_until_healthy(timeout_seconds=120)
        if not snapshot.healthy:
            raise RuntimeError(f"Repair could not restore a healthy server: {snapshot.detail}")
        return snapshot

    def background_start(self) -> None:
        if not self.installation_present():
            return
        self.docker.ensure_ready()
        self.deployment.ensure_running()
        snapshot = self.health.wait_until_healthy(timeout_seconds=90)
        if not snapshot.healthy:
            raise RuntimeError(snapshot.detail)

    def check_updates(self) -> ReleaseInfo:
        return self.updates.check_for_updates()

    def install_available_update(self, release: ReleaseInfo) -> str:
        messages: list[str] = []
        state = self.state_store.load()
        if state.current_cbt_version and is_newer(release.cbt_version, state.current_cbt_version):
            self.updates.update_cbt(release)
            messages.append(f"CBT updated to {release.cbt_version}.")
        if is_newer(release.manager_version, __version__):
            installer = self.updates.download_manager_installer(release)
            self.updates.launch_manager_installer(installer)
            messages.append("Manager installer started.")
        return " ".join(messages) or "WEAVE CBT is already up to date."

    def uninstall_keep_data(self) -> None:
        self.startup.remove_tasks()
        self.startup.clear_resume_after_reboot()
        if self.runtime.is_installed() and self.deployment.config_exists():
            try:
                self.deployment.stop()
            except Exception:
                logger.exception("Could not stop deployment during uninstall; data remains preserved.")
        self.state_store.update(installation_status="retained")

    def purge_all_data(self) -> None:
        self.startup.remove_tasks()
        self.startup.clear_resume_after_reboot()
        if self.runtime.is_installed():
            try:
                if self.deployment.config_exists():
                    self.deployment.purge_volumes()
            finally:
                self.runtime.stop()
                wsl = shutil.which("wsl.exe") or shutil.which("wsl")
                if not wsl:
                    raise RuntimeError("WSL is unavailable; the dedicated WEAVE CBT runtime could not be removed.")
                result = subprocess.run([wsl, "--unregister", "WeaveCBT"], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode != 0:
                    raise RuntimeError(result.stderr.strip() or "Unable to remove the WEAVE CBT runtime.")
        root = state_file().parent
        if root.exists():
            shutil.rmtree(root, ignore_errors=False)


def run_gui(*, first_run: bool = False) -> int:
    configure_logging()
    from PySide6.QtWidgets import QApplication
    from .ui.main_window import MainWindow
    application = QApplication.instance() or QApplication([])
    application.setApplicationName("WEAVE CBT Manager")
    window = MainWindow(ManagerController(), force_setup=first_run)
    window.show()
    return application.exec()
