"""Nuitka entry point for the packaged WEAVE CBT Manager.

This file deliberately lives outside the package so Nuitka compiles a normal
script that imports the installed ``weave_cbt_manager`` package by its absolute
name.  It also provides a last-resort startup error path for failures that occur
before the Manager's normal logging has been configured.
"""

from __future__ import annotations

import ctypes
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path


def _bootstrap_log_path() -> Path:
    program_data = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
    return program_data / "WeaveCBT" / "logs" / "bootstrap-error.log"


def _record_startup_failure(exc: BaseException) -> Path | None:
    try:
        path = _bootstrap_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n[{timestamp}] WEAVE CBT Manager startup failure\n")
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=handle)
        return path
    except Exception:
        return None


def _show_startup_failure(exc: BaseException, log_path: Path | None) -> None:
    message = (
        "WEAVE CBT Manager could not start.\n\n"
        f"{type(exc).__name__}: {exc}\n\n"
    )
    if log_path is not None:
        message += f"Diagnostic details were written to:\n{log_path}"
    else:
        message += "The Manager could not write its startup diagnostic log."

    try:
        ctypes.windll.user32.MessageBoxW(
            None,
            message,
            "WEAVE CBT Manager",
            0x00000010,
        )
    except Exception:
        pass


def main() -> int:
    try:
        from weave_cbt_manager.__main__ import main as manager_main

        return int(manager_main())
    except BaseException as exc:
        log_path = _record_startup_failure(exc)
        _show_startup_failure(exc, log_path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
