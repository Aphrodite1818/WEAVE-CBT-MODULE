"""add elective selection projection

Revision ID: 20260927_elective_selection
Revises: 20260926_candidate_overlap
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260927_elective_selection"
down_revision: str | Sequence[str] | None = "20260926_candidate_overlap"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "curriculum_subjects",
        sa.Column("elective_group_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_curriculum_subjects_elective_group_id",
        "curriculum_subjects",
        ["elective_group_id"],
        unique=False,
    )

    op.create_table(
        "student_elective_selections",
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("elective_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("curriculum_subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source_deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["curriculum_subject_id"],
            ["curriculum_subjects.id"],
            ondelete="RESTRICT",
            name="fk_student_elective_selections_curriculum_subject_id_curriculum_subjects",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_student_elective_selections"),
    )
    op.create_index(
        "ix_student_elective_selections_student_id",
        "student_elective_selections",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        "ix_student_elective_selections_elective_group_id",
        "student_elective_selections",
        ["elective_group_id"],
        unique=False,
    )
    op.create_index(
        "ix_student_elective_selections_curriculum_subject_id",
        "student_elective_selections",
        ["curriculum_subject_id"],
        unique=False,
    )
    op.create_index(
        "ix_student_elective_selections_source_deleted_at",
        "student_elective_selections",
        ["source_deleted_at"],
        unique=False,
    )
    op.create_index(
        "uq_student_elective_selections_live_student_subject",
        "student_elective_selections",
        ["student_id", "curriculum_subject_id"],
        unique=True,
        postgresql_where=sa.text("source_deleted_at IS NULL"),
    )
    op.create_index(
        "ix_student_elective_selections_live_group_student",
        "student_elective_selections",
        ["elective_group_id", "student_id"],
        unique=False,
        postgresql_where=sa.text("source_deleted_at IS NULL"),
    )
    op.create_index(
        "ix_student_elective_selections_live_subject_student",
        "student_elective_selections",
        ["curriculum_subject_id", "student_id"],
        unique=False,
        postgresql_where=sa.text("source_deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_student_elective_selections_live_subject_student",
        table_name="student_elective_selections",
    )
    op.drop_index(
        "ix_student_elective_selections_live_group_student",
        table_name="student_elective_selections",
    )
    op.drop_index(
        "uq_student_elective_selections_live_student_subject",
        table_name="student_elective_selections",
    )
    op.drop_index(
        "ix_student_elective_selections_source_deleted_at",
        table_name="student_elective_selections",
    )
    op.drop_index(
        "ix_student_elective_selections_curriculum_subject_id",
        table_name="student_elective_selections",
    )
    op.drop_index(
        "ix_student_elective_selections_elective_group_id",
        table_name="student_elective_selections",
    )
    op.drop_index(
        "ix_student_elective_selections_student_id",
        table_name="student_elective_selections",
    )
    op.drop_table("student_elective_selections")

    op.drop_index(
        "ix_curriculum_subjects_elective_group_id",
        table_name="curriculum_subjects",
    )
    op.drop_column("curriculum_subjects", "elective_group_id")
