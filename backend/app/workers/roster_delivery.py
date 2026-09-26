"""Low-latency delivery for durable candidate-roster reconciliation work.

PostgreSQL remains authoritative. Academic synchronization marks affected
pre-execution rosters STALE inside its own transaction; only after that
transaction commits do we ask ARQ to deliver reconciliation work immediately.
The periodic maintenance sweep remains the recovery path if Redis is unavailable
or an enqueue is otherwise lost.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.core.database import async_session_factory
from app.domains.exams.models import Exam, ExamRosterStatus, ExamStatus
from app.domains.sync.schemas import SyncReconcileResponse
from app.workers.producer import arq_producer

logger = logging.getLogger(__name__)


async def enqueue_stale_roster_reconciliations() -> int:
    """Immediately enqueue every durable SEALED + STALE roster.

    The query runs in a fresh session so this function can only observe roster
    invalidations that have already committed. Deterministic ARQ job IDs make
    duplicate delivery safe when maintenance discovers the same work later.
    """

    async with async_session_factory() as db:
        exam_ids = list(
            (
                await db.execute(
                    select(Exam.id)
                    .where(
                        Exam.status == ExamStatus.SEALED,
                        Exam.roster_status == ExamRosterStatus.STALE,
                    )
                    .order_by(Exam.updated_at.asc(), Exam.id.asc())
                )
            )
            .scalars()
            .all()
        )
        await db.rollback()

    queued = 0
    for exam_id in exam_ids:
        delivered = await arq_producer.enqueue(
            "reconcile_exam_roster",
            str(exam_id),
        )
        if delivered:
            queued += 1

    if exam_ids:
        logger.info(
            "Immediate roster reconciliation delivery requested for %s stale exam(s); %s accepted by ARQ",
            len(exam_ids),
            queued,
        )

    return queued


async def enqueue_roster_reconciliation_after_sync(
    result: SyncReconcileResponse,
) -> int:
    """Deliver stale-roster work only when synchronization changed local truth."""

    if not result.bootstrapped and result.changes_applied <= 0:
        return 0

    return await enqueue_stale_roster_reconciliations()
