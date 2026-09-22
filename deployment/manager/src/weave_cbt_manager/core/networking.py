"""Expose only the CBT web port on the school's Windows LAN interface."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import json
import logging
from pathlib import Path
import subprocess

from ..runtime.base import RuntimeProvider


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NetworkAccessStatus:
    """Describe whether Windows currently permits classroom LAN access."""

    lan_ip: str | None
    network_name: str | None
    interface_alias: str | None
    interface_index: int | None
    category: str

    @property
    def connected(self) -> bool:
        return self.lan_ip is not None

    @property
    def trusted(self) -> bool:
        return self.category.casefold() in {
            "private",
            "domain",
            "domainauthenticated",
        }

    @property
    def requires_approval(self) -> bool:
        return self.category.casefold() == "public"


class WindowsNetworkingService:
    RULE_NAME = "WeaveCBT-Web"
    WEB_PORT = "80"

    def __init__(self, runtime: RuntimeProvider, state_path: Path) -> None:
        self.runtime = runtime
        self.state_path = state_path

    @staticmethod
    def _run(arguments: list[str]) -> str:
        try:
            result = subprocess.run(
                arguments,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=30,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("School network setup timed out.") from exc
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(
                "School network setup failed"
                + (f": {detail}" if detail else ".")
            )
        return result.stdout

    def _saved_state(self) -> dict[str, str] | None:
        if not self.state_path.exists():
            return None
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            listen = str(ipaddress.IPv4Address(payload["listen_address"]))
            raw_connect = payload.get("connect_address")
            connect = (
                str(ipaddress.IPv4Address(raw_connect))
                if raw_connect is not None
                else ""
            )
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            logger.warning(
                "Ignoring invalid WEAVE CBT network ownership state at %s.",
                self.state_path,
            )
            return None
        return {"listen_address": listen, "connect_address": connect}

    def _save_state(self, listen_address: str, connect_address: str) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(
                {
                    "listen_address": listen_address,
                    "connect_address": connect_address,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _parse_proxies(output: str) -> dict[tuple[str, str], tuple[str, str]]:
        proxies: dict[tuple[str, str], tuple[str, str]] = {}
        for line in output.splitlines():
            fields = line.split()
            if len(fields) != 4:
                continue
            listen_address, listen_port, connect_address, connect_port = fields
            try:
                listen_address = str(ipaddress.IPv4Address(listen_address))
                connect_address = str(ipaddress.IPv4Address(connect_address))
                int(listen_port)
                int(connect_port)
            except (ValueError, TypeError):
                continue
            proxies[(listen_address, listen_port)] = (
                connect_address,
                connect_port,
            )
        return proxies

    def _runtime_ipv4(self) -> str:
        """Return the WSL runtime IPv4 without requiring internet connectivity."""

        result = self.runtime.execute(
            ["ip", "-j", "-4", "addr", "show", "scope", "global"],
            timeout=15,
        )
        if not result.succeeded:
            raise RuntimeError(
                "Cannot determine the local server network address: "
                + (result.stderr or result.stdout)
            )
        try:
            interfaces = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            raise RuntimeError(
                "The local server returned invalid network information."
            ) from exc
        if not isinstance(interfaces, list):
            raise RuntimeError("The local server returned invalid network information.")

        ignored_markers = ("lo", "docker", "br-", "veth")
        candidates: list[ipaddress.IPv4Address] = []
        for interface in interfaces:
            if not isinstance(interface, dict):
                continue
            name = str(interface.get("ifname") or "").lower()
            if any(name == marker or name.startswith(marker) for marker in ignored_markers):
                continue
            address_info = interface.get("addr_info")
            if not isinstance(address_info, list):
                continue
            for entry in address_info:
                if not isinstance(entry, dict) or entry.get("family") != "inet":
                    continue
                raw = entry.get("local")
                try:
                    address = ipaddress.IPv4Address(str(raw))
                except ipaddress.AddressValueError:
                    continue
                if address.is_loopback or address.is_link_local or address.is_unspecified:
                    continue
                candidates.append(address)

        if not candidates:
            raise RuntimeError(
                "The local server has no usable WSL network address yet. "
                "Retry after Windows finishes preparing the network."
            )
        return str(candidates[0])

    def _show_proxies(self) -> dict[tuple[str, str], tuple[str, str]]:
        output = self._run(
            ["netsh", "interface", "portproxy", "show", "v4tov4"]
        )
        return self._parse_proxies(output)

    def _start_portproxy_service(self) -> None:
        self._run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "$ErrorActionPreference='Stop'; Start-Service iphlpsvc",
            ]
        )

    def _remove_firewall(self) -> None:
        self._run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "$ErrorActionPreference='Stop'; "
                f"Get-NetFirewallRule -Name '{self.RULE_NAME}' "
                "-ErrorAction SilentlyContinue | Remove-NetFirewallRule",
            ]
        )

    def _install_firewall(self, address: str) -> None:
        self._run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "$ErrorActionPreference='Stop'; "
                f"Get-NetFirewallRule -Name '{self.RULE_NAME}' "
                "-ErrorAction SilentlyContinue | Remove-NetFirewallRule; "
                f"New-NetFirewallRule -Name '{self.RULE_NAME}' "
                "-DisplayName 'Weave CBT school network' "
                "-Direction Inbound -Action Allow -Protocol TCP "
                f"-LocalPort {self.WEB_PORT} -LocalAddress '{address}' "
                "-RemoteAddress LocalSubnet -Profile Private,Domain | Out-Null",
            ]
        )

    def _delete_proxy(self, address: str) -> None:
        self._run(
            [
                "netsh",
                "interface",
                "portproxy",
                "delete",
                "v4tov4",
                f"listenaddress={address}",
                f"listenport={self.WEB_PORT}",
            ]
        )

    def inspect_access(self, lan_ip: str | None) -> NetworkAccessStatus:
        """Read the Windows profile that owns the current LAN address.

        Profile inspection is deliberately read-only. A Public network remains
        Public until an administrator explicitly approves it for classroom use.
        """

        if not lan_ip:
            return NetworkAccessStatus(None, None, None, None, "Disconnected")

        address = str(ipaddress.IPv4Address(lan_ip))
        command = (
            "$ErrorActionPreference='Stop'; "
            f"$ip=Get-NetIPAddress -AddressFamily IPv4 -IPAddress '{address}' "
            "-ErrorAction Stop | Select-Object -First 1; "
            "if ($null -eq $ip) { throw 'No Windows adapter owns the WEAVE LAN address.' }; "
            "$profile=Get-NetConnectionProfile -InterfaceIndex $ip.InterfaceIndex "
            "-ErrorAction Stop; "
            "[pscustomobject]@{"
            "network_name=[string]$profile.Name;"
            "interface_alias=[string]$profile.InterfaceAlias;"
            "interface_index=[int]$profile.InterfaceIndex;"
            "category=[string]$profile.NetworkCategory"
            "} | ConvertTo-Json -Compress"
        )
        try:
            output = self._run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    command,
                ]
            )
            payload = json.loads(output.lstrip("\ufeff").strip())
            interface_index = int(payload["interface_index"])
            if interface_index <= 0:
                raise ValueError("invalid interface index")
            return NetworkAccessStatus(
                lan_ip=address,
                network_name=str(payload.get("network_name") or "") or None,
                interface_alias=str(payload.get("interface_alias") or "") or None,
                interface_index=interface_index,
                category=str(payload.get("category") or "Unknown"),
            )
        except (RuntimeError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            logger.exception(
                "Could not determine the Windows network profile for %s.", address
            )
            return NetworkAccessStatus(address, None, None, None, "Unknown")

    def approve_current_network(
        self, status: NetworkAccessStatus
    ) -> NetworkAccessStatus:
        """Mark one explicitly approved Public Windows network as Private."""

        if not status.connected or status.interface_index is None:
            raise RuntimeError("No connected school network is available to approve.")
        if status.trusted:
            return status
        if not status.requires_approval:
            raise RuntimeError(
                "Windows could not identify the current network profile. "
                "Reconnect to the school network and try again."
            )

        self._run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "$ErrorActionPreference='Stop'; "
                f"Set-NetConnectionProfile -InterfaceIndex {status.interface_index} "
                "-NetworkCategory Private",
            ]
        )
        updated = self.inspect_access(status.lan_ip)
        if not updated.trusted:
            raise RuntimeError(
                "Windows did not mark the selected school network as Private. "
                "Reconnect to the network and try again."
            )
        return updated

    def configure(self, lan_ip: str | None) -> None:
        saved = self._saved_state()
        if not lan_ip:
            # A stale forwarding rule should not remain exposed after the host
            # leaves its school LAN. Localhost access remains unaffected.
            if saved:
                try:
                    self._delete_proxy(saved["listen_address"])
                except RuntimeError:
                    logger.exception("Could not remove stale WEAVE CBT port forwarding.")
                self.state_path.unlink(missing_ok=True)
            self._remove_firewall()
            return

        address = str(ipaddress.IPv4Address(lan_ip))
        target = self._runtime_ipv4()
        proxies = self._show_proxies()
        desired_key = (address, self.WEB_PORT)
        desired_existing = proxies.get(desired_key)
        wildcard_existing = proxies.get(("0.0.0.0", self.WEB_PORT))
        previous_address = saved["listen_address"] if saved else None
        previous_target = saved["connect_address"] if saved else ""

        if wildcard_existing is not None:
            raise RuntimeError(
                "Windows already forwards port 80 for another application. "
                "Remove that forwarding rule before enabling the WEAVE school network."
            )

        # Never replace a rule that WEAVE cannot prove it owns. Older manager
        # versions stored only listen_address, so an empty saved target remains
        # a valid legacy ownership marker.
        if desired_existing is not None:
            if previous_address != address:
                raise RuntimeError(
                    f"Windows already forwards {address}:80 for another application."
                )
            if previous_target and desired_existing != (previous_target, self.WEB_PORT):
                raise RuntimeError(
                    "The WEAVE network forwarding rule was changed by another "
                    "application. Remove the conflicting rule before continuing."
                )

        if previous_address and previous_address != address:
            old_key = (previous_address, self.WEB_PORT)
            old_existing = proxies.get(old_key)
            if old_existing is not None:
                if previous_target and old_existing != (previous_target, self.WEB_PORT):
                    raise RuntimeError(
                        "The previous WEAVE network forwarding rule was changed "
                        "by another application; it was left untouched."
                    )

        self._start_portproxy_service()

        if previous_address and previous_address != address:
            if (previous_address, self.WEB_PORT) in proxies:
                self._delete_proxy(previous_address)

        if target == address:
            # Mirrored WSL networking already reaches the host interface. Any
            # older WEAVE-owned NAT forwarding rule is now unnecessary.
            if desired_existing is not None:
                self._delete_proxy(address)
            self.state_path.unlink(missing_ok=True)
        else:
            desired = (target, self.WEB_PORT)
            if desired_existing != desired:
                # WSL NAT addresses can change after a WSL/Windows restart.
                # Delete WEAVE's old rule before adding the new target so netsh
                # never rejects a duplicate listen address/port.
                if desired_existing is not None:
                    self._delete_proxy(address)
                self._run(
                    [
                        "netsh",
                        "interface",
                        "portproxy",
                        "add",
                        "v4tov4",
                        f"listenaddress={address}",
                        f"listenport={self.WEB_PORT}",
                        f"connectaddress={target}",
                        f"connectport={self.WEB_PORT}",
                    ]
                )
            self._save_state(address, target)

        self._install_firewall(address)

    def remove(self) -> None:
        saved = self._saved_state()
        if saved:
            try:
                proxies = self._show_proxies()
                key = (saved["listen_address"], self.WEB_PORT)
                existing = proxies.get(key)
                saved_target = saved["connect_address"]
                if existing is not None:
                    if saved_target and existing != (saved_target, self.WEB_PORT):
                        logger.warning(
                            "Leaving externally modified portproxy rule %s untouched.",
                            saved["listen_address"],
                        )
                    else:
                        self._delete_proxy(saved["listen_address"])
            finally:
                self.state_path.unlink(missing_ok=True)
        self._remove_firewall()
