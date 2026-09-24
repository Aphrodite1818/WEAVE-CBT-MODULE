"""create candidate late-start authorization table

Revision ID: 20260924_late_start
Revises: 20260918_exam_folder_color
Create Date: 2026-09-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260924_late_start"
down_revision: str | Sequence[str] | None = "20260918_exam_folder_color"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_late_start_authorizations",
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("granted_by_actor_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_actor_id", sa.Uuid(), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "expires_at IS NULL OR expires_at >= granted_at",
            name="ck_candidate_late_start_expiry_valid",
        ),
        sa.CheckConstraint(
            "consumed_at IS NULL OR consumed_at >= granted_at",
            name="ck_candidate_late_start_consumed_valid",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= granted_at",
            name="ck_candidate_late_start_revoked_valid",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_by_actor_id IS NOT NULL",
            name="ck_candidate_late_start_revocation_actor_required",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revocation_reason IS NOT NULL",
            name="ck_candidate_late_start_revocation_reason_required",
        ),
        sa.CheckConstraint(
            "NOT (consumed_at IS NOT NULL AND revoked_at IS NOT NULL)",
            name="ck_candidate_late_start_not_consumed_and_revoked",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["exam_candidates.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_actor_id"],
            ["local_actors.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_actor_id"],
            ["local_actors.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_candidate_late_start_authorizations_candidate_id",
        "candidate_late_start_authorizations",
        ["candidate_id"],
    )
    op.create_index(
        "ix_candidate_late_start_authorizations_granted_by_actor_id",
        "candidate_late_start_authorizations",
        ["granted_by_actor_id"],
    )
    op.create_index(
        "ix_candidate_late_start_authorizations_granted_at",
        "candidate_late_start_authorizations",
        ["granted_at"],
    )
    op.create_index(
        "ix_candidate_late_start_authorizations_revoked_by_actor_id",
        "candidate_late_start_authorizations",
        ["revoked_by_actor_id"],
    )
    op.create_index(
        "ix_candidate_late_start_candidate_granted",
        "candidate_late_start_authorizations",
        ["candidate_id", "granted_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_candidate_late_start_candidate_granted",
        table_name="candidate_late_start_authorizations",
    )
    op.drop_index(
        "ix_candidate_late_start_authorizations_revoked_by_actor_id",
        table_name="candidate_late_start_authorizations",
    )
    op.drop_index(
        "ix_candidate_late_start_authorizations_granted_at",
        table_name="candidate_late_start_authorizations",
    )
    op.drop_index(
        "ix_candidate_late_start_authorizations_granted_by_actor_id",
        table_name="candidate_late_start_authorizations",
    )
    op.drop_index(
        "ix_candidate_late_start_authorizations_candidate_id",
        table_name="candidate_late_start_authorizations",
    )
    op.drop_table("candidate_late_start_authorizations")
