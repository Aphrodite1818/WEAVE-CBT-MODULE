import os
import unittest
from datetime import datetime, timezone

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test",
)
os.environ.setdefault(
    "REDIS_URL",
    "redis://localhost:6379/15",
)

from app.domains.attempts.exceptions import (  # noqa: E402
    AttemptTimeExhausted,
    ExamNotYetOpen,
    ExamStartWindowClosed,
)
from app.domains.attempts.models import AttemptStatus, ExamAttempt  # noqa: E402
from app.domains.attempts.service import (  # noqa: E402
    ensure_exam_accepts_new_attempt,
    ensure_interrupted_attempt_can_resume,
)
from app.domains.exams.models import Exam, ExamStatus  # noqa: E402


class AttemptWindowPolicyTests(unittest.TestCase):
    def setUp(self):
        self.opens_at = datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc)
        self.closes_at = datetime(2026, 8, 11, 11, 0, tzinfo=timezone.utc)
        self.exam = Exam(
            status=ExamStatus.ACTIVE,
            opens_at=self.opens_at,
            closes_at=self.closes_at,
        )

    def test_new_attempt_is_allowed_inside_exam_window(self):
        now = datetime(2026, 8, 11, 10, 59, tzinfo=timezone.utc)

        ensure_exam_accepts_new_attempt(self.exam, now=now)

    def test_new_attempt_is_blocked_at_exact_close_time(self):
        with self.assertRaises(ExamStartWindowClosed):
            ensure_exam_accepts_new_attempt(self.exam, now=self.closes_at)

    def test_new_attempt_is_blocked_after_close_time(self):
        now = datetime(2026, 8, 11, 11, 1, tzinfo=timezone.utc)

        with self.assertRaises(ExamStartWindowClosed):
            ensure_exam_accepts_new_attempt(self.exam, now=now)

    def test_new_attempt_is_blocked_before_open_time(self):
        now = datetime(2026, 8, 11, 9, 59, tzinfo=timezone.utc)

        with self.assertRaises(ExamNotYetOpen):
            ensure_exam_accepts_new_attempt(self.exam, now=now)


class AttemptResumePolicyTests(unittest.TestCase):
    def test_interrupted_attempt_can_resume_with_remaining_time(self):
        attempt = ExamAttempt(
            status=AttemptStatus.INTERRUPTED,
            time_limit_seconds=3600,
            elapsed_seconds=2100,
            active_since=None,
        )

        ensure_interrupted_attempt_can_resume(attempt)

    def test_interrupted_attempt_cannot_resume_without_remaining_time(self):
        attempt = ExamAttempt(
            status=AttemptStatus.INTERRUPTED,
            time_limit_seconds=3600,
            elapsed_seconds=3600,
            active_since=None,
        )

        with self.assertRaises(AttemptTimeExhausted):
            ensure_interrupted_attempt_can_resume(attempt)


if __name__ == "__main__":
    unittest.main()
