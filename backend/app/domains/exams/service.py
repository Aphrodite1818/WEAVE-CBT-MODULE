"""Public examination service facade."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AcademicAuthorizationError
from app.domains.academics.authorization import AcademicAuthorizationService
from app.domains.auth.models import LocalActor
from app.domains.exams.authoring_service import ExamService as _AuthoringExamService
from app.domains.exams.exceptions import ExamAuthorizationError, ExamNotFound
from app.domains.exams.lifecycle_service import ExamLifecycleServiceMixin
from app.domains.exams.models import Exam
from app.domains.exams.repository import ExamRepository


class ExamService(ExamLifecycleServiceMixin, _AuthoringExamService):
    """Combined exam authoring, review, invigilation, and lifecycle service."""

    @staticmethod
    async def get_exam(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
    ) -> Exam:
        """Return one examination when the actor has a legitimate exam relationship."""

        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id)

        if exam is None:
            raise ExamNotFound("Examination does not exist")

        if not actor.is_active:
            raise ExamAuthorizationError("Active local actor is required")

        if actor.role == "admin":
            return exam

        if actor.role != "teacher":
            raise ExamAuthorizationError(
                "You are not allowed to view this examination"
            )

        # The original author retains read access even if their current
        # teaching assignment later changes.
        if exam.created_by_actor_id == actor.id:
            return exam

        teacher_membership_id: UUID | None = None
        if actor.weave_membership_id is not None:
            try:
                teacher_membership_id = UUID(actor.weave_membership_id)
            except ValueError as exc:
                raise ExamAuthorizationError(
                    "Teacher has an invalid Weave membership identity"
                ) from exc

        # Invigilation is independent of subject-authoring permission. An
        # assigned invigilator still needs the examination details.
        if teacher_membership_id is not None:
            invigilator = await ExamRepository.get_invigilator(
                db,
                exam.id,
                teacher_membership_id,
            )
            if invigilator is not None:
                return exam

        try:
            await AcademicAuthorizationService.require_can_author_curriculum_subject(
                db,
                actor=actor,
                curriculum_subject_id=exam.curriculum_subject_id,
            )
        except AcademicAuthorizationError as exc:
            raise ExamAuthorizationError(
                "You are not allowed to view this examination"
            ) from exc

        return exam


__all__ = ["ExamService"]
