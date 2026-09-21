from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import weave_cbt_manager.runtime.providers.windows_wsl as wsl_module
from weave_cbt_manager.runtime.providers.windows_wsl import WindowsWSLRuntime


def _runtime(tmp_path: Path) -> WindowsWSLRuntime:
    return WindowsWSLRuntime(
        rootfs_archive=tmp_path / "runtime.tar",
        install_directory=tmp_path / "runtime",
    )


def test_wsl_invocation_uses_hidden_real_console(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "_wsl_executable", lambda: Path("C:/Windows/System32/wsl.exe"))
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    runtime._run_wsl(["--status"])

    assert captured["creationflags"] == subprocess.CREATE_NEW_CONSOLE
    assert captured["stdin"] == subprocess.DEVNULL
    startupinfo = captured["startupinfo"]
    assert isinstance(startupinfo, subprocess.STARTUPINFO)
    assert startupinfo.dwFlags & subprocess.STARTF_USESHOWWINDOW
    assert startupinfo.wShowWindow == subprocess.SW_HIDE


def test_start_accepts_success_even_with_systemd_user_warning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    calls: list[tuple[str, ...]] = []

    def fake_run(command, *, timeout):
        calls.append(tuple(command))
        return subprocess.CompletedProcess(
            args=list(command),
            returncode=0,
            stdout="",
            stderr="wsl: Failed to start the systemd user session for 'root'.",
        )

    monkeypatch.setattr(runtime, "_run_in_distro", fake_run)

    runtime.start()

    assert calls == [("true",)]


def test_start_retries_transient_wsl_service_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    monkeypatch.setattr(wsl_module, "sleep", lambda _seconds: None)

    attempts = 0

    def fake_run(command, *, timeout):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return subprocess.CompletedProcess(
                args=list(command),
                returncode=1,
                stdout="",
                stderr=(
                    "Catastrophic failure\n"
                    "Error code: Wsl/Service/E_UNEXPECTED"
                ),
            )
        return subprocess.CompletedProcess(
            args=list(command),
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(runtime, "_run_in_distro", fake_run)

    runtime.start()

    assert attempts == 2


def test_responsiveness_timeout_reports_last_wsl_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    times = iter([0.0, 0.0, 0.5, 1.1])
    monkeypatch.setattr(wsl_module, "monotonic", lambda: next(times))
    monkeypatch.setattr(wsl_module, "sleep", lambda _seconds: None)

    def failed_run(command, *, timeout):
        return subprocess.CompletedProcess(
            args=list(command),
            returncode=1,
            stdout="",
            stderr="Error code: Wsl/Service/E_UNEXPECTED",
        )

    monkeypatch.setattr(runtime, "_run_in_distro", failed_run)

    with pytest.raises(RuntimeError, match="Last WSL error"):
        runtime._wait_for_distro_responsive(
            timeout=1.0,
            retry_interval=0.1,
        )
