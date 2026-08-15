# ========================== #
# app.main
# ========================== #

from fastapi import FastAPI

from app.core.settings import settings
from app.domains.auth.router import router as auth_router
from app.domains.node.router import router as node_router


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
)

app.include_router(
    node_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    auth_router,
    prefix=settings.API_V1_PREFIX,
)
