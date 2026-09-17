"""Student authentication facade that preserves suspended exam binding."""

from __future__ import annotations

from app.domains.auth.student_schemas import StudentExamAvailability
from app.domains.auth.student_service import (
    INVALID_STUDENT_LOGIN,
    StudentAuthenticationError,
    StudentAuthService as _StudentAuthService,
    StudentExamResolution,
    StudentSessionContext,
)
from app.domains.exams.models import ExamStatus


SUSPENDED_MESSAGE = (
    "This examination is temporarily paused. Please wait for an administrator "
    "to resume it. Your saved work and remaining time are protected."
)
FINALIZING_MESSAGE = (
    "This examination is being finalized. No further answers can be submitted."
)


class StudentAuthService(_StudentAuthService):
    """Prefer a suspended/finalizing normal exam before later waiting papers."""

    @classmethod
    async def _resolve_candidate(cls, db, *, enrollment):
        paused = await cls._normal_candidate_rows(
            db,
            student_id=enrollment.student_id,
            statuses=(
                ExamStatus.SUSPENDED,
                ExamStatus.CLOSING,
                ExamStatus.CANCELLING,
            ),
        )
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
        return await super()._resolve_candidate(db, enrollment=enrollment)


__all__ = [
    "INVALID_STUDENT_LOGIN",
    "StudentAuthenticationError",
    "StudentAuthService",
    "StudentSessionContext",
]
