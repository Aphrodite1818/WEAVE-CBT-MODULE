# ======================================== #
# backend.app.domains.exams.repository
# ======================================== #

"""Persistence operations for locally owned examination data.

Repositories do not authorize teachers, decide lifecycle transitions, seal
exams, synchronize with Weave, or commit transactions. Those responsibilities
belong to services and the integration layer.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academics.models import AcademicLevelSubject
from app.domains.exams.models import (
    Exam,
    ExamInvigilator,
    ExamQuestion,
    ExamQuestionOption,
    ExamStatus,
    ExamTargetClass,
)


class ExamRepository:
    """Provide database operations for local examination data."""

    # ========================== #
    # EXAMS
    # ========================== #

    @staticmethod
    async def add_exam(db: AsyncSession, exam: Exam) -> Exam:
        db.add(exam)
        await db.flush()
        return exam

    @staticmethod
    async def get_exam_by_id(
        db: AsyncSession,
        exam_id: UUID,
        *,
        lock: bool = False,
    ) -> Exam | None:
        query = select(Exam).where(Exam.id == exam_id)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_exam_by_title(
        db: AsyncSession,
        term_id: UUID,
        level_subject_id: UUID,
        title: str,
        *,
        lock: bool = False,
    ) -> Exam | None:
        """Return an exam by its term-scoped, LevelSubject-scoped title."""
        query = select(Exam).where(
            Exam.term_id == term_id,
            Exam.level_subject_id == level_subject_id,
            func.lower(Exam.title) == title.lower(),
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_exam_by_calendar_event_id(
        db: AsyncSession,
        weave_calendar_event_id: str,
        *,
        lock: bool = False,
    ) -> Exam | None:
        query = select(Exam).where(
            Exam.weave_calendar_event_id == weave_calendar_event_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_exams(
        db: AsyncSession,
        *,
        session_id: UUID | None = None,
        term_id: UUID | None = None,
        level_subject_id: UUID | None = None,
        level_id: UUID | None = None,
        subject_id: UUID | None = None,
        target_class_id: UUID | None = None,
        assessment_scheme_id: UUID | None = None,
        assessment_component_id: UUID | None = None,
        created_by_actor_id: UUID | None = None,
        invigilator_teacher_id: UUID | None = None,
        status: ExamStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Exam]:
        """Return exams matching explicit local academic scope filters."""
        query = select(Exam)
        joined_level_subject = False

        if level_id is not None or subject_id is not None:
            query = query.join(
                AcademicLevelSubject,
                AcademicLevelSubject.id == Exam.level_subject_id,
            )
            joined_level_subject = True

        if target_class_id is not None:
            query = query.join(
                ExamTargetClass,
                ExamTargetClass.exam_id == Exam.id,
            ).where(ExamTargetClass.class_id == target_class_id)

        if invigilator_teacher_id is not None:
            query = query.join(
                ExamInvigilator,
                ExamInvigilator.exam_id == Exam.id,
            ).where(ExamInvigilator.teacher_id == invigilator_teacher_id)

        if session_id is not None:
            query = query.where(Exam.session_id == session_id)
        if term_id is not None:
            query = query.where(Exam.term_id == term_id)
        if level_subject_id is not None:
            query = query.where(Exam.level_subject_id == level_subject_id)
        if level_id is not None:
            query = query.where(AcademicLevelSubject.level_id == level_id)
        if subject_id is not None:
            if not joined_level_subject:
                query = query.join(
                    AcademicLevelSubject,
                    AcademicLevelSubject.id == Exam.level_subject_id,
                )
            query = query.where(AcademicLevelSubject.subject_id == subject_id)
        if assessment_scheme_id is not None:
            query = query.where(Exam.assessment_scheme_id == assessment_scheme_id)
        if assessment_component_id is not None:
            query = query.where(
                Exam.assessment_component_id == assessment_component_id
            )
        if created_by_actor_id is not None:
            query = query.where(Exam.created_by_actor_id == created_by_actor_id)
        if status is not None:
            query = query.where(Exam.status == status)

        result = await db.execute(
            query.distinct()
            .order_by(Exam.created_at.desc(), Exam.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_exams_for_invigilator(
        db: AsyncSession,
        teacher_id: UUID,
        *,
        session_id: UUID | None = None,
        term_id: UUID | None = None,
        status: ExamStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Exam]:
        query = (
            select(Exam)
            .join(ExamInvigilator, ExamInvigilator.exam_id == Exam.id)
            .where(ExamInvigilator.teacher_id == teacher_id)
        )
        if session_id is not None:
            query = query.where(Exam.session_id == session_id)
        if term_id is not None:
            query = query.where(Exam.term_id == term_id)
        if status is not None:
            query = query.where(Exam.status == status)
        result = await db.execute(
            query.order_by(Exam.created_at.desc(), Exam.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_exams_for_class(
        db: AsyncSession,
        class_id: UUID,
        *,
        session_id: UUID | None = None,
        term_id: UUID | None = None,
        status: ExamStatus | None = None,
    ) -> list[Exam]:
        query = (
            select(Exam)
            .join(ExamTargetClass, ExamTargetClass.exam_id == Exam.id)
            .where(ExamTargetClass.class_id == class_id)
        )
        if session_id is not None:
            query = query.where(Exam.session_id == session_id)
        if term_id is not None:
            query = query.where(Exam.term_id == term_id)
        if status is not None:
            query = query.where(Exam.status == status)
        result = await db.execute(
            query.order_by(Exam.created_at.desc(), Exam.id.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_exams_for_level_subject(
        db: AsyncSession,
        level_subject_id: UUID,
        *,
        session_id: UUID | None = None,
        term_id: UUID | None = None,
        status: ExamStatus | None = None,
    ) -> list[Exam]:
        query = select(Exam).where(Exam.level_subject_id == level_subject_id)
        if session_id is not None:
            query = query.where(Exam.session_id == session_id)
        if term_id is not None:
            query = query.where(Exam.term_id == term_id)
        if status is not None:
            query = query.where(Exam.status == status)
        result = await db.execute(
            query.order_by(Exam.created_at.desc(), Exam.id.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_exams_for_component(
        db: AsyncSession,
        assessment_component_id: UUID,
        *,
        target_class_id: UUID | None = None,
        level_subject_id: UUID | None = None,
        term_id: UUID | None = None,
    ) -> list[Exam]:
        query = select(Exam).where(
            Exam.assessment_component_id == assessment_component_id
        )
        if target_class_id is not None:
            query = query.join(
                ExamTargetClass,
                ExamTargetClass.exam_id == Exam.id,
            ).where(ExamTargetClass.class_id == target_class_id)
        if level_subject_id is not None:
            query = query.where(Exam.level_subject_id == level_subject_id)
        if term_id is not None:
            query = query.where(Exam.term_id == term_id)
        result = await db.execute(
            query.distinct().order_by(Exam.created_at.desc(), Exam.id.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_exams(
        db: AsyncSession,
        *,
        session_id: UUID | None = None,
        term_id: UUID | None = None,
        level_subject_id: UUID | None = None,
        level_id: UUID | None = None,
        subject_id: UUID | None = None,
        target_class_id: UUID | None = None,
        assessment_scheme_id: UUID | None = None,
        assessment_component_id: UUID | None = None,
        created_by_actor_id: UUID | None = None,
        invigilator_teacher_id: UUID | None = None,
        status: ExamStatus | None = None,
    ) -> int:
        query = select(func.count(func.distinct(Exam.id))).select_from(Exam)
        joined_level_subject = False

        if level_id is not None or subject_id is not None:
            query = query.join(
                AcademicLevelSubject,
                AcademicLevelSubject.id == Exam.level_subject_id,
            )
            joined_level_subject = True

        if target_class_id is not None:
            query = query.join(
                ExamTargetClass,
                ExamTargetClass.exam_id == Exam.id,
            ).where(ExamTargetClass.class_id == target_class_id)

        if invigilator_teacher_id is not None:
            query = query.join(
                ExamInvigilator,
                ExamInvigilator.exam_id == Exam.id,
            ).where(ExamInvigilator.teacher_id == invigilator_teacher_id)

        if session_id is not None:
            query = query.where(Exam.session_id == session_id)
        if term_id is not None:
            query = query.where(Exam.term_id == term_id)
        if level_subject_id is not None:
            query = query.where(Exam.level_subject_id == level_subject_id)
        if level_id is not None:
            query = query.where(AcademicLevelSubject.level_id == level_id)
        if subject_id is not None:
            if not joined_level_subject:
                query = query.join(
                    AcademicLevelSubject,
                    AcademicLevelSubject.id == Exam.level_subject_id,
                )
            query = query.where(AcademicLevelSubject.subject_id == subject_id)
        if assessment_scheme_id is not None:
            query = query.where(Exam.assessment_scheme_id == assessment_scheme_id)
        if assessment_component_id is not None:
            query = query.where(
                Exam.assessment_component_id == assessment_component_id
            )
        if created_by_actor_id is not None:
            query = query.where(Exam.created_by_actor_id == created_by_actor_id)
        if status is not None:
            query = query.where(Exam.status == status)

        return int((await db.execute(query)).scalar_one() or 0)

    @staticmethod
    async def save_exam(db: AsyncSession, exam: Exam) -> Exam:
        db.add(exam)
        await db.flush()
        return exam

    # ========================== #
    # TARGET CLASSES
    # ========================== #

    @staticmethod
    async def add_target_class(
        db: AsyncSession,
        target_class: ExamTargetClass,
    ) -> ExamTargetClass:
        db.add(target_class)
        await db.flush()
        return target_class

    @staticmethod
    async def add_target_classes(
        db: AsyncSession,
        target_classes: Sequence[ExamTargetClass],
    ) -> list[ExamTargetClass]:
        rows = list(target_classes)
        if not rows:
            return []
        db.add_all(rows)
        await db.flush()
        return rows

    @staticmethod
    async def get_target_class(
        db: AsyncSession,
        exam_id: UUID,
        class_id: UUID,
        *,
        lock: bool = False,
    ) -> ExamTargetClass | None:
        query = select(ExamTargetClass).where(
            ExamTargetClass.exam_id == exam_id,
            ExamTargetClass.class_id == class_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_target_classes_for_exam(
        db: AsyncSession,
        exam_id: UUID,
    ) -> list[ExamTargetClass]:
        result = await db.execute(
            select(ExamTargetClass)
            .where(ExamTargetClass.exam_id == exam_id)
            .order_by(ExamTargetClass.class_id.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def save_target_class(
        db: AsyncSession,
        target_class: ExamTargetClass,
    ) -> ExamTargetClass:
        """Persist assignment provenance resolved while preparing/sealing."""
        db.add(target_class)
        await db.flush()
        return target_class

    @staticmethod
    async def remove_target_class(
        db: AsyncSession,
        target_class: ExamTargetClass,
    ) -> None:
        await db.delete(target_class)
        await db.flush()

    # ========================== #
    # INVIGILATORS
    # ========================== #

    @staticmethod
    async def add_invigilator(
        db: AsyncSession,
        invigilator: ExamInvigilator,
    ) -> ExamInvigilator:
        db.add(invigilator)
        await db.flush()
        return invigilator

    @staticmethod
    async def add_invigilators(
        db: AsyncSession,
        invigilators: Sequence[ExamInvigilator],
    ) -> list[ExamInvigilator]:
        rows = list(invigilators)
        if not rows:
            return []
        db.add_all(rows)
        await db.flush()
        return rows

    @staticmethod
    async def get_invigilator(
        db: AsyncSession,
        exam_id: UUID,
        teacher_id: UUID,
        *,
        lock: bool = False,
    ) -> ExamInvigilator | None:
        query = select(ExamInvigilator).where(
            ExamInvigilator.exam_id == exam_id,
            ExamInvigilator.teacher_id == teacher_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_invigilators_for_exam(
        db: AsyncSession,
        exam_id: UUID,
    ) -> list[ExamInvigilator]:
        result = await db.execute(
            select(ExamInvigilator)
            .where(ExamInvigilator.exam_id == exam_id)
            .order_by(ExamInvigilator.teacher_id.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_invigilations_for_teacher(
        db: AsyncSession,
        teacher_id: UUID,
    ) -> list[ExamInvigilator]:
        result = await db.execute(
            select(ExamInvigilator)
            .where(ExamInvigilator.teacher_id == teacher_id)
            .order_by(ExamInvigilator.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def remove_invigilator(
        db: AsyncSession,
        invigilator: ExamInvigilator,
    ) -> None:
        await db.delete(invigilator)
        await db.flush()

    # ========================== #
    # EXAM QUESTION SNAPSHOTS
    # ========================== #

    @staticmethod
    async def add_exam_question(
        db: AsyncSession,
        exam_question: ExamQuestion,
    ) -> ExamQuestion:
        db.add(exam_question)
        await db.flush()
        return exam_question

    @staticmethod
    async def add_exam_questions(
        db: AsyncSession,
        exam_questions: Sequence[ExamQuestion],
    ) -> list[ExamQuestion]:
        rows = list(exam_questions)
        if not rows:
            return []
        db.add_all(rows)
        await db.flush()
        return rows

    @staticmethod
    async def get_exam_question_by_id(
        db: AsyncSession,
        exam_id: UUID,
        exam_question_id: UUID,
        *,
        lock: bool = False,
    ) -> ExamQuestion | None:
        query = select(ExamQuestion).where(
            ExamQuestion.id == exam_question_id,
            ExamQuestion.exam_id == exam_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_exam_question_by_source_question(
        db: AsyncSession,
        exam_id: UUID,
        source_question_id: UUID,
    ) -> ExamQuestion | None:
        query = select(ExamQuestion).where(
            ExamQuestion.exam_id == exam_id,
            ExamQuestion.source_question_id == source_question_id,
        )
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_exam_questions(
        db: AsyncSession,
        exam_id: UUID,
    ) -> list[ExamQuestion]:
        result = await db.execute(
            select(ExamQuestion)
            .where(ExamQuestion.exam_id == exam_id)
            .order_by(ExamQuestion.position.asc(), ExamQuestion.id.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_exam_questions_by_ids(
        db: AsyncSession,
        exam_id: UUID,
        exam_question_ids: Sequence[UUID],
    ) -> list[ExamQuestion]:
        if not exam_question_ids:
            return []
        result = await db.execute(
            select(ExamQuestion)
            .where(
                ExamQuestion.exam_id == exam_id,
                ExamQuestion.id.in_(exam_question_ids),
            )
            .order_by(ExamQuestion.position.asc(), ExamQuestion.id.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_exam_questions(
        db: AsyncSession,
        exam_id: UUID,
    ) -> int:
        query = (
            select(func.count())
            .select_from(ExamQuestion)
            .where(ExamQuestion.exam_id == exam_id)
        )
        return int((await db.execute(query)).scalar_one() or 0)

    @staticmethod
    async def get_exam_question_point_total(
        db: AsyncSession,
        exam_id: UUID,
    ) -> Decimal:
        query = select(
            func.coalesce(func.sum(ExamQuestion.points), 0)
        ).where(ExamQuestion.exam_id == exam_id)
        value = (await db.execute(query)).scalar_one()
        return Decimal(str(value))

    # ========================== #
    # EXAM QUESTION OPTIONS
    # ========================== #

    @staticmethod
    async def add_exam_question_option(
        db: AsyncSession,
        option: ExamQuestionOption,
    ) -> ExamQuestionOption:
        db.add(option)
        await db.flush()
        return option

    @staticmethod
    async def add_exam_question_options(
        db: AsyncSession,
        options: Sequence[ExamQuestionOption],
    ) -> list[ExamQuestionOption]:
        rows = list(options)
        if not rows:
            return []
        db.add_all(rows)
        await db.flush()
        return rows

    @staticmethod
    async def get_exam_question_option_by_id(
        db: AsyncSession,
        exam_question_id: UUID,
        option_id: UUID,
    ) -> ExamQuestionOption | None:
        query = select(ExamQuestionOption).where(
            ExamQuestionOption.id == option_id,
            ExamQuestionOption.exam_question_id == exam_question_id,
        )
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_options_for_exam_question(
        db: AsyncSession,
        exam_question_id: UUID,
    ) -> list[ExamQuestionOption]:
        result = await db.execute(
            select(ExamQuestionOption)
            .where(ExamQuestionOption.exam_question_id == exam_question_id)
            .order_by(
                ExamQuestionOption.position.asc(),
                ExamQuestionOption.id.asc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_options_for_exam_questions(
        db: AsyncSession,
        exam_question_ids: Sequence[UUID],
    ) -> list[ExamQuestionOption]:
        if not exam_question_ids:
            return []
        result = await db.execute(
            select(ExamQuestionOption)
            .where(ExamQuestionOption.exam_question_id.in_(exam_question_ids))
            .order_by(
                ExamQuestionOption.exam_question_id.asc(),
                ExamQuestionOption.position.asc(),
                ExamQuestionOption.id.asc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_options_for_exam_question(
        db: AsyncSession,
        exam_question_id: UUID,
    ) -> int:
        query = (
            select(func.count())
            .select_from(ExamQuestionOption)
            .where(ExamQuestionOption.exam_question_id == exam_question_id)
        )
        return int((await db.execute(query)).scalar_one() or 0)
