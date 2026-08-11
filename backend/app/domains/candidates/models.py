# ===================================== #
# backend.app.domains.candidates.models
# ===================================== #

"""
Candidate models for Weave CBT.

The candidates domain represents students who have been placed onto
the roster of a specific local CBT examination.

Academic enrollment and examination candidacy are separate concepts.

StudentEnrollment means:

    "Weave says this student is academically enrolled."

ExamCandidate means:

    "This student has been placed onto this specific examination roster."

This domain owns:

- examination candidate rosters;
- candidate eligibility state;
- stable candidate identity snapshots;
- per-examination candidate PIN credentials.

This domain does NOT own:

- student academic enrollment;
- examination definitions;
- live examination attempts;
- candidate answers;
- examination scores;
- result synchronization.

Those responsibilities belong to their respective domains.
"""

from datetime import datetime
from enum import Enum as PyEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# ========================== #
# CONSTANTS
# ========================== #

WEAVE_ID_MAX_LENGTH = 128
ADMISSION_NUMBER_MAX_LENGTH = 128
NAME_MAX_LENGTH = 255
STATUS_REASON_MAX_LENGTH = 500
PIN_HASH_MAX_LENGTH = 512


# ========================== #
# ENUMS
# ========================== #


class CandidateStatus(str, PyEnum):
    """
    Eligibility state of a candidate on an examination roster.

    ELIGIBLE:
        Candidate may enter the examination when the exam lifecycle
        and authentication requirements allow it.

    BLOCKED:
        Candidate remains on the roster but cannot enter the exam.

    WITHDRAWN:
        Candidate has been removed from active participation while
        preserving the historical roster record.
    """

    ELIGIBLE = "eligible"
    BLOCKED = "blocked"
    WITHDRAWN = "withdrawn"


# ========================== #
# EXAM CANDIDATE
# ========================== #


class ExamCandidate(Base):
    """
    Represent one student on one examination roster.

    Identity fields are intentionally snapshotted from the academic
    enrollment projection.

    This prevents later academic synchronization changes, such as
    admission-number or display-name changes, from silently changing
    the historical identity attached to an already-prepared exam.

    The original academic enrollment is still referenced through
    enrollment_id.
    """

    __tablename__ = "exam_candidates"

    __table_args__ = (
        UniqueConstraint(
            "exam_id",
            "enrollment_id",
        ),
        UniqueConstraint(
            "exam_id",
            "weave_student_id",
        ),
        UniqueConstraint(
            "exam_id",
            "admission_number",
        ),
    )

    exam_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "exams.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    enrollment_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "academic_student_enrollments.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    weave_student_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
        index=True,
    )

    admission_number: Mapped[str] = mapped_column(
        String(ADMISSION_NUMBER_MAX_LENGTH),
        nullable=False,
        index=True,
    )

    display_name: Mapped[str] = mapped_column(
        String(NAME_MAX_LENGTH),
        nullable=False,
    )

    status: Mapped[CandidateStatus] = mapped_column(
        Enum(
            CandidateStatus,
            name="candidate_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=CandidateStatus.ELIGIBLE,
        server_default=CandidateStatus.ELIGIBLE.value,
        index=True,
    )

    status_reason: Mapped[str | None] = mapped_column(
        String(STATUS_REASON_MAX_LENGTH),
        nullable=True,
    )


# ========================== #
# CANDIDATE CREDENTIAL
# ========================== #


class CandidateCredential(Base):
    """
    Store the current examination PIN credential for a candidate.

    The raw PIN must never be stored.

    security.py generates the PIN and stores only its Argon2 hash here.

    Each ExamCandidate has at most one current credential record.

    Regenerating a PIN updates:

    - pin_hash;
    - credential_version;
    - issued_at;
    - revoked_at.

    Detailed regeneration/revocation history belongs to the audit domain.
    """

    __tablename__ = "candidate_credentials"

    __table_args__ = (
        CheckConstraint(
            "credential_version >= 1"
        ),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "exam_candidates.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    pin_hash: Mapped[str] = mapped_column(
        String(PIN_HASH_MAX_LENGTH),
        nullable=False,
    )

    credential_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )