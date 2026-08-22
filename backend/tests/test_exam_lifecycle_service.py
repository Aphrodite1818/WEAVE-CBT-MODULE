from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime
from decimal import Decimal
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
    ExamInvigilatorAssignment,
    ExamResponse,
)
from app.domains.exams.service import ExamService  # noqa: E402
from app.domains.exams.timetable_service import ExamTimetableService  # noqa: E402
from app.domains.questions.models import QuestionType  # noqa: E402
from app.domains.questions.repository import QuestionRepository  # noqa: E402
from app.domains.runtime.repository import RuntimeRepository  # noqa: E402
from app.domains.sync.repository import SyncRepository  # noqa: E402


def actor(*, role: str = "teacher") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        role=role,
        is_active=True,
        weave_membership_id=str(uuid4()) if role == "teacher" else None,
    )


def exam(**overrides) -> SimpleNamespace:
    values = {
        "id": uuid4(),
        "session_id": uuid4(),
        "term_id": uuid4(),
        "curriculum_subject_id": uuid4(),
        "assessment_scheme_id": uuid4(),
        "assessment_component_id": uuid4(),
        "question_bank_id": uuid4(),
        "question_selection_mode": ExamQuestionSelectionMode.RANDOM,
        "question_count": 1,
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
        "roster_prepared_at": None,
        "roster_error": None,
        "revision_number": 1,
        "revision_of_exam_id": None,
        "created_by_actor_id": uuid4(),
        "submitted_by_actor_id": None,
        "submitted_at": None,
        "sealed_by_actor_id": None,
        "sealed_at": None,
        "activated_by_actor_id": None,
        "activated_at": None,
        "closed_by_actor_id": None,
        "closed_at": None,
        "cancelled_by_actor_id": None,
        "cancelled_at": None,
        "cancellation_reason": None,
        "component_maximum_score": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def academic_scope(current_exam: SimpleNamespace) -> dict[str, SimpleNamespace]:
    return {
        "session": SimpleNamespace(id=current_exam.session_id),
        "term": SimpleNamespace(
            id=current_exam.term_id,
            academic_session_id=current_exam.session_id,
        ),
        "scheme": SimpleNamespace(
            id=current_exam.assessment_scheme_id,
            status="active",
        ),
        "component": SimpleNamespace(
            id=current_exam.assessment_component_id,
            assessment_scheme_id=current_exam.assessment_scheme_id,
            is_active=True,
            maximum_score=Decimal("10.00"),
        ),
        "bank": SimpleNamespace(
            id=current_exam.question_bank_id,
            is_active=True,
            curriculum_subject_id=current_exam.curriculum_subject_id,
        ),
    }


class ExamLifecycleSchemaTests(unittest.TestCase):
    def test_invigilator_assignment_accepts_multiple_teacher_ids(self) -> None:
        first = uuid4()
        second = uuid4()
        payload = ExamInvigilatorAssignment(teacher_ids=[first, second])
        self.assertEqual(payload.teacher_ids, [first, second])

    def test_exam_response_exposes_lifecycle_audit_fields(self) -> None:
        expected = {
            "submitted_by_actor_id",
            "submitted_at",
            "sealed_by_actor_id",
            "sealed_at",
            "activated_by_actor_id",
            "activated_at",
            "closed_by_actor_id",
            "closed_at",
            "cancelled_by_actor_id",
            "cancelled_at",
            "cancellation_reason",
        }
        self.assertTrue(expected.issubset(ExamResponse.model_fields))


class ExamLifecycleServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_submit_random_exam_records_submission_metadata(self) -> None:
        db = AsyncMock()
        current_actor = actor()
        current_exam = exam(status=ExamStatus.DRAFT)
        scope = academic_scope(current_exam)

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
            ),
            patch.object(
                AcademicAuthorizationService,
                "require_can_author_curriculum_subject",
                new=AsyncMock(),
            ),
            patch.object(
                AcademicRepository,
                "get_session_by_id",
                new=AsyncMock(return_value=scope["session"]),
            ),
            patch.object(
                AcademicRepository,
                "get_term_by_id",
                new=AsyncMock(return_value=scope["term"]),
            ),
            patch.object(
                AcademicRepository,
                "get_assessment_scheme_by_id",
                new=AsyncMock(return_value=scope["scheme"]),
            ),
            patch.object(
                AcademicRepository,
                "get_component_by_id",
                new=AsyncMock(return_value=scope["component"]),
            ),
            patch.object(
                QuestionRepository,
                "get_bank_by_id",
                new=AsyncMock(return_value=scope["bank"]),
            ),
            patch.object(
                QuestionRepository,
                "count_questions_for_bank",
                new=AsyncMock(return_value=1),
            ),
            patch.object(
                ExamRepository,
                "list_question_selections",
                new=AsyncMock(return_value=[]),
            ),
            patch.object(
                ExamRepository,
                "save_exam",
                new=AsyncMock(side_effect=lambda _db, row: row),
            ),
        ):
            result = await ExamService.submit_exam(
                db,
                actor=current_actor,  # type: ignore[arg-type]
                exam_id=current_exam.id,
            )

        self.assertEqual(result.status, ExamStatus.SUBMITTED)
        self.assertEqual(result.submitted_by_actor_id, current_actor.id)
        self.assertIsNotNone(result.submitted_at)
        db.commit.assert_awaited_once()

    async def test_submit_manual_exam_rejects_incomplete_selection(self) -> None:
        db = AsyncMock()
        current_actor = actor()
        current_exam = exam(
            status=ExamStatus.DRAFT,
            question_selection_mode=ExamQuestionSelectionMode.MANUAL,
            question_count=2,
        )
        scope = academic_scope(current_exam)

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
            ),
            patch.object(
                AcademicAuthorizationService,
                "require_can_author_curriculum_subject",
                new=AsyncMock(),
            ),
            patch.object(
                AcademicRepository,
                "get_session_by_id",
                new=AsyncMock(return_value=scope["session"]),
            ),
            patch.object(
                AcademicRepository,
                "get_term_by_id",
                new=AsyncMock(return_value=scope["term"]),
            ),
            patch.object(
                AcademicRepository,
                "get_assessment_scheme_by_id",
                new=AsyncMock(return_value=scope["scheme"]),
            ),
            patch.object(
                AcademicRepository,
                "get_component_by_id",
                new=AsyncMock(return_value=scope["component"]),
            ),
            patch.object(
                QuestionRepository,
                "get_bank_by_id",
                new=AsyncMock(return_value=scope["bank"]),
            ),
            patch.object(
                ExamRepository,
                "list_question_selections",
                new=AsyncMock(
                    return_value=[SimpleNamespace(question_id=uuid4(), position=1)]
                ),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "exactly 2 selected"):
                await ExamService.submit_exam(
                    db,
                    actor=current_actor,  # type: ignore[arg-type]
                    exam_id=current_exam.id,
                )

        db.commit.assert_not_awaited()

    async def test_delete_draft_allows_any_current_authorized_teacher(self) -> None:
        db = AsyncMock()
        current_actor = actor()
        current_exam = exam(created_by_actor_id=uuid4())

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
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
                exam_id=current_exam.id,
            )

        authorize.assert_awaited_once_with(
            db,
            actor=current_actor,
            curriculum_subject_id=current_exam.curriculum_subject_id,
        )
        delete_exam.assert_awaited_once_with(db, current_exam)
        db.commit.assert_awaited_once()

    async def test_assign_invigilator_needs_school_membership_not_assignment(
        self,
    ) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        teacher_id = uuid4()
        current_exam = exam(status=ExamStatus.SEALED)

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
            ),
            patch.object(
                AcademicRepository,
                "list_teachers_by_ids",
                new=AsyncMock(return_value=[SimpleNamespace(id=teacher_id)]),
            ) as teachers,
            patch.object(
                ExamRepository,
                "list_invigilators_for_exam_and_teachers",
                new=AsyncMock(return_value=[]),
            ),
            patch.object(
                ExamRepository,
                "add_invigilators",
                new=AsyncMock(side_effect=lambda _db, rows: rows),
            ),
        ):
            rows = await ExamService.assign_invigilators(
                db,
                actor=admin,  # type: ignore[arg-type]
                exam_id=current_exam.id,
                teacher_ids=[teacher_id],
            )

        teachers.assert_awaited_once_with(db, [teacher_id], active_only=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].teacher_id, teacher_id)
        db.commit.assert_awaited_once()

    async def test_return_to_draft_is_admin_only_and_clears_submission(self) -> None:
        db = AsyncMock()
        teacher = actor()
        current_exam = exam(
            status=ExamStatus.SUBMITTED,
            submitted_by_actor_id=uuid4(),
            submitted_at=datetime.now(UTC),
        )

        with self.assertRaises(AcademicAuthorizationError):
            await ExamService.return_exam_to_draft(
                db,
                actor=teacher,  # type: ignore[arg-type]
                exam_id=current_exam.id,
            )

        admin = actor(role="admin")
        db.reset_mock()
        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
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
                exam_id=current_exam.id,
            )

        self.assertEqual(result.status, ExamStatus.DRAFT)
        self.assertIsNone(result.submitted_by_actor_id)
        self.assertIsNone(result.submitted_at)

    async def test_seal_holds_sync_lock_before_reading_academic_scope(self) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        current_exam = exam(status=ExamStatus.SUBMITTED)
        scope = academic_scope(current_exam)
        source_question = SimpleNamespace(
            id=uuid4(),
            bank_id=current_exam.question_bank_id,
            version=3,
            question_type=QuestionType.SINGLE_CHOICE,
            prompt="2 + 2?",
            instruction=None,
            image_asset_id=None,
        )
        source_option = SimpleNamespace(
            question_id=source_question.id,
            position=1,
            text="4",
            is_correct=True,
        )
        classroom = SimpleNamespace(id=uuid4())
        offering = SimpleNamespace(id=uuid4())
        frozen_id = uuid4()
        order: list[str] = []

        async def record_lock(*_args, **_kwargs):
            order.append("sync_lock")

        async def record_authorize(*_args, **_kwargs):
            order.append("authorize")

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
            ),
            patch.object(
                SyncRepository,
                "acquire_apply_lock",
                new=AsyncMock(side_effect=record_lock),
            ) as acquire_sync_lock,
            patch.object(
                AcademicAuthorizationService,
                "require_can_author_curriculum_subject",
                new=AsyncMock(side_effect=record_authorize),
            ),
            patch.object(
                AcademicRepository,
                "get_session_by_id",
                new=AsyncMock(return_value=scope["session"]),
            ),
            patch.object(
                AcademicRepository,
                "get_term_by_id",
                new=AsyncMock(return_value=scope["term"]),
            ),
            patch.object(
                AcademicRepository,
                "get_assessment_scheme_by_id",
                new=AsyncMock(return_value=scope["scheme"]),
            ),
            patch.object(
                AcademicRepository,
                "get_component_by_id",
                new=AsyncMock(return_value=scope["component"]),
            ),
            patch.object(
                QuestionRepository,
                "get_bank_by_id",
                new=AsyncMock(return_value=scope["bank"]),
            ),
            patch.object(
                ExamRepository,
                "count_exam_questions",
                new=AsyncMock(return_value=0),
            ),
            patch.object(
                ExamService,
                "_resolve_questions_for_sealing",
                new=AsyncMock(return_value=[source_question]),
            ),
            patch.object(
                ExamService,
                "_validate_questions_for_sealing",
                new=AsyncMock(return_value={source_question.id: [source_option]}),
            ),
            patch.object(
                AcademicRepository,
                "list_classes_for_curriculum_subject",
                new=AsyncMock(return_value=[classroom]),
            ),
            patch.object(
                AcademicRepository,
                "get_offering_for_class_scope",
                new=AsyncMock(return_value=offering),
            ),
            patch.object(
                AcademicRepository,
                "get_active_assignment_for_class_curriculum_subject",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                ExamRepository,
                "add_exam_questions",
                new=AsyncMock(
                    return_value=[
                        SimpleNamespace(
                            id=frozen_id,
                            source_question_id=source_question.id,
                        )
                    ]
                ),
            ),
            patch.object(
                ExamRepository,
                "add_exam_question_options",
                new=AsyncMock(),
            ),
            patch.object(
                ExamRepository,
                "add_target_classes",
                new=AsyncMock(),
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
            result = await ExamService.seal_exam(
                db,
                actor=admin,  # type: ignore[arg-type]
                exam_id=current_exam.id,
            )

        acquire_sync_lock.assert_awaited_once_with(db)
        self.assertLess(order.index("sync_lock"), order.index("authorize"))
        self.assertEqual(result.status, ExamStatus.SEALED)
        self.assertEqual(result.roster_status, ExamRosterStatus.PENDING)
        self.assertEqual(result.component_maximum_score, Decimal("10.00"))

        outbox_event = add_event.await_args.args[1]
        self.assertEqual(outbox_event.event_type, "exam.sealed")
        self.assertEqual(outbox_event.payload["actor_id"], str(admin.id))
        self.assertIn("occurred_at", outbox_event.payload)
        self.assertNotIn("sealed_by_actor_id", outbox_event.payload)
        self.assertEqual(outbox_event.payload["target_class_count"], 1)
        db.commit.assert_awaited_once()

    async def test_seal_rolls_back_if_snapshot_transaction_hits_integrity_error(
        self,
    ) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        current_exam = exam(status=ExamStatus.SUBMITTED)
        scope = academic_scope(current_exam)
        source_question = SimpleNamespace(
            id=uuid4(),
            bank_id=current_exam.question_bank_id,
            version=1,
            question_type=QuestionType.SINGLE_CHOICE,
            prompt="Question",
            instruction=None,
            image_asset_id=None,
        )
        option = SimpleNamespace(
            question_id=source_question.id,
            position=1,
            text="Answer",
            is_correct=True,
        )
        classroom = SimpleNamespace(id=uuid4())
        offering = SimpleNamespace(id=uuid4())
        integrity_error = IntegrityError("insert", {}, Exception("boom"))

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
            ),
            patch.object(SyncRepository, "acquire_apply_lock", new=AsyncMock()),
            patch.object(
                AcademicAuthorizationService,
                "require_can_author_curriculum_subject",
                new=AsyncMock(),
            ),
            patch.object(
                AcademicRepository,
                "get_session_by_id",
                new=AsyncMock(return_value=scope["session"]),
            ),
            patch.object(
                AcademicRepository,
                "get_term_by_id",
                new=AsyncMock(return_value=scope["term"]),
            ),
            patch.object(
                AcademicRepository,
                "get_assessment_scheme_by_id",
                new=AsyncMock(return_value=scope["scheme"]),
            ),
            patch.object(
                AcademicRepository,
                "get_component_by_id",
                new=AsyncMock(return_value=scope["component"]),
            ),
            patch.object(
                QuestionRepository,
                "get_bank_by_id",
                new=AsyncMock(return_value=scope["bank"]),
            ),
            patch.object(
                ExamRepository,
                "count_exam_questions",
                new=AsyncMock(return_value=0),
            ),
            patch.object(
                ExamService,
                "_resolve_questions_for_sealing",
                new=AsyncMock(return_value=[source_question]),
            ),
            patch.object(
                ExamService,
                "_validate_questions_for_sealing",
                new=AsyncMock(return_value={source_question.id: [option]}),
            ),
            patch.object(
                AcademicRepository,
                "list_classes_for_curriculum_subject",
                new=AsyncMock(return_value=[classroom]),
            ),
            patch.object(
                AcademicRepository,
                "get_offering_for_class_scope",
                new=AsyncMock(return_value=offering),
            ),
            patch.object(
                AcademicRepository,
                "get_active_assignment_for_class_curriculum_subject",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                ExamRepository,
                "add_exam_questions",
                new=AsyncMock(
                    return_value=[
                        SimpleNamespace(
                            id=uuid4(),
                            source_question_id=source_question.id,
                        )
                    ]
                ),
            ),
            patch.object(
                ExamRepository,
                "add_exam_question_options",
                new=AsyncMock(),
            ),
            patch.object(
                ExamRepository,
                "add_target_classes",
                new=AsyncMock(side_effect=integrity_error),
            ),
            patch.object(
                ExamRepository,
                "save_exam",
                new=AsyncMock(),
            ) as save_exam,
            patch.object(
                RuntimeRepository,
                "add_outbox_event",
                new=AsyncMock(),
            ) as add_event,
        ):
            with self.assertRaisesRegex(ValueError, "could not be sealed"):
                await ExamService.seal_exam(
                    db,
                    actor=admin,  # type: ignore[arg-type]
                    exam_id=current_exam.id,
                )

        db.rollback.assert_awaited_once()
        db.commit.assert_not_awaited()
        save_exam.assert_not_awaited()
        add_event.assert_not_awaited()

    async def test_revision_creation_rejects_active_suspended_and_closed_leaf(
        self,
    ) -> None:
        admin = actor(role="admin")

        for lifecycle_status in (
            ExamStatus.ACTIVE,
            ExamStatus.SUSPENDED,
            ExamStatus.CLOSED,
        ):
            with self.subTest(status=lifecycle_status):
                db = AsyncMock()
                current_exam = exam(status=lifecycle_status)
                with (
                    patch.object(
                        ExamRepository,
                        "get_exam_by_id",
                        new=AsyncMock(return_value=current_exam),
                    ),
                    patch.object(
                        ExamRepository,
                        "get_latest_child_revision",
                        new=AsyncMock(return_value=None),
                    ),
                ):
                    with self.assertRaisesRegex(
                        ExamStateError,
                        "latest SEALED or CANCELLED",
                    ):
                        await ExamService.create_revision(
                            db,
                            actor=admin,  # type: ignore[arg-type]
                            exam_id=current_exam.id,
                        )
                db.commit.assert_not_awaited()

    async def test_cancelled_leaf_can_create_next_revision(self) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        current_exam = exam(
            status=ExamStatus.CANCELLED,
            revision_number=2,
            revision_of_exam_id=uuid4(),
        )

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
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
                exam_id=current_exam.id,
            )

        self.assertEqual(revision.status, ExamStatus.DRAFT)
        self.assertEqual(revision.revision_number, 3)
        self.assertEqual(revision.revision_of_exam_id, current_exam.id)
        db.commit.assert_awaited_once()

    async def test_activate_rejects_non_latest_revision(self) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        current_exam = exam(
            status=ExamStatus.SEALED,
            roster_status=ExamRosterStatus.READY,
            sealed_at=datetime.now(UTC),
            component_maximum_score=Decimal("10.00"),
        )
        child = exam(
            status=ExamStatus.DRAFT,
            revision_number=2,
            revision_of_exam_id=current_exam.id,
        )

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
            ),
            patch.object(
                ExamRepository,
                "get_latest_child_revision",
                new=AsyncMock(side_effect=[child, None]),
            ),
            patch.object(
                ExamRepository,
                "count_exam_questions",
                new=AsyncMock(),
            ) as count_questions,
        ):
            with self.assertRaisesRegex(ExamStateError, "latest examination revision"):
                await ExamService.activate_exam(
                    db,
                    actor=admin,  # type: ignore[arg-type]
                    exam_id=current_exam.id,
                )

        count_questions.assert_not_awaited()
        db.commit.assert_not_awaited()

    async def test_suspended_close_requires_open_suspension(self) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        current_exam = exam(status=ExamStatus.SUSPENDED)

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
            ),
            patch.object(
                ExamRepository,
                "get_open_suspension_for_exam",
                new=AsyncMock(return_value=None),
            ),
        ):
            with self.assertRaisesRegex(ExamStateError, "no open suspension"):
                await ExamService.close_exam(
                    db,
                    actor=admin,  # type: ignore[arg-type]
                    exam_id=current_exam.id,
                )

        db.commit.assert_not_awaited()

    async def test_suspended_cancel_requires_open_suspension(self) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        current_exam = exam(status=ExamStatus.SUSPENDED)

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
            ),
            patch.object(
                ExamRepository,
                "get_open_suspension_for_exam",
                new=AsyncMock(return_value=None),
            ),
        ):
            with self.assertRaisesRegex(ExamStateError, "no open suspension"):
                await ExamService.cancel_exam(
                    db,
                    actor=admin,  # type: ignore[arg-type]
                    exam_id=current_exam.id,
                    reason="Invalid sitting",
                )

        db.commit.assert_not_awaited()

    async def test_close_rolls_back_if_suspension_flush_fails(self) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        current_exam = exam(status=ExamStatus.SUSPENDED)
        suspension = SimpleNamespace(
            resumed_at=None,
            resumed_by_actor_id=None,
            resume_reason=None,
        )
        integrity_error = IntegrityError("update", {}, Exception("boom"))

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
            ),
            patch.object(
                ExamRepository,
                "get_open_suspension_for_exam",
                new=AsyncMock(return_value=suspension),
            ),
            patch.object(
                ExamRepository,
                "save_suspension",
                new=AsyncMock(side_effect=integrity_error),
            ),
            patch.object(
                ExamRepository,
                "save_exam",
                new=AsyncMock(),
            ) as save_exam,
        ):
            with self.assertRaisesRegex(ValueError, "could not be closed"):
                await ExamService.close_exam(
                    db,
                    actor=admin,  # type: ignore[arg-type]
                    exam_id=current_exam.id,
                )

        db.rollback.assert_awaited_once()
        save_exam.assert_not_awaited()
        db.commit.assert_not_awaited()

    async def test_activate_requires_ready_roster(self) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        current_exam = exam(
            status=ExamStatus.SEALED,
            roster_status=ExamRosterStatus.PENDING,
            sealed_at=datetime.now(UTC),
            component_maximum_score=Decimal("10.00"),
        )

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
            ),
            patch.object(
                ExamRepository,
                "get_latest_child_revision",
                new=AsyncMock(return_value=None),
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
                    exam_id=current_exam.id,
                )

        count_questions.assert_not_awaited()
        db.commit.assert_not_awaited()

    async def test_activate_emits_consistent_outbox_event(self) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        current_exam = exam(
            status=ExamStatus.SEALED,
            roster_status=ExamRosterStatus.READY,
            sealed_at=datetime.now(UTC),
            component_maximum_score=Decimal("10.00"),
        )

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
            ),
            patch.object(
                ExamRepository,
                "get_latest_child_revision",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                ExamRepository,
                "count_exam_questions",
                new=AsyncMock(return_value=current_exam.question_count),
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
            patch.object(
                ExamTimetableService,
                "require_level_free",
                new=AsyncMock(),
            ) as require_level_free,
        ):
            result = await ExamService.activate_exam(
                db,
                actor=admin,  # type: ignore[arg-type]
                exam_id=current_exam.id,
            )

        self.assertEqual(result.status, ExamStatus.ACTIVE)
        require_level_free.assert_awaited_once_with(db, exam_id=current_exam.id)
        event = add_event.await_args.args[1]
        self.assertEqual(event.event_type, "exam.activated")
        self.assertEqual(event.payload["actor_id"], str(admin.id))
        self.assertIn("occurred_at", event.payload)
        db.commit.assert_awaited_once()

    async def test_suspend_resume_close_and_cancel_valid_transitions(self) -> None:
        admin = actor(role="admin")

        # ACTIVE -> SUSPENDED
        db = AsyncMock()
        current_exam = exam(status=ExamStatus.ACTIVE)
        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
            ),
            patch.object(ExamRepository, "add_suspension", new=AsyncMock()),
            patch.object(
                ExamRepository,
                "save_exam",
                new=AsyncMock(side_effect=lambda _db, row: row),
            ),
            patch.object(RuntimeRepository, "add_outbox_event", new=AsyncMock()),
        ):
            await ExamService.suspend_exam(
                db,
                actor=admin,  # type: ignore[arg-type]
                exam_id=current_exam.id,
                reason="Network outage",
            )
        self.assertEqual(current_exam.status, ExamStatus.SUSPENDED)

        # SUSPENDED -> ACTIVE
        suspension = SimpleNamespace(
            resumed_at=None,
            resumed_by_actor_id=None,
            resume_reason=None,
        )
        db = AsyncMock()
        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
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
            patch.object(
                ExamTimetableService,
                "require_level_free",
                new=AsyncMock(),
            ) as require_level_free,
        ):
            await ExamService.resume_exam(
                db,
                actor=admin,  # type: ignore[arg-type]
                exam_id=current_exam.id,
                reason="Recovered",
            )
        self.assertEqual(current_exam.status, ExamStatus.ACTIVE)
        self.assertEqual(suspension.resume_reason, "Recovered")
        require_level_free.assert_awaited_once_with(db, exam_id=current_exam.id)

        # ACTIVE -> CLOSED
        db = AsyncMock()
        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
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
                exam_id=current_exam.id,
            )
        self.assertEqual(current_exam.status, ExamStatus.CLOSED)
        self.assertIsNotNone(current_exam.closed_at)

        # SEALED -> CANCELLED
        cancellable = exam(status=ExamStatus.SEALED)
        db = AsyncMock()
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

    async def test_manual_sealing_resolution_preserves_selection_order_and_locks(
        self,
    ) -> None:
        db = AsyncMock()
        first_id = uuid4()
        second_id = uuid4()
        current_exam = exam(
            status=ExamStatus.SUBMITTED,
            question_selection_mode=ExamQuestionSelectionMode.MANUAL,
            question_count=2,
        )
        selections = [
            SimpleNamespace(question_id=first_id, position=1),
            SimpleNamespace(question_id=second_id, position=2),
        ]
        first = SimpleNamespace(id=first_id)
        second = SimpleNamespace(id=second_id)

        with (
            patch.object(
                ExamRepository,
                "list_question_selections",
                new=AsyncMock(return_value=selections),
            ),
            patch.object(
                QuestionRepository,
                "list_questions_by_ids",
                new=AsyncMock(return_value=[second, first]),
            ) as list_questions,
        ):
            resolved = await ExamService._resolve_questions_for_sealing(
                db,
                exam=current_exam,
            )

        self.assertEqual([question.id for question in resolved], [first_id, second_id])
        list_questions.assert_awaited_once_with(
            db,
            [first_id, second_id],
            active_only=True,
            lock=True,
        )

    async def test_assign_invigilators_rejects_missing_or_inactive_teacher(
        self,
    ) -> None:
        db = AsyncMock()
        admin = actor(role="admin")
        teacher_id = uuid4()
        current_exam = exam(status=ExamStatus.ACTIVE)

        with (
            patch.object(
                ExamRepository,
                "get_exam_by_id",
                new=AsyncMock(return_value=current_exam),
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
                    exam_id=current_exam.id,
                    teacher_ids=[teacher_id],
                )

        add_invigilators.assert_not_awaited()
        db.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
