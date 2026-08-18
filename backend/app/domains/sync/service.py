"""Application services for Cloud -> local CBT synchronization.

Bootstrap and incremental recovery deliberately share the same entity
projection handlers. The WebSocket layer only wakes this reconciliation path;
PostgreSQL cursor recovery remains authoritative after disconnects or missed
live frames.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    SchoolProfile,
    StudentEnrollment,
    SubjectOffering,
    TeacherAssignment,
)
from app.domains.academics.repository import AcademicRepository
from app.domains.node.identity_store import node_identity_store
from app.domains.sync.repository import SyncRepository
from app.domains.sync.schemas import SyncReconcileResponse, SyncStatusResponse
from app.integrations.weave.academics import WeaveAcademicsGateway, weave_academics_gateway
from app.integrations.weave.schemas import (
    SYNC_SCHEMA_VERSION,
    WeaveAcademicBootstrap,
    WeaveAcademicLevelSnapshot,
    WeaveAcademicSessionSnapshot,
    WeaveAcademicTermSnapshot,
    WeaveAdminSnapshot,
    WeaveArmLabelSnapshot,
    WeaveAssessmentComponentSnapshot,
    WeaveAssessmentSchemeSnapshot,
    WeaveClassSnapshot,
    WeaveClassTermDepartmentSnapshot,
    WeaveCurriculumSnapshot,
    WeaveCurriculumSubjectSnapshot,
    WeaveDepartmentSnapshot,
    WeaveStudentEnrollmentSnapshot,
    WeaveSubjectOfferingSnapshot,
    WeaveSubjectSnapshot,
    WeaveSyncChange,
    WeaveTeacherAssignmentSnapshot,
    WeaveTeacherSnapshot,
)

logger = logging.getLogger(__name__)

SYNC_SCOPE = "academics"
DEFAULT_PAGE_SIZE = 500

ENTITY_SCHEMAS: dict[str, type[BaseModel]] = {
    "academic_session": WeaveAcademicSessionSnapshot,
    "academic_term": WeaveAcademicTermSnapshot,
    "academic_level": WeaveAcademicLevelSnapshot,
    "arm_label": WeaveArmLabelSnapshot,
    "department": WeaveDepartmentSnapshot,
    "class": WeaveClassSnapshot,
    "class_term_department": WeaveClassTermDepartmentSnapshot,
    "subject": WeaveSubjectSnapshot,
    "curriculum": WeaveCurriculumSnapshot,
    "curriculum_subject": WeaveCurriculumSubjectSnapshot,
    "subject_offering": WeaveSubjectOfferingSnapshot,
    "assessment_scheme": WeaveAssessmentSchemeSnapshot,
    "assessment_component": WeaveAssessmentComponentSnapshot,
    "admin": WeaveAdminSnapshot,
    "teacher": WeaveTeacherSnapshot,
    "teacher_assignment": WeaveTeacherAssignmentSnapshot,
    "student_enrollment": WeaveStudentEnrollmentSnapshot,
}

ENTITY_MODELS = {
    "academic_session": AcademicSession,
    "academic_term": AcademicTerm,
    "academic_level": AcademicLevel,
    "arm_label": ArmLabel,
    "department": Department,
    "class": AcademicClass,
    "class_term_department": ClassTermDepartment,
    "subject": AcademicSubject,
    "curriculum": Curriculum,
    "curriculum_subject": CurriculumSubject,
    "subject_offering": SubjectOffering,
    "assessment_scheme": AssessmentScheme,
    "assessment_component": AssessmentComponent,
    "admin": AcademicAdmin,
    "teacher": AcademicTeacher,
    "teacher_assignment": TeacherAssignment,
    "student_enrollment": StudentEnrollment,
}


class SyncContractViolation(RuntimeError):
    """Raised when a valid Weave response contradicts local identity/cursor state."""


class SyncDependencyMissing(SyncContractViolation):
    """Raised when a delta references a Weave projection not installed locally."""

    def __init__(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        dependency_type: str,
        missing_ids: Sequence[UUID],
    ) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.dependency_type = dependency_type
        self.missing_ids = tuple(missing_ids)
        super().__init__(
            f"{entity_type} {entity_id} references {len(self.missing_ids)} "
            f"{dependency_type} projection(s) missing locally; full bootstrap required."
        )


class SyncService:
    def __init__(self, gateway: WeaveAcademicsGateway = weave_academics_gateway) -> None:
        self.gateway = gateway

    @staticmethod
    def _values(snapshot: BaseModel) -> dict[str, Any]:
        return snapshot.model_dump(exclude={"id", "eligible_enrollment_ids"})

    @staticmethod
    async def _missing_enrollment_ids(
        db: AsyncSession,
        enrollment_ids: Sequence[UUID],
    ) -> tuple[UUID, ...]:
        unique_ids = tuple(dict.fromkeys(enrollment_ids))
        if not unique_ids:
            return ()
        installed_ids = set(
            (
                await db.execute(
                    select(StudentEnrollment.id).where(
                        StudentEnrollment.id.in_(unique_ids),
                        StudentEnrollment.source_deleted_at.is_(None),
                    )
                )
            ).scalars()
        )
        return tuple(
            enrollment_id
            for enrollment_id in unique_ids
            if enrollment_id not in installed_ids
        )

    async def _apply_snapshot_entity(
        self,
        db: AsyncSession,
        entity_type: str,
        snapshot: BaseModel,
        *,
        synced_at: datetime,
    ) -> None:
        model = ENTITY_MODELS[entity_type]
        entity_id = snapshot.id  # type: ignore[attr-defined]
        await AcademicRepository.upsert_projection(
            db,
            model,
            entity_id,
            self._values(snapshot),
            synced_at=synced_at,
        )
        if entity_type == "subject_offering":
            enrollment_ids = snapshot.eligible_enrollment_ids  # type: ignore[attr-defined]
            missing_ids = await self._missing_enrollment_ids(db, enrollment_ids)
            if missing_ids:
                raise SyncDependencyMissing(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    dependency_type="student_enrollment",
                    missing_ids=missing_ids,
                )
            await AcademicRepository.replace_offering_eligibility(
                db,
                offering_id=entity_id,
                enrollment_ids=enrollment_ids,
            )

    async def _apply_change(self, db: AsyncSession, change: WeaveSyncChange) -> None:
        if change.schema_version != SYNC_SCHEMA_VERSION:
            raise SyncContractViolation(
                f"Unsupported Weave sync schema version {change.schema_version}."
            )

        model = ENTITY_MODELS[change.entity_type]
        if change.operation == "deleted":
            await AcademicRepository.tombstone_projection(
                db,
                model,
                change.entity_id,
                deleted_at=change.occurred_at,
            )
            if change.entity_type == "subject_offering":
                await AcademicRepository.replace_offering_eligibility(
                    db,
                    offering_id=change.entity_id,
                    enrollment_ids=[],
                )
            return

        schema = ENTITY_SCHEMAS[change.entity_type]
        snapshot = schema.model_validate(change.payload)
        if snapshot.id != change.entity_id:  # type: ignore[attr-defined]
            raise SyncContractViolation(
                f"Sync entity id mismatch for {change.entity_type} at cursor {change.cursor}."
            )
        await self._apply_snapshot_entity(
            db,
            change.entity_type,
            snapshot,
            synced_at=change.occurred_at,
        )

    @staticmethod
    async def _status(db: AsyncSession) -> SyncStatusResponse:
        state = await SyncRepository.get_state(db, SYNC_SCOPE)
        if state is None:
            return SyncStatusResponse(
                scope=SYNC_SCOPE,
                schema_version=SYNC_SCHEMA_VERSION,
                cursor=0,
            )
        return SyncStatusResponse.model_validate(state, from_attributes=True)

    async def get_status(self, db: AsyncSession) -> SyncStatusResponse:
        return await self._status(db)

    async def bootstrap(
        self,
        db: AsyncSession,
        *,
        force: bool = False,
    ) -> SyncReconcileResponse:
        """Fetch and atomically install one complete current Weave snapshot.

        ``force`` permits reinstalling a snapshot at the same cursor when the
        incremental stream proves the local projection graph is incomplete.
        A snapshot older than a concurrently advanced local cursor is never
        installed.
        """
        identity = node_identity_store.load()

        # Never hold a local PostgreSQL transaction while waiting on Weave.
        payload = await self.gateway.fetch_bootstrap(
            server_credential=identity.server_credential,
        )
        self._validate_bootstrap_identity(payload, identity.tenant_id, identity.server_id)

        previous_state = await SyncRepository.get_state(db, SYNC_SCOPE)
        previous_cursor = previous_state.cursor if previous_state is not None else 0
        await db.rollback()

        applied_at = datetime.now(UTC)
        installed_snapshot = False
        try:
            async with db.begin():
                await SyncRepository.acquire_apply_lock(db)
                state = await SyncRepository.get_or_create_state(
                    db,
                    SYNC_SCOPE,
                    lock=True,
                )
                state.last_attempted_at = applied_at

                # Another process may have completed reconciliation/bootstrap
                # while this process downloaded its snapshot. Never replace a
                # newer local cursor with an older bootstrap.
                if state.cursor > payload.metadata.cursor:
                    state.last_error = None
                    await SyncRepository.save_state(db, state)
                elif (
                    not force
                    and state.bootstrap_completed_at is not None
                    and state.cursor >= payload.metadata.cursor
                ):
                    state.last_error = None
                    await SyncRepository.save_state(db, state)
                else:
                    await AcademicRepository.upsert_projection(
                        db,
                        SchoolProfile,
                        payload.school.id,
                        self._values(payload.school),
                        synced_at=payload.metadata.generated_at,
                    )
                    await AcademicRepository.mark_all_projection_rows_deleted(
                        db,
                        deleted_at=applied_at,
                    )

                    ordered_sections: tuple[tuple[str, list[BaseModel]], ...] = (
                        ("academic_session", list(payload.sessions)),
                        ("academic_term", list(payload.terms)),
                        ("academic_level", list(payload.levels)),
                        ("arm_label", list(payload.arm_labels)),
                        ("department", list(payload.departments)),
                        ("class", list(payload.classes)),
                        ("class_term_department", list(payload.class_term_departments)),
                        ("subject", list(payload.subjects)),
                        ("curriculum", list(payload.curricula)),
                        ("curriculum_subject", list(payload.curriculum_subjects)),
                        ("assessment_scheme", list(payload.assessment_schemes)),
                        ("assessment_component", list(payload.assessment_components)),
                        ("admin", list(payload.admins)),
                        ("teacher", list(payload.teachers)),
                        ("teacher_assignment", list(payload.teacher_assignments)),
                        ("student_enrollment", list(payload.student_enrollments)),
                        # Eligibility FKs reference synchronized enrollments.
                        ("subject_offering", list(payload.offerings)),
                    )
                    for entity_type, snapshots in ordered_sections:
                        for snapshot in snapshots:
                            await self._apply_snapshot_entity(
                                db,
                                entity_type,
                                snapshot,
                                synced_at=payload.metadata.generated_at,
                            )

                    state.schema_version = payload.metadata.schema_version
                    state.cursor = payload.metadata.cursor
                    state.bootstrap_snapshot_id = payload.metadata.snapshot_id
                    state.bootstrap_completed_at = applied_at
                    state.last_successful_at = applied_at
                    state.last_error = None
                    await SyncRepository.save_state(db, state)
                    installed_snapshot = True
        except Exception as exc:
            await self._record_failure(db, str(exc))
            raise

        status = await self._status(db)
        return SyncReconcileResponse(
            **status.model_dump(),
            previous_cursor=previous_cursor,
            changes_applied=0,
            bootstrapped=installed_snapshot,
        )

    async def reconcile(self, db: AsyncSession) -> SyncReconcileResponse:
        """Recover every durable Weave change after the local committed cursor."""
        identity = node_identity_store.load()
        state = await SyncRepository.get_state(db, SYNC_SCOPE)
        if state is None or state.bootstrap_completed_at is None:
            await db.rollback()
            return await self.bootstrap(db)

        previous_cursor = state.cursor
        cursor = state.cursor
        await db.rollback()
        changes_applied = 0

        try:
            while True:
                # Network recovery happens without a database transaction/lock.
                delta = await self.gateway.fetch_changes(
                    server_credential=identity.server_credential,
                    after_cursor=cursor,
                    limit=DEFAULT_PAGE_SIZE,
                )
                if delta.from_cursor != cursor:
                    raise SyncContractViolation(
                        f"Weave delta started at {delta.from_cursor}; local cursor is {cursor}."
                    )
                if delta.next_cursor < cursor:
                    raise SyncContractViolation("Weave synchronization cursor moved backwards.")

                attempted_at = datetime.now(UTC)
                cursor_was_advanced_elsewhere = False
                async with db.begin():
                    await SyncRepository.acquire_apply_lock(db)
                    locked_state = await SyncRepository.get_or_create_state(
                        db,
                        SYNC_SCOPE,
                        lock=True,
                    )

                    if locked_state.cursor < cursor:
                        raise SyncContractViolation(
                            "Local synchronization cursor moved backwards."
                        )
                    if locked_state.cursor != cursor:
                        # A concurrent manual/live reconciliation already
                        # committed progress. Exit this transaction and refetch
                        # from the newer durable cursor instead of returning 500.
                        cursor = locked_state.cursor
                        cursor_was_advanced_elsewhere = True
                    else:
                        locked_state.last_attempted_at = attempted_at
                        last_change_cursor = cursor
                        for change in delta.changes:
                            if change.cursor <= last_change_cursor:
                                raise SyncContractViolation(
                                    "Weave returned non-increasing synchronization changes."
                                )
                            await self._apply_change(db, change)
                            last_change_cursor = change.cursor
                            changes_applied += 1

                        if delta.changes and delta.next_cursor != last_change_cursor:
                            raise SyncContractViolation(
                                "Weave delta next_cursor does not match the last returned change."
                            )

                        locked_state.cursor = delta.next_cursor
                        locked_state.schema_version = SYNC_SCHEMA_VERSION
                        locked_state.last_successful_at = attempted_at
                        locked_state.last_error = None
                        await SyncRepository.save_state(db, locked_state)

                if cursor_was_advanced_elsewhere:
                    continue

                cursor = delta.next_cursor
                if not delta.has_more:
                    break
        except SyncDependencyMissing as exc:
            # The delta page is already rolled back by the transaction context.
            # Reinstall the authoritative current snapshot instead of repeatedly
            # retrying a cursor whose derived payload references missing parents.
            logger.warning(
                "Local CBT sync dependency gap detected; forcing full academic "
                "bootstrap recovery: %s",
                exc,
            )
            await db.rollback()
            return await self.bootstrap(db, force=True)
        except Exception as exc:
            await self._record_failure(db, str(exc))
            raise

        status = await self._status(db)
        return SyncReconcileResponse(
            **status.model_dump(),
            previous_cursor=previous_cursor,
            changes_applied=changes_applied,
            bootstrapped=False,
        )

    @staticmethod
    def _validate_bootstrap_identity(
        payload: WeaveAcademicBootstrap,
        tenant_id: UUID,
        server_id: UUID,
    ) -> None:
        if payload.school.id != tenant_id:
            raise SyncContractViolation("Weave bootstrap belongs to an unexpected tenant.")
        if payload.server.id != server_id:
            raise SyncContractViolation("Weave bootstrap belongs to an unexpected CBT server.")

    @staticmethod
    async def _record_failure(db: AsyncSession, message: str) -> None:
        await db.rollback()
        async with db.begin():
            await SyncRepository.acquire_apply_lock(db)
            state = await SyncRepository.get_or_create_state(
                db,
                SYNC_SCOPE,
                lock=True,
            )
            state.last_attempted_at = datetime.now(UTC)
            state.last_error = message[:1024]
            await SyncRepository.save_state(db, state)


sync_service = SyncService()
