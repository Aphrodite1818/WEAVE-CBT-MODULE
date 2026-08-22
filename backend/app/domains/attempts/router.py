"""HTTP routes for candidate examination attempts."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.database import DbSession
from app.core.exceptions import AcademicAuthorizationError
from app.domains.attempts.schemas import (
    AttemptAnswerMutation,
    AttemptAnswerResponse,
    AttemptOperatorResponse,
    AttemptReasonPayload,
    AttemptResponse,
    AttemptSubmissionResponse,
)
from app.domains.attempts.service import AttemptService, AttemptStateError
from app.domains.auth.dependencies import CurrentLocalActor
from app.domains.auth.student_dependencies import CurrentStudentSession
from app.domains.exams.exceptions import ExamNotFound, ExamStateError


student_router = APIRouter(prefix="/student/attempts", tags=["Student Attempts"])
operator_router = APIRouter(prefix="/attempts", tags=["Attempts"])


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ExamNotFound) or "does not exist" in str(exc).lower():
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, AcademicAuthorizationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, (AttemptStateError, ExamStateError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@student_router.post("/current/start", response_model=AttemptResponse)
async def start_current_attempt(
    db: DbSession,
    context: CurrentStudentSession,
) -> AttemptResponse:
    try:
        return await AttemptService.start_current(db, context=context)
    except (AttemptStateError, ExamNotFound, ExamStateError, ValueError) as exc:
        raise _http_error(exc) from exc


@student_router.get("/current", response_model=AttemptResponse)
async def get_current_attempt(
    db: DbSession,
    context: CurrentStudentSession,
) -> AttemptResponse:
    try:
        return await AttemptService.get_current(db, context=context)
    except (AttemptStateError, ExamNotFound, ExamStateError, ValueError) as exc:
        raise _http_error(exc) from exc


@student_router.put(
    "/current/questions/{attempt_question_id}/answer",
    response_model=AttemptAnswerResponse,
)
async def save_current_answer(
    attempt_question_id: UUID,
    payload: AttemptAnswerMutation,
    db: DbSession,
    context: CurrentStudentSession,
) -> AttemptAnswerResponse:
    try:
        return await AttemptService.mutate_answer(
            db,
            context=context,
            attempt_question_id=attempt_question_id,
            mutation_sequence=payload.mutation_sequence,
            selected_option_ids=payload.selected_option_ids,
            is_flagged=payload.is_flagged,
        )
    except (AttemptStateError, ExamNotFound, ExamStateError, ValueError) as exc:
        raise _http_error(exc) from exc


@student_router.post("/current/submit", response_model=AttemptSubmissionResponse)
async def submit_current_attempt(
    db: DbSession,
    context: CurrentStudentSession,
) -> AttemptSubmissionResponse:
    try:
        return await AttemptService.submit_current(db, context=context)
    except (AttemptStateError, ExamNotFound, ExamStateError, ValueError) as exc:
        raise _http_error(exc) from exc


@operator_router.post("/{attempt_id}/interrupt", response_model=AttemptOperatorResponse)
async def interrupt_attempt(
    attempt_id: UUID,
    payload: AttemptReasonPayload,
    db: DbSession,
    actor: CurrentLocalActor,
) -> AttemptOperatorResponse:
    try:
        return await AttemptService.interrupt_attempt(
            db, actor=actor, attempt_id=attempt_id, reason=payload.reason
        )
    except (
        AcademicAuthorizationError,
        AttemptStateError,
        ExamNotFound,
        ExamStateError,
        ValueError,
    ) as exc:
        raise _http_error(exc) from exc


@operator_router.post("/{attempt_id}/resume", response_model=AttemptOperatorResponse)
async def resume_attempt(
    attempt_id: UUID,
    payload: AttemptReasonPayload,
    db: DbSession,
    actor: CurrentLocalActor,
) -> AttemptOperatorResponse:
    try:
        return await AttemptService.resume_attempt(
            db, actor=actor, attempt_id=attempt_id, reason=payload.reason
        )
    except (
        AcademicAuthorizationError,
        AttemptStateError,
        ExamNotFound,
        ExamStateError,
        ValueError,
    ) as exc:
        raise _http_error(exc) from exc


@operator_router.post("/{attempt_id}/terminate", response_model=AttemptOperatorResponse)
async def terminate_attempt(
    attempt_id: UUID,
    payload: AttemptReasonPayload,
    db: DbSession,
    actor: CurrentLocalActor,
) -> AttemptOperatorResponse:
    try:
        return await AttemptService.terminate_attempt(
            db, actor=actor, attempt_id=attempt_id, reason=payload.reason
        )
    except (
        AcademicAuthorizationError,
        AttemptStateError,
        ExamNotFound,
        ExamStateError,
        ValueError,
    ) as exc:
        raise _http_error(exc) from exc
