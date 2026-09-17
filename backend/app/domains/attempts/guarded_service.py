"""Lifecycle-aware attempt facade used by HTTP routes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.attempts.models import AttemptStatus
from app.domains.attempts.repository import AttemptRepository
from app.domains.attempts.schemas import AttemptHeartbeatResponse
from app.domains.attempts.service import AttemptService as _AttemptService
from app.domains.attempts.service import AttemptStateError
from app.domains.auth.models import LocalActor
from app.domains.auth.student_service import StudentSessionContext
from app.domains.candidates.repository import CandidateRepository
from app.domains.exams.exceptions import ExamNotFound
from app.domains.exams.execution_repository import ExamExecutionRepository
from app.domains.exams.models import ExamStatus
from app.domains.exams.repository import ExamRepository
from app.workers.producer import arq_producer


_FINALIZING_STATES = {ExamStatus.CLOSING, ExamStatus.CANCELLING}
ATTEMPT_HEARTBEAT_RECOMMENDED_INTERVAL_SECONDS = 20


class AttemptService(_AttemptService):
    """Apply whole-exam lifecycle guards around the core attempt service."""

    @classmethod
    async def _build_finalizing_response(
        cls,
        db: AsyncSession,
        *,
        context: StudentSessionContext,
    ):
        attempt, candidate, exam = await cls._get_current_attempt(
            db,
            context=context,
            lock=True,
        )
        control = await ExamExecutionRepository.get_control(db, exam.id)
        if control is None or control.operation_requested_at is None:
            raise AttemptStateError(
                "Examination finalization metadata is unavailable"
            )

        response = await cls._build_attempt_response(
            db,
            attempt=attempt,
            candidate=candidate,
            exam=exam,
            is_makeup=context.is_makeup,
        )
        response.exam_suspended = True
        response.remaining_seconds = await cls.remaining_seconds(
            db,
            attempt=attempt,
            exam_id=exam.id,
            at=control.operation_requested_at,
        )
        return response

    @classmethod
    async def heartbeat_current(
        cls,
        db: AsyncSession,
        *,
        context: StudentSessionContext,
    ) -> AttemptHeartbeatResponse:
        """Record candidate-device liveness without changing attempt state.

        This path intentionally avoids locks on the shared Exam row so a large
        examination can accept heartbeats concurrently. Missing heartbeats are
        monitoring evidence only; they never auto-interrupt or auto-submit a
        candidate because a transient client/network problem must not change
        academic state without an explicit lifecycle decision.
        """

        attempt, _candidate, exam = await cls._get_current_attempt(
            db,
            context=context,
            lock=False,
        )
        if attempt.status not in {
            AttemptStatus.IN_PROGRESS,
            AttemptStatus.INTERRUPTED,
        }:
            raise AttemptStateError("Ended attempts do not accept heartbeats")

        if not context.is_makeup and exam.status not in {
            ExamStatus.ACTIVE,
            ExamStatus.SUSPENDED,
        }:
            raise AttemptStateError(
                "Examination finalization has started and no longer accepts candidate heartbeats"
            )

        now = datetime.now(UTC)
        attempt.last_heartbeat_at = now
        await AttemptRepository.save_attempt(db, attempt)
        await db.commit()

        remaining = await cls.remaining_seconds(
            db,
            attempt=attempt,
            exam_id=exam.id,
            at=now,
        )
        return AttemptHeartbeatResponse(
            attempt_id=attempt.id,
            status=attempt.status,
            server_time=now,
            last_heartbeat_at=now,
            remaining_seconds=remaining,
            exam_suspended=(exam.status == ExamStatus.SUSPENDED and not context.is_makeup),
            next_heartbeat_after_seconds=ATTEMPT_HEARTBEAT_RECOMMENDED_INTERVAL_SECONDS,
        )

    @classmethod
    async def get_current(
        cls,
        db: AsyncSession,
        *,
        context: StudentSessionContext,
    ):
        if not context.is_makeup:
            _candidate, exam = await cls._get_candidate_and_exam(
                db,
                context=context,
                lock=False,
            )
            if exam.status in _FINALIZING_STATES:
                await db.rollback()
                return await cls._build_finalizing_response(db, context=context)
            await db.rollback()
        return await super().get_current(db, context=context)

    @classmethod
    async def start_current(
        cls,
        db: AsyncSession,
        *,
        context: StudentSessionContext,
    ):
        if not context.is_makeup:
            candidate, exam = await cls._get_candidate_and_exam(
                db,
                context=context,
                lock=False,
            )
            if exam.status in _FINALIZING_STATES:
                existing = await AttemptRepository.get_attempt_by_candidate_id(
                    db,
                    candidate.id,
                )
                await db.rollback()
                if existing is None:
                    raise AttemptStateError(
                        "Examination finalization has started; no new attempts may begin"
                    )
                return await cls._build_finalizing_response(db, context=context)
            await db.rollback()
        return await super().start_current(db, context=context)

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
