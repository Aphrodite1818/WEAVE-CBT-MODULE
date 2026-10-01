from __future__ import annotations

import unittest
from pathlib import Path


class StaffCloudAuthMigrationTests(unittest.TestCase):
    def test_migration_adds_session_cloud_credentials_and_local_recovery(self):
        migration = (
            Path(__file__).parents[1]
            / "alembic"
            / "versions"
            / "20261001_staff_cloud_auth.py"
        ).read_text(encoding="utf-8")

        self.assertIn('revision: str = "20261001_staff_cloud_auth"', migration)
        self.assertIn(
            'down_revision: str | Sequence[str] | None = "20260927_elective_selection"',
            migration,
        )
        self.assertIn("weave_access_token_encrypted", migration)
        self.assertIn("weave_access_token_expires_at", migration)
        self.assertIn("weave_refresh_token_encrypted", migration)
        self.assertIn("weave_refresh_token_expires_at", migration)
        self.assertIn("weave_refresh_operation_id", migration)
        self.assertIn("weave_auth_state", migration)
        self.assertIn("refresh_operation_id", migration)
        self.assertIn("replacement_token_encrypted", migration)
        self.assertIn('server_default="legacy"', migration)


if __name__ == "__main__":
    unittest.main()
