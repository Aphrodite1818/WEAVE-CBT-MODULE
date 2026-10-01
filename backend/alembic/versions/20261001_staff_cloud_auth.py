"""attach Weave actor authorization state to local staff sessions

Revision ID: 20261001_staff_cloud_auth
Revises: 20260927_elective_selection
Create Date: 2026-10-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261001_staff_cloud_auth"
down_revision: str | Sequence[str] | None = "20260927_elective_selection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "local_actor_sessions",
        sa.Column("weave_access_token_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "local_actor_sessions",
        sa.Column("weave_access_token_issued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "local_actor_sessions",
        sa.Column("weave_access_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "local_actor_sessions",
        sa.Column("weave_refresh_token_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "local_actor_sessions",
        sa.Column("weave_refresh_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "local_actor_sessions",
        sa.Column(
            "weave_auth_state",
            sa.String(length=32),
            nullable=False,
            server_default="legacy",
        ),
    )
    op.add_column(
        "local_actor_sessions",
        sa.Column(
            "weave_refresh_operation_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_local_actor_sessions_weave_access_token_expires_at",
        "local_actor_sessions",
        ["weave_access_token_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_local_actor_sessions_weave_refresh_token_expires_at",
        "local_actor_sessions",
        ["weave_refresh_token_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_local_actor_sessions_weave_auth_state",
        "local_actor_sessions",
        ["weave_auth_state"],
        unique=False,
    )
    op.create_index(
        "ix_local_actor_sessions_weave_refresh_operation_id",
        "local_actor_sessions",
        ["weave_refresh_operation_id"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_local_actor_sessions_weave_auth_state",
        "local_actor_sessions",
        "weave_auth_state IN ('legacy', 'synced', 'degraded', 'refresh_pending', 'revoked')",
    )
    op.alter_column(
        "local_actor_sessions",
        "weave_auth_state",
        server_default=None,
    )

    op.add_column(
        "local_refresh_tokens",
        sa.Column(
            "refresh_operation_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "local_refresh_tokens",
        sa.Column("replacement_token_encrypted", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_local_refresh_tokens_refresh_operation_id",
        "local_refresh_tokens",
        ["refresh_operation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_local_refresh_tokens_refresh_operation_id",
        table_name="local_refresh_tokens",
    )
    op.drop_column("local_refresh_tokens", "replacement_token_encrypted")
    op.drop_column("local_refresh_tokens", "refresh_operation_id")

    op.drop_constraint(
        "ck_local_actor_sessions_weave_auth_state",
        "local_actor_sessions",
        type_="check",
    )
    op.drop_index(
        "ix_local_actor_sessions_weave_refresh_operation_id",
        table_name="local_actor_sessions",
    )
    op.drop_index(
        "ix_local_actor_sessions_weave_auth_state",
        table_name="local_actor_sessions",
    )
    op.drop_index(
        "ix_local_actor_sessions_weave_refresh_token_expires_at",
        table_name="local_actor_sessions",
    )
    op.drop_index(
        "ix_local_actor_sessions_weave_access_token_expires_at",
        table_name="local_actor_sessions",
    )
    op.drop_column("local_actor_sessions", "weave_refresh_operation_id")
    op.drop_column("local_actor_sessions", "weave_auth_state")
    op.drop_column("local_actor_sessions", "weave_refresh_token_expires_at")
    op.drop_column("local_actor_sessions", "weave_refresh_token_encrypted")
    op.drop_column("local_actor_sessions", "weave_access_token_expires_at")
    op.drop_column("local_actor_sessions", "weave_access_token_issued_at")
    op.drop_column("local_actor_sessions", "weave_access_token_encrypted")
