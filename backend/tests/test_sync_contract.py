from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from pydantic import SecretStr

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
from app.domains.sync.service import (  # noqa: E402
    ENTITY_MODELS,
    ENTITY_SCHEMAS,
    SyncDependencyMissing,
    SyncService,
)
from app.integrations.weave.schemas import (  # noqa: E402
    SYNC_SCHEMA_VERSION,
    WeaveAcademicBootstrap,
    WeaveSubjectOfferingSnapshot,
    WeaveSyncChange,
    WeaveSyncDelta,
)


class _AsyncTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, traceback) -> bool:
        return False


class _FakeAsyncSession:
    def __init__(self) -> None:
        self.rollback = AsyncMock()

    def begin(self) -> _AsyncTransaction:
        return _AsyncTransaction()


class SyncContractTests(unittest.TestCase):
    def test_bootstrap_v2_parses_exact_top_level_shape(self) -> None:
        tenant_id = uuid4()
        server_id = uuid4()
        payload = WeaveAcademicBootstrap.model_validate(
            {
                "metadata": {
                    "schema_version": 2,
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
        self.assertEqual(payload.metadata.schema_version, SYNC_SCHEMA_VERSION)
        self.assertEqual(payload.metadata.cursor, 134)
        self.assertEqual(payload.school.id, tenant_id)
        self.assertEqual(payload.server.id, server_id)

    def test_incremental_dispatch_covers_every_weave_v2_entity(self) -> None:
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
                "schema_version": 2,
                "payload": None,
                "occurred_at": "2026-08-18T00:11:00Z",
            }
        )
        self.assertEqual(change.operation, "deleted")

    def test_model_registry_contains_entire_local_schema(self) -> None:
        tables = set(Base.metadata.tables)
        expected = {
            "local_actors",
            "local_actor_sessions",
            "local_refresh_tokens",
            "academic_sessions",
            "academic_terms",
            "academic_levels",
            "arm_labels",
            "departments",
            "academic_classes",
            "class_term_departments",
            "academic_subjects",
            "curricula",
            "curriculum_subjects",
            "subject_offerings",
            "subject_offering_eligibilities",
            "assessment_schemes",
            "assessment_components",
            "academic_admins",
            "academic_teachers",
            "teacher_assignments",
            "student_enrollments",
            "sync_states",
            "question_banks",
            "questions",
            "question_options",
            "exams",
            "exam_target_classes",
            "exam_invigilators",
            "exam_questions",
            "exam_question_options",
            "exam_candidates",
            "candidate_credentials",
            "exam_attempts",
            "attempt_interruptions",
            "attempt_question_allocations",
            "attempt_option_allocations",
            "attempt_answers",
            "attempt_answer_selections",
            "exam_results",
            "audit_events",
        }
        self.assertTrue(expected <= tables, expected - tables)


class SyncRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_offering_enrollment_is_detected_before_fk_write(self) -> None:
        service = SyncService()
        offering_id = uuid4()
        missing_enrollment_id = uuid4()
        snapshot = WeaveSubjectOfferingSnapshot(
            id=offering_id,
            curriculum_subject_id=uuid4(),
            academic_term_id=uuid4(),
            department_id=None,
            eligible_enrollment_ids=[missing_enrollment_id],
        )

        with (
            patch.object(
                AcademicRepository,
                "upsert_projection",
                new=AsyncMock(),
            ),
            patch.object(
                service,
                "_missing_enrollment_ids",
                new=AsyncMock(return_value=(missing_enrollment_id,)),
            ),
            patch.object(
                AcademicRepository,
                "replace_offering_eligibility",
                new=AsyncMock(),
            ) as replace_eligibility,
        ):
            with self.assertRaises(SyncDependencyMissing) as raised:
                await service._apply_snapshot_entity(
                    object(),  # type: ignore[arg-type]
                    "subject_offering",
                    snapshot,
                    synced_at=datetime.now(UTC),
                )

        self.assertEqual(raised.exception.entity_id, offering_id)
        self.assertEqual(raised.exception.missing_ids, (missing_enrollment_id,))
        replace_eligibility.assert_not_awaited()

    async def test_dependency_gap_forces_authoritative_bootstrap_recovery(self) -> None:
        cursor = 40
        offering_id = uuid4()
        missing_enrollment_id = uuid4()
        delta = WeaveSyncDelta(
            from_cursor=cursor,
            next_cursor=cursor + 1,
            has_more=False,
            changes=[
                WeaveSyncChange(
                    event_id=uuid4(),
                    cursor=cursor + 1,
                    entity_type="subject_offering",
                    entity_id=offering_id,
                    operation="updated",
                    schema_version=SYNC_SCHEMA_VERSION,
                    payload={
                        "id": str(offering_id),
                        "curriculum_subject_id": str(uuid4()),
                        "academic_term_id": str(uuid4()),
                        "department_id": None,
                        "eligible_enrollment_ids": [str(missing_enrollment_id)],
                    },
                    occurred_at=datetime.now(UTC),
                )
            ],
        )
        gateway = SimpleNamespace(fetch_changes=AsyncMock(return_value=delta))
        service = SyncService(gateway=gateway)  # type: ignore[arg-type]
        db = _FakeAsyncSession()
        state = SimpleNamespace(
            cursor=cursor,
            bootstrap_completed_at=datetime.now(UTC),
        )
        locked_state = SimpleNamespace(
            cursor=cursor,
            last_attempted_at=None,
            schema_version=SYNC_SCHEMA_VERSION,
            last_successful_at=None,
            last_error=None,
        )
        dependency_error = SyncDependencyMissing(
            entity_type="subject_offering",
            entity_id=offering_id,
            dependency_type="student_enrollment",
            missing_ids=[missing_enrollment_id],
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
                SyncRepository,
                "acquire_apply_lock",
                new=AsyncMock(),
            ),
            patch.object(
                SyncRepository,
                "get_or_create_state",
                new=AsyncMock(return_value=locked_state),
            ),
            patch.object(
                service,
                "_apply_change",
                new=AsyncMock(side_effect=dependency_error),
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
        self.assertGreaterEqual(db.rollback.await_count, 2)


if __name__ == "__main__":
    unittest.main()
