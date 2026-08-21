from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.database import DbSession
from app.core.exceptions import AcademicAuthorizationError, AcademicScopeError
from app.domains.auth.dependencies import CurrentLocalActor
from app.domains.exams.exceptions import (
    ExamAuthorizationError,
    ExamNotFound,
    ExamStateError,
)
from app.domains.exams.schemas import (
    ExamCreate,
    ExamQuestionConfiguration,
    ExamResponse,
    ExamUpdate,
    ManualQuestionAdd,
    ManualQuestionRemove,
    ManualQuestionReorder,
)
from app.domains.exams.service import ExamService


router = APIRouter(
    prefix="/exams",
    tags=["Exams"],
)


def _domain_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ExamNotFound):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    if isinstance(exc, (AcademicAuthorizationError, ExamAuthorizationError)):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )

    if isinstance(exc, (AcademicScopeError, ExamStateError)):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    detail = str(exc)
    lowered = detail.lower()

    if "does not exist" in lowered:
        code = status.HTTP_404_NOT_FOUND
    elif any(
        marker in lowered
        for marker in (
            "cannot",
            "inactive",
            "already",
            "conflict",
            "not enough",
            "exceed",
        )
    ):
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_400_BAD_REQUEST

    return HTTPException(status_code=code, detail=detail)


@router.post(
    "",
    response_model=ExamResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_exam(
    payload: ExamCreate,
    db: DbSession,
    actor: CurrentLocalActor,
) -> ExamResponse:
    try:
        exam = await ExamService.create_exam(
            db,
            actor=actor,
            payload=payload,
        )
    except (
        AcademicAuthorizationError,
        AcademicScopeError,
        ExamAuthorizationError,
        ExamNotFound,
        ExamStateError,
        ValueError,
    ) as exc:
        raise _domain_http_error(exc) from exc

    return ExamResponse.model_validate(exam)


@router.patch(
    "/{exam_id}",
    response_model=ExamResponse,
)
async def update_exam(
    exam_id: UUID,
    payload: ExamUpdate,
    db: DbSession,
    actor: CurrentLocalActor,
) -> ExamResponse:
    try:
        exam = await ExamService.update_exam(
            db,
            actor=actor,
            payload=payload,
            exam_id=exam_id,
        )
    except (
        AcademicAuthorizationError,
        AcademicScopeError,
        ExamAuthorizationError,
        ExamNotFound,
        ExamStateError,
        ValueError,
    ) as exc:
        raise _domain_http_error(exc) from exc

    return ExamResponse.model_validate(exam)


@router.put(
    "/{exam_id}/questions/configuration",
    response_model=ExamResponse,
)
async def configure_exam_questions(
    exam_id: UUID,
    payload: ExamQuestionConfiguration,
    db: DbSession,
    actor: CurrentLocalActor,
) -> ExamResponse:
    try:
        exam = await ExamService.configure_questions(
            db,
            actor=actor,
            exam_id=exam_id,
            payload=payload,
        )
    except (
        AcademicAuthorizationError,
        AcademicScopeError,
        ExamAuthorizationError,
        ExamNotFound,
        ExamStateError,
        ValueError,
    ) as exc:
        raise _domain_http_error(exc) from exc

    return ExamResponse.model_validate(exam)


@router.post(
    "/{exam_id}/manual-questions",
    response_model=ExamResponse,
)
async def add_manual_questions(
    exam_id: UUID,
    payload: ManualQuestionAdd,
    db: DbSession,
    actor: CurrentLocalActor,
) -> ExamResponse:
    try:
        exam = await ExamService.add_manual_questions(
            db,
            actor=actor,
            exam_id=exam_id,
            payload=payload,
        )
    except (
        AcademicAuthorizationError,
        AcademicScopeError,
        ExamAuthorizationError,
        ExamNotFound,
        ExamStateError,
        ValueError,
    ) as exc:
        raise _domain_http_error(exc) from exc

    return ExamResponse.model_validate(exam)


@router.post(
    "/{exam_id}/manual-questions/remove",
    response_model=ExamResponse,
)
async def remove_manual_question(
    exam_id: UUID,
    payload: ManualQuestionRemove,
    db: DbSession,
    actor: CurrentLocalActor,
) -> ExamResponse:
    try:
        exam = await ExamService.remove_manual_question(
            db,
            actor=actor,
            exam_id=exam_id,
            payload=payload,
        )
    except (
        AcademicAuthorizationError,
        AcademicScopeError,
        ExamAuthorizationError,
        ExamNotFound,
        ExamStateError,
        ValueError,
    ) as exc:
        raise _domain_http_error(exc) from exc

    return ExamResponse.model_validate(exam)


@router.post(
    "/{exam_id}/manual-questions/reorder",
    response_model=ExamResponse,
)
async def reorder_manual_questions(
    exam_id: UUID,
    payload: ManualQuestionReorder,
    db: DbSession,
    actor: CurrentLocalActor,
) -> ExamResponse:
    try:
        exam = await ExamService.reorder_manual_questions(
            db,
            actor=actor,
            exam_id=exam_id,
            payload=payload,
        )
    except (
        AcademicAuthorizationError,
        AcademicScopeError,
        ExamAuthorizationError,
        ExamNotFound,
        ExamStateError,
        ValueError,
    ) as exc:
        raise _domain_http_error(exc) from exc

    return ExamResponse.model_validate(exam)
