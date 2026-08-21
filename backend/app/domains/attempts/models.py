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
    func,
    text as sql_text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


ATTEMPT_REASON_MAX_LENGTH = 500


# ========================== #
# ENUMS
# ========================== #


class AttemptStatus(str, PyEnum):
    """
    Lifecycle state of one candidate examination sitting.

    IN_PROGRESS
        Candidate is actively writing and consuming examination time.

    INTERRUPTED
        Candidate's individual attempt has been paused after a confirmed
        interruption. Time does not continue consuming while interrupted.

    SUBMITTED
        Attempt ended normally, either through candidate submission,
        time expiration, or examination closure.

    TERMINATED
        Attempt was explicitly terminated by an authorized administrator.
    """

    IN_PROGRESS = "in_progress"
    INTERRUPTED = "interrupted"
    SUBMITTED = "submitted"
    TERMINATED = "terminated"


class AttemptEndReason(str, PyEnum):
    """
    Reason an attempt permanently stopped accepting answers.
    """

    CANDIDATE_SUBMITTED = "candidate_submitted"
    TIME_EXPIRED = "time_expired"
    EXAM_CLOSED = "exam_closed"
    ADMIN_TERMINATED = "admin_terminated"


# ========================== #
# EXAM ATTEMPT
# ========================== #


class ExamAttempt(Base):
    """
    One candidate's sitting of one examination.

    One ExamCandidate may have at most one ExamAttempt.

    This means logging into another computer must never create a second
    attempt. Device transfer or reconnection always resumes this same row.

    Timing is interruption-aware:

        time_limit_seconds
            Frozen amount of writing time granted to the candidate.

        elapsed_seconds
            Active writing time already consumed and durably checkpointed.

        active_since
            Beginning of the currently active writing segment.

    While IN_PROGRESS:

        consumed time =
            elapsed_seconds
            + current active segment

    When an individual interruption is confirmed:

        1. current active segment is added to elapsed_seconds
        2. active_since is cleared
        3. status becomes INTERRUPTED
        4. AttemptInterruption is recorded

    When an authorized resume occurs:

        1. status becomes IN_PROGRESS
        2. active_since is set to the resume time

    High-frequency candidate presence heartbeats belong in Redis.
    last_heartbeat_at is only a durable PostgreSQL checkpoint and must
    not be updated for every browser heartbeat.
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

    # Frozen candidate writing-time allowance.
    #
    # Example:
    # 60-minute exam -> 3600 seconds.
    time_limit_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Active writing time already durably consumed.
    elapsed_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=sql_text("0"),
    )

    # Beginning of the current active writing segment.
    #
    # Must exist only while status == IN_PROGRESS.
    active_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Durable checkpoint only.
    #
    # Browser/WebSocket heartbeats should normally update Redis rather
    # than PostgreSQL on every heartbeat.
    last_heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Latest meaningful candidate activity persisted to PostgreSQL,
    # for example an accepted answer mutation.
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Permanent end of the sitting.
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    end_reason: Mapped[AttemptEndReason | None] = mapped_column(
        SQLEnum(
            AttemptEndReason,
            name="attempt_end_reason",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=True,
    )

    # Required only when an administrator terminates the attempt.
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
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_exam_attempts_valid_end",
        ),
        CheckConstraint(
            "(status = 'in_progress' AND active_since IS NOT NULL) "
            "OR (status <> 'in_progress' AND active_since IS NULL)",
            name="ck_exam_attempts_active_segment_matches_status",
        ),
        CheckConstraint(
            "("
            "status IN ('in_progress', 'interrupted') "
            "AND ended_at IS NULL "
            "AND end_reason IS NULL"
            ") OR ("
            "status IN ('submitted', 'terminated') "
            "AND ended_at IS NOT NULL "
            "AND end_reason IS NOT NULL"
            ")",
            name="ck_exam_attempts_terminal_state_consistent",
        ),
        CheckConstraint(
            "("
            "status = 'terminated' "
            "AND end_reason = 'admin_terminated' "
            "AND termination_reason IS NOT NULL"
            ") OR ("
            "status <> 'terminated' "
            "AND termination_reason IS NULL"
            ")",
            name="ck_exam_attempts_termination_reason_consistent",
        ),
        CheckConstraint(
            "status <> 'submitted' OR end_reason <> 'admin_terminated'",
            name="ck_exam_attempts_submitted_not_admin_terminated",
        ),
        Index(
            "ix_exam_attempts_status_heartbeat",
            "status",
            "last_heartbeat_at",
        ),
    )


# ========================== #
# ATTEMPT INTERRUPTION
# ========================== #


class AttemptInterruption(Base):
    """
    Historical record of one candidate-specific interruption.

    This is different from ExamSuspension:

        ExamSuspension
            affects the whole examination.

        AttemptInterruption
            affects one candidate's sitting.

    Examples:

        - candidate computer crashes;
        - candidate loses connection for long enough to be considered
          genuinely disconnected;
        - invigilator moves the candidate to another computer.

    Multiple interruptions may occur during one attempt.

    Only one unresolved interruption may exist for an attempt at a time.
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

    # Frozen remaining writing time at the interruption boundary.
    remaining_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        String(ATTEMPT_REASON_MAX_LENGTH),
        nullable=False,
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
        CheckConstraint(
            "resumed_at IS NULL OR resumed_by_actor_id IS NOT NULL",
            name="ck_attempt_interruptions_resume_actor_required",
        ),
        CheckConstraint(
            "resumed_at IS NULL OR resume_reason IS NOT NULL",
            name="ck_attempt_interruptions_resume_reason_required",
        ),
        # An attempt cannot have two unresolved interruptions at once.
        Index(
            "uq_attempt_interruptions_one_open",
            "attempt_id",
            unique=True,
            postgresql_where=sql_text("resumed_at IS NULL"),
        ),
        Index(
            "ix_attempt_interruptions_attempt_interrupted",
            "attempt_id",
            "interrupted_at",
        ),
    )


# ========================== #
# QUESTION ALLOCATION
# ========================== #


class AttemptQuestionAllocation(Base):
    """
    One frozen examination question allocated to one candidate attempt.

    Allocation is generated once when the candidate begins the exam and
    is then persisted.

    This ensures that refresh, reconnection, server restart, or device
    transfer never reshuffles the candidate's paper.

    `position` is the candidate-specific presentation position.

    Example:

        Exam canonical order:
            Q1 Q2 Q3

        Candidate order:
            Q3 Q1 Q2

        AttemptQuestionAllocation stores:
            Q3 -> position 1
            Q1 -> position 2
            Q2 -> position 3
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


# ========================== #
# OPTION ALLOCATION
# ========================== #


class AttemptOptionAllocation(Base):
    """
    Persisted candidate-specific presentation order for one answer option.

    The underlying correct answer remains on ExamQuestionOption.

    This table only controls which order the candidate sees the options in.
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


# ========================== #
# ATTEMPT ANSWER
# ========================== #


class AttemptAnswer(Base):
    """
    Current durable candidate answer state for one allocated question.

    One AttemptAnswer exists per AttemptQuestionAllocation.

    The selected options themselves are stored in AttemptAnswerSelection
    because both single-select and multiple-select questions must be
    supported.

    `mutation_sequence` protects answer persistence from delayed or
    duplicated WebSocket messages.

    Example:

        sequence 15 -> option B
        sequence 16 -> option C

    If sequence 15 arrives after sequence 16:

        local stored sequence = 16
        incoming sequence     = 15

        -> reject/ignore sequence 15

    If sequence 16 is resent because PostgreSQL committed but the ACK was
    lost:

        local stored sequence = 16
        incoming sequence     = 16

        -> treat as idempotent and ACK the already-saved state

    Sequence numbers are scoped to THIS question, not globally to the
    entire attempt. This prevents an answer on one question from causing
    a valid delayed update for another question to be rejected.
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
        server_default=sql_text("false"),
    )

    # Latest accepted client mutation number for this question.
    #
    # 0 means the question has not received any candidate mutation yet.
    mutation_sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=sql_text("0"),
    )

    # Time the question currently became answered.
    #
    # If the candidate clears every selected option, this may return to NULL.
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Last accepted mutation persisted to this answer row.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "mutation_sequence >= 0",
            name="ck_attempt_answers_mutation_sequence_nonnegative",
        ),
        Index(
            "ix_attempt_answers_updated",
            "updated_at",
        ),
    )


# ========================== #
# ANSWER SELECTION
# ========================== #


class AttemptAnswerSelection(Base):
    """
    One option currently selected for one candidate answer.

    A single-choice question normally has one row.

    A multiple-select question may have several rows.

    Example:

        Correct choices: A + C

        candidate selects:
            A
            C

        -> two AttemptAnswerSelection rows

    Scoring later uses exact-set matching:

        selected option set == correct option set
            -> 1 raw mark

        otherwise
            -> 0 raw marks

    No partial credit is awarded.
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
