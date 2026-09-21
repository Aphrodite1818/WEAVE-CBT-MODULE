"""Release discovery and safe CBT/Manager update orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import ctypes
from pathlib import Path
import re
import tempfile

import httpx

from ..build_metadata import BuildMetadata
from ..state import StateStore
from .backup import BackupService
from .deployment import DeploymentService
from .health import HealthService

_VERSION_PATTERN = re.compile(r"^(?:v)?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


@dataclass(frozen=True, slots=True)
class ReleaseInfo:
    channel: str
    manager_version: str
    cbt_version: str
    minimum_supported_version: str
    image: str
    installer_url: str
    installer_sha256: str
    release_notes: str = ""


def version_tuple(value: str) -> tuple[int, int, int]:
    match = _VERSION_PATTERN.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"Unsupported version value: {value!r}")
    return tuple(int(part) for part in match.groups())


def is_newer(candidate: str, installed: str) -> bool:
    return version_tuple(candidate) > version_tuple(installed)


class UpdateService:
    def __init__(self, *, build_metadata: BuildMetadata, manager_version: str, deployment: DeploymentService, health: HealthService, backup: BackupService, state_store: StateStore) -> None:
        self.build_metadata = build_metadata
        self.manager_version = manager_version
        self.deployment = deployment
        self.health = health
        self.backup = backup
        self.state_store = state_store

    def check_for_updates(self) -> ReleaseInfo:
        url = f"{self.build_metadata.weave_api_base_url}/api/v1/cbt/releases/latest"
        try:
            response = httpx.get(url, timeout=10.0, headers={"Accept": "application/json", "User-Agent": "WEAVE-CBT-Manager"})
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError("Unable to check for WEAVE CBT updates. The local CBT server can continue operating normally.") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("WEAVE Cloud returned invalid release metadata.")
        try:
            release = ReleaseInfo(
                channel=str(payload["channel"]), manager_version=str(payload["manager_version"]),
                cbt_version=str(payload["cbt_version"]), minimum_supported_version=str(payload["minimum_supported_version"]),
                image=str(payload["image"]), installer_url=str(payload["installer_url"]),
                installer_sha256=str(payload["installer_sha256"]).lower(), release_notes=str(payload.get("release_notes") or ""),
            )
        except KeyError as exc:
            raise RuntimeError(f"WEAVE Cloud release metadata is missing {exc.args[0]!r}.") from exc
        if release.channel != self.build_metadata.channel:
            raise RuntimeError("WEAVE Cloud returned a release for the wrong update channel.")
        version_tuple(release.manager_version)
        version_tuple(release.cbt_version)
        version_tuple(release.minimum_supported_version)
        if not re.fullmatch(r"[0-9a-f]{64}", release.installer_sha256):
            raise RuntimeError("WEAVE Cloud returned an invalid installer checksum.")
        state = self.state_store.load()
        state.last_update_check_at = datetime.now(timezone.utc).isoformat()
        state.available_manager_version = release.manager_version
        state.available_cbt_version = release.cbt_version
        self.state_store.save(state)
        return release

    def update_cbt(self, release: ReleaseInfo) -> None:
        state = self.state_store.load()
        if not state.current_image or not state.current_cbt_version:
            raise RuntimeError("WEAVE CBT installation state is incomplete; run Repair before updating.")
        if not is_newer(release.cbt_version, state.current_cbt_version):
            return
        if self.deployment.has_exam_in_progress():
            raise RuntimeError("An examination is active or suspended. Finish or safely close it before updating WEAVE CBT.")
        previous_image = state.current_image
        previous_version = state.current_cbt_version
        backup_path = self.backup.create_database_backup()
        state.previous_image = previous_image
        state.previous_cbt_version = previous_version
        self.state_store.save(state)
        try:
            self.deployment.set_image(release.image)
            self.deployment.deploy()
            snapshot = self.health.wait_until_healthy(timeout_seconds=180)
            if not snapshot.healthy:
                raise RuntimeError(f"Updated services did not become healthy: {snapshot.detail}")
        except Exception as update_error:
            rollback_error: Exception | None = None
            try:
                self.deployment.set_image(previous_image)
                self.backup.restore_database_backup(backup_path)
                self.deployment.deploy()
                restored = self.health.wait_until_healthy(timeout_seconds=180)
                if not restored.healthy:
                    raise RuntimeError(restored.detail)
            except Exception as exc:
                rollback_error = exc
            if rollback_error is not None:
                raise RuntimeError(f"The update failed and automatic rollback also failed. Database backup is preserved at {backup_path}. Rollback error: {rollback_error}") from update_error
            raise RuntimeError("The update failed. The previous WEAVE CBT version and database were restored.") from update_error
        state.current_image = release.image
        state.current_cbt_version = release.cbt_version
        state.updated_at = datetime.now(timezone.utc).isoformat()
        state.last_error = None
        self.state_store.save(state)

    def download_manager_installer(self, release: ReleaseInfo) -> Path:
        if not is_newer(release.manager_version, self.manager_version):
            raise RuntimeError("The WEAVE CBT Manager is already current.")
        target = Path(tempfile.gettempdir()) / f"WeaveCBT-Setup-{release.manager_version}.exe"
        digest = hashlib.sha256()
        try:
            with httpx.stream("GET", release.installer_url, timeout=120.0, follow_redirects=True) as response:
                response.raise_for_status()
                with target.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        handle.write(chunk)
                        digest.update(chunk)
        except (httpx.HTTPError, OSError) as exc:
            target.unlink(missing_ok=True)
            raise RuntimeError("Unable to download the WEAVE CBT Manager update.") from exc
        if digest.hexdigest().lower() != release.installer_sha256:
            target.unlink(missing_ok=True)
            raise RuntimeError("The downloaded installer failed its SHA-256 integrity check and was rejected.")
        return target

    @staticmethod
    def launch_manager_installer(installer: Path) -> None:
        # ShellExecute handles Windows paths with spaces without a shell parser.
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", str(installer), None, str(installer.parent), 1)
        if result <= 32:
            raise RuntimeError("The installer could not start or its administrator prompt was cancelled.")
