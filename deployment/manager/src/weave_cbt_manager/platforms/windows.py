"""Windows implementation of the host PlatformAdapter."""

from __future__ import annotations

import ctypes
import csv
import ipaddress
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import psutil

from .base import DiskSpace, PlatformAdapter, SystemMemory


class WindowsPlatform(PlatformAdapter):
    """
    Read-only Windows host adapter.

    This class inspects Windows itself. It deliberately does not manage Docker,
    WSL, or containers; those responsibilities belong to the runtime-provider
    layer so they can run in the background without exposing container-runtime
    management to normal WEAVE CBT users.
    """

    @property
    def name(self) -> str:
        return "Windows"

    @property
    def architecture(self) -> str:
        machine = platform.machine().lower()

        architecture_map = {
            "amd64": "x86_64",
            "x86_64": "x86_64",
            "arm64": "arm64",
            "aarch64": "arm64",
        }

        return architecture_map.get(machine, machine)

    @property
    def runtime_root(self) -> Path:
        program_data = os.getenv("PROGRAMDATA")

        if program_data:
            return Path(program_data) / "WeaveCBT"

        return Path("C:/ProgramData/WeaveCBT")

    def is_supported(self) -> bool:
        return platform.system().lower() == "windows" and sys.getwindowsversion().build >= 19041

    def is_admin(self) -> bool:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except (AttributeError, OSError):
            return False

    def account_sid(self) -> str:
        result = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True,
                                text=True, check=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
        return next(csv.reader(result.stdout.splitlines()))[1]

    def memory(self) -> SystemMemory:
        memory = psutil.virtual_memory()

        return SystemMemory(
            total_bytes=memory.total,
            available_bytes=memory.available,
        )

    def disk_space(self) -> DiskSpace:
        root = self.runtime_root.anchor or "C:\\"
        usage = shutil.disk_usage(root)

        return DiskSpace(
            total_bytes=usage.total,
            used_bytes=usage.used,
            free_bytes=usage.free,
        )

    def lan_ip(self) -> str | None:
        """
        Return the preferred physical/LAN IPv4 address for the Windows host.

        Virtual adapters such as WSL, Hyper-V, Docker, VMware, and VirtualBox
        are deprioritized so the Manager is less likely to display an internal
        virtual-network address to students or staff.
        """

        interface_stats = psutil.net_if_stats()
        preferred: list[str] = []
        fallback: list[str] = []

        virtual_interface_markers = (
            "loopback",
            "vethernet",
            "wsl",
            "docker",
            "hyper-v",
            "vmware",
            "virtualbox",
        )

        for interface_name, addresses in psutil.net_if_addrs().items():
            stats = interface_stats.get(interface_name)

            if stats is not None and not stats.isup:
                continue

            interface_is_virtual = any(
                marker in interface_name.lower()
                for marker in virtual_interface_markers
            )

            for address in addresses:
                if address.family != socket.AF_INET:
                    continue

                try:
                    ip = ipaddress.ip_address(address.address)
                except ValueError:
                    continue

                if ip.is_loopback or ip.is_link_local or ip.is_unspecified:
                    continue

                if ip.is_private and not interface_is_virtual:
                    preferred.append(address.address)
                elif not interface_is_virtual:
                    fallback.append(address.address)

        if preferred:
            return preferred[0]

        if fallback:
            return fallback[0]

        return None
