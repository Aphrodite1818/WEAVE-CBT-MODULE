"""Shared WEAVE CBT installation workflow used by GUI and CLI frontends."""

from __future__ import annotations

import os
import shutil
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from weave_cbt_manager import __version__
from weave_cbt_manager.core.config import RuntimeConfigService
from weave_cbt_manager.core.docker import DockerService
from weave_cbt_manager.core.health import HealthReport, HealthService
from weave_cbt_manager.platforms.base import PlatformAdapter
from weave_cbt_manager.state import ManagerStateStore


class InstallStage(str, Enum):
    CHECKING_SYSTEM = "checking_system"
    PREPARING_FILES = "preparing_files"
    VALIDATING_CONFIGURATION = "validating_configuration"
    PULLING_IMAGES = "pulling_images"
    STARTING_SERVICES = "starting_services"
    VERIFYING = "verifying"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class InstallEvent:
    stage: InstallStage
    message: str
    progress: int


ProgressCallback = Callable[[InstallEvent], None]


class InstallationError(RuntimeError):
    """Raised when the Manager cannot complete installation safely."""


class InstallerService:
    """Orchestrates the same deployment flow regardless of UI frontend."""

    def __init__(
        self,
        platform: PlatformAdapter,
        *,
        image: str | None = None,
        asset_root: Path | None = None,
    ) -> None:
        self.platform = platform
        self.image = image
        self.asset_root = asset_root or self._resolve_asset_root()
        self.docker = DockerService(
            compose_file=platform.paths.compose_file,
            env_file=platform.paths.env_file,
        )
        self.health = HealthService(self.docker)
        self.state_store = ManagerStateStore(platform.paths.state_file)

    @staticmethod
    def _resolve_asset_root() -> Path:
        override = os.getenv("WEAVE_MANAGER_ASSET_ROOT")
        if override:
            return Path(override).expanduser().resolve()

        # Packaged Manager builds place canonical deployment files beside the exe.
        packaged = Path(sys.executable).resolve().parent / "resources" / "deployment"
        if (packaged / "compose.yaml").is_file():
            return packaged

        # Source-tree development: core/installer.py -> deployment/.
        source = Path(__file__).resolve().parents[4]
        return source

    @staticmethod
    def _emit(
        callback: ProgressCallback | None,
        stage: InstallStage,
        message: str,
        progress: int,
    ) -> None:
        if callback:
            callback(InstallEvent(stage=stage, message=message, progress=progress))

    def _copy_runtime_assets(self) -> None:
        compose_source = self.asset_root / "compose.yaml"
        nginx_source = self.asset_root / "nginx" / "nginx.conf"

        if not compose_source.is_file() or not nginx_source.is_file():
            raise InstallationError(
                "WEAVE CBT deployment assets are missing from the Manager package."
            )

        self.platform.ensure_runtime_directories()
        shutil.copy2(compose_source, self.platform.paths.compose_file)
        shutil.copy2(
            nginx_source,
            self.platform.paths.nginx_dir / "nginx.conf",
        )

    def install(
        self,
        *,
        callback: ProgressCallback | None = None,
        timeout_seconds: int = 240,
    ) -> HealthReport:
        self._emit(callback, InstallStage.CHECKING_SYSTEM, "Checking this computer", 5)

        if not self.platform.is_supported():
            raise InstallationError("This operating system is not supported yet.")

        self._copy_runtime_assets()
        self._emit(
            callback,
            InstallStage.PREPARING_FILES,
            "Preparing WEAVE CBT runtime files",
            15,
        )

        RuntimeConfigService(self.platform.paths.env_file).ensure(image=self.image)

        if not self.docker.docker_available():
            raise InstallationError(
                "Docker is not ready. Install or start Docker Desktop, then try again."
            )
        if not self.docker.compose_available():
            raise InstallationError("Docker Compose is not available on this computer.")

        self._emit(
            callback,
            InstallStage.VALIDATING_CONFIGURATION,
            "Validating server configuration",
            25,
        )
        self.docker.validate()

        self._emit(
            callback,
            InstallStage.PULLING_IMAGES,
            "Downloading WEAVE CBT and required services",
            35,
        )
        self.docker.pull()

        self._emit(
            callback,
            InstallStage.STARTING_SERVICES,
            "Starting WEAVE CBT services",
            75,
        )
        self.docker.up()

        self._emit(
            callback,
            InstallStage.VERIFYING,
            "Verifying server health",
            85,
        )
        deadline = time.monotonic() + timeout_seconds
        report = self.health.inspect()
        while not report.healthy and time.monotonic() < deadline:
            time.sleep(2)
            report = self.health.inspect()

        if not report.healthy:
            missing = ", ".join(sorted(report.missing_services)) or "HTTP service"
            raise InstallationError(
                f"WEAVE CBT did not become healthy before timeout. Check: {missing}."
            )

        state = self.state_store.load()
        state.mark_installed(__version__)
        self.state_store.save(state)

        self._emit(
            callback,
            InstallStage.COMPLETE,
            "WEAVE CBT is ready",
            100,
        )
        return report
