"""Authorization rules for shared CurriculumSubject question banks."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academics.repository import AcademicRepository
from app.domains.auth.repository import AuthRepository
from app.domains.questions.exceptions import (
    QuestionAuthorizationError,
    QuestionNotFound,
    QuestionScopeError,
)
from app.domains.questions.repository import QuestionRepository

TEACHER_ROLE = "teacher"
ADMIN_ROLES = frozenset({"admin", "tenant_admin"})


class QuestionService:
    """Enforce Weave assignment authorization around shared question-bank scopes."""

    @staticmethod
    async def ensure_actor_can_author_for_curriculum_subject(
        db: AsyncSession,
        *,
        actor_id: UUID,
        curriculum_subject_id: UUID,
    ) -> None:
        actor = await AuthRepository.get_actor_by_id(db, actor_id)
        if actor is None or not actor.is_active:
            raise QuestionAuthorizationError("Active local actor is required.")

        curriculum_subject = await AcademicRepository.get_curriculum_subject_by_id(
            db,
            curriculum_subject_id,
        )
        if curriculum_subject is None or not curriculum_subject.is_active:
            raise QuestionScopeError(
                "Question authoring requires an active synchronized CurriculumSubject."
            )

        if actor.role in ADMIN_ROLES:
            return
        if actor.role != TEACHER_ROLE:
            raise QuestionAuthorizationError(
                "Only school admins and teachers can author question-bank content."
            )
        if not actor.weave_membership_id:
            raise QuestionAuthorizationError(
                "Teacher actor is missing its Weave membership identity."
            )

        try:
            membership_id = UUID(actor.weave_membership_id)
        except ValueError as exc:
            raise QuestionAuthorizationError(
                "Teacher actor has an invalid Weave membership identity."
            ) from exc

        teacher = await AcademicRepository.get_teacher_by_membership_id(db, membership_id)
        if teacher is None or teacher.status != "active":
            raise QuestionAuthorizationError(
                "Teacher membership is not active in the local academic projection."
            )

        allowed = await AcademicRepository.teacher_has_curriculum_subject_assignment(
            db,
            membership_id,
            curriculum_subject_id,
        )
        if not allowed:
            raise QuestionAuthorizationError(
                "Teacher needs an active assignment for this curriculum subject to author questions."
            )

    @staticmethod
    async def ensure_actor_can_author_in_bank(
        db: AsyncSession,
        *,
        actor_id: UUID,
        bank_id: UUID,
    ) -> None:
        bank = await QuestionRepository.get_bank_by_id(db, bank_id)
        if bank is None:
            raise QuestionNotFound("Question bank not found.")
        if not bank.is_active:
            raise QuestionScopeError("Question bank is inactive.")

        await QuestionService.ensure_actor_can_author_for_curriculum_subject(
            db,
            actor_id=actor_id,
            curriculum_subject_id=bank.curriculum_subject_id,
        )
