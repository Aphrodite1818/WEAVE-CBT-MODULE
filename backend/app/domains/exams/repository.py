#========================================#
# backend.app.domains.exams.repository
#========================================#

"""
Persistence operations for locally owned examination data.

The exam repository manages:

- exam configuration persistence;
- exam lifecycle persistence;
- target-class and invigilator assignment persistence;
- frozen exam-question snapshots;
- frozen exam-question-option snapshots;
- exam lookup and filtering;
- persistence-level aggregates required by exam services.

The repository does NOT:

- authorize teachers;
- validate academic assignments;
- decide lifecycle transitions;
- seal exams;
- access Weave directly;
- manage candidates;
- create candidate attempts;
- allocate attempt questions;
- score attempts;
- synchronize results;
- commit transactions.

Services own business rules and transaction boundaries.

ExamQuestion and ExamQuestionOption represent immutable examination
snapshots created during exam sealing.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from app.domains.academics.models import AcademicTerm, AssessmentComponent
from app.domains.exams.models import (
    Exam,
    ExamInvigilator,
    ExamQuestion,
    ExamQuestionOption,
    ExamStatus,
    ExamTargetClass,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

#==========================#
# REPOSITORY
#==========================#


class ExamRepository:
    """Provide database operations for local examination data."""


    #==========================#
    # EXAMS
    #==========================#

    @staticmethod
    async def add_exam(
        db: AsyncSession,
        exam: Exam,
    ) -> Exam:
        """Add an exam to the unit of work and flush pending changes."""

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
        """Return an exam by local ID, optionally locking its row."""

        query = select(Exam).where(
            Exam.id == exam_id,
        )

        if lock:
            query = query.with_for_update()

        result = await db.execute(query)

        return result.scalar_one_or_none()


    @staticmethod
    async def get_exam_by_title(
        db: AsyncSession,
        title: str,
        *,
        lock: bool = False,
    ) -> Exam | None:
        """Return an exam by its case-insensitive unique title."""

        query = select(Exam).where(
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
        """Return an exam by its unique Weave calendar event ID."""

        query = select(Exam).where(
            Exam.weave_calendar_event_id == weave_calendar_event_id,
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
        level_id: UUID | None = None,
        target_class_id: UUID | None = None,
        subject_id: UUID | None = None,
        assessment_component_id: UUID | None = None,
        invigilator_teacher_id: UUID | None = None,
        status: ExamStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Exam]:
        """
        Return exams matching the supplied filters.

        Filters are optional so the same persistence primitive can support
        administrator and teacher exam listings.
        """

        query = select(Exam)

        if session_id is not None or term_id is not None:
            query = query.join(
                AssessmentComponent,
                AssessmentComponent.id == Exam.assessment_component_id,
            )

        if session_id is not None:
            query = query.join(
                AcademicTerm,
                AcademicTerm.id == AssessmentComponent.term_id,
            ).where(
                AcademicTerm.session_id == session_id,
            )

        if term_id is not None:
            query = query.where(
                AssessmentComponent.term_id == term_id,
            )

        if level_id is not None:
            query = query.where(
                Exam.level_id == level_id,
            )

        if target_class_id is not None:
            query = query.join(
                ExamTargetClass,
                ExamTargetClass.exam_id == Exam.id,
            ).where(
                ExamTargetClass.class_id == target_class_id,
            )

        if subject_id is not None:
            query = query.where(
                Exam.subject_id == subject_id,
            )

        if assessment_component_id is not None:
            query = query.where(
                Exam.assessment_component_id == assessment_component_id,
            )

        if invigilator_teacher_id is not None:
            query = query.join(
                ExamInvigilator,
                ExamInvigilator.exam_id == Exam.id,
            ).where(
                ExamInvigilator.teacher_id == invigilator_teacher_id,
            )

        if status is not None:
            query = query.where(
                Exam.status == status,
            )

        query = (
            query
            .order_by(
                Exam.created_at.desc(),
                Exam.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        result = await db.execute(query)

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
        """Return exams assigned to a teacher for invigilation."""

        query = (
            select(Exam)
            .join(
                ExamInvigilator,
                ExamInvigilator.exam_id == Exam.id,
            )
            .where(ExamInvigilator.teacher_id == teacher_id)
        )

        if session_id is not None or term_id is not None:
            query = query.join(
                AssessmentComponent,
                AssessmentComponent.id == Exam.assessment_component_id,
            )

        if session_id is not None:
            query = query.join(
                AcademicTerm,
                AcademicTerm.id == AssessmentComponent.term_id,
            ).where(
                AcademicTerm.session_id == session_id,
            )

        if term_id is not None:
            query = query.where(
                AssessmentComponent.term_id == term_id,
            )

        if status is not None:
            query = query.where(
                Exam.status == status,
            )

        query = (
            query
            .order_by(
                Exam.created_at.desc(),
                Exam.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        result = await db.execute(query)

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
        """Return exams configured for a class."""

        query = (
            select(Exam)
            .join(
                ExamTargetClass,
                ExamTargetClass.exam_id == Exam.id,
            )
            .where(ExamTargetClass.class_id == class_id)
        )

        if session_id is not None or term_id is not None:
            query = query.join(
                AssessmentComponent,
                AssessmentComponent.id == Exam.assessment_component_id,
            )

        if session_id is not None:
            query = query.join(
                AcademicTerm,
                AcademicTerm.id == AssessmentComponent.term_id,
            ).where(
                AcademicTerm.session_id == session_id,
            )

        if term_id is not None:
            query = query.where(
                AssessmentComponent.term_id == term_id,
            )

        if status is not None:
            query = query.where(
                Exam.status == status,
            )

        result = await db.execute(
            query.order_by(
                Exam.created_at.desc(),
                Exam.id.desc(),
            )
        )

        return list(result.scalars().all())


    @staticmethod
    async def list_exams_for_subject(
        db: AsyncSession,
        subject_id: UUID,
        *,
        session_id: UUID | None = None,
        term_id: UUID | None = None,
        status: ExamStatus | None = None,
    ) -> list[Exam]:
        """Return exams configured for a subject."""

        query = select(Exam).where(
            Exam.subject_id == subject_id,
        )

        if session_id is not None or term_id is not None:
            query = query.join(
                AssessmentComponent,
                AssessmentComponent.id == Exam.assessment_component_id,
            )

        if session_id is not None:
            query = query.join(
                AcademicTerm,
                AcademicTerm.id == AssessmentComponent.term_id,
            ).where(
                AcademicTerm.session_id == session_id,
            )

        if term_id is not None:
            query = query.where(
                AssessmentComponent.term_id == term_id,
            )

        if status is not None:
            query = query.where(
                Exam.status == status,
            )

        result = await db.execute(
            query.order_by(
                Exam.created_at.desc(),
                Exam.id.desc(),
            )
        )

        return list(result.scalars().all())


    @staticmethod
    async def list_exams_for_component(
        db: AsyncSession,
        assessment_component_id: UUID,
        *,
        target_class_id: UUID | None = None,
        subject_id: UUID | None = None,
    ) -> list[Exam]:
        """Return exams associated with an assessment component."""

        query = select(Exam).where(
            Exam.assessment_component_id == assessment_component_id,
        )

        if target_class_id is not None:
            query = query.join(
                ExamTargetClass,
                ExamTargetClass.exam_id == Exam.id,
            ).where(
                ExamTargetClass.class_id == target_class_id,
            )

        if subject_id is not None:
            query = query.where(
                Exam.subject_id == subject_id,
            )

        result = await db.execute(
            query.order_by(
                Exam.created_at.desc(),
                Exam.id.desc(),
            )
        )

        return list(result.scalars().all())


    @staticmethod
    async def count_exams(
        db: AsyncSession,
        *,
        session_id: UUID | None = None,
        term_id: UUID | None = None,
        level_id: UUID | None = None,
        target_class_id: UUID | None = None,
        subject_id: UUID | None = None,
        assessment_component_id: UUID | None = None,
        invigilator_teacher_id: UUID | None = None,
        status: ExamStatus | None = None,
    ) -> int:
        """Return the number of exams matching the supplied filters."""

        query = (
            select(func.count())
            .select_from(Exam)
        )

        if session_id is not None or term_id is not None:
            query = query.join(
                AssessmentComponent,
                AssessmentComponent.id == Exam.assessment_component_id,
            )

        if session_id is not None:
            query = query.join(
                AcademicTerm,
                AcademicTerm.id == AssessmentComponent.term_id,
            ).where(
                AcademicTerm.session_id == session_id,
            )

        if term_id is not None:
            query = query.where(
                AssessmentComponent.term_id == term_id,
            )

        if level_id is not None:
            query = query.where(
                Exam.level_id == level_id,
            )

        if target_class_id is not None:
            query = query.join(
                ExamTargetClass,
                ExamTargetClass.exam_id == Exam.id,
            ).where(
                ExamTargetClass.class_id == target_class_id,
            )

        if subject_id is not None:
            query = query.where(
                Exam.subject_id == subject_id,
            )

        if assessment_component_id is not None:
            query = query.where(
                Exam.assessment_component_id == assessment_component_id,
            )

        if invigilator_teacher_id is not None:
            query = query.join(
                ExamInvigilator,
                ExamInvigilator.exam_id == Exam.id,
            ).where(
                ExamInvigilator.teacher_id == invigilator_teacher_id,
            )

        if status is not None:
            query = query.where(
                Exam.status == status,
            )

        result = await db.execute(query)

        return int(result.scalar_one() or 0)


    @staticmethod
    async def save_exam(
        db: AsyncSession,
        exam: Exam,
    ) -> Exam:
        """
        Attach an exam to the unit of work and flush pending changes.

        Lifecycle validation belongs to the exam service.
        """

        db.add(exam)
        await db.flush()

        return exam


    #==========================#
    # TARGET CLASSES
    #==========================#

    @staticmethod
    async def add_target_class(
        db: AsyncSession,
        target_class: ExamTargetClass,
    ) -> ExamTargetClass:
        """Add one target-class assignment and flush pending changes."""

        db.add(target_class)
        await db.flush()

        return target_class


    @staticmethod
    async def add_target_classes(
        db: AsyncSession,
        target_classes: Sequence[ExamTargetClass],
    ) -> list[ExamTargetClass]:
        """Add target-class assignments in one unit-of-work operation."""

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
        """Return a target-class assignment for an exam and class pair."""

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
        """Return all target-class assignments for an exam."""

        result = await db.execute(
            select(ExamTargetClass)
            .where(ExamTargetClass.exam_id == exam_id)
            .order_by(ExamTargetClass.class_id.asc())
        )

        return list(result.scalars().all())


    @staticmethod
    async def remove_target_class(
        db: AsyncSession,
        target_class: ExamTargetClass,
    ) -> None:
        """Remove a target-class assignment and flush pending changes."""

        await db.delete(target_class)
        await db.flush()


    #==========================#
    # INVIGILATORS
    #==========================#

    @staticmethod
    async def add_invigilator(
        db: AsyncSession,
        invigilator: ExamInvigilator,
    ) -> ExamInvigilator:
        """Add one exam invigilator assignment and flush pending changes."""

        db.add(invigilator)
        await db.flush()

        return invigilator


    @staticmethod
    async def add_invigilators(
        db: AsyncSession,
        invigilators: Sequence[ExamInvigilator],
    ) -> list[ExamInvigilator]:
        """Add invigilator assignments in one unit-of-work operation."""

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
        """Return an invigilator assignment for an exam and teacher pair."""

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
        """Return all invigilator assignments for an exam."""

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
        """Return all exam assignments for an invigilating teacher."""

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
        """Remove an invigilator assignment and flush pending changes."""

        await db.delete(invigilator)
        await db.flush()


    #==========================#
    # EXAM QUESTION SNAPSHOTS
    #==========================#

    @staticmethod
    async def add_exam_question(
        db: AsyncSession,
        exam_question: ExamQuestion,
    ) -> ExamQuestion:
        """Add one frozen exam-question snapshot."""

        db.add(exam_question)
        await db.flush()

        return exam_question


    @staticmethod
    async def add_exam_questions(
        db: AsyncSession,
        exam_questions: Sequence[ExamQuestion],
    ) -> list[ExamQuestion]:
        """Add frozen exam-question snapshots in one unit-of-work operation."""

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
        """Return an exam question within the specified exam."""

        query = select(ExamQuestion).where(
            ExamQuestion.id == exam_question_id,
            ExamQuestion.exam_id == exam_id,
        )

        if lock:
            query = query.with_for_update()

        result = await db.execute(query)

        return result.scalar_one_or_none()


    @staticmethod
    async def get_exam_question_by_source_question(
        db: AsyncSession,
        exam_id: UUID,
        source_question_id: UUID,
    ) -> ExamQuestion | None:
        """
        Return the frozen snapshot created from a source question.

        This is useful during sealing to detect accidental duplicate inclusion.
        """

        query = select(ExamQuestion).where(
            ExamQuestion.exam_id == exam_id,
            ExamQuestion.source_question_id == source_question_id,
        )

        result = await db.execute(query)

        return result.scalar_one_or_none()


    @staticmethod
    async def list_exam_questions(
        db: AsyncSession,
        exam_id: UUID,
    ) -> list[ExamQuestion]:
        """Return an exam's frozen questions in canonical exam order."""

        query = (
            select(ExamQuestion)
            .where(
                ExamQuestion.exam_id == exam_id,
            )
            .order_by(
                ExamQuestion.position.asc(),
                ExamQuestion.id.asc(),
            )
        )

        result = await db.execute(query)

        return list(result.scalars().all())


    @staticmethod
    async def list_exam_questions_by_ids(
        db: AsyncSession,
        exam_id: UUID,
        exam_question_ids: Sequence[UUID],
    ) -> list[ExamQuestion]:
        """Return selected frozen questions belonging to an exam."""

        if not exam_question_ids:
            return []

        query = (
            select(ExamQuestion)
            .where(
                ExamQuestion.exam_id == exam_id,
                ExamQuestion.id.in_(exam_question_ids),
            )
            .order_by(
                ExamQuestion.position.asc(),
                ExamQuestion.id.asc(),
            )
        )

        result = await db.execute(query)

        return list(result.scalars().all())


    @staticmethod
    async def count_exam_questions(
        db: AsyncSession,
        exam_id: UUID,
    ) -> int:
        """Return the number of frozen questions contained in an exam."""

        query = (
            select(func.count())
            .select_from(ExamQuestion)
            .where(
                ExamQuestion.exam_id == exam_id,
            )
        )

        result = await db.execute(query)

        return int(result.scalar_one() or 0)


    @staticmethod
    async def get_exam_question_point_total(
        db: AsyncSession,
        exam_id: UUID,
    ) -> Decimal:
        """
        Return the sum of points represented by an exam's frozen questions.

        The service can compare this value with the exam's configured
        maximum score during sealing.
        """

        query = select(
            func.coalesce(
                func.sum(ExamQuestion.points),
                0,
            )
        ).where(
            ExamQuestion.exam_id == exam_id,
        )

        result = await db.execute(query)
        value = result.scalar_one()

        return Decimal(str(value))


    #==========================#
    # EXAM QUESTION OPTIONS
    #==========================#

    @staticmethod
    async def add_exam_question_option(
        db: AsyncSession,
        option: ExamQuestionOption,
    ) -> ExamQuestionOption:
        """Add one frozen answer-option snapshot."""

        db.add(option)
        await db.flush()

        return option


    @staticmethod
    async def add_exam_question_options(
        db: AsyncSession,
        options: Sequence[ExamQuestionOption],
    ) -> list[ExamQuestionOption]:
        """Add frozen answer-option snapshots in one operation."""

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
        """Return an option belonging to a frozen exam question."""

        query = select(ExamQuestionOption).where(
            ExamQuestionOption.id == option_id,
            ExamQuestionOption.exam_question_id == exam_question_id,
        )

        result = await db.execute(query)

        return result.scalar_one_or_none()


    @staticmethod
    async def list_options_for_exam_question(
        db: AsyncSession,
        exam_question_id: UUID,
    ) -> list[ExamQuestionOption]:
        """Return frozen options for one exam question in canonical order."""

        query = (
            select(ExamQuestionOption)
            .where(
                ExamQuestionOption.exam_question_id == exam_question_id,
            )
            .order_by(
                ExamQuestionOption.position.asc(),
                ExamQuestionOption.id.asc(),
            )
        )

        result = await db.execute(query)

        return list(result.scalars().all())


    @staticmethod
    async def list_options_for_exam_questions(
        db: AsyncSession,
        exam_question_ids: Sequence[UUID],
    ) -> list[ExamQuestionOption]:
        """
        Return frozen options for multiple exam questions.

        This avoids issuing one SQL query for every question when loading
        an exam for candidate allocation or server-side scoring.
        """

        if not exam_question_ids:
            return []

        query = (
            select(ExamQuestionOption)
            .where(
                ExamQuestionOption.exam_question_id.in_(
                    exam_question_ids
                ),
            )
            .order_by(
                ExamQuestionOption.exam_question_id.asc(),
                ExamQuestionOption.position.asc(),
                ExamQuestionOption.id.asc(),
            )
        )

        result = await db.execute(query)

        return list(result.scalars().all())


    @staticmethod
    async def count_options_for_exam_question(
        db: AsyncSession,
        exam_question_id: UUID,
    ) -> int:
        """Return the number of frozen options for an exam question."""

        query = (
            select(func.count())
            .select_from(ExamQuestionOption)
            .where(
                ExamQuestionOption.exam_question_id == exam_question_id,
            )
        )

        result = await db.execute(query)

        return int(result.scalar_one() or 0)
