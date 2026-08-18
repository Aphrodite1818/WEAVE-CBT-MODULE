"""Persistence operations for examination candidates and PIN credentials."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.candidates.models import CandidateCredential, CandidateStatus, ExamCandidate


class CandidateRepository:
    @staticmethod
    async def add_candidate(db: AsyncSession, candidate: ExamCandidate) -> ExamCandidate:
        db.add(candidate)
        await db.flush()
        return candidate

    @staticmethod
    async def add_candidates(db: AsyncSession, candidates: Sequence[ExamCandidate]) -> list[ExamCandidate]:
        rows = list(candidates)
        if rows:
            db.add_all(rows)
            await db.flush()
        return rows

    @staticmethod
    async def get_candidate_by_id(db: AsyncSession, candidate_id: UUID, *, lock: bool = False) -> ExamCandidate | None:
        query = select(ExamCandidate).where(ExamCandidate.id == candidate_id)
        if lock:
            query = query.with_for_update(of=ExamCandidate)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_candidate_by_enrollment(
        db: AsyncSession, exam_id: UUID, enrollment_id: UUID, *, lock: bool = False
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
        db: AsyncSession, exam_id: UUID, student_id: UUID, *, lock: bool = False
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
        db: AsyncSession, exam_id: UUID, admission_number: str, *, lock: bool = False
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
        offset: int = 0,
        limit: int | None = None,
    ) -> list[ExamCandidate]:
        query = select(ExamCandidate).where(ExamCandidate.exam_id == exam_id)
        if status is not None:
            query = query.where(ExamCandidate.status == status)
        query = query.order_by(ExamCandidate.display_name.asc(), ExamCandidate.admission_number.asc()).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return list((await db.execute(query)).scalars().all())

    @staticmethod
    async def count_candidates_for_exam(
        db: AsyncSession, exam_id: UUID, *, status: CandidateStatus | None = None
    ) -> int:
        query = select(func.count()).select_from(ExamCandidate).where(ExamCandidate.exam_id == exam_id)
        if status is not None:
            query = query.where(ExamCandidate.status == status)
        return int((await db.execute(query)).scalar_one() or 0)

    @staticmethod
    async def save_candidate(db: AsyncSession, candidate: ExamCandidate) -> ExamCandidate:
        db.add(candidate)
        await db.flush()
        return candidate

    @staticmethod
    async def save_candidates(db: AsyncSession, candidates: Sequence[ExamCandidate]) -> list[ExamCandidate]:
        rows = list(candidates)
        if rows:
            db.add_all(rows)
            await db.flush()
        return rows

    @staticmethod
    async def add_credential(db: AsyncSession, credential: CandidateCredential) -> CandidateCredential:
        db.add(credential)
        await db.flush()
        return credential

    @staticmethod
    async def add_credentials(db: AsyncSession, credentials: Sequence[CandidateCredential]) -> list[CandidateCredential]:
        rows = list(credentials)
        if rows:
            db.add_all(rows)
            await db.flush()
        return rows

    @staticmethod
    async def get_credential_by_id(db: AsyncSession, credential_id: UUID, *, lock: bool = False) -> CandidateCredential | None:
        query = select(CandidateCredential).where(CandidateCredential.id == credential_id)
        if lock:
            query = query.with_for_update(of=CandidateCredential)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_credential_by_candidate_id(
        db: AsyncSession, candidate_id: UUID, *, lock: bool = False
    ) -> CandidateCredential | None:
        query = select(CandidateCredential).where(CandidateCredential.candidate_id == candidate_id)
        if lock:
            query = query.with_for_update(of=CandidateCredential)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def save_credential(db: AsyncSession, credential: CandidateCredential) -> CandidateCredential:
        db.add(credential)
        await db.flush()
        return credential
