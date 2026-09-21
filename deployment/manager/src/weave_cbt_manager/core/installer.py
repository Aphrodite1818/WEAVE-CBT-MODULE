"""WEAVE CBT installation orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .prerequisites import PrerequisiteReport, PrerequisiteService
from ..runtime.base import RuntimeProvider
from ..runtime.docker import DockerService


class InstallationStage(str, Enum):
    """Major stages of WEAVE CBT installation."""

    CHECKING_PREREQUISITES = "checking_prerequisites"
    PREPARING_RUNTIME = "preparing_runtime"
    REBOOT_REQUIRED = "reboot_required"
    INSTALLING_RUNTIME = "installing_runtime"
    STARTING_RUNTIME = "starting_runtime"
    CHECKING_DOCKER = "checking_docker"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class InstallationProgress:
    """Current installation progress reported to the caller."""

    stage: InstallationStage
    message: str


@dataclass(frozen=True, slots=True)
class InstallationResult:
    """Final result of an installation attempt."""

    completed: bool
    reboot_required: bool
    stage: InstallationStage
    message: str


class InstallationError(RuntimeError):
    """Raised when WEAVE CBT installation cannot continue."""


ProgressCallback = Callable[[InstallationProgress], None]


class InstallerService:
    """Coordinate WEAVE CBT infrastructure installation."""

    def __init__(
        self,
        *,
        prerequisites: PrerequisiteService,
        runtime: RuntimeProvider,
        docker: DockerService,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.prerequisites = prerequisites
        self.runtime = runtime
        self.docker = docker
        self.progress_callback = progress_callback

    def _progress(
        self,
        stage: InstallationStage,
        message: str,
    ) -> None:
        if self.progress_callback is None:
            return
        self.progress_callback(InstallationProgress(stage=stage, message=message))

    def _check_prerequisites(self) -> PrerequisiteReport:
        self._progress(
            InstallationStage.CHECKING_PREREQUISITES,
            "Checking system requirements.",
        )
        report = self.prerequisites.assess()
        if report.blocked:
            details = " ".join(
                check.message for check in report.checks if check.blocked
            )
            raise InstallationError(
                f"This machine cannot currently install WEAVE CBT. {details}"
            )
        return report

    def _prepare_runtime(self) -> bool:
        if self.runtime.is_available():
            return False

        self._progress(
            InstallationStage.PREPARING_RUNTIME,
            f"Preparing {self.runtime.name}.",
        )
        result = self.runtime.prepare()
        if result.reboot_required:
            return True
        if not self.runtime.is_available():
            raise InstallationError(
                f"{self.runtime.name} preparation completed but the runtime "
                "capability is still unavailable."
            )
        return False

    def _install_runtime(self) -> None:
        if self.runtime.is_installed():
            return

        self._progress(
            InstallationStage.INSTALLING_RUNTIME,
            "Installing the WEAVE CBT runtime.",
        )
        self.runtime.install()
        if not self.runtime.is_installed():
            raise InstallationError(
                "The WEAVE CBT runtime installation did not complete successfully."
            )

    def _start_runtime(self) -> None:
        """
        Start the runtime and wait for its own readiness contract.

        RuntimeProvider.start() is intentionally called even when the runtime
        is already reported as running. On Windows, WSL can enter the Running
        state before systemd has finished booting; the Windows provider uses
        this call to wait for system services to become usable.
        """

        self._progress(
            InstallationStage.STARTING_RUNTIME,
            "Starting the WEAVE CBT runtime.",
        )
        self.runtime.start()
        if not self.runtime.is_running():
            raise InstallationError("The WEAVE CBT runtime could not be started.")

    def _prepare_docker(self) -> None:
        self._progress(
            InstallationStage.CHECKING_DOCKER,
            "Preparing the container engine. This can take up to a minute on first start.",
        )
        try:
            self.docker.ensure_ready()
        except RuntimeError as exc:
            raise InstallationError(str(exc)) from exc

    def install(self) -> InstallationResult:
        try:
            self._check_prerequisites()
            reboot_required = self._prepare_runtime()

            if reboot_required:
                self._progress(
                    InstallationStage.REBOOT_REQUIRED,
                    "Windows must restart before WEAVE CBT installation can continue.",
                )
                return InstallationResult(
                    completed=False,
                    reboot_required=True,
                    stage=InstallationStage.REBOOT_REQUIRED,
                    message=(
                        "A system restart is required before installation can continue."
                    ),
                )

            self._install_runtime()
            self._start_runtime()
            self._prepare_docker()

            self._progress(
                InstallationStage.COMPLETE,
                "WEAVE CBT runtime installation is complete.",
            )
            return InstallationResult(
                completed=True,
                reboot_required=False,
                stage=InstallationStage.COMPLETE,
                message="WEAVE CBT runtime infrastructure is ready.",
            )
        except Exception as exc:
            self._progress(InstallationStage.FAILED, str(exc))
            if isinstance(exc, InstallationError):
                raise
            raise InstallationError(
                f"WEAVE CBT installation failed: {exc}"
            ) from exc
