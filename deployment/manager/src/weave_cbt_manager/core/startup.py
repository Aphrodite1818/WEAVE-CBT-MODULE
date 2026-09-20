"""Windows scheduled-task and reboot-resume integration."""

from __future__ import annotations

import subprocess
import sys

from ..constants import RUNONCE_VALUE_NAME, STARTUP_TASK_NAME, UPDATE_CHECK_TASK_NAME


class WindowsStartupService:
    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or sys.executable

    def _manager_command(self, argument: str) -> str:
        return f'"{self.executable}" {argument}'

    @staticmethod
    def _run(arguments: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(arguments, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, creationflags=subprocess.CREATE_NO_WINDOW)
        if check and result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Windows task command failed.")
        return result

    def install_tasks(self) -> None:
        self._run(["schtasks", "/Create", "/F", "/RL", "HIGHEST", "/SC", "ONLOGON", "/TN", STARTUP_TASK_NAME, "/TR", self._manager_command("--startup")])
        self._run(["schtasks", "/Create", "/F", "/RL", "HIGHEST", "/SC", "DAILY", "/ST", "12:00", "/TN", UPDATE_CHECK_TASK_NAME, "/TR", self._manager_command("--check-updates")])

    def remove_tasks(self) -> None:
        for name in (STARTUP_TASK_NAME, UPDATE_CHECK_TASK_NAME):
            self._run(["schtasks", "/Delete", "/F", "/TN", name], check=False)

    def register_resume_after_reboot(self) -> None:
        self._run(["reg", "add", r"HKLM\Software\Microsoft\Windows\CurrentVersion\RunOnce", "/v", RUNONCE_VALUE_NAME, "/t", "REG_SZ", "/d", self._manager_command("--first-run"), "/f"])

    def clear_resume_after_reboot(self) -> None:
        self._run(["reg", "delete", r"HKLM\Software\Microsoft\Windows\CurrentVersion\RunOnce", "/v", RUNONCE_VALUE_NAME, "/f"], check=False)

    @staticmethod
    def restart_windows() -> None:
        subprocess.Popen(["shutdown", "/r", "/t", "0"], creationflags=subprocess.CREATE_NO_WINDOW)
