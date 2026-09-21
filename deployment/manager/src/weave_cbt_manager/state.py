"""Durable local state for the WEAVE CBT Manager."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ManagerState:
    schema_version: int = 1
    installation_status: str = "new"
    channel: str = "unknown"
    manager_version: str = "0.0.0"
    current_cbt_version: str | None = None
    current_image: str | None = None
    previous_cbt_version: str | None = None
    previous_image: str | None = None
    installed_at: str | None = None
    updated_at: str | None = None
    last_error: str | None = None
    owner_sid: str | None = None
    startup_warning: str | None = None
    last_update_check_at: str | None = None
    available_manager_version: str | None = None
    available_cbt_version: str | None = None

    def mark_installed(self, *, channel: str, manager_version: str, cbt_version: str, image: str) -> None:
        now = _utc_now()
        self.installation_status = "installed"
        self.channel = channel
        self.manager_version = manager_version
        self.current_cbt_version = cbt_version
        self.current_image = image
        self.installed_at = self.installed_at or now
        self.updated_at = now
        self.last_error = None


class StateStore:
    """Atomic JSON persistence that intentionally excludes database credentials."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> ManagerState:
        if not self.path.exists():
            return ManagerState()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return ManagerState(installation_status="recovery_required")
        if not isinstance(payload, dict):
            return ManagerState(installation_status="recovery_required")
        allowed = ManagerState.__dataclass_fields__.keys()
        filtered: dict[str, Any] = {key: payload[key] for key in allowed if key in payload}
        try:
            return ManagerState(**filtered)
        except TypeError:
            return ManagerState(installation_status="recovery_required")

    def save(self, state: ManagerState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(state), indent=2, sort_keys=True) + "\n"
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        temp_path.replace(self.path)

    def update(self, **changes: Any) -> ManagerState:
        state = self.load()
        for key, value in changes.items():
            if key not in ManagerState.__dataclass_fields__:
                raise KeyError(f"Unknown ManagerState field: {key}")
            setattr(state, key, value)
        state.updated_at = _utc_now()
        self.save(state)
        return state
