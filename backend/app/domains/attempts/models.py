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
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

ATTEMPT_REASON_MAX_LENGTH = 500


class AttemptStatus(str, PyEnum):
    """Lifecycle states for a candidate examination attempt."""

    IN_PROGRESS = "in_progress"
    INTERRUPTED = "interrupted"
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

    Timing is interruption-aware. `time_limit_seconds` snapshots the exam time
    budget. `elapsed_seconds` stores already-consumed active time, while
    `active_since` marks the start of the currently running segment.

    When an interruption is confirmed, the service adds the current active
    segment to `elapsed_seconds`, clears `active_since`, marks the attempt as
    INTERRUPTED, and records an AttemptInterruption row. An approved resume
    starts a new active segment without charging the candidate for the paused
    interval.
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

    time_limit_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    elapsed_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    active_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
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
            "time_limit_seconds > 0",
            name="ck_exam_attempts_time_limit_positive",
        ),
        CheckConstraint(
            "elapsed_seconds >= 0",
            name="ck_exam_attempts_elapsed_nonnegative",
        ),
        CheckConstraint(
            "elapsed_seconds <= time_limit_seconds",
            name="ck_exam_attempts_elapsed_within_limit",
        ),
        CheckConstraint(
            "active_since IS NULL OR active_since >= started_at",
            name="ck_exam_attempts_valid_active_since",
        ),
        CheckConstraint(
            "last_heartbeat_at >= started_at",
            name="ck_exam_attempts_valid_heartbeat",
        ),
        CheckConstraint(
            "last_activity_at >= started_at",
            name="ck_exam_attempts_valid_activity",
        ),
        CheckConstraint(
            "submitted_at IS NULL OR submitted_at >= started_at",
            name="ck_exam_attempts_valid_submission",
        ),
        CheckConstraint(
            "(status = 'in_progress' AND active_since IS NOT NULL) "
            "OR (status <> 'in_progress' AND active_since IS NULL)",
            name="ck_exam_attempts_active_segment_matches_status",
        ),
        Index(
            "ix_exam_attempts_status_heartbeat",
            "status",
            "last_heartbeat_at",
        ),
    )


class AttemptInterruption(Base):
    """
    Historical record of one interruption and any later approved resume.

    Multiple rows may exist for one attempt. Audit records capture the broader
    administrative action; this table preserves timing-specific state needed
    to explain and reconstruct attempt resumes.
    """

    __tablename__ = "attempt_interruptions"

    attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "exam_attempts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    interrupted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    remaining_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        String(ATTEMPT_REASON_MAX_LENGTH),
        nullable=True,
    )

    resumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    resumed_by_actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "local_actors.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    resume_reason: Mapped[str | None] = mapped_column(
        String(ATTEMPT_REASON_MAX_LENGTH),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "remaining_seconds >= 0",
            name="ck_attempt_interruptions_remaining_nonnegative",
        ),
        CheckConstraint(
            "resumed_at IS NULL OR resumed_at >= interrupted_at",
            name="ck_attempt_interruptions_valid_resume",
        ),
        Index(
            "ix_attempt_interruptions_attempt_interrupted",
            "attempt_id",
            "interrupted_at",
        ),
    )


class AttemptQuestionAllocation(Base):
    """
    One exam question allocated to one candidate attempt.

    Allocation is generated once and persisted so refresh, reconnection, or a
    device change never reshuffles the candidate's question order.
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
    """Persisted presentation order for one allocated answer option."""

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
    """Candidate answer state for one allocated question."""

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
    """One option currently selected by the candidate."""

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
