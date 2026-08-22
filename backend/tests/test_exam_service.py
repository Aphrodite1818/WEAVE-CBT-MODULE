from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ["DEBUG"] = "false"

from app.domains.academics.authorization import (  # noqa: E402
    AcademicAuthorizationService,
)
from app.domains.academics.repository import AcademicRepository  # noqa: E402
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
        start_at = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)

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
        start_at = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
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


if __name__ == "__main__":
    unittest.main()
