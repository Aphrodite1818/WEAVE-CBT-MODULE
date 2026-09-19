"""Read-only adapter for inspecting host operating-system state."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SystemMemory:
    """Physical memory information for the host machine."""

    total_bytes: int
    available_bytes: int

    @property
    def total_gb(self) -> float:
        return self.total_bytes / (1024**3)

    @property
    def available_gb(self) -> float:
        return self.available_bytes / (1024**3)


@dataclass(frozen=True, slots=True)
class DiskSpace:
    """Disk capacity information for the target installation drive."""

    total_bytes: int
    used_bytes: int
    free_bytes: int

    @property
    def total_gb(self) -> float:
        return self.total_bytes / (1024**3)

    @property
    def used_gb(self) -> float:
        return self.used_bytes / (1024**3)

    @property
    def free_gb(self) -> float:
        return self.free_bytes / (1024**3)


class PlatformAdapter(ABC):
    """
    Base interface for host operating-system inspection.

    This adapter owns only OS-level information needed by the Manager.
    Container runtime concerns belong to the runtime provider layer so the
    shared Manager core does not depend on Docker Desktop, WSL, or any other
    platform-specific container implementation.

    During prerequisite checks this interface is intentionally read-only.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the human-readable operating-system name."""

    @property
    @abstractmethod
    def architecture(self) -> str:
        """
        Return the normalized host CPU architecture.

        Expected values include x86_64 and arm64.
        """

    @property
    @abstractmethod
    def runtime_root(self) -> Path:
        """
        Return the intended host-side WEAVE CBT data directory.

        The directory does not need to exist yet.
        """

    @abstractmethod
    def is_supported(self) -> bool:
        """Return whether this operating system is supported by the Manager."""

    @abstractmethod
    def is_admin(self) -> bool:
        """
        Return whether the current process has administrative privileges.

        This method must not request elevation.
        """

    @abstractmethod
    def memory(self) -> SystemMemory:
        """Return physical memory information for the host machine."""

    @abstractmethod
    def disk_space(self) -> DiskSpace:
        """
        Return disk-space information for the drive where WEAVE CBT host data
        will be stored.
        """

    @abstractmethod
    def lan_ip(self) -> str | None:
        """
        Return the preferred host LAN IPv4 address when available.

        Return None if it cannot be determined.
        """
