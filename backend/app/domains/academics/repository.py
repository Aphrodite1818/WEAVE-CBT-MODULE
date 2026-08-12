#========================================#
#backend.app.domains.academics.repository
#========================================#

"""Persistence operations for academic data projected from Weave.

The repository reads and writes local SQLAlchemy projection models. It does not
call Weave, enforce business rules, commit transactions, or delete Weave-owned
data. Services own synchronization workflows and transaction boundaries.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

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
    StudentEnrollment,
    TeacherAssignment,
)
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

#==========================#
#REPOSITORY
#==========================#

class AcademicRepository:
    """Provide database operations for local academic projections."""


    @staticmethod
    async def add_session(
        db : AsyncSession,
        academic_session : AcademicSession
    ) -> AcademicSession:
        """Add a session to the unit of work and flush pending changes."""

        db.add(academic_session)
        await db.flush()
        return academic_session



    @staticmethod
    async def get_session_by_id(
        db : AsyncSession,
        academic_session_id : UUID,
        *,
        lock : bool = False
    ) -> AcademicSession | None:
        """Return a session by local ID, optionally locking its row."""

        query = select(AcademicSession).where(
            AcademicSession.id == academic_session_id
        )

        if lock:
            query = query.with_for_update()

        result = await db.execute(query)

        return result.scalar_one_or_none()



    @staticmethod
    async def get_session_by_weave_id(
        db : AsyncSession,
        academic_session_weave_id : str,
        *,
        lock : bool = False
    ) -> AcademicSession | None:
        """Return a session by Weave ID, optionally locking its row."""

        query = select(AcademicSession).where(
            AcademicSession.weave_session_id == academic_session_weave_id
        )

        if lock:
            query = query.with_for_update()


        result = await db.execute(query)

        return result.scalar_one_or_none()



    @staticmethod
    async def get_current_session(
        db : AsyncSession,
        *,
        lock : bool = False
    ) -> AcademicSession | None:
        """Return the current session, optionally locking its row."""

        query = select(AcademicSession).where(
            AcademicSession.is_current.is_(True)
        )

        if lock:
            query = query.with_for_update()


        result = await db.execute(query)


        return result.scalar_one_or_none()




    @staticmethod
    async def list_sessions(
        db : AsyncSession
    ) -> list[AcademicSession]:
        """Return all sessions, ordered from newest to oldest."""

        query = select(AcademicSession).order_by(
            AcademicSession.starts_on.desc().null_last(),
            AcademicSession.name.desc()
            )

        result = await db.execute(query)

        return list(result.scalars().all())






    @staticmethod
    async def add_term(
        db : AsyncSession,
        term : AcademicTerm
    ) -> AcademicTerm:
        """Add a term to the unit of work and flush pending changes."""

        db.add(term)
        await db.flush()
        return term



    @staticmethod
    async def get_term_by_id(
        db : AsyncSession,
        academic_term_id : UUID,
        *,
        lock : bool = False
    ) -> AcademicTerm | None:
        """Return a term by local ID, optionally locking its row."""

        query = select(AcademicTerm).where(
            AcademicTerm.id == academic_term_id
        )

        if lock:
            query = query.with_for_update()


        result = await db.execute(query)

        return result.scalar_one_or_none()




    @staticmethod
    async def get_term_by_weave_id(
        db : AsyncSession,
        academic_term_weave_id : str,
        *,
        lock : bool = False
    ) -> AcademicTerm | None:
        """Return a term by Weave ID, optionally locking its row."""

        query = select(AcademicTerm).where(
            AcademicTerm.weave_term_id == academic_term_weave_id
        )

        if lock:
            query = query.with_for_update()


        result = await db.execute(query)

        return result.scalar_one_or_none()




    @staticmethod
    async def get_current_term(
        db : AsyncSession,
        session_id : UUID,
        *,
        lock : bool = False
    ) -> AcademicTerm | None:
        """Return a session's current term, optionally locking its row."""

        query = select(AcademicTerm).where(
            AcademicTerm.session_id == session_id ,
            AcademicTerm.is_current.is_(True)
        )

        if lock:
            query = query.with_for_update()


        result = await db.execute(query)

        return result.scalar_one_or_none()



    @staticmethod
    async def list_terms_for_session(
        db : AsyncSession,
        session_id : UUID
    ) -> list[AcademicTerm]:
        """Return a session's terms in chronological order."""

        query = select(AcademicTerm).where(
            AcademicTerm.session_id == session_id
        ).order_by(
            AcademicTerm.starts_on.asc().nulls_last(),
            AcademicTerm.name.asc()
        )

        result = await db.execute(query)

        return list(result.scalars().all())


    @staticmethod
    async def save_term(
        db : AsyncSession,
        term : AcademicTerm
    ) -> AcademicTerm:
        """Attach a term to the unit of work and flush pending changes."""
        db.add(term)
        await db.flush()
        return term




    @staticmethod
    async def add_level(
        db : AsyncSession,
        level : AcademicLevel
    ) -> AcademicLevel:
        """Add a level to the unit of work and flush pending changes."""

        db.add(level)
        await db.flush()
        return level


    @staticmethod
    async def get_level_by_id(
        db : AsyncSession,
        academic_level_id : UUID,
        *,
        lock : bool = False
    ) -> AcademicLevel | None:
        """Return a level by local ID, optionally locking its row."""

        query = select(AcademicLevel).where(
            AcademicLevel.id == academic_level_id
        )

        if lock:
            query = query.with_for_update()


        result = await db.execute(query)

        return result.scalar_one_or_none()



    @staticmethod
    async def get_level_by_weave_id(
        db : AsyncSession,
        weave_academic_level_id : str,
        *,
        lock : bool = False
    ):
        """Return a level by Weave ID, optionally locking its row."""

        query = select(AcademicLevel).where(
            AcademicLevel.weave_level_id == weave_academic_level_id
        )

        if lock:
            query = query.with_for_update()


        result = await db.execute(query)

        return result.scalar_one_or_none()



    @staticmethod
    async def list_active_levels(
        db : AsyncSession
    ) -> list[AcademicLevel]:
        """Return active levels in display order."""

        query = select(AcademicLevel).where(
            AcademicLevel.is_active.is_(True)
        ).order_by(
            AcademicLevel.position.asc().nulls_last(),
            AcademicLevel.name.asc()
        )

        result = await db.execute(query)

        return list(result.scalars().all())



    @staticmethod
    async def save_level(
        db : AsyncSession,
        level : AcademicLevel
    ) -> AcademicLevel:
        """Attach a level to the unit of work and flush pending changes."""
        db.add(level)
        await db.flush()
        return level





    @staticmethod
    async def add_class(
        db : AsyncSession,
        academic_class : AcademicClass
    ) -> AcademicClass:
        """Add a class to the unit of work and flush pending changes."""
        db.add(academic_class)
        await db.flush()
        return academic_class


    @staticmethod
    async def get_class_by_id(
        db : AsyncSession,
        class_id : UUID,
        *,
        lock : bool = False
    ) -> AcademicClass | None:
        """Return a class by local ID, optionally locking its row."""

        query = select(AcademicClass).where(
            AcademicClass.id == class_id
        )


        if lock:
            query = query.with_for_update()

        result = await db.execute(query)

        return result.scalar_one_or_none()



    @staticmethod
    async def get_class_by_weave_id(
        db : AsyncSession,
        weave_class_id : str,
        *,
        lock : bool = False
    ) -> AcademicClass | None:
        """Return a class by Weave ID, optionally locking its row."""

        query = select(AcademicClass).where(
            AcademicClass.weave_class_id == weave_class_id
        )


        if lock:
            query = query.with_for_update()


        result = await db.execute(query)


        return result.scalar_one_or_none()




    @staticmethod
    async def list_classes_for_level(
        db : AsyncSession,
        level_id : UUID,
        *,
        active_only : bool = True
    ) -> list[AcademicClass]:
        """Return classes for a level, optionally excluding inactive rows."""

        query = select(AcademicClass).where(
            AcademicClass.level_id == level_id
        )


        if active_only:
            query = query.where(
                AcademicClass.is_active.is_(True)
            )



        result = await db.execute(
            query.order_by(
                AcademicClass.name.asc(),
                AcademicClass.arm.asc().nulls_last()
            )
        )

        return list(result.scalars().all())




    @staticmethod
    async def list_classes_by_ids(
        db : AsyncSession,
        class_ids : Sequence[UUID],
        *,
        active_only : bool = False
    ):# -> list[Any] | list[AcademicClass]:
        """Return classes matching the supplied local IDs."""

        if not class_ids:
            return []


        query = select(AcademicClass).where(
            AcademicClass.id.in_(class_ids)
        )

        if active_only:
            query = query.where(
                AcademicClass.is_active.is_(True)
            )


        result = await db.execute(query)

        return list(result.scalars().all())




    @staticmethod
    async def save_class(
        db : AsyncSession,
        academic_class : AcademicClass
    ) -> AcademicClass:
        """Attach a class to the unit of work and flush pending changes."""
        db.add(academic_class)
        await db.flush()
        return academic_class




    @staticmethod
    async def add_subject(
        db : AsyncSession,
        subject : AcademicSubject
    ) -> AcademicSubject:
        """Add a subject to the unit of work and flush pending changes."""

        db.add(subject)
        await db.flush()
        return subject



    @staticmethod
    async def get_subject_by_id(
        db : AsyncSession,
        subject_id : UUID,
        *,
        lock : bool = False
    ) -> AcademicSubject | None:
        """Return a subject by local ID, optionally locking its row."""

        query = select(AcademicSubject).where(
            AcademicSubject.id == subject_id
        )

        if lock:
            query = query.with_for_update()


        result = await db.execute(query)

        return result.scalar_one_or_none()




    @staticmethod
    async def get_subject_by_weave_id(
        db : AsyncSession,
        weave_id : str ,
        *,
        lock : bool = False
    ) -> AcademicSubject | None:
        """Return a subject by Weave ID, optionally locking its row."""

        query = select(AcademicSubject).where(
            AcademicSubject.weave_subject_id == weave_id
        )


        if lock:
            query = query.with_for_update()


        result = await db.execute(query)

        return result.scalar_one_or_none()


    @staticmethod
    async def list_active_subjects(
        db : AsyncSession
    ) -> list[AcademicSubject]:
        """Return active subjects ordered by name."""

        query = select(AcademicSubject).where(
            AcademicSubject.is_active.is_(True)
        ).order_by(
            AcademicSubject.name.asc()
        )

        result = await db.execute(query)

        return list(result.scalars().all())




    @staticmethod
    async def save_subject(
        db : AsyncSession,
        subject : AcademicSubject
    ) -> AcademicSubject:
        """Attach a subject to the unit of work and flush pending changes."""
        db.add(subject)
        await db.flush()
        return subject






    @staticmethod
    async def add_level_subject(
        db : AsyncSession,
        level_subject : AcademicLevelSubject
    ) -> AcademicLevelSubject:
        """Add a level-subject mapping and flush pending changes."""

        db.add(level_subject)
        await db.flush()
        return level_subject





    @staticmethod
    async def get_level_subject_by_id(
        db : AsyncSession,
        level_subject_id : UUID,
        *,
        lock : bool = False
    ) -> AcademicLevelSubject | None:
        """Return a level-subject mapping by local ID."""


        query = select(AcademicLevelSubject).where(
            AcademicLevelSubject.id == level_subject_id
        )

        if lock:
            query = query.with_for_update()



        result = await db.execute(query)

        return result.scalar_one_or_none()






    @staticmethod
    async def get_level_subject_by_weave_id(
        db : AsyncSession,
        weave_mapping_id : str,
        *,
        lock : bool = False
    ) -> AcademicLevelSubject | None:
        """Return a level-subject mapping by Weave ID."""


        query = select(AcademicLevelSubject).where(
            AcademicLevelSubject.weave_mapping_id == weave_mapping_id
        )

        if lock:
            query = query.with_for_update()



        result = await db.execute(query)

        return result.scalar_one_or_none()




    @staticmethod
    async def get_level_subject(
        db : AsyncSession,
        level_id : UUID,
        subject_id : UUID,
        *,
        lock : bool = False
    ) -> AcademicLevelSubject | None:
        """Return the mapping for a level and subject pair."""


        query = select(AcademicLevelSubject).where(
            AcademicLevelSubject.level_id == level_id,
            AcademicLevelSubject.subject_id == subject_id
        )



        if lock:
            query = query.with_for_update()



        result = await db.execute(query)

        return result.scalar_one_or_none()




    @staticmethod
    async def list_subjects_for_level(
        db : AsyncSession,
        level_id : UUID,
        *,
        active_only : bool = False
    ) -> list[AcademicSubject]:
        """Return subjects mapped to a level, optionally only active ones."""

        query = (
            select(AcademicSubject).join(
            AcademicLevelSubject,
            AcademicLevelSubject.subject_id == AcademicSubject.id,

        ).where(
            AcademicLevelSubject.level_id == level_id
        )
        )

        if active_only:
            query = query.where(
                AcademicLevelSubject.is_active.is_(True),
                AcademicSubject.is_active.is_(True)
            )


        result = await db.execute(
            query.order_by(
                AcademicSubject.name.asc()
            )
        )

        return list(result.scalars().unique().all())




    @staticmethod
    async def active_level_subject_exists(
        db : AsyncSession,
        level_id : UUID,
        subject_id : UUID
    ) -> bool:
        """Return whether an active mapping exists for the level and subject."""
        query = select(
            exists().where(
                AcademicLevelSubject.level_id == level_id,
                AcademicLevelSubject.subject_id == subject_id,
                AcademicLevelSubject.is_active.is_(True)
            )
        )
        return bool(await db.scalar(query))



    @staticmethod
    async def save_level_subject(
        db : AsyncSession,
        level_subject : AcademicLevelSubject
    ) -> AcademicLevelSubject:
        """Attach a level-subject mapping and flush pending changes."""
        db.add(level_subject)
        await db.flush()
        return level_subject





    @staticmethod
    async def add_component(
        db : AsyncSession,
        component : AssessmentComponent
    ) -> AssessmentComponent:
        """Add an assessment component and flush pending changes."""
        db.add(component)
        await db.flush()
        return component


    @staticmethod
    async def get_component_by_id(
        db : AsyncSession,
        component_id : UUID,
        *,
        lock : bool = False
    ) -> AssessmentComponent | None:
        """Return an assessment component by local ID."""

        query = select(AssessmentComponent).where(
            AssessmentComponent.id == component_id
        )

        if lock:
            query = query.with_for_update()

        result = await db.execute(query)

        return result.scalar_one_or_none()





    @staticmethod
    async def get_component_by_weave_id(
        db : AsyncSession,
        weave_component_id : str,
        *,
        lock : bool = False
    ) -> AssessmentComponent | None:
        """Return an assessment component by Weave ID."""

        query = select(AssessmentComponent).where(
            AssessmentComponent.weave_component_id == weave_component_id
        )

        if lock:
            query = query.with_for_update()

        result = await db.execute(query)

        return result.scalar_one_or_none()



    @staticmethod
    async def list_components_for_term(
        db : AsyncSession,
        term_id : UUID,
        *,
        active_only : bool = True
    ) -> list[AssessmentComponent]:
        """Return a term's components in display order."""

        query = select(AssessmentComponent).where(
            AssessmentComponent.term_id == term_id
        )

        if active_only:
            query = query.where(
                AssessmentComponent.is_active.is_(True)
            )


        result = await db.execute(
            query.order_by(
                AssessmentComponent.position.asc(),
                AssessmentComponent.name.asc()
            )
        )

        return list(result.scalars().all())


    @staticmethod
    async def save_component(
        db : AsyncSession,
        component : AssessmentComponent
    ) -> AssessmentComponent:
        """Attach an assessment component and flush pending changes."""
        db.add(component)
        await db.flush()
        return component





    @staticmethod
    async def add_teacher(
        db : AsyncSession,
        teacher : AcademicTeacher
    ) -> AcademicTeacher:
        """Add a teacher projection and flush pending changes."""

        db.add(teacher)
        await db.flush()
        return teacher




    @staticmethod
    async def get_teacher_by_id(
        db : AsyncSession,
        teacher_id : UUID,
        *,
        lock : bool = False
    ) -> AcademicTeacher | None:
        """Return a teacher by local ID, optionally locking its row."""

        query = select(AcademicTeacher).where(
            AcademicTeacher.id == teacher_id
        )


        if lock:
            query = query.with_for_update()

        result = await db.execute(query)

        return result.scalar_one_or_none()




    @staticmethod
    async def get_teacher_by_weave_id(
        db : AsyncSession,
        weave_teacher_id : str,
        *,
        lock : bool = False
    ) -> AcademicTeacher | None:
        """Return a teacher by Weave ID, optionally locking its row."""



        query = select(AcademicTeacher).where(
            AcademicTeacher.weave_teacher_id == weave_teacher_id
        )


        if lock:
            query = query.with_for_update()

        result = await db.execute(query)

        return result.scalar_one_or_none()




    @staticmethod
    async def get_teacher_by_membership_id(
        db : AsyncSession,
        membership_id : str,
        *,
        lock : bool = False
    ) -> AcademicTeacher | None:
        """Return a teacher by membership ID, optionally locking its row."""


        query = select(AcademicTeacher).where(
            AcademicTeacher.weave_membership_id == membership_id
        )


        if lock:
            query = query.with_for_update()

        result = await db.execute(query)

        return result.scalar_one_or_none()



    @staticmethod
    async def list_active_teachers(
        db: AsyncSession,
    ) -> list[AcademicTeacher]:
        """Return active teachers ordered by display name."""
        result = await db.execute(
            select(AcademicTeacher)
            .where(
                AcademicTeacher.is_active.is_(True),
            )
            .order_by(
                AcademicTeacher.display_name.asc(),
            )
        )

        return list(result.scalars().all())





    @staticmethod
    async def save_teacher(
        db : AsyncSession,
        teacher : AcademicTeacher
    ) -> AcademicTeacher:
        """Attach a teacher projection and flush pending changes."""
        db.add(teacher)
        await db.flush()
        return teacher





    @staticmethod
    async def add_assignment(
        db : AsyncSession,
        assignment : TeacherAssignment
    ) -> TeacherAssignment:
        """Add a teacher assignment and flush pending changes."""

        db.add(assignment)
        await db.flush()
        return assignment






    @staticmethod
    async def add_assignments(
        db : AsyncSession,
        assignments : Sequence[TeacherAssignment]
    ):# -> list[Any] | list[TeacherAssignment]:
        """Add teacher assignments and return the flushed rows."""
        rows = list(assignments)


        if not rows:
            return []


        db.add_all(rows)
        await db.flush()

        return rows



    @staticmethod
    async def get_assignment_by_id(
        db : AsyncSession,
        assignment_id : UUID,
        *,
        lock : bool  = False
    ) -> TeacherAssignment | None:
        """Return a teacher assignment by local ID."""

        query = select(TeacherAssignment).where(
            TeacherAssignment.id == assignment_id,
        )

        if lock:
            query = query.with_for_update()


        result = await db.execute(query)

        return result.scalar_one_or_none()




    @staticmethod
    async def get_assignment_by_weave_id(
        db : AsyncSession,
        weave_assignment_id : str,
        *,
        lock : bool  = False
    ) -> TeacherAssignment | None:
        """Return a teacher assignment by Weave ID."""

        query = select(TeacherAssignment).where(
            TeacherAssignment.weave_assignment_id == weave_assignment_id,
        )

        if lock:
            query = query.with_for_update()


        result = await db.execute(query)

        return result.scalar_one_or_none()





    @staticmethod
    async def get_assignment_for_scope(
        db : AsyncSession,
        teacher_id : UUID,
        session_id : UUID,
        class_id : UUID,
        subject_id : UUID,
        *,
        lock : bool = False
    ) -> TeacherAssignment | None:
        """Return the assignment matching a teacher's academic scope."""
        query = select(TeacherAssignment).where(
            TeacherAssignment.teacher_id == teacher_id,
            TeacherAssignment.session_id == session_id,
            TeacherAssignment.class_id == class_id ,
            TeacherAssignment.subject_id == subject_id
        )

        if lock:
            query = query.with_for_update()

        result = await db.execute(query)

        return result.scalar_one_or_none()





    @staticmethod
    async def list_assignments_for_teacher(
        db : AsyncSession,
        teacher_id : UUID,
        session_id : UUID,
        *,
        active_only : bool = True
    ) -> list[TeacherAssignment]:
        """Return a teacher's assignments for a session."""

        query = select(TeacherAssignment).where(
            TeacherAssignment.teacher_id == teacher_id,
            TeacherAssignment.session_id == session_id
        )


        if active_only:
            query = query.where(
                TeacherAssignment.is_active.is_(True)
            )



        result = await db.execute(
            query.order_by(
                TeacherAssignment.class_id.asc(),
                TeacherAssignment.subject_id.asc()
            )
        )

        return list(result.scalars().all())





    @staticmethod
    async def active_assignment_exists(
        db: AsyncSession,
        teacher_id: UUID,
        session_id: UUID,
        class_id: UUID,
        subject_id: UUID,
    ) -> bool:
        """Return whether an active assignment exists for the given scope."""
        query = select(
            exists().where(
                TeacherAssignment.teacher_id == teacher_id,
                TeacherAssignment.session_id == session_id,
                TeacherAssignment.class_id == class_id,
                TeacherAssignment.subject_id == subject_id,
                TeacherAssignment.is_active.is_(True),
            )
        )

        return bool(await db.scalar(query))

    @staticmethod
    async def save_assignment(
        db: AsyncSession,
        assignment: TeacherAssignment,
    ) -> TeacherAssignment:
        """Attach a teacher assignment and flush pending changes."""
        db.add(assignment)
        await db.flush()
        return assignment

    @staticmethod
    async def save_assignments(
        db: AsyncSession,
        assignments: Sequence[TeacherAssignment],
    ) -> list[TeacherAssignment]:
        """Attach teacher assignments and return the flushed rows."""
        rows = list(assignments)

        if not rows:
            return []

        db.add_all(rows)
        await db.flush()

        return rows






    @staticmethod
    async def add_enrollment(
        db : AsyncSession,
        student_enrollment : StudentEnrollment
    ) -> StudentEnrollment:
        """Add a student enrollment and flush pending changes."""

        db.add(student_enrollment)
        await db.flush()
        return student_enrollment



    @staticmethod
    async def add_enrollments(
        db : AsyncSession,
        enrollments : Sequence[StudentEnrollment]
    ):# -> list[Any] | list[StudentEnrollment]:
        """Add student enrollments and return the flushed rows."""

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
        """Return an enrollment by local ID, optionally locking its row."""
        query = select(StudentEnrollment).where(
            StudentEnrollment.id == enrollment_id,
        )

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
        """Return an enrollment by Weave enrollment ID."""
        query = select(StudentEnrollment).where(
            StudentEnrollment.weave_enrollment_id == weave_enrollment_id,
        )

        if lock:
            query = query.with_for_update()

        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_enrollment_by_weave_student_id(
        db: AsyncSession,
        session_id: UUID,
        weave_student_id: str,
        *,
        lock: bool = False,
    ) -> StudentEnrollment | None:
        """Return a session enrollment by Weave student ID."""
        query = select(StudentEnrollment).where(
            StudentEnrollment.session_id == session_id,
            StudentEnrollment.weave_student_id == weave_student_id,
        )

        if lock:
            query = query.with_for_update()

        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_enrollment_by_admission_number(
        db: AsyncSession,
        session_id: UUID,
        admission_number: str,
        *,
        lock: bool = False,
    ) -> StudentEnrollment | None:
        """Return a session enrollment by admission number."""
        query = select(StudentEnrollment).where(
            StudentEnrollment.session_id == session_id,
            StudentEnrollment.admission_number == admission_number,
        )

        if lock:
            query = query.with_for_update()

        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_enrollments_for_class(
        db: AsyncSession,
        session_id: UUID,
        class_id: UUID,
        *,
        active_only: bool = True,
    ) -> list[StudentEnrollment]:
        """Return a session's enrollments for one class."""
        query = select(StudentEnrollment).where(
            StudentEnrollment.session_id == session_id,
            StudentEnrollment.class_id == class_id,
        )

        if active_only:
            query = query.where(
                StudentEnrollment.is_active.is_(True),
            )

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
        active_only: bool = True,
    ) -> list[StudentEnrollment]:
        """Return a session's enrollments for the supplied classes."""
        if not class_ids:
            return []

        query = select(StudentEnrollment).where(
            StudentEnrollment.session_id == session_id,
            StudentEnrollment.class_id.in_(class_ids),
        )

        if active_only:
            query = query.where(
                StudentEnrollment.is_active.is_(True),
            )

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
        """Attach a student enrollment and flush pending changes."""
        db.add(enrollment)
        await db.flush()
        return enrollment

    @staticmethod
    async def save_enrollments(
        db: AsyncSession,
        enrollments: Sequence[StudentEnrollment],
    ) -> list[StudentEnrollment]:
        """Attach student enrollments and return the flushed rows."""
        rows = list(enrollments)

        if not rows:
            return []

        db.add_all(rows)
        await db.flush()

        return rows







    @staticmethod
    async def add_sync_state(
        db: AsyncSession,
        sync_state: AcademicSyncState,
    ) -> AcademicSyncState:
        """Add a synchronization state and flush pending changes."""
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
        """Return synchronization state for a scope."""
        query = select(AcademicSyncState).where(
            AcademicSyncState.scope == scope,
        )

        if lock:
            query = query.with_for_update()

        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def save_sync_state(
        db: AsyncSession,
        sync_state: AcademicSyncState,
    ) -> AcademicSyncState:
        """Attach a synchronization state and flush pending changes."""
        db.add(sync_state)
        await db.flush()
        return sync_state
