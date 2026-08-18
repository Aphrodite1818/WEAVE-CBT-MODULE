from __future__ import annotations

import ast
import importlib.util
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
INITIAL_REVISION = BACKEND_ROOT / "alembic" / "versions" / "0001_initial_schema.py"

EXPECTED_INITIAL_TABLES = {
    "academic_admins",
    "academic_levels",
    "academic_sessions",
    "academic_subjects",
    "academic_teachers",
    "arm_labels",
    "assessment_schemes",
    "audit_events",
    "local_actors",
    "school_profiles",
    "sync_states",
    "academic_classes",
    "academic_terms",
    "assessment_components",
    "curricula",
    "departments",
    "local_actor_sessions",
    "class_term_departments",
    "curriculum_subjects",
    "local_refresh_tokens",
    "student_enrollments",
    "exams",
    "question_banks",
    "subject_offerings",
    "teacher_assignments",
    "exam_candidates",
    "exam_invigilators",
    "exam_target_classes",
    "questions",
    "subject_offering_eligibilities",
    "candidate_credentials",
    "exam_attempts",
    "exam_questions",
    "question_options",
    "attempt_interruptions",
    "attempt_question_allocations",
    "exam_question_options",
    "exam_results",
    "attempt_answers",
    "attempt_option_allocations",
    "attempt_answer_selections",
}


def _load_initial_revision():
    spec = importlib.util.spec_from_file_location(
        "_weave_cbt_initial_revision_contract",
        INITIAL_REVISION,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_initial_revision_is_static_first_revision() -> None:
    revision = _load_initial_revision()
    source = INITIAL_REVISION.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert revision.revision == "0001_initial_schema"
    assert revision.down_revision is None
    assert not (BACKEND_ROOT / "alembic" / "schema_v1").exists()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("app")
        elif isinstance(node, ast.Import):
            assert all(not alias.name.startswith("app") for alias in node.names)


def test_initial_revision_covers_the_complete_v1_table_set() -> None:
    revision = _load_initial_revision()

    created_tables = {
        statement.split()[2]
        for statement in revision._UPGRADE_SQL
        if statement.startswith("CREATE TABLE ")
    }
    dropped_tables = set(re.findall(r"op\.drop_table\(['\"]([^'\"]+)['\"]\)", INITIAL_REVISION.read_text(encoding="utf-8")))

    assert created_tables == EXPECTED_INITIAL_TABLES
    assert dropped_tables == EXPECTED_INITIAL_TABLES
