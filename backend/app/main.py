from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.core.database import check_database_connection, dispose_database_engine
from app.core.redis import close_redis_client
from app.core.settings import settings
from app.domains.auth.router import router as auth_router
from app.domains.node.router import router as node_router
from app.domains.sync.router import router as sync_router
from app.domains.sync.supervisor import sync_supervisor
from app.integrations.weave.client import weave_client


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Start local infrastructure and the non-blocking Cloud sync supervisor."""
    await check_database_connection()
    sync_task = asyncio.create_task(
        sync_supervisor.run(), name="weave-cbt-sync-supervisor"
    )
    try:
        yield
    finally:
        await sync_supervisor.stop()
        sync_task.cancel()
        with suppress(asyncio.CancelledError):
            await sync_task
        await weave_client.close()
        await close_redis_client()
        await dispose_database_engine()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

for router in (node_router, auth_router, sync_router):
    app.include_router(router, prefix=settings.API_V1_PREFIX)
