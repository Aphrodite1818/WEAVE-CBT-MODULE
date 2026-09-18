from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ["DEBUG"] = "false"

from app.domains.exams.execution_models import (  # noqa: E402
    ExamExecutionOperation,
    ExamOperationSource,
    ExamResultDisposition,
)
from app.domains.exams.execution_repository import ExamExecutionRepository  # noqa: E402
from app.domains.exams.execution_service import ExamExecutionService  # noqa: E402
from app.domains.exams.models import ExamStatus, ExamSuspensionSource  # noqa: E402
from app.domains.exams.repository import ExamRepository  # noqa: E402
from app.domains.runtime.repository import RuntimeRepository  # noqa: E402


def admin() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role="admin", is_active=True)


def exam(
    *, status: ExamStatus = ExamStatus.ACTIVE, activated_at=None
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        status=status,
        activated_at=activated_at,
        closed_at=None,
        closed_by_actor_id=None,
        cancelled_at=None,
        cancelled_by_actor_id=None,
        cancellation_reason=None,
    )


def control(**overrides) -> SimpleNamespace:
    values = {
        "operation": None,
        "operation_source": None,
        "operation_requested_at": None,
        "operation_requested_by_actor_id": None,
        "operation_reason": None,
        "operation_attempts": 0,
        "last_operation_attempt_at": None,
        "operation_error": None,
        "result_disposition": None,
        "results_decided_at": None,
        "results_decided_by_actor_id": None,
        "results_decision_reason": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class ExamExecutionLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_manual_close_stages_durable_closing_before_worker(self) -> None:
        db = AsyncMock()
        current_exam = exam()
        current_control = control()
        current_actor = admin()

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
            ),
            patch.object(
                ExamExecutionRepository,
                "get_or_create_control",
                new=AsyncMock(return_value=current_control),
            ),
            patch.object(ExamExecutionRepository, "save_control", new=AsyncMock()),
            patch.object(
                ExamRepository,
                "save_exam",
                new=AsyncMock(side_effect=lambda _db, row: row),
            ),
            patch.object(RuntimeRepository, "add_outbox_event", new=AsyncMock()),
        ):
            result = await ExamExecutionService.request_close(
                db,
                actor=current_actor,
                exam_id=current_exam.id,
            )

        self.assertIs(result, current_exam)
        self.assertEqual(current_exam.status, ExamStatus.CLOSING)
        self.assertEqual(current_control.operation, ExamExecutionOperation.CLOSING)
        self.assertEqual(current_control.operation_source, ExamOperationSource.ADMIN)
        self.assertEqual(
            current_control.operation_requested_by_actor_id,
            current_actor.id,
        )
        self.assertIsNotNone(current_control.operation_requested_at)
        db.commit.assert_awaited_once()

    async def test_cancel_stages_invalid_sitting_and_reason(self) -> None:
        db = AsyncMock()
        current_exam = exam(status=ExamStatus.SUSPENDED)
        current_control = control()
        current_actor = admin()

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
            ),
            patch.object(
                ExamExecutionRepository,
                "get_or_create_control",
                new=AsyncMock(return_value=current_control),
            ),
            patch.object(ExamExecutionRepository, "save_control", new=AsyncMock()),
            patch.object(
                ExamRepository,
                "save_exam",
                new=AsyncMock(side_effect=lambda _db, row: row),
            ),
            patch.object(RuntimeRepository, "add_outbox_event", new=AsyncMock()),
        ):
            await ExamExecutionService.request_cancel(
                db,
                actor=current_actor,
                exam_id=current_exam.id,
                reason="Paper compromised",
            )

        self.assertEqual(current_exam.status, ExamStatus.CANCELLING)
        self.assertEqual(current_control.operation, ExamExecutionOperation.CANCELLING)
        self.assertEqual(current_control.operation_reason, "Paper compromised")
        db.commit.assert_awaited_once()

    async def test_closed_results_require_explicit_approval(self) -> None:
        db = AsyncMock()
        current_exam = exam(status=ExamStatus.CLOSED)
        current_control = control(
            result_disposition=ExamResultDisposition.PENDING_REVIEW
        )
        current_actor = admin()

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
            ),
            patch.object(
                ExamExecutionRepository,
                "get_or_create_control",
                new=AsyncMock(return_value=current_control),
            ),
            patch.object(ExamExecutionRepository, "save_control", new=AsyncMock()),
            patch.object(RuntimeRepository, "add_outbox_event", new=AsyncMock()),
        ):
            approved = await ExamExecutionService.approve_results(
                db,
                actor=current_actor,
                exam_id=current_exam.id,
            )

        self.assertEqual(approved.result_disposition, ExamResultDisposition.APPROVED)
        self.assertEqual(approved.results_decided_by_actor_id, current_actor.id)
        self.assertIsNotNone(approved.results_decided_at)
        db.commit.assert_awaited_once()

    async def test_auto_close_requests_close_when_every_candidate_is_done(self) -> None:
        db = AsyncMock()
        current_exam = exam(status=ExamStatus.ACTIVE)
        db.scalar = AsyncMock(side_effect=[False, False])

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
            ),
            patch.object(
                ExamExecutionRepository,
                "get_control",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                ExamExecutionService,
                "request_automatic_close",
                new=AsyncMock(return_value=current_exam),
            ) as request_close,
        ):
            requested = await ExamExecutionService.evaluate_automatic_close(
                db,
                exam_id=current_exam.id,
            )

        self.assertTrue(requested)
        request_close.assert_awaited_once()

    async def test_auto_close_does_not_run_while_attempt_is_unfinished(self) -> None:
        db = AsyncMock()
        current_exam = exam(status=ExamStatus.ACTIVE)
        db.scalar = AsyncMock(return_value=True)

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
            ),
            patch.object(
                ExamExecutionRepository,
                "get_control",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                ExamExecutionService,
                "request_automatic_close",
                new=AsyncMock(),
            ) as request_close,
        ):
            requested = await ExamExecutionService.evaluate_automatic_close(
                db,
                exam_id=current_exam.id,
            )

        self.assertFalse(requested)
        request_close.assert_not_awaited()

    async def test_runtime_gap_backdates_system_suspension_to_last_healthy_heartbeat(
        self,
    ) -> None:
        db = AsyncMock()
        activated_at = datetime.now(UTC) - timedelta(minutes=20)
        last_healthy = activated_at + timedelta(minutes=5)
        current_exam = exam(status=ExamStatus.ACTIVE, activated_at=activated_at)

        result = MagicMock()
        result.scalars.return_value.all.return_value = [current_exam]
        db.execute = AsyncMock(return_value=result)

        with (
            patch.object(
                ExamRepository,
                "get_open_suspension_for_exam",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                ExamRepository,
                "add_suspension",
                new=AsyncMock(side_effect=lambda _db, row: row),
            ) as add_suspension,
            patch.object(
                ExamRepository,
                "save_exam",
                new=AsyncMock(side_effect=lambda _db, row: row),
            ),
            patch.object(
                ExamExecutionService,
                "_add_event",
                new=AsyncMock(),
            ),
        ):
            recovered = (
                await ExamExecutionService.suspend_active_exams_after_runtime_gap(
                    db,
                    outage_started_at=last_healthy,
                    reason="Server interruption",
                )
            )

        self.assertEqual(recovered, [current_exam.id])
        self.assertEqual(current_exam.status, ExamStatus.SUSPENDED)
        suspension = add_suspension.await_args.args[1]
        self.assertEqual(suspension.source, ExamSuspensionSource.SYSTEM)
        self.assertEqual(suspension.suspended_at, last_healthy)
        db.commit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
