"""Persistence operations for examination candidates and CBT credentials.

Repositories only perform database reads/writes and row locking. Roster
eligibility, credential verification, late-start policy, lifecycle decisions,
and transaction boundaries belong to services/workers.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.candidates.models import (
    CandidateLateStartAuthorization,
    CandidateStatus,
    ExamCandidate,
    StudentCBTCredential,
)


class CandidateRepository:
    """Provide persistence operations for rosters, credentials and late starts."""

    @staticmethod
    async def add_candidate(
        db: AsyncSession, candidate: ExamCandidate
    ) -> ExamCandidate:
        db.add(candidate)
        await db.flush()
        return candidate

    @staticmethod
    async def add_candidates(
        db: AsyncSession,
        candidates: Sequence[ExamCandidate],
    ) -> list[ExamCandidate]:
        rows = list(candidates)
        if rows:
            db.add_all(rows)
            await db.flush()
        return rows

    @staticmethod
    async def save_candidate(
        db: AsyncSession, candidate: ExamCandidate
    ) -> ExamCandidate:
        db.add(candidate)
        await db.flush()
        return candidate

    @staticmethod
    async def save_candidates(
        db: AsyncSession,
        candidates: Sequence[ExamCandidate],
    ) -> list[ExamCandidate]:
        rows = list(candidates)
        if rows:
            db.add_all(rows)
            await db.flush()
        return rows

    @staticmethod
    async def get_candidate_by_id(
        db: AsyncSession,
        candidate_id: UUID,
        *,
        lock: bool = False,
    ) -> ExamCandidate | None:
        query = select(ExamCandidate).where(ExamCandidate.id == candidate_id)
        if lock:
            query = query.with_for_update(of=ExamCandidate)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_candidate_by_enrollment(
        db: AsyncSession,
        exam_id: UUID,
        enrollment_id: UUID,
        *,
        lock: bool = False,
    ) -> ExamCandidate | None:
        query = select(ExamCandidate).where(
            ExamCandidate.exam_id == exam_id,
            ExamCandidate.enrollment_id == enrollment_id,
        )
        if lock:
            query = query.with_for_update(of=ExamCandidate)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_candidate_by_student_id(
        db: AsyncSession,
        exam_id: UUID,
        student_id: UUID,
        *,
        lock: bool = False,
    ) -> ExamCandidate | None:
        query = select(ExamCandidate).where(
            ExamCandidate.exam_id == exam_id,
            ExamCandidate.student_id == student_id,
        )
        if lock:
            query = query.with_for_update(of=ExamCandidate)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_candidate_by_admission_number(
        db: AsyncSession,
        exam_id: UUID,
        admission_number: str,
        *,
        lock: bool = False,
    ) -> ExamCandidate | None:
        query = select(ExamCandidate).where(
            ExamCandidate.exam_id == exam_id,
            ExamCandidate.admission_number == admission_number,
        )
        if lock:
            query = query.with_for_update(of=ExamCandidate)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_candidates_for_exam(
        db: AsyncSession,
        exam_id: UUID,
        *,
        status: CandidateStatus | None = None,
        class_id: UUID | None = None,
        roster_version: int | None = None,
        offset: int = 0,
        limit: int | None = None,
        lock: bool = False,
        skip_locked: bool = False,
    ) -> list[ExamCandidate]:
        query = select(ExamCandidate).where(ExamCandidate.exam_id == exam_id)
        if status is not None:
            query = query.where(ExamCandidate.status == status)
        if class_id is not None:
            query = query.where(ExamCandidate.class_id == class_id)
        if roster_version is not None:
            query = query.where(ExamCandidate.roster_version == roster_version)
        query = query.order_by(
            ExamCandidate.display_name.asc(),
            ExamCandidate.admission_number.asc(),
            ExamCandidate.id.asc(),
        ).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        if lock:
            query = query.with_for_update(
                of=ExamCandidate,
                skip_locked=skip_locked,
            )
        return list((await db.execute(query)).scalars().all())

    @staticmethod
    async def list_candidates_not_seen_in_roster_version(
        db: AsyncSession,
        exam_id: UUID,
        roster_version: int,
        *,
        lock: bool = False,
        skip_locked: bool = False,
    ) -> list[ExamCandidate]:
        query = (
            select(ExamCandidate)
            .where(
                ExamCandidate.exam_id == exam_id,
                ExamCandidate.roster_version < roster_version,
            )
            .order_by(ExamCandidate.id.asc())
        )
        if lock:
            query = query.with_for_update(
                of=ExamCandidate,
                skip_locked=skip_locked,
            )
        return list((await db.execute(query)).scalars().all())

    @staticmethod
    async def count_candidates_for_exam(
        db: AsyncSession,
        exam_id: UUID,
        *,
        status: CandidateStatus | None = None,
        class_id: UUID | None = None,
    ) -> int:
        query = (
            select(func.count())
            .select_from(ExamCandidate)
            .where(ExamCandidate.exam_id == exam_id)
        )
        if status is not None:
            query = query.where(ExamCandidate.status == status)
        if class_id is not None:
            query = query.where(ExamCandidate.class_id == class_id)
        return int((await db.execute(query)).scalar_one() or 0)

    @staticmethod
    async def add_credential(
        db: AsyncSession,
        credential: StudentCBTCredential,
    ) -> StudentCBTCredential:
        db.add(credential)
        await db.flush()
        return credential

    @staticmethod
    async def get_credential_by_id(
        db: AsyncSession,
        credential_id: UUID,
        *,
        lock: bool = False,
    ) -> StudentCBTCredential | None:
        query = select(StudentCBTCredential).where(
            StudentCBTCredential.id == credential_id
        )
        if lock:
            query = query.with_for_update(of=StudentCBTCredential)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_credential_by_student_id(
        db: AsyncSession,
        student_id: UUID,
        *,
        lock: bool = False,
    ) -> StudentCBTCredential | None:
        query = select(StudentCBTCredential).where(
            StudentCBTCredential.student_id == student_id
        )
        if lock:
            query = query.with_for_update(of=StudentCBTCredential)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_active_credential_by_student_id(
        db: AsyncSession,
        student_id: UUID,
        *,
        lock: bool = False,
    ) -> StudentCBTCredential | None:
        query = select(StudentCBTCredential).where(
            StudentCBTCredential.student_id == student_id,
            StudentCBTCredential.is_active.is_(True),
            StudentCBTCredential.source_deleted_at.is_(None),
        )
        if lock:
            query = query.with_for_update(of=StudentCBTCredential)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def save_credential(
        db: AsyncSession,
        credential: StudentCBTCredential,
    ) -> StudentCBTCredential:
        db.add(credential)
        await db.flush()
        return credential

    @staticmethod
    async def add_late_start_authorization(
        db: AsyncSession,
        authorization: CandidateLateStartAuthorization,
    ) -> CandidateLateStartAuthorization:
        db.add(authorization)
        await db.flush()
        return authorization

    @staticmethod
    async def get_late_start_authorization_by_id(
        db: AsyncSession,
        authorization_id: UUID,
        *,
        lock: bool = False,
    ) -> CandidateLateStartAuthorization | None:
        query = select(CandidateLateStartAuthorization).where(
            CandidateLateStartAuthorization.id == authorization_id
        )
        if lock:
            query = query.with_for_update(of=CandidateLateStartAuthorization)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_usable_late_start_authorization(
        db: AsyncSession,
        candidate_id: UUID,
        *,
        at: datetime,
        lock: bool = False,
    ) -> CandidateLateStartAuthorization | None:
        query = (
            select(CandidateLateStartAuthorization)
            .where(
                CandidateLateStartAuthorization.candidate_id == candidate_id,
                CandidateLateStartAuthorization.consumed_at.is_(None),
                CandidateLateStartAuthorization.revoked_at.is_(None),
                (
                    CandidateLateStartAuthorization.expires_at.is_(None)
                    | (CandidateLateStartAuthorization.expires_at >= at)
                ),
            )
            .order_by(
                CandidateLateStartAuthorization.granted_at.desc(),
                CandidateLateStartAuthorization.id.desc(),
            )
            .limit(1)
        )
        if lock:
            query = query.with_for_update(of=CandidateLateStartAuthorization)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_late_start_authorizations(
        db: AsyncSession,
        candidate_id: UUID,
    ) -> list[CandidateLateStartAuthorization]:
        result = await db.execute(
            select(CandidateLateStartAuthorization)
            .where(CandidateLateStartAuthorization.candidate_id == candidate_id)
            .order_by(
                CandidateLateStartAuthorization.granted_at.asc(),
                CandidateLateStartAuthorization.id.asc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def save_late_start_authorization(
        db: AsyncSession,
        authorization: CandidateLateStartAuthorization,
    ) -> CandidateLateStartAuthorization:
        db.add(authorization)
        await db.flush()
        return authorization
