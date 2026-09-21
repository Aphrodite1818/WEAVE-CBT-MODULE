from __future__ import annotations

import hashlib
import shutil
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
    assert "input" not in captured
    startupinfo = captured["startupinfo"]
    assert isinstance(startupinfo, subprocess.STARTUPINFO)
    assert startupinfo.dwFlags & subprocess.STARTF_USESHOWWINDOW
    assert startupinfo.wShowWindow == subprocess.SW_HIDE


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


def test_wsl_share_paths_do_not_depend_on_windows_drive_mounts(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    primary, fallback = runtime._wsl_share_candidates(
        "/tmp/weave-cbt-transfer-payload.tmp"
    )

    assert primary.casefold() == (
        r"\\wsl.localhost\WeaveCBT\tmp\weave-cbt-transfer-payload.tmp".casefold()
    )
    assert fallback.casefold() == (
        r"\\wsl$\WeaveCBT\tmp\weave-cbt-transfer-payload.tmp".casefold()
    )
    assert "/mnt/" not in primary
    assert "/mnt/" not in fallback


def test_copy_host_payload_falls_back_to_legacy_wsl_share(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    host_payload = tmp_path / "payload.tmp"
    host_payload.write_text("payload", encoding="utf-8")
    destinations: list[str] = []

    def fake_copy(source, destination):
        assert Path(source) == host_payload
        destinations.append(str(destination))
        if "wsl.localhost" in str(destination).casefold():
            raise OSError("primary WSL share unavailable")
        return str(destination)

    monkeypatch.setattr(shutil, "copyfile", fake_copy)

    runtime._copy_host_payload_to_wsl(
        host_payload,
        "/tmp/weave-cbt-transfer-payload.tmp",
    )

    assert len(destinations) == 2
    assert "wsl.localhost" in destinations[0].casefold()
    assert "wsl$" in destinations[1].casefold()


def test_write_text_file_uses_wsl_share_not_drvfs_or_stdin(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    staged = tmp_path / "payload.tmp"
    secret = "POSTGRES_PASSWORD='super-secret'\n"
    expected_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    calls: list[list[str]] = []
    copies: list[tuple[Path, str]] = []

    def stage(content: str) -> Path:
        assert content == secret
        staged.write_text(content, encoding="utf-8")
        return staged

    def copy_to_wsl(source: Path, destination: str) -> None:
        copies.append((source, destination))

    def fake_run(command, *, timeout):
        calls.append(list(command))
        if command[0] == "sha256sum":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=f"{expected_hash}  {command[-1]}\n",
                stderr="",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(runtime, "_stage_host_payload", stage)
    monkeypatch.setattr(runtime, "_copy_host_payload_to_wsl", copy_to_wsl)
    monkeypatch.setattr(runtime, "_run_in_distro", fake_run)

    result = runtime.write_text_file(
        "/opt/weave-cbt/runtime.env",
        secret,
        mode="0600",
        timeout=30,
    )

    assert result.succeeded
    assert not staged.exists()
    assert len(copies) == 1
    assert copies[0][0] == staged
    assert copies[0][1].startswith("/tmp/weave-cbt-transfer-")
    assert copies[0][1].endswith(".tmp")

    flattened = " ".join(part for command in calls for part in command)
    assert "/mnt/c" not in flattened
    assert "/mnt/d" not in flattened
    assert "cat >" not in flattened
    assert secret not in flattened
    assert ["install", "-d", "-m", "0755", "--", "/opt/weave-cbt"] in calls
    assert any(command[:3] == ["install", "-m", "0600"] for command in calls)
    assert ["mv", "-f", "--", copies[0][1], "/opt/weave-cbt/runtime.env"] in calls


def test_share_copy_failure_does_not_replace_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    staged = tmp_path / "payload.tmp"
    calls: list[list[str]] = []

    def stage(content: str) -> Path:
        staged.write_text(content, encoding="utf-8")
        return staged

    def fail_copy(_source: Path, _destination: str) -> None:
        raise RuntimeError("WSL share unavailable")

    def fake_run(command, *, timeout):
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(runtime, "_stage_host_payload", stage)
    monkeypatch.setattr(runtime, "_copy_host_payload_to_wsl", fail_copy)
    monkeypatch.setattr(runtime, "_run_in_distro", fake_run)

    result = runtime.write_text_file(
        "/opt/weave-cbt/runtime.env",
        "POSTGRES_PASSWORD='super-secret'\n",
        mode="0600",
        timeout=30,
    )

    assert not result.succeeded
    assert "wsl share unavailable" in result.stderr.lower()
    assert not any(command and command[0] == "mv" for command in calls)
    assert not staged.exists()


def test_move_timeout_is_accepted_when_target_hash_matches(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    staged = tmp_path / "payload.tmp"
    secret = "POSTGRES_PASSWORD='super-secret'\n"
    expected_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    move_attempts = 0

    def stage(content: str) -> Path:
        staged.write_text(content, encoding="utf-8")
        return staged

    def fake_run(command, *, timeout):
        nonlocal move_attempts
        if command[0] == "mv":
            move_attempts += 1
            raise subprocess.TimeoutExpired(cmd=command, timeout=timeout)
        if command[0] == "sha256sum":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=f"{expected_hash}  {command[-1]}\n",
                stderr="",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(runtime, "_stage_host_payload", stage)
    monkeypatch.setattr(runtime, "_copy_host_payload_to_wsl", lambda *_args: None)
    monkeypatch.setattr(runtime, "_run_in_distro", fake_run)

    result = runtime.write_text_file(
        "/opt/weave-cbt/runtime.env",
        secret,
        mode="0600",
        timeout=30,
    )

    assert result.succeeded
    assert move_attempts == 1
    assert not staged.exists()


def test_successful_move_is_rejected_when_target_hash_does_not_match(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    staged = tmp_path / "payload.tmp"
    secret = "POSTGRES_PASSWORD='super-secret'\n"
    expected_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    hash_calls = 0

    def stage(content: str) -> Path:
        staged.write_text(content, encoding="utf-8")
        return staged

    def fake_run(command, *, timeout):
        nonlocal hash_calls
        if command[0] == "sha256sum":
            hash_calls += 1
            digest = expected_hash if hash_calls == 1 else "0" * 64
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=f"{digest}  {command[-1]}\n",
                stderr="",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(runtime, "_stage_host_payload", stage)
    monkeypatch.setattr(runtime, "_copy_host_payload_to_wsl", lambda *_args: None)
    monkeypatch.setattr(runtime, "_run_in_distro", fake_run)

    result = runtime.write_text_file(
        "/opt/weave-cbt/runtime.env",
        secret,
        mode="0600",
        timeout=30,
    )

    assert not result.succeeded
    assert "verification failed" in result.stderr.lower()
    assert not staged.exists()


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

    def fake_run(command, *, timeout):
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


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-16-le"])
def test_wsl_output_preserves_localized_diagnostics(encoding):
    message = "WSL: erreur syst?me ? 0x80370102"
    assert WindowsWSLRuntime._decode_output(message.encode(encoding)) == message


def test_inbox_wsl_with_no_systemd_support_is_not_ready(monkeypatch, tmp_path):
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "_wsl_executable", lambda: Path("wsl.exe"))
    calls = []

    def run(arguments, **kwargs):
        calls.append(arguments)
        return subprocess.CompletedProcess(
            arguments,
            0 if arguments == ["--status"] else 1,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(runtime, "_run_wsl", run)
    assert runtime.is_available() is False
    assert calls == [["--status"], ["--version"]]


def test_keepalive_is_detached_and_scoped_to_weave(monkeypatch, tmp_path):
    from unittest.mock import Mock

    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "_wsl_executable", lambda: Path("wsl.exe"))
    launch = Mock()
    monkeypatch.setattr(subprocess, "Popen", launch)
    runtime.keep_alive()
    command = launch.call_args.args[0]
    assert command[1:3] == ["--distribution", "WeaveCBT"]
    assert "flock" in command
    assert command[-2:] == ["sleep", "infinity"]
    assert launch.call_args.kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW
