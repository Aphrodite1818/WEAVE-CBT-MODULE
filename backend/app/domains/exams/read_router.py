from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.database import DbSession
from app.core.exceptions import AcademicAuthorizationError, AcademicScopeError
from app.domains.auth.dependencies import CurrentLocalActor
from app.domains.exams.exceptions import ExamAuthorizationError, ExamNotFound
from app.domains.exams.schemas import ExamResponse
from app.domains.exams.service import ExamService


router = APIRouter(
    prefix="/exams",
    tags=["Exams"],
)


@router.get(
    "/{exam_id}",
    response_model=ExamResponse,
)
async def get_exam(
    exam_id: UUID,
    db: DbSession,
    actor: CurrentLocalActor,
) -> ExamResponse:
    try:
        exam = await ExamService.get_exam(
            db,
            actor=actor,
            exam_id=exam_id,
        )
    except ExamNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (AcademicAuthorizationError, ExamAuthorizationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except AcademicScopeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return ExamResponse.model_validate(exam)
