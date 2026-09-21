from __future__ import annotations

import sys

import weave_cbt_manager.__main__ as manager_entry
from weave_cbt_manager.app import ManagerController


def test_self_test_runs_before_controller_construction(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["weave-cbt-manager", "--self-test"])
    monkeypatch.setattr(manager_entry, "_run_self_test", lambda: 0)

    def unexpected_controller():
        raise AssertionError("self-test must not construct ManagerController")

    monkeypatch.setattr(manager_entry, "ManagerController", unexpected_controller)

    assert manager_entry.main() == 0


def test_parser_recognizes_self_test() -> None:
    arguments = manager_entry._parser().parse_args(["--self-test"])

    assert arguments.self_test is True
    assert arguments.first_run is False
    assert arguments.startup is False


def test_development_build_uses_acceptance_disk_floor() -> None:
    controller = ManagerController()

    assert controller.prerequisites.policy.minimum_free_disk_gb == 4.0
    # An 8 GB host exposes slightly less usable physical RAM to Windows.
    assert controller.prerequisites.policy.minimum_memory_gb == 7.5
