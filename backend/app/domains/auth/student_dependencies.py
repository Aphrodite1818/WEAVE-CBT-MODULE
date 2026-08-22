"""FastAPI dependency for opaque student examination sessions."""

from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status

from app.core.database import DbSession
from app.domains.auth.student_service import (
    StudentAuthenticationError,
    StudentAuthService,
    StudentSessionContext,
)

STUDENT_SESSION_COOKIE = "weave_cbt_student"


async def get_current_student_session(
    db: DbSession,
    raw_token: Annotated[str | None, Cookie(alias=STUDENT_SESSION_COOKIE)] = None,
) -> StudentSessionContext:
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Student authentication required.",
        )
    try:
        return await StudentAuthService.resolve_session(db, raw_token=raw_token)
    except StudentAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


CurrentStudentSession = Annotated[
    StudentSessionContext,
    Depends(get_current_student_session),
]
