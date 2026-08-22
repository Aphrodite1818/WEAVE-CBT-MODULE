import os
import unittest
from datetime import UTC, datetime, timedelta

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

from app.domains.exams.timetable_service import ExamTimetableService  # noqa: E402


class TimetableIntervalTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 8, 22, 10, 0, tzinfo=UTC)

    def test_overlapping_same_level_slots_conflict(self):
        self.assertTrue(
            ExamTimetableService.intervals_overlap(
                self.start,
                self.start + timedelta(hours=1),
                self.start + timedelta(minutes=30),
                self.start + timedelta(hours=1, minutes=30),
            )
        )

    def test_touching_slots_do_not_overlap(self):
        self.assertFalse(
            ExamTimetableService.intervals_overlap(
                self.start,
                self.start + timedelta(hours=1),
                self.start + timedelta(hours=1),
                self.start + timedelta(hours=2),
            )
        )


if __name__ == "__main__":
    unittest.main()
