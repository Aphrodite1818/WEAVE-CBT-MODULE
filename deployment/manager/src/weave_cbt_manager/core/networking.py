"""Expose only the CBT web port on the school's Windows LAN interface."""

from __future__ import annotations

import ipaddress
import json
from pathlib import Path
import subprocess

from ..runtime.base import RuntimeProvider


class WindowsNetworkingService:
    RULE_NAME = "WeaveCBT-Web"

    def __init__(self, runtime: RuntimeProvider, state_path: Path) -> None:
        self.runtime = runtime
        self.state_path = state_path

    @staticmethod
    def _run(arguments: list[str]) -> str:
        result = subprocess.run(
            arguments, capture_output=True, text=True, errors="replace",
            timeout=30, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode:
            raise RuntimeError("School network setup failed: " + (result.stderr or result.stdout).strip())
        return result.stdout

    def _saved_address(self) -> str | None:
        if not self.state_path.exists():
            return None
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        return str(ipaddress.IPv4Address(payload["listen_address"]))

    def configure(self, lan_ip: str | None) -> None:
        if not lan_ip:
            return  # Local use remains possible while the host is offline.
        address = str(ipaddress.IPv4Address(lan_ip))
        result = self.runtime.execute(["ip", "-j", "-4", "route", "get", "1.1.1.1"], timeout=15)
        if not result.succeeded:
            raise RuntimeError("Cannot determine the local server network address: " + result.stderr)
        routes = json.loads(result.stdout)
        target = str(ipaddress.IPv4Address(routes[0]["prefsrc"]))
        previous = self._saved_address()
        # Refuse to replace a forwarding rule we did not create.
        proxies = self._run(["netsh", "interface", "portproxy", "show", "v4tov4"])
        for line in proxies.splitlines():
            fields = line.split()
            if len(fields) == 4 and fields[0] == address and fields[1] == "80" and previous != address:
                raise RuntimeError(f"Windows already forwards {address}:80 for another application.")
        self._run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                   "$ErrorActionPreference='Stop'; Start-Service iphlpsvc"])
        if previous and (previous != address or target == address):
            self._run(["netsh", "interface", "portproxy", "delete", "v4tov4", f"listenaddress={previous}", "listenport=80"])
        if target != address:  # Mirrored networking already uses the host address.
            self._run(["netsh", "interface", "portproxy", "add", "v4tov4",
                       f"listenaddress={address}", "listenport=80", f"connectaddress={target}", "connectport=80"])
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps({"listen_address": address}), encoding="utf-8")
        else:
            self.state_path.unlink(missing_ok=True)
        self._run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                   "$ErrorActionPreference='Stop'; "
                   f"Get-NetFirewallRule -Name '{self.RULE_NAME}' -ErrorAction SilentlyContinue | Remove-NetFirewallRule; "
                   f"New-NetFirewallRule -Name '{self.RULE_NAME}' -DisplayName 'Weave CBT school network' "
                   f"-Direction Inbound -Action Allow -Protocol TCP -LocalPort 80 -LocalAddress '{address}' "
                   "-RemoteAddress LocalSubnet -Profile Private,Domain | Out-Null"])

    def remove(self) -> None:
        previous = self._saved_address()
        if previous:
            self._run(["netsh", "interface", "portproxy", "delete", "v4tov4", f"listenaddress={previous}", "listenport=80"])
            self.state_path.unlink(missing_ok=True)
        self._run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                   "$ErrorActionPreference='Stop'; "
                   f"Get-NetFirewallRule -Name '{self.RULE_NAME}' -ErrorAction SilentlyContinue | Remove-NetFirewallRule"])
