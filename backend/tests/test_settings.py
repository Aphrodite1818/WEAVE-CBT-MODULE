import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError

TEST_ENVIRONMENT = {
    "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/cbt",
    "DEBUG": "false",
    "REDIS_URL": "redis://localhost:6379/0",
    "TASKIQ_REDIS_URL": "redis://localhost:6379/1",
}

with patch.dict(os.environ, TEST_ENVIRONMENT):
    from app.core.settings import Settings


class DatabaseSettingsTests(unittest.TestCase):
    def setUp(self):
        environment_patcher = patch.dict(os.environ, {}, clear=True)
        environment_patcher.start()
        self.addCleanup(environment_patcher.stop)

        self.required_settings = {
            "REDIS_URL": "redis://localhost:6379/0",
            "TASKIQ_REDIS_URL": "redis://localhost:6379/1",
        }

    def test_database_url_is_required(self):
        with self.assertRaises(ValidationError) as context:
            Settings(_env_file=None, **self.required_settings)

        self.assertIn("DATABASE_URL", str(context.exception))

    def test_database_url_cannot_be_blank(self):
        with self.assertRaisesRegex(
            ValidationError,
            "DATABASE_URL must use PostgreSQL",
        ):
            Settings(
                _env_file=None,
                DATABASE_URL="   ",
                **self.required_settings,
            )

    def test_database_url_rejects_non_postgresql_drivers(self):
        with self.assertRaisesRegex(
            ValidationError,
            "DATABASE_URL must use PostgreSQL",
        ):
            Settings(
                _env_file=None,
                DATABASE_URL="sqlite+aiosqlite:///cbt.db",
                **self.required_settings,
            )

    def test_database_url_normalizes_postgresql_scheme(self):
        settings = Settings(
            _env_file=None,
            DATABASE_URL="postgresql://user:password@localhost/cbt",
            **self.required_settings,
        )

        self.assertEqual(
            settings.DATABASE_URL,
            "postgresql+asyncpg://user:password@localhost/cbt",
        )


if __name__ == "__main__":
    unittest.main()
