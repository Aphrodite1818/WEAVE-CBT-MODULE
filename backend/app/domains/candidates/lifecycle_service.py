"""Lifecycle-aware candidate service facade."""

from __future__ import annotations

from app.domains.candidates.service import CandidateService as _CandidateService
from app.domains.exams.models import ExamStatus


class CandidateService(_CandidateService):
    """Prevent roster-policy mutations once terminal finalization has started."""

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
