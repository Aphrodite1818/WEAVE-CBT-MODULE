"""Scoring and read services for locally calculated CBT results."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AcademicAuthorizationError
from app.domains.academics.authorization import AcademicAuthorizationService
from app.domains.attempts.models import AttemptStatus, ExamAttempt
from app.domains.attempts.repository import AttemptRepository
from app.domains.auth.models import LocalActor
from app.domains.candidates.repository import CandidateRepository
from app.domains.exams.exceptions import ExamNotFound
from app.domains.exams.models import Exam
from app.domains.exams.repository import ExamRepository
from app.domains.results.models import ExamResult, ResultSyncStatus
from app.domains.results.repository import ResultRepository


_TWO_DP = Decimal("0.01")


class ResultService:
    @staticmethod
    async def calculate_for_submitted_attempt(
        db: AsyncSession,
        *,
        attempt: ExamAttempt,
        candidate,
        exam: Exam,
    ) -> ExamResult:
        """Calculate exactly once from immutable attempt paper/answer snapshots."""
        if attempt.status != AttemptStatus.SUBMITTED:
            raise ValueError("Only submitted attempts can produce a result")
        existing = await ResultRepository.get_result_by_attempt_id(
            db, attempt.id, lock=True
        )
        if existing is not None:
            return existing
        if exam.component_maximum_score is None:
            raise ValueError("Examination is missing its frozen component maximum")

        questions = await AttemptRepository.list_question_allocations(db, attempt.id)
        if not questions:
            raise ValueError("Attempt has no allocated questions")
        options = await AttemptRepository.list_option_allocations_for_questions(
            db, [question.id for question in questions]
        )
        answers = await AttemptRepository.list_answers_for_attempt(db, attempt.id)
        selections = await AttemptRepository.list_selections_for_answers(
            db, [answer.id for answer in answers]
        )

        correct_by_question: dict[UUID, set[UUID]] = defaultdict(set)
        for option in options:
            if option.is_correct:
                correct_by_question[option.attempt_question_id].add(option.id)

        answer_by_question = {answer.attempt_question_id: answer for answer in answers}
        selected_by_answer: dict[UUID, set[UUID]] = defaultdict(set)
        for selection in selections:
            selected_by_answer[selection.answer_id].add(selection.attempt_option_id)

        raw_score = 0
        for question in questions:
            answer = answer_by_question.get(question.id)
            selected = selected_by_answer.get(answer.id, set()) if answer else set()
            correct = correct_by_question.get(question.id, set())
            if correct and selected == correct:
                raw_score += 1

        raw_max = len(questions)
        percentage = (Decimal(raw_score) * Decimal(100) / Decimal(raw_max)).quantize(
            _TWO_DP, rounding=ROUND_HALF_UP
        )
        component_max = Decimal(exam.component_maximum_score)
        component_score = (
            Decimal(raw_score) * component_max / Decimal(raw_max)
        ).quantize(_TWO_DP, rounding=ROUND_HALF_UP)

        result = ExamResult(
            attempt_id=attempt.id,
            candidate_id=candidate.id,
            exam_id=exam.id,
            assessment_component_id=exam.assessment_component_id,
            raw_score=raw_score,
            raw_max_score=raw_max,
            percentage=percentage,
            component_score=component_score,
            component_maximum_score=component_max,
            calculated_at=datetime.now(UTC),
            sync_status=ResultSyncStatus.PENDING,
            sync_batch_id=None,
            sync_attempts=0,
        )
        try:
            return await ResultRepository.add_result(db, result)
        except IntegrityError:
            # The caller owns the transaction. A concurrent duplicate will be
            # resolved by its unique attempt/candidate-exam constraints after
            # rollback at the service boundary rather than creating a duplicate.
            raise

    @staticmethod
    async def _require_can_view_exam_results(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
    ) -> None:
        if not actor.is_active:
            raise AcademicAuthorizationError("Active local actor is required")

        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id)
        if exam is None:
            raise ExamNotFound("Examination does not exist")

        if actor.role == "admin":
            return

        if actor.role != "teacher" or actor.weave_membership_id is None:
            raise AcademicAuthorizationError(
                "Administrator, invigilator, or authorized subject-teacher access is required"
            )

        try:
            teacher_id = UUID(actor.weave_membership_id)
        except ValueError as exc:
            raise AcademicAuthorizationError(
                "Teacher has an invalid Weave membership identity"
            ) from exc

        invigilator = await ExamRepository.get_invigilator(db, exam.id, teacher_id)
        if invigilator is not None:
            return

        try:
            await AcademicAuthorizationService.require_can_author_curriculum_subject_for_term(
                db,
                actor=actor,
                curriculum_subject_id=exam.curriculum_subject_id,
                academic_term_id=exam.term_id,
            )
        except AcademicAuthorizationError as exc:
            raise AcademicAuthorizationError(
                "Only assigned invigilators or currently authorized subject teachers "
                "may view these results"
            ) from exc

    @classmethod
    async def get_result(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        result_id: UUID,
    ) -> ExamResult:
        result = await ResultRepository.get_result_by_id(db, result_id)
        if result is None:
            raise ValueError("Result does not exist")
        await cls._require_can_view_exam_results(
            db, actor=actor, exam_id=result.exam_id
        )
        return result

    @classmethod
    async def list_exam_results(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[ExamResult], int]:
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        await cls._require_can_view_exam_results(db, actor=actor, exam_id=exam.id)
        rows = await ResultRepository.list_results_for_exam(
            db, exam.id, offset=offset, limit=limit
        )
        total = await ResultRepository.count_results_for_exam(db, exam.id)
        return rows, total
