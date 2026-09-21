from unittest.mock import Mock
import pytest
from weave_cbt_manager.app import ManagerController
from weave_cbt_manager.build_metadata import BUILD_METADATA
from weave_cbt_manager.core.config import ConfigService
from weave_cbt_manager.core.health import HealthSnapshot
from weave_cbt_manager.state import StateStore

def controller(tmp_path, *, saved=False, data=False):
    c = ManagerController.__new__(ManagerController)
    c.state_store = StateStore(tmp_path / "state.json")
    c.runtime = Mock()
    c.docker = Mock()
    c.platform = Mock()
    c.platform.lan_ip.return_value = "192.168.1.10"
    c.networking = Mock()
    c.startup = Mock()
    c.config = ConfigService(BUILD_METADATA)
    c.deployment = Mock()
    c.deployment.environment_exists.return_value = saved
    c.deployment.has_persistent_data.return_value = data
    c.deployment.read_asset.return_value = "asset"
    c.health = Mock()
    c.health.wait_until_healthy.return_value = HealthSnapshot(True, True, True, "Healthy")
    return c

def test_retry_reuses_configuration_after_image_download_failure(tmp_path):
    c = controller(tmp_path)
    c.deployment.deploy.side_effect = RuntimeError("Download interrupted")
    with pytest.raises(RuntimeError, match="Download interrupted"):
        c.install_application()
    first_env = c.deployment.prepare_assets.call_args.kwargs["runtime_env"]
    assert "POSTGRES_PASSWORD=" in first_env
    assert c.state.installation_status == "setup_failed"
    c.deployment.environment_exists.return_value = True
    c.deployment.deploy.side_effect = None
    c.install_application()
    c.deployment.prepare_assets.assert_called_once()
    c.deployment.refresh_assets.assert_called_once()
    assert c.state.installation_status == "installed"
    assert "POSTGRES_PASSWORD" not in c.state_store.path.read_text()

def test_missing_configuration_never_overwrites_existing_school_data(tmp_path):
    c = controller(tmp_path, data=True)
    with pytest.raises(RuntimeError, match="School data already exists"):
        c.install_application()
    c.deployment.prepare_assets.assert_not_called()
    c.deployment.deploy.assert_not_called()

def test_repairing_saved_setup_preserves_previously_installed_image(tmp_path):
    c = controller(tmp_path, saved=True)
    c.state_store.update(current_image="repo/app@sha256:previous", current_cbt_version="1.2.3")
    c.install_application()
    assert c.state.current_image == "repo/app@sha256:previous"
    assert c.state.current_cbt_version == "1.2.3"

def test_wrong_channel_fails_before_runtime_or_configuration_changes(tmp_path):
    c = controller(tmp_path)
    c.state_store.update(channel="other-channel")
    with pytest.raises(RuntimeError, match="separate server computers"):
        c.install_application()
    c.docker.ensure_ready.assert_not_called()
    c.deployment.prepare_assets.assert_not_called()
