# ruff: noqa: E402

import os
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

from app.domains.attempts.guarded_service import AttemptService
from app.domains.attempts.models import AttemptEndReason, AttemptStatus
from app.domains.attempts.repository import AttemptRepository
from app.domains.auth.student_lifecycle_service import (
    COMPLETED_MESSAGE,
    StudentAuthService,
)
from app.domains.auth.student_schemas import StudentExamAvailability
from app.domains.auth.student_service import StudentSessionContext
from app.domains.exams.models import ExamStatus
from app.domains.results.repository import ResultRepository


class StudentCompletedAttemptResolutionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.student_id = uuid4()
        self.candidate_id = uuid4()
        self.exam_id = uuid4()
        self.enrollment = SimpleNamespace(student_id=self.student_id)
        self.candidate = SimpleNamespace(
            id=self.candidate_id,
            student_id=self.student_id,
            exam_id=self.exam_id,
        )

    def exam(self, status: ExamStatus):
        return SimpleNamespace(
            id=self.exam_id,
            title="JSS1 English Exam",
            status=status,
            scheduled_start_at=datetime.now(UTC),
            activated_at=datetime.now(UTC),
        )

    async def _resolve(self, status: ExamStatus, attempt_status: AttemptStatus):
        exam = self.exam(status)
        attempt = SimpleNamespace(status=attempt_status)
        db = AsyncMock()
        with (
            patch.object(
                StudentAuthService,
                "_normal_candidate_rows",
                new=AsyncMock(return_value=[(self.candidate, exam)]),
            ) as candidate_rows,
            patch.object(
                AttemptRepository,
                "get_attempt_by_candidate_id",
                new=AsyncMock(return_value=attempt),
            ) as get_attempt,
        ):
            resolution = await StudentAuthService._resolve_candidate(
                db,
                enrollment=self.enrollment,
            )
        return resolution, candidate_rows, get_attempt

    async def test_submitted_active_exam_resolves_directly_to_completed(self) -> None:
        resolution, candidate_rows, get_attempt = await self._resolve(
            ExamStatus.ACTIVE,
            AttemptStatus.SUBMITTED,
        )

        self.assertEqual(
            resolution.availability,
            StudentExamAvailability.COMPLETED,
        )
        self.assertEqual(resolution.status_message, COMPLETED_MESSAGE)
        self.assertIs(resolution.candidate, self.candidate)
        self.assertEqual(
            candidate_rows.await_args.kwargs["statuses"],
            (
                ExamStatus.ACTIVE,
                ExamStatus.SUSPENDED,
                ExamStatus.CLOSING,
                ExamStatus.CANCELLING,
            ),
        )
        get_attempt.assert_awaited_once_with(ANY, self.candidate_id)

    async def test_submitted_suspended_exam_hides_suspension_and_resolves_completed(
        self,
    ) -> None:
        resolution, _candidate_rows, _get_attempt = await self._resolve(
            ExamStatus.SUSPENDED,
            AttemptStatus.SUBMITTED,
        )

        self.assertEqual(
            resolution.availability,
            StudentExamAvailability.COMPLETED,
        )
        self.assertEqual(resolution.status_message, COMPLETED_MESSAGE)
        self.assertNotEqual(
            resolution.availability,
            StudentExamAvailability.SUSPENDED,
        )

    async def test_in_progress_suspended_exam_still_uses_suspension_waiting_room(
        self,
    ) -> None:
        resolution, _candidate_rows, _get_attempt = await self._resolve(
            ExamStatus.SUSPENDED,
            AttemptStatus.IN_PROGRESS,
        )

        self.assertEqual(
            resolution.availability,
            StudentExamAvailability.SUSPENDED,
        )
        self.assertIn("temporarily paused", resolution.status_message)


class StudentCompletedResultTests(unittest.IsolatedAsyncioTestCase):
    async def test_current_result_returns_exact_submitted_attempt_score(self) -> None:
        attempt_id = uuid4()
        candidate_id = uuid4()
        exam_id = uuid4()
        result_id = uuid4()
        ended_at = datetime.now(UTC)
        attempt = SimpleNamespace(
            id=attempt_id,
            status=AttemptStatus.SUBMITTED,
            end_reason=AttemptEndReason.CANDIDATE_SUBMITTED,
            ended_at=ended_at,
        )
        candidate = SimpleNamespace(id=candidate_id)
        exam = SimpleNamespace(id=exam_id)
        result = SimpleNamespace(
            id=result_id,
            raw_score=8,
            raw_max_score=10,
            percentage="80.00",
            component_score="16.00",
            component_maximum_score="20.00",
        )
        context = StudentSessionContext(
            session_id=uuid4(),
            student_id=uuid4(),
            candidate_id=candidate_id,
            exam_id=exam_id,
            makeup_authorization_id=None,
        )
        db = AsyncMock()

        with (
            patch.object(
                AttemptService,
                "_get_current_attempt",
                new=AsyncMock(return_value=(attempt, candidate, exam)),
            ),
            patch.object(
                ResultRepository,
                "get_result_by_attempt_id",
                new=AsyncMock(return_value=result),
            ) as get_result,
        ):
            response = await AttemptService.get_current_result(db, context=context)

        self.assertEqual(response.attempt_id, attempt_id)
        self.assertEqual(response.result_id, result_id)
        self.assertEqual(response.status, AttemptStatus.SUBMITTED.value)
        self.assertEqual(response.raw_score, 8)
        self.assertEqual(response.raw_max_score, 10)
        self.assertEqual(response.percentage, "80.00")
        self.assertEqual(response.component_score, "16.00")
        self.assertEqual(response.component_maximum_score, "20.00")
        get_result.assert_awaited_once_with(db, attempt_id)

    async def test_current_result_rejects_non_submitted_attempt(self) -> None:
        attempt = SimpleNamespace(
            id=uuid4(),
            status=AttemptStatus.IN_PROGRESS,
        )
        context = StudentSessionContext(
            session_id=uuid4(),
            student_id=uuid4(),
            candidate_id=uuid4(),
            exam_id=uuid4(),
            makeup_authorization_id=None,
        )
        db = AsyncMock()

        with (
            patch.object(
                AttemptService,
                "_get_current_attempt",
                new=AsyncMock(
                    return_value=(attempt, SimpleNamespace(), SimpleNamespace())
                ),
            ),
            self.assertRaisesRegex(ValueError, "not completed"),
        ):
            await AttemptService.get_current_result(db, context=context)


if __name__ == "__main__":
    unittest.main()
