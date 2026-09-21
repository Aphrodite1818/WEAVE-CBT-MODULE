import json

from weave_cbt_manager.app import ManagerController
from weave_cbt_manager.state import ManagerState, StateStore


class _Runtime:
    def __init__(self, installed=True):
        self.installed = installed

    def is_installed(self):
        return self.installed


class _Deployment:
    def __init__(self):
        self.probed = False

    def config_exists(self):
        self.probed = True
        raise AssertionError(
            "installation_present must not cold-start WSL through config_exists"
        )


class _StateStore:
    def __init__(self, status):
        self.status = status

    def load(self):
        return ManagerState(installation_status=self.status)


def _controller_for_status(
    status: str,
    *,
    installed: bool = True,
) -> ManagerController:
    controller = ManagerController.__new__(ManagerController)
    controller.runtime = _Runtime(installed)
    controller.deployment = _Deployment()
    controller.state_store = _StateStore(status)
    return controller


def test_state_round_trip_does_not_require_secrets(tmp_path):
    store = StateStore(tmp_path / "state.json")
    state = ManagerState()
    state.mark_installed(
        channel="staging",
        manager_version="0.1.0",
        cbt_version="0.1.0",
        image="repo/app:1",
    )
    store.save(state)
    loaded = store.load()
    assert loaded.installation_status == "installed"
    assert loaded.current_image == "repo/app:1"
    assert "password" not in (tmp_path / "state.json").read_text().lower()


def test_empty_retained_state_self_heals_to_fresh_setup(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "installation_status": "retained",
                "channel": "unknown",
                "manager_version": "0.0.0",
                "current_cbt_version": None,
                "current_image": None,
                "installed_at": None,
            }
        ),
        encoding="utf-8",
    )

    loaded = StateStore(path).load()

    assert loaded.installation_status == "new"
    assert loaded.current_image is None
    assert loaded.current_cbt_version is None


def test_retained_state_with_deployment_identity_is_preserved(tmp_path):
    path = tmp_path / "state.json"
    state = ManagerState(
        installation_status="retained",
        channel="staging",
        manager_version="0.1.11",
        current_cbt_version="0.1.0",
        current_image="repo/app@sha256:abc",
    )
    StateStore(path).save(state)

    loaded = StateStore(path).load()

    assert loaded.installation_status == "retained"


def test_partial_setup_is_not_treated_as_complete_installation():
    assert _controller_for_status("configuring").installation_present() is False
    assert _controller_for_status("setup_failed").installation_present() is False


def test_complete_and_retained_installations_are_recoverable_without_runtime_file_probe():
    for status in ("installed", "retained", "recovery_required"):
        controller = _controller_for_status(status)
        assert controller.installation_present() is True
        assert controller.deployment.probed is False


def test_installation_still_requires_registered_weave_runtime():
    controller = _controller_for_status("installed", installed=False)
    assert controller.installation_present() is False
    assert controller.deployment.probed is False
