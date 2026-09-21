from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from weave_cbt_manager.runtime.providers.windows_wsl import WindowsWSLRuntime


def _runtime(tmp_path: Path) -> WindowsWSLRuntime:
    return WindowsWSLRuntime(
        rootfs_archive=tmp_path / "runtime.tar",
        install_directory=tmp_path / "runtime",
    )


def test_start_waits_for_systemd_even_when_wsl_already_reports_running(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    monkeypatch.setattr(runtime, "is_running", lambda: True)
    calls: list[tuple[str, ...]] = []

    def fake_run(command, *, timeout):
        calls.append(tuple(command))
        return subprocess.CompletedProcess(
            args=list(command),
            returncode=1,
            stdout="degraded\n",
            stderr="wsl: Failed to start the systemd user session for 'root'.",
        )

    monkeypatch.setattr(runtime, "_run_in_distro", fake_run)

    runtime.start()

    assert calls == [("systemctl", "is-system-running", "--wait")]


def test_start_cold_distro_then_waits_for_systemd(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    monkeypatch.setattr(runtime, "is_running", lambda: False)
    calls: list[tuple[str, ...]] = []

    def fake_run(command, *, timeout):
        normalized = tuple(command)
        calls.append(normalized)
        if normalized == ("true",):
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if normalized == ("systemctl", "is-system-running", "--wait"):
            return subprocess.CompletedProcess(command, 0, stdout="running\n", stderr="")
        raise AssertionError(f"Unexpected command: {normalized}")

    monkeypatch.setattr(runtime, "_run_in_distro", fake_run)

    runtime.start()

    assert calls == [
        ("true",),
        ("systemctl", "is-system-running", "--wait"),
    ]


def test_systemd_readiness_timeout_is_reported_cleanly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)

    def timeout_run(command, *, timeout):
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(runtime, "_run_in_distro", timeout_run)

    with pytest.raises(RuntimeError, match="system services did not become ready"):
        runtime._wait_for_systemd_ready(timeout=1)
