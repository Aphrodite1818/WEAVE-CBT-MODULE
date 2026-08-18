from __future__ import annotations

import os
import unittest
from unittest.mock import AsyncMock

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app.domains.sync.supervisor import (  # noqa: E402
    RECONCILE_FALLBACK_SECONDS,
    SyncSupervisor,
)


class SyncSupervisorFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_periodic_reconcile_waits_until_fallback_interval(self) -> None:
        supervisor = SyncSupervisor()
        supervisor._reconcile_once = AsyncMock()  # type: ignore[method-assign]
        started_at = 100.0

        last_reconcile_at = await supervisor._reconcile_if_due(
            last_reconcile_at=started_at,
            now=started_at + RECONCILE_FALLBACK_SECONDS - 0.001,
        )

        self.assertEqual(last_reconcile_at, started_at)
        supervisor._reconcile_once.assert_not_awaited()  # type: ignore[attr-defined]

    async def test_periodic_reconcile_uses_authoritative_cursor_path_when_due(self) -> None:
        supervisor = SyncSupervisor()
        supervisor._reconcile_once = AsyncMock()  # type: ignore[method-assign]
        started_at = 100.0
        due_at = started_at + RECONCILE_FALLBACK_SECONDS

        last_reconcile_at = await supervisor._reconcile_if_due(
            last_reconcile_at=started_at,
            now=due_at,
        )

        self.assertEqual(last_reconcile_at, due_at)
        supervisor._reconcile_once.assert_awaited_once_with()  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main()
