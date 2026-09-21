from __future__ import annotations

import subprocess

import weave_cbt_manager.runtime.docker as docker_module
from weave_cbt_manager.runtime.base import RuntimeCommandResult
from weave_cbt_manager.runtime.docker import DockerService


class ColdStartRuntime:
    def __init__(self) -> None:
        self.started = False
        self.daemon_running = False
        self.version_attempts = 0
        self.commands: list[tuple[str, ...]] = []

    def is_installed(self) -> bool:
        return True

    def is_running(self) -> bool:
        return self.started

    def start(self) -> None:
        self.started = True

    def execute(
        self,
        command,
        *,
        timeout=None,
    ) -> RuntimeCommandResult:
        normalized = tuple(command)
        self.commands.append(normalized)

        if normalized == ("docker", "--version"):
            self.version_attempts += 1
            if self.version_attempts == 1:
                raise subprocess.TimeoutExpired(command, timeout)
            return RuntimeCommandResult(0, "Docker version 29.8.1", "")

        if normalized == ("docker", "compose", "version"):
            return RuntimeCommandResult(0, "Docker Compose version v2", "")

        if normalized == ("docker", "info"):
            if self.daemon_running:
                return RuntimeCommandResult(0, "Server Version: 29.8.1", "")
            return RuntimeCommandResult(1, "", "daemon not ready")

        if normalized == ("systemctl", "start", "docker"):
            self.daemon_running = True
            return RuntimeCommandResult(0, "", "")

        raise AssertionError(f"Unexpected command: {normalized}")


class AlwaysTimingOutRuntime(ColdStartRuntime):
    def execute(
        self,
        command,
        *,
        timeout=None,
    ) -> RuntimeCommandResult:
        normalized = tuple(command)
        if normalized == ("docker", "--version"):
            raise subprocess.TimeoutExpired(command, timeout)
        return super().execute(command, timeout=timeout)


def test_ensure_ready_retries_cold_wsl_timeout_and_starts_daemon(monkeypatch) -> None:
    runtime = ColdStartRuntime()
    service = DockerService(runtime)
    monkeypatch.setattr(docker_module, "sleep", lambda _seconds: None)

    service.ensure_ready()

    assert runtime.started is True
    assert runtime.daemon_running is True
    assert runtime.version_attempts >= 2
    assert ("systemctl", "start", "docker") in runtime.commands


def test_status_treats_probe_timeout_as_transient_unavailability() -> None:
    service = DockerService(AlwaysTimingOutRuntime())

    status = service.status()

    assert status.installed is False
    assert status.running is False
    assert status.compose_available is False
