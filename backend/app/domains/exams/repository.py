"""Persistence operations for locally owned examination data."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, exists
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academics.models import Curriculum, CurriculumSubject
from app.domains.exams.models import (
    Exam,
    ExamInvigilator,
    ExamQuestion,
    ExamQuestionOption,
    ExamStatus,
    ExamTargetClass,
)


class ExamRepository:
    @staticmethod
    async def add_exam(db: AsyncSession, exam: Exam) -> Exam:
        db.add(exam)
        await db.flush()
        return exam

    @staticmethod
    async def get_exam_by_id(
        db: AsyncSession, exam_id: UUID, *, lock: bool = False
    ) -> Exam | None:
        query = select(Exam).where(Exam.id == exam_id)
        if lock:
            query = query.with_for_update(of=Exam)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_exam_by_title(
        db: AsyncSession,
        term_id: UUID,
        curriculum_subject_id: UUID,
        title: str,
        *,
        lock: bool = False,
    ) -> Exam | None:
        query = select(Exam).where(
            Exam.term_id == term_id,
            Exam.curriculum_subject_id == curriculum_subject_id,
            func.lower(Exam.title) == title.lower(),
        )
        if lock:
            query = query.with_for_update(of=Exam)
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
            query = query.with_for_update(of=Exam)
        return (await db.execute(query)).scalar_one_or_none()

    from sqlalchemy import exists, select

    @staticmethod
    async def is_source_question_referenced(
        db: AsyncSession,
        question_id: UUID,
    ) -> bool:

        result = await db.execute(
            select(exists().where(ExamQuestion.source_question_id == question_id))
        )

        return bool(result.scalar())

    @staticmethod
    def _apply_exam_filters(
        query,
        *,
        session_id: UUID | None,
        term_id: UUID | None,
        curriculum_subject_id: UUID | None,
        level_id: UUID | None,
        subject_id: UUID | None,
        target_class_id: UUID | None,
        assessment_scheme_id: UUID | None,
        assessment_component_id: UUID | None,
        created_by_actor_id: UUID | None,
        invigilator_teacher_id: UUID | None,
        status: ExamStatus | None,
    ):
        if level_id is not None or subject_id is not None:
            query = query.join(
                CurriculumSubject,
                CurriculumSubject.id == Exam.curriculum_subject_id,
            )
        if level_id is not None:
            query = query.join(
                Curriculum, Curriculum.id == CurriculumSubject.curriculum_id
            ).where(Curriculum.academic_level_id == level_id)
        if subject_id is not None:
            query = query.where(CurriculumSubject.subject_id == subject_id)
        if target_class_id is not None:
            query = query.join(
                ExamTargetClass, ExamTargetClass.exam_id == Exam.id
            ).where(ExamTargetClass.class_id == target_class_id)
        if invigilator_teacher_id is not None:
            query = query.join(
                ExamInvigilator, ExamInvigilator.exam_id == Exam.id
            ).where(ExamInvigilator.teacher_id == invigilator_teacher_id)
        if session_id is not None:
            query = query.where(Exam.session_id == session_id)
        if term_id is not None:
            query = query.where(Exam.term_id == term_id)
        if curriculum_subject_id is not None:
            query = query.where(Exam.curriculum_subject_id == curriculum_subject_id)
        if assessment_scheme_id is not None:
            query = query.where(Exam.assessment_scheme_id == assessment_scheme_id)
        if assessment_component_id is not None:
            query = query.where(Exam.assessment_component_id == assessment_component_id)
        if created_by_actor_id is not None:
            query = query.where(Exam.created_by_actor_id == created_by_actor_id)
        if status is not None:
            query = query.where(Exam.status == status)
        return query

    @classmethod
    async def list_exams(
        cls,
        db: AsyncSession,
        *,
        session_id: UUID | None = None,
        term_id: UUID | None = None,
        curriculum_subject_id: UUID | None = None,
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
        query = cls._apply_exam_filters(
            select(Exam),
            session_id=session_id,
            term_id=term_id,
            curriculum_subject_id=curriculum_subject_id,
            level_id=level_id,
            subject_id=subject_id,
            target_class_id=target_class_id,
            assessment_scheme_id=assessment_scheme_id,
            assessment_component_id=assessment_component_id,
            created_by_actor_id=created_by_actor_id,
            invigilator_teacher_id=invigilator_teacher_id,
            status=status,
        )
        result = await db.execute(
            query.distinct()
            .order_by(Exam.created_at.desc(), Exam.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    @classmethod
    async def count_exams(cls, db: AsyncSession, **filters) -> int:
        query = cls._apply_exam_filters(
            select(func.count(func.distinct(Exam.id))).select_from(Exam),
            session_id=filters.get("session_id"),
            term_id=filters.get("term_id"),
            curriculum_subject_id=filters.get("curriculum_subject_id"),
            level_id=filters.get("level_id"),
            subject_id=filters.get("subject_id"),
            target_class_id=filters.get("target_class_id"),
            assessment_scheme_id=filters.get("assessment_scheme_id"),
            assessment_component_id=filters.get("assessment_component_id"),
            created_by_actor_id=filters.get("created_by_actor_id"),
            invigilator_teacher_id=filters.get("invigilator_teacher_id"),
            status=filters.get("status"),
        )
        return int((await db.execute(query)).scalar_one() or 0)

    @classmethod
    async def list_exams_for_invigilator(
        cls, db: AsyncSession, teacher_id: UUID, **filters
    ) -> list[Exam]:
        return await cls.list_exams(db, invigilator_teacher_id=teacher_id, **filters)

    @classmethod
    async def list_exams_for_class(
        cls, db: AsyncSession, class_id: UUID, **filters
    ) -> list[Exam]:
        return await cls.list_exams(db, target_class_id=class_id, **filters)

    @classmethod
    async def list_exams_for_curriculum_subject(
        cls, db: AsyncSession, curriculum_subject_id: UUID, **filters
    ) -> list[Exam]:
        return await cls.list_exams(
            db, curriculum_subject_id=curriculum_subject_id, **filters
        )

    @classmethod
    async def list_exams_for_component(
        cls,
        db: AsyncSession,
        assessment_component_id: UUID,
        *,
        target_class_id: UUID | None = None,
        curriculum_subject_id: UUID | None = None,
        term_id: UUID | None = None,
    ) -> list[Exam]:
        return await cls.list_exams(
            db,
            assessment_component_id=assessment_component_id,
            target_class_id=target_class_id,
            curriculum_subject_id=curriculum_subject_id,
            term_id=term_id,
        )

    @staticmethod
    async def save_exam(db: AsyncSession, exam: Exam) -> Exam:
        db.add(exam)
        await db.flush()
        return exam

    @staticmethod
    async def add_target_class(
        db: AsyncSession, target_class: ExamTargetClass
    ) -> ExamTargetClass:
        db.add(target_class)
        await db.flush()
        return target_class

    @staticmethod
    async def add_target_classes(
        db: AsyncSession, target_classes: Sequence[ExamTargetClass]
    ) -> list[ExamTargetClass]:
        rows = list(target_classes)
        if rows:
            db.add_all(rows)
            await db.flush()
        return rows

    @staticmethod
    async def get_target_class(
        db: AsyncSession, exam_id: UUID, class_id: UUID, *, lock: bool = False
    ) -> ExamTargetClass | None:
        query = select(ExamTargetClass).where(
            ExamTargetClass.exam_id == exam_id,
            ExamTargetClass.class_id == class_id,
        )
        if lock:
            query = query.with_for_update(of=ExamTargetClass)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_target_classes_for_exam(
        db: AsyncSession, exam_id: UUID
    ) -> list[ExamTargetClass]:
        result = await db.execute(
            select(ExamTargetClass)
            .where(ExamTargetClass.exam_id == exam_id)
            .order_by(ExamTargetClass.class_id.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def save_target_class(
        db: AsyncSession, target_class: ExamTargetClass
    ) -> ExamTargetClass:
        db.add(target_class)
        await db.flush()
        return target_class

    @staticmethod
    async def remove_target_class(
        db: AsyncSession, target_class: ExamTargetClass
    ) -> None:
        await db.delete(target_class)
        await db.flush()

    @staticmethod
    async def add_invigilator(
        db: AsyncSession, invigilator: ExamInvigilator
    ) -> ExamInvigilator:
        db.add(invigilator)
        await db.flush()
        return invigilator

    @staticmethod
    async def add_invigilators(
        db: AsyncSession, invigilators: Sequence[ExamInvigilator]
    ) -> list[ExamInvigilator]:
        rows = list(invigilators)
        if rows:
            db.add_all(rows)
            await db.flush()
        return rows

    @staticmethod
    async def get_invigilator(
        db: AsyncSession, exam_id: UUID, teacher_id: UUID, *, lock: bool = False
    ) -> ExamInvigilator | None:
        query = select(ExamInvigilator).where(
            ExamInvigilator.exam_id == exam_id,
            ExamInvigilator.teacher_id == teacher_id,
        )
        if lock:
            query = query.with_for_update(of=ExamInvigilator)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_invigilators_for_exam(
        db: AsyncSession, exam_id: UUID
    ) -> list[ExamInvigilator]:
        return list(
            (
                await db.execute(
                    select(ExamInvigilator).where(ExamInvigilator.exam_id == exam_id)
                )
            )
            .scalars()
            .all()
        )

    @staticmethod
    async def list_invigilations_for_teacher(
        db: AsyncSession, teacher_id: UUID
    ) -> list[ExamInvigilator]:
        return list(
            (
                await db.execute(
                    select(ExamInvigilator).where(
                        ExamInvigilator.teacher_id == teacher_id
                    )
                )
            )
            .scalars()
            .all()
        )

    @staticmethod
    async def remove_invigilator(
        db: AsyncSession, invigilator: ExamInvigilator
    ) -> None:
        await db.delete(invigilator)
        await db.flush()

    @staticmethod
    async def add_exam_question(
        db: AsyncSession, question: ExamQuestion
    ) -> ExamQuestion:
        db.add(question)
        await db.flush()
        return question

    @staticmethod
    async def add_exam_questions(
        db: AsyncSession, questions: Sequence[ExamQuestion]
    ) -> list[ExamQuestion]:
        rows = list(questions)
        if rows:
            db.add_all(rows)
            await db.flush()
        return rows

    @staticmethod
    async def get_exam_question_by_id(
        db: AsyncSession, question_id: UUID, *, lock: bool = False
    ) -> ExamQuestion | None:
        query = select(ExamQuestion).where(ExamQuestion.id == question_id)
        if lock:
            query = query.with_for_update(of=ExamQuestion)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_exam_question_for_source(
        db: AsyncSession, exam_id: UUID, source_question_id: UUID
    ) -> ExamQuestion | None:
        return (
            await db.execute(
                select(ExamQuestion).where(
                    ExamQuestion.exam_id == exam_id,
                    ExamQuestion.source_question_id == source_question_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_exam_questions(
        db: AsyncSession, exam_id: UUID
    ) -> list[ExamQuestion]:
        result = await db.execute(
            select(ExamQuestion)
            .where(ExamQuestion.exam_id == exam_id)
            .order_by(ExamQuestion.position.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_exam_question_point_total(db: AsyncSession, exam_id: UUID) -> Decimal:
        value = await db.scalar(
            select(func.coalesce(func.sum(ExamQuestion.points), 0)).where(
                ExamQuestion.exam_id == exam_id
            )
        )
        return Decimal(value or 0)

    @staticmethod
    async def save_exam_question(
        db: AsyncSession, question: ExamQuestion
    ) -> ExamQuestion:
        db.add(question)
        await db.flush()
        return question

    @staticmethod
    async def remove_exam_question(db: AsyncSession, question: ExamQuestion) -> None:
        await db.delete(question)
        await db.flush()

    @staticmethod
    async def add_exam_question_option(
        db: AsyncSession, option: ExamQuestionOption
    ) -> ExamQuestionOption:
        db.add(option)
        await db.flush()
        return option

    @staticmethod
    async def add_exam_question_options(
        db: AsyncSession, options: Sequence[ExamQuestionOption]
    ) -> list[ExamQuestionOption]:
        rows = list(options)
        if rows:
            db.add_all(rows)
            await db.flush()
        return rows

    @staticmethod
    async def list_exam_question_options(
        db: AsyncSession, exam_question_id: UUID
    ) -> list[ExamQuestionOption]:
        result = await db.execute(
            select(ExamQuestionOption)
            .where(ExamQuestionOption.exam_question_id == exam_question_id)
            .order_by(ExamQuestionOption.position.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def remove_exam_question_option(
        db: AsyncSession, option: ExamQuestionOption
    ) -> None:
        await db.delete(option)
        await db.flush()
