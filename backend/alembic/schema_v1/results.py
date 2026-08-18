# =========================== #
#       results/models.py     #
# =========================== #

"""Database models for locally calculated CBT assessment results."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

WEAVE_ID_MAX_LENGTH = 128
RESULT_IDEMPOTENCY_KEY_MAX_LENGTH = 128
RESULT_SYNC_ERROR_MAX_LENGTH = 1024


class ResultSyncStatus(str, PyEnum):
    """Synchronization state of a local CBT result."""

    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"


class ExamResult(Base):
    """
    Final locally calculated score for one candidate examination attempt.

    The result represents one Weave assessment component, not the student's
    complete academic result.

    Example:

        Assessment component: CA 1
        Component maximum:    10
        Candidate score:       5

    The local UI may display this as both:

        5 / 10
        50 / 100

    Only the raw component score is synchronized back to Weave.
    """

    __tablename__ = "exam_results"

    attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "exam_attempts.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "exam_candidates.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    exam_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "exams.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    assessment_component_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "assessment_components.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    score: Mapped[Decimal] = mapped_column(
        Numeric(8, 2),
        nullable=False,
    )

    maximum_score: Mapped[Decimal] = mapped_column(
        Numeric(8, 2),
        nullable=False,
    )

    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    sync_status: Mapped[ResultSyncStatus] = mapped_column(
        SQLEnum(
            ResultSyncStatus,
            name="result_sync_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ResultSyncStatus.PENDING,
        server_default=ResultSyncStatus.PENDING.value,
        index=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(RESULT_IDEMPOTENCY_KEY_MAX_LENGTH),
        nullable=False,
        unique=True,
        index=True,
    )

    weave_result_id: Mapped[str | None] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=True,
        unique=True,
        index=True,
    )

    sync_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    last_sync_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    sync_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "exam_id",
            name="uq_exam_results_candidate_exam",
        ),
        CheckConstraint(
            "score >= 0",
            name="ck_exam_results_score_nonnegative",
        ),
        CheckConstraint(
            "maximum_score > 0",
            name="ck_exam_results_maximum_score_positive",
        ),
        CheckConstraint(
            "score <= maximum_score",
            name="ck_exam_results_score_within_maximum",
        ),
        CheckConstraint(
            "sync_attempts >= 0",
            name="ck_exam_results_sync_attempts_nonnegative",
        ),
        CheckConstraint(
            f"sync_error IS NULL OR char_length(sync_error) <= "
            f"{RESULT_SYNC_ERROR_MAX_LENGTH}",
            name="ck_exam_results_sync_error_length",
        ),
        Index(
            "ix_exam_results_exam_sync_status",
            "exam_id",
            "sync_status",
        ),
        Index(
            "ix_exam_results_component_sync_status",
            "assessment_component_id",
            "sync_status",
        ),
    )
