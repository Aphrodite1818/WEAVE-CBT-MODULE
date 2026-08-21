"""Public examination service facade."""

from __future__ import annotations

from app.domains.exams.authoring_service import ExamService as _AuthoringExamService
from app.domains.exams.lifecycle_service import ExamLifecycleServiceMixin


class ExamService(ExamLifecycleServiceMixin, _AuthoringExamService):
    """Combined exam authoring, review, invigilation, and lifecycle service."""


__all__ = ["ExamService"]
