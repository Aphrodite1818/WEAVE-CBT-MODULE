from unittest.mock import Mock

import pytest

import weave_cbt_manager.app as app_module
from weave_cbt_manager.app import ManagerController
from weave_cbt_manager.core.deployment import DatabaseCredentials, DeploymentPaths, DeploymentService
from weave_cbt_manager.runtime.base import RuntimeCommandResult
from weave_cbt_manager.state import StateStore


def test_database_credentials_are_read_from_runtime_env_without_state_copy(tmp_path):
    runtime = Mock()
    runtime.execute.return_value = RuntimeCommandResult(
        0,
        "POSTGRES_DB='weave_cbt'\n"
        "POSTGRES_USER='weave'\n"
        "POSTGRES_PASSWORD='Generated-secret_123'\n"
        "DATABASE_URL='postgresql+asyncpg://hidden'\n",
        "",
    )
    deployment = DeploymentService(runtime, Mock())

    credentials = deployment.database_credentials()

    assert credentials == DatabaseCredentials("weave_cbt", "weave", "Generated-secret_123")
    runtime.execute.assert_called_once_with(["cat", "/opt/weave-cbt/runtime.env"], timeout=10)


def _controller(tmp_path, *, admin=True):
    controller = ManagerController.__new__(ManagerController)
    controller.state_store = StateStore(tmp_path / "state.json")
    controller.platform = Mock()
    controller.platform.is_admin.return_value = admin
    controller.platform.account_sid.return_value = "S-1-test"
    controller.runtime = Mock()
    controller.runtime.is_installed.return_value = True
    controller.docker = Mock()
    controller.deployment = Mock()
    controller.deployment.environment_exists.return_value = True
    controller.deployment.paths = DeploymentPaths()
    return controller


def test_reveal_database_credentials_requires_administrator(tmp_path):
    controller = _controller(tmp_path, admin=False)

    with pytest.raises(RuntimeError, match="Administrator privileges"):
        controller.database_credentials()

    controller.runtime.start.assert_not_called()
    controller.deployment.database_credentials.assert_not_called()


def test_reveal_database_credentials_starts_runtime_but_does_not_persist_secret(tmp_path):
    controller = _controller(tmp_path)
    expected = DatabaseCredentials("weave_cbt", "weave", "Generated-secret_123")
    controller.deployment.database_credentials.return_value = expected

    assert controller.database_credentials() == expected

    controller.runtime.start.assert_called_once_with()
    controller.runtime.keep_alive.assert_called_once_with()
    assert "Generated-secret_123" not in controller.state_store.path.read_text() if controller.state_store.path.exists() else True


def test_database_console_is_local_interactive_wsl_session(tmp_path, monkeypatch):
    controller = _controller(tmp_path)
    launch = Mock()
    monkeypatch.setattr(app_module.shutil, "which", lambda _name: r"C:\Windows\System32\wsl.exe")
    monkeypatch.setattr(app_module.subprocess, "Popen", launch)

    controller.open_database_console()

    controller.docker.ensure_ready.assert_called_once_with()
    controller.deployment.ensure_running.assert_called_once_with()
    command = launch.call_args.args[0]
    assert command[:5] == [r"C:\Windows\System32\wsl.exe", "--distribution", "WeaveCBT", "--user", "root"]
    assert "exec" in command
    assert "postgres" in command
    assert "psql" in command[-1]
    assert "POSTGRES_PASSWORD" not in " ".join(command)
    assert launch.call_args.kwargs["creationflags"] == app_module.subprocess.CREATE_NEW_CONSOLE
