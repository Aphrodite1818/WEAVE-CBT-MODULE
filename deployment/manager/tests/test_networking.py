import json
from unittest.mock import Mock

import pytest

from weave_cbt_manager.core.networking import WindowsNetworkingService
from weave_cbt_manager.runtime.base import RuntimeCommandResult


def service(tmp_path, target="172.25.1.2"):
    runtime = Mock()
    runtime.execute.return_value = RuntimeCommandResult(
        0,
        json.dumps(
            [
                {
                    "ifname": "eth0",
                    "addr_info": [
                        {
                            "family": "inet",
                            "local": target,
                            "scope": "global",
                        }
                    ],
                },
                {
                    "ifname": "docker0",
                    "addr_info": [
                        {
                            "family": "inet",
                            "local": "172.17.0.1",
                            "scope": "global",
                        }
                    ],
                },
            ]
        ),
        "",
    )
    instance = WindowsNetworkingService(runtime, tmp_path / "network.json")
    instance._run = Mock(return_value="")
    return instance


def calls(service):
    return [call.args[0] for call in service._run.call_args_list]


def test_network_exposes_only_web_port_on_the_school_interface(tmp_path):
    instance = service(tmp_path)
    instance.configure("192.168.1.10")

    commands = calls(instance)
    forwarding = next(
        command
        for command in commands
        if command[:5] == ["netsh", "interface", "portproxy", "add", "v4tov4"]
    )
    assert "listenaddress=192.168.1.10" in forwarding
    assert "listenport=80" in forwarding
    assert "connectaddress=172.25.1.2" in forwarding
    firewall = commands[-1][-1]
    assert "-RemoteAddress LocalSubnet -Profile Private,Domain" in firewall
    assert "5432" not in firewall and "6379" not in firewall
    saved = json.loads(instance.state_path.read_text(encoding="utf-8"))
    assert saved == {
        "connect_address": "172.25.1.2",
        "listen_address": "192.168.1.10",
    }


def test_runtime_address_discovery_does_not_require_internet_route(tmp_path):
    instance = service(tmp_path)
    instance.configure("192.168.1.10")
    command = instance.runtime.execute.call_args.args[0]
    assert command == ["ip", "-j", "-4", "addr", "show", "scope", "global"]
    assert "1.1.1.1" not in command


def test_foreign_port_forward_is_never_overwritten(tmp_path):
    instance = service(tmp_path)
    instance._run.return_value = "192.168.1.10  80  10.0.0.1  9000"
    with pytest.raises(RuntimeError, match="another application"):
        instance.configure("192.168.1.10")
    assert instance._run.call_count == 1


def test_wildcard_port_forward_is_treated_as_conflict(tmp_path):
    instance = service(tmp_path)
    instance._run.return_value = "0.0.0.0  80  10.0.0.1  9000"
    with pytest.raises(RuntimeError, match="already forwards port 80"):
        instance.configure("192.168.1.10")


def test_changed_wsl_address_replaces_owned_rule_before_adding_new_target(tmp_path):
    instance = service(tmp_path, "172.25.99.3")
    instance.state_path.write_text(
        json.dumps(
            {
                "listen_address": "192.168.1.10",
                "connect_address": "172.25.1.2",
            }
        ),
        encoding="utf-8",
    )
    instance._run.return_value = "192.168.1.10  80  172.25.1.2  80"

    instance.configure("192.168.1.10")

    commands = calls(instance)
    delete_index = next(
        index
        for index, command in enumerate(commands)
        if command[:5] == ["netsh", "interface", "portproxy", "delete", "v4tov4"]
    )
    add_index = next(
        index
        for index, command in enumerate(commands)
        if command[:5] == ["netsh", "interface", "portproxy", "add", "v4tov4"]
    )
    assert delete_index < add_index
    assert "connectaddress=172.25.99.3" in commands[add_index]


def test_legacy_saved_rule_without_connect_address_is_still_recoverable(tmp_path):
    instance = service(tmp_path, "172.25.99.3")
    instance.state_path.write_text(
        '{"listen_address":"192.168.1.10"}', encoding="utf-8"
    )
    instance._run.return_value = "192.168.1.10  80  172.25.1.2  80"
    instance.configure("192.168.1.10")
    assert any(
        "connectaddress=172.25.99.3" in command
        for command in calls(instance)
    )


def test_no_lan_does_not_probe_runtime_and_removes_firewall_exposure(tmp_path):
    instance = service(tmp_path)
    instance.configure(None)
    instance.runtime.execute.assert_not_called()
    assert any(
        command[0] == "powershell.exe" and "Remove-NetFirewallRule" in command[-1]
        for command in calls(instance)
    )


def test_no_lan_removes_previous_weave_forwarding(tmp_path):
    instance = service(tmp_path)
    instance.state_path.write_text(
        json.dumps(
            {
                "listen_address": "192.168.1.10",
                "connect_address": "172.25.1.2",
            }
        ),
        encoding="utf-8",
    )
    instance.configure(None)
    assert any(
        command[:5] == ["netsh", "interface", "portproxy", "delete", "v4tov4"]
        for command in calls(instance)
    )
    assert not instance.state_path.exists()


def test_corrupt_network_state_does_not_crash_fresh_configuration(tmp_path):
    instance = service(tmp_path)
    instance.state_path.write_text("not-json", encoding="utf-8")
    instance.configure("192.168.1.10")
    saved = json.loads(instance.state_path.read_text(encoding="utf-8"))
    assert saved["connect_address"] == "172.25.1.2"


def test_mirrored_network_never_forwards_back_to_itself(tmp_path):
    instance = service(tmp_path, "192.168.1.10")
    instance.configure("192.168.1.10")
    assert not any(
        command[:5] == ["netsh", "interface", "portproxy", "add", "v4tov4"]
        for command in calls(instance)
    )
