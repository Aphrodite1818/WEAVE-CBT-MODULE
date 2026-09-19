"""Executable entry point for the WEAVE CBT Manager desktop application."""

from __future__ import annotations

from weave_cbt_manager.app import run


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
