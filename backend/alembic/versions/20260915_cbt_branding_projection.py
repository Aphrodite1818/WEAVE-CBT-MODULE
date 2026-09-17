"""add durable local CBT tenant branding projection

Revision ID: 20260915_cbt_branding
Revises: 20260915_admission_auth
Create Date: 2026-09-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260915_cbt_branding"
down_revision: str | Sequence[str] | None = "20260915_admission_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "branding_states",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("school_name", sa.String(length=255), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("logo_revision", sa.Uuid(), nullable=True),
        sa.Column(
            "is_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "is_default_theme",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "theme_version", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "token_schema_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "light_tokens", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "theme_version >= 0", name="ck_branding_states_theme_version_nonnegative"
        ),
        sa.CheckConstraint(
            "token_schema_version >= 1",
            name="ck_branding_states_token_schema_version_positive",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_branding_states")),
        sa.UniqueConstraint("tenant_id", name=op.f("uq_branding_states_tenant_id")),
    )
    op.create_index(
        op.f("ix_branding_states_tenant_id"),
        "branding_states",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_branding_states_tenant_id"), table_name="branding_states")
    op.drop_table("branding_states")
