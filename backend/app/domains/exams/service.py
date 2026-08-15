# =========================== #
#       exams/service.py      #
# =========================== #

"""Business rules for exam academic scope, authorization, and sealing.

The service is deliberately strict at the lifecycle boundary. Draft rows may be
incomplete while a teacher/admin is preparing an exam, but submission and seal
operations validate the synchronized Weave academic projection so an active
exam can never contain contradictory session, term, curriculum, assignment, or
assessment references.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academics.models import (
    AcademicLevelSubject,
    AssessmentComponent,
    AssessmentScheme,
    AcademicTeacher,
)
from app.domains.academics.repository import AcademicRepository
from app.domains.auth.models import LocalActor
from app.domains.auth.repository import AuthRepository
from app.domains.exams.exceptions import (
    ExamAcademicScopeError,
    ExamAuthorizationError,
    ExamNotFound,
    ExamQuestionScopeError,
    ExamStateError,
    ExamTargetScopeError,
)
from app.domains.exams.models import Exam, ExamStatus, ExamTargetClass
from app.domains.exams.repository import ExamRepository
from app.domains.questions.repository import QuestionRepository

TEACHER_ROLE = "teacher"
ADMIN_ROLES = frozenset({"admin", "tenant_admin"})


class ExamService:
    """Orchestrate exam lifecycle rules above persistence repositories."""

    @staticmethod
    async def _get_active_actor(db: AsyncSession, actor_id: UUID) -> LocalActor:
        actor = await AuthRepository.get_actor_by_id(db, actor_id)
        if actor is None or not actor.is_active:
            raise ExamAuthorizationError("Active local actor is required.")
        return actor

    @staticmethod
    async def _get_teacher_for_actor(
        db: AsyncSession,
        actor: LocalActor,
    ) -> AcademicTeacher:
        if actor.role != TEACHER_ROLE:
            raise ExamAuthorizationError("Teacher actor is required.")
        if not actor.weave_membership_id:
            raise ExamAuthorizationError(
                "Teacher actor is missing its Weave membership identity."
            )

        teacher = await AcademicRepository.get_teacher_by_membership_id(
            db,
            actor.weave_membership_id,
        )
        if teacher is None or not teacher.is_active:
            raise ExamAuthorizationError(
                "Teacher membership is not active in the local academic projection."
            )
        return teacher

    @staticmethod
    async def _validate_academic_scope(
        db: AsyncSession,
        exam: Exam,
    ) -> tuple[AcademicLevelSubject, AssessmentScheme, AssessmentComponent]:
        """Validate cross-table academic references that SQL foreign keys cannot express."""
        session = await AcademicRepository.get_session_by_id(db, exam.session_id)
        if session is None:
            raise ExamAcademicScopeError(
                "Exam academic session does not exist locally."
            )

        term = await AcademicRepository.get_term_by_id(db, exam.term_id)
        if term is None:
            raise ExamAcademicScopeError("Exam academic term does not exist locally.")
        if term.session_id != exam.session_id:
            raise ExamAcademicScopeError(
                "Exam term does not belong to the selected academic session."
            )

        level_subject = await AcademicRepository.get_level_subject_by_id(
            db,
            exam.level_subject_id,
        )
        if level_subject is None or not level_subject.is_active:
            raise ExamAcademicScopeError(
                "Exam LevelSubject is missing or inactive in the Weave projection."
            )

        scheme = await AcademicRepository.get_assessment_scheme_by_id(
            db,
            exam.assessment_scheme_id,
        )
        if scheme is None or scheme.status != "active":
            raise ExamAcademicScopeError(
                "Exam must use the active synchronized assessment scheme."
            )

        component = await AcademicRepository.get_component_by_id(
            db,
            exam.assessment_component_id,
        )
        if component is None or not component.is_active:
            raise ExamAcademicScopeError(
                "Exam assessment component is missing or inactive."
            )
        if component.assessment_scheme_id != exam.assessment_scheme_id:
            raise ExamAcademicScopeError(
                "Exam assessment component does not belong to its assessment scheme."
            )

        if Decimal(exam.maximum_score) != Decimal(component.maximum_score):
            raise ExamAcademicScopeError(
                "Exam maximum score must equal the synchronized component maximum score."
            )

        return level_subject, scheme, component

    @staticmethod
    async def _resolve_target_assignments(
        db: AsyncSession,
        exam: Exam,
        level_subject: AcademicLevelSubject,
        *,
        effective_on: date,
        required_teacher_id: UUID | None = None,
    ) -> list[ExamTargetClass]:
        """Validate each concrete arm and freeze the active Weave assignment provenance."""
        targets = await ExamRepository.list_target_classes_for_exam(db, exam.id)
        if not targets:
            raise ExamTargetScopeError("Exam must target at least one class arm.")

        for target in targets:
            academic_class = await AcademicRepository.get_class_by_id(
                db,
                target.class_id,
            )
            if academic_class is None or not academic_class.is_active:
                raise ExamTargetScopeError(
                    "Exam target class is missing or inactive in the academic projection."
                )
            if academic_class.level_id != level_subject.level_id:
                raise ExamTargetScopeError(
                    "Exam target class does not belong to the exam LevelSubject level."
                )

            assignment = (
                await AcademicRepository.get_active_assignment_for_class_level_subject(
                    db,
                    target.class_id,
                    exam.level_subject_id,
                    effective_on=effective_on,
                )
            )
            if assignment is None:
                raise ExamTargetScopeError(
                    "Every target class must have an active teacher assignment for the exam LevelSubject."
                )

            if (
                required_teacher_id is not None
                and assignment.teacher_id != required_teacher_id
            ):
                raise ExamAuthorizationError(
                    "Teacher may only target class arms they are actively assigned to teach."
                )

            target.teacher_assignment_id = assignment.id
            target.weave_teacher_assignment_id = assignment.weave_assignment_id
            await ExamRepository.save_target_class(db, target)

        return targets

    @staticmethod
    async def _validate_question_scope_and_points(
        db: AsyncSession,
        exam: Exam,
        component: AssessmentComponent,
    ) -> None:
        """Ensure every frozen exam question came from the same LevelSubject bank."""
        exam_questions = await ExamRepository.list_exam_questions(db, exam.id)
        if not exam_questions:
            raise ExamQuestionScopeError("Exam cannot be sealed without questions.")

        for exam_question in exam_questions:
            source_question = await QuestionRepository.get_question_by_id(
                db,
                exam_question.source_question_id,
            )
            if source_question is None or not source_question.is_active:
                raise ExamQuestionScopeError(
                    "Exam contains a missing or inactive source question."
                )
            if source_question.version != exam_question.source_question_version:
                raise ExamQuestionScopeError(
                    "Exam question snapshot is stale; rebuild it from the current source version."
                )

            bank = await QuestionRepository.get_bank_by_id(db, source_question.bank_id)
            if bank is None or not bank.is_active:
                raise ExamQuestionScopeError(
                    "Exam contains a question from a missing or inactive bank."
                )
            if bank.level_subject_id != exam.level_subject_id:
                raise ExamQuestionScopeError(
                    "Every exam question must come from a bank for the exam LevelSubject."
                )

        point_total = await ExamRepository.get_exam_question_point_total(db, exam.id)
        component_maximum = Decimal(component.maximum_score)
        if point_total != component_maximum:
            raise ExamQuestionScopeError(
                "Exam question point total must equal the assessment component maximum score."
            )
        if point_total != Decimal(exam.maximum_score):
            raise ExamQuestionScopeError(
                "Exam question point total must equal Exam.maximum_score."
            )

    @staticmethod
    async def ensure_teacher_can_target_exam(
        db: AsyncSession,
        *,
        actor_id: UUID,
        exam_id: UUID,
        effective_on: date | None = None,
    ) -> list[ExamTargetClass]:
        """Reusable authorization check for teacher-managed target-class operations."""
        exam = await ExamRepository.get_exam_by_id(db, exam_id)
        if exam is None:
            raise ExamNotFound("Exam not found.")

        actor = await ExamService._get_active_actor(db, actor_id)
        teacher = await ExamService._get_teacher_for_actor(db, actor)
        level_subject, _, _ = await ExamService._validate_academic_scope(db, exam)
        return await ExamService._resolve_target_assignments(
            db,
            exam,
            level_subject,
            effective_on=effective_on or date.today(),
            required_teacher_id=teacher.id,
        )

    @staticmethod
    async def submit_exam(
        db: AsyncSession,
        *,
        exam_id: UUID,
        actor_id: UUID,
        now: datetime | None = None,
    ) -> Exam:
        """Submit a draft after validating academic scope and target authority."""
        current_time = now or datetime.now(timezone.utc)
        effective_on = current_time.date()

        try:
            exam = await ExamRepository.get_exam_by_id(db, exam_id, lock=True)
            if exam is None:
                raise ExamNotFound("Exam not found.")
            if exam.status != ExamStatus.DRAFT:
                raise ExamStateError("Only a draft exam can be submitted.")

            actor = await ExamService._get_active_actor(db, actor_id)
            if actor.role not in ADMIN_ROLES and actor.role != TEACHER_ROLE:
                raise ExamAuthorizationError(
                    "Only a school admin or teacher can submit an exam."
                )

            level_subject, _, _ = await ExamService._validate_academic_scope(db, exam)

            required_teacher_id: UUID | None = None
            if actor.role == TEACHER_ROLE:
                teacher = await ExamService._get_teacher_for_actor(db, actor)
                required_teacher_id = teacher.id

            await ExamService._resolve_target_assignments(
                db,
                exam,
                level_subject,
                effective_on=effective_on,
                required_teacher_id=required_teacher_id,
            )

            exam.status = ExamStatus.SUBMITTED
            exam.submitted_by_actor_id = actor.id
            exam.submitted_at = current_time
            await ExamRepository.save_exam(db, exam)
            await db.commit()
            await db.refresh(exam)
            return exam
        except Exception:
            await db.rollback()
            raise

    @staticmethod
    async def seal_exam(
        db: AsyncSession,
        *,
        exam_id: UUID,
        actor_id: UUID,
        now: datetime | None = None,
    ) -> Exam:
        """Admin-only seal that freezes assignment and assessment provenance."""
        current_time = now or datetime.now(timezone.utc)
        effective_on = current_time.date()

        try:
            exam = await ExamRepository.get_exam_by_id(db, exam_id, lock=True)
            if exam is None:
                raise ExamNotFound("Exam not found.")
            if exam.status != ExamStatus.SUBMITTED:
                raise ExamStateError("Only a submitted exam can be sealed.")

            actor = await ExamService._get_active_actor(db, actor_id)
            if actor.role not in ADMIN_ROLES:
                raise ExamAuthorizationError("Only a school admin can seal an exam.")

            (
                level_subject,
                scheme,
                component,
            ) = await ExamService._validate_academic_scope(
                db,
                exam,
            )
            await ExamService._resolve_target_assignments(
                db,
                exam,
                level_subject,
                effective_on=effective_on,
            )
            await ExamService._validate_question_scope_and_points(
                db,
                exam,
                component,
            )

            exam.source_assessment_scheme_weave_id = scheme.weave_scheme_id
            exam.source_assessment_component_weave_id = component.weave_component_id
            exam.source_assessment_component_name = component.name
            exam.source_assessment_component_code = component.code
            exam.source_assessment_component_maximum_score = Decimal(
                component.maximum_score
            )
            exam.status = ExamStatus.SEALED
            exam.sealed_at = current_time

            await ExamRepository.save_exam(db, exam)
            await db.commit()
            await db.refresh(exam)
            return exam
        except Exception:
            await db.rollback()
            raise
