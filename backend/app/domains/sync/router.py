"""Local administrator endpoints for synchronization recovery and health."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.core.database import DbSession
from app.domains.auth.dependencies import CurrentLocalAdmin
from app.domains.sync.schemas import SyncReconcileResponse, SyncStatusResponse
from app.domains.sync.service import sync_service

router = APIRouter(prefix="/sync", tags=["Synchronization"])


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status(
    db: DbSession,
    _admin: CurrentLocalAdmin,
    response: Response,
) -> SyncStatusResponse:
    response.headers["Cache-Control"] = "no-store"
    return await sync_service.get_status(db)


@router.post("/reconcile", response_model=SyncReconcileResponse)
async def reconcile_now(
    db: DbSession,
    _admin: CurrentLocalAdmin,
    response: Response,
) -> SyncReconcileResponse:
    """Manually recover bootstrap/deltas using the same path as live sync."""
    response.headers["Cache-Control"] = "no-store"
    return await sync_service.reconcile(db)
