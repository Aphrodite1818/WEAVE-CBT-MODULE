"""Joint-authoring guards for examination lifecycle transitions."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academics.authorization import AcademicAuthorizationService
from app.domains.auth.models import LocalActor
from app.domains.exams.exceptions import ExamNotFound, ExamStateError
from app.domains.exams.models import Exam, ExamStatus
from app.domains.exams.repository import ExamRepository


class ExamCollaborationLifecycleMixin:
    """Apply shared-paper coordination rules before lifecycle transitions."""

    @classmethod
    async def submit_exam(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
        expected_authoring_version: int = 1,
    ) -> Exam:
        exam = await ExamRepository.get_exam_by_id(
            db,
            exam_id=exam_id,
            lock=True,
        )
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        if exam.status != ExamStatus.DRAFT:
            raise ExamStateError("Only examinations in DRAFT state can be submitted")

        cls._require_expected_authoring_version(exam, expected_authoring_version)
        cls._require_lead_or_admin(actor, exam)
        await AcademicAuthorizationService.require_can_author_curriculum_subject_for_term(
            db,
            actor=actor,
            curriculum_subject_id=exam.curriculum_subject_id,
            academic_term_id=exam.term_id,
        )

        # Stage the version bump in the same transaction used by the existing
        # submit implementation. If submission validation fails, roll back both.
        cls._bump_authoring_version(exam)
        await ExamRepository.save_exam(db, exam)
        try:
            return await super().submit_exam(
                db,
                actor=actor,
                exam_id=exam_id,
            )
        except Exception:
            await db.rollback()
            raise

    @classmethod
    async def delete_draft_exam(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
        expected_authoring_version: int = 1,
    ) -> None:
        exam = await ExamRepository.get_exam_by_id(
            db,
            exam_id=exam_id,
            lock=True,
        )
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        if exam.status != ExamStatus.DRAFT:
            raise ExamStateError("Only DRAFT examinations can be deleted")

        cls._require_expected_authoring_version(exam, expected_authoring_version)
        cls._require_lead_or_admin(actor, exam)
        await AcademicAuthorizationService.require_can_author_curriculum_subject_for_term(
            db,
            actor=actor,
            curriculum_subject_id=exam.curriculum_subject_id,
            academic_term_id=exam.term_id,
        )

        await super().delete_draft_exam(
            db,
            actor=actor,
            exam_id=exam_id,
        )

    @classmethod
    async def return_exam_to_draft(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
    ) -> Exam:
        exam = await super().return_exam_to_draft(
            db,
            actor=actor,
            exam_id=exam_id,
        )

        # Returning a reviewed submission to DRAFT starts a new collaborative
        # editing state and invalidates any screen that still holds the old token.
        exam.authoring_version += 1
        exam = await ExamRepository.save_exam(db, exam)
        await db.commit()
        return exam
