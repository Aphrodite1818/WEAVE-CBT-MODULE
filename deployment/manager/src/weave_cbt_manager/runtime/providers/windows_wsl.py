"""Windows WSL2 runtime provider for WEAVE CBT."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
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

        result = subprocess.run(
            [str(wsl), *arguments],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            check=False,
            startupinfo=self._hidden_console_startupinfo(),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        # WSL management commands emit UTF-16LE on Windows; Linux commands
        # emit UTF-8. Decoding everything as UTF-8 corrupts localized errors.
        return subprocess.CompletedProcess(
            result.args,
            result.returncode,
            self._decode_output(result.stdout),
            self._decode_output(result.stderr),
        )

    @staticmethod
    def _decode_output(value: bytes | str | None) -> str:
        if isinstance(value, str):
            return value
        if not value:
            return ""
        encoding = (
            "utf-16"
            if value.startswith((b"\xff\xfe", b"\xfe\xff"))
            else ("utf-16-le" if b"\x00" in value else "utf-8")
        )
        return value.decode(encoding, errors="replace").lstrip("\ufeff")

    def _modern_wsl_available(self) -> bool:
        result = self._run_wsl(["--version"])
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", result.stdout)
        return bool(
            result.returncode == 0
            and match
            and tuple(map(int, match.groups())) >= (0, 67, 6)
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

    @staticmethod
    def _wsl_share_candidates(runtime_path: str) -> tuple[str, str]:
        """Return Windows UNC paths for a file inside the dedicated WSL distro.

        Writing through the WSL filesystem share avoids depending on DrvFS
        automounts such as /mnt/c or /mnt/d. Those mounts can be unavailable or
        unreadable for imported distros and elevated installer temp files.
        """

        posix_path = PurePosixPath(runtime_path)
        if not posix_path.is_absolute():
            raise ValueError("Runtime staging path must be absolute.")
        relative_parts = posix_path.parts[1:]
        return (
            str(
                PureWindowsPath(
                    rf"\\wsl.localhost\{WEAVE_DISTRO_NAME}",
                    *relative_parts,
                )
            ),
            str(
                PureWindowsPath(
                    rf"\\wsl$\{WEAVE_DISTRO_NAME}",
                    *relative_parts,
                )
            ),
        )

    def _copy_host_payload_to_wsl(self, host_path: Path, runtime_path: str) -> None:
        """Copy a staged Windows file into WSL without using wsl.exe stdin.

        Modern WSL exposes each running distro through \\wsl.localhost; \\wsl$
        remains a compatibility alias. Trying both removes the previous
        dependency on Linux being able to read the Windows temp directory.
        """

        errors: list[str] = []
        for candidate in self._wsl_share_candidates(runtime_path):
            try:
                shutil.copyfile(host_path, candidate)
                return
            except OSError as exc:
                errors.append(f"{candidate}: {exc}")

        detail = "; ".join(errors)
        raise RuntimeError(
            "Windows could not transfer the WEAVE configuration into the local "
            "Linux runtime through the WSL filesystem share"
            + (f": {detail}" if detail else ".")
        )

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
            return result.returncode == 0 and self._modern_wsl_available()
        except (OSError, subprocess.TimeoutExpired, RuntimeError):
            return False

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

        # Inbox WSL can pass --status while lacking systemd support.
        status = self._run_wsl(["--status"])
        if status.returncode == 0:
            result = self._run_wsl(["--update", "--web-download"], timeout=600)
            if result.returncode != 0:
                raise RuntimeError(
                    "Unable to update WSL: "
                    + self._normalize_wsl_output(result.stderr or result.stdout)
                )
            return RuntimePreparationResult(reboot_required=not self.is_available())

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
            stderr = self._normalize_wsl_output(result.stderr or result.stdout)
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

    def keep_alive(self) -> None:
        """Hold a WSL client open independently of the desktop window.

        A Linux flock makes repeated starts harmless. Systemd services alone
        do not prevent WSL idle shutdown. This process ends with this distro.
        """

        wsl = self._wsl_executable()
        if wsl is None:
            raise RuntimeError("WSL is unavailable.")
        subprocess.Popen(
            [
                str(wsl),
                "--distribution",
                WEAVE_DISTRO_NAME,
                "--user",
                "root",
                "--exec",
                "flock",
                "--nonblock",
                "/run/weave-cbt-keepalive.lock",
                "sleep",
                "infinity",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

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
        """Atomically place UTF-8 content inside the dedicated WSL distro.

        The payload is first written to a short-lived Windows temp file, then
        Windows copies it directly into the running distro through the WSL UNC
        filesystem share. Linux never has to read /mnt/c or /mnt/d, and the
        payload never appears in wsl.exe arguments or stdin. A SHA-256 check is
        performed before and after the atomic rename.
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
        target = PurePosixPath(path)
        runtime_staging = PurePosixPath("/tmp") / (
            f"weave-cbt-transfer-{secrets.token_hex(12)}.tmp"
        )
        command_timeout = timeout if timeout is not None else 30

        try:
            parent_result = self._run_in_distro(
                ["install", "-d", "-m", "0755", "--", str(target.parent)],
                timeout=command_timeout,
            )
            if parent_result.returncode != 0:
                return RuntimeCommandResult(
                    parent_result.returncode,
                    self._normalize_wsl_output(parent_result.stdout),
                    self._normalize_wsl_output(
                        parent_result.stderr or parent_result.stdout
                    ),
                )

            staging_result = self._run_in_distro(
                [
                    "install",
                    "-m",
                    mode,
                    "/dev/null",
                    str(runtime_staging),
                ],
                timeout=command_timeout,
            )
            if staging_result.returncode != 0:
                return RuntimeCommandResult(
                    staging_result.returncode,
                    self._normalize_wsl_output(staging_result.stdout),
                    self._normalize_wsl_output(
                        staging_result.stderr or staging_result.stdout
                    ),
                )

            try:
                self._copy_host_payload_to_wsl(staged_path, str(runtime_staging))
            except (OSError, RuntimeError) as exc:
                return RuntimeCommandResult(
                    1,
                    "",
                    f"Unable to copy runtime file {path}: {exc}",
                )

            if not self._runtime_file_matches(str(runtime_staging), expected_sha256):
                return RuntimeCommandResult(
                    1,
                    "",
                    f"Runtime staging verification failed for {path}.",
                )

            try:
                move_result = self._run_in_distro(
                    ["mv", "-f", "--", str(runtime_staging), path],
                    timeout=command_timeout,
                )
            except subprocess.TimeoutExpired:
                if self._runtime_file_matches(path, expected_sha256):
                    return RuntimeCommandResult(0, "", "")
                return RuntimeCommandResult(
                    124,
                    "",
                    f"Timed out while finalizing runtime file {path}.",
                )
            except (OSError, RuntimeError) as exc:
                if self._runtime_file_matches(path, expected_sha256):
                    return RuntimeCommandResult(0, "", "")
                return RuntimeCommandResult(
                    1,
                    "",
                    f"Unable to finalize runtime file {path}: {exc}",
                )

            stdout = self._normalize_wsl_output(move_result.stdout)
            stderr = self._normalize_wsl_output(move_result.stderr)
            if move_result.returncode != 0:
                if self._runtime_file_matches(path, expected_sha256):
                    return RuntimeCommandResult(0, stdout, stderr)
                return RuntimeCommandResult(
                    move_result.returncode,
                    stdout,
                    stderr,
                )

            if not self._runtime_file_matches(path, expected_sha256):
                return RuntimeCommandResult(
                    1,
                    stdout,
                    f"Runtime file verification failed for {path}.",
                )
            return RuntimeCommandResult(0, stdout, stderr)
        finally:
            self._cleanup_host_payload(staged_path)
            try:
                self._run_in_distro(
                    ["rm", "-f", "--", str(runtime_staging)],
                    timeout=10,
                )
            except (OSError, subprocess.TimeoutExpired, RuntimeError):
                pass
