"""Windows WSL2 runtime provider for WEAVE CBT."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from time import sleep
from typing import Sequence

from ..base import (
    RuntimeCommandResult,
    RuntimePreparationResult,
    RuntimeProvider,
)


WEAVE_DISTRO_NAME = "WeaveCBT"
_WSL_BOOT_CONFIG_COMMAND = (
    "printf '%s\\n' '[boot]' 'systemd=true' 'initTimeout=60000' '' "
    "'[user]' 'default=root' > /etc/wsl.conf"
)
_WSL_COLD_START_TIMEOUT_SECONDS = 75.0
_WSL_START_ATTEMPTS = 2
_WSL_RETRY_DELAY_SECONDS = 2.0


class WindowsWSLRuntime(RuntimeProvider):
    """Runtime provider backed by a dedicated WSL2 distro on Windows."""

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
        return Path(executable) if executable is not None else None

    @staticmethod
    def _hidden_console_startupinfo() -> subprocess.STARTUPINFO:
        """Create a hidden real-console configuration for Windows child processes."""

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        return startupinfo

    def _run_wsl(
        self,
        arguments: Sequence[str],
        *,
        timeout: float | None = 30,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a WSL management/command call whose output must be captured."""

        wsl = self._wsl_executable()
        if wsl is None:
            raise RuntimeError("WSL is not available on this system.")

        kwargs: dict[str, object] = {
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": timeout,
            "check": False,
            "startupinfo": self._hidden_console_startupinfo(),
            "creationflags": subprocess.CREATE_NEW_CONSOLE,
        }
        if input_text is None:
            kwargs["stdin"] = subprocess.DEVNULL
        else:
            # Transfer sensitive file content over stdin instead of placing it
            # in argv. This prevents database credentials from appearing in
            # process listings, exception text, or installer logs.
            kwargs["input"] = input_text

        return subprocess.run([str(wsl), *arguments], **kwargs)

    def _run_distro_bootstrap(
        self,
        *,
        timeout: float,
    ) -> subprocess.CompletedProcess[bytes]:
        """Wake the WEAVE distro using normal console-backed WSL startup.

        The first distro command deliberately does not pipe stdin/stdout/stderr
        through the GUI process. On affected WSL builds, cold-starting a
        systemd distro with redirected standard streams can return
        ``Wsl/Service/E_UNEXPECTED`` even though the identical interactive WSL
        command succeeds. Once WSL has brought the distro up, normal captured
        commands are safe to use for Docker and diagnostics.
        """

        wsl = self._wsl_executable()
        if wsl is None:
            raise RuntimeError("WSL is not available on this system.")

        return subprocess.run(
            [
                str(wsl),
                "--distribution",
                WEAVE_DISTRO_NAME,
                "--user",
                "root",
                "--",
                "true",
            ],
            timeout=timeout,
            check=False,
            startupinfo=self._hidden_console_startupinfo(),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )

    @staticmethod
    def _normalize_wsl_output(value: str) -> str:
        """Normalize redirected output returned by wsl.exe."""

        return value.replace("\x00", "").strip()

    def _listed_distros(self, *, running_only: bool = False) -> set[str]:
        arguments = ["--list"]
        if running_only:
            arguments.append("--running")
        arguments.append("--quiet")

        result = self._run_wsl(arguments)
        if result.returncode != 0:
            return set()

        output = self._normalize_wsl_output(result.stdout)
        return {line.strip() for line in output.splitlines() if line.strip()}

    def _run_in_distro(
        self,
        command: Sequence[str],
        *,
        timeout: float | None,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return self._run_wsl(
            [
                "--distribution",
                WEAVE_DISTRO_NAME,
                "--user",
                "root",
                "--",
                *command,
            ],
            timeout=timeout,
            input_text=input_text,
        )

    def _targeted_restart(self) -> None:
        """Reset only the WEAVE distro; never shut down unrelated WSL distros."""

        try:
            self._run_wsl(["--terminate", WEAVE_DISTRO_NAME], timeout=30)
        except (OSError, subprocess.TimeoutExpired, RuntimeError):
            return

    def _diagnose_boot_failure(self) -> str:
        """Capture a final WSL error after a bootstrap attempt has failed."""

        try:
            result = self._run_in_distro(["true"], timeout=10)
        except subprocess.TimeoutExpired:
            return "WSL startup probe timed out."
        except (OSError, RuntimeError) as exc:
            return str(exc)

        if result.returncode == 0:
            return ""
        return self._normalize_wsl_output(result.stderr or result.stdout)

    def _wait_for_distro_responsive(
        self,
        *,
        cold_start_timeout: float = _WSL_COLD_START_TIMEOUT_SECONDS,
        max_attempts: int = _WSL_START_ATTEMPTS,
        retry_delay: float = _WSL_RETRY_DELAY_SECONDS,
    ) -> None:
        """Start the dedicated distro without repeatedly interrupting systemd.

        WEAVE configures WSL to allow systemd initialization up to 60 seconds.
        A cold-start probe therefore gets a full 75-second window instead of
        being killed every 15 seconds. If that attempt fails, a short captured
        probe first checks whether the distro nevertheless became usable. Only
        when it is still unusable do we terminate *only* WeaveCBT and perform
        one final full cold-start attempt.
        """

        if cold_start_timeout <= 0:
            raise ValueError("WSL cold-start timeout must be positive.")
        if max_attempts < 1:
            raise ValueError("WSL startup attempts must be at least one.")
        if retry_delay < 0:
            raise ValueError("WSL retry delay cannot be negative.")

        last_error = ""

        for attempt in range(1, max_attempts + 1):
            try:
                result = self._run_distro_bootstrap(timeout=cold_start_timeout)
            except subprocess.TimeoutExpired:
                last_error = (
                    f"WSL startup attempt {attempt} exceeded "
                    f"{int(cold_start_timeout)} seconds."
                )
            except OSError as exc:
                last_error = str(exc)
            else:
                if result.returncode == 0:
                    return
                last_error = (
                    f"WSL startup attempt {attempt} exited with code "
                    f"{result.returncode}."
                )

            # The console-backed process can fail or time out even after WSL
            # has finished bringing the distro up. Before restarting anything,
            # verify whether a normal command is already succeeding.
            diagnostic = self._diagnose_boot_failure()
            if not diagnostic:
                return
            last_error = diagnostic

            if attempt < max_attempts:
                self._targeted_restart()
                if retry_delay:
                    sleep(retry_delay)

        raise RuntimeError(
            "WEAVE CBT runtime did not become responsive after "
            f"{max_attempts} startup attempt"
            + ("s" if max_attempts != 1 else "")
            + (f". Last WSL error: {last_error}" if last_error else ".")
        )

    def _apply_boot_config_best_effort(self) -> None:
        """Upgrade an existing WEAVE distro to the safer WSL boot settings."""

        try:
            self._run_in_distro(
                ["sh", "-c", _WSL_BOOT_CONFIG_COMMAND],
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired, RuntimeError):
            # The current session is already usable. This repair improves the
            # next cold start but must never turn a healthy runtime into a
            # failed installation solely because the config write was blocked.
            return

    def is_available(self) -> bool:
        if self._wsl_executable() is None:
            return False

        try:
            result = self._run_wsl(["--status"])
        except (OSError, subprocess.TimeoutExpired, RuntimeError):
            return False
        return result.returncode == 0

    def is_installed(self) -> bool:
        if not self.is_available():
            return False
        try:
            distros = self._listed_distros()
        except (OSError, subprocess.TimeoutExpired, RuntimeError):
            return False
        return WEAVE_DISTRO_NAME.casefold() in {
            distro.casefold() for distro in distros
        }

    def is_running(self) -> bool:
        if not self.is_installed():
            return False
        try:
            distros = self._listed_distros(running_only=True)
        except (OSError, subprocess.TimeoutExpired, RuntimeError):
            return False
        return WEAVE_DISTRO_NAME.casefold() in {
            distro.casefold() for distro in distros
        }

    def prepare(self) -> RuntimePreparationResult:
        if self.is_available():
            return RuntimePreparationResult(reboot_required=False)

        if self._wsl_executable() is None:
            raise RuntimeError(
                "wsl.exe is not available on this Windows installation."
            )

        try:
            result = self._run_wsl(
                ["--install", "--no-distribution"],
                timeout=600,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Timed out while preparing WSL2.") from exc

        output = self._normalize_wsl_output(f"{result.stdout}\n{result.stderr}")
        lowered = output.casefold()
        reboot_markers = (
            "restart your machine",
            "restart your computer",
            "reboot your machine",
            "reboot your computer",
            "changes will not be effective until the system is rebooted",
        )
        reboot_required = result.returncode == 3010 or any(
            marker in lowered for marker in reboot_markers
        )

        if result.returncode not in (0, 3010):
            raise RuntimeError(
                "Unable to prepare WSL2" + (f": {output}" if output else ".")
            )
        if reboot_required or not self.is_available():
            return RuntimePreparationResult(reboot_required=True)
        return RuntimePreparationResult(reboot_required=False)

    def install(self) -> None:
        if not self.is_available():
            raise RuntimeError(
                "WSL2 is not available. Windows must enable WSL2 before "
                "the WEAVE CBT runtime can be provisioned."
            )
        if self.is_installed():
            return
        if not self.rootfs_archive.is_file():
            raise FileNotFoundError(
                f"WEAVE CBT root filesystem not found: {self.rootfs_archive}"
            )

        self.install_directory.mkdir(parents=True, exist_ok=True)
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
        """Start the distro, allowing a complete WSL/systemd cold-start window."""

        if not self.is_installed():
            raise RuntimeError("WEAVE CBT WSL runtime has not been installed.")

        self._wait_for_distro_responsive()
        self._apply_boot_config_best_effort()

    def stop(self) -> None:
        if not self.is_installed() or not self.is_running():
            return

        result = self._run_wsl(["--terminate", WEAVE_DISTRO_NAME])
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
        if not command:
            raise ValueError("Runtime command cannot be empty.")
        if not self.is_installed():
            raise RuntimeError("WEAVE CBT WSL runtime has not been installed.")

        result = self._run_in_distro(command, timeout=timeout)
        return RuntimeCommandResult(
            return_code=result.returncode,
            stdout=self._normalize_wsl_output(result.stdout),
            stderr=self._normalize_wsl_output(result.stderr),
        )

    def write_text_file(
        self,
        path: str,
        content: str,
        *,
        mode: str,
        timeout: float | None = None,
    ) -> RuntimeCommandResult:
        """Atomically write a UTF-8 file without exposing its content in argv."""

        if not path.startswith("/"):
            raise ValueError("Runtime file path must be absolute.")
        if len(mode) != 4 or mode[0] != "0" or any(
            character not in "01234567" for character in mode[1:]
        ):
            raise ValueError("Runtime file mode must be a four-digit octal mode.")
        if not self.is_installed():
            raise RuntimeError("WEAVE CBT WSL runtime has not been installed.")

        script = (
            "set -eu\n"
            "target=$1\n"
            "mode=$2\n"
            "parent=$(dirname -- \"$target\")\n"
            "install -d -m 0755 -- \"$parent\"\n"
            "tmp=\"${target}.tmp.$$\"\n"
            "cleanup() { rm -f -- \"$tmp\"; }\n"
            "trap cleanup EXIT HUP INT TERM\n"
            "cat > \"$tmp\"\n"
            "chmod \"$mode\" \"$tmp\"\n"
            "mv -f -- \"$tmp\" \"$target\"\n"
            "trap - EXIT HUP INT TERM\n"
        )
        result = self._run_in_distro(
            ["sh", "-c", script, "weave-write", path, mode],
            timeout=timeout,
            input_text=content,
        )
        return RuntimeCommandResult(
            return_code=result.returncode,
            stdout=self._normalize_wsl_output(result.stdout),
            stderr=self._normalize_wsl_output(result.stderr),
        )
