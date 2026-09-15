"""remove obsolete student CBT credential storage

Revision ID: 20260915_admission_auth
Revises: 20260915_joint_authoring
Create Date: 2026-09-15

Student authentication is now deterministic from the authoritative synced
admission number: the visible admission number must be uppercase and the
password must equal that same stored admission number lowercased. No separate
student CBT PIN/password verifier is stored locally.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260915_admission_auth"
down_revision: str | Sequence[str] | None = "20260915_joint_authoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("student_cbt_credentials")


def downgrade() -> None:
    op.create_table(
        "student_cbt_credentials",
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("pin_hash", sa.String(length=512), nullable=False),
        sa.Column(
            "credential_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "credential_version >= 1",
            name="ck_student_cbt_credentials_version_positive",
        ),
        sa.CheckConstraint(
            "source_deleted_at IS NULL OR is_active = false",
            name="ck_student_cbt_credentials_deleted_inactive",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_cbt_credentials")),
        sa.UniqueConstraint(
            "student_id",
            name=op.f("uq_student_cbt_credentials_student_id"),
        ),
    )
    op.create_index(
        op.f("ix_student_cbt_credentials_student_id"),
        "student_cbt_credentials",
        ["student_id"],
    )
    op.create_index(
        op.f("ix_student_cbt_credentials_is_active"),
        "student_cbt_credentials",
        ["is_active"],
    )
    op.create_index(
        op.f("ix_student_cbt_credentials_source_deleted_at"),
        "student_cbt_credentials",
        ["source_deleted_at"],
    )
    op.create_index(
        "ix_student_cbt_credentials_active_student",
        "student_cbt_credentials",
        ["student_id", "is_active"],
    )
