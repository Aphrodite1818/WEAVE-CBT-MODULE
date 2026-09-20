"""Database backup and restore workflows used to protect updates."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
import shlex

from ..constants import COMPOSE_PROJECT_NAME, RUNTIME_BACKUP_ROOT
from ..runtime.base import RuntimeProvider
from .deployment import DeploymentService


class BackupService:
    def __init__(self, runtime: RuntimeProvider, deployment: DeploymentService) -> None:
        self.runtime = runtime
        self.deployment = deployment

    def _compose_prefix(self) -> str:
        paths = self.deployment.paths
        return shlex.join(["docker", "compose", "--project-name", COMPOSE_PROJECT_NAME, "--file", str(paths.compose_file), "--project-directory", str(paths.root), "--env-file", str(paths.env_file)])

    def create_database_backup(self) -> PurePosixPath:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = PurePosixPath(str(RUNTIME_BACKUP_ROOT)) / f"postgres-{stamp}.sql.gz"
        prefix = self._compose_prefix()
        inner = 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"'
        command = f"install -d -m 0700 {shlex.quote(str(RUNTIME_BACKUP_ROOT))} && {prefix} exec -T postgres sh -lc {shlex.quote(inner)} | gzip -c > {shlex.quote(str(backup))} && test -s {shlex.quote(str(backup))} && chmod 0600 {shlex.quote(str(backup))}"
        result = self.runtime.execute(["sh", "-lc", command], timeout=1800)
        if not result.succeeded:
            raise RuntimeError(f"Unable to back up the WEAVE CBT database: {result.stderr or result.stdout}")
        return backup

    def restore_database_backup(self, backup: PurePosixPath) -> None:
        prefix = self._compose_prefix()
        self.runtime.execute(["sh", "-lc", f"{prefix} stop api worker nginx migrate >/dev/null 2>&1 || true"], timeout=120)
        recreate = 'dropdb --if-exists --force -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
        restore = 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" "$POSTGRES_DB"'
        command = f"test -s {shlex.quote(str(backup))} && {prefix} exec -T postgres sh -lc {shlex.quote(recreate)} && gunzip -c {shlex.quote(str(backup))} | {prefix} exec -T postgres sh -lc {shlex.quote(restore)}"
        result = self.runtime.execute(["sh", "-lc", command], timeout=1800)
        if not result.succeeded:
            raise RuntimeError(f"Unable to restore the WEAVE CBT database backup: {result.stderr or result.stdout}")
