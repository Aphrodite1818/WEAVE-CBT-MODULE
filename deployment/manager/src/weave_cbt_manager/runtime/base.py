"""Base contract for WEAVE CBT runtime providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class RuntimeCommandResult:
    """Result returned after executing a command inside a runtime."""

    return_code: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0


@dataclass(frozen=True, slots=True)
class RuntimePreparationResult:
    """Result of preparing the host for a runtime provider."""

    reboot_required: bool = False


class RuntimeProvider(ABC):
    """
    Base interface for the environment in which WEAVE CBT runs.

    The Manager core should depend on this interface rather than knowing
    whether the runtime is implemented using:

    - WSL2 on Windows
    - the native Linux host
    - a lightweight Linux VM on macOS

    Docker management is intentionally not part of this interface. Docker
    runs inside the runtime and is handled separately by DockerService.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return a human-readable runtime provider name."""

    @abstractmethod
    def is_available(self) -> bool:
        """
        Return whether the host currently has the capability required by this
        runtime provider.
        """

    @abstractmethod
    def is_installed(self) -> bool:
        """Return whether the WEAVE-managed runtime environment exists."""

    @abstractmethod
    def is_running(self) -> bool:
        """Return whether the runtime environment is currently running."""

    @abstractmethod
    def prepare(self) -> RuntimePreparationResult:
        """
        Prepare the host so this runtime provider can operate.

        This may modify the host. A provider may report that a reboot is
        required before installation can continue.
        """

    @abstractmethod
    def install(self) -> None:
        """
        Provision the runtime environment.

        This should prepare only the runtime itself. Docker Engine management
        and WEAVE CBT deployment belong to separate layers.
        """

    @abstractmethod
    def start(self) -> None:
        """Start the runtime environment if it is not already running."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the runtime environment if it is running."""

    @abstractmethod
    def execute(
        self,
        command: Sequence[str],
        *,
        timeout: float | None = None,
    ) -> RuntimeCommandResult:
        """
        Execute a command inside the runtime environment.

        The caller provides command arguments separately rather than passing
        a shell command string.
        """
