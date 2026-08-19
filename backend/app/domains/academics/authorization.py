# ==================================================#
# backend.app.domains.academics.authorization.py
# ==================================================#


from __future__ import annotations

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academics.repository import AcademicRepository
from app.domains.auth.models import LocalActor
from app.core.exceptions import AcademicAuthorizationError, AcademicScopeError
from backend.app.domains.academics.models import (
    AcademicClass,
    CurriculumSubject,
    TeacherAssignment,
)
from sqlalchemy import select


class AcademicAuthorizationService:
    """
    Central authorization layer for actions that depend
    on synchronized Weave academic data
    """

    @staticmethod
    async def require_can_author_curriculum_subject(
        db: AsyncSession, *, actor: LocalActor, curriculum_subject_id: UUID
    ) -> None:
        """
        Ensure the current actor can author content for a CurriculumSubject

        Admin:
            can author for any active synchronized CurriculumSubject


        Teacher:
            Must have an active synchronized teacher membership and at least
            one currently effective assignment for the CurriculumSubject
        """

        # Authenticated local actor must still be active

        if not actor.is_active:
            raise AcademicAuthorizationError("Active local actor is required")

        # Curriculum subject must still exist locally
        # already excludes rows where source_deteled is not NULL

        curriculum_subject = await AcademicRepository.get_curriculum_subject_by_id(
            db, curriculum_subject_id
        )

        if curriculum_subject is None:
            raise AcademicScopeError(
                "curriculum subject does not exist or is no longer available"
            )

        if not curriculum_subject.is_active:
            raise AcademicScopeError("curriculum subject is inactive")

        # for admin they do not require a teacher assignment

        if actor.role == "admin":
            return

        if actor.role != "teacher":
            raise AcademicAuthorizationError(
                "Only administrators and teachers can author academic content"
            )

        # teacher must have a weave membership identity

        if actor.weave_membership_id is None:
            raise AcademicAuthorizationError(
                "Teacher is missing a Weave membership identity"
            )

        try:
            teacher_membership_id = UUID(actor.weave_membership_id)

        except ValueError as exc:
            raise AcademicAuthorizationError(
                "Teacher has an invalid Weave membership identity"
            ) from exc

        # confirm the synchronized teacher still exists and is active

        teacher = await AcademicRepository.get_teacher_by_membership_id(
            db, teacher_membership_id
        )

        if teacher is None:
            raise AcademicAuthorizationError(
                "Teacher is not available in the local academic projection"
            )

        if teacher.status != "active":
            raise AcademicAuthorizationError("Teacher is not currently active")

        # check whether the teacher has at least one current assignment

        has_assignment = (
            await AcademicRepository.teacher_has_curriculum_subject_assignment(
                db, teacher_membership_id, curriculum_subject_id
            )
        )

        if not has_assignment:
            raise AcademicAuthorizationError(
                "Teacher does not have an active assignment for this curriculum subject"
            )

    @staticmethod
    async def require_teacher_assignment_for_class(
        db: AsyncSession,
        *,
        actor: LocalActor,
        class_id: UUID,
        curriculum_subject_id: UUID,
    ):
        """
        Ensure the actor can work with a specific class + curriculum subject

        Admin:
            Allowed for any valid live academic scope


        Teacher:
            Must have a current live assignment for this exact
            class + curriculum subject
        """

        if not actor.is_active:
            raise AcademicAuthorizationError("Active local actor is required")

        classroom = await AcademicRepository.get_class_by_id(db, class_id)

        if classroom is None:
            raise AcademicScopeError("Class does not exist or is no longer available")

        if not classroom.is_active:
            raise AcademicScopeError("class is inactive")

        curriculum_subject = await AcademicRepository.get_curriculum_subject_by_id(
            db, curriculum_subject_id
        )

        if curriculum_subject is None:
            raise AcademicScopeError(
                "Curriculum subject does not exist or is no longer available"
            )

        if not curriculum_subject.is_active:
            raise AcademicScopeError("Curriculum subject is inactive")

        if actor.role == "admin":
            return

        if actor.role != "teacher":
            raise AcademicAuthorizationError(
                "Only administrators and teachers can access this academic scope"
            )

        if actor.weave_membership_id is None:
            raise AcademicAuthorizationError(
                "Teacher is missing a Weave membership identity"
            )

        try:
            teacher_membership_id = UUID(actor.weave_membership_id)

        except ValueError as exc:
            raise AcademicAuthorizationError(
                "Teacher has an invalid Weave membership identity"
            ) from exc

        teacher = await AcademicRepository.get_teacher_by_membership_id(
            db, teacher_membership_id
        )

        if teacher is None:
            raise AcademicAuthorizationError(
                "Teacher is not available in the local academic projection"
            )

        if teacher.status != "active":
            raise AcademicAuthorizationError("Teacher is not currently active")

        assignment = await AcademicRepository.get_active_assignment_for_scope(
            db,
            teacher_membership_id=teacher_membership_id,
            class_id=class_id,
            curriculum_subject_id=curriculum_subject_id,
        )

        if assignment is None:
            raise AcademicAuthorizationError(
                "Teacher does not have an active assignment "
                "for this class and curriculum subject"
            )

    @staticmethod
    async def list_authorable_curriculum_subjects_for_teacher(
        db: AsyncSession, *, teacher_membership_id: UUID
    ) -> list[CurriculumSubject]:
        """
        Return distince live CurriculumSubjects for which the teacher
        currently has at least one effective assignment
        """

        query = (
            select(CurriculumSubject)
            .join(
                TeacherAssignment,
                TeacherAssignment.curriculum_subject_id == CurriculumSubject.id,
            )
            .where(
                TeacherAssignment.teacher_membership_id == teacher_membership_id,
                TeacherAssignment.is_active.is_(True),
                TeacherAssignment.source_deleted_at.is_(None),
                CurriculumSubject.is_active.is_(True),
                CurriculumSubject.source_deleted_at.is_(None),
                *AcademicRepository._effective_assignment_predicates(),
            )
            .distinct()
            .order_by(CurriculumSubject.subject_id.asc())
        )

        result = await db.execute(query)

        return list(result.scalars().all())

    @staticmethod
    async def list_actor_authorable_curriculum_subjects(
        db: AsyncSession, *, actor: LocalActor
    ) -> list[CurriculumSubject]:
        """
        Return CurriculumSubjects the actor is allowed
        to author content for

        Admin:
            can access every live active CurriculumSubject


        Teacher:
            can access only CurriculumSubject for which they have
            at least one current effective assignment
        """

        if not actor.is_active:
            raise AcademicAuthorizationError("Active local actor is required")

        if actor.role == "admin":
            return await AcademicRepository.list_all_active_curriculum_subjects(db)

        if actor.role != "teacher":
            raise AcademicAuthorizationError(
                "Only administrators and teachers can author academic content"
            )

        if actor.weave_membership_id is None:
            raise AcademicAuthorizationError(
                "Teachr is missing a Weave membership identity"
            )

        try:
            teacher_membership_id = UUID(actor.weave_membership_id)

        except ValueError as exc:
            raise AcademicAuthorizationError(
                "Teacher has an invalid Weave membership identity"
            ) from exc

        teacher = await AcademicRepository.get_teacher_by_membership_id(
            db,
            teacher_membership_id,
        )

        if teacher is None:
            raise AcademicAuthorizationError(
                "Teacher is not available in the local academic projection"
            )

        if teacher.status != "active":
            raise AcademicAuthorizationError("Teacher is not currently active")

        # ---------------------------------------------------------
        # Return only subjects backed by a current effective
        # TeacherAssignment.
        # ---------------------------------------------------------

        return await AcademicRepository.list_authorable_curriculum_subjects_for_teacher(
            db,
            teacher_membership_id=teacher_membership_id,
        )

    @staticmethod
    async def list_actor_targetable_classes(
        db: AsyncSession,
        *,
        actor: LocalActor,
        curriculum_subject_id: UUID,
    ) -> list[AcademicClass]:
        """
        Return classes the actor may target for the given CurriculumSubject.

        Admin:
            May target any live class belonging to the CurriculumSubject's
            academic level.

        Teacher:
            May target only classes for which they currently have an
            effective TeacherAssignment to this CurriculumSubject.
        """

        if not actor.is_active:
            raise AcademicAuthorizationError("Active local actor is required")

        curriculum_subject = await AcademicRepository.get_curriculum_subject_by_id(
            db,
            curriculum_subject_id,
        )

        if curriculum_subject is None:
            raise AcademicScopeError(
                "Curriculum subject does not exist or is no longer available"
            )

        if not curriculum_subject.is_active:
            raise AcademicScopeError("Curriculum subject is inactive")

        if actor.role == "admin":
            return await AcademicRepository.list_classes_for_curriculum_subject(
                db,
                curriculum_subject_id=curriculum_subject_id,
            )

        if actor.role != "teacher":
            raise AcademicAuthorizationError(
                "Only administrators and teachers can access this academic scope"
            )

        if actor.weave_membership_id is None:
            raise AcademicAuthorizationError(
                "Teacher is missing a Weave membership identity"
            )

        try:
            teacher_membership_id = UUID(actor.weave_membership_id)
        except ValueError as exc:
            raise AcademicAuthorizationError(
                "Teacher has an invalid Weave membership identity"
            ) from exc

        teacher = await AcademicRepository.get_teacher_by_membership_id(
            db,
            teacher_membership_id,
        )

        if teacher is None:
            raise AcademicAuthorizationError(
                "Teacher is not available in the local academic projection"
            )

        if teacher.status != "active":
            raise AcademicAuthorizationError("Teacher is not currently active")

        return await AcademicRepository.list_teacher_classes_for_curriculum_subject(
            db,
            teacher_membership_id=teacher_membership_id,
            curriculum_subject_id=curriculum_subject_id,
        )
