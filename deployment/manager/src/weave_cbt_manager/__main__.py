"""Windows entry point for the WEAVE CBT Manager."""

from __future__ import annotations

import argparse
import sys

from .app import ManagerController, configure_logging, run_gui


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--first-run", action="store_true")
    parser.add_argument("--startup", action="store_true")
    parser.add_argument("--check-updates", action="store_true")
    parser.add_argument("--uninstall-keep-data", action="store_true")
    parser.add_argument("--purge-data", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
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
