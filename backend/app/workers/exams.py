"""ARQ jobs for durable examination lifecycle finalization."""

from __future__ import annotations

import logging
from uuid import UUID

from app.core.database import async_session_factory
from app.domains.exams.execution_service import ExamExecutionService


logger = logging.getLogger(__name__)


def _parse_exam_id(value: str, *, job_name: str) -> UUID:
    try:
        return UUID(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{job_name} received an invalid exam ID") from exc


async def finalize_exam_close(_ctx: dict, exam_id: str) -> None:
    parsed_exam_id = _parse_exam_id(exam_id, job_name="finalize_exam_close")
    try:
        async with async_session_factory() as db:
            await ExamExecutionService.finalize_close(db, exam_id=parsed_exam_id)
    except Exception as exc:
        logger.exception("Exam close finalization failed for %s", parsed_exam_id)
        async with async_session_factory() as db:
            await ExamExecutionService.mark_operation_error(
                db,
                exam_id=parsed_exam_id,
                message=f"{type(exc).__name__}: {exc}",
            )
        raise


async def finalize_exam_cancellation(_ctx: dict, exam_id: str) -> None:
    parsed_exam_id = _parse_exam_id(
        exam_id, job_name="finalize_exam_cancellation"
    )
    try:
        async with async_session_factory() as db:
            await ExamExecutionService.finalize_cancellation(
                db,
                exam_id=parsed_exam_id,
            )
    except Exception as exc:
        logger.exception("Exam cancellation finalization failed for %s", parsed_exam_id)
        async with async_session_factory() as db:
            await ExamExecutionService.mark_operation_error(
                db,
                exam_id=parsed_exam_id,
                message=f"{type(exc).__name__}: {exc}",
            )
        raise


async def evaluate_exam_completion(ctx: dict, exam_id: str) -> None:
    parsed_exam_id = _parse_exam_id(exam_id, job_name="evaluate_exam_completion")
    async with async_session_factory() as db:
        requested = await ExamExecutionService.evaluate_automatic_close(
            db,
            exam_id=parsed_exam_id,
        )
    if not requested:
        return

    # Complete the automatic close in the same worker invocation. PostgreSQL
    # state makes this safe to retry if this process stops between the two steps.
    await finalize_exam_close(ctx, exam_id)
