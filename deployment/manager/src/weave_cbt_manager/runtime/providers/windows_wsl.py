"""Windows WSL2 runtime provider for WEAVE CBT."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from ..base import RuntimeCommandResult, RuntimeProvider


WEAVE_DISTRO_NAME = "WeaveCBT"


class WindowsWSLRuntime(RuntimeProvider):
    """
    Runtime provider backed by WSL2 on Windows.

    This provider manages only the Linux environment required to host the
    container engine. Docker itself is managed by the Docker service.
    """

    def __init__(
        self,
        *,
        rootfs_archive: Path,
        install_directory: Path,
    ) -> None:
        self.rootfs_archive = rootfs_archive
        self.install_directory = install_directory

    @property
    def name(self) -> str:
        return "Windows WSL2"

    def _wsl_executable(self) -> Path | None:
        executable = shutil.which("wsl.exe")

        if executable is None:
            executable = shutil.which("wsl")

        if executable is None:
            return None

        return Path(executable)

    def _run_wsl(
        self,
        arguments: Sequence[str],
        *,
        timeout: float | None = 30,
    ) -> subprocess.CompletedProcess[str]:
        wsl = self._wsl_executable()

        if wsl is None:
            raise RuntimeError("WSL is not available on this system.")

        return subprocess.run(
            [str(wsl), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    @staticmethod
    def _normalize_wsl_output(value: str) -> str:
        """
        Normalize output returned by wsl.exe.

        Some Windows/WSL combinations may include null characters in
        redirected command output.
        """

        return value.replace("\x00", "").strip()

    def _listed_distros(
        self,
        *,
        running_only: bool = False,
    ) -> set[str]:
        arguments = ["--list"]

        if running_only:
            arguments.append("--running")

        arguments.append("--quiet")

        result = self._run_wsl(arguments)

        if result.returncode != 0:
            return set()

        output = self._normalize_wsl_output(result.stdout)

        return {
            line.strip()
            for line in output.splitlines()
            if line.strip()
        }

    def is_available(self) -> bool:
        """
        Return whether WSL is installed and responds successfully.

        This does not require the WEAVE CBT distro to already exist.
        """

        if self._wsl_executable() is None:
            return False

        try:
            result = self._run_wsl(["--status"])
        except (OSError, subprocess.TimeoutExpired, RuntimeError):
            return False

        return result.returncode == 0

    def is_installed(self) -> bool:
        """
        Return whether the dedicated WEAVE CBT WSL distro exists.
        """

        if not self.is_available():
            return False

        try:
            distros = self._listed_distros()
        except (OSError, subprocess.TimeoutExpired, RuntimeError):
            return False

        return WEAVE_DISTRO_NAME.casefold() in {
            distro.casefold()
            for distro in distros
        }

    def is_running(self) -> bool:
        """
        Return whether the WEAVE CBT WSL distro is currently running.
        """

        if not self.is_installed():
            return False

        try:
            running_distros = self._listed_distros(running_only=True)
        except (OSError, subprocess.TimeoutExpired, RuntimeError):
            return False

        return WEAVE_DISTRO_NAME.casefold() in {
            distro.casefold()
            for distro in running_distros
        }

    def install(self) -> None:
        """
        Import the dedicated WEAVE CBT Linux runtime into WSL2.

        This assumes WSL itself has already been enabled on Windows.

        The rootfs archive is supplied by the higher-level installer layer.
        """

        if not self.is_available():
            raise RuntimeError(
                "WSL2 is not available. Windows must enable WSL2 before "
                "the WEAVE CBT runtime can be provisioned."
            )

        if self.is_installed():
            return

        if not self.rootfs_archive.is_file():
            raise FileNotFoundError(
                f"WEAVE CBT root filesystem not found: "
                f"{self.rootfs_archive}"
            )

        self.install_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        result = self._run_wsl(
            [
                "--import",
                WEAVE_DISTRO_NAME,
                str(self.install_directory),
                str(self.rootfs_archive),
                "--version",
                "2",
            ],
            timeout=300,
        )

        if result.returncode != 0:
            stderr = self._normalize_wsl_output(result.stderr)

            raise RuntimeError(
                f"Unable to create WEAVE CBT WSL runtime: {stderr}"
            )

    def start(self) -> None:
        """
        Start the dedicated WEAVE CBT distro.

        Running a minimal command inside a WSL distro causes WSL to start it.
        """

        if not self.is_installed():
            raise RuntimeError(
                "WEAVE CBT WSL runtime has not been installed."
            )

        if self.is_running():
            return

        result = self._run_wsl(
            [
                "--distribution",
                WEAVE_DISTRO_NAME,
                "--",
                "true",
            ]
        )

        if result.returncode != 0:
            stderr = self._normalize_wsl_output(result.stderr)

            raise RuntimeError(
                f"Unable to start WEAVE CBT runtime: {stderr}"
            )

    def stop(self) -> None:
        """Terminate the dedicated WEAVE CBT WSL distro."""

        if not self.is_installed():
            return

        if not self.is_running():
            return

        result = self._run_wsl(
            [
                "--terminate",
                WEAVE_DISTRO_NAME,
            ]
        )

        if result.returncode != 0:
            stderr = self._normalize_wsl_output(result.stderr)

            raise RuntimeError(
                f"Unable to stop WEAVE CBT runtime: {stderr}"
            )

    def execute(
        self,
        command: Sequence[str],
        *,
        timeout: float | None = None,
    ) -> RuntimeCommandResult:
        """
        Execute a command inside the dedicated WEAVE CBT WSL distro.
        """

        if not command:
            raise ValueError("Runtime command cannot be empty.")

        if not self.is_installed():
            raise RuntimeError(
                "WEAVE CBT WSL runtime has not been installed."
            )

        result = self._run_wsl(
            [
                "--distribution",
                WEAVE_DISTRO_NAME,
                "--",
                *command,
            ],
            timeout=timeout,
        )

        return RuntimeCommandResult(
            return_code=result.returncode,
            stdout=self._normalize_wsl_output(result.stdout),
            stderr=self._normalize_wsl_output(result.stderr),
        )