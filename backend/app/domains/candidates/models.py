"""Candidate models for Weave CBT."""

from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

ADMISSION_NUMBER_MAX_LENGTH = 128
NAME_MAX_LENGTH = 255
STATUS_REASON_MAX_LENGTH = 500
PIN_HASH_MAX_LENGTH = 512


class CandidateStatus(str, PyEnum):
    ELIGIBLE = "eligible"
    BLOCKED = "blocked"
    WITHDRAWN = "withdrawn"


class ExamCandidate(Base):
    """Immutable exam-roster snapshot derived from one synchronized enrollment."""

    __tablename__ = "exam_candidates"

    exam_id: Mapped[UUID] = mapped_column(
        ForeignKey("exams.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    enrollment_id: Mapped[UUID] = mapped_column(
        ForeignKey("student_enrollments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    admission_number: Mapped[str] = mapped_column(
        String(ADMISSION_NUMBER_MAX_LENGTH), nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), nullable=False)
    status: Mapped[CandidateStatus] = mapped_column(
        SQLEnum(
            CandidateStatus,
            name="candidate_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=CandidateStatus.ELIGIBLE,
        server_default=CandidateStatus.ELIGIBLE.value,
        index=True,
    )
    status_reason: Mapped[str | None] = mapped_column(
        String(STATUS_REASON_MAX_LENGTH), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "exam_id", "enrollment_id", name="uq_exam_candidates_exam_enrollment"
        ),
        UniqueConstraint(
            "exam_id", "student_id", name="uq_exam_candidates_exam_student"
        ),
        UniqueConstraint(
            "exam_id",
            "admission_number",
            name="uq_exam_candidates_exam_admission_number",
        ),
    )


class CandidateCredential(Base):
    __tablename__ = "candidate_credentials"

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("exam_candidates.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    pin_hash: Mapped[str] = mapped_column(String(PIN_HASH_MAX_LENGTH), nullable=False)
    credential_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "credential_version >= 1", name="ck_candidate_credentials_version_positive"
        ),
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= issued_at",
            name="ck_candidate_credentials_valid_revocation",
        ),
    )
