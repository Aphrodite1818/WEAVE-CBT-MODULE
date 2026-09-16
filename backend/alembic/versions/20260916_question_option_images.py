"""add answer-option image snapshots

Revision ID: 20260916_option_images
Revises: 20260915_student_waiting_room
Create Date: 2026-09-16

Answer choices may now carry text, an image, or both. Media references are
preserved from source questions through sealed exam snapshots and candidate
attempt snapshots so an authored image remains stable during execution.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260916_option_images"
down_revision: str | Sequence[str] | None = "20260915_student_waiting_room"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_option_image(table: str, index_name: str, constraint_name: str) -> None:
    op.alter_column(table, "text", existing_type=sa.Text(), nullable=True)
    op.add_column(table, sa.Column("image_asset_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        f"fk_{table}_image_asset_id_media_assets",
        table,
        "media_assets",
        ["image_asset_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(index_name, table, ["image_asset_id"], unique=False)
    op.create_check_constraint(
        constraint_name,
        table,
        "text IS NOT NULL OR image_asset_id IS NOT NULL",
    )


def _drop_option_image(table: str, index_name: str, constraint_name: str) -> None:
    # Image-only choices need a bounded textual downgrade value before restoring
    # the legacy NOT NULL column shape.
    op.execute(sa.text(f"UPDATE {table} SET text = '' WHERE text IS NULL"))
    op.drop_constraint(constraint_name, table, type_="check")
    op.drop_index(index_name, table_name=table)
    op.drop_constraint(
        f"fk_{table}_image_asset_id_media_assets",
        table,
        type_="foreignkey",
    )
    op.drop_column(table, "image_asset_id")
    op.alter_column(table, "text", existing_type=sa.Text(), nullable=False)


def upgrade() -> None:
    _add_option_image(
        "question_options",
        "ix_question_options_image_asset_id",
        "ck_question_options_content_required",
    )
    _add_option_image(
        "exam_question_options",
        "ix_exam_question_options_image_asset_id",
        "ck_exam_question_options_content_required",
    )
    _add_option_image(
        "attempt_option_allocations",
        "ix_attempt_option_allocations_image_asset_id",
        "ck_attempt_options_content_required",
    )


def downgrade() -> None:
    _drop_option_image(
        "attempt_option_allocations",
        "ix_attempt_option_allocations_image_asset_id",
        "ck_attempt_options_content_required",
    )
    _drop_option_image(
        "exam_question_options",
        "ix_exam_question_options_image_asset_id",
        "ck_exam_question_options_content_required",
    )
    _drop_option_image(
        "question_options",
        "ix_question_options_image_asset_id",
        "ck_question_options_content_required",
    )
