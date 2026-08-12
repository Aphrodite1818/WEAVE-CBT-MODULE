"""Persistence operations for locally calculated examination results.

The repository reads and writes result models but does not calculate scores,
decide synchronization transitions, call Weave, or commit transactions. Those
responsibilities belong to the results service.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.domains.results.models import ExamResult, ResultSyncStatus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ResultRepository:
    """Provide database operations for locally calculated exam results."""

    @staticmethod
    async def add_result(
        db: AsyncSession,
        exam_result: ExamResult,
    ) -> ExamResult:
        """Add an exam result to the unit of work and flush it."""
        db.add(exam_result)
        await db.flush()
        return exam_result

    @staticmethod
    async def add_results(
        db: AsyncSession,
        exam_results: Sequence[ExamResult],
    ) -> list[ExamResult]:
        """Add exam results and return the flushed rows."""
        rows = list(exam_results)

        if not rows:
            return []

        db.add_all(rows)
        await db.flush()
        return rows

    @staticmethod
    async def get_result_by_id(
        db: AsyncSession,
        result_id: UUID,
        *,
        lock: bool = False,
    ) -> ExamResult | None:
        """Return a result by local ID, optionally locking its row."""
        query = select(ExamResult).where(ExamResult.id == result_id)

        if lock:
            query = query.with_for_update()

        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_result_by_attempt_id(
        db: AsyncSession,
        attempt_id: UUID,
        *,
        lock: bool = False,
    ) -> ExamResult | None:
        """Return the unique result calculated for an attempt."""
        query = select(ExamResult).where(ExamResult.attempt_id == attempt_id)

        if lock:
            query = query.with_for_update()

        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_result_for_candidate_exam(
        db: AsyncSession,
        candidate_id: UUID,
        exam_id: UUID,
        *,
        lock: bool = False,
    ) -> ExamResult | None:
        """Return the unique result for a candidate and exam pair."""
        query = select(ExamResult).where(
            ExamResult.candidate_id == candidate_id,
            ExamResult.exam_id == exam_id,
        )

        if lock:
            query = query.with_for_update()

        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_result_by_idempotency_key(
        db: AsyncSession,
        idempotency_key: str,
        *,
        lock: bool = False,
    ) -> ExamResult | None:
        """Return a result by its unique synchronization idempotency key."""
        query = select(ExamResult).where(
            ExamResult.idempotency_key == idempotency_key,
        )

        if lock:
            query = query.with_for_update()

        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_result_by_weave_id(
        db: AsyncSession,
        weave_result_id: str,
        *,
        lock: bool = False,
    ) -> ExamResult | None:
        """Return a result by its unique Weave result ID."""
        query = select(ExamResult).where(
            ExamResult.weave_result_id == weave_result_id,
        )

        if lock:
            query = query.with_for_update()

        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_results_for_exam(
        db: AsyncSession,
        exam_id: UUID,
        *,
        sync_statuses: Sequence[ResultSyncStatus] | None = None,
    ) -> list[ExamResult]:
        """Return an exam's results, optionally filtered by sync status."""
        query = select(ExamResult).where(ExamResult.exam_id == exam_id)

        if sync_statuses is not None:
            statuses = list(sync_statuses)
            if not statuses:
                return []
            query = query.where(ExamResult.sync_status.in_(statuses))

        result = await db.execute(
            query.order_by(
                ExamResult.calculated_at.asc(),
                ExamResult.candidate_id.asc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_results_for_candidate(
        db: AsyncSession,
        candidate_id: UUID,
    ) -> list[ExamResult]:
        """Return a candidate's results, newest calculation first."""
        result = await db.execute(
            select(ExamResult)
            .where(ExamResult.candidate_id == candidate_id)
            .order_by(ExamResult.calculated_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_results_for_component(
        db: AsyncSession,
        assessment_component_id: UUID,
        *,
        sync_statuses: Sequence[ResultSyncStatus] | None = None,
    ) -> list[ExamResult]:
        """Return results for one assessment component."""
        query = select(ExamResult).where(
            ExamResult.assessment_component_id == assessment_component_id,
        )

        if sync_statuses is not None:
            statuses = list(sync_statuses)
            if not statuses:
                return []
            query = query.where(ExamResult.sync_status.in_(statuses))

        result = await db.execute(
            query.order_by(
                ExamResult.calculated_at.asc(),
                ExamResult.candidate_id.asc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_results_for_sync(
        db: AsyncSession,
        sync_statuses: Sequence[ResultSyncStatus],
        *,
        limit: int | None = None,
        lock: bool = False,
        skip_locked: bool = False,
    ) -> list[ExamResult]:
        """Return sync work in deterministic order, optionally row-locking it."""
        statuses = list(sync_statuses)

        if not statuses:
            return []

        query = (
            select(ExamResult)
            .where(ExamResult.sync_status.in_(statuses))
            .order_by(ExamResult.calculated_at.asc(), ExamResult.id.asc())
        )

        if limit is not None:
            query = query.limit(limit)

        if lock:
            query = query.with_for_update(skip_locked=skip_locked)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def save_result(
        db: AsyncSession,
        exam_result: ExamResult,
    ) -> ExamResult:
        """Attach an exam result and flush pending changes."""
        db.add(exam_result)
        await db.flush()
        return exam_result

    @staticmethod
    async def save_results(
        db: AsyncSession,
        exam_results: Sequence[ExamResult],
    ) -> list[ExamResult]:
        """Attach exam results and return the flushed rows."""
        rows = list(exam_results)

        if not rows:
            return []

        db.add_all(rows)
        await db.flush()
        return rows
