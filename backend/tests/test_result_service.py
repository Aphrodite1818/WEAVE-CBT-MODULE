import os
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

from app.domains.attempts.models import AttemptStatus  # noqa: E402
from app.domains.results.service import ResultService  # noqa: E402


class ResultScoringTests(unittest.IsolatedAsyncioTestCase):
    async def test_multiple_choice_uses_exact_set_matching_and_component_normalization(self):
        attempt_id = uuid4()
        candidate_id = uuid4()
        exam_id = uuid4()
        q1, q2 = uuid4(), uuid4()
        a1, a2 = uuid4(), uuid4()
        q1a, q1b, q2a, q2b, q2c = [uuid4() for _ in range(5)]

        attempt = SimpleNamespace(id=attempt_id, status=AttemptStatus.SUBMITTED)
        candidate = SimpleNamespace(id=candidate_id)
        exam = SimpleNamespace(
            id=exam_id,
            assessment_component_id=uuid4(),
            component_maximum_score=Decimal("10.00"),
        )
        questions = [SimpleNamespace(id=q1), SimpleNamespace(id=q2)]
        options = [
            SimpleNamespace(id=q1a, attempt_question_id=q1, is_correct=True),
            SimpleNamespace(id=q1b, attempt_question_id=q1, is_correct=False),
            SimpleNamespace(id=q2a, attempt_question_id=q2, is_correct=True),
            SimpleNamespace(id=q2b, attempt_question_id=q2, is_correct=True),
            SimpleNamespace(id=q2c, attempt_question_id=q2, is_correct=False),
        ]
        answers = [
            SimpleNamespace(id=a1, attempt_question_id=q1),
            SimpleNamespace(id=a2, attempt_question_id=q2),
        ]
        selections = [
            SimpleNamespace(answer_id=a1, attempt_option_id=q1a),
            SimpleNamespace(answer_id=a2, attempt_option_id=q2a),
            SimpleNamespace(answer_id=a2, attempt_option_id=q2c),
        ]

        async def add_result(_db, result):
            result.id = uuid4()
            return result

        with patch(
            "app.domains.results.service.ResultRepository.get_result_by_attempt_id",
            AsyncMock(return_value=None),
        ), patch(
            "app.domains.results.service.AttemptRepository.list_question_allocations",
            AsyncMock(return_value=questions),
        ), patch(
            "app.domains.results.service.AttemptRepository.list_option_allocations_for_questions",
            AsyncMock(return_value=options),
        ), patch(
            "app.domains.results.service.AttemptRepository.list_answers_for_attempt",
            AsyncMock(return_value=answers),
        ), patch(
            "app.domains.results.service.AttemptRepository.list_selections_for_answers",
            AsyncMock(return_value=selections),
        ), patch(
            "app.domains.results.service.ResultRepository.add_result",
            AsyncMock(side_effect=add_result),
        ):
            result = await ResultService.calculate_for_submitted_attempt(
                AsyncMock(),
                attempt=attempt,
                candidate=candidate,
                exam=exam,
            )

        self.assertEqual(result.raw_score, 1)
        self.assertEqual(result.raw_max_score, 2)
        self.assertEqual(result.percentage, Decimal("50.00"))
        self.assertEqual(result.component_score, Decimal("5.00"))
        self.assertEqual(result.component_maximum_score, Decimal("10.00"))


if __name__ == "__main__":
    unittest.main()
