"""Local read endpoint for the cached effective CBT branding."""

from fastapi import APIRouter, Response

from app.core.database import DbSession
from app.domains.branding.schemas import BrandingResponse
from app.domains.branding.service import branding_service

router = APIRouter(prefix="/branding", tags=["Branding"])


@router.get("", response_model=BrandingResponse)
async def get_branding(
    db: DbSession,
    response: Response,
) -> BrandingResponse:
    """Return local branding even when Weave Cloud is unavailable."""

    response.headers["Cache-Control"] = "no-store"
    return await branding_service.get_effective(db)
