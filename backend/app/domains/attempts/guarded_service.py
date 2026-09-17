"""Lifecycle-aware attempt facade used by HTTP routes."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.attempts.models import AttemptStatus
from app.domains.attempts.repository import AttemptRepository
from app.domains.attempts.service import AttemptService as _AttemptService
from app.domains.attempts.service import AttemptStateError
from app.domains.auth.models import LocalActor
from app.domains.auth.student_service import StudentSessionContext
from app.domains.candidates.repository import CandidateRepository
from app.domains.exams.exceptions import ExamNotFound
from app.domains.exams.models import ExamStatus
from app.domains.exams.repository import ExamRepository
from app.workers.producer import arq_producer


class AttemptService(_AttemptService):
    """Apply whole-exam lifecycle guards around the core attempt service."""

    @classmethod
    async def submit_current(
        cls,
        db: AsyncSession,
        *,
        context: StudentSessionContext,
    ):
        _attempt, _candidate, exam = await cls._get_current_attempt(
            db,
            context=context,
            lock=False,
        )
        if not context.is_makeup and exam.status in {
            ExamStatus.CLOSING,
            ExamStatus.CANCELLING,
            ExamStatus.CANCELLED,
        }:
            await db.rollback()
            raise AttemptStateError(
                "Examination is being finalized and cannot be submitted by the candidate"
            )
        await db.rollback()
        result = await super().submit_current(db, context=context)
        if context.exam_id is not None and not context.is_makeup:
            await arq_producer.enqueue("evaluate_exam_completion", str(context.exam_id))
        return result

    @classmethod
    async def interrupt_attempt(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        attempt_id: UUID,
        reason: str,
    ):
        attempt = await AttemptRepository.get_attempt_by_id(db, attempt_id)
        if attempt is None:
            raise AttemptStateError("Attempt does not exist")
        candidate = await CandidateRepository.get_candidate_by_id(db, attempt.candidate_id)
        if candidate is None:
            raise AttemptStateError("Attempt candidate does not exist")
        exam = await ExamRepository.get_exam_by_id(db, exam_id=candidate.exam_id)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        if exam.status != ExamStatus.ACTIVE:
            await db.rollback()
            raise AttemptStateError(
                "Candidate attempts can only be interrupted while the examination is active"
            )
        await db.rollback()
        return await super().interrupt_attempt(
            db,
            actor=actor,
            attempt_id=attempt_id,
            reason=reason,
        )

    @classmethod
    async def terminate_attempt(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        attempt_id: UUID,
        reason: str,
    ):
        attempt = await AttemptRepository.get_attempt_by_id(db, attempt_id)
        if attempt is None:
            raise AttemptStateError("Attempt does not exist")
        candidate = await CandidateRepository.get_candidate_by_id(db, attempt.candidate_id)
        if candidate is None:
            raise AttemptStateError("Attempt candidate does not exist")
        exam = await ExamRepository.get_exam_by_id(db, exam_id=candidate.exam_id)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        if exam.status not in {ExamStatus.ACTIVE, ExamStatus.SUSPENDED}:
            await db.rollback()
            raise AttemptStateError(
                "Candidate attempts cannot be terminated after exam finalization starts"
            )
        await db.rollback()
        response = await super().terminate_attempt(
            db,
            actor=actor,
            attempt_id=attempt_id,
            reason=reason,
        )
        await arq_producer.enqueue("evaluate_exam_completion", str(candidate.exam_id))
        return response
