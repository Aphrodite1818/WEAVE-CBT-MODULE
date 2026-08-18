"""Create the complete initial Weave CBT database schema.

Revision ID: 0001_initial_schema
Revises:

This revision intentionally loads a frozen copy of the model sources stored in
``alembic/schema_v1``. It must not import the live application model registry:
future model changes belong in later Alembic revisions and must never change
what revision 0001 creates on a fresh database.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from alembic import op
from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

_CONSTRAINT_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

_SCHEMA_V1_DIR = Path(__file__).resolve().parents[1] / "schema_v1"
_SCHEMA_V1_MODULES = (
    "academics",
    "auth",
    "questions",
    "candidates",
    "exams",
    "attempts",
    "results",
    "audit",
    "sync",
)


class _TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class _UUIDMixin:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)


class _SchemaV1Base(_TimestampMixin, _UUIDMixin, DeclarativeBase):
    metadata = MetaData(naming_convention=_CONSTRAINT_NAMING_CONVENTION)


_schema_v1_metadata: MetaData | None = None


def _load_module(module_name: str, source_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, source_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load frozen schema source: {source_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def get_schema_v1_metadata() -> MetaData:
    """Build metadata from the immutable model-source snapshot for revision 0001."""

    global _schema_v1_metadata
    if _schema_v1_metadata is not None:
        return _schema_v1_metadata

    missing = [
        name
        for name in _SCHEMA_V1_MODULES
        if not (_SCHEMA_V1_DIR / f"{name}.py").is_file()
    ]
    if missing:
        raise RuntimeError(
            "Initial schema snapshot is incomplete; missing: " + ", ".join(missing)
        )

    frozen_database_module = types.ModuleType("app.core.database")
    frozen_database_module.Base = _SchemaV1Base

    database_module_name = "app.core.database"
    questions_module_name = "app.domains.questions.models"
    previous_database_module = sys.modules.get(database_module_name)
    previous_questions_module = sys.modules.get(questions_module_name)

    try:
        # Every frozen model source imports Base from app.core.database. Point that
        # import at the migration-only declarative base while the snapshot loads.
        sys.modules[database_module_name] = frozen_database_module

        frozen_questions = _load_module(
            "_weave_cbt_schema_v1_questions",
            _SCHEMA_V1_DIR / "questions.py",
        )

        # The frozen exam source imports QuestionType using the application's
        # absolute module path. Temporarily route that import to the frozen enum.
        sys.modules[questions_module_name] = frozen_questions

        for module_name in _SCHEMA_V1_MODULES:
            if module_name == "questions":
                continue
            _load_module(
                f"_weave_cbt_schema_v1_{module_name}",
                _SCHEMA_V1_DIR / f"{module_name}.py",
            )
    finally:
        if previous_database_module is None:
            sys.modules.pop(database_module_name, None)
        else:
            sys.modules[database_module_name] = previous_database_module

        if previous_questions_module is None:
            sys.modules.pop(questions_module_name, None)
        else:
            sys.modules[questions_module_name] = previous_questions_module

    _schema_v1_metadata = _SchemaV1Base.metadata
    return _schema_v1_metadata


def upgrade() -> None:
    """Create every table, constraint, and index in the v1 CBT schema."""

    get_schema_v1_metadata().create_all(
        bind=op.get_bind(),
        checkfirst=False,
    )


def downgrade() -> None:
    """Drop the complete v1 CBT schema in reverse dependency order."""

    get_schema_v1_metadata().drop_all(
        bind=op.get_bind(),
        checkfirst=False,
    )
