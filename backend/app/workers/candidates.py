"""ARQ jobs for examination candidate-roster preparation."""

from __future__ import annotations

import logging
from uuid import UUID

from app.core.database import async_session_factory
from app.domains.candidates.exceptions import CandidateRosterError
from app.domains.candidates.service import CandidateService
from app.domains.exams.models import (
    ROSTER_ERROR_MAX_LENGTH,
    ExamRosterStatus,
    ExamStatus,
)
from app.domains.exams.repository import ExamRepository

logger = logging.getLogger(__name__)


async def _mark_roster_failed(
    *,
    exam_id: UUID,
    error_message: str,
) -> None:
    """Persist a recoverable roster failure in PostgreSQL."""

    async with async_session_factory() as db:
        exam = await ExamRepository.get_exam_by_id(
            db,
            exam_id=exam_id,
            lock=True,
        )

        if exam is None:
            return

        # Do not overwrite a roster another execution already completed.
        if exam.roster_status == ExamRosterStatus.READY:
            return

        # Roster preparation only belongs to sealed examinations.
        if exam.status != ExamStatus.SEALED:
            return

        exam.roster_status = ExamRosterStatus.FAILED
        exam.roster_error = error_message[:ROSTER_ERROR_MAX_LENGTH]

        await ExamRepository.save_exam(db, exam)
        await db.commit()


async def prepare_exam_roster(
    _ctx: dict,
    exam_id: str,
) -> None:
    """Prepare the candidate roster for one sealed examination."""

    try:
        parsed_exam_id = UUID(exam_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "prepare_exam_roster received an invalid exam ID"
        ) from exc

    try:
        async with async_session_factory() as db:
            # Lock before deciding whether duplicate delivery still needs work.
            exam = await ExamRepository.get_exam_by_id(
                db,
                exam_id=parsed_exam_id,
                lock=True,
            )

            if exam is None:
                logger.warning(
                    "Roster job ignored because exam %s no longer exists",
                    parsed_exam_id,
                )
                return

            if exam.roster_status == ExamRosterStatus.READY:
                return

            # A queued job may outlive the exam state that created it.
            if exam.status != ExamStatus.SEALED:
                return

            if exam.roster_status not in {
                ExamRosterStatus.PENDING,
                ExamRosterStatus.FAILED,
            }:
                return

            await CandidateService.prepare_roster(
                db,
                exam_id=parsed_exam_id,
            )

    except CandidateRosterError as exc:
        await _mark_roster_failed(
            exam_id=parsed_exam_id,
            error_message=str(exc),
        )
        logger.warning(
            "Candidate roster preparation failed for exam %s: %s",
            parsed_exam_id,
            exc,
        )
        raise

    except Exception:
        await _mark_roster_failed(
            exam_id=parsed_exam_id,
            error_message="Candidate roster preparation failed unexpectedly",
        )
        logger.exception(
            "Unexpected candidate roster preparation failure for exam %s",
            parsed_exam_id,
        )
        raise
