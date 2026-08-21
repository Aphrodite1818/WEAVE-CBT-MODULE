from __future__ import annotations

import ast
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION = BACKEND_ROOT / "alembic" / "versions" / "7dfe6fd9894b_.py"
MODEL_REGISTRY = BACKEND_ROOT / "app" / "model_registry.py"


def test_runtime_models_are_registered_with_alembic() -> None:
    source = MODEL_REGISTRY.read_text(encoding="utf-8")

    assert "from app.domains.runtime import models as runtime_models" in source


def test_cutover_migration_is_valid_python() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    ast.parse(source)


def test_cutover_creates_and_drops_runtime_tables() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'op.create_table(\n        "cbt_runtime_states"' in source
    assert 'op.create_table(\n        "realtime_outbox_events"' in source
    assert 'op.drop_table("realtime_outbox_events")' in source
    assert 'op.drop_table("cbt_runtime_states")' in source


def test_cutover_does_not_invent_historical_exam_or_result_values() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    # Old DRAFT exams did not contain enough information to infer the new
    # question-bank/count contract reliably, and old generic result scores do
    # not map unambiguously to the new raw/component score split.
    assert "Cannot infer question_bank_id" not in source
    assert "SET question_count = COALESCE" not in source
    assert "raw_score = score::integer" not in source
    assert "component_score = score" not in source

    # This is an explicit pre-launch cutover instead of a lossy data rewrite.
    assert "_require_empty_exam_domain()" in source


def test_cutover_aligns_result_calculated_at_server_default() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert '"calculated_at",' in source
    assert 'server_default=sa.text("now()")' in source
