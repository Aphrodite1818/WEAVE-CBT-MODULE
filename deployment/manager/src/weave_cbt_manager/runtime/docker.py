"""Docker Engine service used inside a WEAVE CBT runtime."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep
from typing import Sequence

from .base import RuntimeCommandResult, RuntimeProvider


@dataclass(frozen=True, slots=True)
class DockerStatus:
    """Current Docker capabilities inside the runtime."""

    installed: bool
    running: bool
    compose_available: bool

    @property
    def ready(self) -> bool:
        return self.installed and self.running and self.compose_available


class DockerService:
    """
    Manage Docker Engine inside a RuntimeProvider.

    This class does not know whether the underlying environment is:

    - WSL2 on Windows
    - native Linux
    - a Linux VM on macOS

    All commands are executed through RuntimeProvider.
    """

    def __init__(self, runtime: RuntimeProvider) -> None:
        self.runtime = runtime

    def _execute(
        self,
        command: Sequence[str],
        *,
        timeout: float | None = 30,
    ) -> RuntimeCommandResult:
        return self.runtime.execute(command, timeout=timeout)

    def _probe(
        self,
        command: Sequence[str],
        *,
        timeout: float,
    ) -> RuntimeCommandResult | None:
        """Run a read-only Docker probe without surfacing transient timeouts."""

        try:
            return self._execute(command, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    def _wait_for_command(
        self,
        command: Sequence[str],
        *,
        timeout_seconds: float,
        attempt_timeout_seconds: float = 15.0,
        retry_interval_seconds: float = 2.0,
    ) -> bool:
        """
        Retry a Docker probe until it succeeds or the bounded deadline expires.

        Cold WSL2 starts can take substantially longer than an individual
        Docker CLI probe. A timed-out probe is therefore treated as transient,
        while the overall deadline still prevents installation from hanging.
        """

        deadline = monotonic() + timeout_seconds

        while True:
            remaining = deadline - monotonic()
            if remaining <= 0:
                return False

            result = self._probe(
                command,
                timeout=min(attempt_timeout_seconds, remaining),
            )
            if result is not None and result.succeeded:
                return True

            remaining = deadline - monotonic()
            if remaining <= 0:
                return False

            sleep(min(retry_interval_seconds, remaining))

    def is_installed(self) -> bool:
        """Return whether the Docker CLI exists inside the runtime."""

        result = self._probe(["docker", "--version"], timeout=15)
        return result is not None and result.succeeded

    def wait_until_installed(self, *, timeout_seconds: float = 60.0) -> bool:
        """Wait for the Docker CLI to become responsive after runtime startup."""

        return self._wait_for_command(
            ["docker", "--version"],
            timeout_seconds=timeout_seconds,
        )

    def is_running(self) -> bool:
        """Return whether Docker Engine is accepting commands."""

        if not self.is_installed():
            return False

        result = self._probe(["docker", "info"], timeout=20)
        return result is not None and result.succeeded

    def wait_until_running(self, *, timeout_seconds: float = 60.0) -> bool:
        """Wait until the Docker daemon accepts commands."""

        return self._wait_for_command(
            ["docker", "info"],
            timeout_seconds=timeout_seconds,
        )

    def compose_available(self) -> bool:
        """Return whether Docker Compose v2 is available."""

        if not self.is_installed():
            return False

        result = self._probe(["docker", "compose", "version"], timeout=15)
        return result is not None and result.succeeded

    def wait_until_compose_available(
        self,
        *,
        timeout_seconds: float = 60.0,
    ) -> bool:
        """Wait until Docker Compose v2 responds successfully."""

        return self._wait_for_command(
            ["docker", "compose", "version"],
            timeout_seconds=timeout_seconds,
        )

    def status(self) -> DockerStatus:
        """Return the current Docker readiness state without raising on probe timeouts."""

        installed = self.is_installed()

        if not installed:
            return DockerStatus(
                installed=False,
                running=False,
                compose_available=False,
            )

        return DockerStatus(
            installed=True,
            running=self.is_running(),
            compose_available=self.compose_available(),
        )

    def start(self) -> None:
        """Start Docker Engine inside the runtime and wait for daemon readiness."""

        if not self.wait_until_installed(timeout_seconds=60):
            raise RuntimeError(
                "Docker Engine is not installed inside the WEAVE CBT runtime."
            )

        if self.is_running():
            return

        result = self._execute(
            ["systemctl", "start", "docker"],
            timeout=60,
        )

        if not result.succeeded:
            raise RuntimeError(
                "Unable to start Docker Engine: "
                f"{result.stderr or result.stdout}"
            )

        if not self.wait_until_running(timeout_seconds=60):
            raise RuntimeError(
                "Docker Engine was started but did not become ready within 60 seconds."
            )

    def stop(self) -> None:
        """Stop Docker Engine inside the runtime."""

        if not self.is_installed():
            return

        if not self.is_running():
            return

        result = self._execute(
            ["systemctl", "stop", "docker"],
            timeout=30,
        )

        if not result.succeeded:
            raise RuntimeError(
                "Unable to stop Docker Engine: "
                f"{result.stderr or result.stdout}"
            )

    def restart(self) -> None:
        """Restart Docker Engine inside the runtime."""

        if not self.wait_until_installed(timeout_seconds=60):
            raise RuntimeError(
                "Docker Engine is not installed inside the WEAVE CBT runtime."
            )

        result = self._execute(
            ["systemctl", "restart", "docker"],
            timeout=60,
        )

        if not result.succeeded:
            raise RuntimeError(
                "Unable to restart Docker Engine: "
                f"{result.stderr or result.stdout}"
            )

        if not self.wait_until_running(timeout_seconds=60):
            raise RuntimeError(
                "Docker Engine did not become ready within 60 seconds after restart."
            )

    def ensure_ready(self) -> None:
        """Ensure the runtime, Docker CLI, Compose, and daemon are ready."""

        if not self.runtime.is_installed():
            raise RuntimeError("WEAVE CBT runtime has not been installed.")

        if not self.runtime.is_running():
            self.runtime.start()

        if not self.wait_until_installed(timeout_seconds=60):
            raise RuntimeError(
                "Docker Engine did not become available within 60 seconds of starting the WEAVE CBT runtime."
            )

        if not self.wait_until_compose_available(timeout_seconds=60):
            raise RuntimeError(
                "Docker Compose v2 did not become available within 60 seconds of starting the WEAVE CBT runtime."
            )

        if not self.is_running():
            self.start()

        if not self.wait_until_running(timeout_seconds=60):
            raise RuntimeError(
                "Docker Engine did not become ready within 60 seconds."
            )

    def docker(
        self,
        arguments: Sequence[str],
        *,
        timeout: float | None = None,
    ) -> RuntimeCommandResult:
        """Execute an arbitrary Docker CLI command."""

        if not arguments:
            raise ValueError("Docker command arguments cannot be empty.")

        return self._execute(["docker", *arguments], timeout=timeout)

    def compose(
        self,
        arguments: Sequence[str],
        *,
        compose_file: Path | str | None = None,
        project_directory: Path | str | None = None,
        env_file: Path | str | None = None,
        project_name: str | None = None,
        timeout: float | None = None,
    ) -> RuntimeCommandResult:
        """
        Execute a Docker Compose v2 command.

        Paths supplied here are paths inside the runtime, not Windows
        filesystem paths.
        """

        command: list[str] = ["docker", "compose"]

        if project_name is not None:
            command.extend(["--project-name", project_name])

        if compose_file is not None:
            command.extend(["--file", str(compose_file)])

        if project_directory is not None:
            command.extend(["--project-directory", str(project_directory)])

        if env_file is not None:
            command.extend(["--env-file", str(env_file)])

        command.extend(arguments)

        return self._execute(command, timeout=timeout)

    def pull(
        self,
        *,
        compose_file: Path | str,
        project_directory: Path | str | None = None,
        env_file: Path | str | None = None,
        project_name: str | None = None,
        timeout: float | None = 1800,
    ) -> None:
        """Pull all images referenced by the WEAVE Compose project."""

        result = self.compose(
            ["pull"],
            compose_file=compose_file,
            project_directory=project_directory,
            env_file=env_file,
            project_name=project_name,
            timeout=timeout,
        )

        if not result.succeeded:
            raise RuntimeError(
                "Unable to pull WEAVE CBT container images: "
                f"{result.stderr or result.stdout}"
            )

    def up(
        self,
        *,
        compose_file: Path | str,
        project_directory: Path | str | None = None,
        env_file: Path | str | None = None,
        project_name: str | None = None,
        timeout: float | None = 300,
    ) -> None:
        """Start the WEAVE Compose stack in detached mode."""

        result = self.compose(
            ["up", "--detach"],
            compose_file=compose_file,
            project_directory=project_directory,
            env_file=env_file,
            project_name=project_name,
            timeout=timeout,
        )

        if not result.succeeded:
            raise RuntimeError(
                "Unable to start WEAVE CBT containers: "
                f"{result.stderr or result.stdout}"
            )

    def down(
        self,
        *,
        compose_file: Path | str,
        project_directory: Path | str | None = None,
        env_file: Path | str | None = None,
        project_name: str | None = None,
        timeout: float | None = 120,
    ) -> None:
        """
        Stop the WEAVE Compose stack.

        Volumes are deliberately preserved.
        """

        result = self.compose(
            ["down"],
            compose_file=compose_file,
            project_directory=project_directory,
            env_file=env_file,
            project_name=project_name,
            timeout=timeout,
        )

        if not result.succeeded:
            raise RuntimeError(
                "Unable to stop WEAVE CBT containers: "
                f"{result.stderr or result.stdout}"
            )

    def ps(
        self,
        *,
        compose_file: Path | str,
        project_directory: Path | str | None = None,
        env_file: Path | str | None = None,
        project_name: str | None = None,
    ) -> RuntimeCommandResult:
        """Return Compose service status."""

        return self.compose(
            ["ps"],
            compose_file=compose_file,
            project_directory=project_directory,
            env_file=env_file,
            project_name=project_name,
            timeout=30,
        )
