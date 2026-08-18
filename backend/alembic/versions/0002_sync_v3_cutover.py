"""Cut local academic synchronization to the v3 contract.

Revision ID: 0002_sync_v3_cutover
Revises: 0001_initial_schema
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_sync_v3_cutover"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Candidate eligibility is now derived from the synchronized relational graph
    # instead of materialized from giant offering payloads.
    op.drop_table("subject_offering_eligibilities")

    # Replace generic boolean composites with smaller partial indexes matching the
    # actual live-row predicates used by CBT execution queries.
    op.drop_index("ix_teacher_assignments_teacher_active", table_name="teacher_assignments")
    op.drop_index(
        "ix_teacher_assignments_class_subject_active",
        table_name="teacher_assignments",
    )
    live_assignment = sa.text("is_active = true AND source_deleted_at IS NULL")
    op.create_index(
        "ix_teacher_assignments_live_teacher",
        "teacher_assignments",
        ["teacher_membership_id"],
        unique=False,
        postgresql_where=live_assignment,
    )
    op.create_index(
        "ix_teacher_assignments_live_class_subject",
        "teacher_assignments",
        ["class_id", "curriculum_subject_id"],
        unique=False,
        postgresql_where=live_assignment,
    )

    op.drop_index("ix_student_enrollments_class_current", table_name="student_enrollments")
    op.drop_index("ix_student_enrollments_session_current", table_name="student_enrollments")
    live_enrollment = sa.text("is_current = true AND source_deleted_at IS NULL")
    op.create_index(
        "ix_student_enrollments_live_class",
        "student_enrollments",
        ["class_id"],
        unique=False,
        postgresql_where=live_enrollment,
    )
    op.create_index(
        "ix_student_enrollments_live_session",
        "student_enrollments",
        ["academic_session_id"],
        unique=False,
        postgresql_where=live_enrollment,
    )

    # Existing development installations must not continue from a v2 cursor. A
    # fresh v3 bootstrap is authoritative and preserves historical rows as
    # tombstones while rebuilding the live projection graph.
    op.execute("ALTER TABLE sync_states ALTER COLUMN schema_version SET DEFAULT 3")
    op.execute(
        "UPDATE sync_states SET schema_version = 3, cursor = 0, "
        "bootstrap_snapshot_id = NULL, bootstrap_completed_at = NULL, "
        "last_successful_at = NULL, last_error = NULL"
    )


def downgrade() -> None:
    raise RuntimeError("The CBT sync v3 cutover is intentionally irreversible.")
