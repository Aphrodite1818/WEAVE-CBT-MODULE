# ===================================== #
# backend.app.domains.academics.models
# ===================================== #

"""Local academic projection models synchronized from Weave."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

WEAVE_ID_MAX_LENGTH = 128
ACADEMIC_NAME_MAX_LENGTH = 255
ACADEMIC_STATUS_MAX_LENGTH = 64
ACADEMIC_CODE_MAX_LENGTH = 64
CLASS_ARM_MAX_LENGTH = 64
ADMISSION_NUMBER_MAX_LENGTH = 128
SYNC_CURSOR_MAX_LENGTH = 512
SYNC_ERROR_MAX_LENGTH = 1024


class SyncTimestampMixin:
    """Timestamp recording when a Weave projection was last synchronized."""

    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class AcademicSession(SyncTimestampMixin, Base):
    """Academic session synchronized from Weave."""

    __tablename__ = "academic_sessions"

    weave_session_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
        unique=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(ACADEMIC_NAME_MAX_LENGTH),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(ACADEMIC_STATUS_MAX_LENGTH),
        nullable=False,
    )

    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    starts_on: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ends_on: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on",
            name="ck_academic_sessions_valid_dates",
        ),
    )


class AcademicTerm(SyncTimestampMixin, Base):
    """Academic term synchronized from Weave."""

    __tablename__ = "academic_terms"

    weave_term_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
        unique=True,
        index=True,
    )

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "academic_sessions.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(ACADEMIC_NAME_MAX_LENGTH),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(ACADEMIC_STATUS_MAX_LENGTH),
        nullable=False,
    )

    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    starts_on: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ends_on: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on",
            name="ck_academic_terms_valid_dates",
        ),
        Index(
            "ix_academic_terms_session_current",
            "session_id",
            "is_current",
        ),
    )


class AcademicLevel(SyncTimestampMixin, Base):
    """Academic level such as JSS1, JSS2, SS1, or SS2."""

    __tablename__ = "academic_levels"

    weave_level_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
        unique=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(ACADEMIC_NAME_MAX_LENGTH),
        nullable=False,
    )

    code: Mapped[str | None] = mapped_column(
        String(ACADEMIC_CODE_MAX_LENGTH),
        nullable=True,
    )

    position: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    __table_args__ = (
        CheckConstraint(
            "position IS NULL OR position >= 1",
            name="ck_academic_levels_position_positive",
        ),
        Index(
            "ix_academic_levels_active_position",
            "is_active",
            "position",
        ),
    )


class AcademicClass(SyncTimestampMixin, Base):
    """Actual class arm belonging to an AcademicLevel, such as JSS1 A."""

    __tablename__ = "academic_classes"

    weave_class_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
        unique=True,
        index=True,
    )

    level_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "academic_levels.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(ACADEMIC_NAME_MAX_LENGTH),
        nullable=False,
    )

    arm: Mapped[str | None] = mapped_column(
        String(CLASS_ARM_MAX_LENGTH),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    __table_args__ = (
        Index(
            "ix_academic_classes_level_active",
            "level_id",
            "is_active",
        ),
    )


class AcademicSubject(SyncTimestampMixin, Base):
    """Academic subject synchronized from Weave."""

    __tablename__ = "academic_subjects"

    weave_subject_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
        unique=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(ACADEMIC_NAME_MAX_LENGTH),
        nullable=False,
    )

    code: Mapped[str | None] = mapped_column(
        String(ACADEMIC_CODE_MAX_LENGTH),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )


class AcademicLevelSubject(SyncTimestampMixin, Base):
    """
    Curriculum mapping showing that a subject belongs to an academic level.

    Example: JSS1 -> Mathematics. Teacher delivery remains arm-specific through
    TeacherAssignment; sharing a level never grants a teacher access to every
    class arm in that level.
    """

    __tablename__ = "academic_level_subjects"

    weave_mapping_id: Mapped[str | None] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=True,
        unique=True,
        index=True,
    )

    level_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "academic_levels.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    subject_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "academic_subjects.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    __table_args__ = (
        UniqueConstraint(
            "level_id",
            "subject_id",
            name="uq_academic_level_subjects_level_subject",
        ),
        Index(
            "ix_academic_level_subjects_level_subject_active",
            "level_id",
            "subject_id",
            "is_active",
        ),
    )


class AssessmentComponent(SyncTimestampMixin, Base):
    """Dynamic assessment component synchronized from Weave."""

    __tablename__ = "assessment_components"

    weave_component_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
        unique=True,
        index=True,
    )

    term_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "academic_terms.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(ACADEMIC_NAME_MAX_LENGTH),
        nullable=False,
    )

    maximum_score: Mapped[Decimal] = mapped_column(
        Numeric(8, 2),
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    __table_args__ = (
        CheckConstraint(
            "maximum_score > 0",
            name="ck_assessment_components_maximum_score_positive",
        ),
        CheckConstraint(
            "position >= 1",
            name="ck_assessment_components_position_positive",
        ),
        Index(
            "ix_assessment_components_term_active_position",
            "term_id",
            "is_active",
            "position",
        ),
    )


class TeacherAssignment(SyncTimestampMixin, Base):
    """Local projection of a teacher's arm-specific class-subject assignment."""

    __tablename__ = "teacher_assignments"

    weave_assignment_id: Mapped[str | None] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=True,
        unique=True,
        index=True,
    )

    weave_teacher_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
        index=True,
    )

    weave_membership_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
        index=True,
    )

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "academic_sessions.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    class_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "academic_classes.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    subject_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "academic_subjects.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "weave_membership_id",
            "class_id",
            "subject_id",
            name="uq_teacher_assignments_session_membership_class_subject",
        ),
        Index(
            "ix_teacher_assignments_membership_active",
            "weave_membership_id",
            "is_active",
        ),
        Index(
            "ix_teacher_assignments_class_subject_active",
            "class_id",
            "subject_id",
            "is_active",
        ),
    )


class StudentEnrollment(SyncTimestampMixin, Base):
    """Local projection of a Weave student enrollment for one session/class."""

    __tablename__ = "student_enrollments"

    weave_enrollment_id: Mapped[str | None] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=True,
        unique=True,
        index=True,
    )

    weave_student_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
        index=True,
    )

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "academic_sessions.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    class_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "academic_classes.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    admission_number: Mapped[str] = mapped_column(
        String(ADMISSION_NUMBER_MAX_LENGTH),
        nullable=False,
        index=True,
    )

    display_name: Mapped[str] = mapped_column(
        String(ACADEMIC_NAME_MAX_LENGTH),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "weave_student_id",
            name="uq_student_enrollments_session_student",
        ),
        UniqueConstraint(
            "session_id",
            "admission_number",
            name="uq_student_enrollments_session_admission_number",
        ),
        Index(
            "ix_student_enrollments_class_active",
            "class_id",
            "is_active",
        ),
    )


class AcademicSyncState(Base):
    """Cursor/checkpoint and health bookkeeping for academic synchronization."""

    __tablename__ = "academic_sync_states"

    scope: Mapped[str] = mapped_column(
        String(ACADEMIC_STATUS_MAX_LENGTH),
        nullable=False,
        unique=True,
    )

    source_cursor: Mapped[str | None] = mapped_column(
        String(SYNC_CURSOR_MAX_LENGTH),
        nullable=True,
    )

    last_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_successful_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            f"last_error IS NULL OR char_length(last_error) <= {SYNC_ERROR_MAX_LENGTH}",
            name="ck_academic_sync_states_error_length",
        ),
    )
