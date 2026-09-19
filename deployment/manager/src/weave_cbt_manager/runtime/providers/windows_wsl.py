"""Windows WSL2 runtime provider for WEAVE CBT."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from ..base import (
    RuntimeCommandResult,
    RuntimePreparationResult,
    RuntimeProvider,
)


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
        executable = shutil.which("wsl.exe") or shutil.which("wsl")

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
        """Normalize redirected output returned by wsl.exe."""

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
        """Return whether the dedicated WEAVE CBT WSL distro exists."""

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
        """Return whether the WEAVE CBT WSL distro is currently running."""

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

    def prepare(self) -> RuntimePreparationResult:
        """
        Enable/install the WSL capability required by this provider.

        The Manager is expected to be running elevated when this operation is
        necessary. The dedicated WEAVE distro itself is created by install().
        """

        if self.is_available():
            return RuntimePreparationResult(reboot_required=False)

        wsl = self._wsl_executable()

        if wsl is None:
            raise RuntimeError(
                "wsl.exe is not available on this Windows installation."
            )

        try:
            result = self._run_wsl(
                ["--install", "--no-distribution"],
                timeout=600,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "Timed out while preparing WSL2."
            ) from exc

        output = self._normalize_wsl_output(
            f"{result.stdout}\n{result.stderr}"
        )
        lowered_output = output.casefold()

        reboot_markers = (
            "restart",
            "reboot",
            "changes will not be effective until the system is rebooted",
        )
        reboot_required = (
            result.returncode == 3010
            or any(marker in lowered_output for marker in reboot_markers)
        )

        if result.returncode not in (0, 3010):
            raise RuntimeError(
                "Unable to prepare WSL2"
                + (f": {output}" if output else ".")
            )

        if reboot_required:
            return RuntimePreparationResult(reboot_required=True)

        if not self.is_available():
            # Windows feature activation can succeed but remain unavailable
            # until after a reboot.
            return RuntimePreparationResult(reboot_required=True)

        return RuntimePreparationResult(reboot_required=False)

    def install(self) -> None:
        """Import the dedicated WEAVE CBT Linux runtime into WSL2."""

        if not self.is_available():
            raise RuntimeError(
                "WSL2 is not available. Windows must enable WSL2 before "
                "the WEAVE CBT runtime can be provisioned."
            )

        if self.is_installed():
            return

        if not self.rootfs_archive.is_file():
            raise FileNotFoundError(
                "WEAVE CBT root filesystem not found: "
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
                "Unable to create WEAVE CBT WSL runtime"
                + (f": {stderr}" if stderr else ".")
            )

    def start(self) -> None:
        """Start the dedicated WEAVE CBT distro."""

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
                "Unable to start WEAVE CBT runtime"
                + (f": {stderr}" if stderr else ".")
            )

    def stop(self) -> None:
        """Terminate the dedicated WEAVE CBT WSL distro."""

        if not self.is_installed() or not self.is_running():
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
                "Unable to stop WEAVE CBT runtime"
                + (f": {stderr}" if stderr else ".")
            )

    def execute(
        self,
        command: Sequence[str],
        *,
        timeout: float | None = None,
    ) -> RuntimeCommandResult:
        """Execute a command inside the dedicated WEAVE CBT WSL distro."""

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
