from weave_cbt_manager.app import ManagerController
from weave_cbt_manager.state import ManagerState, StateStore


class _Runtime:
    def __init__(self, installed=True):
        self.installed = installed

    def is_installed(self):
        return self.installed


class _Deployment:
    def __init__(self, configured=True):
        self.configured = configured

    def config_exists(self):
        return self.configured


class _StateStore:
    def __init__(self, status):
        self.status = status

    def load(self):
        return ManagerState(installation_status=self.status)


def _controller_for_status(status: str, *, installed: bool = True, configured: bool = True) -> ManagerController:
    controller = ManagerController.__new__(ManagerController)
    controller.runtime = _Runtime(installed)
    controller.deployment = _Deployment(configured)
    controller.state_store = _StateStore(status)
    return controller


def test_state_round_trip_does_not_require_secrets(tmp_path):
    store = StateStore(tmp_path / "state.json")
    state = ManagerState()
    state.mark_installed(channel="staging", manager_version="0.1.0", cbt_version="0.1.0", image="repo/app:1")
    store.save(state)
    loaded = store.load()
    assert loaded.installation_status == "installed"
    assert loaded.current_image == "repo/app:1"
    assert "password" not in (tmp_path / "state.json").read_text().lower()


def test_partial_setup_is_not_treated_as_complete_installation():
    assert _controller_for_status("configuring").installation_present() is False
    assert _controller_for_status("setup_failed").installation_present() is False


def test_complete_and_retained_installations_are_recoverable():
    assert _controller_for_status("installed").installation_present() is True
    assert _controller_for_status("retained").installation_present() is True
    assert _controller_for_status("recovery_required").installation_present() is True


def test_installation_requires_runtime_and_complete_config_bundle():
    assert _controller_for_status("installed", installed=False).installation_present() is False
    assert _controller_for_status("installed", configured=False).installation_present() is False
