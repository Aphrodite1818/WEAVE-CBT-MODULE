# ==================================================#
# backend.app.domains.academics.authorization.py
# ==================================================#

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AcademicAuthorizationError, AcademicScopeError
from app.domains.academics.models import AcademicClass, CurriculumSubject
from app.domains.academics.repository import AcademicRepository
from app.domains.academics.service import AcademicEligibilityService
from app.domains.auth.models import LocalActor


class AcademicAuthorizationService:
    """Authorization rules backed by synchronized local academic projections."""

    @staticmethod
    async def require_can_author_curriculum_subject(
        db: AsyncSession,
        *,
        actor: LocalActor,
        curriculum_subject_id: UUID,
    ) -> None:
        """Require authoring access to one live CurriculumSubject."""

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
            return

        if actor.role != "teacher":
            raise AcademicAuthorizationError(
                "Only administrators and teachers can author academic content"
            )

        teacher_membership_id = AcademicAuthorizationService._teacher_membership_id(
            actor
        )

        await AcademicAuthorizationService._require_live_teacher(
            db,
            teacher_membership_id=teacher_membership_id,
        )

        has_assignment = (
            await AcademicRepository.teacher_has_curriculum_subject_assignment(
                db,
                teacher_membership_id,
                curriculum_subject_id,
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
    ) -> None:
        """Require access to one exact Class + CurriculumSubject scope."""

        if not actor.is_active:
            raise AcademicAuthorizationError("Active local actor is required")

        classroom = await AcademicRepository.get_class_by_id(
            db,
            class_id,
        )

        if classroom is None:
            raise AcademicScopeError("Class does not exist or is no longer available")

        if not classroom.is_active:
            raise AcademicScopeError("Class is inactive")

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
            return

        if actor.role != "teacher":
            raise AcademicAuthorizationError(
                "Only administrators and teachers can access this academic scope"
            )

        teacher_membership_id = AcademicAuthorizationService._teacher_membership_id(
            actor
        )

        await AcademicAuthorizationService._require_live_teacher(
            db,
            teacher_membership_id=teacher_membership_id,
        )

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
    async def list_actor_authorable_curriculum_subjects(
        db: AsyncSession,
        *,
        actor: LocalActor,
    ) -> list[CurriculumSubject]:
        """Return distinct CurriculumSubjects the actor may author content for."""

        if not actor.is_active:
            raise AcademicAuthorizationError("Active local actor is required")

        if actor.role == "admin":
            return await AcademicRepository.list_all_active_curriculum_subjects(db)

        if actor.role != "teacher":
            raise AcademicAuthorizationError(
                "Only administrators and teachers can author academic content"
            )

        teacher_membership_id = AcademicAuthorizationService._teacher_membership_id(
            actor
        )

        await AcademicAuthorizationService._require_live_teacher(
            db,
            teacher_membership_id=teacher_membership_id,
        )

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
        academic_term_id: UUID,
    ) -> list[AcademicClass]:
        """Return academically eligible classes the actor may target for a subject.

        AcademicEligibilityService owns the curriculum/specialization rules.
        Authorization then narrows that academic scope according to actor authority:

        - administrators may target every academically eligible class;
        - teachers may target only academically eligible classes for which they
          also hold a current effective Weave teacher assignment.
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

        if actor.role not in {"admin", "teacher"}:
            raise AcademicAuthorizationError(
                "Only administrators and teachers can access this academic scope"
            )

        eligible_classes = await AcademicEligibilityService.list_eligible_classes(
            db,
            curriculum_subject_id=curriculum_subject_id,
            academic_term_id=academic_term_id,
        )

        if actor.role == "admin":
            return eligible_classes

        teacher_membership_id = AcademicAuthorizationService._teacher_membership_id(
            actor
        )

        await AcademicAuthorizationService._require_live_teacher(
            db,
            teacher_membership_id=teacher_membership_id,
        )

        assigned_classes = (
            await AcademicRepository.list_teacher_classes_for_curriculum_subject(
                db,
                teacher_membership_id=teacher_membership_id,
                curriculum_subject_id=curriculum_subject_id,
            )
        )
        assigned_class_ids = {classroom.id for classroom in assigned_classes}

        return [
            classroom
            for classroom in eligible_classes
            if classroom.id in assigned_class_ids
        ]

    @staticmethod
    def _teacher_membership_id(actor: LocalActor) -> UUID:
        if actor.weave_membership_id is None:
            raise AcademicAuthorizationError(
                "Teacher is missing a Weave membership identity"
            )

        try:
            return UUID(actor.weave_membership_id)
        except ValueError as exc:
            raise AcademicAuthorizationError(
                "Teacher has an invalid Weave membership identity"
            ) from exc

    @staticmethod
    async def _require_live_teacher(
        db: AsyncSession,
        *,
        teacher_membership_id: UUID,
    ) -> None:
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
