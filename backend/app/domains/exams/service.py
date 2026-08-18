"""Business rules for exam academic scope, authorization, and sealing."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academics.models import (
    AcademicTeacher,
    AssessmentComponent,
    AssessmentScheme,
    Curriculum,
    CurriculumSubject,
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
    @staticmethod
    async def _get_active_actor(db: AsyncSession, actor_id: UUID) -> LocalActor:
        actor = await AuthRepository.get_actor_by_id(db, actor_id)
        if actor is None or not actor.is_active:
            raise ExamAuthorizationError("Active local actor is required.")
        return actor

    @staticmethod
    async def _get_teacher_for_actor(db: AsyncSession, actor: LocalActor) -> AcademicTeacher:
        if actor.role != TEACHER_ROLE:
            raise ExamAuthorizationError("Teacher actor is required.")
        if not actor.weave_membership_id:
            raise ExamAuthorizationError("Teacher actor is missing its Weave membership identity.")
        try:
            membership_id = UUID(actor.weave_membership_id)
        except ValueError as exc:
            raise ExamAuthorizationError("Teacher actor has an invalid Weave membership identity.") from exc
        teacher = await AcademicRepository.get_teacher_by_membership_id(db, membership_id)
        if teacher is None or teacher.status != "active":
            raise ExamAuthorizationError(
                "Teacher membership is not active in the local academic projection."
            )
        return teacher

    @staticmethod
    async def _validate_academic_scope(
        db: AsyncSession,
        exam: Exam,
    ) -> tuple[CurriculumSubject, Curriculum, AssessmentScheme, AssessmentComponent]:
        session = await AcademicRepository.get_session_by_id(db, exam.session_id)
        if session is None:
            raise ExamAcademicScopeError("Exam academic session does not exist locally.")

        term = await AcademicRepository.get_term_by_id(db, exam.term_id)
        if term is None:
            raise ExamAcademicScopeError("Exam academic term does not exist locally.")
        if term.academic_session_id != exam.session_id:
            raise ExamAcademicScopeError("Exam term does not belong to the selected academic session.")

        curriculum_subject = await AcademicRepository.get_curriculum_subject_by_id(
            db, exam.curriculum_subject_id
        )
        if curriculum_subject is None or not curriculum_subject.is_active:
            raise ExamAcademicScopeError(
                "Exam CurriculumSubject is missing or inactive in the Weave projection."
            )
        curriculum = await AcademicRepository.get_curriculum_by_id(
            db, curriculum_subject.curriculum_id
        )
        if curriculum is None:
            raise ExamAcademicScopeError("Exam curriculum is missing in the Weave projection.")

        scheme = await AcademicRepository.get_assessment_scheme_by_id(db, exam.assessment_scheme_id)
        if scheme is None or scheme.status != "active":
            raise ExamAcademicScopeError("Exam must use the active synchronized assessment scheme.")

        component = await AcademicRepository.get_component_by_id(db, exam.assessment_component_id)
        if component is None or not component.is_active:
            raise ExamAcademicScopeError("Exam assessment component is missing or inactive.")
        if component.assessment_scheme_id != exam.assessment_scheme_id:
            raise ExamAcademicScopeError("Exam assessment component does not belong to its scheme.")
        if Decimal(exam.maximum_score) != Decimal(component.maximum_score):
            raise ExamAcademicScopeError(
                "Exam maximum score must equal the synchronized component maximum score."
            )
        return curriculum_subject, curriculum, scheme, component

    @staticmethod
    async def _resolve_target_provenance(
        db: AsyncSession,
        exam: Exam,
        curriculum: Curriculum,
        *,
        required_teacher_membership_id: UUID | None = None,
    ) -> list[ExamTargetClass]:
        targets = await ExamRepository.list_target_classes_for_exam(db, exam.id)
        if not targets:
            raise ExamTargetScopeError("Exam must target at least one class arm.")

        for target in targets:
            academic_class = await AcademicRepository.get_class_by_id(db, target.class_id)
            if academic_class is None or not academic_class.is_active:
                raise ExamTargetScopeError("Exam target class is missing or inactive.")
            if academic_class.academic_level_id != curriculum.academic_level_id:
                raise ExamTargetScopeError(
                    "Exam target class does not belong to the curriculum's academic level."
                )

            offering = await AcademicRepository.get_offering_for_class_scope(
                db,
                academic_term_id=exam.term_id,
                curriculum_subject_id=exam.curriculum_subject_id,
                class_id=target.class_id,
            )
            if offering is None:
                raise ExamTargetScopeError(
                    "Every target class must have a current subject offering for this exam scope."
                )

            assignment = await AcademicRepository.get_active_assignment_for_class_curriculum_subject(
                db,
                target.class_id,
                exam.curriculum_subject_id,
            )
            if assignment is None:
                raise ExamTargetScopeError(
                    "Every target class must have an active teacher assignment for this curriculum subject."
                )
            if (
                required_teacher_membership_id is not None
                and assignment.teacher_membership_id != required_teacher_membership_id
            ):
                raise ExamAuthorizationError(
                    "Teacher may only target classes they are actively assigned to teach."
                )

            target.subject_offering_id = offering.id
            target.teacher_assignment_id = assignment.id
            await ExamRepository.save_target_class(db, target)

        return targets

    @staticmethod
    async def _validate_question_scope_and_points(
        db: AsyncSession,
        exam: Exam,
        component: AssessmentComponent,
    ) -> None:
        exam_questions = await ExamRepository.list_exam_questions(db, exam.id)
        if not exam_questions:
            raise ExamQuestionScopeError("Exam cannot be sealed without questions.")

        for exam_question in exam_questions:
            source_question = await QuestionRepository.get_question_by_id(
                db, exam_question.source_question_id
            )
            if source_question is None or not source_question.is_active:
                raise ExamQuestionScopeError("Exam contains a missing or inactive source question.")
            if source_question.version != exam_question.source_question_version:
                raise ExamQuestionScopeError(
                    "Exam question snapshot is stale; rebuild it from the current source version."
                )
            bank = await QuestionRepository.get_bank_by_id(db, source_question.bank_id)
            if bank is None or not bank.is_active:
                raise ExamQuestionScopeError("Exam contains a question from a missing or inactive bank.")
            if bank.curriculum_subject_id != exam.curriculum_subject_id:
                raise ExamQuestionScopeError(
                    "Every exam question must come from a bank for the exam CurriculumSubject."
                )

        point_total = await ExamRepository.get_exam_question_point_total(db, exam.id)
        component_maximum = Decimal(component.maximum_score)
        if point_total != component_maximum or point_total != Decimal(exam.maximum_score):
            raise ExamQuestionScopeError(
                "Exam question point total must equal the assessment component maximum score."
            )

    @staticmethod
    async def ensure_teacher_can_target_exam(
        db: AsyncSession,
        *,
        actor_id: UUID,
        exam_id: UUID,
    ) -> list[ExamTargetClass]:
        exam = await ExamRepository.get_exam_by_id(db, exam_id)
        if exam is None:
            raise ExamNotFound("Exam not found.")
        actor = await ExamService._get_active_actor(db, actor_id)
        teacher = await ExamService._get_teacher_for_actor(db, actor)
        _, curriculum, _, _ = await ExamService._validate_academic_scope(db, exam)
        return await ExamService._resolve_target_provenance(
            db,
            exam,
            curriculum,
            required_teacher_membership_id=teacher.id,
        )

    @staticmethod
    async def submit_exam(
        db: AsyncSession,
        *,
        exam_id: UUID,
        actor_id: UUID,
        now: datetime | None = None,
    ) -> Exam:
        current_time = now or datetime.now(timezone.utc)
        try:
            exam = await ExamRepository.get_exam_by_id(db, exam_id, lock=True)
            if exam is None:
                raise ExamNotFound("Exam not found.")
            if exam.status != ExamStatus.DRAFT:
                raise ExamStateError("Only a draft exam can be submitted.")

            actor = await ExamService._get_active_actor(db, actor_id)
            if actor.role not in ADMIN_ROLES and actor.role != TEACHER_ROLE:
                raise ExamAuthorizationError("Only a school admin or teacher can submit an exam.")

            _, curriculum, _, _ = await ExamService._validate_academic_scope(db, exam)
            required_teacher_id = None
            if actor.role == TEACHER_ROLE:
                required_teacher_id = (await ExamService._get_teacher_for_actor(db, actor)).id

            await ExamService._resolve_target_provenance(
                db,
                exam,
                curriculum,
                required_teacher_membership_id=required_teacher_id,
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
        current_time = now or datetime.now(timezone.utc)
        try:
            exam = await ExamRepository.get_exam_by_id(db, exam_id, lock=True)
            if exam is None:
                raise ExamNotFound("Exam not found.")
            if exam.status != ExamStatus.SUBMITTED:
                raise ExamStateError("Only a submitted exam can be sealed.")

            actor = await ExamService._get_active_actor(db, actor_id)
            if actor.role not in ADMIN_ROLES:
                raise ExamAuthorizationError("Only a school admin can seal an exam.")

            _, curriculum, scheme, component = await ExamService._validate_academic_scope(db, exam)
            await ExamService._resolve_target_provenance(db, exam, curriculum)
            await ExamService._validate_question_scope_and_points(db, exam, component)

            exam.source_assessment_scheme_id = scheme.id
            exam.source_assessment_component_id = component.id
            exam.source_assessment_component_name = component.name
            exam.source_assessment_component_code = component.code
            exam.source_assessment_component_maximum_score = Decimal(component.maximum_score)
            exam.status = ExamStatus.SEALED
            exam.sealed_at = current_time
            await ExamRepository.save_exam(db, exam)
            await db.commit()
            await db.refresh(exam)
            return exam
        except Exception:
            await db.rollback()
            raise
