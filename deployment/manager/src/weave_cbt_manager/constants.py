"""Shared constants and filesystem locations for the Windows Manager."""

from __future__ import annotations

import os
import sys
from pathlib import Path, PurePosixPath

APP_NAME = "WEAVE CBT"
MANAGER_EXECUTABLE_NAME = "WeaveCBT-Manager.exe"
WSL_DISTRO_NAME = "WeaveCBT"
COMPOSE_PROJECT_NAME = "weave-cbt"

# These paths live inside the Linux runtime, not on the Windows host. Keep
# them POSIX-native even when the Manager itself is running on Windows.
RUNTIME_DEPLOYMENT_ROOT = PurePosixPath("/opt/weave-cbt")
RUNTIME_COMPOSE_FILE = RUNTIME_DEPLOYMENT_ROOT / "compose.yaml"
RUNTIME_ENV_FILE = RUNTIME_DEPLOYMENT_ROOT / "runtime.env"
RUNTIME_NGINX_FILE = RUNTIME_DEPLOYMENT_ROOT / "nginx" / "nginx.conf"
RUNTIME_BACKUP_ROOT = RUNTIME_DEPLOYMENT_ROOT / "backups"

STARTUP_TASK_NAME = "WEAVE CBT Runtime"
UPDATE_CHECK_TASK_NAME = "WEAVE CBT Update Check"
NETWORK_RECONCILE_TASK_NAME = "WEAVE CBT Network Reconcile"
RUNONCE_VALUE_NAME = "WeaveCBTResume"


def program_data_root() -> Path:
    return Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "WeaveCBT"


def state_file() -> Path:
    return program_data_root() / "manager-state.json"


def log_directory() -> Path:
    return program_data_root() / "logs"


def runtime_install_directory() -> Path:
    return program_data_root() / "runtime"


def application_root() -> Path:
    executable_dir = Path(sys.executable).resolve().parent
    if executable_dir.name.casefold() == "manager":
        return executable_dir.parent
    return Path(__file__).resolve().parents[3]


def rootfs_archive_path() -> Path:
    installed = application_root() / "assets" / "weave-runtime-rootfs.tar"
    if installed.exists():
        return installed
    return application_root() / "runtime" / "distro" / "weave-runtime-rootfs.tar"


def compose_asset_path() -> Path:
    installed = application_root() / "assets" / "compose.yaml"
    if installed.exists():
        return installed
    return application_root().parent / "compose.yaml"


def nginx_asset_path() -> Path:
    installed = application_root() / "assets" / "nginx.conf"
    if installed.exists():
        return installed
    return application_root().parent / "nginx" / "nginx.conf"
