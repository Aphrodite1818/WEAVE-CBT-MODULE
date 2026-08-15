from __future__ import annotations

import os
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app.domains.academics.repository import AcademicRepository  # noqa: E402
from app.domains.candidates.exceptions import CandidateEnrollmentError  # noqa: E402
from app.domains.candidates.service import CandidateService  # noqa: E402
from app.domains.exams.exceptions import (  # noqa: E402
    ExamAcademicScopeError,
    ExamAuthorizationError,
    ExamQuestionScopeError,
)
from app.domains.exams.models import ExamStatus  # noqa: E402
from app.domains.exams.repository import ExamRepository  # noqa: E402
from app.domains.exams.service import ExamService  # noqa: E402
from app.domains.questions.exceptions import QuestionAuthorizationError  # noqa: E402
from app.domains.questions.repository import QuestionRepository  # noqa: E402
from app.domains.questions.service import QuestionService  # noqa: E402


class ExamAcademicIntegrityTests(unittest.IsolatedAsyncioTestCase):
    async def test_exam_term_must_belong_to_exam_session(self) -> None:
        exam = SimpleNamespace(
            session_id=uuid4(),
            term_id=uuid4(),
            level_subject_id=uuid4(),
            assessment_scheme_id=uuid4(),
            assessment_component_id=uuid4(),
            maximum_score=Decimal("10"),
        )

        with (
            patch.object(
                AcademicRepository,
                "get_session_by_id",
                AsyncMock(return_value=SimpleNamespace(id=exam.session_id)),
            ),
            patch.object(
                AcademicRepository,
                "get_term_by_id",
                AsyncMock(return_value=SimpleNamespace(session_id=uuid4())),
            ),
        ):
            with self.assertRaises(ExamAcademicScopeError):
                await ExamService._validate_academic_scope(object(), exam)

    async def test_component_must_belong_to_exam_scheme(self) -> None:
        exam = SimpleNamespace(
            session_id=uuid4(),
            term_id=uuid4(),
            level_subject_id=uuid4(),
            assessment_scheme_id=uuid4(),
            assessment_component_id=uuid4(),
            maximum_score=Decimal("10"),
        )
        level_subject = SimpleNamespace(is_active=True, level_id=uuid4())
        scheme = SimpleNamespace(status="active")
        component = SimpleNamespace(
            is_active=True,
            assessment_scheme_id=uuid4(),
            maximum_score=Decimal("10"),
        )

        with (
            patch.object(
                AcademicRepository,
                "get_session_by_id",
                AsyncMock(return_value=SimpleNamespace(id=exam.session_id)),
            ),
            patch.object(
                AcademicRepository,
                "get_term_by_id",
                AsyncMock(return_value=SimpleNamespace(session_id=exam.session_id)),
            ),
            patch.object(
                AcademicRepository,
                "get_level_subject_by_id",
                AsyncMock(return_value=level_subject),
            ),
            patch.object(
                AcademicRepository,
                "get_assessment_scheme_by_id",
                AsyncMock(return_value=scheme),
            ),
            patch.object(
                AcademicRepository,
                "get_component_by_id",
                AsyncMock(return_value=component),
            ),
        ):
            with self.assertRaises(ExamAcademicScopeError):
                await ExamService._validate_academic_scope(object(), exam)

    async def test_target_resolution_freezes_exact_assignment_provenance(self) -> None:
        level_id = uuid4()
        teacher_id = uuid4()
        assignment_id = uuid4()
        target = SimpleNamespace(class_id=uuid4())
        exam = SimpleNamespace(id=uuid4(), level_subject_id=uuid4())
        level_subject = SimpleNamespace(level_id=level_id)
        assignment = SimpleNamespace(
            id=assignment_id,
            weave_assignment_id="weave-assignment-1",
            teacher_id=teacher_id,
        )

        with (
            patch.object(
                ExamRepository,
                "list_target_classes_for_exam",
                AsyncMock(return_value=[target]),
            ),
            patch.object(
                AcademicRepository,
                "get_class_by_id",
                AsyncMock(
                    return_value=SimpleNamespace(is_active=True, level_id=level_id)
                ),
            ),
            patch.object(
                AcademicRepository,
                "get_active_assignment_for_class_level_subject",
                AsyncMock(return_value=assignment),
            ),
            patch.object(
                ExamRepository,
                "save_target_class",
                AsyncMock(return_value=target),
            ),
        ):
            await ExamService._resolve_target_assignments(
                object(),
                exam,
                level_subject,
                effective_on=date(2026, 8, 12),
                required_teacher_id=teacher_id,
            )

        self.assertEqual(target.teacher_assignment_id, assignment_id)
        self.assertEqual(
            target.weave_teacher_assignment_id,
            "weave-assignment-1",
        )

    async def test_teacher_cannot_target_another_teachers_arm(self) -> None:
        level_id = uuid4()
        target = SimpleNamespace(class_id=uuid4())
        exam = SimpleNamespace(id=uuid4(), level_subject_id=uuid4())
        level_subject = SimpleNamespace(level_id=level_id)
        assignment = SimpleNamespace(
            id=uuid4(),
            weave_assignment_id="weave-assignment-2",
            teacher_id=uuid4(),
        )

        with (
            patch.object(
                ExamRepository,
                "list_target_classes_for_exam",
                AsyncMock(return_value=[target]),
            ),
            patch.object(
                AcademicRepository,
                "get_class_by_id",
                AsyncMock(
                    return_value=SimpleNamespace(is_active=True, level_id=level_id)
                ),
            ),
            patch.object(
                AcademicRepository,
                "get_active_assignment_for_class_level_subject",
                AsyncMock(return_value=assignment),
            ),
        ):
            with self.assertRaises(ExamAuthorizationError):
                await ExamService._resolve_target_assignments(
                    object(),
                    exam,
                    level_subject,
                    effective_on=date(2026, 8, 12),
                    required_teacher_id=uuid4(),
                )

    async def test_exam_question_bank_must_match_exam_level_subject(self) -> None:
        exam = SimpleNamespace(
            id=uuid4(),
            level_subject_id=uuid4(),
            maximum_score=Decimal("10"),
        )
        snapshot = SimpleNamespace(
            source_question_id=uuid4(),
            source_question_version=2,
        )
        source_question = SimpleNamespace(
            bank_id=uuid4(),
            is_active=True,
            version=2,
        )
        component = SimpleNamespace(maximum_score=Decimal("10"))

        with (
            patch.object(
                ExamRepository,
                "list_exam_questions",
                AsyncMock(return_value=[snapshot]),
            ),
            patch.object(
                QuestionRepository,
                "get_question_by_id",
                AsyncMock(return_value=source_question),
            ),
            patch.object(
                QuestionRepository,
                "get_bank_by_id",
                AsyncMock(
                    return_value=SimpleNamespace(
                        is_active=True,
                        level_subject_id=uuid4(),
                    )
                ),
            ),
        ):
            with self.assertRaises(ExamQuestionScopeError):
                await ExamService._validate_question_scope_and_points(
                    object(),
                    exam,
                    component,
                )

    async def test_seal_freezes_component_snapshot(self) -> None:
        now = datetime(2026, 8, 12, 17, 30, tzinfo=timezone.utc)
        actor_id = uuid4()
        exam = SimpleNamespace(
            id=uuid4(),
            status=ExamStatus.SUBMITTED,
        )
        actor = SimpleNamespace(id=actor_id, role="tenant_admin", is_active=True)
        level_subject = SimpleNamespace(level_id=uuid4())
        scheme = SimpleNamespace(weave_scheme_id="scheme-1")
        component = SimpleNamespace(
            weave_component_id="component-1",
            name="CA 1",
            code="CA1",
            maximum_score=Decimal("10"),
        )
        db = SimpleNamespace(
            commit=AsyncMock(),
            rollback=AsyncMock(),
            refresh=AsyncMock(),
        )

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                AsyncMock(return_value=exam),
            ),
            patch.object(
                ExamService,
                "_get_active_actor",
                AsyncMock(return_value=actor),
            ),
            patch.object(
                ExamService,
                "_validate_academic_scope",
                AsyncMock(return_value=(level_subject, scheme, component)),
            ),
            patch.object(
                ExamService,
                "_resolve_target_assignments",
                AsyncMock(return_value=[]),
            ),
            patch.object(
                ExamService,
                "_validate_question_scope_and_points",
                AsyncMock(return_value=None),
            ),
            patch.object(
                ExamRepository,
                "save_exam",
                AsyncMock(return_value=exam),
            ),
        ):
            sealed = await ExamService.seal_exam(
                db,
                exam_id=exam.id,
                actor_id=actor_id,
                now=now,
            )

        self.assertEqual(sealed.status, ExamStatus.SEALED)
        self.assertEqual(sealed.source_assessment_scheme_weave_id, "scheme-1")
        self.assertEqual(sealed.source_assessment_component_weave_id, "component-1")
        self.assertEqual(
            sealed.source_assessment_component_maximum_score, Decimal("10")
        )
        self.assertEqual(sealed.sealed_at, now)
        db.commit.assert_awaited_once()


class CandidateAcademicIntegrityTests(unittest.IsolatedAsyncioTestCase):
    async def test_candidate_enrollment_must_belong_to_exam_target_arm(self) -> None:
        session_id = uuid4()
        exam = SimpleNamespace(id=uuid4(), session_id=session_id)
        enrollment = SimpleNamespace(
            id=uuid4(),
            session_id=session_id,
            class_id=uuid4(),
        )

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                AsyncMock(return_value=exam),
            ),
            patch.object(
                AcademicRepository,
                "get_enrollment_by_id",
                AsyncMock(return_value=enrollment),
            ),
            patch.object(
                ExamRepository,
                "get_target_class",
                AsyncMock(return_value=None),
            ),
        ):
            with self.assertRaises(CandidateEnrollmentError):
                await CandidateService.validate_enrollment_for_exam(
                    object(),
                    exam_id=exam.id,
                    enrollment_id=enrollment.id,
                )


class QuestionAuthorizationIntegrityTests(unittest.IsolatedAsyncioTestCase):
    async def test_teacher_with_any_arm_assignment_can_author_shared_bank(self) -> None:
        actor_id = uuid4()
        teacher_id = uuid4()
        level_subject_id = uuid4()
        actor = SimpleNamespace(
            id=actor_id,
            role="teacher",
            is_active=True,
            weave_membership_id="membership-1",
        )
        teacher = SimpleNamespace(id=teacher_id, is_active=True)

        with (
            patch(
                "app.domains.questions.service.AuthRepository.get_actor_by_id",
                AsyncMock(return_value=actor),
            ),
            patch.object(
                AcademicRepository,
                "get_level_subject_by_id",
                AsyncMock(return_value=SimpleNamespace(is_active=True)),
            ),
            patch.object(
                AcademicRepository,
                "get_teacher_by_membership_id",
                AsyncMock(return_value=teacher),
            ),
            patch.object(
                AcademicRepository,
                "teacher_has_level_subject_assignment",
                AsyncMock(return_value=True),
            ),
        ):
            await QuestionService.ensure_actor_can_author_for_level_subject(
                object(),
                actor_id=actor_id,
                level_subject_id=level_subject_id,
                effective_on=date(2026, 8, 12),
            )

    async def test_teacher_without_level_subject_assignment_cannot_author(self) -> None:
        actor_id = uuid4()
        actor = SimpleNamespace(
            id=actor_id,
            role="teacher",
            is_active=True,
            weave_membership_id="membership-2",
        )

        with (
            patch(
                "app.domains.questions.service.AuthRepository.get_actor_by_id",
                AsyncMock(return_value=actor),
            ),
            patch.object(
                AcademicRepository,
                "get_level_subject_by_id",
                AsyncMock(return_value=SimpleNamespace(is_active=True)),
            ),
            patch.object(
                AcademicRepository,
                "get_teacher_by_membership_id",
                AsyncMock(return_value=SimpleNamespace(id=uuid4(), is_active=True)),
            ),
            patch.object(
                AcademicRepository,
                "teacher_has_level_subject_assignment",
                AsyncMock(return_value=False),
            ),
        ):
            with self.assertRaises(QuestionAuthorizationError):
                await QuestionService.ensure_actor_can_author_for_level_subject(
                    object(),
                    actor_id=actor_id,
                    level_subject_id=uuid4(),
                    effective_on=date(2026, 8, 12),
                )


if __name__ == "__main__":
    unittest.main()
