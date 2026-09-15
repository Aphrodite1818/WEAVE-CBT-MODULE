"""align exam attempt terminal lifecycle columns with current model

Revision ID: 20260915_attempt_terminal_lifecycle
Revises: 20260915_branding_logo_cache
Create Date: 2026-09-15

The original schema stored terminal attempt state as submitted_at /
submission_reason.  The current attempt domain models all terminal outcomes
(submission, expiry, exam closure, and administrative termination) using the
more general ended_at / end_reason pair.  This migration preserves existing
attempt rows while moving the physical database schema to that contract.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260915_attempt_terminal_lifecycle"
down_revision: str | Sequence[str] | None = "20260915_branding_logo_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Remove constraints tied to the legacy column names before renaming them.
    op.drop_constraint(
        "ck_exam_attempts_valid_submission",
        "exam_attempts",
        type_="check",
    )
    op.drop_constraint(
        "attempt_submission_reason",
        "exam_attempts",
        type_="check",
    )

    op.alter_column(
        "exam_attempts",
        "submitted_at",
        new_column_name="ended_at",
    )
    op.alter_column(
        "exam_attempts",
        "submission_reason",
        new_column_name="end_reason",
    )

    # Normalize legacy rows before installing the stricter current lifecycle
    # constraints.  Existing terminal timestamps/reasons are preserved where
    # valid; missing legacy terminal metadata receives the least-surprising
    # value required by the current model.
    op.execute(
        """
        UPDATE exam_attempts
        SET
            active_since = CASE
                WHEN status = 'in_progress' THEN COALESCE(active_since, started_at)
                ELSE NULL
            END,
            ended_at = CASE
                WHEN status IN ('submitted', 'terminated')
                    THEN COALESCE(ended_at, updated_at, started_at)
                ELSE NULL
            END,
            end_reason = CASE
                WHEN status = 'terminated' THEN 'admin_terminated'
                WHEN status = 'submitted' AND end_reason = 'admin_terminated'
                    THEN 'candidate_submitted'
                WHEN status = 'submitted'
                    THEN COALESCE(end_reason, 'candidate_submitted')
                ELSE NULL
            END,
            termination_reason = CASE
                WHEN status = 'terminated'
                    THEN COALESCE(
                        NULLIF(BTRIM(termination_reason), ''),
                        'Migrated terminated attempt'
                    )
                ELSE NULL
            END
        """
    )

    op.create_check_constraint(
        "attempt_end_reason",
        "exam_attempts",
        "end_reason IS NULL OR end_reason IN "
        "('candidate_submitted', 'time_expired', 'exam_closed', 'admin_terminated')",
    )
    op.create_check_constraint(
        "ck_exam_attempts_valid_end",
        "exam_attempts",
        "ended_at IS NULL OR ended_at >= started_at",
    )
    op.create_check_constraint(
        "ck_exam_attempts_terminal_state_consistent",
        "exam_attempts",
        "((status IN ('in_progress', 'interrupted') "
        "AND ended_at IS NULL AND end_reason IS NULL) "
        "OR (status IN ('submitted', 'terminated') "
        "AND ended_at IS NOT NULL AND end_reason IS NOT NULL))",
    )
    op.create_check_constraint(
        "ck_exam_attempts_termination_reason_consistent",
        "exam_attempts",
        "((status = 'terminated' "
        "AND end_reason = 'admin_terminated' "
        "AND termination_reason IS NOT NULL) "
        "OR (status <> 'terminated' AND termination_reason IS NULL))",
    )
    op.create_check_constraint(
        "ck_exam_attempts_submitted_not_admin_terminated",
        "exam_attempts",
        "status <> 'submitted' OR end_reason <> 'admin_terminated'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_exam_attempts_submitted_not_admin_terminated",
        "exam_attempts",
        type_="check",
    )
    op.drop_constraint(
        "ck_exam_attempts_termination_reason_consistent",
        "exam_attempts",
        type_="check",
    )
    op.drop_constraint(
        "ck_exam_attempts_terminal_state_consistent",
        "exam_attempts",
        type_="check",
    )
    op.drop_constraint(
        "ck_exam_attempts_valid_end",
        "exam_attempts",
        type_="check",
    )
    op.drop_constraint(
        "attempt_end_reason",
        "exam_attempts",
        type_="check",
    )

    op.alter_column(
        "exam_attempts",
        "ended_at",
        new_column_name="submitted_at",
    )
    op.alter_column(
        "exam_attempts",
        "end_reason",
        new_column_name="submission_reason",
    )

    op.create_check_constraint(
        "ck_exam_attempts_valid_submission",
        "exam_attempts",
        "submitted_at IS NULL OR submitted_at >= started_at",
    )
    op.create_check_constraint(
        "attempt_submission_reason",
        "exam_attempts",
        "submission_reason IS NULL OR submission_reason IN "
        "('candidate_submitted', 'time_expired', 'exam_closed', 'admin_terminated')",
    )
