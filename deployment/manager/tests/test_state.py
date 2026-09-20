from weave_cbt_manager.state import ManagerState, StateStore


def test_state_round_trip_does_not_require_secrets(tmp_path):
    store = StateStore(tmp_path / "state.json")
    state = ManagerState()
    state.mark_installed(channel="staging", manager_version="0.1.0", cbt_version="0.1.0", image="repo/app:1")
    store.save(state)
    loaded = store.load()
    assert loaded.installation_status == "installed"
    assert loaded.current_image == "repo/app:1"
    assert "password" not in (tmp_path / "state.json").read_text().lower()
