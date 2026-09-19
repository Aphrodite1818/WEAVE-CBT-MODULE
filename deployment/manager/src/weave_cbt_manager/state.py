"""Persistent Manager state that is separate from CBT application data."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True)
class ManagerState:
    installed: bool = False
    installed_version: str | None = None
    installed_at: str | None = None

    def mark_installed(self, version: str) -> None:
        self.installed = True
        self.installed_version = version
        self.installed_at = datetime.now(UTC).isoformat()


class ManagerStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> ManagerState:
        if not self.path.is_file():
            return ManagerState()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return ManagerState(
            installed=bool(data.get("installed", False)),
            installed_version=data.get("installed_version"),
            installed_at=data.get("installed_at"),
        )

    def save(self, state: ManagerState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(state), indent=2) + "\n",
            encoding="utf-8",
        )
