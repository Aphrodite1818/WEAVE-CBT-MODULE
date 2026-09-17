"""add candidate roster version snapshot

Revision ID: 20260822_candidate_roster
Revises: 20260822_cred_schema
Create Date: 2026-08-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260822_candidate_roster"
down_revision: str | Sequence[str] | None = "20260822_cred_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "exam_candidates",
        sa.Column(
            "roster_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.create_check_constraint(
        "ck_exam_candidates_roster_version_positive",
        "exam_candidates",
        "roster_version >= 1",
    )
    op.create_index(
        "ix_exam_candidates_roster_version",
        "exam_candidates",
        ["roster_version"],
    )
    op.create_index(
        "ix_exam_candidates_exam_roster_version",
        "exam_candidates",
        ["exam_id", "roster_version"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_exam_candidates_exam_roster_version", table_name="exam_candidates"
    )
    op.drop_index("ix_exam_candidates_roster_version", table_name="exam_candidates")
    op.drop_constraint(
        "ck_exam_candidates_roster_version_positive",
        "exam_candidates",
        type_="check",
    )
    op.drop_column("exam_candidates", "roster_version")
