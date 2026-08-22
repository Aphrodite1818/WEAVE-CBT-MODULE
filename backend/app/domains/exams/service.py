"""Public examination service facade."""

from __future__ import annotations

from datetime import datetime
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
from app.domains.exams.schemas import ExamCreate, ExamUpdate
from app.domains.exams.timetable_service import ExamTimetableService


class ExamService(ExamLifecycleServiceMixin, _AuthoringExamService):
    """Combined authoring/lifecycle facade with timetable integrity guards."""

    @classmethod
    async def _before_create_exam_save(
        cls,
        db: AsyncSession,
        *,
        payload: ExamCreate,
    ) -> None:
        await ExamTimetableService.require_planned_slot_available(
            db,
            session_id=payload.session_id,
            term_id=payload.term_id,
            curriculum_subject_id=payload.curriculum_subject_id,
            scheduled_start_at=payload.scheduled_start_at,
            duration_minutes=payload.duration_minutes,
        )

    @classmethod
    async def _before_update_exam_save(
        cls,
        db: AsyncSession,
        *,
        exam: Exam,
        session_id: UUID,
        term_id: UUID,
        scheduled_start_at: datetime | None,
        duration_minutes: int,
    ) -> None:
        await ExamTimetableService.require_planned_slot_available(
            db,
            session_id=session_id,
            term_id=term_id,
            curriculum_subject_id=exam.curriculum_subject_id,
            scheduled_start_at=scheduled_start_at,
            duration_minutes=duration_minutes,
            exclude_exam_id=exam.id,
        )

    @classmethod
    async def _before_activate_exam_save(
        cls,
        db: AsyncSession,
        *,
        exam: Exam,
    ) -> None:
        await ExamTimetableService.require_level_free(db, exam_id=exam.id)

    @classmethod
    async def _before_resume_exam_save(
        cls,
        db: AsyncSession,
        *,
        exam: Exam,
    ) -> None:
        await ExamTimetableService.require_level_free(db, exam_id=exam.id)

    @classmethod
    async def create_exam(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        payload: ExamCreate,
    ) -> Exam:
        return await super().create_exam(
            db,
            actor=actor,
            payload=payload,
        )

    @classmethod
    async def update_exam(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        payload: ExamUpdate,
        exam_id: UUID,
    ) -> Exam:
        return await super().update_exam(
            db,
            actor=actor,
            payload=payload,
            exam_id=exam_id,
        )

    @classmethod
    async def seal_exam(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
    ) -> Exam:
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        await ExamTimetableService.require_planned_slot_available(
            db,
            session_id=exam.session_id,
            term_id=exam.term_id,
            curriculum_subject_id=exam.curriculum_subject_id,
            scheduled_start_at=exam.scheduled_start_at,
            duration_minutes=exam.duration_minutes,
            exclude_exam_id=exam.id,
        )
        return await super().seal_exam(
            db,
            actor=actor,
            exam_id=exam_id,
        )

    @classmethod
    async def activate_exam(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
    ) -> Exam:
        return await super().activate_exam(
            db,
            actor=actor,
            exam_id=exam_id,
        )

    @classmethod
    async def resume_exam(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
        reason: str | None = None,
    ) -> Exam:
        return await super().resume_exam(
            db,
            actor=actor,
            exam_id=exam_id,
            reason=reason,
        )

    @staticmethod
    async def get_exam(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
    ) -> Exam:
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        if not actor.is_active:
            raise ExamAuthorizationError("Active local actor is required")
        if actor.role == "admin":
            return exam
        if actor.role != "teacher":
            raise ExamAuthorizationError("You are not allowed to view this examination")
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
