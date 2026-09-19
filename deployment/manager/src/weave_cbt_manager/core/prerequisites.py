"""Prerequisite assessment for WEAVE CBT installation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..platforms.base import PlatformAdapter
from ..runtime.base import RuntimeProvider
from ..runtime.docker import DockerService


class PrerequisiteState(str, Enum):
    """Possible outcomes for a prerequisite check."""

    PASS = "pass"
    ACTION_REQUIRED = "action_required"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class PrerequisiteCheck:
    """Result of one prerequisite assessment."""

    key: str
    label: str
    state: PrerequisiteState
    message: str

    @property
    def passed(self) -> bool:
        return self.state is PrerequisiteState.PASS

    @property
    def blocked(self) -> bool:
        return self.state is PrerequisiteState.BLOCKED

    @property
    def action_required(self) -> bool:
        return self.state is PrerequisiteState.ACTION_REQUIRED


@dataclass(frozen=True, slots=True)
class PrerequisitePolicy:
    """
    Hardware and architecture requirements for WEAVE CBT.

    Values are provided by the application rather than being scattered
    throughout prerequisite-checking logic.
    """

    minimum_memory_gb: float
    minimum_free_disk_gb: float
    supported_architectures: frozenset[str]


@dataclass(frozen=True, slots=True)
class PrerequisiteReport:
    """Complete prerequisite assessment for the current machine."""

    checks: tuple[PrerequisiteCheck, ...]

    @property
    def blocked(self) -> bool:
        return any(check.blocked for check in self.checks)

    @property
    def action_required(self) -> bool:
        return any(check.action_required for check in self.checks)

    @property
    def ready(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def can_continue_installation(self) -> bool:
        """
        Return whether installation may continue.

        ACTION_REQUIRED items can be resolved during installation. BLOCKED
        items prevent installation entirely.
        """

        return not self.blocked


class PrerequisiteService:
    """
    Inspect whether the host can run WEAVE CBT.

    This service is read-only. It does not enable WSL, install or start the
    runtime, start Docker, modify Windows features, or deploy WEAVE CBT.
    """

    def __init__(
        self,
        *,
        platform: PlatformAdapter,
        runtime: RuntimeProvider,
        docker: DockerService,
        policy: PrerequisitePolicy,
    ) -> None:
        self.platform = platform
        self.runtime = runtime
        self.docker = docker
        self.policy = policy

    def check_platform(self) -> PrerequisiteCheck:
        """Check whether the host operating system is supported."""

        if self.platform.is_supported():
            return PrerequisiteCheck(
                key="platform",
                label="Operating system",
                state=PrerequisiteState.PASS,
                message=f"{self.platform.name} is supported.",
            )

        return PrerequisiteCheck(
            key="platform",
            label="Operating system",
            state=PrerequisiteState.BLOCKED,
            message=(
                f"{self.platform.name} is not supported by this "
                "WEAVE CBT Manager build."
            ),
        )

    def check_architecture(self) -> PrerequisiteCheck:
        """Check whether the host CPU architecture is supported."""

        architecture = self.platform.architecture

        if architecture in self.policy.supported_architectures:
            return PrerequisiteCheck(
                key="architecture",
                label="CPU architecture",
                state=PrerequisiteState.PASS,
                message=f"{architecture} is supported.",
            )

        return PrerequisiteCheck(
            key="architecture",
            label="CPU architecture",
            state=PrerequisiteState.BLOCKED,
            message=(
                f"{architecture} is not supported. "
                "Supported architectures: "
                f"{', '.join(sorted(self.policy.supported_architectures))}."
            ),
        )

    def check_admin(self) -> PrerequisiteCheck:
        """Check whether the Manager currently has administrator privileges."""

        if self.platform.is_admin():
            return PrerequisiteCheck(
                key="admin",
                label="Administrator privileges",
                state=PrerequisiteState.PASS,
                message="Manager is running with administrator privileges.",
            )

        return PrerequisiteCheck(
            key="admin",
            label="Administrator privileges",
            state=PrerequisiteState.ACTION_REQUIRED,
            message=(
                "Administrator privileges are required to install "
                "WEAVE CBT."
            ),
        )

    def check_memory(self) -> PrerequisiteCheck:
        """Check whether the host has enough physical memory."""

        memory = self.platform.memory()

        if memory.total_gb >= self.policy.minimum_memory_gb:
            return PrerequisiteCheck(
                key="memory",
                label="System memory",
                state=PrerequisiteState.PASS,
                message=f"{memory.total_gb:.1f} GB RAM installed on the host.",
            )

        return PrerequisiteCheck(
            key="memory",
            label="System memory",
            state=PrerequisiteState.BLOCKED,
            message=(
                f"{memory.total_gb:.1f} GB RAM detected. "
                f"WEAVE CBT requires at least "
                f"{self.policy.minimum_memory_gb:.1f} GB."
            ),
        )

    def check_disk_space(self) -> PrerequisiteCheck:
        """Check whether sufficient free disk space is available."""

        disk = self.platform.disk_space()

        if disk.free_gb >= self.policy.minimum_free_disk_gb:
            return PrerequisiteCheck(
                key="disk",
                label="Disk space",
                state=PrerequisiteState.PASS,
                message=f"{disk.free_gb:.1f} GB free disk space available.",
            )

        return PrerequisiteCheck(
            key="disk",
            label="Disk space",
            state=PrerequisiteState.BLOCKED,
            message=(
                f"{disk.free_gb:.1f} GB free disk space detected. "
                f"WEAVE CBT requires at least "
                f"{self.policy.minimum_free_disk_gb:.1f} GB free."
            ),
        )

    def check_runtime_available(self) -> PrerequisiteCheck:
        """Check whether the underlying runtime capability is available."""

        if self.runtime.is_available():
            return PrerequisiteCheck(
                key="runtime_available",
                label="Runtime capability",
                state=PrerequisiteState.PASS,
                message=f"{self.runtime.name} is available.",
            )

        return PrerequisiteCheck(
            key="runtime_available",
            label="Runtime capability",
            state=PrerequisiteState.ACTION_REQUIRED,
            message=(
                f"{self.runtime.name} is not currently available "
                "and must be prepared by the installer."
            ),
        )

    def check_runtime_installed(self) -> PrerequisiteCheck:
        """Check whether the WEAVE-managed runtime already exists."""

        if not self.runtime.is_available():
            return PrerequisiteCheck(
                key="runtime_installed",
                label="WEAVE runtime",
                state=PrerequisiteState.ACTION_REQUIRED,
                message=(
                    "Runtime capability must be prepared before the "
                    "WEAVE CBT runtime can be installed."
                ),
            )

        if self.runtime.is_installed():
            return PrerequisiteCheck(
                key="runtime_installed",
                label="WEAVE runtime",
                state=PrerequisiteState.PASS,
                message="WEAVE CBT runtime is installed.",
            )

        return PrerequisiteCheck(
            key="runtime_installed",
            label="WEAVE runtime",
            state=PrerequisiteState.ACTION_REQUIRED,
            message="WEAVE CBT runtime has not been provisioned yet.",
        )

    def check_runtime_running(self) -> PrerequisiteCheck:
        """
        Check whether the WEAVE runtime is currently running.

        The prerequisite service deliberately does not start it.
        """

        if not self.runtime.is_available():
            return PrerequisiteCheck(
                key="runtime_running",
                label="Runtime state",
                state=PrerequisiteState.ACTION_REQUIRED,
                message="Runtime capability is not available yet.",
            )

        if not self.runtime.is_installed():
            return PrerequisiteCheck(
                key="runtime_running",
                label="Runtime state",
                state=PrerequisiteState.ACTION_REQUIRED,
                message="WEAVE CBT runtime has not been installed yet.",
            )

        if self.runtime.is_running():
            return PrerequisiteCheck(
                key="runtime_running",
                label="Runtime state",
                state=PrerequisiteState.PASS,
                message="WEAVE CBT runtime is running.",
            )

        return PrerequisiteCheck(
            key="runtime_running",
            label="Runtime state",
            state=PrerequisiteState.ACTION_REQUIRED,
            message="WEAVE CBT runtime is installed but not currently running.",
        )

    def check_docker(self) -> PrerequisiteCheck:
        """
        Check Docker readiness inside the runtime.

        Docker is only inspected when the runtime is already running. This
        avoids starting WSL or another runtime merely to perform a prerequisite
        check.
        """

        if not self.runtime.is_available():
            return PrerequisiteCheck(
                key="docker",
                label="Docker Engine",
                state=PrerequisiteState.ACTION_REQUIRED,
                message=(
                    "Docker cannot be checked until the runtime capability "
                    "is available."
                ),
            )

        if not self.runtime.is_installed():
            return PrerequisiteCheck(
                key="docker",
                label="Docker Engine",
                state=PrerequisiteState.ACTION_REQUIRED,
                message=(
                    "Docker will be available after the WEAVE CBT runtime "
                    "is provisioned."
                ),
            )

        if not self.runtime.is_running():
            return PrerequisiteCheck(
                key="docker",
                label="Docker Engine",
                state=PrerequisiteState.ACTION_REQUIRED,
                message="Runtime must be started before Docker can be checked.",
            )

        status = self.docker.status()

        if not status.installed:
            return PrerequisiteCheck(
                key="docker",
                label="Docker Engine",
                state=PrerequisiteState.ACTION_REQUIRED,
                message=(
                    "Docker Engine is not installed inside the "
                    "WEAVE CBT runtime."
                ),
            )

        if not status.compose_available:
            return PrerequisiteCheck(
                key="docker",
                label="Docker Engine",
                state=PrerequisiteState.ACTION_REQUIRED,
                message=(
                    "Docker Compose v2 is not available inside the "
                    "WEAVE CBT runtime."
                ),
            )

        if not status.running:
            return PrerequisiteCheck(
                key="docker",
                label="Docker Engine",
                state=PrerequisiteState.ACTION_REQUIRED,
                message="Docker Engine is installed but not currently running.",
            )

        return PrerequisiteCheck(
            key="docker",
            label="Docker Engine",
            state=PrerequisiteState.PASS,
            message="Docker Engine and Docker Compose are ready.",
        )

    def assess(self) -> PrerequisiteReport:
        """Run the complete prerequisite assessment."""

        checks = (
            self.check_platform(),
            self.check_architecture(),
            self.check_admin(),
            self.check_memory(),
            self.check_disk_space(),
            self.check_runtime_available(),
            self.check_runtime_installed(),
            self.check_runtime_running(),
            self.check_docker(),
        )

        return PrerequisiteReport(checks=checks)
