from __future__ import annotations

import os
import unittest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app.main import app  # noqa: E402


class MainTests(unittest.TestCase):
    def test_core_local_routes_are_registered(self) -> None:
        paths = {route.path for route in app.routes}
        self.assertIn("/api/v1/installation/status", paths)
        self.assertIn("/api/v1/installation/pair", paths)
        self.assertIn("/api/v1/auth/login", paths)
        self.assertIn("/api/v1/sync/status", paths)
        self.assertIn("/api/v1/sync/reconcile", paths)
        self.assertIn("/api/v1/media/question-images", paths)
        self.assertIn("/api/v1/questions/banks", paths)
        self.assertIn("/api/v1/questions/banks/{curriculum_subject_id}", paths)
        self.assertIn("/api/v1/questions/banks/authorable", paths)
        self.assertIn("/api/v1/questions/banks/{bank_id}/single-choice", paths)
        self.assertIn("/api/v1/questions/banks/{bank_id}/multiple-choice", paths)
        self.assertIn("/api/v1/questions/{question_id}/image", paths)


if __name__ == "__main__":
    unittest.main()
