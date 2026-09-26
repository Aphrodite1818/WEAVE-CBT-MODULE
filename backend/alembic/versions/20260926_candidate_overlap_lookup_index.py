"""add candidate overlap lookup index

Revision ID: 20260926_candidate_overlap
Revises: 20260924_late_start
Create Date: 2026-09-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260926_candidate_overlap"
down_revision: str | Sequence[str] | None = "20260924_late_start"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INDEX_NAME = "ix_exam_candidates_eligible_student_exam"


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        "exam_candidates",
        ["student_id", "exam_id"],
        unique=False,
        postgresql_where=sa.text("status = 'eligible'"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="exam_candidates")
