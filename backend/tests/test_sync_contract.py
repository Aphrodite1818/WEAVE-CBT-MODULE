from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from pydantic import SecretStr, ValidationError

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app import model_registry  # noqa: E402,F401
from app.core.database import Base  # noqa: E402
from app.domains.academics.repository import AcademicRepository  # noqa: E402
from app.domains.node.identity_store import node_identity_store  # noqa: E402
from app.domains.sync.repository import SyncRepository  # noqa: E402
from app.domains.sync.service import ENTITY_MODELS, ENTITY_SCHEMAS, SyncService  # noqa: E402
from app.integrations.weave.exceptions import WeaveRequestRejectedError  # noqa: E402
from app.integrations.weave.schemas import (  # noqa: E402
    SYNC_SCHEMA_VERSION,
    WeaveAcademicBootstrap,
    WeaveSubjectOfferingSnapshot,
    WeaveSyncChange,
)


class _FakeAsyncSession:
    def __init__(self) -> None:
        self.rollback = AsyncMock()


class SyncContractTests(unittest.TestCase):
    def test_bootstrap_v3_parses_exact_top_level_shape(self) -> None:
        tenant_id = uuid4()
        server_id = uuid4()
        payload = WeaveAcademicBootstrap.model_validate(
            {
                "metadata": {
                    "schema_version": SYNC_SCHEMA_VERSION,
                    "snapshot_id": str(uuid4()),
                    "generated_at": "2026-08-18T00:10:46Z",
                    "cursor": 134,
                },
                "school": {
                    "id": str(tenant_id),
                    "name": "Debright college",
                    "institution_type": "SECONDARY_SCHOOL",
                    "timezone": "Africa/Lagos",
                },
                "server": {"id": str(server_id), "name": "Debright server 1"},
                "sessions": [],
                "terms": [],
                "levels": [],
                "arm_labels": [],
                "departments": [],
                "classes": [],
                "class_term_departments": [],
                "subjects": [],
                "curricula": [],
                "curriculum_subjects": [],
                "offerings": [],
                "assessment_schemes": [],
                "assessment_components": [],
                "admins": [],
                "teachers": [],
                "teacher_assignments": [],
                "student_enrollments": [],
            }
        )
        self.assertEqual(payload.metadata.schema_version, 3)
        self.assertEqual(payload.metadata.cursor, 134)
        self.assertEqual(payload.school.id, tenant_id)
        self.assertEqual(payload.server.id, server_id)

    def test_incremental_dispatch_covers_every_weave_v3_entity(self) -> None:
        expected = {
            "academic_level",
            "department",
            "arm_label",
            "class",
            "class_term_department",
            "academic_session",
            "academic_term",
            "subject",
            "curriculum",
            "curriculum_subject",
            "subject_offering",
            "assessment_scheme",
            "assessment_component",
            "admin",
            "teacher",
            "teacher_assignment",
            "student_enrollment",
        }
        self.assertEqual(set(ENTITY_MODELS), expected)
        self.assertEqual(set(ENTITY_SCHEMAS), expected)

    def test_deleted_change_requires_null_tombstone(self) -> None:
        change = WeaveSyncChange.model_validate(
            {
                "event_id": str(uuid4()),
                "cursor": 135,
                "entity_type": "class",
                "entity_id": str(uuid4()),
                "operation": "deleted",
                "schema_version": SYNC_SCHEMA_VERSION,
                "payload": None,
                "occurred_at": "2026-08-18T00:11:00Z",
            }
        )
        self.assertEqual(change.operation, "deleted")

    def test_offering_contract_rejects_legacy_candidate_array(self) -> None:
        with self.assertRaises(ValidationError):
            WeaveSubjectOfferingSnapshot.model_validate(
                {
                    "id": str(uuid4()),
                    "curriculum_subject_id": str(uuid4()),
                    "academic_term_id": str(uuid4()),
                    "department_id": None,
                    "eligible_enrollment_ids": [str(uuid4())],
                }
            )

    def test_model_registry_contains_v3_schema_without_eligibility_table(self) -> None:
        tables = set(Base.metadata.tables)
        self.assertNotIn("subject_offering_eligibilities", tables)
        expected = {
            "academic_sessions",
            "academic_terms",
            "academic_levels",
            "academic_classes",
            "curricula",
            "curriculum_subjects",
            "subject_offerings",
            "academic_teachers",
            "teacher_assignments",
            "student_enrollments",
            "sync_states",
            "exams",
            "exam_attempts",
            "exam_results",
        }
        self.assertTrue(expected <= tables, expected - tables)


class SyncApplyTests(unittest.IsolatedAsyncioTestCase):
    async def test_replacements_tombstone_old_rows_before_any_live_upsert(self) -> None:
        service = SyncService()
        now = datetime.now(UTC)
        class_id = uuid4()
        curriculum_subject_id = uuid4()
        student_id = uuid4()
        old_assignment = uuid4()
        new_assignment = uuid4()
        old_enrollment = uuid4()
        new_enrollment = uuid4()

        changes = [
            WeaveSyncChange(
                event_id=uuid4(),
                cursor=1,
                entity_type="teacher_assignment",
                entity_id=old_assignment,
                operation="deleted",
                schema_version=SYNC_SCHEMA_VERSION,
                payload=None,
                occurred_at=now,
            ),
            WeaveSyncChange(
                event_id=uuid4(),
                cursor=2,
                entity_type="student_enrollment",
                entity_id=old_enrollment,
                operation="deleted",
                schema_version=SYNC_SCHEMA_VERSION,
                payload=None,
                occurred_at=now,
            ),
            WeaveSyncChange(
                event_id=uuid4(),
                cursor=3,
                entity_type="student_enrollment",
                entity_id=new_enrollment,
                operation="created",
                schema_version=SYNC_SCHEMA_VERSION,
                payload={
                    "id": str(new_enrollment),
                    "student_id": str(student_id),
                    "admission_number": "STD-001",
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                    "academic_level_id": str(uuid4()),
                    "class_id": str(class_id),
                    "academic_session_id": str(uuid4()),
                    "is_current": True,
                    "student_status": "active",
                },
                occurred_at=now,
            ),
            WeaveSyncChange(
                event_id=uuid4(),
                cursor=4,
                entity_type="teacher_assignment",
                entity_id=new_assignment,
                operation="created",
                schema_version=SYNC_SCHEMA_VERSION,
                payload={
                    "id": str(new_assignment),
                    "teacher_membership_id": str(uuid4()),
                    "class_id": str(class_id),
                    "curriculum_subject_id": str(curriculum_subject_id),
                    "is_active": True,
                    "effective_from": now.date().isoformat(),
                    "effective_to": None,
                },
                occurred_at=now,
            ),
        ]

        calls: list[tuple[str, str]] = []

        async def tombstone(_db, model, _ids, **_kwargs):
            calls.append(("tombstone", model.__tablename__))

        async def upsert(_db, model, _rows, **_kwargs):
            calls.append(("upsert", model.__tablename__))

        with (
            patch.object(
                AcademicRepository,
                "bulk_tombstone_projections",
                new=tombstone,
            ),
            patch.object(
                AcademicRepository,
                "bulk_upsert_projections",
                new=upsert,
            ),
        ):
            await service._apply_delta_page(object(), changes)  # type: ignore[arg-type]

        first_upsert = next(
            index for index, call in enumerate(calls) if call[0] == "upsert"
        )
        self.assertTrue(all(call[0] == "tombstone" for call in calls[:first_upsert]))
        self.assertIn(("tombstone", "teacher_assignments"), calls)
        self.assertIn(("tombstone", "student_enrollments"), calls)
        self.assertIn(("upsert", "teacher_assignments"), calls)
        self.assertIn(("upsert", "student_enrollments"), calls)

    async def test_cursor_expiry_forces_authoritative_bootstrap(self) -> None:
        cursor = 40
        gateway = SimpleNamespace(
            fetch_changes=AsyncMock(
                side_effect=WeaveRequestRejectedError(
                    status_code=409,
                    detail="bootstrap required",
                )
            )
        )
        service = SyncService(gateway=gateway)  # type: ignore[arg-type]
        db = _FakeAsyncSession()
        state = SimpleNamespace(
            cursor=cursor,
            bootstrap_completed_at=datetime.now(UTC),
            schema_version=SYNC_SCHEMA_VERSION,
        )
        recovered = object()

        with (
            patch.object(
                node_identity_store,
                "load",
                return_value=SimpleNamespace(
                    server_credential=SecretStr("server-credential")
                ),
            ),
            patch.object(
                SyncRepository,
                "get_state",
                new=AsyncMock(return_value=state),
            ),
            patch.object(
                service,
                "bootstrap",
                new=AsyncMock(return_value=recovered),
            ) as bootstrap,
        ):
            result = await service.reconcile(db)  # type: ignore[arg-type]

        self.assertIs(result, recovered)
        bootstrap.assert_awaited_once_with(db, force=True)


if __name__ == "__main__":
    unittest.main()
