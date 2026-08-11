# =========================== #
#     questions/models.py     #
# =========================== #

"""Database models for locally owned CBT question banks and questions."""

from __future__ import annotations

from enum import Enum as PyEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
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

QUESTION_BANK_NAME_MAX_LENGTH = 255
QUESTION_IMAGE_URL_MAX_LENGTH = 2048


class QuestionType(str, PyEnum):
    """Question types currently supported by the CBT engine."""

    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"


class QuestionBank(Base):
    """
    Locally owned collection of questions for one academic level and subject.

    Example:

        Level: JSS1
        Subject: Mathematics
        Bank: Algebra Questions

    The bank may therefore be reused across JSS1 A, JSS1 B, JSS1 C, and any
    other class arm belonging to JSS1.
    """

    __tablename__ = "question_banks"

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

    name: Mapped[str] = mapped_column(
        String(QUESTION_BANK_NAME_MAX_LENGTH),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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
            "name",
            name="uq_question_banks_level_subject_name",
        ),
        Index(
            "ix_question_banks_level_subject_active",
            "level_id",
            "subject_id",
            "is_active",
        ),
    )


class Question(Base):
    """
    Authoritative locally stored question.

    Questions may optionally reference an image stored on the local CBT server.

    `version` increases whenever the question's meaningful content changes.
    Sealed exams later store their own immutable snapshot of the question.
    """

    __tablename__ = "questions"

    bank_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "question_banks.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    question_type: Mapped[QuestionType] = mapped_column(
        SQLEnum(
            QuestionType,
            name="question_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=QuestionType.SINGLE_CHOICE,
        server_default=QuestionType.SINGLE_CHOICE.value,
    )

    prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    instruction: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    image_url: Mapped[str | None] = mapped_column(
        String(QUESTION_IMAGE_URL_MAX_LENGTH),
        nullable=True,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    __table_args__ = (
        CheckConstraint(
            "version >= 1",
            name="ck_questions_version_positive",
        ),
        Index(
            "ix_questions_bank_active",
            "bank_id",
            "is_active",
        ),
    )


class QuestionOption(Base):
    """
    One selectable answer option belonging to a question.

    `is_correct` is server-side information and must never be exposed through
    candidate-facing APIs.
    """

    __tablename__ = "question_options"

    question_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "questions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    __table_args__ = (
        UniqueConstraint(
            "question_id",
            "position",
            name="uq_question_options_question_position",
        ),
        CheckConstraint(
            "position >= 1",
            name="ck_question_options_position_positive",
        ),
        Index(
            "ix_question_options_question_position",
            "question_id",
            "position",
        ),
    )