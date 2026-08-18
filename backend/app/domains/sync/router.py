"""Local administrator endpoints for synchronization recovery and health."""

from __future__ import annotations

from fastapi import APIRouter, Query, Response

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
    force_full: bool = Query(
        default=False,
        description=(
            "Reinstall the complete authoritative Weave academic snapshot instead of "
            "only applying durable changes after the local cursor."
        ),
    ),
) -> SyncReconcileResponse:
    """Manually synchronize the local CBT projection from authoritative Weave APIs.

    The default path is an efficient cursor reconciliation: fetch and apply every
    durable Weave change after the local committed cursor. ``force_full=true`` is
    the recovery path for intentionally reinstalling the current complete academic
    snapshot when an operator needs a full resync.
    """

    response.headers["Cache-Control"] = "no-store"
    if force_full:
        return await sync_service.bootstrap(db, force=True)
    return await sync_service.reconcile(db)
