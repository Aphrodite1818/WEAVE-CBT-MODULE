"""Persistence operations for Weave academic projections.

Repositories only read/write local PostgreSQL projections. They never call
Weave and never commit transactions. Synchronization policy belongs to the sync
domain; exam/question authorization belongs to their respective services.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base
from app.domains.academics.models import (
    AcademicAdmin,
    AcademicClass,
    AcademicLevel,
    AcademicSession,
    AcademicSubject,
    AcademicTeacher,
    AcademicTerm,
    ArmLabel,
    AssessmentComponent,
    AssessmentScheme,
    ClassTermDepartment,
    Curriculum,
    CurriculumSubject,
    Department,
    StudentEnrollment,
    SubjectOffering,
    TeacherAssignment,
)

ProjectionT = TypeVar("ProjectionT", bound=Base)
PROJECTION_WRITE_BATCH_SIZE = 1000

PROJECTION_MODELS: tuple[type[Base], ...] = (
    AcademicSession,
    AcademicTerm,
    AcademicLevel,
    ArmLabel,
    Department,
    AcademicClass,
    ClassTermDepartment,
    AcademicSubject,
    Curriculum,
    CurriculumSubject,
    SubjectOffering,
    AssessmentScheme,
    AssessmentComponent,
    AcademicAdmin,
    AcademicTeacher,
    TeacherAssignment,
    StudentEnrollment,
)


class AcademicRepository:
    """Data-access layer for current and historical Weave projections."""

    @staticmethod
    async def bulk_upsert_projections(
        db: AsyncSession,
        model: type[ProjectionT],
        rows: Sequence[dict[str, Any]],
        *,
        synced_at: datetime | None = None,
    ) -> None:
        """Upsert projection rows in bounded PostgreSQL batches.

        Chunking avoids PostgreSQL/asyncpg parameter-count ceilings for large
        schools while still reducing thousands of row-at-a-time flushes to a
        handful of set-based statements.
        """

        if not rows:
            return
        timestamp = synced_at or datetime.now(UTC)
        for start in range(0, len(rows), PROJECTION_WRITE_BATCH_SIZE):
            chunk = rows[start : start + PROJECTION_WRITE_BATCH_SIZE]
            values = [
                {
                    **row,
                    "synced_at": timestamp,
                    "source_deleted_at": None,
                }
                for row in chunk
            ]
            statement = pg_insert(model).values(values)
            mutable_columns = {
                key: getattr(statement.excluded, key)
                for key in values[0]
                if key != "id"
            }
            if "updated_at" in model.__table__.c:
                mutable_columns["updated_at"] = func.now()
            await db.execute(
                statement.on_conflict_do_update(
                    index_elements=[model.id],
                    set_=mutable_columns,
                )
            )

    @classmethod
    async def upsert_projection(
        cls,
        db: AsyncSession,
        model: type[ProjectionT],
        entity_id: UUID,
        values: dict[str, Any],
        *,
        synced_at: datetime | None = None,
    ) -> ProjectionT:
        await cls.bulk_upsert_projections(
            db,
            model,
            [{"id": entity_id, **values}],
            synced_at=synced_at,
        )
        row = await db.get(model, entity_id)
        if row is None:
            raise RuntimeError(f"Failed to upsert {model.__name__} {entity_id}.")
        return row

    @staticmethod
    async def bulk_tombstone_projections(
        db: AsyncSession,
        model: type[ProjectionT],
        entity_ids: Sequence[UUID],
        *,
        deleted_at: datetime | None = None,
    ) -> None:
        unique_ids = tuple(dict.fromkeys(entity_ids))
        if not unique_ids:
            return
        timestamp = deleted_at or datetime.now(UTC)
        for start in range(0, len(unique_ids), PROJECTION_WRITE_BATCH_SIZE):
            chunk = unique_ids[start : start + PROJECTION_WRITE_BATCH_SIZE]
            await db.execute(
                update(model)
                .where(model.id.in_(chunk))
                .values(
                    source_deleted_at=timestamp,
                    updated_at=func.now(),
                )
            )

    @classmethod
    async def tombstone_projection(
        cls,
        db: AsyncSession,
        model: type[ProjectionT],
        entity_id: UUID,
        *,
        deleted_at: datetime | None = None,
    ) -> ProjectionT | None:
        await cls.bulk_tombstone_projections(
            db,
            model,
            [entity_id],
            deleted_at=deleted_at,
        )
        return await db.get(model, entity_id)

    @staticmethod
    async def mark_all_projection_rows_deleted(
        db: AsyncSession,
        *,
        deleted_at: datetime | None = None,
    ) -> None:
        timestamp = deleted_at or datetime.now(UTC)
        for model in PROJECTION_MODELS:
            await db.execute(
                update(model).values(
                    source_deleted_at=timestamp,
                    updated_at=func.now(),
                )
            )

    @staticmethod
    async def _get_by_id(
        db: AsyncSession,
        model: type[ProjectionT],
        entity_id: UUID,
        *,
        lock: bool = False,
        include_deleted: bool = False,
    ) -> ProjectionT | None:
        query = select(model).where(model.id == entity_id)
        if not include_deleted and hasattr(model, "source_deleted_at"):
            query = query.where(model.source_deleted_at.is_(None))
        if lock:
            query = query.with_for_update(of=model)
        return (await db.execute(query)).scalar_one_or_none()

    @classmethod
    async def get_session_by_id(
        cls, db: AsyncSession, session_id: UUID, *, lock: bool = False
    ) -> AcademicSession | None:
        return await cls._get_by_id(db, AcademicSession, session_id, lock=lock)

    @staticmethod
    async def get_current_session(
        db: AsyncSession, *, lock: bool = False
    ) -> AcademicSession | None:
        query = select(AcademicSession).where(
            AcademicSession.is_current.is_(True),
            AcademicSession.source_deleted_at.is_(None),
        )
        if lock:
            query = query.with_for_update(of=AcademicSession)
        return (await db.execute(query)).scalar_one_or_none()

    @classmethod
    async def get_term_by_id(
        cls, db: AsyncSession, term_id: UUID, *, lock: bool = False
    ) -> AcademicTerm | None:
        return await cls._get_by_id(db, AcademicTerm, term_id, lock=lock)

    @staticmethod
    async def get_current_term(
        db: AsyncSession, *, session_id: UUID | None = None
    ) -> AcademicTerm | None:
        query = select(AcademicTerm).where(
            AcademicTerm.is_current.is_(True),
            AcademicTerm.source_deleted_at.is_(None),
        )
        if session_id is not None:
            query = query.where(AcademicTerm.academic_session_id == session_id)
        return (await db.execute(query)).scalar_one_or_none()

    @classmethod
    async def get_level_by_id(
        cls, db: AsyncSession, level_id: UUID, *, lock: bool = False
    ) -> AcademicLevel | None:
        return await cls._get_by_id(db, AcademicLevel, level_id, lock=lock)

    @staticmethod
    async def list_levels(db: AsyncSession) -> list[AcademicLevel]:
        result = await db.execute(
            select(AcademicLevel)
            .where(AcademicLevel.source_deleted_at.is_(None))
            .order_by(
                AcademicLevel.category.asc(),
                AcademicLevel.position.asc(),
                AcademicLevel.name.asc(),
            )
        )
        return list(result.scalars().all())

    @classmethod
    async def get_arm_label_by_id(
        cls, db: AsyncSession, arm_label_id: UUID
    ) -> ArmLabel | None:
        return await cls._get_by_id(db, ArmLabel, arm_label_id)

    @classmethod
    async def get_department_by_id(
        cls, db: AsyncSession, department_id: UUID
    ) -> Department | None:
        return await cls._get_by_id(db, Department, department_id)

    @classmethod
    async def get_class_by_id(
        cls, db: AsyncSession, class_id: UUID, *, lock: bool = False
    ) -> AcademicClass | None:
        return await cls._get_by_id(db, AcademicClass, class_id, lock=lock)

    @staticmethod
    async def list_classes_for_level(
        db: AsyncSession,
        academic_level_id: UUID,
        *,
        active_only: bool = True,
    ) -> list[AcademicClass]:
        query = select(AcademicClass).where(
            AcademicClass.academic_level_id == academic_level_id,
            AcademicClass.source_deleted_at.is_(None),
        )
        if active_only:
            query = query.where(AcademicClass.is_active.is_(True))
        result = await db.execute(query.order_by(AcademicClass.display_name.asc()))
        return list(result.scalars().all())

    @staticmethod
    async def get_class_term_department(
        db: AsyncSession,
        class_id: UUID,
        academic_term_id: UUID,
    ) -> ClassTermDepartment | None:
        return (
            await db.execute(
                select(ClassTermDepartment).where(
                    ClassTermDepartment.class_id == class_id,
                    ClassTermDepartment.academic_term_id == academic_term_id,
                    ClassTermDepartment.source_deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

    @classmethod
    async def get_subject_by_id(
        cls, db: AsyncSession, subject_id: UUID
    ) -> AcademicSubject | None:
        return await cls._get_by_id(db, AcademicSubject, subject_id)

    @classmethod
    async def get_curriculum_by_id(
        cls, db: AsyncSession, curriculum_id: UUID
    ) -> Curriculum | None:
        return await cls._get_by_id(db, Curriculum, curriculum_id)

    @staticmethod
    async def get_curriculum_for_level(
        db: AsyncSession, academic_level_id: UUID
    ) -> Curriculum | None:
        return (
            await db.execute(
                select(Curriculum).where(
                    Curriculum.academic_level_id == academic_level_id,
                    Curriculum.source_deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

    @classmethod
    async def get_curriculum_subject_by_id(
        cls,
        db: AsyncSession,
        curriculum_subject_id: UUID,
        *,
        lock: bool = False,
    ) -> CurriculumSubject | None:
        return await cls._get_by_id(
            db, CurriculumSubject, curriculum_subject_id, lock=lock
        )

    @staticmethod
    async def list_curriculum_subjects(
        db: AsyncSession,
        curriculum_id: UUID,
        *,
        active_only: bool = True,
    ) -> list[CurriculumSubject]:
        query = select(CurriculumSubject).where(
            CurriculumSubject.curriculum_id == curriculum_id,
            CurriculumSubject.source_deleted_at.is_(None),
        )
        if active_only:
            query = query.where(CurriculumSubject.is_active.is_(True))
        return list(
            (
                await db.execute(
                    query.order_by(CurriculumSubject.subject_id.asc())
                )
            ).scalars().all()
        )

    @classmethod
    async def get_offering_by_id(
        cls, db: AsyncSession, offering_id: UUID
    ) -> SubjectOffering | None:
        return await cls._get_by_id(db, SubjectOffering, offering_id)

    @staticmethod
    async def get_offering_for_scope(
        db: AsyncSession,
        *,
        academic_term_id: UUID,
        curriculum_subject_id: UUID,
        department_id: UUID | None,
    ) -> SubjectOffering | None:
        query = select(SubjectOffering).where(
            SubjectOffering.academic_term_id == academic_term_id,
            SubjectOffering.curriculum_subject_id == curriculum_subject_id,
            SubjectOffering.source_deleted_at.is_(None),
        )
        if department_id is None:
            query = query.where(SubjectOffering.department_id.is_(None))
        else:
            query = query.where(SubjectOffering.department_id == department_id)
        return (await db.execute(query)).scalar_one_or_none()

    @classmethod
    async def get_offering_for_class_scope(
        cls,
        db: AsyncSession,
        *,
        academic_term_id: UUID,
        curriculum_subject_id: UUID,
        class_id: UUID,
    ) -> SubjectOffering | None:
        specialization = await cls.get_class_term_department(
            db, class_id, academic_term_id
        )
        if specialization is not None:
            departmental = await cls.get_offering_for_scope(
                db,
                academic_term_id=academic_term_id,
                curriculum_subject_id=curriculum_subject_id,
                department_id=specialization.department_id,
            )
            if departmental is not None:
                return departmental
        return await cls.get_offering_for_scope(
            db,
            academic_term_id=academic_term_id,
            curriculum_subject_id=curriculum_subject_id,
            department_id=None,
        )

    @staticmethod
    def _eligible_enrollment_query(offering_id: UUID):
        departmental_match = exists(
            select(ClassTermDepartment.id).where(
                ClassTermDepartment.class_id == StudentEnrollment.class_id,
                ClassTermDepartment.academic_term_id == SubjectOffering.academic_term_id,
                ClassTermDepartment.department_id == SubjectOffering.department_id,
                ClassTermDepartment.source_deleted_at.is_(None),
            )
        )
        return (
            select(StudentEnrollment)
            .select_from(SubjectOffering)
            .join(
                CurriculumSubject,
                CurriculumSubject.id == SubjectOffering.curriculum_subject_id,
            )
            .join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id)
            .join(AcademicTerm, AcademicTerm.id == SubjectOffering.academic_term_id)
            .join(
                StudentEnrollment,
                and_(
                    StudentEnrollment.academic_level_id == Curriculum.academic_level_id,
                    StudentEnrollment.academic_session_id == AcademicTerm.academic_session_id,
                ),
            )
            .where(
                SubjectOffering.id == offering_id,
                SubjectOffering.source_deleted_at.is_(None),
                CurriculumSubject.source_deleted_at.is_(None),
                CurriculumSubject.is_active.is_(True),
                Curriculum.source_deleted_at.is_(None),
                AcademicTerm.source_deleted_at.is_(None),
                StudentEnrollment.source_deleted_at.is_(None),
                StudentEnrollment.is_current.is_(True),
                StudentEnrollment.student_status == "active",
                or_(
                    SubjectOffering.department_id.is_(None),
                    departmental_match,
                ),
            )
        )

    @classmethod
    async def enrollment_is_eligible_for_offering(
        cls,
        db: AsyncSession,
        *,
        offering_id: UUID,
        enrollment_id: UUID,
    ) -> bool:
        query = cls._eligible_enrollment_query(offering_id).where(
            StudentEnrollment.id == enrollment_id
        )
        return (await db.execute(query.limit(1))).scalar_one_or_none() is not None

    @classmethod
    async def list_eligible_enrollments_for_offering(
        cls,
        db: AsyncSession,
        offering_id: UUID,
        *,
        class_id: UUID | None = None,
    ) -> list[StudentEnrollment]:
        query = cls._eligible_enrollment_query(offering_id)
        if class_id is not None:
            query = query.where(StudentEnrollment.class_id == class_id)
        return list(
            (
                await db.execute(
                    query.order_by(StudentEnrollment.admission_number.asc())
                )
            ).scalars().all()
        )

    @classmethod
    async def get_assessment_scheme_by_id(
        cls, db: AsyncSession, scheme_id: UUID
    ) -> AssessmentScheme | None:
        return await cls._get_by_id(db, AssessmentScheme, scheme_id)

    @classmethod
    async def get_component_by_id(
        cls, db: AsyncSession, component_id: UUID
    ) -> AssessmentComponent | None:
        return await cls._get_by_id(db, AssessmentComponent, component_id)

    @classmethod
    async def get_admin_by_id(
        cls, db: AsyncSession, admin_id: UUID
    ) -> AcademicAdmin | None:
        return await cls._get_by_id(db, AcademicAdmin, admin_id)

    @classmethod
    async def get_teacher_by_id(
        cls, db: AsyncSession, teacher_id: UUID
    ) -> AcademicTeacher | None:
        return await cls._get_by_id(db, AcademicTeacher, teacher_id)

    @classmethod
    async def get_teacher_by_membership_id(
        cls,
        db: AsyncSession,
        membership_id: UUID | str,
    ) -> AcademicTeacher | None:
        try:
            teacher_id = membership_id if isinstance(membership_id, UUID) else UUID(membership_id)
        except (TypeError, ValueError):
            return None
        return await cls.get_teacher_by_id(db, teacher_id)

    @classmethod
    async def get_assignment_by_id(
        cls, db: AsyncSession, assignment_id: UUID
    ) -> TeacherAssignment | None:
        return await cls._get_by_id(db, TeacherAssignment, assignment_id)

    @staticmethod
    def _effective_assignment_predicates() -> tuple[Any, Any]:
        today = date.today()
        return (
            TeacherAssignment.effective_from <= today,
            or_(
                TeacherAssignment.effective_to.is_(None),
                TeacherAssignment.effective_to >= today,
            ),
        )

    @staticmethod
    async def get_active_assignment_for_scope(
        db: AsyncSession,
        *,
        teacher_membership_id: UUID,
        class_id: UUID,
        curriculum_subject_id: UUID,
    ) -> TeacherAssignment | None:
        return (
            await db.execute(
                select(TeacherAssignment).where(
                    TeacherAssignment.teacher_membership_id == teacher_membership_id,
                    TeacherAssignment.class_id == class_id,
                    TeacherAssignment.curriculum_subject_id == curriculum_subject_id,
                    TeacherAssignment.is_active.is_(True),
                    TeacherAssignment.source_deleted_at.is_(None),
                    *AcademicRepository._effective_assignment_predicates(),
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_active_assignment_for_class_curriculum_subject(
        db: AsyncSession,
        class_id: UUID,
        curriculum_subject_id: UUID,
    ) -> TeacherAssignment | None:
        return (
            await db.execute(
                select(TeacherAssignment).where(
                    TeacherAssignment.class_id == class_id,
                    TeacherAssignment.curriculum_subject_id == curriculum_subject_id,
                    TeacherAssignment.is_active.is_(True),
                    TeacherAssignment.source_deleted_at.is_(None),
                    *AcademicRepository._effective_assignment_predicates(),
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def teacher_has_curriculum_subject_assignment(
        db: AsyncSession,
        teacher_membership_id: UUID,
        curriculum_subject_id: UUID,
    ) -> bool:
        return bool(
            await db.scalar(
                select(
                    exists().where(
                        TeacherAssignment.teacher_membership_id == teacher_membership_id,
                        TeacherAssignment.curriculum_subject_id == curriculum_subject_id,
                        TeacherAssignment.is_active.is_(True),
                        TeacherAssignment.source_deleted_at.is_(None),
                        *AcademicRepository._effective_assignment_predicates(),
                    )
                )
            )
        )

    @classmethod
    async def get_enrollment_by_id(
        cls, db: AsyncSession, enrollment_id: UUID
    ) -> StudentEnrollment | None:
        return await cls._get_by_id(db, StudentEnrollment, enrollment_id)

    @staticmethod
    async def list_current_enrollments_for_class(
        db: AsyncSession,
        class_id: UUID,
    ) -> list[StudentEnrollment]:
        result = await db.execute(
            select(StudentEnrollment)
            .where(
                StudentEnrollment.class_id == class_id,
                StudentEnrollment.is_current.is_(True),
                StudentEnrollment.student_status == "active",
                StudentEnrollment.source_deleted_at.is_(None),
            )
            .order_by(StudentEnrollment.admission_number.asc())
        )
        return list(result.scalars().all())
