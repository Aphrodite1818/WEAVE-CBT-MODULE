from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app.core.exceptions import AcademicAuthorizationError  # noqa: E402
from app.domains.academics.authorization import AcademicAuthorizationService  # noqa: E402
from app.domains.academics.repository import AcademicRepository  # noqa: E402


class AcademicAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_can_author_any_live_active_curriculum_subject(self) -> None:
        actor = SimpleNamespace(
            id=uuid4(),
            role="admin",
            is_active=True,
            weave_membership_id=None,
        )
        subject_id = uuid4()

        with patch.object(
            AcademicRepository,
            "get_curriculum_subject_by_id",
            new=AsyncMock(return_value=SimpleNamespace(id=subject_id, is_active=True)),
        ):
            await AcademicAuthorizationService.require_can_author_curriculum_subject(
                object(),  # type: ignore[arg-type]
                actor=actor,  # type: ignore[arg-type]
                curriculum_subject_id=subject_id,
            )

    async def test_teacher_with_current_assignment_can_author_shared_subject(self) -> None:
        membership_id = uuid4()
        subject_id = uuid4()
        actor = SimpleNamespace(
            id=uuid4(),
            role="teacher",
            is_active=True,
            weave_membership_id=str(membership_id),
        )

        with (
            patch.object(
                AcademicRepository,
                "get_curriculum_subject_by_id",
                new=AsyncMock(return_value=SimpleNamespace(id=subject_id, is_active=True)),
            ),
            patch.object(
                AcademicRepository,
                "get_teacher_by_membership_id",
                new=AsyncMock(return_value=SimpleNamespace(id=membership_id, status="active")),
            ),
            patch.object(
                AcademicRepository,
                "teacher_has_curriculum_subject_assignment",
                new=AsyncMock(return_value=True),
            ) as has_assignment,
        ):
            await AcademicAuthorizationService.require_can_author_curriculum_subject(
                object(),  # type: ignore[arg-type]
                actor=actor,  # type: ignore[arg-type]
                curriculum_subject_id=subject_id,
            )

        has_assignment.assert_awaited_once_with(
            ANY,
            membership_id,
            subject_id,
        )

    async def test_teacher_without_subject_assignment_is_rejected(self) -> None:
        membership_id = uuid4()
        subject_id = uuid4()
        actor = SimpleNamespace(
            id=uuid4(),
            role="teacher",
            is_active=True,
            weave_membership_id=str(membership_id),
        )

        with (
            patch.object(
                AcademicRepository,
                "get_curriculum_subject_by_id",
                new=AsyncMock(return_value=SimpleNamespace(id=subject_id, is_active=True)),
            ),
            patch.object(
                AcademicRepository,
                "get_teacher_by_membership_id",
                new=AsyncMock(return_value=SimpleNamespace(id=membership_id, status="active")),
            ),
            patch.object(
                AcademicRepository,
                "teacher_has_curriculum_subject_assignment",
                new=AsyncMock(return_value=False),
            ),
        ):
            with self.assertRaisesRegex(
                AcademicAuthorizationError,
                "does not have an active assignment",
            ):
                await AcademicAuthorizationService.require_can_author_curriculum_subject(
                    object(),  # type: ignore[arg-type]
                    actor=actor,  # type: ignore[arg-type]
                    curriculum_subject_id=subject_id,
                )

    async def test_exact_class_scope_requires_exact_teacher_assignment(self) -> None:
        membership_id = uuid4()
        class_id = uuid4()
        subject_id = uuid4()
        actor = SimpleNamespace(
            id=uuid4(),
            role="teacher",
            is_active=True,
            weave_membership_id=str(membership_id),
        )

        with (
            patch.object(
                AcademicRepository,
                "get_class_by_id",
                new=AsyncMock(return_value=SimpleNamespace(id=class_id, is_active=True)),
            ),
            patch.object(
                AcademicRepository,
                "get_curriculum_subject_by_id",
                new=AsyncMock(return_value=SimpleNamespace(id=subject_id, is_active=True)),
            ),
            patch.object(
                AcademicRepository,
                "get_teacher_by_membership_id",
                new=AsyncMock(return_value=SimpleNamespace(id=membership_id, status="active")),
            ),
            patch.object(
                AcademicRepository,
                "get_active_assignment_for_scope",
                new=AsyncMock(return_value=None),
            ),
        ):
            with self.assertRaisesRegex(
                AcademicAuthorizationError,
                "for this class and curriculum subject",
            ):
                await AcademicAuthorizationService.require_teacher_assignment_for_class(
                    object(),  # type: ignore[arg-type]
                    actor=actor,  # type: ignore[arg-type]
                    class_id=class_id,
                    curriculum_subject_id=subject_id,
                )


if __name__ == "__main__":
    unittest.main()
