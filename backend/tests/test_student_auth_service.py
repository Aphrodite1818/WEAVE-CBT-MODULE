import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

from app.domains.auth.student_schemas import StudentExamAvailability  # noqa: E402
from app.domains.auth.student_service import StudentAuthService  # noqa: E402


class StudentAuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_creates_exam_scoped_opaque_session(self):
        student_id = uuid4()
        candidate_id = uuid4()
        exam_id = uuid4()
        enrollment = SimpleNamespace(student_id=student_id)
        credential = SimpleNamespace(pin_hash="stored-hash")
        candidate = SimpleNamespace(
            id=candidate_id,
            display_name="Candidate A",
        )
        exam = SimpleNamespace(
            id=exam_id,
            title="Mathematics",
            scheduled_start_at=None,
            activated_at=None,
        )
        captured = {}

        async def add_session(_db, session):
            captured["session"] = session
            return session

        db = AsyncMock()
        with patch.object(
            StudentAuthService,
            "_get_current_enrollment",
            AsyncMock(return_value=enrollment),
        ), patch(
            "app.domains.auth.student_service.CandidateRepository.get_active_credential_by_student_id",
            AsyncMock(return_value=credential),
        ), patch(
            "app.domains.auth.student_service.verify_candidate_pin",
            AsyncMock(return_value=True),
        ), patch.object(
            StudentAuthService,
            "_resolve_candidate",
            AsyncMock(
                return_value=(
                    candidate,
                    exam,
                    None,
                    StudentExamAvailability.READY,
                )
            ),
        ), patch(
            "app.domains.auth.student_service.StudentAuthRepository.list_unrevoked_sessions_for_student",
            AsyncMock(return_value=[]),
        ), patch(
            "app.domains.auth.student_service.StudentAuthRepository.save_sessions",
            AsyncMock(return_value=[]),
        ), patch(
            "app.domains.auth.student_service.StudentAuthRepository.add_session",
            AsyncMock(side_effect=add_session),
        ):
            result = await StudentAuthService.login(
                db,
                admission_number="STU001",
                pin="123456",
            )

        self.assertEqual(result.response.student_id, student_id)
        self.assertEqual(result.response.candidate_id, candidate_id)
        self.assertEqual(result.response.exam_id, exam_id)
        self.assertFalse(result.response.is_makeup)
        self.assertNotEqual(result.raw_token, captured["session"].token_hash)
        self.assertEqual(len(captured["session"].token_hash), 64)


if __name__ == "__main__":
    unittest.main()
