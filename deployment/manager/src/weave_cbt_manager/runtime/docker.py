"""Docker Engine service used inside a WEAVE CBT runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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
        return (
            self.installed
            and self.running
            and self.compose_available
        )


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
        return self.runtime.execute(
            command,
            timeout=timeout,
        )

    def is_installed(self) -> bool:
        """
        Return whether the Docker CLI exists inside the runtime.
        """

        result = self._execute(
            ["docker", "--version"],
            timeout=10,
        )

        return result.succeeded

    def is_running(self) -> bool:
        """
        Return whether Docker Engine is accepting commands.
        """

        if not self.is_installed():
            return False

        result = self._execute(
            ["docker", "info"],
            timeout=15,
        )

        return result.succeeded

    def compose_available(self) -> bool:
        """
        Return whether Docker Compose v2 is available.
        """

        if not self.is_installed():
            return False

        result = self._execute(
            ["docker", "compose", "version"],
            timeout=10,
        )

        return result.succeeded

    def status(self) -> DockerStatus:
        """
        Return the current Docker readiness state.
        """

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
        """
        Start Docker Engine inside the runtime.

        The WEAVE runtime is expected to use systemd to manage dockerd.
        """

        if not self.is_installed():
            raise RuntimeError(
                "Docker Engine is not installed inside the WEAVE CBT runtime."
            )

        if self.is_running():
            return

        result = self._execute(
            ["systemctl", "start", "docker"],
            timeout=30,
        )

        if not result.succeeded:
            raise RuntimeError(
                "Unable to start Docker Engine: "
                f"{result.stderr or result.stdout}"
            )

        if not self.is_running():
            raise RuntimeError(
                "Docker Engine was started but did not become ready."
            )

    def stop(self) -> None:
        """
        Stop Docker Engine inside the runtime.
        """

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
        """
        Restart Docker Engine inside the runtime.
        """

        if not self.is_installed():
            raise RuntimeError(
                "Docker Engine is not installed inside the WEAVE CBT runtime."
            )

        result = self._execute(
            ["systemctl", "restart", "docker"],
            timeout=30,
        )

        if not result.succeeded:
            raise RuntimeError(
                "Unable to restart Docker Engine: "
                f"{result.stderr or result.stdout}"
            )

        if not self.is_running():
            raise RuntimeError(
                "Docker Engine did not become ready after restart."
            )

    def ensure_ready(self) -> None:
        """
        Ensure the runtime and Docker Engine are ready for deployment.
        """

        if not self.runtime.is_installed():
            raise RuntimeError(
                "WEAVE CBT runtime has not been installed."
            )

        if not self.runtime.is_running():
            self.runtime.start()

        if not self.is_installed():
            raise RuntimeError(
                "Docker Engine is missing from the WEAVE CBT runtime."
            )

        if not self.compose_available():
            raise RuntimeError(
                "Docker Compose v2 is missing from the WEAVE CBT runtime."
            )

        if not self.is_running():
            self.start()

    def docker(
        self,
        arguments: Sequence[str],
        *,
        timeout: float | None = None,
    ) -> RuntimeCommandResult:
        """
        Execute an arbitrary Docker CLI command.

        Example:

            docker(["ps", "--all"])
        """

        if not arguments:
            raise ValueError(
                "Docker command arguments cannot be empty."
            )

        return self._execute(
            ["docker", *arguments],
            timeout=timeout,
        )

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

        command: list[str] = [
            "docker",
            "compose",
        ]

        if project_name is not None:
            command.extend(
                ["--project-name", project_name]
            )

        if compose_file is not None:
            command.extend(
                ["--file", str(compose_file)]
            )

        if project_directory is not None:
            command.extend(
                [
                    "--project-directory",
                    str(project_directory),
                ]
            )

        if env_file is not None:
            command.extend(
                ["--env-file", str(env_file)]
            )

        command.extend(arguments)

        return self._execute(
            command,
            timeout=timeout,
        )

    def pull(
        self,
        *,
        compose_file: Path | str,
        project_directory: Path | str | None = None,
        env_file: Path | str | None = None,
        project_name: str | None = None,
        timeout: float | None = 1800,
    ) -> None:
        """
        Pull all images referenced by the WEAVE Compose project.
        """

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
        """
        Start the WEAVE Compose stack in detached mode.
        """

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
        """
        Return Compose service status.
        """

        return self.compose(
            ["ps"],
            compose_file=compose_file,
            project_directory=project_directory,
            env_file=env_file,
            project_name=project_name,
            timeout=30,
        )