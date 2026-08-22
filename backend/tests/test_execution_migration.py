import importlib.util
import os
import unittest
from pathlib import Path

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")


class ExecutionMigrationTests(unittest.TestCase):
    def test_execution_migration_is_chained_from_current_head(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "alembic"
            / "versions"
            / "c4f31a2d9e77_makeup_attempt_sessions.py"
        )
        spec = importlib.util.spec_from_file_location("execution_migration", path)
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.revision, "c4f31a2d9e77")
        self.assertEqual(module.down_revision, "b91d2c4e7a10")


if __name__ == "__main__":
    unittest.main()
