from __future__ import annotations

import os
import unittest

from pydantic import ValidationError

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

from app import model_registry  # noqa: E402,F401
from app.core.database import Base  # noqa: E402
from app.domains.auth.student_models import StudentExamSession  # noqa: E402
from app.domains.auth.student_schemas import StudentLoginRequest  # noqa: E402


class StudentAuthContractTests(unittest.TestCase):
    def test_login_contract_uses_password_not_pin(self) -> None:
        payload = StudentLoginRequest.model_validate(
            {
                "admission_number": "STU/2026/001",
                "password": "stu/2026/001",
            }
        )
        self.assertEqual(payload.password, "stu/2026/001")

        with self.assertRaises(ValidationError):
            StudentLoginRequest.model_validate(
                {
                    "admission_number": "STU/2026/001",
                    "pin": "123456",
                }
            )

    def test_no_student_password_or_pin_verifier_is_stored(self) -> None:
        self.assertNotIn("student_cbt_credentials", Base.metadata.tables)

    def test_exam_session_is_bound_to_student_candidate_and_exam(self) -> None:
        columns = set(StudentExamSession.__table__.c.keys())
        self.assertTrue({"student_id", "candidate_id", "exam_id", "token_hash"} <= columns)
        self.assertNotIn("password", columns)
        self.assertNotIn("pin_hash", columns)


if __name__ == "__main__":
    unittest.main()
