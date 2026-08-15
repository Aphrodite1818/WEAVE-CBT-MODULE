# ======================================== #
# backend.app.domains.academics.repository
# ======================================== #

"""Persistence operations for academic data projected from Weave.

The repository only reads and writes local projection models. It does not call
Weave, authorize actors, decide synchronization policy, or commit transactions.
Services own business rules and transaction boundaries.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academics.models import (
    AcademicClass,
    AcademicLevel,
    AcademicLevelSubject,
    AcademicSession,
    AcademicSubject,
    AcademicSyncState,
    AcademicTeacher,
    AcademicTerm,
    AssessmentComponent,
    AssessmentScheme,
    StudentEnrollment,
    TeacherAssignment,
)


class AcademicRepository:
    """Database operations for local academic projections."""

    # ========================== #
    # SESSIONS
    # ========================== #

    @staticmethod
    async def add_session(
        db: AsyncSession,
        academic_session: AcademicSession,
    ) -> AcademicSession:
        db.add(academic_session)
        await db.flush()
        return academic_session

    @staticmethod
    async def get_session_by_id(
        db: AsyncSession,
        academic_session_id: UUID,
        *,
        lock: bool = False,
    ) -> AcademicSession | None:
        query = select(AcademicSession).where(AcademicSession.id == academic_session_id)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_session_by_weave_id(
        db: AsyncSession,
        academic_session_weave_id: str,
        *,
        lock: bool = False,
    ) -> AcademicSession | None:
        query = select(AcademicSession).where(
            AcademicSession.weave_session_id == academic_session_weave_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_current_session(
        db: AsyncSession,
        *,
        lock: bool = False,
    ) -> AcademicSession | None:
        query = select(AcademicSession).where(AcademicSession.is_current.is_(True))
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_sessions(db: AsyncSession) -> list[AcademicSession]:
        result = await db.execute(
            select(AcademicSession).order_by(
                AcademicSession.start_date.desc().nulls_last(),
                AcademicSession.name.desc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def save_session(
        db: AsyncSession,
        academic_session: AcademicSession,
    ) -> AcademicSession:
        db.add(academic_session)
        await db.flush()
        return academic_session

    # ========================== #
    # TERMS
    # ========================== #

    @staticmethod
    async def add_term(db: AsyncSession, term: AcademicTerm) -> AcademicTerm:
        db.add(term)
        await db.flush()
        return term

    @staticmethod
    async def get_term_by_id(
        db: AsyncSession,
        academic_term_id: UUID,
        *,
        lock: bool = False,
    ) -> AcademicTerm | None:
        query = select(AcademicTerm).where(AcademicTerm.id == academic_term_id)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_term_by_weave_id(
        db: AsyncSession,
        academic_term_weave_id: str,
        *,
        lock: bool = False,
    ) -> AcademicTerm | None:
        query = select(AcademicTerm).where(
            AcademicTerm.weave_term_id == academic_term_weave_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_current_term(
        db: AsyncSession,
        session_id: UUID,
        *,
        lock: bool = False,
    ) -> AcademicTerm | None:
        query = select(AcademicTerm).where(
            AcademicTerm.session_id == session_id,
            AcademicTerm.is_current.is_(True),
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_terms_for_session(
        db: AsyncSession,
        session_id: UUID,
    ) -> list[AcademicTerm]:
        result = await db.execute(
            select(AcademicTerm)
            .where(AcademicTerm.session_id == session_id)
            .order_by(
                AcademicTerm.start_date.asc().nulls_last(),
                AcademicTerm.name.asc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def save_term(db: AsyncSession, term: AcademicTerm) -> AcademicTerm:
        db.add(term)
        await db.flush()
        return term

    # ========================== #
    # LEVELS
    # ========================== #

    @staticmethod
    async def add_level(db: AsyncSession, level: AcademicLevel) -> AcademicLevel:
        db.add(level)
        await db.flush()
        return level

    @staticmethod
    async def get_level_by_id(
        db: AsyncSession,
        academic_level_id: UUID,
        *,
        lock: bool = False,
    ) -> AcademicLevel | None:
        query = select(AcademicLevel).where(AcademicLevel.id == academic_level_id)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_level_by_weave_id(
        db: AsyncSession,
        weave_academic_level_id: str,
        *,
        lock: bool = False,
    ) -> AcademicLevel | None:
        query = select(AcademicLevel).where(
            AcademicLevel.weave_level_id == weave_academic_level_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_active_levels(db: AsyncSession) -> list[AcademicLevel]:
        result = await db.execute(
            select(AcademicLevel)
            .where(AcademicLevel.is_active.is_(True))
            .order_by(AcademicLevel.name.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def save_level(db: AsyncSession, level: AcademicLevel) -> AcademicLevel:
        db.add(level)
        await db.flush()
        return level

    # ========================== #
    # CLASSES / ARMS
    # ========================== #

    @staticmethod
    async def add_class(
        db: AsyncSession,
        academic_class: AcademicClass,
    ) -> AcademicClass:
        db.add(academic_class)
        await db.flush()
        return academic_class

    @staticmethod
    async def get_class_by_id(
        db: AsyncSession,
        class_id: UUID,
        *,
        lock: bool = False,
    ) -> AcademicClass | None:
        query = select(AcademicClass).where(AcademicClass.id == class_id)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_class_by_weave_id(
        db: AsyncSession,
        weave_class_id: str,
        *,
        lock: bool = False,
    ) -> AcademicClass | None:
        query = select(AcademicClass).where(
            AcademicClass.weave_class_id == weave_class_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_class_for_level_and_arm(
        db: AsyncSession,
        level_id: UUID,
        arm: str,
        *,
        lock: bool = False,
    ) -> AcademicClass | None:
        query = select(AcademicClass).where(
            AcademicClass.level_id == level_id,
            AcademicClass.arm == arm,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_classes_for_level(
        db: AsyncSession,
        level_id: UUID,
        *,
        active_only: bool = True,
    ) -> list[AcademicClass]:
        query = select(AcademicClass).where(AcademicClass.level_id == level_id)
        if active_only:
            query = query.where(AcademicClass.is_active.is_(True))
        result = await db.execute(query.order_by(AcademicClass.arm.asc()))
        return list(result.scalars().all())

    @staticmethod
    async def list_classes_by_ids(
        db: AsyncSession,
        class_ids: Sequence[UUID],
        *,
        active_only: bool = False,
    ) -> list[AcademicClass]:
        if not class_ids:
            return []
        query = select(AcademicClass).where(AcademicClass.id.in_(class_ids))
        if active_only:
            query = query.where(AcademicClass.is_active.is_(True))
        result = await db.execute(query.order_by(AcademicClass.arm.asc()))
        return list(result.scalars().all())

    @staticmethod
    async def save_class(
        db: AsyncSession,
        academic_class: AcademicClass,
    ) -> AcademicClass:
        db.add(academic_class)
        await db.flush()
        return academic_class

    # ========================== #
    # SUBJECTS
    # ========================== #

    @staticmethod
    async def add_subject(
        db: AsyncSession,
        subject: AcademicSubject,
    ) -> AcademicSubject:
        db.add(subject)
        await db.flush()
        return subject

    @staticmethod
    async def get_subject_by_id(
        db: AsyncSession,
        subject_id: UUID,
        *,
        lock: bool = False,
    ) -> AcademicSubject | None:
        query = select(AcademicSubject).where(AcademicSubject.id == subject_id)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_subject_by_weave_id(
        db: AsyncSession,
        weave_subject_id: str,
        *,
        lock: bool = False,
    ) -> AcademicSubject | None:
        query = select(AcademicSubject).where(
            AcademicSubject.weave_subject_id == weave_subject_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_active_subjects(db: AsyncSession) -> list[AcademicSubject]:
        result = await db.execute(
            select(AcademicSubject)
            .where(AcademicSubject.is_active.is_(True))
            .order_by(AcademicSubject.name.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def save_subject(
        db: AsyncSession,
        subject: AcademicSubject,
    ) -> AcademicSubject:
        db.add(subject)
        await db.flush()
        return subject

    # ========================== #
    # LEVEL SUBJECTS
    # ========================== #

    @staticmethod
    async def add_level_subject(
        db: AsyncSession,
        level_subject: AcademicLevelSubject,
    ) -> AcademicLevelSubject:
        db.add(level_subject)
        await db.flush()
        return level_subject

    @staticmethod
    async def get_level_subject_by_id(
        db: AsyncSession,
        level_subject_id: UUID,
        *,
        lock: bool = False,
    ) -> AcademicLevelSubject | None:
        query = select(AcademicLevelSubject).where(
            AcademicLevelSubject.id == level_subject_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_level_subject_by_weave_id(
        db: AsyncSession,
        weave_level_subject_id: str,
        *,
        lock: bool = False,
    ) -> AcademicLevelSubject | None:
        query = select(AcademicLevelSubject).where(
            AcademicLevelSubject.weave_level_subject_id == weave_level_subject_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_level_subject(
        db: AsyncSession,
        level_id: UUID,
        subject_id: UUID,
        *,
        lock: bool = False,
    ) -> AcademicLevelSubject | None:
        query = select(AcademicLevelSubject).where(
            AcademicLevelSubject.level_id == level_id,
            AcademicLevelSubject.subject_id == subject_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_level_subjects_for_level(
        db: AsyncSession,
        level_id: UUID,
        *,
        active_only: bool = True,
    ) -> list[AcademicLevelSubject]:
        query = select(AcademicLevelSubject).where(
            AcademicLevelSubject.level_id == level_id
        )
        if active_only:
            query = query.where(AcademicLevelSubject.is_active.is_(True))
        result = await db.execute(query.order_by(AcademicLevelSubject.subject_id.asc()))
        return list(result.scalars().all())

    @staticmethod
    async def list_subjects_for_level(
        db: AsyncSession,
        level_id: UUID,
        *,
        active_only: bool = False,
    ) -> list[AcademicSubject]:
        query = (
            select(AcademicSubject)
            .join(
                AcademicLevelSubject,
                AcademicLevelSubject.subject_id == AcademicSubject.id,
            )
            .where(AcademicLevelSubject.level_id == level_id)
        )
        if active_only:
            query = query.where(
                AcademicLevelSubject.is_active.is_(True),
                AcademicSubject.is_active.is_(True),
            )
        result = await db.execute(query.order_by(AcademicSubject.name.asc()))
        return list(result.scalars().unique().all())

    @staticmethod
    async def active_level_subject_exists(
        db: AsyncSession,
        level_id: UUID,
        subject_id: UUID,
    ) -> bool:
        query = select(
            exists().where(
                AcademicLevelSubject.level_id == level_id,
                AcademicLevelSubject.subject_id == subject_id,
                AcademicLevelSubject.is_active.is_(True),
            )
        )
        return bool(await db.scalar(query))

    @staticmethod
    async def save_level_subject(
        db: AsyncSession,
        level_subject: AcademicLevelSubject,
    ) -> AcademicLevelSubject:
        db.add(level_subject)
        await db.flush()
        return level_subject

    # ========================== #
    # ASSESSMENT SCHEMES
    # ========================== #

    @staticmethod
    async def add_assessment_scheme(
        db: AsyncSession,
        scheme: AssessmentScheme,
    ) -> AssessmentScheme:
        db.add(scheme)
        await db.flush()
        return scheme

    @staticmethod
    async def get_assessment_scheme_by_id(
        db: AsyncSession,
        scheme_id: UUID,
        *,
        lock: bool = False,
    ) -> AssessmentScheme | None:
        query = select(AssessmentScheme).where(AssessmentScheme.id == scheme_id)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_assessment_scheme_by_weave_id(
        db: AsyncSession,
        weave_scheme_id: str,
        *,
        lock: bool = False,
    ) -> AssessmentScheme | None:
        query = select(AssessmentScheme).where(
            AssessmentScheme.weave_scheme_id == weave_scheme_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_active_assessment_scheme(
        db: AsyncSession,
        *,
        lock: bool = False,
    ) -> AssessmentScheme | None:
        query = select(AssessmentScheme).where(AssessmentScheme.status == "active")
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_assessment_schemes(
        db: AsyncSession,
    ) -> list[AssessmentScheme]:
        result = await db.execute(
            select(AssessmentScheme).order_by(
                AssessmentScheme.activated_at.desc().nulls_last(),
                AssessmentScheme.name.asc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def save_assessment_scheme(
        db: AsyncSession,
        scheme: AssessmentScheme,
    ) -> AssessmentScheme:
        db.add(scheme)
        await db.flush()
        return scheme

    # ========================== #
    # ASSESSMENT COMPONENTS
    # ========================== #

    @staticmethod
    async def add_component(
        db: AsyncSession,
        component: AssessmentComponent,
    ) -> AssessmentComponent:
        db.add(component)
        await db.flush()
        return component

    @staticmethod
    async def get_component_by_id(
        db: AsyncSession,
        component_id: UUID,
        *,
        lock: bool = False,
    ) -> AssessmentComponent | None:
        query = select(AssessmentComponent).where(
            AssessmentComponent.id == component_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_component_by_weave_id(
        db: AsyncSession,
        weave_component_id: str,
        *,
        lock: bool = False,
    ) -> AssessmentComponent | None:
        query = select(AssessmentComponent).where(
            AssessmentComponent.weave_component_id == weave_component_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_components_for_scheme(
        db: AsyncSession,
        assessment_scheme_id: UUID,
        *,
        active_only: bool = True,
    ) -> list[AssessmentComponent]:
        query = select(AssessmentComponent).where(
            AssessmentComponent.assessment_scheme_id == assessment_scheme_id
        )
        if active_only:
            query = query.where(AssessmentComponent.is_active.is_(True))
        result = await db.execute(
            query.order_by(
                AssessmentComponent.position.asc(),
                AssessmentComponent.name.asc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def save_component(
        db: AsyncSession,
        component: AssessmentComponent,
    ) -> AssessmentComponent:
        db.add(component)
        await db.flush()
        return component

    # ========================== #
    # TEACHERS
    # ========================== #

    @staticmethod
    async def add_teacher(
        db: AsyncSession,
        teacher: AcademicTeacher,
    ) -> AcademicTeacher:
        db.add(teacher)
        await db.flush()
        return teacher

    @staticmethod
    async def get_teacher_by_id(
        db: AsyncSession,
        teacher_id: UUID,
        *,
        lock: bool = False,
    ) -> AcademicTeacher | None:
        query = select(AcademicTeacher).where(AcademicTeacher.id == teacher_id)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_teacher_by_weave_id(
        db: AsyncSession,
        weave_teacher_id: str,
        *,
        lock: bool = False,
    ) -> AcademicTeacher | None:
        query = select(AcademicTeacher).where(
            AcademicTeacher.weave_teacher_id == weave_teacher_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_teacher_by_membership_id(
        db: AsyncSession,
        membership_id: str,
        *,
        lock: bool = False,
    ) -> AcademicTeacher | None:
        query = select(AcademicTeacher).where(
            AcademicTeacher.weave_membership_id == membership_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_active_teachers(db: AsyncSession) -> list[AcademicTeacher]:
        result = await db.execute(
            select(AcademicTeacher)
            .where(AcademicTeacher.is_active.is_(True))
            .order_by(AcademicTeacher.display_name.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def save_teacher(
        db: AsyncSession,
        teacher: AcademicTeacher,
    ) -> AcademicTeacher:
        db.add(teacher)
        await db.flush()
        return teacher

    # ========================== #
    # TEACHER ASSIGNMENTS
    # ========================== #

    @staticmethod
    async def add_assignment(
        db: AsyncSession,
        assignment: TeacherAssignment,
    ) -> TeacherAssignment:
        db.add(assignment)
        await db.flush()
        return assignment

    @staticmethod
    async def add_assignments(
        db: AsyncSession,
        assignments: Sequence[TeacherAssignment],
    ) -> list[TeacherAssignment]:
        rows = list(assignments)
        if not rows:
            return []
        db.add_all(rows)
        await db.flush()
        return rows

    @staticmethod
    async def get_assignment_by_id(
        db: AsyncSession,
        assignment_id: UUID,
        *,
        lock: bool = False,
    ) -> TeacherAssignment | None:
        query = select(TeacherAssignment).where(TeacherAssignment.id == assignment_id)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_assignment_by_weave_id(
        db: AsyncSession,
        weave_assignment_id: str,
        *,
        lock: bool = False,
    ) -> TeacherAssignment | None:
        query = select(TeacherAssignment).where(
            TeacherAssignment.weave_assignment_id == weave_assignment_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_active_assignment_for_scope(
        db: AsyncSession,
        teacher_id: UUID,
        class_id: UUID,
        level_subject_id: UUID,
        *,
        effective_on: date | None = None,
        lock: bool = False,
    ) -> TeacherAssignment | None:
        """Return the current active assignment for one teacher/arm/curriculum scope."""
        query = select(TeacherAssignment).where(
            TeacherAssignment.teacher_id == teacher_id,
            TeacherAssignment.class_id == class_id,
            TeacherAssignment.level_subject_id == level_subject_id,
            TeacherAssignment.is_active.is_(True),
        )
        if effective_on is not None:
            query = query.where(
                TeacherAssignment.effective_from <= effective_on,
                or_(
                    TeacherAssignment.effective_to.is_(None),
                    TeacherAssignment.effective_to >= effective_on,
                ),
            )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_assignment_effective_on(
        db: AsyncSession,
        teacher_id: UUID,
        class_id: UUID,
        level_subject_id: UUID,
        *,
        effective_on: date,
        lock: bool = False,
    ) -> TeacherAssignment | None:
        """Return the most recent assignment row valid on an explicit historical date."""
        query = (
            select(TeacherAssignment)
            .where(
                TeacherAssignment.teacher_id == teacher_id,
                TeacherAssignment.class_id == class_id,
                TeacherAssignment.level_subject_id == level_subject_id,
                TeacherAssignment.effective_from <= effective_on,
                or_(
                    TeacherAssignment.effective_to.is_(None),
                    TeacherAssignment.effective_to >= effective_on,
                ),
            )
            .order_by(
                TeacherAssignment.effective_from.desc(),
                TeacherAssignment.id.desc(),
            )
            .limit(1)
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalars().first()

    @staticmethod
    async def get_active_assignment_for_class_level_subject(
        db: AsyncSession,
        class_id: UUID,
        level_subject_id: UUID,
        *,
        effective_on: date | None = None,
        lock: bool = False,
    ) -> TeacherAssignment | None:
        """Return the active teacher assignment for a concrete arm/subject pair."""
        query = select(TeacherAssignment).where(
            TeacherAssignment.class_id == class_id,
            TeacherAssignment.level_subject_id == level_subject_id,
            TeacherAssignment.is_active.is_(True),
        )
        if effective_on is not None:
            query = query.where(
                TeacherAssignment.effective_from <= effective_on,
                or_(
                    TeacherAssignment.effective_to.is_(None),
                    TeacherAssignment.effective_to >= effective_on,
                ),
            )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_assignments_for_teacher(
        db: AsyncSession,
        teacher_id: UUID,
        *,
        active_only: bool = True,
        effective_on: date | None = None,
    ) -> list[TeacherAssignment]:
        query = select(TeacherAssignment).where(
            TeacherAssignment.teacher_id == teacher_id
        )
        if active_only:
            query = query.where(TeacherAssignment.is_active.is_(True))
        if effective_on is not None:
            query = query.where(
                TeacherAssignment.effective_from <= effective_on,
                or_(
                    TeacherAssignment.effective_to.is_(None),
                    TeacherAssignment.effective_to >= effective_on,
                ),
            )
        result = await db.execute(
            query.order_by(
                TeacherAssignment.class_id.asc(),
                TeacherAssignment.level_subject_id.asc(),
                TeacherAssignment.effective_from.desc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_assignments_for_level_subject(
        db: AsyncSession,
        level_subject_id: UUID,
        *,
        active_only: bool = True,
    ) -> list[TeacherAssignment]:
        query = select(TeacherAssignment).where(
            TeacherAssignment.level_subject_id == level_subject_id
        )
        if active_only:
            query = query.where(TeacherAssignment.is_active.is_(True))
        result = await db.execute(
            query.order_by(
                TeacherAssignment.class_id.asc(),
                TeacherAssignment.teacher_id.asc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def active_assignment_exists(
        db: AsyncSession,
        teacher_id: UUID,
        class_id: UUID,
        level_subject_id: UUID,
        *,
        effective_on: date | None = None,
    ) -> bool:
        conditions = [
            TeacherAssignment.teacher_id == teacher_id,
            TeacherAssignment.class_id == class_id,
            TeacherAssignment.level_subject_id == level_subject_id,
            TeacherAssignment.is_active.is_(True),
        ]
        if effective_on is not None:
            conditions.extend(
                [
                    TeacherAssignment.effective_from <= effective_on,
                    or_(
                        TeacherAssignment.effective_to.is_(None),
                        TeacherAssignment.effective_to >= effective_on,
                    ),
                ]
            )
        query = select(exists().where(*conditions))
        return bool(await db.scalar(query))

    @staticmethod
    async def teacher_has_level_subject_assignment(
        db: AsyncSession,
        teacher_id: UUID,
        level_subject_id: UUID,
        *,
        effective_on: date | None = None,
    ) -> bool:
        """Check question-authoring eligibility for a shared level-subject bank."""
        conditions = [
            TeacherAssignment.teacher_id == teacher_id,
            TeacherAssignment.level_subject_id == level_subject_id,
            TeacherAssignment.is_active.is_(True),
        ]
        if effective_on is not None:
            conditions.extend(
                [
                    TeacherAssignment.effective_from <= effective_on,
                    or_(
                        TeacherAssignment.effective_to.is_(None),
                        TeacherAssignment.effective_to >= effective_on,
                    ),
                ]
            )
        query = select(exists().where(*conditions))
        return bool(await db.scalar(query))

    @staticmethod
    async def save_assignment(
        db: AsyncSession,
        assignment: TeacherAssignment,
    ) -> TeacherAssignment:
        db.add(assignment)
        await db.flush()
        return assignment

    @staticmethod
    async def save_assignments(
        db: AsyncSession,
        assignments: Sequence[TeacherAssignment],
    ) -> list[TeacherAssignment]:
        rows = list(assignments)
        if not rows:
            return []
        db.add_all(rows)
        await db.flush()
        return rows

    # ========================== #
    # STUDENT ENROLLMENTS
    # ========================== #

    @staticmethod
    async def add_enrollment(
        db: AsyncSession,
        student_enrollment: StudentEnrollment,
    ) -> StudentEnrollment:
        db.add(student_enrollment)
        await db.flush()
        return student_enrollment

    @staticmethod
    async def add_enrollments(
        db: AsyncSession,
        enrollments: Sequence[StudentEnrollment],
    ) -> list[StudentEnrollment]:
        rows = list(enrollments)
        if not rows:
            return []
        db.add_all(rows)
        await db.flush()
        return rows

    @staticmethod
    async def get_enrollment_by_id(
        db: AsyncSession,
        enrollment_id: UUID,
        *,
        lock: bool = False,
    ) -> StudentEnrollment | None:
        query = select(StudentEnrollment).where(StudentEnrollment.id == enrollment_id)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_enrollment_by_weave_id(
        db: AsyncSession,
        weave_enrollment_id: str,
        *,
        lock: bool = False,
    ) -> StudentEnrollment | None:
        query = select(StudentEnrollment).where(
            StudentEnrollment.weave_enrollment_id == weave_enrollment_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_current_enrollment_by_weave_student_id(
        db: AsyncSession,
        weave_student_id: str,
        *,
        lock: bool = False,
    ) -> StudentEnrollment | None:
        query = select(StudentEnrollment).where(
            StudentEnrollment.weave_student_id == weave_student_id,
            StudentEnrollment.is_current.is_(True),
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_current_enrollment_by_admission_number(
        db: AsyncSession,
        admission_number: str,
        *,
        lock: bool = False,
    ) -> StudentEnrollment | None:
        query = select(StudentEnrollment).where(
            StudentEnrollment.admission_number == admission_number,
            StudentEnrollment.is_current.is_(True),
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_enrollment_history_for_student(
        db: AsyncSession,
        weave_student_id: str,
    ) -> list[StudentEnrollment]:
        result = await db.execute(
            select(StudentEnrollment)
            .where(StudentEnrollment.weave_student_id == weave_student_id)
            .order_by(
                StudentEnrollment.started_on.desc(),
                StudentEnrollment.id.desc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_enrollments_for_class(
        db: AsyncSession,
        session_id: UUID,
        class_id: UUID,
        *,
        current_only: bool = True,
    ) -> list[StudentEnrollment]:
        query = select(StudentEnrollment).where(
            StudentEnrollment.session_id == session_id,
            StudentEnrollment.class_id == class_id,
        )
        if current_only:
            query = query.where(StudentEnrollment.is_current.is_(True))
        result = await db.execute(
            query.order_by(
                StudentEnrollment.display_name.asc(),
                StudentEnrollment.admission_number.asc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_enrollments_for_classes(
        db: AsyncSession,
        session_id: UUID,
        class_ids: Sequence[UUID],
        *,
        current_only: bool = True,
    ) -> list[StudentEnrollment]:
        if not class_ids:
            return []
        query = select(StudentEnrollment).where(
            StudentEnrollment.session_id == session_id,
            StudentEnrollment.class_id.in_(class_ids),
        )
        if current_only:
            query = query.where(StudentEnrollment.is_current.is_(True))
        result = await db.execute(
            query.order_by(
                StudentEnrollment.class_id.asc(),
                StudentEnrollment.display_name.asc(),
                StudentEnrollment.admission_number.asc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def save_enrollment(
        db: AsyncSession,
        enrollment: StudentEnrollment,
    ) -> StudentEnrollment:
        db.add(enrollment)
        await db.flush()
        return enrollment

    @staticmethod
    async def save_enrollments(
        db: AsyncSession,
        enrollments: Sequence[StudentEnrollment],
    ) -> list[StudentEnrollment]:
        rows = list(enrollments)
        if not rows:
            return []
        db.add_all(rows)
        await db.flush()
        return rows

    # ========================== #
    # SYNC STATE
    # ========================== #

    @staticmethod
    async def add_sync_state(
        db: AsyncSession,
        sync_state: AcademicSyncState,
    ) -> AcademicSyncState:
        db.add(sync_state)
        await db.flush()
        return sync_state

    @staticmethod
    async def get_sync_state_by_scope(
        db: AsyncSession,
        scope: str,
        *,
        lock: bool = False,
    ) -> AcademicSyncState | None:
        query = select(AcademicSyncState).where(AcademicSyncState.scope == scope)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def save_sync_state(
        db: AsyncSession,
        sync_state: AcademicSyncState,
    ) -> AcademicSyncState:
        db.add(sync_state)
        await db.flush()
        return sync_state
