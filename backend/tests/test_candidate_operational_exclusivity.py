import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

from app.domains.candidates.models import CandidateStatus  # noqa: E402
from app.domains.candidates.service import CandidateService  # noqa: E402
from app.domains.exams.models import ExamStatus  # noqa: E402
from app.domains.exams.timetable_service import ExamTimetableService  # noqa: E402


class CandidateOperationalExclusivityTests(unittest.IsolatedAsyncioTestCase):
    def candidate(self):
        return SimpleNamespace(
            id=uuid4(),
            student_id=uuid4(),
            exam_id=uuid4(),
            status=CandidateStatus.BLOCKED,
        )

    def exam(self, *, status):
        return SimpleNamespace(
            id=uuid4(),
            status=status,
            session_id=uuid4(),
            term_id=uuid4(),
            curriculum_subject_id=uuid4(),
        )

    async def test_unblocking_active_exam_rejects_student_busy_elsewhere(self):
        db = AsyncMock()
        db.scalar = AsyncMock(return_value=True)
        candidate = self.candidate()
        exam = self.exam(status=ExamStatus.ACTIVE)
        candidate.exam_id = exam.id
        level_id = uuid4()

        with (
            patch.object(
                ExamTimetableService,
                "level_id",
                new=AsyncMock(return_value=level_id),
            ),
            patch.object(
                ExamTimetableService,
                "acquire_level_lock",
                new=AsyncMock(),
            ) as acquire_lock,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "already assigned to another operational examination",
            ):
                await CandidateService._require_operational_unblock_safe(
                    db,
                    candidate=candidate,
                    exam=exam,
                )

        acquire_lock.assert_awaited_once_with(
            db,
            session_id=exam.session_id,
            term_id=exam.term_id,
            level_id=level_id,
        )
        db.scalar.assert_awaited_once()
        self.assertIn("EXISTS", str(db.scalar.await_args.args[0]).upper())

    async def test_unblocking_suspended_exam_is_checked_too(self):
        db = AsyncMock()
        db.scalar = AsyncMock(return_value=False)
        candidate = self.candidate()
        exam = self.exam(status=ExamStatus.SUSPENDED)
        candidate.exam_id = exam.id

        with (
            patch.object(
                ExamTimetableService,
                "level_id",
                new=AsyncMock(return_value=uuid4()),
            ),
            patch.object(
                ExamTimetableService,
                "acquire_level_lock",
                new=AsyncMock(),
            ),
        ):
            await CandidateService._require_operational_unblock_safe(
                db,
                candidate=candidate,
                exam=exam,
            )

        db.scalar.assert_awaited_once()

    async def test_unblocking_sealed_exam_defers_conflict_check_until_activation(self):
        db = AsyncMock()
        db.scalar = AsyncMock()
        candidate = self.candidate()
        exam = self.exam(status=ExamStatus.SEALED)
        candidate.exam_id = exam.id

        with (
            patch.object(
                ExamTimetableService,
                "level_id",
                new=AsyncMock(),
            ) as level_id,
            patch.object(
                ExamTimetableService,
                "acquire_level_lock",
                new=AsyncMock(),
            ) as acquire_lock,
        ):
            await CandidateService._require_operational_unblock_safe(
                db,
                candidate=candidate,
                exam=exam,
            )

        level_id.assert_not_awaited()
        acquire_lock.assert_not_awaited()
        db.scalar.assert_not_awaited()

    def test_candidate_mutation_is_frozen_during_closing(self):
        with self.assertRaisesRegex(ValueError, "Finalizing"):
            CandidateService._ensure_exam_mutable(ExamStatus.CLOSING)

    def test_candidate_mutation_is_frozen_during_cancelling(self):
        with self.assertRaisesRegex(ValueError, "Finalizing"):
            CandidateService._ensure_exam_mutable(ExamStatus.CANCELLING)


if __name__ == "__main__":
    unittest.main()
