from fastapi import APIRouter, Response, status

from app.core.database import DbSession
from app.core.settings import settings
from app.domains.auth.schemas import (
    LocalActorResponse,
    StaffLoginRequest,
    StaffLoginResponse,
)
from app.domains.auth.service import LocalAuthService


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


REFRESH_COOKIE_NAME = "weave_cbt_refresh"


@router.post(
    "/login",
    response_model=StaffLoginResponse,
    status_code=status.HTTP_200_OK,
)
async def login_staff(
    payload: StaffLoginRequest,
    response: Response,
    db: DbSession,
) -> StaffLoginResponse:

    result = await LocalAuthService.login_staff(
        db,
        payload=payload,
    )

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=result.refresh_token,
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=(
            settings.LOCAL_REFRESH_TOKEN_EXPIRE_HOURS
            * 60
            * 60
        ),
        path="/api/v1/auth",
    )

    return StaffLoginResponse(
        access_token=result.access_token,
        actor=LocalActorResponse.model_validate(
            result.actor
        ),
    )