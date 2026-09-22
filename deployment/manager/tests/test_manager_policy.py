from __future__ import annotations

from subprocess import CompletedProcess
from unittest.mock import Mock

import weave_cbt_manager.app as app_module
from weave_cbt_manager.build_metadata import BuildEnvironment, BuildMetadata
from weave_cbt_manager.constants import NETWORK_RECONCILE_TASK_NAME
from weave_cbt_manager.core.startup import WindowsStartupService


def metadata(environment: BuildEnvironment) -> BuildMetadata:
    return BuildMetadata(
        environment=environment,
        weave_api_base_url=(
            "https://api.weavecloudspace.com"
            if environment is BuildEnvironment.PROD
            else "https://weave-container-staging.up.railway.app"
        ),
        weave_image="ghcr.io/aphrodite1818/weave-cbt-module@sha256:" + ("0" * 64),
        cbt_version="0.1.0",
    )


def test_production_keeps_twenty_gb_disk_floor(monkeypatch):
    monkeypatch.setattr(app_module, "BUILD_METADATA", metadata(BuildEnvironment.PROD))
    controller = app_module.ManagerController()
    assert controller.prerequisites.policy.minimum_free_disk_gb == 20.0


def test_staging_uses_acceptance_test_disk_floor(monkeypatch):
    monkeypatch.setattr(app_module, "BUILD_METADATA", metadata(BuildEnvironment.STAGING))
    controller = app_module.ManagerController()
    assert controller.prerequisites.policy.minimum_free_disk_gb == 4.0


def test_startup_tasks_include_periodic_network_reconciliation():
    service = WindowsStartupService(executable=r"C:\Program Files\WEAVE CBT\manager\WeaveCBT-Manager.exe")
    service._run = Mock(
        side_effect=[
            CompletedProcess(["whoami"], 0, stdout="SCHOOL\\admin\n", stderr=""),
            CompletedProcess([], 0, stdout="", stderr=""),
            CompletedProcess([], 0, stdout="", stderr=""),
            CompletedProcess([], 0, stdout="", stderr=""),
        ]
    )

    service.install_tasks()

    commands = [call.args[0] for call in service._run.call_args_list]
    network_task = next(
        command
        for command in commands
        if NETWORK_RECONCILE_TASK_NAME in command
    )
    assert "/SC" in network_task and "MINUTE" in network_task
    assert "/MO" in network_task and "5" in network_task
    assert "/RL" in network_task and "HIGHEST" in network_task
    assert "--reconcile-network" in network_task[-1]
