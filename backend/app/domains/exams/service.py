"""Public examination service facade."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AcademicAuthorizationError
from app.domains.academics.authorization import AcademicAuthorizationService
from app.domains.auth.models import LocalActor
from app.domains.exams.authoring_service import ExamService as _AuthoringExamService
from app.domains.exams.collaboration_service import ExamCollaborationLifecycleMixin
from app.domains.exams.exceptions import ExamAuthorizationError, ExamNotFound, ExamStateError
from app.domains.exams.execution_service import ExamExecutionService
from app.domains.exams.lifecycle_service import ExamLifecycleServiceMixin
from app.domains.exams.models import (
    Exam,
    ExamQuestionSelection,
    ExamQuestionSelectionMode,
    ExamRosterStatus,
    ExamStatus,
)
from app.domains.exams.repository import ExamRepository
from app.domains.exams.schemas import ExamCreate, ExamUpdate
from app.domains.exams.timetable_service import ExamTimetableService
from app.workers.producer import arq_producer


class ExamService(
    ExamCollaborationLifecycleMixin,
    ExamLifecycleServiceMixin,
    _AuthoringExamService,
):
    """Combined authoring/lifecycle facade with collaboration and timetable guards."""

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
    async def _before_activate_exam_save(cls, db: AsyncSession, *, exam: Exam) -> None:
        await ExamTimetableService.require_level_free(db, exam_id=exam.id)

    @classmethod
    async def _before_resume_exam_save(cls, db: AsyncSession, *, exam: Exam) -> None:
        await ExamTimetableService.require_level_free(db, exam_id=exam.id)

    @classmethod
    async def create_exam(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        payload: ExamCreate,
    ) -> Exam:
        return await super().create_exam(db, actor=actor, payload=payload)

    @classmethod
    async def update_exam(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        payload: ExamUpdate,
        exam_id: UUID,
    ) -> Exam:
        return await super().update_exam(db, actor=actor, payload=payload, exam_id=exam_id)

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
        return await super().seal_exam(db, actor=actor, exam_id=exam_id)

    @classmethod
    async def activate_exam(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
    ) -> Exam:
        return await super().activate_exam(db, actor=actor, exam_id=exam_id)

    @classmethod
    async def resume_exam(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
        reason: str | None = None,
    ) -> Exam:
        return await super().resume_exam(db, actor=actor, exam_id=exam_id, reason=reason)

    @staticmethod
    async def _preflight_suspended_terminal_transition(
        db: AsyncSession,
        *,
        exam: Exam,
        operation: str,
    ) -> None:
        if exam.status != ExamStatus.SUSPENDED:
            return
        suspension = await ExamRepository.get_open_suspension_for_exam(
            db,
            exam.id,
            lock=True,
        )
        if suspension is None:
            raise ExamStateError(
                "Suspended examination has no open suspension record"
            )
        # Flush the locked row before staging terminal state. Besides validating
        # the durable suspension row, this preserves the old all-or-nothing
        # behavior if its persistence is inconsistent.
        try:
            await ExamRepository.save_suspension(db, suspension)
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(f"The examination could not be {operation}") from exc

    @classmethod
    async def close_exam(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
    ) -> Exam:
        current = await ExamRepository.get_exam_by_id(db, exam_id=exam_id, lock=True)
        if current is None:
            raise ExamNotFound("Examination does not exist")
        await cls._preflight_suspended_terminal_transition(
            db,
            exam=current,
            operation="closed",
        )
        exam = await ExamExecutionService.request_close(
            db,
            actor=actor,
            exam_id=exam_id,
        )
        await arq_producer.enqueue("finalize_exam_close", str(exam.id))
        return exam

    @classmethod
    async def cancel_exam(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
        reason: str,
    ) -> Exam:
        current = await ExamRepository.get_exam_by_id(db, exam_id=exam_id, lock=True)
        if current is None:
            raise ExamNotFound("Examination does not exist")
        await cls._preflight_suspended_terminal_transition(
            db,
            exam=current,
            operation="cancelled",
        )
        exam = await ExamExecutionService.request_cancel(
            db,
            actor=actor,
            exam_id=exam_id,
            reason=reason,
        )
        await arq_producer.enqueue("finalize_exam_cancellation", str(exam.id))
        return exam

    @classmethod
    async def _create_voided_closed_revision(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        latest: Exam,
    ) -> Exam:
        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=latest.curriculum_subject_id,
        )

        revision = Exam(
            session_id=latest.session_id,
            term_id=latest.term_id,
            curriculum_subject_id=latest.curriculum_subject_id,
            assessment_scheme_id=latest.assessment_scheme_id,
            assessment_component_id=latest.assessment_component_id,
            question_bank_id=latest.question_bank_id,
            question_selection_mode=latest.question_selection_mode,
            question_count=latest.question_count,
            title=latest.title,
            instructions=latest.instructions,
            duration_minutes=latest.duration_minutes,
            shuffle_questions=latest.shuffle_questions,
            shuffle_options=latest.shuffle_options,
            scheduled_start_at=latest.scheduled_start_at,
            latest_normal_start_at=latest.latest_normal_start_at,
            status=ExamStatus.DRAFT,
            roster_status=ExamRosterStatus.NOT_PREPARED,
            roster_version=0,
            roster_candidate_count=0,
            revision_number=latest.revision_number + 1,
            revision_of_exam_id=latest.id,
            created_by_actor_id=actor.id,
            component_maximum_score=None,
        )

        try:
            revision = await ExamRepository.add_exam(db, revision)
            if revision.question_selection_mode == ExamQuestionSelectionMode.MANUAL:
                frozen_questions = await ExamRepository.list_exam_questions(db, latest.id)
                if any(question.added_by_actor_id is None for question in frozen_questions):
                    raise ExamStateError(
                        "Manual examination revision cannot be created because "
                        "question contributor provenance is incomplete"
                    )
                await ExamRepository.add_question_selections(
                    db,
                    [
                        ExamQuestionSelection(
                            exam_id=revision.id,
                            added_by_actor_id=question.added_by_actor_id,
                            question_id=question.source_question_id,
                            position=question.position,
                        )
                        for question in frozen_questions
                    ],
                )
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(
                "The examination revision could not be created because it "
                "conflicts with existing examination data"
            ) from exc
        return revision

    @classmethod
    async def create_revision(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
    ) -> Exam:
        cls._require_admin(actor)
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id, lock=True)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        latest = await cls._latest_revision_in_lineage(db, exam)
        if latest.status != ExamStatus.CLOSED:
            return await super().create_revision(db, actor=actor, exam_id=exam_id)

        if not await ExamExecutionService.results_are_voided(db, exam_id=latest.id):
            raise ExamStateError(
                "A CLOSED examination can only be revised after its results are voided"
            )
        return await cls._create_voided_closed_revision(
            db,
            actor=actor,
            latest=latest,
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
            try:
                await AcademicAuthorizationService.require_can_author_curriculum_subject_for_term(
                    db,
                    actor=actor,
                    curriculum_subject_id=exam.curriculum_subject_id,
                    academic_term_id=exam.term_id,
                )
            except AcademicAuthorizationError as exc:
                raise ExamAuthorizationError(
                    "You are not allowed to view this examination"
                ) from exc
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
            await AcademicAuthorizationService.require_can_author_curriculum_subject_for_term(
                db,
                actor=actor,
                curriculum_subject_id=exam.curriculum_subject_id,
                academic_term_id=exam.term_id,
            )
        except AcademicAuthorizationError as exc:
            raise ExamAuthorizationError(
                "You are not allowed to view this examination"
            ) from exc
        return exam


__all__ = ["ExamService"]
