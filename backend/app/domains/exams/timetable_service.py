"""Exam timetable integrity helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domains.academics.models import Curriculum, CurriculumSubject
from app.domains.exams.exceptions import ExamNotFound, ExamStateError
from app.domains.exams.models import Exam, ExamStatus
from app.domains.exams.repository import ExamRepository


@dataclass(frozen=True)
class TimetableImpact:
    exam_id: UUID
    title: str
    original_start_at: datetime
    proposed_start_at: datetime
    proposed_end_at: datetime


class ExamTimetableService:
    @staticmethod
    def intervals_overlap(
        a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime
    ) -> bool:
        return a_start < b_end and b_start < a_end

    @staticmethod
    async def level_id(db: AsyncSession, curriculum_subject_id: UUID) -> UUID:
        value = await db.scalar(
            select(Curriculum.academic_level_id)
            .join(CurriculumSubject, CurriculumSubject.curriculum_id == Curriculum.id)
            .where(CurriculumSubject.id == curriculum_subject_id)
        )
        if value is None:
            raise ValueError("Curriculum subject does not resolve to an academic level")
        return value

    @staticmethod
    async def acquire_level_lock(
        db: AsyncSession,
        *,
        session_id: UUID,
        term_id: UUID,
        level_id: UUID,
    ) -> None:
        scope = f"exam-timetable:{session_id}:{term_id}:{level_id}"
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
            {"scope": scope},
        )

    @classmethod
    async def list_leaf_exams(
        cls,
        db: AsyncSession,
        *,
        session_id: UUID,
        term_id: UUID,
        level_id: UUID,
        statuses: tuple[ExamStatus, ...],
        exclude_exam_id: UUID | None = None,
    ) -> list[Exam]:
        child = aliased(Exam)
        has_child = (
            select(child.id).where(child.revision_of_exam_id == Exam.id).exists()
        )
        query = (
            select(Exam)
            .join(CurriculumSubject, CurriculumSubject.id == Exam.curriculum_subject_id)
            .join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id)
            .where(
                Exam.session_id == session_id,
                Exam.term_id == term_id,
                Curriculum.academic_level_id == level_id,
                Exam.status.in_(statuses),
                ~has_child,
            )
        )
        if exclude_exam_id is not None:
            query = query.where(Exam.id != exclude_exam_id)
        result = await db.execute(
            query.order_by(Exam.scheduled_start_at.asc().nulls_last(), Exam.id.asc())
        )
        return list(result.scalars().all())

    @classmethod
    async def require_planned_slot_available(
        cls,
        db: AsyncSession,
        *,
        session_id: UUID,
        term_id: UUID,
        curriculum_subject_id: UUID,
        scheduled_start_at: datetime | None,
        duration_minutes: int,
        exclude_exam_id: UUID | None = None,
    ) -> None:
        if scheduled_start_at is None:
            return
        level_id = await cls.level_id(db, curriculum_subject_id)
        await cls.acquire_level_lock(
            db,
            session_id=session_id,
            term_id=term_id,
            level_id=level_id,
        )
        proposed_end = scheduled_start_at + timedelta(minutes=duration_minutes)
        rows = await cls.list_leaf_exams(
            db,
            session_id=session_id,
            term_id=term_id,
            level_id=level_id,
            exclude_exam_id=exclude_exam_id,
            statuses=(
                ExamStatus.DRAFT,
                ExamStatus.SUBMITTED,
                ExamStatus.SEALED,
                ExamStatus.ACTIVE,
                ExamStatus.SUSPENDED,
            ),
        )
        for row in rows:
            if row.scheduled_start_at is None:
                continue
            row_end = row.scheduled_start_at + timedelta(minutes=row.duration_minutes)
            if cls.intervals_overlap(
                scheduled_start_at, proposed_end, row.scheduled_start_at, row_end
            ):
                raise ExamStateError(
                    f"Academic level already has a planned examination overlapping this slot: {row.title}"
                )

    @classmethod
    async def require_level_free(cls, db: AsyncSession, *, exam_id: UUID) -> None:
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        level_id = await cls.level_id(db, exam.curriculum_subject_id)
        await cls.acquire_level_lock(
            db,
            session_id=exam.session_id,
            term_id=exam.term_id,
            level_id=level_id,
        )
        rows = await cls.list_leaf_exams(
            db,
            session_id=exam.session_id,
            term_id=exam.term_id,
            level_id=level_id,
            exclude_exam_id=exam.id,
            statuses=(ExamStatus.ACTIVE, ExamStatus.SUSPENDED),
        )
        if rows:
            raise ExamStateError(
                "Another examination for this academic level is already active or suspended"
            )

    @classmethod
    async def impact_after_start(
        cls, db: AsyncSession, *, exam_id: UUID
    ) -> list[TimetableImpact]:
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        if exam.activated_at is None:
            return []
        level_id = await cls.level_id(db, exam.curriculum_subject_id)
        rows = await cls.list_leaf_exams(
            db,
            session_id=exam.session_id,
            term_id=exam.term_id,
            level_id=level_id,
            exclude_exam_id=exam.id,
            statuses=(ExamStatus.DRAFT, ExamStatus.SUBMITTED, ExamStatus.SEALED),
        )
        current_end = exam.activated_at + timedelta(minutes=exam.duration_minutes)
        impacts: list[TimetableImpact] = []
        for row in rows:
            if row.scheduled_start_at is None:
                continue
            if (
                exam.scheduled_start_at is not None
                and row.scheduled_start_at <= exam.scheduled_start_at
            ):
                continue
            if row.scheduled_start_at >= current_end:
                break
            proposed_start = current_end
            proposed_end = proposed_start + timedelta(minutes=row.duration_minutes)
            impacts.append(
                TimetableImpact(
                    row.id,
                    row.title,
                    row.scheduled_start_at,
                    proposed_start,
                    proposed_end,
                )
            )
            current_end = proposed_end
        return impacts
