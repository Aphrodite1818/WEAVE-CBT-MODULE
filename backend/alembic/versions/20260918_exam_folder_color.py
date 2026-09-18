"""add persisted exam folder colour

Revision ID: 20260918_exam_folder_color
Revises: 20260918_exam_lead_author
Create Date: 2026-09-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260918_exam_folder_color"
down_revision: str | Sequence[str] | None = "20260918_exam_lead_author"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "exams",
        sa.Column("folder_color", sa.String(length=7), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("exams", "folder_color")
