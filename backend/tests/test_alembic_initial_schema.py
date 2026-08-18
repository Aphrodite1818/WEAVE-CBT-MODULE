from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, MetaData

from app import model_registry  # noqa: F401
from app.core.database import Base

BACKEND_ROOT = Path(__file__).resolve().parents[1]
INITIAL_REVISION = BACKEND_ROOT / "alembic" / "versions" / "0001_initial_schema.py"


def _load_initial_revision():
    spec = importlib.util.spec_from_file_location(
        "_weave_cbt_initial_revision_contract",
        INITIAL_REVISION,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _column_signature(metadata: MetaData) -> dict[str, tuple]:
    signature: dict[str, tuple] = {}
    for table_name, table in sorted(metadata.tables.items()):
        columns = []
        for column in table.columns:
            foreign_keys = tuple(
                sorted(
                    (
                        foreign_key.target_fullname,
                        foreign_key.ondelete,
                        foreign_key.onupdate,
                    )
                    for foreign_key in column.foreign_keys
                )
            )
            server_default = None
            if column.server_default is not None:
                server_default = str(column.server_default.arg)
            columns.append(
                (
                    column.name,
                    str(column.type),
                    column.nullable,
                    column.primary_key,
                    bool(column.unique),
                    server_default,
                    foreign_keys,
                )
            )
        signature[table_name] = tuple(columns)
    return signature


def _index_signature(metadata: MetaData) -> dict[str, tuple]:
    signature: dict[str, tuple] = {}
    for table_name, table in sorted(metadata.tables.items()):
        indexes = []
        for index in table.indexes:
            postgres_where = index.dialect_options["postgresql"].get("where")
            indexes.append(
                (
                    index.name,
                    bool(index.unique),
                    tuple(str(expression) for expression in index.expressions),
                    None if postgres_where is None else str(postgres_where),
                )
            )
        signature[table_name] = tuple(sorted(indexes))
    return signature


def _constraint_signature(metadata: MetaData) -> dict[str, tuple]:
    signature: dict[str, tuple] = {}
    for table_name, table in sorted(metadata.tables.items()):
        constraints = []
        for constraint in table.constraints:
            columns = tuple(column.name for column in constraint.columns)
            expression = None
            if isinstance(constraint, CheckConstraint):
                expression = str(constraint.sqltext)
            referred = None
            ondelete = None
            onupdate = None
            if isinstance(constraint, ForeignKeyConstraint):
                referred = tuple(
                    sorted(element.target_fullname for element in constraint.elements)
                )
                ondelete = constraint.ondelete
                onupdate = constraint.onupdate
            constraints.append(
                (
                    type(constraint).__name__,
                    constraint.name,
                    columns,
                    expression,
                    referred,
                    ondelete,
                    onupdate,
                )
            )
        signature[table_name] = tuple(sorted(constraints, key=repr))
    return signature


def test_initial_revision_is_first_revision_and_snapshot_exists():
    revision = _load_initial_revision()

    assert revision.revision == "0001_initial_schema"
    assert revision.down_revision is None
    assert INITIAL_REVISION.is_file()
    assert (BACKEND_ROOT / "alembic" / "schema_v1").is_dir()


def test_frozen_initial_schema_matches_current_model_registry():
    revision = _load_initial_revision()
    frozen_metadata = revision.get_schema_v1_metadata()
    runtime_metadata = Base.metadata

    assert set(frozen_metadata.tables) == set(runtime_metadata.tables)
    assert _column_signature(frozen_metadata) == _column_signature(runtime_metadata)
    assert _index_signature(frozen_metadata) == _index_signature(runtime_metadata)
    assert _constraint_signature(frozen_metadata) == _constraint_signature(runtime_metadata)
