"""Deployment asset preparation and Compose orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import shlex

from ..constants import COMPOSE_PROJECT_NAME, RUNTIME_COMPOSE_FILE, RUNTIME_DEPLOYMENT_ROOT, RUNTIME_ENV_FILE, RUNTIME_NGINX_FILE
from ..runtime.base import RuntimeProvider
from ..runtime.docker import DockerService


@dataclass(frozen=True, slots=True)
class DeploymentPaths:
    root: PurePosixPath = PurePosixPath(str(RUNTIME_DEPLOYMENT_ROOT))
    compose_file: PurePosixPath = PurePosixPath(str(RUNTIME_COMPOSE_FILE))
    env_file: PurePosixPath = PurePosixPath(str(RUNTIME_ENV_FILE))
    nginx_file: PurePosixPath = PurePosixPath(str(RUNTIME_NGINX_FILE))


@dataclass(frozen=True, slots=True)
class DatabaseCredentials:
    database_name: str
    database_user: str
    database_password: str


def _decode_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("\\'", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


class DeploymentService:
    """Own the local WEAVE Compose project without touching persistent volumes."""

    def __init__(self, runtime: RuntimeProvider, docker: DockerService, paths: DeploymentPaths | None = None) -> None:
        self.runtime = runtime
        self.docker = docker
        self.paths = paths or DeploymentPaths()

    @staticmethod
    def read_asset(path: Path) -> str:
        if not path.is_file():
            raise FileNotFoundError(f"Deployment asset not found: {path}")
        return path.read_text(encoding="utf-8")

    def _write_runtime_file(self, path: PurePosixPath, content: str, *, mode: str) -> None:
        # RuntimeProvider owns the host-to-runtime transfer mechanism. The
        # Windows provider stages a short-lived host file and copies it into
        # WSL atomically without placing file contents in argv or stdin pipes.
        result = self.runtime.write_text_file(
            str(path),
            content,
            mode=mode,
            timeout=30,
        )
        if not result.succeeded:
            raise RuntimeError(
                f"Unable to write runtime file {path}: "
                f"{result.stderr or result.stdout}"
            )

    def prepare_assets(self, *, runtime_env: str, compose_yaml: str, nginx_config: str) -> None:
        # Write non-secret assets first and runtime.env last. A partially failed
        # preparation therefore cannot leave the configuration marker in place
        # before the rest of the deployment bundle exists.
        self._write_runtime_file(self.paths.compose_file, compose_yaml, mode="0644")
        self._write_runtime_file(self.paths.nginx_file, nginx_config, mode="0644")
        self._write_runtime_file(self.paths.env_file, runtime_env, mode="0600")

    def environment_exists(self) -> bool:
        result = self.runtime.execute(["test", "-s", str(self.paths.env_file)], timeout=15)
        if result.return_code not in (0, 1):
            raise RuntimeError("Unable to inspect saved server configuration: " + result.stderr)
        return result.succeeded

    def database_credentials(self) -> DatabaseCredentials:
        """Read the locally stored PostgreSQL credentials on explicit admin request.

        The secret is returned only to the Manager process. It is never copied
        into Manager state, command arguments, or logs.
        """
        result = self.runtime.execute(["cat", str(self.paths.env_file)], timeout=10)
        if not result.succeeded:
            raise RuntimeError("Unable to read the saved database credentials.")

        values: dict[str, str] = {}
        wanted = {"POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"}
        for line in result.stdout.splitlines():
            key, separator, raw_value = line.partition("=")
            if separator and key in wanted:
                values[key] = _decode_env_value(raw_value)

        missing = wanted.difference(values)
        if missing:
            raise RuntimeError("The saved database configuration is incomplete. Run Repair before accessing the database.")

        return DatabaseCredentials(
            database_name=values["POSTGRES_DB"],
            database_user=values["POSTGRES_USER"],
            database_password=values["POSTGRES_PASSWORD"],
        )

    def refresh_assets(self, *, compose_yaml: str, nginx_config: str) -> None:
        """Repair deployment files without replacing existing database secrets."""
        self._write_runtime_file(self.paths.compose_file, compose_yaml, mode="0644")
        self._write_runtime_file(self.paths.nginx_file, nginx_config, mode="0644")

    def has_persistent_data(self) -> bool:
        result = self.docker.docker(
            ["volume", "ls", "--quiet", "--filter", f"label=com.docker.compose.project={COMPOSE_PROJECT_NAME}"], timeout=15,
        )
        if not result.succeeded:
            raise RuntimeError("Unable to check for existing school data: " + result.stderr)
        return bool(result.stdout.strip())

    def config_exists(self) -> bool:
        script = (
            'test -s "$1" && test -s "$2" && test -s "$3"'
        )
        return self.runtime.execute(
            [
                "sh",
                "-c",
                script,
                "weave-config-check",
                str(self.paths.env_file),
                str(self.paths.compose_file),
                str(self.paths.nginx_file),
            ],
            timeout=10,
        ).succeeded

    def validate(self) -> None:
        result = self.docker.compose(
            ["config", "--quiet"], compose_file=self.paths.compose_file,
            project_directory=self.paths.root, env_file=self.paths.env_file,
            project_name=COMPOSE_PROJECT_NAME, timeout=30,
        )
        if not result.succeeded:
            raise RuntimeError(f"WEAVE CBT deployment configuration is invalid: {result.stderr or result.stdout}")

    def deploy(self) -> None:
        self.docker.ensure_ready()
        self.validate()
        self.docker.pull(compose_file=self.paths.compose_file, project_directory=self.paths.root, env_file=self.paths.env_file, project_name=COMPOSE_PROJECT_NAME)
        self.docker.up(compose_file=self.paths.compose_file, project_directory=self.paths.root, env_file=self.paths.env_file, project_name=COMPOSE_PROJECT_NAME)

    def ensure_running(self) -> None:
        self.docker.ensure_ready()
        self.docker.up(compose_file=self.paths.compose_file, project_directory=self.paths.root, env_file=self.paths.env_file, project_name=COMPOSE_PROJECT_NAME)

    def restart(self) -> None:
        result = self.docker.compose(["restart"], compose_file=self.paths.compose_file, project_directory=self.paths.root, env_file=self.paths.env_file, project_name=COMPOSE_PROJECT_NAME, timeout=180)
        if not result.succeeded:
            raise RuntimeError(f"Unable to restart WEAVE CBT: {result.stderr or result.stdout}")

    def stop(self) -> None:
        self.docker.down(compose_file=self.paths.compose_file, project_directory=self.paths.root, env_file=self.paths.env_file, project_name=COMPOSE_PROJECT_NAME)

    def purge_volumes(self) -> None:
        result = self.docker.compose(["down", "--volumes", "--remove-orphans"], compose_file=self.paths.compose_file, project_directory=self.paths.root, env_file=self.paths.env_file, project_name=COMPOSE_PROJECT_NAME, timeout=180)
        if not result.succeeded:
            raise RuntimeError(f"Unable to remove WEAVE CBT data volumes: {result.stderr or result.stdout}")

    def compose_ps_json(self) -> str:
        result = self.docker.compose(["ps", "--all", "--format", "json"], compose_file=self.paths.compose_file, project_directory=self.paths.root, env_file=self.paths.env_file, project_name=COMPOSE_PROJECT_NAME, timeout=30)
        if not result.succeeded:
            raise RuntimeError(f"Unable to inspect WEAVE CBT services: {result.stderr or result.stdout}")
        return result.stdout

    def set_image(self, image: str) -> None:
        if not image or any(character.isspace() for character in image) or "'" in image:
            raise ValueError("Invalid WEAVE image reference.")
        script = (
            "set -eu\n"
            "env_file=$1\n"
            "image=$2\n"
            "tmp=\"${env_file}.tmp.$$\"\n"
            "cleanup() { rm -f -- \"$tmp\"; }\n"
            "trap cleanup EXIT HUP INT TERM\n"
            "awk '!/^WEAVE_IMAGE=/' \"$env_file\" > \"$tmp\"\n"
            "printf \"WEAVE_IMAGE='%s'\\n\" \"$image\" >> \"$tmp\"\n"
            "chmod 0600 \"$tmp\"\n"
            "mv -f -- \"$tmp\" \"$env_file\"\n"
            "trap - EXIT HUP INT TERM\n"
        )
        result = self.runtime.execute(
            ["sh", "-c", script, "weave-image-update", str(self.paths.env_file), image],
            timeout=20,
        )
        if not result.succeeded:
            raise RuntimeError(f"Unable to update WEAVE image: {result.stderr or result.stdout}")

    def has_exam_in_progress(self) -> bool:
        sql = "SELECT EXISTS(SELECT 1 FROM exams WHERE status IN ('active','suspended','closing','cancelling'));"
        command = f'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc {shlex.quote(sql)}'
        result = self.docker.compose(["exec", "-T", "postgres", "sh", "-lc", command], compose_file=self.paths.compose_file, project_directory=self.paths.root, env_file=self.paths.env_file, project_name=COMPOSE_PROJECT_NAME, timeout=30)
        if not result.succeeded:
            raise RuntimeError("Unable to verify whether an examination is active; update cancelled for safety.")
        return result.stdout.strip().lower() in {"t", "true", "1"}
