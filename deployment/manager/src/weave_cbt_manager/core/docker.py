"""Docker and Compose orchestration for WEAVE CBT."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


class DockerCommandError(RuntimeError):
    """Raised when a Docker command exits unsuccessfully."""


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class DockerService:
    def __init__(self, *, compose_file: Path, env_file: Path) -> None:
        self.compose_file = compose_file
        self.env_file = env_file

    def _run(
        self,
        args: Sequence[str],
        *,
        check: bool = True,
        cwd: Path | None = None,
    ) -> CommandResult:
        creationflags = 0
        if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW

        completed = subprocess.run(
            list(args),
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
            check=False,
        )
        result = CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
        )
        if check and result.returncode != 0:
            detail = result.stderr or result.stdout or "Docker command failed."
            raise DockerCommandError(detail)
        return result

    def docker_available(self) -> bool:
        try:
            return self._run(["docker", "version"], check=False).returncode == 0
        except OSError:
            return False

    def compose_available(self) -> bool:
        try:
            return (
                self._run(["docker", "compose", "version"], check=False).returncode
                == 0
            )
        except OSError:
            return False

    def compose(self, *args: str, check: bool = True) -> CommandResult:
        command = [
            "docker",
            "compose",
            "--env-file",
            str(self.env_file),
            "-f",
            str(self.compose_file),
            *args,
        ]
        return self._run(command, check=check, cwd=self.compose_file.parent)

    def validate(self) -> None:
        self.compose("config", "--quiet")

    def pull(self) -> None:
        self.compose("pull")

    def up(self) -> None:
        self.compose("up", "-d")

    def down(self) -> None:
        self.compose("down")

    def restart(self) -> None:
        self.compose("restart")

    def running_services(self) -> set[str]:
        result = self.compose(
            "ps",
            "--services",
            "--filter",
            "status=running",
            check=False,
        )
        if result.returncode != 0:
            return set()
        return {line.strip() for line in result.stdout.splitlines() if line.strip()}

    def logs(self, service: str | None = None, *, tail: int = 200) -> str:
        args = ["logs", "--tail", str(tail)]
        if service:
            args.append(service)
        result = self.compose(*args, check=False)
        return "\n".join(part for part in (result.stdout, result.stderr) if part)
