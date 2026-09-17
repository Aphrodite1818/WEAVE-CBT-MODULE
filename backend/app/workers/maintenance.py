"""Recovery sweeps for durable CBT background work.

PostgreSQL is the source of truth for whether background work is still needed.
Redis/ARQ is only the delivery mechanism. These sweeps rebuild missing queue
work after process crashes, Redis loss, failed enqueue attempts, or worker
termination.

This module intentionally does not register ARQ jobs. Registration belongs to
the final worker settings module.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from arq.connections import ArqRedis
from sqlalchemy import and_, or_, select

from app.core.database import async_session_factory
from app.domains.exams.models import Exam, ExamRosterStatus, ExamStatus
from app.domains.results.models import (
    RESULT_SYNC_ERROR_MAX_LENGTH,
    ExamResult,
    ResultSyncStatus,
)

logger = logging.getLogger(__name__)

MAINTENANCE_SCAN_LIMIT = 500
ROSTER_FAILED_RETRY_AFTER = timedelta(minutes=5)
RESULT_FAILED_RETRY_AFTER = timedelta(minutes=5)
RESULT_SYNCING_STALE_AFTER = timedelta(minutes=10)

_STALE_RESULT_ERROR = (
    "Previous result synchronization worker stopped before completion; "
    "the durable batch has been scheduled for recovery."
)


def _arq_redis_from_context(ctx: dict[str, Any]) -> ArqRedis:
    """Return the worker's process-local ARQ Redis connection."""

    redis = ctx.get("redis")
    if redis is None:
        raise RuntimeError("ARQ maintenance context is missing the Redis connection")
    return cast(ArqRedis, redis)


async def _recover_stale_result_batches(
    *,
    now: datetime,
) -> set[UUID]:
    """Move abandoned SYNCING rows back to retryable FAILED state.

    The existing sync_batch_id is deliberately preserved. A worker may have
    died after Weave accepted the request but before local acknowledgement was
    committed, so recovery must replay the exact same durable batch.
    """

    stale_before = now - RESULT_SYNCING_STALE_AFTER

    async with async_session_factory() as db:
        query = (
            select(ExamResult)
            .where(
                ExamResult.sync_status == ResultSyncStatus.SYNCING,
                ExamResult.last_sync_attempt_at.is_not(None),
                ExamResult.last_sync_attempt_at <= stale_before,
            )
            .order_by(
                ExamResult.last_sync_attempt_at.asc(),
                ExamResult.id.asc(),
            )
            .limit(MAINTENANCE_SCAN_LIMIT)
            .with_for_update(of=ExamResult, skip_locked=True)
        )

        rows = list((await db.execute(query)).scalars().all())
        if not rows:
            await db.rollback()
            return set()

        exam_ids: set[UUID] = set()
        error_message = _STALE_RESULT_ERROR[:RESULT_SYNC_ERROR_MAX_LENGTH]

        for row in rows:
            row.sync_status = ResultSyncStatus.FAILED
            row.synced_at = None
            row.sync_error = error_message

            # A SYNCING row should always have a batch id because the database
            # constraint enforces it. Guard against corrupted/legacy data by
            # only scheduling automatic replay when exact batch identity exists.
            if row.sync_batch_id is not None:
                exam_ids.add(row.exam_id)

        await db.commit()

        logger.warning(
            "Recovered %s stale result synchronization row(s) across %s exam(s)",
            len(rows),
            len(exam_ids),
        )

        return exam_ids


async def _list_roster_exam_ids_needing_recovery(
    *,
    now: datetime,
) -> list[UUID]:
    """Find sealed exams whose candidate-roster job is missing or retryable."""

    failed_before = now - ROSTER_FAILED_RETRY_AFTER

    async with async_session_factory() as db:
        query = (
            select(Exam.id)
            .where(
                Exam.status == ExamStatus.SEALED,
                or_(
                    Exam.roster_status == ExamRosterStatus.PENDING,
                    and_(
                        Exam.roster_status == ExamRosterStatus.FAILED,
                        Exam.updated_at <= failed_before,
                    ),
                ),
            )
            .order_by(Exam.updated_at.asc(), Exam.id.asc())
            .limit(MAINTENANCE_SCAN_LIMIT)
        )

        return list((await db.execute(query)).scalars().all())


async def _list_result_exam_ids_needing_recovery(
    *,
    now: datetime,
) -> list[UUID]:
    """Find closed exams with unscheduled or retryable result-sync work."""

    failed_before = now - RESULT_FAILED_RETRY_AFTER

    async with async_session_factory() as db:
        query = (
            select(ExamResult.exam_id)
            .join(Exam, Exam.id == ExamResult.exam_id)
            .where(
                Exam.status == ExamStatus.CLOSED,
                or_(
                    and_(
                        ExamResult.sync_status == ResultSyncStatus.PENDING,
                        ExamResult.sync_batch_id.is_(None),
                    ),
                    and_(
                        ExamResult.sync_status == ResultSyncStatus.FAILED,
                        ExamResult.sync_batch_id.is_not(None),
                        or_(
                            ExamResult.last_sync_attempt_at.is_(None),
                            ExamResult.last_sync_attempt_at <= failed_before,
                        ),
                    ),
                ),
            )
            .distinct()
            .order_by(ExamResult.exam_id.asc())
            .limit(MAINTENANCE_SCAN_LIMIT)
        )

        return list((await db.execute(query)).scalars().all())


async def recover_background_work(ctx: dict[str, Any]) -> dict[str, int]:
    """Re-enqueue durable work that PostgreSQL says still needs execution.

    Intended to run periodically from ARQ cron once worker registration is
    added. Duplicate queue deliveries are safe because the candidate and result
    workers re-check PostgreSQL state before doing work.
    """

    redis = _arq_redis_from_context(ctx)
    now = datetime.now(UTC)

    stale_result_exam_ids = await _recover_stale_result_batches(now=now)
    roster_exam_ids = await _list_roster_exam_ids_needing_recovery(now=now)
    result_exam_ids = set(await _list_result_exam_ids_needing_recovery(now=now))
    result_exam_ids.update(stale_result_exam_ids)

    roster_enqueued = 0
    for exam_id in roster_exam_ids:
        await redis.enqueue_job(
            "prepare_exam_roster",
            str(exam_id),
        )
        roster_enqueued += 1

    result_enqueued = 0
    for exam_id in sorted(result_exam_ids, key=str):
        await redis.enqueue_job(
            "sync_exam_results",
            str(exam_id),
        )
        result_enqueued += 1

    if roster_enqueued or result_enqueued:
        logger.info(
            "Maintenance recovery enqueued %s roster job(s) and %s result job(s)",
            roster_enqueued,
            result_enqueued,
        )

    return {
        "roster_jobs_enqueued": roster_enqueued,
        "result_jobs_enqueued": result_enqueued,
        "stale_result_exams_recovered": len(stale_result_exam_ids),
    }
