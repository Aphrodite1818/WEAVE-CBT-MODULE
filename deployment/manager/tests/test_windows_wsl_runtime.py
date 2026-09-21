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


def test_captured_wsl_invocation_uses_hidden_real_console(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(
        runtime,
        "_wsl_executable",
        lambda: Path("C:/Windows/System32/wsl.exe"),
    )
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    runtime._run_wsl(["--status"])

    assert captured["creationflags"] == subprocess.CREATE_NEW_CONSOLE
    assert captured["stdin"] == subprocess.DEVNULL
    assert captured["capture_output"] is True
    startupinfo = captured["startupinfo"]
    assert isinstance(startupinfo, subprocess.STARTUPINFO)
    assert startupinfo.dwFlags & subprocess.STARTF_USESHOWWINDOW
    assert startupinfo.wShowWindow == subprocess.SW_HIDE


def test_wsl_input_is_sent_over_stdin_not_process_arguments(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(
        runtime,
        "_wsl_executable",
        lambda: Path("C:/Windows/System32/wsl.exe"),
    )
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    secret = "POSTGRES_PASSWORD='not-for-argv'\n"
    runtime._run_wsl(["--status"], input_text=secret)

    assert captured["input"] == secret
    assert "stdin" not in captured
    assert secret not in " ".join(captured["command"])


def test_bootstrap_wsl_invocation_does_not_redirect_standard_streams(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(
        runtime,
        "_wsl_executable",
        lambda: Path("C:/Windows/System32/wsl.exe"),
    )
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    runtime._run_distro_bootstrap(timeout=15)

    assert captured["creationflags"] == subprocess.CREATE_NEW_CONSOLE
    assert "stdin" not in captured
    assert "stdout" not in captured
    assert "stderr" not in captured
    assert "capture_output" not in captured
    assert captured["command"][-1] == "true"


def test_write_text_file_is_atomic_and_does_not_put_secret_in_argv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    captured: dict[str, object] = {}

    def fake_run(command, *, timeout, input_text=None):
        captured["command"] = list(command)
        captured["timeout"] = timeout
        captured["input_text"] = input_text
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(runtime, "_run_in_distro", fake_run)

    secret = "POSTGRES_PASSWORD='super-secret'\n"
    result = runtime.write_text_file(
        "/opt/weave-cbt/runtime.env",
        secret,
        mode="0600",
        timeout=20,
    )

    assert result.succeeded
    assert captured["input_text"] == secret
    assert captured["timeout"] == 20
    command = captured["command"]
    assert command[:2] == ["sh", "-c"]
    assert "-l" not in command
    assert command[-2:] == ["/opt/weave-cbt/runtime.env", "0600"]
    assert "super-secret" not in " ".join(command)
    assert "mv -f" in command[2]
    assert "trap cleanup" in command[2]


def test_start_repairs_existing_boot_config_after_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    monkeypatch.setattr(
        runtime,
        "_run_distro_bootstrap",
        lambda *, timeout: subprocess.CompletedProcess(["wsl"], 0),
    )
    repaired = False

    def repair() -> None:
        nonlocal repaired
        repaired = True

    monkeypatch.setattr(runtime, "_apply_boot_config_best_effort", repair)

    runtime.start()

    assert repaired is True


def test_start_retries_and_targeted_restarts_only_weave_distro(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    monkeypatch.setattr(wsl_module, "sleep", lambda _seconds: None)
    monkeypatch.setattr(runtime, "_apply_boot_config_best_effort", lambda: None)

    attempts = 0
    restarts = 0

    def fake_bootstrap(*, timeout):
        nonlocal attempts
        attempts += 1
        return subprocess.CompletedProcess(
            ["wsl"],
            0 if attempts == 4 else 1,
        )

    def targeted_restart() -> None:
        nonlocal restarts
        restarts += 1

    monkeypatch.setattr(runtime, "_run_distro_bootstrap", fake_bootstrap)
    monkeypatch.setattr(runtime, "_targeted_restart", targeted_restart)

    runtime.start()

    assert attempts == 4
    assert restarts == 1


def test_responsiveness_timeout_reports_final_wsl_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    times = iter([0.0, 0.0, 0.5, 1.1])
    monkeypatch.setattr(wsl_module, "monotonic", lambda: next(times))
    monkeypatch.setattr(wsl_module, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        runtime,
        "_run_distro_bootstrap",
        lambda *, timeout: subprocess.CompletedProcess(["wsl"], 1),
    )
    monkeypatch.setattr(
        runtime,
        "_diagnose_boot_failure",
        lambda: "Error code: Wsl/Service/E_UNEXPECTED",
    )

    with pytest.raises(RuntimeError, match="Last WSL error"):
        runtime._wait_for_distro_responsive(
            timeout=1.0,
            retry_interval=0.1,
        )


def test_existing_runtime_boot_config_is_upgraded_best_effort(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    calls: list[tuple[str, ...]] = []

    def fake_run(command, *, timeout, input_text=None):
        calls.append(tuple(command))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(runtime, "_run_in_distro", fake_run)

    runtime._apply_boot_config_best_effort()

    assert len(calls) == 1
    assert calls[0][:2] == ("sh", "-c")
    assert "initTimeout=60000" in calls[0][2]
    assert "default=root" in calls[0][2]


def test_runtime_rootfs_has_longer_wsl_init_timeout_and_user_session_support() -> None:
    dockerfile = (
        Path(__file__).resolve().parents[1]
        / "runtime"
        / "distro"
        / "Dockerfile"
    ).read_text(encoding="utf-8")

    assert "initTimeout=60000" in dockerfile
    assert "dbus-user-session" in dockerfile
    assert "libpam-systemd" in dockerfile
