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

    runtime._run_distro_bootstrap(timeout=75)

    assert captured["creationflags"] == subprocess.CREATE_NEW_CONSOLE
    assert captured["timeout"] == 75
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


def test_start_allows_complete_cold_start_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    timeouts: list[float] = []

    def fake_bootstrap(*, timeout):
        timeouts.append(timeout)
        return subprocess.CompletedProcess(["wsl"], 0)

    monkeypatch.setattr(runtime, "_run_distro_bootstrap", fake_bootstrap)
    monkeypatch.setattr(runtime, "_apply_boot_config_best_effort", lambda: None)

    runtime.start()

    assert timeouts == [75.0]


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


def test_start_retries_once_and_targeted_restarts_only_weave_distro(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    monkeypatch.setattr(wsl_module, "sleep", lambda _seconds: None)
    monkeypatch.setattr(runtime, "_apply_boot_config_best_effort", lambda: None)

    timeouts: list[float] = []
    restarts = 0

    def fake_bootstrap(*, timeout):
        timeouts.append(timeout)
        return subprocess.CompletedProcess(
            ["wsl"],
            0 if len(timeouts) == 2 else 1,
        )

    def targeted_restart() -> None:
        nonlocal restarts
        restarts += 1

    monkeypatch.setattr(runtime, "_run_distro_bootstrap", fake_bootstrap)
    monkeypatch.setattr(
        runtime,
        "_diagnose_boot_failure",
        lambda: "Error code: Wsl/Service/E_UNEXPECTED",
    )
    monkeypatch.setattr(runtime, "_targeted_restart", targeted_restart)

    runtime.start()

    assert timeouts == [75.0, 75.0]
    assert restarts == 1


def test_bootstrap_timeout_is_accepted_if_followup_probe_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    monkeypatch.setattr(runtime, "_apply_boot_config_best_effort", lambda: None)
    restarts = 0

    def timed_out_bootstrap(*, timeout):
        raise subprocess.TimeoutExpired(cmd=["wsl"], timeout=timeout)

    def targeted_restart() -> None:
        nonlocal restarts
        restarts += 1

    monkeypatch.setattr(runtime, "_run_distro_bootstrap", timed_out_bootstrap)
    monkeypatch.setattr(runtime, "_diagnose_boot_failure", lambda: "")
    monkeypatch.setattr(runtime, "_targeted_restart", targeted_restart)

    runtime.start()

    assert restarts == 0


def test_failed_start_reports_final_wsl_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(wsl_module, "sleep", lambda _seconds: None)
    attempts = 0
    restarts = 0

    def timed_out_bootstrap(*, timeout):
        nonlocal attempts
        attempts += 1
        raise subprocess.TimeoutExpired(cmd=["wsl"], timeout=timeout)

    def targeted_restart() -> None:
        nonlocal restarts
        restarts += 1

    monkeypatch.setattr(runtime, "_run_distro_bootstrap", timed_out_bootstrap)
    monkeypatch.setattr(
        runtime,
        "_diagnose_boot_failure",
        lambda: "WSL startup probe timed out.",
    )
    monkeypatch.setattr(runtime, "_targeted_restart", targeted_restart)

    with pytest.raises(RuntimeError, match="Last WSL error"):
        runtime._wait_for_distro_responsive()

    assert attempts == 2
    assert restarts == 1


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
