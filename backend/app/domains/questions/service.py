# =========================== #
#      questions/service.py   #
# =========================== #

"""Authorization rules for shared LevelSubject question banks.

Question-bank access is intentionally broader than exam delivery authority:
a teacher assigned to any arm for a LevelSubject may author within that shared
LevelSubject bank, while exam targeting remains arm-specific in ExamService.
"""

from __future__ import annotations

from datetime import date
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
    """Enforce academic authorization around shared question-bank scopes."""

    @staticmethod
    async def ensure_actor_can_author_for_level_subject(
        db: AsyncSession,
        *,
        actor_id: UUID,
        level_subject_id: UUID,
        effective_on: date | None = None,
    ) -> None:
        actor = await AuthRepository.get_actor_by_id(db, actor_id)
        if actor is None or not actor.is_active:
            raise QuestionAuthorizationError("Active local actor is required.")

        level_subject = await AcademicRepository.get_level_subject_by_id(
            db,
            level_subject_id,
        )
        if level_subject is None or not level_subject.is_active:
            raise QuestionScopeError(
                "Question authoring requires an active synchronized LevelSubject."
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

        teacher = await AcademicRepository.get_teacher_by_membership_id(
            db,
            actor.weave_membership_id,
        )
        if teacher is None or not teacher.is_active:
            raise QuestionAuthorizationError(
                "Teacher membership is not active in the local academic projection."
            )

        allowed = await AcademicRepository.teacher_has_level_subject_assignment(
            db,
            teacher.id,
            level_subject_id,
            effective_on=effective_on or date.today(),
        )
        if not allowed:
            raise QuestionAuthorizationError(
                "Teacher needs an active assignment in this LevelSubject to author questions."
            )

    @staticmethod
    async def ensure_actor_can_author_in_bank(
        db: AsyncSession,
        *,
        actor_id: UUID,
        bank_id: UUID,
        effective_on: date | None = None,
    ) -> None:
        bank = await QuestionRepository.get_bank_by_id(db, bank_id)
        if bank is None:
            raise QuestionNotFound("Question bank not found.")
        if not bank.is_active:
            raise QuestionScopeError("Question bank is inactive.")

        await QuestionService.ensure_actor_can_author_for_level_subject(
            db,
            actor_id=actor_id,
            level_subject_id=bank.level_subject_id,
            effective_on=effective_on,
        )
