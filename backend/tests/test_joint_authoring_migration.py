from __future__ import annotations

import ast
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    BACKEND_ROOT
    / "alembic"
    / "versions"
    / "20260915_joint_exam_authoring.py"
)


def test_joint_authoring_migration_is_valid_python() -> None:
    ast.parse(MIGRATION.read_text(encoding="utf-8"))


def test_joint_authoring_migration_has_expected_parent() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision: str | Sequence[str] | None = "20260914_sync_v5"' in source


def test_joint_authoring_migration_replaces_title_based_exam_identity() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'op.drop_index("uq_exams_scope_title_revision", table_name="exams")' in source
    assert '"uq_exams_scope_revision"' in source
    assert '"authoring_version"' in source


def test_joint_authoring_migration_preserves_manual_contributor_provenance() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert '"added_by_actor_id"' in source
    assert "weave_cbt_fill_selection_contributor" in source
    assert "weave_cbt_fill_frozen_contributor" in source
    assert "CREATE TRIGGER" in source
