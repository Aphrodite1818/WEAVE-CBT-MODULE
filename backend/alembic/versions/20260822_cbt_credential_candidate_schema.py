"""repair candidate roster class and student credential schema

Revision ID: 20260822_cred_schema
Revises: 7dfe6fd9894b, c4f31a2d9e77
Create Date: 2026-08-22

The runtime model now authenticates students through a student-scoped CBT
credential, not an exam-candidate-scoped credential. Candidate roster rows also
snapshot class_id so roster filters do not need to join mutable enrollment data.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op


revision: str = "20260822_cred_schema"
down_revision: str | Sequence[str] | None = (
    "7dfe6fd9894b",
    "c4f31a2d9e77",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def _upgrade_exam_candidates() -> None:
    op.add_column(
        "exam_candidates",
        sa.Column("class_id", sa.Uuid(), nullable=True),
    )

    op.execute(
        """
        UPDATE exam_candidates AS candidate
        SET class_id = enrollment.class_id
        FROM student_enrollments AS enrollment
        WHERE enrollment.id = candidate.enrollment_id
          AND enrollment.class_id IS NOT NULL
        """
    )

    bind = op.get_bind()
    missing_class_count = bind.execute(
        sa.text("SELECT count(*) FROM exam_candidates WHERE class_id IS NULL")
    ).scalar_one()
    if missing_class_count:
        raise RuntimeError(
            "Cannot add non-null exam_candidates.class_id because "
            f"{missing_class_count} existing candidate rows have no "
            "inferable enrollment class."
        )

    op.alter_column("exam_candidates", "class_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_exam_candidates_class_id_academic_classes"),
        "exam_candidates",
        "academic_classes",
        ["class_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_exam_candidates_class_id"),
        "exam_candidates",
        ["class_id"],
    )
    op.create_index(
        "ix_exam_candidates_exam_class_status",
        "exam_candidates",
        ["exam_id", "class_id", "status"],
    )


def _upgrade_student_credentials() -> None:
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
        *_timestamps(),
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

    bind = op.get_bind()
    old_rows = bind.execute(
        sa.text(
            """
            SELECT DISTINCT ON (candidate.student_id)
                candidate.student_id,
                credential.pin_hash,
                credential.credential_version,
                credential.revoked_at,
                credential.issued_at,
                credential.created_at,
                credential.updated_at
            FROM candidate_credentials AS credential
            JOIN exam_candidates AS candidate
              ON candidate.id = credential.candidate_id
            ORDER BY
                candidate.student_id,
                credential.credential_version DESC,
                credential.issued_at DESC,
                credential.created_at DESC
            """
        )
    ).mappings()

    now = datetime.now(UTC)
    for row in old_rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO student_cbt_credentials (
                    id,
                    student_id,
                    pin_hash,
                    credential_version,
                    is_active,
                    source_updated_at,
                    synced_at,
                    source_deleted_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    :id,
                    :student_id,
                    :pin_hash,
                    :credential_version,
                    :is_active,
                    :source_updated_at,
                    :synced_at,
                    :source_deleted_at,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "id": uuid4(),
                "student_id": row["student_id"],
                "pin_hash": row["pin_hash"],
                "credential_version": row["credential_version"],
                "is_active": row["revoked_at"] is None,
                "source_updated_at": row["issued_at"],
                "synced_at": now,
                "source_deleted_at": row["revoked_at"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        )

    op.drop_table("candidate_credentials")


def upgrade() -> None:
    _upgrade_exam_candidates()
    _upgrade_student_credentials()


def downgrade() -> None:
    raise RuntimeError(
        "The candidate credential repair migration is irreversible because it "
        "collapses old exam-candidate credentials into one student credential."
    )
