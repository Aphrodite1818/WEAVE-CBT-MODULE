"""Read-optimized roster queries for candidate administration views."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.candidates.models import CandidateStatus, ExamCandidate


class CandidateRosterQueryRepository:
    """Provide paginated roster reads without changing candidate lifecycle state."""

    @staticmethod
    def _filters(
        *,
        exam_id: UUID,
        status: CandidateStatus | None,
        class_id: UUID | None,
        search: str | None,
    ) -> list:
        filters: list = [ExamCandidate.exam_id == exam_id]
        if status is not None:
            filters.append(ExamCandidate.status == status)
        if class_id is not None:
            filters.append(ExamCandidate.class_id == class_id)

        needle = (search or "").strip()
        if needle:
            pattern = f"%{needle}%"
            filters.append(
                or_(
                    ExamCandidate.display_name.ilike(pattern),
                    ExamCandidate.admission_number.ilike(pattern),
                )
            )
        return filters

    @classmethod
    async def list_candidates(
        cls,
        db: AsyncSession,
        *,
        exam_id: UUID,
        status: CandidateStatus | None = None,
        class_id: UUID | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ExamCandidate]:
        query = (
            select(ExamCandidate)
            .where(
                *cls._filters(
                    exam_id=exam_id,
                    status=status,
                    class_id=class_id,
                    search=search,
                )
            )
            .order_by(
                ExamCandidate.display_name.asc(),
                ExamCandidate.admission_number.asc(),
                ExamCandidate.id.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        return list((await db.execute(query)).scalars().all())

    @classmethod
    async def count_candidates(
        cls,
        db: AsyncSession,
        *,
        exam_id: UUID,
        status: CandidateStatus | None = None,
        class_id: UUID | None = None,
        search: str | None = None,
    ) -> int:
        query = (
            select(func.count())
            .select_from(ExamCandidate)
            .where(
                *cls._filters(
                    exam_id=exam_id,
                    status=status,
                    class_id=class_id,
                    search=search,
                )
            )
        )
        return int((await db.execute(query)).scalar_one() or 0)
