"""Business rules for immutable exam rosters derived from Weave offerings."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academics.models import StudentEnrollment
from app.domains.academics.repository import AcademicRepository
from app.domains.candidates.exceptions import (
    CandidateAlreadyExists,
    CandidateEnrollmentError,
    CandidateRosterError,
)
from app.domains.candidates.models import CandidateStatus, ExamCandidate
from app.domains.candidates.repository import CandidateRepository
from app.domains.exams.exceptions import ExamNotFound
from app.domains.exams.models import Exam, ExamStatus
from app.domains.exams.repository import ExamRepository

ROSTER_EDITABLE_EXAM_STATUSES = frozenset(
    {ExamStatus.DRAFT, ExamStatus.SUBMITTED, ExamStatus.SEALED}
)


class CandidateService:
    @staticmethod
    def _display_name(enrollment: StudentEnrollment) -> str:
        parts = [
            value.strip()
            for value in (enrollment.first_name, enrollment.last_name)
            if value and value.strip()
        ]
        return " ".join(parts) or enrollment.admission_number

    @staticmethod
    async def validate_enrollment_for_exam(
        db: AsyncSession,
        *,
        exam_id: UUID,
        enrollment_id: UUID,
    ) -> tuple[Exam, StudentEnrollment]:
        exam = await ExamRepository.get_exam_by_id(db, exam_id)
        if exam is None:
            raise ExamNotFound("Exam not found.")

        enrollment = await AcademicRepository.get_enrollment_by_id(db, enrollment_id)
        if enrollment is None:
            raise CandidateEnrollmentError("Student enrollment not found.")
        if enrollment.academic_session_id != exam.session_id:
            raise CandidateEnrollmentError(
                "Student enrollment does not belong to the exam academic session."
            )
        if not enrollment.is_current or enrollment.student_status != "active":
            raise CandidateEnrollmentError("Student enrollment is not currently active.")
        if enrollment.class_id is None:
            raise CandidateEnrollmentError("Student enrollment has no assigned class.")

        target = await ExamRepository.get_target_class(db, exam.id, enrollment.class_id)
        if target is None:
            raise CandidateEnrollmentError(
                "Student enrollment class is not one of the exam target classes."
            )
        if target.subject_offering_id is None:
            raise CandidateEnrollmentError(
                "Exam target has not been resolved to a synchronized subject offering."
            )
        if not await AcademicRepository.enrollment_is_eligible_for_offering(
            db,
            offering_id=target.subject_offering_id,
            enrollment_id=enrollment.id,
        ):
            raise CandidateEnrollmentError(
                "Student enrollment is not eligible for this subject offering."
            )

        return exam, enrollment

    @staticmethod
    async def add_candidate_from_enrollment(
        db: AsyncSession,
        *,
        exam_id: UUID,
        enrollment_id: UUID,
        status: CandidateStatus = CandidateStatus.ELIGIBLE,
    ) -> ExamCandidate:
        try:
            exam, enrollment = await CandidateService.validate_enrollment_for_exam(
                db,
                exam_id=exam_id,
                enrollment_id=enrollment_id,
            )
            if exam.status not in ROSTER_EDITABLE_EXAM_STATUSES:
                raise CandidateRosterError(
                    "Candidate roster cannot be changed after the exam becomes active or final."
                )
            existing = await CandidateRepository.get_candidate_by_enrollment(
                db, exam.id, enrollment.id
            )
            if existing is not None:
                raise CandidateAlreadyExists(
                    "This enrollment is already present on the exam roster."
                )

            candidate = ExamCandidate(
                exam_id=exam.id,
                enrollment_id=enrollment.id,
                student_id=enrollment.student_id,
                admission_number=enrollment.admission_number,
                display_name=CandidateService._display_name(enrollment),
                status=status,
            )
            await CandidateRepository.add_candidate(db, candidate)
            await db.commit()
            await db.refresh(candidate)
            return candidate
        except Exception:
            await db.rollback()
            raise
