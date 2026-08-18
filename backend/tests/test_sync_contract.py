from __future__ import annotations

import os
import unittest
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app import model_registry  # noqa: E402,F401
from app.core.database import Base  # noqa: E402
from app.domains.sync.service import ENTITY_MODELS, ENTITY_SCHEMAS  # noqa: E402
from app.integrations.weave.schemas import (  # noqa: E402
    SYNC_SCHEMA_VERSION,
    WeaveAcademicBootstrap,
    WeaveSyncChange,
)


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


if __name__ == "__main__":
    unittest.main()
