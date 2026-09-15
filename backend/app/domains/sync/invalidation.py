"""Cross-domain invalidation caused by authoritative academic sync changes."""

from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.exams.models import Exam, ExamRosterStatus, ExamStatus


class SyncInvalidationRepository:
    """Invalidate local derived state when synced academic truth changes.

    Candidate rosters are derived from synchronized student enrollment. Once an
    exam is ACTIVE the roster is execution evidence and must not be rewritten by
    later Cloud changes. SEALED + READY rosters, however, are still pre-execution
    materializations and must be refreshed when enrollment truth changes.
    """

    @staticmethod
    async def mark_pre_execution_rosters_stale(db: AsyncSession) -> int:
        result = await db.execute(
            update(Exam)
            .where(
                Exam.status == ExamStatus.SEALED,
                Exam.roster_status == ExamRosterStatus.READY,
            )
            .values(
                roster_status=ExamRosterStatus.STALE,
                roster_error=(
                    "Synchronized student enrollment changed; candidate roster "
                    "must be reconciled before activation"
                ),
            )
        )
        return int(result.rowcount or 0)
