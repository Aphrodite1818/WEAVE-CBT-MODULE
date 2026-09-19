"""Windows host integration for the WEAVE CBT Manager."""

from __future__ import annotations

import ctypes
import os
import socket
import webbrowser
from pathlib import Path

from weave_cbt_manager.constants import (
    BACKUP_DIR_NAME,
    COMPOSE_FILE_NAME,
    DEPLOYMENT_DIR_NAME,
    ENV_FILE_NAME,
    LOG_DIR_NAME,
    RUNTIME_DIR_NAME,
    STATE_FILE_NAME,
)
from weave_cbt_manager.platforms.base import PlatformAdapter, RuntimePaths


class WindowsPlatform(PlatformAdapter):
    """Windows implementation used by the first WEAVE CBT Manager release."""

    def __init__(self) -> None:
        program_data = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
        root = program_data / RUNTIME_DIR_NAME
        deployment = root / DEPLOYMENT_DIR_NAME

        self._paths = RuntimePaths(
            root=root,
            deployment=deployment,
            logs=root / LOG_DIR_NAME,
            backups=root / BACKUP_DIR_NAME,
            state_file=root / STATE_FILE_NAME,
            env_file=deployment / ENV_FILE_NAME,
            compose_file=deployment / COMPOSE_FILE_NAME,
            nginx_dir=deployment / "nginx",
        )

    @property
    def paths(self) -> RuntimePaths:
        return self._paths

    def is_supported(self) -> bool:
        return os.name == "nt"

    def is_admin(self) -> bool:
        if os.name != "nt":
            return False
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except (AttributeError, OSError):
            return False

    def ensure_runtime_directories(self) -> None:
        for path in (
            self.paths.root,
            self.paths.deployment,
            self.paths.logs,
            self.paths.backups,
            self.paths.nginx_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def open_url(self, url: str) -> None:
        webbrowser.open(url)

    def lan_address(self) -> str | None:
        """Return the preferred LAN address without requiring an HTTP request."""

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # UDP connect selects the preferred outbound interface without sending data.
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
        except OSError:
            try:
                return socket.gethostbyname(socket.gethostname())
            except OSError:
                return None
        finally:
            sock.close()
