from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AcademicAuthorizationError
from app.domains.academics.models import StudentEnrollment
from app.domains.academics.repository import AcademicRepository
from app.domains.auth.models import LocalActor
from app.domains.candidates.exceptions import CandidateRosterError
from app.domains.candidates.models import (
    CandidateLateStartAuthorization,
    CandidateStatus,
    ExamCandidate,
    CandidateMakeupAuthorization,
)

from app.domains.candidates.repository import CandidateRepository
from app.domains.candidates.schemas import (
    CandidateLateStartAuthorizationResponse,
    CandidateMakeupAuthorizationResponse,
    CandidateResponse,
    CandidateRosterResponse,
    MissedCandidateListResponse,
    MissedCandidateResponse,
)

from app.domains.exams.exceptions import ExamNotFound
from app.domains.exams.models import Exam, ExamRosterStatus, ExamStatus
from app.domains.exams.repository import ExamRepository
from app.domains.sync.repository import SyncRepository
from app.domains.attempts.repository import AttemptRepository


class CandidateService:
    @staticmethod
    def _require_admin(actor: LocalActor) -> None:
        if not actor.is_active:
            raise AcademicAuthorizationError("Active local actor is required")
        if actor.role != "admin":
            raise AcademicAuthorizationError("Administrator access is required")

    @staticmethod
    def _require_reason(reason: str, *, field_name: str = "reason") -> str:
        normalized = reason.strip()
        if not normalized:
            raise ValueError(f"{field_name} is required")
        return normalized

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _ensure_exam_mutable(exam_status: ExamStatus) -> None:
        if exam_status in {ExamStatus.CANCELLED, ExamStatus.CLOSED}:
            raise ValueError("Cancelled or closed examinations are read-only")

    @staticmethod
    async def _require_can_view_roster(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
    ) -> None:
        if not actor.is_active:
            raise AcademicAuthorizationError("Active local actor is required")

        if actor.role == "admin":
            return

        if actor.role != "teacher":
            raise AcademicAuthorizationError(
                "You are not allowed to view examination candidates"
            )

        if actor.weave_membership_id is None:
            raise AcademicAuthorizationError(
                "Teacher is missing a Weave membership identity"
            )

        try:
            teacher_id = UUID(actor.weave_membership_id)
        except ValueError as exc:
            raise AcademicAuthorizationError(
                "Teacher has an invalid Weave membership identity"
            ) from exc

        invigilator = await ExamRepository.get_invigilator(
            db,
            exam_id,
            teacher_id,
        )

        if invigilator is None:
            raise AcademicAuthorizationError(
                "Only assigned invigilators may view this examination roster"
            )

    @classmethod
    async def _get_candidate_and_exam(
        cls,
        db: AsyncSession,
        *,
        candidate_id: UUID,
        lock_candidate: bool = False,
        lock_exam: bool = False,
    ) -> tuple[ExamCandidate, Exam]:
        candidate = await CandidateRepository.get_candidate_by_id(
            db,
            candidate_id,
            lock=lock_candidate,
        )

        if candidate is None:
            raise ValueError("Candidate does not exist")

        exam = await ExamRepository.get_exam_by_id(
            db,
            exam_id=candidate.exam_id,
            lock=lock_exam,
        )

        if exam is None:
            raise ExamNotFound("Examination does not exist")

        return candidate, exam

    @classmethod
    async def list_roster(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
        status: CandidateStatus | None = None,
        class_id: UUID | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> CandidateRosterResponse:
        exam = await ExamRepository.get_exam_by_id(
            db,
            exam_id=exam_id,
        )

        if exam is None:
            raise ExamNotFound("Examination does not exist")

        await cls._require_can_view_roster(
            db,
            actor=actor,
            exam_id=exam.id,
        )

        if class_id is not None:
            target_class = await ExamRepository.get_target_class(
                db,
                exam.id,
                class_id,
            )

            if target_class is None:
                raise ValueError("Class is not part of this examination")

        candidates = await CandidateRepository.list_candidates_for_exam(
            db,
            exam.id,
            status=status,
            class_id=class_id,
            offset=offset,
            limit=limit,
        )

        total = await CandidateRepository.count_candidates_for_exam(
            db,
            exam_id=exam.id,
            status=status,
            class_id=class_id,
        )

        return CandidateRosterResponse(
            exam_id=exam.id,
            roster_status=exam.roster_status,
            roster_version=exam.roster_version,
            roster_candidate_count=exam.roster_candidate_count,
            offset=offset,
            limit=limit,
            total=total,
            candidates=[
                CandidateResponse.model_validate(candidate) for candidate in candidates
            ],
        )

    @classmethod
    async def get_candidate(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        candidate_id: UUID,
    ) -> CandidateResponse:
        candidate, exam = await cls._get_candidate_and_exam(
            db,
            candidate_id=candidate_id,
        )

        await cls._require_can_view_roster(
            db,
            actor=actor,
            exam_id=exam.id,
        )

        return CandidateResponse.model_validate(candidate)

    @classmethod
    async def block_candidate(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        candidate_id: UUID,
        reason: str,
    ) -> CandidateResponse:
        cls._require_admin(actor)
        normalized_reason = cls._require_reason(reason)

        candidate, exam = await cls._get_candidate_and_exam(
            db,
            candidate_id=candidate_id,
            lock_candidate=True,
            lock_exam=True,
        )
        cls._ensure_exam_mutable(exam.status)

        if candidate.status != CandidateStatus.ELIGIBLE:
            raise ValueError("Only eligible candidates can be blocked")

        try:
            candidate.status = CandidateStatus.BLOCKED
            candidate.status_reason = normalized_reason

            await CandidateRepository.save_candidate(db, candidate)
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError("Candidate could not be blocked") from exc

        return CandidateResponse.model_validate(candidate)

    @classmethod
    async def unblock_candidate(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        candidate_id: UUID,
    ) -> CandidateResponse:
        cls._require_admin(actor)

        candidate, exam = await cls._get_candidate_and_exam(
            db,
            candidate_id=candidate_id,
            lock_candidate=True,
            lock_exam=True,
        )
        cls._ensure_exam_mutable(exam.status)

        if candidate.status != CandidateStatus.BLOCKED:
            raise ValueError("Only blocked candidates can be unblocked")

        try:
            candidate.status = CandidateStatus.ELIGIBLE
            candidate.status_reason = None

            await CandidateRepository.save_candidate(db, candidate)
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError("Candidate could not be unblocked") from exc

        return CandidateResponse.model_validate(candidate)

    @classmethod
    async def grant_late_start(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        candidate_id: UUID,
        reason: str,
        expires_at: datetime | None = None,
    ) -> CandidateLateStartAuthorizationResponse:
        cls._require_admin(actor)
        normalized_reason = cls._require_reason(reason)
        now = datetime.now(UTC)
        normalized_expires_at = (
            cls._normalize_datetime(expires_at) if expires_at is not None else None
        )

        if normalized_expires_at is not None and normalized_expires_at < now:
            raise ValueError("Late-start authorization expiry cannot be in the past")

        candidate, exam = await cls._get_candidate_and_exam(
            db,
            candidate_id=candidate_id,
            lock_candidate=True,
            lock_exam=True,
        )

        if exam.status != ExamStatus.ACTIVE:
            raise ValueError("Late start can only be granted for an active examination")

        if candidate.status != CandidateStatus.ELIGIBLE:
            raise ValueError("Only eligible candidates can receive late start")

        authorization = CandidateLateStartAuthorization(
            candidate_id=candidate.id,
            granted_by_actor_id=actor.id,
            reason=normalized_reason,
            granted_at=now,
            expires_at=normalized_expires_at,
        )

        try:
            authorization = await CandidateRepository.add_late_start_authorization(
                db,
                authorization,
            )
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError("Late-start authorization could not be granted") from exc

        return CandidateLateStartAuthorizationResponse.model_validate(authorization)

    @classmethod
    async def revoke_late_start(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        authorization_id: UUID,
        reason: str,
    ) -> CandidateLateStartAuthorizationResponse:
        cls._require_admin(actor)
        normalized_reason = cls._require_reason(reason)

        authorization = await CandidateRepository.get_late_start_authorization_by_id(
            db,
            authorization_id,
            lock=True,
        )

        if authorization is None:
            raise ValueError("Late-start authorization does not exist")

        _candidate, exam = await cls._get_candidate_and_exam(
            db,
            candidate_id=authorization.candidate_id,
            lock_candidate=True,
            lock_exam=True,
        )
        cls._ensure_exam_mutable(exam.status)

        if authorization.consumed_at is not None:
            raise ValueError("Consumed late-start authorization cannot be revoked")

        if authorization.revoked_at is not None:
            raise ValueError("Late-start authorization has already been revoked")

        try:
            authorization.revoked_at = datetime.now(UTC)
            authorization.revoked_by_actor_id = actor.id
            authorization.revocation_reason = normalized_reason

            await CandidateRepository.save_late_start_authorization(db, authorization)
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError("Late-start authorization could not be revoked") from exc

        return CandidateLateStartAuthorizationResponse.model_validate(authorization)

    @classmethod
    async def list_late_start_authorizations(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        candidate_id: UUID,
    ) -> list[CandidateLateStartAuthorizationResponse]:
        candidate, exam = await cls._get_candidate_and_exam(
            db,
            candidate_id=candidate_id,
        )

        await cls._require_can_view_roster(
            db,
            actor=actor,
            exam_id=exam.id,
        )

        authorizations = await CandidateRepository.list_late_start_authorizations(
            db,
            candidate.id,
        )

        return [
            CandidateLateStartAuthorizationResponse.model_validate(authorization)
            for authorization in authorizations
        ]

    @staticmethod
    def _display_name(enrollment: StudentEnrollment) -> str:
        """Build the candidate name stored in the frozen roster snapshot"""

        parts = [
            enrollment.first_name.strip() if enrollment.first_name else "",
            enrollment.last_name.strip() if enrollment.last_name else "",
        ]

        display_name = " ".join(part for part in parts if part)

        return display_name or enrollment.admission_number

    @classmethod
    async def prepare_roster(cls, db: AsyncSession, *, exam_id: UUID):
        """
        Materialize the initial candidate roster for one sealed exam
        The frozen ExamTargetClass rows define the classes that may
        participate. Synchronized StudentEnrollment rows determine the
        individual students currently eligible inside those classes

        This method is intended to be called by a background worker
        """

        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id, lock=True)

        if exam is None:
            raise ExamNotFound("Examination does not exist")

        if exam.status != ExamStatus.SEALED:
            raise CandidateRosterError(
                "Candidate roster can only be prepared for a SEALED examination"
            )
        if exam.roster_status not in {
            ExamRosterStatus.PENDING,
            ExamRosterStatus.FAILED,
        }:
            raise CandidateRosterError(
                "Candidate roster cannot be prepared in its current state"
            )

        await SyncRepository.acquire_apply_lock(db)

        target_classes = await ExamRepository.list_target_classes_for_exam(db, exam.id)

        if not target_classes:
            raise CandidateRosterError("Examination has no target classes")

        next_roster_version = exam.roster_version + 1

        enrollments_by_student: dict[UUID, StudentEnrollment] = {}

        for target in target_classes:
            if target.subject_offering_id is None:
                raise CandidateRosterError(
                    "Examination target class is missing its subject offering"
                )

            enrollments = (
                await AcademicRepository.list_eligible_enrollments_for_offering(
                    db, target.subject_offering_id, class_id=target.class_id
                )
            )

            for enrollment in enrollments:
                if enrollment.class_id is None:
                    continue

                enrollments_by_student[enrollment.student_id] = enrollment

        if not enrollments_by_student:
            raise CandidateRosterError(
                "No eligible students were found for this examination"
            )

        candidates = [
            ExamCandidate(
                exam_id=exam.id,
                enrollment_id=enrollment.id,
                student_id=enrollment.student_id,
                class_id=cast(UUID, enrollment.class_id),
                admission_number=enrollment.admission_number,
                display_name=cls._display_name(enrollment),
                status=CandidateStatus.ELIGIBLE,
                status_reason=None,
                roster_version=next_roster_version,
            )
            for enrollment in enrollments_by_student.values()
        ]

        prepared_at = datetime.now(UTC)

        try:
            exam.roster_status = ExamRosterStatus.BUILDING
            exam.roster_error = None

            await ExamRepository.save_exam(db, exam)

            await CandidateRepository.add_candidates(
                db,
                candidates,
            )

            exam.roster_version = next_roster_version
            exam.roster_candidate_count = len(candidates)
            exam.roster_prepared_at = prepared_at
            exam.roster_status = ExamRosterStatus.READY
            exam.roster_error = None

            await ExamRepository.save_exam(db, exam)

            await db.commit()

        except IntegrityError as exc:
            await db.rollback()

            raise CandidateRosterError(
                "Candidate roster could not be prepared because it "
                "conflicts with existing examination data"
            ) from exc

        return exam

    @classmethod
    async def reconcile_roster(
        cls,
        db: AsyncSession,
        *,
        exam_id: UUID,
    ):
        """
        Refresh an existing candidate roster against the latest synchronized
        academic eligibility

        Existing eligible candidates are retained
        Newly eligible students are added
        Students who are no longer eligible are marker WITHDRAWN
        BLOCKED canaidates remain blocked until they are eligible
        """
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id, lock=True)

        if exam is None:
            raise ExamNotFound("Examination does not exist")

        if exam.status != ExamStatus.SEALED:
            raise CandidateRosterError(
                "Candidate roster can only be reconciled for a SEALED examination"
            )

        if exam.roster_status not in {ExamRosterStatus.STALE, ExamRosterStatus.FAILED}:
            raise CandidateRosterError(
                "Candidate roster does not require reconciliation"
            )

        await SyncRepository.acquire_apply_lock(db)

        target_classes = await ExamRepository.list_target_classes_for_exam(db, exam.id)

        if not target_classes:
            raise CandidateRosterError("Examination has no target classes")

        next_roster_version = exam.roster_version + 1

        eligible_enrollments: dict[UUID, StudentEnrollment] = {}

        for target in target_classes:
            if target.subject_offering_id is None:
                raise CandidateRosterError(
                    "Examination target class is missing its subject offering"
                )

            enrollments = (
                await AcademicRepository.list_eligible_enrollments_for_offering(
                    db,
                    offering_id=target.subject_offering_id,
                    class_id=target.class_id,
                )
            )
            for enrollment in enrollments:
                if enrollment.class_id is None:
                    continue

                eligible_enrollments[enrollment.student_id] = enrollment

        existing_candidates = await CandidateRepository.list_candidates_for_exam(
            db,
            exam.id,
            lock=True,
        )

        existing_by_student = {
            candidate.student_id: candidate for candidate in existing_candidates
        }

        new_candidates: list[ExamCandidate] = []
        changed_candidates: list[ExamCandidate] = []

        for enrollment in eligible_enrollments.values():
            existing = existing_by_student.get(enrollment.student_id)

            if existing is None:
                new_candidates.append(
                    ExamCandidate(
                        exam_id=exam.id,
                        enrollment_id=enrollment.id,
                        student_id=enrollment.student_id,
                        class_id=cast(UUID, enrollment.class_id),
                        admission_number=enrollment.admission_number,
                        display_name=cls._display_name(enrollment),
                        status=CandidateStatus.ELIGIBLE,
                        status_reason=None,
                        roster_version=next_roster_version,
                    )
                )
                continue

            existing.enrollment_id = enrollment.id
            existing.class_id = cast(UUID, enrollment.class_id)
            existing.admission_number = enrollment.admission_number
            existing.display_name = cls._display_name(enrollment)
            existing.roster_version = next_roster_version

            if existing.status != CandidateStatus.BLOCKED:
                existing.status = CandidateStatus.ELIGIBLE
                existing.status_reason = None

            changed_candidates.append(existing)

        for candidate in existing_candidates:
            if candidate.student_id in eligible_enrollments:
                continue

            candidate.status = CandidateStatus.WITHDRAWN
            candidate.status_reason = (
                "Student is no longer academically eligible for this examination"
            )
            candidate.roster_version = next_roster_version
            changed_candidates.append(candidate)

        prepared_at = datetime.now(UTC)

        try:
            exam.roster_status = ExamRosterStatus.BUILDING
            exam.roster_error = None

            await ExamRepository.save_exam(db, exam)

            if new_candidates:
                await CandidateRepository.add_candidates(
                    db,
                    new_candidates,
                )

            if changed_candidates:
                await CandidateRepository.save_candidates(
                    db,
                    changed_candidates,
                )

            current_candidate_count = len(eligible_enrollments)

            exam.roster_version = next_roster_version
            exam.roster_candidate_count = current_candidate_count
            exam.roster_prepared_at = prepared_at
            exam.roster_status = ExamRosterStatus.READY
            exam.roster_error = None

            await ExamRepository.save_exam(db, exam)

            await db.commit()

        except IntegrityError as exc:
            await db.rollback()

            raise CandidateRosterError(
                "Candidate roster could not be reconciled because it "
                "conflicts with existing examination data"
            ) from exc

        return exam

    @classmethod
    async def list_missed_candidates(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> MissedCandidateListResponse:
        """
        Return candidates who were on the original roster but never started
        the examination

        A candidate becomes definitely "misses" only after the original
        examination is CLOSED


        CANCELLED examinations do not produce missed candidates because the
        sitting itself was invalidated
        """

        cls._require_admin(actor)

        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id)

        if exam is None:
            raise ExamNotFound("Examination does not exist")

        if exam.status != ExamStatus.CLOSED:
            raise ValueError(
                "Missed candidates can only be determined after "
                "the examination is closed"
            )

        candidates = await CandidateRepository.list_missed_candidates_for_exam(
            db, exam.id, offset=offset, limit=limit
        )

        total = await CandidateRepository.count_missed_candidates_for_exam(db, exam.id)

        active_authorizations = (
            await CandidateRepository.list_active_makeup_authorizations_for_candidates(
                db, [candidate.id for candidate in candidates]
            )
        )

        authorization_by_candidate = {
            authorization.candidate_id: authorization
            for authorization in active_authorizations
        }

        return MissedCandidateListResponse(
            exam_id=exam.id,
            exam_title=exam.title,
            scheduled_start_at=exam.scheduled_start_at,
            offset=offset,
            limit=limit,
            total=total,
            candidates=[
                MissedCandidateResponse(
                    candidate=CandidateResponse.model_validate(candidate),
                    makeup_authorization=(
                        CandidateMakeupAuthorizationResponse.model_validate(
                            authorization_by_candidate[candidate.id]
                        )
                        if candidate.id in authorization_by_candidate
                        else None
                    ),
                )
                for candidate in candidates
            ],
        )

    @classmethod
    async def approve_makeup(
        cls, db: AsyncSession, *, actor: LocalActor, candidate_id: UUID, reason: str
    ) -> CandidateMakeupAuthorizationResponse:
        """
        Approve one exact missed candidate/exam pair for a future makeup

        Approval does not create an attempt and does not make the makeup
        immediately executable. Makeup-period eligibility is a later phase
        """

        cls._require_admin(actor)

        normalized_reason = cls._require_reason(reason)
        now = datetime.now(UTC)

        candidate, exam = await cls._get_candidate_and_exam(
            db, candidate_id=candidate_id, lock_candidate=True, lock_exam=True
        )

        if exam.status != ExamStatus.CLOSED:
            raise ValueError(
                "Makeup can only be approved after the original examination is closed"
            )

        if candidate.status != CandidateStatus.ELIGIBLE:
            raise ValueError(
                "Only eligible candidates who missed the examination "
                "can receive makeup approval"
            )

        attempt = await AttemptRepository.get_attempt_by_candidate_id(
            db, candidate_id=candidate_id, lock=True
        )

        if attempt is not None:
            raise ValueError(
                "Candidate cannot receive makeup approval because "
                "an examination attempt was already recorded for candidate"
            )

        existing = await CandidateRepository.get_active_makeup_authorization(
            db, candidate.id, lock=True
        )

        if existing is not None:
            raise ValueError("Candidate already has an active makeup authorization")

        authorization = CandidateMakeupAuthorization(
            candidate_id=candidate.id,
            approved_by_actor_id=actor.id,
            reason=normalized_reason,
            approved_at=now,
        )

        try:
            authorization = await CandidateRepository.add_makeup_authorization(
                db, authorization
            )

            await db.commit()

        except IntegrityError as exc:
            await db.rollback()

            raise ValueError("Makeup authorization could not be created") from exc

        return CandidateMakeupAuthorizationResponse.model_validate(authorization)

    @classmethod
    async def revoke_makeup(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        authorization_id: UUID,
        reason: str,
    ) -> CandidateMakeupAuthorizationResponse:
        cls._require_admin(actor)

        normalized_reason = cls._require_reason(reason)
        now = datetime.now(UTC)

        authorization = await CandidateRepository.get_makeup_authorization_by_id(
            db,
            authorization_id,
            lock=True,
        )

        if authorization is None:
            raise ValueError("Makeup authorization does not exist")

        if authorization.consumed_at is not None:
            raise ValueError("Consumed makeup authorization cannot be revoked")

        if authorization.revoked_at is not None:
            raise ValueError("Makeup authorization has already been revoked")

        # Lock candidate as well so future makeup-attempt creation and
        # revocation cannot race each other.
        _candidate, _exam = await cls._get_candidate_and_exam(
            db,
            candidate_id=authorization.candidate_id,
            lock_candidate=True,
            lock_exam=False,
        )

        try:
            authorization.revoked_at = now
            authorization.revoked_by_actor_id = actor.id
            authorization.revocation_reason = normalized_reason

            authorization = await CandidateRepository.save_makeup_authorization(
                db,
                authorization,
            )

            await db.commit()

        except IntegrityError as exc:
            await db.rollback()

            raise ValueError("Makeup authorization could not be revoked") from exc

        return CandidateMakeupAuthorizationResponse.model_validate(authorization)

    @classmethod
    async def list_makeup_authorizations(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        candidate_id: UUID,
    ) -> list[CandidateMakeupAuthorizationResponse]:
        cls._require_admin(actor)

        candidate, _exam = await cls._get_candidate_and_exam(
            db,
            candidate_id=candidate_id,
        )

        authorizations = await CandidateRepository.list_makeup_authorizations(
            db,
            candidate.id,
        )

        return [
            CandidateMakeupAuthorizationResponse.model_validate(authorization)
            for authorization in authorizations
        ]
