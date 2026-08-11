# =========================== #
#      attempts/service.py    #
# =========================== #

"""Attempt-domain business rules shared by API and background workflows."""

from __future__ import annotations

from datetime import datetime

from app.domains.attempts.exceptions import (
    AttemptNotInterrupted,
    AttemptTimeExhausted,
    ExamNotActiveForAttempt,
    ExamNotYetOpen,
    ExamStartWindowClosed,
)
from app.domains.attempts.models import AttemptStatus, ExamAttempt
from app.domains.exams.models import Exam, ExamStatus


def _require_aware_datetime(value: datetime, *, field_name: str) -> None:
    """Reject naive datetimes so exam-window comparisons remain unambiguous."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


def _remaining_seconds(attempt: ExamAttempt) -> int:
    """Return persisted remaining writing time for an inactive attempt."""

    return max(attempt.time_limit_seconds - attempt.elapsed_seconds, 0)


def ensure_exam_accepts_new_attempt(exam: Exam, *, now: datetime) -> None:
    """
    Validate whether a candidate may create a brand-new attempt.

    The exam window is half-open:

        opens_at <= now < closes_at

    Therefore `closes_at` means "no new attempts from this instant onward."
    It does not invalidate an already-created interrupted attempt.
    """

    _require_aware_datetime(now, field_name="now")

    if exam.status != ExamStatus.ACTIVE:
        raise ExamNotActiveForAttempt(
            "A new attempt can only start while the exam is active."
        )

    if exam.opens_at is not None:
        _require_aware_datetime(exam.opens_at, field_name="exam.opens_at")

        if now < exam.opens_at:
            raise ExamNotYetOpen("The examination has not opened yet.")

    if exam.closes_at is not None:
        _require_aware_datetime(exam.closes_at, field_name="exam.closes_at")

        if now >= exam.closes_at:
            raise ExamStartWindowClosed(
                "The examination window has closed for new attempts."
            )


def ensure_interrupted_attempt_can_resume(attempt: ExamAttempt) -> None:
    """
    Validate timer state before an authorized invigilator/admin resumes an attempt.

    This rule intentionally does NOT check Exam.closes_at. The attempt already
    existed before the window closed, so closing time prevents new starts rather
    than converting a legitimate resume into a retake.
    """

    if attempt.status != AttemptStatus.INTERRUPTED:
        raise AttemptNotInterrupted(
            "Only an interrupted attempt can be resumed through this flow."
        )

    if _remaining_seconds(attempt) <= 0:
        raise AttemptTimeExhausted(
            "The interrupted attempt has no examination time remaining."
        )
