"""Lifecycle-aware candidate service facade."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academics.repository import AcademicRepository
from app.domains.auth.models import LocalActor
from app.domains.candidates.exceptions import CandidateRosterError
from app.domains.candidates.models import CandidateStatus
from app.domains.candidates.query_repository import CandidateRosterQueryRepository
from app.domains.candidates.schemas import (
    CandidateResponse,
    CandidateRosterClassResponse,
    CandidateRosterResponse,
)
from app.domains.candidates.service import CandidateService as _CandidateService
from app.domains.exams.exceptions import ExamNotFound
from app.domains.exams.models import Exam, ExamRosterStatus, ExamStatus
from app.domains.exams.repository import ExamRepository


class CandidateService(_CandidateService):
    """Candidate facade with lifecycle guards and admin roster read models."""

    @staticmethod
    def _ensure_exam_mutable(exam_status: ExamStatus) -> None:
        if exam_status in {
            ExamStatus.CLOSING,
            ExamStatus.CANCELLING,
            ExamStatus.CLOSED,
            ExamStatus.CANCELLED,
        }:
            raise ValueError(
                "Closing, cancelling, closed, or cancelled examinations are read-only"
            )

    @classmethod
    async def list_roster(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
        status: CandidateStatus | None = None,
        class_id: UUID | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> CandidateRosterResponse:
        """Return a filterable roster read model without changing roster state."""

        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id)
        if exam is None:
            raise ExamNotFound("Examination does not exist")

        await cls._require_can_view_roster(
            db,
            actor=actor,
            exam_id=exam.id,
        )

        target_classes = await ExamRepository.list_target_classes_for_exam(db, exam.id)
        target_class_ids = {target.class_id for target in target_classes}
        if class_id is not None and class_id not in target_class_ids:
            raise ValueError("Class is not part of this examination")

        candidates = await CandidateRosterQueryRepository.list_candidates(
            db,
            exam_id=exam.id,
            status=status,
            class_id=class_id,
            search=search,
            offset=offset,
            limit=limit,
        )
        total = await CandidateRosterQueryRepository.count_candidates(
            db,
            exam_id=exam.id,
            status=status,
            class_id=class_id,
            search=search,
        )

        class_rows = []
        for target_class_id in target_class_ids:
            classroom = await AcademicRepository.get_class_by_id(
                db,
                class_id=target_class_id,
            )
            if classroom is not None:
                class_rows.append(classroom)
        class_rows.sort(
            key=lambda classroom: (classroom.display_name.casefold(), str(classroom.id))
        )
        class_name_by_id = {
            classroom.id: classroom.display_name for classroom in class_rows
        }

        candidate_rows = [
            CandidateResponse.model_validate(candidate).model_copy(
                update={"class_name": class_name_by_id.get(candidate.class_id)}
            )
            for candidate in candidates
        ]

        return CandidateRosterResponse(
            exam_id=exam.id,
            roster_status=exam.roster_status,
            roster_version=exam.roster_version,
            roster_candidate_count=exam.roster_candidate_count,
            offset=offset,
            limit=limit,
            total=total,
            classes=[
                CandidateRosterClassResponse(
                    id=classroom.id,
                    display_name=classroom.display_name,
                )
                for classroom in class_rows
            ],
            candidates=candidate_rows,
        )

    @classmethod
    async def retry_failed_roster(
        cls,
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
    ) -> tuple[Exam, str]:
        """Return a failed sealed roster to a durable recoverable state.

        PostgreSQL owns the recovery request. Queue delivery is deliberately
        handled by the router after this transaction commits so Redis failure
        cannot lose the operator's retry request; maintenance can reconstruct
        PENDING/STale work later from the database.
        """

        cls._require_admin(actor)

        exam = await ExamRepository.get_exam_by_id(
            db,
            exam_id=exam_id,
            lock=True,
        )
        if exam is None:
            raise ExamNotFound("Examination does not exist")

        if exam.status != ExamStatus.SEALED:
            raise CandidateRosterError(
                "Failed roster recovery is only available for a SEALED examination"
            )

        if exam.roster_status != ExamRosterStatus.FAILED:
            raise CandidateRosterError(
                "Roster recovery can only be retried from FAILED state"
            )

        initial_preparation = exam.roster_version == 0
        recovery_mode = "prepare" if initial_preparation else "reconcile"
        exam.roster_status = (
            ExamRosterStatus.PENDING
            if initial_preparation
            else ExamRosterStatus.STALE
        )
        exam.roster_error = None

        await ExamRepository.save_exam(db, exam)
        await db.commit()
        return exam, recovery_mode
