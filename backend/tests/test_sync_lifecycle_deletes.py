from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app.domains.academics.repository import AcademicRepository  # noqa: E402
from app.domains.sync.service import ENTITY_MODELS, SyncService  # noqa: E402
from app.integrations.weave.schemas import WeaveSyncChange  # noqa: E402


class SyncLifecycleDeleteTests(unittest.IsolatedAsyncioTestCase):
    async def test_revoked_academic_entities_tombstone_existing_local_projection(self) -> None:
        service = SyncService()
        occurred_at = datetime.now(UTC)

        for entity_type in ("student_enrollment", "teacher_assignment"):
            with self.subTest(entity_type=entity_type):
                entity_id = uuid4()
                change = WeaveSyncChange(
                    event_id=uuid4(),
                    cursor=200,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    operation="deleted",
                    schema_version=2,
                    payload=None,
                    occurred_at=occurred_at,
                )
                db = object()

                with patch.object(
                    AcademicRepository,
                    "tombstone_projection",
                    new=AsyncMock(),
                ) as tombstone_projection:
                    await service._apply_change(db, change)  # type: ignore[arg-type]

                tombstone_projection.assert_awaited_once_with(
                    db,
                    ENTITY_MODELS[entity_type],
                    entity_id,
                    deleted_at=occurred_at,
                )


if __name__ == "__main__":
    unittest.main()
