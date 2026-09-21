"""Windows WSL2 runtime provider for WEAVE CBT."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from time import sleep
from typing import Sequence

from ..base import (
    RuntimeCommandResult,
    RuntimePreparationResult,
    RuntimeProvider,
)


logger = logging.getLogger(__name__)

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
    ) -> subprocess.CompletedProcess[str]:
        """Run a captured WSL command after the distro has been started."""

        wsl = self._wsl_executable()
        if wsl is None:
            raise RuntimeError("WSL is not available on this system.")

        return subprocess.run(
            [str(wsl), *arguments],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            startupinfo=self._hidden_console_startupinfo(),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )

    def _run_distro_bootstrap(
        self,
        *,
        timeout: float,
    ) -> subprocess.CompletedProcess[bytes]:
        """Wake the WEAVE distro using normal console-backed WSL startup.

        The first distro command deliberately does not redirect standard
        streams through the GUI process. On affected WSL builds, cold-starting
        a systemd distro with redirected streams can fail even when the same
        interactive WSL command succeeds.
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
        A cold-start probe therefore gets a full 75-second window. If that
        attempt fails, a captured probe first checks whether the distro became
        usable anyway. Only when it is still unusable do we terminate only the
        dedicated WeaveCBT distro and perform one final full attempt.
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

    @staticmethod
    def _windows_path_to_wsl_mount(path: Path) -> str:
        """Map a local Windows drive path to the dedicated distro's /mnt path."""

        resolved = PureWindowsPath(str(path.resolve()))
        drive = resolved.drive
        if len(drive) != 2 or drive[1] != ":":
            raise RuntimeError(
                "WEAVE CBT could not stage configuration on a local Windows drive."
            )
        return str(
            PurePosixPath(
                "/mnt",
                drive[0].lower(),
                *resolved.parts[1:],
            )
        )

    @staticmethod
    def _stage_host_payload(content: str) -> Path:
        """Persist a short-lived payload in the current Windows user's temp area."""

        transfer_root = Path(tempfile.gettempdir()) / "WeaveCBT"
        transfer_root.mkdir(parents=True, exist_ok=True)
        descriptor, filename = tempfile.mkstemp(
            prefix="runtime-transfer-",
            suffix=".tmp",
            dir=transfer_root,
        )
        path = Path(filename)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content.encode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            path.unlink(missing_ok=True)
            raise
        return path

    @staticmethod
    def _cleanup_host_payload(path: Path) -> None:
        """Remove a staged payload, retrying briefly if Windows still holds it."""

        for _attempt in range(5):
            try:
                path.unlink(missing_ok=True)
                return
            except PermissionError:
                sleep(0.1)
            except OSError:
                break
        logger.warning("Unable to remove temporary WEAVE runtime transfer file: %s", path)

    def _runtime_file_matches(self, path: str, expected_sha256: str) -> bool:
        """Verify the runtime file exactly matches the staged payload."""

        try:
            result = self._run_in_distro(["sha256sum", "--", path], timeout=10)
        except (OSError, subprocess.TimeoutExpired, RuntimeError):
            return False
        if result.returncode != 0:
            return False
        output = self._normalize_wsl_output(result.stdout)
        if not output:
            return False
        actual = output.split(maxsplit=1)[0].lower()
        return actual == expected_sha256.lower()

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
        """Atomically copy UTF-8 content from a short-lived Windows staging file.

        Configuration bytes are never sent through wsl.exe stdin and never
        appear in process arguments. The Linux side reads a normal finite file
        from the mounted Windows drive, installs it atomically, and the Manager
        verifies the SHA-256 before deleting the host-side staging file.
        """

        if not path.startswith("/"):
            raise ValueError("Runtime file path must be absolute.")
        if len(mode) != 4 or mode[0] != "0" or any(
            character not in "01234567" for character in mode[1:]
        ):
            raise ValueError("Runtime file mode must be a four-digit octal mode.")
        if not self.is_installed():
            raise RuntimeError("WEAVE CBT WSL runtime has not been installed.")

        payload = content.encode("utf-8")
        expected_sha256 = hashlib.sha256(payload).hexdigest()
        staged_path = self._stage_host_payload(content)

        script = (
            "set -eu\n"
            "source_file=$1\n"
            "target=$2\n"
            "mode=$3\n"
            "parent=$(dirname -- \"$target\")\n"
            "if [ ! -r \"$source_file\" ]; then\n"
            "  printf '%s\\n' 'WEAVE staging file is not readable inside WSL.' >&2\n"
            "  exit 23\n"
            "fi\n"
            "install -d -m 0755 -- \"$parent\"\n"
            "tmp=\"${target}.tmp.$$\"\n"
            "cleanup() { rm -f -- \"$tmp\"; }\n"
            "trap cleanup EXIT HUP INT TERM\n"
            "install -m \"$mode\" -- \"$source_file\" \"$tmp\"\n"
            "mv -f -- \"$tmp\" \"$target\"\n"
            "trap - EXIT HUP INT TERM\n"
        )

        try:
            source_path = self._windows_path_to_wsl_mount(staged_path)
            try:
                result = self._run_in_distro(
                    [
                        "sh",
                        "-c",
                        script,
                        "weave-copy",
                        source_path,
                        path,
                        mode,
                    ],
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                if self._runtime_file_matches(path, expected_sha256):
                    return RuntimeCommandResult(0, "", "")
                return RuntimeCommandResult(
                    124,
                    "",
                    f"Timed out while copying runtime file {path}.",
                )
            except (OSError, RuntimeError) as exc:
                if self._runtime_file_matches(path, expected_sha256):
                    return RuntimeCommandResult(0, "", "")
                return RuntimeCommandResult(
                    1,
                    "",
                    f"Unable to copy runtime file {path}: {exc}",
                )

            stdout = self._normalize_wsl_output(result.stdout)
            stderr = self._normalize_wsl_output(result.stderr)
            if result.returncode != 0:
                if self._runtime_file_matches(path, expected_sha256):
                    return RuntimeCommandResult(0, stdout, stderr)
                return RuntimeCommandResult(result.returncode, stdout, stderr)

            if not self._runtime_file_matches(path, expected_sha256):
                return RuntimeCommandResult(
                    1,
                    stdout,
                    f"Runtime file verification failed for {path}.",
                )
            return RuntimeCommandResult(0, stdout, stderr)
        finally:
            self._cleanup_host_payload(staged_path)
