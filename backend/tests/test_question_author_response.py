from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app.domains.academics.repository import AcademicRepository  # noqa: E402
from app.domains.questions.models import Question, QuestionType  # noqa: E402
from app.domains.questions.repository import QuestionRepository  # noqa: E402
from app.domains.questions.response_builder import (  # noqa: E402
    build_question_response,
    build_question_responses,
)


class _ScalarRows:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


def _question(*, author_id):
    return Question(
        id=uuid4(),
        bank_id=uuid4(),
        question_type=QuestionType.SINGLE_CHOICE,
        prompt="Question",
        instruction=None,
        image_asset_id=None,
        version=1,
        created_by_actor_id=author_id,
        last_edited_by_actor_id=None,
        is_active=True,
    )


class QuestionAuthorResponseTests(unittest.IsolatedAsyncioTestCase):
    async def test_teacher_question_prefers_current_academic_name(self) -> None:
        membership_id = uuid4()
        teacher = SimpleNamespace(
            id=uuid4(),
            role="teacher",
            display_name="Ada Old Name",
            weave_membership_id=str(membership_id),
        )
        current_teacher = SimpleNamespace(
            id=membership_id,
            first_name="Ada",
            last_name="Okafor",
        )
        question = _question(author_id=teacher.id)

        with (
            patch.object(
                QuestionRepository,
                "list_options_for_question",
                new=AsyncMock(return_value=[]),
            ),
            patch.object(
                AcademicRepository,
                "list_teachers_by_ids",
                new=AsyncMock(return_value=[current_teacher]),
            ) as list_teachers,
        ):
            response = await build_question_response(
                object(),
                question,
                request_actor=teacher,
            )

        self.assertEqual(response.author_name, "Ada Okafor")
        self.assertEqual(response.created_by_actor_id, teacher.id)
        list_teachers.assert_awaited_once_with(
            object(),
            [membership_id],
            active_only=False,
        )

    async def test_teacher_question_falls_back_to_local_display_name(self) -> None:
        membership_id = uuid4()
        teacher = SimpleNamespace(
            id=uuid4(),
            role="teacher",
            display_name="Former Teacher Name",
            weave_membership_id=str(membership_id),
        )
        question = _question(author_id=teacher.id)
        db = object()

        with (
            patch.object(
                QuestionRepository,
                "list_options_for_question",
                new=AsyncMock(return_value=[]),
            ),
            patch.object(
                AcademicRepository,
                "list_teachers_by_ids",
                new=AsyncMock(return_value=[]),
            ),
        ):
            response = await build_question_response(
                db,
                question,
                request_actor=teacher,
            )

        self.assertEqual(response.author_name, "Former Teacher Name")

    async def test_admin_question_is_labeled_admin_not_personal_name(self) -> None:
        admin = SimpleNamespace(
            id=uuid4(),
            role="admin",
            display_name="Jane Administrator",
            weave_membership_id=None,
        )
        question = _question(author_id=admin.id)

        with patch.object(
            QuestionRepository,
            "list_options_for_question",
            new=AsyncMock(return_value=[]),
        ):
            response = await build_question_response(
                object(),
                question,
                request_actor=admin,
            )

        self.assertEqual(response.author_name, "Admin")

    async def test_bulk_questions_batch_actor_and_teacher_resolution(self) -> None:
        membership_id = uuid4()
        teacher = SimpleNamespace(
            id=uuid4(),
            role="teacher",
            display_name="Old Chidi Name",
            weave_membership_id=str(membership_id),
        )
        current_teacher = SimpleNamespace(
            id=membership_id,
            first_name="Chidi",
            last_name="Bello",
        )
        admin = SimpleNamespace(
            id=uuid4(),
            role="admin",
            display_name="Named Admin",
            weave_membership_id=None,
        )
        questions = [
            _question(author_id=teacher.id),
            _question(author_id=teacher.id),
            _question(author_id=admin.id),
        ]
        db = SimpleNamespace(
            execute=AsyncMock(return_value=_ScalarRows([teacher, admin]))
        )

        with (
            patch.object(
                QuestionRepository,
                "list_options_for_questions",
                new=AsyncMock(return_value=[]),
            ),
            patch.object(
                AcademicRepository,
                "list_teachers_by_ids",
                new=AsyncMock(return_value=[current_teacher]),
            ) as list_teachers,
        ):
            responses = await build_question_responses(db, questions)

        self.assertEqual(
            [response.author_name for response in responses],
            ["Chidi Bello", "Chidi Bello", "Admin"],
        )
        db.execute.assert_awaited_once()
        list_teachers.assert_awaited_once_with(
            db,
            [membership_id],
            active_only=False,
        )


if __name__ == "__main__":
    unittest.main()
