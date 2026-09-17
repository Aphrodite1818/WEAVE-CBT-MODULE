"""Durable synchronization of locally calculated CBT results to Weave Cloud."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academics.repository import AcademicRepository
from app.domains.candidates.repository import CandidateRepository
from app.domains.exams.exceptions import ExamNotFound
from app.domains.exams.models import Exam, ExamStatus
from app.domains.exams.repository import ExamRepository
from app.domains.node.identity_store import (
    NodeIdentityStore,
    node_identity_store,
)
from app.domains.results.models import (
    RESULT_SYNC_ERROR_MAX_LENGTH,
    ExamResult,
    ResultSyncStatus,
)
from app.domains.results.repository import ResultRepository
from app.integrations.weave.exceptions import (
    WeaveContractError,
    WeaveIntegrationError,
)
from app.integrations.weave.results import (
    WeaveResultGateway,
    weave_result_gateway,
)
from app.integrations.weave.schemas import (
    WeaveResultBulkRequest,
    WeaveResultBulkResponse,
    WeaveResultScore,
)


MAX_RESULT_SYNC_BATCH_SIZE = 1000


class ResultSyncError(RuntimeError):
    """Raised when local result synchronization state is invalid."""


@dataclass(frozen=True, slots=True)
class _PreparedResultBatch:
    """Local representation of one exact durable Weave result batch."""

    payload: WeaveResultBulkRequest

    # Maps local ExamResult.id -> Weave student_id.
    #
    # We need this when Weave returns per-student rejections so the response
    # can be mapped back onto the correct local result rows.
    student_id_by_result_id: dict[UUID, UUID]


class ResultSyncService:
    """
    Synchronize locally calculated component scores to Weave Cloud.

    PostgreSQL is the source of truth for synchronization state.

    A batch is persisted before network I/O. This means that if the process
    crashes after Weave accepts the request but before CBT receives the
    response, the exact same batch can be reconstructed and retried.
    """

    def __init__(
        self,
        *,
        gateway: WeaveResultGateway = weave_result_gateway,
        identity_store: NodeIdentityStore = node_identity_store,
    ) -> None:
        self.gateway = gateway
        self.identity_store = identity_store

    async def sync_next_batch(
        self,
        db: AsyncSession,
        *,
        exam_id: UUID,
        limit: int = MAX_RESULT_SYNC_BATCH_SIZE,
    ) -> WeaveResultBulkResponse | None:
        """
        Synchronize at most one result batch for an examination.

        Returns None when there is currently no result work to synchronize.
        """

        if limit < 1 or limit > MAX_RESULT_SYNC_BATCH_SIZE:
            raise ValueError(
                f"Result sync batch limit must be between 1 and "
                f"{MAX_RESULT_SYNC_BATCH_SIZE}."
            )

        # Load the machine credential BEFORE claiming database work.
        #
        # If this installation is not paired, or its identity is corrupt,
        # no result rows should be moved into SYNCING.
        identity = await asyncio.to_thread(
            self.identity_store.load,
        )

        batch_id = await self._claim_or_resume_batch(
            db,
            exam_id=exam_id,
            limit=limit,
        )

        if batch_id is None:
            return None

        try:
            prepared = await self._prepare_batch(
                db,
                batch_id=batch_id,
            )

            # SQLAlchemy opens an implicit transaction while _prepare_batch
            # performs reads.
            #
            # End that transaction before contacting Weave. We must never keep
            # database locks/transactions open while waiting for the internet.
            await db.rollback()

            response = await self.gateway.submit_results(
                payload=prepared.payload,
                server_credential=identity.server_credential,
            )

            self._validate_response(
                prepared=prepared,
                response=response,
            )

        except WeaveIntegrationError as exc:
            await db.rollback()

            # Preserve the batch identity.
            #
            # We may not know whether Weave processed the request before the
            # connection failed, so any retry must use the exact same batch_id
            # and payload.
            await self._mark_batch_failed(
                db,
                batch_id=batch_id,
                error_message=self._integration_error_message(exc),
                preserve_batch=True,
            )

            raise

        except Exception:
            await db.rollback()

            await self._mark_batch_failed(
                db,
                batch_id=batch_id,
                error_message="Unexpected result synchronization failure.",
                preserve_batch=True,
            )

            raise

        await self._finalize_batch(
            db,
            prepared=prepared,
            response=response,
        )

        return response

    async def _claim_or_resume_batch(
        self,
        db: AsyncSession,
        *,
        exam_id: UUID,
        limit: int,
    ) -> UUID | None:
        """
        Claim new work or resume an uncertain previous batch.

        Existing FAILED rows which still carry sync_batch_id must be retried
        before creating another batch for those rows.
        """

        exam = await ExamRepository.get_exam_by_id(
            db,
            exam_id=exam_id,
            lock=True,
        )

        if exam is None:
            await db.rollback()
            raise ExamNotFound("Examination does not exist")

        # Result publication to Weave occurs after local execution has reached
        # its final state.
        if exam.status != ExamStatus.CLOSED:
            await db.rollback()
            return None

        # --------------------------------------------------------------
        # 1. Resume uncertain previous delivery first
        # --------------------------------------------------------------

        retry_batch_id = (
            await ResultRepository.get_retryable_sync_batch_id_for_exam(
                db,
                exam_id=exam.id,
            )
        )

        if retry_batch_id is not None:
            rows = await ResultRepository.list_results_for_sync_batch(
                db,
                retry_batch_id,
                lock=True,
            )

            if not rows:
                await db.rollback()

                raise ResultSyncError(
                    "A retryable result batch exists without result rows."
                )

            if any(row.exam_id != exam.id for row in rows):
                await db.rollback()

                raise ResultSyncError(
                    "A result sync batch cannot contain multiple examinations."
                )

            await self._mark_rows_syncing(
                db,
                rows=rows,
                batch_id=retry_batch_id,
            )

            await db.commit()

            return retry_batch_id

        # --------------------------------------------------------------
        # 2. Claim fresh PENDING rows
        # --------------------------------------------------------------

        rows = await ResultRepository.list_pending_results_for_exam_sync(
            db,
            exam_id=exam.id,
            limit=limit,
            lock=True,
        )

        if not rows:
            await db.rollback()
            return None

        batch_id = uuid4()

        await self._mark_rows_syncing(
            db,
            rows=rows,
            batch_id=batch_id,
        )

        # IMPORTANT:
        #
        # This commit happens BEFORE network I/O.
        #
        # PostgreSQL now permanently knows exactly which rows belong to this
        # batch even if the machine loses power immediately afterwards.
        await db.commit()

        return batch_id

    @staticmethod
    async def _mark_rows_syncing(
        db: AsyncSession,
        *,
        rows: list[ExamResult],
        batch_id: UUID,
    ) -> None:
        attempted_at = datetime.now(UTC)

        for row in rows:
            row.sync_status = ResultSyncStatus.SYNCING
            row.sync_batch_id = batch_id
            row.sync_attempts += 1
            row.last_sync_attempt_at = attempted_at

            row.sync_error = None
            row.synced_at = None

        await ResultRepository.save_results(
            db,
            rows,
        )

    async def _prepare_batch(
        self,
        db: AsyncSession,
        *,
        batch_id: UUID,
    ) -> _PreparedResultBatch:
        """
        Reconstruct the exact Weave request from PostgreSQL.

        Nothing needed to construct the request comes from Redis.
        """

        rows = await ResultRepository.list_results_for_sync_batch(
            db,
            batch_id,
        )

        if not rows:
            raise ResultSyncError(
                "Result synchronization batch does not exist."
            )

        exam_id = rows[0].exam_id

        if any(row.exam_id != exam_id for row in rows):
            raise ResultSyncError(
                "A result synchronization batch contains multiple examinations."
            )

        if any(
            row.sync_status != ResultSyncStatus.SYNCING
            for row in rows
        ):
            raise ResultSyncError(
                "Every result in an active synchronization batch must be SYNCING."
            )

        # --------------------------------------------------------------
        # Exam
        # --------------------------------------------------------------

        exam = await ExamRepository.get_exam_by_id(
            db,
            exam_id=exam_id,
        )

        if exam is None:
            raise ExamNotFound(
                "Examination does not exist"
            )

        # --------------------------------------------------------------
        # Academic level
        # --------------------------------------------------------------
        #
        # Weave requires academic_level_id.
        #
        # Exam stores curriculum_subject_id, so resolve:
        #
        # curriculum subject
        #     -> curriculum
        #     -> academic level
        # --------------------------------------------------------------

        curriculum_subject = (
            await AcademicRepository.get_curriculum_subject_by_id(
                db,
                exam.curriculum_subject_id,
            )
        )

        if curriculum_subject is None:
            raise ResultSyncError(
                "The examination curriculum subject is unavailable locally."
            )

        curriculum = await AcademicRepository.get_curriculum_by_id(
            db,
            curriculum_subject.curriculum_id,
        )

        if curriculum is None:
            raise ResultSyncError(
                "The examination curriculum is unavailable locally."
            )

        # --------------------------------------------------------------
        # Candidate -> canonical Weave student
        # --------------------------------------------------------------

        candidate_ids = [
            row.candidate_id
            for row in rows
        ]

        candidates = await CandidateRepository.list_candidates_by_ids(
            db,
            candidate_ids,
        )

        candidate_by_id = {
            candidate.id: candidate
            for candidate in candidates
        }

        if len(candidate_by_id) != len(set(candidate_ids)):
            raise ResultSyncError(
                "One or more result candidates are unavailable locally."
            )

        student_id_by_result_id: dict[UUID, UUID] = {}
        scores: list[WeaveResultScore] = []

        for row in rows:
            candidate = candidate_by_id[row.candidate_id]

            if candidate.exam_id != exam.id:
                raise ResultSyncError(
                    "A result candidate does not belong to its examination."
                )

            student_id_by_result_id[row.id] = candidate.student_id

            scores.append(
                WeaveResultScore(
                    student_id=candidate.student_id,
                    score=row.component_score,
                )
            )

        # --------------------------------------------------------------
        # Final Weave contract
        # --------------------------------------------------------------

        payload = WeaveResultBulkRequest(
            batch_id=batch_id,
            source_exam_id=exam.id,
            academic_session_id=exam.session_id,
            academic_term_id=exam.term_id,
            academic_level_id=curriculum.academic_level_id,
            curriculum_subject_id=exam.curriculum_subject_id,
            assessment_component_id=exam.assessment_component_id,
            exam_date=self._exam_date(exam),
            scores=scores,
        )

        return _PreparedResultBatch(
            payload=payload,
            student_id_by_result_id=student_id_by_result_id,
        )

    @staticmethod
    def _exam_date(
        exam: Exam,
    ) -> date:
        """
        Resolve the stable examination date sent to Weave.

        Prefer the actual activation time. Scheduled start is the fallback for
        legacy/imported examination state.
        """

        timestamp = (
            exam.activated_at
            or exam.scheduled_start_at
            or exam.closed_at
        )

        if timestamp is None:
            raise ResultSyncError(
                "The examination has no usable execution date for result sync."
            )

        return timestamp.date()

    @staticmethod
    def _validate_response(
        *,
        prepared: _PreparedResultBatch,
        response: WeaveResultBulkResponse,
    ) -> None:
        """
        Ensure Weave acknowledged the same logical batch CBT submitted.
        """

        payload = prepared.payload

        if response.batch_id != payload.batch_id:
            raise WeaveContractError(
                "Weave acknowledged a different CBT result batch."
            )

        if response.source_exam_id != payload.source_exam_id:
            raise WeaveContractError(
                "Weave acknowledged a different CBT examination."
            )

        if response.received != len(payload.scores):
            raise WeaveContractError(
                "Weave acknowledged an unexpected number of CBT results."
            )

        submitted_student_ids = {
            item.student_id
            for item in payload.scores
        }

        rejected_student_ids = [
            error.student_id
            for error in response.errors
        ]

        if len(rejected_student_ids) != len(
            set(rejected_student_ids)
        ):
            raise WeaveContractError(
                "Weave returned duplicate rejected student results."
            )

        if not set(rejected_student_ids).issubset(
            submitted_student_ids
        ):
            raise WeaveContractError(
                "Weave rejected a student that was not present in the CBT batch."
            )

    async def _finalize_batch(
        self,
        db: AsyncSession,
        *,
        prepared: _PreparedResultBatch,
        response: WeaveResultBulkResponse,
    ) -> None:
        """
        Apply Weave's acknowledgement to the durable local result rows.
        """

        batch_id = prepared.payload.batch_id

        rows = await ResultRepository.list_results_for_sync_batch(
            db,
            batch_id,
            lock=True,
        )

        expected_result_ids = set(
            prepared.student_id_by_result_id
        )

        actual_result_ids = {
            row.id
            for row in rows
        }

        if actual_result_ids != expected_result_ids:
            await db.rollback()

            raise ResultSyncError(
                "Result batch membership changed during synchronization."
            )

        error_by_student_id = {
            error.student_id: error
            for error in response.errors
        }

        for row in rows:
            student_id = prepared.student_id_by_result_id[row.id]

            error = error_by_student_id.get(
                student_id
            )

            # ----------------------------------------------------------
            # Accepted by Weave
            # ----------------------------------------------------------

            if error is None:
                row.sync_status = ResultSyncStatus.SYNCED
                row.synced_at = response.processed_at
                row.sync_error = None

                # Deliberately preserve sync_batch_id as historical evidence
                # of exactly which Weave ingestion batch accepted this result.
                continue

            # ----------------------------------------------------------
            # Explicit per-student rejection
            # ----------------------------------------------------------
            #
            # We know Weave processed the batch and explicitly rejected this
            # score.
            #
            # Therefore we detach this result from the completed batch.
            #
            # If the underlying problem is later fixed, a future deliberate
            # retry must place it into a NEW batch. Reusing the old batch ID
            # with different contents would violate Weave's idempotency
            # contract.
            # ----------------------------------------------------------

            row.sync_status = ResultSyncStatus.FAILED
            row.sync_batch_id = None
            row.synced_at = None
            row.sync_error = self._bounded_error(
                f"{error.code}: {error.detail}"
            )

        await ResultRepository.save_results(
            db,
            rows,
        )

        await db.commit()

    async def _mark_batch_failed(
        self,
        db: AsyncSession,
        *,
        batch_id: UUID,
        error_message: str,
        preserve_batch: bool,
    ) -> None:
        """
        Persist synchronization failure for one durable batch.
        """

        rows = await ResultRepository.list_results_for_sync_batch(
            db,
            batch_id,
            lock=True,
        )

        if not rows:
            await db.rollback()
            return

        bounded_error = self._bounded_error(
            error_message
        )

        for row in rows:
            # Never regress confirmed success.
            if row.sync_status == ResultSyncStatus.SYNCED:
                continue

            row.sync_status = ResultSyncStatus.FAILED
            row.sync_error = bounded_error
            row.synced_at = None

            if not preserve_batch:
                row.sync_batch_id = None

        await ResultRepository.save_results(
            db,
            rows,
        )

        await db.commit()

    @staticmethod
    def _integration_error_message(
        exc: WeaveIntegrationError,
    ) -> str:
        return (
            str(exc)
            or "Weave result synchronization failed."
        )

    @staticmethod
    def _bounded_error(
        message: str,
    ) -> str:
        normalized = " ".join(
            message.split()
        )

        if not normalized:
            normalized = "Result synchronization failed."

        return normalized[
            :RESULT_SYNC_ERROR_MAX_LENGTH
        ]


result_sync_service = ResultSyncService()