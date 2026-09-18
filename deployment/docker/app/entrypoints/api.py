"""Production entry point for the compiled WEAVE CBT API"""

from __future__ import annotations

import uvicorn

from app.core.settings import settings
from app.main import app 



def main() -> None:
    """Start the WEAVE CBT API PROCESS"""

    uvicorn.run(
        app,
        host = settings.HOST,
        port = settings.PORT,
        log_level = settings.LOG_LEVEL.lower()
    )


if __name__ == "__main__":
    main()