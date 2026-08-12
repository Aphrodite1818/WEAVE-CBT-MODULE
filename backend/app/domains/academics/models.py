# ===================================== #
# backend.app.domains.academics.models
# ===================================== #

"""Local academic projection models synchronized from Weave.

These tables are not a second academic-management system. They are the minimum
local projection the CBT runtime needs for authoring authorization, exam scope,
candidate preparation, and result attribution while remaining operational on
the school LAN.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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
TEACHER_EMAIL_MAX_LENGTH = 255
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

    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_academic_sessions_valid_dates",
        ),
        Index(
            "ix_academic_sessions_current_status",
            "is_current",
            "status",
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
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"),
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

    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_academic_terms_valid_dates",
        ),
        Index(
            "ix_academic_terms_session_current",
            "session_id",
            "is_current",
        ),
    )


class AcademicLevel(SyncTimestampMixin, Base):
    """Curriculum level such as JSS1, JSS2, SS1, or SS2."""

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

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    is_terminal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    weave_next_level_id: Mapped[str | None] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        Index(
            "ix_academic_levels_active_name",
            "is_active",
            "name",
        ),
    )


class AcademicClass(SyncTimestampMixin, Base):
    """Concrete class arm belonging to one AcademicLevel, for example JSS1 A."""

    __tablename__ = "academic_classes"

    weave_class_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
        unique=True,
        index=True,
    )

    level_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_levels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    arm: Mapped[str] = mapped_column(
        String(CLASS_ARM_MAX_LENGTH),
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
            "level_id",
            "arm",
            name="uq_academic_classes_level_arm",
        ),
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
    """Weave LevelSubject projection: one subject taught at one academic level."""

    __tablename__ = "academic_level_subjects"

    weave_level_subject_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
        unique=True,
        index=True,
    )

    level_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_levels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    subject_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_subjects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    is_core: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
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


class AssessmentScheme(SyncTimestampMixin, Base):
    """Assessment scheme synchronized from Weave."""

    __tablename__ = "assessment_schemes"

    weave_scheme_id: Mapped[str] = mapped_column(
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
        index=True,
    )

    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index(
            "ix_assessment_schemes_status",
            "status",
        ),
    )


class AssessmentComponent(SyncTimestampMixin, Base):
    """Assessment component belonging to a synchronized Weave scheme."""

    __tablename__ = "assessment_components"

    weave_component_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
        unique=True,
        index=True,
    )

    assessment_scheme_id: Mapped[UUID] = mapped_column(
        ForeignKey("assessment_schemes.id", ondelete="RESTRICT"),
        nullable=False,
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

    maximum_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )

    position: Mapped[int] = mapped_column(Integer, nullable=False)

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    __table_args__ = (
        UniqueConstraint(
            "assessment_scheme_id",
            "name",
            name="uq_assessment_components_scheme_name",
        ),
        UniqueConstraint(
            "assessment_scheme_id",
            "position",
            name="uq_assessment_components_scheme_position",
        ),
        CheckConstraint(
            "maximum_score > 0 AND maximum_score <= 100",
            name="ck_assessment_components_maximum_score",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_assessment_components_position_nonnegative",
        ),
        Index(
            "ix_assessment_components_scheme_active_position",
            "assessment_scheme_id",
            "is_active",
            "position",
        ),
    )


class AcademicTeacher(SyncTimestampMixin, Base):
    """Minimal local directory projection of a Weave teacher membership."""

    __tablename__ = "academic_teachers"

    weave_teacher_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
        unique=True,
        index=True,
    )

    weave_membership_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
        unique=True,
        index=True,
    )

    display_name: Mapped[str] = mapped_column(
        String(ACADEMIC_NAME_MAX_LENGTH),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(TEACHER_EMAIL_MAX_LENGTH),
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
        CheckConstraint(
            "char_length(trim(display_name)) > 0",
            name="ck_academic_teachers_display_name_not_blank",
        ),
        CheckConstraint(
            "char_length(trim(email)) > 0",
            name="ck_academic_teachers_email_not_blank",
        ),
        Index(
            "ix_academic_teachers_active_name",
            "is_active",
            "display_name",
        ),
    )


class TeacherAssignment(SyncTimestampMixin, Base):
    """Arm-specific Weave teacher assignment projected into the CBT runtime."""

    __tablename__ = "teacher_assignments"

    weave_assignment_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
        unique=True,
        index=True,
    )

    teacher_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_teachers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    class_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_classes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    level_subject_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_level_subjects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_teacher_assignments_effective_range",
        ),
        Index(
            "uq_teacher_assignments_active_class_level_subject",
            "class_id",
            "level_subject_id",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
        Index(
            "ix_teacher_assignments_teacher_active",
            "teacher_id",
            "is_active",
        ),
        Index(
            "ix_teacher_assignments_teacher_level_subject_active",
            "teacher_id",
            "level_subject_id",
            "is_active",
        ),
    )


class StudentEnrollment(SyncTimestampMixin, Base):
    """Historical local projection of one Weave StudentEnrollment row."""

    __tablename__ = "student_enrollments"

    weave_enrollment_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
        unique=True,
        index=True,
    )

    weave_student_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
        index=True,
    )

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    class_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_classes.id", ondelete="RESTRICT"),
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

    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    outcome: Mapped[str] = mapped_column(
        String(ACADEMIC_STATUS_MAX_LENGTH),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "ended_on IS NULL OR ended_on >= started_on",
            name="ck_student_enrollments_valid_dates",
        ),
        CheckConstraint(
            "(is_current = true AND ended_on IS NULL) OR "
            "(is_current = false AND ended_on IS NOT NULL)",
            name="ck_student_enrollments_current_end_consistency",
        ),
        Index(
            "uq_student_enrollments_one_current_student",
            "weave_student_id",
            unique=True,
            postgresql_where=text("is_current = true"),
        ),
        Index(
            "uq_student_enrollments_one_current_admission_number",
            "admission_number",
            unique=True,
            postgresql_where=text("is_current = true"),
        ),
        Index(
            "ix_student_enrollments_class_current",
            "class_id",
            "is_current",
        ),
        Index(
            "ix_student_enrollments_student_session",
            "weave_student_id",
            "session_id",
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

    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            f"last_error IS NULL OR char_length(last_error) <= {SYNC_ERROR_MAX_LENGTH}",
            name="ck_academic_sync_states_error_length",
        ),
    )
