"""Persistence operations for candidate examination attempts.

The repository persists attempt state, interruptions, stable presentation
allocations, answers, and selections. Timing policy, lifecycle transitions,
scoring, authorization, and transaction boundaries belong to services.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.domains.attempts.models import (
    AttemptAnswer,
    AttemptAnswerSelection,
    AttemptInterruption,
    AttemptOptionAllocation,
    AttemptQuestionAllocation,
    AttemptStatus,
    ExamAttempt,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class AttemptRepository:
    """Provide database operations for attempts and persisted answer state."""

    @staticmethod
    async def add_attempt(db: AsyncSession, attempt: ExamAttempt) -> ExamAttempt:
        """Add an attempt and flush pending changes."""
        db.add(attempt)
        await db.flush()
        return attempt

    @staticmethod
    async def get_attempt_by_id(
        db: AsyncSession,
        attempt_id: UUID,
        *,
        lock: bool = False,
    ) -> ExamAttempt | None:
        """Return an attempt by local ID, optionally locking its row."""
        query = select(ExamAttempt).where(ExamAttempt.id == attempt_id)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_attempt_by_candidate_id(
        db: AsyncSession,
        candidate_id: UUID,
        *,
        lock: bool = False,
    ) -> ExamAttempt | None:
        """Return the candidate's unique examination attempt."""
        query = select(ExamAttempt).where(ExamAttempt.candidate_id == candidate_id)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_attempts(
        db: AsyncSession,
        *,
        statuses: Sequence[AttemptStatus] | None = None,
        heartbeat_before: datetime | None = None,
        limit: int | None = None,
        lock: bool = False,
        skip_locked: bool = False,
    ) -> list[ExamAttempt]:
        """Return attempts matching lifecycle and heartbeat filters."""
        query = select(ExamAttempt)
        if statuses is not None:
            status_values = list(statuses)
            if not status_values:
                return []
            query = query.where(ExamAttempt.status.in_(status_values))
        if heartbeat_before is not None:
            query = query.where(ExamAttempt.last_heartbeat_at < heartbeat_before)

        query = query.order_by(
            ExamAttempt.last_heartbeat_at.asc(),
            ExamAttempt.id.asc(),
        )
        if limit is not None:
            query = query.limit(limit)
        if lock:
            query = query.with_for_update(skip_locked=skip_locked)

        return list((await db.execute(query)).scalars().all())

    @staticmethod
    async def save_attempt(db: AsyncSession, attempt: ExamAttempt) -> ExamAttempt:
        """Attach an attempt and flush pending changes."""
        db.add(attempt)
        await db.flush()
        return attempt

    @staticmethod
    async def add_interruption(
        db: AsyncSession,
        interruption: AttemptInterruption,
    ) -> AttemptInterruption:
        """Add an attempt interruption and flush pending changes."""
        db.add(interruption)
        await db.flush()
        return interruption

    @staticmethod
    async def get_interruption_by_id(
        db: AsyncSession,
        interruption_id: UUID,
        *,
        lock: bool = False,
    ) -> AttemptInterruption | None:
        """Return an interruption by local ID."""
        query = select(AttemptInterruption).where(
            AttemptInterruption.id == interruption_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_open_interruption_for_attempt(
        db: AsyncSession,
        attempt_id: UUID,
        *,
        lock: bool = False,
    ) -> AttemptInterruption | None:
        """Return the latest interruption that has not yet been resumed."""
        query = (
            select(AttemptInterruption)
            .where(
                AttemptInterruption.attempt_id == attempt_id,
                AttemptInterruption.resumed_at.is_(None),
            )
            .order_by(AttemptInterruption.interrupted_at.desc())
            .limit(1)
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_interruptions_for_attempt(
        db: AsyncSession,
        attempt_id: UUID,
    ) -> list[AttemptInterruption]:
        """Return an attempt's interruption history in chronological order."""
        result = await db.execute(
            select(AttemptInterruption)
            .where(AttemptInterruption.attempt_id == attempt_id)
            .order_by(AttemptInterruption.interrupted_at.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def save_interruption(
        db: AsyncSession,
        interruption: AttemptInterruption,
    ) -> AttemptInterruption:
        """Attach an interruption and flush pending changes."""
        db.add(interruption)
        await db.flush()
        return interruption

    @staticmethod
    async def add_question_allocations(
        db: AsyncSession,
        allocations: Sequence[AttemptQuestionAllocation],
    ) -> list[AttemptQuestionAllocation]:
        """Add stable question allocations and return the flushed rows."""
        rows = list(allocations)
        if not rows:
            return []

        db.add_all(rows)
        await db.flush()
        return rows

    @staticmethod
    async def add_question_allocation(
        db: AsyncSession,
        allocation: AttemptQuestionAllocation,
    ) -> AttemptQuestionAllocation:
        """Add one stable question allocation and flush pending changes."""
        db.add(allocation)
        await db.flush()
        return allocation

    @staticmethod
    async def get_question_allocation_by_id(
        db: AsyncSession,
        allocation_id: UUID,
        *,
        lock: bool = False,
    ) -> AttemptQuestionAllocation | None:
        """Return a question allocation by local ID."""
        query = select(AttemptQuestionAllocation).where(
            AttemptQuestionAllocation.id == allocation_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_question_allocation(
        db: AsyncSession,
        attempt_id: UUID,
        exam_question_id: UUID,
    ) -> AttemptQuestionAllocation | None:
        """Return an attempt allocation for one frozen exam question."""
        query = select(AttemptQuestionAllocation).where(
            AttemptQuestionAllocation.attempt_id == attempt_id,
            AttemptQuestionAllocation.exam_question_id == exam_question_id,
        )
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_question_allocations(
        db: AsyncSession,
        attempt_id: UUID,
    ) -> list[AttemptQuestionAllocation]:
        """Return an attempt's questions in persisted presentation order."""
        result = await db.execute(
            select(AttemptQuestionAllocation)
            .where(AttemptQuestionAllocation.attempt_id == attempt_id)
            .order_by(AttemptQuestionAllocation.position.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def add_option_allocations(
        db: AsyncSession,
        allocations: Sequence[AttemptOptionAllocation],
    ) -> list[AttemptOptionAllocation]:
        """Add stable option allocations and return the flushed rows."""
        rows = list(allocations)
        if not rows:
            return []

        db.add_all(rows)
        await db.flush()
        return rows

    @staticmethod
    async def add_option_allocation(
        db: AsyncSession,
        allocation: AttemptOptionAllocation,
    ) -> AttemptOptionAllocation:
        """Add one stable option allocation and flush pending changes."""
        db.add(allocation)
        await db.flush()
        return allocation

    @staticmethod
    async def get_option_allocation_by_id(
        db: AsyncSession,
        allocation_id: UUID,
    ) -> AttemptOptionAllocation | None:
        """Return an option allocation by local ID."""
        query = select(AttemptOptionAllocation).where(
            AttemptOptionAllocation.id == allocation_id,
        )
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_option_allocation(
        db: AsyncSession,
        attempt_question_id: UUID,
        exam_question_option_id: UUID,
    ) -> AttemptOptionAllocation | None:
        """Return one allocated option for an allocated question."""
        query = select(AttemptOptionAllocation).where(
            AttemptOptionAllocation.attempt_question_id == attempt_question_id,
            AttemptOptionAllocation.exam_question_option_id
            == exam_question_option_id,
        )
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_option_allocations(
        db: AsyncSession,
        attempt_question_id: UUID,
    ) -> list[AttemptOptionAllocation]:
        """Return allocated options in persisted presentation order."""
        result = await db.execute(
            select(AttemptOptionAllocation)
            .where(
                AttemptOptionAllocation.attempt_question_id == attempt_question_id
            )
            .order_by(AttemptOptionAllocation.position.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_option_allocations_for_questions(
        db: AsyncSession,
        attempt_question_ids: Sequence[UUID],
    ) -> list[AttemptOptionAllocation]:
        """Return options for multiple allocated questions without N+1 queries."""
        if not attempt_question_ids:
            return []

        result = await db.execute(
            select(AttemptOptionAllocation)
            .where(
                AttemptOptionAllocation.attempt_question_id.in_(
                    attempt_question_ids
                )
            )
            .order_by(
                AttemptOptionAllocation.attempt_question_id.asc(),
                AttemptOptionAllocation.position.asc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def add_answers(
        db: AsyncSession,
        answers: Sequence[AttemptAnswer],
    ) -> list[AttemptAnswer]:
        """Add answer-state rows and return the flushed rows."""
        rows = list(answers)
        if not rows:
            return []

        db.add_all(rows)
        await db.flush()
        return rows

    @staticmethod
    async def add_answer(
        db: AsyncSession,
        answer: AttemptAnswer,
    ) -> AttemptAnswer:
        """Add one answer-state row and flush pending changes."""
        db.add(answer)
        await db.flush()
        return answer

    @staticmethod
    async def get_answer_by_id(
        db: AsyncSession,
        answer_id: UUID,
        *,
        lock: bool = False,
    ) -> AttemptAnswer | None:
        """Return answer state by local ID."""
        query = select(AttemptAnswer).where(AttemptAnswer.id == answer_id)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_answer_for_question(
        db: AsyncSession,
        attempt_question_id: UUID,
        *,
        lock: bool = False,
    ) -> AttemptAnswer | None:
        """Return answer state for one allocated question."""
        query = select(AttemptAnswer).where(
            AttemptAnswer.attempt_question_id == attempt_question_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_answers_for_attempt(
        db: AsyncSession,
        attempt_id: UUID,
    ) -> list[AttemptAnswer]:
        """Return all answer-state rows for an attempt in question order."""
        result = await db.execute(
            select(AttemptAnswer)
            .join(
                AttemptQuestionAllocation,
                AttemptQuestionAllocation.id == AttemptAnswer.attempt_question_id,
            )
            .where(AttemptQuestionAllocation.attempt_id == attempt_id)
            .order_by(AttemptQuestionAllocation.position.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def save_answer(
        db: AsyncSession,
        answer: AttemptAnswer,
    ) -> AttemptAnswer:
        """Attach answer state and flush pending changes."""
        db.add(answer)
        await db.flush()
        return answer

    @staticmethod
    async def add_selections(
        db: AsyncSession,
        selections: Sequence[AttemptAnswerSelection],
    ) -> list[AttemptAnswerSelection]:
        """Add selected options and return the flushed rows."""
        rows = list(selections)
        if not rows:
            return []

        db.add_all(rows)
        await db.flush()
        return rows

    @staticmethod
    async def add_selection(
        db: AsyncSession,
        selection: AttemptAnswerSelection,
    ) -> AttemptAnswerSelection:
        """Add one selected option and flush pending changes."""
        db.add(selection)
        await db.flush()
        return selection

    @staticmethod
    async def get_selection(
        db: AsyncSession,
        answer_id: UUID,
        attempt_option_id: UUID,
    ) -> AttemptAnswerSelection | None:
        """Return one selected option for an answer."""
        query = select(AttemptAnswerSelection).where(
            AttemptAnswerSelection.answer_id == answer_id,
            AttemptAnswerSelection.attempt_option_id == attempt_option_id,
        )
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_selections_for_answer(
        db: AsyncSession,
        answer_id: UUID,
    ) -> list[AttemptAnswerSelection]:
        """Return all selected options for one answer."""
        result = await db.execute(
            select(AttemptAnswerSelection)
            .where(AttemptAnswerSelection.answer_id == answer_id)
            .order_by(AttemptAnswerSelection.created_at.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_selections_for_answers(
        db: AsyncSession,
        answer_ids: Sequence[UUID],
    ) -> list[AttemptAnswerSelection]:
        """Return selections for multiple answers without N+1 queries."""
        if not answer_ids:
            return []

        result = await db.execute(
            select(AttemptAnswerSelection)
            .where(AttemptAnswerSelection.answer_id.in_(answer_ids))
            .order_by(
                AttemptAnswerSelection.answer_id.asc(),
                AttemptAnswerSelection.created_at.asc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def remove_selection(
        db: AsyncSession,
        selection: AttemptAnswerSelection,
    ) -> None:
        """Remove a selected option and flush pending changes."""
        await db.delete(selection)
        await db.flush()
