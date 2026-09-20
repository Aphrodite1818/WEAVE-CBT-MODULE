"""Windows entry point for the WEAVE CBT Manager."""

from __future__ import annotations

import argparse
import os
import sys

from .app import ManagerController, configure_logging, run_gui


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--first-run", action="store_true")
    parser.add_argument("--startup", action="store_true")
    parser.add_argument("--check-updates", action="store_true")
    parser.add_argument("--uninstall-keep-data", action="store_true")
    parser.add_argument("--purge-data", action="store_true")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Validate packaged imports and Qt startup without changing the host.",
    )
    return parser


def _run_self_test() -> int:
    """Exercise the packaged Python/Qt startup path without touching WSL or Docker."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    # Importing the real window module verifies that Nuitka bundled the Manager
    # UI and its transitive application imports correctly.  We intentionally do
    # not construct MainWindow because that would begin host provisioning.
    from .ui.main_window import MainWindow

    application = QApplication.instance() or QApplication([])
    if MainWindow is None:  # pragma: no cover - defensive import assertion
        raise RuntimeError("WEAVE CBT Manager UI could not be imported.")
    application.processEvents()
    application.quit()
    return 0


def main() -> int:
    args = _parser().parse_args()

    # CI executes this against the actual Nuitka-built executable. Keep it
    # before logging/controller construction so it is completely host-safe.
    if args.self_test:
        return _run_self_test()

    configure_logging()
    controller = ManagerController()
    try:
        if args.startup:
            controller.background_start()
            try:
                controller.check_updates()
            except Exception:
                pass
            return 0
        if args.check_updates:
            controller.check_updates()
            return 0
        if args.uninstall_keep_data:
            controller.uninstall_keep_data()
            return 0
        if args.purge_data:
            controller.purge_all_data()
            return 0
        return run_gui(first_run=args.first_run)
    except Exception as exc:
        print(f"WEAVE CBT Manager failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
