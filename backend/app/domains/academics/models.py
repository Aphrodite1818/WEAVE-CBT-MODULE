"""Local academic projections synchronized from Weave Cloud v2.

These rows are read-only projections from Weave. Their primary keys are the
Weave UUIDs supplied by the synchronization contract. Local CBT-owned domains
reference them, but CBT never mutates the academic meaning of these records.
"""

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
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

NAME_MAX_LENGTH = 255
STATUS_MAX_LENGTH = 64
CODE_MAX_LENGTH = 64
ADMISSION_NUMBER_MAX_LENGTH = 128
STAFF_ID_MAX_LENGTH = 128
EMAIL_MAX_LENGTH = 255
CATEGORY_MAX_LENGTH = 64
TIMEZONE_MAX_LENGTH = 128
INSTITUTION_TYPE_MAX_LENGTH = 64


class WeaveProjectionMixin:
    """Common synchronization metadata for Weave-owned projection rows."""

    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    source_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )


class SchoolProfile(WeaveProjectionMixin, Base):
    """Paired school identity/context projected from the bootstrap envelope."""

    __tablename__ = "school_profiles"

    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), nullable=False)
    institution_type: Mapped[str | None] = mapped_column(
        String(INSTITUTION_TYPE_MAX_LENGTH), nullable=True
    )
    timezone: Mapped[str] = mapped_column(String(TIMEZONE_MAX_LENGTH), nullable=False)


class AcademicSession(WeaveProjectionMixin, Base):
    __tablename__ = "academic_sessions"

    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), nullable=False)
    status: Mapped[str] = mapped_column(String(STATUS_MAX_LENGTH), nullable=False, index=True)
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"), index=True
    )

    __table_args__ = (
        Index("ix_academic_sessions_current_status", "is_current", "status"),
    )


class AcademicTerm(WeaveProjectionMixin, Base):
    __tablename__ = "academic_terms"

    academic_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), nullable=False)
    status: Mapped[str] = mapped_column(String(STATUS_MAX_LENGTH), nullable=False, index=True)
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"), index=True
    )

    __table_args__ = (
        Index("ix_academic_terms_session_current", "academic_session_id", "is_current"),
    )


class AcademicLevel(WeaveProjectionMixin, Base):
    __tablename__ = "academic_levels"

    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), nullable=False)
    category: Mapped[str] = mapped_column(String(CATEGORY_MAX_LENGTH), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_academic_levels_position_nonnegative"),
        Index("ix_academic_levels_category_position", "category", "position"),
    )


class ArmLabel(WeaveProjectionMixin, Base):
    __tablename__ = "arm_labels"

    label: Mapped[str] = mapped_column(String(CODE_MAX_LENGTH), nullable=False)

    __table_args__ = (
        Index(
            "uq_arm_labels_current_label",
            "label",
            unique=True,
            postgresql_where=text("source_deleted_at IS NULL"),
        ),
    )


class Department(WeaveProjectionMixin, Base):
    __tablename__ = "departments"

    academic_level_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_levels.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), nullable=False)

    __table_args__ = (
        Index(
            "uq_departments_current_level_name",
            "academic_level_id",
            "name",
            unique=True,
            postgresql_where=text("source_deleted_at IS NULL"),
        ),
        Index("ix_departments_level_name", "academic_level_id", "name"),
    )


class AcademicClass(WeaveProjectionMixin, Base):
    __tablename__ = "academic_classes"

    academic_level_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_levels.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    arm_label_id: Mapped[UUID] = mapped_column(
        ForeignKey("arm_labels.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true"), index=True
    )

    __table_args__ = (
        Index(
            "uq_academic_classes_current_level_arm_label",
            "academic_level_id",
            "arm_label_id",
            unique=True,
            postgresql_where=text("source_deleted_at IS NULL"),
        ),
        Index("ix_academic_classes_level_active", "academic_level_id", "is_active"),
    )


class ClassTermDepartment(WeaveProjectionMixin, Base):
    __tablename__ = "class_term_departments"

    class_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_classes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    academic_term_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_terms.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    __table_args__ = (
        Index(
            "uq_class_term_departments_current_class_term",
            "class_id",
            "academic_term_id",
            unique=True,
            postgresql_where=text("source_deleted_at IS NULL"),
        ),
        Index("ix_class_term_departments_term_department", "academic_term_id", "department_id"),
    )


class AcademicSubject(WeaveProjectionMixin, Base):
    __tablename__ = "academic_subjects"

    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), nullable=False)
    code: Mapped[str | None] = mapped_column(String(CODE_MAX_LENGTH), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true"), index=True
    )


class Curriculum(WeaveProjectionMixin, Base):
    __tablename__ = "curricula"

    academic_level_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_levels.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    __table_args__ = (
        Index(
            "uq_curricula_current_level",
            "academic_level_id",
            unique=True,
            postgresql_where=text("source_deleted_at IS NULL"),
        ),
    )


class CurriculumSubject(WeaveProjectionMixin, Base):
    __tablename__ = "curriculum_subjects"

    curriculum_id: Mapped[UUID] = mapped_column(
        ForeignKey("curricula.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subject_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_subjects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    is_elective: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"), index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true"), index=True
    )

    __table_args__ = (
        Index(
            "uq_curriculum_subjects_current_curriculum_subject",
            "curriculum_id",
            "subject_id",
            unique=True,
            postgresql_where=text("source_deleted_at IS NULL"),
        ),
        Index("ix_curriculum_subjects_curriculum_active", "curriculum_id", "is_active"),
    )


class SubjectOffering(WeaveProjectionMixin, Base):
    __tablename__ = "subject_offerings"

    curriculum_subject_id: Mapped[UUID] = mapped_column(
        ForeignKey("curriculum_subjects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    academic_term_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_terms.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    __table_args__ = (
        Index(
            "uq_subject_offerings_general",
            "curriculum_subject_id",
            "academic_term_id",
            unique=True,
            postgresql_where=text(
                "department_id IS NULL AND source_deleted_at IS NULL"
            ),
        ),
        Index(
            "uq_subject_offerings_department",
            "curriculum_subject_id",
            "academic_term_id",
            "department_id",
            unique=True,
            postgresql_where=text(
                "department_id IS NOT NULL AND source_deleted_at IS NULL"
            ),
        ),
        Index("ix_subject_offerings_term_subject", "academic_term_id", "curriculum_subject_id"),
    )


class AssessmentScheme(WeaveProjectionMixin, Base):
    __tablename__ = "assessment_schemes"

    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), nullable=False)
    status: Mapped[str] = mapped_column(String(STATUS_MAX_LENGTH), nullable=False, index=True)


class AssessmentComponent(WeaveProjectionMixin, Base):
    __tablename__ = "assessment_components"

    assessment_scheme_id: Mapped[UUID] = mapped_column(
        ForeignKey("assessment_schemes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), nullable=False)
    code: Mapped[str | None] = mapped_column(String(CODE_MAX_LENGTH), nullable=True)
    maximum_score: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true"), index=True
    )

    __table_args__ = (
        Index(
            "uq_assessment_components_current_scheme_position",
            "assessment_scheme_id",
            "position",
            unique=True,
            postgresql_where=text("source_deleted_at IS NULL"),
        ),
        CheckConstraint("maximum_score > 0", name="ck_assessment_components_maximum_positive"),
        CheckConstraint("position >= 0", name="ck_assessment_components_position_nonnegative"),
        Index("ix_assessment_components_scheme_active", "assessment_scheme_id", "is_active"),
    )


class AcademicAdmin(WeaveProjectionMixin, Base):
    __tablename__ = "academic_admins"

    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(STATUS_MAX_LENGTH), nullable=False, index=True)


class AcademicTeacher(WeaveProjectionMixin, Base):
    __tablename__ = "academic_teachers"

    teacher_account_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    first_name: Mapped[str | None] = mapped_column(String(NAME_MAX_LENGTH), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(NAME_MAX_LENGTH), nullable=True)
    staff_id: Mapped[str | None] = mapped_column(String(STAFF_ID_MAX_LENGTH), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(STATUS_MAX_LENGTH), nullable=False, index=True)

    __table_args__ = (
        Index("ix_academic_teachers_status_name", "status", "last_name", "first_name"),
    )


class TeacherAssignment(WeaveProjectionMixin, Base):
    __tablename__ = "teacher_assignments"

    teacher_membership_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_teachers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    class_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_classes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    curriculum_subject_id: Mapped[UUID] = mapped_column(
        ForeignKey("curriculum_subjects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true"), index=True
    )

    __table_args__ = (
        Index(
            "uq_teacher_assignments_active_scope",
            "class_id",
            "curriculum_subject_id",
            unique=True,
            postgresql_where=text(
                "is_active = true AND source_deleted_at IS NULL"
            ),
        ),
        Index("ix_teacher_assignments_teacher_active", "teacher_membership_id", "is_active"),
        Index("ix_teacher_assignments_class_subject_active", "class_id", "curriculum_subject_id", "is_active"),
    )


class StudentEnrollment(WeaveProjectionMixin, Base):
    __tablename__ = "student_enrollments"

    student_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    admission_number: Mapped[str] = mapped_column(String(ADMISSION_NUMBER_MAX_LENGTH), nullable=False, index=True)
    first_name: Mapped[str | None] = mapped_column(String(NAME_MAX_LENGTH), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(NAME_MAX_LENGTH), nullable=True)
    academic_level_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_levels.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    class_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("academic_classes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    academic_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true"), index=True
    )
    student_status: Mapped[str] = mapped_column(String(STATUS_MAX_LENGTH), nullable=False, index=True)

    __table_args__ = (
        Index(
            "uq_student_enrollments_current_student",
            "student_id",
            unique=True,
            postgresql_where=text("is_current = true AND source_deleted_at IS NULL"),
        ),
        Index("ix_student_enrollments_class_current", "class_id", "is_current"),
        Index("ix_student_enrollments_session_current", "academic_session_id", "is_current"),
    )


class SubjectOfferingEligibility(Base):
    """Normalized candidate eligibility projected from an offering payload."""

    __tablename__ = "subject_offering_eligibilities"

    offering_id: Mapped[UUID] = mapped_column(
        ForeignKey("subject_offerings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enrollment_id: Mapped[UUID] = mapped_column(
        ForeignKey("student_enrollments.id", ondelete="CASCADE"), nullable=False, index=True
    )

    __table_args__ = (
        UniqueConstraint("offering_id", "enrollment_id", name="uq_subject_offering_eligibility"),
        Index("ix_subject_offering_eligibilities_enrollment", "enrollment_id", "offering_id"),
    )
