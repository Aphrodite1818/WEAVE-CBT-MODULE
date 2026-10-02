"""Widen exam status to accommodate the cancelling lifecycle state.

Revision ID: 20261002_exam_status_length
Revises: 20261001_question_ai_import
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261002_exam_status_length"
down_revision: str | Sequence[str] | None = "20261001_question_ai_import"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Extending the enum CHECK constraint does not widen its VARCHAR storage.
    op.alter_column(
        "exams",
        "status",
        existing_type=sa.String(length=9),
        type_=sa.String(length=10),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Do not silently truncate or rewrite a cancellation already in progress.
    op.execute("LOCK TABLE exams IN ACCESS EXCLUSIVE MODE")
    op.execute(
        """DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM exams WHERE length(status) > 9) THEN
            RAISE EXCEPTION 'Cannot narrow exams.status while cancellation is in progress';
        END IF;
        END $$"""
    )
    op.alter_column(
        "exams",
        "status",
        existing_type=sa.String(length=10),
        type_=sa.String(length=9),
        existing_nullable=False,
    )
