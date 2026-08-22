"""Offline student authentication and exam-scoped opaque sessions."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import StoredCredentialHashError, verify_candidate_pin
from app.domains.academics.models import StudentEnrollment
from app.domains.academics.repository import AcademicRepository
from app.domains.auth.student_models import StudentExamSession
from app.domains.auth.student_repository import StudentAuthRepository
from app.domains.auth.student_schemas import StudentExamAvailability, StudentLoginResponse
from app.domains.candidates.makeup_service import CandidateMakeupService
from app.domains.candidates.models import CandidateStatus, ExamCandidate
from app.domains.candidates.repository import CandidateRepository
from app.domains.exams.models import Exam, ExamRosterStatus, ExamStatus


STUDENT_SESSION_TOKEN_BYTES = 48
STUDENT_SESSION_LIFETIME_HOURS = 8


class StudentAuthenticationError(ValueError):
    """Raised when local student authentication/session resolution fails."""


@dataclass(frozen=True)
class StudentSessionContext:
    session_id: UUID
    student_id: UUID
    candidate_id: UUID
    exam_id: UUID
    makeup_authorization_id: UUID | None

    @property
    def is_makeup(self) -> bool:
        return self.makeup_authorization_id is not None


@dataclass(frozen=True)
class StudentLoginResult:
    raw_token: str
    expires_at: datetime
    response: StudentLoginResponse


def hash_student_session_token(token: str) -> str:
    if not isinstance(token, str) or not token:
        raise StudentAuthenticationError("Student session token is missing")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class StudentAuthService:
    @staticmethod
    async def _get_current_enrollment(
        db: AsyncSession,
        admission_number: str,
    ) -> StudentEnrollment | None:
        normalized = admission_number.strip().casefold()
        query = (
            select(StudentEnrollment)
            .where(
                StudentEnrollment.is_current.is_(True),
                StudentEnrollment.source_deleted_at.is_(None),
                StudentEnrollment.student_status == "active",
            )
            .order_by(StudentEnrollment.updated_at.desc())
        )
        rows = list((await db.execute(query)).scalars().all())
        matches = [
            row for row in rows if row.admission_number.strip().casefold() == normalized
        ]
        if len(matches) > 1:
            raise StudentAuthenticationError(
                "Admission number resolves to multiple current enrollments"
            )
        return matches[0] if matches else None

    @staticmethod
    async def _normal_candidate_rows(
        db: AsyncSession,
        *,
        student_id: UUID,
        statuses: tuple[ExamStatus, ...],
    ) -> list[tuple[ExamCandidate, Exam]]:
        result = await db.execute(
            select(ExamCandidate, Exam)
            .join(Exam, Exam.id == ExamCandidate.exam_id)
            .where(
                ExamCandidate.student_id == student_id,
                ExamCandidate.status == CandidateStatus.ELIGIBLE,
                Exam.status.in_(statuses),
                Exam.roster_status == ExamRosterStatus.READY,
            )
            .order_by(Exam.scheduled_start_at.asc().nulls_last(), Exam.id.asc())
        )
        return list(result.tuples().all())

    @classmethod
    async def _resolve_candidate(
        cls,
        db: AsyncSession,
        *,
        enrollment: StudentEnrollment,
    ) -> tuple[ExamCandidate, Exam, UUID | None, StudentExamAvailability]:
        active = await cls._normal_candidate_rows(
            db,
            student_id=enrollment.student_id,
            statuses=(ExamStatus.ACTIVE,),
        )
        if len(active) > 1:
            raise StudentAuthenticationError(
                "Multiple active examinations were found for this student"
            )
        if active:
            candidate, exam = active[0]
            return candidate, exam, None, StudentExamAvailability.READY

        waiting = await cls._normal_candidate_rows(
            db,
            student_id=enrollment.student_id,
            statuses=(ExamStatus.SEALED,),
        )
        if waiting:
            candidate, exam = waiting[0]
            return (
                candidate,
                exam,
                None,
                StudentExamAvailability.WAITING_FOR_ACTIVATION,
            )

        session = await AcademicRepository.get_current_session(db)
        if session is None:
            raise StudentAuthenticationError("No current academic session is available")
        term = await AcademicRepository.get_current_term(db, session_id=session.id)
        if term is None:
            raise StudentAuthenticationError("No current academic term is available")

        queue = await CandidateMakeupService.resolve_queue(
            db,
            student_id=enrollment.student_id,
            session_id=session.id,
            term_id=term.id,
        )
        if not queue.available or queue.next_candidate_id is None or queue.next_exam_id is None:
            raise StudentAuthenticationError(
                queue.blocked_reason or "No examination is currently available"
            )

        candidate = await CandidateRepository.get_candidate_by_id(
            db, queue.next_candidate_id
        )
        if candidate is None:
            raise StudentAuthenticationError("Makeup candidate no longer exists")
        exam = await db.get(Exam, queue.next_exam_id)
        if exam is None:
            raise StudentAuthenticationError("Makeup examination no longer exists")
        return (
            candidate,
            exam,
            queue.authorization_id,
            StudentExamAvailability.MAKEUP,
        )

    @staticmethod
    async def _revoke_existing_sessions(
        db: AsyncSession,
        *,
        student_id: UUID,
        now: datetime,
    ) -> None:
        sessions = await StudentAuthRepository.list_unrevoked_sessions_for_student(
            db, student_id, lock=True
        )
        for session in sessions:
            session.revoked_at = now
            session.revocation_reason = "Superseded by a new student login"
        await StudentAuthRepository.save_sessions(db, sessions)

    @classmethod
    async def login(
        cls,
        db: AsyncSession,
        *,
        admission_number: str,
        pin: str,
    ) -> StudentLoginResult:
        enrollment = await cls._get_current_enrollment(db, admission_number)
        if enrollment is None:
            raise StudentAuthenticationError("Invalid admission number or CBT PIN")

        credential = await CandidateRepository.get_active_credential_by_student_id(
            db, enrollment.student_id
        )
        if credential is None:
            raise StudentAuthenticationError("Invalid admission number or CBT PIN")
        try:
            valid_pin = await verify_candidate_pin(pin, credential.pin_hash)
        except StoredCredentialHashError as exc:
            raise StudentAuthenticationError(
                "Student CBT credential is invalid; administrator intervention is required"
            ) from exc
        if not valid_pin:
            raise StudentAuthenticationError("Invalid admission number or CBT PIN")

        candidate, exam, makeup_authorization_id, availability = (
            await cls._resolve_candidate(db, enrollment=enrollment)
        )
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=STUDENT_SESSION_LIFETIME_HOURS)
        raw_token = secrets.token_urlsafe(STUDENT_SESSION_TOKEN_BYTES)
        session_row = StudentExamSession(
            student_id=enrollment.student_id,
            candidate_id=candidate.id,
            exam_id=exam.id,
            makeup_authorization_id=makeup_authorization_id,
            token_hash=hash_student_session_token(raw_token),
            expires_at=expires_at,
            last_seen_at=now,
        )

        try:
            await cls._revoke_existing_sessions(
                db, student_id=enrollment.student_id, now=now
            )
            await StudentAuthRepository.add_session(db, session_row)
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise StudentAuthenticationError(
                "Student examination session could not be created"
            ) from exc

        return StudentLoginResult(
            raw_token=raw_token,
            expires_at=expires_at,
            response=StudentLoginResponse(
                student_id=enrollment.student_id,
                candidate_id=candidate.id,
                exam_id=exam.id,
                exam_title=exam.title,
                display_name=candidate.display_name,
                availability=availability,
                is_makeup=makeup_authorization_id is not None,
                scheduled_start_at=exam.scheduled_start_at,
                activated_at=exam.activated_at,
            ),
        )

    @classmethod
    async def resolve_session(
        cls,
        db: AsyncSession,
        *,
        raw_token: str,
        touch: bool = True,
    ) -> StudentSessionContext:
        token_hash = hash_student_session_token(raw_token)
        session = await StudentAuthRepository.get_session_by_hash(db, token_hash)
        now = datetime.now(UTC)
        if (
            session is None
            or session.revoked_at is not None
            or session.expires_at <= now
        ):
            raise StudentAuthenticationError("Student examination session is not active")

        candidate = await CandidateRepository.get_candidate_by_id(db, session.candidate_id)
        if (
            candidate is None
            or candidate.student_id != session.student_id
            or candidate.exam_id != session.exam_id
        ):
            raise StudentAuthenticationError("Student examination session is inconsistent")

        if touch and (now - session.last_seen_at) >= timedelta(minutes=5):
            session.last_seen_at = now
            await StudentAuthRepository.save_session(db, session)
            await db.commit()

        return StudentSessionContext(
            session_id=session.id,
            student_id=session.student_id,
            candidate_id=session.candidate_id,
            exam_id=session.exam_id,
            makeup_authorization_id=session.makeup_authorization_id,
        )

    @classmethod
    async def logout(cls, db: AsyncSession, *, raw_token: str) -> None:
        session = await StudentAuthRepository.get_session_by_hash(
            db, hash_student_session_token(raw_token), lock=True
        )
        if session is None or session.revoked_at is not None:
            return
        session.revoked_at = datetime.now(UTC)
        session.revocation_reason = "Student logged out"
        await StudentAuthRepository.save_session(db, session)
        await db.commit()
