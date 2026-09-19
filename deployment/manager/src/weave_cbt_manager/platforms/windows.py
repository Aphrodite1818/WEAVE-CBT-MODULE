"""Windows platform implementation of the primary Platform Adapter."""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
import winreg
from pathlib import Path

import psutil

from manager.src.weave_cbt_manager.platforms.base import (
    DiskSpace,
    PlatformAdapter,
    SystemMemory,
)


class WindowsPlatform(PlatformAdapter):
    """
    Windows-specific platform adapter.

    This implementation is intentionally read-only during the prerequisite
    phase. It only inspects host state and does not modify the machine.
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

        # Safe fallback for unusual Windows environments.
        return Path("C:/ProgramData/WeaveCBT")

    def is_supported(self) -> bool:
        return platform.system().lower() == "windows"

    def is_admin(self) -> bool:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except (AttributeError, OSError):
            return False

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

    def docker_desktop_install_path(self) -> Path | None:
        """
        Attempt to discover Docker Desktop's installation directory.

        Registry detection is preferred so custom Docker Desktop installation
        locations can be discovered. Conventional locations are used as
        fallbacks.
        """

        registry_locations = (
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            ),
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
            ),
            (
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            ),
        )

        for hive, uninstall_path in registry_locations:
            try:
                with winreg.OpenKey(hive, uninstall_path) as uninstall_key:
                    subkey_count = winreg.QueryInfoKey(uninstall_key)[0]

                    for index in range(subkey_count):
                        try:
                            subkey_name = winreg.EnumKey(uninstall_key, index)

                            with winreg.OpenKey(
                                uninstall_key,
                                subkey_name,
                            ) as application_key:
                                try:
                                    display_name, _ = winreg.QueryValueEx(
                                        application_key,
                                        "DisplayName",
                                    )
                                except FileNotFoundError:
                                    continue

                                if str(display_name).strip().lower() != "docker desktop":
                                    continue

                                try:
                                    install_location, _ = winreg.QueryValueEx(
                                        application_key,
                                        "InstallLocation",
                                    )

                                    install_path = Path(
                                        str(install_location).strip().strip('"')
                                    )

                                    if install_path.exists():
                                        return install_path

                                except FileNotFoundError:
                                    pass

                                try:
                                    display_icon, _ = winreg.QueryValueEx(
                                        application_key,
                                        "DisplayIcon",
                                    )

                                    icon_value = str(display_icon).strip().strip('"')

                                    # DisplayIcon can sometimes look like:
                                    # C:\...\Docker Desktop.exe,0
                                    icon_path = Path(
                                        icon_value.rsplit(",", 1)[0].strip('"')
                                    )

                                    if icon_path.is_file():
                                        return icon_path.parent

                                except FileNotFoundError:
                                    pass

                        except OSError:
                            continue

            except (FileNotFoundError, PermissionError, OSError):
                continue

        # Fallback to conventional Docker Desktop locations.
        fallback_locations = [
            Path(os.getenv("PROGRAMFILES", "C:/Program Files"))
            / "Docker"
            / "Docker",
            Path(os.getenv("LOCALAPPDATA", ""))
            / "Docker",
        ]

        for path in fallback_locations:
            if (path / "Docker Desktop.exe").is_file():
                return path

        return None

    def docker_desktop_installed(self) -> bool:
        return self.docker_desktop_install_path() is not None

    def docker_executable(self) -> Path | None:
        """
        Locate the Docker CLI executable.

        PATH lookup is preferred because it works regardless of where Docker
        was installed, provided Docker was correctly added to PATH.

        If Docker is not present in PATH, the Docker Desktop installation
        directory and conventional Docker locations are checked.
        """

        executable = shutil.which("docker")

        if executable:
            return Path(executable)

        docker_install_path = self.docker_desktop_install_path()

        if docker_install_path:
            candidates = [
                docker_install_path / "resources" / "bin" / "docker.exe",
                docker_install_path / "docker.exe",
            ]

            for candidate in candidates:
                if candidate.is_file():
                    return candidate

        # Final fallback for conventional Docker Desktop installations.
        program_files = Path(
            os.getenv("PROGRAMFILES", "C:/Program Files")
        )

        fallback_candidates = [
            program_files
            / "Docker"
            / "Docker"
            / "resources"
            / "bin"
            / "docker.exe",
        ]

        for candidate in fallback_candidates:
            if candidate.is_file():
                return candidate

        return None

    def docker_engine_running(self) -> bool:
        docker = self.docker_executable()

        if docker is None:
            return False

        try:
            result = subprocess.run(
                [str(docker), "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False

        return result.returncode == 0

    def docker_compose_available(self) -> bool:
        docker = self.docker_executable()

        if docker is None:
            return False

        try:
            result = subprocess.run(
                [str(docker), "compose", "version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False

        return result.returncode == 0