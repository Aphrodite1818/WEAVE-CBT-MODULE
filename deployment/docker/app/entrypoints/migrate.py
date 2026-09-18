"""Production entrypoint for WEAVE CBT database migrations."""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command 
from alembic.config import Config




def get_alembic_config() -> Config:
    """Load the Alembic configuration used by WEAVE CBT"""

    configured_path = os.getenv("WEAVE_ALEMBIC_CONFIG")


    if configured_path:
        configured_path = Path(configured_path)

    else:
        repo_root = Path(__file__).resolve().parents[4]
        config_path = repo_root/ "backend" / "alembic.ini"


    if not config_path.is_file():
        raise RuntimeError(
            f"Alembic configuration was not found at: {config_path}"
        )

    return Config(str(config_path))



def main() -> None:
    """Upgrade the database schema to the latest migration"""

    config = get_alembic_config()
    command.upgrade(config , "head")



if __name__ == "__main__":
    main()
