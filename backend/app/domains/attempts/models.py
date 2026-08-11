# =========================== #
#     attempts/models.py      #
# =========================== #

"""Database models for candidate examination attempts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

ATTEMPT_REASON_MAX_LENGTH = 500


class AttemptStatus(str, PyEnum):
    """Lifecycle states for a candidate examination attempt."""

    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    TERMINATED = "terminated"


class AttemptSubmissionReason(str, PyEnum):
    """Reason an attempt stopped accepting candidate answers."""

    CANDIDATE_SUBMITTED = "candidate_submitted"
    TIME_EXPIRED = "time_expired"
    EXAM_CLOSED = "exam_closed"
    ADMIN_TERMINATED = "admin_terminated"


class ExamAttempt(Base):
    """
    One candidate's sitting of one exam.

    ExamCandidate already belongs to a specific exam, so each candidate
    receives at most one attempt.

    The attempt stores its own deadline when it begins so later exam schedule
    changes do not silently alter an already-running candidate timer.
    """

    __tablename__ = "exam_attempts"

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "exam_candidates.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    status: Mapped[AttemptStatus] = mapped_column(
        SQLEnum(
            AttemptStatus,
            name="attempt_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=AttemptStatus.IN_PROGRESS,
        server_default=AttemptStatus.IN_PROGRESS.value,
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    deadline_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    submission_reason: Mapped[AttemptSubmissionReason | None] = mapped_column(
        SQLEnum(
            AttemptSubmissionReason,
            name="attempt_submission_reason",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=True,
    )

    termination_reason: Mapped[str | None] = mapped_column(
        String(ATTEMPT_REASON_MAX_LENGTH),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "deadline_at > started_at",
            name="ck_exam_attempts_valid_deadline",
        ),
        Index(
            "ix_exam_attempts_status_deadline",
            "status",
            "deadline_at",
        ),
    )


class AttemptQuestionAllocation(Base):
    """
    One exam question allocated to one candidate attempt.

    The allocation is generated once when the attempt starts and then
    persisted. This prevents question order from changing when the candidate
    refreshes, disconnects, or resumes on another device.
    """

    __tablename__ = "attempt_question_allocations"

    attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "exam_attempts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    exam_question_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "exam_questions.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "attempt_id",
            "exam_question_id",
            name="uq_attempt_questions_attempt_exam_question",
        ),
        UniqueConstraint(
            "attempt_id",
            "position",
            name="uq_attempt_questions_attempt_position",
        ),
        CheckConstraint(
            "position >= 1",
            name="ck_attempt_questions_position_positive",
        ),
        Index(
            "ix_attempt_questions_attempt_position",
            "attempt_id",
            "position",
        ),
    )


class AttemptOptionAllocation(Base):
    """
    Presentation order for an answer option within a candidate attempt.

    Options are allocated once so shuffled answer choices remain in the same
    order after refreshes, reconnects, or device changes.
    """

    __tablename__ = "attempt_option_allocations"

    attempt_question_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "attempt_question_allocations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    exam_question_option_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "exam_question_options.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "attempt_question_id",
            "exam_question_option_id",
            name="uq_attempt_options_question_option",
        ),
        UniqueConstraint(
            "attempt_question_id",
            "position",
            name="uq_attempt_options_question_position",
        ),
        CheckConstraint(
            "position >= 1",
            name="ck_attempt_options_position_positive",
        ),
        Index(
            "ix_attempt_options_question_position",
            "attempt_question_id",
            "position",
        ),
    )


class AttemptAnswer(Base):
    """
    Candidate answer state for one allocated question.

    Selected choices live in AttemptAnswerSelection so single-choice and
    multiple-choice questions use the same storage structure.
    """

    __tablename__ = "attempt_answers"

    attempt_question_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "attempt_question_allocations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    is_flagged: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class AttemptAnswerSelection(Base):
    """
    One option currently selected by the candidate.

    Multiple rows allow multiple-choice questions to have several selected
    answers. Single-choice validation is enforced by the attempts service.
    """

    __tablename__ = "attempt_answer_selections"

    answer_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "attempt_answers.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    attempt_option_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "attempt_option_allocations.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "answer_id",
            "attempt_option_id",
            name="uq_attempt_answer_selections_answer_option",
        ),
        Index(
            "ix_attempt_answer_selections_answer",
            "answer_id",
        ),
    )