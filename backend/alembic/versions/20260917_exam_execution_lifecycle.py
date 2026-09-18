"""add durable exam execution lifecycle and result review

Revision ID: 20260917_exam_execution
Revises: e1ba56757257
Create Date: 2026-09-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260917_exam_execution"
down_revision: str | Sequence[str] | None = "e1ba56757257"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLAlchemy's non-native Enum is represented by CHECK constraints. Extend
    # the two lifecycle enums before application code can persist new values.
    op.execute("ALTER TABLE exams DROP CONSTRAINT IF EXISTS exam_status")
    op.create_check_constraint(
        "exam_status",
        "exams",
        "status IN ('draft','submitted','sealed','active','suspended','closing','cancelling','closed','cancelled')",
    )

    op.execute("ALTER TABLE exam_attempts DROP CONSTRAINT IF EXISTS attempt_end_reason")
    op.create_check_constraint(
        "attempt_end_reason",
        "exam_attempts",
        "end_reason IS NULL OR end_reason IN ('candidate_submitted','time_expired','exam_closed','exam_cancelled','admin_terminated')",
    )
    op.drop_constraint(
        "ck_exam_attempts_termination_reason_consistent",
        "exam_attempts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_exam_attempts_termination_reason_consistent",
        "exam_attempts",
        "((status = 'terminated' AND end_reason IN ('admin_terminated','exam_cancelled') AND termination_reason IS NOT NULL) OR (status <> 'terminated' AND termination_reason IS NULL))",
    )
    op.drop_constraint(
        "ck_exam_attempts_submitted_not_admin_terminated",
        "exam_attempts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_exam_attempts_submitted_not_admin_terminated",
        "exam_attempts",
        "status <> 'submitted' OR end_reason NOT IN ('admin_terminated','exam_cancelled')",
    )

    op.create_table(
        "exam_execution_controls",
        sa.Column("exam_id", sa.Uuid(), nullable=False),
        sa.Column(
            "operation",
            sa.Enum(
                "closing",
                "cancelling",
                name="exam_execution_operation",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "operation_source",
            sa.Enum(
                "admin",
                "automatic",
                name="exam_operation_source",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("operation_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("operation_requested_by_actor_id", sa.Uuid(), nullable=True),
        sa.Column("operation_reason", sa.Text(), nullable=True),
        sa.Column(
            "operation_attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "last_operation_attempt_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("operation_error", sa.Text(), nullable=True),
        sa.Column(
            "result_disposition",
            sa.Enum(
                "pending_review",
                "approved",
                "voided",
                name="exam_result_disposition",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("results_decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("results_decided_by_actor_id", sa.Uuid(), nullable=True),
        sa.Column("results_decision_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "operation_attempts >= 0",
            name="ck_exam_execution_controls_attempts_nonnegative",
        ),
        sa.CheckConstraint(
            "operation_error IS NULL OR char_length(operation_error) <= 2048",
            name="ck_exam_execution_controls_error_length",
        ),
        sa.CheckConstraint(
            "(operation IS NULL) OR (operation_source IS NOT NULL AND operation_requested_at IS NOT NULL)",
            name="ck_exam_execution_controls_operation_metadata",
        ),
        sa.CheckConstraint(
            "operation_source != 'admin' OR operation_requested_by_actor_id IS NOT NULL",
            name="ck_exam_execution_controls_admin_actor",
        ),
        sa.CheckConstraint(
            "operation != 'cancelling' OR operation_reason IS NOT NULL",
            name="ck_exam_execution_controls_cancel_reason",
        ),
        sa.CheckConstraint(
            "result_disposition NOT IN ('approved','voided') OR (results_decided_at IS NOT NULL AND results_decided_by_actor_id IS NOT NULL)",
            name="ck_exam_execution_controls_result_decision_metadata",
        ),
        sa.CheckConstraint(
            "results_decision_reason IS NULL OR char_length(results_decision_reason) <= 1000",
            name="ck_exam_execution_controls_result_reason_length",
        ),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["operation_requested_by_actor_id"],
            ["local_actors.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["results_decided_by_actor_id"],
            ["local_actors.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exam_id"),
    )
    op.create_index(
        op.f("ix_exam_execution_controls_exam_id"),
        "exam_execution_controls",
        ["exam_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_exam_execution_controls_operation"),
        "exam_execution_controls",
        ["operation"],
    )
    op.create_index(
        op.f("ix_exam_execution_controls_operation_requested_at"),
        "exam_execution_controls",
        ["operation_requested_at"],
    )
    op.create_index(
        op.f("ix_exam_execution_controls_operation_requested_by_actor_id"),
        "exam_execution_controls",
        ["operation_requested_by_actor_id"],
    )
    op.create_index(
        op.f("ix_exam_execution_controls_result_disposition"),
        "exam_execution_controls",
        ["result_disposition"],
    )
    op.create_index(
        op.f("ix_exam_execution_controls_results_decided_by_actor_id"),
        "exam_execution_controls",
        ["results_decided_by_actor_id"],
    )
    op.create_index(
        "ix_exam_execution_controls_operation_requested",
        "exam_execution_controls",
        ["operation", "operation_requested_at"],
    )
    op.create_index(
        "ix_exam_execution_controls_result_disposition_exam",
        "exam_execution_controls",
        ["result_disposition", "exam_id"],
    )


def downgrade() -> None:
    op.execute(
        "UPDATE exams SET status = 'suspended' WHERE status IN ('closing','cancelling')"
    )
    op.execute(
        "UPDATE exam_attempts SET end_reason = 'admin_terminated' WHERE end_reason = 'exam_cancelled'"
    )

    op.drop_index(
        "ix_exam_execution_controls_result_disposition_exam",
        table_name="exam_execution_controls",
    )
    op.drop_index(
        "ix_exam_execution_controls_operation_requested",
        table_name="exam_execution_controls",
    )
    op.drop_index(
        op.f("ix_exam_execution_controls_results_decided_by_actor_id"),
        table_name="exam_execution_controls",
    )
    op.drop_index(
        op.f("ix_exam_execution_controls_result_disposition"),
        table_name="exam_execution_controls",
    )
    op.drop_index(
        op.f("ix_exam_execution_controls_operation_requested_by_actor_id"),
        table_name="exam_execution_controls",
    )
    op.drop_index(
        op.f("ix_exam_execution_controls_operation_requested_at"),
        table_name="exam_execution_controls",
    )
    op.drop_index(
        op.f("ix_exam_execution_controls_operation"),
        table_name="exam_execution_controls",
    )
    op.drop_index(
        op.f("ix_exam_execution_controls_exam_id"), table_name="exam_execution_controls"
    )
    op.drop_table("exam_execution_controls")

    op.drop_constraint(
        "ck_exam_attempts_submitted_not_admin_terminated",
        "exam_attempts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_exam_attempts_submitted_not_admin_terminated",
        "exam_attempts",
        "status <> 'submitted' OR end_reason <> 'admin_terminated'",
    )
    op.drop_constraint(
        "ck_exam_attempts_termination_reason_consistent", "exam_attempts", type_="check"
    )
    op.create_check_constraint(
        "ck_exam_attempts_termination_reason_consistent",
        "exam_attempts",
        "((status = 'terminated' AND end_reason = 'admin_terminated' AND termination_reason IS NOT NULL) OR (status <> 'terminated' AND termination_reason IS NULL))",
    )
    op.drop_constraint("attempt_end_reason", "exam_attempts", type_="check")
    op.create_check_constraint(
        "attempt_end_reason",
        "exam_attempts",
        "end_reason IS NULL OR end_reason IN ('candidate_submitted','time_expired','exam_closed','admin_terminated')",
    )

    op.drop_constraint("exam_status", "exams", type_="check")
    op.create_check_constraint(
        "exam_status",
        "exams",
        "status IN ('draft','submitted','sealed','active','suspended','closed','cancelled')",
    )
