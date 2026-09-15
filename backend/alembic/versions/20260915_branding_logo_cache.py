"""add persistent local tenant-logo cache metadata

Revision ID: 20260915_branding_logo_cache
Revises: 20260915_cbt_branding
Create Date: 2026-09-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_branding_logo_cache"
down_revision: str | Sequence[str] | None = "20260915_cbt_branding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "branding_states",
        sa.Column("logo_storage_key", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "branding_states",
        sa.Column("logo_mime_type", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "branding_states",
        sa.Column("logo_size_bytes", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "branding_states",
        sa.Column("logo_sha256", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_branding_states_logo_size_positive",
        "branding_states",
        "logo_size_bytes IS NULL OR logo_size_bytes > 0",
    )
    op.create_check_constraint(
        "ck_branding_states_logo_cache_complete",
        "branding_states",
        "(logo_storage_key IS NULL AND logo_mime_type IS NULL AND "
        "logo_size_bytes IS NULL AND logo_sha256 IS NULL) OR "
        "(logo_storage_key IS NOT NULL AND logo_mime_type IS NOT NULL AND "
        "logo_size_bytes IS NOT NULL AND logo_sha256 IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_branding_states_logo_cache_complete",
        "branding_states",
        type_="check",
    )
    op.drop_constraint(
        "ck_branding_states_logo_size_positive",
        "branding_states",
        type_="check",
    )
    op.drop_column("branding_states", "logo_sha256")
    op.drop_column("branding_states", "logo_size_bytes")
    op.drop_column("branding_states", "logo_mime_type")
    op.drop_column("branding_states", "logo_storage_key")
