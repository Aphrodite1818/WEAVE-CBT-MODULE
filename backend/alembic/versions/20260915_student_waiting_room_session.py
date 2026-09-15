"""allow authenticated student waiting-room sessions before exam binding

Revision ID: 20260915_student_waiting_room
Revises: 20260915_attempt_terminal_lifecycle
Create Date: 2026-09-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260915_student_waiting_room"
down_revision: str | Sequence[str] | None = "20260915_attempt_terminal_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "uq_student_exam_sessions_one_active_candidate",
        table_name="student_exam_sessions",
    )

    op.alter_column(
        "student_exam_sessions",
        "candidate_id",
        nullable=True,
    )
    op.alter_column(
        "student_exam_sessions",
        "exam_id",
        nullable=True,
    )

    op.create_check_constraint(
        "ck_student_exam_sessions_binding_pair",
        "student_exam_sessions",
        "(candidate_id IS NULL AND exam_id IS NULL) OR "
        "(candidate_id IS NOT NULL AND exam_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_student_exam_sessions_makeup_requires_binding",
        "student_exam_sessions",
        "makeup_authorization_id IS NULL OR candidate_id IS NOT NULL",
    )
    op.create_index(
        "uq_student_exam_sessions_one_active_candidate",
        "student_exam_sessions",
        ["candidate_id"],
        unique=True,
        postgresql_where=op.inline_literal(
            "revoked_at IS NULL AND candidate_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_student_exam_sessions_one_active_candidate",
        table_name="student_exam_sessions",
    )
    op.drop_constraint(
        "ck_student_exam_sessions_makeup_requires_binding",
        "student_exam_sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_student_exam_sessions_binding_pair",
        "student_exam_sessions",
        type_="check",
    )

    # Waiting-room-only sessions cannot exist under the old schema.
    op.execute(
        "DELETE FROM student_exam_sessions "
        "WHERE candidate_id IS NULL OR exam_id IS NULL"
    )

    op.alter_column(
        "student_exam_sessions",
        "candidate_id",
        nullable=False,
    )
    op.alter_column(
        "student_exam_sessions",
        "exam_id",
        nullable=False,
    )
    op.create_index(
        "uq_student_exam_sessions_one_active_candidate",
        "student_exam_sessions",
        ["candidate_id"],
        unique=True,
        postgresql_where=op.inline_literal("revoked_at IS NULL"),
    )
