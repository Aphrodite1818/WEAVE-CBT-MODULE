"""separate exam creator provenance from lead author

Revision ID: 20260918_exam_lead_author
Revises: 20260917_exam_execution
Create Date: 2026-09-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260918_exam_lead_author"
down_revision: str | Sequence[str] | None = "20260917_exam_execution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "exams",
        sa.Column("lead_teacher_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "exams",
        sa.Column("lead_assigned_by_actor_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "exams",
        sa.Column("lead_assigned_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_foreign_key(
        "fk_exams_lead_teacher_id_academic_teachers",
        "exams",
        "academic_teachers",
        ["lead_teacher_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_exams_lead_assigned_by_actor_id_local_actors",
        "exams",
        "local_actors",
        ["lead_assigned_by_actor_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_exams_lead_teacher_id",
        "exams",
        ["lead_teacher_id"],
        unique=False,
    )
    op.create_index(
        "ix_exams_lead_assigned_by_actor_id",
        "exams",
        ["lead_assigned_by_actor_id"],
        unique=False,
    )

    # Existing teacher-created papers previously treated created_by_actor_id as
    # both provenance and lead authority. Preserve that behavior by translating
    # the creator's Weave membership to the synchronized academic teacher row.
    # Joining on text avoids unsafe UUID casts if legacy membership data is bad.
    op.execute(
        """
        UPDATE exams AS e
        SET lead_teacher_id = t.id
        FROM local_actors AS a
        JOIN academic_teachers AS t
          ON t.id::text = a.weave_membership_id
        WHERE e.created_by_actor_id = a.id
          AND a.role = 'teacher'
        """
    )

    # Mark only leadership decisions that can be reconstructed safely. Admin
    # creators become explicitly admin-led. Teacher creators become explicit
    # teacher-led only when their synchronized teacher row was resolved above.
    # Any malformed legacy teacher identity is left without assignment metadata
    # so the service's legacy creator-as-lead fallback remains available until
    # an administrator deliberately assigns a valid lead.
    op.execute(
        """
        UPDATE exams AS e
        SET lead_assigned_by_actor_id = e.created_by_actor_id,
            lead_assigned_at = e.created_at
        FROM local_actors AS a
        WHERE e.created_by_actor_id = a.id
          AND (a.role = 'admin' OR e.lead_teacher_id IS NOT NULL)
        """
    )

    op.create_check_constraint(
        "ck_exams_lead_assignment_actor_required",
        "exams",
        "lead_assigned_at IS NULL OR lead_assigned_by_actor_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_exams_lead_assignment_actor_required",
        "exams",
        type_="check",
    )
    op.drop_index("ix_exams_lead_assigned_by_actor_id", table_name="exams")
    op.drop_index("ix_exams_lead_teacher_id", table_name="exams")
    op.drop_constraint(
        "fk_exams_lead_assigned_by_actor_id_local_actors",
        "exams",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_exams_lead_teacher_id_academic_teachers",
        "exams",
        type_="foreignkey",
    )
    op.drop_column("exams", "lead_assigned_at")
    op.drop_column("exams", "lead_assigned_by_actor_id")
    op.drop_column("exams", "lead_teacher_id")
