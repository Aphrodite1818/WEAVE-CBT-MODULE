"""Unified production entry point for the compiled WEAVE CBT runtime."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable


def run_api() -> None:
    """Start the WEAVE CBT FastAPI server."""
    import uvicorn

    from app.core.settings import settings
    from app.main import app

    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
    )


def run_worker() -> None:
    """Start the WEAVE CBT ARQ worker."""
    from arq.worker import run_worker

    from app.workers.worker import WorkerSettings

    run_worker(WorkerSettings)


def get_alembic_config():
    """Resolve the Alembic configuration for source and compiled runtimes."""
    from alembic.config import Config

    configured_path = os.getenv("WEAVE_ALEMBIC_CONFIG")

    if configured_path:
        config_path = Path(configured_path)
    else:
        repo_root = Path(__file__).resolve().parents[4]
        config_path = repo_root / "backend" / "alembic.ini"

    if not config_path.is_file():
        raise RuntimeError(
            f"Alembic configuration was not found at: {config_path}"
        )

    return Config(str(config_path))


def run_migrate() -> None:
    """Upgrade the database schema to the latest Alembic migration."""
    from alembic import command

    command.upgrade(get_alembic_config(), "head")


COMMANDS: dict[str, Callable[[], None]] = {
    "api": run_api,
    "worker": run_worker,
    "migrate": run_migrate,
}


def main() -> None:
    """Dispatch the compiled runtime to the requested process mode."""
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        commands = " | ".join(COMMANDS)
        raise SystemExit(f"Usage: weave-cbt <{commands}>")

    COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    main()
