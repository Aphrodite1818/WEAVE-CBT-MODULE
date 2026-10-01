"""add AI question import idempotency

Revision ID: 20261001_question_ai_import
Revises: 20261001_staff_cloud_auth
Create Date: 2026-10-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261001_question_ai_import"
down_revision: str | Sequence[str] | None = "20261001_staff_cloud_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "question_ai_import_batches",
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["local_actors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["bank_id"], ["question_banks.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("draft_id", name="uq_question_ai_import_batches_draft_id"),
    )
    op.create_index(
        "ix_question_ai_import_batches_bank",
        "question_ai_import_batches",
        ["bank_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_question_ai_import_batches_actor",
        "question_ai_import_batches",
        ["actor_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "question_ai_import_items",
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["question_ai_import_batches.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id",
            "position",
            name="uq_question_ai_import_items_batch_position",
        ),
        sa.UniqueConstraint(
            "batch_id",
            "question_id",
            name="uq_question_ai_import_items_batch_question",
        ),
    )
    op.create_index(
        "ix_question_ai_import_items_question",
        "question_ai_import_items",
        ["question_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_question_ai_import_items_question",
        table_name="question_ai_import_items",
    )
    op.drop_table("question_ai_import_items")
    op.drop_index(
        "ix_question_ai_import_batches_actor",
        table_name="question_ai_import_batches",
    )
    op.drop_index(
        "ix_question_ai_import_batches_bank",
        table_name="question_ai_import_batches",
    )
    op.drop_table("question_ai_import_batches")
