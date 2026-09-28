"""Student authentication facade that preserves exam lifecycle binding."""

from __future__ import annotations

from app.domains.attempts.models import AttemptStatus
from app.domains.attempts.repository import AttemptRepository
from app.domains.auth.student_schemas import StudentExamAvailability
from app.domains.auth.student_service import (
    INVALID_STUDENT_LOGIN,
    READY_MESSAGE,
    StudentAuthenticationError,
    StudentExamResolution,
    StudentSessionContext,
)
from app.domains.auth.student_service import (
    StudentAuthService as _StudentAuthService,
)
from app.domains.exams.models import ExamStatus

SUSPENDED_MESSAGE = (
    "This examination is temporarily paused. Please wait for an administrator "
    "to resume it. Your saved work and remaining time are protected."
)
FINALIZING_MESSAGE = (
    "This examination is being finalized. No further answers can be submitted."
)
COMPLETED_MESSAGE = (
    "You have already completed this examination. Your score is ready to view."
)

_CURRENT_OPERATIONAL_STATUSES = (
    ExamStatus.ACTIVE,
    ExamStatus.SUSPENDED,
    ExamStatus.CLOSING,
    ExamStatus.CANCELLING,
)
_PAUSED_STATUSES = {
    ExamStatus.SUSPENDED,
    ExamStatus.CLOSING,
    ExamStatus.CANCELLING,
}


class StudentAuthService(_StudentAuthService):
    """Resolve completed work before the current exam operational state."""

    @classmethod
    async def _completed_resolution(cls, db, rows):
        completed = []
        for candidate, exam in rows:
            attempt = await AttemptRepository.get_attempt_by_candidate_id(
                db,
                candidate.id,
            )
            if attempt is not None and attempt.status == AttemptStatus.SUBMITTED:
                completed.append((candidate, exam))

        if len(completed) > 1:
            raise StudentAuthenticationError(
                "Multiple completed operational examinations were found for this student"
            )
        if not completed:
            return None

        candidate, exam = completed[0]
        return StudentExamResolution(
            candidate=candidate,
            exam=exam,
            makeup_authorization_id=None,
            availability=StudentExamAvailability.COMPLETED,
            status_message=COMPLETED_MESSAGE,
        )

    @classmethod
    async def _resolve_candidate(cls, db, *, enrollment):
        operational = await cls._normal_candidate_rows(
            db,
            student_id=enrollment.student_id,
            statuses=_CURRENT_OPERATIONAL_STATUSES,
        )

        # Attempt completion is candidate-specific and final. Once the student
        # has submitted this sitting, later suspension/finalization of the exam
        # must not send them back into operational waiting-room messaging.
        completed = await cls._completed_resolution(db, operational)
        if completed is not None:
            return completed

        paused = [row for row in operational if row[1].status in _PAUSED_STATUSES]
        if len(paused) > 1:
            raise StudentAuthenticationError(
                "Multiple paused examinations were found for this student"
            )
        if paused:
            candidate, exam = paused[0]
            return StudentExamResolution(
                candidate=candidate,
                exam=exam,
                makeup_authorization_id=None,
                availability=StudentExamAvailability.SUSPENDED,
                status_message=(
                    SUSPENDED_MESSAGE
                    if exam.status == ExamStatus.SUSPENDED
                    else FINALIZING_MESSAGE
                ),
            )

        active = [row for row in operational if row[1].status == ExamStatus.ACTIVE]
        if len(active) > 1:
            raise StudentAuthenticationError(
                "Multiple active examinations were found for this student"
            )
        if active:
            candidate, exam = active[0]
            return StudentExamResolution(
                candidate=candidate,
                exam=exam,
                makeup_authorization_id=None,
                availability=StudentExamAvailability.READY,
                status_message=READY_MESSAGE,
            )

        return await super()._resolve_candidate(db, enrollment=enrollment)


__all__ = [
    "COMPLETED_MESSAGE",
    "INVALID_STUDENT_LOGIN",
    "StudentAuthService",
    "StudentAuthenticationError",
    "StudentSessionContext",
]
