from fastapi import APIRouter, Cookie, HTTPException, Response, status

from app.core.database import DbSession
from app.core.settings import settings
from app.domains.auth.schemas import (
    LocalActorResponse,
    StaffLoginRequest,
    StaffLoginResponse,
)
from app.domains.auth.service import (
    INVALID_LOCAL_STAFF_SESSION,
    LocalAuthService,
    LocalSessionAuthenticationError,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


REFRESH_COOKIE_NAME = "weave_cbt_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=(settings.LOCAL_REFRESH_TOKEN_EXPIRE_HOURS * 60 * 60),
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=False,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )


def _login_response(result) -> StaffLoginResponse:
    return StaffLoginResponse(
        access_token=result.access_token,
        actor=LocalActorResponse.model_validate(result.actor),
    )


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
    _set_refresh_cookie(response, result.refresh_token)
    return _login_response(result)


@router.post(
    "/refresh",
    response_model=StaffLoginResponse,
    status_code=status.HTTP_200_OK,
)
async def refresh_staff(
    response: Response,
    db: DbSession,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> StaffLoginResponse:
    if not refresh_token:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_LOCAL_STAFF_SESSION,
        )

    try:
        result = await LocalAuthService.refresh_staff(
            db,
            refresh_token=refresh_token,
        )
    except LocalSessionAuthenticationError as exc:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    _set_refresh_cookie(response, result.refresh_token)
    return _login_response(result)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout_staff(
    response: Response,
    db: DbSession,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> None:
    await LocalAuthService.logout_staff(
        db,
        refresh_token=refresh_token,
    )
    _clear_refresh_cookie(response)
