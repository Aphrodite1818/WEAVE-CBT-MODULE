"""Read routes for locally calculated CBT results."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.core.database import DbSession
from app.core.exceptions import AcademicAuthorizationError, AcademicScopeError
from app.domains.auth.dependencies import CurrentLocalActor
from app.domains.exams.exceptions import ExamNotFound
from app.domains.results.schemas import ResultListResponse, ResultResponse
from app.domains.results.service import ResultService


router = APIRouter(tags=["Results"])


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ExamNotFound) or "does not exist" in str(exc).lower():
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, AcademicAuthorizationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, AcademicScopeError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/results/{result_id}", response_model=ResultResponse)
async def get_result(
    result_id: UUID,
    db: DbSession,
    actor: CurrentLocalActor,
) -> ResultResponse:
    try:
        result = await ResultService.get_result(db, actor=actor, result_id=result_id)
    except (
        AcademicAuthorizationError,
        AcademicScopeError,
        ExamNotFound,
        ValueError,
    ) as exc:
        raise _http_error(exc) from exc
    return ResultResponse.model_validate(result)


@router.get("/exams/{exam_id}/results", response_model=ResultListResponse)
async def list_exam_results(
    exam_id: UUID,
    db: DbSession,
    actor: CurrentLocalActor,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> ResultListResponse:
    try:
        rows, total = await ResultService.list_exam_results(
            db,
            actor=actor,
            exam_id=exam_id,
            offset=offset,
            limit=limit,
        )
    except (
        AcademicAuthorizationError,
        AcademicScopeError,
        ExamNotFound,
        ValueError,
    ) as exc:
        raise _http_error(exc) from exc
    return ResultListResponse(
        exam_id=exam_id,
        offset=offset,
        limit=limit,
        total=total,
        results=[ResultResponse.model_validate(row) for row in rows],
    )
