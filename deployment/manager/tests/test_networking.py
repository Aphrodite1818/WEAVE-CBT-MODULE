import json
from unittest.mock import Mock
import pytest
from weave_cbt_manager.core.networking import WindowsNetworkingService
from weave_cbt_manager.runtime.base import RuntimeCommandResult

def service(tmp_path, target="172.25.1.2"):
    runtime = Mock()
    runtime.execute.return_value = RuntimeCommandResult(0, json.dumps([{"prefsrc": target}]), "")
    s = WindowsNetworkingService(runtime, tmp_path / "network.json")
    s._run = Mock(return_value="")
    return s

def test_network_exposes_only_web_port_on_the_school_interface(tmp_path):
    s = service(tmp_path)
    s.configure("192.168.1.10")
    commands = [c.args[0] for c in s._run.call_args_list]
    forwarding = next(c for c in commands if c[:5] == ["netsh", "interface", "portproxy", "add", "v4tov4"])
    assert "listenaddress=192.168.1.10" in forwarding
    assert "listenport=80" in forwarding
    assert "connectaddress=172.25.1.2" in forwarding
    firewall = commands[-1][-1]
    assert "-RemoteAddress LocalSubnet -Profile Private,Domain" in firewall
    assert "5432" not in firewall and "6379" not in firewall

def test_foreign_port_forward_is_never_overwritten(tmp_path):
    s = service(tmp_path)
    s._run.return_value = "192.168.1.10  80  10.0.0.1  9000"
    with pytest.raises(RuntimeError, match="another application"):
        s.configure("192.168.1.10")
    assert s._run.call_count == 1

def test_changed_wsl_address_updates_owned_rule(tmp_path):
    s = service(tmp_path, "172.25.99.3")
    s.state_path.write_text('{"listen_address":"192.168.1.10"}')
    s._run.return_value = "192.168.1.10  80  172.25.1.2  80"
    s.configure("192.168.1.10")
    assert any("connectaddress=172.25.99.3" in c.args[0] for c in s._run.call_args_list)

def test_no_lan_does_not_prevent_local_use(tmp_path):
    s = service(tmp_path)
    s.configure(None)
    s.runtime.execute.assert_not_called()
    s._run.assert_not_called()

def test_mirrored_network_never_forwards_back_to_itself(tmp_path):
    s = service(tmp_path, "192.168.1.10")
    s.configure("192.168.1.10")
    assert not any("portproxy" in c.args[0] and "add" in c.args[0] for c in s._run.call_args_list)
