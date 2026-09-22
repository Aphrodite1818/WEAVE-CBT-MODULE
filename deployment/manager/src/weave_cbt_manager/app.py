"""Composition root for the Windows WEAVE CBT Manager."""

from __future__ import annotations

import logging
import secrets
from logging.handlers import RotatingFileHandler
import shutil
import subprocess
from typing import Callable

from . import __version__
from .build_metadata import BUILD_METADATA
from .constants import COMPOSE_PROJECT_NAME, WSL_DISTRO_NAME, compose_asset_path, log_directory, nginx_asset_path, rootfs_archive_path, runtime_install_directory, state_file
from .core.backup import BackupService
from .core.config import ConfigService, InstallationConfigInput, render_runtime_env
from .core.deployment import DatabaseCredentials, DeploymentService
from .core.health import HealthService, HealthSnapshot
from .core.installer import InstallationProgress, InstallationResult, InstallerService
from .core.networking import NetworkAccessStatus, WindowsNetworkingService
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
        # Production keeps a realistic capacity floor for images and school
        # data. Staging/development intentionally use the temporary 4 GB floor
        # used by acceptance testing on constrained machines.
        minimum_free_disk_gb = 20.0 if BUILD_METADATA.channel == "production" else 4.0
        self.prerequisites = PrerequisiteService(
            platform=self.platform, runtime=self.runtime, docker=self.docker,
            policy=PrerequisitePolicy(minimum_memory_gb=7.5, minimum_free_disk_gb=minimum_free_disk_gb, supported_architectures=frozenset({"x86_64"})),
        )
        self.deployment = DeploymentService(self.runtime, self.docker)
        self.health = HealthService(self.deployment)
        self.state_store = StateStore(state_file())
        self.startup = WindowsStartupService()
        self.backup = BackupService(self.runtime, self.deployment)
        self.updates = UpdateService(build_metadata=BUILD_METADATA, manager_version=__version__, deployment=self.deployment, health=self.health, backup=self.backup, state_store=self.state_store)
        self.config = ConfigService(BUILD_METADATA)
        self.networking = WindowsNetworkingService(self.runtime, state_file().parent / "network.json")

    def _check_channel(self) -> None:
        owner_sid = self.state.owner_sid
        if owner_sid and owner_sid != self.platform.account_sid():
            raise RuntimeError("This server belongs to another Windows account. Sign in with the account used to set up Weave; WSL servers are registered per user.")
        channel = self.state.channel
        if channel not in {"unknown", BUILD_METADATA.channel}:
            raise RuntimeError(
                f"This computer has a {channel} installation. Open that channel's Manager. "
                "Production and staging must use separate server computers."
            )

    def _prepare_database_admin(self) -> None:
        self._check_channel()
        if not self.platform.is_admin():
            raise RuntimeError("Administrator privileges are required to access local database administration tools.")
        if not self.runtime.is_installed():
            raise RuntimeError("The WEAVE CBT runtime is not installed on this computer.")
        self.runtime.start()
        self.runtime.keep_alive()
        if not self.deployment.environment_exists():
            raise RuntimeError("Saved database configuration is missing. Run Repair before accessing the database.")

    @property
    def state(self) -> ManagerState:
        return self.state_store.load()

    def installation_present(self) -> bool:
        """Return true for a durable complete or intentionally retained install.

        This method deliberately does not execute a command inside WSL. The UI
        calls it before the runtime has been started, and probing runtime files
        here would cold-start WSL through the captured-command path instead of
        the provider's dedicated bootstrap path. Durable Manager state is the
        installation marker; health/repair verifies runtime files after WSL is
        started safely.
        """

        try:
            state = self.state_store.load()
            if state.installation_status not in {
                "installed",
                "retained",
                "recovery_required",
            }:
                return False
            return self.runtime.is_installed()
        except Exception:
            return False

    def prepare_infrastructure(self, progress: Callable[[InstallationProgress], None] | None = None) -> InstallationResult:
        self._check_channel()
        if self.platform.is_supported() and self.platform.is_admin():
            self.state_store.update(owner_sid=self.platform.account_sid())
        installer = InstallerService(prerequisites=self.prerequisites, runtime=self.runtime, docker=self.docker, progress_callback=progress)
        result = installer.install()
        if result.reboot_required:
            self.state_store.update(installation_status="awaiting_reboot", channel=BUILD_METADATA.channel, manager_version=__version__)
            self.startup.register_resume_after_reboot()
        else:
            self.startup.clear_resume_after_reboot()
            self.runtime.keep_alive()
        return result

    def install_application(self, *, database_name: str = "weave_cbt", database_user: str = "weave", database_password: str | None = None, progress: Callable[[str], None] | None = None) -> HealthSnapshot:
        self._check_channel()
        report = progress or (lambda _message: None)
        self.state_store.update(
            installation_status="configuring",
            channel=BUILD_METADATA.channel,
            manager_version=__version__,
            last_error=None,
        )
        try:
            self.docker.ensure_ready()
            self.runtime.keep_alive()
            compose_yaml = self.deployment.read_asset(compose_asset_path())
            nginx_config = self.deployment.read_asset(nginx_asset_path())
            report("Preparing your server configuration")
            if self.deployment.environment_exists():
                # Postgres initializes a volume once. A different password on
                # retry will NOT change that database's password.
                self.deployment.refresh_assets(compose_yaml=compose_yaml, nginx_config=nginx_config)
            else:
                if self.deployment.has_persistent_data():
                    raise RuntimeError("School data already exists, but its saved configuration is missing. Restore runtime.env from backup before continuing; existing data has been preserved.")
                runtime_config = self.config.create_runtime_config(
                    InstallationConfigInput(database_name=database_name, database_user=database_user,
                                            database_password=database_password or secrets.token_urlsafe(32))
                )
                self.deployment.prepare_assets(runtime_env=render_runtime_env(runtime_config), compose_yaml=compose_yaml, nginx_config=nginx_config)
                self.state_store.update(current_image=BUILD_METADATA.weave_image, current_cbt_version=BUILD_METADATA.cbt_version)
            report("Downloading and starting Weave services. The first download may take several minutes.")
            self.deployment.deploy()
            report("Connecting the school network")
            self.networking.configure(self.platform.lan_ip())
            report("Checking the database, services and staff portal")
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
            cbt_version=state.current_cbt_version or BUILD_METADATA.cbt_version,
            image=state.current_image or BUILD_METADATA.weave_image,
        )
        self.state_store.save(state)

        # The local server is already healthy at this point. Scheduled-task
        # creation is desirable for reboot persistence, but must not turn a
        # healthy installation into a false setup failure. The dashboard also
        # retries task registration whenever it is opened.
        try:
            self.startup.install_tasks()
            self.state_store.update(startup_warning=None)
        except Exception:
            logger.exception("WEAVE CBT installed, but startup tasks could not be registered yet.")
            self.state_store.update(startup_warning="Automatic startup could not be registered. Open the Manager after signing in, or use Repair to try again.")
        return snapshot

    def database_credentials(self) -> DatabaseCredentials:
        """Return saved DB credentials only after an explicit elevated admin action."""
        self._prepare_database_admin()
        return self.deployment.database_credentials()

    def open_database_console(self) -> None:
        """Open an interactive psql session without exposing PostgreSQL to the LAN."""
        self._prepare_database_admin()
        self.docker.ensure_ready()
        self.deployment.ensure_running()

        wsl = shutil.which("wsl.exe") or shutil.which("wsl")
        if not wsl:
            raise RuntimeError("WSL is unavailable; the database console cannot be opened.")

        paths = self.deployment.paths
        command = [
            wsl,
            "--distribution", WSL_DISTRO_NAME,
            "--user", "root",
            "--",
            "docker", "compose",
            "--project-name", COMPOSE_PROJECT_NAME,
            "--file", str(paths.compose_file),
            "--project-directory", str(paths.root),
            "--env-file", str(paths.env_file),
            "exec", "postgres", "sh", "-lc",
            'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
        ]
        try:
            subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_CONSOLE)
        except OSError as exc:
            raise RuntimeError("Unable to open the local PostgreSQL console.") from exc

    def network_access(self) -> NetworkAccessStatus:
        return self.networking.inspect_access(self.platform.lan_ip())

    def reconcile_network(self) -> NetworkAccessStatus:
        """Rebuild WEAVE-owned LAN forwarding for the host's current network."""

        self._check_channel()
        lan_ip = self.platform.lan_ip()
        if not self.installation_present():
            return self.networking.inspect_access(lan_ip)
        if not self.runtime.is_installed():
            return self.networking.inspect_access(lan_ip)

        self.runtime.start()
        self.runtime.keep_alive()
        if not self.deployment.config_exists():
            return self.networking.inspect_access(lan_ip)
        self.networking.configure(lan_ip)
        return self.networking.inspect_access(lan_ip)

    def enable_school_network(self) -> NetworkAccessStatus:
        """Trust the current Public Windows network after explicit admin approval."""

        self._check_channel()
        if not self.platform.is_admin():
            raise RuntimeError(
                "Administrator privileges are required to enable school network access."
            )
        lan_ip = self.platform.lan_ip()
        status = self.networking.inspect_access(lan_ip)
        if not status.connected:
            raise RuntimeError(
                "Connect this computer to the trusted school Wi-Fi or Ethernet network first."
            )
        status = self.networking.approve_current_network(status)
        self.networking.configure(status.lan_ip)
        return self.networking.inspect_access(status.lan_ip)

    def status(self) -> HealthSnapshot:
        self._check_channel()
        if not self.installation_present():
            return HealthSnapshot(False, False, False, "WEAVE CBT has not been configured on this computer.")
        snapshot = self.health.snapshot()
        if snapshot.healthy:
            self.networking.configure(self.platform.lan_ip())
        return snapshot

    def repair(self) -> HealthSnapshot:
        self._check_channel()
        if not self.runtime.is_installed():
            raise RuntimeError("The WEAVE CBT runtime is missing. Run setup again.")
        self.docker.ensure_ready()
        self.runtime.keep_alive()
        if not self.deployment.environment_exists():
            raise RuntimeError("Saved server configuration is missing. Restore runtime.env from backup before repairing this installation.")
        self.deployment.refresh_assets(compose_yaml=self.deployment.read_asset(compose_asset_path()),
                                       nginx_config=self.deployment.read_asset(nginx_asset_path()))
        self.deployment.ensure_running()
        self.networking.configure(self.platform.lan_ip())
        snapshot = self.health.wait_until_healthy(timeout_seconds=120)
        if not snapshot.healthy:
            raise RuntimeError(f"Repair could not restore a healthy server: {snapshot.detail}")
        self.startup.install_tasks()
        self.state_store.update(startup_warning=None)
        return snapshot

    def background_start(self) -> None:
        self._check_channel()
        if not self.installation_present():
            return
        self.docker.ensure_ready()
        self.runtime.keep_alive()
        if not self.deployment.config_exists():
            raise RuntimeError("Runtime configuration is missing. Open WEAVE CBT Manager and run repair.")
        self.deployment.ensure_running()
        self.networking.configure(self.platform.lan_ip())
        snapshot = self.health.wait_until_healthy(timeout_seconds=90)
        if not snapshot.healthy:
            raise RuntimeError(snapshot.detail)

    def check_updates(self) -> ReleaseInfo:
        return self.updates.check_for_updates()

    def install_available_update(self, release: ReleaseInfo) -> str:
        self._check_channel()
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
        self._check_channel()
        self.startup.remove_tasks()
        self.startup.clear_resume_after_reboot()
        if self.runtime.is_installed() and self.deployment.config_exists():
            try:
                self.deployment.stop()
            except Exception:
                logger.exception("Could not stop deployment during uninstall; data remains preserved.")
        self.state_store.update(installation_status="retained")
        self.runtime.stop()
        self.networking.remove()

    def purge_all_data(self) -> None:
        self._check_channel()
        self.startup.remove_tasks()
        self.startup.clear_resume_after_reboot()
        self.networking.remove()
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
        # Keep diagnostic logs and the active Manager lock. Deleting this
        # directory while its log file is open fails on Windows.
        self.state_store.save(ManagerState())


def run_gui(*, first_run: bool = False) -> int:
    configure_logging()
    from PySide6.QtWidgets import QApplication
    from .ui.main_window import MainWindow
    application = QApplication.instance() or QApplication([])
    application.setApplicationName("WEAVE CBT Manager")
    window = MainWindow(ManagerController(), force_setup=first_run)
    window.show()
    return application.exec()
