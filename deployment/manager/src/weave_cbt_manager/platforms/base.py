"""Read only adapter for inspecting the machine state before handling installation"""


from __future__ import annotations

from abc import ABC , abstractmethod
from dataclasses import dataclass
from pathlib import Path



@dataclass(frozen = True , slots = True)
class SystemMemory:
    """Physical memory information for the host machine"""


    total_bytes : int
    available_bytes : int 

    @property
    def total_gb(self) -> float:
        return self.total_bytes / (1024**3)

    @property
    def availavle_gb(self) -> float:
        return self.available_bytes / (1024**3)



@dataclass(frozen=True , slots = True)
class DiskSpace:
    """Disk capacity information for the target installation drive"""

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
    Base interface for operating-system-specific functionality.

    The shared WEAVE CBT Manager core should depend on this interface instead 
    of directly calling Windows , Linux or macOS APIs

    During the prerequisite-checking phase this adapter is intentionally
    read-only. Methods that modify the machine will be added when installation
    orchestration is implemented
    """


    @property
    @abstractmethod
    def name(self)->str:
        """Human-readable operating system name."""

    @property
    @abstractmethod
    def architecture(self)->str:
        """
        Return the host CPU architecture
        Expected normalized values will eventually include values such as:
        - x86_64
        -arm64
        """


    @property
    @abstractmethod
    def runtime_root(self)->str:
        """
        Return the intended WEAVE CBT runtime data directory.

        The directory does not need to exist yet
        """


    @abstractmethod
    def is_supported(self)->bool:
        """Return whether this operating system is supported by the Manager"""


    @abstractmethod
    def is_admin(self)->bool:
        """
        Return whether the current process has administrative privileges.

        This method must not request elevation
        """


    @abstractmethod
    def memory(self)->SystemMemory:
        """Return physical memory information for the host machine"""


    @abstractmethod
    def disk_space(self)->DiskSpace:
        """
        Return disk-space information for the drve where WEAVE CBT runtime
        data will be stored
        """


    @abstractmethod
    def docker_executable(self)-> Path | None:
        """
        Return the DOCKER CLI executable path if available

        Return None when Docker cannot be located
        """


    @abstractmethod
    def docker_desktop_installed(self)->bool:
        """
        Return whether Docker Desktop is installed

        This is primarily relevant to the current Windows implementation
        """


    @abstractmethod
    def docker_engine_running(self)->bool:
        """
        Return whether the Docker engine can currently accept commands

        This should only inspect state and must not attempt to start Docker 
        """

    @abstractmethod
    def docker_compose_available(self)->bool:
        """
        Return whether the Docker Compose v2 command is available.

        Equivalent capability:
            docker compose version
        """


    @abstractmethod
    def lan_ip(self)->str | None:
        """
        Return the machine's preferred LAN IPv4 address when available

        Return None if it cannot be determined
        """


    