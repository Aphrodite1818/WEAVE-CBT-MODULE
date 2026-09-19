"""Platform abstraction for host-specific WEAVE CBT operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    """Host filesystem locations owned by the Manager."""

    root: Path
    deployment: Path
    logs: Path
    backups: Path
    state_file: Path
    env_file: Path
    compose_file: Path
    nginx_dir: Path


class PlatformAdapter(ABC):
    """Contract implemented by each supported host operating system."""

    @property
    @abstractmethod
    def paths(self) -> RuntimePaths:
        raise NotImplementedError

    @abstractmethod
    def is_supported(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def is_admin(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def ensure_runtime_directories(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def open_url(self, url: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def lan_address(self) -> str | None:
        raise NotImplementedError
