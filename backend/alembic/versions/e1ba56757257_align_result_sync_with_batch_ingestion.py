"""align result sync with batch ingestion

Revision ID: e1ba56757257
Revises: 20260916_option_images
Create Date: 2026-09-17 17:52:15.957555
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e1ba56757257"
down_revision: str | Sequence[str] | None = "20260916_option_images"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "exam_results",
        sa.Column(
            "sync_batch_id",
            sa.Uuid(),
            nullable=True,
        ),
    )

    # Existing rows were created under the old per-result sync contract.
    # Preserve already-synced/syncing rows by assigning each one a stable
    # synthetic batch identity before enforcing the new state constraints.
    op.execute(
        sa.text(
            """
            UPDATE exam_results
            SET sync_batch_id = md5(id::text)::uuid
            WHERE sync_status IN ('syncing', 'synced')
              AND sync_batch_id IS NULL
            """
        )
    )

    op.create_index(
        "ix_exam_results_sync_batch_id",
        "exam_results",
        ["sync_batch_id"],
        unique=False,
    )

    op.create_index(
        "ix_exam_results_sync_batch_status",
        "exam_results",
        ["sync_batch_id", "sync_status"],
        unique=False,
    )

    op.create_check_constraint(
        "ck_exam_results_syncing_requires_batch",
        "exam_results",
        "sync_status != 'syncing' OR sync_batch_id IS NOT NULL",
    )

    op.create_check_constraint(
        "ck_exam_results_synced_requires_batch",
        "exam_results",
        "sync_status != 'synced' OR sync_batch_id IS NOT NULL",
    )

    op.drop_index(
        "ix_exam_results_idempotency_key",
        table_name="exam_results",
    )

    op.drop_index(
        "ix_exam_results_weave_result_id",
        table_name="exam_results",
    )

    op.drop_column(
        "exam_results",
        "idempotency_key",
    )

    op.drop_column(
        "exam_results",
        "weave_result_id",
    )


def downgrade() -> None:
    op.add_column(
        "exam_results",
        sa.Column(
            "idempotency_key",
            sa.String(length=128),
            nullable=True,
        ),
    )

    op.add_column(
        "exam_results",
        sa.Column(
            "weave_result_id",
            sa.String(length=128),
            nullable=True,
        ),
    )

    # Reconstruct a unique legacy key for every local result.
    op.execute(
        sa.text(
            """
            UPDATE exam_results
            SET idempotency_key =
                'cbt:' || exam_id::text || ':' || candidate_id::text
            """
        )
    )

    op.alter_column(
        "exam_results",
        "idempotency_key",
        existing_type=sa.String(length=128),
        nullable=False,
    )

    op.create_index(
        "ix_exam_results_idempotency_key",
        "exam_results",
        ["idempotency_key"],
        unique=True,
    )

    op.create_index(
        "ix_exam_results_weave_result_id",
        "exam_results",
        ["weave_result_id"],
        unique=True,
    )

    op.drop_constraint(
        "ck_exam_results_syncing_requires_batch",
        "exam_results",
        type_="check",
    )

    op.drop_constraint(
        "ck_exam_results_synced_requires_batch",
        "exam_results",
        type_="check",
    )

    op.drop_index(
        "ix_exam_results_sync_batch_status",
        table_name="exam_results",
    )

    op.drop_index(
        "ix_exam_results_sync_batch_id",
        table_name="exam_results",
    )

    op.drop_column(
        "exam_results",
        "sync_batch_id",
    )
