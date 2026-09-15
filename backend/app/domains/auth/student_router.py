"""Student CBT authentication routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Response, status

from app.core.database import DbSession
from app.domains.auth.student_dependencies import STUDENT_SESSION_COOKIE
from app.domains.auth.student_schemas import StudentLoginRequest, StudentLoginResponse
from app.domains.auth.student_service import (
    INVALID_STUDENT_LOGIN,
    StudentAuthenticationError,
    StudentAuthService,
)


router = APIRouter(prefix="/student/auth", tags=["Student Authentication"])


@router.post("/login", response_model=StudentLoginResponse)
async def login_student(
    payload: StudentLoginRequest,
    response: Response,
    db: DbSession,
) -> StudentLoginResponse:
    try:
        result = await StudentAuthService.login(
            db,
            admission_number=payload.admission_number,
            password=payload.password,
        )
    except StudentAuthenticationError as exc:
        detail = str(exc)
        code = (
            status.HTTP_401_UNAUTHORIZED
            if detail == INVALID_STUDENT_LOGIN
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=code, detail=detail) from exc

    response.set_cookie(
        key=STUDENT_SESSION_COOKIE,
        value=result.raw_token,
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=8 * 60 * 60,
        path="/api/v1/student",
    )
    return result.response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_student(
    response: Response,
    db: DbSession,
    raw_token: Annotated[str | None, Cookie(alias=STUDENT_SESSION_COOKIE)] = None,
) -> None:
    if raw_token:
        await StudentAuthService.logout(db, raw_token=raw_token)
    response.delete_cookie(
        key=STUDENT_SESSION_COOKIE,
        path="/api/v1/student",
        samesite="strict",
    )
