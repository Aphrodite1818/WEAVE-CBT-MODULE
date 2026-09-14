"""cut local academic projections to Weave sync v5

Revision ID: 20260914_sync_v5
Revises: 20260822_candidate_roster
Create Date: 2026-09-14

The v5 academic contract replaces term-scoped SubjectOffering rows with
persistent CurriculumSubjectDepartment applicability and makes teacher
assignment dates authoritative. This is an intentional pre-launch cutover.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260914_sync_v5"
down_revision: str | Sequence[str] | None = "20260822_candidate_roster"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Academic levels now carry the point at which department specialization
    # becomes operational. Null means specialization is not used for the level.
    op.add_column(
        "academic_levels",
        sa.Column(
            "specialization_required_from_term_position",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_academic_levels_specialization_term_position",
        "academic_levels",
        "specialization_required_from_term_position IS NULL OR "
        "specialization_required_from_term_position BETWEEN 1 AND 3",
    )

    # Replace the v3 term-scoped offering projection with v5's persistent
    # curriculum-subject -> level-department applicability link.
    op.create_table(
        "curriculum_subject_departments",
        sa.Column("curriculum_subject_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("source_deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["curriculum_subject_id"],
            ["curriculum_subjects.id"],
            name=op.f(
                "fk_curriculum_subject_departments_curriculum_subject_id_curriculum_subjects"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name=op.f("fk_curriculum_subject_departments_department_id_departments"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_curriculum_subject_departments"),
        ),
    )
    op.create_index(
        op.f("ix_curriculum_subject_departments_source_deleted_at"),
        "curriculum_subject_departments",
        ["source_deleted_at"],
    )
    op.create_index(
        "uq_curriculum_subject_departments_current_scope",
        "curriculum_subject_departments",
        ["curriculum_subject_id", "department_id"],
        unique=True,
        postgresql_where=sa.text("source_deleted_at IS NULL"),
    )
    op.create_index(
        "ix_curriculum_subject_departments_live_subject",
        "curriculum_subject_departments",
        ["curriculum_subject_id"],
        postgresql_where=sa.text("source_deleted_at IS NULL"),
    )
    op.create_index(
        "ix_curriculum_subject_departments_live_department",
        "curriculum_subject_departments",
        ["department_id"],
        postgresql_where=sa.text("source_deleted_at IS NULL"),
    )

    # ExamTargetClass already freezes the actual class. The obsolete offering ID
    # is not meaningful in v5 and would otherwise keep the legacy table alive.
    op.drop_index("ix_exam_target_classes_offering", table_name="exam_target_classes")
    op.drop_constraint(
        "fk_exam_target_classes_subject_offering_id_subject_offerings",
        "exam_target_classes",
        type_="foreignkey",
    )
    op.drop_column("exam_target_classes", "subject_offering_id")
    op.drop_table("subject_offerings")

    # Teacher assignment validity is now entirely temporal. Remove the redundant
    # persisted boolean and indexes that encoded it.
    op.drop_index(
        "uq_teacher_assignments_active_scope",
        table_name="teacher_assignments",
    )
    op.drop_index(
        "ix_teacher_assignments_live_teacher",
        table_name="teacher_assignments",
    )
    op.drop_index(
        "ix_teacher_assignments_live_class_subject",
        table_name="teacher_assignments",
    )
    op.drop_index(
        "ix_teacher_assignments_is_active",
        table_name="teacher_assignments",
    )
    op.drop_column("teacher_assignments", "is_active")

    op.create_index(
        "ix_teacher_assignments_live_teacher_effective",
        "teacher_assignments",
        ["teacher_membership_id", "effective_from", "effective_to"],
        postgresql_where=sa.text("source_deleted_at IS NULL"),
    )
    op.create_index(
        "ix_teacher_assignments_live_scope_effective",
        "teacher_assignments",
        [
            "class_id",
            "curriculum_subject_id",
            "effective_from",
            "effective_to",
        ],
        postgresql_where=sa.text("source_deleted_at IS NULL"),
    )

    # A v3 cursor cannot safely continue against the v5 projection graph.
    op.alter_column(
        "sync_states",
        "schema_version",
        server_default=sa.text("5"),
    )
    op.execute(
        "UPDATE sync_states "
        "SET schema_version = 5, cursor = 0, bootstrap_snapshot_id = NULL, "
        "bootstrap_completed_at = NULL, last_successful_at = NULL, last_error = NULL "
        "WHERE scope = 'academics'"
    )


def downgrade() -> None:
    raise RuntimeError(
        "The CBT sync v5 academic projection cutover is intentionally irreversible."
    )
