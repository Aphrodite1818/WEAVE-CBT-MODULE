"""Database models for locally owned CBT examinations."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.domains.questions.models import QuestionType

EXAM_TITLE_MAX_LENGTH = 255
EXAM_IMAGE_URL_MAX_LENGTH = 2048
ACADEMIC_NAME_MAX_LENGTH = 255
ACADEMIC_CODE_MAX_LENGTH = 64
WEAVE_ID_MAX_LENGTH = 128


class ExamStatus(str, PyEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    SEALED = "sealed"
    ACTIVE = "active"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class Exam(Base):
    """Local examination scoped to one synchronized CurriculumSubject and term."""

    __tablename__ = "exams"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    term_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_terms.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    curriculum_subject_id: Mapped[UUID] = mapped_column(
        ForeignKey("curriculum_subjects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    assessment_scheme_id: Mapped[UUID] = mapped_column(
        ForeignKey("assessment_schemes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    assessment_component_id: Mapped[UUID] = mapped_column(
        ForeignKey("assessment_components.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(EXAM_TITLE_MAX_LENGTH), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ExamStatus] = mapped_column(
        SQLEnum(
            ExamStatus,
            name="exam_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ExamStatus.DRAFT,
        server_default=ExamStatus.DRAFT.value,
        index=True,
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    maximum_score: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shuffle_questions: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    shuffle_options: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_by_actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("local_actors.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    submitted_by_actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("local_actors.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Frozen Weave academic provenance captured at seal time.
    source_assessment_scheme_id: Mapped[UUID | None] = mapped_column(nullable=True)
    source_assessment_component_id: Mapped[UUID | None] = mapped_column(nullable=True)
    source_assessment_component_name: Mapped[str | None] = mapped_column(
        String(ACADEMIC_NAME_MAX_LENGTH), nullable=True
    )
    source_assessment_component_code: Mapped[str | None] = mapped_column(
        String(ACADEMIC_CODE_MAX_LENGTH), nullable=True
    )
    source_assessment_component_maximum_score: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True
    )

    weave_calendar_event_id: Mapped[str | None] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH), nullable=True, unique=True, index=True
    )
    calendar_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "uq_exams_term_curriculum_subject_title_lower",
            "term_id",
            "curriculum_subject_id",
            func.lower(title),
            unique=True,
        ),
        CheckConstraint("duration_minutes > 0", name="ck_exams_duration_positive"),
        CheckConstraint("maximum_score > 0", name="ck_exams_maximum_score_positive"),
        CheckConstraint(
            "source_assessment_component_maximum_score IS NULL OR "
            "source_assessment_component_maximum_score > 0",
            name="ck_exams_source_component_maximum_positive",
        ),
        CheckConstraint(
            "closes_at IS NULL OR opens_at IS NULL OR closes_at > opens_at",
            name="ck_exams_valid_schedule",
        ),
        CheckConstraint(
            "submitted_at IS NULL OR submitted_by_actor_id IS NOT NULL",
            name="ck_exams_submission_actor_required",
        ),
        Index("ix_exams_session_term_status", "session_id", "term_id", "status"),
        Index(
            "ix_exams_curriculum_subject_status",
            "curriculum_subject_id",
            "status",
        ),
        Index("ix_exams_component_status", "assessment_component_id", "status"),
    )


class ExamTargetClass(Base):
    """Concrete class delivery target with frozen Weave authorization provenance."""

    __tablename__ = "exam_target_classes"

    exam_id: Mapped[UUID] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_classes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subject_offering_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("subject_offerings.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    teacher_assignment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("teacher_assignments.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    __table_args__ = (
        UniqueConstraint("exam_id", "class_id", name="uq_exam_target_classes_exam_class"),
        Index("ix_exam_target_classes_class_exam", "class_id", "exam_id"),
        Index("ix_exam_target_classes_offering", "subject_offering_id"),
        Index("ix_exam_target_classes_assignment", "teacher_assignment_id"),
    )


class ExamInvigilator(Base):
    __tablename__ = "exam_invigilators"

    exam_id: Mapped[UUID] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teacher_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_teachers.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    __table_args__ = (
        UniqueConstraint("exam_id", "teacher_id", name="uq_exam_invigilators_exam_teacher"),
        Index("ix_exam_invigilators_teacher_exam", "teacher_id", "exam_id"),
    )


class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    exam_id: Mapped[UUID] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_question_version: Mapped[int] = mapped_column(Integer, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(
        SQLEnum(
            QuestionType,
            name="exam_question_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(EXAM_IMAGE_URL_MAX_LENGTH), nullable=True)
    points: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)

    __table_args__ = (
        UniqueConstraint("exam_id", "source_question_id", name="uq_exam_questions_exam_source_question"),
        UniqueConstraint("exam_id", "position", name="uq_exam_questions_exam_position"),
        CheckConstraint("source_question_version >= 1", name="ck_exam_questions_source_version_positive"),
        CheckConstraint("position >= 1", name="ck_exam_questions_position_positive"),
        CheckConstraint("points > 0", name="ck_exam_questions_points_positive"),
        Index("ix_exam_questions_exam_position", "exam_id", "position"),
    )


class ExamQuestionOption(Base):
    __tablename__ = "exam_question_options"

    exam_question_id: Mapped[UUID] = mapped_column(
        ForeignKey("exam_questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    __table_args__ = (
        UniqueConstraint(
            "exam_question_id",
            "position",
            name="uq_exam_question_options_question_position",
        ),
        CheckConstraint("position >= 1", name="ck_exam_question_options_position_positive"),
        Index("ix_exam_question_options_question_position", "exam_question_id", "position"),
    )
