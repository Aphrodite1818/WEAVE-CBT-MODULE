from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ["DEBUG"] = "false"

from app.core.exceptions import AcademicAuthorizationError, AcademicScopeError  # noqa: E402
from app.domains.academics.authorization import (  # noqa: E402
    AcademicAuthorizationService,
)
from app.domains.academics.repository import AcademicRepository  # noqa: E402
from app.domains.exams.exceptions import ExamStateError  # noqa: E402
from app.domains.exams.models import (  # noqa: E402
    ExamQuestionSelectionMode,
    ExamRosterStatus,
    ExamStatus,
)
from app.domains.exams.repository import ExamRepository  # noqa: E402
from app.domains.exams.schemas import (  # noqa: E402
    ExamCreate,
    ExamQuestionConfiguration,
    ExamUpdate,
    ManualQuestionAdd,
    ManualQuestionReorder,
)
from app.domains.exams.service import ExamService  # noqa: E402
from app.domains.questions.repository import QuestionRepository  # noqa: E402
from app.domains.runtime.repository import RuntimeRepository  # noqa: E402


def actor(*, role: str = "teacher") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        role=role,
        is_active=True,
        weave_membership_id=str(uuid4()) if role == "teacher" else None,
    )


def draft_exam(**overrides) -> SimpleNamespace:
    values = {
        "id": uuid4(),
        "session_id": uuid4(),
        "term_id": uuid4(),
        "curriculum_subject_id": uuid4(),
        "assessment_scheme_id": uuid4(),
        "assessment_component_id": uuid4(),
        "question_bank_id": uuid4(),
        "question_selection_mode": ExamQuestionSelectionMode.RANDOM,
        "question_count": 20,
        "title": "Midterm CBT",
        "instructions": None,
        "duration_minutes": 45,
        "shuffle_questions": True,
        "shuffle_options": True,
        "scheduled_start_at": None,
        "latest_normal_start_at": None,
        "status": ExamStatus.DRAFT,
        "roster_status": ExamRosterStatus.NOT_PREPARED,
        "roster_version": 0,
        "roster_candidate_count": 0,
        "revision_number": 1,
        "revision_of_exam_id": None,
        "created_by_actor_id": uuid4(),
        "component_maximum_score": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class ExamSchemaValidationTests(unittest.TestCase):
    def test_update_rejects_invalid_window_when_both_fields_are_supplied(self) -> None:
        start_at = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)

        with self.assertRaisesRegex(
            ValueError,
            "latest_normal_start_at cannot be earlier",
        ):
            ExamUpdate(
                scheduled_start_at=start_at,
                latest_normal_start_at=start_at - timedelta(minutes=1),
            )

    def test_manual_question_payloads_reject_duplicate_ids(self) -> None:
        question_id = uuid4()

        with self.assertRaisesRegex(ValueError, "duplicate questions"):
            ManualQuestionAdd(question_ids=[question_id, question_id])

        with self.assertRaisesRegex(ValueError, "duplicate questions"):
            ManualQuestionReorder(question_ids=[question_id, question_id])

    def test_question_configuration_does_not_confirm_destructive_clear_by_default(
        self,
    ) -> None:
        payload = ExamQuestionConfiguration(
            question_bank_id=uuid4(),
            question_selection_mode=ExamQuestionSelectionMode.RANDOM,
            question_count=20,
        )

        self.assertFalse(payload.clear_existing_manual_selections)


class ExamServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_random_exam_requires_enough_active_questions(self) -> None:
        db = AsyncMock()
        current_actor = actor()
        subject_id = uuid4()
        session_id = uuid4()
        term_id = uuid4()
        scheme_id = uuid4()
        component_id = uuid4()
        bank_id = uuid4()

        payload = ExamCreate(
            session_id=session_id,
            term_id=term_id,
            curriculum_subject_id=subject_id,
            assessment_scheme_id=scheme_id,
            assessment_component_id=component_id,
            question_bank_id=bank_id,
            question_selection_mode=ExamQuestionSelectionMode.RANDOM,
            question_count=20,
            title="First CA",
            duration_minutes=45,
        )

        with (
            patch.object(
                AcademicAuthorizationService,
                "require_can_author_curriculum_subject",
                new=AsyncMock(),
            ),
            patch.object(
                AcademicRepository,
                "get_session_by_id",
                new=AsyncMock(return_value=SimpleNamespace(id=session_id)),
            ),
            patch.object(
                AcademicRepository,
                "get_term_by_id",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        id=term_id,
                        academic_session_id=session_id,
                    )
                ),
            ),
            patch.object(
                AcademicRepository,
                "get_assessment_scheme_by_id",
                new=AsyncMock(return_value=SimpleNamespace(id=scheme_id)),
            ),
            patch.object(
                AcademicRepository,
                "get_component_by_id",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        id=component_id,
                        assessment_scheme_id=scheme_id,
                    )
                ),
            ),
            patch.object(
                QuestionRepository,
                "get_bank_by_id",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        id=bank_id,
                        is_active=True,
                        curriculum_subject_id=subject_id,
                    )
                ),
            ),
            patch.object(
                QuestionRepository,
                "count_questions_for_bank",
                new=AsyncMock(return_value=19),
            ) as count_questions,
            patch.object(
                ExamRepository,
                "get_exam_revision",
                new=AsyncMock(),
            ) as get_revision,
            patch.object(
                ExamRepository,
                "add_exam",
                new=AsyncMock(),
            ) as add_exam,
        ):
            with self.assertRaisesRegex(ValueError, "enough active questions"):
                await ExamService.create_exam(
                    db,
                    actor=current_actor,  # type: ignore[arg-type]
                    payload=payload,
                )

        count_questions.assert_awaited_once_with(
            db,
            bank_id,
            active_only=True,
        )
        get_revision.assert_not_awaited()
        add_exam.assert_not_awaited()
        db.commit.assert_not_awaited()

    async def test_update_merges_existing_schedule_before_validating_window(
        self,
    ) -> None:
        db = AsyncMock()
        current_actor = actor()
        start_at = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
        exam = draft_exam(
            scheduled_start_at=start_at,
            latest_normal_start_at=None,
        )
        payload = ExamUpdate(
            latest_normal_start_at=start_at - timedelta(minutes=5),
        )

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(
                AcademicAuthorizationService,
                "require_can_author_curriculum_subject",
                new=AsyncMock(),
            ),
            patch.object(
                AcademicRepository,
                "get_session_by_id",
                new=AsyncMock(return_value=SimpleNamespace(id=exam.session_id)),
            ),
            patch.object(
                AcademicRepository,
                "get_term_by_id",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        id=exam.term_id,
                        academic_session_id=exam.session_id,
                    )
                ),
            ),
            patch.object(
                AcademicRepository,
                "get_assessment_scheme_by_id",
                new=AsyncMock(
                    return_value=SimpleNamespace(id=exam.assessment_scheme_id)
                ),
            ),
            patch.object(
                AcademicRepository,
                "get_component_by_id",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        id=exam.assessment_component_id,
                        assessment_scheme_id=exam.assessment_scheme_id,
                    )
                ),
            ),
            patch.object(
                QuestionRepository,
                "get_bank_by_id",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        id=exam.question_bank_id,
                        is_active=True,
                        curriculum_subject_id=exam.curriculum_subject_id,
                    )
                ),
            ),
            patch.object(
                ExamRepository,
                "save_exam",
                new=AsyncMock(),
            ) as save_exam,
        ):
            with self.assertRaisesRegex(ValueError, "earlier than scheduled_start_at"):
                await ExamService.update_exam(
                    db,
                    actor=current_actor,  # type: ignore[arg-type]
                    payload=payload,
                    exam_id=exam.id,
                )

        save_exam.assert_not_awaited()
        db.commit.assert_not_awaited()

    async def test_configure_random_questions_requires_destructive_confirmation(
        self,
    ) -> None:
        db = AsyncMock()
        current_actor = actor()
        exam = draft_exam(
            question_selection_mode=ExamQuestionSelectionMode.MANUAL,
            question_count=3,
        )
        payload = ExamQuestionConfiguration(
            question_bank_id=exam.question_bank_id,
            question_selection_mode=ExamQuestionSelectionMode.RANDOM,
            question_count=2,
        )
        existing_selections = [
            SimpleNamespace(question_id=uuid4(), position=1),
            SimpleNamespace(question_id=uuid4(), position=2),
        ]

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(
                AcademicAuthorizationService,
                "require_can_author_curriculum_subject",
                new=AsyncMock(),
            ),
            patch.object(
                QuestionRepository,
                "get_bank_by_id",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        id=exam.question_bank_id,
                        is_active=True,
                        curriculum_subject_id=exam.curriculum_subject_id,
                    )
                ),
            ),
            patch.object(
                ExamRepository,
                "list_question_selections",
                new=AsyncMock(return_value=existing_selections),
            ),
            patch.object(
                ExamRepository,
                "clear_question_selections",
                new=AsyncMock(),
            ) as clear_selections,
            patch.object(
                ExamRepository,
                "save_exam",
                new=AsyncMock(),
            ) as save_exam,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "clear_existing_manual_selections=true",
            ):
                await ExamService.configure_questions(
                    db,
                    actor=current_actor,  # type: ignore[arg-type]
                    exam_id=exam.id,
                    payload=payload,
                )

        clear_selections.assert_not_awaited()
        save_exam.assert_not_awaited()
        db.commit.assert_not_awaited()

    async def test_configure_manual_bank_change_requires_destructive_confirmation(
        self,
    ) -> None:
        db = AsyncMock()
        current_actor = actor()
        new_bank_id = uuid4()
        exam = draft_exam(
            question_selection_mode=ExamQuestionSelectionMode.MANUAL,
            question_count=3,
        )
        payload = ExamQuestionConfiguration(
            question_bank_id=new_bank_id,
            question_selection_mode=ExamQuestionSelectionMode.MANUAL,
            question_count=3,
        )
        existing_selections = [
            SimpleNamespace(question_id=uuid4(), position=1),
        ]

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(
                AcademicAuthorizationService,
                "require_can_author_curriculum_subject",
                new=AsyncMock(),
            ),
            patch.object(
                QuestionRepository,
                "get_bank_by_id",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        id=new_bank_id,
                        is_active=True,
                        curriculum_subject_id=exam.curriculum_subject_id,
                    )
                ),
            ),
            patch.object(
                ExamRepository,
                "list_question_selections",
                new=AsyncMock(return_value=existing_selections),
            ),
            patch.object(
                ExamRepository,
                "clear_question_selections",
                new=AsyncMock(),
            ) as clear_selections,
            patch.object(
                ExamRepository,
                "save_exam",
                new=AsyncMock(),
            ) as save_exam,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "clear_existing_manual_selections=true",
            ):
                await ExamService.configure_questions(
                    db,
                    actor=current_actor,  # type: ignore[arg-type]
                    exam_id=exam.id,
                    payload=payload,
                )

        clear_selections.assert_not_awaited()
        save_exam.assert_not_awaited()
        db.commit.assert_not_awaited()

    async def test_configure_random_questions_clears_manual_selections(self) -> None:
        db = AsyncMock()
        current_actor = actor()
        new_bank_id = uuid4()
        exam = draft_exam(
            question_selection_mode=ExamQuestionSelectionMode.MANUAL,
            question_count=3,
        )
        payload = ExamQuestionConfiguration(
            question_bank_id=new_bank_id,
            question_selection_mode=ExamQuestionSelectionMode.RANDOM,
            question_count=2,
            clear_existing_manual_selections=True,
        )
        existing_selections = [
            SimpleNamespace(question_id=uuid4(), position=1),
            SimpleNamespace(question_id=uuid4(), position=2),
        ]

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(
                AcademicAuthorizationService,
                "require_can_author_curriculum_subject",
                new=AsyncMock(),
            ),
            patch.object(
                QuestionRepository,
                "get_bank_by_id",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        id=new_bank_id,
                        is_active=True,
                        curriculum_subject_id=exam.curriculum_subject_id,
                    )
                ),
            ),
            patch.object(
                ExamRepository,
                "list_question_selections",
                new=AsyncMock(return_value=existing_selections),
            ),
            patch.object(
                QuestionRepository,
                "count_questions_for_bank",
                new=AsyncMock(return_value=2),
            ),
            patch.object(
                ExamRepository,
                "clear_question_selections",
                new=AsyncMock(),
            ) as clear_selections,
            patch.object(
                ExamRepository,
                "save_exam",
                new=AsyncMock(side_effect=lambda _db, row: row),
            ),
        ):
            result = await ExamService.configure_questions(
                db,
                actor=current_actor,  # type: ignore[arg-type]
                exam_id=exam.id,
                payload=payload,
            )

        clear_selections.assert_awaited_once_with(db, exam.id)
        self.assertEqual(result.question_bank_id, new_bank_id)
        self.assertEqual(
            result.question_selection_mode,
            ExamQuestionSelectionMode.RANDOM,
        )
        self.assertEqual(result.question_count, 2)
        db.commit.assert_awaited_once()

    async def test_add_manual_questions_rejects_questions_from_another_bank(
        self,
    ) -> None:
        db = AsyncMock()
        current_actor = actor()
        exam = draft_exam(
            question_selection_mode=ExamQuestionSelectionMode.MANUAL,
            question_count=3,
        )
        question_id = uuid4()
        payload = ManualQuestionAdd(question_ids=[question_id])

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(
                AcademicAuthorizationService,
                "require_can_author_curriculum_subject",
                new=AsyncMock(),
            ),
            patch.object(
                QuestionRepository,
                "get_bank_by_id",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        id=exam.question_bank_id,
                        is_active=True,
                        curriculum_subject_id=exam.curriculum_subject_id,
                    )
                ),
            ),
            patch.object(
                ExamRepository,
                "list_question_selections",
                new=AsyncMock(return_value=[]),
            ),
            patch.object(
                QuestionRepository,
                "list_questions_by_ids",
                new=AsyncMock(
                    return_value=[
                        SimpleNamespace(
                            id=question_id,
                            bank_id=uuid4(),
                        )
                    ]
                ),
            ),
            patch.object(
                ExamRepository,
                "add_question_selections",
                new=AsyncMock(),
            ) as add_selections,
        ):
            with self.assertRaisesRegex(ValueError, "examination question bank"):
                await ExamService.add_manual_questions(
                    db,
                    actor=current_actor,  # type: ignore[arg-type]
                    exam_id=exam.id,
                    payload=payload,
                )

        add_selections.assert_not_awaited()
        db.commit.assert_not_awaited()

    async def test_return_exam_to_draft_clears_submission_metadata(self) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        exam = draft_exam(
            status=ExamStatus.SUBMITTED,
            submitted_by_actor_id=uuid4(),
            submitted_at=datetime.now(UTC),
        )

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(
                ExamRepository,
                "save_exam",
                new=AsyncMock(side_effect=lambda _db, row: row),
            ),
        ):
            result = await ExamService.return_exam_to_draft(
                db,
                actor=admin,  # type: ignore[arg-type]
                exam_id=exam.id,
            )

        self.assertEqual(result.status, ExamStatus.DRAFT)
        self.assertIsNone(result.submitted_by_actor_id)
        self.assertIsNone(result.submitted_at)
        db.commit.assert_awaited_once()

    async def test_return_exam_to_draft_rejects_sealed_exam(self) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        exam = draft_exam(status=ExamStatus.SEALED)

        with patch.object(
            ExamRepository,
            "get_exam_by_id",
            new=AsyncMock(return_value=exam),
        ):
            with self.assertRaisesRegex(ExamStateError, "SUBMITTED"):
                await ExamService.return_exam_to_draft(
                    db,
                    actor=admin,  # type: ignore[arg-type]
                    exam_id=exam.id,
                )

        db.commit.assert_not_awaited()

    async def test_delete_draft_exam_allows_current_author(self) -> None:
        db = AsyncMock()
        current_actor = actor()
        exam = draft_exam(created_by_actor_id=current_actor.id)

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(
                AcademicAuthorizationService,
                "require_can_author_curriculum_subject",
                new=AsyncMock(),
            ) as authorize,
            patch.object(
                ExamRepository,
                "delete_exam",
                new=AsyncMock(),
            ) as delete_exam,
        ):
            await ExamService.delete_draft_exam(
                db,
                actor=current_actor,  # type: ignore[arg-type]
                exam_id=exam.id,
            )

        authorize.assert_awaited_once()
        delete_exam.assert_awaited_once_with(db, exam)
        db.commit.assert_awaited_once()

    async def test_delete_draft_exam_rejects_non_author_teacher(self) -> None:
        db = AsyncMock()
        current_actor = actor()
        exam = draft_exam(created_by_actor_id=uuid4())

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(
                ExamRepository,
                "delete_exam",
                new=AsyncMock(),
            ) as delete_exam,
        ):
            with self.assertRaises(AcademicAuthorizationError):
                await ExamService.delete_draft_exam(
                    db,
                    actor=current_actor,  # type: ignore[arg-type]
                    exam_id=exam.id,
                )

        delete_exam.assert_not_awaited()
        db.commit.assert_not_awaited()

    async def test_assign_invigilators_deduplicates_and_accepts_unassigned_teachers(
        self,
    ) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        teacher_id = uuid4()
        exam = draft_exam(status=ExamStatus.SEALED)

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(
                AcademicRepository,
                "list_teachers_by_ids",
                new=AsyncMock(
                    return_value=[
                        SimpleNamespace(id=teacher_id, status="active"),
                    ]
                ),
            ) as list_teachers,
            patch.object(
                ExamRepository,
                "list_invigilators_for_exam_and_teachers",
                new=AsyncMock(return_value=[]),
            ),
            patch.object(
                ExamRepository,
                "add_invigilators",
                new=AsyncMock(side_effect=lambda _db, rows: rows),
            ) as add_invigilators,
        ):
            rows = await ExamService.assign_invigilators(
                db,
                actor=admin,  # type: ignore[arg-type]
                exam_id=exam.id,
                teacher_ids=[teacher_id, teacher_id],
            )

        list_teachers.assert_awaited_once_with(db, [teacher_id], active_only=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].teacher_id, teacher_id)
        add_invigilators.assert_awaited_once()
        db.commit.assert_awaited_once()

    async def test_assign_invigilators_rejects_inactive_or_missing_teacher(
        self,
    ) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        teacher_id = uuid4()
        exam = draft_exam(status=ExamStatus.ACTIVE)

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(
                AcademicRepository,
                "list_teachers_by_ids",
                new=AsyncMock(return_value=[]),
            ),
            patch.object(
                ExamRepository,
                "add_invigilators",
                new=AsyncMock(),
            ) as add_invigilators,
        ):
            with self.assertRaises(AcademicScopeError):
                await ExamService.assign_invigilators(
                    db,
                    actor=admin,  # type: ignore[arg-type]
                    exam_id=exam.id,
                    teacher_ids=[teacher_id],
                )

        add_invigilators.assert_not_awaited()
        db.commit.assert_not_awaited()

    async def test_assign_invigilators_ignores_existing_duplicate(self) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        teacher_id = uuid4()
        exam = draft_exam(status=ExamStatus.SUSPENDED)
        existing = SimpleNamespace(exam_id=exam.id, teacher_id=teacher_id)

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(
                AcademicRepository,
                "list_teachers_by_ids",
                new=AsyncMock(
                    return_value=[SimpleNamespace(id=teacher_id, status="active")]
                ),
            ),
            patch.object(
                ExamRepository,
                "list_invigilators_for_exam_and_teachers",
                new=AsyncMock(return_value=[existing]),
            ),
            patch.object(
                ExamRepository,
                "add_invigilators",
                new=AsyncMock(return_value=[]),
            ) as add_invigilators,
        ):
            rows = await ExamService.assign_invigilators(
                db,
                actor=admin,  # type: ignore[arg-type]
                exam_id=exam.id,
                teacher_ids=[teacher_id],
            )

        add_invigilators.assert_awaited_once_with(db, [])
        self.assertEqual(rows, [existing])
        db.commit.assert_awaited_once()

    async def test_remove_invigilators_rejects_closed_exam(self) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        exam = draft_exam(status=ExamStatus.CLOSED)

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(
                ExamRepository,
                "remove_invigilators_by_teacher_ids",
                new=AsyncMock(),
            ) as remove_invigilators,
        ):
            with self.assertRaisesRegex(ExamStateError, "closed or cancelled"):
                await ExamService.remove_invigilators(
                    db,
                    actor=admin,  # type: ignore[arg-type]
                    exam_id=exam.id,
                    teacher_ids=[uuid4()],
                )

        remove_invigilators.assert_not_awaited()
        db.commit.assert_not_awaited()

    async def test_update_rejects_immutable_sealed_exam(self) -> None:
        db = AsyncMock()
        current_actor = actor()
        exam = draft_exam(status=ExamStatus.SEALED)

        with patch.object(
            ExamRepository,
            "get_exam_by_id",
            new=AsyncMock(return_value=exam),
        ):
            with self.assertRaisesRegex(ExamStateError, "DRAFT"):
                await ExamService.update_exam(
                    db,
                    actor=current_actor,  # type: ignore[arg-type]
                    payload=ExamUpdate(title="Edited"),
                    exam_id=exam.id,
                )

        db.commit.assert_not_awaited()

    async def test_create_revision_from_sealed_exam_returns_new_draft(self) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        exam = draft_exam(
            status=ExamStatus.SEALED,
            revision_number=1,
            component_maximum_score=10,
        )

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(
                ExamRepository,
                "get_latest_child_revision",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                AcademicAuthorizationService,
                "require_can_author_curriculum_subject",
                new=AsyncMock(),
            ),
            patch.object(
                ExamRepository,
                "add_exam",
                new=AsyncMock(side_effect=lambda _db, row: row),
            ),
        ):
            revision = await ExamService.create_revision(
                db,
                actor=admin,  # type: ignore[arg-type]
                exam_id=exam.id,
            )

        self.assertEqual(revision.status, ExamStatus.DRAFT)
        self.assertEqual(revision.revision_number, 2)
        self.assertEqual(revision.revision_of_exam_id, exam.id)
        self.assertIsNone(revision.component_maximum_score)
        db.commit.assert_awaited_once()

    async def test_activate_exam_requires_ready_roster(self) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        exam = draft_exam(
            status=ExamStatus.SEALED, roster_status=ExamRosterStatus.PENDING
        )

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(
                ExamRepository,
                "count_exam_questions",
                new=AsyncMock(),
            ) as count_questions,
        ):
            with self.assertRaisesRegex(ExamStateError, "READY"):
                await ExamService.activate_exam(
                    db,
                    actor=admin,  # type: ignore[arg-type]
                    exam_id=exam.id,
                )

        count_questions.assert_not_awaited()
        db.commit.assert_not_awaited()

    async def test_activate_exam_emits_outbox_event(self) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        exam = draft_exam(
            status=ExamStatus.SEALED,
            roster_status=ExamRosterStatus.READY,
            sealed_at=datetime.now(UTC),
            component_maximum_score=10,
        )

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(
                ExamRepository,
                "count_exam_questions",
                new=AsyncMock(return_value=exam.question_count),
            ),
            patch.object(
                ExamRepository,
                "save_exam",
                new=AsyncMock(side_effect=lambda _db, row: row),
            ),
            patch.object(
                RuntimeRepository,
                "add_outbox_event",
                new=AsyncMock(),
            ) as add_event,
        ):
            result = await ExamService.activate_exam(
                db,
                actor=admin,  # type: ignore[arg-type]
                exam_id=exam.id,
            )

        self.assertEqual(result.status, ExamStatus.ACTIVE)
        self.assertEqual(result.activated_by_actor_id, admin.id)
        add_event.assert_awaited_once()
        self.assertEqual(add_event.await_args.args[1].event_type, "exam.activated")
        db.commit.assert_awaited_once()

    async def test_suspend_resume_close_and_cancel_valid_transitions(self) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        exam = draft_exam(status=ExamStatus.ACTIVE)
        suspension = SimpleNamespace(
            resumed_at=None,
            resumed_by_actor_id=None,
            resume_reason=None,
        )

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(ExamRepository, "add_suspension", new=AsyncMock()),
            patch.object(
                ExamRepository,
                "save_exam",
                new=AsyncMock(side_effect=lambda _db, row: row),
            ),
            patch.object(
                RuntimeRepository,
                "add_outbox_event",
                new=AsyncMock(),
            ),
        ):
            await ExamService.suspend_exam(
                db,
                actor=admin,  # type: ignore[arg-type]
                exam_id=exam.id,
                reason="Network outage",
            )

        self.assertEqual(exam.status, ExamStatus.SUSPENDED)

        db.reset_mock()
        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(
                ExamRepository,
                "get_open_suspension_for_exam",
                new=AsyncMock(return_value=suspension),
            ),
            patch.object(ExamRepository, "save_suspension", new=AsyncMock()),
            patch.object(
                ExamRepository,
                "save_exam",
                new=AsyncMock(side_effect=lambda _db, row: row),
            ),
            patch.object(RuntimeRepository, "add_outbox_event", new=AsyncMock()),
        ):
            await ExamService.resume_exam(
                db,
                actor=admin,  # type: ignore[arg-type]
                exam_id=exam.id,
                reason="Recovered",
            )

        self.assertEqual(exam.status, ExamStatus.ACTIVE)
        self.assertIsNotNone(suspension.resumed_at)

        db.reset_mock()
        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(
                ExamRepository,
                "save_exam",
                new=AsyncMock(side_effect=lambda _db, row: row),
            ),
            patch.object(RuntimeRepository, "add_outbox_event", new=AsyncMock()),
        ):
            await ExamService.close_exam(
                db,
                actor=admin,  # type: ignore[arg-type]
                exam_id=exam.id,
            )

        self.assertEqual(exam.status, ExamStatus.CLOSED)

        cancellable = draft_exam(status=ExamStatus.SEALED)
        db.reset_mock()
        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=cancellable),
            ),
            patch.object(
                ExamRepository,
                "save_exam",
                new=AsyncMock(side_effect=lambda _db, row: row),
            ),
            patch.object(RuntimeRepository, "add_outbox_event", new=AsyncMock()),
        ):
            await ExamService.cancel_exam(
                db,
                actor=admin,  # type: ignore[arg-type]
                exam_id=cancellable.id,
                reason="Invalid paper",
            )

        self.assertEqual(cancellable.status, ExamStatus.CANCELLED)
        self.assertEqual(cancellable.cancellation_reason, "Invalid paper")

    async def test_suspend_requires_admin_and_active_exam(self) -> None:
        db = AsyncMock()
        current_actor = actor()

        with self.assertRaises(AcademicAuthorizationError):
            await ExamService.suspend_exam(
                db,
                actor=current_actor,  # type: ignore[arg-type]
                exam_id=uuid4(),
                reason="Nope",
            )

        admin = actor(role="admin")
        exam = draft_exam(status=ExamStatus.SEALED)
        with patch.object(
            ExamRepository,
            "get_exam_by_id",
            new=AsyncMock(return_value=exam),
        ):
            with self.assertRaisesRegex(ExamStateError, "ACTIVE"):
                await ExamService.suspend_exam(
                    db,
                    actor=admin,  # type: ignore[arg-type]
                    exam_id=exam.id,
                    reason="Nope",
                )

    async def test_cancel_requires_nonblank_reason(self) -> None:
        db = AsyncMock()
        admin = actor(role="admin")

        with self.assertRaisesRegex(ValueError, "reason is required"):
            await ExamService.cancel_exam(
                db,
                actor=admin,  # type: ignore[arg-type]
                exam_id=uuid4(),
                reason=" ",
            )

    async def test_lifecycle_rolls_back_on_integrity_failure(self) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        exam = draft_exam(
            status=ExamStatus.SEALED,
            roster_status=ExamRosterStatus.READY,
            sealed_at=datetime.now(UTC),
            component_maximum_score=10,
        )
        integrity_error = IntegrityError("insert", {}, Exception("boom"))

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=exam),
            ),
            patch.object(
                ExamRepository,
                "count_exam_questions",
                new=AsyncMock(return_value=exam.question_count),
            ),
            patch.object(
                ExamRepository,
                "save_exam",
                new=AsyncMock(side_effect=integrity_error),
            ),
            patch.object(
                RuntimeRepository,
                "add_outbox_event",
                new=AsyncMock(),
            ) as add_event,
        ):
            with self.assertRaisesRegex(ValueError, "could not be activated"):
                await ExamService.activate_exam(
                    db,
                    actor=admin,  # type: ignore[arg-type]
                    exam_id=exam.id,
                )

        add_event.assert_not_awaited()
        db.rollback.assert_awaited_once()
        db.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
